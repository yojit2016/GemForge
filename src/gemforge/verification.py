"""Consent-gated, manifest-only verification using temporary host workspaces."""

import ctypes
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from .comparison import compare_environments
from .engine import scan_repository
from .execution import copy_snapshot, execution_environment, run_command, sanitized_output
from .files import read_text
from .migrations import apply_migration, prepare_migration
from .schemas import CommandResult, EnvironmentResult, ExitCapsule, ModelProbe, VerificationStatus


def elevated() -> bool:
    return bool(ctypes.windll.shell32.IsUserAnAdmin()) if os.name == "nt" else os.geteuid() == 0


def install_requirements(root: Path) -> list[str]:
    items = []
    for name in ("requirements.txt", "requirements-dev.txt"):
        if not (root / name).is_file():
            continue
        for line in read_text(root / name).splitlines():
            line = re.split(r"\s+#", line, maxsplit=1)[0].strip()
            if not line or line.startswith("#"):
                continue
            req = Requirement(line)
            if req.url:
                raise ValueError(
                    "Direct references are not allowed in verification installation profiles."
                )
            items.append(str(req))
    if not (root / "requirements.txt").is_file():
        capsule = scan_repository(root)
        items += [
            d.raw
            for d in capsule.dependencies
            if d.source.file == "pyproject.toml" and d.group == "runtime"
        ]
    for raw in items:
        if Requirement(raw).url:
            raise ValueError("Direct references are not allowed in verification profiles.")
    if not items:
        raise ValueError("No supported root dependency installation profile found.")
    return [*items, "pytest>=8.3,<10"]


def parse_packages(output: str) -> tuple[dict[str, str], list[str]]:
    try:
        data = json.loads(output)
        versions = {
            canonicalize_name(row["name"]): row["version"]
            for row in data
            if isinstance(row.get("name"), str)
            and isinstance(row.get("version"), str)
            and row["version"]
        }
        return versions, [] if len(versions) == len(data) else [
            "Some installed package versions are missing."
        ]
    except (ValueError, TypeError, KeyError, AttributeError):
        return {}, ["Installed package version metadata could not be parsed."]


def parse_junit(path: Path) -> dict[str, str]:
    tree = ET.fromstring(read_text(path))
    outcomes = {}
    for test in tree.iter("testcase"):
        key = test.get("classname", "") + "::" + test.get("name", "")
        if key in outcomes:
            raise ValueError("Duplicate JUnit test IDs; comparison would be ambiguous.")
        outcomes[key] = (
            "error"
            if test.find("error") is not None
            else "failed"
            if test.find("failure") is not None
            else "skipped"
            if test.find("skipped") is not None
            else "passed"
        )
    return outcomes


def run_environment(
    label: str,
    side: Path,
    requirements: list[str],
    constraints: list[str],
    dependency: str,
    module: str,
    probes: list[ModelProbe],
    timeout: int,
    install_timeout: int,
) -> EnvironmentResult:
    result = EnvironmentResult(
        label=label, install_requirements=requirements, constraints=constraints
    )
    root, control = side / "repo", side / "control"
    control.mkdir()
    venv_path = side / "venv"
    python = venv_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    env = execution_environment(side / "home", python)

    def run(check, args, duration=timeout):
        command = run_command(check, args, root, env, duration)
        result.commands.append(command)
        return command

    setup = run(
        "venv",
        [sys.executable, "-I", "-X", "utf8", "-m", "venv", "--copies", str(venv_path)],
        install_timeout,
    )
    if setup.status != "passed":
        result.limitations.append("Isolated virtual environment creation failed.")
        return result
    base = [str(python), "-I", "-X", "utf8", "-B"]
    version = run("python", [*base, "-c", "import platform; print(platform.python_version())"])
    if version.status == "passed":
        result.python_version = version.stdout.strip()
    req_file, constraints_file = control / "requirements.txt", control / "constraints.txt"
    req_file.write_text("\n".join(requirements) + "\n", encoding="utf-8")
    constraints_file.write_text("\n".join(constraints) + "\n", encoding="utf-8")
    install = run(
        "install",
        [
            *base,
            "-m",
            "pip",
            "--isolated",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            "--no-cache-dir",
            "--only-binary=:all:",
            "--index-url",
            "https://pypi.org/simple",
            "--report",
            str(control / "install.json"),
            "-r",
            str(req_file),
            *(["-c", str(constraints_file)] if constraints else []),
        ],
        install_timeout,
    )
    packages = run(
        "packages",
        [*base, "-m", "pip", "--isolated", "list", "--format=json", "--disable-pip-version-check"],
    )
    result.installed_packages, limits = parse_packages(packages.stdout)
    result.limitations.extend(limits)
    if dependency not in result.installed_packages:
        result.limitations.append(f"Installed version metadata missing for {dependency}.")
    if (control / "install.json").is_file():
        try:
            for item in json.loads(read_text(control / "install.json")).get("install", []):
                hash_value = (
                    item.get("download_info", {})
                    .get("archive_info", {})
                    .get("hashes", {})
                    .get("sha256")
                )
                if hash_value:
                    result.package_hashes[canonicalize_name(item["metadata"]["name"])] = hash_value
        except (OSError, ValueError, KeyError, TypeError):
            result.limitations.append("Installation artifact hashes could not be collected.")
    if install.status != "passed":
        result.limitations.append("Dependency installation failed; source checks were not run.")
        return result
    runner = control / "runner.py"
    runner.write_bytes(Path(__file__).with_name("verification_runner.py").read_bytes())
    (control / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    probe_file = control / "probe-specs.json"
    probe_file.write_text(json.dumps([p.model_dump(mode="json") for p in probes]), encoding="utf-8")

    def check(name, extra=None):
        return run(
            name,
            [
                *base,
                str(runner),
                name,
                str(root),
                str(control / f"{name}.xml" if name == "pytest" else control / f"{name}.json"),
                *(extra or []),
            ],
        )

    check("syntax")
    check("import", [module])
    tests = list(root.rglob("test_*.py"))
    if tests:
        check("pytest")
        try:
            result.test_outcomes = parse_junit(control / "pytest.xml")
            if not result.test_outcomes or not any(
                v == "passed" for v in result.test_outcomes.values()
            ):
                result.limitations.append(
                    "No passing test cases were observed; suite may be missing, skipped or uncollectable."
                )
        except (OSError, ValueError, ET.ParseError):
            result.limitations.append(
                "No readable JUnit outcomes; pytest collection/execution is not comparable."
            )
    else:
        result.commands.append(
            CommandResult(
                check="pytest", argv=[], status="not_run", stderr="No supported test suite found."
            )
        )
        result.limitations.append("No supported test suite found; no test pass is inferred.")
    if probes:
        check("probes", [str(probe_file)])
        try:
            data = json.loads(read_text(control / "probes.json"))
            # Output is deliberately separate from the input specification.
            result.probe_outcomes = {row["name"]: row["status"] for row in data}
            if set(result.probe_outcomes) != {p.name for p in probes} or any(
                v not in {"passed", "failed"} for v in result.probe_outcomes.values()
            ):
                raise ValueError("Incomplete probe results")
        except (OSError, ValueError, TypeError, KeyError):
            result.probe_outcomes = {}
            result.limitations.append("Probe execution did not produce complete outcomes.")
    return result


def verify_repository(
    path: str | Path,
    dependency: str,
    target: str | None = None,
    *,
    analysis: ExitCapsule | None = None,
    confirm_execution: bool = False,
    probes: list[ModelProbe] | None = None,
    import_module: str | None = None,
    timeout: int = 60,
    install_timeout: int = 180,
    work_parent: Path | None = None,
) -> ExitCapsule:
    root = Path(path).expanduser().resolve(strict=True)
    fresh = scan_repository(root)
    if analysis and (
        Path(analysis.repository).resolve() != root or analysis.dependencies != fresh.dependencies
    ):
        raise ValueError("Analysis capsule does not match current repository declarations.")
    capsule = analysis.model_copy(deep=True) if analysis else fresh
    dependency = canonicalize_name(dependency)
    plan = prepare_migration(root, dependency, target, capsule)
    module = import_module or dependency.replace("-", "_")
    if not re.fullmatch(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)*", module):
        raise ValueError("Import smoke test requires a valid module identifier.")
    if not (1 <= timeout <= 300 and 1 <= install_timeout <= 600):
        raise ValueError("Check timeout must be 1–300 seconds; installation timeout 1–600.")
    probes = probes or []
    if len(probes) > 20 or len({p.name for p in probes}) != len(probes):
        raise ValueError("Use at most 20 uniquely named model probes.")
    for probe in probes:
        if not probe.expected_attributes and not probe.expected_exception:
            raise ValueError("Each probe requires an expected attribute or exception.")
        if any(
            not name.isidentifier() or name.startswith("_") for name in probe.expected_attributes
        ):
            raise ValueError("Probe attributes must be public identifiers.")
    profile = "Root requirements.txt + requirements-dev.txt (or PEP 621 runtime fallback); binary wheels only; no project installation; pytest harness >=8.3,<10."
    verification = VerificationStatus(
        plan=plan,
        install_profile=profile,
        probes=probes,
        import_module=module,
        timeout_seconds=timeout,
        install_timeout_seconds=install_timeout,
        compatibility_gaps=[
            "Virtual environments isolate packages, not host filesystem/network permissions. Execute reviewed trusted code only.",
            "Only manifest changes applied. AI-proposed source migrations remain unresolved.",
            "Selected checks do not establish universal migration safety.",
        ],
    )
    capsule.verification = verification
    if not confirm_execution:
        verification.reason = "Preview only: pass --confirm-execution after reviewing the plan and host-execution boundary. No target code ran."
        return capsule
    if elevated():
        raise ValueError("Refusing target verification under administrator/root privileges.")
    if sys.version_info[:2] != (3, 12):
        raise ValueError("Verification requires the engine to run under Python 3.12.")
    parent = (work_parent or Path.cwd() / ".dist/verification").resolve()
    if parent.is_relative_to(root) or parent.is_relative_to(Path(sys.prefix).resolve()):
        raise ValueError(
            "Verification work directory must be outside the original repository and active environment."
        )
    parent.mkdir(parents=True, exist_ok=True)
    temp = tempfile.TemporaryDirectory(prefix="gemforge-", dir=parent)
    run_root = Path(temp.name).resolve()
    verification.started_at = datetime.now(UTC)
    try:
        baseline_side, candidate_side = run_root / "baseline", run_root / "candidate"
        verification.snapshot_sha256, limits = copy_snapshot(root, baseline_side / "repo")
        candidate_hash, more_limits = copy_snapshot(root, candidate_side / "repo")
        if verification.snapshot_sha256 != candidate_hash:
            raise ValueError(
                "Repository changed while preparing snapshots; no target execution attempted."
            )
        verification.compatibility_gaps.extend(limits + more_limits)
        apply_migration(candidate_side / "repo", plan)
        baseline_reqs = install_requirements(baseline_side / "repo")
        candidate_reqs = install_requirements(candidate_side / "repo")
        baseline = run_environment(
            "baseline",
            baseline_side,
            baseline_reqs,
            [],
            dependency,
            module,
            probes,
            timeout,
            install_timeout,
        )
        constraints = [
            f"{name}=={version}"
            for name, version in sorted(baseline.installed_packages.items())
            if name not in {dependency, "pip"}
        ]
        candidate = run_environment(
            "candidate",
            candidate_side,
            candidate_reqs,
            constraints,
            dependency,
            module,
            probes,
            timeout,
            install_timeout,
        )
        observed = compare_environments(baseline, candidate)
        verification = verification.model_copy(
            update={
                "status": observed.status,
                "verdict": observed.verdict,
                "reason": observed.reason,
                "original_status": observed.original_status,
                "candidate_status": observed.candidate_status,
                "baseline": baseline,
                "candidate": candidate,
                "comparisons": observed.comparisons,
                "evidence": observed.evidence,
                "commands": [
                    " ".join(c.argv) for s in (baseline, candidate) for c in s.commands if c.argv
                ],
            }
        )
        changed = {
            name
            for name in set(baseline.installed_packages) & set(candidate.installed_packages)
            if name != dependency
            and baseline.installed_packages[name] != candidate.installed_packages[name]
        }
        if changed:
            verification.compatibility_gaps.append(
                "Unrelated package versions changed: " + ", ".join(sorted(changed))
            )
            if verification.verdict == "verified_for_selected_checks":
                verification.status, verification.verdict = "inconclusive", "inconclusive"
        verification.unresolved_risks = [r.evidence for r in fresh.risks]
        verification.compatibility_gaps.extend(baseline.limitations + candidate.limitations)
        if (limits or more_limits) and verification.verdict == "verified_for_selected_checks":
            verification.status, verification.verdict = "inconclusive", "inconclusive"
    except (OSError, ValueError) as error:
        verification.status, verification.verdict = "inconclusive", "execution_failed"
        verification.reason = sanitized_output(str(error))
    finally:
        # Delete only the generated, owned directory after resolving its boundary.
        try:
            if run_root.parent != parent or run_root.is_symlink() or run_root.is_junction():
                raise ValueError("Temporary cleanup boundary changed")
            temp.cleanup()
            verification.cleanup_completed = not run_root.exists()
        except (OSError, ValueError):
            verification.cleanup_completed = False
            verification.compatibility_gaps.append(
                "Temporary cleanup failed; resources require review."
            )
            verification.status, verification.verdict = "inconclusive", "execution_failed"
        verification.completed_at = datetime.now(UTC)
    capsule.verification = verification
    return capsule
