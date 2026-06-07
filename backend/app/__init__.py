from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from .config import Config
from .extensions import db
from .routes.ai import ai_bp
from .routes.appeal import appeal_bp
from .routes.auth import auth_bp
from .routes.export import export_bp
from .routes.external import external_bp
from .routes.materials import materials_bp
from .routes.notifications import notifications_bp
from .routes.organization import organization_bp
from .routes.publicity import publicity_bp
from .routes.review import review_bp
from .routes.risk import risk_bp
from .routes.stats import stats_bp
from .routes.terms import terms_bp
from .state_machine import StateMachineError


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    db.init_app(app)

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(materials_bp, url_prefix="/api/materials")
    app.register_blueprint(review_bp, url_prefix="/api/review")
    app.register_blueprint(appeal_bp, url_prefix="/api/appeal")
    app.register_blueprint(publicity_bp, url_prefix="/api/publicity")
    app.register_blueprint(risk_bp, url_prefix="/api/risk")
    app.register_blueprint(ai_bp, url_prefix="/api/ai")
    app.register_blueprint(terms_bp, url_prefix="/api/terms")
    app.register_blueprint(organization_bp, url_prefix="/api/organization")
    app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
    app.register_blueprint(export_bp, url_prefix="/api/export")
    app.register_blueprint(stats_bp, url_prefix="/api/stats")
    app.register_blueprint(external_bp, url_prefix="/api/external")

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "service": "zong-ce-backend"})

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        return jsonify({"message": error.description, "status": error.code}), error.code

    @app.errorhandler(StateMachineError)
    def handle_state_error(error: StateMachineError):
        return jsonify({"message": str(error), "status": 400}), 400

    @app.errorhandler(ValueError)
    def handle_value_error(error: ValueError):
        return jsonify({"message": str(error) or "请求参数格式不正确", "status": 400}), 400

    with app.app_context():
        from . import models  # noqa: F401

        db.create_all()

    return app
