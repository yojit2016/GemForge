"""Local read-only CLI. JSON stdout is clean; the human report uses stderr."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .engine import scan_repository
from .exporters import write_capsule

app = typer.Typer(
    no_args_is_help=True, help="Scan Python dependency facts without executing repository code."
)
console = Console(stderr=True)


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
        mapping = {}
        for value in import_map or []:
            module, separator, package = value.partition("=")
            if not separator or not module or not package:
                raise ValueError("--import-map requires MODULE=PACKAGE")
            mapping[module] = package
        # Preflight both destinations before writing either one.
        for destination in (output, markdown):
            if destination and destination.exists():
                raise FileExistsError(f"Refusing to overwrite {destination}")
        if output and markdown and output.resolve() == markdown.resolve():
            raise ValueError("JSON and Markdown destinations must differ")
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


if __name__ == "__main__":
    app()
