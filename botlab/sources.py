"""Fetch real Reddit posts to use as prompts for the mock threads.

Uses Reddit's public, read-only JSON listing endpoints. No login is needed and
nothing is written back to Reddit.
"""

import json
import urllib.request
from pathlib import Path

USER_AGENT = "botlab-research/0.1 (educational bot-manipulation demo)"


def fetch_posts(subreddit: str, listing: str = "top", t: str = "day", limit: int = 5) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/{listing}.json?t={t}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.load(resp)
    posts = []
    for child in payload["data"]["children"]:
        d = child["data"]
        if d.get("stickied"):
            continue
        posts.append(
            {
                "id": d["id"],
                "subreddit": d["subreddit"],
                "title": d["title"],
                "selftext": d.get("selftext", "")[:2000],
                "url": d.get("url"),
                "permalink": "https://www.reddit.com" + d["permalink"],
            }
        )
    return posts


def load_posts(path: Path) -> list[dict]:
    """Load posts from a local JSON file: a list of {id, title, selftext?, url?, subreddit?}."""
    posts = json.loads(path.read_text())
    for i, p in enumerate(posts):
        p.setdefault("id", f"local{i}")
        p.setdefault("subreddit", "local")
        p.setdefault("selftext", "")
        p.setdefault("url", None)
        p.setdefault("permalink", None)
    return posts
