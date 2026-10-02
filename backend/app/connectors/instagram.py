"""Instagram connector — 공식 Instagram Platform API (Content Publishing + Insights).

흐름: POST /{ig-user-id}/media (컨테이너 생성) → status_code 가 FINISHED 될 때까지 확인
     → POST /{ig-user-id}/media_publish
- 이미지/영상은 공개 URL 이어야 합니다 (PUBLIC_MEDIA_BASE_URL).
- 24시간 동안 API 게시 100개 제한.
필요 권한(Instagram Login): instagram_business_basic, instagram_business_content_publish,
instagram_business_manage_insights
"""
from __future__ import annotations

import time

from app.connectors.base import BaseConnector, ConnectorError, MetricsResult, PublishRequest, PublishResult


class InstagramConnector(BaseConnector):
    platform = "instagram"
    poll_interval_seconds = 5.0
    max_polls = 24

    @property
    def base(self) -> str:
        return f"https://{self.settings.instagram_api_host}/{self.settings.meta_graph_version}"

    def missing_settings(self) -> list[str]:
        missing = []
        if not self.settings.instagram_access_token:
            missing.append("INSTAGRAM_ACCESS_TOKEN")
        if not self.settings.instagram_user_id:
            missing.append("INSTAGRAM_USER_ID")
        return missing

    def is_configured(self) -> bool:
        return not self.missing_settings()

    def _auth(self) -> dict:
        return {"access_token": self.settings.instagram_access_token}

    def refresh_token(self) -> bool:
        """장기 토큰(60일) 갱신. 24시간 이상 지난 유효 토큰만 갱신 가능."""
        if not self.settings.instagram_access_token or self.settings.instagram_api_host != "graph.instagram.com":
            return False
        data = self._request(
            "GET",
            "https://graph.instagram.com/refresh_access_token",
            "토큰 갱신",
            params={"grant_type": "ig_refresh_token", "access_token": self.settings.instagram_access_token},
        )
        if not data.get("access_token"):
            return False
        from app.core.secret_store import save_secrets

        save_secrets({"INSTAGRAM_ACCESS_TOKEN": data["access_token"]})
        return True

    def _wait_ready(self, container_id: str) -> None:
        for _ in range(self.max_polls):
            status = self._request(
                "GET", f"{self.base}/{container_id}", "컨테이너 상태 확인", params={**self._auth(), "fields": "status_code"}
            )
            code = status.get("status_code")
            if code in (None, "FINISHED"):
                return
            if code in ("ERROR", "EXPIRED"):
                raise ConnectorError(f"Instagram 미디어 처리 실패: {code}", retryable=False, response=status)
            time.sleep(self.poll_interval_seconds)
        raise ConnectorError("Instagram 미디어 처리 시간 초과", retryable=True)

    def _publish_carousel(self, req: PublishRequest) -> str:
        ig = self.settings.instagram_user_id
        children = []
        for url in req.media_urls[:10]:
            child = self._request("POST", f"{self.base}/{ig}/media", "캐러셀 이미지 등록",
                                  params={**self._auth(), "image_url": url, "is_carousel_item": "true"})
            children.append(child["id"])
        for c in children:
            self._wait_ready(c)
        container = self._request("POST", f"{self.base}/{ig}/media", "캐러셀 생성", params={
            **self._auth(), "media_type": "CAROUSEL", "children": ",".join(children), "caption": req.full_caption})
        return container["id"]

    def _publish_live(self, req: PublishRequest) -> PublishResult:
        if len(req.media_urls) >= 2:
            creation_id = self._publish_carousel(req)
            self._wait_ready(creation_id)
            return self._finish(creation_id)
        if not req.media_url:
            raise ConnectorError(
                "Instagram 게시에는 공개 URL 의 이미지/영상이 필요합니다 (media_url 또는 PUBLIC_MEDIA_BASE_URL).",
                retryable=False,
            )
        ig = self.settings.instagram_user_id
        params = {**self._auth(), "caption": req.full_caption}
        if req.is_video:
            params.update({"media_type": "REELS", "video_url": req.media_url})
        else:
            params["image_url"] = req.media_url
        container = self._request("POST", f"{self.base}/{ig}/media", "컨테이너 생성", params=params)
        creation_id = container.get("id")
        if not creation_id:
            raise ConnectorError("Instagram 컨테이너 ID 를 받지 못했습니다.", response=container)

        self._wait_ready(creation_id)
        return self._finish(creation_id)

    def _finish(self, creation_id: str) -> PublishResult:
        ig = self.settings.instagram_user_id
        published = self._request(
            "POST", f"{self.base}/{ig}/media_publish", "게시", params={**self._auth(), "creation_id": creation_id}
        )
        media_id = published.get("id", "")
        url = ""
        try:
            info = self._request(
                "GET", f"{self.base}/{media_id}", "permalink 조회", params={**self._auth(), "fields": "permalink"}
            )
            url = info.get("permalink", "")
        except ConnectorError:
            pass
        return PublishResult(success=True, external_id=media_id, url=url, raw={"container": creation_id})

    def get_metrics(self, external_id: str, hours_since_publish: float = 24.0) -> MetricsResult:
        metric_sets = [
            "reach,likes,comments,shares,saved,views,total_interactions",
            "reach,likes,comments,shares,saved",
        ]
        data = None
        last_error: ConnectorError | None = None
        for metrics in metric_sets:
            try:
                data = self._request(
                    "GET",
                    f"{self.base}/{external_id}/insights",
                    "인사이트 조회",
                    params={**self._auth(), "metric": metrics},
                )
                break
            except ConnectorError as exc:
                last_error = exc
                if not exc.status_code or exc.status_code >= 500:
                    raise
        if data is None:
            raise last_error or ConnectorError("Instagram 인사이트 없음")
        values: dict[str, int] = {}
        for item in data.get("data", []):
            name = item.get("name")
            val = None
            if item.get("values"):
                val = item["values"][0].get("value")
            elif isinstance(item.get("total_value"), dict):
                val = item["total_value"].get("value")
            if isinstance(val, (int, float)):
                values[name] = int(val)
        return MetricsResult(
            impressions=None,  # 신규 미디어에서는 제공되지 않음 → null
            reach=values.get("reach"),
            views=values.get("views"),
            likes=values.get("likes"),
            comments=values.get("comments"),
            shares=values.get("shares"),
            saves=values.get("saved"),
            clicks=None,
            followers_gained=None,
        )
