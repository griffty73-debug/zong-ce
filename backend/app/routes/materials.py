import mimetypes

from flask import Blueprint, abort, jsonify, request
from werkzeug.utils import secure_filename

from ..agents.material_parser import ALLOWED_MIME_TYPES, MAX_FILE_SIZE
from .helpers import current_user, json_payload, master

materials_bp = Blueprint("materials", __name__)


@materials_bp.post("/upload")
def upload():
    return jsonify(master().audit.upload_material(current_user(), json_payload()))


@materials_bp.post("/upload-file")
def upload_file():
    user = current_user()
    if user.role != "student":
        abort(403, description="仅学生可解析材料")
    if "file" not in request.files:
        abort(400, description="未找到上传文件")

    uploaded = request.files["file"]
    if not uploaded.filename:
        abort(400, description="文件名为空")

    filename = secure_filename(uploaded.filename)
    content_type = uploaded.content_type or mimetypes.guess_type(filename)[0] or ""
    if content_type not in ALLOWED_MIME_TYPES:
        abort(400, description="不支持的文件类型")

    file_data = uploaded.read()
    if len(file_data) > MAX_FILE_SIZE:
        abort(400, description="文件大小超过 5MB 限制")

    return jsonify(master().material_parser.parse(file_data, content_type, filename))


@materials_bp.get("/list")
def list_materials():
    return jsonify(master().audit.list_materials(current_user()))


@materials_bp.get("/summary")
def summary():
    return jsonify(master().audit.student_summary(current_user()))
