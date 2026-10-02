"""일본어 음성 합성 (VOICEVOX 엔진, 무료/로컬).

VOICEVOX_URL 이 설정되어 있으면 사용하고, 없으면 음성 없이(자막만) 영상을 만듭니다.
※ VOICEVOX 음성을 상업적으로 쓸 때는 각 캐릭터 이용약관의 크레딧 표기(例: VOICEVOX:春日部つむぎ)를 확인하세요.
"""
from __future__ import annotations

import io
import wave

import httpx

from app.core.config import get_settings
from app.services.events import log_event

TONE_PARAMS = {
    "casual": {"speedScale": 1.05, "pitchScale": 0.0, "intonationScale": 1.1},
    "energetic": {"speedScale": 1.15, "pitchScale": 0.02, "intonationScale": 1.3},
    "calm": {"speedScale": 0.95, "pitchScale": -0.01, "intonationScale": 0.9},
    "luxury": {"speedScale": 0.9, "pitchScale": -0.02, "intonationScale": 0.85},
}


class VoicevoxTTS:
    def __init__(self, http: httpx.Client | None = None):
        self.url = get_settings().voicevox_url.rstrip("/")
        self.http = http or httpx.Client(timeout=httpx.Timeout(60.0))

    def is_available(self) -> bool:
        return bool(self.url)

    def speakers(self) -> list[dict]:
        r = self.http.get(f"{self.url}/speakers")
        r.raise_for_status()
        return [{"name": sp["name"], "style": st["name"], "id": st["id"]} for sp in r.json() for st in sp.get("styles", [])]

    def synthesize(self, text: str, speaker: int, tone: str = "casual") -> bytes | None:
        try:
            q = self.http.post(f"{self.url}/audio_query", params={"text": text, "speaker": speaker})
            q.raise_for_status()
            query = q.json()
            query.update(TONE_PARAMS.get(tone, TONE_PARAMS["casual"]))
            r = self.http.post(f"{self.url}/synthesis", params={"speaker": speaker}, json=query)
            r.raise_for_status()
            return r.content
        except (httpx.HTTPError, ValueError) as exc:
            log_event("api_error", f"VOICEVOX 음성 합성 실패 → 자막만 사용: {type(exc).__name__}", level="WARNING")
            return None


def speaker_for(voice_cfg: dict, gender: str | None = None, tone: str | None = None) -> int:
    g = gender or voice_cfg.get("gender", "female")
    t = tone or voice_cfg.get("tone", "casual")
    table = voice_cfg.get("speakers", {}).get(g, {})
    return int(table.get(t, next(iter(table.values()), 8)))


def wav_duration(data: bytes) -> float:
    with wave.open(io.BytesIO(data)) as w:
        return w.getnframes() / float(w.getframerate())


_override = None


def get_tts():
    return _override or VoicevoxTTS()


def set_tts_override(t) -> None:
    global _override
    _override = t
