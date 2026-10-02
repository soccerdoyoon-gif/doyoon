"""OAuth 연결 (비밀번호는 절대 저장하지 않음 — 공식 OAuth 로 받은 토큰만 data/secrets.env 에 저장).

- X:        OAuth 2.0 Authorization Code + PKCE
- TikTok:   Login Kit (Authorization Code)
- Instagram: Instagram API with Instagram Login (Authorization Code → 장기 토큰 교환)
Redirect URI: {PUBLIC_BASE_URL}/api/oauth/{platform}/callback  ← 각 개발자 포털에 그대로 등록하세요.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.secret_store import save_secrets
from app.services.events import log_event

router = APIRouter(prefix="/api/oauth", tags=["oauth"])
_pending: dict[str, dict] = {}
STATE_TTL = 900

X_SCOPES = "tweet.read tweet.write users.read offline.access"
TIKTOK_SCOPES = "user.info.basic,video.publish,video.upload,video.list"
IG_SCOPES = "instagram_business_basic,instagram_business_content_publish,instagram_business_manage_insights"


def _redirect_uri(platform: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/api/oauth/{platform}/callback"


def _done(platform: str, ok: bool, msg: str = "") -> RedirectResponse:
    q = urlencode({"oauth": platform, "status": "ok" if ok else "error", "msg": msg[:200]})
    return RedirectResponse(f"{get_settings().public_base_url.rstrip('/')}/settings?{q}")


def _new_state(platform: str, **extra) -> str:
    now = time.time()
    for k in [k for k, v in _pending.items() if now - v["ts"] > STATE_TTL]:
        _pending.pop(k, None)
    state = secrets.token_urlsafe(24)
    _pending[state] = {"platform": platform, "ts": now, **extra}
    return state


@router.get("/{platform}/start")
def start(platform: str):
    s = get_settings()
    if platform == "x":
        if not s.x_client_id:
            raise HTTPException(400, "X_CLIENT_ID 를 먼저 설정하세요.")
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = _new_state("x", verifier=verifier)
        url = "https://x.com/i/oauth2/authorize?" + urlencode({
            "response_type": "code", "client_id": s.x_client_id, "redirect_uri": _redirect_uri("x"),
            "scope": X_SCOPES, "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
        })
    elif platform == "tiktok":
        if not s.tiktok_client_key:
            raise HTTPException(400, "TIKTOK_CLIENT_KEY 를 먼저 설정하세요.")
        state = _new_state("tiktok")
        url = "https://www.tiktok.com/v2/auth/authorize/?" + urlencode({
            "client_key": s.tiktok_client_key, "scope": TIKTOK_SCOPES, "response_type": "code",
            "redirect_uri": _redirect_uri("tiktok"), "state": state,
        })
    elif platform == "instagram":
        if not s.instagram_app_id:
            raise HTTPException(400, "INSTAGRAM_APP_ID 를 먼저 설정하세요.")
        state = _new_state("instagram")
        url = "https://www.instagram.com/oauth/authorize?" + urlencode({
            "client_id": s.instagram_app_id, "redirect_uri": _redirect_uri("instagram"),
            "response_type": "code", "scope": IG_SCOPES, "state": state,
        })
    else:
        raise HTTPException(404, "지원하지 않는 플랫폼")
    return {"authorize_url": url, "redirect_uri": _redirect_uri(platform)}


@router.get("/{platform}/callback")
def callback(platform: str, code: str = "", state: str = "", error: str = ""):
    pending = _pending.pop(state, None)
    if error:
        return _done(platform, False, error)
    if not pending or pending["platform"] != platform or time.time() - pending["ts"] > STATE_TTL:
        return _done(platform, False, "invalid_state")
    s = get_settings()
    timeout = httpx.Timeout(s.http_timeout_seconds)
    try:
        if platform == "x":
            auth = (s.x_client_id, s.x_client_secret) if s.x_client_secret else None
            r = httpx.post("https://api.x.com/2/oauth2/token", timeout=timeout, auth=auth, data={
                "code": code, "grant_type": "authorization_code", "client_id": s.x_client_id,
                "redirect_uri": _redirect_uri("x"), "code_verifier": pending["verifier"],
            })
            r.raise_for_status()
            d = r.json()
            save_secrets({"X_ACCESS_TOKEN": d["access_token"], "X_REFRESH_TOKEN": d.get("refresh_token", "")})
        elif platform == "tiktok":
            r = httpx.post("https://open.tiktokapis.com/v2/oauth/token/", timeout=timeout, data={
                "client_key": s.tiktok_client_key, "client_secret": s.tiktok_client_secret, "code": code,
                "grant_type": "authorization_code", "redirect_uri": _redirect_uri("tiktok"),
            }, headers={"Content-Type": "application/x-www-form-urlencoded"})
            r.raise_for_status()
            d = r.json()
            if not d.get("access_token"):
                return _done(platform, False, str(d.get("error_description") or d.get("error") or "token_error"))
            save_secrets({"TIKTOK_ACCESS_TOKEN": d["access_token"], "TIKTOK_REFRESH_TOKEN": d.get("refresh_token", "")})
        elif platform == "instagram":
            r = httpx.post("https://api.instagram.com/oauth/access_token", timeout=timeout, data={
                "client_id": s.instagram_app_id, "client_secret": s.instagram_app_secret, "grant_type": "authorization_code",
                "redirect_uri": _redirect_uri("instagram"), "code": code,
            })
            r.raise_for_status()
            d = r.json()
            if isinstance(d.get("data"), list) and d["data"]:
                d = d["data"][0]
            short = d["access_token"]
            r2 = httpx.get("https://graph.instagram.com/access_token", timeout=timeout, params={
                "grant_type": "ig_exchange_token", "client_secret": s.instagram_app_secret, "access_token": short,
            })
            r2.raise_for_status()
            long_token = r2.json()["access_token"]
            r3 = httpx.get(f"https://graph.instagram.com/{s.meta_graph_version}/me", timeout=timeout,
                           params={"fields": "user_id,username", "access_token": long_token})
            r3.raise_for_status()
            me = r3.json()
            save_secrets({"INSTAGRAM_ACCESS_TOKEN": long_token, "INSTAGRAM_USER_ID": str(me.get("user_id") or d.get("user_id"))})
        else:
            return _done(platform, False, "unsupported")
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log_event("api_error", f"OAuth 토큰 교환 실패 ({platform}): {type(exc).__name__}", level="ERROR")
        return _done(platform, False, type(exc).__name__)
    log_event("system", f"OAuth 연결 완료: {platform}")
    return _done(platform, True)
