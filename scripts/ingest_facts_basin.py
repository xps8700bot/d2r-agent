from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from d2r_agent.config import HTTP_TIMEOUT_S
from d2r_agent.knowledge.memory_store import append_fact_card
from d2r_agent.retrieval.adapters.theamazonbasin import (
    BASIN_API,
    BASIN_HOST,
    basin_fetch_page_html,
)
from d2r_agent.schemas import EvidenceSnippet, FactCard


def mw_category_members(category: str, *, cmtype: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
    """List members of a category via MediaWiki API."""
    out: list[dict[str, Any]] = []
    cont = None
    while True:
        params = {
            "action": "query",
            "format": "json",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmlimit": min(500, int(limit)),
        }
        if cmtype:
            params["cmtype"] = cmtype
        if cont:
            params.update(cont)

        r = requests.get(BASIN_API, params=params, timeout=HTTP_TIMEOUT_S, headers={"User-Agent": "d2r-agent/0.2"})
        r.raise_for_status()
        data = r.json()
        out.extend((data.get("query") or {}).get("categorymembers") or [])
        cont = data.get("continue")
        if not cont:
            break
        if len(out) >= limit:
            break
    return out[:limit]


def mw_recursive_category_titles(root: str, *, max_pages: int = 4000) -> list[str]:
    """Recursively walk subcategories collecting page titles."""
    seen_cat: set[str] = set()
    seen_pages: set[str] = set()

    def walk(cat: str):
        if cat in seen_cat:
            return
        seen_cat.add(cat)

        # pages
        for m in mw_category_members(cat, cmtype="page", limit=500):
            title = str(m.get("title") or "").strip()
            if not title:
                continue
            if title.startswith("Category:"):
                continue
            seen_pages.add(title)
            if len(seen_pages) >= max_pages:
                return

        # subcats
        for m in mw_category_members(cat, cmtype="subcat", limit=500):
            title = str(m.get("title") or "").strip()
            if not title.startswith("Category:"):
                continue
            sub = title.replace("Category:", "", 1)
            walk(sub)
            if len(seen_pages) >= max_pages:
                return

    walk(root)
    return sorted(seen_pages)


def _text(soup: BeautifulSoup) -> str:
    return " ".join((soup.get_text(" ", strip=True) or "").split())


def parse_runeword_infobox(html: str) -> dict[str, Any]:
    """Heuristic parsing of Runeword pages for key fields."""
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()

    facts: dict[str, Any] = {}

    # Try to locate a table with key-value pairs
    for table in soup.find_all("table", limit=15):
        rows = table.find_all("tr")
        for tr in rows:
            th = tr.find("th")
            td = tr.find("td")
            if not th or not td:
                continue
            k = th.get_text(" ", strip=True)
            v = td.get_text(" ", strip=True)
            if not k or not v:
                continue
            kl = k.lower()
            if "runes" in kl or "rune" == kl:
                facts["runes"] = v
            if "sockets" in kl:
                facts["sockets"] = v
            if "required level" in kl or "level req" in kl:
                facts["required_level"] = v
            if "item" in kl and "type" in kl:
                facts["base_types"] = v
            if "ladder" in kl:
                facts["ladder_restriction"] = v

    # Fallback regex on full page text
    txt = _text(soup)
    if "required_level" not in facts:
        m = re.search(r"Required Level\s*:?\s*(\d+)", txt, flags=re.I)
        if m:
            facts["required_level"] = m.group(1)

    if "ladder_restriction" not in facts and re.search(r"Ladder\s+only", txt, flags=re.I):
        facts["ladder_restriction"] = "Ladder only"

    return facts


def ingest_titles(titles: list[str], *, cache_dir: str, out_path: str, release_track: str = "d2r_roitw") -> int:
    now = datetime.now(timezone.utc)
    wrote = 0

    for i, title in enumerate(titles, start=1):
        if i == 1 or i % 20 == 0:
            print(f"[{i}/{len(titles)}] {title}")
        try:
            source_url, html = basin_fetch_page_html(title, cache_dir)
        except Exception as e:
            print(f"skip {title}: {e}")
            continue

        facts_obj = parse_runeword_infobox(html)
        # Evidence: take a short snippet around runes/required level if possible
        soup = BeautifulSoup(html, "lxml")
        ev_text = ""
        # Prefer first table cell mentioning runes
        for cell in soup.find_all(["td", "th"], limit=400):
            t = cell.get_text(" ", strip=True)
            if not t:
                continue
            if any(x in t.lower() for x in ["runes", "required level", "sockets", "ladder"]):
                ev_text = " ".join(t.split())
                break
        if not ev_text:
            ev_text = _text(soup)[:280]

        ev = EvidenceSnippet(source_url=source_url, source_site=BASIN_HOST, title_path=[title], snippet=ev_text[:280])

        card = FactCard(
            topic=title,
            release_track=release_track,
            season_id=None,
            ladder_flag="unknown",
            platform=None,
            facts=[facts_obj] if facts_obj else [],
            sources=[ev],
            last_verified_at=now,
        )

        append_fact_card(out_path, card)
        wrote += 1

    return wrote


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest Basin runewords/cube pages into FactCard JSONL")
    ap.add_argument("--out", default="data/fact_cards.jsonl")
    ap.add_argument("--cache", default="cache")
    ap.add_argument("--max_pages", type=int, default=250)
    args = ap.parse_args()

    # Runewords: Basin uses Category:Rune_Words
    runeword_titles = mw_recursive_category_titles("Rune_Words", max_pages=args.max_pages)
    print(f"discovered runeword pages: {len(runeword_titles)}")

    # Cube recipes are not consistently categorized; we fallback to the Horadric Cube page and its subpages.
    # We'll include any pages in Category:Diablo_II that have 'Cube' and 'Recipe' in title via search heuristic.
    # (Keep it small for MVP.)
    cube_candidates = ["Horadric_Cube"]

    titles = []
    titles.extend(runeword_titles)
    titles.extend([t for t in cube_candidates if t not in titles])

    # Write as jsonl (FactCard) via append_fact_card
    Path(args.out).unlink(missing_ok=True)

    wrote = ingest_titles(titles, cache_dir=args.cache, out_path=args.out)
    print(f"wrote {args.out}: {wrote} fact cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
