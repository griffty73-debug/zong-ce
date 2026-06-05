from flask import current_app, request

from ..agents import AuthAgent, MasterAgent


def json_payload() -> dict:
    return request.get_json(silent=True) or {}


def bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header.removeprefix("Bearer ").strip()
    return None


def current_user():
    auth = AuthAgent(current_app.config["SECRET_KEY"])
    return auth.current_user(bearer_token())


def master() -> MasterAgent:
    return MasterAgent()
