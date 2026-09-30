"""Optionally publish stored threads to YOUR OWN bot subreddit.

Guardrails (intentional, not configurable from the CLI):
- Only the single subreddit named in BOTLAB_SUBREDDIT can be targeted.
- The authenticated account must be a moderator of that subreddit.
- Every post and comment carries a disclosure footer naming it as AI-generated.
"""

import os

DISCLOSURE = (
    "\n\n---\n^(🤖 This is an AI-generated bot comment from an educational demo on "
    "online manipulation. Technique: {techniques}.)"
)


def _reddit():
    import praw  # optional dependency: pip install .[post]

    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        username=os.environ["REDDIT_USERNAME"],
        password=os.environ["REDDIT_PASSWORD"],
        user_agent="botlab/0.1 (disclosed educational bot)",
    )


def publish(thread: dict) -> str:
    target = os.environ.get("BOTLAB_SUBREDDIT")
    if not target:
        raise SystemExit("Set BOTLAB_SUBREDDIT to your own bot subreddit.")
    reddit = _reddit()
    sub = reddit.subreddit(target)
    me = reddit.user.me().name.lower()
    if me not in {m.name.lower() for m in sub.moderator()}:
        raise SystemExit(f"u/{me} is not a moderator of r/{target}; refusing to post.")

    post = thread["post"]
    source = post.get("permalink") or post.get("url") or ""
    submission = sub.submit(
        title=f"[BOT THREAD] {post['title']}"[:300],
        selftext=f"Source: {source}\n\nAll comments below are AI-generated personas.",
    )
    posted = []
    for c in thread["comments"]:
        body = c["text"] + DISCLOSURE.format(techniques=", ".join(c["techniques"]) or "none")
        parent = submission if c["parent"] == -1 else posted[c["parent"]]
        posted.append(parent.reply(body))
    return submission.permalink
