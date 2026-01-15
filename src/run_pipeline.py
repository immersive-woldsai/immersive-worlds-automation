import os, random, subprocess
from pathlib import Path
from TTS.api import TTS
from src.youtube_upload import upload_video

OUT = Path("out"); OUT.mkdir(exist_ok=True)
ASSETS = Path("assets")

def run(cmd):
    subprocess.run(cmd, check=True)

def pick_content():
    topics = [
        ("sleep_calm", "A calm drifting city under starlight"),
        ("sci_fi", "A silent journey through a distant space station"),
        ("sleep_calm", "A peaceful night train through glowing landscapes"),
    ]
    return random.choice(topics)

def build_story(kind, minutes=60):
    # ~150 wpm → 60 dk ≈ 9000 kelime (parçalı üretim)
    base = ("Breathe slowly. Nothing is required of you. "
            "The world moves gently as you listen. ")
    words = base.split()
    target = minutes * 150
    story = []
    while len(story) < target:
        story.extend(words)
    return " ".join(story[:target])

def choose_voice(kind):
    if kind == "sleep_calm":
        return {"gender": "female", "speed": 1.08, "speaker": "p225"}
    return {"gender": "male", "speed": 1.12, "speaker": "p226"}

def tts_audio(text, wav, voice):
    model = "tts_models/en/vctk/vits"
    tts = TTS(model_name=model, gpu=False, progress_bar=False)
    tts.tts_to_file(text=text, file_path=str(wav), speaker=voice["speaker"])

def mix_ambient(voice_wav, out_wav, kind):
    amb = ASSETS / "ambient" / ("rain.wav" if kind=="sleep_calm" else "synth.wav")
    run([
        "ffmpeg","-y",
        "-i",str(voice_wav),
        "-stream_loop","-1","-i",str(amb),
        "-filter_complex","amix=inputs=2:weights=1 0.1",
        "-shortest",str(out_wav)
    ])

def make_video(audio, mp4):
    imgs = list((ASSETS/"images").glob("*.jpg"))
    img = random.choice(imgs)
    run([
        "ffmpeg","-y",
        "-loop","1","-i",str(img),
        "-i",str(audio),
        "-vf","zoompan=z='min(zoom+0.0002,1.08)':d=1",
        "-shortest","-c:v","libx264","-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","192k",str(mp4)
    ])

def seo(kind):
    if kind=="sleep_calm":
        return (
            "Fall Asleep Instantly | Calm Sleep Story 🌙",
            "A deeply calming sleep story with gentle narration and soft ambient sound.",
            ["sleep story","calm voice","deep sleep","relax","bedtime"]
        )
    return (
        "A Quiet Sci-Fi Journey | Immersive Story",
        "An immersive science fiction narration designed for focus and calm.",
        ["sci fi story","immersive","narration","calm"]
    )

def main():
    kind, hint = pick_content()
    story = build_story(kind, minutes=60)

    voice = choose_voice(kind)
    voice_wav = OUT/"voice.wav"
    mix_wav = OUT/"final.wav"
    mp4 = OUT/"final.mp4"

    tts_audio(story, voice_wav, voice)
    mix_ambient(voice_wav, mix_wav, kind)
    make_video(mix_wav, mp4)

    title, desc, tags = seo(kind)
    upload_video(
        video_file=str(mp4),
        title=title,
        description=desc,
        tags=tags,
        privacy_status=os.getenv("YT_DEFAULT_PRIVACY","public"),
        category_id="22",
        language="en"
    )

if __name__ == "__main__":
    main()
