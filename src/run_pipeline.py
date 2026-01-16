import os
import random
import subprocess
from pathlib import Path
from datetime import datetime, timezone

from TTS.api import TTS
from src.youtube_upload import upload_video
from src.long_story import generate_long_story
from src.long_video import render_long_video
from src.long_audio import build_long_audio_with_ambient

OUT = Path("out")
OUT.mkdir(exist_ok=True)

def run(cmd):
    subprocess.run(cmd, check=True)

def fmt_ts(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def ffprobe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True
    )
    return float(r.stdout.strip())

def tts_to_wav(text: str, wav_path: Path, speaker: str):
    tts = TTS(model_name="tts_models/en/vctk/vits", gpu=False, progress_bar=False)
    tts.tts_to_file(text=text, file_path=str(wav_path), speaker=speaker)

def main():
    # --- SETTINGS ---
    minutes = int(os.getenv("LONG_MINUTES", "60"))   # 45-80 arasında oynatılabilir
    speaker = os.getenv("LONG_SPEAKER", "p225")      # p225 (female-ish), p226 (male-ish)
    privacy = os.getenv("YT_DEFAULT_PRIVACY", "public")

    # --- 1) STORY ---
    story = generate_long_story(target_minutes=minutes)
    # story: dict {title, theme, chapters:[{name, text}], hashtags, tags}

    # --- 2) TTS per chapter (more control + chapter timestamps) ---
    chapter_wavs = []
    timestamps = []
    current_sec = 0

    for idx, ch in enumerate(story["chapters"], start=1):
        wav = OUT / f"chapter_{idx:02d}.wav"
        tts_to_wav(ch["text"], wav, speaker=speaker)

        dur = int(round(ffprobe_duration(wav)))
        timestamps.append((current_sec, ch["name"]))
        current_sec += dur + 4  # +4 sec pause between chapters
        chapter_wavs.append(wav)

    # --- 3) Build final audio (voice concat + ambient mix + pauses) ---
    voice_wav = OUT / "voice_full.wav"
    final_audio = OUT / "audio_full.wav"
    build_long_audio_with_ambient(chapter_wavs, voice_wav, final_audio, pause_sec=4)

    total_dur = int(round(ffprobe_duration(final_audio)))

    # --- 4) Render professional long video (procedural visuals + chapter cards) ---
    mp4 = OUT / "long.mp4"
    render_long_video(
        total_seconds=total_dur,
        title=story["title"],
        chapters=timestamps,
        out_mp4=mp4
    )

    # --- 5) Metadata (title/desc/tags + timestamps) ---
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ts_lines = "\n".join([f"{fmt_ts(sec)} — {name}" for sec, name in timestamps])

    description = (
        f"{story['title']}\n"
        f"Immersive long-form sleep story. ({today} UTC)\n\n"
        f"CHAPTERS:\n{ts_lines}\n\n"
        f"Tip: Lower your screen brightness and breathe slowly.\n\n"
        f"{' '.join(story['hashtags'])}\n"
    )

    upload_video(
        video_file=str(mp4),
        title=story["title"],
        description=description,
        tags=story["tags"],
        privacy_status=privacy,
        category_id="22",
        language="en",
    )

if __name__ == "__main__":
    main()
