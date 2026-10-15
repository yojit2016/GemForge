"""Narrow manifest edits only. Plans are data, never AI shell/source patches."""

import difflib
import hashlib
import re
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from .files import read_text
from .schemas import ExitCapsule, ManifestEdit, MigrationPlan


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def prepare_migration(
    root: Path, dependency: str, target: str | None, capsule: ExitCapsule
) -> MigrationPlan:
    dependency = canonicalize_name(dependency)
    if not target:
        candidates = [
            r
            for r in capsule.recommendations
            if r.package == dependency and r.status == "generated" and r.replacement
        ]
        if len(candidates) != 1:
            raise ValueError(
                "Provide --target PACKAGE_SPEC or a capsule with exactly one generated target recommendation."
            )
        target = candidates[0].replacement
    req = Requirement(target)
    if (
        canonicalize_name(req.name) != dependency
        or req.url
        or req.marker
        or req.extras
        or not str(req.specifier)
    ):
        raise ValueError("Target must constrain the same package, without URLs, markers or extras.")
    entries = [d for d in capsule.dependencies if d.package == dependency]
    if not entries:
        raise ValueError("Requested dependency is not declared in the repository.")
    edits = []
    for file in sorted({d.source.file for d in entries}):
        declarations = [d for d in entries if d.source.file == file]
        if file not in {"requirements.txt", "requirements-dev.txt", "pyproject.toml"} or any(
            d.group != "runtime" or d.marker or d.url or d.extras for d in declarations
        ):
            raise ValueError(
                "Manifest editing currently supports unconditional root requirements and PEP 621 runtime declarations only."
            )
        path = root / file
        if path.is_symlink() or path.resolve().parent != root.resolve():
            raise ValueError("Linked or non-root manifests cannot be modified.")
        before = read_text(path)
        after = before
        for raw in sorted({d.raw for d in declarations}):
            if file == "pyproject.toml":
                # Only replace a unique exact quoted requirement. Duplicate or
                # ambiguous occurrences are rejected instead of rewriting TOML.
                pattern = re.compile(r"([\"'])" + re.escape(raw) + r"\1")
                if len(pattern.findall(after)) != 1:
                    raise ValueError("Ambiguous TOML dependency string; manual migration required.")
                after = pattern.sub(lambda m: m.group(1) + target + m.group(1), after)
            else:
                pattern = re.compile(r"^(\s*)" + re.escape(raw) + r"(\s*(?:#.*)?)$", re.MULTILINE)
                if not pattern.search(after):
                    raise ValueError("Complex/continued requirements need a manual migration.")
                after = pattern.sub(lambda m: m.group(1) + target + m.group(2), after)
        if file == "pyproject.toml":
            tomllib.loads(after)
        if after != before:
            edits.append(
                ManifestEdit(file=file, before_sha256=sha256(before), before=before, after=after)
            )
    if not edits:
        raise ValueError("Target introduces no manifest change.")
    diff = "".join(
        line
        for edit in edits
        for line in difflib.unified_diff(
            edit.before.replace("\r\n", "\n").splitlines(keepends=True),
            edit.after.replace("\r\n", "\n").splitlines(keepends=True),
            fromfile=f"a/{edit.file}",
            tofile=f"b/{edit.file}",
        )
    )
    return MigrationPlan(
        dependency=dependency,
        target=target,
        edits=edits,
        unified_diff=diff,
        limitations=["Manifest-only candidate; no AI-generated source changes applied."],
    )


def apply_migration(copy_root: Path, plan: MigrationPlan) -> None:
    """Caller supplies an owned temporary copy, never the original repository."""
    for edit in plan.edits:
        path = copy_root / edit.file
        if path.is_symlink() or path.resolve().parent != copy_root.resolve():
            raise ValueError("Unsafe candidate edit path.")
        if sha256(read_text(path)) != edit.before_sha256:
            raise ValueError("Manifest changed since plan preparation; refusing stale edits.")
    for edit in plan.edits:
        (copy_root / edit.file).write_text(edit.after, encoding="utf-8", newline="")
