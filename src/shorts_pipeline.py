import os, random, subprocess, math
from pathlib import Path
from datetime import datetime, timezone

from TTS.api import TTS
from src.youtube_upload import upload_video

OUT = Path("out"); OUT.mkdir(exist_ok=True)

OBJECTS = [
    ("Mirror", "You keep looking at me… but you rarely *see* yourself."),
    ("Clock", "I don’t steal your time. I just show you where it goes."),
    ("Coffee Cup", "You drink me for energy… but your mind needs rest too."),
    ("Key", "Some doors open when you stop forcing them."),
    ("Book", "I can’t change your life… unless you open me."),
    ("Door", "Not every closed door is a rejection. Sometimes it’s protection."),
    ("Candle", "You don’t need to burn loudly to be seen."),
]

def run(cmd):
    subprocess.run(cmd, check=True)

def pick_short():
    obj, hook = random.choice(OBJECTS)

    # 20–35s motivasyon: 3–5 cümle, loopable kapanış
    lines = [
        hook,
        f"I’m just a {obj.lower()}… but I notice patterns.",
        "Most people rush. You don’t have to.",
        "Take one small step today. Then another.",
        f"And tomorrow… come back and tell me what changed."
    ]
    script = " ".join(lines)

    # basit sınıflandırma: daha yumuşak olanlar kadın, diğerleri erkek
    calm = obj in {"Mirror", "Candle", "Book"}
    voice = {"speaker": ("p225" if calm else "p226"), "speed": (1.14 if calm else 1.18)}
    return obj, script, voice

def tts_wav(text, wav_path, speaker):
    model = "tts_models/en/vctk/vits"
    tts = TTS(model_name=model, gpu=False, progress_bar=False)
    tts.tts_to_file(text=text, file_path=str(wav_path), speaker=speaker)

def get_duration_seconds(audio_path: Path) -> float:
    # ffprobe ile süre al
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True, check=True
    )
    return float(result.stdout.strip())

def write_srt(words, total_sec, srt_path: Path):
    # basit ama etkili: kelime kelime altyazı (Shorts retention için iyi)
    # süreyi kelime sayısına böler, min 0.12s max 0.35s
    n = len(words)
    if n == 0:
        srt_path.write_text("", encoding="utf-8")
        return
    per = max(0.12, min(0.35, total_sec / n))
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

def make_vertical_video(obj_name, audio_wav: Path, srt: Path, mp4: Path):
    # 1080x1920 vertical, hareketli arka plan + büyük nesne adı + altyazı
    # altyazı: libass ile srt yakılır
    bg = f"color=c=black:s=1080x1920:r=30"
    title_text = obj_name.replace(":", "").replace("'", "")

    run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", bg,
        "-i", str(audio_wav),
        "-shortest",
        "-vf",
        # hafif hareket hissi + nesne adı
        "drawtext=text='Talking Object':fontcolor=white:fontsize=54:x=(w-text_w)/2:y=140,"
        f"drawtext=text='{title_text}':fontcolor=white:fontsize=88:x=(w-text_w)/2:y=240,"
        # altyazı yak
        f"subtitles={srt}:force_style='Fontsize=72,Alignment=2,Outline=2,Shadow=1,MarginV=180'",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(mp4)
    ])

def main():
    obj, script, voice = pick_short()

    wav = OUT / "short.wav"
    srt = OUT / "short.srt"
    mp4 = OUT / "short.mp4"

    tts_wav(script, wav, voice["speaker"])
    dur = get_duration_seconds(wav)

    words = script.split()
    write_srt(words, dur, srt)
    make_vertical_video(obj, wav, srt, mp4)

    # SEO / title / hashtags
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title = f"{obj} Speaks — 30s Motivation #Shorts"
    desc = (
        f"{obj} speaks. A short reminder for your day.\n"
        f"Upload date (UTC): {today}\n\n"
        "#shorts #motivation #mindset #selfimprovement"
    )
    tags = ["shorts", "motivation", "mindset", "self improvement", "talking objects", obj.lower()]

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
