import mimetypes
import os
import secrets
from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from ..agents.material_parser import ALLOWED_MIME_TYPES, MAX_FILE_SIZE
from .helpers import current_user, json_payload, master

materials_bp = Blueprint("materials", __name__)

UPLOAD_ROOT = Path(__file__).resolve().parents[1] / "uploads"


def _save_upload(file_storage, sub: str) -> dict:
    if "file" not in request.files:
        abort(400, description="未找到上传文件")
    uploaded = file_storage
    if not uploaded.filename:
        abort(400, description="文件名为空")

    safe_name = secure_filename(uploaded.filename) or "upload"
    content_type = uploaded.content_type or mimetypes.guess_type(safe_name)[0] or ""
    if content_type not in ALLOWED_MIME_TYPES:
        abort(400, description="不支持的文件类型")

    raw = uploaded.read()
    if len(raw) > MAX_FILE_SIZE:
        abort(400, description="文件大小超过 5MB 限制")

    target_dir = UPLOAD_ROOT / sub
    target_dir.mkdir(parents=True, exist_ok=True)
    unique = secrets.token_urlsafe(8)
    stored_name = f"{unique}_{safe_name}"
    (target_dir / stored_name).write_bytes(raw)
    rel = f"{sub}/{stored_name}"
    url = f"/api/uploads/{sub}/{stored_name}"
    return {"name": uploaded.filename, "url": url, "storedName": stored_name, "size": len(raw), "contentType": content_type, "rel": rel}


@materials_bp.post("/upload")
def upload():
    return jsonify(master().audit.upload_material(current_user(), json_payload()))


@materials_bp.post("/upload-file")
def upload_file():
    user = current_user()
    if user.role != "student":
        abort(403, description="仅学生可解析材料")
    saved = _save_upload(request.files.get("file"), "materials")
    response = master().material_parser.parse(Path(UPLOAD_ROOT / saved["rel"]).read_bytes(), saved["contentType"], saved["name"])
    payload = response.get("data") if isinstance(response.get("data"), dict) else None
    if payload is not None:
        payload["fileUrl"] = saved["url"]
        payload["fileName"] = saved["name"]
    return jsonify(response)


@materials_bp.get("/list")
def list_materials():
    term_id = request.args.get("termId", type=int)
    return jsonify(master().audit.list_materials(current_user(), term_id=term_id))


@materials_bp.get("/summary")
def summary():
    term_id = request.args.get("termId", type=int)
    return jsonify(master().audit.student_summary(current_user(), term_id=term_id))


@materials_bp.get("/uploads/<sub>/<path:filename>")
def serve_upload(sub: str, filename: str):
    if sub not in {"materials", "appeals"}:
        abort(404)
    return send_from_directory(UPLOAD_ROOT / sub, filename)


