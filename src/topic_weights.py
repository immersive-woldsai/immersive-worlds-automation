import random
import re

# ---------- UTIL ----------
def _cap(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return s
    return s[0].upper() + s[1:]

def _clean(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    # keep it ASCII-ish (your overlay/TTS is fine with this)
    s = s.replace("…", "...").replace("’", "'")
    return s

def _pick(rng: random.Random, arr):
    return rng.choice(arr)

# ---------- TOPIC BANKS ----------
TOPICS = {
    "ghosting": {
        "identity": ["If you're waiting on a reply", "If you got left on read", "If you feel ignored"],
        "hooks": ["Don't send that.", "Close the chat.", "Stop typing.", "Delete it."],
        "confessions": [
            "I wasn't asking for love. Just clarity.",
            "I hate how fast I miss people.",
            "I'm tired of feeling optional.",
        ],
        "inner_attacks": [
            "They already chose silence.",
            "You're about to beg for the bare minimum.",
            "If they cared, you'd know.",
        ],
        "twists": [
            "Sometimes closure is just disappointment with a caption.",
            "Silence is still an answer.",
            "You're not too much. You're just in the wrong place.",
        ],
        "cliffs": [
            "Wait... maybe I shouldn't send it.",
            "And that's when I stopped typing.",
            "No. Not tonight.",
        ],
    },
    "boundaries": {
        "identity": ["If you struggle to say no", "If you keep overgiving", "If you feel guilty for boundaries"],
        "hooks": ["Don't explain.", "Say no once.", "Stop apologizing.", "Hold your line."],
        "confessions": [
            "I was shrinking to be easier to love.",
            "I kept lowering my standards to avoid being alone.",
            "I keep saying yes, then hating myself for it.",
        ],
        "inner_attacks": [
            "You're trying to be chosen, not respected.",
            "You're teaching them what you'll tolerate.",
            "You don't need to earn basic decency.",
        ],
        "twists": [
            "The right people don't need you to beg.",
            "Peace feels boring when you're addicted to chaos.",
            "Self-respect is quiet... and powerful.",
        ],
        "cliffs": [
            "So I finally said no.",
            "And I meant it.",
            "And I didn't explain.",
        ],
    },
    "overthinking": {
        "identity": ["If you overthink at night", "If your brain won't shut off", "If 2AM feels loud"],
        "hooks": ["Stop replaying it.", "Breathe. Slowly.", "You're spiraling.", "Pause."],
        "confessions": [
            "My brain won't stop replaying it.",
            "One sentence ruined my whole night.",
            "I don't trust calm. I wait for the twist.",
        ],
        "inner_attacks": [
            "You're searching for certainty in a person who can't give it.",
            "You're reading between lines that aren't there.",
            "You're confusing fear with intuition.",
        ],
        "twists": [
            "Maybe you're not anxious. Maybe you're unsafe.",
            "Your body remembers what you ignore.",
            "The answer isn't in the text. It's in the pattern.",
        ],
        "cliffs": [
            "And that's when I put the phone down.",
            "So I stopped checking.",
            "So I chose sleep over answers.",
        ],
    },
    "attachment": {
        "identity": ["If you get attached fast", "If you confuse intensity with love", "If you chase mixed signals"],
        "hooks": ["Don't chase.", "Stop reaching.", "Hold still.", "Wait."],
        "confessions": [
            "I confuse intensity with love.",
            "I chase what won't choose me.",
            "I miss the idea more than the person.",
        ],
        "inner_attacks": [
            "You're addicted to uncertainty.",
            "You're calling it love to avoid the truth.",
            "You're trying to win a game you didn't start.",
        ],
        "twists": [
            "Familiar pain feels safer than unknown peace.",
            "If they wanted to, you wouldn't be guessing.",
            "You're not behind... you're just waking up.",
        ],
        "cliffs": [
            "So I didn't send it.",
            "So I chose myself.",
            "And the craving passed.",
        ],
    },
}

# ---------- TITLE PSYCHOLOGY ----------
TITLE_PATTERNS = [
    # identity + warning
    "{identity}... don't do this",
    "{identity}... this is why it hurts",
    "{identity}? watch this",
    # direct command
    "Don't text them.",
    "Read this before you text them",
    "If you overthink, this will hit",
    # tension / risk
    "This text would ruin everything",
    "I almost sent this... then stopped",
    "The message I didn't send",
    # inner voice brand
    "My inner voice said this",
    "My inner voice stopped me",
]

def generate_title(rng: random.Random, identity: str, hook: str, cliff: str) -> str:
    # keep short, punchy
    patt = _pick(rng, TITLE_PATTERNS)
    t = patt.format(identity=identity)
    t = _clean(t)

    # small chance to add micro-tension tail
    if rng.random() < 0.25:
        tail = _pick(rng, ["(wait for the end)", "(don't scroll)", "(watch twice)"])
        t = f"{t} {tail}"

    # ensure <= ~60 chars ideally
    if len(t) > 62:
        t = t[:62].rstrip() + "..."
    return t

# ---------- LOOP-AWARE SCRIPT ----------
def generate_chat_script(seed: int | None = None):
    """
    Returns: (title, lines)
    lines: list of tuples (who, text)
    who in {"A","INNER"}
    """

    rng = random.Random(seed) if seed is not None else random.Random()

    topic_key = _pick(rng, list(TOPICS.keys()))
    bank = TOPICS[topic_key]

    identity = _pick(rng, bank["identity"])
    hook = _pick(rng, bank["hooks"])
    conf = _pick(rng, bank["confessions"])
    inner = _pick(rng, bank["inner_attacks"])
    twist = _pick(rng, bank["twists"])
    cliff = _pick(rng, bank["cliffs"])

    # --- Loop bridge rules ---
    # We try to make last line naturally connect to first hook.
    # Option 1: end with "So I stopped." when hook begins "Stop..."
    if hook.lower().startswith("stop") and rng.random() < 0.5:
        cliff = _pick(rng, ["...so I stopped.", "So I stopped.", "And I stopped."])
    # Option 2: end with "I won't." when hook begins "Don't..."
    if hook.lower().startswith("don't") and rng.random() < 0.5:
        cliff = _pick(rng, ["...maybe I won't.", "I won't.", "Not anymore."])

    # Build 5-line inner voice dominant chat
    lines = [
        ("A", hook),
        ("INNER", inner),
        ("A", conf),
        ("INNER", twist),
        ("A", cliff),
    ]

    # Title built from identity + pattern
    title = generate_title(rng, identity=identity, hook=hook, cliff=cliff)

    # clean all
    lines = [(w, _clean(t)) for (w, t) in lines]
    return title, lines
