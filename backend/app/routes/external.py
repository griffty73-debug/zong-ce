import secrets
import hashlib
from functools import wraps

from flask import Blueprint, abort, jsonify, request

from ..agents import MasterAgent
from ..extensions import db
from ..models import ApiKey, Material, User


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            abort(401, description="缺少 Authorization: Bearer <api_key>")
        api_key = auth_header[7:]
        if not api_key:
            abort(401, description="API key 不能为空")

        key_hash = _hash_key(api_key)
        key_record = ApiKey.query.filter_by(key_hash=key_hash).first()
        if not key_record:
            abort(401, description="无效的 API key")
        if not key_record.is_active:
            abort(403, description="API key 已停用")

        key_record.last_used_at = db.func.now()
        db.session.commit()

        return f(*args, **kwargs)
    return decorated


def _get_master():
    return MasterAgent()


external_bp = Blueprint("external", __name__)


@external_bp.post("/api-keys")
@_require_api_key
def create_api_key():
    payload = request.get_json() or {}
    name = str(payload.get("name", "")).strip()
    role = str(payload.get("role", "external")).strip()
    if not name:
        abort(400, description="name 不能为空")
    if role not in {"external", "student", "teacher", "counselor"}:
        abort(400, description="role 必须是 external/student/teacher/counselor")

    raw_key = f"zce_{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(raw_key)
    record = ApiKey(name=name, key_hash=key_hash, role=role)
    db.session.add(record)
    db.session.commit()
    return jsonify({
        "name": name,
        "apiKey": raw_key,
        "role": role,
        "message": "请妥善保管 apiKey，只显示一次"
    })


@external_bp.get("/api-keys")
@_require_api_key
def list_api_keys():
    keys = ApiKey.query.all()
    return jsonify({"keys": [k.to_dict() for k in keys]})


@external_bp.delete("/api-keys/<int:key_id>")
@_require_api_key
def delete_api_key(key_id: int):
    key_record = ApiKey.query.get(key_id)
    if not key_record:
        abort(404, description="API key 不存在")
    db.session.delete(key_record)
    db.session.commit()
    return jsonify({"message": "已删除"})


@external_bp.get("/users")
@_require_api_key
def list_users():
    role = request.args.get("role")
    query = User.query
    if role:
        query = query.filter_by(role=role)
    users = query.all()
    return jsonify({"users": [u.to_dict() for u in users]})


@external_bp.get("/users/<int:user_id>")
@_require_api_key
def get_user(user_id: int):
    user = db.session.get(User, user_id)
    if not user:
        abort(404, description="用户不存在")
    return jsonify(user.to_dict())


@external_bp.get("/students/<student_no>/summary")
@_require_api_key
def student_summary(student_no: str):
    user = User.query.filter_by(student_no=student_no).first()
    if not user:
        abort(404, description="学生不存在")
    return jsonify(_get_master().audit.student_summary(user))


@external_bp.get("/students/<student_no>/materials")
@_require_api_key
def student_materials(student_no: str):
    user = User.query.filter_by(student_no=student_no).first()
    if not user:
        abort(404, description="学生不存在")
    return jsonify(_get_master().audit.list_materials(user))


@external_bp.get("/materials")
@_require_api_key
def list_materials():
    status = request.args.get("status")
    category = request.args.get("category")
    query = Material.query
    if status:
        query = query.filter_by(status=status)
    if category:
        query = query.filter_by(category=category)
    materials = query.order_by(Material.created_at.desc()).limit(100).all()
    return jsonify({"materials": [m.to_dict() for m in materials]})


@external_bp.get("/materials/<int:material_id>")
@_require_api_key
def get_material(material_id: int):
    material = db.session.get(Material, material_id)
    if not material:
        abort(404, description="材料不存在")
    return jsonify(material.to_dict())


@external_bp.post("/materials")
@_require_api_key
def create_material():
    payload = request.get_json() or {}
    student_no = str(payload.get("studentNo", "")).strip()
    if not student_no:
        abort(400, description="studentNo 不能为空")

    user = User.query.filter_by(student_no=student_no).first()
    if not user:
        abort(404, description=f"学生 {student_no} 不存在")

    result = _get_master().audit.upload_material(user, payload)
    return jsonify(result)


@external_bp.get("/publicity/rankings")
@_require_api_key
def rankings():
    anonymous = request.args.get("anonymous", "1") != "0"
    return jsonify(_get_master().publicity.ranking(None, anonymous))


@external_bp.get("/publicity/batches")
@_require_api_key
def publicity_batches():
    from ..models import PublicityBatch
    status = request.args.get("status")
    query = PublicityBatch.query
    if status:
        query = query.filter_by(status=status)
    batches = query.order_by(PublicityBatch.starts_at.desc()).limit(50).all()
    return jsonify({"batches": [b.to_dict() for b in batches]})


@external_bp.get("/stats/overview")
@_require_api_key
def stats_overview():
    from ..models import Appeal, ReviewRecord
    total_students = User.query.filter_by(role="student").count()
    total_materials = Material.query.count()
    pending_review = Material.query.filter_by(status="审核中").count()
    total_appeals = Appeal.query.count()
    return jsonify({
        "totalStudents": total_students,
        "totalMaterials": total_materials,
        "pendingReview": pending_review,
        "totalAppeals": total_appeals,
    })


@external_bp.post("/ai/chat")
@_require_api_key
def external_ai_chat():
    payload = request.get_json() or {}
    messages = payload.get("messages", [])
    if not messages:
        abort(400, description="messages 不能为空")

    from flask import current_app
    from ..agents.deepseek_client import DeepSeekConfig, DeepSeekClient

    config = DeepSeekConfig(
        api_key=current_app.config["DEEPSEEK_API_KEY"],
        base_url=current_app.config["DEEPSEEK_BASE_URL"],
        model=current_app.config["DEEPSEEK_MODEL"],
        timeout=current_app.config["DEEPSEEK_TIMEOUT"],
    )
    client = DeepSeekClient(config)
    result = client.chat(messages)
    return jsonify({
        "model": result["model"],
        "content": result["content"],
        "usage": result["usage"],
        "finishReason": result["finishReason"],
    })