"""Facebook Page connector — 공식 Graph API.

- 텍스트/링크: POST /{page-id}/feed
- 이미지:      POST /{page-id}/photos (url)
- 영상:        POST /{page-id}/videos (file_url)
필요 권한: pages_manage_posts, pages_read_engagement (Page access token)
"""
from __future__ import annotations

from app.connectors.base import BaseConnector, MetricsResult, PublishRequest, PublishResult


class FacebookConnector(BaseConnector):
    platform = "facebook"

    @property
    def base(self) -> str:
        return f"https://graph.facebook.com/{self.settings.meta_graph_version}"

    def missing_settings(self) -> list[str]:
        missing = []
        if not self.settings.facebook_page_id:
            missing.append("FACEBOOK_PAGE_ID")
        if not self.settings.facebook_page_access_token:
            missing.append("FACEBOOK_PAGE_ACCESS_TOKEN")
        return missing

    def is_configured(self) -> bool:
        return not self.missing_settings()

    def _auth(self) -> dict:
        return {"access_token": self.settings.facebook_page_access_token}

    def _publish_live(self, req: PublishRequest) -> PublishResult:
        page = self.settings.facebook_page_id
        if req.media_url and req.is_video:
            data = self._request(
                "POST",
                f"{self.base}/{page}/videos",
                "영상 게시",
                data={**self._auth(), "file_url": req.media_url, "description": req.full_caption},
            )
        elif req.media_url:
            data = self._request(
                "POST",
                f"{self.base}/{page}/photos",
                "사진 게시",
                data={**self._auth(), "url": req.media_url, "caption": req.full_caption},
            )
        else:
            data = self._request(
                "POST", f"{self.base}/{page}/feed", "게시", data={**self._auth(), "message": req.full_caption}
            )
        post_id = data.get("post_id") or data.get("id", "")
        return PublishResult(success=True, external_id=post_id, url=f"https://www.facebook.com/{post_id}")

    def get_metrics(self, external_id: str, hours_since_publish: float = 24.0) -> MetricsResult:
        data = self._request(
            "GET",
            f"{self.base}/{external_id}",
            "게시물 반응 조회",
            params={**self._auth(), "fields": "shares,reactions.summary(total_count).limit(0),comments.summary(total_count).limit(0)"},
        )
        reactions = (data.get("reactions") or {}).get("summary", {}).get("total_count")
        comments = (data.get("comments") or {}).get("summary", {}).get("total_count")
        shares = (data.get("shares") or {}).get("count") if data.get("shares") else 0
        return MetricsResult(likes=reactions, comments=comments, shares=shares)
