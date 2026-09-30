"""One unattended run: sample real posts, generate bot threads and voice sets, render the
Spot the Bot page, and (if Reddit posting is configured) post to your own bot subreddit."""

import json
from datetime import date
from pathlib import Path

import anthropic

from . import generate, post, sources, viewer


def run(
    subreddit: str = "politics",
    n_posts: int = 3,
    n_comments: int = 20,
    n_publish: int = 1,
    out_dir: Path = Path("data/daily"),
    include: list[str] | None = None,
) -> Path:
    day = out_dir / date.today().isoformat()
    day.mkdir(parents=True, exist_ok=True)
    threads_path, voices_path, samples_path = day / "threads.jsonl", day / "voices.jsonl", day / "samples.json"

    print(f"sampling r/{subreddit} ...")
    samples = sources.sample(subreddit, n_posts, n_comments)
    samples_path.write_text(json.dumps(samples, indent=2))

    client = anthropic.Anthropic()
    threads, voice_sets = [], {}
    for p in samples:
        try:
            t = generate.generate_thread(client, p, include=include)
            generate.append_thread(t, threads_path)
            threads.append(t)
            vs = generate.generate_voices(client, p)
            generate.append_thread(vs, voices_path)
            voice_sets[p["id"]] = vs
            print(f"  {t['thread_id']}  {len(t['comments'])} comments, {len(vs['variants'])} voices  {p['title'][:60]}")
        except RuntimeError as e:
            print(f"  skip: {e}")

    page = day / "spot-the-bot.html"
    viewer.render(threads, page, samples, fragment=True, voice_sets=list(voice_sets.values()),
                  note=f"Generated automatically on {day.name} from the top posts of r/{subreddit}.")
    print(f"page: {page}")

    if n_publish and threads:
        if post.configured():
            for t in threads[:n_publish]:
                print("posted:", post.publish(t, voice_sets.get(t["post"]["id"])))
        else:
            print("Reddit posting not configured (needs approved API access); skipped posting.")
    return page
