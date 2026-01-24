import subprocess
from pathlib import Path

BG_DIR = Path("assets/bg")
BG_DIR.mkdir(parents=True, exist_ok=True)

W, H, FPS, DUR = 1080, 1920, 30, 45  # 45 sn üret; shortta 35 sn keseriz

def run(cmd):
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

def make_one(i: int):
    out = BG_DIR / f"bg_{i:02d}.mp4"
    seed = 1000 + i * 97

    # İnternetsiz "satisfying / slime-like" abstract: gradient + noise + blur + hue drift
    filt = (
        f"gradients=size={W}x{H}:rate={FPS}:type=radial,"
        f"noise=alls=28:allf=t+u:all_seed={seed},"
        f"gblur=sigma=22:steps=2,"
        f"hue=h='3*t':s=1.4,"
        f"eq=contrast=1.10:saturation=1.40:brightness=0.02,"
        f"vignette=PI/4,"
        f"format=yuv420p"
    )

    run([
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", filt,
        "-t", str(DUR),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(out),
    ])

def main():
    for i in range(1, 16):
        make_one(i)
    print("[OK] Generated 15 backgrounds in assets/bg/", flush=True)

if __name__ == "__main__":
    main()

