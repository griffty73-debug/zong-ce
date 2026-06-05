from __future__ import annotations

from typing import Any

from flask import abort

from ..models import User
from .deepseek_client import DeepSeekClient, DeepSeekConfig
from .responses import agent_response


MAX_PROMPT_LENGTH = 4000
MAX_MESSAGES = 12


SCORING_RULES_PROMPT = """【综测评分规则】当用户询问综测分数相关问题时，必须以此规则为基准进行回答：

## 通用规则
- 所有分值保留两位小数（如：1.40 分）
- 成员折算：规则标明"成员×0.7"的（如SRP项目、学科竞赛），若身份为非队长成员，基础分值必须乘以 0.7
- 同赛事取最高奖：同一项竞赛或活动，学生上传多张不同奖项证书时，系统自动识别并仅保留最高分的一项，其余项不予加分
- 上限封顶拦截：当某分类累计得分达到上限时，后续同类材料正常列出，但加分计为 +0，且不增加总分

## 五育评分细则

### 德育模块
- 先进个人：国家级 +5 | 省级 +4 | 校级 +3 | 院级 +2（总上限 15 分）
- 志愿活动：每 8 小时计 1 次，每次 +0.5（上限 4 分）
- 优秀志愿者：院级 +1 | 校级 +2（上限 4 分）
- 集体荣誉（文明班级/五四红旗团支部）：干部 +3 | 成员 +1
- 班寝奖励：零挂科宿舍 +1 | 零挂科班级 +4 | 无诈班级 +1 | 平安班级 +1
- 其他：献血 +1/学期 | 见义勇为（国家级 +25 | 省级 +20 | 市级 +15 | 校级 +10）

### 智育模块
- 学习表现：单科专业第一 +1 | 班级第一 +0.5
- 论文发表：顶级期刊 +200 | 高水平A/T1 +100 | 高水平B/T2 +80 | C类 +50 | 核心 +30 | 国家级 +8 | 省级 +5 | 普通 +1
- 知识产权（软件著作权）：每项 +5（按 4:3:2:1 比例顺位分配作者得分）
- 知识产权（专利）：发明授权 +20 | 发明受理 +5 | 实用新型 +10
- 英语等级证书：四级 +2 | 六级 +3（仅取最高项，不累计）
- 计算机等级证书：二级 +1 | 三级 +2 | 四级 +3
- 专业资格证：初级 +3 | 中级 +5 | 高级 +10
- CSP/CCSP +5
- SRP项目/学科竞赛：国家级一等10/二等5/三等3，省级一等5/二等3/三等2，市级一等3/二等2/三等1，校级一等2/二等1.5/三等1，院级/SRP校重点+2/SRP校一般+1。队长拿全分，成员分值×0.7。同赛事仅取最高奖。学科竞赛最多累计 5 项。

### 体育模块
- 比赛获奖：校级（一等2/二等1.5/三等1）| 院级（一等1.5/二等1.2/三等0.8）| 国家级（按校级×3）| 省级（按校级×2）
- 其他：破纪录（校级+5/院级+3）| 完赛+0.3 | 运动会方队+1

### 美育模块
- 文艺比赛：校级（一等2/二等1.5/三等1/优秀奖0.8）| 院级（一等1.5/二等1.2/三等0.8/优秀奖0.3）| 国家级（按校级×2）| 省级（按校级×1.5）
- 宿舍文明：一星0.3|二星0.5|三星0.8|四星1|校级文明宿舍2（宿舍长额外+0.5）
- 宣传文学：国家级4|省级3|市级2|校级1（最多累计3篇最高项）
- 演出活动：校级+1/次|院级+0.5/次（上限3分）

### 能力模块
- 学生干部：校主席团/团委副书记5|校部长/院主席团4|院部长/团总支/班长/团支书/学委3|其他班委2|干事/宿舍长0.5（总上限8分）
- 社会实践优秀个人：国家级4|省级3|校级2|院级1
- 年度工先：国家级3|省级2|校级1|院级0.5（先进个人与工先总上限4分）
- 工作人员：+0.5/次（上限3分）

## 五育上限
德育15分|智育20分|体育8分|美育6分|劳育6分|能力8分
"""


class DeepSeekAgent:
    def __init__(self, config: DeepSeekConfig):
        self.config = config
        self.client = DeepSeekClient(config)

    def status(self) -> dict[str, Any]:
        return agent_response(
            agent="DeepSeek Agent",
            message="DeepSeek V4 Pro 模型配置已加载" if self.config.api_key else "DeepSeek V4 Pro 模型尚未配置 API key",
            data={
                "configured": bool(self.config.api_key),
                "model": self.config.model,
                "baseUrl": self.config.base_url,
            },
        )

    def chat(self, user: User, payload: dict[str, Any]) -> dict[str, Any]:
        messages = self._messages(user, payload)
        temperature = self._bounded_float(payload.get("temperature", 0.2), 0, 1, 0.2)
        max_tokens = self._bounded_int(payload.get("maxTokens", 900), 256, 2000, 900)
        result = self.client.chat(messages, temperature=temperature, max_tokens=max_tokens)
        return agent_response(
            agent="DeepSeek Agent",
            message="DeepSeek V4 Pro 已完成本次智能分析",
            suggestions_key="audit" if user.role == "student" else "staff",
            data={
                "model": result["model"],
                "content": result["content"],
                "usage": result["usage"],
                "finishReason": result["finishReason"],
            },
        )

    def _messages(self, user: User, payload: dict[str, Any]) -> list[dict[str, Any]]:
        incoming = payload.get("messages")
        if incoming is None:
            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                abort(400, description="prompt 不能为空")
            if len(prompt) > MAX_PROMPT_LENGTH:
                abort(400, description=f"prompt 不能超过 {MAX_PROMPT_LENGTH} 字符")
            incoming = [{"role": "user", "content": prompt}]

        if not isinstance(incoming, list) or not incoming:
            abort(400, description="messages 必须是非空数组")
        if len(incoming) > MAX_MESSAGES:
            abort(400, description=f"messages 不能超过 {MAX_MESSAGES} 条")

        messages = [self._system_message(user)]
        for item in incoming:
            if not isinstance(item, dict):
                abort(400, description="messages 中的每一项必须是对象")
            role = str(item.get("role", "user")).strip()
            if role not in {"user", "assistant"}:
                abort(400, description="messages.role 仅支持 user 或 assistant")
            
            # 正确处理内容：可能是字符串，也可能是包含 image_url 的列表
            content = item.get("content")
            if isinstance(content, str):
                content = content.strip()
                if not content:
                    abort(400, description="messages.content 不能为空")
                if len(content) > MAX_PROMPT_LENGTH:
                    abort(400, description=f"单条消息不能超过 {MAX_PROMPT_LENGTH} 字符")
            elif isinstance(content, list):
                text_parts = []
                image_parts = []
                for block in content:
                    if not isinstance(block, dict):
                        abort(400, description="messages.content 块必须是对象")
                    block_type = block.get("type")
                    if block_type == "text":
                        text = block.get("text", "").strip()
                        if text:
                            text_parts.append(text)
                    elif block_type == "image_url":
                        image_url_data = block.get("image_url", {})
                        if isinstance(image_url_data, dict):
                            url = image_url_data.get("url", "")
                            if url.startswith("data:"):
                                image_parts.append({"type": "image_url", "image_url": image_url_data})
                            elif url:
                                image_parts.append({"type": "image_url", "image_url": {"url": url}})
                    else:
                        abort(400, description=f"不支持的 content 类型: {block_type}")

                if text_parts and image_parts:
                    content = [{"type": "text", "text": "\n".join(text_parts)}] + image_parts
                elif image_parts:
                    content = image_parts
                elif text_parts:
                    content = "\n".join(text_parts)
                else:
                    abort(400, description="messages.content 不能为空")

                if isinstance(content, str) and len(content) > MAX_PROMPT_LENGTH:
                    abort(400, description=f"单条消息不能超过 {MAX_PROMPT_LENGTH} 字符")
            else:
                abort(400, description="messages.content 必须是字符串或数组")
            
            messages.append({"role": role, "content": content})
        return messages

    def _system_message(self, user: User) -> dict[str, str]:
        role_label = {"student": "学生", "teacher": "教师", "counselor": "辅导员"}.get(user.role, "用户")
        return {
            "role": "system",
            "content": (
                f"你是高校综合测评系统的智能助手。当前登录用户身份：{role_label}，学工号：{user.student_no}。\n\n"
                + SCORING_RULES_PROMPT
                + "\n\n请围绕综测材料、审核、申诉、公示、风控规则回答，保持简洁、准确、可执行。当用户询问综测分数相关问题时，必须以【综测评分规则】为基准进行回答。"
            ),
        }

    def _bounded_float(self, value: Any, minimum: float, maximum: float, default: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        return min(max(parsed, minimum), maximum)

    def _bounded_int(self, value: Any, minimum: int, maximum: int, default: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return min(max(parsed, minimum), maximum)
