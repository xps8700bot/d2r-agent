#!/usr/bin/env python3
"""
D2R Agent - Factbase Ingest Script
Usage: python scripts/ingest_factbase.py --src /tmp/d2data_src

Reads raw JSON data from a blizzhackers/d2data clone and outputs
cleaned/filtered facts to data/facts/ for use by the D2R agent.

Source: https://github.com/blizzhackers/d2data
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MONSTATS_LITE_FIELDS = [
    "Id", "NameStr", "MonType", "enabled",
    "Level", "Level(N)", "Level(H)",
    "minHP", "maxHP", "MinHP(N)", "MaxHP(N)", "MinHP(H)", "MaxHP(H)",
    "AC", "AC(N)", "AC(H)",
    "Exp", "Exp(N)", "Exp(H)",
    "ResFi", "ResLi", "ResCo", "ResPo", "ResDm",
    "ResFi(N)", "ResLi(N)", "ResCo(N)", "ResPo(N)", "ResDm(N)",
    "ResFi(H)", "ResLi(H)", "ResCo(H)", "ResPo(H)", "ResDm(H)",
    "demon", "undead", "boss", "primeevil", "killable", "threat",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(src_dir: Path, filename: str):
    """Load a JSON file from src_dir/json/. Returns (data_as_list, raw_dict_or_list)."""
    path = src_dir / "json" / filename
    if not path.exists():
        print(f"  [WARN] {filename} not found at {path}", file=sys.stderr)
        return [], None
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, list):
        return raw, raw
    elif isinstance(raw, dict):
        return list(raw.values()), raw
    else:
        print(f"  [WARN] {filename} has unexpected type: {type(raw)}", file=sys.stderr)
        return [], raw


def save_json(out_path: Path, data, label: str, orig_count: int = None):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    count = len(data) if isinstance(data, (list, dict)) else "?"
    if orig_count is not None and orig_count != count:
        print(f"  {label}: {orig_count} → {count} records  ({out_path.name})")
    else:
        print(f"  {label}: {count} records  ({out_path.name})")
    return count


def get_src_version(src_dir: Path) -> str:
    """Try to get git commit hash from src_dir."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=src_dir, capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Ingest d2data facts into data/facts/")
    parser.add_argument("--src", required=True, help="Path to blizzhackers/d2data clone")
    parser.add_argument("--out", default=None, help="Output directory (default: data/facts/ relative to script)")
    args = parser.parse_args()

    src_dir = Path(args.src).resolve()
    if not src_dir.exists():
        print(f"ERROR: --src {src_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    # Output dir: default = <project_root>/data/facts/
    if args.out:
        out_dir = Path(args.out).resolve()
    else:
        # scripts/ -> project root -> data/facts/
        project_root = Path(__file__).parent.parent
        out_dir = project_root / "data" / "facts"

    print(f"Source : {src_dir}")
    print(f"Output : {out_dir}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    stats = {}

    # -----------------------------------------------------------------------
    # core/
    # -----------------------------------------------------------------------
    print("=== core/ ===")

    records, _ = load_json(src_dir, "allstrings-eng.json")
    # allstrings is a plain dict key→string; keep as-is
    raw_allstrings_path = src_dir / "json" / "allstrings-eng.json"
    if raw_allstrings_path.exists():
        with open(raw_allstrings_path, encoding="utf-8") as f:
            allstrings_data = json.load(f)
        n = save_json(out_dir / "core" / "allstrings-eng.json", allstrings_data,
                      "allstrings-eng", len(allstrings_data))
        stats["core/allstrings-eng.json"] = n

    records, raw = load_json(src_dir, "properties.json")
    n = save_json(out_dir / "core" / "properties.json", records, "properties")
    stats["core/properties.json"] = n

    records, raw = load_json(src_dir, "itemstatcost.json")
    n = save_json(out_dir / "core" / "itemstatcost.json", records, "itemstatcost")
    stats["core/itemstatcost.json"] = n

    # -----------------------------------------------------------------------
    # items/
    # -----------------------------------------------------------------------
    print("\n=== items/ ===")

    # runes_complete.json: keep only complete == 1
    records, raw = load_json(src_dir, "runes.json")
    orig = len(records)
    # complete field can be int 1 or string "1"; filter accordingly
    filtered = [r for r in records if str(r.get("complete", "")) == "1"]
    n = save_json(out_dir / "items" / "runes_complete.json", filtered, "runes_complete", orig)
    stats["items/runes_complete.json"] = {"total": orig, "filtered": n}
    if orig - n > 0:
        print(f"    (dropped {orig - n} placeholder/incomplete rune entries)")

    for fname, label in [
        ("gems.json",        "gems"),
        ("uniqueitems.json", "uniqueitems"),
        ("setitems.json",    "setitems"),
        ("sets.json",        "sets"),
        ("armor.json",       "armor"),
        ("weapons.json",     "weapons"),
    ]:
        records, _ = load_json(src_dir, fname)
        n = save_json(out_dir / "items" / fname, records, label)
        stats[f"items/{fname}"] = n

    # -----------------------------------------------------------------------
    # crafting/
    # -----------------------------------------------------------------------
    print("\n=== crafting/ ===")

    records, _ = load_json(src_dir, "cubemain.json")
    n = save_json(out_dir / "crafting" / "cubemain.json", records, "cubemain")
    stats["crafting/cubemain.json"] = n

    # -----------------------------------------------------------------------
    # monsters/
    # -----------------------------------------------------------------------
    print("\n=== monsters/ ===")

    # monstats_lite.json: only core fields
    records, _ = load_json(src_dir, "monstats.json")
    orig = len(records)
    # Collect all available fields across all records (they're sparse)
    all_monstats_keys = set()
    for rec in records:
        all_monstats_keys.update(rec.keys())
    missing_fields = [f for f in MONSTATS_LITE_FIELDS if f not in all_monstats_keys]
    if missing_fields:
        print(f"    [WARN] Fields not found in any monstats record: {missing_fields}")

    lite = []
    for rec in records:
        slim = {field: rec[field] for field in MONSTATS_LITE_FIELDS if field in rec}
        lite.append(slim)
    n = save_json(out_dir / "monsters" / "monstats_lite.json", lite, "monstats_lite", orig)
    stats["monsters/monstats_lite.json"] = {"total": orig, "lite_fields": len(MONSTATS_LITE_FIELDS)}

    records, _ = load_json(src_dir, "superuniques.json")
    n = save_json(out_dir / "monsters" / "superuniques.json", records, "superuniques")
    stats["monsters/superuniques.json"] = n

    # -----------------------------------------------------------------------
    # skills/
    # -----------------------------------------------------------------------
    print("\n=== skills/ ===")

    # skills_player.json: only records with non-empty charclass
    records, _ = load_json(src_dir, "skills.json")
    orig = len(records)
    player_skills = [r for r in records if r.get("charclass")]
    n = save_json(out_dir / "skills" / "skills_player.json", player_skills, "skills_player", orig)
    stats["skills/skills_player.json"] = {"total": orig, "filtered": n}
    if orig - n > 0:
        print(f"    (dropped {orig - n} non-player/monster skill entries)")

    records, _ = load_json(src_dir, "skilldesc.json")
    n = save_json(out_dir / "skills" / "skilldesc.json", records, "skilldesc")
    stats["skills/skilldesc.json"] = n

    # -----------------------------------------------------------------------
    # world/
    # -----------------------------------------------------------------------
    print("\n=== world/ ===")

    for fname, label in [
        ("levels.json",          "levels"),
        ("treasureclassex.json", "treasureclassex"),
    ]:
        records, _ = load_json(src_dir, fname)
        n = save_json(out_dir / "world" / fname, records, label)
        stats[f"world/{fname}"] = n

    # -----------------------------------------------------------------------
    # meta.json
    # -----------------------------------------------------------------------
    src_version = get_src_version(src_dir)
    meta = {
        "ingest_at": datetime.now(timezone.utc).isoformat(),
        "src_version": src_version,
        "src_path": str(src_dir),
        "stats": stats,
    }
    save_json(out_dir / "meta.json", meta, "meta")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print("\n=== Summary ===")
    total_bytes = sum(
        p.stat().st_size for p in out_dir.rglob("*.json")
    )
    file_count = sum(1 for _ in out_dir.rglob("*.json"))
    print(f"Files written : {file_count}")
    print(f"Total size    : {total_bytes / 1024:.1f} KB ({total_bytes:,} bytes)")
    print(f"Src commit    : {src_version}")
    print(f"\nDone! Facts written to: {out_dir}")


if __name__ == "__main__":
    main()
