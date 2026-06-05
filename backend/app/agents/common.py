import re

from flask import abort

from ..models import User


def infer_role(identifier: str, requested_role: str | None = None) -> str:
    del requested_role
    normalized = str(identifier).strip()
    if not re.fullmatch(r"20\d{9}", normalized):
        abort(400, description="未能识别该学号/工号，学号必须为20开头的11位纯数字。")
    if normalized == "123456":
        return "counselor"
    if len(normalized) <= 6:
        return "teacher"
    return "student"


def ensure_role(user: User, allowed_roles: set[str]) -> None:
    if user.role not in allowed_roles:
        abort(403, description="当前角色无权访问该功能")
