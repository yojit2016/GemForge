"""Read PEP 508 requirements and PEP 621 metadata without executing build hooks."""

import re
import tomllib
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from .files import read_text
from .schemas import Dependency, SourceLocation


def parse_manifests(root: Path, files: list[Path], limitations: list[str]) -> list[Dependency]:
    dependencies: list[Dependency] = []

    def add(raw: str, path: Path, line: int | None, group: str = "runtime") -> None:
        try:
            req = Requirement(raw)
        except InvalidRequirement as error:
            limitations.append(
                f"{path.relative_to(root)}:{line or '?'}: invalid requirement: {error}"
            )
            return
        dependencies.append(
            Dependency(
                package=canonicalize_name(req.name),
                constraint=str(req.specifier),
                extras=sorted(req.extras),
                marker=str(req.marker) if req.marker else None,
                url=req.url,
                group=group,
                source=SourceLocation(file=path.relative_to(root).as_posix(), line=line),
                raw=raw,
            )
        )

    for path in files:
        if path.suffix == ".py":
            continue
        try:
            text = read_text(path)
            if path.name != "pyproject.toml":
                pending = ""
                start = 1
                for number, raw_line in enumerate(text.splitlines(), 1):
                    line = re.split(r"\s+#", raw_line, maxsplit=1)[0].strip()
                    if not line or line.startswith("#"):
                        continue
                    if not pending:
                        start = number
                    if line.endswith("\\"):
                        pending += line[:-1].strip() + " "
                        continue
                    line = pending + line
                    pending = ""
                    if line.startswith("-"):
                        limitations.append(
                            f"{path.relative_to(root)}:{start}: pip option/include/editable unsupported: {line}"
                        )
                    else:
                        add(line, path, start)
                if pending:
                    limitations.append(f"{path.relative_to(root)}:{start}: unfinished continuation")
                continue
            data = tomllib.loads(text)
            project = data.get("project", {})
            entries = [("runtime", project.get("dependencies", []))]
            entries.extend(
                (f"optional:{name}", items)
                for name, items in project.get("optional-dependencies", {}).items()
            )
            entries.extend(
                (f"group:{name}", items)
                for name, items in data.get("dependency-groups", {}).items()
            )
            for group, items in entries:
                if not isinstance(items, list):
                    limitations.append(
                        f"{path.relative_to(root)}: {group} must be a dependency array"
                    )
                    continue
                for raw in items:
                    if not isinstance(raw, str):
                        limitations.append(
                            f"{path.relative_to(root)}: unsupported dependency entry in {group}: {raw!r}"
                        )
                        continue
                    # tomllib has no source spans. Only report unambiguous single-line strings.
                    matches = [
                        i
                        for i, line in enumerate(text.splitlines(), 1)
                        if f'"{raw}"' in line or f"'{raw}'" in line
                    ]
                    add(raw, path, matches[0] if len(matches) == 1 else None, group)
            if project.get("dynamic"):
                limitations.append(
                    f"{path.relative_to(root)}: dynamic project metadata is not executed"
                )
            if "poetry" in data.get("tool", {}):
                limitations.append(
                    f"{path.relative_to(root)}: Poetry-specific dependency tables are unsupported"
                )
        except (OSError, UnicodeError, ValueError, TypeError, AttributeError) as error:
            limitations.append(
                f"{path.relative_to(root)}: manifest could not be fully parsed: {error}"
            )
    return dependencies
