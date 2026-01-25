import os
import random
from pathlib import Path
import requests
import subprocess

PEXELS_API = "https://api.pexels.com/videos/search"

PEXELS_QUERIES = [
    "oddly satisfying close up",
    "soap cutting asmr",
    "kinetic sand close up",
    "slime satisfying macro",
    "metal polishing macro",
    "woodworking close up",
    "paint mixing macro",
    "ink in water macro",
    "resin art close up",
]

def ffprobe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True
    )
    return float(r.stdout.strip())

def _download(url: str, out_path: Path, timeout: int = 180) -> None:
    if out_path.exists():
        out_path.unlink()

    with requests.get(url, stream=True, timeout=timeout) as rr:
        rr.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in rr.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)

def download_bg_from_pexels(out_path: Path) -> Path:
    """
    Robust downloader:
    - Accepts >= 6s clips (we will loop to 35s anyway)
    - Accepts small files too (>= 700KB)
    - If Pexels fails completely, uses local fallback if exists.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # fallback (optional)
    fallback = Path("assets/fallback_bg.mp4")

    key = os.environ["PEXELS_API_KEY"]
    headers = {"Authorization": key}

    min_dur = int(os.getenv("PEXELS_MIN_DUR", "6"))              # seconds
    min_bytes = int(os.getenv("PEXELS_MIN_BYTES", "700000"))     # ~0.7MB

    for attempt in range(1, 10):
        q = random.choice(PEXELS_QUERIES)
        print(f"[BG] Search attempt {attempt} query='{q}'", flush=True)

        r = requests.get(
            PEXELS_API,
            headers=headers,
            params={"query": q, "orientation": "portrait", "per_page": 40},
            timeout=30,
        )
        r.raise_for_status()
        videos = r.json().get("videos", [])
        if not videos:
            continue

        random.shuffle(videos)

        for v in videos[:12]:
            files = v.get("video_files", [])
            if not files:
                continue

            # Prefer portrait and decent height, but don't be too strict
            cand = []
            for f in files:
                w = f.get("width") or 0
                h = f.get("height") or 0
                link = f.get("link")
                size = f.get("file_size") or 0
                if not link:
                    continue
                if h > w and h >= 720:  # portrait-ish
                    # aspect closeness + size hint
                    cand.append((abs((w / h) - (9 / 16)), 0 if size == 0 else abs(size - 8_000_000), link, w, h, size))

            if not cand:
                continue

            cand.sort(key=lambda x: (x[0], x[1]))

            for _, __, url, w, h, size_hint in cand[:4]:
                try:
                    print(f"[BG] Trying {w}x{h} ({url[:60]}...)", flush=True)
                    _download(url, out_path)

                    if not out_path.exists():
                        continue

                    actual = out_path.stat().st_size
                    if actual < min_bytes:
                        print(f"[WARN] BG too small ({actual} bytes), retry...", flush=True)
                        continue

                    try:
                        dur = ffprobe_duration(out_path)
                    except Exception as e:
                        print(f"[WARN] ffprobe failed: {e}, retry...", flush=True)
                        continue

                    if dur < min_dur:
                        print(f"[WARN] BG too short ({dur:.1f}s), retry...", flush=True)
                        continue

                    print(f"[OK] BG ready: {out_path} ({dur:.1f}s, {actual} bytes)", flush=True)
                    return out_path

                except Exception as e:
                    print(f"[WARN] Download failed: {e}", flush=True)
                    continue

        print("[WARN] No valid BG this attempt, retrying...", flush=True)

    # If all failed, fallback
    if fallback.exists():
        print("[WARN] Pexels failed; using fallback assets/fallback_bg.mp4", flush=True)
        out_path.write_bytes(fallback.read_bytes())
        return out_path

    raise RuntimeError("Failed to download a valid satisfying portrait background from Pexels (and no fallback).")
