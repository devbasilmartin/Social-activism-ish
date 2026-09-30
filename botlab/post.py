"""Optionally publish stored threads to YOUR OWN bot subreddit.

Guardrails (intentional, not configurable from the CLI):
- Only the single subreddit named in BOTLAB_SUBREDDIT can be targeted.
- The authenticated account must be a moderator of that subreddit.
- Every comment starts with a [bot · persona · voice] header and ends with a disclosure footer.
- Posts name the source subreddit and headline but never link the real thread (no brigading),
  and never repost real users' comments.
- Threads are locked after posting so real people aren't mixed in with the bots.

Reddit requires approved API access (Responsible Builder Policy) for posting.
"""

import os

from .personas import persona_by_id

DISCLOSURE = (
    "\n\n---\n^(🤖 AI-generated bot comment from an educational demo on online manipulation. "
    "Technique: {techniques}.)"
)


def configured() -> bool:
    keys = ("BOTLAB_SUBREDDIT", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD")
    return all(os.environ.get(k) for k in keys)


def _reddit():
    import praw  # optional dependency: pip install .[post]

    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        username=os.environ["REDDIT_USERNAME"],
        password=os.environ["REDDIT_PASSWORD"],
        user_agent="botlab/0.1 (disclosed educational bot)",
    )


def _header(c: dict) -> str:
    try:
        ideology = persona_by_id(c["persona_id"])["ideology"]
    except KeyError:
        ideology = c["persona_id"]
    voice = f" · {c['voice'].replace('_', ' ')} voice" if c.get("voice") else ""
    return f"**[bot · {ideology}{voice}]**\n\n"


def _selftext(thread: dict, voice_set: dict | None) -> str:
    post = thread["post"]
    lines = [
        f"**Real headline from r/{post['subreddit']}:** {post['title']}",
        "",
        "Every comment below was written by an AI persona using a known manipulation tactic. "
        "Each one is labeled. This thread is locked; discuss it in the weekly thread.",
    ]
    if voice_set:
        lines += [
            "",
            "---",
            "",
            f"**One message, {len(voice_set['variants'])} voices.** Core message: *{voice_set['core_message']}* "
            f"(tactics: {', '.join(voice_set['techniques']) or 'n/a'})",
            "",
        ]
        lines += [f"> **{v['voice'].replace('_', ' ')}:** {v['text'].replace(chr(10), ' ')}\n" for v in voice_set["variants"]]
    return "\n".join(lines)[:39000]


def publish(thread: dict, voice_set: dict | None = None) -> str:
    target = os.environ.get("BOTLAB_SUBREDDIT")
    if not target:
        raise SystemExit("Set BOTLAB_SUBREDDIT to your own bot subreddit.")
    reddit = _reddit()
    sub = reddit.subreddit(target)
    me = reddit.user.me().name.lower()
    if me not in {m.name.lower() for m in sub.moderator()}:
        raise SystemExit(f"u/{me} is not a moderator of r/{target}; refusing to post.")

    submission = sub.submit(
        title=f"[BOT THREAD] {thread['post']['title']}"[:300],
        selftext=_selftext(thread, voice_set),
    )
    posted = []
    for c in thread["comments"]:
        body = _header(c) + c["text"] + DISCLOSURE.format(techniques=", ".join(c["techniques"]) or "none")
        parent = submission if c["parent"] == -1 else posted[c["parent"]]
        posted.append(parent.reply(body))
    submission.mod.lock()
    return submission.permalink


def draft(thread: dict, voice_set: dict | None = None) -> dict:
    """A single self-post you can paste into your subreddit by hand: intro, the bot thread as
    labeled quotes, and the voice set. Posting it yourself still carries the same labels."""
    comments = thread["comments"]

    def depth(i: int) -> int:
        d = 0
        while comments[i]["parent"] != -1:
            i, d = comments[i]["parent"], d + 1
        return d

    lines = [_selftext(thread, voice_set), "", "---", "", "**The bot thread:**", ""]
    for i, c in enumerate(comments):
        q = ">" * (depth(i) + 1) + " "
        text = _header(c) + c["text"] + f"\n\n*Tactic: {', '.join(c['techniques']) or 'none'}*"
        lines += [q + line if line else q.rstrip() for line in text.split("\n")] + [""]
    lines += ["---", "", "^(🤖 Everything quoted above is AI-generated, for a demo on online manipulation.)"]
    body = "\n".join(lines).replace("This thread is locked; discuss it in the weekly thread.", "Discuss below.")
    return {"title": f"[BOT THREAD] {thread['post']['title']}"[:300], "body": body[:39000]}


QUIZ_BODY = (
    "Some of the numbered comments in this image are from real people on r/{sub} (names redacted). "
    "The rest were written by AI personas using manipulation tactics. Guess in the comments which "
    "numbers are real, then check the pinned answer key."
)


def quiz_title(thread: dict) -> str:
    return f"[SPOT THE BOT] Which of these comments are real? \"{thread['post']['title']}\""[:300]


def publish_quiz(thread: dict, image: str, answers: str) -> str:
    """Image post for guessing: left unlocked, answer key pinned as a spoiler comment."""
    target = os.environ["BOTLAB_SUBREDDIT"]
    reddit = _reddit()
    sub = reddit.subreddit(target)
    me = reddit.user.me().name.lower()
    if me not in {m.name.lower() for m in sub.moderator()}:
        raise SystemExit(f"u/{me} is not a moderator of r/{target}; refusing to post.")
    submission = sub.submit_image(quiz_title(thread), image)
    key = submission.reply(QUIZ_BODY.format(sub=thread["post"]["subreddit"]) + "\n\n" + answers)
    key.mod.distinguish(sticky=True)
    return submission.permalink
