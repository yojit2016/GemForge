"""Bounded, symlink-free discovery. Never import or execute scanned files."""

import os
from pathlib import Path

IGNORED = {
    ".git",
    ".dist",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
}
MAX_FILES = 20_000
MAX_BYTES = 2_000_000


def discover(root: Path, limitations: list[str]) -> list[Path]:
    found = []
    visited = 0

    def onerror(error: OSError) -> None:
        limitations.append(f"Directory could not be read: {error}")

    for directory, folders, files in os.walk(root, followlinks=False, onerror=onerror):
        folders[:] = sorted(
            name
            for name in folders
            if name not in IGNORED
            and not (Path(directory) / name).is_symlink()
            and not (Path(directory) / name).is_junction()
        )
        for name in sorted(files):
            visited += 1
            if visited > MAX_FILES:
                limitations.append(f"Discovery stopped at {MAX_FILES} files; scan is partial.")
                return found
            path = Path(directory) / name
            if path.is_symlink():
                continue
            if (
                name == "pyproject.toml"
                or (name.startswith("requirements") and name.endswith(".txt"))
                or name.endswith(".py")
            ):
                found.append(path)
    return found


def read_text(path: Path) -> str:
    # A bounded read also handles a file growing after discovery.
    with path.open("rb") as handle:
        data = handle.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError(f"file exceeds {MAX_BYTES} bytes")
    return data.decode("utf-8-sig")
