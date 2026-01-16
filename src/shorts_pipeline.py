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

# (İstersen sonra 2000'e çıkarırız; stabilite için şimdilik böyle)
OBJECT_POOL = [
    "headphones","train ticket","door","mirror","clock","coffee cup","key","book","candle","umbrella","wallet",
    "notebook","pen","shoe","backpack","water bottle","chair","window","lamp","phone","laptop",
    "staircase","streetlight","map","compass","watch","ring","pillow","blanket","curtain",
    "toothbrush","remote control","spoon","fork","plate","camera","passport","suitcase","receipt","coin",
    "gloves","scarf","jacket","bus stop","subway","elevator","stairs"
]

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
    subprocess.run(cmd, check=True)

def pick_object():
    obj = random.choice(OBJECT_POOL)

    calm = {"mirror","candle","book","pillow","blanket","window","lamp","curtain"}
    energetic = {"clock","phone","laptop","watch","camera","ticket","passport","train","subway"}

    toks = set(obj.lower().split())
    is_calm = len(toks & calm) > 0 and len(toks & energetic) == 0
    speaker = "p225" if is_calm else "p226"
    return obj, speaker

def build_script(obj: str) -> str:
    # 25–45 saniye hedef: kısa, vurucu
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
    """
    Word-by-word yerine 3 kelimelik chunk:
    - altyazı üstte saçmalamaz
    - daha profesyonel görünür
    """
    words = text.split()
    if not words:
        srt_path.write_text("", encoding="utf-8")
        return

    parts = list(chunks(words, 3))
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
    with requests.get(url, stream=True, timeout=30, headers=headers, allow_redirects=True) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)

def ensure_bg_image(obj: str, img_path: Path):
    """
    RESIM GARANTI:
    1) Unsplash Source (no key) -> related
    2) Picsum fallback -> random
    Resim gelmezse FAIL (siyah video yok!)
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
            if img_path.exists() and img_path.stat().st_size > 30_000:
                print(f"[DEBUG] BG OK: {u} size={img_path.stat().st_size}")
                return
        except Exception as e:
            last_err = e
    raise RuntimeError(f"BG image download failed. Last error: {last_err}")

def safe_label(obj: str) -> str:
    t = obj.upper().replace("'", "").replace(":", "")
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > 20:
        t = t[:20].rstrip() + "…"
    return t

def render_shorts_9x16(obj: str, img_path: Path, wav_path: Path, srt_path: Path, out_mp4: Path):
    """
    Shorts şartları:
    - 9:16 output: 1080x1920
    - <=60s: -t 58
    Layout:
    - Büyük orta başlık YOK
    - Küçük etiket alt-orta
    - Altyazı çok küçük alt-orta
    """
    label = safe_label(obj)

    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "zoompan=z='min(zoom+0.00020,1.05)':d=1,"
        # alt-orta etiket için hafif şerit
        "drawbox=x=0:y=1180:w=iw:h=70:color=black@0.35:t=fill,"
        # ÇOK küçük yazı + alt-ortaya alındı
        f"drawtext=text='TALKING OBJECT · {label}':fontcolor=white@0.9:fontsize=20:"
        "x=(w-text_w)/2:y=1205,"
        # Altyazı küçük ve alt-orta (Alignment=2)
        f"subtitles={srt_path}:force_style='Fontsize=26,Alignment=2,Outline=2,Shadow=1,MarginV=70'"
    )

    run([
        "ffmpeg","-y",
        "-loop","1","-i",str(img_path),
        "-i",str(wav_path),
        "-t","58",
        "-shortest",
        "-vf",vf,
        "-r","30",
        "-c:v","libx264","-pix_fmt","yuv420p",
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
    print(f"[DEBUG] audio duration={dur:.2f}s")
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
