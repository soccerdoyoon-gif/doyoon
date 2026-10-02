"""X connector — 공식 X API v2.

- 게시: POST https://api.x.com/2/tweets  (Thread 는 reply.in_reply_to_tweet_id 로 연결)
- 성과: GET  https://api.x.com/2/tweets/{id}?tweet.fields=public_metrics,non_public_metrics
- 인증: OAuth 2.0 Authorization Code + PKCE (scope: tweet.read tweet.write users.read offline.access)
- X API 는 사용량 과금(pay-per-use) 입니다. 게시/조회마다 크레딧이 차감될 수 있습니다.
- 현재 버전은 텍스트 게시만 지원합니다 (미디어 첨부는 추후).
"""
from __future__ import annotations

from app.connectors.base import BaseConnector, ConnectorError, MetricsResult, PublishRequest, PublishResult

API = "https://api.x.com"


class XConnector(BaseConnector):
    platform = "x"

    def missing_settings(self) -> list[str]:
        return [] if self.settings.x_access_token else ["X_ACCESS_TOKEN (설정 화면에서 X 연결)"]

    def is_configured(self) -> bool:
        return not self.missing_settings()

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.settings.x_access_token}"}

    def refresh_token(self) -> bool:
        s = self.settings
        if not (s.x_refresh_token and s.x_client_id):
            return False
        auth = (s.x_client_id, s.x_client_secret) if s.x_client_secret else None
        data = self._request(
            "POST",
            f"{API}/2/oauth2/token",
            "토큰 갱신",
            data={"grant_type": "refresh_token", "refresh_token": s.x_refresh_token, "client_id": s.x_client_id},
            auth=auth,
        )
        if not data.get("access_token"):
            return False
        from app.core.config import get_settings
        from app.core.secret_store import save_secrets

        save_secrets({"X_ACCESS_TOKEN": data["access_token"], "X_REFRESH_TOKEN": data.get("refresh_token", "")})
        self.settings = get_settings()
        return True

    def _call(self, method: str, path: str, what: str, **kwargs) -> dict:
        try:
            return self._request(method, f"{API}{path}", what, headers=self._headers(), **kwargs)
        except ConnectorError as exc:
            if exc.status_code == 401 and self.refresh_token():
                return self._request(method, f"{API}{path}", what, headers=self._headers(), **kwargs)
            raise

    def _publish_live(self, req: PublishRequest) -> PublishResult:
        if req.media_url or req.media_path:
            raise ConnectorError("X 미디어 첨부는 아직 지원하지 않습니다. 텍스트만 게시하세요.", retryable=False)
        texts = [t for t in (req.thread or []) if t.strip()] or [req.full_caption]
        for t in texts:
            if len(t) > 280:
                raise ConnectorError(f"X 게시글이 280자를 넘습니다 ({len(t)}자).", retryable=False)
        ids: list[str] = []
        for i, text in enumerate(texts):
            body: dict = {"text": text}
            if ids:
                body["reply"] = {"in_reply_to_tweet_id": ids[-1]}
            data = self._call("POST", "/2/tweets", f"게시 ({i + 1}/{len(texts)})", json=body)
            tweet_id = (data.get("data") or {}).get("id")
            if not tweet_id:
                raise ConnectorError("X 게시 ID 를 받지 못했습니다.", response=data)
            ids.append(tweet_id)
        return PublishResult(
            success=True, external_id=ids[0], url=f"https://x.com/i/web/status/{ids[0]}", raw={"thread_ids": ids}
        )

    def get_metrics(self, external_id: str, hours_since_publish: float = 24.0) -> MetricsResult:
        try:
            data = self._call(
                "GET",
                f"/2/tweets/{external_id}",
                "성과 조회",
                params={"tweet.fields": "public_metrics,non_public_metrics"},
            )
        except ConnectorError as exc:
            if exc.status_code in (400, 403):
                data = self._call("GET", f"/2/tweets/{external_id}", "성과 조회", params={"tweet.fields": "public_metrics"})
            else:
                raise
        tweet = data.get("data") or {}
        pub = tweet.get("public_metrics") or {}
        npub = tweet.get("non_public_metrics") or {}
        shares = None
        if "retweet_count" in pub or "quote_count" in pub:
            shares = (pub.get("retweet_count") or 0) + (pub.get("quote_count") or 0)
        return MetricsResult(
            impressions=npub.get("impression_count", pub.get("impression_count")),
            likes=pub.get("like_count"),
            comments=pub.get("reply_count"),
            shares=shares,
            saves=pub.get("bookmark_count"),
            clicks=npub.get("url_link_clicks"),
        )
