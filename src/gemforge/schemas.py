"""Versioned capsule contracts shared by the CLI and API."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


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


class EvidenceItem(Schema):
    id: str
    package: str
    kind: Literal["manifest", "risk", "usage", "source", "test_inventory", "limitation"]
    description: str
    source: SourceLocation | None = None
    excerpt: str | None = None
    excerpt_sha256: str | None = None


class ProposedChange(Schema):
    file: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=4000)


class VerificationCheck(Schema):
    command: str = Field(min_length=1, max_length=2000)
    purpose: str = Field(min_length=1, max_length=2000)
    status: Literal["not_run"] = "not_run"


class MigrationProposal(Schema):
    """Untrusted model payload. No fact, execution, or inference-status fields."""

    package: str = Field(min_length=1, max_length=200)
    evidence_ids: list[str] = Field(min_length=1, max_length=100)
    risk_explanation: str = Field(min_length=1, max_length=4000)
    target: str | None = Field(min_length=1, max_length=1000)
    rationale: str = Field(min_length=1, max_length=4000)
    affected_files: list[str] = Field(max_length=50)
    proposed_changes: list[ProposedChange] = Field(max_length=50)
    migration_steps: list[str] = Field(max_length=30)
    compatibility_concerns: list[str] = Field(min_length=1, max_length=30)
    verification_checks: list[VerificationCheck] = Field(max_length=20)
    unknowns: list[str] = Field(min_length=1, max_length=30)
    limitations: list[str] = Field(min_length=1, max_length=30)


class ProviderDiagnostic(Schema):
    operation: Literal["model_access", "generation"]
    attempt: int = Field(ge=1)
    http_status: int | None = None
    provider_status: str | None = None
    provider_message: str | None = None
    request_ids: dict[str, str] = Field(default_factory=dict)
    retryable: bool


class InferenceRecord(Schema):
    package: str
    model_id: str
    access_method: Literal["google_genai_developer_api"] = "google_genai_developer_api"
    status: Literal["not_requested", "succeeded", "failed", "invalid_response", "blocked"]
    model_access: Literal["not_checked", "confirmed", "failed"] = "not_checked"
    attempts: int = Field(default=0, ge=0)
    duration_ms: float = Field(default=0, ge=0)
    response_id: str | None = None
    model_version: str | None = None
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    prompt_sha256: str | None = None
    response_sha256: str | None = None
    error_code: str | None = None
    message: str | None = None
    diagnostics: list[ProviderDiagnostic] = Field(default_factory=list)


class AIRecommendation(Schema):
    package: str
    status: Literal["not_requested", "generated", "unavailable"] = "not_requested"
    model_id: str | None = None
    replacement: str | None = None
    migration_steps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    origin: Literal["ai_hypothesis"] = "ai_hypothesis"
    original_constraints: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    risk_explanation: str | None = None
    rationale: str | None = None
    affected_files: list[str] = Field(default_factory=list)
    proposed_changes: list[ProposedChange] = Field(default_factory=list)
    compatibility_concerns: list[str] = Field(default_factory=list)
    verification_checks: list[VerificationCheck] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class ManifestEdit(Schema):
    file: str
    before_sha256: str
    before: str
    after: str


class MigrationPlan(Schema):
    dependency: str
    target: str
    edits: list[ManifestEdit]
    unified_diff: str
    limitations: list[str] = Field(default_factory=list)


class ModelProbe(Schema):
    name: str = Field(min_length=1, max_length=200)
    module: str = Field(pattern=r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$")
    class_name: str = Field(pattern=r"^[A-Za-z_]\w*$")
    kwargs: dict[str, JsonValue] = Field(default_factory=dict)
    expected_attributes: dict[str, JsonValue] = Field(default_factory=dict)
    expected_exception: str | None = Field(default=None, pattern=r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)+$")


class CommandResult(Schema):
    check: str
    argv: list[str]
    status: Literal["passed", "failed", "timeout", "not_run", "execution_failed"]
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0
    output_truncated: bool = False


class EnvironmentResult(Schema):
    label: Literal["baseline", "candidate"]
    commands: list[CommandResult] = Field(default_factory=list)
    python_version: str | None = None
    installed_packages: dict[str, str] = Field(default_factory=dict)
    test_outcomes: dict[str, Literal["passed", "failed", "error", "skipped"]] = Field(
        default_factory=dict
    )
    probe_outcomes: dict[str, Literal["passed", "failed"]] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    install_requirements: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    package_hashes: dict[str, str] = Field(default_factory=dict)


class CheckComparison(Schema):
    check: str
    status: Literal[
        "passed_both", "baseline_failure", "repaired", "regression", "not_comparable", "not_run"
    ]
    explanation: str


class VerificationStatus(Schema):
    status: Literal["not_run", "passed", "failed", "inconclusive"] = "not_run"
    original_status: Literal["not_run", "passed", "failed", "inconclusive"] = "not_run"
    candidate_status: Literal["not_run", "passed", "failed", "inconclusive"] = "not_run"
    commands: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    reason: str = (
        "No repository code was executed; compatibility testing requires explicit consent."
    )
    verdict: Literal[
        "verified_for_selected_checks",
        "regression_detected",
        "inconclusive",
        "not_run",
        "execution_failed",
    ] = "not_run"
    plan: MigrationPlan | None = None
    install_profile: str | None = None
    baseline: EnvironmentResult | None = None
    candidate: EnvironmentResult | None = None
    comparisons: list[CheckComparison] = Field(default_factory=list)
    compatibility_gaps: list[str] = Field(default_factory=list)
    unresolved_risks: list[str] = Field(default_factory=list)
    cleanup_completed: bool | None = None
    snapshot_sha256: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    probes: list[ModelProbe] = Field(default_factory=list)
    import_module: str | None = None
    timeout_seconds: int | None = None
    install_timeout_seconds: int | None = None


class ProbeObservation(Schema):
    name: str
    status: Literal["passed", "failed"]
    actual: dict[str, JsonValue] | None = None
    actual_exception: str | None = None
    error_type: str | None = None
    message: str | None = None


class ProbeComparison(Schema):
    name: str
    specification: ModelProbe | None = None
    baseline: ProbeObservation | None = None
    candidate: ProbeObservation | None = None
    comparison: CheckComparison | None = None


class VerificationView(Schema):
    verification: VerificationStatus
    probes: list[ProbeComparison]
    limitations: list[str] = Field(default_factory=list)


class RepairEvidence(Schema):
    id: str
    kind: Literal["source", "probe", "diagnostic", "prior_recommendation"]
    description: str
    excerpt: str
    excerpt_sha256: str
    source: SourceLocation | None = None
    end_line: int | None = Field(default=None, ge=1)
    regression: bool = False


class RepairChange(Schema):
    source_evidence_id: str = Field(min_length=1, max_length=200)
    file: str = Field(min_length=1, max_length=500)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    before: str = Field(min_length=1, max_length=4000)
    after: str = Field(min_length=1, max_length=4000)
    explanation: str = Field(min_length=1, max_length=4000)


class RepairProposal(Schema):
    """Untrusted source suggestions only; no commands or verification claims."""

    package: str = Field(min_length=1, max_length=200)
    evidence_ids: list[str] = Field(min_length=1, max_length=50)
    failure_explanation: str = Field(min_length=1, max_length=4000)
    changes: list[RepairChange] = Field(min_length=1, max_length=5)
    verification_plan: list[str] = Field(min_length=1, max_length=15)
    compatibility_concerns: list[str] = Field(min_length=1, max_length=15)
    limitations: list[str] = Field(min_length=1, max_length=15)


class RepairRecommendation(Schema):
    package: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: Literal["not_requested", "generated", "unavailable"] = "not_requested"
    origin: Literal["ai_hypothesis"] = "ai_hypothesis"
    verification_status: Literal["unverified"] = "unverified"
    parent_verification_sha256: str
    evidence: list[RepairEvidence]
    proposal: RepairProposal | None = None
    inference: InferenceRecord | None = None
    reason: str


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
    evidence: list[EvidenceItem] = Field(default_factory=list)
    inferences: list[InferenceRecord] = Field(default_factory=list)
    repairs: list[RepairRecommendation] = Field(default_factory=list)
    ai_status: Literal["not_requested", "generated", "partial", "unavailable", "no_risks"] = (
        "not_requested"
    )
