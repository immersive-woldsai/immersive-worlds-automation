import os
import random
import subprocess
from pathlib import Path
from datetime import datetime, timezone

from TTS.api import TTS
from src.youtube_upload import upload_video

OUT = Path("out")
OUT.mkdir(exist_ok=True)

# 200 dosya vs yok. Sonsuz: object card uretip her gun yeni "nesne" seciyoruz.
OBJECT_POOL = [
    "door","mirror","clock","coffee cup","key","book","candle","umbrella","wallet","headphones",
    "notebook","pen","shoe","backpack","bottle","chair","window","lamp","phone","laptop",
    "train ticket","elevator button","staircase","streetlight","map","compass","watch","ring",
    "pillow","blanket","curtain","toothbrush","remote control","kitchen spoon","fork","plate",
    "camera","tripod","guitar","piano key","paintbrush","passport","suitcase","receipt","coin",
    "bridge","bench","raincoat","helmet","gloves","calendar","sticky note","alarm","thermostat",
]

# kısa, vurucu motivational script template
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
    # Voice choice: calm objects -> female, energetic/tech -> male
    calm_keywords = {"mirror","candle","book","pillow","blanket","window","lamp","curtain"}
    energetic_keywords = {"clock","phone","laptop","alarm","watch","camera","ticket","passport"}

    tokens = set(obj.lower().split())
    is_calm = len(tokens & calm_keywords) > 0 and len(tokens & energetic_keywords) == 0

    voice = {
        "speaker": "p225" if is_calm else "p226",
        "speed": 1.12 if is_calm else 1.18
    }
    return obj, voice

def build_script(obj: str) -> str:
    # 20-35s hedef
    hook = random.choice(HOOKS)
    line1 = f"I’m a {obj}. And I notice patterns."
    line2 = random.choice(BODY_LINES)
    line3 = random.choice(BODY_LINES)
    close = random.choice(CLOSERS)

    # Loop-friendly ending
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

    # Daha okunur: biraz daha yavas altyazi ama hizli hissettirir
    per = max(0.14, min(0.26, total_sec / len(words)))
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

def make_object_card_video(obj: str, audio_wav: Path, srt_path: Path, out_mp4: Path):
    # Dikey 1080x1920
    # Metin boyutu küçültüldü ve ortalandı.
    # Üst bant yok: daha ortalı, daha temiz.
    obj_text = obj.upper().replace("'", "").replace(":", "")
    # çok uzun ise kırp
    if len(obj_text) > 18:
        obj_text = obj_text[:18] + "…"

    # Arkaplan: koyu gradient + hafif noise hissi (basit)
    # drawtext: ortada (y=720 civarı), subtitle alt-orta (MarginV küçük)
    vf = (
        "format=yuv420p,"
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@1:t=fill,"
        # header küçük ve ortalı (çok yukarıda değil)
        "drawtext=text='TALKING OBJECT':fontcolor=white@0.85:fontsize=42:x=(w-text_w)/2:y=520,"
        # object adı büyük ama ekrana sığacak şekilde
        f"drawtext=text='{obj_text}':fontcolor=white:fontsize=78:x=(w-text_w)/2:y=620,"
        # altyazı: daha küçük, alt-orta
        f"subtitles={srt_path}:force_style='Fontsize=46,Alignment=2,Outline=2,Shadow=1,MarginV=140'"
    )

    run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=#090a0f:s=1080x1920:r=30",
        "-i", str(audio_wav),
        "-shortest",
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(out_mp4)
    ])

def make_metadata(obj: str, script: str):
    title = f"{obj.title()} Speaks — 30s Motivation #Shorts"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    desc = (
        f"{obj.title()} speaks.\n"
        f"UTC: {today}\n\n"
        f"{script}\n\n"
        "#shorts #motivation #mindset #selfimprovement"
    )
    tags = ["shorts", "motivation", "mindset", "self improvement", "talking objects", obj.lower()]
    return title, desc, tags

def main():
    obj, voice = pick_object()
    script = build_script(obj)

    wav = OUT / "short_voice.wav"
    srt = OUT / "short.srt"
    mp4 = OUT / "short.mp4"

    tts_wav(script, wav, speaker=voice["speaker"])
    dur = duration_seconds(wav)
    write_srt_word_by_word(script, dur, srt)

    make_object_card_video(obj, wav, srt, mp4)

    title, desc, tags = make_metadata(obj, script)

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
