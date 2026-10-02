"""Simple secret storage: data/secrets.env (gitignore 대상, 권한 600).

설치 마법사/설정 화면에서 입력한 API Key 는 여기에만 저장되고,
API 응답에는 마스킹된 값만 돌려줍니다. 비밀번호는 절대 저장하지 않습니다.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from app.core.config import get_settings, reload_settings

ALLOWED_SECRET_KEYS = {
    "ANTHROPIC_API_KEY",
    "META_APP_ID",
    "META_APP_SECRET",
    "INSTAGRAM_APP_ID",
    "INSTAGRAM_APP_SECRET",
    "INSTAGRAM_ACCESS_TOKEN",
    "INSTAGRAM_USER_ID",
    "FACEBOOK_PAGE_ID",
    "FACEBOOK_PAGE_ACCESS_TOKEN",
    "META_ADS_ACCESS_TOKEN",
    "META_AD_ACCOUNT_ID",
    "TIKTOK_CLIENT_KEY",
    "TIKTOK_CLIENT_SECRET",
    "TIKTOK_ACCESS_TOKEN",
    "TIKTOK_REFRESH_TOKEN",
    "X_CLIENT_ID",
    "X_CLIENT_SECRET",
    "X_ACCESS_TOKEN",
    "X_REFRESH_TOKEN",
    "PUBLIC_MEDIA_BASE_URL",
    "SLACK_WEBHOOK_URL",
    "DISCORD_WEBHOOK_URL",
}
_LINE = re.compile(r"^([A-Z0-9_]+)=(.*)$")


def _read(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            m = _LINE.match(raw.strip())
            if m:
                data[m.group(1)] = m.group(2)
    return data


def save_secrets(values: dict[str, str]) -> list[str]:
    """Save allowed keys. Empty string removes nothing (ignored)."""
    settings = get_settings()
    path = settings.secrets_file
    path.parent.mkdir(parents=True, exist_ok=True)
    current = _read(path)
    saved = []
    for key, value in values.items():
        key = key.upper()
        if key not in ALLOWED_SECRET_KEYS:
            raise ValueError(f"허용되지 않은 키입니다: {key}")
        value = (value or "").strip().replace("\n", "")
        if not value:
            continue
        current[key] = value
        os.environ.pop(key, None)  # env 가 파일보다 우선하므로 오래된 값 제거
        saved.append(key)
    body = "# 자동 생성 파일 — Git 에 올리지 마세요\n" + "".join(f"{k}={v}\n" for k, v in sorted(current.items()))
    path.write_text(body, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover (Windows)
        pass
    reload_settings()
    return saved
