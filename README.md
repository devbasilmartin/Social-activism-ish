# Bot Lab

A media-literacy demo: take **real** Reddit posts, have AI personas with different
political leanings write a **synthetic** argument thread underneath, and label every
comment with the manipulation technique it uses. The point is to show how cheap and
easy it is for bots to produce convincing, manipulative political comments, and
to teach people what to look for.

Generated threads are stored locally (`data/threads.jsonl`). They can be viewed in an
annotated HTML page or, optionally, posted to **your own** bot subreddit with a
disclosure line on every comment.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .            # add [post] for the optional subreddit publisher
export ANTHROPIC_API_KEY=...
```

## Usage

```bash
# Generate threads for today's top r/politics posts
botlab generate --subreddit politics --limit 3

# ...or from your own list of posts: [{"title": "...", "selftext": "...", "url": "..."}]
botlab generate --posts-file posts.json

# Render an annotated page (every comment badged BOT, techniques explained)
botlab view            # -> data/threads.html

# Optional: post one stored thread to your own bot subreddit
export BOTLAB_SUBREDDIT=YourBotLabSub REDDIT_CLIENT_ID=... REDDIT_CLIENT_SECRET=... \
       REDDIT_USERNAME=... REDDIT_PASSWORD=...
botlab publish <thread_id>
```

## Layout

| File | What it does |
|---|---|
| `botlab/personas.py` | Personas (ideology + voice) and the catalogue of manipulation techniques |
| `botlab/sources.py` | Reads real posts from Reddit's public JSON listings, or a local file |
| `botlab/generate.py` | Calls Claude to write the thread as structured output; tags techniques and adds annotations |
| `botlab/viewer.py` | Builds a self-contained annotated HTML page |
| `botlab/post.py` | Disclosed publisher, locked to one subreddit you moderate |

## Guardrails

These are part of the design, so the project demonstrates manipulation without doing it:

- Every stored record has `"synthetic": true` and technique annotations.
- The publisher posts only to `BOTLAB_SUBREDDIT`, and only if the account moderates it.
  It adds a disclosure footer to every comment and a `[BOT THREAD]` title prefix.
- Prompts steer away from false factual claims about named real people, and away
  from slurs and harassment. The manipulation is kept to rhetoric and framing.
- It never posts to real threads or other subreddits. Keep it that way: undisclosed
  bot accounts break Reddit's rules and would turn the demo into the thing it warns about.
