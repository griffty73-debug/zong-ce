from flask import Blueprint, jsonify

from .helpers import current_user, json_payload, master

risk_bp = Blueprint("risk", __name__)


@risk_bp.post("/inspect")
def inspect():
    current_user()
    return jsonify(master().risk.inspect_material(json_payload()))


@risk_bp.get("/report")
def report():
    current_user()
    return jsonify(master().risk.report())
