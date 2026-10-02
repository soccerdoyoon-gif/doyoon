"""Application settings.

모든 설정은 환경변수 / .env 파일 / data/secrets.env 에서 읽습니다.
API Key, Access Token 같은 비밀값은 절대 소스코드에 쓰지 마세요.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> project root is 3 levels up from backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"
SECRETS_FILE_NAME = "secrets.env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- General -----------------------------------------------------------
    app_name: str = "SNS AI Marketing"
    dry_run: bool = True  # 초기에는 반드시 true. 실제 게시/광고 수정/결제 없음
    # --- 기본 시장: 일본 (코드 전체에서 이 값을 사용) ---------------------
    default_country: str = "JP"
    default_language: str = "ja"  # 콘텐츠 기본 언어. ko/en 은 요청할 때만 사용
    default_currency: str = "JPY"
    default_timezone: str = Field(default="Asia/Tokyo", validation_alias=AliasChoices("DEFAULT_TIMEZONE", "TIMEZONE"))
    data_dir: Path = DEFAULT_DATA_DIR
    log_dir: Path = DEFAULT_LOG_DIR
    database_url: str = ""  # 비어 있으면 data/app.db (SQLite)
    scheduler_enabled: bool = True
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    public_base_url: str = "http://localhost:8000"  # OAuth redirect 에 사용
    http_timeout_seconds: float = 20.0

    # --- AI (Claude) -------------------------------------------------------
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5-5"
    claude_effort: str = "medium"  # low / medium / high
    claude_use_fallback: bool = True
    claude_timeout_seconds: float = 300.0

    # --- Meta (Instagram / Facebook / Ads) ---------------------------------
    meta_graph_version: str = "v26.0"
    # Instagram API with Instagram Login -> graph.instagram.com
    # Instagram API with Facebook Login  -> graph.facebook.com
    instagram_api_host: str = "graph.instagram.com"
    meta_app_id: str = ""
    meta_app_secret: str = ""
    instagram_app_id: str = ""  # Instagram Login 용 앱 ID (App Dashboard > Instagram > API setup)
    instagram_app_secret: str = ""
    instagram_access_token: str = ""
    instagram_user_id: str = ""
    facebook_page_id: str = ""
    facebook_page_access_token: str = ""
    meta_ads_access_token: str = ""
    meta_ad_account_id: str = ""  # 숫자만 (act_ 접두어 없이)

    # --- TikTok ------------------------------------------------------------
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_access_token: str = ""
    tiktok_refresh_token: str = ""
    # 심사(audit) 전 앱은 SELF_ONLY(비공개) 게시만 가능합니다.
    tiktok_privacy_level: str = "SELF_ONLY"

    # --- X -----------------------------------------------------------------
    x_client_id: str = ""
    x_client_secret: str = ""
    x_access_token: str = ""
    x_refresh_token: str = ""

    # --- Media -------------------------------------------------------------
    # Instagram/TikTok(PULL_FROM_URL) 는 공개 URL 의 이미지/영상만 가져갈 수 있습니다.
    public_media_base_url: str = ""

    # --- Notifications -----------------------------------------------------
    slack_webhook_url: str = ""
    discord_webhook_url: str = ""

    # --- Creative (이미지 / 영상 / 음성) -------------------------------------
    assets_dir: Path = PROJECT_ROOT / "assets"
    # template: 서버에서 직접 디자인 이미지를 그림 (무료)
    # openai  : OpenAI 이미지 API 로 배경 비주얼 생성 + 일본어 문구는 서버에서 합성 (유료)
    image_provider: str = "template"
    openai_api_key: str = ""
    openai_image_model: str = "gpt-image-1"
    # slideshow: 장면 이미지 + 일본어 자막 + 음성으로 9:16 초안 영상(mp4)을 서버에서 생성 (ffmpeg 필요)
    # none     : 영상 파일 없이 장면(Scene) 정보와 영상 생성 프롬프트만 생성
    video_provider: str = "slideshow"
    video_fps: int = 30  # Instagram Reels 는 23~60fps 필요
    video_preset: str = "veryfast"  # ffmpeg x264 preset (빠를수록 파일이 커짐)
    voicevox_url: str = ""  # 예: http://localhost:50021 (무료 일본어 TTS 엔진)
    font_path: str = ""  # 일본어 폰트 파일 경로 (비우면 자동 탐색)
    trend_web_search: bool = True
    pipeline_background: bool = True  # 콘텐츠 생성 파이프라인을 백그라운드로 실행 (테스트에서는 false)  # 트렌드 조사에 Claude 웹 검색 사용 (검색당 추가 요금)

    retry_delays_minutes: list[int] = Field(default_factory=lambda: [1, 5, 15])

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(self.data_dir / 'app.db').as_posix()}"

    @property
    def secrets_file(self) -> Path:
        return self.data_dir / SECRETS_FILE_NAME

    @property
    def timezone(self) -> str:
        return self.default_timezone

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    # 우선순위: 환경변수 > data/secrets.env (화면에서 저장한 키) > .env
    data_dir = Path(os.environ.get("DATA_DIR") or DEFAULT_DATA_DIR)
    return Settings(_env_file=(str(PROJECT_ROOT / ".env"), str(data_dir / SECRETS_FILE_NAME)))


def reload_settings() -> Settings:
    """Clear cache so newly saved secrets are picked up."""
    get_settings.cache_clear()
    return get_settings()
