"""
collect_reddit.py - turn browser-saved Reddit .json files into plain .txt for the RAG pipeline.

Reddit blocks scripted requests (403), so we let the *browser* fetch the JSON:

    1. For each thread, open the URL with .json appended in your browser, e.g.
       https://www.reddit.com/r/UIUC/comments/16xycks/please_do_not_live_at_legacy_202/.json
    2. Save Page As (Ctrl/Cmd-S) into a ./raw_json/ folder. Filename doesn't matter.
    3. Run:  python collect_reddit.py
    4. Find one cleaned .txt per thread in ./documents/

No network, no dependencies beyond the standard library.
"""

import os
import re
import glob
import json
import datetime

IN_DIR = "raw_reddit_json"      # where your browser-saved .json files live
OUT_DIR = "documents"    # where the .txt files are written


def walk_comments(children, depth=0, out=None):
    """Recursively collect comment bodies; skip deleted/removed and 'load more' stubs."""
    if out is None:
        out = []
    for child in children:
        if child.get("kind") != "t1":          # 't1' = a comment; skip 'more' stubs
            continue
        data = child["data"]
        body = (data.get("body") or "").strip()
        if body and body not in ("[deleted]", "[removed]"):
            out.append(("    " * depth) + body)
        replies = data.get("replies")
        if isinstance(replies, dict):           # "" (empty string) when no replies
            walk_comments(replies["data"]["children"], depth + 1, out)
    return out


def thread_to_text(payload):
    """Flatten one thread (post + comments) into a single labeled text block."""
    post = payload[0]["data"]["children"][0]["data"]
    subreddit = post.get("subreddit", "reddit")
    title = post.get("title", "").strip()
    selftext = (post.get("selftext") or "").strip()
    date = datetime.datetime.fromtimestamp(
        post.get("created_utc", 0), datetime.timezone.utc
    ).strftime("%Y-%m-%d")

    lines = [
        f"SOURCE: r/{subreddit}",
        f"DATE: {date}",
        f"TITLE: {title}",
        "",
        selftext,
        "",
        "--- COMMENTS ---",
        "",
    ]
    lines.extend(walk_comments(payload[1]["data"]["children"]))
    return subreddit, post.get("id", "thread"), "\n".join(lines)


def load_json(path):
    """Load a browser-saved Reddit JSON file, tolerating minor wrapping."""
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Some browsers wrap the JSON; grab from the first bracket onward.
        start = raw.find("[")
        if start == -1:
            raise
        return json.loads(raw[start:])


def safe_name(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(IN_DIR, "*.json")))
    if not files:
        print(f"No .json files found in ./{IN_DIR}/ — save your threads there first.")
        return

    for path in files:
        try:
            payload = load_json(path)
            subreddit, tid, text = thread_to_text(payload)
            out_path = os.path.join(OUT_DIR, f"reddit_{safe_name(subreddit)}_{tid}.txt")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"saved {out_path}  ({len(text)} chars)  <- {os.path.basename(path)}")
        except Exception as e:
            print(f"FAILED {os.path.basename(path)}: {e}")


if __name__ == "__main__":
    main()