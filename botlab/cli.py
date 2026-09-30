import argparse
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
    g.add_argument("--comments", type=int, default=10)
    g.add_argument("--personas", type=int, default=4)
    g.add_argument(
        "--include",
        action="append",
        default=[],
        choices=[p["id"] for p in PERSONAS],
        metavar="PERSONA",
        help="persona id to always include (repeatable); others are filled in at random",
    )
    g.add_argument("--store", type=Path, default=DEFAULT_STORE)

    v = sub.add_parser("view", help="render stored threads to an annotated HTML page")
    v.add_argument("--store", type=Path, default=DEFAULT_STORE)
    v.add_argument("--out", type=Path, default=Path("data/threads.html"))

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

    elif args.cmd == "view":
        threads = generate.load_threads(args.store)
        viewer.render(threads, args.out)
        print(f"wrote {args.out} ({len(threads)} threads)")

    elif args.cmd == "publish":
        from . import post

        thread = next((t for t in generate.load_threads(args.store) if t["thread_id"] == args.thread_id), None)
        if thread is None:
            raise SystemExit(f"no thread {args.thread_id} in {args.store}")
        print("posted:", post.publish(thread))


if __name__ == "__main__":
    main()
