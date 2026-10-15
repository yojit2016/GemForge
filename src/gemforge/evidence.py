"""Bounded local evidence. Never load .env, execute code, or follow links."""

import hashlib
import re
from pathlib import Path

from .files import discover, read_text
from .schemas import EvidenceItem, ExitCapsule, SourceLocation


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_evidence(capsule: ExitCapsule) -> list[EvidenceItem]:
    root = Path(capsule.repository)
    inventory_limits: list[str] = []
    files = discover(root, inventory_limits)
    tests = [
        p.relative_to(root).as_posix()
        for p in files
        if p.suffix == ".py"
        and (
            p.name.startswith("test_")
            or p.name.endswith("_test.py")
            or "tests" in p.relative_to(root).parts
        )
    ]
    result = []
    for package in sorted({r.package for r in capsule.risks}):
        counts: dict[str, int] = {}

        def add(kind: str, description: str, source=None, excerpt=None):
            counts[kind] = counts.get(kind, 0) + 1
            result.append(
                EvidenceItem(
                    id=f"{package}:{kind}:{counts[kind]}",
                    package=package,
                    kind=kind,
                    description=description,
                    source=source,
                    excerpt=excerpt,
                    excerpt_sha256=digest(excerpt) if excerpt is not None else None,
                )
            )

        dependencies = [d for d in capsule.dependencies if d.package == package]
        for dep in dependencies:
            add("manifest", f"Declaration: {dep.raw}; group: {dep.group}.", dep.source)
        for risk in (r for r in capsule.risks if r.package == package):
            add("risk", f"{risk.kind} ({risk.certainty}): {risk.evidence}")
        usages = [u for u in capsule.usages if u.package == package]
        for usage in usages[:80]:
            add(
                "usage",
                f"{usage.kind}: {usage.symbol}; alias={usage.alias}; mapping={usage.mapping}.",
                usage.source,
            )
        if len(usages) > 80:
            add(
                "limitation",
                "Usage evidence truncated to the first 80 locations; full locations remain in the capsule.",
            )
        relevant: dict[str, int] = {}
        for source in [d.source for d in dependencies] + [u.source for u in usages]:
            relevant.setdefault(source.file, source.line or 1)
        for file, line in list(relevant.items())[:8]:
            path = root / file
            try:
                relative = path.relative_to(root)
                if path.resolve().is_relative_to(root.resolve()) is False or any(
                    (root / Path(*relative.parts[:i])).is_symlink()
                    or (root / Path(*relative.parts[:i])).is_junction()
                    for i in range(1, len(relative.parts) + 1)
                ):
                    raise ValueError("linked or outside repository")
                if path.suffix not in {".py", ".toml", ".txt"} or path.name.startswith(".env"):
                    raise ValueError("not a supported evidence file")
                lines = read_text(path).splitlines()
                start = max(1, line - 5)
                excerpt = "\n".join(lines[start - 1 : start + 59])[:4000]
                # Public source can still contain hardcoded credentials. Suppress
                # credential-like assignment lines instead of sending their values.
                excerpt = "\n".join(
                    "[REDACTED credential-like assignment]"
                    if re.search(
                        r"(?i)\b\w*(?:api_key|apikey|secret|password|token|credential)\w*\s*(?::[^=]+)?=",
                        row,
                    )
                    else row
                    for row in excerpt.splitlines()
                )
                add(
                    "source",
                    "Bounded source excerpt, at most 60 lines/4000 characters; credential-like assignments redacted.",
                    SourceLocation(file=file, line=start),
                    excerpt,
                )
            except (OSError, UnicodeError, ValueError) as error:
                add("limitation", f"Excerpt unavailable for {file}: {type(error).__name__}.")
        if len(relevant) > 8:
            add("limitation", "Source excerpts truncated to the first eight relevant files.")
        for file in tests[:30]:
            add(
                "test_inventory",
                "Test file detected by filename only. Not executed or judged sufficient.",
                SourceLocation(file=file),
            )
        if not tests:
            add(
                "limitation",
                "No test files detected by the supported filename heuristic; no tests executed.",
            )
        if len(tests) > 30:
            add("limitation", "Test inventory truncated to 30 files.")
        for limitation in capsule.limitations + inventory_limits:
            add("limitation", limitation)
        add(
            "limitation",
            "No external dependency/release/API/maintenance metadata is available. Do not claim a version exists or that migration is compatible.",
        )
        add(
            "limitation",
            "Evidence is read from a mutable working tree after scanning, not an atomic repository snapshot. Excerpt hashes cover only the redacted text shown.",
        )
    return result
