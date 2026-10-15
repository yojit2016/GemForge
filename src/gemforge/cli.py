"""Local read-only CLI. JSON stdout is clean; the human report uses stderr."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .analysis import analyze_repository
from .engine import scan_repository
from .exporters import write_capsule

app = typer.Typer(
    no_args_is_help=True, help="Scan Python dependency facts without executing repository code."
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


if __name__ == "__main__":
    app()
