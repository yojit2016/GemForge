"""Capsule serialization; creation never overwrites an existing artifact."""

from pathlib import Path

from .schemas import ExitCapsule


def capsule_markdown(capsule: ExitCapsule) -> str:
    lines = [
        "# Dependency Exit Capsule",
        "",
        f"Repository: `{capsule.repository}`",
        f"Generated: {capsule.generated_at.isoformat()}",
        "",
        "## Dependencies",
        "",
    ]
    for dep in capsule.dependencies:
        lines.append(
            f"- `{dep.package}{dep.constraint}` — `{dep.source.file}:{dep.source.line or '?'}` ({dep.group})"
        )
    lines += ["", "## Detected risks", ""]
    lines.extend(
        f"- **{risk.package}** ({risk.certainty}): {risk.evidence}" for risk in capsule.risks
    )
    if not capsule.risks:
        lines.append("No risks detected by the implemented checks. This does not establish safety.")
    lines += ["", "## Migration recommendations", ""]
    for recommendation in capsule.recommendations:
        lines.append(f"- **{recommendation.package}**: {recommendation.status}")
        lines.append(
            f"  - Origin: {recommendation.origin}; model: {recommendation.model_id or 'not requested'}"
        )
        lines.append(
            f"  - Proposed target (unverified): {recommendation.replacement or 'none established'}"
        )
        if recommendation.risk_explanation:
            lines.append(f"  - AI risk explanation: {recommendation.risk_explanation}")
        if recommendation.rationale:
            lines.append(f"  - AI rationale: {recommendation.rationale}")
        if recommendation.evidence_ids:
            lines.append(f"  - Evidence references: {', '.join(recommendation.evidence_ids)}")
        lines.extend(
            f"  - Proposed change in `{change.file}`: {change.description}"
            for change in recommendation.proposed_changes
        )
        lines.extend(
            f"  - Compatibility concern: {text}" for text in recommendation.compatibility_concerns
        )
        lines.extend(f"  - Unknown: {text}" for text in recommendation.unknowns)
        lines.extend(
            f"  - Proposed verification (not_run): `{check.command}` — {check.purpose}"
            for check in recommendation.verification_checks
        )
        lines.extend(
            f"  - {step}" for step in recommendation.migration_steps + recommendation.limitations
        )
    if capsule.inferences:
        lines += ["", "## Inference provenance", "", f"AI analysis status: {capsule.ai_status}", ""]
        for record in capsule.inferences:
            lines.append(
                f"- {record.package}: {record.status}; {record.model_id}; {record.access_method}; access={record.model_access}; calls={record.attempts}; duration_ms={record.duration_ms:.1f}"
            )
            lines.append(
                f"  - Response ID: {record.response_id or 'none'}; model version: {record.model_version or 'not reported'}; finish: {record.finish_reason or 'not reported'}"
            )
            lines.append(
                f"  - Prompt SHA256: {record.prompt_sha256 or 'none'}; response SHA256: {record.response_sha256 or 'none'}"
            )
            if record.message:
                lines.append(f"  - {record.error_code}: {record.message}")
    if capsule.evidence:
        lines += ["", "## Observed evidence", ""]
        for item in capsule.evidence:
            lines.append(f"- `{item.id}` ({item.kind}): {item.description}")
            if item.source:
                lines.append(f"  - `{item.source.file}:{item.source.line or '?'}`")
            if item.excerpt is not None:
                lines.append(f"  - Excerpt SHA256: {item.excerpt_sha256}")
                # Indented blocks keep source backticks from closing a fence.
                lines.extend(f"\n    {row}" for row in item.excerpt.splitlines())
    lines += ["", "## Usage evidence", ""]
    lines.extend(
        f"- `{u.package}`: {u.kind} `{u.symbol}` at `{u.source.file}:{u.source.line}` ({u.mapping})"
        for u in capsule.usages
    )
    lines += [
        "",
        "## Verification",
        "",
        f"Status: **{capsule.verification.status}**. {capsule.verification.reason}",
        "",
        "## Analysis limitations",
        "",
    ]
    lines.extend(f"- {limitation}" for limitation in capsule.limitations)
    return "\n".join(lines) + "\n"


def write_capsule(capsule: ExitCapsule, destination: Path, markdown: bool = False) -> None:
    content = capsule_markdown(capsule) if markdown else capsule.model_dump_json(indent=2) + "\n"
    with destination.open("x", encoding="utf-8") as handle:
        handle.write(content)
