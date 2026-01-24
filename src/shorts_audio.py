import subprocess
from pathlib import Path
from typing import List, Tuple
from TTS.api import TTS

def run(cmd: List[str]):
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

def tts_to_wav(text: str, wav_path: Path, speaker: str):
    tts = TTS(model_name="tts_models/en/vctk/vits", gpu=False, progress_bar=False)
    tts.tts_to_file(text=text, file_path=str(wav_path), speaker=speaker)

def build_timeline_audio(
    items: List[Tuple[float, Path]],
    out_wav: Path,
    total_sec: int = 35
) -> Path:
    """
    items: [(start_seconds, wav_path), ...]
    We adelay each wav and then amix them into one track.
    """
    inputs = []
    for _, p in items:
        inputs += ["-i", str(p)]

    # filter: [0:a]adelay=... [a0]; [1:a]adelay=... [a1]; ...; amix
    parts = []
    amix_inputs = []
    for i, (t, _) in enumerate(items):
        ms = int(round(t * 1000))
        parts.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
        amix_inputs.append(f"[a{i}]")

    # pad to total_sec so video never truncates
    # we mix into [mix], then apad, then atrim
    filter_complex = ";".join(parts) + ";" + "".join(amix_inputs) + f"amix=inputs={len(items)}:normalize=0[mix];" \
                     f"[mix]apad=pad_dur={total_sec+5},atrim=0:{total_sec}[out]"

    out_wav.parent.mkdir(parents=True, exist_ok=True)

    run([
        "ffmpeg","-y","-hide_banner","-loglevel","error",
        *inputs,
        "-filter_complex", filter_complex,
        "-map","[out]",
        str(out_wav)
    ])
    return out_wav
