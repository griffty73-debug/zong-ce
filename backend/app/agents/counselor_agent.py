from decimal import Decimal

from flask import abort

from ..extensions import db
from ..models import Material, ReviewRecord, User
from ..state_machine import MaterialStatus, assert_transition
from .common import ensure_role


class CounselorAgent:
    def list_pending(self, user: User) -> dict:
        ensure_role(user, {"teacher", "counselor"})
        query = Material.query.filter(Material.status.in_([MaterialStatus.SUBMITTED.value, MaterialStatus.REVIEWING.value]))
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
        db.session.commit()
        return {"status": "ok", "material": material.to_dict(), "review": record.to_dict()}
