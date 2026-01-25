import os
import random
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

from src.youtube_upload import upload_video, verify_auth
from src.pexels_bg import download_bg_from_pexels
from src.shorts_audio import tts_to_wav, build_timeline_audio
from src.wp_overlay import render_whatsapp_overlays, Msg as WpMsg
from src.titles import generate_title

title = generate_title()

OUT = Path("out")
OUT.mkdir(exist_ok=True)

DURATION = int(os.getenv("SHORTS_SECONDS", "35"))
PRIVACY = (os.getenv("YT_DEFAULT_PRIVACY", "public") or "public").strip().lower()
if PRIVACY not in ("public", "unlisted", "private"):
    PRIVACY = "public"

FEMALE_SPK = os.getenv("SHORTS_FEMALE_SPEAKER", "p225")
MALE_SPK = os.getenv("SHORTS_MALE_SPEAKER", "p226")
INNER_SPK = os.getenv("SHORTS_INNER_SPEAKER", "p225")

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def run(cmd: List[str]):
    print(" ".join(cmd), flush=True)
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


# -------- Chat (ASCII only) --------
TOPIC_HOOKS = [
    "I saw something today and I can't say it out loud.",
    "This is the kind of truth people only admit at 2 AM.",
    "Everyone talks about it... but nobody says the real part.",
    "I almost sent this message. Then I froze.",
    "I learned something this week that changed how I see people.",
    "This is embarrassing to admit... but it's honest.",
]

CONFESSIONS = [
    "I keep acting calm, but I'm not okay inside.",
    "I realized the 'nice' version of me is just fear with good manners.",
    "I don't miss them. I miss who I was before them.",
    "I think I'm addicted to uncertainty.",
    "I'm tired of being the strong one.",
]

TWISTS = [
    "What if the silence was the answer?",
    "What if you already outgrew them?",
    "What if you were right the first time?",
    "What if you're not behind... just early?",
    "What if the problem isn't them?",
]

CLIFF = [
    "I can't type the last part here.",
    "If I say it... it changes everything.",
    "Promise you won't ask me who.",
    "I'm deleting this in 10 seconds.",
    "Just... don't look at me the same after this.",
]


def _hhmm(base: datetime, add_min: int) -> str:
    return (base + timedelta(minutes=add_min)).strftime("%-I:%M %p")


@dataclass
class TimedLine:
    who: str
    text: str
    t: float
    hhmm: str


def generate_chat() -> Tuple[str, List[TimedLine]]:
    base = datetime.utcnow()

    two_person = random.random() < 0.7
    hook = random.choice(TOPIC_HOOKS)
    conf = random.choice(CONFESSIONS)
    twist = random.choice(TWISTS)
    cliff = random.choice(CLIFF)

    if two_person:
        title = "I almost sent this..."
        lines = [
            ("A", hook),
            ("B", "Say it."),
            ("A", conf),
            ("B", twist),
            ("A", cliff),
        ]
    else:
        title = "My inner voice said this..."
        lines = [
            ("A", hook),
            ("INNER", "Don't send it."),
            ("A", conf),
            ("INNER", twist),
            ("A", cliff),
        ]

    # timeline (senin ayarın)
    appear = [0.9, 4.2, 7.2, 11.6, 14.9]

    out: List[TimedLine] = []
    for i, ((who, text), t) in enumerate(zip(lines, appear)):
        out.append(TimedLine(who=who, text=text, t=t, hhmm=_hhmm(base, i)))
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
        # ✅ loop background forever, then cut with -t
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

    filter_complex = ";".join(vf)

    audio_idx = len(overlays) + 1

    cmd += [
        "-filter_complex", filter_complex,
        "-map", f"[{cur}]",
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

        # 3) WhatsApp overlays
        wp_msgs = [WpMsg(who=("A" if l.who == "A" else "B"), text=l.text, hhmm=l.hhmm) for l in lines]
        for i in range(len(wp_msgs)):
            if lines[i].who == "INNER":
                wp_msgs[i].who = "B"

        overlay_dir = OUT / "overlays"
        overlays = render_whatsapp_overlays(overlay_dir, wp_msgs, font_path=FONT)

        # Typing total 0.90s => typ1/typ2/typ3 each 0.30s, then full
        times: List[float] = []
        for l in lines:
            t0 = max(0.0, l.t - 0.90)
            times.append(t0)         # typ1
            times.append(t0 + 0.30)  # typ2
            times.append(t0 + 0.60)  # typ3
            times.append(l.t)        # full

        # 4) TTS audio timeline (ONLY voices)
        tts_dir = OUT / "tts"
        tts_dir.mkdir(exist_ok=True)

        wav_items: List[Tuple[float, Path]] = []
        for i, l in enumerate(lines, start=1):
            wav = tts_dir / f"m{i:02d}.wav"
            if l.who == "A":
                spk = FEMALE_SPK
            elif l.who == "B":
                spk = MALE_SPK
            else:
                spk = INNER_SPK

            tts_to_wav(l.text, wav, speaker=spk)

            # ✅ voice almost immediately after message appears
            wav_items.append((l.t + 0.03, wav))

        audio = OUT / "chat_audio.wav"
        build_timeline_audio(wav_items, audio, total_sec=DURATION)

        # 5) Render final mp4
        mp4 = OUT / "short.mp4"
        render_final(bg, overlays, times, audio, mp4, chat_h=860)

        # 6) Upload
        hashtags = "#shorts #texting #chatstory #relatable #psychology"
        description = f"{title}\n\n{hashtags}\n"

        upload_video(
            video_file=str(mp4),
            title=title,
            description=description,
            tags=["shorts", "chat", "texting", "story", "satisfying", "viral", "psychology"],
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
