from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from flask import abort
from sqlalchemy import func

from ..extensions import db
from ..models import (
    Appeal,
    ClassGroup,
    College,
    Major,
    Material,
    PublicityBatch,
    ReviewRecord,
    User,
    utc_now,
)
from ..state_machine import MaterialStatus
from .common import ensure_role
from .term_agent import TermAgent


CATEGORY_ORDER = ["德育", "智育", "体育", "美育", "劳育", "能力"]


class StatsAgent:
    def __init__(self):
        self.term = TermAgent()

    def overview(self, user: User, term_id: int | None = None) -> dict:
        ensure_role(user, {"teacher", "counselor"})
        current_term_id = term_id or self.term.ensure_current().id

        material_query = Material.query
        if term_id:
            material_query = material_query.filter_by(term_id=term_id)
        if user.role == "counselor" and user.class_group_id:
            material_query = material_query.join(User, Material.student_id == User.id).filter(User.class_group_id == user.class_group_id)

        total_materials = material_query.count()
        pending = material_query.filter(Material.status.in_([MaterialStatus.SUBMITTED.value, MaterialStatus.REVIEWING.value])).count()
        approved = material_query.filter(Material.status.in_([MaterialStatus.APPROVED.value, MaterialStatus.PUBLICIZING.value, MaterialStatus.PUBLICITY_ENDED.value])).count()
        rejected = material_query.filter_by(status=MaterialStatus.REJECTED.value).count()
        appealing = material_query.filter_by(status=MaterialStatus.APPEALING.value).count()

        category_breakdown = self._category_breakdown(material_query)
        top_students = self._top_students(material_query, limit=8)
        class_breakdown = self._class_breakdown(material_query)
        trend = self._trend(material_query, days=14)
        pending_appeals = Appeal.query.filter_by(status="待处理")
        if term_id:
            pending_appeals = pending_appeals.filter_by(term_id=term_id)
        if user.role == "counselor" and user.class_group_id:
            pending_appeals = pending_appeals.join(User, Appeal.student_id == User.id).filter(User.class_group_id == user.class_group_id)
        pending_appeals_count = pending_appeals.count()

        return {
            "term": {"id": current_term_id, "name": (self.term.ensure_current().name if not term_id else (db.session.get(Major, current_term_id) or self.term.ensure_current()).name)},
            "summary": {
                "totalMaterials": total_materials,
                "pending": pending,
                "approved": approved,
                "rejected": rejected,
                "appealing": appealing,
                "pendingAppeals": pending_appeals_count,
            },
            "categoryBreakdown": category_breakdown,
            "topStudents": top_students,
            "classBreakdown": class_breakdown,
            "trend": trend,
        }

    def student(self, user: User, term_id: int | None = None) -> dict:
        if user.role != "student":
            abort(403, description="仅学生可访问个人统计")
        current_term_id = term_id or self.term.ensure_current().id
        query = Material.query.filter_by(student_id=user.id)
        if term_id:
            query = query.filter_by(term_id=term_id)
        materials = query.all()
        category = self._category_breakdown(query)
        radar = {item["category"]: item["score"] for item in category}
        status_dist = defaultdict(int)
        for material in materials:
            status_dist[material.status] += 1
        total = round(sum(radar.values()), 2)
        return {
            "term": {"id": current_term_id, "name": self.term.ensure_current().name},
            "totalScore": total,
            "category": category,
            "radar": {key: radar.get(key, 0.0) for key in CATEGORY_ORDER},
            "statusDistribution": dict(status_dist),
            "materials": [m.to_dict(include_student=False) for m in materials],
        }

    def _category_breakdown(self, query) -> list[dict]:
        rows = (
            query.with_entities(Material.category, func.coalesce(func.sum(Material.score), 0))
            .filter(
                Material.status.in_(
                    [
                        MaterialStatus.APPROVED.value,
                        MaterialStatus.PUBLICIZING.value,
                        MaterialStatus.PUBLICITY_ENDED.value,
                    ]
                )
            )
            .group_by(Material.category)
            .all()
        )
        by_category = {category: 0.0 for category in CATEGORY_ORDER}
        for category, total in rows:
            by_category[category] = float(total or 0)
        return [{"category": c, "score": round(by_category[c], 2)} for c in CATEGORY_ORDER]

    def _top_students(self, query, limit: int = 8) -> list[dict]:
        rows = (
            db.session.query(User, func.coalesce(func.sum(Material.score), 0).label("total"))
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
            .group_by(User.id)
            .order_by(func.coalesce(func.sum(Material.score), 0).desc(), User.student_no.asc())
            .limit(limit)
            .all()
        )
        return [
            {
                "studentNo": student.student_no,
                "name": student.name,
                "className": student.class_name,
                "totalScore": float(total),
            }
            for student, total in rows
        ]

    def _class_breakdown(self, query) -> list[dict]:
        rows = (
            db.session.query(
                User.class_name,
                func.coalesce(func.sum(Material.score), 0).label("total"),
                func.count(func.distinct(User.id)).label("student_count"),
            )
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
            .group_by(User.class_name)
            .order_by(func.coalesce(func.sum(Material.score), 0).desc())
            .all()
        )
        result = []
        for class_name, total, count in rows:
            result.append(
                {
                    "className": class_name or "未分班",
                    "totalScore": float(total or 0),
                    "studentCount": int(count or 0),
                }
            )
        return result

    def _trend(self, query, days: int = 14) -> list[dict]:
        since = utc_now() - timedelta(days=days)
        rows = (
            db.session.query(
                func.date(Material.created_at).label("date"),
                func.count(Material.id).label("count"),
            )
            .filter(Material.created_at >= since)
            .group_by("date")
            .order_by("date")
            .all()
        )
        return [{"date": str(date_value), "count": int(count or 0)} for date_value, count in rows]
