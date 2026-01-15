import os
import subprocess
from pathlib import Path

from TTS.api import TTS
from src.youtube_upload import upload_video

OUT_DIR = Path("out")
OUT_DIR.mkdir(exist_ok=True)

def run(cmd: list[str]) -> None:
    print("RUN:", " ".join(cmd))
    subprocess.run(cmd, check=True)

def build_test_story_text(target_words: int = 1400) -> str:
    # 10 dakika civarı için ~1300–1600 kelime yeterli (konuşma hızına göre değişir)
    base = (
        "Welcome. Tonight, you will travel through a quiet, drifting city of light. "
        "There are no alarms here. No urgency. Only slow streets, soft air, and distant stars. "
        "With every sentence, your shoulders grow heavier, and your breathing becomes calmer. "
        "You walk beneath tall buildings that glow like lanterns, hearing only gentle wind. "
        "You are safe, and you do not need to do anything at all.\n\n"
    )
    words = []
    while len(words) < target_words:
        words.extend(base.split())
    text = " ".join(words[:target_words])
    # küçük “chapter” dokunuşu
    return (
        "Immersive Worlds — Sleep Story (Test)\n\n"
        + text
        + "\n\nNow the city fades into a soft horizon. You can rest."
    )

def make_tts_audio(text: str, wav_path: Path) -> None:
    # Daha iyi kalite için VITS tabanlı model (CPU’da çalışır, ilk indirme uzun sürebilir)
    model_name = "tts_models/en/vctk/vits"
    tts = TTS(model_name=model_name, progress_bar=False, gpu=False)

    # Bu model çoklu speaker destekler; sabit bir speaker seçiyoruz
    speaker = "p225"
    tts.tts_to_file(text=text, file_path=str(wav_path), speaker=speaker)

def make_video(audio_wav: Path, output_mp4: Path) -> None:
    # Basit ama düzgün: siyah arkaplan + metin + audio
    # 1280x720, 30fps
    run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=30",
        "-i", str(audio_wav),
        "-shortest",
        "-vf", "drawtext=text='Immersive Worlds (Test)':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(output_mp4)
    ])

def main():
    story = build_test_story_text(target_words=1400)

    wav_path = OUT_DIR / "test.wav"
    mp4_path = OUT_DIR / "test.mp4"

    print("Generating TTS audio...")
    make_tts_audio(story, wav_path)

    print("Building video...")
    make_video(wav_path, mp4_path)

    title = "Immersive Worlds — Sleep Story (10 Min Test Upload)"
    description = (
        "Automated test upload from GitHub Actions.\n\n"
        "If you can see this video, the pipeline works end-to-end:\n"
        "Text → Coqui TTS → FFmpeg → YouTube Upload.\n"
    )
    tags = [
        "sleep story",
        "immersive worlds",
        "relaxing story",
        "bedtime story",
        "ambient",
        "calm narration",
        "test upload"
    ]

    privacy = os.getenv("YT_DEFAULT_PRIVACY", "unlisted").lower()
    if privacy not in {"public", "unlisted", "private"}:
        privacy = "unlisted"

    print("Uploading to YouTube...")
    upload_video(
        video_file=str(mp4_path),
        title=title,
        description=description,
        tags=tags,
        privacy_status=privacy,
        category_id="22",
        language="en",
    )

    print("Done.")

if __name__ == "__main__":
    main()
