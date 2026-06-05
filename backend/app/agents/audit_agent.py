from datetime import date
from decimal import Decimal

from flask import abort

from ..extensions import db
from ..models import Material, User
from ..state_machine import MaterialStatus, assert_transition
from .responses import agent_response
from .risk_agent import RiskAgent
from .scoring_rules import CATEGORY_SCORE_CAPS, ScoreDecision, apply_existing_constraints, score_material


class AuditAgent:
    def __init__(self, risk_agent: RiskAgent | None = None):
        self.risk_agent = risk_agent or RiskAgent()

    def upload_material(self, user: User, payload: dict) -> dict:
        if user.role != "student":
            abort(403, description="仅学生可上传材料")

        title = str(payload.get("title", "")).strip()
        category = str(payload.get("category", "")).strip()
        certificate_no = str(payload.get("certificateNo", "")).strip()
        if not title or not category or not certificate_no:
            abort(400, description="标题、五育类别、证书编号不能为空")
        if category not in CATEGORY_SCORE_CAPS:
            abort(400, description="五育类别不合法")

        inspection = self.risk_agent.inspect_material(payload)
        self.risk_agent.assert_upload_allowed(inspection)
        decision = self._score_decision(user, payload)

        material = Material(
            student_id=user.id,
            title=title,
            category=category,
            description=str(payload.get("description", "")).strip(),
            certificate_no=certificate_no,
            issued_at=date.fromisoformat(payload["issuedAt"]),
            expires_at=date.fromisoformat(payload["expiresAt"]) if payload.get("expiresAt") else None,
            file_name=str(payload.get("fileName", "")).strip() or None,
            file_url=str(payload.get("fileUrl", "")).strip() or None,
            ocr_text=self._mock_ocr(payload),
            score=decision.final_score,
            status=MaterialStatus.DRAFT.value,
            risk_level=inspection["riskLevel"],
            risk_reasons=[*inspection["riskReasons"], *decision.reasons],
        )
        assert_transition(material.status, MaterialStatus.SUBMITTED)
        material.status = MaterialStatus.SUBMITTED.value
        db.session.add(material)
        db.session.commit()
        total = self._student_total(user)
        return agent_response(
            agent="Audit Agent",
            message=f"【{title}（{decision.level}/{decision.role}）】+{decision.final_score:.2f}分\n当前综测总分：{total:.2f}分",
            suggestions_key="audit",
            data={
                "material": material.to_dict(),
                "scoreDecision": decision.to_dict(),
                "totalScore": total,
            },
        )

    def list_materials(self, user: User) -> dict:
        query = Material.query
        if user.role == "student":
            query = query.filter_by(student_id=user.id)
        materials = query.order_by(Material.updated_at.desc()).all()
        return agent_response(
            agent="Audit Agent",
            message="材料列表已加载",
            suggestions_key="audit",
            data={"items": [item.to_dict() for item in materials]},
        )

    def student_summary(self, user: User) -> dict:
        materials = Material.query.filter_by(student_id=user.id).all()
        approved = [item for item in materials if item.status in {MaterialStatus.APPROVED.value, MaterialStatus.PUBLICIZING.value, MaterialStatus.PUBLICITY_ENDED.value}]
        total = sum(float(item.score) for item in approved)
        return agent_response(
            agent="Audit Agent",
            message=f"当前综测总分：{round(total, 2):.2f}分",
            suggestions_key="audit",
            data={
            "status": self._summary_status(materials),
            "totalScore": round(total, 2),
            "materials": [item.to_dict(include_student=False) for item in materials],
            },
        )

    def _score_decision(self, user: User, payload: dict) -> ScoreDecision:
        decision = score_material(payload)
        query = Material.query.filter_by(student_id=user.id)
        existing_rule_score = Decimal("0")
        existing_event_score: Decimal | None = None
        contest_count = 0
        for material in query.all():
            if material.status == MaterialStatus.REJECTED.value:
                continue
            existing_decision = self._existing_decision(material)
            if not existing_decision:
                continue
            if existing_decision.rule_key == decision.rule_key:
                existing_rule_score += Decimal(str(material.score or 0))
            if decision.rule_name == "英语等级证书" and existing_decision.rule_name == "英语等级证书":
                existing_rule_score = max(existing_rule_score, Decimal(str(material.score or 0)))
            if decision.rule_name == "学科竞赛" and existing_decision.rule_name == "学科竞赛":
                contest_count += 1
            if decision.event_key and existing_decision.event_key == decision.event_key:
                score = Decimal(str(material.score or 0))
                existing_event_score = score if existing_event_score is None else max(existing_event_score, score)

        if decision.rule_name == "学科竞赛" and contest_count >= 5:
            return ScoreDecision(
                category=decision.category,
                rule_name=decision.rule_name,
                level=decision.level,
                role=decision.role,
                raw_score=decision.raw_score,
                final_score=Decimal("0.00"),
                cap=decision.cap,
                rule_key=decision.rule_key,
                event_key=decision.event_key,
                reasons=[*decision.reasons, "学科竞赛最多累计 5 项，本次不再加分"],
                confidence=decision.confidence,
            )

        return apply_existing_constraints(
            decision,
            existing_rule_score=existing_rule_score,
            existing_event_score=existing_event_score,
        )

    def _existing_decision(self, material: Material) -> ScoreDecision | None:
        try:
            return score_material(
                {
                    "title": material.title,
                    "category": material.category,
                    "description": material.description or "",
                    "ocrText": material.ocr_text or "",
                    "score": material.score,
                }
            )
        except Exception:
            return None

    def _student_total(self, user: User) -> float:
        materials = Material.query.filter_by(student_id=user.id).all()
        total = sum(
            Decimal(str(item.score or 0))
            for item in materials
            if item.status in {
                MaterialStatus.SUBMITTED.value,
                MaterialStatus.REVIEWING.value,
                MaterialStatus.APPROVED.value,
                MaterialStatus.PUBLICIZING.value,
                MaterialStatus.PUBLICITY_ENDED.value,
            }
        )
        return float(total.quantize(Decimal("0.01")))

    def _mock_ocr(self, payload: dict) -> str:
        source = payload.get("fileName") or payload.get("title") or "未命名材料"
        level = payload.get("level") or ""
        role = payload.get("role") or ""
        return f"OCR解析结果：识别到材料《{source}》，证书编号 {payload.get('certificateNo', '')}。{level}{role}"

    def _summary_status(self, materials: list[Material]) -> str:
        if not materials:
            return "未提交"
        statuses = {item.status for item in materials}
        if MaterialStatus.APPEALING.value in statuses:
            return MaterialStatus.APPEALING.value
        if MaterialStatus.PUBLICIZING.value in statuses:
            return MaterialStatus.PUBLICIZING.value
        if MaterialStatus.REVIEWING.value in statuses or MaterialStatus.SUBMITTED.value in statuses:
            return MaterialStatus.REVIEWING.value
        if MaterialStatus.REJECTED.value in statuses:
            return MaterialStatus.REJECTED.value
        if statuses == {MaterialStatus.APPROVED.value}:
            return MaterialStatus.APPROVED.value
        return "处理中"
