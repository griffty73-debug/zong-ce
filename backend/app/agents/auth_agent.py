import re

from flask import abort
from itsdangerous import BadSignature, URLSafeTimedSerializer

from ..extensions import db
from ..models import User
from .common import infer_role
from .responses import agent_response


class AuthAgent:
    def __init__(self, secret_key: str):
        self.serializer = URLSafeTimedSerializer(secret_key=secret_key, salt="zong-ce-auth")

    def register(self, payload: dict) -> dict:
        student_no = str(payload.get("studentNo", "")).strip()
        name = str(payload.get("name", "")).strip()
        password = str(payload.get("password", "")).strip()
        class_name = str(payload.get("className", "")).strip() or None
        role = infer_role(student_no, payload.get("role"))

        if not student_no or not re.fullmatch(r"20\d{9}", student_no):
            abort(400, description="学号必须为20开头的11位纯数字")
        if not name:
            abort(400, description="姓名不能为空")
        if len(password) < 6:
            abort(400, description="密码至少 6 位")
        if User.query.filter_by(student_no=student_no).first():
            abort(409, description="该学工号已注册")

        user = User(student_no=student_no, name=name, role=role, class_name=class_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return self._session_payload(user)

    def login(self, payload: dict) -> dict:
        student_no = str(payload.get("studentNo", "")).strip()
        password = str(payload.get("password", "")).strip()

        if not student_no:
            abort(400, description="学工号不能为空")

        user = User.query.filter_by(student_no=student_no).first()

        if not user:
            if re.fullmatch(r"20\d{9}", student_no):
                role = "student"
                user = User(student_no=student_no, name=f"学生{student_no[-4:]}", role=role, class_name="计科2301")
                user.set_password(password or "123456")
                db.session.add(user)
                db.session.commit()
            else:
                abort(401, description="学工号或密码错误")
        elif not user.check_password(password):
            abort(401, description="学工号或密码错误")

        return self._session_payload(user)

    def current_user(self, token: str | None) -> User:
        if not token:
            abort(
                401,
                description=(
                    "欢迎使用综测助手。为了保障您的数据安全，请首先输入您的【学号】"
                    "（学生）或【工号】（老师/辅导员）以验证身份。"
                ),
            )
        try:
            data = self.serializer.loads(token, max_age=60 * 60 * 12)
        except BadSignature:
            abort(401, description="登录已失效，请重新登录")
        user = db.session.get(User, data.get("id"))
        if not user:
            abort(401, description="用户不存在")
        return user

    def _session_payload(self, user: User) -> dict:
        token = self.serializer.dumps({"id": user.id, "role": user.role})
        role_label = {"student": "学生", "teacher": "老师", "counselor": "辅导员"}[user.role]
        suggestion_key = "student" if user.role == "student" else "staff"
        return agent_response(
            agent="Auth Agent",
            message=f"身份验证成功！已为您锁定角色为：【{role_label} {user.student_no}】。欢迎进入系统，您现在可以开始办理相关业务了。",
            suggestions_key=suggestion_key,
            data={
                "token": token,
                "user": user.to_dict(),
                "menus": self._menus(user.role),
            },
        )

    def _menus(self, role: str) -> list[str]:
        common = ["总览", "公示排名", "智能助手"]
        if role == "student":
            return [*common, "材料上传", "我的申诉"]
        if role == "teacher":
            return [*common, "材料审核"]
        return [*common, "班级审核", "申诉处理", "公示发起"]
