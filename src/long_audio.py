import subprocess
from pathlib import Path

def run(cmd):
    print("\n[CMD]", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.stdout:
        print("[STDOUT]\n", p.stdout[-4000:], flush=True)
    if p.stderr:
        print("[STDERR]\n", p.stderr[-4000:], flush=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {p.returncode}")

def normalize_wav(in_wav: Path, out_wav: Path):
    """
    Tüm chapter wav'larını aynı formata getir:
    - PCM 16-bit
    - 22050 Hz
    - mono
    """
    run([
        "ffmpeg","-y",
        "-i", str(in_wav),
        "-ac","1",
        "-ar","22050",
        "-c:a","pcm_s16le",
        str(out_wav)
    ])

def concat_wavs_filter(normalized_wavs, out_voice_wav: Path):
    """
    WAV concat için en stabil yöntem: concat filter (re-encode)
    """
    # ffmpeg input list: -i a.wav -i b.wav ...
    cmd = ["ffmpeg","-y"]
    for w in normalized_wavs:
        cmd += ["-i", str(w)]

    # concat filter: n = input sayısı
    n = len(normalized_wavs)
    cmd += [
        "-filter_complex", f"concat=n={n}:v=0:a=1[aout]",
        "-map", "[aout]",
        "-c:a","pcm_s16le",
        str(out_voice_wav)
    ]
    run(cmd)

def build_long_audio_with_ambient(chapter_wavs, out_voice_wav: Path, out_final_wav: Path, pause_sec: int = 4):
    """
    1) Chapter wav -> normalize (mono, 22050, pcm_s16le)
    2) concat filter ile birleştir
    3) aralara “pause” eklemek için voice'a apad + atrim değil:
       basitçe ambient mix ile yumuşatıyoruz (stabil)
    4) pink noise ambient düşük vol ile mix
    """
    tmp_dir = out_voice_wav.parent / "tmp_norm"
    tmp_dir.mkdir(exist_ok=True)

    normalized = []
    for i, w in enumerate(chapter_wavs, start=1):
        nw = tmp_dir / f"norm_{i:02d}.wav"
        normalize_wav(w, nw)
        normalized.append(nw)

    concat_wavs_filter(normalized, out_voice_wav)

    # Ambient mix (çok kısık)
    run([
        "ffmpeg","-y",
        "-i", str(out_voice_wav),
        "-f","lavfi","-i","anoisesrc=color=pink:amplitude=0.03",
        "-filter_complex",
        "[1:a]lowpass=f=1800,volume=0.10[aamb];"
        "[0:a]volume=1.0[avoice];"
        "[avoice][aamb]amix=inputs=2:duration=first:dropout_transition=2[amix]",
        "-map","[amix]",
        "-c:a","pcm_s16le",
        str(out_final_wav)
    ])
