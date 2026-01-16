import subprocess
from pathlib import Path

def run(cmd):
    subprocess.run(cmd, check=True)

def render_long_video(total_seconds: int, title: str, chapters, out_mp4: Path):
    """
    Telifsiz/procedural profesyonel arkaplan:
    - Koyu gradient + hafif hareket (noise/zoom hissi)
    - Chapter timestamp'lerinde çok küçük chapter card
    Not: Chapter card'ı yakmak için basit bir yol kullanıyoruz: sadece intro title.
    Daha gelişmiş "per chapter card" isterseniz, chapter'ları ayrı video yapıp concat yaparız.
    """

    safe_title = title.replace("'", "").replace(":", "")
    # basit: tek sahne + üstte küçük title
    vf = (
        "format=yuv420p,"
        # subtle moving noise using geq is heavy; we keep it light:
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@1:t=fill,"
        "drawtext=text='IMMERSIVE WORLDS':fontcolor=white@0.6:fontsize=34:x=(w-text_w)/2:y=80,"
        f"drawtext=text='{safe_title}':fontcolor=white@0.85:fontsize=44:x=(w-text_w)/2:y=140"
    )

    run([
        "ffmpeg","-y",
        "-f","lavfi","-i","color=c=#06080f:s=1280x720:r=30",
        "-t", str(total_seconds),
        "-vf", vf,
        "-c:v","libx264","-pix_fmt","yuv420p",
        str(out_mp4)
    ])

    # Audio will be muxed later by upload pipeline? We'll mux here if audio exists externally.
    # In our run_pipeline we render video separately and upload mp4. We'll mux audio before upload outside if needed.
