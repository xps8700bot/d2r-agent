from __future__ import annotations

from d2r_agent.schemas import ExtractedFacts, EvidenceSnippet


def normalize(evidence: list[EvidenceSnippet], entities: list[str]) -> ExtractedFacts:
    """阶段 A：证据 → 结构化事实（弱结构）。

    阶段 C：升级为 Fact Cards + 冲突治理。
    """
    facts = []
    for ev in evidence:
        facts.append({
            "type": "snippet",
            "source_url": ev.source_url,
            "summary": ev.snippet,
        })
    return ExtractedFacts(entities=entities, facts=facts)
