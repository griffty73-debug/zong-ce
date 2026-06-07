from flask import Blueprint, jsonify, request

from .helpers import current_user, json_payload, master
from .materials import _save_upload

appeal_bp = Blueprint("appeal", __name__)


@appeal_bp.post("/submit")
def submit():
    return jsonify(master().appeal.submit(current_user(), json_payload()))


@appeal_bp.get("/list")
def list_appeals():
    term_id = request.args.get("termId", type=int)
    return jsonify(master().appeal.list(current_user(), term_id=term_id))


@appeal_bp.get("/detail/<int:appeal_id>")
def detail(appeal_id: int):
    return jsonify(master().appeal.detail(current_user(), appeal_id))


@appeal_bp.post("/resolve")
def resolve():
    return jsonify(master().appeal.resolve(current_user(), json_payload()))


@appeal_bp.post("/confirm-review")
def confirm_review():
    return jsonify(master().appeal.confirm_review(current_user(), json_payload()))


@appeal_bp.post("/upload-file")
def upload_evidence():
    user = current_user()
    if user.role != "student":
        from flask import abort
        abort(403, description="仅学生可上传证据")
    saved = _save_upload(request.files.get("file"), "appeals")
    return jsonify({"data": {"name": saved["name"], "url": saved["url"]}})

