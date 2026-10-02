"""리포트 전송 채널. 새 채널은 Notifier 를 상속해 NOTIFIERS 에 등록하면 됩니다.

현재: file (항상 data/reports 에 저장), slack, discord (Webhook URL 설정 시)
추후: email, line — 같은 구조로 추가
"""
from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.services.events import log_event


class Notifier:
    name = "base"

    def is_configured(self) -> bool:
        return False

    def send(self, title: str, body: str) -> None:  # pragma: no cover
        raise NotImplementedError


class FileNotifier(Notifier):
    name = "file"

    def is_configured(self) -> bool:
        return True

    def send(self, title: str, body: str) -> None:
        pass  # report_service 가 이미 파일로 저장함


class SlackNotifier(Notifier):
    name = "slack"

    def is_configured(self) -> bool:
        return bool(get_settings().slack_webhook_url)

    def send(self, title: str, body: str) -> None:
        httpx.post(get_settings().slack_webhook_url, json={"text": f"*{title}*\n{body[:35000]}"}, timeout=15).raise_for_status()


class DiscordNotifier(Notifier):
    name = "discord"

    def is_configured(self) -> bool:
        return bool(get_settings().discord_webhook_url)

    def send(self, title: str, body: str) -> None:
        httpx.post(get_settings().discord_webhook_url, json={"content": f"**{title}**\n{body}"[:1990]}, timeout=15).raise_for_status()


NOTIFIERS: dict[str, Notifier] = {n.name: n for n in (FileNotifier(), SlackNotifier(), DiscordNotifier())}


def dispatch(channels: list[str], title: str, body: str) -> dict[str, str]:
    results = {}
    for ch in channels:
        n = NOTIFIERS.get(ch)
        if n is None:
            results[ch] = "unknown channel"
            continue
        if not n.is_configured():
            results[ch] = "not configured"
            continue
        try:
            n.send(title, body)
            results[ch] = "sent"
        except Exception as exc:
            results[ch] = f"error: {type(exc).__name__}"
            log_event("api_error", f"리포트 전송 실패 ({ch}): {type(exc).__name__}", level="WARNING")
    return results
