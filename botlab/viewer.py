"""Render stored threads as a self-contained, annotated HTML page."""

import html
from pathlib import Path

from .personas import TECHNIQUES, persona_by_id

CSS = """
:root { --bg:#f6f7f8; --card:#fff; --text:#1a1a1b; --muted:#6b6f73; --line:#e3e5e8;
        --bot:#d93a00; --tag:#fff4e5; --tagtext:#8a4b00; --note:#eef4ff; --notetext:#1d3f7a; }
@media (prefers-color-scheme: dark) { :root { --bg:#111214; --card:#1b1c1f; --text:#e6e6e6;
        --muted:#9aa0a6; --line:#2c2e33; --tag:#3a2a12; --tagtext:#ffcf8a; --note:#15233d; --notetext:#b7cdf5; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font:15px/1.5 system-ui, sans-serif; }
main { max-width:820px; margin:0 auto; padding:24px 16px 64px; }
.banner { background:var(--bot); color:#fff; padding:12px 16px; border-radius:8px; margin-bottom:24px; }
.post { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:16px; margin-bottom:32px; }
.post h2 { margin:4px 0 8px; font-size:18px; }
.meta { color:var(--muted); font-size:13px; }
.comment { border-left:2px solid var(--line); padding:8px 0 4px 12px; margin-top:12px; }
.who { font-size:13px; color:var(--muted); }
.badge { background:var(--bot); color:#fff; font-size:11px; font-weight:600; padding:1px 6px; border-radius:4px; margin-right:6px; }
.text { margin:4px 0; white-space:pre-wrap; overflow-wrap:anywhere; }
.tags span { display:inline-block; background:var(--tag); color:var(--tagtext); font-size:12px; padding:1px 8px; border-radius:10px; margin:2px 4px 2px 0; cursor:help; }
.note { background:var(--note); color:var(--notetext); font-size:13px; padding:6px 10px; border-radius:6px; margin:4px 0; }
details summary { cursor:pointer; color:var(--muted); font-size:13px; }
"""


def _comment_html(comments: list[dict], idx: int) -> str:
    c = comments[idx]
    persona = persona_by_id(c["persona_id"]) if c["persona_id"] else {"ideology": "?"}
    tags = "".join(
        f'<span title="{html.escape(TECHNIQUES[t])}">{html.escape(t.replace("_", " "))}</span>'
        for t in c["techniques"]
    )
    children = "".join(_comment_html(comments, j) for j, k in enumerate(comments) if k["parent"] == idx)
    return (
        '<div class="comment">'
        f'<div class="who"><span class="badge">BOT</span>u/{html.escape(c["persona_id"])} · {html.escape(persona["ideology"])}</div>'
        f'<p class="text">{html.escape(c["text"])}</p>'
        f'<div class="tags">{tags}</div>'
        f'<details><summary>How this manipulates</summary><div class="note">{html.escape(c["annotation"])}</div></details>'
        f"{children}</div>"
    )


def render(threads: list[dict], out: Path) -> None:
    sections = []
    for t in threads:
        post = t["post"]
        link = f' · <a href="{html.escape(post["permalink"])}">original post</a>' if post.get("permalink") else ""
        roots = "".join(_comment_html(t["comments"], i) for i, c in enumerate(t["comments"]) if c["parent"] == -1)
        sections.append(
            f'<section class="post"><div class="meta">r/{html.escape(post["subreddit"])}{link}</div>'
            f'<h2>{html.escape(post["title"])}</h2>{roots}</section>'
        )
    out.write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Bot Lab Threads</title><style>{CSS}</style></head><body><main>"
        '<div class="banner"><strong>Every comment on this page was written by an AI bot.</strong> '
        "The posts are real; the replies are synthetic, generated to show how easily bots can "
        "produce persuasive, manipulative political comments. Tap a comment's tags or "
        "\"How this manipulates\" to see the technique.</div>"
        + "".join(sections)
        + "</main></body></html>"
    )
