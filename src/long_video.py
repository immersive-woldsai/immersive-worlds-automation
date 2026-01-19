import subprocess
from pathlib import Path

def run(cmd):
    print("\n[CMD]", " ".join(map(str, cmd)), flush=True)
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.stdout:
        print("[STDOUT]\n", p.stdout[-4000:], flush=True)
    if p.stderr:
        print("[STDERR]\n", p.stderr[-4000:], flush=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {p.returncode}")

def _escape_drawtext(s: str) -> str:
    # ffmpeg drawtext escaping (basic)
    return (
        s.replace("\\", "\\\\")
         .replace(":", "\\:")
         .replace("'", "")
         .replace('"', "")
    )

def render_long_video(
    total_seconds: int,
    title: str,
    chapters,
    bg_img: Path,        # required
    audio_wav: Path,     # required
    out_mp4: Path
):
    """
    Long video render:
    - background image + slow Ken Burns zoom
    - soft dark overlay
    - small title text
    - audio muxed in same command (final mp4 ready)
    """
    safe_title = _escape_drawtext(title)

    vf = (
        "scale=1280:720:force_original_aspect_ratio=increase,"
        "crop=1280:720,"
        "setsar=1,"
        # slow zoom/pan
        "zoompan=z='min(zoom+0.00008,1.12)':"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        "d=1:s=1280x720:fps=30,"
        "gblur=sigma=2,"
        "format=yuv420p,"
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.22:t=fill,"
        "drawtext=text='IMMERSIVE WORLDS':fontcolor=white@0.70:fontsize=34:x=(w-text_w)/2:y=70,"
        f"drawtext=text='{safe_title}':fontcolor=white@0.90:fontsize=44:x=(w-text_w)/2:y=130"
    )

    run([
        "ffmpeg","-y",
        "-loop","1","-i", str(bg_img),
        "-i", str(audio_wav),
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
