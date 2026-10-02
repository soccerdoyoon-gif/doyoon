"""숏폼 영상 생성 (9:16, 1080x1920).

Short-form Script Agent 의 장면(scene) 정보로 영상을 만듭니다.
- 장면별 배경(브랜드 컬러 미니멀 배경 또는 AI 비주얼) + 짧게 나눈 일본어 자막(화면에 직접 합성)
- VOICEVOX 가 연결되어 있으면 일본어 음성(voiceover) 포함, 없으면 무음
- .srt 자막 파일과 썸네일(9:16)도 함께 저장
외부 영상 생성 AI 를 쓰려면 content.video_prompt 와 scenes(JSON)를 그대로 사용하면 됩니다.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.media import image_render, storage
from app.media.image_providers import get_image_provider
from app.media.tts import get_tts, speaker_for, wav_duration
from app.models import ContentItem, GeneratedAsset

logger = get_logger("video")
SUB_MAX_CHARS = 14  # 한 화면 자막 최대 글자 수 (짧게 나눔)
SPLIT_RE = re.compile(r"(?<=[。！？!?、\n])|\s+")


class VideoError(RuntimeError):
    pass


def ffmpeg_exe() -> str | None:
    """시스템 ffmpeg → 없으면 pip 패키지(imageio-ffmpeg)에 포함된 ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def ffmpeg_available() -> bool:
    return ffmpeg_exe() is not None


def split_subtitle(text: str, max_chars: int = SUB_MAX_CHARS) -> list[str]:
    """자막을 읽기 쉬운 짧은 덩어리로 나눔. 구두점 우선, 길면 강제로 자름."""
    text = (text or "").strip()
    if not text:
        return []
    phrases = [p.strip() for p in SPLIT_RE.split(text) if p and p.strip()]
    chunks: list[str] = []
    cur = ""
    for p in phrases:
        while len(p) > max_chars:
            cut = max_chars
            while cut > max_chars // 2 and p[cut] in image_render.NO_LINE_START:
                cut -= 1
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(p[:cut])
            p = p[cut:]
        if len(cur) + len(p) <= max_chars:
            cur += p
        else:
            if cur:
                chunks.append(cur)
            cur = p
        if cur and cur[-1] in "。！？!?":  # 문장 끝에서는 항상 끊음
            chunks.append(cur)
            cur = ""
    if cur:
        chunks.append(cur)
    return chunks


def _ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _run(cmd: list[str]) -> None:
    if cmd and cmd[0] == "ffmpeg":
        cmd = [ffmpeg_exe() or "ffmpeg", *cmd[1:]]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise VideoError(f"ffmpeg 실패: {proc.stderr[-400:]}")


def render_video(
    db: Session,
    item: ContentItem,
    *,
    brand_name: str,
    voice_cfg: dict,
    ai_scene_images: bool = False,
) -> list[GeneratedAsset]:
    if not ffmpeg_available():
        raise VideoError("ffmpeg 가 설치되어 있지 않아 영상 파일을 만들 수 없습니다 (장면 정보/프롬프트는 저장됨).")
    scenes = item.scenes or []
    if not scenes:
        raise VideoError("장면(scene) 정보가 없습니다.")
    s = get_settings()
    tts = get_tts()
    use_voice = voice_cfg.get("enabled", True) and tts.is_available()
    speaker = speaker_for(voice_cfg)
    tone = voice_cfg.get("tone", "casual")
    provider = get_image_provider() if ai_scene_images else None
    seed = item.idea_id or item.id
    assets: list[GeneratedAsset] = []

    with tempfile.TemporaryDirectory(prefix="sns-video-") as tmp_s:
        tmp = Path(tmp_s)
        frame_lines: list[str] = []
        audio_lines: list[str] = []
        srt: list[str] = []
        t = 0.0
        cue = 1
        last_frame = None
        for i, sc in enumerate(scenes):
            subtitle = (sc.get("subtitle") or sc.get("voiceover") or "").strip()
            voice_text = (sc.get("voiceover") or "").strip()
            dur = max(1.0, float(sc.get("duration") or 2))
            audio_path = tmp / f"a{i}.wav"
            wav = tts.synthesize(voice_text, speaker, tone) if use_voice and voice_text else None
            if wav:
                raw = tmp / f"raw{i}.wav"
                raw.write_bytes(wav)
                dur = max(dur, wav_duration(wav) + 0.3)
                _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", "apad", "-t", f"{dur:.3f}", "-ar", "44100", "-ac", "2", str(audio_path)])
            else:
                _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{dur:.3f}", str(audio_path)])
            audio_lines.append(f"file '{audio_path.as_posix()}'")

            ai_img = provider.generate(sc.get("visual", ""), "9:16") if provider and provider.name != "template" else None
            bg = image_render.scene_background(sc.get("visual", ""), style=item.style, seed=f"{seed}-{i}", brand_name=brand_name, ai_image=ai_img)
            chunks = split_subtitle(subtitle) or [""]
            total_chars = sum(max(1, len(c)) for c in chunks)
            for j, chunk in enumerate(chunks):
                cdur = dur * max(1, len(chunk)) / total_chars
                frame = tmp / f"f{i}_{j}.png"
                image_render.render_subtitle_frame(bg, chunk, centered=ai_img is None).save(frame, compress_level=1)
                frame_lines += [f"file '{frame.as_posix()}'", f"duration {cdur:.3f}"]
                last_frame = frame
                if chunk:
                    srt += [str(cue), f"{_ts(t)} --> {_ts(t + cdur)}", chunk, ""]
                    cue += 1
                t += cdur
        frame_lines.append(f"file '{last_frame.as_posix()}'")  # concat demuxer 규칙: 마지막 프레임 반복
        (tmp / "frames.txt").write_text("\n".join(frame_lines), encoding="utf-8")
        (tmp / "audio.txt").write_text("\n".join(audio_lines), encoding="utf-8")
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "audio.txt"), "-c", "copy", str(tmp / "audio.wav")])

        out_abs, out_rel = storage.new_file("video", "mp4", content_id=item.id, purpose=item.platform)
        _run([
            "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "frames.txt"),
            "-i", str(tmp / "audio.wav"), "-vf", f"fps={s.video_fps},format=yuv420p", "-c:v", "libx264", "-preset", s.video_preset,
            "-tune", "stillimage", "-crf", "23", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
            "-metadata", f"comment=content_id={item.id}", str(out_abs),
        ])
        assets.append(storage.record(
            db, "video", out_rel, content_id=item.id, idea_id=item.idea_id, purpose=item.platform, aspect="9:16",
            width=1080, height=1920, duration=round(t, 2), provider="slideshow" + ("+voicevox" if use_voice else ""),
            prompt=item.video_prompt, meta={"voice": use_voice, "speaker": speaker if use_voice else None, "scenes": len(scenes)},
        ))
        srt_abs, srt_rel = storage.new_file("subtitle", "srt", content_id=item.id, purpose=item.platform)
        srt_abs.write_text("\n".join(srt), encoding="utf-8")
        assets.append(storage.record(db, "subtitle", srt_rel, content_id=item.id, idea_id=item.idea_id, purpose=item.platform))

    thumb = image_render.render("thumbnail", item.thumbnail_text or item.hook, brand_name=brand_name, style=item.style, seed=seed)
    th_abs, th_rel = storage.new_file("thumbnail", "jpg", content_id=item.id, purpose=item.platform)
    save_jpeg(thumb, th_abs, item.id)
    assets.append(storage.record(
        db, "thumbnail", th_rel, content_id=item.id, idea_id=item.idea_id, purpose=item.platform, aspect="9:16",
        width=1080, height=1920, overlay_text=item.thumbnail_text or item.hook,
    ))
    return assets


def save_jpeg(img, path: Path, content_id: int | None = None, ad_id: int | None = None) -> None:
    from PIL import Image

    exif = Image.Exif()
    exif[0x010E] = f"content_id={content_id}" if content_id else f"ad_creative_id={ad_id}"  # ImageDescription
    img.convert("RGB").save(path, "JPEG", quality=92, exif=exif)
