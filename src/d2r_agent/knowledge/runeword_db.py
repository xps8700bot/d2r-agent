"""Structured runeword KB loader from data/fact_db/runewords.json."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunewordVariant:
    item_type: str
    sockets: int
    min_rlvl: int
    rune_order: str  # e.g. "Tal + Thul + Ort + Amn"
    modifiers: list[dict]  # raw modifier objects from JSON


@dataclass
class RunewordEntry:
    name: str
    variants: list[RunewordVariant]
    source_url: str | None


@dataclass
class RunewordHit:
    entry: RunewordEntry
    score: int


_ALIASES: dict[str, str] = {
    # Chinese aliases → English runeword name
    # ── Core farming/combat RWs ──────────────────────────────────────────
    "精神": "Spirit",
    "眼光": "Insight",
    "洞察": "Insight",
    "信仰": "Faith",
    "末日": "Doom",
    "无极": "Infinity",
    "奉献": "Obedience",
    "冰霜": "Crescent Moon",
    "死亡": "Death",
    # ── New: Basin RotW confirmed aliases ───────────────────────────────
    "悲伤": "Grief",
    "痛苦": "Grief",
    "梦境": "Dream",
    "永恒": "Eternity",
    "流亡": "Exile",
    "谜团": "Enigma",
    "谜": "Enigma",
    "荣耀之手": "Hand of Justice",
    "橡木之心": "Heart of the Oak",
    "霍塔": "Heart of the Oak",
    "誓言": "Oath",
    "疯狂": "Chaos",
    "混沌": "Chaos",
    "凤凰": "Phoenix",
    "荣耀": "Honor",
    "骨骼": "Bone",
    "激情": "Passion",
    "热情": "Passion",
    "震怒": "Fury (Rune Word)",
    "愤怒": "Fury (Rune Word)",
    "荆棘": "Bramble",
    "堡垒": "Fortitude",
    "坚固": "Fortitude",
    "毒液": "Venom (Rune Word)",
    "圣雷": "Holy Thunder",
    "苦役": "Last Wish",
    "辉耀": "Radiance",
    "繁荣": "Wealth",
    "隐匿": "Treachery",
    "背叛": "Treachery",
    "呼唤武装": "Call to Arms",
    "武装号召": "Call to Arms",
    "荣誉": "Chains of Honor",
    "荣誉之链": "Chains of Honor",
    "王者恩典": "King's Grace",
    "雨": "Rain",
    # ── Extended aliases (Part A expansion) ─────────────────────────────
    # Enigma
    "谜语": "Enigma",
    "秘符": "Enigma",
    "变形": "Enigma",
    # Infinity
    "无限": "Infinity",
    # Fortitude
    "坚韧": "Fortitude",
    "坚强": "Fortitude",
    # Chains of Honor
    "荣誉锁链": "Chains of Honor",
    "coh": "Chains of Honor",
    # Call to Arms
    "战斗呼号": "Call to Arms",
    "呼号": "Call to Arms",
    "cta": "Call to Arms",
    # Beast
    "野兽": "Beast",
    "兽灵": "Beast",
    # Breath of the Dying
    "亡者之息": "Breath of the Dying",
    "botd": "Breath of the Dying",
    # Doom
    "厄运": "Doom",
    # Grief
    "哀恸": "Grief",
    # Hand of Justice
    "正义之手": "Hand of Justice",
    "hoj": "Hand of Justice",
    # Heart of the Oak
    "橡心": "Heart of the Oak",
    "hoto": "Heart of the Oak",
    # Last Wish
    "最后心愿": "Last Wish",
    # Lawbringer
    "执法者": "Lawbringer",
    # Lore
    "学识": "Lore",
    # Meditation
    "冥想": "Meditation",
    # Nadir
    "极地": "Nadir",
    # Oath
    "誓约": "Oath",
    # Obedience
    "顺服": "Obedience",
    "服从": "Obedience",
    # Plague
    "瘟疫": "Plague",
    # Pride
    "傲慢": "Pride",
    # Prudence
    "明智": "Prudence",
    # Rift
    "裂谷": "Rift",
    # Sanctuary
    "圣殿": "Sanctuary",
    # Silence
    "沉默": "Silence",
    # Smoke
    "烟雾": "Smoke",
    # Splendor
    "灿烂": "Splendor",
    "辉煌": "Splendor",
    # Steel
    "钢铁": "Steel",
    # Stone
    "石头": "Stone",
    # Voice of Reason
    "理性之声": "Voice of Reason",
    # White
    "白色": "White",
    # Wind
    "风": "Wind",
    # Wrath
    "怒火": "Wrath",
    # Zephyr
    "和风": "Zephyr",
}


def _load_runewords(path: str) -> list[RunewordEntry]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    rws_raw = data.get("runewords", [])
    results: list[RunewordEntry] = []
    for rw in rws_raw:
        name = rw.get("name", "")
        sources = rw.get("sources", [])
        source_url = sources[0].get("url") if sources else None
        variants: list[RunewordVariant] = []
        for v in rw.get("variants", []):
            variants.append(
                RunewordVariant(
                    item_type=v.get("item_type", ""),
                    sockets=v.get("sockets", 0),
                    min_rlvl=v.get("min_rlvl", 0),
                    rune_order=v.get("rune_order_and_modifiers", ""),
                    modifiers=v.get("runeword_modifiers", []),
                )
            )
        results.append(RunewordEntry(name=name, variants=variants, source_url=source_url))
    return results


def search_runewords(user_query: str, path: str, limit: int = 3) -> list[RunewordHit]:
    """Find runeword entries matching user query by name/alias keyword matching."""
    q = (user_query or "").strip()
    if not q:
        return []

    q_lower = q.lower()
    # Resolve Chinese aliases to English names
    resolved_terms: list[str] = []
    for cn, en in _ALIASES.items():
        if cn in q or cn in q_lower:
            resolved_terms.append(en.lower())
    # Also add raw tokens from query
    tokens = [t for t in q_lower.replace("(", " ").replace(")", " ").replace("?", " ").split() if len(t) >= 3]
    resolved_terms.extend(tokens)

    entries = _load_runewords(path)
    hits: list[RunewordHit] = []
    for entry in entries:
        name_lower = entry.name.lower()
        score = 0
        for term in resolved_terms:
            if term in name_lower:
                score += 2  # name match is stronger
            elif name_lower in term:
                score += 1
        if score > 0:
            hits.append(RunewordHit(entry=entry, score=score))

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]


def format_runeword_hit(hit: RunewordHit) -> str:
    """Format a runeword entry as a compact evidence string."""
    e = hit.entry
    lines = [f"**{e.name}** (符文之语)"]
    for v in e.variants:
        rune_order = v.rune_order.split("\n")[0] if "\n" in v.rune_order else v.rune_order
        # rune_order may include modifiers in some entries; trim to first line or just rune sequence
        # The field is "rune_order_and_modifiers" so it may be long; extract rune part
        rune_part = rune_order.split("(")[0].strip()
        lines.append(
            f"  • {v.item_type} | {v.sockets} 孔 | 需要等级 {v.min_rlvl} | 符文: {rune_part}"
        )
    if e.source_url:
        lines.append(f"  来源: {e.source_url}")
    return "\n".join(lines)
