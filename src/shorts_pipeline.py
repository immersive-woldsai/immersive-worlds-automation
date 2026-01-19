import os
import random
import re
import subprocess
from pathlib import Path
from datetime import datetime, timezone
import time
from PIL import Image, ImageDraw, ImageFont

import requests
from TTS.api import TTS
from src.youtube_upload import upload_video

print("SHORTS_PIPELINE_VERSION = 2026-01-16-FIX-1", flush=True)

OUT = Path("out")
OUT.mkdir(exist_ok=True)

OBJECT_POOL = [
    "headphones","train ticket","door","mirror","clock","coffee cup","key","book","candle","umbrella","wallet",
    "notebook","pen","shoe","backpack","water bottle","chair","window","lamp","phone","laptop",
    "staircase","streetlight","map","compass","watch","ring","pillow","blanket","curtain",
    "toothbrush","remote control","spoon","fork","plate","camera","passport","suitcase","receipt","coin",
    "gloves","scarf","jacket","bus stop","subway","elevator","stairs"
]
QUERY_MAP = {
    "train ticket": ["train station", "train travel", "railway", "commuter train"],
    "door": ["doorway", "hallway door", "wooden door", "home entrance"],
    "mirror": ["mirror reflection", "reflection", "mirror room"],
    "clock": ["clock", "watch", "timepiece", "alarm clock"],
    "coffee cup": ["coffee mug", "coffee cup", "cafe coffee", "coffee table"],
    "key": ["house key", "door key", "key in hand"],
    "book": ["book reading", "open book", "library books"],
    "candle": ["candle flame", "candle light", "soft candle"],
    "umbrella": ["umbrella rain", "rain street umbrella"],
    "wallet": ["wallet", "money wallet", "card wallet"],
    "headphones": ["headphones", "music headphones", "headphones on desk"],
    "notebook": ["notebook writing", "journal", "paper notebook"],
    "pen": ["pen writing", "fountain pen", "pen on paper"],
    "shoe": ["shoe", "sneakers", "running shoes"],
    "backpack": ["backpack", "travel backpack", "school backpack"],
    "window": ["window night", "window rain", "window light"],
    "lamp": ["desk lamp", "lamp light", "bedside lamp"],
    "phone": ["smartphone", "phone screen", "phone in hand"],
    "laptop": ["laptop", "laptop desk", "computer laptop"],
    "subway": ["subway station", "metro train", "underground station"],
    "bus stop": ["bus stop", "street bus stop", "public transport stop"],
    "stairs": ["stairs", "staircase", "stairway"],
    "elevator": ["elevator", "elevator doors", "building elevator"],
}


HOOKS = [
    "Stop scrolling for 10 seconds.",
    "Quick reminder—listen.",
    "This is your sign to slow down.",
    "Before you give up, hear this.",
]
BODY = [
    "You don’t need a perfect plan. You need a repeatable step.",
    "Motivation is unreliable. Systems win.",
    "If today feels heavy, make it smaller—one action, one breath, one win.",
    "Consistency isn’t loud. It’s quiet and daily.",
    "You’re allowed to restart. Even if you restarted a hundred times.",
]
CLOSE = [
    "Do the next right thing—quietly.",
    "Save this and come back tomorrow.",
    "Comment one word: done.",
    "Now go—prove it to yourself.",
]

def run(cmd):
    # full debug
    print("\n[CMD]", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.stdout:
        print("[STDOUT]\n", p.stdout[-4000:], flush=True)
    if p.stderr:
        print("[STDERR]\n", p.stderr[-4000:], flush=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {p.returncode}")

def pick_object():
    obj = random.choice(OBJECT_POOL)

    calm = {"mirror","candle","book","pillow","blanket","window","lamp","curtain"}
    energetic = {"clock","phone","laptop","watch","camera","ticket","passport","train","subway"}

    toks = set(obj.lower().split())
    is_calm = len(toks & calm) > 0 and len(toks & energetic) == 0
    speaker = "p225" if is_calm else "p226"
    return obj, speaker

def build_script(obj: str) -> str:
    return " ".join([
        random.choice(HOOKS),
        f"I’m a {obj}. And I notice patterns.",
        random.choice(BODY),
        random.choice(BODY),
        random.choice(CLOSE),
        "Tomorrow, start smaller—and start again."
    ])

def tts_to_wav(text: str, wav_path: Path, speaker: str):
    tts = TTS(model_name="tts_models/en/vctk/vits", gpu=False, progress_bar=False)
    tts.tts_to_file(text=text, file_path=str(wav_path), speaker=speaker)

def ffprobe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True
    )
    return float(r.stdout.strip())

def chunks(words, n):
    for i in range(0, len(words), n):
        yield words[i:i+n]

def write_srt_chunked(text: str, total_sec: float, srt_path: Path):
    words = text.split()
    parts = list(chunks(words, 3))
    if not parts:
        srt_path.write_text("", encoding="utf-8")
        return

    per = max(0.45, min(1.2, total_sec / max(1, len(parts))))

    def fmt(ts):
        ms = int((ts - int(ts)) * 1000)
        s = int(ts) % 60
        m = (int(ts) // 60) % 60
        h = int(ts) // 3600
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    t = 0.0
    out = []
    for idx, part in enumerate(parts, start=1):
        start = t
        end = min(total_sec, t + per)
        out += [str(idx), f"{fmt(start)} --> {fmt(end)}", " ".join(part), ""]
        t = end
        if t >= total_sec:
            break

    srt_path.write_text("\n".join(out), encoding="utf-8")

def download(url: str, path: Path):
    headers = {"User-Agent": "Mozilla/5.0"}
    with requests.get(url, stream=True, timeout=35, headers=headers, allow_redirects=True) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)


def _make_fallback_image(obj: str, img_path: Path):
    """
    İnternet yoksa / provider patlarsa bile 1080x1920 görsel üretir.
    Böylece pipeline asla fail olmaz.
    """
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), (6, 8, 15))
    draw = ImageDraw.Draw(img)

    # Basit gradient
    for y in range(H):
        v = int(10 + (y / H) * 30)
        draw.line([(0, y), (W, y)], fill=(v, v, v))

    # Yazılar
    title = f"{obj}".upper()
    subtitle = "TALKING OBJECT"

    # Font: PIL default (her ortamda garanti)
    font_big = ImageFont.load_default()
    font_small = ImageFont.load_default()

    # Orta-alt yerleşim (senin istediğin gibi)
    # Büyük obj ismi daha küçük olsun:
    # (default font küçük kalır; ama en azından taşma yapmaz)
    tw = draw.textlength(title, font=font_big)
    sw = draw.textlength(subtitle, font=font_small)

    y_sub = int(H * 0.68)
    y_title = int(H * 0.73)

    draw.text(((W - sw) / 2, y_sub), subtitle, fill=(220, 220, 220), font=font_small)
    draw.text(((W - tw) / 2, y_title), title, fill=(255, 255, 255), font=font_big)

    img.save(img_path, quality=92)
    print(f"[DEBUG] Fallback image generated: {img_path}", flush=True)


def ensure_bg_image(obj: str, img_path: Path):
    """
    Önce ilgili görseli indir (Unsplash source).
    503/timeout vs olursa retry eder.
    Hala olmazsa fallback görsel üretir -> pipeline PATLAMAZ.
    """
    obj_key = obj.lower().strip()
    queries = QUERY_MAP.get(obj_key, [])

    if not queries:
        queries = [
            obj_key,
            f"{obj_key} close up",
            f"{obj_key} in hand",
            f"{obj_key} on table",
            f"{obj_key} minimal",
        ]

    headers = {"User-Agent": "Mozilla/5.0"}

    def try_download(url: str) -> bool:
        try:
            with requests.get(url, stream=True, timeout=35, headers=headers, allow_redirects=True) as r:
                if r.status_code >= 500:
                    return False
                r.raise_for_status()
                with open(img_path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        if chunk:
                            f.write(chunk)
            return img_path.exists() and img_path.stat().st_size > 40_000
        except Exception:
            return False

    # Retry/backoff: toplam 3 tur
    for attempt in range(1, 4):
        for q in queries[:6]:
            q2 = q.replace(" ", ",")
            url = f"https://source.unsplash.com/1080x1920/?{q2}"

            ok = try_download(url)
            if ok:
                print(f"[DEBUG] BG OK (unsplash): {q} | size={img_path.stat().st_size}", flush=True)
                return

        sleep_s = 2 ** attempt  # 2,4,8
        print(f"[WARN] Unsplash failed (attempt {attempt}/3). Sleeping {sleep_s}s...", flush=True)
        time.sleep(sleep_s)

    # Buraya geldiysek: internet/provider sorunlu -> fallback üret
    print("[WARN] No image downloaded. Using generated fallback background.", flush=True)
    _make_fallback_image(obj, img_path)


def safe_label(obj: str) -> str:
    t = obj.upper().replace("'", "").replace(":", "")
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > 20:
        t = t[:20].rstrip() + "…"
    return t
  
def render_shorts_9x16(obj: str, img_path: Path, wav_path: Path, srt_path: Path, out_mp4: Path):
    label = safe_label(obj)

    # IMPORTANT:
    # - remove zoompan (sometimes breaks short classification)
    # - enforce exact 1080x1920 output using scale+crop only
    # - set SAR to 1:1
    # - force yuv420p

    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "setsar=1,"
        "format=yuv420p,"
        "drawbox=x=0:y=1180:w=iw:h=70:color=black@0.35:t=fill,"
        f"drawtext=text='TALKING OBJECT · {label}':fontcolor=white@0.9:fontsize=18:"
        "x=(w-text_w)/2:y=1208,"
        f"subtitles={srt_path}:force_style='Fontsize=24,Alignment=2,Outline=2,Shadow=1,MarginV=65'"
    )

    run([
        "ffmpeg","-y",
        "-loop","1","-i",str(img_path),
        "-i",str(wav_path),
        "-t","58",
        "-shortest",
        "-vf",vf,
        "-r","30",
        "-c:v","libx264",
        "-profile:v","high",
        "-level","4.1",
        "-pix_fmt","yuv420p",
        "-movflags","+faststart",
        "-c:a","aac","-b:a","160k",
        str(out_mp4)
    ])


def make_metadata(obj: str):
    title = f"{obj.title()} Speaks — Motivation #Shorts"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    desc = f"{obj.title()} speaks.\nUTC: {today}\n\n#shorts #motivation #mindset #selfimprovement"
    tags = ["shorts","motivation","mindset","self improvement","talking objects",obj.lower()]
    return title, desc, tags

def main():
    obj, speaker = pick_object()
    script = build_script(obj)

    wav = OUT / "short.wav"
    srt = OUT / "short.srt"
    img = OUT / "bg.jpg"
    mp4 = OUT / "short.mp4"

    tts_to_wav(script, wav, speaker=speaker)
    dur = ffprobe_duration(wav)
    print(f"[DEBUG] audio duration={dur:.2f}s", flush=True)

    write_srt_chunked(script, min(dur, 58.0), srt)
    ensure_bg_image(obj, img)
    render_shorts_9x16(obj, img, wav, srt, mp4)

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
