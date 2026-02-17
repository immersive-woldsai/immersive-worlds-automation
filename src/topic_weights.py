import random

# --- CORE EMOTION BANKS ---

HOOKS = [
    "Don't send that.",
    "Delete it.",
    "You’re about to ruin everything.",
    "Why are you typing that?",
    "You know how this ends.",
    "This is where you always mess up.",
    "Stop. Think.",
    "You’re not thinking clearly.",
    "You’re emotional again.",
    "Don’t do this tonight."
]

CONFESSIONS = [
    "I'm tired of pretending I'm okay.",
    "I miss them more than I should.",
    "I hate how hopeful I get.",
    "I keep forgiving what hurts me.",
    "I was shrinking to be easier to love.",
    "I confuse intensity with love.",
    "I chase what won't choose me.",
    "I overthink because surprises hurt.",
    "I don't trust calm.",
    "I keep lowering my standards."
]

INNER_ATTACK = [
    "You’re about to embarrass yourself.",
    "They don’t care the way you do.",
    "You’re repeating the same mistake.",
    "You already know the answer.",
    "This never ends well.",
    "You’re scared of being alone.",
    "You don’t want them. You want validation.",
]

TWISTS = [
    "Maybe you're not too much. Maybe they’re not enough.",
    "Peace feels boring when you’re addicted to chaos.",
    "Sometimes closure is just disappointment with a caption.",
    "If they wanted to, you wouldn’t be guessing.",
    "Familiar pain feels safer than unknown peace.",
    "You’re not anxious. You’re attached.",
    "Maybe silence is the answer."
]

CLIFFS = [
    "Wait.",
    "No.",
    "Maybe that's the point.",
    "…what if I don’t send it?",
    "What if I walk away?",
    "What if I choose myself?",
    "And that’s when I stopped typing."
]

def generate_chat_script():
    hook = random.choice(HOOKS)
    conf = random.choice(CONFESSIONS)
    inner = random.choice(INNER_ATTACK)
    twist = random.choice(TWISTS)
    cliff = random.choice(CLIFFS)

    return hook, conf, inner, twist, cliff
