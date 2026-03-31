"""Build/validate mechanics fact DB.

Phase 0: basic JSONL validation for MechanicsFactRecord shape.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from d2r_agent.knowledge.mechanics_schema import MechanicsFactRecord


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args()

    ok = 0
    bad = 0
    for pth in args.paths:
        p = Path(pth)
        if not p.exists():
            print(f"missing: {pth}")
            bad += 1
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                MechanicsFactRecord.model_validate(obj)
                ok += 1
            except Exception as e:
                print(f"invalid {pth}:{i}: {e}")
                bad += 1

    print(f"records ok={ok} bad={bad}")
    raise SystemExit(0 if bad == 0 else 1)


if __name__ == "__main__":
    main()
