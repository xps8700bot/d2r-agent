from __future__ import annotations

import re

from d2r_agent.config import DEFAULTS
from d2r_agent.intent_classifier import ClassificationResult, classify
from d2r_agent.schemas import ContextGapResult


# ---------------------------------------------------------------------------
# Public helpers — kept for backward compat with any direct callers
# ---------------------------------------------------------------------------

def classify_intent(q: str) -> str:
    """Simple rule-only classification (Stage 1 only).

    Prefer calling classify() for full two-stage classification with traceability.
    This thin wrapper is kept for tests that call it directly.
    """
    from d2r_agent.intent_classifier import classify_intent_rules
    return classify_intent_rules(q)


def classify_intent_v2(q: str) -> ClassificationResult:
    """Full two-stage classification (rules + LLM fallback) with traceability."""
    return classify(q)


# 每类 intent 的 MVI（最小必要信息）
MVI_FIELDS: dict[str, list[str]] = {
    "runeword_recipe": ["release_track", "ladder_flag"],
    "cube_recipe": ["release_track"],
    "drop_rate": ["release_track", "mode", "offline"],
    "build_advice": ["release_track", "mode", "offline"],
    "build_compare": ["release_track", "mode", "offline"],
    "patch_change": ["release_track"],
    "mechanics_claim": [],

    # Mechanics rules: still need release governance, plus domain-specific variables (asked via followups, not required here).
    "magic_find_rule": ["release_track"],
    "treasure_class_rule": ["release_track"],
    "affix_level_rule": ["release_track"],
    "charm_rule": ["release_track"],
    "crafting_rule": ["release_track"],

    # Season/ladder enable/disable questions are season-scoped.
    "season_info": ["release_track", "season_id"],
    # Farming / boss / area queries need release_track and mode to tailor advice.
    "mechanics_query": ["release_track", "mode"],
    "general": ["release_track"],
}


def detect_context_gaps(
    user_query: str,
    user_ctx: dict,
    *,
    _classification: "ClassificationResult | None" = None,
) -> ContextGapResult:
    """Detect context gaps using v2 two-stage classifier.

    Pass _classification to reuse a pre-computed result and avoid a double LLM call.
    """
    if _classification is None:
        _classification = classify(user_query)
    intent = _classification.final_intent
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
