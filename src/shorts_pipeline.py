import os
import random
import re
import subprocess
from pathlib import Path
from datetime import datetime, timezone

import requests
from TTS.api import TTS
from src.youtube_upload import upload_video

OUT = Path("out")
OUT.mkdir(exist_ok=True)

# Sonsuz dönen nesne havuzu (istersen büyütürüz)
OBJECT_POOL = [
    "train ticket","door","mirror","clock","coffee cup","key","book","candle","umbrella","wallet",
    "headphones","notebook","pen","shoe","backpack","water bottle","chair","window","lamp","phone",
    "laptop","staircase","streetlight","map","compass","watch","ring","pillow","blanket","curtain",
    "toothbrush","remote control","spoon","fork","plate","camera","passport","suitcase","receipt","coin"
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

OPENVERSE_SEARCH = "https://api.openverse.engineering/v1/images/"

def run(cmd):
    subprocess.run(cmd, check=True)

def pick_object():
    obj = random.choice(OBJECT_POOL)

    calm_keywords = {"mirror","candle","book","pillow","blanket","window","lamp","curtain"}
    energetic_keywords = {"clock","phone","laptop","alarm","watch","camera","ticket","passport","train"}

    tokens = set(obj.lower().split())
    is_calm = len(tokens & calm_keywords) > 0 and len(tokens & energetic_keywords) == 0

    voice = {
        "speaker": "p225" if is_calm else "p226",
        "speed": 1.12 if is_calm else 1.18
    }
    return obj, voice

def build_script(obj: str) -> str:
    hook = random.choice(HOOKS)
    line1 = f"I’m a {obj}. And I notice patterns."
    line2 = random.choice(BODY_LINES)
    line3 = random.choice(BODY_LINES)
    close = random.choice(CLOSERS)
    loop = "Tomorrow, start smaller—and start again."
    return " ".join([hook, line1, line2, line3, close, loop])

def tts_wav(text: str, wav_path: Path, speaker: str):
    model = "tts_models/en/vctk/vits"
    tts = TTS(model_name=model, gpu=False, progress_bar=False)
    tts.tts_to_file(text=text, file_path=str(wav_path), speaker=speaker)

def duration_seconds(audio_path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True, check=True
    )
    return float(r.stdout.strip())

def write_srt_word_by_word(text: str, total_sec: float, srt_path: Path):
    words = text.split()
    if not words:
        srt_path.write_text("", encoding="utf-8")
        return

    # Daha okunur ve küçük: hızlı ama göz yormayan
    per = max(0.16, min(0.28, total_sec / len(words)))
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
        out.append(str(i))
        out.append(f"{fmt(start)} --> {fmt(end)}")
        out.append(w)
        out.append("")
        t = end
        if t >= total_sec:
            break

    srt_path.write_text("\n".join(out), encoding="utf-8")

def safe_title(text: str) -> str:
    t = text.upper().replace("'", "").replace(":", "")
    t = re.sub(r"\s+", " ", t).strip()
    # Çok uzunsa kırp
    if len(t) > 22:
        t = t[:22].rstrip() + "…"
    return t

def openverse_pick_image(query: str):
    """
    Openverse (CC) üzerinden görsel bulur.
    API key gerekmez.
    """
    params = {
        "q": query,
        "page_size": 20,
        "license_type": "all",
        "size": "large",   # mümkünse büyük
        "mature": "false"
    }
    r = requests.get(OPENVERSE_SEARCH, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    results = data.get("results", [])
    if not results:
        return None

    # Rastgele bir sonuç seç
    item = random.choice(results)

    img_url = item.get("url") or item.get("thumbnail")  # url genelde direct image
    if not img_url:
        return None

    # Attribution bilgileri
    creator = item.get("creator") or ""
    source = item.get("source") or ""
    license_ = item.get("license") or ""
    license_url = item.get("license_url") or ""
    attribution = {
        "creator": creator,
        "source": source,
        "license": license_,
        "license_url": license_url,
        "image_url": img_url
    }
    return attribution

def download_image(url: str, out_path: Path):
    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

def make_vertical_video_with_image(obj: str, img_path: Path, audio_wav: Path, srt_path: Path, out_mp4: Path):
    """
    Dikey 1080x1920:
    - Arkaplan: indirilen görsel
    - Üstte küçük başlık + ortada obje adı (küçük ve ortalı)
    - Altyazı: küçük, alt-orta
    """
    obj_text = safe_title(obj)

    # Yazıları küçülttük ve daha aşağıya aldık (ortalamaya yakın)
    vf = (
        "scale=1080:-1,"
        "crop=1080:1920,"
        "zoompan=z='min(zoom+0.00025,1.08)':d=1,"
        # hafif üst karartma (yazı okunur olsun)
        "drawbox=x=0:y=430:w=iw:h=300:color=black@0.35:t=fill,"
        # küçük header
        "drawtext=text='TALKING OBJECT':fontcolor=white@0.85:fontsize=28:x=(w-text_w)/2:y=460,"
        # obje adı (küçük ve ortalı)
        f"drawtext=text='{obj_text}':fontcolor=white:fontsize=44:x=(w-text_w)/2:y=515,"
        # altyazı küçük ve alt-orta
        f"subtitles={srt_path}:force_style='Fontsize=34,Alignment=2,Outline=2,Shadow=1,MarginV=110'"
    )

    run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(img_path),
        "-i", str(audio_wav),
        "-shortest",
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(out_mp4)
    ])

def make_metadata(obj: str, script: str, attribution: dict | None):
    title = f"{obj.title()} Speaks — 30s Motivation #Shorts"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Kısa açıklama (Shorts)
    desc_lines = [
        f"{obj.title()} speaks.",
        f"UTC: {today}",
        "",
        "#shorts #motivation #mindset #selfimprovement",
    ]

    # Eğer CC görsel kullandıysak attribution ekle (yasal olarak iyi pratik)
    if attribution:
        desc_lines += [
            "",
            "Image credit (Openverse / CC):",
            f"Creator: {attribution.get('creator','')}",
            f"Source: {attribution.get('source','')}",
            f"License: {attribution.get('license','')}",
        ]
        if attribution.get("license_url"):
            desc_lines.append(f"License URL: {attribution['license_url']}")

    tags = ["shorts", "motivation", "mindset", "self improvement", "talking objects", obj.lower()]
    return title, "\n".join(desc_lines), tags

def main():
    obj, voice = pick_object()
    script = build_script(obj)

    wav = OUT / "short_voice.wav"
    srt = OUT / "short.srt"
    mp4 = OUT / "short.mp4"
    img = OUT / "bg.jpg"

    # 1) TTS
    tts_wav(script, wav, speaker=voice["speaker"])
    dur = duration_seconds(wav)

    # 2) subtitles
    write_srt_word_by_word(script, dur, srt)

    # 3) find image (Openverse)
    attribution = openverse_pick_image(obj)
    if attribution:
        try:
            download_image(attribution["image_url"], img)
        except Exception:
            attribution = None

    # Eğer görsel bulunamazsa: gradient arkaplan fallback
    if not img.exists():
        # fallback image: ffmpeg ile tek renk jpg üret
        run(["ffmpeg","-y","-f","lavfi","-i","color=c=#0b1020:s=1080x1920","-frames:v","1",str(img)])

    # 4) video render
    make_vertical_video_with_image(obj, img, wav, srt, mp4)

    # 5) upload
    title, desc, tags = make_metadata(obj, script, attribution)
    upload_video(
        video_file=str(mp4),
        title=title,
        description=desc,
        tags=tags,
        privacy_status=os.getenv("YT_DEFAULT_PRIVACY", "public"),
        category_id="22",
        language="en",
    )

if __name__ == "__main__":
    main()
