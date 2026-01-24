import os
import json
import random
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

import requests
from TTS.api import TTS

from src.youtube_upload import upload_video, verify_auth

OUT = Path("out")
OUT.mkdir(exist_ok=True)

STATE_FILE = Path("state.json")  # repo root'ta (cache için)
DURATION = int(os.getenv("SHORTS_SECONDS", "35"))
PRIVACY = os.getenv("YT_DEFAULT_PRIVACY", "public")

# Voices (Coqui TTS VCTK)
FEMALE_SPK = os.getenv("SHORTS_FEMALE_SPEAKER", "p225")
MALE_SPK = os.getenv("SHORTS_MALE_SPEAKER", "p226")
INNER_SPK = os.getenv("SHORTS_INNER_SPEAKER", "p225")

PEXELS_API = "https://api.pexels.com/videos/search"

# “çocuksu olmasın” -> adult/clean satisfying b-roll
PEXELS_QUERIES = [
    "precision work hands",
    "craftsmanship close up",
    "macro texture hands",
    "minimal process hands",
    "cinematic b-roll hands",
    "tools close up",
    "calming b-roll process",
    "oddly satisfying close up",
]

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


@dataclass
class Msg:
    who: str      # "A" (female), "B" (male), "INNER"
    text: str
    t: float      # appear time (sec)
    hhmm: str     # shown time


# -----------------------------
# Helpers
# -----------------------------
def run(cmd: List[str]):
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def cleanup_out():
    """Always free disk (after upload or failure)."""
    try:
        for p in OUT.glob("*"):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
    except Exception as e:
        print("[WARN] cleanup failed:", e, flush=True)


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {"n": 0}
    return {"n": 0}


def save_state(s: dict):
    STATE_FILE.write_text(json.dumps(s, indent=2))


def ffprobe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True
    )
    return float(r.stdout.strip())


def ffmpeg_safe_text(s: str) -> str:
    """
    Make text safe for ffmpeg drawtext.
    Covers all common chars that break filter args.
    """
    if not s:
        return ""
    return (
        s.replace("\\", "\\\\")
         .replace("\n", " ")
         .replace("\r", " ")
         .replace(":", "\\:")
         .replace("'", "\\'")
         .replace('"', '\\"')
         .replace("%", "\\%")
         .replace("[", "\\[")
         .replace("]", "\\]")
    )


# -----------------------------
# 1) Download a real background video from Pexels (portrait)
# -----------------------------
def download_bg_from_pexels(out_path: Path) -> Path:
    key = os.environ["PEXELS_API_KEY"]
    headers = {"Authorization": key}

    q = random.choice(PEXELS_QUERIES)
    r = requests.get(
        PEXELS_API,
        headers=headers,
        params={"query": q, "orientation": "portrait", "per_page": 30},
        timeout=30,
    )
    r.raise_for_status()
    videos = r.json().get("videos", [])
    if not videos:
        raise RuntimeError("Pexels returned no videos")

    v = random.choice(videos)
    files = v.get("video_files", [])
    if not files:
        raise RuntimeError("Pexels video has no files")

    # Prefer portrait + smaller size (faster)
    cand = [f for f in files if f.get("width") and f.get("height") and f["height"] > f["width"]]
    if not cand:
        cand = files

    # pick smallest file to keep pipeline fast
    cand.sort(key=lambda x: (x.get("file_size") or 10**18))
    chosen = cand[0]
    url = chosen["link"]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[BG] Pexels query='{q}' -> {out_path}", flush=True)

    with requests.get(url, stream=True, timeout=120) as rr:
        rr.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in rr.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)

    if not out_path.exists() or out_path.stat().st_size < 300_000:
        raise RuntimeError("Downloaded bg video too small/invalid")

    return out_path


# -----------------------------
# 2) Chat generator (mixed: A/B or A/INNER)
# -----------------------------
TOPIC_HOOKS = [
    "I saw something today and I can't say it out loud.",
    "This is the kind of truth people only admit at 2 AM.",
    "Everyone talks about it… but nobody says the real part.",
    "I almost sent this message. Then I froze.",
    "I learned something this week that changed how I see people.",
    "This is embarrassing to admit… but it’s honest.",
]

CONFESSIONS = [
    "I keep acting calm, but I'm not okay inside.",
    "I realized the ‘nice’ version of me is just fear with good manners.",
    "I don't miss them. I miss who I was before them.",
    "I think I’m addicted to uncertainty.",
    "I’m tired of being the strong one.",
]

TWISTS = [
    "What if the silence was the answer?",
    "What if you already outgrew them?",
    "What if you were right the first time?",
    "What if you’re not behind… just early?",
    "What if the problem isn’t them?",
]

CLIFF = [
    "I can’t type the last part here.",
    "If I say it… it changes everything.",
    "Promise you won’t ask me who.",
    "I’m deleting this in 10 seconds.",
    "Just… don’t look at me the same after this.",
]


def _hhmm(base: datetime, add_min: int) -> str:
    # %-I Linux/mac OK; if it ever fails on runner, replace with %I and strip leading 0
    return (base + timedelta(minutes=add_min)).strftime("%-I:%M %p")


def generate_chat(duration_sec: int = 35) -> Tuple[str, List[Msg]]:
    base = datetime.utcnow()
    two_person = random.random() < 0.7  # mixed style
    hook = random.choice(TOPIC_HOOKS)
    conf = random.choice(CONFESSIONS)
    twist = random.choice(TWISTS)
    cliff = random.choice(CLIFF)

    if two_person:
        title = "I almost sent this…"
        lines = [
            ("A", hook),
            ("B", "Say it."),
            ("A", conf),
            ("B", twist),
            ("A", cliff),
        ]
    else:
        title = "My inner voice said this…"
        lines = [
            ("A", hook),
            ("INNER", "Don’t send it."),
            ("A", conf),
            ("INNER", twist),
            ("A", cliff),
        ]

    appear = [2.0, 7.0, 14.0, 22.0, 29.0]

    msgs: List[Msg] = []
    for i, ((who, text), t) in enumerate(zip(lines, appear)):
        msgs.append(Msg(who=who, text=text, t=t, hhmm=_hhmm(base, i)))
    return title, msgs


# -----------------------------
# 3) TTS + build audio
# -----------------------------
def tts_to_wav(text: str, out_wav: Path, speaker: str):
    tts = TTS(model_name="tts_models/en/vctk/vits", gpu=False, progress_bar=False)
    tts.tts_to_file(text=text, file_path=str(out_wav), speaker=speaker)


def build_chat_audio(msgs: List[Msg], out_wav: Path, gap_sec: float = 0.25) -> Path:
    tmp_dir = OUT / "tts"
    tmp_dir.mkdir(exist_ok=True)

    wavs = []
    for i, m in enumerate(msgs, start=1):
        wav = tmp_dir / f"m{i:02d}.wav"
        if m.who == "A":
            spk = FEMALE_SPK
        elif m.who == "B":
            spk = MALE_SPK
        else:
            spk = INNER_SPK
        tts_to_wav(m.text, wav, speaker=spk)
        wavs.append(wav)

    silence = tmp_dir / "silence.wav"
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
        "-t", str(gap_sec), str(silence)
    ])

    inputs = []
    for w in wavs:
        inputs += ["-i", str(w), "-i", str(silence)]

    n = len(inputs) // 2
    filter_in = "".join([f"[{i}:a]" for i in range(n)])
    filter_complex = f"{filter_in}concat=n={n}:v=0:a=1[a]"

    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[a]",
        str(out_wav)
    ])
    return out_wav


# -----------------------------
# 4) Render WhatsApp-like overlay (drawtext boxes) + mux audio
# -----------------------------
def build_filtergraph(msgs: List[Msg]) -> str:
    chat_h = 980
    filters = [f"drawbox=x=0:y=0:w=iw:h={chat_h}:color=black@0.30:t=fill"]

    filters.append(
        f"drawtext=fontfile='{FONT}':text='{ffmpeg_safe_text('WhatsApp')}':x=60:y=25:fontsize=34:fontcolor=white@0.92"
    )

    y0 = 140
    dy = 165
    left_x = 70
    right_x = 520

    for i, m in enumerate(msgs):
        y = y0 + i * dy
        start = m.t
        end = float(DURATION)

        if m.who == "A":
            x = left_x
            boxcolor = "white@0.92"
            fontcolor = "black@0.92"
            timecolor = "black@0.55"
            tick = False
        else:
            x = right_x
            boxcolor = "green@0.30"
            fontcolor = "white@0.95"
            timecolor = "white@0.65"
            tick = True

        # ✅ SAFE TEXT HERE
        safe_msg = ffmpeg_safe_text(m.text)
        safe_time = ffmpeg_safe_text(m.hhmm)

        filters.append(
            "drawtext="
            f"fontfile='{FONT}':"
            f"text='{safe_msg}':"
            f"x={x}:y={y}:"
            "fontsize=38:"
            f"fontcolor={fontcolor}:"
            "box=1:"
            f"boxcolor={boxcolor}:"
            "boxborderw=22:"
            f"enable='between(t,{start},{end})'"
        )

        filters.append(
            "drawtext="
            f"fontfile='{FONT}':"
            f"text='{safe_time}':"
            f"x={x+10}:y={y+92}:"
            "fontsize=24:"
            f"fontcolor={timecolor}:"
            f"enable='between(t,{start},{end})'"
        )

        if tick:
            filters.append(
                "drawtext="
                f"fontfile='{FONT}':"
                f"text='{ffmpeg_safe_text('✓✓')}':"
                f"x={x+280}:y={y+92}:"
                "fontsize=26:"
                "fontcolor=white@0.75:"
                f"enable='between(t,{start},{end})'"
            )

    return ",".join(filters)


def render_short(bg_video: Path, audio_wav: Path, out_mp4: Path, msgs: List[Msg]) -> Path:
    vf = build_filtergraph(msgs)

    extra_vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "eq=contrast=1.03:saturation=1.05,"
        f"{vf}"
    )

    run([
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "error",
        "-stream_loop", "0", "-i", str(bg_video),
        "-i", str(audio_wav),
        "-t", str(DURATION),
        "-vf", extra_vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "160k",
        "-shortest",
        "-movflags", "+faststart",
        str(out_mp4)
    ])
    return out_mp4


# -----------------------------
# MAIN
# -----------------------------
def main():
    try:
        verify_auth()

        bg = OUT / "bg.mp4"
        download_bg_from_pexels(bg)

        title, msgs = generate_chat(DURATION)

        audio = OUT / "audio.wav"
        build_chat_audio(msgs, audio, gap_sec=0.25)

        mp4 = OUT / "short.mp4"
        render_short(bg, audio, mp4, msgs)

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
