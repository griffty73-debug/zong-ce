from decimal import Decimal

from flask import abort

from ..extensions import db
from ..models import Material, ReviewRecord, User
from ..state_machine import MaterialStatus, assert_transition
from .common import ensure_role
from .notification_agent import NotificationAgent


class CounselorAgent:
    def __init__(self):
        self.notification = NotificationAgent()

    def list_pending(self, user: User, term_id: int | None = None) -> dict:
        ensure_role(user, {"teacher", "counselor"})
        query = Material.query.filter(Material.status.in_([MaterialStatus.SUBMITTED.value, MaterialStatus.REVIEWING.value]))
        if term_id:
            query = query.filter_by(term_id=term_id)
        if user.role == "counselor" and user.class_group_id:
            query = query.join(User, Material.student_id == User.id).filter(User.class_group_id == user.class_group_id)
        items = query.order_by(Material.updated_at.asc()).all()
        return {"items": [item.to_dict() for item in items]}

    def detail(self, user: User, material_id: int) -> dict:
        ensure_role(user, {"teacher", "counselor"})
        material = db.session.get(Material, material_id)
        if not material:
            abort(404, description="材料不存在")
        return {
            "material": material.to_dict(),
            "reviews": [record.to_dict() for record in material.reviews],
        }

    def action(self, user: User, payload: dict) -> dict:
        ensure_role(user, {"teacher", "counselor"})
        material = db.session.get(Material, payload.get("materialId"))
        if not material:
            abort(404, description="材料不存在")

        action = payload.get("action")
        opinion = str(payload.get("opinion", "")).strip()
        score_delta = Decimal(str(payload.get("scoreDelta") or "0"))
        if action not in {"pass", "reject"}:
            abort(400, description="审核动作必须为 pass 或 reject")
        if action == "reject" and not opinion:
            abort(400, description="审核打回必须说明原因")

        if material.status == MaterialStatus.SUBMITTED.value:
            assert_transition(material.status, MaterialStatus.REVIEWING)
            material.status = MaterialStatus.REVIEWING.value

        target = MaterialStatus.APPROVED if action == "pass" else MaterialStatus.REJECTED
        assert_transition(material.status, target)
        material.status = target.value
        material.score = max(Decimal("0"), Decimal(material.score) + score_delta)

        record = ReviewRecord(
            material_id=material.id,
            reviewer_id=user.id,
            action="通过" if action == "pass" else "打回",
            opinion=opinion or "审核通过",
            score_delta=score_delta,
        )
        db.session.add(record)
        self._notify_student(material, action, opinion)
        db.session.commit()
        return {"status": "ok", "material": material.to_dict(), "review": record.to_dict()}

    def batch_action(self, user: User, payload: dict) -> dict:
        ensure_role(user, {"teacher", "counselor"})
        material_ids = payload.get("materialIds") or []
        if not isinstance(material_ids, list) or not material_ids:
            abort(400, description="materialIds 不能为空")
        action = payload.get("action")
        opinion = str(payload.get("opinion", "")).strip()
        if action not in {"pass", "reject"}:
            abort(400, description="审核动作必须为 pass 或 reject")
        if action == "reject" and not opinion:
            abort(400, description="批量打回必须说明原因")

        results = []
        for material_id in material_ids:
            material = db.session.get(Material, material_id)
            if not material:
                continue
            if material.status not in {MaterialStatus.SUBMITTED.value, MaterialStatus.REVIEWING.value}:
                continue
            if material.status == MaterialStatus.SUBMITTED.value:
                assert_transition(material.status, MaterialStatus.REVIEWING)
                material.status = MaterialStatus.REVIEWING.value
            target = MaterialStatus.APPROVED if action == "pass" else MaterialStatus.REJECTED
            try:
                assert_transition(material.status, target)
            except Exception:
                continue
            material.status = target.value
            record = ReviewRecord(
                material_id=material.id,
                reviewer_id=user.id,
                action="通过" if action == "pass" else "打回",
                opinion=opinion or "批量审核通过",
                score_delta=Decimal("0"),
            )
            db.session.add(record)
            self._notify_student(material, action, opinion or "批量审核通过")
            results.append(material.id)
        db.session.commit()
        return {
            "message": f"已处理 {len(results)} 条材料",
            "count": len(results),
            "ids": results,
        }

    def _notify_student(self, material: Material, action: str, opinion: str) -> None:
        if not material.student_id:
            return
        if action == "pass":
            title = "材料已通过审核"
            content = f"《{material.title}》已通过审核，最终得分 {float(material.score):.2f} 分"
            notif_type = "review_pass"
        else:
            title = "材料被打回"
            content = f"《{material.title}》被审核打回：{opinion or '请查看详情'}"
            notif_type = "review_reject"
        self.notification.push(
            user_id=material.student_id,
            type=notif_type,
            title=title,
            content=content,
            link=f"/materials?id={material.id}",
            related_id=material.id,
        )

