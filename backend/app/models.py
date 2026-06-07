from datetime import date, datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .state_machine import MaterialStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Term(db.Model):
    __tablename__ = "terms"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    academic_year = db.Column(db.String(20), nullable=False, index=True)
    semester_type = db.Column(db.String(20), nullable=False, default="spring")
    starts_at = db.Column(db.Date, nullable=False)
    ends_at = db.Column(db.Date, nullable=False)
    is_current = db.Column(db.Boolean, nullable=False, default=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    materials = db.relationship("Material", back_populates="term")
    appeals = db.relationship("Appeal", back_populates="term")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "academicYear": self.academic_year,
            "semesterType": self.semester_type,
            "startsAt": self.starts_at.isoformat(),
            "endsAt": self.ends_at.isoformat(),
            "isCurrent": self.is_current,
            "status": self.status,
            "createdAt": self.created_at.isoformat(),
        }


class College(db.Model):
    __tablename__ = "colleges"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    code = db.Column(db.String(20), nullable=False, unique=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    majors = db.relationship("Major", back_populates="college", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
        }


class Major(db.Model):
    __tablename__ = "majors"

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey("colleges.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    code = db.Column(db.String(20), nullable=False)

    college = db.relationship("College", back_populates="majors")
    classes = db.relationship("ClassGroup", back_populates="major", cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint("college_id", "code", name="uq_major_college_code"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "collegeId": self.college_id,
            "collegeName": self.college.name if self.college else None,
            "name": self.name,
            "code": self.code,
        }


class ClassGroup(db.Model):
    __tablename__ = "class_groups"

    id = db.Column(db.Integer, primary_key=True)
    major_id = db.Column(db.Integer, db.ForeignKey("majors.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    grade_year = db.Column(db.Integer, nullable=True)
    counselor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    major = db.relationship("Major", back_populates="classes")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "majorId": self.major_id,
            "majorName": self.major.name if self.major else None,
            "collegeId": self.major.college_id if self.major else None,
            "collegeName": self.major.college.name if self.major and self.major.college else None,
            "name": self.name,
            "gradeYear": self.grade_year,
            "counselorId": self.counselor_id,
        }


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    student_no = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    class_name = db.Column(db.String(80), nullable=True)
    college_id = db.Column(db.Integer, db.ForeignKey("colleges.id"), nullable=True, index=True)
    major_id = db.Column(db.Integer, db.ForeignKey("majors.id"), nullable=True, index=True)
    class_group_id = db.Column(db.Integer, db.ForeignKey("class_groups.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    materials = db.relationship("Material", back_populates="student", lazy=True)
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan", lazy=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "studentNo": self.student_no,
            "name": self.name,
            "role": self.role,
            "className": self.class_name,
            "collegeId": self.college_id,
            "majorId": self.major_id,
            "classGroupId": self.class_group_id,
        }


class Material(db.Model):
    __tablename__ = "materials"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    term_id = db.Column(db.Integer, db.ForeignKey("terms.id"), nullable=True, index=True)
    title = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text, nullable=True)
    certificate_no = db.Column(db.String(80), nullable=False, index=True)
    issued_at = db.Column(db.Date, nullable=False)
    expires_at = db.Column(db.Date, nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    file_url = db.Column(db.String(255), nullable=True)
    ocr_text = db.Column(db.Text, nullable=True)
    score = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default=MaterialStatus.DRAFT.value, index=True)
    risk_level = db.Column(db.String(20), nullable=False, default="low")
    risk_reasons = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    student = db.relationship("User", back_populates="materials")
    term = db.relationship("Term", back_populates="materials")
    reviews = db.relationship("ReviewRecord", back_populates="material", cascade="all, delete-orphan")
    appeals = db.relationship("Appeal", back_populates="material", cascade="all, delete-orphan")

    def to_dict(self, include_student: bool = True) -> dict:
        payload = {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "certificateNo": self.certificate_no,
            "issuedAt": self.issued_at.isoformat(),
            "expiresAt": self.expires_at.isoformat() if self.expires_at else None,
            "fileName": self.file_name,
            "fileUrl": self.file_url,
            "ocrText": self.ocr_text,
            "score": float(self.score),
            "status": self.status,
            "riskLevel": self.risk_level,
            "riskReasons": self.risk_reasons,
            "termId": self.term_id,
            "termName": self.term.name if self.term else None,
            "updatedAt": self.updated_at.isoformat(),
        }
        if include_student:
            payload["student"] = self.student.to_dict()
        return payload


class ReviewRecord(db.Model):
    __tablename__ = "review_records"

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=False, index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    action = db.Column(db.String(20), nullable=False)
    opinion = db.Column(db.Text, nullable=False)
    score_delta = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    material = db.relationship("Material", back_populates="reviews")
    reviewer = db.relationship("User")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "materialId": self.material_id,
            "reviewer": self.reviewer.to_dict(),
            "action": self.action,
            "opinion": self.opinion,
            "scoreDelta": float(self.score_delta),
            "createdAt": self.created_at.isoformat(),
        }


class Appeal(db.Model):
    __tablename__ = "appeals"

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    term_id = db.Column(db.Integer, db.ForeignKey("terms.id"), nullable=True, index=True)
    reason = db.Column(db.Text, nullable=False)
    evidence_files = db.Column(db.JSON, nullable=False, default=list)
    status = db.Column(db.String(20), nullable=False, default="待处理", index=True)
    result_opinion = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    material = db.relationship("Material", back_populates="appeals")
    student = db.relationship("User", foreign_keys=[student_id])
    term = db.relationship("Term", back_populates="appeals")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "materialId": self.material_id,
            "student": self.student.to_dict(),
            "reason": self.reason,
            "evidenceFiles": self.evidence_files or [],
            "status": self.status,
            "resultOpinion": self.result_opinion,
            "createdAt": self.created_at.isoformat(),
            "resolvedAt": self.resolved_at.isoformat() if self.resolved_at else None,
            "termId": self.term_id,
            "termName": self.term.name if self.term else None,
            "material": self.material.to_dict(),
        }


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    type = db.Column(db.String(40), nullable=False, default="info")
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(255), nullable=True)
    related_id = db.Column(db.Integer, nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    user = db.relationship("User", back_populates="notifications")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "content": self.content,
            "link": self.link,
            "relatedId": self.related_id,
            "isRead": self.is_read,
            "createdAt": self.created_at.isoformat(),
        }


class PublicityBatch(db.Model):
    __tablename__ = "publicity_batches"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    class_name = db.Column(db.String(80), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="公示中", index=True)
    starts_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    ends_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_by = db.relationship("User")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "className": self.class_name,
            "status": self.status,
            "startsAt": self.starts_at.isoformat(),
            "endsAt": self.ends_at.isoformat(),
            "createdBy": self.created_by.to_dict(),
            "archivedAt": self.archived_at.isoformat() if self.archived_at else None,
        }


class ApiKey(db.Model):
    __tablename__ = "api_keys"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    key_hash = db.Column(db.String(255), nullable=False, unique=True, index=True)
    role = db.Column(db.String(20), nullable=False, default="external")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    last_used_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "isActive": self.is_active,
            "createdAt": self.created_at.isoformat(),
            "lastUsedAt": self.last_used_at.isoformat() if self.last_used_at else None,
        }
