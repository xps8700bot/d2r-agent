"""Placeholder for DiabloWiki mechanics ingestion.

Phase 0: kept minimal; will be expanded with table/heading extraction.
"""

from __future__ import annotations

import argparse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    _ = ap.parse_args()
    raise SystemExit("Not implemented yet (Phase 0 placeholder).")


if __name__ == "__main__":
    main()
