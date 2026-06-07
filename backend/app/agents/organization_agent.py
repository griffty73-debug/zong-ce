from __future__ import annotations

from flask import abort

from ..extensions import db
from ..models import ClassGroup, College, Major, User


class OrganizationAgent:
    def list_colleges(self) -> dict:
        items = College.query.order_by(College.name.asc()).all()
        return {"items": [item.to_dict() for item in items]}

    def create_college(self, user: User, payload: dict) -> dict:
        if user.role != "counselor":
            abort(403, description="仅辅导员可维护组织架构")
        name = str(payload.get("name", "")).strip()
        code = str(payload.get("code", "")).strip()
        if not name or not code:
            abort(400, description="学院名称和编码不能为空")
        if College.query.filter((College.name == name) | (College.code == code)).first():
            abort(409, description="学院名称或编码已存在")
        college = College(name=name, code=code)
        db.session.add(college)
        db.session.commit()
        return college.to_dict()

    def list_majors(self, college_id: int | None = None) -> dict:
        query = Major.query
        if college_id:
            query = query.filter_by(college_id=college_id)
        items = query.order_by(Major.name.asc()).all()
        return {"items": [item.to_dict() for item in items]}

    def create_major(self, user: User, payload: dict) -> dict:
        if user.role != "counselor":
            abort(403, description="仅辅导员可维护组织架构")
        name = str(payload.get("name", "")).strip()
        code = str(payload.get("code", "")).strip()
        college_id = payload.get("collegeId")
        if not name or not code or not college_id:
            abort(400, description="专业名称、编码、所属学院不能为空")
        if not db.session.get(College, college_id):
            abort(404, description="所属学院不存在")
        if Major.query.filter_by(college_id=college_id, code=code).first():
            abort(409, description="该学院下专业编码已存在")
        major = Major(name=name, code=code, college_id=college_id)
        db.session.add(major)
        db.session.commit()
        return major.to_dict()

    def list_classes(self, major_id: int | None = None) -> dict:
        query = ClassGroup.query
        if major_id:
            query = query.filter_by(major_id=major_id)
        items = query.order_by(ClassGroup.name.asc()).all()
        return {"items": [item.to_dict() for item in items]}

    def create_class(self, user: User, payload: dict) -> dict:
        if user.role != "counselor":
            abort(403, description="仅辅导员可维护组织架构")
        name = str(payload.get("name", "")).strip()
        major_id = payload.get("majorId")
        grade_year = payload.get("gradeYear")
        if not name or not major_id:
            abort(400, description="班级名称、所属专业不能为空")
        if not db.session.get(Major, major_id):
            abort(404, description="所属专业不存在")
        if ClassGroup.query.filter_by(name=name).first():
            abort(409, description="班级名称已存在")
        klass = ClassGroup(
            name=name,
            major_id=major_id,
            grade_year=int(grade_year) if grade_year not in (None, "") else None,
        )
        db.session.add(klass)
        db.session.commit()
        return klass.to_dict()

    def tree(self) -> dict:
        colleges = College.query.order_by(College.name.asc()).all()
        result = []
        for college in colleges:
            majors_payload = []
            for major in sorted(college.majors, key=lambda m: m.name):
                classes_payload = [
                    {"id": c.id, "name": c.name, "gradeYear": c.grade_year}
                    for c in sorted(major.classes, key=lambda x: x.name)
                ]
                majors_payload.append(
                    {
                        "id": major.id,
                        "name": major.name,
                        "code": major.code,
                        "classes": classes_payload,
                    }
                )
            result.append(
                {
                    "id": college.id,
                    "name": college.name,
                    "code": college.code,
                    "majors": majors_payload,
                }
            )
        return {"tree": result}
