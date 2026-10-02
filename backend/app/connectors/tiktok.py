"""TikTok connector — 공식 Content Posting API (Direct Post).

흐름: creator_info/query → video/init (PULL_FROM_URL 또는 FILE_UPLOAD) → status/fetch
- 심사(audit) 전 앱은 SELF_ONLY(비공개)로만 게시됩니다.
- PULL_FROM_URL 은 TikTok 개발자 포털에서 도메인 인증이 필요합니다.
필요 scope: video.publish (게시), video.list (성과 조회)
"""
from __future__ import annotations

import os
import time

from app.connectors.base import BaseConnector, ConnectorError, MetricsResult, PublishRequest, PublishResult

API = "https://open.tiktokapis.com"


class TikTokConnector(BaseConnector):
    platform = "tiktok"
    poll_interval_seconds = 5.0
    max_polls = 36

    def missing_settings(self) -> list[str]:
        return [] if self.settings.tiktok_access_token else ["TIKTOK_ACCESS_TOKEN (설정 화면에서 TikTok 연결)"]

    def is_configured(self) -> bool:
        return not self.missing_settings()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.settings.tiktok_access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def refresh_token(self) -> bool:
        s = self.settings
        if not (s.tiktok_refresh_token and s.tiktok_client_key and s.tiktok_client_secret):
            return False
        data = self._request(
            "POST",
            f"{API}/v2/oauth/token/",
            "토큰 갱신",
            data={
                "client_key": s.tiktok_client_key,
                "client_secret": s.tiktok_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": s.tiktok_refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if not data.get("access_token"):
            return False
        from app.core.secret_store import save_secrets

        save_secrets(
            {"TIKTOK_ACCESS_TOKEN": data["access_token"], "TIKTOK_REFRESH_TOKEN": data.get("refresh_token", "")}
        )
        from app.core.config import get_settings

        self.settings = get_settings()
        return True

    def _api(self, path: str, what: str, json: dict | None = None, params: dict | None = None) -> dict:
        try:
            data = self._request("POST", f"{API}{path}", what, json=json or {}, params=params, headers=self._headers())
        except ConnectorError as exc:
            if exc.status_code == 401 and self.refresh_token():
                data = self._request("POST", f"{API}{path}", what, json=json or {}, params=params, headers=self._headers())
            else:
                raise
        err = data.get("error") or {}
        if isinstance(err, dict) and err.get("code") not in (None, "ok"):
            raise ConnectorError(
                f"TikTok {what} 실패: {err.get('code')} {err.get('message', '')}",
                retryable=err.get("code") in ("rate_limit_exceeded", "internal_error"),
                response=data,
            )
        return data.get("data") or {}

    def _publish_live(self, req: PublishRequest) -> PublishResult:
        if not (req.media_url or req.media_path) or not req.is_video:
            raise ConnectorError("TikTok 게시에는 영상 파일(mp4 등)이 필요합니다.", retryable=False)
        creator = self._api("/v2/post/publish/creator_info/query/", "크리에이터 정보 조회")
        options = creator.get("privacy_level_options") or []
        privacy = self.settings.tiktok_privacy_level
        if options and privacy not in options:
            raise ConnectorError(f"공개 범위 {privacy} 를 사용할 수 없습니다. 가능: {options}", retryable=False)
        post_info = {
            "title": req.full_caption[:2200],
            "privacy_level": privacy,
            "disable_comment": False,
            "disable_duet": False,
            "disable_stitch": False,
        }
        upload_url = None
        size = 0
        if req.media_url:
            source = {"source": "PULL_FROM_URL", "video_url": req.media_url}
        else:
            size = os.path.getsize(req.media_path)
            if size > 64 * 1024 * 1024:
                raise ConnectorError("64MB 이하 영상만 단일 업로드를 지원합니다.", retryable=False)
            source = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}
        init = self._api("/v2/post/publish/video/init/", "업로드 초기화", json={"post_info": post_info, "source_info": source})
        publish_id = init.get("publish_id")
        upload_url = init.get("upload_url")
        if not publish_id:
            raise ConnectorError("TikTok publish_id 를 받지 못했습니다.")
        if upload_url:
            with open(req.media_path, "rb") as fh:
                resp = self.http.put(
                    upload_url,
                    content=fh.read(),
                    headers={"Content-Type": "video/mp4", "Content-Range": f"bytes 0-{size - 1}/{size}"},
                )
            self._check(resp, "영상 업로드")

        for _ in range(self.max_polls):
            st = self._api("/v2/post/publish/status/fetch/", "게시 상태 확인", json={"publish_id": publish_id})
            status = st.get("status")
            if status == "PUBLISH_COMPLETE":
                ids = st.get("publicaly_available_post_id") or st.get("publicly_available_post_id") or []
                post_id = str(ids[0]) if ids else ""
                return PublishResult(
                    success=True,
                    external_id=post_id or publish_id,
                    raw={"publish_id": publish_id, "privacy_level": privacy},
                    message="" if post_id else "비공개(SELF_ONLY) 게시는 공개 post id 가 없어 성과 조회가 제한됩니다.",
                )
            if status == "FAILED":
                raise ConnectorError(f"TikTok 게시 실패: {st.get('fail_reason')}", retryable=False, response=st)
            time.sleep(self.poll_interval_seconds)
        raise ConnectorError("TikTok 게시 상태 확인 시간 초과", retryable=True)

    def get_metrics(self, external_id: str, hours_since_publish: float = 24.0) -> MetricsResult:
        if not external_id.isdigit():
            return MetricsResult()  # publish_id 만 있는 경우 조회 불가 → 모두 null
        data = self._api(
            "/v2/video/query/",
            "영상 성과 조회",
            params={"fields": "id,view_count,like_count,comment_count,share_count"},
            json={"filters": {"video_ids": [external_id]}},
        )
        videos = data.get("videos") or []
        if not videos:
            return MetricsResult()
        v = videos[0]
        return MetricsResult(
            views=v.get("view_count"),
            likes=v.get("like_count"),
            comments=v.get("comment_count"),
            shares=v.get("share_count"),
        )
