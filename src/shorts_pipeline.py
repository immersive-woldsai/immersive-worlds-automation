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
from src.wp_overlay import render_whatsapp_overlays, Msg as WpMsg

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


@dataclass
class TimedLine:
    who: str
    text: str
    t: float
    hhmm: str


def _hhmm(base: datetime, add_min: int) -> str:
    # e.g. 1:05 PM
    return (base + timedelta(minutes=add_min)).strftime("%-I:%M %p")


def generate_chat() -> Tuple[str, List[TimedLine]]:
    """
    Uses AI pattern engine:
    topic_weights.generate_chat_script() -> (title, raw_lines)
      raw_lines: [("A", "..."), ("INNER", "..."), ...]
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
    """
    assert len(overlays) == len(times), "overlays and times must have same length"

    cmd = [
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "error",
        "-stream_loop", "-1", "-i", str(bg_mp4),
    ]

    for p in overlays:
        cmd += ["-i", str(p)]

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

    cur = "base"
    for i, t_start in enumerate(times, start=1):
        in_idx = i
        out_lbl = f"v{i}"
        vf.append(
            f"[{cur}][{in_idx}:v]"
            f"overlay=0:0:enable=between(t\\,{t_start:.3f}\\,{float(DURATION):.3f})"
            f"[{out_lbl}]"
        )
        cur = out_lbl

    # 🔥 SUBSCRIBE CTA (subtle, last 2.5 seconds)
    vf.append(
        f"[{cur}]drawtext=text='Subscribe for more...':"
        f"fontcolor=white@0.75:fontsize=36:"
        f"x=(w-text_w)/2:y=1850:"
        f"enable=between(t\\,{DURATION-2.5}\\,{DURATION})"
        f"[vfinal]"
    )

    filter_complex = ";".join(vf)
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

        # 2) Chat (title + timed lines)
        title, lines = generate_chat()

        # 3) WhatsApp overlays (INNER is rendered as "B")
        wp_msgs: List[WpMsg] = []
        for l in lines:
            who = "A" if l.who == "A" else "B"
            wp_msgs.append(WpMsg(who=who, text=l.text, hhmm=l.hhmm))

        overlay_dir = OUT / "overlays"
        overlays = render_whatsapp_overlays(overlay_dir, wp_msgs, font_path=FONT)

        # Typing total 0.75s => typ1/typ2/typ3 each 0.25s, then full
        times: List[float] = []
        for l in lines:
            t0 = max(0.0, l.t - 0.75)
            times.append(t0)         # typ1
            times.append(t0 + 0.25)  # typ2
            times.append(t0 + 0.50)  # typ3
            times.append(l.t)        # full

        # 4) TTS audio timeline (ONLY voices)
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
