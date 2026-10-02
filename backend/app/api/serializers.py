"""ORM → JSON. 날짜는 UTC ISO8601 (끝에 Z) 로 내보내고 화면에서 현지 시간으로 변환합니다."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import inspect


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.replace(microsecond=0).isoformat() + "Z"


def to_dict(obj: Any, exclude: set[str] | None = None) -> dict:
    exclude = exclude or set()
    out = {}
    for attr in inspect(obj).mapper.column_attrs:
        k = attr.key
        if k in exclude:
            continue
        v = getattr(obj, k)
        if isinstance(v, datetime):
            v = iso(v)
        elif isinstance(v, date):
            v = v.isoformat()
        out[k] = v
    return out


def content_dict(item, with_children: bool = False) -> dict:
    d = to_dict(item)
    last = item.metrics[-1] if item.metrics else None
    d["latest_metrics"] = to_dict(last) if last else None
    if with_children:
        d["attempts"] = [to_dict(a) for a in item.attempts]
        d["metrics_history"] = [to_dict(m) for m in item.metrics[-30:]]
    return d
