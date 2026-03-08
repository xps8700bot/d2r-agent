from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


Confidence = Literal["low", "med", "high"]


class UserContext(BaseModel):
    # Release governance
    release_track: str  # e.g. "d2r_roitw" (default)

    # Season governance (optional; only required for season-specific questions)
    season_id: Optional[str] = None  # e.g. "current", "S10"; resolver may map "current" -> concrete id

    # Player context
    ladder_flag: str
    mode: str
    platform: str = "PC"
    offline: Optional[bool] = None


class ContextGapResult(BaseModel):
    intent: str
    missing_fields: list[str] = Field(default_factory=list)
    questions_to_ask: list[str] = Field(default_factory=list, max_length=3)
    default_assumptions: dict[str, Any] = Field(default_factory=dict)


class QueryPlan(BaseModel):
    keywords: list[str]
    sites: list[str]
    as_of_date: Optional[str] = None  # ISO date


class RetrievalRoute(BaseModel):
    need_retrieval: bool
    reason: str
    query_plan: Optional[QueryPlan] = None
    expected_entities: list[str] = Field(default_factory=list)


class EvidenceSnippet(BaseModel):
    source_url: str
    source_site: str
    title_path: list[str] = Field(default_factory=list)
    snippet: str
    # Where this snippet came from. "stub" means it's just a search entry / placeholder,
    # not an extracted, quotable fact.
    evidence_source_type: Literal["extract", "stub"] = "extract"


class ExtractedFacts(BaseModel):
    # MVP: 先用弱结构；阶段 C 会变成 Fact Cards + 冲突治理
    entities: list[str] = Field(default_factory=list)
    facts: list[dict[str, Any]] = Field(default_factory=list)


class FactCard(BaseModel):
    topic: str
    release_track: str
    season_id: Optional[str] = None
    ladder_flag: str
    platform: Optional[str] = None
    facts: list[dict[str, Any]]
    sources: list[EvidenceSnippet]
    last_verified_at: datetime


class MemoryGateResult(BaseModel):
    should_write: bool
    reason: str
    card_payload: Optional[FactCard] = None


class Answer(BaseModel):
    class FollowupChoice(BaseModel):
        label: str
        value: str
        # A tiny context patch to apply if the user clicks this choice.
        # Convention: shallow-merge into ctx.
        ctxPatch: dict[str, Any] = Field(default_factory=dict)

    class Followup(BaseModel):
        id: str
        question: str
        field: str
        choices: list["Answer.FollowupChoice"] = Field(default_factory=list)
        allowFreeText: bool = False

    assumptions: dict[str, Any]
    tldr: list[str]
    evidence: list[EvidenceSnippet]
    options: list[str]
    next_step_question: str
    followups: list[Followup] | None = None
    confidence: Confidence
    confidence_reason: str


class Trace(BaseModel):
    timestamp: datetime
    current_date: str  # ISO date (local)
    user_query: str

    # Raw context supplied by caller (CLI/API). This is the user's accumulated context
    # *before* we merge in detector defaults.
    user_ctx: dict[str, Any] = Field(default_factory=dict)

    # Whether an interactive follow-up loop was used (e.g., CLI prompting then re-running answer()).
    interactive_loop_used: bool = False

    # Step-level trace events for debugging/regression.
    events: list[dict[str, Any]] = Field(default_factory=list)

    # Convenience copy of the next-step question emitted in the final Answer.
    next_step_question: str | None = None

    intent: str
    missing_fields: list[str]
    questions_to_ask: list[str]
    defaults_used: dict[str, Any]

    # Local KB hits (strategy/facts) are recorded separately from live web retrieval.
    strategy_hits: list[dict[str, Any]] = Field(default_factory=list)
    fact_hits: list[dict[str, Any]] = Field(default_factory=list)

    retrieval_needed: bool
    retrieval_reason: str
    queries: list[dict[str, Any]] = Field(default_factory=list)
    sources_used: list[str] = Field(default_factory=list)

    extracted_facts: dict[str, Any] = Field(default_factory=dict)
    conflicts_found: list[str] = Field(default_factory=list)

    memory_written: dict[str, Any] = Field(default_factory=dict)

    confidence: Confidence
    confidence_reason: str
