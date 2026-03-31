#!/usr/bin/env python3
"""Ingest runeword hard facts from TheAmazonBasin into a local structured fact DB.

Design goals:
- Deterministic extraction (no LLM)
- Cached + rate-limited to avoid bans
- Produce a small sample file for human verification first

Usage:
  source .venv/bin/activate
  PYTHONPATH=src python scripts/ingest_basin_runeword_facts.py Insight Spirit --out data/fact_db/runewords.sample.json --sleep 1.2
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from d2r_agent.config import CACHE_DIR
from d2r_agent.retrieval.adapters.theamazonbasin import BASIN_HOST, basin_fetch_page_html


@dataclass
class SourceRef:
    site: str
    url: str
    extracted_at: str


@dataclass
class Variant:
    item_type: str
    sockets: Optional[int] = None
    # Basin uses min RLvl for runewords.
    min_rlvl: Optional[int] = None
    # Rune order as a normalized string like "Tal + Thul + Ort + Amn".
    rune_order_and_modifiers: Optional[str] = None
    # Structured modifiers (deterministic parse): list of {stat, value, unit?, raw}.
    runeword_modifiers: Optional[list[dict]] = None


@dataclass
class RunewordFact:
    name: str
    variants: list[Variant]
    sources: list[SourceRef]
    last_verified_at: str


def _to_int(s: str) -> Optional[int]:
    try:
        return int(str(s).strip())
    except Exception:
        return None


def extract_runeword_facts_from_html(html: str) -> tuple[list[Variant], dict[str, list[str] | str]]:
    """Parse Basin runeword page HTML and extract variants.

    Returns (variants, debug_rows)
    debug_rows contains raw values for transparency.

    Notes:
    - Basin runeword pages use **min RLvl** (minimum required level).
    - We also persist the two runeword text blocks:
      - "Rune order and modifiers"
      - "Rune Word modifiers"
    """

    soup = BeautifulSoup(html, "lxml")

    item_types: list[str] = []
    sockets_vals: list[int] = []
    min_rlvls: list[int] = []
    rune_order_and_modifiers_txt: str | None = None
    runeword_modifiers_txt: str | None = None

    # 1) Simple key/value rows (Item type / Sockets / min RLvl)
    for tr in soup.find_all("tr"):
        th = tr.find("th")
        td = tr.find("td")
        if not th or not td:
            continue
        k_raw = th.get_text(" ", strip=True).strip()
        k = k_raw.lower()
        v = td.get_text(" ", strip=True).strip()
        if not v:
            continue

        if k == "item type":
            item_types.append(v)
        elif k == "sockets":
            vi = _to_int(v)
            if vi is not None:
                sockets_vals.append(vi)
        elif k in {"min rlvl", "min. rlvl", "min. r lvl", "min r lvl", "min rlv"} or "min rlvl" in k:
            vi = _to_int(v)
            if vi is not None:
                min_rlvls.append(vi)

    # 2) Rune order + modifiers live in a header table (not th->td key/value in the same row).
    # Find the first table that contains the runeword section headers.
    rw_table = None
    for tbl in soup.find_all("table"):
        ths = [t.get_text(" ", strip=True).strip().lower() for t in tbl.find_all("th")]
        if any("rune order and modifiers" == x for x in ths) and any("rune word modifiers" == x for x in ths):
            rw_table = tbl
            break

    # 2b) For column-format tables (Spirit/dual-variant runewords), also extract item types
    # from col-0 TD cells in data rows that precede the metadata rows (Sockets/Patch/etc).
    # Basin layouts for multi-variant runewords put the second item type as a TD in row 1, col 0,
    # not as a th/td key-value pair, so step 1) misses it.
    _KNOWN_ITEM_TYPE_WORDS = {
        "sword", "shield", "axe", "mace", "scepter", "staff", "wand", "polearm",
        "bow", "crossbow", "helm", "armor", "gloves", "belt", "boots",
        "body armor", "chest armor",
    }
    for _tbl in soup.find_all("table"):
        _ths = [t.get_text(" ", strip=True).strip().lower() for t in _tbl.find_all("th")]
        if not (any("rune order and modifiers" == x for x in _ths) and
                any("rune word modifiers" == x for x in _ths)):
            continue
        _rows = _tbl.find_all("tr")
        for _tr in _rows[1:]:
            _first = _tr.find(["td", "th"])
            if _first is None:
                continue
            if _first.name == "th":
                break  # hit Sockets/Patch/MinRlvl metadata rows
            _txt = _first.get_text(" ", strip=True).strip()
            if any(kw in _txt.lower() for kw in _KNOWN_ITEM_TYPE_WORDS):
                if _txt not in item_types:
                    item_types.append(_txt)

    if rw_table is not None:
        # Extract rune order deterministically by collecting rune link texts in order.
        runes: list[str] = []
        for a in rw_table.find_all("a"):
            title = (a.get("title") or "").strip()
            if not title.lower().endswith(" rune"):
                continue
            txt = a.get_text(" ", strip=True).strip()
            if not txt:
                continue
            if txt not in runes:
                runes.append(txt)
        if runes:
            rune_order_and_modifiers_txt = " + ".join(runes)

        # Extract the modifiers column by locating the header cell and then taking the corresponding td
        # from subsequent rows (accounting for colspan).
        def _expanded_header_cells(tr):
            cells = []
            for c in tr.find_all(["th", "td"], recursive=False):
                span = 1
                try:
                    span = int(c.get("colspan") or 1)
                except Exception:
                    span = 1
                cells.extend([c] * max(span, 1))
            return cells

        rows = rw_table.find_all("tr", recursive=True)
        header_idx = None
        rw_mod_col = None
        for i, tr in enumerate(rows):
            expanded = _expanded_header_cells(tr)
            texts = [c.get_text(" ", strip=True).strip().lower() for c in expanded]
            if "rune word modifiers" in texts:
                header_idx = i
                rw_mod_col = texts.index("rune word modifiers")
                break

        mods: list[str] = []
        if header_idx is not None and rw_mod_col is not None:
            empty_streak = 0
            # Walk all subsequent rows; stop after a few consecutive empty cells.
            for tr in rows[header_idx + 1 :]:
                expanded = _expanded_header_cells(tr)
                if rw_mod_col >= len(expanded):
                    continue
                cell = expanded[rw_mod_col]

                # If this row is another header row, stop.
                if cell.name == "th":
                    break

                txt = cell.get_text("\n", strip=True)
                if txt:
                    mods.append(txt)
                    empty_streak = 0
                else:
                    empty_streak += 1
                    if empty_streak >= 3:
                        break

        if mods:
            # Deterministic normalization into structured stats.
            # Basin often renders as alternating lines: value then label.
            flat: list[str] = []
            for m in mods:
                for ln in str(m).splitlines():
                    ln = ln.strip()
                    if ln:
                        flat.append(ln)

            def canon(label: str) -> str:
                l = label.lower().strip()
                l = l.replace("%", "percent")
                l = " ".join(l.split())
                mapping = {
                    "faster hit recovery": "fhr",
                    "faster cast rate": "fcr",
                    "faster run/walk": "frw",
                    "enhanced damage": "ed_percent",
                    "bonus to attack rating": "ar_percent",
                    "all attributes": "all_attributes",
                    "vitality": "vitality",
                    "strength": "strength",
                    "dexterity": "dexterity",
                    "energy": "energy",
                    "defense vs missile": "defense_vs_missile",
                    "to mana": "mana",
                    "to life": "life",
                    "magic absorb": "magic_absorb",
                    "all resistances": "all_res",
                }
                for k, v in mapping.items():
                    if k in l:
                        return v
                return l.replace(" ", "_")

            structured: list[dict] = []
            i = 0
            while i < len(flat):
                a = flat[i]
                b = flat[i + 1] if i + 1 < len(flat) else None
                # pattern: numeric then label
                if b is not None:
                    # numeric can be "55" or "+22" or "(200-260)%"
                    if any(ch.isdigit() for ch in a) and not any(ch.isdigit() for ch in b):
                        structured.append({
                            "stat": canon(b),
                            "value": a,
                            "raw": f"{a} {b}",
                        })
                        i += 2
                        continue
                # fallback: store raw line
                structured.append({"stat": "raw", "value": a, "raw": a})
                i += 1

            runeword_modifiers_txt = structured

    debug_rows = {
        "item_type": item_types,
        "sockets": [str(x) for x in sockets_vals],
        "min_rlvl": [str(x) for x in min_rlvls],
        "rune_order_and_modifiers": rune_order_and_modifiers_txt or "",
        "rune_word_modifiers": runeword_modifiers_txt if runeword_modifiers_txt is not None else "",
    }

    sockets = sockets_vals[0] if sockets_vals else None
    min_rlvl = min_rlvls[0] if min_rlvls else None

    uniq_types: list[str] = []
    for t in item_types:
        if t not in uniq_types:
            uniq_types.append(t)

    if not uniq_types:
        return [], debug_rows

    variants = [
        Variant(
            item_type=t,
            sockets=sockets,
            min_rlvl=min_rlvl,
            rune_order_and_modifiers=rune_order_and_modifiers_txt,
            runeword_modifiers=runeword_modifiers_txt,
        )
        for t in uniq_types
    ]
    return variants, debug_rows


def ingest_one(name: str, sleep_s: float) -> tuple[RunewordFact, dict]:
    url, html = basin_fetch_page_html(name, cache_dir=CACHE_DIR)
    variants, debug_rows = extract_runeword_facts_from_html(html)

    now = datetime.now(timezone.utc).isoformat()
    fact = RunewordFact(
        name=name,
        variants=variants,
        sources=[SourceRef(site=BASIN_HOST, url=url, extracted_at=now)],
        last_verified_at=now,
    )

    if sleep_s > 0:
        time.sleep(sleep_s)

    debug = {"name": name, "source_url": url, "debug_rows": debug_rows}
    return fact, debug


def _fetch_category_members(category: str, limit: int) -> list[str]:
    """Fetch category members from Basin via MediaWiki API.

    category: e.g. 'Runewords' (we'll call Category:Runewords)
    """
    import json as _json
    import requests
    from urllib.parse import quote

    from d2r_agent.retrieval.adapters.theamazonbasin import BASIN_API
    from d2r_agent.config import HTTP_TIMEOUT_S

    cat = category.strip()
    # Normalize common alias (users may type "Runewords" but Basin uses "Rune Words")
    _aliases = {"Runewords": "Rune Words", "runewords": "Rune Words", "RuneWords": "Rune Words"}
    cat = _aliases.get(cat, cat)
    if not cat.lower().startswith("category:"):
        cat = "Category:" + cat

    url = (
        f"{BASIN_API}?action=query&format=json&list=categorymembers"
        f"&cmtitle={quote(cat)}&cmlimit={int(limit)}&cmnamespace=0"
    )
    r = requests.get(url, timeout=HTTP_TIMEOUT_S, headers={"User-Agent": "d2r-agent/0.2"})
    r.raise_for_status()
    data = _json.loads(r.text)
    cms = (((data.get("query") or {}).get("categorymembers")) or [])
    titles = [str(x.get("title") or "").strip() for x in cms]
    return [t for t in titles if t]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help="Basin page titles, e.g. Insight Spirit (optional if using --category)")
    ap.add_argument("--category", default=None, help="Basin category title to ingest from, e.g. 'Runewords' (takes first --limit items)")
    ap.add_argument("--limit", type=int, default=20, help="max items to ingest when using --category")
    ap.add_argument("--out", default="data/fact_db/runewords.sample.json")
    ap.add_argument("--debug-out", default="data/fact_db/runewords.sample.debug.json")
    ap.add_argument("--sleep", type=float, default=1.2, help="sleep seconds between pages")

    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    debug_path = Path(args.debug_out)
    debug_path.parent.mkdir(parents=True, exist_ok=True)

    facts: list[dict] = []
    debugs: list[dict] = []

    names: list[str] = list(args.names or [])
    if args.category:
        names = _fetch_category_members(args.category, limit=int(args.limit))

    if not names:
        raise SystemExit("no page titles provided (pass names or --category)")

    for n in names:
        fact, dbg = ingest_one(n, sleep_s=float(args.sleep))
        facts.append({
            "name": fact.name,
            "variants": [asdict(v) for v in fact.variants],
            "sources": [asdict(s) for s in fact.sources],
            "last_verified_at": fact.last_verified_at,
        })
        debugs.append(dbg)

    out_path.write_text(json.dumps({"runewords": facts}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    debug_path.write_text(json.dumps({"debug": debugs}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"wrote: {out_path}")
    print(f"wrote: {debug_path}")


if __name__ == "__main__":
    main()
