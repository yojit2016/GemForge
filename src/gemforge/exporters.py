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
        lines.extend(
            f"  - {step}" for step in recommendation.migration_steps + recommendation.limitations
        )
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
