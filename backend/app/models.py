from datetime import date, datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .state_machine import MaterialStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    student_no = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    class_name = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    materials = db.relationship("Material", back_populates="student", lazy=True)

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
        }


class Material(db.Model):
    __tablename__ = "materials"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
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
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="待处理", index=True)
    result_opinion = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    material = db.relationship("Material", back_populates="appeals")
    student = db.relationship("User", foreign_keys=[student_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "materialId": self.material_id,
            "student": self.student.to_dict(),
            "reason": self.reason,
            "status": self.status,
            "resultOpinion": self.result_opinion,
            "createdAt": self.created_at.isoformat(),
            "resolvedAt": self.resolved_at.isoformat() if self.resolved_at else None,
            "material": self.material.to_dict(),
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
