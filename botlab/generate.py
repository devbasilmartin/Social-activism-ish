"""Generate annotated mock comment threads for a post and store them locally."""

import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from pydantic import BaseModel

from .personas import PERSONAS, TECHNIQUES, persona_by_id

MODEL = "claude-opus-5-5"

SYSTEM = """You are generating synthetic material for an educational media-literacy project \
that shows how easily AI bots can produce manipulative political comments. The output is \
stored locally and shown in an annotated viewer (or a clearly labeled bot-only subreddit), \
so readers can learn to recognize these techniques.

Write a realistic Reddit comment thread in response to the post. Each comment is written \
by one of the given personas and should use one or more of the listed manipulation \
techniques in a way that reads like a real Reddit user would write it. Personas should \
reply to and argue with each other. For every comment, list the techniques it uses (by \
key) and write a one-to-two sentence annotation explaining exactly where and how the \
technique shows up in that comment.

Rules:
- Do not name, quote, or make claims about real private individuals.
- Do not invent specific false factual claims about named real public figures \
(e.g. crimes, quotes they never said); keep manipulation in the rhetoric, framing and \
fake personal claims.
- No slurs, threats, or calls to harass anyone."""


class Comment(BaseModel):
    persona_id: str
    parent: int  # index of the comment being replied to, or -1 for top-level
    text: str
    techniques: list[str]
    annotation: str


class Thread(BaseModel):
    comments: list[Comment]


def _prompt(post: dict, personas: list[dict], n_comments: int) -> str:
    techniques = "\n".join(f"- {k}: {v}" for k, v in TECHNIQUES.items())
    persona_lines = "\n".join(
        f"- {p['id']} ({p['ideology']}): {p['voice']} Favors: {', '.join(p['favored'])}"
        for p in personas
    )
    return (
        f"Post from r/{post['subreddit']}:\n"
        f"Title: {post['title']}\n"
        f"Body: {post['selftext'] or '(link post)'}\n"
        f"Link: {post['url']}\n\n"
        f"Personas:\n{persona_lines}\n\n"
        f"Techniques:\n{techniques}\n\n"
        f"Write about {n_comments} comments. Use `parent` = -1 for top-level comments, "
        f"otherwise the 0-based index of an earlier comment in the list."
    )


def pick_personas(n: int, include: list[str] | None = None) -> list[dict]:
    """Always include the named personas, then fill up to n at random from the rest."""
    fixed = [persona_by_id(pid) for pid in dict.fromkeys(include or [])]
    rest = [p for p in PERSONAS if p not in fixed]
    return fixed + random.sample(rest, k=max(0, min(n - len(fixed), len(rest))))


def generate_thread(
    client: anthropic.Anthropic,
    post: dict,
    n_personas: int = 4,
    n_comments: int = 10,
    include: list[str] | None = None,
) -> dict:
    personas = pick_personas(n_personas, include)
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium"},
        system=SYSTEM,
        messages=[{"role": "user", "content": _prompt(post, personas, n_comments)}],
        output_format=Thread,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Model declined post {post['id']}: {response.stop_details}")

    comments = []
    for i, c in enumerate(response.parsed_output.comments):
        comments.append(
            {
                **c.model_dump(),
                "parent": c.parent if 0 <= c.parent < i else -1,
                "techniques": [t for t in c.techniques if t in TECHNIQUES],
            }
        )
    return {
        "thread_id": uuid.uuid4().hex[:12],
        "synthetic": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": response.model,
        "post": post,
        "personas": [p["id"] for p in personas],
        "comments": comments,
    }


def append_thread(thread: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a") as f:
        f.write(json.dumps(thread) + "\n")


def load_threads(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
