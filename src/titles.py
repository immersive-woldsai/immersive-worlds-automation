import random

TITLE_HOOKS = [
    "I Almost Sent This Text…",
    "This Message Changed Everything",
    "I Shouldn’t Have Said This",
    "This Conversation Still Haunts Me",
    "I Wasn’t Ready For This Reply",
    "This Text Hit Too Hard",
    "I Deleted This Message…",
]

SEARCH_KEYWORDS = [
    "text message story",
    "whatsapp chat",
    "relatable conversation",
    "deep thoughts",
    "psychology",
    "late night thoughts",
    "relationship text",
]

def generate_title():
    hook = random.choice(TITLE_HOOKS)
    kw = random.sample(SEARCH_KEYWORDS, 2)
    return f"{hook} | {kw[0]} {kw[1]}"
