import os
import subprocess
from pathlib import Path
from youtube_upload import upload_video

OUT_DIR = Path("out")
OUT_DIR.mkdir(exist_ok=True)

def run(cmd: list[str]) -> None:
    print("RUN:", " ".join(cmd))
    subprocess.run(cmd, check=True)

def make_test_video(output_path: Path) -> None:
    run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=10",
        "-vf", "drawtext=text='Immersive Worlds Test Upload':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(output_path)
    ])

def main():
    video_path = OUT_DIR / "test.mp4"
    make_test_video(video_path)

    title = "Immersive Worlds — Test Upload (Automation)"
    description = "Automated test upload from GitHub Actions."
    tags = ["immersive worlds", "test upload", "automation"]

    privacy = os.getenv("YT_DEFAULT_PRIVACY", "unlisted").lower()
    if privacy not in {"public", "unlisted", "private"}:
        privacy = "unlisted"

    upload_video(
        video_file=str(video_path),
        title=title,
        description=description,
        tags=tags,
        privacy_status=privacy,
        category_id="22",
        language="en"
    )

if __name__ == "__main__":
    main()
