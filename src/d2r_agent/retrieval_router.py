from __future__ import annotations

import re

from d2r_agent.config import OFFICIAL_WHITELIST_DOMAINS, WHITELIST_DOMAINS
from d2r_agent.schemas import QueryPlan, RetrievalRoute


# 强事实触发器：数值/配方/掉落/版本改动 等必须检索
# NOTE: Avoid using \b word boundaries for CJK text; it can prevent matches.
STRONG_FACT_PATTERNS = [
    r"(几率|概率|掉落|drop|drop rate)",
    r"(公式|配方|recipe|cube|合成)",
    r"(符文之语|runeword|顺序|rune order)",
    r"(2\.[0-9]|patch|版本改动|改动|buff|nerf|削弱|加强)",
    # Numeric / breakpoint / stat-precision questions.
    # Avoid triggering on any digit by requiring a stat-ish context.
    r"(\d+%|\+\d+|\d+\s*(lvl|level|frames?|bp|breakpoint|ias|fcr|fhr|mf|res|damage|ed|str|dex|vit|energy))",
    # Mechanics / hard rules (e.g., whether a class can one-hand a two-handed weapon)
    r"(死灵法师|necromancer).*(单手|one\-hand|一只手).*(双手|two\-hand|两手)",
    r"(双手|two\-hand|两手).*(单手|one\-hand|一只手).*(死灵法师|necromancer)",
]


def _extract_entities(q: str) -> list[str]:
    # MVP：非常粗糙。阶段 B 会接实体词表/别名表
    candidates = []
    m = re.findall(r"\b([A-Za-z]{3,})\b", q)
    candidates.extend(m)
    # 中文括号里的英文名：谜团(Enigma)
    m2 = re.findall(r"\(([A-Za-z]{3,})\)", q)
    candidates.extend(m2)
    # 常见中文名/符文之语（只做轻量别名表；不做数值）
    for zh in [
        "谜团",
        "悔恨",
        "精神",  # Spirit
        "眼光",  # Insight
        "刚毅",
        "橡树之心",
        "无限",
        "执政官",
        "女伯爵",
    ]:
        if zh in q:
            candidates.append(zh)

    # Minimal alias expansion (CJK -> common English page titles)
    if "精神" in q:
        candidates.append("Spirit")
    if "眼光" in q:
        candidates.append("Insight")
    # 去重保持顺序
    seen = set()
    out = []
    for c in candidates:
        if c.lower() in seen:
            continue
        seen.add(c.lower())
        out.append(c)
    return out[:8]


SEASON_ROUTING_PATTERNS = [
    r"(season|赛季|ladder|天梯)",
    r"(disabled|禁用|关闭|结束|重置|reset)",
]


def route(user_query: str, intent: str, current_date: str | None = None, release_track: str | None = None) -> RetrievalRoute:
    q = user_query.lower()
    need = any(re.search(p, q, flags=re.I) for p in STRONG_FACT_PATTERNS)

    season_related = intent == "season_info" or any(re.search(p, q, flags=re.I) for p in SEASON_ROUTING_PATTERNS)

    # Season governance: prefer official Blizzard News, then official forums, then Basin/others.
    if season_related:
        entities = _extract_entities(user_query)
        keywords = entities if entities else [user_query]

        official_first = [s for s in OFFICIAL_WHITELIST_DOMAINS]
        non_official = [s for s in WHITELIST_DOMAINS if s not in official_first]

        # Include a temporal anchor for retrieval traces/queries.
        return RetrievalRoute(
            need_retrieval=True,
            reason="赛季/天梯启用/禁用等属于强事实：优先官方新闻(news.blizzard.com)，其次官方论坛，再到 Basin/资料站交叉验证。",
            query_plan=QueryPlan(
                keywords=keywords,
                sites=[*official_first, *non_official],
                as_of_date=current_date,
            ),
            expected_entities=entities,
        )

    # Mechanics claims: for D2R (d2r_roitw) prioritize official news first.
    if intent == "mechanics_claim":
        entities = _extract_entities(user_query)

        # For mechanics claims, keep the query keywords slightly richer than the entity list.
        keywords: list[str] = []
        if "levitate" in q:
            keywords.append("levitate")
        if "levitation" in q and "levitate" not in keywords:
            keywords.append("levitation")
        if "two-handed" in q and "one" in q and "hand" in q:
            keywords.append("two-handed weapon in one hand")
        if not keywords:
            keywords = entities if entities else [user_query]

        if (release_track or "") == "d2r_roitw":
            sites = [
                # official first
                "news.blizzard.com",
                "us.forums.blizzard.com",
                # then community references for cross-checking
                "theamazonbasin.com",
                "maxroll.gg",
            ]
        else:
            sites = ["theamazonbasin.com", "maxroll.gg", *OFFICIAL_WHITELIST_DOMAINS]

        return RetrievalRoute(
            need_retrieval=True,
            reason="机制/硬规则属于强事实：优先官方公告，其次官方论坛，最后用资料站交叉验证。",
            query_plan=QueryPlan(keywords=keywords, sites=sites, as_of_date=current_date),
            expected_entities=entities,
        )

    # 策略型意图：build_advice / build_compare 默认不检索；只有触发“强事实”才检索
    if intent in {"build_advice", "build_compare"}:
        if need:
            entities = _extract_entities(user_query)
            keywords = entities if entities else [user_query]
            return RetrievalRoute(
                need_retrieval=True,
                reason="策略/对比型问题中出现了数值/配方/版本等强事实触发器，需要检索证据后才能给出精确结论。",
                query_plan=QueryPlan(keywords=keywords, sites=WHITELIST_DOMAINS, as_of_date=current_date),
                expected_entities=entities,
            )

        return RetrievalRoute(
            need_retrieval=False,
            reason="策略/对比型问题：默认先给思路与取舍；涉及具体数值/机制硬规则时再触发检索。",
            # Important: do NOT attach a query_plan when retrieval is not needed.
            # This avoids accidental downstream generation of official /search URLs as 'evidence'.
            query_plan=None,
            expected_entities=_extract_entities(user_query),
        )

    # Intent-level strong facts: recipes, cube formulas, drop rates, patch changes should always retrieve.
    if intent in {"runeword_recipe", "cube_recipe", "drop_rate", "patch_change"}:
        entities = _extract_entities(user_query)
        keywords = entities if entities else [user_query]
        return RetrievalRoute(
            need_retrieval=True,
            reason="该意图属于强事实（配方/公式/掉落/版本改动）：必须检索白名单来源后再给出结论。",
            query_plan=QueryPlan(keywords=keywords, sites=WHITELIST_DOMAINS, as_of_date=current_date),
            expected_entities=entities,
        )

    if need:
        entities = _extract_entities(user_query)
        keywords = entities if entities else [user_query]
        return RetrievalRoute(
            need_retrieval=True,
            reason="检测到强事实（配方/数值/掉落/版本改动）关键词，必须检索白名单来源。",
            query_plan=QueryPlan(keywords=keywords, sites=WHITELIST_DOMAINS, as_of_date=current_date),
            expected_entities=entities,
        )

    return RetrievalRoute(
        need_retrieval=False,
        reason="未检测到强事实触发器；可在无检索条件下回答（但会保持保守）。",
        query_plan=None,
        expected_entities=_extract_entities(user_query),
    )
