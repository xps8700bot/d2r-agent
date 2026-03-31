from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class StrategyCardHit:
    topic: str
    nugget: str
    source_url: str
    title_path: list[str]


def iter_strategy_cards(path: str):
    p = Path(path)
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def search_strategy_cards(user_query: str, path: str, limit: int = 3) -> list[StrategyCardHit]:
    q = (user_query or "").lower()
    if not q.strip():
        return []

    scored: list[tuple[int, StrategyCardHit]] = []

    import re

    norm_q = re.sub(r"[^0-9a-zA-Z_\u4e00-\u9fff\+\-]+", " ", q)
    tokens = [t for t in norm_q.split() if len(t) >= 3]

    for obj in iter_strategy_cards(path):
        topic = str(obj.get("topic") or "").strip()
        nugget = str(obj.get("nugget") or "").strip()
        if not nugget:
            continue

        hay = " ".join([
            topic,
            nugget,
            " ".join(obj.get("tags") or []),
            " ".join(obj.get("title_path") or []),
        ]).lower()

        score = 0
        for token in tokens:
            if token in hay:
                score += 3 if token.startswith("+") else 1
        if score <= 0:
            continue

        scored.append(
            (
                score,
                StrategyCardHit(
                    topic=topic or "(unknown)",
                    nugget=nugget,
                    source_url=str(obj.get("source_url") or ""),
                    title_path=[str(x) for x in (obj.get("title_path") or []) if str(x).strip()],
                ),
            )
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in scored[:limit]]
