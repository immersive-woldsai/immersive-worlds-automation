import os
import random
from pathlib import Path
import requests
import subprocess

PEXELS_API = "https://api.pexels.com/videos/search"

# “Çocuksu olmasın” + loop izlettiren türler
PEXELS_QUERIES = [
    "oddly satisfying close up",
    "soap cutting asmr",
    "kinetic sand close up",
    "slime satisfying macro",
    "woodworking close up",
    "metal polishing macro",
    "craft hands close up",
    "calming process close up",
]

def ffprobe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True
    )
    return float(r.stdout.strip())

def download_bg_from_pexels(out_path: Path) -> Path:
    key = os.environ["PEXELS_API_KEY"]
    headers = {"Authorization": key}

    out_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, 9):
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

        for v in videos[:10]:
            files = v.get("video_files", [])
            if not files:
                continue

            # portrait ve en az 720p olanları hedefle
            cand = []
            for f in files:
                w = f.get("width") or 0
                h = f.get("height") or 0
                link = f.get("link")
                size = f.get("file_size") or 0
                if not link:
                    continue
                if h > w and h >= 720:
                    # 9:16'ya yakın + orta boy hedef
                    cand.append((abs((w / h) - (9 / 16)), size, link, w, h))

            if not cand:
                continue

            # en iyi aspect ratio yakın olanları, dosya boyutu ~8-20MB arası hedefle
            cand.sort(key=lambda x: (x[0], 0 if x[1] == 0 else abs(x[1] - 12_000_000)))

            for _, _, url, w, h in cand[:3]:
                try:
                    print(f"[BG] Trying {w}x{h} ({url[:60]}...)", flush=True)
                    if out_path.exists():
                        out_path.unlink()

                    with requests.get(url, stream=True, timeout=180) as rr:
                        rr.raise_for_status()
                        with open(out_path, "wb") as f:
                            for chunk in rr.iter_content(1024 * 1024):
                                if chunk:
                                    f.write(chunk)

                    if not out_path.exists() or out_path.stat().st_size < 2_000_000:
                        print("[WARN] BG too small, retry...", flush=True)
                        continue

                    dur = ffprobe_duration(out_path)
                    # 35 sn için 40+ daha stabil
                    if dur < 6:
                        print(f"[WARN] BG too short ({dur:.1f}s), retry...", flush=True)
                        continue

                    print(f"[OK] BG ready: {out_path} ({dur:.1f}s)", flush=True)
                    return out_path

                except Exception as e:
                    print(f"[WARN] Download failed: {e}", flush=True)
                    continue

        print("[WARN] No valid BG this attempt, retrying...", flush=True)

    raise RuntimeError("Failed to download a valid satisfying portrait background from Pexels.")
