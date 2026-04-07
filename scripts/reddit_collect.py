"""reddit_collect.py — helper for the d2r-agent scheduled task.

Given a list of already-fetched Reddit post JSON files (from curl against
`https://www.reddit.com/comments/<id>.json`), build/append benchmark entries
into `reddit_qa_todo.json` at the repo root.

Usage:
    python scripts/reddit_collect.py <comments_json> [<comments_json> ...]

Idempotent: skips entries whose `source_url` is already in the queue.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = REPO_ROOT / "reddit_qa_todo.json"

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "should", "could", "may", "might", "can", "to", "of", "in",
    "on", "at", "for", "with", "by", "from", "as", "that", "this", "these",
    "those", "it", "its", "i", "my", "me", "you", "your", "we", "our",
    "they", "them", "their", "so", "if", "then", "than", "how", "why",
    "what", "which", "when", "where", "who", "any", "some", "about", "just",
    "up", "out", "get", "got", "not", "no", "one", "two", "use", "using",
    "d2r", "d2", "diablo", "game", "help", "question", "thanks",
}


def extract_keywords(text: str, n: int = 5) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z']{2,}", text.lower())
    seen: list[str] = []
    for w in words:
        if w in STOPWORDS:
            continue
        if w in seen:
            continue
        seen.append(w)
    return seen[:n]


def load_queue() -> dict:
    if QUEUE_PATH.exists():
        return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    return {
        "version": 1,
        "description": (
            "D2R question benchmark set, sourced from Reddit. "
            "State machine: pending -> in_progress -> passed | failed."
        ),
        "questions": [],
    }


def summarize_top_comments(comments_listing: list, max_chars: int = 700) -> str:
    """Take up to top 3 comments and concatenate into a reference answer."""
    out: list[str] = []
    total = 0
    for c in comments_listing[:5]:
        if c.get("kind") != "t1":
            continue
        d = c["data"]
        if d.get("stickied"):
            continue
        body = (d.get("body") or "").strip()
        if not body or body in ("[deleted]", "[removed]"):
            continue
        score = d.get("score", 0)
        body = re.sub(r"\s+", " ", body)
        snippet = body[:300]
        out.append(f"[{score}↑] {snippet}")
        total += len(snippet)
        if total >= max_chars:
            break
    return "\n".join(out)


def build_entry(post_data: dict, comments_data: list) -> dict | None:
    title = post_data["title"]
    selftext = (post_data.get("selftext") or "").strip()
    question = title
    if selftext and len(selftext) < 500:
        question = f"{title}\n\n{selftext}"
    elif selftext:
        question = f"{title}\n\n{selftext[:500]}..."

    ref = summarize_top_comments(comments_data)
    if not ref:
        return None

    return {
        "id": f"reddit_{post_data['id']}",
        "source_url": "https://www.reddit.com" + post_data["permalink"],
        "question": question,
        "question_keywords": extract_keywords(title + " " + selftext[:300]),
        "reference_answer": ref,
        "status": "pending",
        "added_date": date.today().isoformat(),
        "improvement_count": 0,
        "failure_reason": None,
        "improvement_history": [],
        "meta": {
            "subreddit": post_data.get("subreddit"),
            "score": post_data.get("score"),
            "num_comments": post_data.get("num_comments"),
            "flair": post_data.get("link_flair_text"),
        },
    }


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: reddit_collect.py <comments_json> [<comments_json> ...]", file=sys.stderr)
        return 2

    queue = load_queue()
    existing_urls = {q["source_url"] for q in queue["questions"]}
    existing_kw_sets = [set(q.get("question_keywords", [])) for q in queue["questions"]]

    added = 0
    for path in argv:
        blob = json.loads(Path(path).read_text(encoding="utf-8"))
        post = blob[0]["data"]["children"][0]["data"]
        comments = blob[1]["data"]["children"]

        url = "https://www.reddit.com" + post["permalink"]
        if url in existing_urls:
            print(f"skip (url dup): {url}")
            continue

        entry = build_entry(post, comments)
        if entry is None:
            print(f"skip (no usable comments): {url}")
            continue

        new_kw = set(entry["question_keywords"])
        dup_semantic = False
        for kw in existing_kw_sets:
            if not kw or not new_kw:
                continue
            overlap = len(kw & new_kw) / max(len(kw | new_kw), 1)
            if overlap > 0.7:
                dup_semantic = True
                break
        if dup_semantic:
            print(f"skip (keyword dup): {entry['id']}")
            continue

        queue["questions"].append(entry)
        existing_urls.add(url)
        existing_kw_sets.append(new_kw)
        added += 1
        print(f"added: {entry['id']} — {entry['question'][:80]}")

    QUEUE_PATH.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\ntotal added: {added}; queue size: {len(queue['questions'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
