from concurrent.futures import ThreadPoolExecutor

from flask import current_app

from ..models import User
from ..extensions import db
from .appeal_agent import AppealAgent
from .audit_agent import AuditAgent
from .auth_agent import AuthAgent
from .counselor_agent import CounselorAgent
from .deepseek_client import DeepSeekConfig
from .export_agent import ExportAgent
from .material_parser import MaterialParser
from .notification_agent import NotificationAgent
from .organization_agent import OrganizationAgent
from .publicity_agent import PublicityAgent
from .risk_agent import RiskAgent
from .siliconflow_client import SiliconFlowConfig
from .stats_agent import StatsAgent
from .term_agent import TermAgent


class MasterAgent:
    def __init__(self):
        self.term = TermAgent()
        self.notification = NotificationAgent()
        self.organization = OrganizationAgent()
        self.risk = RiskAgent()
        self.audit = AuditAgent(self.risk)
        self.counselor = CounselorAgent()
        self.appeal = AppealAgent()
        self.publicity = PublicityAgent()
        self.stats = StatsAgent()
        self.export = ExportAgent()

        deepseek_config = DeepSeekConfig(
            api_key=current_app.config["DEEPSEEK_API_KEY"],
            base_url=current_app.config["DEEPSEEK_BASE_URL"],
            model=current_app.config["MATERIAL_PARSER_MODEL"],
            timeout=current_app.config["MATERIAL_PARSER_TIMEOUT"],
        )

        siliconflow_config = None
        if current_app.config.get("SILICONFLOW_API_KEY"):
            siliconflow_config = SiliconFlowConfig(
                api_key=current_app.config["SILICONFLOW_API_KEY"],
                base_url=current_app.config.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
                model=current_app.config.get("SILICONFLOW_VISION_MODEL", "Qwen/Qwen3-VL-8B-Instruct"),
                timeout=current_app.config.get("SILICONFLOW_TIMEOUT", 60),
            )

        self.material_parser = MaterialParser(deepseek_config, siliconflow_config)

    @property
    def auth(self) -> AuthAgent:
        return AuthAgent(current_app.config["SECRET_KEY"])

    def dashboard(self, user: User) -> dict:
        app = current_app._get_current_object()
        user_id = user.id
        tasks = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            if user.role == "student":
                tasks["summary"] = executor.submit(self._with_user_context, app, user_id, self.audit.student_summary)
                tasks["rank"] = executor.submit(self._with_app_context, app, self.publicity.ranking, None, True)
                tasks["appeals"] = executor.submit(self._with_user_context, app, user_id, self.appeal.list)
            else:
                tasks["pending"] = executor.submit(self._with_user_context, app, user_id, self.counselor.list_pending)
                tasks["rank"] = executor.submit(self._with_app_context, app, self.publicity.ranking, None, False)
                tasks["risk"] = executor.submit(self._with_app_context, app, self.risk.report)
            tasks["currentTerm"] = executor.submit(self._with_app_context, app, self.term.current_term)
            return {name: task.result() for name, task in tasks.items()}

    def _with_app_context(self, app, func, *args):
        with app.app_context():
            return func(*args)

    def _with_user_context(self, app, user_id: int, func):
        with app.app_context():
            user = db.session.get(User, user_id)
            return func(user)

