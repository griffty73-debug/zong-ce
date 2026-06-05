from flask import Blueprint, jsonify

from .helpers import current_user, json_payload, master

appeal_bp = Blueprint("appeal", __name__)


@appeal_bp.post("/submit")
def submit():
    return jsonify(master().appeal.submit(current_user(), json_payload()))


@appeal_bp.get("/list")
def list_appeals():
    return jsonify(master().appeal.list(current_user()))


@appeal_bp.get("/detail/<int:appeal_id>")
def detail(appeal_id: int):
    return jsonify(master().appeal.detail(current_user(), appeal_id))


@appeal_bp.post("/resolve")
def resolve():
    return jsonify(master().appeal.resolve(current_user(), json_payload()))


@appeal_bp.post("/confirm-review")
def confirm_review():
    return jsonify(master().appeal.confirm_review(current_user(), json_payload()))
