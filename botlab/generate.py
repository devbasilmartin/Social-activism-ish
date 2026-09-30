"""Generate annotated mock comment threads for a post and store them locally."""

import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from pydantic import BaseModel

from .personas import PERSONAS, TECHNIQUES, VOICES, persona_by_id

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
    voice: str
    parent: int  # index of the comment being replied to, or -1 for top-level
    text: str
    techniques: list[str]
    annotation: str


class Thread(BaseModel):
    comments: list[Comment]


def _prompt(post: dict, personas: list[dict], n_comments: int) -> str:
    techniques = "\n".join(f"- {k}: {v}" for k, v in TECHNIQUES.items())
    voices = "\n".join(f"- {k}: {v}" for k, v in VOICES.items())
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
        f"Voices (writing registers):\n{voices}\n\n"
        f"Give each persona one voice and keep it consistent; spread the voices out so the "
        f"thread reads like different people. Set `voice` to the key used.\n\n"
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
    return thread_record(post, personas, response.parsed_output, response.model)


def thread_record(post: dict, personas: list[dict], parsed: Thread, model: str) -> dict:
    """Normalize a parsed Thread (from the API or written by a Claude Code session) into a stored record."""
    comments = []
    for i, c in enumerate(parsed.comments):
        comments.append(
            {
                **c.model_dump(),
                "parent": c.parent if 0 <= c.parent < i else -1,
                "techniques": [t for t in c.techniques if t in TECHNIQUES],
                "voice": c.voice if c.voice in VOICES else "",
            }
        )
    return {
        "thread_id": uuid.uuid4().hex[:12],
        "synthetic": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "post": post,
        "personas": [p["id"] for p in personas],
        "comments": comments,
    }


class VoiceVariant(BaseModel):
    voice: str
    text: str


class VoiceSet(BaseModel):
    core_message: str
    techniques: list[str]
    annotation: str
    variants: list[VoiceVariant]


VOICES_SYSTEM = SYSTEM + """

For this task, write ONE manipulative message responding to the post, then rewrite that same \
message in every listed voice. The point is to show readers that one talking point can be \
disguised as many different kinds of people."""


def _voices_prompt(post: dict) -> str:
    techniques = "\n".join(f"- {k}: {v}" for k, v in TECHNIQUES.items())
    voices = "\n".join(f"- {k}: {v}" for k, v in VOICES.items())
    return (
        f"Post from r/{post['subreddit']}:\nTitle: {post['title']}\n"
        f"Body: {post['selftext'] or '(link post)'}\n\n"
        f"Techniques:\n{techniques}\n\nVoices:\n{voices}\n\n"
        "State the core message in one plain sentence, list the techniques it uses, write a "
        "one-to-two sentence annotation of how it manipulates, then give one variant per voice."
    )


def generate_voices(client: anthropic.Anthropic, post: dict) -> dict:
    """One manipulative message about the post, rewritten in every voice."""
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium"},
        system=VOICES_SYSTEM,
        messages=[{"role": "user", "content": _voices_prompt(post)}],
        output_format=VoiceSet,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Model declined post {post['id']}: {response.stop_details}")
    return voiceset_record(post, response.parsed_output, response.model)


def voiceset_record(post: dict, vs: VoiceSet, model: str) -> dict:
    return {
        "set_id": uuid.uuid4().hex[:12],
        "synthetic": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "post": post,
        "core_message": vs.core_message,
        "techniques": [t for t in vs.techniques if t in TECHNIQUES],
        "annotation": vs.annotation,
        "variants": [v.model_dump() for v in vs.variants if v.voice in VOICES],
    }


def append_thread(thread: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a") as f:
        f.write(json.dumps(thread) + "\n")


def load_threads(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
