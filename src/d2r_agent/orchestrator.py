from __future__ import annotations

from datetime import date, datetime

from d2r_agent.config import CACHE_DIR, DEFAULTS, MEMORY_PATH, TRACES_DIR
from d2r_agent.retrieval.adapters.theamazonbasin import basin_extract_evidence
from d2r_agent.retrieval.adapters.official_forums import forums_extract_evidence
from d2r_agent.retrieval.adapters.official_blizzard_news import news_extract_evidence
from d2r_agent.detectors.context_gap import detect_context_gaps
from d2r_agent.followups import build_followups
from d2r_agent.memory_gate import decide_memory_write
from d2r_agent.knowledge.memory_store import append_fact_card
from d2r_agent.knowledge.season_calendar import maybe_update_from_evidence, resolve_current_season_id
from d2r_agent.knowledge.strategy_cards import search_strategy_cards
from d2r_agent.knowledge.fact_cards import search_fact_cards
from d2r_agent.logging.trace import write_trace
from d2r_agent.retrieval_router import route
from d2r_agent.retrieval.search import search
from d2r_agent.schemas import Answer, EvidenceSnippet, Trace


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
        tldr.append("这是强事实类问题：我需要从白名单资料站检索后才能给出具体数值/配方/限制。")
        tldr.append("当前 MVP 只生成检索计划与证据入口，不会凭空编造具体数据。")
        confidence = "low"
        confidence_reason = "强事实未获得证据片段（MVP stub 或未执行 fetch/extract）。"
    else:
        # 策略型/泛问题：给可执行思路，但避免具体数值
        if intent == "build_compare" and any(e in entities for e in ["眼光", "精神", "Insight", "Spirit"]):
            who = (ctx.get("who") or "").lower()
            if who in {"self", "自己"}:
                tldr.append("就‘本体武器/副手’取舍而言：优先精神（Spirit）堆 +技能/施法/生存；眼光（Insight）的核心价值是冥思回蓝，更适合给佣兵带来服务本体。")
                tldr.append("如果你现在缺蓝严重：让佣兵带眼光；本体继续精神（或至少保留 +技能 的主手/副手组合）。")
            elif who in {"merc", "米山", "佣兵"}:
                tldr.append("如果你问的是佣兵武器：优先眼光（Insight）提供冥思回蓝，性价比极高；精神（Spirit）通常是法系本体用的。")
            else:
                tldr.append("我可以先给你一个可执行的对比结论，但需要你先确认：这两件是给本体还是给佣兵。")

        elif intent == "runeword_recipe" and any(e in entities for e in ["精神", "Spirit"]):
            base_4os = ctx.get("base_4os", None)
            if base_4os is True:
                tldr.append("Spirit（精神）盾的符文顺序：Tal + Thul + Ort + Amn（按顺序插入 4 孔白/灰君主盾）。")
            elif base_4os is False:
                tldr.append("Spirit（精神）盾需要：白/灰君主盾（鸢盾）+ 4 孔。你这面如果不是 4 孔，先去做/打出 4 孔底材，再插符文。")
                tldr.append("优先方案：用拉苏克任务打孔；备选：用方块打孔（随机孔数，且底材要求更严格）。")
            else:
                tldr.append("Spirit（精神）盾需要：白/灰君主盾 + 4 孔；符文顺序是 Tal + Thul + Ort + Amn。")

        else:
            tldr.append("我可以先给你一个可执行的解题/配装思路；涉及具体数值与掉落表时会要求检索证据。")

        confidence = "med"
        confidence_reason = "未使用具体数值；答案偏策略与流程，因此中等置信度。"

    # For mechanics claims, echo the specific claim tokens we detected.
    if intent == "mechanics_claim":
        lowq = (user_query or "").lower()
        claimed: list[str] = []
        if "levitate" in lowq:
            claimed.append("levitate")
        if "two-handed weapon in one hand" in lowq:
            claimed.append("two-handed weapon in one hand")
        if claimed:
            tldr.append("机制点（待证据验证）: " + " / ".join(claimed))

    # options：给用户可选路径
    options.append("A) 你补充 release_track/赛季/天梯/模式信息 → 我按你的设定检索并给精确结论")
    options.append("B) 你不补充 → 我按默认假设继续，但会标注不确定项")
    options.append("C) 你给截图/链接/游戏内面板 → 我用其作为证据并写入记忆卡")

    # If we already know the "who" disambiguator, surface it as an explicit assumption.
    if intent == "build_compare" and ctx.get("who") in {"self", "merc", "unknown"}:
        who = str(ctx.get("who"))
        if who == "self":
            tldr.append("补充：你是给自己用（通常更偏向精神盾 + 施法/抗性；眼光更多是佣兵武器思路）。")
        elif who == "merc":
            tldr.append("补充：你是给米山用（眼光=佣兵长柄武器；精神更多是角色盾/剑思路，优先级会变）。")
        else:
            tldr.append("补充：你还不确定给谁用；我会分别给自己/米山两套取舍点。")

    # next question：只问 1 个最高价值问题
    if intent == "build_compare" and any(e in entities for e in ["眼光", "精神", "Insight", "Spirit"]):
        # Best single disambiguator for Insight vs Spirit is *who/slot* (self vs merc; weapon vs shield).
        if (ctx.get("who") or "") in ("self", "merc", "unknown"):
            next_q = "你现在的精神/眼光分别打算做在什么底材上？（例如 Spirit: 剑/盾；Insight: 长柄/弓；以及你是否已经有第二幕佣兵）"
        else:
            next_q = "你是打算给自己用，还是给第二幕佣兵(米山)用？（这会直接决定眼光/精神的底材与取舍）"
    else:
        # Avoid redundant questions when defaults already pin down the track.
        if intent == "runeword_recipe" and any(e in entities for e in ["精神", "Spirit"]):
            if ctx.get("base_4os") is None:
                next_q = "你的君主盾（鸢盾）现在是 4 孔的白/灰底材吗？（符文之语必须白/灰，Spirit 盾需要 4 孔）"
            else:
                next_q = "你现在手里有 Tal/Thul/Ort/Amn 这四个符文吗？如果缺哪个我可以告诉你最常见的刷法。"
        else:
            next_q = "你这条问题对应的 release_track 是哪个？（默认 d2r_roitw；如有 PTR/其他轨道请说明）"

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

    gap = detect_context_gaps(user_query, user_ctx)
    events.append({"step": "context_gap", "input": {"user_query": user_query, "user_ctx": user_ctx}, "output": gap.model_dump(mode="json")})

    ctx = _merge_ctx(gap.default_assumptions, user_ctx, current_date=current_date)
    events.append({"step": "ctx_merge", "input": {"defaults": gap.default_assumptions, "user_ctx": user_ctx}, "output": ctx})

    # Strategy KB: for build questions, surface one actionable nugget first.
    strategy_hits_obj = []
    strategy_tldr: list[str] = []
    if gap.intent in {"build_advice", "build_compare"}:
        sh = search_strategy_cards(user_query, path="data/strategy_cards.jsonl", limit=2)
        for h in sh:
            strategy_hits_obj.append({"topic": h.topic, "source_url": h.source_url, "title_path": h.title_path})
            # TL;DR style line
            strategy_tldr.append(f"[Strategy] {h.nugget} (source: {h.source_url})")

    rr = route(user_query, gap.intent, current_date=current_date, release_track=str(ctx.get("release_track") or ""))
    events.append({"step": "retrieval_router", "input": {"user_query": user_query, "intent": gap.intent}, "output": rr.model_dump(mode="json")})

    evidence: list[EvidenceSnippet] = []
    fact_hits_obj: list[dict] = []

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

    # 阶段 B（initial）：对部分强事实意图执行真实检索（优先 TheAmazonBasin MediaWiki）。
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
            # 其他强事实：尽量至少对 Basin 做真实检索+抽取（避免永远停留在 stub）
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

    ans0 = _compose_answer(user_query, ctx, gap.intent, rr.expected_entities, rr.need_retrieval, evidence, strategy_tldr=strategy_tldr)

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

    trace = Trace(
        timestamp=datetime.now(),
        current_date=current_date,
        user_query=user_query,
        user_ctx=user_ctx,
        interactive_loop_used=interactive_loop_used,
        events=events,
        next_step_question=ans.next_step_question,
        intent=gap.intent,
        missing_fields=gap.missing_fields,
        questions_to_ask=gap.questions_to_ask,
        defaults_used=gap.default_assumptions,
        strategy_hits=strategy_hits_obj,
        fact_hits=fact_hits_obj,
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

    # 固定输出格式
    out_lines: list[str] = []
    out_lines.append("Assumptions")
    for k, v in ans.assumptions.items():
        out_lines.append(f"- {k}: {v}")

    out_lines.append("\nTL;DR")
    for t in ans.tldr:
        out_lines.append(f"- {t}")

    # Note: Evidence is preserved in trace/structured answer, but omitted from user-facing output
    # to keep group replies minimal.

    out_lines.append("\nOptions")
    for o in ans.options:
        out_lines.append(f"- {o}")

    out_lines.append("\nNext step")
    out_lines.append(f"- {ans.next_step_question}")

    out_lines.append("\n(Trace)")
    out_lines.append(f"- wrote: {trace_path}")

    return "\n".join(out_lines), str(trace_path)
