from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from d2r_agent.schemas import Trace


def _safe_ts(dt: datetime) -> str:
    return dt.strftime("%Y%m%d_%H%M%S")


def write_trace(trace: Trace, traces_dir: str) -> Path:
    Path(traces_dir).mkdir(parents=True, exist_ok=True)
    ts = _safe_ts(trace.timestamp)
    h = hashlib.sha1(trace.user_query.encode("utf-8")).hexdigest()[:10]
    out = Path(traces_dir) / f"{ts}_{h}.json"
    out.write_text(json.dumps(trace.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    return out
