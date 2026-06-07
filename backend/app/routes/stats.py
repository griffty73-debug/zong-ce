from flask import Blueprint, jsonify, request

from .helpers import current_user, master

stats_bp = Blueprint("stats", __name__)


@stats_bp.get("/overview")
def overview():
    user = current_user()
    term_id = request.args.get("termId", type=int)
    return jsonify(master().stats.overview(user, term_id=term_id))


@stats_bp.get("/student")
def student():
    user = current_user()
    term_id = request.args.get("termId", type=int)
    return jsonify(master().stats.student(user, term_id=term_id))
