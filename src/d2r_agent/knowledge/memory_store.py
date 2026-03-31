from __future__ import annotations

import json
from pathlib import Path

from d2r_agent.schemas import FactCard


def append_fact_card(path: str, card: FactCard) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(card.model_dump(mode="json"), ensure_ascii=False)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return p
