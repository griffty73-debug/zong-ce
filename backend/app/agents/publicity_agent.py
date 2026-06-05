from datetime import timedelta

from flask import abort
from sqlalchemy import func

from ..extensions import db
from ..models import Appeal, Material, PublicityBatch, User, utc_now
from ..state_machine import MaterialStatus, assert_transition
from .common import ensure_role
from .responses import agent_response


class PublicityAgent:
    def ranking(self, user: User | None = None, anonymous: bool = False) -> dict:
        query = (
            db.session.query(User, func.coalesce(func.sum(Material.score), 0).label("total_score"))
            .join(Material, Material.student_id == User.id)
            .filter(
                Material.status.in_(
                    [
                        MaterialStatus.APPROVED.value,
                        MaterialStatus.PUBLICIZING.value,
                        MaterialStatus.PUBLICITY_ENDED.value,
                    ]
                )
            )
        )
        if user and user.role in {"student", "counselor"} and user.class_name:
            query = query.filter(User.class_name == user.class_name)
        rows = query.group_by(User.id).order_by(func.coalesce(func.sum(Material.score), 0).desc(), User.student_no.asc()).all()
        active_batch = self._active_batch()
        items = []
        for index, (student, total_score) in enumerate(rows, start=1):
            items.append(
                {
                    "rank": index,
                    "student": self._student_payload(student, anonymous),
                    "totalScore": float(total_score),
                }
            )
        return agent_response(
            agent="Publicity Agent",
            message="综合素质测评最终成绩公示榜已生成",
            suggestions_key="publicity" if not active_batch or active_batch.status == "公示中" else "archive",
            data={
                "items": items,
                "batch": active_batch.to_dict() if active_batch else None,
                "countdown": self._countdown(active_batch),
            },
        )

    def start(self, user: User, payload: dict) -> dict:
        ensure_role(user, {"counselor"})
        class_name = payload.get("className") or user.class_name
        pending_appeals = self._pending_appeals(class_name)
        if pending_appeals:
            abort(400, description="存在未处理申诉，暂不能发起公示")

        query = Material.query.filter_by(status=MaterialStatus.APPROVED.value)
        if class_name:
            query = query.join(User, Material.student_id == User.id).filter(User.class_name == class_name)
        materials = query.all()
        if not materials:
            abort(400, description="没有可公示的已通过材料")

        if payload.get("confirm") != "确认公示":
            preview = self.ranking(user, anonymous=True)
            return agent_response(
                agent="Publicity Agent",
                status="pending_confirmation",
                message="已生成匿名公示预览。\n⚠️ 请确认您的操作是否准确。一旦发起公示，全班综测数据将彻底锁定。如果正确，请回复“确认公示”；如需调整，请退出。",
                suggestions_key="publicity",
                data={
                    "preview": preview["items"],
                    "requiresConfirmation": True,
                    "count": len(materials),
                },
            )

        for material in materials:
            assert_transition(material.status, MaterialStatus.PUBLICIZING)
            material.status = MaterialStatus.PUBLICIZING.value

        batch = PublicityBatch(
            title=payload.get("title") or "综合测评公示",
            class_name=class_name,
            starts_at=utc_now(),
            ends_at=utc_now() + timedelta(days=int(payload.get("days") or 3)),
            created_by_id=user.id,
        )
        db.session.add(batch)
        db.session.commit()
        return agent_response(
            agent="Publicity Agent",
            message="【系统通知】全班综测公示已正式启动！为期 3 天的匿名公示大榜已发布。公示期间数据已全盘锁定，严禁任何后台篡改。",
            suggestions_key="publicity",
            data={"batch": batch.to_dict(), "count": len(materials), "countdown": self._countdown(batch)},
        )

    def archive(self, user: User, payload: dict) -> dict:
        ensure_role(user, {"counselor"})
        batch = db.session.get(PublicityBatch, payload.get("batchId"))
        if not batch:
            abort(404, description="公示批次不存在")
        materials = Material.query.filter_by(status=MaterialStatus.PUBLICIZING.value).all()
        for material in materials:
            assert_transition(material.status, MaterialStatus.PUBLICITY_ENDED)
            material.status = MaterialStatus.PUBLICITY_ENDED.value
        batch.status = "已归档"
        batch.archived_at = utc_now()
        db.session.commit()
        return agent_response(
            agent="Publicity Agent",
            message="【系统通知】3天公示期已满，期间无未决申诉。全班综测数据已自动归档并冻结，最终成绩已打包同步至学校奖学金评定系统。",
            suggestions_key="archive",
            data={"batch": batch.to_dict(), "count": len(materials)},
        )

    def _student_payload(self, student: User, anonymous: bool) -> dict:
        if not anonymous:
            return student.to_dict()
        no = student.student_no
        return {
            "id": student.id,
            "studentNo": no,
            "name": f"{student.name[:1]}*",
            "role": student.role,
            "className": student.class_name,
        }

    def _active_batch(self) -> PublicityBatch | None:
        return PublicityBatch.query.order_by(PublicityBatch.starts_at.desc()).first()

    def _countdown(self, batch: PublicityBatch | None) -> dict | None:
        if not batch:
            return None
        now = utc_now()
        ends_at = batch.ends_at
        if ends_at.tzinfo is None:
            now = now.replace(tzinfo=None)
        remaining = max(timedelta(0), ends_at - now)
        hours = int(remaining.total_seconds() // 3600)
        return {
            "days": hours // 24,
            "hours": hours % 24,
            "text": f"距离公示结束还剩 {hours // 24} 天 {hours % 24} 小时",
        }

    def _pending_appeals(self, class_name: str | None) -> int:
        query = Appeal.query.filter_by(status="待处理")
        if class_name:
            query = query.join(User, Appeal.student_id == User.id).filter(User.class_name == class_name)
        return query.count()
