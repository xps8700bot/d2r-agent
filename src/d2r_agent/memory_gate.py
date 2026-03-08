from __future__ import annotations

from datetime import datetime

from d2r_agent.config import OFFICIAL_WHITELIST_DOMAINS
from d2r_agent.retrieval.adapters.theamazonbasin import BASIN_HOST
from d2r_agent.schemas import EvidenceSnippet, ExtractedFacts, FactCard, MemoryGateResult


def decide_memory_write(
    topic: str,
    release_track: str,
    season_id: str | None,
    ladder_flag: str,
    platform: str | None,
    extracted: ExtractedFacts,
    evidence: list[EvidenceSnippet],
) -> MemoryGateResult:
    """记忆写入闸门（Memory Gate）

    规则（MVP）：
    - 必须有证据（evidence 非空）
    - release_track 必须明确（非空；ladder_flag 允许 unknown 但会降低可复用性）
    - 不写入“未验证的具体数值”：MVP 只写入 evidence 摘要型事实
    """
    if not evidence:
        return MemoryGateResult(should_write=False, reason="无证据片段，禁止写入记忆（避免污染）。")

    # Never write memory from stub/search-entry evidence.
    non_stub = [e for e in evidence if getattr(e, "evidence_source_type", "extract") != "stub"]
    if not non_stub:
        return MemoryGateResult(should_write=False, reason="证据均为 stub/search-entry（非可引用片段），禁止写入记忆。")

    if not release_track:
        return MemoryGateResult(should_write=False, reason="release_track 不明确，禁止写入记忆。")

    # Stricter policy for mechanics/hard-rule claims: only persist when evidence is from
    # official sources OR from Basin with some explicit citation-like content.
    if topic == "mechanics_claim":
        official_ok = any((e.source_site or "").lower() in OFFICIAL_WHITELIST_DOMAINS for e in non_stub)

        def _basin_has_citation(e: EvidenceSnippet) -> bool:
            if (e.source_site or "").lower() not in {BASIN_HOST, "www." + BASIN_HOST}:
                return False
            sn = (e.snippet or "")
            # Heuristic: citation markers / external refs / patch-note style links.
            return ("http://" in sn) or ("https://" in sn) or ("source:" in sn.lower()) or ("ref" in sn.lower())

        basin_ok = any(_basin_has_citation(e) for e in non_stub)

        if not (official_ok or basin_ok):
            return MemoryGateResult(
                should_write=False,
                reason="mechanics_claim 只允许从官方白名单证据写入；或 Basin 且含可追溯引用标记（链接/Ref）。",
            )

    card = FactCard(
        topic=topic,
        release_track=release_track,
        season_id=season_id,
        ladder_flag=ladder_flag or "unknown",
        platform=platform,
        facts=extracted.facts,
        sources=evidence,
        last_verified_at=datetime.utcnow(),
    )
    return MemoryGateResult(should_write=True, reason="有证据且版本字段存在：允许写入可复用 FactCard（MVP 先弱结构）。", card_payload=card)
