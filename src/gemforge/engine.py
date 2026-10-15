"""Public read-only scanning API shared by all entry points."""

from datetime import UTC, datetime
from pathlib import Path

from packaging.utils import canonicalize_name

from .constraints import detect_risks
from .files import discover
from .manifests import parse_manifests
from .schemas import AIRecommendation, ExitCapsule
from .usage import map_usages


def scan_repository(path: str | Path, import_map: dict[str, str] | None = None) -> ExitCapsule:
    root = Path(path).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Repository path must be a directory: {root}")
    limitations = [
        (
            "Static local manifest facts only: no PyPI release, vulnerability, maintenance, "
            "transitive dependency or installed-distribution metadata was queried."
        ),
        (
            "All discovered requirements*.txt and pyproject.toml declarations are compared together; "
            "independent nested projects and alternative install profiles may need separate scans."
        ),
        (
            "Pip includes/options, hashes, editable requirements, lockfiles, setup.py and "
            "build-system dependencies are not resolved. Symlinked files/directories are skipped."
        ),
        (
            "Constraint compatibility is metadata overlap, not runtime/API compatibility. "
            "Prereleases are allowed for existential overlap checks. Conditional constraints remain uncertain."
        ),
    ]
    files = discover(root, limitations)
    dependencies = parse_manifests(root, files, limitations)
    if not dependencies:
        limitations.append(
            "No supported dependency declarations found; this is not evidence of safety."
        )
    constraints, risks = detect_risks(dependencies)
    usages = map_usages(
        root,
        files,
        dependencies,
        limitations,
        {k: canonicalize_name(v) for k, v in (import_map or {}).items()},
    )
    recommendations = [
        AIRecommendation(
            package=package,
            limitations=[
                "AI migration recommendation was not requested; use analyze --ai after configuring Gemma 4."
            ],
        )
        for package in sorted({risk.package for risk in risks})
    ]
    return ExitCapsule(
        generated_at=datetime.now(UTC),
        repository=str(root),
        dependencies=dependencies,
        constraints=constraints,
        risks=risks,
        usages=usages,
        recommendations=recommendations,
        limitations=limitations,
    )
