from flask import Blueprint, current_app, jsonify

from ..agents import AuthAgent
from .helpers import current_user, json_payload, master

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    return jsonify(AuthAgent(current_app.config["SECRET_KEY"]).register(json_payload()))


@auth_bp.post("/login")
def login():
    return jsonify(AuthAgent(current_app.config["SECRET_KEY"]).login(json_payload()))


@auth_bp.get("/me")
def me():
    user = current_user()
    return jsonify({"user": user.to_dict(), "dashboard": master().dashboard(user)})
