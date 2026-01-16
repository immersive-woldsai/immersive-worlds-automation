import random

THEMES = [
    "The Quiet Floating City of Light",
    "A Night Train Through Silent Stars",
    "The Library at the Edge of the Ocean",
    "A Calm Space Station With No Alarms",
    "The Lantern Streets of a Dream City",
    "A Snowy Cabin Where Time Slows Down",
]

CHAPTER_NAMES = [
    "Arrival", "The First Streets", "Gentle Rules", "A Safe Path",
    "Soft Wind", "The Quiet Center", "Slower Steps", "Lights Fading",
    "Breath Like Waves", "Closing the Day"
]

SENTENCE_BANK = {
    "calm": [
        "There is nothing to fix right now.",
        "Your only job is to rest.",
        "Each breath is enough.",
        "You are safe, and the world can wait.",
        "Let your shoulders soften.",
        "Let your thoughts pass like clouds.",
    ],
    "world": [
        "The air feels clean and slow, as if the city is breathing with you.",
        "Lights glow gently, like lanterns behind frosted glass.",
        "Footsteps are quiet here, softened by distance and calm.",
        "Everything moves at a patient pace, with no urgency.",
        "You notice small details, and they make you feel grounded.",
    ],
    "journey": [
        "You walk forward without rushing, and the path meets you halfway.",
        "A calm corridor opens into a wider space, and you exhale.",
        "You turn a corner and find a place that feels familiar, even if you’ve never been here.",
        "The world seems designed for peace—simple, soft, and kind.",
    ],
    "sleep": [
        "With each sentence, your breathing becomes slower.",
        "Your eyelids grow heavier, and that is perfectly okay.",
        "If your mind wanders, gently return to the sound of the voice.",
        "The day can fade now.",
    ]
}

def _make_paragraph(rng: random.Random, n_sent: int) -> str:
    parts = []
    for _ in range(n_sent):
        bucket = rng.choice(["world","journey","calm","sleep"])
        parts.append(rng.choice(SENTENCE_BANK[bucket]))
    return " ".join(parts)

def generate_long_story(target_minutes: int = 60) -> dict:
    rng = random.Random()

    theme = rng.choice(THEMES)
    title = f"Immersive Worlds — Sleep Story: {theme}"

    # 8–12 chapters, target length control by sentence count
    num_chapters = rng.choice([8,9,10,11,12])
    chapter_names = CHAPTER_NAMES[:num_chapters]

    # Rough length control: 60 min için daha fazla cümle
    # (TTS hızına göre yeterince uzun üretir.)
    base_sent = 55 if target_minutes >= 60 else 40
    jitter = 10

    chapters = []
    for i, name in enumerate(chapter_names, start=1):
        # İlk 2 chapter biraz daha “world-building”
        n = base_sent + rng.randint(-jitter, jitter)
        if i <= 2:
            n += 10
        if i == num_chapters:
            n += 15  # closure daha uzun

        text = _make_paragraph(rng, n)

        # Chapter başı yumuşak giriş
        intro = (
            f"Chapter {i}. {name}. "
            "Take a slow breath in… and out. "
        )
        chapters.append({"name": name, "text": intro + text})

    hashtags = ["#SleepStory", "#ImmersiveWorlds", "#DeepSleep", "#Relaxation"]
    tags = ["sleep story","immersive","relaxation","deep sleep","calm","bedtime story","ambient"]

    return {
        "title": title,
        "theme": theme,
        "chapters": chapters,
        "hashtags": hashtags,
        "tags": tags
    }
