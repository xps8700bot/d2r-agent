from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from d2r_agent.schemas import EvidenceSnippet


@dataclass(frozen=True)
class SeasonRecord:
    release_track: str
    season_id: str
    start_date: str  # ISO date
    end_date: str | None = None
    source_url: str | None = None


DEFAULT_CALENDAR_PATH = "data/season_calendar.json"


def _load(path: str = DEFAULT_CALENDAR_PATH) -> list[SeasonRecord]:
    p = Path(path)
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    out: list[SeasonRecord] = []
    for r in raw.get("seasons", []):
        try:
            out.append(
                SeasonRecord(
                    release_track=str(r.get("release_track") or ""),
                    season_id=str(r.get("season_id") or ""),
                    start_date=str(r.get("start_date") or ""),
                    end_date=r.get("end_date"),
                    source_url=r.get("source_url"),
                )
            )
        except Exception:
            continue
    return [r for r in out if r.release_track and r.season_id and r.start_date]


def _save(records: list[SeasonRecord], path: str = DEFAULT_CALENDAR_PATH) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "seasons": [
            {
                "release_track": r.release_track,
                "season_id": r.season_id,
                "start_date": r.start_date,
                "end_date": r.end_date,
                "source_url": r.source_url,
            }
            for r in sorted(records, key=lambda x: (x.release_track, x.start_date, x.season_id))
        ]
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_current_season_id(release_track: str, as_of: str | None = None, path: str = DEFAULT_CALENDAR_PATH) -> Optional[str]:
    """Resolve the most recent season_id whose start_date <= as_of.

    If calendar is empty or no match, return None.
    """
    records = [r for r in _load(path) if r.release_track == release_track]
    if not records:
        return None

    as_of_d = date.fromisoformat(as_of) if as_of else date.today()

    best: SeasonRecord | None = None
    for r in records:
        try:
            sd = date.fromisoformat(r.start_date)
        except Exception:
            continue
        if sd <= as_of_d and (best is None or sd > date.fromisoformat(best.start_date)):
            best = r

    return best.season_id if best else None


_DATE_RE = re.compile(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b")


def maybe_update_from_evidence(
    release_track: str,
    season_id: str,
    evidence: list[EvidenceSnippet],
    path: str = DEFAULT_CALENDAR_PATH,
) -> bool:
    """Controlled write:

    Only write when we have *official* evidence (us.forums.blizzard.com) and can parse
    an ISO-like date (YYYY-MM-DD or YYYY/M/D) from the snippet.

    Returns True if calendar file was updated.
    """
    if not release_track or not season_id or not evidence:
        return False

    # Only accept official forum as a source for calendar updates (MVP governance).
    official = [e for e in evidence if "us.forums.blizzard.com" in (e.source_url or "")]
    if not official:
        return False

    # Parse the first date-like token.
    start_date: str | None = None
    source_url: str | None = None
    for e in official:
        m = _DATE_RE.search(e.snippet or "")
        if not m:
            continue
        yyyy, mm, dd = m.groups()
        start_date = f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
        source_url = e.source_url
        break

    if not start_date:
        return False

    records = _load(path)
    # Upsert by (release_track, season_id)
    updated = False
    new_records: list[SeasonRecord] = []
    for r in records:
        if r.release_track == release_track and r.season_id == season_id:
            new_records.append(SeasonRecord(release_track=release_track, season_id=season_id, start_date=start_date, end_date=r.end_date, source_url=source_url or r.source_url))
            updated = True
        else:
            new_records.append(r)

    if not updated:
        new_records.append(SeasonRecord(release_track=release_track, season_id=season_id, start_date=start_date, end_date=None, source_url=source_url))
        updated = True

    if updated:
        _save(new_records, path)

    return updated
