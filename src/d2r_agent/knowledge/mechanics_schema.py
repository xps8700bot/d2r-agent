from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


SourceTier = Literal["official", "tierA", "tierB", "tierC"]
Confidence = Literal["low", "med", "high"]


class MechanicsVariable(BaseModel):
    name: str
    meaning: str
    unit: Optional[str] = None


class MechanicsExample(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    work: Optional[str] = None
    output: dict[str, Any] = Field(default_factory=dict)


class VersionScope(BaseModel):
    game: str = "d2/d2r"
    patch_min: Optional[str] = None
    patch_max: Optional[str] = None


class MechanicsFactRecord(BaseModel):
    id: str
    topic: str
    subtopic: Optional[str] = None
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)

    fact_type: Literal["rule", "formula", "definition", "note"] = "rule"
    statement: str
    formula: Optional[str] = None

    conditions: list[str] = Field(default_factory=list)
    variables: list[MechanicsVariable] = Field(default_factory=list)
    examples: list[MechanicsExample] = Field(default_factory=list)

    source_url: str
    source_title: Optional[str] = None
    source_site: str
    source_tier: SourceTier
    evidence_source_type: Literal["extract", "stub", "community_consensus"] = "extract"

    confidence: Confidence = "med"
    version_scope: VersionScope = Field(default_factory=VersionScope)
    notes: Optional[str] = None
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
