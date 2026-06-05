from __future__ import annotations

import secrets
import threading
from time import time
from typing import Any

from flask import abort

from ..extensions import db
from ..models import Material, User
from ..state_machine import MaterialStatus, normalize_status
from .appeal_agent import AppealAgent
from .audit_agent import AuditAgent
from .counselor_agent import CounselorAgent
from .publicity_agent import PublicityAgent
from .risk_agent import RiskAgent


GESTURE_THRESHOLDS = {
    "OPEN_PALM": 0.85,
    "FIST": 0.8,
    "OK_SIGN": 0.9,
    "POINT": 0.8,
    "SWIPE_LEFT": 0.75,
    "SWIPE_RIGHT": 0.75,
    "SWIPE_UP": 0.75,
    "SWIPE_DOWN": 0.75,
    "V_SIGN": 0.8,
}

HIGH_RISK_ACTIONS = {"REJECT_MATERIAL", "SUBMIT_APPEAL"}
CONFIRMATION_TTL_SECONDS = 30
CONFIRMATION_HOLD_SECONDS = 3
DEBOUNCE_SECONDS = 2

STATUS_ALIASES = {
    "DRAFT": MaterialStatus.DRAFT.value,
    "SUBMITTED": MaterialStatus.SUBMITTED.value,
    "UNDER_REVIEW": MaterialStatus.REVIEWING.value,
    "REVIEWING": MaterialStatus.REVIEWING.value,
    "APPROVED": MaterialStatus.APPROVED.value,
    "REJECTED": MaterialStatus.REJECTED.value,
    "PUBLICITY": MaterialStatus.PUBLICIZING.value,
    "PUBLICIZING": MaterialStatus.PUBLICIZING.value,
    "FINISHED": MaterialStatus.PUBLICITY_ENDED.value,
    "PUBLICITY_ENDED": MaterialStatus.PUBLICITY_ENDED.value,
    "APPEAL_PROCESSING": MaterialStatus.APPEALING.value,
    "APPEALING": MaterialStatus.APPEALING.value,
    "APPEAL_EDITING": "APPEAL_EDITING",
}

PAGE_ALIASES = {
    "material_submit": "material_submit",
    "submit": "material_submit",
    "materials": "list",
    "material_list": "list",
    "list": "list",
    "review": "review",
    "publicity": "publicity",
    "rank": "publicity",
    "appeal": "appeal",
}

ACTION_LABELS = {
    "REJECT_MATERIAL": "打回材料",
    "SUBMIT_APPEAL": "提交申诉",
    "APPROVE_MATERIAL": "审核通过",
    "CLEAR_DRAFT": "撤销草稿",
    "SELECT_REVIEW": "选择审核记录",
    "NEXT_PAGE": "下一页",
    "PREV_PAGE": "上一页",
    "SCROLL_UP": "上划",
    "SCROLL_DOWN": "下划",
    "NEXT_REVIEW": "下一条待审",
    "PREV_REVIEW": "上一条待审",
    "MATERIAL_CAMERA_DISABLED": "材料上传页禁用摄像头",
}

_debounce_cache: dict[tuple[int, str, str, str], float] = {}
_pending_confirmations: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


class GestureAgent:
    def __init__(self):
        self.risk = RiskAgent()
        self.audit = AuditAgent(self.risk)
        self.appeal = AppealAgent()
        self.counselor = CounselorAgent()
        self.publicity = PublicityAgent()

    def dispatch(self, user: User, payload: dict) -> dict:
        self._assert_identity(user, payload)
        gesture = self._gesture(payload)
        page = self._page(payload)
        confidence = self._confidence(payload)
        threshold = GESTURE_THRESHOLDS.get(gesture)
        if threshold is None:
            return self._feedback(
                status="noop",
                action="UNBOUND_GESTURE",
                allowed=False,
                level="warning",
                message=f"手势 {gesture} 暂未绑定系统操作",
            )
        if confidence < threshold:
            return self._feedback(
                status="rejected",
                action="LOW_CONFIDENCE",
                allowed=False,
                level="warning",
                message="手势识别不稳定，请重新尝试",
                meta={"confidence": confidence, "threshold": threshold},
            )

        context = self._context(payload)
        confirmation_result = self._maybe_confirm_pending(user, gesture, payload)
        if confirmation_result:
            return confirmation_result

        if self._is_debounced(user, page, gesture):
            return self._feedback(
                status="ignored",
                action="DEBOUNCED",
                allowed=False,
                level="info",
                message="检测到 2 秒内重复手势，已忽略本次操作",
            )

        intent = self._resolve_intent(user, page, gesture, context)
        if not intent:
            return self._feedback(
                status="noop",
                action="UNBOUND_CONTEXT",
                allowed=False,
                level="warning",
                message=f"当前页面 {page} 暂不支持手势 {gesture}",
            )

        if intent["action"] in HIGH_RISK_ACTIONS:
            return self._require_confirmation(user, page, gesture, intent)

        return self._execute_intent(user, intent)

    def _resolve_intent(self, user: User, page: str, gesture: str, context: dict) -> dict | None:
        if user.role == "student":
            return self._student_intent(page, gesture, context)
        if user.role in {"teacher", "counselor"}:
            return self._staff_intent(page, gesture, context)
        abort(403, description="当前角色无权使用手势控制")

    def _student_intent(self, page: str, gesture: str, context: dict) -> dict | None:
        if page == "material_submit":
            return {"action": "MATERIAL_CAMERA_DISABLED", "agent": "UI", "page": page, "context": context}

        if gesture in {"SWIPE_LEFT", "SWIPE_RIGHT", "SWIPE_UP", "SWIPE_DOWN"} and page in {"publicity", "list", "appeal"}:
            agent = {
                "publicity": "Publicity Agent",
                "list": "Audit Agent",
                "appeal": "Appeal Agent",
            }[page]
            if gesture in {"SWIPE_UP", "SWIPE_DOWN"}:
                return {
                    "action": "SCROLL_UP" if gesture == "SWIPE_UP" else "SCROLL_DOWN",
                    "agent": agent,
                    "page": page,
                    "context": context,
                }
            return {
                "action": "PREV_PAGE" if gesture == "SWIPE_LEFT" else "NEXT_PAGE",
                "agent": agent,
                "page": page,
                "context": context,
            }

        if gesture == "FIST":
            status = self._context_status(context, default=MaterialStatus.DRAFT.value)
            if status == MaterialStatus.REVIEWING.value or status == MaterialStatus.SUBMITTED.value:
                abort(400, description="[审核中]或[已提交]状态下学生端不能撤回")
            if status != MaterialStatus.DRAFT.value:
                abort(400, description="仅草稿阶段可撤回")
            return {"action": "CLEAR_DRAFT", "agent": "UI", "page": page, "context": context}

        if gesture in {"OPEN_PALM", "OK_SIGN"} and page == "appeal":
            status = self._context_status(context, default="APPEAL_EDITING")
            if status not in {"APPEAL_EDITING", MaterialStatus.PUBLICIZING.value}:
                abort(400, description="仅申诉编辑或公示中材料可提交申诉")
            self._ensure_material_id(context)
            if not str(context.get("reason", "")).strip():
                abort(400, description="申诉原因不能为空")
            return {"action": "SUBMIT_APPEAL", "agent": "Appeal Agent", "page": page, "context": context}

        return None

    def _staff_intent(self, page: str, gesture: str, context: dict) -> dict | None:
        if page == "publicity":
            if gesture in {"SWIPE_LEFT", "SWIPE_RIGHT", "SWIPE_UP", "SWIPE_DOWN"}:
                if gesture in {"SWIPE_UP", "SWIPE_DOWN"}:
                    return {
                        "action": "SCROLL_UP" if gesture == "SWIPE_UP" else "SCROLL_DOWN",
                        "agent": "Publicity Agent",
                        "page": page,
                        "context": context,
                    }
                return {
                    "action": "PREV_PAGE" if gesture == "SWIPE_LEFT" else "NEXT_PAGE",
                    "agent": "Publicity Agent",
                    "page": page,
                    "context": context,
                }
            return None

        if page in {"list", "appeal"}:
            if gesture in {"SWIPE_LEFT", "SWIPE_RIGHT", "SWIPE_UP", "SWIPE_DOWN"}:
                agent = "Counselor Agent" if page == "list" else "Appeal Agent"
                if gesture in {"SWIPE_UP", "SWIPE_DOWN"}:
                    return {
                        "action": "SCROLL_UP" if gesture == "SWIPE_UP" else "SCROLL_DOWN",
                        "agent": agent,
                        "page": page,
                        "context": context,
                    }
                return {
                    "action": "PREV_PAGE" if gesture == "SWIPE_LEFT" else "NEXT_PAGE",
                    "agent": agent,
                    "page": page,
                    "context": context,
                }
            return None

        if gesture == "POINT":
            self._ensure_material_id(context)
            return {"action": "SELECT_REVIEW", "agent": "Counselor Agent", "page": page, "context": context}

        if gesture == "OPEN_PALM":
            self._ensure_material_id(context)
            self._assert_review_write_allowed(context)
            return {"action": "APPROVE_MATERIAL", "agent": "Counselor Agent", "page": page, "context": context}

        if gesture == "FIST":
            self._ensure_material_id(context)
            self._assert_review_write_allowed(context)
            if not str(context.get("opinion") or context.get("reason") or "").strip():
                abort(400, description="打回材料必须填写理由")
            return {"action": "REJECT_MATERIAL", "agent": "Counselor Agent", "page": page, "context": context}

        if gesture in {"SWIPE_LEFT", "SWIPE_RIGHT"}:
            return {
                "action": "PREV_REVIEW" if gesture == "SWIPE_LEFT" else "NEXT_REVIEW",
                "agent": "Counselor Agent",
                "page": page,
                "context": context,
            }

        return None

    def _execute_intent(self, user: User, intent: dict) -> dict:
        action = intent["action"]
        context = intent["context"]
        if action == "CLEAR_DRAFT":
            return self._feedback(
                status="executed",
                action=action,
                allowed=True,
                agent=intent["agent"],
                level="success",
                message="已撤销",
                data={"draftCleared": True},
            )

        if action == "MATERIAL_CAMERA_DISABLED":
            return self._feedback(
                status="noop",
                action=action,
                allowed=False,
                agent=intent["agent"],
                level="info",
                message="学生材料上传页不接入摄像头动作捕捉，请在上传表单中确认提交",
            )

        if action == "SUBMIT_APPEAL":
            result = self.appeal.submit(
                user,
                {"materialId": context.get("materialId"), "reason": context.get("reason")},
            )
            return self._success(action, intent["agent"], "申诉已提交，材料进入[申诉处理中]", result)

        if action == "APPROVE_MATERIAL":
            result = self.counselor.action(
                user,
                {
                    "materialId": context.get("materialId"),
                    "action": "pass",
                    "opinion": context.get("opinion") or "手势审核通过",
                    "scoreDelta": context.get("scoreDelta") or 0,
                },
            )
            return self._success(action, intent["agent"], "已通过该材料", result)

        if action == "REJECT_MATERIAL":
            result = self.counselor.action(
                user,
                {
                    "materialId": context.get("materialId"),
                    "action": "reject",
                    "opinion": context.get("opinion") or context.get("reason"),
                    "scoreDelta": context.get("scoreDelta") or 0,
                },
            )
            return self._success(action, intent["agent"], "已打回该材料", result)

        if action == "SELECT_REVIEW":
            result = self.counselor.detail(user, int(context["materialId"]))
            return self._success(action, intent["agent"], "已选中审核记录并加载详情", result)

        if action in {"NEXT_REVIEW", "PREV_REVIEW"}:
            result = self._review_page(user, context, delta=1 if action == "NEXT_REVIEW" else -1)
            return self._success(action, intent["agent"], "已切换待审核记录", result)

        if action in {"NEXT_PAGE", "PREV_PAGE"}:
            result = self._paginate(user, intent["page"], context, delta=1 if action == "NEXT_PAGE" else -1)
            return self._success(action, intent["agent"], "已切换页面", result)

        if action in {"SCROLL_UP", "SCROLL_DOWN"}:
            result = self._scroll_list(user, intent["page"], context, direction="up" if action == "SCROLL_UP" else "down")
            return self._success(action, intent["agent"], "已执行列表滑动", result)

        return self._feedback(
            status="noop",
            action=action,
            allowed=False,
            level="warning",
            message=f"动作 {action} 尚未实现",
        )

    def _require_confirmation(self, user: User, page: str, gesture: str, intent: dict) -> dict:
        token = secrets.token_urlsafe(16)
        now = time()
        with _lock:
            _pending_confirmations[token] = {
                "userId": user.id,
                "page": page,
                "gesture": gesture,
                "intent": intent,
                "createdAt": now,
            }
        action = intent["action"]
        return self._feedback(
            status="pending_confirmation",
            action=action,
            allowed=False,
            agent=intent["agent"],
            level="warning",
            message=f"⚠️ 检测到高风险操作：{ACTION_LABELS[action]}\n请保持手势3秒或重复一次OK手势确认",
            requires_confirmation=True,
            confirm_token=token,
            meta={"holdSeconds": CONFIRMATION_HOLD_SECONDS, "ttlSeconds": CONFIRMATION_TTL_SECONDS},
        )

    def _maybe_confirm_pending(self, user: User, gesture: str, payload: dict) -> dict | None:
        token = payload.get("confirmToken")
        now = time()
        pending_token = token
        if not pending_token and gesture == "OK_SIGN":
            pending_token = self._latest_pending_token(user.id)
        if not pending_token:
            return None

        with _lock:
            pending = _pending_confirmations.get(str(pending_token))
            if not pending:
                return self._feedback(
                    status="rejected",
                    action="CONFIRMATION_EXPIRED",
                    allowed=False,
                    level="warning",
                    message="确认请求不存在或已过期，请重新触发手势",
                )
            if pending["userId"] != user.id:
                abort(403, description="确认令牌不属于当前用户")
            age = now - pending["createdAt"]
            if age > CONFIRMATION_TTL_SECONDS:
                _pending_confirmations.pop(str(pending_token), None)
                return self._feedback(
                    status="rejected",
                    action="CONFIRMATION_EXPIRED",
                    allowed=False,
                    level="warning",
                    message="确认已超时，请重新触发手势",
                )
            if gesture != "OK_SIGN" and age < CONFIRMATION_HOLD_SECONDS:
                return self._feedback(
                    status="pending_confirmation",
                    action=pending["intent"]["action"],
                    allowed=False,
                    agent=pending["intent"]["agent"],
                    level="warning",
                    message=f"请继续保持手势 {round(CONFIRMATION_HOLD_SECONDS - age, 1)} 秒",
                    requires_confirmation=True,
                    confirm_token=str(pending_token),
                )
            _pending_confirmations.pop(str(pending_token), None)
            intent = pending["intent"]

        return self._execute_intent(user, intent)

    def _latest_pending_token(self, user_id: int) -> str | None:
        with _lock:
            candidates = [
                (token, pending)
                for token, pending in _pending_confirmations.items()
                if pending["userId"] == user_id
            ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item[1]["createdAt"])[0]

    def _is_debounced(self, user: User, page: str, gesture: str) -> bool:
        key = (user.id, user.role, page, gesture)
        now = time()
        with _lock:
            last_seen = _debounce_cache.get(key)
            _debounce_cache[key] = now
        return last_seen is not None and now - last_seen < DEBOUNCE_SECONDS

    def _paginate(self, user: User, page: str, context: dict, delta: int) -> dict:
        requested_page = max(1, int(context.get("pageIndex") or context.get("page") or 1) + delta)
        page_size = max(1, min(50, int(context.get("pageSize") or 10)))
        items = self._list_items(user, page)
        total_pages = max(1, (len(items) + page_size - 1) // page_size)
        page_index = min(requested_page, total_pages)
        start = (page_index - 1) * page_size
        return {
            "pageIndex": page_index,
            "pageSize": page_size,
            "total": len(items),
            "items": items[start : start + page_size],
        }

    def _scroll_list(self, user: User, page: str, context: dict, direction: str) -> dict:
        page_index = max(1, int(context.get("pageIndex") or context.get("page") or 1))
        page_size = max(1, min(50, int(context.get("pageSize") or 10)))
        items = self._list_items(user, page)
        start = (page_index - 1) * page_size
        return {
            "scrollDirection": direction,
            "pageIndex": page_index,
            "pageSize": page_size,
            "total": len(items),
            "items": items[start : start + page_size],
        }

    def _list_items(self, user: User, page: str) -> list[dict]:
        if page == "publicity":
            result = self.publicity.ranking(user, anonymous=user.role == "student")
            return result["items"]
        if page == "appeal":
            result = self.appeal.list(user)
            return result["items"]
        if user.role in {"teacher", "counselor"}:
            result = self.counselor.list_pending(user)
            return result["items"]
        result = self.audit.list_materials(user)
        return result["items"]

    def _review_page(self, user: User, context: dict, delta: int) -> dict:
        result = self.counselor.list_pending(user)
        items = result["items"]
        if not items:
            return {"items": [], "selected": None}
        current_id = self._optional_int(context.get("materialId"))
        current_index = 0
        if current_id:
            for index, item in enumerate(items):
                if item["id"] == current_id:
                    current_index = index
                    break
        next_index = (current_index + delta) % len(items)
        selected = items[next_index]
        detail = self.counselor.detail(user, selected["id"])
        return {"items": items, "selected": selected, "detail": detail}

    def _assert_review_write_allowed(self, context: dict) -> None:
        material = self._material_from_context(context)
        status = material.status if material else self._context_status(context)
        if status in {MaterialStatus.PUBLICIZING.value, MaterialStatus.PUBLICITY_ENDED.value, MaterialStatus.APPEALING.value}:
            abort(400, description=f"[{status}]状态禁止审核通过、打回或修改")

    def _context_status(self, context: dict, default: str | None = None) -> str | None:
        raw = context.get("status") or context.get("currentStatus") or context.get("materialStatus")
        if not raw:
            return default
        status = STATUS_ALIASES.get(str(raw).strip().upper(), str(raw).strip())
        if status == "APPEAL_EDITING":
            return status
        return normalize_status(status).value

    def _material_from_context(self, context: dict) -> Material | None:
        material_id = self._optional_int(context.get("materialId"))
        if not material_id:
            return None
        material = db.session.get(Material, material_id)
        if not material:
            abort(404, description="材料不存在")
        return material

    def _ensure_material_id(self, context: dict) -> None:
        if not self._optional_int(context.get("materialId")):
            abort(400, description="缺少 materialId")

    def _assert_identity(self, user: User, payload: dict) -> None:
        declared_user = str(payload.get("userId", "")).strip()
        declared_role = str(payload.get("role", "")).strip()
        if declared_user and declared_user not in {str(user.id), user.student_no}:
            abort(403, description="手势用户与登录用户不一致")
        if declared_role and declared_role != user.role:
            abort(403, description="手势角色与登录角色不一致")

    def _gesture(self, payload: dict) -> str:
        gesture = str(payload.get("gesture", "")).strip().upper()
        if not gesture:
            abort(400, description="缺少 gesture")
        return gesture

    def _page(self, payload: dict) -> str:
        raw = str(payload.get("page", "")).strip()
        page = PAGE_ALIASES.get(raw)
        if not page:
            abort(400, description="缺少或不支持的 page")
        return page

    def _confidence(self, payload: dict) -> float:
        try:
            confidence = float(payload.get("confidence"))
        except (TypeError, ValueError):
            abort(400, description="confidence 必须为 0.0-1.0")
        if confidence < 0 or confidence > 1:
            abort(400, description="confidence 必须为 0.0-1.0")
        return confidence

    def _context(self, payload: dict) -> dict:
        context = payload.get("context")
        if isinstance(context, dict):
            merged = {**payload, **context}
            merged["context"] = context
            return merged
        return dict(payload)

    def _optional_int(self, value) -> int | None:
        if value in {None, ""}:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            abort(400, description="materialId 必须为数字")

    def _success(self, action: str, agent: str, message: str, data: dict) -> dict:
        return self._feedback(
            status="executed",
            action=action,
            allowed=True,
            agent=agent,
            level="success",
            message=message,
            data=data,
        )

    def _feedback(
        self,
        *,
        status: str,
        action: str,
        allowed: bool,
        level: str,
        message: str,
        agent: str | None = None,
        data: dict | None = None,
        requires_confirmation: bool = False,
        confirm_token: str | None = None,
        meta: dict | None = None,
    ) -> dict:
        return {
            "status": status,
            "action": action,
            "actionLabel": ACTION_LABELS.get(action, action),
            "allowed": allowed,
            "agent": agent,
            "requiresConfirmation": requires_confirmation,
            "confirmToken": confirm_token,
            "uiFeedback": {"level": level, "message": message},
            "data": data or {},
            "meta": meta or {},
        }
