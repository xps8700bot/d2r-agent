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

    # Stop-words excluded from phrase generation so we don't reward
    # filler bigrams like "with fire" or "dealing with".
    _STOPWORDS = {
        "the", "and", "for", "with", "from", "are", "you", "your", "this",
        "that", "they", "them", "have", "has", "any", "but", "not", "all",
        "out", "into", "onto", "what", "which", "when", "where", "how",
        "why", "who", "doing", "dealing", "getting", "going", "really",
        "still", "just", "very", "can", "could", "would", "should",
    }

    content_tokens = [t for t in tokens if t not in _STOPWORDS]

    # Build bigrams + trigrams from contiguous content tokens.
    # Also add singular variants (strip trailing 's') so "fire immunes"
    # matches a card containing "fire immune".
    def _variants(phrase: str) -> list[str]:
        out = [phrase]
        parts = phrase.split()
        # Singular form of last word.
        if parts and len(parts[-1]) > 3 and parts[-1].endswith("s"):
            singular_last = parts[:-1] + [parts[-1][:-1]]
            out.append(" ".join(singular_last))
        # Singular form of every word (covers "fire immunes" -> "fire immune"
        # and also "warlocks dealing" -> "warlock dealing" if relevant).
        all_singular = [p[:-1] if (len(p) > 3 and p.endswith("s")) else p for p in parts]
        cand = " ".join(all_singular)
        if cand not in out:
            out.append(cand)
        return out

    bigrams: list[str] = []
    trigrams: list[str] = []
    # Walk the original normalized token stream so we keep adjacency,
    # but skip stop-words inside windows.
    for i in range(len(tokens) - 1):
        a, b = tokens[i], tokens[i + 1]
        if a in _STOPWORDS or b in _STOPWORDS:
            continue
        bigrams.append(f"{a} {b}")
    for i in range(len(tokens) - 2):
        a, b, c = tokens[i], tokens[i + 1], tokens[i + 2]
        if a in _STOPWORDS or c in _STOPWORDS:
            continue
        trigrams.append(f"{a} {b} {c}")

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

        # Phrase bonuses dwarf single-token overlap so a card that
        # matches "fire immune" beats a generic card that just happens
        # to share single words like "fire" and "hell".
        for phrase in bigrams:
            for variant in _variants(phrase):
                if variant in hay:
                    score += 6
                    break
        for phrase in trigrams:
            for variant in _variants(phrase):
                if variant in hay:
                    score += 10
                    break

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
