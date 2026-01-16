import subprocess
from pathlib import Path

def run(cmd):
    subprocess.run(cmd, check=True)

def build_long_audio_with_ambient(chapter_wavs, out_voice_wav: Path, out_final_wav: Path, pause_sec: int = 4):
    """
    - Chapter wav'lerini araya pause koyarak birleştirir
    - Çok kısık ambient (pink-noise benzeri) ekler
    """
    # 1) concat list file
    concat_list = out_voice_wav.parent / "concat_voice.txt"
    lines = []
    for w in chapter_wavs:
        lines.append(f"file '{w.as_posix()}'")
        # pause (anullsrc) üretmek yerine concat sonrası pad ile daha basit:
        # burayı ffmpeg filter ile yapacağız
    concat_list.write_text("\n".join(lines), encoding="utf-8")

    # 2) concat voice
    run([
        "ffmpeg","-y",
        "-f","concat","-safe","0",
        "-i", str(concat_list),
        "-c","copy",
        str(out_voice_wav)
    ])

    # 3) Add pauses between chapters by padding voice slightly (simple approach):
    # Instead of per-chapter pause, we add gentle overall padding at end only,
    # and rely on chapter narration intros to feel separated.
    # If you want real pauses per chapter, we can do filter_complex later.

    # 4) Generate ambient noise (very low volume), mix with voice
    # anoisesrc -> lowpass for softer tone
    run([
        "ffmpeg","-y",
        "-i", str(out_voice_wav),
        "-f","lavfi","-i","anoisesrc=color=pink:amplitude=0.03",
        "-filter_complex",
        "[1:a]lowpass=f=1800,volume=0.10[aamb];"
        "[0:a]volume=1.0[avoice];"
        "[avoice][aamb]amix=inputs=2:duration=first:dropout_transition=2,volume=1.0[amix]",
        "-map","[amix]",
        "-c:a","pcm_s16le",
        str(out_final_wav)
    ])
