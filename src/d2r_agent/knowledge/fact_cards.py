from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from d2r_agent.schemas import EvidenceSnippet, FactCard


@dataclass
class FactCardHit:
    card: FactCard
    # Convenience for callers
    sources: list[EvidenceSnippet]


def iter_fact_cards(path: str):
    p = Path(path)
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                yield FactCard.model_validate(obj)
            except Exception:
                continue


def search_fact_cards(user_query: str, path: str, limit: int = 3) -> list[FactCardHit]:
    q = (user_query or "").lower().strip()
    if not q:
        return []

    hits: list[FactCardHit] = []

    # Extremely simple matcher: topic contains a keyword (runeword name etc.).
    tokens = [t for t in q.replace("(", " ").replace(")", " ").replace("?", " ").split() if len(t) >= 3]

    for card in iter_fact_cards(path):
        topic = (card.topic or "").lower()
        hay = topic
        for f in card.facts or []:
            hay += " " + json.dumps(f, ensure_ascii=False).lower()

        score = 0
        for t in tokens:
            if t in hay:
                score += 1
        if score <= 0:
            continue

        hits.append(FactCardHit(card=card, sources=card.sources or []))
        if len(hits) >= limit:
            break

    return hits
