"""Intent Classifier v2 — rule-first + LLM fallback.

Stage 1: deterministic rule classifier (keyword + heuristics).
Stage 2: LLM fallback for rule misses (intent == 'general').

The result includes full traceability:
  rule_intent, final_intent, intent_source, fallback_confidence, fallback_reason_code.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Literal

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Allowed intent values
# ---------------------------------------------------------------------------
VALID_INTENTS = frozenset({
    "runeword_recipe",
    "magic_find_rule",
    "treasure_class_rule",
    "affix_level_rule",
    "charm_rule",
    "crafting_rule",
    "cube_recipe",
    "drop_rate",
    "build_compare",
    "build_advice",
    "patch_change",
    "mechanics_claim",
    "season_info",
    "mechanics_query",
    "general",
})

# ---------------------------------------------------------------------------
# Fallback output schema (constrained)
# ---------------------------------------------------------------------------
FallbackConfidence = Literal["high", "med", "low"]
FallbackReasonCode = Literal[
    "weapon_interaction_rule",
    "mechanic_capability_question",
    "boss_farming_question",
    "gear_tradeoff",
    "recipe_query",
    "season_timing",
    "unknown",
]


class FallbackClassification(BaseModel):
    """Constrained output from LLM fallback classifier."""

    intent: str = Field(description="One of the allowed VALID_INTENTS values.")
    confidence: FallbackConfidence = Field(description="Classification confidence: high|med|low")
    reason_code: FallbackReasonCode = Field(default="unknown", description="Short enum reason code.")
    needs_review: bool = Field(default=False, description="True if human review is recommended.")


# ---------------------------------------------------------------------------
# Full classification result (traceability)
# ---------------------------------------------------------------------------
class ClassificationResult(BaseModel):
    """Full intent classification result with provenance."""

    rule_intent: str
    final_intent: str
    intent_source: Literal["rule", "llm_fallback"]
    fallback_confidence: FallbackConfidence | None = None
    fallback_reason_code: FallbackReasonCode | None = None
    fallback_needs_review: bool = False


# ---------------------------------------------------------------------------
# Stage 1: Rule classifier
# ---------------------------------------------------------------------------

# NOTE: rules are evaluated in order; first match wins.
INTENT_RULES: list[tuple[str, list[str]]] = [
    ("runeword_recipe", ["符文之语", "runeword", "顺序", "怎么做", "配方", "enigma", "谜团", "grief", "悔恨"]),

    # Mechanics-focused intents (must be checked BEFORE generic drop_rate)
    ("magic_find_rule", ["mf", "magic find", "魔法找到率", "寻宝", "掉宝", "递减"]),
    ("treasure_class_rule", [
        "tc", "treasure class", "掉落表", "掉落池", "品质选择哪个先", "max socket", "max_socket",
        "最大孔数", "孔数", "qlvl", "alvl", "ilvl", "ilvl_breakpoints", "防御", "str req", "力量要求", "机制", "技能",
    ]),
    ("affix_level_rule", ["affix", "词缀", "前缀", "后缀"]),
    ("charm_rule", ["gc", "grand charm", "技能板", "45 life", "45life", "baal gc", "巴尔 gc", "护身符"]),
    ("crafting_rule", ["craft 项链", "caster amulet", "手工项链", "crafted amulet", "93级", "93 级"]),

    ("cube_recipe", ["公式", "合成", "赫拉迪克方块", "cube", "recipe", "blood craft"]),

    ("drop_rate", [
        "掉落", "掉率", "drop", "drop rate", "哪里出", "哪出", "在哪刷", "刷哪里", "countess", "女伯爵",
        # English item-hunting phrases
        "where to find", "looking for", "hunting for",
    ]),
    ("build_compare", ["还是", "哪个好", "选哪个", "对比", "vs", "V.S.", "比较"]),
    ("build_advice", [
        # CJK
        "配装", "bd", "build", "思路", "加点", "开荒", "预算", "刷图", "刷安姐", "刷巴尔",
        # English — classes (full + common abbreviations).
        # Class nouns alone aren't enough to *uniquely* indicate build-advice
        # (they could appear in lore questions), but in practice 95%+ of
        # Reddit questions that mention a class + anything else are asking
        # for build / gear / leveling advice.
        "warlock", "sorceress", "sorc", "sorc's", "paladin", "pally",
        "barbarian", "barb", "druid", "necromancer", "necro",
        "amazon", "zon", "bowazon", "javazon", "assassin", "sin",
        # English — archetypes
        "hammerdin", "zealot", "smiter", "fishymancer", "wind druid",
        "fury druid", "frenzy barb", "whirlwind barb", "ww barb",
        "bone necro", "summoner necro", "trap sin", "kick sin",
        "blizzard sorc", "blizz sorc", "lightning sorc", "fire sorc",
        "cold sorc", "meteorb", "frenzy", "blessed hammer",
        # English — leveling / gearing phrases
        "leveling", "gearing", "gear setup", "end game gear", "endgame gear",
        "starter build", "beginner build", "build advice", "build help",
        "dealing with immunes", "fire immunes", "cold immunes",
        "lightning immunes", "poison immunes", "physical immunes",
        "hell difficulty", "going into hell", "transitioning to hell",
        # English — Warlock-specific skill/mechanic phrases (RotW)
        "consume", "consuming", "bound demon", "bind demon", "defiler",
        "defilers", "echoing strike", "death sigil", "abyss",
    ]),
    ("patch_change", ["2.", "改动", "patch", "版本", "nerf", "buff", "加强", "削弱"]),

    # Mechanics / hard-rule claims
    # Note: "双持" is handled by the co-occurrence heuristic above, not as a standalone keyword
    # (to avoid over-triggering on build-advice queries like "双持旋风蛮开荒怎么配").
    ("mechanics_claim", [
        "能不能", "可以吗", "是否",
        "被动", "passive",
        "one hand", "one-hand",
        "two hand", "two-hand", "two-handed",
        "levitate", "levitation",
    ]),

    # Season governance
    ("season_info", [
        "season", "赛季", "ladder", "天梯",
        "disabled", "禁用", "封禁", "结束了吗", "什么时候开始", "start date",
    ]),

    # Farming / boss / area mechanics queries
    ("mechanics_query", [
        "farm", "怎么farm", "怎么刷", "在哪farm",
        "boss", "怪", "monster", "精英", "区域",
        # Herald / Sunder / Terror Zone mechanics (RotW 2.5+)
        "herald", "heralds", "先驱者", "传令官",
        "sunder", "sunder charm", "sunders", "碎裂护符", "碎裂",
        "terror zone", "terrorize", "terrorized", "恐怖区域", "恐怖地带",
        "tz", "terror", "ire",
        "nihlathak", "尼拉萨克", "cows", "奶牛", "chaos sanctuary", "混沌圣殿",
        "baal run", "巴尔跑", "diablo run", "暗黑跑", "mephisto", "梅菲斯托",
        "shenk", "pindle", "巴尔", "刷图效率", "刷图路线",
        "countess", "女伯爵", "andariel", "安达利尔", "duriel", "都瑞尔",
        "墨菲斯托", "迪亚波罗", "diablo", "mephisto",
        "山克", "皮叔", "暴躁外皮", "pindleskin", "奶牛王", "cow king",
        "埃尔德里奇", "eldritch", "hephasto", "helphesto", "海法斯特", "碎骨者", "bonebreak",
        "unique", "暗金", "shako", "小丑帽", "arachnid", "蜘蛛腰带",
        "soj", "约旦之石", "索命戒", "war traveler", "战旅",
        "griffon", "鹰眼", "mara", "玛拉", "andys", "andy", "安达利尔面具",
        "oculus", "天眼", "windforce", "风之力", "thundergods", "雷霆腰带",
        "tgods", "homunculus", "小矮人盾", "chance guards", "幸运手套",
        "shaftstop", "shaft stop", "减伤甲", "verdungo", "维丁格", "减伤腰带",
        "titan", "提坦复仇", "亚马逊矛", "crown of ages", "coa", "时代王冠",
        "nightwing", "夜翼面纱", "寒冰头盔", "jalal", "贾拉尔", "德鲁伊头盔",
        "death's fathom", "死亡深渊", "寒冰宝珠", "trang", "特兰格手套", "法师手套",
        "套装", "set", "tal rasha", "塔拉夏", "tal set", "immortal king", "不朽之王",
        "ik set", "natalya", "娜塔莉亚", "nat set", "griswold", "格里斯沃德",
        "aldur", "阿尔杜尔", "mavina", "玛薇娜", "sigon", "西贡",
        "cow king set", "奶牛王套装",
        "tal rasha's adjudication", "塔拉夏护身符", "塔项链", "塔护",
        "dwarf star", "矮星", "火免戒", "火戒指",
        "raven frost", "渡鸦霜", "冰免戒", "冰戒", "rf",
        "bk ring", "bk戒", "婚戒", "布尔卡索斯", "bul-kathos",
        "highlord", "海洛德", "闪电暗金项链",
        "宝石", "gem", "skull", "骷髅", "amethyst", "紫晶", "ruby", "红宝石",
        "sapphire", "蓝宝石", "topaz", "黄宝石", "emerald", "绿宝石",
        "diamond", "钻石", "perfect gem", "完美宝石", "flawless", "无瑕",
        "宝石升级", "gem upgrade", "魔找宝石", "mf gem", "mf宝石",
        "wisp projector", "wisp", "幽灵投影", "灵球戒", "幽灵戒",
        "string of ears", "soe", "耳环腰带", "缩水腰带",
        "magefist", "魔法拳套", "魔拳",
        "frostburn", "寒霜拳套", "蓝量手套", "冰霜手套",
        "gore rider", "gore", "血腥骑士", "血靴", "骑士靴",
        "peasant crown", "农民冠", "农冠", "PC helm",
        "twitchthroe", "twitch", "抽搐胸甲", "颤抖铠甲",
        "doombringer", "毁灭者", "末日携带者",
        "arreat's face", "arreats face", "阿瑞特之颜", "巴面", "巴巴面具",
        "baranar's star", "baranar", "巴纳之星", "巴拿之星", "巴纳",
        "the grandfather", "grandfather", "老爷剑", "爷爷剑",
        "thunderstroke", "雷击", "雷矛", "亚马逊雷矛", "闪电雷矛",
        "blackbog's sharp", "blackbog", "黑沼毒刃", "黑沼",
        "manald heal", "manald", "曼纳尔愈合戒", "曼纳", "manald ring",
        "metalgrid", "金属网格", "金属链", "全抗项链",
        "cat's eye", "cats eye", "猫眼", "cat eye", "弓手项链", "猫眼护身符",
        "crescent moon", "月牙", "月亮戒",
        "nature's peace", "nature peace", "自然之和", "防复活戒", "骷髅免疫戒",
    ]),
]


def classify_intent_rules(q: str) -> str:
    """Stage 1: deterministic rule-based classification. Returns one of VALID_INTENTS."""
    s = q.lower()

    # Heuristic: comparisons like "X 还是 Y" are almost always build/gear advice.
    if re.search(r"(还是|哪个好|选哪个|对比|\bvs\b)", s, flags=re.I):
        if re.search(r"\S+\s*(还是|vs|对比|比较)\s*\S+", q):
            return "build_compare"

    # Heuristic: "magic find" / "mf" mentioned only in negation context
    # ("no magic find", "without mf", "zero mf", "0 mf") is NOT asking
    # about MF mechanics — skip magic_find_rule so the real intent surfaces.
    _mf_negated = bool(re.search(
        r"\b(no|without|zero|0)\s+(magic\s*find|mf)\b", s
    ))

    # Heuristic: item-farming pattern — "finding X", "trouble finding",
    # "can't find", "where to find" should map to drop_rate before generic
    # keyword matching (which might be hijacked by incidental MF mention).
    if re.search(r"(trouble\s+finding|can'?t\s+find|where\s+to\s+find|having\s+trouble.*finding)", s):
        return "drop_rate"

    # Heuristic: Chinese weapon-mode mechanics — "单手" + "双手" co-occurrence
    # Only trigger mechanics_claim when BOTH appear together (interrogative weapon-mode question).
    # "双持" alone is NOT sufficient: it's commonly used in build contexts ("双持旋风蛮开荒").
    # "双持" + interrogative modal ("能不能" / "可以吗" / "是否") → mechanics_claim.
    _interrogative = ("能不能" in q or "可以吗" in q or "是否" in q or "可以" in q)
    if ("单手" in q and "双手" in q):
        return "mechanics_claim"
    if "双持" in q and _interrogative:
        return "mechanics_claim"

    # Heuristic: class-name + build-context signals → build_advice,
    # even when a recipe keyword (e.g. "runeword") also appears.
    # Actual recipe queries focus on a specific item ("how to make Enigma"),
    # not on class + farming/gearing/leveling context.
    _CLASS_NAMES = {
        "warlock", "sorceress", "sorc", "paladin", "pally",
        "barbarian", "barb", "druid", "necromancer", "necro",
        "amazon", "zon", "assassin", "sin",
    }
    _BUILD_CONTEXT = {
        "farm", "farming", "solo", "gearing", "leveling", "debating",
        "build", "spec", "respec", "skill tree", "early hell", "late hell",
        "starter", "beginner", "endgame", "end game",
    }
    _has_class = any(cn in s for cn in _CLASS_NAMES)
    _has_build_ctx = any(bc in s for bc in _BUILD_CONTEXT)
    # Don't let class+farming trigger build_advice when the question is about
    # item/rune farming locations (e.g. "rune farming for paladin").
    _item_farming = bool(re.search(
        r"\b(rune|runes|high rune|hr|lo|sur|ber|jah|ohm|cham|zod|vex|gul|ist)\b.*\b(farm|farming|drop)\b"
        r"|\b(farm|farming|drop)\b.*\b(rune|runes|high rune|hr|lo|sur|ber|jah|ohm|cham|zod|vex|gul|ist)\b",
        s
    ))
    if _item_farming:
        return "drop_rate"
    if _has_class and _has_build_ctx:
        return "build_advice"

    for intent, kws in INTENT_RULES:
        for kw in kws:
            kw_lower = kw.lower()
            # Short keywords (<=3 chars, ASCII) require word-boundary matching
            # to avoid false positives like "tc" matching inside "matches".
            if len(kw_lower) <= 3 and kw_lower.isascii():
                if not re.search(r"(?<![a-z])" + re.escape(kw_lower) + r"(?![a-z])", s):
                    continue
            elif kw_lower not in s:
                continue
            # Skip magic_find_rule when MF is only mentioned in negation
            if intent == "magic_find_rule" and _mf_negated:
                break
            return intent

    return "general"


# ---------------------------------------------------------------------------
# Stage 2: LLM fallback classifier
# ---------------------------------------------------------------------------

_FALLBACK_SYSTEM_PROMPT = """\
You are an intent classifier for a Diablo II Resurrected (D2R) Q&A bot.

Given a user query (often in Chinese), classify its intent using exactly one of these labels:
runeword_recipe, magic_find_rule, treasure_class_rule, affix_level_rule, charm_rule,
crafting_rule, cube_recipe, drop_rate, build_compare, build_advice, patch_change,
mechanics_claim, season_info, mechanics_query, general

Label definitions:
- runeword_recipe: asks for runeword formula / rune order / socket requirements
- magic_find_rule: asks how magic find works, stacking, diminishing returns
- treasure_class_rule: asks about treasure class mechanics, drop pool selection
- affix_level_rule: asks about affix / prefix / suffix level requirements
- charm_rule: asks about charm rules (grand charms, Baal GC life rolls, etc.)
- crafting_rule: asks about crafted item formulas (caster amulet, blood craft, etc.)
- cube_recipe: asks about Horadric Cube formulas (upgrade, repair, token, etc.)
- drop_rate: asks what a specific boss/monster drops or where to find an item
- build_compare: compares two builds, items, or approaches ("A or B?")
- build_advice: asks for build guidance, spec, gear, leveling path
- patch_change: asks about a specific patch change or balance update
- mechanics_claim: asserts or asks whether a game mechanic is possible (can X do Y?)
- season_info: asks about ladder/season status (start/end/reset/availability)
- mechanics_query: asks about farming spots, boss locations, area efficiency
- general: everything else / ambiguous

Respond ONLY with a JSON object with exactly these keys:
  "intent": <string>,
  "confidence": "high"|"med"|"low",
  "reason_code": "weapon_interaction_rule"|"mechanic_capability_question"|"boss_farming_question"|"gear_tradeoff"|"recipe_query"|"season_timing"|"unknown",
  "needs_review": <boolean>

No prose, no explanation — only the JSON object.
"""


def _call_llm_fallback(query: str) -> FallbackClassification | None:
    """Call LLM classifier. Returns None on failure or unavailability."""
    # Support OpenAI-compatible API (env: OPENAI_API_KEY or OPENAI_BASE_URL).
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        log.debug("LLM fallback skipped: OPENAI_API_KEY not set")
        return None

    try:
        import urllib.request

        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model = os.environ.get("D2R_INTENT_MODEL", "gpt-4o-mini")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": _FALLBACK_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            "temperature": 0.0,
            "max_tokens": 120,
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=data,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read())
        raw = body["choices"][0]["message"]["content"].strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.M)
            raw = raw.rstrip("` \n")
        obj = json.loads(raw)
        classification = FallbackClassification.model_validate(obj)
        # Ensure intent is valid
        if classification.intent not in VALID_INTENTS:
            log.warning("LLM fallback returned unknown intent %r; keeping as general", classification.intent)
            classification = classification.model_copy(update={"intent": "general"})
        return classification
    except Exception as exc:
        log.warning("LLM fallback failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Decision policy
# ---------------------------------------------------------------------------

def classify(query: str) -> ClassificationResult:
    """Two-stage intent classification.

    Stage 1: deterministic rules.
    Stage 2: LLM fallback (only when rule returns 'general').

    Decision policy:
      - Strong rule hit -> accept rule result, no LLM call.
      - Rule result == 'general' -> invoke LLM fallback.
      - If fallback returns non-general with confidence high/med -> accept fallback result.
      - If fallback returns low confidence or general -> keep general.
    """
    rule_intent = classify_intent_rules(query)

    if rule_intent != "general":
        # Strong rule hit: accept immediately, no LLM needed.
        return ClassificationResult(
            rule_intent=rule_intent,
            final_intent=rule_intent,
            intent_source="rule",
        )

    # Rule miss / general: try LLM fallback.
    fb = _call_llm_fallback(query)

    if fb is None:
        # LLM unavailable: stay with general.
        return ClassificationResult(
            rule_intent="general",
            final_intent="general",
            intent_source="rule",  # effectively: rule-only path
        )

    # Accept fallback if high/med confidence and non-general intent.
    if fb.intent != "general" and fb.confidence in ("high", "med"):
        return ClassificationResult(
            rule_intent="general",
            final_intent=fb.intent,
            intent_source="llm_fallback",
            fallback_confidence=fb.confidence,
            fallback_reason_code=fb.reason_code,
            fallback_needs_review=fb.needs_review,
        )

    # Low confidence or general from LLM: keep general.
    return ClassificationResult(
        rule_intent="general",
        final_intent="general",
        intent_source="llm_fallback",
        fallback_confidence=fb.confidence,
        fallback_reason_code=fb.reason_code,
        fallback_needs_review=fb.needs_review,
    )
