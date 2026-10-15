"""Shared evidence -> Gemma -> validated hypotheses pipeline. No code execution."""

from pathlib import Path

from .ai import GemmaAdapter, GemmaConfig, InferenceError
from .engine import scan_repository
from .evidence import build_evidence, digest
from .recommendations import build_prompt, validate_proposal
from .schemas import AIRecommendation, ExitCapsule, InferenceRecord


def analyze_repository(
    path: str | Path,
    *,
    ai: bool = False,
    allow_hosted: bool = False,
    import_map: dict[str, str] | None = None,
    max_ai_packages: int = 10,
    config: GemmaConfig | None = None,
) -> ExitCapsule:
    if not 1 <= max_ai_packages <= 50:
        raise ValueError("max_ai_packages must be between 1 and 50")
    capsule = scan_repository(path, import_map)
    capsule.evidence = build_evidence(capsule)
    if not ai:
        return capsule
    if not capsule.risks:
        capsule.ai_status = "no_risks"
        return capsule
    capsule.limitations.append(
        "AI recommendations are hypotheses. Structure and evidence references are validated; "
        "semantic truth, API/release availability and compatibility are unverified. "
        "Suggested commands are never executed. New file paths are not accepted as observed files."
    )
    config_error = None
    model_id = "gemma-4-26b-a4b-it"
    try:
        config = config or GemmaConfig.from_environment()
        model_id = config.model_id
        if allow_hosted:
            config = config.model_copy(update={"allow_hosted": True})
        adapter = GemmaAdapter(config)
    except ValueError as error:
        config_error = str(error)
        adapter = None
    capsule.recommendations = []
    service_blocked = False
    for index, package in enumerate(sorted({r.package for r in capsule.risks})):
        record = InferenceRecord(package=package, model_id=model_id, status="blocked")
        recommendation = AIRecommendation(
            package=package,
            model_id=model_id,
            status="unavailable",
            original_constraints=sorted(
                {d.constraint or "*" for d in capsule.dependencies if d.package == package}
            ),
        )
        items = [item for item in capsule.evidence if item.package == package]
        try:
            if config_error:
                raise InferenceError("configuration", config_error)
            if index >= max_ai_packages:
                raise InferenceError(
                    "request_budget",
                    "AI package budget reached; increase max_ai_packages explicitly. No request made for this dependency.",
                )
            if service_blocked:
                raise InferenceError(
                    "service_unavailable",
                    "No request made: a prior dependency exhausted retries or failed authentication. Retry the analysis later.",
                )
            prompt = build_prompt(package, items)
            # Defense in depth: the configured credential never enters the prompt.
            key = config.api_key.get_secret_value()
            if key:
                prompt = prompt.replace(key, "[REDACTED API KEY]")
            record.prompt_sha256 = digest(prompt)
            reply = adapter.generate(prompt)
            record = record.model_copy(
                update={
                    "status": "succeeded",
                    "model_access": "confirmed",
                    "attempts": reply.attempts,
                    "duration_ms": reply.duration_ms,
                    "response_id": reply.response_id,
                    "model_version": reply.model_version,
                    "finish_reason": reply.finish_reason,
                    "input_tokens": reply.input_tokens,
                    "output_tokens": reply.output_tokens,
                    "response_sha256": digest(reply.text),
                    "diagnostics": list(reply.diagnostics),
                }
            )
            try:
                proposal = validate_proposal(reply.text, package, items)
            except (ValueError, TypeError, RecursionError):
                record.status = "invalid_response"
                record.error_code = "recommendation_validation"
                record.message = (
                    "Gemma returned an invalid or ungrounded structured recommendation; discarded."
                )
                recommendation.limitations = [record.message]
            else:
                recommendation = AIRecommendation.model_validate(
                    {
                        **recommendation.model_dump(),
                        "status": "generated",
                        "replacement": proposal.target,
                        **proposal.model_dump(exclude={"package", "target"}),
                    }
                )
        except InferenceError as error:
            record.status = (
                "invalid_response"
                if error.code == "invalid_response"
                else "failed"
                if error.attempts
                else "blocked"
            )
            record.attempts = error.attempts
            record.duration_ms = error.duration_ms
            record.model_access = error.model_access
            record.error_code = error.code
            record.message = str(error)
            record.diagnostics = error.diagnostics
            if error.code in {
                "server_error",
                "rate_limit",
                "timeout",
                "network",
                "authentication",
                "permission",
            }:
                service_blocked = True
            recommendation.limitations = [str(error)]
        except ValueError:
            record.status = "blocked"
            record.error_code = "evidence_budget"
            record.message = (
                "Evidence exceeds the prompt budget; narrow the scan. No inference made."
            )
            recommendation.limitations = [record.message]
        capsule.inferences.append(record)
        capsule.recommendations.append(recommendation)
    generated = sum(r.status == "generated" for r in capsule.recommendations)
    capsule.ai_status = (
        "generated"
        if generated == len(capsule.recommendations)
        else "partial"
        if generated
        else "unavailable"
    )
    return capsule
