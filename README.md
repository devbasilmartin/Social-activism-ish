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

Reddit blocks logged-out requests from most cloud servers. If `botlab sample` gets a
403 or 429, create a free "script" app at https://www.reddit.com/prefs/apps and set
`REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`. Reading then goes through Reddit's
official read-only API. No username or password is needed for reading.

## Usage

```bash
# Save today's top r/politics posts and their top comments (no usernames) to data/samples.json
botlab sample --posts 10 --comments 20              # --subreddit front for the front page

# Generate bot threads for those same posts, to compare real vs. bot side by side
botlab generate --posts-file data/samples.json --limit 10

# Generate threads for today's top r/politics posts
botlab generate --subreddit politics --limit 3

# One manipulative message per post, rewritten in every voice (lowercase, phone typos,
# Facebook uncle, Gen Z, essayist, ...) -> data/voices.jsonl, shown as a "Many voices" tab
botlab voices --posts-file data/samples.json --limit 3

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

## Daily run

```bash
botlab daily                     # 3 top r/politics posts -> threads + voice sets + page
botlab daily --mode draft        # write the post for you to paste (the default)
botlab daily --mode auto         # post it to BOTLAB_SUBREDDIT automatically
botlab daily --publish 0         # generate only, no post or draft
```

Two modes, set with `--mode` or the `BOTLAB_MODE` environment variable (default `draft`):

- **draft**: writes `data/daily/<date>/draft.md` and puts a "Draft post" box with Copy
  buttons at the top of the Spot the Bot page. Paste it into a text post in your subreddit.
  The bot thread is included as labeled quotes, so it's one post, not many comments.
- **auto**: posts to your subreddit through the API (needs approved access, see below).
  Falls back to draft if the Reddit credentials aren't set.

Everything lands in `data/daily/<date>/` (samples, threads, voices, draft, `spot-the-bot.html`).

### Posting to your own subreddit

Reddit's Responsible Builder Policy (Nov 2025) requires approved API access for any bot.
Apply describing exactly what this does: one subreddit you moderate, one bot account,
reads top r/politics posts once a day, posts a few labeled threads, no voting, no activity
anywhere else. Once approved, set `BOTLAB_SUBREDDIT`, `REDDIT_CLIENT_ID`,
`REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD` and `pip install -e .[post]`.

Recommended setup:
- One clearly named bot account (e.g. u/SpotTheBotLab) with a bio saying it's an automated
  demo. Not one account per persona: persona and voice go in each comment's header.
- Subreddit sidebar says everything is AI-generated; only mods and the bot can post;
  bot threads are locked; a pinned weekly thread for human discussion.
- Posts name the source subreddit and headline but don't link the real thread, and
  real users' comments are never reposted (the guessing game stays on the Spot the Bot page).

## Layout

| File | What it does |
|---|---|
| `botlab/personas.py` | Personas (ideology), writing voices, and the catalogue of manipulation techniques |
| `botlab/sources.py` | Reads real posts (a subreddit or the front page) and their top comments from Reddit's public JSON, or a local file |
| `botlab/generate.py` | Calls Claude to write the thread as structured output; tags techniques and adds annotations |
| `botlab/viewer.py` | Builds the self-contained Spot the Bot page: guessing game, bot thread, real thread |
| `examples/` | Made-up example post and comments for previewing the viewer |
| `botlab/post.py` | Disclosed publisher, locked to one subreddit you moderate |
| `botlab/daily.py` | The unattended daily run |

## Guardrails

These are part of the design, so the project demonstrates manipulation without doing it:

- Every stored record has `"synthetic": true` and technique annotations.
- The publisher posts only to `BOTLAB_SUBREDDIT`, and only if the account moderates it.
  Every comment carries a `[bot · persona · voice]` header, threads are locked after posting,
  and real threads are named but never linked.
  It adds a disclosure footer to every comment and a `[BOT THREAD]` title prefix.
- Prompts steer away from false factual claims about named real people, and away
  from slurs and harassment. The manipulation is kept to rhetoric and framing.
- It never posts to real threads or other subreddits. Keep it that way: undisclosed
  bot accounts break Reddit's rules and would turn the demo into the thing it warns about.
