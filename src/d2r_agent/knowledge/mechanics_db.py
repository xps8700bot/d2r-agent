from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from d2r_agent.knowledge.mechanics_schema import MechanicsFactRecord


@dataclass
class MechanicsHit:
    record: MechanicsFactRecord
    score: int


def iter_mechanics_records(paths: list[str]) -> list[MechanicsFactRecord]:
    out: list[MechanicsFactRecord] = []
    for pth in paths:
        p = Path(pth)
        if not p.exists():
            continue
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    out.append(MechanicsFactRecord.model_validate(obj))
                except Exception:
                    continue
    return out


def _tokenize(q: str) -> list[str]:
    s = (q or "").lower()
    # Keep some CJK characters but split them for better matching
    # Change: don't just split on spaces if it's CJK.
    
    # First, handle non-CJK words as usual
    non_cjk = re.sub(r"[\u4e00-\u9fff]+", " ", s)
    toks = [t for t in non_cjk.split() if t]
    
    short_keep = {"tc", "mf", "ilvl", "alvl", "qlvl", "fcr", "fhr", "ias"}
    out: list[str] = []
    for t in toks:
        if len(t) >= 2 or t in short_keep:
            out.append(t)
            
    # Then, handle CJK characters
    cjk_blocks = re.findall(r"[\u4e00-\u9fff]+", s)
    for block in cjk_blocks:
        out.append(block) # full block
        if len(block) >= 2:
            for i in range(len(block) - 1):
                out.append(block[i:i+2])
        for char in block:
            out.append(char)
            
    # de-dupe keep order
    seen = set()
    dedup = []
    for t in out:
        if t in seen:
            continue
        seen.add(t)
        dedup.append(t)
    return dedup[:40]

    # de-dupe keep order
    seen = set()
    dedup = []
    for t in out:
        if t in seen:
            continue
        seen.add(t)
        dedup.append(t)
    return dedup[:40]


def search_mechanics(user_query: str, *, paths: list[str], limit: int = 5) -> list[MechanicsHit]:
    q = (user_query or "").strip()
    if not q:
        return []

    records = iter_mechanics_records(paths)
    tokens = _tokenize(q)
    
    # Debug: print tokens if no hits found but records exist
    # if not tokens and records:
    #     print(f"DEBUG: No tokens generated for query: {q}")

    hits: list[MechanicsHit] = []
    for r in records:
        # Weights for search fields
        score = 0
        
        # Pre-calculate fields
        canonical_lower = (r.canonical_name or "").lower()
        aliases_lower = [a.lower() for a in (r.aliases or [])]
        hay = " ".join(
            [
                r.topic or "",
                r.subtopic or "",
                canonical_lower,
                " ".join(aliases_lower),
                (r.statement or "").lower(),
                (r.formula or "").lower(),
                " ".join([c.lower() for c in (r.conditions or [])]),
            ]
        )

        for t in tokens:
            t_low = t.lower()
            
            found_in_top = False
            # EXACT match in Canonical name or aliases get highest priority
            if t_low == canonical_lower:
                score += 50
                found_in_top = True
                
            if not found_in_top:
                for alow in aliases_lower:
                    if t_low == alow:
                        score += 50
                        found_in_top = True
                        break
            
            # SUBSTRING match in top fields
            if not found_in_top:
                if t_low in canonical_lower:
                    score += 20
                    found_in_top = True
                else:
                    for alow in aliases_lower:
                        if t_low in alow:
                            score += 20
                            found_in_top = True
                            break
            
            # OTHER fields (substring match in the full record)
            if t_low in hay:
                score += 2

        if score <= 0:
            continue
        hits.append(MechanicsHit(record=r, score=score))

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]
