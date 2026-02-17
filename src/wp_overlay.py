import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

from src.topic_weights import generate_chat_script
from src.youtube_upload import upload_video, verify_auth
from src.pexels_bg import download_bg_from_pexels
from src.shorts_audio import tts_to_wav, build_timeline_audio

OUT = Path("out")
OUT.mkdir(exist_ok=True)

# 🔥 SHORTER = HIGHER COMPLETION
DURATION = int(os.getenv("SHORTS_SECONDS", "22"))

PRIVACY = (os.getenv("YT_DEFAULT_PRIVACY", "public") or "public").strip().lower()
if PRIVACY not in ("public", "unlisted", "private"):
    PRIVACY = "public"

FEMALE_SPK = os.getenv("SHORTS_FEMALE_SPEAKER", "p225")
INNER_SPK = os.getenv("SHORTS_INNER_SPEAKER", "p226")

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def run(cmd: List[str]):
    print(" ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, check=True)


def cleanup_out():
    try:
        for p in OUT.glob("*"):
            if p.is_file():
                p.unlink()
            else:
                shutil.rmtree(p, ignore_errors=True)
    except Exception as e:
        print("[WARN] cleanup failed:", e, flush=True)


def ensure_subscribe_badge(out_png: Path) -> Path:
    """
    Creates a transparent PNG badge (YouTube play icon + SUBSCRIBE).
    No external assets needed.
    """
    if out_png.exists() and out_png.stat().st_size > 1000:
        return out_png

    from PIL import Image, ImageDraw, ImageFont  # Pillow already used in wp_overlay

    w, h = 420, 120
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # rounded dark bg
    r = 28
    d.rounded_rectangle([0, 0, w, h], radius=r, fill=(20, 20, 20, 190))

    # red play button
    bx, by, bw, bh = 18, 18, 120, 84
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=22, fill=(230, 33, 23, 255))

    # white play triangle
    tri = [(bx + 46, by + 22), (bx + 46, by + 62), (bx + 84, by + 42)]
    d.polygon(tri, fill=(255, 255, 255, 255))

    # text
    try:
        font = ImageFont.truetype(FONT, 44)
    except Exception:
        font = ImageFont.load_default()

    d.text((bx + bw + 18, 34), "SUBSCRIBE", font=font, fill=(255, 255, 255, 245))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    print("[OK] Badge created:", out_png, flush=True)
    return out_png


@dataclass
class TimedLine:
    who: str
    text: str
    t: float
    hhmm: str


def _hhmm(base: datetime, add_min: int) -> str:
    return (base + timedelta(minutes=add_min)).strftime("%-I:%M %p")


def generate_chat() -> Tuple[str, List[TimedLine]]:
    """
    Expects: generate_chat_script() -> (title, raw_lines)
      raw_lines: [("A","..."),("INNER","..."),...]
    """
    base = datetime.utcnow()
    title, raw_lines = generate_chat_script()

    # 22-second pacing optimized for replay
    appear = [0.7, 3.5, 6.5, 11.0, 15.5]

    out: List[TimedLine] = []
    for i, ((who, text), t) in enumerate(zip(raw_lines, appear)):
        out.append(
            TimedLine(
                who=who,
                text=text,
                t=t,
                hhmm=_hhmm(base, i),
            )
        )
    return title, out


def render_final(
    bg_mp4: Path,
    overlays: List[Path],
    times: List[float],
    audio_wav: Path,
    out_mp4: Path,
    chat_h: int = 860,
):
    """
    bg video: only in bottom area (below chat_h)
    overlays: PNG overlays (full-size 1080x1920 with alpha)
    times: start time for each overlay
    audio: ONLY voices
    + subscribe badge (left-middle) last ~2.3 sec
    """
    assert len(overlays) == len(times), "overlays and times must have same length"

    badge = ensure_subscribe_badge(OUT / "subscribe_badge.png")
    use_badge = badge.exists() and badge.stat().st_size > 1000

    cmd = [
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "error",
        "-stream_loop", "-1", "-i", str(bg_mp4),
    ]

    # WhatsApp overlay pngs
    for p in overlays:
        cmd += ["-i", str(p)]

    # Subscribe badge png (optional)
    if use_badge:
        cmd += ["-i", str(badge)]

    # Audio last
    cmd += ["-i", str(audio_wav)]

    bottom_h = 1920 - chat_h

    vf = []
    vf.append(
        f"[0:v]"
        f"scale=1080:{bottom_h}:force_original_aspect_ratio=increase,"
        f"crop=1080:{bottom_h},"
        f"eq=contrast=1.05:saturation=1.10"
        f"[v0]"
    )
    vf.append(f"[v0]pad=1080:1920:0:{chat_h}:color=black[base]")

    # Apply WhatsApp overlays
    cur = "base"
    for i, t_start in enumerate(times, start=1):
        in_idx = i  # overlays start from input 1
        out_lbl = f"v{i}"
        vf.append(
            f"[{cur}][{in_idx}:v]"
            f"overlay=0:0:enable=between(t\\,{t_start:.3f}\\,{float(DURATION):.3f})"
            f"[{out_lbl}]"
        )
        cur = out_lbl

    # Subscribe badge overlay (LEFT-MIDDLE of FULL SCREEN)
    # Inputs: 0 bg, 1..N overlays, (N+1) badge, last audio
    if use_badge:
        badge_idx = 1 + len(overlays)

        start = max(0.0, DURATION - 3.3)
        end = float(DURATION)

        # Smaller + clean
        vf.append(f"[{badge_idx}:v]format=rgba,scale=280:-1[badge]")

        # Position: left-middle of the entire 1080x1920
        # y=(H-h)/2 avoids bottom and avoids most chat-bubble overlap
        vf.append(
            f"[{cur}][badge]"
            f"overlay=x=40:y=(H-h)/2:enable=between(t\\,{start:.3f}\\,{end:.3f})"
            f"[vfinal]"
        )
    else:
        vf.append(f"[{cur}]null[vfinal]")

    filter_complex = ";".join(vf)

    # audio index depends on whether badge exists
    if use_badge:
        audio_idx = badge_idx + 1
    else:
        audio_idx = len(overlays) + 1

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[vfinal]",
        "-map", f"{audio_idx}:a",
        "-t", str(DURATION),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "160k",
        "-movflags", "+faststart",
        str(out_mp4),
    ]

    run(cmd)


def main():
    try:
        verify_auth()

        # 1) BG video
        bg = OUT / "bg.mp4"
        download_bg_from_pexels(bg)

        # 2) Chat
        title, lines = generate_chat()

        # 3) WhatsApp overlays (INNER rendered as B)
        wp_msgs: List[WpMsg] = []
        for l in lines:
            who = "A" if l.who == "A" else "B"
            wp_msgs.append(WpMsg(who=who, text=l.text, hhmm=l.hhmm))

        overlay_dir = OUT / "overlays"
        overlays = render_whatsapp_overlays(overlay_dir, wp_msgs, font_path=FONT)

        # Typing timing
        times: List[float] = []
        for l in lines:
            t0 = max(0.0, l.t - 0.75)
            times.append(t0)
            times.append(t0 + 0.25)
            times.append(t0 + 0.50)
            times.append(l.t)

        # 4) TTS audio timeline
        tts_dir = OUT / "tts"
        tts_dir.mkdir(exist_ok=True)

        wav_items: List[Tuple[float, Path]] = []
        for i, l in enumerate(lines, start=1):
            wav = tts_dir / f"m{i:02d}.wav"
            speaker = FEMALE_SPK if l.who == "A" else INNER_SPK
            tts_to_wav(l.text, wav, speaker=speaker)
            wav_items.append((l.t + 0.02, wav))

        audio = OUT / "chat_audio.wav"
        build_timeline_audio(wav_items, audio, total_sec=DURATION)

        # 5) Render final mp4
        mp4 = OUT / "short.mp4"
        render_final(bg, overlays, times, audio, mp4, chat_h=860)

        # 6) Upload
        hashtags = "#shorts #relatable #innerthoughts #psychology"
        description = f"{title}\n\n{hashtags}\n"

        upload_video(
            video_file=str(mp4),
            title=title,
            description=description,
            tags=["shorts", "chat", "inner thoughts", "psychology"],
            privacy_status=PRIVACY,
            category_id="22",
            language="en",
            thumbnail_file=None,
        )

        print("[OK] Uploaded successfully.", flush=True)

    finally:
        cleanup_out()


if __name__ == "__main__":
    main()
# ---- Export guarantee for pipeline ----
# Some refactors/renames can break imports. This keeps the pipeline stable.
__all__ = ["Msg", "render_whatsapp_overlays"]
