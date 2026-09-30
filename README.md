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
# Save real front-page posts and their top comments (no usernames) to data/samples.json
botlab sample --posts 10 --comments 20

# Generate bot threads for those same posts, to compare real vs. bot side by side
botlab generate --posts-file data/samples.json --limit 10

# Generate threads for today's top r/politics posts
botlab generate --subreddit politics --limit 3

# Always include specific personas (repeatable); the rest are picked at random
botlab generate --subreddit politics --include mutual_aid_anarchist --include rust_belt_dad

# ...or from your own list of posts: [{"title": "...", "selftext": "...", "url": "..."}]
botlab generate --posts-file posts.json

# Render the "Spot the Bot" page -> data/threads.html
# Tabs per post: Guess (real + bot comments shuffled; pick human or bot),
# Bot thread (annotated), Real thread (from `botlab sample`, if saved).
botlab view
botlab view --fragment   # same page without doctype/meta, for publishing as an artifact

# Layout preview with a made-up example post
open examples/preview.html

# Optional: post one stored thread to your own bot subreddit
export BOTLAB_SUBREDDIT=YourBotLabSub REDDIT_CLIENT_ID=... REDDIT_CLIENT_SECRET=... \
       REDDIT_USERNAME=... REDDIT_PASSWORD=...
botlab publish <thread_id>
```

## Layout

| File | What it does |
|---|---|
| `botlab/personas.py` | Personas (ideology + voice) and the catalogue of manipulation techniques |
| `botlab/sources.py` | Reads real posts (a subreddit or the front page) and their top comments from Reddit's public JSON, or a local file |
| `botlab/generate.py` | Calls Claude to write the thread as structured output; tags techniques and adds annotations |
| `botlab/viewer.py` | Builds the self-contained Spot the Bot page: guessing game, bot thread, real thread |
| `examples/` | Made-up example post and comments for previewing the viewer |
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
