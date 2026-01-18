import subprocess
from pathlib import Path

def run(cmd):
    print("\n[CMD]", " ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, check=True)

def render_long_video(
    total_seconds: int,
    title: str,
    chapters,
    bg_img: Path,        # <-- NEW: background image path (jpg/png)
    audio_wav: Path,     # <-- NEW: final audio wav path
    out_mp4: Path
):
    """
    Profesyonel long video:
    - Background image + Ken Burns (slow zoom/pan)
    - Soft dark overlay for readability
    - Title small on top
    - Audio mux inside this function (final mp4 ready for upload)
    """

    safe_title = title.replace("'", "").replace('"', "").replace(":", "")

    # Ken Burns: very slow zoom to avoid "static" look
    vf = (
        "scale=1280:720:force_original_aspect_ratio=increase,"
        "crop=1280:720,"
        "setsar=1,"
        # Slow zoom/pan. fps=30, d=1 because we already output per-frame.
        "zoompan=z='min(zoom+0.00008,1.12)':"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        "d=1:s=1280x720:fps=30,"
        "gblur=sigma=2,"
        "format=yuv420p,"
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.22:t=fill,"
        "drawtext=text='IMMERSIVE WORLDS':fontcolor=white@0.70:fontsize=34:x=(w-text_w)/2:y=70,"
        f"drawtext=text='{safe_title}':fontcolor=white@0.90:fontsize=44:x=(w-text_w)/2:y=130"
    )

    # Build final mp4 with audio muxed in one command (stable)
    run([
        "ffmpeg","-y",
        "-loop","1","-i", str(bg_img),     # <-- use real image
        "-i", str(audio_wav),              # <-- mux audio here
        "-t", str(total_seconds),
        "-vf", vf,
        "-r","30",
        "-c:v","libx264",
        "-profile:v","high",
        "-level","4.1",
        "-pix_fmt","yuv420p",
        "-movflags","+faststart",
        "-c:a","aac","-b:a","192k",
        "-shortest",
        str(out_mp4)
    ])
