"""Credential redaction — 로그/API 응답에 비밀값이 노출되지 않도록 마스킹."""
from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEY_PATTERN = re.compile(
    r"(token|secret|password|passwd|api[_-]?key|authorization|client_secret|refresh|signature|cookie)",
    re.IGNORECASE,
)
INLINE_PATTERNS = [
    re.compile(r"(access_token=)[^&\s\"']+", re.IGNORECASE),
    re.compile(r"(refresh_token=)[^&\s\"']+", re.IGNORECASE),
    re.compile(r"(client_secret=)[^&\s\"']+", re.IGNORECASE),
    re.compile(r"(Bearer\s+)[A-Za-z0-9\-\._~\+/=]+", re.IGNORECASE),
    re.compile(r"(sk-ant-)[A-Za-z0-9\-_]+"),
]
MASK = "***REDACTED***"


def _secret_values() -> list[str]:
    from app.core.config import get_settings

    s = get_settings()
    values = []
    for name, value in s.model_dump().items():
        if isinstance(value, str) and value and SENSITIVE_KEY_PATTERN.search(name) and len(value) >= 6:
            values.append(value)
    return values


def redact_text(text: str) -> str:
    if not text:
        return text
    for value in _secret_values():
        text = text.replace(value, MASK)
    for pattern in INLINE_PATTERNS:
        text = pattern.sub(lambda m: m.group(1) + MASK, text)
    return text


def redact(obj: Any) -> Any:
    """Recursively mask sensitive keys and inline secrets in dicts/lists/strings."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and SENSITIVE_KEY_PATTERN.search(k):
                out[k] = MASK
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj


def mask_value(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"****{value[-4:]}"
