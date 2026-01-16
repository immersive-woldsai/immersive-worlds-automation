import os, random, re, subprocess
from pathlib import Path
from datetime import datetime, timezone

import requests
from TTS.api import TTS
from src.youtube_upload import upload_video

OUT = Path("out")
OUT.mkdir(exist_ok=True)

OBJECT_POOL = [
    "train ticket","door","mirror","clock","coffee cup","key","book","candle","umbrella","wallet",
    "headphones","notebook","pen","shoe","backpack","water bottle","chair","window","lamp","phone",
    "laptop","staircase","streetlight","map","compass","watch","ring","pillow","blanket","curtain",
    "toothbrush","remote control","spoon","fork","plate","camera","passport","suitcase","receipt","coin",
    "gloves","scarf","jacket","bus stop","subway","elevator","stairs"
]

HOOKS = [
    "Stop scrolling for 10 seconds.",
    "Quick reminder—listen.",
    "This is your sign to slow down.",
    "Before you give up, hear this.",
]
BODY_LINES = [
    "You don’t need a perfect plan. You need a repeatable step.",
    "Motivation is unreliable. Systems win.",
    "If today feels heavy, make it smaller—one action, one breath, one win.",
    "Consistency isn’t loud. It’s quiet and daily.",
    "You’re allowed to restart. Even if you restarted a hundred times.",
]
CLOSERS = [
    "Do the next right thing—quietly.",
    "Save this and come back tomorrow.",
    "Comment one word: done.",
    "Now go—prove it to yourself.",
]

def run(cmd):
    subprocess.run(cmd, check=True)

def pick_object():
    obj = random.choice(OBJECT_POOL)

    calm_keywords = {"mirror","candle","book","pillow","blanket","window","lamp","curtain"}
    energetic_keywords = {"clock","phone","laptop","alarm","watch","camera","ticket","passport","train","subway"}

    tokens = set(obj.lower().split())
    is_calm = len(tokens & calm_keywords) > 0 and len(tokens & energetic_keywords) == 0

    voice = {"speaker": "p225" if is_calm else "p226"}
    return obj, voice

def build_script(obj: str) -> str:
    # Script is intentionally short: 25–45 sec target
    return " ".join([
        random.choice(HOOKS),
        f"I’m a {obj}. And I notice patterns.",
        random.choice(BODY_LINES),
        random.choice(BODY_LINES),
        random.choice(CLOSERS),
        "Tomorrow, start smaller—and start again."
    ])

def tts_wav(text: str, wav_path: Path, speaker: str):
    tts = TTS(model_name="tts_models/en/vctk/vits", gpu=False, progress_bar=False)
    tts.tts_to_file(text=text, file_path=str(wav_path), speaker=speaker)

def duration_seconds(audio_path: Path) -> float:
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True, check=True
    )
    return float(r.stdout.strip())

def write_srt_word_by_word(text: str, total_sec: float, srt_path: Path):
    words = text.split()
    per = max(0.16, min(0.30, total_sec / max(1, len(words))))
    t = 0.0

    def fmt(ts):
        ms = int((ts - int(ts)) * 1000)
        s = int(ts) % 60
        m = (int(ts) // 60) % 60
        h = int(ts) // 3600
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    out = []
    for i, w in enumerate(words, start=1):
        start = t
        end = min(total_sec, t + per)
        out += [str(i), f"{fmt(start)} --> {fmt(end)}", w, ""]
        t = end
        if t >= total_sec:
            break

    srt_path.write_text("\n".join(out), encoding="utf-8")

def download(url: str, path: Path):
    headers = {"User-Agent": "Mozilla/5.0"}
    with requests.get(url, stream=True, timeout=30, headers=headers, allow_redirects=True) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)

def ensure_bg_image(obj: str, img_path: Path):
    """
    GUARANTEE image:
    - Unsplash Source (no key) -> if fails -> Picsum
    """
    q = obj.replace(" ", ",")
    urls = [
        f"https://source.unsplash.com/1080x1920/?{q}",
        "https://picsum.photos/1080/1920.jpg",
    ]
    last_err = None
    for u in urls:
        try:
            download(u, img_path)
            if img_path.exists() and img_path.stat().st_size > 20_000:
                print(f"[DEBUG] BG OK: {u} size={img_path.stat().st_size}")
                return
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Image download failed. Last error: {last_err}")

def safe_small_label(obj: str) -> str:
    t = obj.upper().replace("'", "").replace(":", "")
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > 18:
        t = t[:18].rstrip() + "…"
    return t

def make_shorts_video_9x16(obj: str, img_path: Path, audio_wav: Path, srt_path: Path, out_mp4: Path):
    """
    ✅ Shorts guarantee:
    - 1080x1920 output
    - <= 60 sec (script already short; we also hard-cap to 58s)
    - Has #shorts in metadata
    Layout:
    - NO big center title
    - small label around lower-middle
    - subtitles tiny bottom-center
    """
    label = safe_small_label(obj)

    vf = (
        # Ensure correct size then crop to EXACT 1080x1920
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        # mild zoom
        "zoompan=z='min(zoom+0.00025,1.06)':d=1,"
        # lower-middle strip
        "drawbox=x=0:y=1120:w=iw:h=90:color=black@0.35:t=fill,"
        # tiny label lower-middle
        f"drawtext=text='TALKING OBJECT · {label}':fontcolor=white@0.9:fontsize=22:"
        "x=(w-text_w)/2:y=1146,"
        # tiny subtitles
        f"subtitles={srt_path}:force_style='Fontsize=28,Alignment=2,Outline=2,Shadow=1,MarginV=85'"
    )

    # Hard cap video duration to 58s just in case (Shorts must be <=60s)
    run([
        "ffmpeg","-y",
        "-loop","1","-i",str(img_path),
        "-i",str(audio_wav),
        "-t","58",
        "-shortest",
        "-vf",vf,
        "-r","30",
        "-c:v","libx264","-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","192k",
        str(out_mp4)
    ])

def make_metadata(obj: str):
    title = f"{obj.title()} Speaks — 30s Motivation #Shorts"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    desc = f"{obj.title()} speaks.\nUTC: {today}\n\n#shorts #motivation #mindset #selfimprovement"
    tags = ["shorts","motivation","mindset","self improvement","talking objects",obj.lower()]
    return title, desc, tags

def main():
    obj, voice = pick_object()
    script = build_script(obj)

    wav = OUT / "short_voice.wav"
    srt = OUT / "short.srt"
    mp4 = OUT / "short.mp4"
    img = OUT / "bg.jpg"

    tts_wav(script, wav, speaker=voice["speaker"])
    dur = duration_seconds(wav)
    print(f"[DEBUG] audio duration: {dur:.2f}s")

    write_srt_word_by_word(script, dur, srt)
    ensure_bg_image(obj, img)

    make_shorts_video_9x16(obj, img, wav, srt, mp4)

    title, desc, tags = make_metadata(obj)
    upload_video(
        video_file=str(mp4),
        title=title,
        description=desc,
        tags=tags,
        privacy_status=os.getenv("YT_DEFAULT_PRIVACY","public"),
        category_id="22",
        language="en",
    )

if __name__ == "__main__":
    main()
