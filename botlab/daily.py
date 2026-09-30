"""One unattended run: sample real posts, generate bot threads and voice sets, render the
Spot the Bot page, and post to your own bot subreddit (auto mode) or draft it for you.

Two ways to generate:
- API: `run()` calls Claude through the Anthropic API (needs ANTHROPIC_API_KEY).
- Claude Code plan, no API key: `prepare()` writes today's instructions to task.md, the
  Claude Code session writes authored.json itself, then `finish()` validates and builds.
"""

import json
import os
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ValidationError

from . import generate, post, screenshot, sources, viewer
from .personas import persona_by_id

TASK_FILE, AUTHORED_FILE = "task.md", "authored.json"


def _day(out_dir: Path) -> Path:
    day = out_dir / date.today().isoformat()
    day.mkdir(parents=True, exist_ok=True)
    return day


def _mode(mode: str | None) -> str:
    mode = (mode or os.environ.get("BOTLAB_MODE") or "draft").lower()
    if mode == "auto" and not post.configured():
        print("auto mode, but Reddit posting isn't configured (needs approved API access); drafting instead.")
        mode = "draft"
    return mode


def _sample(day: Path, subreddit: str, n_posts: int, n_comments: int) -> list[dict]:
    print(f"sampling r/{subreddit} ...")
    samples = sources.sample(subreddit, n_posts, n_comments)
    (day / "samples.json").write_text(json.dumps(samples, indent=2))
    return samples


def run(
    subreddit: str = "politics",
    n_posts: int = 3,
    n_comments: int = 20,
    n_publish: int = 1,
    out_dir: Path = Path("data/daily"),
    include: list[str] | None = None,
    mode: str | None = None,
) -> Path:
    """API path. mode: 'auto' posts to your subreddit (falls back to draft if posting isn't
    configured); 'draft' writes the post for you to paste. Defaults to $BOTLAB_MODE, then 'draft'."""
    import anthropic

    mode = _mode(mode)
    day = _day(out_dir)
    samples = _sample(day, subreddit, n_posts, n_comments)
    client = anthropic.Anthropic()
    threads, voice_sets = [], []
    for p in samples:
        try:
            threads.append(generate.generate_thread(client, p, include=include))
            voice_sets.append(generate.generate_voices(client, p))
            print(f"  generated: {p['title'][:60]}")
        except RuntimeError as e:
            print(f"  skip: {e}")
    return _build(day, subreddit, samples, threads, voice_sets, n_publish, mode)


# --- Claude Code plan path ------------------------------------------------------


class _AuthoredThread(BaseModel):
    personas: list[str]
    comments: list[generate.Comment]


class _Authored(BaseModel):
    threads: dict[str, _AuthoredThread]
    voices: dict[str, generate.VoiceSet]


def prepare(
    subreddit: str = "politics",
    n_posts: int = 3,
    n_comments: int = 20,
    out_dir: Path = Path("data/daily"),
    include: list[str] | None = None,
    n_bot_comments: int = 10,
) -> Path:
    """Sample posts and write task.md: the exact instructions the API path would send,
    for the Claude Code session to follow and answer in authored.json."""
    day = _day(out_dir)
    samples = _sample(day, subreddit, n_posts, n_comments)
    parts = [
        "# Today's Spot the Bot task",
        "",
        "You are the generator for this run. Follow the rules below, then write your output to "
        f"`{day / AUTHORED_FILE}` as JSON in exactly this shape:",
        "",
        "```json",
        '{"threads": {"<post id>": {"personas": ["<persona id>", ...],',
        '              "comments": [{"persona_id": "...", "voice": "...", "parent": -1,',
        '                            "text": "...", "techniques": ["..."], "annotation": "..."}]}},',
        ' "voices":  {"<post id>": {"core_message": "...", "techniques": ["..."], "annotation": "...",',
        '              "variants": [{"voice": "...", "text": "..."}]}}}',
        "```",
        "",
        "Include one entry in `threads` and one in `voices` for every post below, keyed by its post id.",
        f"Then run `botlab daily --step finish`.",
        "",
        "## Rules",
        "",
        generate.SYSTEM,
        "",
        "## Many voices task (for `voices`)",
        "",
        generate.VOICES_SYSTEM[len(generate.SYSTEM):].strip(),
    ]
    for p in samples:
        personas = generate.pick_personas(4, include)
        parts += [
            "",
            f"## Post `{p['id']}`",
            "",
            f"### Thread (use exactly these personas: {', '.join(x['id'] for x in personas)})",
            "",
            generate._prompt(p, personas, n_bot_comments),
            "",
            "### Many voices",
            "",
            generate._voices_prompt(p),
        ]
    task = day / TASK_FILE
    task.write_text("\n".join(parts) + "\n")
    print(f"task written: {task}")
    return task


def finish(
    subreddit: str = "politics",
    n_publish: int = 1,
    out_dir: Path = Path("data/daily"),
    mode: str | None = None,
) -> Path:
    """Validate the session-authored JSON and build everything from it."""
    mode = _mode(mode)
    day = _day(out_dir)
    samples = json.loads((day / "samples.json").read_text())
    try:
        authored = _Authored.model_validate_json((day / AUTHORED_FILE).read_text())
    except (FileNotFoundError, ValidationError) as e:
        raise SystemExit(f"{day / AUTHORED_FILE} is missing or doesn't match the shape in {TASK_FILE}:\n{e}")
    threads, voice_sets = [], []
    for p in samples:
        t = authored.threads.get(p["id"])
        if t:
            personas = []
            for pid in t.personas:
                try:
                    personas.append(persona_by_id(pid))
                except KeyError:
                    pass
            threads.append(generate.thread_record(p, personas, generate.Thread(comments=t.comments), "claude-code-session"))
        vs = authored.voices.get(p["id"])
        if vs:
            voice_sets.append(generate.voiceset_record(p, vs, "claude-code-session"))
        if not (t and vs):
            print(f"  missing output for post {p['id']}: {p['title'][:60]}")
    return _build(day, subreddit, samples, threads, voice_sets, n_publish, mode)


# --- shared tail ------------------------------------------------------------------


def _build(
    day: Path,
    subreddit: str,
    samples: list[dict],
    threads: list[dict],
    voice_list: list[dict],
    n_publish: int,
    mode: str,
) -> Path:
    for t in threads:
        generate.append_thread(t, day / "threads.jsonl")
    for vs in voice_list:
        generate.append_thread(vs, day / "voices.jsonl")
    voice_sets = {vs["post"]["id"]: vs for vs in voice_list}
    print(f"{len(threads)} threads, {len(voice_sets)} voice sets")

    chosen = threads[:n_publish]
    real_by_post = {p["id"]: p.get("comments", []) for p in samples}
    sub_label = f"r/{os.environ['BOTLAB_SUBREDDIT']}" if os.environ.get("BOTLAB_SUBREDDIT") else "Spot the Bot"
    quizzes = {}
    for t in chosen:
        q = screenshot.build_quiz(t, real_by_post.get(t["post"]["id"], []))
        if not any(not it["bot"] for it in q["items"]):
            continue  # no real comments to mix in
        img = screenshot.render_png(q, day / f"quiz-{t['post']['id']}.png",
                                    f"Guess in the comments: which numbers are real people? · {sub_label}")
        quizzes[t["post"]["id"]] = (str(img), screenshot.answer_key(q))
        print(f"quiz image: {img}")

    drafts = []
    if mode == "draft":
        drafts = [post.draft(t, voice_sets.get(t["post"]["id"])) for t in chosen]
        for t, dr in zip(chosen, drafts):
            if t["post"]["id"] in quizzes:
                img, key = quizzes[t["post"]["id"]]
                dr["quiz"] = {"title": post.quiz_title(t), "image": img,
                              "comment": post.QUIZ_BODY.format(sub=t["post"]["subreddit"]) + "\n\n" + key}
        md = "\n\n=====\n\n".join(f"TITLE: {d['title']}\n\n{d['body']}" for d in drafts)
        (day / "draft.md").write_text(md)
        print(f"drafted {len(drafts)} post(s): {day / 'draft.md'}")

    page = day / "spot-the-bot.html"
    viewer.render(threads, page, samples, fragment=True, voice_sets=list(voice_sets.values()), drafts=drafts,
                  note=f"Generated automatically on {day.name} from the top posts of r/{subreddit}.")
    print(f"page: {page}")

    if mode == "auto":
        for t in chosen:
            print("posted:", post.publish(t, voice_sets.get(t["post"]["id"])))
            if t["post"]["id"] in quizzes:
                print("posted quiz:", post.publish_quiz(t, *quizzes[t["post"]["id"]]))
    return page
