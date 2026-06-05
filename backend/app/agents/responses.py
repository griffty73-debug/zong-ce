from __future__ import annotations

from typing import Any


SUGGESTIONS = {
    "auth_unverified": [
        "我是学生，如何验证身份",
        "我是老师，忘记工号怎么办",
        "验证后系统可以办理哪些业务",
    ],
    "student": [
        "我要提交综测材料",
        "查询我的综测审核进度",
        "错过了公示期怎么申诉",
    ],
    "staff": [
        "查看待审核学生列表",
        "审核单个学生材料",
        "发起班级匿名公示",
    ],
    "audit": [
        "继续上传获奖证书",
        "帮我看看现在的总分是多少",
        "确认提交当前所有材料",
    ],
    "appeal": [
        "查看当前申诉处理状态",
        "补充申诉证明材料",
        "确认一审结果正确",
    ],
    "publicity": [
        "查看当前最新的公示榜单与排名",
        "公示还剩多少时间结束",
        "我对公示里的总分有异议怎么办",
    ],
    "archive": [
        "导出最终综测归档报表",
        "查看奖学金系统同步状态",
        "开启下一年度综测评定准备",
    ],
}


def suggestions(key: str) -> list[str]:
    return SUGGESTIONS.get(key, [])


def agent_response(
    *,
    agent: str,
    message: str,
    status: str = "ok",
    suggestions_key: str | None = None,
    data: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "agentName": agent,
        "message": message,
        "suggestions": suggestions(suggestions_key or ""),
    }
    if data:
        payload.update(data)
    payload.update(extra)
    return payload
