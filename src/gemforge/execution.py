"""Approved trusted-code execution isolation, not an OS security sandbox."""

import hashlib
import os
import re
import signal
import subprocess
import threading
import time
from pathlib import Path

from .files import IGNORED, MAX_BYTES
from .schemas import CommandResult

COPY_SUFFIXES = {
    ".py",
    ".toml",
    ".txt",
    ".j2",
    ".html",
    ".json",
    ".yaml",
    ".yml",
    ".cfg",
    ".ini",
    ".md",
    ".csv",
}
COPY_IGNORED = IGNORED | {".aws", ".ssh", ".codex", ".agents", ".vscode", ".cache"}


def copy_snapshot(source: Path, destination: Path) -> tuple[str, list[str]]:
    """Copy allowlisted data without following links or traversing private folders."""
    destination.mkdir(parents=True, exist_ok=False)
    hashes = []
    limitations = []
    total = 0
    count = 0
    for directory, folders, files in os.walk(source, followlinks=False):
        folders[:] = sorted(
            name
            for name in folders
            if name not in COPY_IGNORED
            and not name.lower().startswith(".env")
            and not (Path(directory) / name).is_symlink()
            and not (Path(directory) / name).is_junction()
        )
        for name in sorted(files):
            path = Path(directory) / name
            relative = path.relative_to(source)
            if path.is_symlink() or re.search(
                r"(?i)(^\.env|credential|secret|\.pem$|\.key$|id_rsa|\.netrc|\.pypirc)", name
            ):
                continue
            if path.suffix.lower() not in COPY_SUFFIXES and name not in {"LICENSE"}:
                limitations.append(f"Not copied (unsupported file type): {relative.as_posix()}")
                continue
            with path.open("rb") as handle:
                data = handle.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError(f"Verification snapshot file too large: {relative}")
            total += len(data)
            count += 1
            if total > 50_000_000 or count > 20_000:
                raise ValueError("Verification snapshot exceeds 50 MB / 20000 files")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            hashes.append(f"{relative.as_posix()}\0{hashlib.sha256(data).hexdigest()}")
    return hashlib.sha256("\n".join(sorted(hashes)).encode()).hexdigest(), limitations


def sanitized_output(value: str) -> str:
    for name, secret in os.environ.items():
        if len(secret) >= 8 and re.search(r"(?i)(key|token|password|secret|credential)", name):
            value = value.replace(secret, "[REDACTED]")
    value = re.sub(r"AIza[\w-]+", "[REDACTED]", value)
    value = re.sub(
        r"(?i)\b(?:api[_-]?key|token|password|secret|authorization)\s*[:=]\s*[^\s,;]+",
        "[REDACTED credential]",
        value,
    )
    return re.sub(r"https?://[^\s]+", "[URL redacted]", value)


def execution_environment(home: Path, python: Path) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    system = os.environ.get("SystemRoot", "C:/Windows")
    return {
        "SystemRoot": system,
        "WINDIR": system,
        "PATH": str(python.parent) + os.pathsep + str(Path(system) / "System32"),
        "HOME": str(home),
        "USERPROFILE": str(home),
        "APPDATA": str(home),
        "LOCALAPPDATA": str(home),
        "TEMP": str(home),
        "TMP": str(home),
        "LANG": "C.UTF-8",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PIP_CONFIG_FILE": os.devnull,
        "PIP_NO_INPUT": "1",
    }


def run_command(
    check: str, argv: list[str], cwd: Path, env: dict[str, str], timeout: float
) -> CommandResult:
    """No shell. Drain both pipes with bounded memory and kill the process tree on timeout."""
    if timeout <= 0:
        raise ValueError("Command timeout must be positive")
    started = time.perf_counter()
    chunks = {"stdout": bytearray(), "stderr": bytearray()}
    truncated = False

    def drain(pipe, name):
        nonlocal truncated
        try:
            while data := pipe.read(4096):
                remaining = 65_536 - len(chunks[name])
                chunks[name].extend(data[: max(0, remaining)])
                truncated |= len(data) > remaining
        except (OSError, ValueError):
            pass

    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=os.name != "nt",
            shell=False,
        )
    except OSError as error:
        return CommandResult(
            check=check,
            argv=argv,
            status="execution_failed",
            stderr=sanitized_output(str(error)),
            duration_ms=(time.perf_counter() - started) * 1000,
        )
    threads = [
        threading.Thread(target=drain, args=(getattr(process, name), name), daemon=True)
        for name in chunks
    ]
    for thread in threads:
        thread.start()
    status = "passed"
    try:
        process.wait(timeout=timeout)
        status = "passed" if process.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        status = "timeout"
        if os.name == "nt":
            try:
                subprocess.run(
                    [
                        str(Path(env["SystemRoot"]) / "System32/taskkill.exe"),
                        "/PID",
                        str(process.pid),
                        "/T",
                        "/F",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    env=env,
                    shell=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
    for thread in threads:
        thread.join(timeout=2)
    return CommandResult(
        check=check,
        argv=argv,
        status=status,
        exit_code=process.returncode,
        stdout=sanitized_output(chunks["stdout"].decode("utf-8", errors="replace")),
        stderr=sanitized_output(chunks["stderr"].decode("utf-8", errors="replace")),
        duration_ms=(time.perf_counter() - started) * 1000,
        output_truncated=truncated,
    )
