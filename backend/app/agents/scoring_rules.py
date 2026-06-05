from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from flask import abort


TWOPLACES = Decimal("0.01")


@dataclass(frozen=True)
class ScoreDecision:
    category: str
    rule_name: str
    level: str
    role: str
    raw_score: Decimal
    final_score: Decimal
    cap: Decimal | None
    rule_key: str
    event_key: str | None
    reasons: list[str]
    confidence: str = "matched"

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "ruleName": self.rule_name,
            "level": self.level,
            "role": self.role,
            "rawScore": float(self.raw_score),
            "score": float(self.final_score),
            "cap": float(self.cap) if self.cap is not None else None,
            "ruleKey": self.rule_key,
            "eventKey": self.event_key,
            "reasons": self.reasons,
            "confidence": self.confidence,
        }


CATEGORY_SCORE_CAPS = {
    "德育": Decimal("15.0"),
    "智育": Decimal("20.0"),
    "体育": Decimal("8.0"),
    "美育": Decimal("6.0"),
    "劳育": Decimal("6.0"),
    "能力": Decimal("8.0"),
}

LEVEL_SCORES = {
    "国家级": Decimal("0"),
    "省级": Decimal("0"),
    "市级": Decimal("0"),
    "校级": Decimal("0"),
    "院级": Decimal("0"),
}

CONTEST_SCORES = {
    "国家级": {"一等": Decimal("10"), "二等": Decimal("5"), "三等": Decimal("3")},
    "省级": {"一等": Decimal("5"), "二等": Decimal("3"), "三等": Decimal("2")},
    "市级": {"一等": Decimal("3"), "二等": Decimal("2"), "三等": Decimal("1")},
    "校级": {"一等": Decimal("2"), "二等": Decimal("1.5"), "三等": Decimal("1")},
    "院级": {"一等": Decimal("1"), "二等": Decimal("1"), "三等": Decimal("1")},
}

SPORT_ART_SCORES = {
    "校级": {"一等": Decimal("2"), "二等": Decimal("1.5"), "三等": Decimal("1"), "优秀": Decimal("0.8")},
    "院级": {"一等": Decimal("1.5"), "二等": Decimal("1.2"), "三等": Decimal("0.8"), "优秀": Decimal("0.3")},
}


def quantize(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def score_material(payload: dict) -> ScoreDecision:
    text = _text(payload)
    category = str(payload.get("category", "")).strip()
    if category not in CATEGORY_SCORE_CAPS:
        abort(400, description="五育类别不合法")

    level = _level(payload, text)
    role = _role(payload, text)
    event_key = _event_key(payload, text)

    decision = (
        _moral_score(payload, text, category, level, role, event_key)
        or _intellectual_score(payload, text, category, level, role, event_key)
        or _sports_score(payload, text, category, level, role, event_key)
        or _aesthetic_score(payload, text, category, level, role, event_key)
        or _ability_score(payload, text, category, level, role, event_key)
        or _fallback_score(payload, category, level, role, event_key)
    )
    return decision


def apply_existing_constraints(
    decision: ScoreDecision,
    *,
    existing_rule_score: Decimal = Decimal("0"),
    existing_event_score: Decimal | None = None,
) -> ScoreDecision:
    reasons = [*decision.reasons]
    final_score = decision.raw_score

    if decision.cap is not None:
        remaining = max(Decimal("0"), decision.cap - existing_rule_score)
        if final_score > remaining:
            reasons.append(f"{decision.rule_name}累计达到上限，按剩余额度计分")
            final_score = remaining

    if existing_event_score is not None and existing_event_score >= final_score and final_score > 0:
        reasons.append("同赛事已存在不低于本次的加分记录，本次不重复加分")
        final_score = Decimal("0")

    return ScoreDecision(
        category=decision.category,
        rule_name=decision.rule_name,
        level=decision.level,
        role=decision.role,
        raw_score=decision.raw_score,
        final_score=quantize(final_score),
        cap=decision.cap,
        rule_key=decision.rule_key,
        event_key=decision.event_key,
        reasons=reasons,
        confidence=decision.confidence,
    )


def _decision(
    *,
    category: str,
    rule_name: str,
    level: str,
    role: str,
    score: Decimal,
    cap: Decimal | None = None,
    event_key: str | None = None,
    reasons: list[str] | None = None,
    confidence: str = "matched",
) -> ScoreDecision:
    return ScoreDecision(
        category=category,
        rule_name=rule_name,
        level=level,
        role=role,
        raw_score=quantize(score),
        final_score=quantize(score),
        cap=cap,
        rule_key=f"{category}:{rule_name}",
        event_key=event_key,
        reasons=reasons or [],
        confidence=confidence,
    )


def _text(payload: dict) -> str:
    fields = [
        payload.get("title"),
        payload.get("description"),
        payload.get("ocrText"),
        payload.get("rawContent"),
        payload.get("materialName"),
        payload.get("level"),
        payload.get("role"),
        payload.get("award"),
    ]
    return " ".join(str(item) for item in fields if item)


def _level(payload: dict, text: str) -> str:
    raw = str(payload.get("level", "")).strip()
    if raw:
        return raw if raw.endswith("级") else f"{raw}级"
    for level in LEVEL_SCORES:
        if level in text or level.removesuffix("级") in text:
            return level
    return "未标注"


def _role(payload: dict, text: str) -> str:
    raw = str(payload.get("role", "")).strip()
    if raw:
        return raw
    if "队长" in text or "负责人" in text:
        return "队长"
    if "干部" in text or "班长" in text or "宿舍长" in text:
        return "干部"
    if "成员" in text or "组员" in text:
        return "成员"
    return "个人"


def _award(text: str) -> str:
    for award in ("一等", "二等奖", "二等", "三等奖", "三等", "优秀"):
        if award in text:
            return award.replace("等奖", "等")
    return "三等"


def _event_key(payload: dict, text: str) -> str | None:
    explicit = str(payload.get("eventName") or payload.get("competitionName") or "").strip()
    if explicit:
        return _normalize_key(explicit)
    if any(keyword in text for keyword in ("竞赛", "比赛", "SRP", "项目")):
        cleaned = re.sub(r"(国家级|省级|市级|校级|院级|一等|二等|三等|一等奖|二等奖|三等奖|优秀奖|获奖|证书)", "", text)
        return _normalize_key(cleaned[:80])
    return None


def _normalize_key(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def _hours(payload: dict, text: str) -> Decimal:
    if payload.get("hours") not in {None, ""}:
        return Decimal(str(payload["hours"]))
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:小时|h)", text, re.IGNORECASE)
    return Decimal(match.group(1)) if match else Decimal("0")


def _moral_score(payload: dict, text: str, category: str, level: str, role: str, event_key: str | None):
    if category != "德育":
        return None
    if "优秀志愿者" in text:
        return _decision(
            category=category,
            rule_name="优秀志愿者",
            level=level,
            role=role,
            score={"院级": Decimal("1"), "校级": Decimal("2")}.get(level, Decimal("1")),
            cap=Decimal("4"),
        )
    if "志愿" in text:
        times = int(_hours(payload, text) // Decimal("8"))
        score = Decimal(times) * Decimal("0.5")
        return _decision(category=category, rule_name="志愿活动", level=level, role=role, score=score, cap=Decimal("4"))
    if "先进个人" in text:
        return _decision(
            category=category,
            rule_name="先进个人",
            level=level,
            role=role,
            score={"国家级": Decimal("5"), "省级": Decimal("4"), "校级": Decimal("3"), "院级": Decimal("2")}.get(level, Decimal("0")),
            cap=Decimal("15"),
        )
    if "文明班级" in text or "五四红旗" in text:
        return _decision(category=category, rule_name="集体荣誉", level=level, role=role, score=Decimal("3" if role == "干部" else "1"))
    if "零挂科宿舍" in text:
        return _decision(category=category, rule_name="班寝奖励", level=level, role=role, score=Decimal("1"))
    if "零挂科班级" in text:
        return _decision(category=category, rule_name="班寝奖励", level=level, role=role, score=Decimal("4"))
    if "无诈班级" in text or "平安班级" in text:
        return _decision(category=category, rule_name="班寝奖励", level=level, role=role, score=Decimal("1"))
    if "献血" in text:
        return _decision(category=category, rule_name="献血", level=level, role=role, score=Decimal("1"))
    if "见义勇为" in text:
        return _decision(
            category=category,
            rule_name="见义勇为",
            level=level,
            role=role,
            score={"国家级": Decimal("25"), "省级": Decimal("20"), "市级": Decimal("15"), "校级": Decimal("10")}.get(level, Decimal("0")),
        )
    return None


def _intellectual_score(payload: dict, text: str, category: str, level: str, role: str, event_key: str | None):
    if category != "智育":
        return None
    if "专业第一" in text:
        return _decision(category=category, rule_name="学习表现", level=level, role=role, score=Decimal("1"))
    if "班级第一" in text:
        return _decision(category=category, rule_name="学习表现", level=level, role=role, score=Decimal("0.5"))
    if "论文" in text or "期刊" in text:
        scores = {
            "顶级": Decimal("200"),
            "高水平A": Decimal("100"),
            "T1": Decimal("100"),
            "高水平B": Decimal("80"),
            "T2": Decimal("80"),
            "C类": Decimal("50"),
            "核心": Decimal("30"),
            "国家级": Decimal("8"),
            "省级": Decimal("5"),
        }
        score = next((value for key, value in scores.items() if key in text), Decimal("1"))
        return _decision(category=category, rule_name="论文发表", level=level, role=role, score=score)
    if "软件著作权" in text or "软著" in text:
        rank = int(payload.get("authorRank") or _rank(text) or 1)
        ratio = [Decimal("0.4"), Decimal("0.3"), Decimal("0.2"), Decimal("0.1")][min(max(rank, 1), 4) - 1]
        return _decision(category=category, rule_name="软件著作权", level=level, role=f"第{rank}作者", score=Decimal("5") * ratio)
    if "发明授权" in text:
        return _decision(category=category, rule_name="专利", level=level, role=role, score=Decimal("20"))
    if "发明受理" in text:
        return _decision(category=category, rule_name="专利", level=level, role=role, score=Decimal("5"))
    if "实用新型" in text:
        return _decision(category=category, rule_name="专利", level=level, role=role, score=Decimal("10"))
    if "六级" in text:
        return _decision(category=category, rule_name="英语等级证书", level="六级", role=role, score=Decimal("3"), cap=Decimal("3"))
    if "四级" in text:
        return _decision(category=category, rule_name="英语等级证书", level="四级", role=role, score=Decimal("2"), cap=Decimal("3"))
    if "计算机四级" in text:
        return _decision(category=category, rule_name="计算机等级证书", level="四级", role=role, score=Decimal("3"))
    if "计算机三级" in text:
        return _decision(category=category, rule_name="计算机等级证书", level="三级", role=role, score=Decimal("2"))
    if "计算机二级" in text:
        return _decision(category=category, rule_name="计算机等级证书", level="二级", role=role, score=Decimal("1"))
    if "高级" in text and "资格" in text:
        return _decision(category=category, rule_name="专业资格证", level="高级", role=role, score=Decimal("10"))
    if "中级" in text and "资格" in text:
        return _decision(category=category, rule_name="专业资格证", level="中级", role=role, score=Decimal("5"))
    if "初级" in text and "资格" in text:
        return _decision(category=category, rule_name="专业资格证", level="初级", role=role, score=Decimal("3"))
    if "CSP" in text or "CCSP" in text:
        return _decision(category=category, rule_name="CSP/CCSP", level=level, role=role, score=Decimal("5"))
    if "竞赛" in text or "SRP" in text:
        score = CONTEST_SCORES.get(level, CONTEST_SCORES["院级"]).get(_award(text), Decimal("1"))
        reasons = []
        if role not in {"队长", "负责人", "个人"}:
            score *= Decimal("0.7")
            reasons.append("成员按基础分值的 0.7 折算")
        rule_name = "SRP项目" if "SRP" in text else "学科竞赛"
        cap = Decimal("999") if rule_name == "SRP项目" else None
        return _decision(category=category, rule_name=rule_name, level=level, role=role, score=score, cap=cap, event_key=event_key, reasons=reasons)
    return None


def _sports_score(payload: dict, text: str, category: str, level: str, role: str, event_key: str | None):
    if category != "体育":
        return None
    if "破纪录" in text:
        return _decision(category=category, rule_name="破纪录", level=level, role=role, score=Decimal("5" if level == "校级" else "3"))
    if "完赛" in text:
        return _decision(category=category, rule_name="完赛", level=level, role=role, score=Decimal("0.3"))
    if "方队" in text:
        return _decision(category=category, rule_name="运动会方队", level=level, role=role, score=Decimal("1"))
    if "比赛" in text or "竞赛" in text:
        base = SPORT_ART_SCORES.get(level, SPORT_ART_SCORES["校级"]).get(_award(text), Decimal("1"))
        if level == "国家级":
            base = SPORT_ART_SCORES["校级"].get(_award(text), Decimal("1")) * Decimal("3")
        if level == "省级":
            base = SPORT_ART_SCORES["校级"].get(_award(text), Decimal("1")) * Decimal("2")
        return _decision(category=category, rule_name="体育比赛获奖", level=level, role=role, score=base, event_key=event_key)
    return None


def _aesthetic_score(payload: dict, text: str, category: str, level: str, role: str, event_key: str | None):
    if category != "美育":
        return None
    if "文明宿舍" in text:
        if "校级" in text:
            score = Decimal("2")
        else:
            score = {"一星": Decimal("0.3"), "二星": Decimal("0.5"), "三星": Decimal("0.8"), "四星": Decimal("1")}.get(
                next((key for key in ("一星", "二星", "三星", "四星") if key in text), "一星"),
                Decimal("0.3"),
            )
        if role == "干部":
            score += Decimal("0.5")
        return _decision(category=category, rule_name="宿舍文明", level=level, role=role, score=score)
    if "宣传" in text or "文学" in text:
        score = {"国家级": Decimal("4"), "省级": Decimal("3"), "市级": Decimal("2"), "校级": Decimal("1")}.get(level, Decimal("1"))
        return _decision(category=category, rule_name="宣传文学", level=level, role=role, score=score, cap=Decimal("12"))
    if "演出" in text:
        score = Decimal("1") if level == "校级" else Decimal("0.5")
        return _decision(category=category, rule_name="演出活动", level=level, role=role, score=score, cap=Decimal("3"))
    if "比赛" in text or "竞赛" in text:
        base = SPORT_ART_SCORES.get(level, SPORT_ART_SCORES["校级"]).get(_award(text), Decimal("1"))
        if level == "国家级":
            base = SPORT_ART_SCORES["校级"].get(_award(text), Decimal("1")) * Decimal("2")
        if level == "省级":
            base = SPORT_ART_SCORES["校级"].get(_award(text), Decimal("1")) * Decimal("1.5")
        return _decision(category=category, rule_name="文艺比赛", level=level, role=role, score=base, event_key=event_key)
    return None


def _ability_score(payload: dict, text: str, category: str, level: str, role: str, event_key: str | None):
    if category not in {"能力", "劳育"}:
        return None
    if "主席团" in text or "团委副书记" in text:
        score = Decimal("5") if "校" in text else Decimal("4")
        return _decision(category=category, rule_name="学生干部", level=level, role=role, score=score, cap=Decimal("8"))
    if "部长" in text or "班长" in text or "团支书" in text or "学委" in text:
        score = Decimal("4") if "校" in text else Decimal("3")
        return _decision(category=category, rule_name="学生干部", level=level, role=role, score=score, cap=Decimal("8"))
    if "班委" in text:
        return _decision(category=category, rule_name="学生干部", level=level, role=role, score=Decimal("2"), cap=Decimal("8"))
    if "干事" in text or "宿舍长" in text:
        return _decision(category=category, rule_name="学生干部", level=level, role=role, score=Decimal("0.5"), cap=Decimal("8"))
    if "社会实践" in text:
        score = {"国家级": Decimal("4"), "省级": Decimal("3"), "校级": Decimal("2"), "院级": Decimal("1")}.get(level, Decimal("1"))
        return _decision(category=category, rule_name="社会实践优秀个人", level=level, role=role, score=score)
    if "工先" in text:
        score = {"国家级": Decimal("3"), "省级": Decimal("2"), "校级": Decimal("1"), "院级": Decimal("0.5")}.get(level, Decimal("0.5"))
        return _decision(category=category, rule_name="年度工先", level=level, role=role, score=score, cap=Decimal("4"))
    if "工作人员" in text:
        return _decision(category=category, rule_name="工作人员", level=level, role=role, score=Decimal("0.5"), cap=Decimal("3"))
    return None


def _fallback_score(payload: dict, category: str, level: str, role: str, event_key: str | None):
    requested = Decimal(str(payload.get("score") or "0"))
    if requested <= 0:
        abort(400, description="无法识别，原因：未匹配到系统评分规则")
    cap = CATEGORY_SCORE_CAPS[category]
    return _decision(
        category=category,
        rule_name="人工预估材料",
        level=level,
        role=role,
        score=min(requested, cap),
        cap=cap,
        event_key=event_key,
        reasons=["未匹配到细则条目，按人工预估分进入待审复核"],
        confidence="fallback",
    )


def _rank(text: str) -> int | None:
    match = re.search(r"第([一二三四1234])作者", text)
    if not match:
        return None
    value = match.group(1)
    if value in {"一", "二", "三", "四"}:
        return {"一": 1, "二": 2, "三": 3, "四": 4}[value]
    return int(value)
