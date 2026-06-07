from flask import Blueprint, jsonify, request

from .helpers import current_user, json_payload, master

review_bp = Blueprint("review", __name__)


@review_bp.get("/list")
def list_pending():
    term_id = request.args.get("termId", type=int)
    return jsonify(master().counselor.list_pending(current_user(), term_id=term_id))


@review_bp.get("/detail/<int:material_id>")
def detail(material_id: int):
    return jsonify(master().counselor.detail(current_user(), material_id))


@review_bp.post("/action")
def action():
    return jsonify(master().counselor.action(current_user(), json_payload()))


@review_bp.post("/batch-action")
def batch_action():
    return jsonify(master().counselor.batch_action(current_user(), json_payload()))
