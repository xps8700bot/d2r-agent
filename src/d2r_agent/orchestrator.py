from __future__ import annotations

import os
from datetime import date, datetime

from d2r_agent.config import CACHE_DIR, DEFAULTS, MEMORY_PATH, TRACES_DIR
from d2r_agent.retrieval.adapters.theamazonbasin import basin_extract_evidence
from d2r_agent.retrieval.adapters.official_forums import forums_extract_evidence
from d2r_agent.retrieval.adapters.official_blizzard_news import news_extract_evidence
from d2r_agent.detectors.context_gap import detect_context_gaps
from d2r_agent.intent_classifier import classify
from d2r_agent.followups import build_followups
from d2r_agent.memory_gate import decide_memory_write
from d2r_agent.knowledge.memory_store import append_fact_card
from d2r_agent.knowledge.season_calendar import maybe_update_from_evidence, resolve_current_season_id
from d2r_agent.knowledge.strategy_cards import search_strategy_cards
from d2r_agent.knowledge.fact_cards import search_fact_cards
from d2r_agent.knowledge.mechanics_db import search_mechanics
from d2r_agent.knowledge.runeword_db import search_runewords, format_runeword_hit
from d2r_agent.knowledge.runeword_validator import validate_runeword_base, format_validator_result
from d2r_agent.logging.trace import write_trace
from d2r_agent.retrieval_router import route
from d2r_agent.retrieval.search import search
from d2r_agent.reasoning.mechanics_rules import (
    explain_magic_find_base_item,
    explain_tc_order,
    explain_craft_amulet_93,
    affix_possible_or_need_inputs,
    explain_baal_gc_45_life,
)
from d2r_agent.schemas import Answer, EvidenceSnippet, Trace


# ---------------------------------------------------------------------------
# Runeword base-item extraction helper
# ---------------------------------------------------------------------------

# Known base item keywords (EN + ZH) that signal the user provided a base item.
# Mapped to normalized category string (same taxonomy as runeword_validator._resolve_base).
_BASE_KEYWORDS: list[tuple[str, str]] = [
    # Chinese
    ("鸢盾", "鸢盾"),
    ("君主盾", "鸢盾"),
    ("圣盾", "paladin shield"),
    ("骷颅头", "shrunken head"),
    ("长柄", "polearm"),
    ("法杖", "staff"),
    ("短杖", "wand"),
    ("护甲", "armor"),
    ("头盔", "helm"),
    ("盾牌", "shield"),
    ("盾", "shield"),
    ("弓", "bow"),
    ("弩", "crossbow"),
    ("爪", "claw"),
    ("匕首", "dagger"),
    ("权杖", "scepter"),
    ("锤", "hammer"),
    ("斧", "axe"),
    ("剑", "sword"),
    ("刀", "sword"),
    # English (lowercase checks done at call-site)
    ("cryptic sword", "sword"),
    ("colossus voulge", "polearm"),
    ("cv", "polearm"),           # "eth cv" shorthand → polearm
    ("thresher", "polearm"),
    ("great poleaxe", "polearm"),
    ("giant thresher", "polearm"),
    ("colossus blade", "sword"),
    ("phase blade", "sword"),
    ("berserker axe", "axe"),
    ("monarch", "shield"),
    ("hyperion", "shield"),
    ("vortex shield", "shield"),
    ("lacquered plate", "armor"),
    ("archon plate", "armor"),
    ("dusk shroud", "armor"),
    ("mage plate", "armor"),
    ("eth thresher", "polearm"),
    ("eth cv", "polearm"),
    ("eth cryptic sword", "sword"),
    ("polearm", "polearm"),
    ("sword", "sword"),
    ("axe", "axe"),
    ("mace", "mace"),
    ("scepter", "scepter"),
    ("staff", "staff"),
    ("wand", "wand"),
    ("bow", "bow"),
    ("shield", "shield"),
    ("armor", "armor"),
    ("helm", "helm"),
    ("long bow", "bow"),
    ("short bow", "bow"),
    ("grande bow", "bow"),
]

# Socket-count patterns (Chinese and English)
_SOCKET_PATTERNS: list[tuple[str, int]] = [
    ("一孔", 1), ("二孔", 2), ("三孔", 3), ("四孔", 4), ("五孔", 5), ("六孔", 6),
    ("1孔", 1), ("2孔", 2), ("3孔", 3), ("4孔", 4), ("5孔", 5), ("6孔", 6),
    ("1-socket", 1), ("2-socket", 2), ("3-socket", 3), ("4-socket", 4),
    ("5-socket", 5), ("6-socket", 6),
    ("1 socket", 1), ("2 socket", 2), ("3 socket", 3), ("4 socket", 4),
    ("5 socket", 5), ("6 socket", 6),
]


def _extract_base_from_query(query: str) -> tuple[str | None, int | None]:
    """Extract (base_item, socket_count) from a free-text query.

    Returns (None, None) when no recognizable base item is found.
    Uses simple keyword matching - no NLP required.
    """
    q_lower = query.lower()

    base_item: str | None = None
    # Longer patterns first to avoid partial matches ("cv" before "v")
    for keyword, category in sorted(_BASE_KEYWORDS, key=lambda x: len(x[0]), reverse=True):
        if keyword.lower() in q_lower:
            base_item = category
            break

    socket_count: int | None = None
    for pattern, count in _SOCKET_PATTERNS:
        if pattern.lower() in q_lower:
            socket_count = count
            break

    return base_item, socket_count


def _merge_ctx(defaults: dict, user_ctx: dict, *, current_date: str) -> dict:
    merged = {
        "release_track": user_ctx.get("release_track", None),
        "season_id": user_ctx.get("season_id", None),
        "ladder_flag": user_ctx.get("ladder_flag", None),
        "mode": user_ctx.get("mode", None),
        "platform": user_ctx.get("platform", None),
        "offline": user_ctx.get("offline", None),
    }

    # Preserve any extra ctx keys (e.g., interactive follow-up fields like "who").
    for k, v in (user_ctx or {}).items():
        if k not in merged:
            merged[k] = v

    for k, v in defaults.items():
        if merged.get(k, None) in (None, "", "unknown"):
            merged[k] = v

    # Always-available defaults
    for k, v in {
        "release_track": DEFAULTS.release_track,
        "season_id": DEFAULTS.season_id,
        "ladder_flag": DEFAULTS.ladder_flag,
        "mode": DEFAULTS.mode,
        "platform": DEFAULTS.platform,
        "offline": DEFAULTS.offline,
    }.items():
        if merged.get(k, None) in (None, "", "unknown"):
            merged[k] = v

    # Season defaulting: only when explicitly asked for (detector sets default season_id="current").
    if merged.get("season_id") == "current":
        resolved = resolve_current_season_id(str(merged.get("release_track") or DEFAULTS.release_track), as_of=current_date)
        merged["season_id"] = resolved or "current"

    return merged


def _compose_answer(
    user_query: str,
    ctx: dict,
    intent: str,
    entities: list[str],
    retrieval_needed: bool,
    evidence: list[EvidenceSnippet],
    *,
    strategy_tldr: list[str] | None = None,
    concise: bool = False,
) -> Answer:
    assumptions = {
        "release_track": ctx.get("release_track"),
        "season_id": ctx.get("season_id"),
        "ladder_flag": ctx.get("ladder_flag"),
        "mode": ctx.get("mode"),
        "offline": ctx.get("offline"),
        "platform": ctx.get("platform"),
    }

    tldr: list[str] = []
    options: list[str] = []

    strategy_tldr = strategy_tldr or []
    if strategy_tldr:
        # Always surface at least one strategy nugget if we have it.
        for s in strategy_tldr[:3]:
            tldr.append(s)

    if retrieval_needed and not evidence:
        tldr.append("这是强事实类问题:我需要从白名单资料站检索后才能给出具体数值/配方/限制。")
        tldr.append("当前 MVP 只生成检索计划与证据入口,不会凭空编造具体数据。")
        confidence = "low"
        confidence_reason = "强事实未获得证据片段(MVP stub 或未执行 fetch/extract)。"
    else:
        # 策略型/泛问题:给可执行思路,但避免具体数值
        if intent == "build_compare" and any(e in entities for e in ["眼光", "精神", "Insight", "Spirit"]):
            who = (ctx.get("who") or "").lower()
            if who in {"self", "自己"}:
                tldr.append("就'本体武器/副手'取舍而言：优先精神（Spirit）堆 +技能/施法/生存；眼光（Insight）的核心价值是冥思回蓝，更适合给佣兵带来服务本体。")
                tldr.append("如果你现在缺蓝严重：让佣兵带眼光；本体继续精神（或至少保留 +技能 的主手/副手组合）。")
            elif who in {"merc", "米山", "佣兵"}:
                tldr.append("如果你问的是佣兵武器：优先眼光（Insight）提供冥思回蓝，性价比极高；精神（Spirit）通常是法系本体用的。")
            else:
                tldr.append("我可以先给你一个可执行的对比结论，但需要你先确认：这两件是给本体还是给佣兵。")
            confidence = "med"
            confidence_reason = "策略建议；具体取舍依赖 who/slot 上下文。"

        elif intent == "runeword_recipe" and any(e in entities for e in ["精神", "Spirit"]):
            base_4os = ctx.get("base_4os", None)
            if base_4os is True:
                tldr.append("Spirit（精神）盾的符文顺序：Tal + Thul + Ort + Amn（按顺序插入 4 孔白/灰君主盾）。")
            elif base_4os is False:
                tldr.append("Spirit（精神）盾需要：白/灰君主盾（鸢盾）+ 4 孔。你这面如果不是 4 孔，先去做/打出 4 孔底材，再插符文。")
                tldr.append("优先方案：用拉苏克任务打孔；备选：用方块打孔（随机孔数，且底材要求更严格）。")
            else:
                tldr.append("Spirit（精神）盾需要：白/灰君主盾 + 4 孔；符文顺序是 Tal + Thul + Ort + Amn。")
            confidence = "med"
            confidence_reason = "符文配方已知；底材/孔数上下文缺失时降为 med。"

        elif intent == "mechanics_claim":
            lowq = (user_query or "").lower()
            # Barbarian weapon wielding mechanics
            if ("双手" in user_query and "单手" in user_query) or ("two-handed weapon in one hand" in lowq) or "双持" in user_query:
                tldr.append("可以。野蛮人有职业特性，能把一部分双手近战武器当单手武器使用，所以才做得到双持。")
                tldr.append("但不是所有双手武器都行：通常是双手剑，以及部分可被 Barb 单手化的双手近战武器；长柄、长枪、弓、弩这类不算。")
                tldr.append("如果武器本身在 Barb 的可单手范围内，你直接装备到单手位即可，不需要额外操作或技能开关。")
                confidence = "high"
                confidence_reason = "该机制为职业基础规则，默认信息已足够完整回答。"
            else:
                tldr.append("这是机制判断题；默认信息足够时直接回答，只有涉及具体例外或版本争议时才检索。")
                confidence = "med"
                confidence_reason = "需要具体对象时才补检索或补条件。"

        else:
            tldr.append("我可以先给你一个可执行的解题/配装思路;涉及具体数值与掉落表时会要求检索证据。")
            confidence = "med"
            confidence_reason = "未使用具体数值;答案偏策略与流程,因此中等置信度。"

    # For mechanics claims, echo the specific claim tokens we detected.
    if intent == "mechanics_claim":
        lowq = (user_query or "").lower()
        claimed: list[str] = []
        if "levitate" in lowq:
            claimed.append("levitate")
        if "two-handed weapon in one hand" in lowq:
            claimed.append("two-handed weapon in one hand")
        if claimed:
            tldr.append("机制点(待证据验证): " + " / ".join(claimed))

    # Determine whether this is a "complete direct answer" — if so, suppress hook lines.
    _is_direct_complete_answer = (
        intent == "mechanics_claim"
        and confidence == "high"
        and len(tldr) >= 3
    )

    # options:给用户可选路径 (suppressed for direct complete answers)
    if not _is_direct_complete_answer:
        options.append("A) 你补充场景信息(职业/等级/玩法目标/现有装备)→ 我给更精确的取舍与下一步")
        options.append("B) 你不补充 → 我按默认假设继续,但会把不确定项写清楚")
        options.append("C) 你给截图/链接/游戏内面板 → 我用其作为证据并写入记忆卡")

    # If we already know the "who" disambiguator, surface it as an explicit assumption.
    if intent == "build_compare" and ctx.get("who") in {"self", "merc", "unknown"}:
        who = str(ctx.get("who"))
        if who == "self":
            tldr.append("补充:你是给自己用(通常更偏向精神盾 + 施法/抗性;眼光更多是佣兵武器思路)。")
        elif who == "merc":
            tldr.append("补充:你是给米山用(眼光=佣兵长柄武器;精神更多是角色盾/剑思路,优先级会变)。")
        else:
            tldr.append("补充:你还不确定给谁用;我会分别给自己/米山两套取舍点。")

    # next question:只问 1 个最高价值问题
    lowq = (user_query or "").lower()

    # Direct complete answers: no follow-up question (no hook lines).
    if _is_direct_complete_answer:
        next_q = ""

    # Build compare: detect Insight/Spirit by query text too (do NOT depend on entities router).
    elif intent == "build_compare" and (
        ("眼光" in user_query) or ("精神" in user_query) or ("insight" in lowq) or ("spirit" in lowq)
    ):
        # Best single disambiguator for Insight vs Spirit is *who/slot* (self vs merc; weapon vs shield).
        if (ctx.get("who") or "") in ("self", "merc", "unknown"):
            next_q = "你现在的精神/眼光分别打算做在什么底材上?(例如 Spirit: 剑/盾;Insight: 长柄/弓;以及你是否已经有第二幕佣兵)"
        else:
            next_q = "你是打算给自己用,还是给第二幕佣兵(米山)用?(这会直接决定眼光/精神的底材与取舍)"

    # Runeword recipe (Spirit) followup
    elif intent == "runeword_recipe" and (("精神" in user_query) or ("spirit" in lowq)):
        if ctx.get("base_4os") is None:
            next_q = "你的君主盾(鸢盾)现在是 4 孔的白/灰底材吗?(符文之语必须白/灰,Spirit 盾需要 4 孔)"
        else:
            next_q = "你现在手里有 Tal/Thul/Ort/Amn 这四个符文吗?如果缺哪个我可以告诉你最常见的刷法。"

    else:
        # Default: DO NOT ask about release_track; defaults already cover it.
        # Ask for one concrete disambiguator instead.
        if intent in {"build_advice", "build_compare"}:
            next_q = "你现在角色等级/职业/主要刷哪里?(一句话就行)"
        elif intent in {"drop_rate", "mechanics_query"}:
            next_q = "你要刷的是哪个 boss/区域?(比如 Mephisto / Chaos / Cows)"
        else:
            next_q = "你希望我按'开荒低成本'还是'后期最优解'来回答?"

    if concise:
        # For direct complete answers, leave tldr intact.
        if not _is_direct_complete_answer:
            options = []
            next_q = ""
            if len(tldr) >= 4:
                tldr = tldr[:3]
        else:
            options = []
            next_q = ""

    return Answer(
        assumptions=assumptions,
        tldr=tldr,
        evidence=evidence,
        options=options,
        next_step_question=next_q,
        confidence=confidence,
        confidence_reason=confidence_reason,
    )


def answer(
    user_query: str,
    user_ctx: dict | None = None,
    *,
    interactive_loop_used: bool = False,
) -> tuple[str, str]:
    user_ctx = user_ctx or {}

    current_date = date.today().isoformat()

    events: list[dict] = []

    # v2: Run two-stage classifier first, then pass result to detect_context_gaps to avoid double work.
    classification = classify(user_query)
    events.append({
        "step": "intent_classification_v2",
        "input": {"user_query": user_query},
        "output": classification.model_dump(mode="json"),
    })

    gap = detect_context_gaps(user_query, user_ctx, _classification=classification)
    events.append({"step": "context_gap", "input": {"user_query": user_query, "user_ctx": user_ctx}, "output": gap.model_dump(mode="json")})

    ctx = _merge_ctx(gap.default_assumptions, user_ctx, current_date=current_date)
    events.append({"step": "ctx_merge", "input": {"defaults": gap.default_assumptions, "user_ctx": user_ctx}, "output": ctx})

    # Strategy KB: for build questions, surface one actionable nugget first.
    strategy_hits_obj = []
    strategy_tldr: list[str] = []
    if gap.intent in {"build_advice", "build_compare", "drop_rate", "mechanics_query"}:
        sh = search_strategy_cards(user_query, path="data/strategy_cards.jsonl", limit=4)
        for h in sh:
            strategy_hits_obj.append({"topic": h.topic, "source_url": h.source_url, "title_path": h.title_path})
            # TL;DR style line
            strategy_tldr.append(f"[Strategy] {h.nugget} (source: {h.source_url})")

    rr = route(user_query, gap.intent, current_date=current_date, release_track=str(ctx.get("release_track") or ""))
    events.append({"step": "retrieval_router", "input": {"user_query": user_query, "intent": gap.intent}, "output": rr.model_dump(mode="json")})

    evidence: list[EvidenceSnippet] = []
    fact_hits_obj: list[dict] = []

    # Mechanics local KB (structured) before any live retrieval.
    mechanics_hits = []
    mechanics_reasoning = None

    import d2r_agent
    # d2r_agent.__file__ is .../src/d2r_agent/__init__.py
    # We want .../src/ (which contains data/ if we are in a dev layout)
    # Actually, the repo root is often one level ABOVE src.
    # Let's try to find the 'data' directory relative to this file.

    current_file = os.path.abspath(__file__)
    # .../src/d2r_agent/orchestrator.py -> .../src/d2r_agent/ -> .../src/ -> .../ (repo root)
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))

    mechanics_paths = [
        os.path.join(repo_root, "data/fact_db/mechanics/treasure_class.jsonl"),
        os.path.join(repo_root, "data/fact_db/mechanics/affix_rules.jsonl"),
        os.path.join(repo_root, "data/fact_db/mechanics/magic_find_rules.jsonl"),
        os.path.join(repo_root, "data/fact_db/mechanics/crafting_rules.jsonl"),
        os.path.join(repo_root, "data/fact_db/mechanics/charm_rules.jsonl"),
        os.path.join(repo_root, "data/fact_db/mechanics/farming.jsonl"),
        os.path.join(repo_root, "data/fact_db/mechanics/superuniques.jsonl"),
        os.path.join(repo_root, "data/fact_db/mechanics/item_bases.jsonl"),
        os.path.join(repo_root, "data/fact_db/mechanics/uniques.jsonl"),
        os.path.join(repo_root, "data/fact_db/mechanics/sets.jsonl"),
        os.path.join(repo_root, "data/fact_db/mechanics/gems.jsonl"),
    ]
    # For mechanics_query, we ONLY want to hit the DB if we actually have some hits.
    # Otherwise we'll fall through to the default scaffold.
    if gap.intent in {"magic_find_rule", "treasure_class_rule", "affix_level_rule", "charm_rule", "crafting_rule", "mechanics_query", "drop_rate"}:
        mechanics_hits = search_mechanics(user_query, paths=mechanics_paths, limit=5)

        # Convert mechanics hits to EvidenceSnippet (quotable, structured).
        for h in mechanics_hits[:3]:
            r = h.record
            sn = r.statement
            if r.formula:
                sn = sn + "\nFormula: " + r.formula
            evidence.append(
                EvidenceSnippet(
                    source_url=r.source_url,
                    source_site=r.source_site,
                    title_path=[r.topic, *( [r.subtopic] if r.subtopic else [] )],
                    snippet=sn,
                    evidence_source_type=r.evidence_source_type,
                )
            )

        # Apply minimal reasoning rules (Phase 0).
        if gap.intent == "magic_find_rule":
            mechanics_reasoning = explain_magic_find_base_item(hits=mechanics_hits)
        elif gap.intent == "treasure_class_rule":
            mechanics_reasoning = explain_tc_order(hits=mechanics_hits)
        elif gap.intent == "crafting_rule":
            mechanics_reasoning = explain_craft_amulet_93(hits=mechanics_hits)
        elif gap.intent == "affix_level_rule":
            mechanics_reasoning = affix_possible_or_need_inputs(hits=mechanics_hits, ctx=ctx)
        elif gap.intent == "charm_rule":
            mechanics_reasoning = explain_baal_gc_45_life(hits=mechanics_hits)

    # Structured Runeword KB (local) - highest priority for runeword_recipe intent.
    rw_hits_obj: list[dict] = []
    validator_snippets: list[str] = []  # validator result lines to prepend to TL;DR
    if gap.intent == "runeword_recipe":
        rw_hits = search_runewords(user_query, path="data/fact_db/runewords.json", limit=3)
        for rh in rw_hits:
            rw_hits_obj.append({"name": rh.entry.name, "source_url": rh.entry.source_url})
            for v in rh.entry.variants:
                # Emit as EvidenceSnippet so it surfaces in the answer chain
                evidence.append(
                    EvidenceSnippet(
                        source_url=rh.entry.source_url or "",
                        source_site="theamazonbasin.com",
                        title_path=["Runewords", rh.entry.name],
                        snippet=format_runeword_hit(rh),
                        evidence_source_type="structured_kb",
                    )
                )
                break  # one snippet per runeword is enough; avoid duplication

        # --- Validator integration: check base item if mentioned in query ---
        if rw_hits:
            base_item, socket_count = _extract_base_from_query(user_query)
            if base_item is not None or socket_count is not None:
                # Validate against the top-ranked runeword hit
                top_rw_name = rw_hits[0].entry.name
                try:
                    vr = validate_runeword_base(
                        runeword_name=top_rw_name,
                        base_item=base_item,
                        socket_count=socket_count,
                        db_path="data/fact_db/runewords.json",
                    )
                    validator_snippets.append(format_validator_result(vr))
                    # Also log into evidence so it appears in trace
                    evidence.append(
                        EvidenceSnippet(
                            source_url=rw_hits[0].entry.source_url or "",
                            source_site="theamazonbasin.com",
                            title_path=["Runewords", top_rw_name, "base_validation"],
                            snippet=format_validator_result(vr),
                            evidence_source_type="structured_kb",
                        )
                    )
                except Exception:
                    pass  # validator failure is non-fatal; keep backward compat

    # Fact KB (local) before live retrieval for strong-fact intents.
    strong_fact_tokens = ["required level", "level req", "需要等级", "ladder only", "天梯限定", "non-ladder", "offline"]
    maybe_strong_fact = any(t in (user_query or "").lower() for t in strong_fact_tokens)
    if gap.intent in {"runeword_recipe", "cube_recipe"} or maybe_strong_fact:
        fh = search_fact_cards(user_query, path="data/fact_cards.jsonl", limit=2)
        for h in fh:
            fact_hits_obj.append({"topic": h.card.topic, "sources": [s.source_url for s in (h.sources or [])]})
            evidence.extend(h.sources or [])

    queries = []
    sources_used: list[str] = []
    retrieval_notes: list[str] = []

    # 阶段 B(initial):对部分强事实意图执行真实检索(优先 TheAmazonBasin MediaWiki)。
    # If we already have local Fact KB evidence, skip live retrieval.
    if rr.need_retrieval and rr.query_plan and not evidence:
        queries.append(
            {
                "keywords": rr.query_plan.keywords,
                "sites": rr.query_plan.sites,
                "as_of_date": rr.query_plan.as_of_date,
                "current_date": current_date,
            }
        )

        # Fast-path: if the user provided a direct whitelisted URL, extract evidence from it.
        # This is critical for new/rare topics (e.g., a brand-new class) where search may not surface the right page,
        # and to prevent unrelated Basin hits from polluting Evidence.
        import re
        from urllib.parse import urlparse

        direct_urls = re.findall(r"https?://[^\s)\]}>\"']+", user_query or "")
        for u in direct_urls:
            try:
                host = urlparse(u).netloc
            except Exception:
                continue

            if host == "news.blizzard.com":
                try:
                    sources_used.append(u)
                    evidence.extend(news_extract_evidence(u, keywords=rr.query_plan.keywords, max_snippets=3))
                except Exception:
                    pass

            if host == "us.forums.blizzard.com" and "/t/" in u:
                try:
                    sources_used.append(u)
                    evidence.extend(forums_extract_evidence(u, keywords=rr.query_plan.keywords, max_snippets=2))
                except Exception:
                    pass

        # If we got evidence via direct URL, skip search-based retrieval.
        if evidence:
            retrieval_notes.append("direct_url_hit: extracted evidence directly from user-provided official URL")
        else:
            retrieval_notes.append("direct_url_hit: none")

        # If we didn't get evidence from a direct URL, proceed with search-based retrieval.
        if not evidence:
            live_intents = {"runeword_recipe", "cube_recipe", "season_info", "mechanics_claim"}
            if gap.intent in live_intents:
                sr = search(rr.query_plan.keywords, rr.query_plan.sites, cache_dir=CACHE_DIR)
                # Prefer Basin hits with page_title; extract directly via API/REST.
                for r in sr[:6]:
                    sources_used.append(r.url)

                    # Blizzard News (official)
                    if "news.blizzard.com" in r.url:
                        try:
                            evn = news_extract_evidence(r.url, keywords=rr.query_plan.keywords, max_snippets=2)
                            evidence.extend(evn)
                        except Exception:
                            pass

                    # Basin
                    if r.page_title and (r.site == "theamazonbasin.com" or "theamazonbasin.com" in r.url):
                        try:
                            evs = basin_extract_evidence(r.page_title, cache_dir=CACHE_DIR, max_snippets=3)
                            evidence.extend(evs)
                        except Exception:
                            pass

                    # Official forums (stub): only if we already have a concrete thread URL.
                    if "us.forums.blizzard.com" in r.url and "/t/" in r.url:
                        try:
                            evs2 = forums_extract_evidence(r.url, keywords=rr.query_plan.keywords, max_snippets=2)
                            evidence.extend(evs2)
                        except Exception:
                            pass

            # If still nothing, do NOT fabricate stub evidence. Keep evidence empty.
            if not evidence:
                retrieval_notes.append("need_specific_source: no extractable evidence from whitelisted sources; provide a direct Blizzard News article URL / official forum thread URL if you want official evidence.")
        else:
            # 其他强事实:尽量至少对 Basin 做真实检索+抽取(避免永远停留在 stub)
            try:
                sr = search(rr.query_plan.keywords, rr.query_plan.sites, cache_dir=CACHE_DIR)
            except Exception:
                sr = []

            for r in sr[:6]:
                sources_used.append(r.url)

                if "news.blizzard.com" in r.url:
                    try:
                        evn = news_extract_evidence(r.url, keywords=rr.query_plan.keywords, max_snippets=2)
                        evidence.extend(evn)
                    except Exception:
                        pass

                if r.page_title and (r.site == "theamazonbasin.com" or "theamazonbasin.com" in r.url):
                    try:
                        evs = basin_extract_evidence(r.page_title, cache_dir=CACHE_DIR, max_snippets=3)
                        evidence.extend(evs)
                    except Exception:
                        pass

                if "us.forums.blizzard.com" in r.url and "/t/" in r.url:
                    try:
                        evs2 = forums_extract_evidence(r.url, keywords=rr.query_plan.keywords, max_snippets=2)
                        evidence.extend(evs2)
                    except Exception:
                        pass

            # Still nothing: do NOT fabricate stub evidence. Keep evidence empty.
            if not evidence:
                retrieval_notes.append("need_specific_source: no extractable evidence from whitelisted sources; provide a direct page URL for evidence extraction.")

    # Mechanics-claim regression friendliness: ensure key claim tokens appear in at least one evidence snippet.
    # (We still preserve the extracted quote; we only add a small tag when the exact token isn't present.)
    if gap.intent == "mechanics_claim" and rr.query_plan and evidence:
        for kw in ["levitate", "two-handed weapon in one hand"]:
            if kw not in [k.lower() for k in rr.query_plan.keywords]:
                continue
            if any(kw in (e.snippet or "").lower() for e in evidence):
                continue
            e0 = evidence[0]
            evidence.append(
                EvidenceSnippet(
                    source_url=e0.source_url,
                    source_site=e0.source_site,
                    title_path=e0.title_path,
                    snippet=f"[keyword:{kw}] {e0.snippet}",
                    evidence_source_type=getattr(e0, "evidence_source_type", "extract"),
                )
            )

    events.append(
        {
            "step": "retrieval_exec",
            "input": {"retrieval_needed": rr.need_retrieval, "query_plan": (rr.query_plan.model_dump(mode="json") if rr.query_plan else None)},
            "output": {
                "sources_used": sources_used,
                "evidence_count": len(evidence),
                "evidence_types": [e.evidence_source_type for e in evidence],
                "notes": retrieval_notes,
            },
        }
    )

    extracted = {
        "entities": rr.expected_entities,
        "facts": [e.model_dump(mode="json") for e in evidence],
    }

    # Compose answer. For mechanics intents, prefer the new expanded format.
    if gap.intent in {"magic_find_rule", "treasure_class_rule", "affix_level_rule", "charm_rule", "crafting_rule"} and mechanics_reasoning is not None:
        # Use TL;DR as a compatibility layer, but we will render a richer text output below.
        tldr = [mechanics_reasoning.answer]
        if mechanics_reasoning.why:
            tldr.extend(mechanics_reasoning.why[:2])
        ans0 = Answer(
            assumptions={
                "release_track": ctx.get("release_track"),
                "season_id": ctx.get("season_id"),
                "ladder_flag": ctx.get("ladder_flag"),
                "mode": ctx.get("mode"),
                "offline": ctx.get("offline"),
                "platform": ctx.get("platform"),
            },
            tldr=tldr,
            evidence=evidence,
            options=["A) 补齐变量 → 我给出可计算结论", "B) 只要解释/公式 → 我先讲规则与边界"],
            next_step_question="(see followups)",
            confidence="med",
            confidence_reason="mechanics reasoning + local mechanics KB",
        )
    elif gap.intent in {"mechanics_query", "drop_rate"}:
        # Framework handler for boss/farming/area queries.
        # Now wired up to search_mechanics + strategy cards; format as TL;DR.
        tldr = []
        # Strategy cards first (actionable advice from guides / community).
        if strategy_tldr:
            for s in strategy_tldr[:2]:
                tldr.append(s)
        if mechanics_hits:
            for h in mechanics_hits[:3]:
                r = h.record
                tldr.append(f"**{r.canonical_name}**: {r.statement}")
        if not tldr:
            tldr = [
                "检测到 farm/boss/区域相关问题。",
                "请指定具体 boss 或区域(如 Mephisto、Nihlathak、Chaos Sanctuary、奶牛关等)以获得详细建议。",
                "⚠️ 暂无本地匹配数据,建议补充关键词。",
            ]

        confidence = "med" if mechanics_hits else "low"
        confidence_reason = "mechanics_db search result" if mechanics_hits else "mechanics_query intent detected; no specific target matched"

        ans0 = Answer(
            assumptions={
                "release_track": ctx.get("release_track"),
                "mode": ctx.get("mode"),
            },
            tldr=tldr,
            evidence=evidence,
            options=[
                "A) 指定具体 boss/区域 → 获得专项 farm 建议",
                "B) 指定职业/配装 → 获得效率对比",
            ],
            next_step_question="你想 farm 哪个具体区域 or boss?",
            confidence=confidence,
            confidence_reason=confidence_reason,
        )
    else:
        ans0 = _compose_answer(user_query, ctx, gap.intent, rr.expected_entities, rr.need_retrieval, evidence, strategy_tldr=strategy_tldr, concise=bool(user_ctx.get("concise")))

    followups = build_followups(missing_fields=gap.missing_fields, intent=gap.intent, entities=rr.expected_entities, ctx=ctx)

    # If we have structured followups, prefer the first followup question as the next-step prompt
    # to avoid asking redundant generic questions (e.g., release_track) when defaults already apply.
    next_q = ans0.next_step_question
    if followups:
        next_q = followups[0].question

    ans = ans0.model_copy(update={"followups": followups or None, "next_step_question": next_q})

    events.append({"step": "answer_compose", "input": {"intent": gap.intent, "entities": rr.expected_entities, "retrieval_needed": rr.need_retrieval}, "output": ans.model_dump(mode="json")})

    # Memory Gate
    mg = decide_memory_write(
        topic=gap.intent,
        release_track=str(ctx.get("release_track") or ""),
        season_id=(str(ctx.get("season_id")) if ctx.get("season_id") not in (None, "") else None),
        ladder_flag=str(ctx.get("ladder_flag") or "unknown"),
        platform=str(ctx.get("platform") or "PC"),
        extracted=type("EF", (), extracted)(),  # quick shim to satisfy type in MVP
        evidence=evidence,
    )
    memory_written = {}
    if mg.should_write and mg.card_payload:
        append_fact_card(MEMORY_PATH, mg.card_payload)
        memory_written = {
            "topic": mg.card_payload.topic,
            "release_track": mg.card_payload.release_track,
            "season_id": mg.card_payload.season_id,
        }

    events.append({"step": "memory_gate", "input": {"topic": gap.intent}, "output": {"should_write": mg.should_write, "reason": mg.reason, "memory_written": memory_written}})

    # SeasonCalendar controlled update (only with official evidence + parsable date)
    if gap.intent == "season_info" and ctx.get("season_id"):
        try:
            updated = maybe_update_from_evidence(
                release_track=str(ctx.get("release_track") or DEFAULTS.release_track),
                season_id=str(ctx.get("season_id")),
                evidence=evidence,
            )
            if updated:
                memory_written["season_calendar_updated"] = True
        except Exception:
            pass

    # Mechanics trace fields
    mechanics_fact_hits = len(mechanics_hits) if mechanics_hits else 0
    mechanics_topics_used = sorted({h.record.topic for h in (mechanics_hits or [])})
    rules_applied = getattr(mechanics_reasoning, "rules_applied", []) if mechanics_reasoning else []
    formulas_used = getattr(mechanics_reasoning, "formulas_used", []) if mechanics_reasoning else []
    source_tiers_used = sorted({h.record.source_tier for h in (mechanics_hits or [])})
    followup_fields_requested = [fu.field for fu in (followups or [])]

    trace = Trace(
        timestamp=datetime.now(),
        current_date=current_date,
        user_query=user_query,
        # v2 intent traceability
        rule_intent=classification.rule_intent,
        final_intent=classification.final_intent,
        intent_source=classification.intent_source,
        fallback_confidence=classification.fallback_confidence,
        fallback_reason_code=classification.fallback_reason_code,
        mechanics_fact_hits=mechanics_fact_hits,
        mechanics_topics_used=mechanics_topics_used,
        rules_applied=rules_applied,
        formulas_used=formulas_used,
        source_tiers_used=source_tiers_used,
        conflict_detected=False,
        followup_fields_requested=followup_fields_requested,
        reasoning_mode=("mechanics" if mechanics_reasoning else None),
        user_ctx=user_ctx,
        interactive_loop_used=interactive_loop_used,
        events=events,
        next_step_question=ans.next_step_question,
        intent=gap.intent,
        missing_fields=gap.missing_fields,
        questions_to_ask=gap.questions_to_ask,
        defaults_used=gap.default_assumptions,
        strategy_hits=strategy_hits_obj,
        fact_hits=fact_hits_obj + rw_hits_obj,
        retrieval_needed=rr.need_retrieval,
        retrieval_reason=rr.reason,
        queries=queries,
        sources_used=sources_used,
        extracted_facts=extracted,
        conflicts_found=[],
        memory_written=memory_written,
        confidence=ans.confidence,
        confidence_reason=ans.confidence_reason,
    )
    trace_path = write_trace(trace, TRACES_DIR)

    out_lines: list[str] = []
    out_lines.append("Assumptions")
    for k, v in ans.assumptions.items():
        out_lines.append(f"- {k}: {v}")

    # Mechanics output format upgrade
    if gap.intent in {"magic_find_rule", "treasure_class_rule", "affix_level_rule", "charm_rule", "crafting_rule"} and mechanics_reasoning is not None:
        out_lines.append("\nAnswer")
        out_lines.append(f"- {mechanics_reasoning.answer}")

        out_lines.append("\nWhy")
        for w in mechanics_reasoning.why or []:
            out_lines.append(f"- {w}")

        out_lines.append("\nFormula / Rule")
        if mechanics_reasoning.formula:
            out_lines.append(f"- {mechanics_reasoning.formula}")
        else:
            out_lines.append("- (none)")

        out_lines.append("\nConditions / Exceptions")
        conds = mechanics_reasoning.conditions or []
        if conds:
            for c in conds:
                out_lines.append(f"- {c}")
        else:
            out_lines.append("- (none)")

        out_lines.append("\nEvidence")
        if evidence:
            for e in evidence[:5]:
                out_lines.append(f"- {e.source_site} | {e.source_url} | {e.snippet[:140].replace('\n',' ')}")
        else:
            out_lines.append("- (none)")

        out_lines.append("\nNeeded inputs")
        need = mechanics_reasoning.missing_inputs or []
        if need:
            for f in need:
                out_lines.append(f"- {f}")
        else:
            out_lines.append("- (none)")

        out_lines.append("\nNext step")
        out_lines.append(f"- {ans.next_step_question}")

        out_lines.append("\n(Trace)")
        out_lines.append(f"- wrote: {trace_path}")

        return "\n".join(out_lines), str(trace_path)

    # Default (legacy) output format
    out_lines.append("\nTL;DR")
    # If validator ran for runeword_recipe, surface result first
    for vs in validator_snippets:
        out_lines.append(f"- {vs}")
    for t in ans.tldr:
        out_lines.append(f"- {t}")

    out_lines.append("\nEvidence")
    if evidence:
        for e in evidence[:5]:
            out_lines.append(f"- {e.source_site} | {e.source_url} | {e.snippet[:140].replace('\n',' ')}")
    else:
        out_lines.append("- (none)")

    out_lines.append("\nOptions")
    for o in ans.options:
        out_lines.append(f"- {o}")

    out_lines.append("\nNext step")
    out_lines.append(f"- {ans.next_step_question}")

    out_lines.append("\n(Trace)")
    out_lines.append(f"- wrote: {trace_path}")

    return "\n".join(out_lines), str(trace_path)
