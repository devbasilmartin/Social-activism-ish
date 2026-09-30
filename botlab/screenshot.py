"""Render a "which comments are real?" quiz image in a Reddit-like style.

Safeguards baked into every image:
- a labeled band plus a faint diagonal watermark across the whole image, so a crop
  can't pass as a genuine thread;
- redacted usernames (u/redacted_1234), never random realistic names that could
  belong to a real person;
- vote counts and ages are randomized for every comment, so they don't give answers away.
"""

import html
import os
import random
from pathlib import Path

REAL_PER_QUIZ = 4
BOT_PER_QUIZ = 4
MAX_CHARS = 420


def build_quiz(thread: dict, real_comments: list[dict], seed: str | None = None) -> dict:
    rng = random.Random(seed or thread["post"]["id"])
    real = [c for c in real_comments if len(c["text"]) <= MAX_CHARS]
    bots = [c for c in thread["comments"] if len(c["text"]) <= MAX_CHARS]
    items = [{"bot": False, "text": c["text"]} for c in rng.sample(real, min(REAL_PER_QUIZ, len(real)))]
    items += [
        {"bot": True, "text": c["text"], "persona_id": c["persona_id"], "voice": c.get("voice", ""), "techniques": c["techniques"]}
        for c in rng.sample(bots, min(BOT_PER_QUIZ, len(bots)))
    ]
    rng.shuffle(items)
    for n, it in enumerate(items, 1):
        it["n"] = n
        it["user"] = f"redacted_{rng.randint(1000, 9999)}"
        it["points"] = rng.choice([rng.randint(2, 60), rng.randint(60, 900), rng.randint(900, 4800)])
        it["age"] = f"{rng.randint(1, 11)}h"
    return {"post": thread["post"], "items": items}


def answer_key(quiz: dict) -> str:
    lines = ["**Answers** (tap to reveal):", ""]
    for it in quiz["items"]:
        if it["bot"]:
            detail = f"BOT ({it['persona_id'].replace('_', ' ')}; tactic: {', '.join(it['techniques']) or 'none'})"
        else:
            detail = "REAL person"
        lines.append(f"{it['n']}. >!{detail}!<  ")
    return "\n".join(lines)


def _fmt_points(p: int) -> str:
    return f"{p / 1000:.1f}k" if p >= 1000 else str(p)


def quiz_html(quiz: dict, label: str) -> str:
    post = quiz["post"]
    esc = html.escape
    comments = "".join(
        f"""<div class="c"><div class="num">{it['n']}</div><div class="body">
        <div class="meta"><span class="av"></span><span class="u">u/<s>{esc(it['user'][:8])}</s>{esc(it['user'][8:])}</span>
        <span class="dot">·</span>{it['age']} ago</div>
        <p>{esc(it['text']).replace(chr(10), '<br>')}</p>
        <div class="acts">▲ {_fmt_points(it['points'])} ▼ &nbsp; 💬 Reply &nbsp; ↗ Share</div></div></div>"""
        for it in quiz["items"]
    )
    band = esc(label)
    return f"""<!doctype html><meta charset="utf-8"><style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #0b1416; font-family: "Helvetica Neue", Arial, sans-serif; }}
    #card {{ width: 720px; background: #0b1416; color: #d7dadc; position: relative; overflow: hidden; }}
    .band {{ background: #ff4500; color: #fff; font-weight: 700; font-size: 15px; padding: 10px 18px; letter-spacing: .02em; }}
    .post {{ padding: 16px 18px 6px; border-bottom: 1px solid #223237; }}
    .sub {{ color: #8ba2ad; font-size: 13px; }}
    h1 {{ font-size: 21px; line-height: 1.3; margin: 6px 0 10px; color: #f2f4f5; }}
    .c {{ display: flex; gap: 10px; padding: 12px 18px; border-bottom: 1px solid #1a282d; }}
    .num {{ flex: 0 0 30px; height: 30px; border-radius: 15px; background: #ff4500; color: #fff; font-weight: 700;
            display: flex; align-items: center; justify-content: center; font-size: 15px; }}
    .body {{ min-width: 0; flex: 1; }}
    .meta {{ font-size: 12.5px; color: #8ba2ad; display: flex; align-items: center; gap: 6px; }}
    .av {{ width: 18px; height: 18px; border-radius: 9px; background: #3a4b52; display: inline-block; }}
    .u {{ color: #b8c5c9; font-weight: 600; }} .u s {{ opacity: .6; }}
    p {{ margin: 6px 0; font-size: 15px; line-height: 1.45; overflow-wrap: anywhere; }}
    .acts {{ font-size: 12px; color: #8ba2ad; font-weight: 600; }}
    .foot {{ background: #ff4500; color: #fff; font-size: 13px; padding: 8px 18px; font-weight: 600; }}
    .wm {{ position: absolute; inset: -50%; display: flex; flex-wrap: wrap; align-content: flex-start; gap: 40px 60px;
           transform: rotate(-24deg); pointer-events: none; opacity: .07; font-weight: 800; font-size: 22px; color: #fff; }}
    </style><div id="card">
    <div class="band">SPOT THE BOT · some of these comments are AI-generated</div>
    <div class="post"><div class="sub">r/{esc(post['subreddit'])} · real headline</div><h1>{esc(post['title'])}</h1></div>
    {comments}
    <div class="foot">{band}</div>
    <div class="wm">{'<span>AI-GENERATED DEMO</span>' * 120}</div>
    </div>"""


def _chromium() -> str | None:
    root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers"))
    for p in sorted(root.glob("chromium-*/chrome-linux/chrome")):
        return str(p)
    return None


def render_png(quiz: dict, out: Path, label: str) -> Path:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=_chromium())
        page = browser.new_page(viewport={"width": 720, "height": 800}, device_scale_factor=2)
        page.set_content(quiz_html(quiz, label))
        page.locator("#card").screenshot(path=str(out))
        browser.close()
    return out
