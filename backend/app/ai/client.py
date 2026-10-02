"""Claude API wrapper.

- ANTHROPIC_API_KEY 가 없으면 is_available() == False → 각 기능이 Mock AI 로 대체됩니다.
- 구조화 출력(JSON schema)으로 항상 파싱 가능한 결과를 받습니다.
- 안전 분류기가 요청을 거절(refusal)하면 서버 측 fallback 모델로 자동 재시도합니다.
- 모든 호출은 timeout 이 설정되어 있고, 사용량은 event log 에 기록됩니다 (키는 기록 안 함).
"""
from __future__ import annotations

import json
from typing import Any

import anthropic

from app.core.config import get_settings
from app.services.events import log_event

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AIError(Exception):
    pass


class ClaudeClient:
    def __init__(self, sdk_client: Any | None = None):
        self.settings = get_settings()
        self._client = sdk_client
        self._fallback_ok = self.settings.claude_use_fallback

    def is_available(self) -> bool:
        return self._client is not None or bool(self.settings.anthropic_api_key)

    @property
    def client(self):
        if self._client is None:
            if not self.settings.anthropic_api_key:
                raise AIError("ANTHROPIC_API_KEY 가 설정되지 않았습니다.")
            self._client = anthropic.Anthropic(
                api_key=self.settings.anthropic_api_key,
                timeout=self.settings.claude_timeout_seconds,
                max_retries=2,
            )
        return self._client

    def _base_params(self, max_tokens: int) -> dict:
        params: dict[str, Any] = {"model": self.settings.claude_model, "max_tokens": max_tokens}
        output_config: dict[str, Any] = {}
        if self.settings.claude_effort and not self.settings.claude_model.startswith("claude-haiku"):
            output_config["effort"] = self.settings.claude_effort
        if output_config:
            params["output_config"] = output_config
        return params

    def create(self, purpose: str, **params) -> Any:
        """messages.create with refusal fallback and usage logging."""
        try:
            if self._fallback_ok:
                try:
                    resp = self.client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **params)
                except anthropic.BadRequestError as exc:
                    if "fallback" not in str(exc).lower():
                        raise
                    self._fallback_ok = False  # 이 모델/계정에서 미지원 → 일반 호출로
                    resp = self.client.messages.create(**params)
            else:
                resp = self.client.messages.create(**params)
        except anthropic.AuthenticationError as exc:
            log_event("api_error", f"Claude 인증 실패 ({purpose}) — ANTHROPIC_API_KEY 를 확인하세요", level="ERROR")
            raise AIError("Claude API Key 가 올바르지 않습니다.") from exc
        except anthropic.RateLimitError as exc:
            log_event("api_error", f"Claude rate limit ({purpose})", level="WARNING")
            raise AIError("Claude API 사용량 한도에 걸렸습니다. 잠시 후 다시 시도하세요.") from exc
        except anthropic.APIStatusError as exc:
            log_event("api_error", f"Claude API 오류 {exc.status_code} ({purpose})", {"message": str(exc)[:500]}, level="ERROR")
            raise AIError(f"Claude API 오류 ({exc.status_code})") from exc
        except anthropic.APIConnectionError as exc:
            log_event("api_error", f"Claude 연결 실패 ({purpose})", level="ERROR")
            raise AIError("Claude API 에 연결할 수 없습니다.") from exc

        usage = getattr(resp, "usage", None)
        log_event(
            "ai_generation",
            f"Claude 호출 완료: {purpose}",
            {
                "model": getattr(resp, "model", self.settings.claude_model),
                "stop_reason": getattr(resp, "stop_reason", None),
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
            },
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            raise AIError("AI 가 이 요청을 처리하지 않았습니다 (안전 정책). 요청 내용을 바꿔 다시 시도하세요.")
        return resp

    @staticmethod
    def text_of(resp: Any) -> str:
        return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")

    def generate_json(self, purpose: str, system: str, prompt: str, schema: dict, max_tokens: int = 16000) -> dict:
        params = self._base_params(max_tokens)
        params["output_config"] = {
            **params.get("output_config", {}),
            "format": {"type": "json_schema", "schema": schema},
        }
        resp = self.create(purpose, system=system, messages=[{"role": "user", "content": prompt}], **params)
        if getattr(resp, "stop_reason", None) == "max_tokens":
            raise AIError("AI 응답이 너무 길어 잘렸습니다. 생성 개수를 줄여 다시 시도하세요.")
        text = self.text_of(resp)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIError("AI 응답을 해석하지 못했습니다.") from exc

    def generate_text(self, purpose: str, system: str, prompt: str, max_tokens: int = 8000) -> str:
        params = self._base_params(max_tokens)
        resp = self.create(purpose, system=system, messages=[{"role": "user", "content": prompt}], **params)
        return self.text_of(resp).strip()


_override: ClaudeClient | None = None


def get_ai() -> ClaudeClient:
    return _override or ClaudeClient()


def set_ai_override(client: ClaudeClient | None) -> None:
    global _override
    _override = client
