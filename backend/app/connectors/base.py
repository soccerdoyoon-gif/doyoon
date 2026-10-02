"""Connector 공통 인터페이스.

- 모든 외부 호출은 timeout 이 설정된 httpx.Client 를 사용합니다.
- DRY_RUN=true 이면 publish() 는 실제 API 를 절대 호출하지 않고 로그만 남깁니다.
- 자격 증명이 없으면 registry 가 MockConnector 를 대신 돌려줍니다.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.redact import redact


class ConnectorError(Exception):
    def __init__(self, message: str, *, retryable: bool = True, status_code: int | None = None, response: Any = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
        self.response = redact(response) if response is not None else None


@dataclass
class PublishRequest:
    content_id: int
    platform: str
    content_type: str = "post"
    title: str = ""
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    thread: list[str] = field(default_factory=list)
    media_url: str = ""
    media_path: str = ""
    media_urls: list[str] = field(default_factory=list)  # Instagram 캐러셀 (순서대로)

    @property
    def full_caption(self) -> str:
        tags = " ".join(h if h.startswith("#") else f"#{h}" for h in self.hashtags if h)
        return f"{self.caption}\n\n{tags}".strip() if tags else self.caption.strip()

    @property
    def is_video(self) -> bool:
        if self.content_type in {"reel", "short_video", "video"}:
            return True
        ref = (self.media_url or self.media_path).lower()
        return ref.endswith((".mp4", ".mov", ".m4v", ".webm"))


@dataclass
class PublishResult:
    success: bool
    external_id: str = ""
    url: str = ""
    dry_run: bool = False
    simulated: bool = False
    message: str = ""
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return redact(asdict(self))


METRIC_FIELDS = (
    "impressions",
    "reach",
    "views",
    "likes",
    "comments",
    "shares",
    "saves",
    "clicks",
    "followers_gained",
)


@dataclass
class MetricsResult:
    impressions: int | None = None
    reach: int | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None
    clicks: int | None = None
    followers_gained: int | None = None
    source: str = "api"

    @property
    def engagement_rate(self) -> float | None:
        """(좋아요+댓글+공유+저장) / (reach → views → impressions). 분모가 없으면 None."""
        parts = [self.likes, self.comments, self.shares, self.saves]
        if all(p is None for p in parts):
            return None
        denominator = self.reach or self.views or self.impressions
        if not denominator:
            return None
        return round(sum(p or 0 for p in parts) / denominator * 100, 3)


def stable_seed(*parts: Any) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


class BaseConnector:
    platform: str = "base"
    mode: str = "live"  # live / mock

    def __init__(self, http: httpx.Client | None = None):
        self.settings = get_settings()
        self._http = http

    @property
    def http(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(timeout=httpx.Timeout(self.settings.http_timeout_seconds))
        return self._http

    # ---- capability --------------------------------------------------------
    def is_configured(self) -> bool:  # pragma: no cover - overridden
        return False

    def missing_settings(self) -> list[str]:  # pragma: no cover - overridden
        return []

    # ---- publish -----------------------------------------------------------
    def publish(self, req: PublishRequest) -> PublishResult:
        if get_settings().dry_run:
            return PublishResult(
                success=True,
                external_id=f"dryrun-{self.platform}-{req.content_id}",
                dry_run=True,
                simulated=True,
                message=f"[DRY RUN] {self.platform} 에 다음 게시물을 게시했을 것: {req.full_caption[:120]!r}",
            )
        return self._publish_live(req)

    def _publish_live(self, req: PublishRequest) -> PublishResult:  # pragma: no cover
        raise NotImplementedError

    def get_metrics(self, external_id: str) -> MetricsResult:  # pragma: no cover
        raise NotImplementedError

    # ---- helpers -----------------------------------------------------------
    def _check(self, resp: httpx.Response, what: str) -> dict:
        try:
            data = resp.json()
        except ValueError:
            data = {"text": resp.text[:500]}
        if resp.status_code >= 400:
            retryable = resp.status_code == 429 or resp.status_code >= 500
            raise ConnectorError(
                f"{self.platform} {what} 실패 (HTTP {resp.status_code}): {self._error_message(data)}",
                retryable=retryable,
                status_code=resp.status_code,
                response=data,
            )
        return data if isinstance(data, dict) else {"data": data}

    @staticmethod
    def _error_message(data: Any) -> str:
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                return str(err.get("message") or err.get("code") or err)[:300]
            if err:
                return str(err)[:300]
            if data.get("detail"):
                return str(data["detail"])[:300]
            if data.get("errors"):
                return str(data["errors"])[:300]
        return str(data)[:300]

    def _request(self, method: str, url: str, what: str, **kwargs) -> dict:
        try:
            resp = self.http.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise ConnectorError(f"{self.platform} {what} 시간 초과", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ConnectorError(f"{self.platform} {what} 네트워크 오류: {type(exc).__name__}", retryable=True) from exc
        return self._check(resp, what)
