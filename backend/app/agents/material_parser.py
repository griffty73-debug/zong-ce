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
                    prompt=(
                        "请分析这张图片中的材料内容。"
                        "对奖项名称、证书编号、颁奖机构三个字段，分别给出在图片中的归一化包围框 [x1, y1, x2, y2]（取值 0-1，原点在左上角）。"
                    ),
                    system_prompt=self._system_prompt(),
                    max_tokens=1800,
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
你是一个高校综合测评材料分析助手。请分析材料内容，提取关键信息、定位关键字段在图片中的位置并给出评分建议。

输出要求：仅返回 JSON，字段如下：
{
  "title": "材料名称/奖项名称",
  "category": "五育类别（德育/智育/体育/美育/劳育/能力）",
  "certificateNo": "证书编号，若无则为空字符串",
  "issuer": "颁奖机构全称，无法识别则为空字符串",
  "description": "材料描述摘要，50字以内",
  "suggestedScore": 0,
  "level": "级别（国家级/省级/市级/校级/院级/未标注）",
  "role": "角色（个人/队长/负责人/干部/成员）",
  "reasoning": "识别依据说明，30字以内",
  "confidence": "匹配度（high/medium/low）",
  "regions": [
    {
      "label": "title | certificateNo | issuer",
      "text": "该区域内的文字",
      "box": [x1, y1, x2, y2],
      "confidence": 0.0
    }
  ]
}

区域定位规则：
1. box 坐标使用归一化值 0-1，原点在图片左上角，x1<x2, y1<y2。
2. 对 title / certificateNo / issuer 三个字段，如果能在图片中找到对应文字区域，必须给出 box 和 confidence。
3. confidence 范围 0-1，1 表示完全确定。
4. 若某字段在图片中不可见，regions 中可以省略该字段；不要编造坐标。
5. region 数量不超过 5 个；坐标精度保留 4 位小数。

评分规则：
1. category 必须从 德育、智育、体育、美育、劳育、能力 中选择。
2. 国家级一等奖建议 5-10 分，省级一等奖建议 3-5 分，校级一等奖建议 1-2 分，等级越低分数越低。
3. 若无法识别有效信息，confidence 设为 low，title 设为"未识别材料"。
""".strip()

    def _normalize_result(self, content: str, *, raw_content: str) -> dict[str, Any]:
        parsed = self._parse_json(content)
        category = self._category(parsed.get("category"))
        title = self._string(parsed.get("title")) or "未识别材料"
        description = self._string(parsed.get("description"))[:80]
        certificate_no = self._string(parsed.get("certificateNo") or parsed.get("certificate_no"))
        issuer = self._string(parsed.get("issuer") or parsed.get("organization"))
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

        regions = self._regions(parsed.get("regions"), title, certificate_no, issuer)

        return {
            "title": title,
            "category": category,
            "certificateNo": certificate_no,
            "issuer": issuer,
            "description": description,
            "suggestedScore": suggested_score,
            "level": level,
            "role": role,
            "reasoning": reasoning[:50],
            "confidence": confidence,
            "rawContent": raw_content,
            "regions": regions,
            "scoreBasis": self._score_basis(decision) if "decision" in locals() and decision else None,
        }

    def _regions(self, raw_regions: Any, title: str, certificate_no: str, issuer: str) -> list[dict[str, Any]]:
        regions: list[dict[str, Any]] = []
        if not isinstance(raw_regions, list):
            raw_regions = []
        valid_labels = {"title", "certificateNo", "issuer"}
        for item in raw_regions:
            if not isinstance(item, dict):
                continue
            label = self._string(item.get("label")).strip()
            if label not in valid_labels:
                continue
            box = self._box(item.get("box"))
            if not box:
                continue
            text = self._string(item.get("text"))
            if not text:
                text = {"title": title, "certificateNo": certificate_no, "issuer": issuer}.get(label, "")
            if not text:
                continue
            confidence = self._box_confidence(item.get("confidence"))
            regions.append(
                {
                    "label": label,
                    "text": text,
                    "box": box,
                    "confidence": confidence,
                }
            )
        return regions

    def _box(self, value: Any) -> list[float] | None:
        if not isinstance(value, (list, tuple)) or len(value) != 4:
            return None
        try:
            coords = [float(v) for v in value]
        except (TypeError, ValueError):
            return None
        x1, y1, x2, y2 = coords
        x1, x2 = sorted([max(0.0, min(1.0, x1)), max(0.0, min(1.0, x2))])
        y1, y2 = sorted([max(0.0, min(1.0, y1)), max(0.0, min(1.0, y2))])
        if x2 - x1 < 0.01 or y2 - y1 < 0.01:
            return None
        return [round(x1, 4), round(y1, 4), round(x2, 4), round(y2, 4)]

    def _box_confidence(self, value: Any) -> float:
        try:
            conf = float(value)
        except (TypeError, ValueError):
            return 0.6
        return round(max(0.0, min(1.0, conf)), 2)

    def _score_basis(self, decision: Any) -> dict[str, Any]:
        if decision is None:
            return None
        try:
            data = decision.to_dict()
        except AttributeError:
            return None
        data["citation"] = self._citation(decision)
        return data

    def _citation(self, decision: Any) -> str:
        rule_name = getattr(decision, "rule_name", None) or "未匹配细则"
        category = getattr(decision, "category", None) or "通用"
        level = getattr(decision, "level", None) or "未标注"
        role = getattr(decision, "role", None) or "个人"
        article = _RULE_ARTICLES.get(getattr(decision, "rule_name", ""), "通用条款")
        parts = [f"《综测细则》{article}"]
        if category and category != "通用":
            parts.append(f"{category}模块")
        if rule_name and rule_name not in {"未匹配细则", "人工预估材料"}:
            parts.append(rule_name)
        if level and level != "未标注":
            parts.append(level)
        if role and role != "个人":
            parts.append(f"({role})")
        return "·".join(parts)

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


_RULE_ARTICLES = {
    "优秀志愿者": "第2.1条",
    "志愿活动": "第2.2条",
    "先进个人": "第2.3条",
    "集体荣誉": "第2.4条",
    "班寝奖励": "第2.5条",
    "献血": "第2.6条",
    "见义勇为": "第2.7条",
    "学习表现": "第3.1条",
    "学科竞赛": "第3.2条",
    "SRP项目": "第3.3条",
    "论文发表": "第3.4条",
    "软件著作权": "第3.5条",
    "专利": "第3.6条",
    "英语等级证书": "第3.7条",
    "计算机等级证书": "第3.8条",
    "专业资格证": "第3.9条",
    "CSP/CCSP": "第3.10条",
    "破纪录": "第4.1条",
    "完赛": "第4.2条",
    "运动会方队": "第4.3条",
    "体育比赛获奖": "第4.4条",
    "文艺比赛": "第5.1条",
    "宿舍文明": "第5.2条",
    "宣传文学": "第5.3条",
    "演出活动": "第5.4条",
    "学生干部": "第6.1条",
    "社会实践优秀个人": "第6.2条",
    "年度工先": "第6.3条",
    "工作人员": "第6.4条",
    "人工预估材料": "第7.1条",
}
