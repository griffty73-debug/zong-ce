from flask import Blueprint, jsonify, request

from .helpers import current_user, json_payload, master

publicity_bp = Blueprint("publicity", __name__)


@publicity_bp.get("/rank")
def rank():
    anonymous = request.args.get("anonymous", "1") != "0"
    term_id = request.args.get("termId", type=int)
    return jsonify(master().publicity.ranking(current_user(), anonymous, term_id=term_id))


@publicity_bp.post("/start")
def start():
    return jsonify(master().publicity.start(current_user(), json_payload()))


@publicity_bp.post("/archive")
def archive():
    return jsonify(master().publicity.archive(current_user(), json_payload()))
