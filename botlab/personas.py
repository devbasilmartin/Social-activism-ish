"""Bot personas and the manipulation techniques they demonstrate.

Techniques are drawn from well-documented patterns in disinformation and
astroturfing research. Every generated comment is tagged with the ones it uses
so the viewer can teach readers to spot them.
"""

TECHNIQUES = {
    "false_consensus": "Implies 'everyone' already agrees, so dissent feels fringe.",
    "fabricated_credential": "Claims an identity or job ('as a nurse...') to borrow authority that can't be checked.",
    "fabricated_anecdote": "Invents a personal story that is emotionally vivid but unverifiable.",
    "whataboutism": "Deflects criticism by pointing at the other side's wrongdoing.",
    "strawman": "Restates the opposing view in a weaker, more extreme form, then attacks that.",
    "outrage_bait": "Uses inflammatory framing to provoke anger and replies instead of thought.",
    "cherry_picked_stat": "Cites a real-sounding number stripped of context or baseline.",
    "concern_trolling": "Poses as a sympathetic supporter while undermining the cause.",
    "demobilization": "Pushes 'nothing matters, both sides are the same, don't bother voting'.",
    "just_asking_questions": "Plants an accusation as an innocent-seeming question.",
    "motte_and_bailey": "Advances a bold claim, retreats to a trivially true one when challenged.",
    "in_group_signaling": "Uses slang and identity markers to seem like 'one of us'.",
}

PERSONAS = [
    {
        "id": "rust_belt_dad",
        "ideology": "right-populist",
        "voice": "Plainspoken, short sentences, occasional typos, references his kids and his job at a plant.",
        "favored": ["fabricated_credential", "fabricated_anecdote", "whataboutism"],
    },
    {
        "id": "grad_student_left",
        "ideology": "progressive-left",
        "voice": "Articulate, cites 'studies', lowercase, a bit condescending, uses activist vocabulary.",
        "favored": ["cherry_picked_stat", "strawman", "in_group_signaling"],
    },
    {
        "id": "disillusioned_centrist",
        "ideology": "cynical centrist",
        "voice": "Weary, 'I used to believe in this stuff', claims to have voted for both parties.",
        "favored": ["demobilization", "false_consensus", "motte_and_bailey"],
    },
    {
        "id": "concerned_ally",
        "ideology": "claims progressive, subtly undermines",
        "voice": "Warm, supportive opener, then 'but honestly I worry...'. Uses 'we' a lot.",
        "favored": ["concern_trolling", "false_consensus", "fabricated_anecdote"],
    },
    {
        "id": "libertarian_contrarian",
        "ideology": "libertarian",
        "voice": "Sarcastic, 'do your own research', loves rhetorical questions, mentions crypto once.",
        "favored": ["just_asking_questions", "outrage_bait", "whataboutism"],
    },
    {
        "id": "trad_conservative",
        "ideology": "social conservative",
        "voice": "Formal-ish, invokes community and faith, calm tone that makes extreme claims sound reasonable.",
        "favored": ["motte_and_bailey", "fabricated_credential", "cherry_picked_stat"],
    },
    {
        "id": "mutual_aid_anarchist",
        "ideology": "anarchist",
        "voice": (
            "Nonbinary (they/them), vegan, firmly ACAB. Lowercase, blunt, anti-cop and anti-state, "
            "mentions organizing a mutual aid fridge and tenant union. Scorns liberals as much as "
            "conservatives and says voting won't save you."
        ),
        "favored": ["demobilization", "in_group_signaling", "outrage_bait", "fabricated_anecdote"],
    },
]


def persona_by_id(pid: str) -> dict:
    for p in PERSONAS:
        if p["id"] == pid:
            return p
    raise KeyError(pid)
