import random

TOPICS = [
    # (topic_name, weight, hooks[], confessions[], twists[], cliffs[])
    ("relationship_ghosting", 10,
     ["They replied... but it felt colder than silence.", "I saw their name and my stomach dropped.", "I didn't expect that message."],
     ["I wasn't asking for love. Just clarity.", "I keep forgiving what I shouldn't.", "I hate how fast I miss people."],
     ["Maybe you're not 'too much'. Maybe they're not enough.", "Sometimes closure is just disappointment with a caption."],
     ["Don't ask me who. You'll know."]),

    ("self_respect_boundaries", 9,
     ["I finally said no... and everything changed.", "This is what self-respect looks like.", "I stopped explaining myself."],
     ["I was shrinking to be easier to love.", "I kept lowering my standards to avoid being alone."],
     ["The right people don't need you to beg.", "Peace feels boring when you're addicted to chaos."],
     ["I'm not ready to tell you what happened next."]),

    ("overthinking_anxiety", 8,
     ["My brain won't stop replaying it.", "It's 2 AM and I'm still thinking about it.", "One sentence ruined my whole night."],
     ["I overanalyze because surprises hurt.", "I don't trust calm. I wait for the twist."],
     ["Maybe you're not anxious. Maybe you're unsafe.", "Your body remembers what you ignore."],
     ["If I say the last part, you'll understand everything."]),

    ("psychology_attachment", 8,
     ["People don't leave suddenly. They leave quietly first.", "Attachment is a wild thing.", "This is why you can't let go."],
     ["I confuse intensity with love.", "I chase what won't choose me."],
     ["Avoidants fear closeness. Anxious fear distance.", "Familiar pain feels safer than unknown peace."],
     ["This is the part nobody teaches you."]),

    ("late_night_confession", 7,
     ["I almost sent this... then I panicked.", "This is embarrassing to admit.", "I typed it. Deleted it. Typed it again."],
     ["I miss the idea more than the person.", "I hate how hopeful I get."],
     ["Sometimes 'maybe' is just a soft no.", "If they wanted to, you wouldn't be guessing."],
     ["I'm deleting this soon."]),

    ("friendship_betrayal", 6,
     ["It hurts more when it's a friend.", "I didn't expect it from them.", "That laugh felt fake."],
     ["I defended them. They never did the same.", "I ignored the red flags because I wanted it to work."],
     ["Loyalty isn't loud. It's consistent.", "You outgrow people when you stop accepting crumbs."],
     ["Don't make me say their name."]),
]

def weighted_choice():
    total = sum(w for _, w, *_ in TOPICS)
    r = random.uniform(0, total)
    acc = 0
    for item in TOPICS:
        acc += item[1]
        if r <= acc:
            return item
    return TOPICS[0]

def generate_chat_script():
    topic, _w, hooks, confs, twists, cliffs = weighted_choice()
    hook = random.choice(hooks)
    conf = random.choice(confs)
    twist = random.choice(twists)
    cliff = random.choice(cliffs)

    return topic, hook, conf, twist, cliff
