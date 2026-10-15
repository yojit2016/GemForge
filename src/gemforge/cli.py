"""Local CLI. Verification is opt-in; JSON stdout and terminal stderr stay separate."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .analysis import analyze_repository
from .engine import scan_repository
from .exporters import write_capsule
from .files import read_text
from .repairs import suggest_repair
from .schemas import ExitCapsule, ModelProbe
from .verification import verify_repository

app = typer.Typer(
    no_args_is_help=True, help="Inspect Python dependencies and opt into reviewed migration checks."
)
console = Console(stderr=True)


def parse_import_map(values: list[str] | None) -> dict[str, str]:
    mapping = {}
    for value in values or []:
        module, separator, package = value.partition("=")
        if not separator or not module or not package:
            raise ValueError("--import-map requires MODULE=PACKAGE")
        mapping[module] = package
    return mapping


def preflight_exports(output: Path | None, markdown: Path | None) -> None:
    for destination in (output, markdown):
        if destination and (destination.exists() or destination.is_symlink()):
            raise FileExistsError(f"Refusing to overwrite {destination}")
    if output and markdown and output.resolve() == markdown.resolve():
        raise ValueError("JSON and Markdown destinations must differ")


@app.callback()
def main() -> None:
    """GemForge dependency inspection commands."""


@app.command()
def scan(
    repository: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit capsule JSON on stdout.")
    ] = False,
    output: Annotated[
        Path | None, typer.Option(help="Create a JSON capsule file; never overwrite.")
    ] = None,
    markdown: Annotated[
        Path | None, typer.Option(help="Create a Markdown capsule file; never overwrite.")
    ] = None,
    import_map: Annotated[
        list[str] | None,
        typer.Option(help="Repeat MODULE=PACKAGE to resolve mismatched import names."),
    ] = None,
) -> None:
    try:
        mapping = parse_import_map(import_map)
        preflight_exports(output, markdown)
        capsule = scan_repository(repository, mapping)
        if output:
            write_capsule(capsule, output)
        if markdown:
            write_capsule(capsule, markdown, markdown=True)
    except (OSError, ValueError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(2) from error
    table = Table(title="GemForge dependency facts")
    for label in ("Package", "Constraint", "Source", "Assessment"):
        table.add_column(label)
    statuses = {assessment.package: assessment.status for assessment in capsule.constraints}
    for dep in capsule.dependencies:
        table.add_row(
            dep.package,
            dep.constraint or "unconstrained",
            f"{dep.source.file}:{dep.source.line or '?'}",
            statuses[dep.package],
        )
    console.print(table)
    for risk in capsule.risks:
        console.print(f"{risk.package} [{risk.certainty}]: {risk.evidence}", markup=False)
    console.print(
        f"{len(capsule.usages)} usage locations. Verification: {capsule.verification.status}"
    )
    for limitation in capsule.limitations:
        console.print(f"Limitation: {limitation}", markup=False)
    if json_output:
        typer.echo(capsule.model_dump_json(indent=2))


@app.command()
def analyze(
    repository: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    ai: Annotated[
        bool, typer.Option("--ai", help="Request real Gemma 4 migration analysis.")
    ] = False,
    allow_hosted: Annotated[
        bool,
        typer.Option(
            "--allow-hosted",
            help="Confirm hosted inference and disclosure of relevant repository excerpts are permitted.",
        ),
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit capsule JSON on stdout.")
    ] = False,
    output: Annotated[
        Path | None, typer.Option(help="Create JSON capsule; never overwrite.")
    ] = None,
    markdown: Annotated[
        Path | None, typer.Option(help="Create Markdown capsule; never overwrite.")
    ] = None,
    import_map: Annotated[list[str] | None, typer.Option(help="Repeat MODULE=PACKAGE.")] = None,
    max_ai_packages: Annotated[
        int,
        typer.Option(
            min=1,
            max=50,
            help="Bound hosted analysis requests; remaining risks get explicit limitations.",
        ),
    ] = 10,
) -> None:
    try:
        mapping = parse_import_map(import_map)
        preflight_exports(output, markdown)
        capsule = analyze_repository(
            repository,
            ai=ai,
            allow_hosted=allow_hosted,
            import_map=mapping,
            max_ai_packages=max_ai_packages,
        )
        if output:
            write_capsule(capsule, output)
        if markdown:
            write_capsule(capsule, markdown, markdown=True)
    except (OSError, ValueError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(2) from error
    console.print(
        f"GemForge analysis: {capsule.ai_status}; {len(capsule.risks)} detected risks; verification: {capsule.verification.status}",
        markup=False,
    )
    for recommendation in capsule.recommendations:
        console.print(
            f"{recommendation.package}: {recommendation.status}; AI hypothesis target: {recommendation.replacement or 'none established'}",
            markup=False,
        )
        for text in recommendation.migration_steps + recommendation.limitations:
            console.print(f"  {text}", markup=False)
    if json_output:
        typer.echo(capsule.model_dump_json(indent=2))
    if ai and capsule.ai_status in {"unavailable", "partial"}:
        raise typer.Exit(3)


@app.command()
def verify(
    repository: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    dependency: Annotated[str, typer.Option(help="Declared package to migrate.")],
    target: Annotated[
        str | None, typer.Option(help="Same-package requirement, e.g. pydantic>=2,<3.")
    ] = None,
    analysis: Annotated[
        Path | None, typer.Option(help="Existing matching AI capsule; no new inference.")
    ] = None,
    confirm_execution: Annotated[
        bool,
        typer.Option(
            "--confirm-execution",
            help="Approve reviewed target code running on this host in temporary virtual environments. Preview only by default.",
        ),
    ] = False,
    probe_file: Annotated[
        Path | None, typer.Option(help="Reviewed data-only model probe JSON.")
    ] = None,
    import_module: Annotated[
        str | None, typer.Option(help="Module to smoke-test; defaults to dependency name.")
    ] = None,
    timeout: Annotated[int, typer.Option(min=1, max=300)] = 60,
    install_timeout: Annotated[int, typer.Option(min=1, max=600)] = 180,
    work_dir: Annotated[
        Path | None, typer.Option(help="Temporary-work parent outside the target and active venv.")
    ] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    output: Annotated[
        Path | None, typer.Option(help="Create JSON capsule; never overwrite.")
    ] = None,
    markdown: Annotated[
        Path | None, typer.Option(help="Create Markdown capsule; never overwrite.")
    ] = None,
) -> None:
    """Preview or explicitly execute manifest-only baseline/candidate verification."""
    import json

    try:
        preflight_exports(output, markdown)
        prior = ExitCapsule.model_validate_json(read_text(analysis)) if analysis else None
        probes = (
            [ModelProbe.model_validate(p) for p in json.loads(read_text(probe_file))]
            if probe_file
            else []
        )
        capsule = verify_repository(
            repository,
            dependency,
            target,
            analysis=prior,
            confirm_execution=confirm_execution,
            probes=probes,
            import_module=import_module,
            timeout=timeout,
            install_timeout=install_timeout,
            work_parent=work_dir,
        )
        if output:
            write_capsule(capsule, output)
        if markdown:
            write_capsule(capsule, markdown, markdown=True)
    except (OSError, ValueError, TypeError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(2) from error
    result = capsule.verification
    console.print(f"Verification: {result.verdict}. {result.reason}", markup=False)
    if result.plan:
        console.print(result.plan.unified_diff, markup=False)
    for item in result.comparisons:
        console.print(f"{item.check}: {item.status} ({item.explanation})", markup=False)
    console.print(f"Temporary cleanup: {result.cleanup_completed}")
    if json_output:
        typer.echo(capsule.model_dump_json(indent=2))
    if result.verdict in {"regression_detected", "inconclusive", "execution_failed"}:
        raise typer.Exit(
            {"regression_detected": 4, "inconclusive": 5, "execution_failed": 6}[result.verdict]
        )


@app.command()
def repair(
    analysis: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    dependency: Annotated[str, typer.Option(help="Dependency with an observed probe regression.")],
    ai: Annotated[
        bool, typer.Option("--ai", help="Request a real Gemma 4 repair suggestion.")
    ] = False,
    allow_hosted: Annotated[
        bool,
        typer.Option(
            "--allow-hosted",
            help="Permit disclosure of relevant repository/probe evidence to hosted Gemma.",
        ),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    output: Annotated[
        Path | None, typer.Option(help="Create a new JSON capsule; never overwrite.")
    ] = None,
    markdown: Annotated[
        Path | None, typer.Option(help="Create a new Markdown capsule; never overwrite.")
    ] = None,
) -> None:
    """Suggest repairs from a saved regression capsule; never apply or execute them."""
    try:
        preflight_exports(output, markdown)
        parent = ExitCapsule.model_validate_json(read_text(analysis))
        capsule = suggest_repair(parent, dependency, ai=ai, allow_hosted=allow_hosted)
        if output:
            write_capsule(capsule, output)
        if markdown:
            write_capsule(capsule, markdown, markdown=True)
    except (OSError, ValueError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(2) from error
    suggestion = capsule.repairs[-1]
    console.print(f"Repair: {suggestion.status}; unverified. {suggestion.reason}", markup=False)
    if suggestion.proposal:
        for change in suggestion.proposal.changes:
            console.print(
                f"{change.file}:{change.start_line}-{change.end_line}: {change.explanation}",
                markup=False,
            )
            console.print(change.after, markup=False)
    if json_output:
        typer.echo(capsule.model_dump_json(indent=2))
    if ai and suggestion.status != "generated":
        raise typer.Exit(3)


if __name__ == "__main__":
    app()
