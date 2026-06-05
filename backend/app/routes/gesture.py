from flask import Blueprint, jsonify

from ..agents import GestureAgent
from .helpers import current_user, json_payload

gesture_bp = Blueprint("gesture", __name__)


@gesture_bp.post("/dispatch")
def dispatch():
    return jsonify(GestureAgent().dispatch(current_user(), json_payload()))
