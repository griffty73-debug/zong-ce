from enum import StrEnum


class MaterialStatus(StrEnum):
    DRAFT = "草稿"
    SUBMITTED = "已提交"
    REVIEWING = "审核中"
    APPROVED = "已通过"
    REJECTED = "已打回"
    PUBLICIZING = "公示中"
    PUBLICITY_ENDED = "公示结束"
    APPEALING = "申诉处理中"


ALLOWED_TRANSITIONS: dict[MaterialStatus, set[MaterialStatus]] = {
    MaterialStatus.DRAFT: {MaterialStatus.SUBMITTED},
    MaterialStatus.SUBMITTED: {MaterialStatus.REVIEWING},
    MaterialStatus.REVIEWING: {MaterialStatus.APPROVED, MaterialStatus.REJECTED},
    MaterialStatus.APPROVED: {MaterialStatus.PUBLICIZING, MaterialStatus.APPEALING},
    MaterialStatus.REJECTED: {MaterialStatus.DRAFT},
    MaterialStatus.PUBLICIZING: {MaterialStatus.PUBLICITY_ENDED, MaterialStatus.APPEALING},
    MaterialStatus.APPEALING: {MaterialStatus.APPROVED, MaterialStatus.PUBLICIZING, MaterialStatus.PUBLICITY_ENDED},
    MaterialStatus.PUBLICITY_ENDED: set(),
}

LOCKED_STATUSES = {MaterialStatus.PUBLICIZING, MaterialStatus.PUBLICITY_ENDED, MaterialStatus.APPEALING}


class StateMachineError(ValueError):
    pass


def normalize_status(status: str | MaterialStatus) -> MaterialStatus:
    if isinstance(status, MaterialStatus):
        return status
    try:
        return MaterialStatus(status)
    except ValueError as exc:
        raise StateMachineError(f"未知材料状态: {status}") from exc


def assert_transition(current: str | MaterialStatus, target: str | MaterialStatus) -> None:
    current_status = normalize_status(current)
    target_status = normalize_status(target)
    if target_status not in ALLOWED_TRANSITIONS[current_status]:
        raise StateMachineError(f"禁止从[{current_status}]跳转到[{target_status}]")


def assert_editable(status: str | MaterialStatus) -> None:
    current_status = normalize_status(status)
    if current_status in LOCKED_STATUSES:
        raise StateMachineError(f"[{current_status}]状态已锁定，禁止修改")
