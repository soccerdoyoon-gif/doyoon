"""DB 에 저장되는 운영 설정 (비밀값 아님). 기본값 + 사용자 변경값 병합."""
from __future__ import annotations

import copy
from typing import Any

from sqlalchemy.orm import Session

from app.models import AppSetting

DEFAULTS: dict[str, Any] = {
    "setup_completed": False,
    # 기본 업로드 대상: Instagram / TikTok / X (일본 시장)
    "platforms_enabled": {"instagram": True, "facebook": False, "tiktok": True, "x": True},
    # 특정 SNS 만 자동 승인하고 싶을 때 true 로 변경 (기본: 전부 수동 승인)
    "auto_approve": {"instagram": False, "facebook": False, "tiktok": False, "x": False},
    # ideas_per_day: 하루 아이디어 수. 아이디어 1개 → 플랫폼별 콘텐츠 패키지 (최소 5개 콘텐츠 보장)
    "generation": {"ideas_per_day": 2, "hour": 7, "minute": 0},
    # JST 기준 테스트 후보 시간 (7-9시 / 12-13시 / 18-22시).
    # 실제 추천 시간은 우리 계정 성과 데이터로 매일 다시 학습됩니다.
    "posting_times": {
        "instagram": ["07:30", "12:15", "20:00"],
        "facebook": ["12:00"],
        "tiktok": ["12:30", "19:00", "21:00"],
        "x": ["07:30", "12:00", "18:30", "21:30"],
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
    # 대시보드 / 리포트 / AI 분석 요약 언어 (ja / ko). 콘텐츠는 항상 일본어 기본
    "ui_language": "ja",
    # 콘텐츠 패키지 생성 시 이미지·영상·광고안 자동 생성 여부
    "media": {"generate_images": True, "generate_videos": True, "include_ads": True, "ai_scene_images": False},
    # 영상 음성 (VOICEVOX). speakers: 성별/톤 → VOICEVOX speaker id (설정 화면에서 변경 가능)
    "voice": {
        "enabled": True,
        "gender": "female",
        "tone": "casual",
        "speakers": {
            "female": {"casual": 8, "energetic": 10, "calm": 14, "luxury": 2},
            "male": {"casual": 11, "energetic": 12, "calm": 13, "luxury": 13},
        },
    },
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


def ui_language(db: Session) -> str:
    return "ko" if get_setting(db, "ui_language") == "ko" else "ja"
