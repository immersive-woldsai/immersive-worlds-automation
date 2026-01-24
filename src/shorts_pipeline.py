import os
import random
import re
import subprocess
from pathlib import Path
import shutil
from datetime import datetime, timezone
import time
import json
import base64
from typing import Dict, Any, Tuple, List, Optional

from PIL import Image, ImageDraw, ImageFont

import requests
from TTS.api import TTS
from src.youtube_upload import upload_video

print("SHORTS_PIPELINE_VERSION = 2026-01-24-FINAL-ENG-HUGE-PARALLAX", flush=True)

OUT = Path("out")
OUT.mkdir(exist_ok=True)

STATE_PATH = OUT / "state.json"


# ---------------------------
# Huge Procedural Pools (no manual editing needed)
# ---------------------------

ANIMALS = [
    "wolf","lion","tiger","bear","fox","horse","elephant","gorilla","panther","leopard","cheetah","hyena",
    "deer","moose","bison","boar","rabbit","otter","seal","dolphin","whale","shark",
    "raccoon","kangaroo","camel","zebra","rhino","hippo",
    "eagle","owl","crow","raven","falcon","hawk","swan","peacock","sparrow","pigeon",
    "snake","crocodile","turtle","lizard","frog",
    "butterfly","bee","ant","spider"
]

OBJECT_BASE = [
    "mirror","clock","watch","camera","phone","laptop","tablet","headphones","microphone","speaker",
    "book","notebook","pen","pencil","paintbrush","map","compass",
    "key","wallet","coin","receipt","passport","train ticket","boarding pass",
    "umbrella","candle","lamp","flashlight",
    "shoe","backpack","suitcase","jacket","gloves","scarf",
    "chair","window","door","curtain","stairs","elevator","streetlight","bus stop","subway",
    "coffee cup","water bottle","remote control","plate","fork","spoon","toothbrush",
    "helmet","guitar","violin","drum","bicycle","motorcycle helmet","shopping cart",
    "plant pot","vase","ring","necklace","bracelet",
]

ADJECTIVES = [
    "old","broken","tiny","heavy","silent","rusty","golden","glass","wooden","plastic","steel",
    "forgotten","dusty","new","cracked","lost","cheap","expensive","burned","wet","frozen",
    "shiny","scarred","battered","smooth","sharp","bent","stolen","returned",
]

MATERIALS = ["wood","metal","glass","plastic","leather","paper","stone","ceramic","carbon","rubber","fabric"]

PLACES = [
    "train station","subway platform","empty classroom","quiet library","rainy street","mountain trail",
    "night city rooftop","abandoned factory","desert road","forest cabin","ocean cliff","old bridge",
    "hospital hallway","airport gate","empty cinema","parking garage","gym at 5am","night diner",
    "small apartment desk","construction site","snowy sidewalk","crowded market","lonely beach"
]

BACKDROPS_EPIC = [
    "ruined city","apocalyptic skyline","stormy neon city","cracked desert","burning horizon",
    "giant waves","ash-filled street","collapsed bridge","smoke and debris","dark thunderstorm"
]

THEMES = [
    "discipline","consistency","patience","starting again","focus","self-respect","courage","resilience",
    "quiet confidence","no excuses","one step today","progress over perfection","doing hard things",
    "forgiving yourself","earning your future","staying calm","building habits","winning in silence",
    "outworking your doubts","showing up anyway","choosing the hard path"
]

TONES = ["calm","gritty","epic","funny"]

HOOKS = [
    "Stop scrolling for 10 seconds.",
    "Quick reminder—listen.",
    "This is your sign.",
    "Before you give up, hear this.",
    "If no one believes you, good.",
    "You're closer than you think.",
]

CLOSES = [
    "Do the next right thing—quietly.",
    "Save this and come back tomorrow.",
    "Comment one word: done.",
    "Now go—prove it to yourself.",
    "No excuses. Start now.",
]

MODE_WEIGHTS = {
    "object": 42,
    "animal": 20,
    "place": 23,
    "epic": 15,
}


def generate_entities() -> List[str]:
    objects = set(OBJECT_BASE)
    for base in OBJECT_BASE:
        for adj in ADJECTIVES:
            objects.add(f"{adj} {base}")
        for mat in MATERIALS:
            objects.add(f"{mat} {base}")
        for adj in ADJECTIVES[:10]:
            for mat in MATERIALS[:7]:
                objects.add(f"{adj} {mat} {base}")
    return sorted(objects)

HUGE_OBJECTS = generate_entities()


# ---------------------------
# Helpers
# ---------------------------

def _bool_env(name: str, default: str = "false") -> bool:
    v = os.getenv(name, default).strip().lower()
    return v in ("1","true","yes","y","on")

def _float_env(name: str, default: str) -> float:
    try:
        return float(os.getenv(name, default))
    except Exception:
        return float(default)

def run(cmd):
    print("\n[CMD]", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.stdout:
        print("[STDOUT]\n", p.stdout[-4000:], flush=True)
    if p.stderr:
        print("[STDERR]\n", p.stderr[-4000:], flush=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {p.returncode}")

def ffprobe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True
    )
    return float(r.stdout.strip())

def chunks(words, n):
    for i in range(0, len(words), n):
        yield words[i:i+n]

def write_srt_chunked(text: str, total_sec: float, srt_path: Path):
    words = text.split()
    parts = list(chunks(words, 3))
    if not parts:
        srt_path.write_text("", encoding="utf-8")
        return

    per = max(0.45, min(1.15, total_sec / max(1, len(parts))))

    def fmt(ts):
        ms = int((ts - int(ts)) * 1000)
        s = int(ts) % 60
        m = (int(ts) // 60) % 60
        h = int(ts) // 3600
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    t = 0.0
    out = []
    for idx, part in enumerate(parts, start=1):
        start = t
        end = min(total_sec, t + per)
        out += [str(idx), f"{fmt(start)} --> {fmt(end)}", " ".join(part), ""]
        t = end
        if t >= total_sec:
            break

    srt_path.write_text("\n".join(out), encoding="utf-8")

def is_valid_image(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 10_000:
        return False
    try:
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception:
        return False

def download(url: str, path: Path):
    headers = {"User-Agent": "Mozilla/5.0"}
    with requests.get(url, stream=True, timeout=35, headers=headers, allow_redirects=True) as r:
        r.raise_for_status()
        ctype = (r.headers.get("content-type") or "").lower()
        if "image" not in ctype:
            raise RuntimeError(f"Not an image response. content-type={ctype} url={url}")
        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
    if not is_valid_image(path):
        raise RuntimeError(f"Downloaded file is not a valid image: {path} size={path.stat().st_size}")

def wikimedia_image_url(query: str) -> Optional[str]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": "8",
        "gsrnamespace": "6",
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": "1080",
        "iiurlheight": "1920",
    }
    url = "https://commons.wikimedia.org/w/api.php"
    r = requests.get(url, params=params, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    data = r.json()
    pages = (data.get("query") or {}).get("pages") or {}
    for _, p in pages.items():
        ii = (p.get("imageinfo") or [])
        if not ii:
            continue
        thumb = ii[0].get("thumburl") or ii[0].get("url")
        if thumb:
            return thumb
    return None

def ensure_bg_image_free(queries: List[str], img_path: Path):
    last_err = None

    for q in queries[:10]:
        q2 = q.replace(" ", ",")
        url = f"https://source.unsplash.com/1080x1920/?{q2}"
        for attempt in range(1, 4):
            try:
                if img_path.exists():
                    img_path.unlink()
                download(url, img_path)
                print(f"[OK] BG (unsplash): {q}", flush=True)
                return
            except Exception as e:
                last_err = e
                wait = 1.5 * attempt
                print(f"[WARN] Unsplash failed ({q}) attempt={attempt}: {e} | sleep={wait}s", flush=True)
                time.sleep(wait)

    for q in queries[:18]:
        try:
            img_url = wikimedia_image_url(q)
            if not img_url:
                continue
            if img_path.exists():
                img_path.unlink()
            download(img_url, img_path)
            print(f"[OK] BG (wikimedia): {q}", flush=True)
            return img_path   # <-- IMPORTANT: return inside function
        except Exception as e:
            last_err = e
            print(f"[WARN] Wikimedia failed ({q}): {e}", flush=True)

    print("[WARN] No image found online, using local fallback.", flush=True)

    fallback = Path("assets/fallback.jpg")   # <-- MUST be indented (inside function)
    if fallback.exists():
        img_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(fallback, img_path)
        return img_path

    raise RuntimeError(
        f"No valid image found and no fallback image present. Last error: {last_err}"
    )



# ---------------------------
# Optional: SDWebUI image generation (for truly epic visuals)
# ---------------------------

def sdwebui_generate(prompt: str, out_path: Path):
    base_url = os.getenv("SDWEBUI_URL", "").strip()
    if not base_url:
        raise RuntimeError("SDWEBUI_URL is not set")

    payload = {
        "prompt": prompt,
        "negative_prompt": "blurry, low-res, watermark, text, logo, deformed, extra limbs, bad anatomy",
        "steps": int(os.getenv("SD_STEPS", "25")),
        "width": 576,
        "height": 1024,
        "cfg_scale": float(os.getenv("SD_CFG", "7")),
        "sampler_name": os.getenv("SD_SAMPLER", "DPM++ 2M Karras"),
    }
    r = requests.post(f"{base_url}/sdapi/v1/txt2img", json=payload, timeout=300)
    r.raise_for_status()
    data = r.json()
    img_b64 = data["images"][0]
    img_bytes = base64.b64decode(img_b64.split(",", 1)[-1])
    out_path.write_bytes(img_bytes)
    if not is_valid_image(out_path):
        raise RuntimeError("SD generated file invalid")


# ---------------------------
# State: avoid repeating subjects across runs
# ---------------------------

def load_state() -> Dict[str, Any]:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"recent": []}

def save_state(state: Dict[str, Any]):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def pick_weighted_mode(rng: random.Random) -> str:
    items = list(MODE_WEIGHTS.items())
    total = sum(w for _, w in items)
    r = rng.uniform(0, total)
    upto = 0
    for mode, w in items:
        upto += w
        if r <= upto:
            return mode
    return items[-1][0]

def pick_subject_auto(rng: random.Random, state: Dict[str, Any]) -> Tuple[str, str, str, str]:
    recent = state.get("recent", [])
    recent_set = set(recent)

    def pick_new(cands: List[str]) -> str:
        c2 = [c for c in cands if c not in recent_set]
        if not c2:
            c2 = cands
        return rng.choice(c2)

    mode = pick_weighted_mode(rng)

    if mode == "object":
        subject = pick_new(HUGE_OBJECTS)
    elif mode == "animal":
        subject = pick_new(ANIMALS)
    elif mode == "place":
        subject = pick_new(PLACES)
    else:
        subject = pick_new(ANIMALS)

    tone = rng.choice(TONES)
    theme = rng.choice(THEMES)

    recent.append(subject)
    state["recent"] = recent[-200:]
    return mode, tone, subject, theme

def pick_speaker(subject: str) -> str:
    calm_words = {"mirror","candle","book","pillow","blanket","window","lamp","curtain","owl","whale","library","beach"}
    energetic_words = {"clock","phone","laptop","watch","camera","ticket","passport","train","subway","lion","tiger","wolf","bear","gym"}
    toks = set(subject.lower().split())
    is_calm = len(toks & calm_words) > 0 and len(toks & energetic_words) == 0
    return "p225" if is_calm else "p226"


# ---------------------------
# Script + prompt generation (English only)
# ---------------------------

def build_script_and_prompt(mode: str, tone: str, subject: str, theme: str, rng: random.Random) -> Tuple[str, str, List[str]]:
    hook = rng.choice(HOOKS)
    close = rng.choice(CLOSES)

    style_words = {
        "calm": ["soft light", "minimal", "cozy", "warm", "quiet"],
        "gritty": ["moody", "dramatic shadows", "film grain", "dark", "rain"],
        "epic": ["cinematic", "dramatic lighting", "storm", "smoke", "high contrast"],
        "funny": ["quirky", "playful", "odd", "unexpected", "bright"]
    }.get(tone, ["cinematic"])

    if mode == "epic":
        backdrop = rng.choice(BACKDROPS_EPIC)
        script = " ".join([
            hook,
            f"I'm a {subject}.",
            "I don't roar to scare people.",
            "I roar to wake myself up.",
            f"{theme.title()} is simple:",
            "show up when it's boring.",
            "One more rep. One more page. One more try.",
            close
        ])
        sd_prompt = (
            f"A colossal {subject} towering over a {backdrop}, cinematic, ultra realistic, "
            f"dramatic lighting, smoke, debris, epic scale, 9:16 vertical, no text, no watermark."
        )
        queries = [
            f"{subject} cinematic {backdrop}",
            f"{subject} dramatic {backdrop}",
            f"{subject} stormy night",
            f"{subject} dark portrait",
            f"{subject} cinematic portrait"
        ]
        return script, sd_prompt, queries

    if mode == "animal":
        script = " ".join([
            hook,
            f"I'm a {subject}. I notice patterns.",
            "Most people quit when it gets quiet.",
            f"But {theme} is built in silence.",
            "Small actions. Daily.",
            close
        ])
        sd_prompt = (
            f"A powerful cinematic portrait of a {subject}, {', '.join(style_words)}, "
            f"depth of field, high detail, 9:16 vertical, no text, no watermark."
        )
        queries = [
            f"{subject} cinematic portrait",
            f"{subject} dramatic lighting",
            f"{subject} close up portrait",
            f"{subject} {style_words[0]}",
        ]
        return script, sd_prompt, queries

    if mode == "place":
        script = " ".join([
            hook,
            f"I live in a {subject}.",
            "I watch people rush, panic, and quit.",
            f"But the ones who win have {theme}.",
            "They do the simple thing—again.",
            close
        ])
        sd_prompt = (
            f"Cinematic scene of a {subject}, {', '.join(style_words)}, ultra detailed, "
            f"9:16 vertical, no text, no watermark."
        )
        queries = [
            f"{subject} cinematic",
            f"{subject} {style_words[0]}",
            f"{subject} dramatic lighting",
            f"{subject} rainy night" if "rain" in style_words else f"{subject} night",
        ]
        return script, sd_prompt, queries

    # object
    if tone == "funny":
        script = " ".join([
            hook,
            f"I'm a {subject}.",
            "People ignore me… until they need me.",
            f"That's the lesson: {theme}.",
            "Do it before it becomes a crisis.",
            close
        ])
    elif tone == "gritty":
        script = " ".join([
            hook,
            f"I'm a {subject}. I've been dropped, scratched, ignored.",
            "But I still show up.",
            f"That's {theme}:",
            "not perfect—just consistent.",
            close
        ])
    else:
        script = " ".join([
            hook,
            f"I'm a {subject}. I notice patterns.",
            "You don't need a perfect plan.",
            "You need a repeatable step.",
            f"{theme.title()} isn't a mood.",
            "It's a decision you make again—today.",
            close,
            "Tomorrow, start smaller—and start again."
        ])

    sd_prompt = (
        f"Cinematic close-up photo of a {subject}, {', '.join(style_words)}, shallow depth of field, "
        f"9:16 vertical, no text, no watermark."
    )
    queries = [
        f"{subject} close up photo",
        f"{subject} on table photo",
        f"{subject} cinematic",
        f"{subject} {style_words[0]}",
        f"{subject} macro"
    ]
    return script, sd_prompt, queries


# ---------------------------
# TTS
# ---------------------------

def tts_to_wav(text: str, wav_path: Path, speaker: str):
    tts = TTS(model_name="tts_models/en/vctk/vits", gpu=False, progress_bar=False)
    tts.tts_to_file(text=text, file_path=str(wav_path), speaker=speaker)


# ---------------------------
# Thumbnail + labels
# ---------------------------

def safe_label(subject: str) -> str:
    t = subject.upper().replace("'", "").replace(":", "")
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > 22:
        t = t[:22].rstrip() + "…"
    return t

def make_thumbnail(bg_path: Path, label: str, out_path: Path):
    with Image.open(bg_path) as im:
        im = im.convert("RGB").resize((1280, 720))

    draw = ImageDraw.Draw(im)
    font = ImageFont.load_default()

    draw.rectangle([0, 520, 1280, 720], fill=(0, 0, 0))
    text = f"{label} SPEAKS"
    tw = draw.textlength(text, font=font)
    draw.text(((1280 - tw) / 2, 590), text, fill=(255, 255, 255), font=font)

    im.save(out_path, quality=92)
    print(f"[OK] Thumbnail generated: {out_path}", flush=True)


# ---------------------------
# Image selection (SD if enabled else free)
# ---------------------------

def ensure_bg_image(subject: str, sd_prompt: str, queries: List[str], img_path: Path):
    if _bool_env("ENABLE_SD", "false"):
        try:
            sdwebui_generate(sd_prompt, img_path)
            print("[OK] BG generated via SDWebUI", flush=True)
            return
        except Exception as e:
            print(f"[WARN] SDWebUI failed, falling back: {e}", flush=True)

    ensure_bg_image_free(queries, img_path)


# ---------------------------
# Ambient (optional)
# ---------------------------

def make_ambient_wav(out_wav: Path, duration_sec: float):
    # pink noise at low amplitude; fully offline (lavfi)
    amp = _float_env("AMBIENT_AMP", "0.03")
    run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"anoisesrc=color=pink:amplitude={amp}",
        "-t", f"{duration_sec:.3f}",
        "-c:a", "pcm_s16le",
        str(out_wav)
    ])


# ---------------------------
# Render Shorts (PARALLAX + SHAKE + GRAIN + VIGNETTE)
# ---------------------------

def render_shorts_9x16(subject: str, img_path: Path, voice_wav: Path, srt_path: Path, out_mp4: Path):
    label = safe_label(subject)

    enable_parallax = _bool_env("ENABLE_PARALLAX", "true")
    enable_grain = _bool_env("ENABLE_GRAIN", "true")
    enable_vignette = _bool_env("ENABLE_VIGNETTE", "true")
    enable_ambient = _bool_env("ENABLE_AMBIENT", "false")

    # Shake intensities (pixels)
    shake_x = int(_float_env("SHAKE_X", "4"))
    shake_y = int(_float_env("SHAKE_Y", "3"))

    # Grain level (ffmpeg noise)
    grain_strength = int(_float_env("GRAIN", "10"))

    # Zoom levels
    bg_zoom_max = _float_env("BG_ZOOM_MAX", "1.14")
    fg_zoom_max = _float_env("FG_ZOOM_MAX", "1.07")

    # If ambient enabled, create + mix
    final_audio = voice_wav
    ambient_wav = OUT / "ambient.wav"
    mixed_wav = OUT / "audio_mix.wav"

    dur = ffprobe_duration(voice_wav)

    if enable_ambient:
        try:
            make_ambient_wav(ambient_wav, dur)
            ambient_level = _float_env("AMBIENT_LEVEL", "0.18")
            run([
                "ffmpeg", "-y",
                "-i", str(voice_wav),
                "-i", str(ambient_wav),
                "-filter_complex",
                f"[0:a]volume=1[a0];[1:a]volume={ambient_level}[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "[aout]",
                "-c:a", "pcm_s16le",
                str(mixed_wav)
            ])
            final_audio = mixed_wav
        except Exception as e:
            print(f"[WARN] ambient mix failed, continue without ambient: {e}", flush=True)
            final_audio = voice_wav

    # Parallax from single image:
    # - background: blurred + slower zoom
    # - foreground: slightly different zoom
    # - overlay with tiny shake offsets
    #
    # IMPORTANT: keep 1080x1920 and yuv420p.
    if enable_parallax:
        # Note: zoompan uses 'on' (output frame count). d=1 for per-frame.
        filter_complex = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,split=2[bg][fg];"
            # background: blur + slow zoom
            f"[bg]scale=1200:2134,boxblur=10:1,zoompan=z='min({bg_zoom_max},1+0.0007*on)':d=1:s=1080x1920[bgz];"
            # foreground: slightly faster zoom
            f"[fg]scale=1120:1992,zoompan=z='min({fg_zoom_max},1+0.0011*on)':d=1:s=1080x1920[fgz];"
            # overlay + shake
            f"[bgz][fgz]overlay="
            f"x='(W-w)/2 + sin(2*PI*t*1.7)*{shake_x}':"
            f"y='(H-h)/2 + cos(2*PI*t*1.3)*{shake_y}'"
            "[v0];"
        )
    else:
        filter_complex = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[v0];"
        )

    # Grain + vignette
    post = "[v0]"
    if enable_grain:
        filter_complex += f"{post}noise=alls={grain_strength}:allf=t+u[v1];"
        post = "[v1]"
    if enable_vignette:
        filter_complex += f"{post}vignette=PI/4[v2];"
        post = "[v2]"

    # Text overlays + subtitles
    # subtitles filter comes last
    filter_complex += (
        f"{post}format=yuv420p,"
        "drawbox=x=0:y=1180:w=iw:h=70:color=black@0.35:t=fill,"
        f"drawtext=text='IMMERSIVE · {label}':fontcolor=white@0.9:fontsize=18:x=(w-text_w)/2:y=1208,"
        f"subtitles={srt_path}:force_style='Fontsize=24,Alignment=2,Outline=2,Shadow=1,MarginV=65'"
        "[vout]"
    )

    run([
        "ffmpeg","-y",
        "-loop","1","-framerate","30","-i",str(img_path),
        "-i",str(final_audio),
        "-t","58",
        "-shortest",
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "1:a",
        "-r","30",
        "-c:v","libx264",
        "-profile:v","high",
        "-level","4.1",
        "-pix_fmt","yuv420p",
        "-movflags","+faststart",
        "-c:a","aac","-b:a","160k",
        str(out_mp4)
    ])


# ---------------------------
# Metadata
# ---------------------------

def make_metadata(subject: str, mode: str, tone: str, theme: str, script: str):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if mode == "epic":
        title = f"{subject.title()} — Giant Mindset ({theme.title()}) #Shorts"
    else:
        title = f"{subject.title()} Speaks — {theme.title()} #Shorts"

    desc = (
        f"{subject.title()} speaks.\n"
        f"Theme: {theme}\n"
        f"Tone: {tone}\n"
        f"UTC: {today}\n\n"
        f"{script}\n\n"
        "#shorts #motivation #mindset #selfimprovement\n"
    )
    tags = ["shorts","motivation","mindset","self improvement","immersive worlds",subject.lower(),theme]
    return title, desc, tags


# ---------------------------
# Main
# ---------------------------

def main():
    seed = int(time.time())
    rng = random.Random(seed)

    state = load_state()

    mode, tone, subject, theme = pick_subject_auto(rng, state)
    speaker = pick_speaker(subject)

    script, sd_prompt, queries = build_script_and_prompt(mode, tone, subject, theme, rng)

    wav = OUT / "short.wav"
    srt = OUT / "short.srt"
    img = OUT / "bg.jpg"
    mp4 = OUT / "short.mp4"
    thumb = OUT / "thumb.jpg"

    tts_to_wav(script, wav, speaker=speaker)
    dur = ffprobe_duration(wav)
    print(f"[DEBUG] mode={mode} tone={tone} subject={subject} theme={theme} speaker={speaker} audio={dur:.2f}s seed={seed}", flush=True)

    write_srt_chunked(script, min(dur, 58.0), srt)

    ensure_bg_image(subject, sd_prompt, queries, img)

    render_shorts_9x16(subject, img, wav, srt, mp4)

    thumb_path = None
    try:
        make_thumbnail(img, safe_label(subject), thumb)
        thumb_path = str(thumb)
    except Exception as e:
        print(f"[WARN] thumbnail generation failed: {e}", flush=True)

    title, desc, tags = make_metadata(subject, mode, tone, theme, script)

    upload_video(
        video_file=str(mp4),
        title=title,
        description=desc,
        tags=tags,
        privacy_status=os.getenv("YT_DEFAULT_PRIVACY","public"),
        category_id="22",
        language="en",
        thumbnail_file=thumb_path,
    )

    save_state(state)
    print("[OK] state saved:", STATE_PATH, flush=True)


if __name__ == "__main__":
    main()
