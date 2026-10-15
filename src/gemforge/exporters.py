"""Capsule serialization; creation never overwrites an existing artifact."""

import json
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
            for diagnostic in record.diagnostics:
                lines.append(
                    f"  - {diagnostic.operation} attempt {diagnostic.attempt}: HTTP {diagnostic.http_status or 'unknown'} / {diagnostic.provider_status or 'not reported'}; {diagnostic.provider_message or 'no provider message'}"
                )
                if diagnostic.request_ids:
                    lines.append(f"    - Request IDs: {diagnostic.request_ids}")
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
    if capsule.repairs:
        lines += ["", "## Repair suggestions — unverified, unapplied", ""]
        for repair in capsule.repairs:
            lines += [
                f"### {repair.package}: {repair.status}",
                "",
                f"Created: {repair.created_at.isoformat()}",
                f"Verification: **{repair.verification_status}**. {repair.reason}",
                f"Parent verification SHA256: {repair.parent_verification_sha256}",
                "",
            ]
            if repair.inference:
                record = repair.inference
                lines += [
                    f"Inference: {record.status}; model: {record.model_id}; calls: {record.attempts}; response ID: {record.response_id or 'none'}",
                    f"Prompt SHA256: {record.prompt_sha256}; response SHA256: {record.response_sha256}",
                    f"Model version: {record.model_version}; finish: {record.finish_reason}; input/output tokens: {record.input_tokens}/{record.output_tokens}",
                ]
                if record.message:
                    lines.append(f"Inference error: {record.error_code}; {record.message}")
                lines.extend(
                    f"- {d.operation} attempt {d.attempt}: HTTP {d.http_status}; {d.provider_status}; {d.provider_message}; request IDs: {d.request_ids}"
                    for d in record.diagnostics
                )
            if repair.proposal:
                proposal = repair.proposal
                lines += [
                    "",
                    f"AI failure explanation: {proposal.failure_explanation}",
                    f"Evidence references: {', '.join(proposal.evidence_ids)}",
                    "",
                ]
                for change in proposal.changes:
                    lines += [
                        f"#### Suggested change: {change.file}:{change.start_line}–{change.end_line}",
                        "",
                        change.explanation,
                        "",
                        "Observed before:",
                        "",
                    ]
                    lines.extend("    " + row for row in change.before.splitlines())
                    lines += ["", "Suggested after (never applied):", ""]
                    lines.extend("    " + row for row in change.after.splitlines())
                    lines.append("")
                lines += ["Verification required under separate authorization:", ""]
                lines.extend(f"- {item}" for item in proposal.verification_plan)
                lines += ["", "Compatibility concerns and limitations:", ""]
                lines.extend(
                    f"- {item}" for item in proposal.compatibility_concerns + proposal.limitations
                )
            lines += ["", "Repair evidence:", ""]
            for item in repair.evidence:
                lines += [
                    f"- `{item.id}` ({item.kind}): {item.description}",
                    f"  - Excerpt SHA256: {item.excerpt_sha256}",
                ]
                if item.source:
                    lines.append(f"  - `{item.source.file}:{item.source.line}–{item.end_line}`")
                lines.append("")
                lines.extend("    " + row for row in item.excerpt.splitlines())
                lines.append("")
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
    ]
    verification = capsule.verification
    lines += [
        f"Verdict: **{verification.verdict}**",
        "",
        f"Started: {verification.started_at}; completed: {verification.completed_at}",
        f"Snapshot SHA256: {verification.snapshot_sha256 or 'not captured'}",
        f"Temporary cleanup: {verification.cleanup_completed}",
        f"Install profile: {verification.install_profile or 'not executed'}",
        f"Import module: {verification.import_module or 'not recorded'}; check timeout: {verification.timeout_seconds}; install timeout: {verification.install_timeout_seconds}",
        "",
    ]
    if verification.probes:
        lines += ["### Reviewed probe specifications", ""]
        lines.extend(
            "    " + row
            for row in json.dumps(
                [p.model_dump(mode="json") for p in verification.probes], indent=2
            ).splitlines()
        )
    if verification.plan:
        lines += ["### Manifest-only candidate", "", f"Target: `{verification.plan.target}`", ""]
        lines.extend("    " + row for row in verification.plan.unified_diff.splitlines())
        for edit in verification.plan.edits:
            lines += ["", f"- `{edit.file}` original SHA256: {edit.before_sha256}"]
        lines.extend(f"- Plan limitation: {item}" for item in verification.plan.limitations)
    for side in (verification.baseline, verification.candidate):
        if not side:
            continue
        lines += [
            "",
            f"### {side.label.title()} execution",
            "",
            f"Python: {side.python_version or 'unknown'}",
            "",
            "Installation requirements:",
            "",
        ]
        lines.extend(f"- `{raw}`" for raw in side.install_requirements)
        lines += ["", "Pinned control constraints:", ""]
        lines.extend(f"- `{raw}`" for raw in side.constraints)
        lines += ["", "Installed versions and wheel SHA256:", ""]
        lines.extend(
            f"- `{name}=={version}`; wheel: {side.package_hashes.get(name, 'not captured')}"
            for name, version in sorted(side.installed_packages.items())
        )
        lines += ["", "Test outcomes:", ""]
        lines.extend(f"- `{name}`: {status}" for name, status in side.test_outcomes.items())
        lines += ["", "Probe outcomes:", ""]
        lines.extend(f"- `{name}`: {status}" for name, status in side.probe_outcomes.items())
        for command in side.commands:
            lines += [
                "",
                f"#### {command.check}: {command.status}",
                "",
                f"Exit: {command.exit_code}; duration: {command.duration_ms:.1f} ms; output truncated: {command.output_truncated}",
                "",
                "Argument vector:",
                "",
                "    " + json.dumps(command.argv),
                "",
                "Sanitized stdout:",
                "",
            ]
            lines.extend("    " + row for row in command.stdout.splitlines())
            lines += ["", "Sanitized stderr:", ""]
            lines.extend("    " + row for row in command.stderr.splitlines())
        lines.extend(f"- Execution limitation: {item}" for item in side.limitations)
    if verification.comparisons:
        lines += ["", "### Paired comparison", ""]
        lines.extend(
            f"- `{item.check}`: **{item.status}**. {item.explanation}"
            for item in verification.comparisons
        )
    if verification.evidence:
        lines += ["", "### Verification evidence", ""]
        lines.extend(f"- {item}" for item in verification.evidence)
    lines += ["", "### Compatibility gaps and unresolved risks", ""]
    lines.extend(
        f"- {item}" for item in verification.compatibility_gaps + verification.unresolved_risks
    )
    lines += ["", "## Analysis limitations", ""]
    lines.extend(f"- {limitation}" for limitation in capsule.limitations)
    return "\n".join(lines) + "\n"


def write_capsule(capsule: ExitCapsule, destination: Path, markdown: bool = False) -> None:
    content = capsule_markdown(capsule) if markdown else capsule.model_dump_json(indent=2) + "\n"
    with destination.open("x", encoding="utf-8") as handle:
        handle.write(content)
