"""Meta Ads connector — 공식 Marketing API.

읽기: 캠페인/광고세트/광고 구조 + /act_{id}/insights (level=ad, time_increment=1)
쓰기: 예산 변경 / 중지 / 재개 — 반드시 Budget Guard + 사용자 승인 후에만 호출됩니다.
      DRY_RUN=true 이면 실제 호출 없이 "변경했을 것" 로그만 남깁니다.
필요 권한: ads_read (조회), ads_management (수정)
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from app.connectors.base import BaseConnector, ConnectorError, stable_seed
from app.core.config import get_settings

PURCHASE_ACTIONS = ("purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase")
LEAD_ACTIONS = ("lead", "offsite_conversion.fb_pixel_lead", "complete_registration")
ZERO_DECIMAL_CURRENCIES = {"JPY", "KRW", "VND", "CLP", "ISK", "TWD", "HUF"}


def _f(v: Any) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _i(v: Any) -> int | None:
    f = _f(v)
    return int(f) if f is not None else None


@dataclass
class AdsSnapshot:
    entities: list[dict] = field(default_factory=list)  # level, external_id, parent, name, status, daily_budget...
    insights: list[dict] = field(default_factory=list)  # one row per ad per day
    source: str = "api"


@dataclass
class AdActionResult:
    success: bool
    dry_run: bool
    message: str
    raw: dict = field(default_factory=dict)


def parse_insight_row(row: dict) -> dict:
    spend = _f(row.get("spend"))
    actions = {a.get("action_type"): _f(a.get("value")) for a in row.get("actions") or []}
    values = {a.get("action_type"): _f(a.get("value")) for a in row.get("action_values") or []}
    conversions = None
    conv_value = None
    for key in PURCHASE_ACTIONS + LEAD_ACTIONS:
        if actions.get(key) is not None:
            conversions = actions[key]
            conv_value = values.get(key)
            break
    roas = None
    if row.get("purchase_roas"):
        roas = _f(row["purchase_roas"][0].get("value"))
    elif conv_value is not None and spend:
        roas = round(conv_value / spend, 4)
    cpa = round(spend / conversions, 2) if spend is not None and conversions else None
    return {
        "level": "ad",
        "external_id": row.get("ad_id", ""),
        "name": row.get("ad_name", ""),
        "campaign_external_id": row.get("campaign_id", ""),
        "adset_external_id": row.get("adset_id", ""),
        "date": date.fromisoformat(row["date_start"]),
        "spend": spend,
        "impressions": _i(row.get("impressions")),
        "reach": _i(row.get("reach")),
        "clicks": _i(row.get("clicks")),
        "ctr": _f(row.get("ctr")),
        "cpc": _f(row.get("cpc")),
        "cpm": _f(row.get("cpm")),
        "conversions": conversions,
        "conversion_value": conv_value,
        "cpa": cpa,
        "roas": roas,
    }


class MetaAdsConnector(BaseConnector):
    platform = "meta_ads"

    def __init__(self, http=None, currency: str = "JPY"):
        super().__init__(http)
        self.currency = currency.upper()

    @property
    def base(self) -> str:
        return f"https://graph.facebook.com/{self.settings.meta_graph_version}"

    @property
    def offset(self) -> int:
        return 1 if self.currency in ZERO_DECIMAL_CURRENCIES else 100

    def missing_settings(self) -> list[str]:
        m = []
        if not self.settings.meta_ads_access_token:
            m.append("META_ADS_ACCESS_TOKEN")
        if not self.settings.meta_ad_account_id:
            m.append("META_AD_ACCOUNT_ID")
        return m

    def is_configured(self) -> bool:
        return not self.missing_settings()

    def _auth(self) -> dict:
        return {"access_token": self.settings.meta_ads_access_token}

    def _paged(self, url: str, what: str, params: dict, max_pages: int = 20) -> list[dict]:
        out: list[dict] = []
        data = self._request("GET", url, what, params={**self._auth(), **params})
        for _ in range(max_pages):
            out.extend(data.get("data", []))
            nxt = (data.get("paging") or {}).get("next")
            if not nxt:
                break
            data = self._request("GET", nxt, what)
        return out

    def fetch(self, since: date, until: date) -> AdsSnapshot:
        acct = f"act_{self.settings.meta_ad_account_id.removeprefix('act_')}"
        entities: list[dict] = []
        for c in self._paged(f"{self.base}/{acct}/campaigns", "캠페인 조회", {"fields": "id,name,status,objective,daily_budget", "limit": 100}):
            entities.append({"level": "campaign", "external_id": c["id"], "parent_external_id": "", "name": c.get("name", ""),
                             "status": c.get("status", ""), "objective": c.get("objective", ""),
                             "daily_budget": (_f(c.get("daily_budget")) or 0) / self.offset if c.get("daily_budget") else None})
        for a in self._paged(f"{self.base}/{acct}/adsets", "광고세트 조회", {"fields": "id,name,status,campaign_id,daily_budget", "limit": 100}):
            entities.append({"level": "adset", "external_id": a["id"], "parent_external_id": a.get("campaign_id", ""),
                             "name": a.get("name", ""), "status": a.get("status", ""),
                             "daily_budget": (_f(a.get("daily_budget")) or 0) / self.offset if a.get("daily_budget") else None})
        for ad in self._paged(f"{self.base}/{acct}/ads", "광고 조회", {"fields": "id,name,status,adset_id,creative{title,body}", "limit": 100}):
            cr = ad.get("creative") or {}
            entities.append({"level": "ad", "external_id": ad["id"], "parent_external_id": ad.get("adset_id", ""),
                             "name": ad.get("name", ""), "status": ad.get("status", ""),
                             "creative_summary": " / ".join(x for x in (cr.get("title"), cr.get("body")) if x)[:1000]})
        rows = self._paged(
            f"{self.base}/{acct}/insights",
            "광고 성과 조회",
            {
                "level": "ad",
                "time_increment": 1,
                "time_range": f'{{"since":"{since.isoformat()}","until":"{until.isoformat()}"}}',
                "fields": "campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,spend,impressions,reach,clicks,ctr,cpc,cpm,actions,action_values,purchase_roas",
                "limit": 500,
            },
        )
        return AdsSnapshot(entities=entities, insights=[parse_insight_row(r) for r in rows], source="api")

    # ---- write operations (승인 후에만 호출) ----------------------------------
    def update_budget(self, external_id: str, old_budget: float | None, new_budget: float) -> AdActionResult:
        msg = f"Meta 광고 예산을 {old_budget or 0:,.0f} {self.currency} → {new_budget:,.0f} {self.currency} 로 변경"
        if get_settings().dry_run:
            return AdActionResult(True, True, f"[DRY RUN] {msg}했을 것 (대상 {external_id})")
        data = self._request("POST", f"{self.base}/{external_id}", "예산 변경",
                             data={**self._auth(), "daily_budget": int(round(new_budget * self.offset))})
        return AdActionResult(bool(data.get("success", True)), False, msg, data)

    def set_status(self, external_id: str, status: str) -> AdActionResult:
        if status not in ("PAUSED", "ACTIVE"):
            raise ConnectorError(f"지원하지 않는 상태: {status}", retryable=False)
        msg = f"Meta 광고 {external_id} 상태를 {status} 로 변경"
        if get_settings().dry_run:
            return AdActionResult(True, True, f"[DRY RUN] {msg}했을 것")
        data = self._request("POST", f"{self.base}/{external_id}", "상태 변경", data={**self._auth(), "status": status})
        return AdActionResult(bool(data.get("success", True)), False, msg, data)


class MockMetaAdsConnector(MetaAdsConnector):
    """테스트용 가짜 광고 데이터 (source='mock')."""

    mode = "mock"

    def is_configured(self) -> bool:
        return True

    def fetch(self, since: date, until: date) -> AdsSnapshot:
        entities = [
            {"level": "campaign", "external_id": "mock_c1", "parent_external_id": "", "name": "[MOCK] 판매 캠페인", "status": "ACTIVE", "objective": "OUTCOME_SALES", "daily_budget": None},
            {"level": "adset", "external_id": "mock_as1", "parent_external_id": "mock_c1", "name": "[MOCK] 25-34 여성", "status": "ACTIVE", "daily_budget": 3000.0},
            {"level": "adset", "external_id": "mock_as2", "parent_external_id": "mock_c1", "name": "[MOCK] 리타겟팅", "status": "ACTIVE", "daily_budget": 2000.0},
        ]
        ads = [
            ("mock_ad1", "mock_as1", "[MOCK] 광고 A - 사용 후기 영상", 0.025, 0.06),
            ("mock_ad2", "mock_as1", "[MOCK] 광고 B - 제품 이미지", 0.008, 0.02),
            ("mock_ad3", "mock_as2", "[MOCK] 광고 C - 할인 강조", 0.018, 0.045),
        ]
        insights = []
        for ad_id, adset, name, ctr_base, cvr_base in ads:
            entities.append({"level": "ad", "external_id": ad_id, "parent_external_id": adset, "name": name, "status": "ACTIVE", "creative_summary": name})
            d = since
            while d <= until:
                rng = random.Random(stable_seed(ad_id, d.isoformat()))
                impressions = rng.randint(2500, 9000)
                clicks = int(impressions * ctr_base * rng.uniform(0.7, 1.3))
                spend = round(impressions / 1000 * rng.uniform(250, 450), 0)
                conv = round(clicks * cvr_base * rng.uniform(0.5, 1.5))
                value = conv * rng.uniform(3500, 6000)
                insights.append({
                    "level": "ad", "external_id": ad_id, "name": name, "campaign_external_id": "mock_c1",
                    "adset_external_id": adset, "date": d, "spend": spend, "impressions": impressions,
                    "reach": int(impressions * 0.8), "clicks": clicks,
                    "ctr": round(clicks / impressions * 100, 3), "cpc": round(spend / clicks, 1) if clicks else None,
                    "cpm": round(spend / impressions * 1000, 1), "conversions": float(conv),
                    "conversion_value": round(value, 0) if conv else None,
                    "cpa": round(spend / conv, 1) if conv else None,
                    "roas": round(value / spend, 3) if conv and spend else None,
                })
                d += timedelta(days=1)
        return AdsSnapshot(entities=entities, insights=insights, source="mock")

    def update_budget(self, external_id: str, old_budget: float | None, new_budget: float) -> AdActionResult:
        return AdActionResult(True, True, f"[MOCK] Meta 광고 예산을 {old_budget or 0:,.0f} → {new_budget:,.0f} {self.currency} 로 변경했을 것 (대상 {external_id})")

    def set_status(self, external_id: str, status: str) -> AdActionResult:
        return AdActionResult(True, True, f"[MOCK] Meta 광고 {external_id} 상태를 {status} 로 변경했을 것")
