"""Budget Guard — 광고비 안전장치.

규칙
1. 실제 돈과 관련된 작업(삭제/중지/캠페인 생성/결제 설정 변경)은 항상 승인 필요.
2. 예산 변경 1회 최대 ±max_budget_change_percent (기본 10%). 초과 시 승인 필요.
3. 변경 금액이 approval_required_above 를 넘으면 승인 필요.
4. 변경 후 전체 일일 예산 합계가 daily_budget_limit 를 넘으면 무조건 차단 (승인해도 불가).
5. 예산을 늘리는 작업인데 오늘 지출이 이미 한도를 넘었으면 차단.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.enums import AdActionType

ALWAYS_APPROVAL = {
    AdActionType.PAUSE.value,
    AdActionType.RESUME.value,
    AdActionType.DELETE.value,
    AdActionType.CREATE_CAMPAIGN.value,
    AdActionType.BILLING_CHANGE.value,
}


@dataclass
class GuardDecision:
    allowed: bool  # False = BLOCKED (절대 실행 불가)
    requires_approval: bool
    reasons: list[str] = field(default_factory=list)
    change_percent: float | None = None
    new_total_daily_budget: float | None = None

    @property
    def can_auto_execute(self) -> bool:
        return self.allowed and not self.requires_approval

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["can_auto_execute"] = self.can_auto_execute
        return d


def evaluate_action(
    action_type: str,
    config: dict[str, Any],
    *,
    current_budget: float | None = None,
    new_budget: float | None = None,
    current_total_daily_budget: float = 0.0,
    today_spend: float = 0.0,
) -> GuardDecision:
    reasons: list[str] = []
    limit = float(config.get("daily_budget_limit") or 0)
    max_pct = float(config.get("max_budget_change_percent") or 10)
    approval_above = float(config.get("approval_required_above") or 0)

    if action_type in ALWAYS_APPROVAL:
        return GuardDecision(
            allowed=True,
            requires_approval=True,
            reasons=[f"'{action_type}' 작업은 항상 사용자 승인이 필요합니다."],
        )

    if action_type != AdActionType.BUDGET_CHANGE.value:
        return GuardDecision(allowed=False, requires_approval=True, reasons=[f"알 수 없는 작업: {action_type}"])

    if new_budget is None or new_budget < 0:
        return GuardDecision(allowed=False, requires_approval=True, reasons=["새 예산 값이 올바르지 않습니다."])

    current = float(current_budget or 0)
    delta = new_budget - current
    pct = (delta / current * 100.0) if current > 0 else (100.0 if new_budget > 0 else 0.0)
    new_total = current_total_daily_budget - current + new_budget

    allowed = True
    requires_approval = False
    if limit > 0 and new_total > limit:
        allowed = False
        reasons.append(f"변경 후 일일 예산 합계 {new_total:,.0f} 이(가) 한도 {limit:,.0f} 를 초과하여 차단됩니다.")
    if delta > 0 and limit > 0 and today_spend >= limit:
        allowed = False
        reasons.append(f"오늘 지출 {today_spend:,.0f} 이(가) 이미 한도 {limit:,.0f} 에 도달하여 증액이 차단됩니다.")
    if abs(pct) > max_pct:
        requires_approval = True
        reasons.append(f"변경 폭 {pct:+.1f}% 가 허용 범위 ±{max_pct:.0f}% 를 넘어 승인이 필요합니다.")
    if approval_above > 0 and abs(delta) > approval_above:
        requires_approval = True
        reasons.append(f"변경 금액 {abs(delta):,.0f} 이(가) {approval_above:,.0f} 를 넘어 승인이 필요합니다.")
    if not config.get("ads_auto_execute", False):
        requires_approval = True
        reasons.append("광고 자동 실행이 꺼져 있어 승인이 필요합니다 (설정 > Budget Guard).")
    if allowed and not reasons:
        reasons.append("Budget Guard 통과")
    return GuardDecision(
        allowed=allowed,
        requires_approval=requires_approval or not allowed,
        reasons=reasons,
        change_percent=round(pct, 2),
        new_total_daily_budget=new_total,
    )
