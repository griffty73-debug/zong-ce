from __future__ import annotations

import base64
import json
import re
from io import BytesIO
from typing import Any

from flask import abort
from PyPDF2 import PdfReader

from .deepseek_client import DeepSeekClient, DeepSeekConfig
from .siliconflow_client import SiliconFlowClient, SiliconFlowConfig
from .responses import agent_response
from .scoring_rules import CATEGORY_SCORE_CAPS, score_material


ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/pdf",
}
MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_RAW_CONTENT_LENGTH = 8000


class MaterialParser:
    def __init__(self, config: DeepSeekConfig, siliconflow_config: SiliconFlowConfig | None = None):
        self.config = config
        self.client = DeepSeekClient(config)
        self.vision_client = SiliconFlowClient(siliconflow_config) if siliconflow_config else None

    def parse(self, file_data: bytes, content_type: str, filename: str = "") -> dict[str, Any]:
        if content_type not in ALLOWED_MIME_TYPES:
            abort(400, description="不支持的文件类型")
        if len(file_data) > MAX_FILE_SIZE:
            abort(400, description="文件大小超过 5MB 限制")
        if not file_data:
            abort(400, description="文件内容为空")

        if content_type == "application/pdf":
            result = self.parse_pdf(file_data)
        else:
            result = self.parse_image(file_data, content_type)

        result["fileName"] = filename
        return agent_response(
            agent="Material Parser",
            message="文件解析完成",
            suggestions_key="audit",
            data={
                "success": True,
                "data": result,
            },
        )

    def parse_pdf(self, file_data: bytes) -> dict[str, Any]:
        try:
            reader = PdfReader(BytesIO(file_data))
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception:
            abort(400, description="无法解析文件内容")

        content = "\n".join(page.strip() for page in pages if page.strip())
        if not content.strip():
            abort(400, description="无法解析文件内容")
        return self.analyze_content(content, "PDF")

    def parse_image(self, file_data: bytes, content_type: str) -> dict[str, Any]:
        base64_image = base64.b64encode(file_data).decode("utf-8")
        mime_type = content_type
        return self.analyze_image(base64_image, mime_type)

    def analyze_image(self, base64_image: str, mime_type: str) -> dict[str, Any]:
        if self.vision_client:
            try:
                content = self.vision_client.analyze_image(
                    base64_image,
                    mime_type,
                    prompt="请分析这张图片中的材料内容，提取关键信息并给出评分建议。",
                    system_prompt=self._system_prompt(),
                    max_tokens=1200,
                )
                raw_content = f"[图片数据 base64:{len(base64_image)}字符]"
                return self._normalize_result(content, raw_content=raw_content)
            except Exception as e:
                error_msg = str(e)
                if "image" in error_msg.lower() or "vision" in error_msg.lower():
                    abort(400, description=f"图片解析失败：{error_msg}")
                raise

    def analyze_content(self, content: str, file_type: str) -> dict[str, Any]:
        raw_content = content.strip()[:MAX_RAW_CONTENT_LENGTH]
        result = self.client.chat(
            [
                {"role": "system", "content": self._system_prompt()},
                {
                    "role": "user",
                    "content": (
                        f"文件类型：{file_type}\n\n"
                        "材料内容如下：\n"
                        f"{raw_content}\n\n"
                        "请仅返回 JSON，不要输出 Markdown 或解释。"
                    ),
                },
            ],
            temperature=0.1,
            max_tokens=1200,
        )
        return self._normalize_result(result.get("content", ""), raw_content=raw_content)

    def _system_prompt(self) -> str:
        return """
你是一个高校综合测评材料分析助手。请分析材料内容，提取关键信息并给出评分建议。

输出要求：仅返回 JSON，字段如下：
{
  "title": "材料名称/奖项名称",
  "category": "五育类别（德育/智育/体育/美育/劳育/能力）",
  "certificateNo": "证书编号，若无则为空字符串",
  "description": "材料描述摘要，50字以内",
  "suggestedScore": 0,
  "level": "级别（国家级/省级/市级/校级/院级/未标注）",
  "role": "角色（个人/队长/负责人/干部/成员）",
  "reasoning": "识别依据说明，30字以内",
  "confidence": "匹配度（high/medium/low）"
}

规则：
1. category 必须从 德育、智育、体育、美育、劳育、能力 中选择。
2. 国家级一等奖建议 5-10 分，省级一等奖建议 3-5 分，校级一等奖建议 1-2 分，等级越低分数越低。
3. 若无法识别有效信息，confidence 设为 low，title 设为“未识别材料”。
""".strip()

    def _normalize_result(self, content: str, *, raw_content: str) -> dict[str, Any]:
        parsed = self._parse_json(content)
        category = self._category(parsed.get("category"))
        title = self._string(parsed.get("title")) or "未识别材料"
        description = self._string(parsed.get("description"))[:80]
        certificate_no = self._string(parsed.get("certificateNo") or parsed.get("certificate_no"))
        level = self._level(parsed.get("level"))
        role = self._role(parsed.get("role"))
        confidence = self._confidence(parsed.get("confidence"))
        suggested_score = self._score(parsed.get("suggestedScore") or parsed.get("score"))

        local_payload = {
            "title": title,
            "category": category,
            "description": description,
            "certificateNo": certificate_no,
            "level": level,
            "role": role,
            "rawContent": raw_content,
            "score": suggested_score,
        }
        try:
            decision = score_material(local_payload)
            if suggested_score <= 0:
                suggested_score = float(decision.final_score)
            reasoning = self._string(parsed.get("reasoning")) or "依据材料文本与本地评分规则生成"
        except Exception:
            reasoning = self._string(parsed.get("reasoning")) or "依据材料文本生成"

        if not description:
            description = raw_content.replace("\n", " ")[:50]

        return {
            "title": title,
            "category": category,
            "certificateNo": certificate_no,
            "description": description,
            "suggestedScore": suggested_score,
            "level": level,
            "role": role,
            "reasoning": reasoning[:50],
            "confidence": confidence,
            "rawContent": raw_content,
        }

    def _parse_json(self, content: str) -> dict[str, Any]:
        cleaned = content.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.S)
        if fenced:
            cleaned = fenced.group(1)
        else:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start >= 0 and end > start:
                cleaned = cleaned[start : end + 1]
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            abort(400, description="AI 分析失败：未返回有效 JSON")
        if not isinstance(parsed, dict):
            abort(400, description="AI 分析失败：返回结构不正确")
        return parsed

    def _category(self, value: Any) -> str:
        category = self._string(value)
        return category if category in CATEGORY_SCORE_CAPS else "能力"

    def _level(self, value: Any) -> str:
        level = self._string(value) or "未标注"
        return level if level.endswith("级") or level == "未标注" else f"{level}级"

    def _role(self, value: Any) -> str:
        role = self._string(value)
        return role if role in {"个人", "队长", "负责人", "干部", "成员"} else "个人"

    def _confidence(self, value: Any) -> str:
        confidence = self._string(value).lower()
        return confidence if confidence in {"high", "medium", "low"} else "medium"

    def _score(self, value: Any) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        return min(max(round(score * 2) / 2, 0), 20)

    def _string(self, value: Any) -> str:
        return str(value or "").strip()
