"""Versioned capsule contracts shared by the CLI and API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceLocation(Schema):
    file: str
    line: int | None = Field(default=None, ge=1)


class Dependency(Schema):
    package: str
    constraint: str = ""
    extras: list[str] = Field(default_factory=list)
    marker: str | None = None
    url: str | None = None
    group: str = "runtime"
    source: SourceLocation
    raw: str


class DetectedRisk(Schema):
    package: str
    kind: Literal["constraint_conflict", "constraint_uncertainty", "direct_reference"]
    certainty: Literal["proven", "uncertain"]
    evidence: str
    sources: list[SourceLocation]


class ConstraintAssessment(Schema):
    package: str
    status: Literal["conflict", "compatible", "uncertain"]
    explanation: str
    witness: str | None = None


class UsageLocation(Schema):
    package: str
    module: str
    symbol: str
    alias: str | None = None
    kind: Literal["import", "reference"]
    mapping: Literal["explicit", "name_heuristic"]
    source: SourceLocation


class AIRecommendation(Schema):
    package: str
    status: Literal["not_requested", "generated", "unavailable"] = "not_requested"
    model_id: str | None = None
    replacement: str | None = None
    migration_steps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class VerificationStatus(Schema):
    status: Literal["not_run", "passed", "failed", "inconclusive"] = "not_run"
    original_status: Literal["not_run", "passed", "failed", "inconclusive"] = "not_run"
    candidate_status: Literal["not_run", "passed", "failed", "inconclusive"] = "not_run"
    commands: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    reason: str = "Phase 1 performs static analysis only; no repository code was executed."


class ExitCapsule(Schema):
    schema_version: Literal["1.0"] = "1.0"
    generated_at: datetime
    repository: str
    dependencies: list[Dependency]
    risks: list[DetectedRisk]
    constraints: list[ConstraintAssessment]
    usages: list[UsageLocation]
    recommendations: list[AIRecommendation]
    verification: VerificationStatus = Field(default_factory=VerificationStatus)
    limitations: list[str]
