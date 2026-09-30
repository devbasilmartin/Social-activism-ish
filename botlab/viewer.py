"""Render stored threads as a self-contained, annotated HTML page.

Each post gets up to three tabs:
- Guess: real and bot comments shuffled together; the reader labels each one
  before the answer (and, for bots, the manipulation technique) is revealed.
- Bot thread: the synthetic thread with techniques and annotations.
- Real thread: the real top comments, when samples for that post were saved.
"""

import html
import json
import random
from pathlib import Path

from .personas import PERSONAS, TECHNIQUES

GUESS_PER_SIDE = 5

CSS = """
/* Layout: one narrow reading column; each post is a case file with tabs. */
:root {
  --paper: #f3f5f7; --card: #ffffff; --ink: #17202a; --muted: #5c6773; --rule: #d9dee4;
  --bot: #c2410c; --bot-soft: #fdeee4; --human: #15803d; --human-soft: #e6f4ea;
  --note: #eef2fb; --note-ink: #273a63; --focus: #2563eb;
  --display: "Barlow Condensed", "Arial Narrow", sans-serif;
  --body: "Public Sans", system-ui, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --paper: #0f1418; --card: #182027; --ink: #e5e9ed; --muted: #97a3ae; --rule: #2a343d;
  --bot: #fb923c; --bot-soft: #3a2415; --human: #4ade80; --human-soft: #15301f;
  --note: #1a2438; --note-ink: #c3d2f2; --focus: #60a5fa; color-scheme: dark; } }
:root[data-theme="dark"] {
  --paper: #0f1418; --card: #182027; --ink: #e5e9ed; --muted: #97a3ae; --rule: #2a343d;
  --bot: #fb923c; --bot-soft: #3a2415; --human: #4ade80; --human-soft: #15301f;
  --note: #1a2438; --note-ink: #c3d2f2; --focus: #60a5fa; color-scheme: dark; }
* { box-sizing: border-box; }
body { background: var(--paper); color: var(--ink); font: 15px/1.55 var(--body); }
main { max-width: 760px; margin: 0 auto; padding: 24px 16px 64px; display: grid; gap: 28px; }
h1 { font: 700 2.1rem/1.05 var(--display); letter-spacing: .01em; margin: 0; text-wrap: balance; }
.intro { display: grid; gap: 10px; }
.intro p { margin: 0; color: var(--muted); max-width: 62ch; }
.flag { justify-self: start; font: 600 .72rem var(--mono); letter-spacing: .08em; text-transform: uppercase;
  color: var(--bot); background: var(--bot-soft); padding: 3px 8px; border-radius: 3px; }
.score { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 2; background: var(--paper);
  border-bottom: 1px solid var(--rule); padding-block: 8px; font: 600 .95rem var(--display);
  letter-spacing: .04em; text-transform: uppercase; font-variant-numeric: tabular-nums; }
.post { background: var(--card); border: 1px solid var(--rule); border-radius: 6px; padding: 16px; display: grid; gap: 12px; min-width: 0; }
.meta { font: .78rem var(--mono); color: var(--muted); overflow-wrap: anywhere; }
.meta a { color: inherit; }
.post h2 { font: 600 1.35rem/1.2 var(--display); margin: 0; text-wrap: balance; }
.tabs { display: flex; flex-wrap: wrap; gap: 6px; border-bottom: 1px solid var(--rule); padding-bottom: 8px; }
.tabs button { font: 600 .85rem var(--display); letter-spacing: .05em; text-transform: uppercase; color: var(--muted);
  background: none; border: 1px solid transparent; border-radius: 4px; padding: 4px 10px; cursor: pointer; }
.tabs button[aria-selected="true"] { color: var(--ink); border-color: var(--rule); background: var(--paper); }
button:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.list { display: grid; gap: 10px; min-width: 0; }
.c { border-left: 3px solid var(--rule); padding: 4px 0 4px 12px; display: grid; gap: 6px; min-width: 0; }
.c.is-bot { border-left-color: var(--bot); }
.c.is-human { border-left-color: var(--human); }
.c .c { margin-top: 6px; }
.who { font: .75rem var(--mono); color: var(--muted); display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.pill { font: 600 .68rem var(--mono); letter-spacing: .06em; text-transform: uppercase; padding: 1px 6px; border-radius: 3px; }
.pill.bot { color: var(--bot); background: var(--bot-soft); }
.pill.human { color: var(--human); background: var(--human-soft); }
.text { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.tags { display: flex; flex-wrap: wrap; gap: 4px; }
.tag { font: .72rem var(--mono); color: var(--bot); border: 1px solid var(--bot); border-radius: 3px; padding: 0 6px; }
.note { background: var(--note); color: var(--note-ink); font-size: .88rem; padding: 8px 10px; border-radius: 4px; }
.def { color: var(--muted); font-size: .82rem; }
.choices { display: flex; gap: 8px; }
.choices button { font: 600 .85rem var(--display); letter-spacing: .05em; text-transform: uppercase; cursor: pointer;
  background: var(--card); color: var(--ink); border: 1px solid var(--rule); border-radius: 4px; padding: 6px 14px; }
.verdict { font: 600 .85rem var(--display); letter-spacing: .04em; text-transform: uppercase; }
.verdict.right { color: var(--human); } .verdict.wrong { color: var(--bot); }
.empty { color: var(--muted); font-style: italic; margin: 0; }
"""

JS = r"""
const DATA = JSON.parse(document.getElementById('botlab-data').textContent);
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
let right = 0, answered = 0, total = 0;
const scoreEl = document.getElementById('score');
const updateScore = () => { if (scoreEl) scoreEl.textContent = `Your score: ${right} of ${answered} correct · ${total - answered} left`; };

function techniques(c) {
  const box = el('div', 'tags');
  c.techniques.forEach(t => { const s = el('span', 'tag', t.replace(/_/g, ' ')); s.title = DATA.techniques[t] || ''; box.append(s); });
  return box;
}
function botNote(c) {
  const wrap = el('div', 'list');
  wrap.append(techniques(c), el('div', 'note', c.annotation));
  c.techniques.forEach(t => wrap.append(el('div', 'def', `${t.replace(/_/g, ' ')}: ${DATA.techniques[t] || ''}`)));
  return wrap;
}
function botComment(list, i) {
  const c = list[i], n = el('div', 'c is-bot'), who = el('div', 'who');
  who.append(el('span', 'pill bot', 'bot'), el('span', null, `u/${c.persona_id} · ${DATA.personas[c.persona_id] || ''}`));
  const d = el('details'); d.append(el('summary', 'def', 'How this manipulates'), botNote(c));
  n.append(who, el('p', 'text', c.text), techniques(c), d);
  list.forEach((k, j) => { if (k.parent === i) n.append(botComment(list, j)); });
  return n;
}
function realComment(list, i) {
  const c = list[i], n = el('div', 'c is-human'), who = el('div', 'who');
  who.append(el('span', 'pill human', 'real'), el('span', null, `${c.score ?? '?'} points`));
  n.append(who, el('p', 'text', c.text));
  list.forEach((k, j) => { if (k.parent === i) n.append(realComment(list, j)); });
  return n;
}
function guessItem(item) {
  total++;
  const n = el('div', 'c'), choices = el('div', 'choices');
  n.append(el('p', 'text', item.text), choices);
  ['Human', 'Bot'].forEach(label => {
    const b = el('button', null, label); b.type = 'button';
    b.addEventListener('click', () => {
      const ok = (label === 'Bot') === item.bot;
      answered++; if (ok) right++; updateScore();
      choices.replaceWith(el('div', `verdict ${ok ? 'right' : 'wrong'}`, `${ok ? 'Correct' : 'Wrong'}: ${item.bot ? 'bot' : 'real person'}`));
      n.classList.add(item.bot ? 'is-bot' : 'is-human');
      if (item.bot) n.append(el('div', 'who', `u/${item.persona_id} · ${DATA.personas[item.persona_id] || ''}`), botNote(item));
    });
    choices.append(b);
  });
  return n;
}
function roots(list, render) {
  const box = el('div', 'list');
  list.forEach((c, i) => { if (c.parent === -1) box.append(render(list, i)); });
  return box;
}

const main = document.getElementById('posts');
DATA.threads.forEach((t, idx) => {
  const sec = el('section', 'post'), meta = el('div', 'meta', `r/${t.post.subreddit}`);
  if (t.post.permalink) { meta.append(' · '); const a = el('a', null, 'original post'); a.href = t.post.permalink; meta.append(a); }
  sec.append(meta, el('h2', null, t.post.title));
  const panes = [];
  if (t.guess.length) { const p = el('div', 'list'); t.guess.forEach(g => p.append(guessItem(g))); panes.push(['Guess', p]); }
  panes.push(['Bot thread', roots(t.comments, botComment)]);
  if (t.real.length) panes.push(['Real thread', roots(t.real, realComment)]);
  const tabs = el('div', 'tabs'); tabs.setAttribute('role', 'tablist');
  panes.forEach(([label, pane], k) => {
    const b = el('button', null, label); b.type = 'button'; b.setAttribute('role', 'tab');
    b.id = `tab-${idx}-${k}`;
    b.addEventListener('click', () => panes.forEach(([, p], j) => { p.hidden = j !== k; tabs.children[j].setAttribute('aria-selected', String(j === k)); }));
    tabs.append(b); pane.hidden = k !== 0; b.setAttribute('aria-selected', String(k === 0));
  });
  sec.append(tabs, ...panes.map(([, p]) => p));
  main.append(sec);
});
if (!DATA.threads.length) main.append(el('p', 'empty', 'No threads yet. Run botlab generate, then botlab view.'));
if (!total && scoreEl) scoreEl.hidden = true;
updateScore();
"""

FONTS = (
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700'
    '&family=JetBrains+Mono:wght@400;600&family=Public+Sans:ital,wght@0,400;0,600;1,400&display=swap">'
)


def _guess_items(thread: dict, real: list[dict]) -> list[dict]:
    if not real:
        return []
    rng = random.Random(thread["post"]["id"])
    humans = sorted(real, key=lambda c: -(c.get("score") or 0))[:GUESS_PER_SIDE]
    bots = rng.sample(thread["comments"], k=min(GUESS_PER_SIDE, len(thread["comments"])))
    items = [{"bot": False, "text": c["text"]} for c in humans] + [{"bot": True, **c} for c in bots]
    rng.shuffle(items)
    return items


def render(threads: list[dict], out: Path, samples: list[dict] | None = None, fragment: bool = False, note: str = "") -> None:
    """Write the page. `fragment=True` omits the doctype/meta lines (for publishing as an Artifact)."""
    real_by_post = {s["id"]: s.get("comments", []) for s in samples or []}
    data = {
        "techniques": TECHNIQUES,
        "personas": {p["id"]: p["ideology"] for p in PERSONAS},
        "threads": [
            {
                "post": t["post"],
                "comments": t["comments"],
                "real": real_by_post.get(t["post"]["id"], []),
                "guess": _guess_items(t, real_by_post.get(t["post"]["id"], [])),
            }
            for t in threads
        ],
    }
    blob = json.dumps(data).replace("</", "<\\/")
    head = "" if fragment else '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">\n'
    extra = f"<p>{html.escape(note)}</p>" if note else ""
    out.write_text(
        f"{head}<title>Spot the Bot</title>{FONTS}<style>{CSS}</style>\n"
        '<main><header class="intro"><span class="flag">Every labeled bot comment here is AI-generated</span>'
        "<h1>Spot the Bot</h1>"
        "<p>Real posts, with comments from AI personas that use common manipulation tactics. "
        "Where real comments were saved, the Guess tab mixes them with bot comments. "
        "Pick human or bot for each, then see which tactic the bot used.</p>"
        f"{extra}</header>"
        '<div class="score" id="score"></div><div id="posts" class="list" style="gap:28px"></div></main>\n'
        f'<script type="application/json" id="botlab-data">{blob}</script>\n<script>{JS}</script>\n'
    )
