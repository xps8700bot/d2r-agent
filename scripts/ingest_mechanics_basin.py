"""Ingest mechanics pages from TheAmazonBasin into structured MechanicsFactRecord JSONL.

Phase 0 note:
- This script is intentionally conservative and will expand over time.
- For now it can (a) fetch & cache HTML, (b) extract a few high-signal formulas/claims.

Usage:
  PYTHONPATH=src python scripts/ingest_mechanics_basin.py --out data/fact_db/mechanics/magic_find_rules.jsonl --url https://www.theamazonbasin.com/wiki/index.php/Magic_find
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from d2r_agent.retrieval.cache import cache_get, cache_put
from d2r_agent.config import CACHE_DIR


def fetch_cached(url: str) -> str:
    key = f"mechanics:{url}"
    cached = cache_get(CACHE_DIR, key)
    if cached:
        return cached.decode("utf-8", errors="ignore")

    r = requests.get(url, timeout=20)
    r.raise_for_status()
    html = r.text
    cache_put(CACHE_DIR, key, html.encode("utf-8"))
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tier", default="tierA")
    args = ap.parse_args()

    html = fetch_cached(args.url)
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n")

    site = urlparse(args.url).netloc

    # Extremely small Phase-0 extractor: keep as seed.
    records = []
    if "Magic_find" in args.url:
        records.append(
            {
                "id": "mf.quality_only.seed",
                "topic": "magic_find",
                "canonical_name": "MF affects quality, not base item",
                "aliases": ["MF", "Magic Find"],
                "fact_type": "rule",
                "statement": "Magic Find affects quality selection; base item selection is separate.",
                "formula": None,
                "conditions": [],
                "variables": [],
                "examples": [],
                "source_url": args.url,
                "source_title": "Magic find",
                "source_site": site,
                "source_tier": args.tier,
                "evidence_source_type": "extract",
                "confidence": "low",
                "version_scope": {"game": "d2/d2r"},
                "notes": "seed extractor; expand later",
                "extracted_at": datetime.utcnow().isoformat(),
            }
        )

    with open(args.out, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
