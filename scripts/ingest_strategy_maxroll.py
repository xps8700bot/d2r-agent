from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from d2r_agent.retrieval.adapters.maxroll import fetch_and_extract


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest Maxroll strategy nuggets into local StrategyCard JSONL")
    ap.add_argument("--seeds", default="data/seed_urls.yaml")
    ap.add_argument("--out", default="data/strategy_cards.jsonl")
    ap.add_argument("--cache", default="cache")
    ap.add_argument("--max_per_url", type=int, default=6)
    args = ap.parse_args()

    seeds = yaml.safe_load(Path(args.seeds).read_text(encoding="utf-8")) or {}
    urls: list[str] = (seeds.get("maxroll") or {}).get("seed_urls") or []

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()

    wrote = 0
    with outp.open("w", encoding="utf-8") as f:
        for url in urls:
            try:
                source_url, sections = fetch_and_extract(url, cache_dir=args.cache)
            except Exception as e:
                print(f"skip {url}: {e}")
                continue

            # Basic topic: use page H1 (title_path[0]) if present
            topic = sections[0].title_path[0] if sections and sections[0].title_path else url

            n = 0
            for sec in sections:
                # Nugget = first 260 chars of section text
                nugget = sec.text.strip().replace("\n", " ")
                nugget = " ".join(nugget.split())
                if len(nugget) > 280:
                    nugget = nugget[:277] + "..."

                card = {
                    "topic": topic,
                    "tags": ["maxroll", "strategy"],
                    "nugget": nugget,
                    "source_site": "maxroll.gg",
                    "source_url": source_url,
                    "title_path": sec.title_path,
                    "created_at": now,
                }
                f.write(json.dumps(card, ensure_ascii=False) + "\n")
                wrote += 1
                n += 1
                if n >= int(args.max_per_url):
                    break

    print(f"wrote {args.out}: {wrote} cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
