import argparse
import json
from pathlib import Path

import anthropic

from . import generate, sources, viewer
from .personas import PERSONAS

DEFAULT_STORE = Path("data/threads.jsonl")


def main() -> None:
    ap = argparse.ArgumentParser(prog="botlab")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate annotated bot threads for real posts")
    src = g.add_mutually_exclusive_group(required=True)
    src.add_argument("--subreddit", help="pull top posts from this subreddit, e.g. politics")
    src.add_argument("--posts-file", type=Path, help="local JSON list of posts")
    g.add_argument("--limit", type=int, default=3)
    g.add_argument("--comments", type=int, help="bot comments per thread (default: profiles.toml)")
    g.add_argument("--personas", type=int, help="personas per thread (default: profiles.toml)")
    g.add_argument(
        "--include",
        action="append",
        default=[],
        choices=[p["id"] for p in PERSONAS],
        metavar="PERSONA",
        help="persona id to always include (repeatable); others are filled in at random",
    )
    g.add_argument("--store", type=Path, default=DEFAULT_STORE)

    vo = sub.add_parser("voices", help="rewrite one manipulative message per post in every voice")
    vsrc = vo.add_mutually_exclusive_group(required=True)
    vsrc.add_argument("--subreddit")
    vsrc.add_argument("--posts-file", type=Path)
    vo.add_argument("--limit", type=int, default=3)
    vo.add_argument("--store", type=Path, default=Path("data/voices.jsonl"))

    s = sub.add_parser("sample", help="save real posts and their top comments")
    s.add_argument("--subreddit", default="politics", help="subreddit to sample (top of the day); 'front' for the front page")
    s.add_argument("--posts", type=int, default=10)
    s.add_argument("--comments", type=int, default=20)
    s.add_argument("--out", type=Path, default=Path("data/samples.json"))

    v = sub.add_parser("view", help="render stored threads to an annotated HTML page")
    v.add_argument("--store", type=Path, default=DEFAULT_STORE)
    v.add_argument("--out", type=Path, default=Path("data/threads.html"))
    v.add_argument("--samples", type=Path, default=Path("data/samples.json"), help="real comments from botlab sample")
    v.add_argument("--fragment", action="store_true", help="omit doctype/meta, for publishing as an artifact")
    v.add_argument("--voices", type=Path, default=Path("data/voices.jsonl"), help="output of botlab voices")
    v.add_argument("--note", default="", help="extra line shown under the intro")

    d = sub.add_parser("daily", help="sample, generate, render the page, and post to your bot subreddit if configured")
    d.add_argument("--subreddit", default="politics")
    d.add_argument("--posts", type=int, default=3)
    d.add_argument("--comments", type=int, default=20, help="real comments to sample per post")
    d.add_argument("--publish", type=int, default=1, help="threads to post or draft (0 to skip)")
    d.add_argument("--mode", choices=["auto", "draft"], help="auto: post to BOTLAB_SUBREDDIT; draft: write it for you to post. Default $BOTLAB_MODE or draft")
    d.add_argument("--include", action="append", default=[], choices=[p["id"] for p in PERSONAS], metavar="PERSONA")
    d.add_argument(
        "--step",
        choices=["all", "prepare", "finish"],
        default="all",
        help="all: generate through the API (needs ANTHROPIC_API_KEY). Without a key: 'prepare' writes "
        "today's task.md, the Claude Code session writes authored.json, then 'finish' builds everything",
    )

    sub.add_parser("profiles", help="check profiles.toml and list personas, voices and techniques")

    p = sub.add_parser("publish", help="post a stored thread to your own bot subreddit (disclosed)")
    p.add_argument("thread_id")
    p.add_argument("--store", type=Path, default=DEFAULT_STORE)

    args = ap.parse_args()

    if args.cmd == "generate":
        posts = (
            sources.fetch_posts(args.subreddit, limit=args.limit)
            if args.subreddit
            else sources.load_posts(args.posts_file)[: args.limit]
        )
        client = anthropic.Anthropic()
        for post in posts:
            try:
                thread = generate.generate_thread(client, post, args.personas, args.comments, args.include)
            except RuntimeError as e:
                print(f"skip: {e}")
                continue
            generate.append_thread(thread, args.store)
            print(f"{thread['thread_id']}  {len(thread['comments'])} comments  {post['title'][:70]}")

    elif args.cmd == "voices":
        posts = (
            sources.fetch_posts(args.subreddit, limit=args.limit)
            if args.subreddit
            else sources.load_posts(args.posts_file)[: args.limit]
        )
        client = anthropic.Anthropic()
        for post in posts:
            try:
                vs = generate.generate_voices(client, post)
            except RuntimeError as e:
                print(f"skip: {e}")
                continue
            generate.append_thread(vs, args.store)
            print(f"{vs['set_id']}  {len(vs['variants'])} voices  {post['title'][:70]}")

    elif args.cmd == "sample":
        posts = sources.sample(None if args.subreddit == "front" else args.subreddit, args.posts, args.comments)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(posts, indent=2))
        n = sum(len(p["comments"]) for p in posts)
        print(f"wrote {args.out}: {len(posts)} posts, {n} comments")

    elif args.cmd == "view":
        threads = generate.load_threads(args.store)
        samples = json.loads(args.samples.read_text()) if args.samples.exists() else None
        voice_sets = generate.load_threads(args.voices)
        viewer.render(threads, args.out, samples, fragment=args.fragment, note=args.note, voice_sets=voice_sets)
        print(f"wrote {args.out} ({len(threads)} threads, real comments: {'yes' if samples else 'no'})")

    elif args.cmd == "daily":
        from . import daily

        if args.step == "prepare":
            daily.prepare(args.subreddit, args.posts, args.comments, include=args.include)
        elif args.step == "finish":
            daily.finish(args.subreddit, args.publish, mode=args.mode)
        else:
            daily.run(args.subreddit, args.posts, args.comments, args.publish, include=args.include, mode=args.mode)

    elif args.cmd == "profiles":
        from .personas import PROFILES_PATH, SETTINGS, TECHNIQUES, VOICES

        print(f"{PROFILES_PATH}: OK")
        print(f"settings: {SETTINGS}")
        for p in PERSONAS:
            print(f"- {p['id']} ({p['ideology']}) voice={p['voice'] or 'any'} techniques={', '.join(p['favored'])}")
            for pos in p["positions"]:
                print(f"    · {pos}")
        print(f"voices: {', '.join(VOICES)}")
        print(f"techniques: {', '.join(TECHNIQUES)}")

    elif args.cmd == "publish":
        from . import post

        thread = next((t for t in generate.load_threads(args.store) if t["thread_id"] == args.thread_id), None)
        if thread is None:
            raise SystemExit(f"no thread {args.thread_id} in {args.store}")
        print("posted:", post.publish(thread))


if __name__ == "__main__":
    main()
