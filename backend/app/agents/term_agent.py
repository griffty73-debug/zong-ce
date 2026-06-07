from __future__ import annotations

from datetime import date, timedelta

from flask import abort
from sqlalchemy import or_

from ..extensions import db
from ..models import Term, User


def _ensure_default_term() -> Term:
    current = Term.query.filter_by(is_current=True).first()
    if current:
        return current
    today = date.today()
    if today.month >= 8:
        academic_year = f"{today.year}-{today.year + 1}"
        semester_type = "fall"
    else:
        academic_year = f"{today.year - 1}-{today.year}"
        semester_type = "spring"
    start = today - timedelta(days=30)
    end = today + timedelta(days=120)
    term = Term.query.filter_by(name=f"{academic_year} 学年{'上' if semester_type == 'fall' else '下'}学期").first()
    if not term:
        term = Term(
            name=f"{academic_year} 学年{'上' if semester_type == 'fall' else '下'}学期",
            academic_year=academic_year,
            semester_type=semester_type,
            starts_at=start,
            ends_at=end,
            is_current=True,
            status="active",
        )
        db.session.add(term)
    else:
        term.is_current = True
    db.session.commit()
    return term


class TermAgent:
    def list_terms(self) -> dict:
        items = Term.query.order_by(Term.starts_at.desc()).all()
        return {"items": [item.to_dict() for item in items]}

    def current_term(self) -> dict:
        term = _ensure_default_term()
        return term.to_dict()

    def create(self, user: User, payload: dict) -> dict:
        if user.role not in {"counselor", "teacher"}:
            abort(403, description="仅教务/辅导员可创建学期")
        name = str(payload.get("name", "")).strip()
        if not name:
            abort(400, description="学期名称不能为空")
        if Term.query.filter_by(name=name).first():
            abort(409, description="学期名称已存在")
        academic_year = str(payload.get("academicYear", "")).strip()
        semester_type = str(payload.get("semesterType", "spring")).strip()
        if semester_type not in {"spring", "fall", "summer"}:
            abort(400, description="semesterType 必须为 spring/fall/summer")
        try:
            starts_at = date.fromisoformat(payload["startsAt"])
            ends_at = date.fromisoformat(payload["endsAt"])
        except (KeyError, ValueError, TypeError):
            abort(400, description="startsAt/endsAt 必填且为 YYYY-MM-DD")
        if ends_at <= starts_at:
            abort(400, description="结束日期必须晚于开始日期")
        make_current = bool(payload.get("isCurrent"))
        if make_current:
            Term.query.update({Term.is_current: False})
        term = Term(
            name=name,
            academic_year=academic_year or name[:7],
            semester_type=semester_type,
            starts_at=starts_at,
            ends_at=ends_at,
            is_current=make_current,
            status=str(payload.get("status", "active")),
        )
        db.session.add(term)
        db.session.commit()
        return term.to_dict()

    def update(self, user: User, term_id: int, payload: dict) -> dict:
        if user.role not in {"counselor", "teacher"}:
            abort(403, description="仅教务/辅导员可修改学期")
        term = db.session.get(Term, term_id)
        if not term:
            abort(404, description="学期不存在")
        if "startsAt" in payload:
            try:
                term.starts_at = date.fromisoformat(payload["startsAt"])
            except (KeyError, ValueError, TypeError):
                abort(400, description="startsAt 格式错误")
        if "endsAt" in payload:
            try:
                term.ends_at = date.fromisoformat(payload["endsAt"])
            except (KeyError, ValueError, TypeError):
                abort(400, description="endsAt 格式错误")
        if term.ends_at <= term.starts_at:
            abort(400, description="结束日期必须晚于开始日期")
        if "name" in payload and payload["name"]:
            term.name = str(payload["name"]).strip()
        if "status" in payload:
            term.status = str(payload["status"])
        if payload.get("isCurrent"):
            Term.query.filter(Term.id != term.id).update({Term.is_current: False})
            term.is_current = True
        db.session.commit()
        return term.to_dict()

    def delete(self, user: User, term_id: int) -> dict:
        if user.role != "counselor":
            abort(403, description="仅辅导员可删除学期")
        term = db.session.get(Term, term_id)
        if not term:
            abort(404, description="学期不存在")
        if term.materials or term.appeals:
            abort(400, description="该学期已有数据，禁止删除")
        db.session.delete(term)
        db.session.commit()
        return {"message": "已删除", "id": term_id}

    def resolve_term_id(self, term_id: int | None) -> int | None:
        if not term_id:
            return _ensure_default_term().id
        term = db.session.get(Term, term_id)
        if not term:
            abort(404, description="学期不存在")
        return term.id

    def ensure_current(self) -> Term:
        return _ensure_default_term()

    def search_terms(self, query: str | None = None) -> list[Term]:
        q = Term.query
        if query:
            like = f"%{query.strip()}%"
            q = q.filter(or_(Term.name.ilike(like), Term.academic_year.ilike(like)))
        return q.order_by(Term.starts_at.desc()).all()
