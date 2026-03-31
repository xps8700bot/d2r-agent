"""Runeword base-item and socket validator.

Given a runeword name and (optionally) a base item type + socket count,
returns whether the combination is valid — and explains why.

Uses data/fact_db/runewords.json as the authoritative source.
"""
from __future__ import annotations

from dataclasses import dataclass

from .runeword_db import RunewordEntry, RunewordVariant, _load_runewords, search_runewords

# ---------------------------------------------------------------------------
# Item-type taxonomy: maps broad categories to concrete item types they include.
# This lets us resolve "sword" → matches variant item_type "Sword" / "Melee weapon" / "Weapon".
# ---------------------------------------------------------------------------

# Broad category → set of item_types that accept it
_CATEGORY_COVERS: dict[str, set[str]] = {
    # Weapons (melee)
    "sword": {"Sword", "Melee weapon", "Weapon"},
    "axe": {"Axe", "Melee weapon", "Weapon"},
    "mace": {"Mace", "Club", "Hammer", "Melee weapon", "Weapon"},
    "club": {"Club", "Mace", "Hammer", "Melee weapon", "Weapon"},
    "hammer": {"Hammer", "Mace", "Club", "Melee weapon", "Weapon"},
    "scepter": {"Scepter", "Melee weapon", "Weapon"},
    "polearm": {"Polearm", "Melee weapon", "Weapon"},
    "staff": {"Staff", "Weapon"},
    "wand": {"Wand", "Weapon"},
    "dagger": {"Dagger", "Melee weapon", "Weapon"},
    "claw": {"Claw", "Melee weapon", "Weapon"},
    "grimoire": {"Grimoire", "Weapon"},
    # Ranged
    "bow": {"Missile weapon", "Weapon"},
    "crossbow": {"Missile weapon", "Weapon"},
    # Armor
    "body armor": {"Body armor"},
    "armor": {"Body armor"},
    "helm": {"Helm"},
    # Shields
    "shield": {"Shield", "Any Shield"},
    "monarch": {"Shield", "Any Shield"},          # common shorthand
    "paladin shield": {"Paladin item", "Any Shield"},
    "shrunken head": {"Any Shield"},              # druid/necro shields
    # Paladin
    "paladin": {"Paladin item"},
    # Generic broad types
    "melee weapon": {"Melee weapon", "Weapon"},
    "missile weapon": {"Missile weapon", "Weapon"},
    "weapon": {"Weapon", "Melee weapon", "Missile weapon",
               "Sword", "Axe", "Mace", "Club", "Hammer", "Scepter",
               "Polearm", "Staff", "Wand", "Dagger", "Claw", "Grimoire"},
    "any shield": {"Any Shield", "Shield", "Paladin item"},
}

# Chinese shorthand → base category
_ZH_BASE_ALIASES: dict[str, str] = {
    "鸢盾": "shield",
    "君主盾": "shield",
    "圣盾": "paladin shield",
    "骷颅头": "shrunken head",
    "刀": "sword",
    "剑": "sword",
    "大刀": "sword",
    "神兵": "sword",
    "斧": "axe",
    "锤": "hammer",
    "权杖": "scepter",
    "长柄": "polearm",
    "法杖": "staff",
    "短杖": "wand",
    "匕首": "dagger",
    "爪": "claw",
    "弓": "bow",
    "弩": "crossbow",
    "护甲": "armor",
    "头盔": "helm",
    "头部": "helm",
    "盾牌": "shield",
}


def _resolve_base(raw_base: str) -> str:
    """Normalize a raw base string (CN or EN) to lowercase English category key."""
    b = raw_base.strip()
    # Try Chinese alias first
    for zh, en in _ZH_BASE_ALIASES.items():
        if zh in b:
            return en
    return b.lower()


def _item_type_matches(variant_item_type: str, base_category: str) -> bool:
    """Return True if the variant's item_type is compatible with the given base category."""
    vit = variant_item_type.lower()
    bc = base_category.lower()

    # Direct match
    if vit == bc:
        return True

    # Look up which variant types the base_category covers
    covers = _CATEGORY_COVERS.get(bc, set())
    if variant_item_type in covers:
        return True

    # Reverse: if base_category is contained in the variant type's label
    # e.g. base_category="sword" and variant_item_type="Melee weapon"
    if vit in ("weapon", "melee weapon", "missile weapon"):
        # These broad types accept many bases — check if base is one of them
        broad_bases = {
            "weapon": {"sword", "axe", "mace", "club", "hammer", "scepter",
                       "polearm", "staff", "wand", "dagger", "claw", "grimoire",
                       "bow", "crossbow"},
            "melee weapon": {"sword", "axe", "mace", "club", "hammer", "scepter",
                             "polearm", "dagger", "claw"},
            "missile weapon": {"bow", "crossbow"},
        }
        return bc in broad_bases.get(vit, set())

    if vit == "any shield":
        return bc in {"shield", "paladin shield", "shrunken head", "monarch", "any shield"}

    return False


# ---------------------------------------------------------------------------
# Public validator API
# ---------------------------------------------------------------------------

@dataclass
class ValidatorResult:
    runeword_name: str
    valid: bool
    reason: str
    matching_variants: list[RunewordVariant]
    all_variants: list[RunewordVariant]
    required_sockets: list[int]  # all valid socket counts for this RW
    suggestions: list[str]       # human-friendly suggestions if invalid


def validate_runeword_base(
    runeword_name: str,
    base_item: str | None,
    socket_count: int | None,
    db_path: str,
) -> ValidatorResult:
    """Check whether a base item + socket count is valid for the named runeword.

    Args:
        runeword_name: English or Chinese name of the runeword.
        base_item: Item type string (e.g. "sword", "shield", "鸢盾"). None = skip base check.
        socket_count: Number of sockets. None = skip socket check.
        db_path: Path to data/fact_db/runewords.json.
    """
    # Load all RWs and find the one we want
    entries = _load_runewords(db_path)
    entry: RunewordEntry | None = None
    rw_lower = runeword_name.strip().lower()

    # Try exact match first
    for e in entries:
        if e.name.lower() == rw_lower:
            entry = e
            break

    # Fallback: fuzzy search
    if entry is None:
        hits = search_runewords(runeword_name, db_path, limit=1)
        if hits:
            entry = hits[0].entry

    if entry is None:
        return ValidatorResult(
            runeword_name=runeword_name,
            valid=False,
            reason=f"未在 KB 中找到符文之语「{runeword_name}」。请检查拼写或使用英文名。",
            matching_variants=[],
            all_variants=[],
            required_sockets=[],
            suggestions=[],
        )

    all_variants = entry.variants
    required_sockets = sorted(set(v.sockets for v in all_variants))

    # --- Filter by base item type ---
    if base_item:
        base_cat = _resolve_base(base_item)
        base_matched = [v for v in all_variants if _item_type_matches(v.item_type, base_cat)]
    else:
        base_matched = list(all_variants)  # no filter

    if not base_matched and base_item:
        valid_types = sorted(set(v.item_type for v in all_variants))
        suggestions = [f"「{entry.name}」可以制作在以下底材上：{', '.join(valid_types)}"]
        return ValidatorResult(
            runeword_name=entry.name,
            valid=False,
            reason=f"底材「{base_item}」不适用于符文之语「{entry.name}」。",
            matching_variants=[],
            all_variants=all_variants,
            required_sockets=required_sockets,
            suggestions=suggestions,
        )

    # --- Filter by socket count ---
    if socket_count is not None:
        socket_matched = [v for v in base_matched if v.sockets == socket_count]
    else:
        socket_matched = base_matched

    if not socket_matched and socket_count is not None:
        needed = sorted(set(v.sockets for v in base_matched))
        suggestions = []
        if base_item:
            suggestions.append(f"「{entry.name}」在「{base_item}」底材上需要 {needed} 孔（你的是 {socket_count} 孔）。")
        else:
            suggestions.append(f"「{entry.name}」需要 {needed} 孔（你提供的是 {socket_count} 孔）。")
        return ValidatorResult(
            runeword_name=entry.name,
            valid=False,
            reason=f"孔数不匹配：符文之语「{entry.name}」需要 {needed} 孔，提供的是 {socket_count} 孔。",
            matching_variants=base_matched,
            all_variants=all_variants,
            required_sockets=required_sockets,
            suggestions=suggestions,
        )

    # --- All checks passed ---
    reasons = []
    if base_item:
        reasons.append(f"底材「{base_item}」✓")
    if socket_count is not None:
        reasons.append(f"{socket_count} 孔 ✓")
    if socket_matched:
        rune_seq = socket_matched[0].rune_order.split("\n")[0]
        reasons.append(f"符文顺序: {rune_seq}")

    return ValidatorResult(
        runeword_name=entry.name,
        valid=True,
        reason="验证通过：" + "；".join(reasons) if reasons else "验证通过",
        matching_variants=socket_matched,
        all_variants=all_variants,
        required_sockets=required_sockets,
        suggestions=[],
    )


def format_validator_result(result: ValidatorResult) -> str:
    """Render a ValidatorResult as a compact human-readable string."""
    icon = "✅" if result.valid else "❌"
    lines = [f"{icon} **{result.runeword_name}** — {result.reason}"]
    if result.suggestions:
        for s in result.suggestions:
            lines.append(f"  💡 {s}")
    if result.valid and result.matching_variants:
        for v in result.matching_variants:
            rune_seq = v.rune_order.split("\n")[0].split("(")[0].strip()
            lines.append(f"  • {v.item_type} | {v.sockets} 孔 | rlvl {v.min_rlvl} | {rune_seq}")
    return "\n".join(lines)
