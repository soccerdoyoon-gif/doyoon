"""플랫폼 이름 → connector. 자격 증명이 없으면 자동으로 Mock 사용."""
from __future__ import annotations

from app.connectors.base import BaseConnector
from app.connectors.facebook import FacebookConnector
from app.connectors.instagram import InstagramConnector
from app.connectors.meta_ads import MetaAdsConnector, MockMetaAdsConnector
from app.connectors.mock import MockConnector
from app.connectors.tiktok import TikTokConnector
from app.connectors.x import XConnector

CONNECTOR_CLASSES: dict[str, type[BaseConnector]] = {
    "instagram": InstagramConnector,
    "facebook": FacebookConnector,
    "tiktok": TikTokConnector,
    "x": XConnector,
}

# 테스트에서 connector 를 바꿔 끼우기 위한 override
_overrides: dict[str, BaseConnector] = {}


def set_override(platform: str, connector: BaseConnector | None) -> None:
    if connector is None:
        _overrides.pop(platform, None)
    else:
        _overrides[platform] = connector


def get_connector(platform: str) -> BaseConnector:
    if platform in _overrides:
        return _overrides[platform]
    cls = CONNECTOR_CLASSES.get(platform)
    if cls is None:
        raise ValueError(f"지원하지 않는 플랫폼: {platform}")
    real = cls()
    if real.is_configured():
        return real
    return MockConnector(platform)


def get_ads_connector(currency: str = "JPY") -> MetaAdsConnector:
    if "meta_ads" in _overrides:
        return _overrides["meta_ads"]  # type: ignore[return-value]
    real = MetaAdsConnector(currency=currency)
    return real if real.is_configured() else MockMetaAdsConnector(currency=currency)


def connection_status() -> dict[str, dict]:
    out = {}
    for name, cls in CONNECTOR_CLASSES.items():
        c = cls()
        out[name] = {"mode": "live" if c.is_configured() else "mock", "missing": c.missing_settings()}
    ads = MetaAdsConnector()
    out["meta_ads"] = {"mode": "live" if ads.is_configured() else "mock", "missing": ads.missing_settings()}
    return out
