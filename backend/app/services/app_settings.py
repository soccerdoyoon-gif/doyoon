"""DB 에 저장되는 운영 설정 (비밀값 아님). 기본값 + 사용자 변경값 병합."""
from __future__ import annotations

import copy
from typing import Any

from sqlalchemy.orm import Session

from app.models import AppSetting

DEFAULTS: dict[str, Any] = {
    "setup_completed": False,
    "platforms_enabled": {"instagram": True, "facebook": False, "tiktok": True, "x": True},
    # 특정 SNS 만 자동 승인하고 싶을 때 true 로 변경 (기본: 전부 수동 승인)
    "auto_approve": {"instagram": False, "facebook": False, "tiktok": False, "x": False},
    "generation": {"daily_count": 6, "hour": 7, "minute": 0},
    # 현지 시간 기준 기본 게시 시간
    "posting_times": {
        "instagram": ["12:00", "19:00"],
        "facebook": ["12:00"],
        "tiktok": ["18:00", "21:00"],
        "x": ["08:00", "12:00", "20:00"],
    },
    "ads_enabled": False,
    "budget_guard": {
        "currency": "JPY",
        "daily_budget_limit": 10000,  # 하루 광고비 총 한도 (초과 작업은 무조건 차단)
        "max_budget_change_percent": 10,  # 1회 변경 최대 ±10%, 초과 시 승인 필요
        "approval_required_above": 1000,  # 1회 변경 금액이 이 값을 넘으면 승인 필요
        "ads_auto_execute": False,  # true 여도 한도 내 소폭 예산 변경만 자동 실행
    },
    "reports": {"notify_channels": ["file"]},
}


def _merge(default: Any, override: Any) -> Any:
    if isinstance(default, dict) and isinstance(override, dict):
        out = copy.deepcopy(default)
        for k, v in override.items():
            out[k] = _merge(default.get(k), v) if k in default else v
        return out
    return copy.deepcopy(override) if override is not None else copy.deepcopy(default)


def get_setting(db: Session, key: str) -> Any:
    row = db.get(AppSetting, key)
    default = DEFAULTS.get(key)
    if row is None:
        return copy.deepcopy(default)
    return _merge(default, row.value)


def set_setting(db: Session, key: str, value: Any) -> Any:
    if key not in DEFAULTS:
        raise KeyError(key)
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.flush()
    return get_setting(db, key)


def get_all_settings(db: Session) -> dict[str, Any]:
    return {k: get_setting(db, k) for k in DEFAULTS}
