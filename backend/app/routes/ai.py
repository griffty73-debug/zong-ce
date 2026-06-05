from flask import Blueprint, current_app, jsonify

from ..agents import DeepSeekAgent
from ..agents.deepseek_client import DeepSeekConfig
from .helpers import current_user, json_payload

ai_bp = Blueprint("ai", __name__)


def deepseek_agent() -> DeepSeekAgent:
    return DeepSeekAgent(
        DeepSeekConfig(
            api_key=current_app.config["DEEPSEEK_API_KEY"],
            base_url=current_app.config["DEEPSEEK_BASE_URL"],
            model=current_app.config["DEEPSEEK_MODEL"],
            timeout=current_app.config["DEEPSEEK_TIMEOUT"],
        )
    )


@ai_bp.get("/status")
def status():
    current_user()
    return jsonify(deepseek_agent().status())


@ai_bp.post("/chat")
def chat():
    return jsonify(deepseek_agent().chat(current_user(), json_payload()))
