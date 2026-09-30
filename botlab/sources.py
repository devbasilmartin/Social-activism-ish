"""Fetch real Reddit posts to use as prompts for the mock threads.

Uses Reddit's public, read-only JSON listing endpoints. No login is needed and
nothing is written back to Reddit.
"""

import base64
import json
import os
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path

USER_AGENT = "botlab-research/0.1 (educational bot-manipulation demo)"


def fetch_posts(subreddit: str, listing: str = "top", t: str = "day", limit: int = 5) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/{listing}.json?t={t}&limit={limit}"
    payload = _get(url)
    posts = [_post(c["data"]) for c in payload["data"]["children"] if not c["data"].get("stickied")]
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


@lru_cache(maxsize=1)
def _oauth_token() -> str | None:
    """App-only, read-only OAuth token. Reddit blocks logged-out JSON from most cloud IPs,
    so when REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET are set we go through the official API."""
    cid, secret = os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        return None
    req = urllib.request.Request(
        "https://www.reddit.com/api/v1/access_token",
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={
            "User-Agent": USER_AGENT,
            "Authorization": "Basic " + base64.b64encode(f"{cid}:{secret}".encode()).decode(),
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)["access_token"]


def _get(url: str) -> object:
    headers = {"User-Agent": USER_AGENT}
    token = _oauth_token()
    if token:
        url = url.replace("https://www.reddit.com/", "https://oauth.reddit.com/").replace("/.json", "/best.json")
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def fetch_front_page(limit: int = 10) -> list[dict]:
    """Posts currently on the logged-out front page (r/popular-style mix)."""
    payload = _get(f"https://www.reddit.com/.json?limit={limit}")
    return [_post(c["data"]) for c in payload["data"]["children"] if not c["data"].get("stickied")]


def fetch_comments(post_id: str, limit: int = 20, depth: int = 3) -> list[dict]:
    """Top comments for a post, flattened in reading order with `parent` indexes like generated threads."""
    payload = _get(f"https://www.reddit.com/comments/{post_id}.json?sort=top&limit={limit}&depth={depth}")
    out: list[dict] = []

    def walk(children: list, parent: int) -> None:
        for child in children:
            if child["kind"] != "t1" or len(out) >= limit:
                continue
            d = child["data"]
            if d.get("body") in ("[deleted]", "[removed]"):
                continue
            out.append({"score": d.get("score"), "parent": parent, "text": d["body"]})
            replies = d.get("replies")
            if replies:
                walk(replies["data"]["children"], len(out) - 1)

    walk(payload[1]["data"]["children"], -1)
    return out


def _post(d: dict) -> dict:
    return {
        "id": d["id"],
        "subreddit": d["subreddit"],
        "title": d["title"],
        "selftext": d.get("selftext", "")[:2000],
        "url": d.get("url"),
        "permalink": "https://www.reddit.com" + d["permalink"],
    }


def sample_front_page(n_posts: int = 10, n_comments: int = 20) -> list[dict]:
    posts = fetch_front_page(n_posts)
    for p in posts:
        p["comments"] = fetch_comments(p["id"], n_comments)
    return posts
