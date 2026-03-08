from __future__ import annotations

import re

from d2r_agent.config import DEFAULTS
from d2r_agent.schemas import ContextGapResult


# 阶段 A：简单规则 intent 分类（关键词 + 同义词）
INTENT_RULES: list[tuple[str, list[str]]] = [
    ("runeword_recipe", ["符文之语", "runeword", "顺序", "怎么做", "配方", "enigma", "谜团", "grief", "悔恨"]),
    ("cube_recipe", ["公式", "合成", "赫拉迪克方块", "cube", "craft", "手工", "caster", "blood"]),
    # IMPORTANT: do not treat difficulty/act words as drop-rate intent by themselves.
    # Require explicit drop/rate/location cues.
    ("drop_rate", ["掉落", "掉率", "概率", "drop", "drop rate", "哪里出", "哪出", "在哪刷", "刷哪里", "countess", "女伯爵"]),
    ("build_compare", ["还是", "哪个好", "选哪个", "对比", "vs", "V.S.", "比较"]),
    ("build_advice", ["配装", "bd", "build", "思路", "加点", "开荒", "预算", "刷图", "刷安姐", "刷巴尔"]),
    ("patch_change", ["2.", "改动", "patch", "版本", "nerf", "buff", "加强", "削弱"]),
    # Mechanics / hard-rule claims ("can/can't", passive interactions, wielding rules, etc.)
    ("mechanics_claim", [
        "能不能",
        "可以吗",
        "是否",
        "机制",
        "被动",
        "passive",
        "one hand",
        "one-hand",
        "two hand",
        "two-hand",
        "two-handed",
        "levitate",
        "levitation",
    ]),
    # Season governance / ladder enablement
    ("season_info", ["season", "赛季", "ladder", "天梯", "disabled", "禁用", "封禁", "结束了吗", "什么时候开始", "start date"]),
]


def classify_intent(q: str) -> str:
    s = q.lower()

    # Heuristic: comparisons like "X 还是 Y" are almost always build/gear advice, even if the
    # sentence also contains difficulty/act words (e.g., "地狱第一幕").
    if re.search(r"(还是|哪个好|选哪个|对比|\bvs\b)", s, flags=re.I):
        # Require at least two non-trivial tokens around the comparator.
        if re.search(r"\S+\s*(还是|vs|对比|比较)\s*\S+", q):
            return "build_compare"

    for intent, kws in INTENT_RULES:
        for kw in kws:
            if kw.lower() in s:
                return intent
    return "general"


# 每类 intent 的 MVI（最小必要信息）
MVI_FIELDS: dict[str, list[str]] = {
    "runeword_recipe": ["release_track", "ladder_flag"],
    "cube_recipe": ["release_track"],
    "drop_rate": ["release_track", "mode", "offline"],
    "build_advice": ["release_track", "mode", "offline"],
    "build_compare": ["release_track", "mode", "offline"],
    "patch_change": ["release_track"],
    "mechanics_claim": ["release_track"],
    # Season/ladder enable/disable questions are season-scoped.
    "season_info": ["release_track", "season_id"],
    "general": ["release_track"],
}


def detect_context_gaps(user_query: str, user_ctx: dict) -> ContextGapResult:
    intent = classify_intent(user_query)
    required = MVI_FIELDS.get(intent, ["release_track"])

    # Missing is evaluated against *effective ctx* = user_ctx overlaid on DEFAULTS.
    # If DEFAULTS already provides a value, we should not pester the user.
    missing: list[str] = []
    for f in required:
        v = user_ctx.get(f, None)
        if v in (None, "", "unknown"):
            # fall back to DEFAULTS
            dv = getattr(DEFAULTS, f, None)
            if dv in (None, "", "unknown"):
                missing.append(f)

    # 追问最多 3 个，优先影响结论最大的字段
    questions = []
    if "release_track" in missing:
        questions.append("你问的是哪个发布轨道 release_track？（默认 d2r_roitw；如有 PTR/经典版等请说明）")
    if "season_id" in missing:
        questions.append("你问的是哪个赛季 season_id？（例如 current / S10；不填我会按“当前赛季”处理）")
    if "ladder_flag" in missing:
        questions.append("你是天梯(Ladder)还是非天梯/单机？（ladder / non-ladder / offline）")
    if "mode" in missing:
        questions.append("你是软核(SC)还是硬核(HC)？")
    if "offline" in missing:
        questions.append("你是离线(offline)还是在线(online)？")

    questions = questions[:3]

    # 默认假设（用户不答也继续）
    defaults_used = {}
    # Only include defaults_used for fields that are actually missing.
    if "release_track" in missing:
        defaults_used["release_track"] = DEFAULTS.release_track
    if "season_id" in missing:
        # Keep 'current' sentinel so merge_ctx resolves it to a concrete season id.
        defaults_used["season_id"] = "current"
    if "ladder_flag" in missing:
        defaults_used["ladder_flag"] = DEFAULTS.ladder_flag
    if "mode" in missing:
        defaults_used["mode"] = DEFAULTS.mode
    if "offline" in missing:
        defaults_used["offline"] = DEFAULTS.offline

    return ContextGapResult(
        intent=intent,
        missing_fields=missing,
        questions_to_ask=questions,
        default_assumptions=defaults_used,
    )
