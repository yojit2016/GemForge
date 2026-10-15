"""Synthetic verification orchestration: no target installations or network requests."""

from unittest.mock import Mock

import pytest

import gemforge.verification as verification
from gemforge.comparison import compare_environments
from gemforge.schemas import CommandResult, EnvironmentResult, ModelProbe


def side(label, statuses=None, tests=None, probes=None):
    return EnvironmentResult(
        label=label,
        commands=[
            CommandResult(check=k, argv=["fixture"], status=v)
            for k, v in (
                statuses
                or {"install": "passed", "syntax": "passed", "import": "passed", "pytest": "passed"}
            ).items()
        ],
        test_outcomes=tests if tests is not None else {"suite::test_one": "passed"},
        probe_outcomes=probes or {},
        installed_packages={
            "pydantic": "1.10.13" if label == "baseline" else "2.12.0",
            "pytest": "8.4.0",
        },
    )


@pytest.mark.parametrize(
    "before,after,verdict,comparison",
    [
        ("passed", "passed", "verified_for_selected_checks", "passed_both"),
        ("passed", "failed", "regression_detected", "regression"),
        ("failed", "passed", "verified_for_selected_checks", "repaired"),
        ("failed", "failed", "inconclusive", "baseline_failure"),
        ("skipped", "passed", "inconclusive", "not_comparable"),
    ],
)
def test_paired_test_classification(before, after, verdict, comparison):
    a = side("baseline", tests={"test": before})
    b = side("candidate", tests={"test": after})
    result = compare_environments(a, b)
    assert result.verdict == verdict
    assert next(c for c in result.comparisons if c.check == "test:test").status == comparison


def test_probe_regression_survives_shared_suite_failure():
    a = side(
        "baseline",
        {"install": "passed", "pytest": "failed", "probes": "passed"},
        tests={"test": "error"},
        probes={"whitespace": "passed"},
    )
    b = side(
        "candidate",
        {"install": "passed", "pytest": "failed", "probes": "failed"},
        tests={"test": "error"},
        probes={"whitespace": "failed"},
    )
    assert compare_environments(a, b).verdict == "regression_detected"


@pytest.mark.parametrize("status", ["failed", "timeout", "execution_failed"])
def test_install_failure_never_passes(status):
    a = side("baseline")
    b = side("candidate", {"install": status}, tests={})
    assert compare_environments(a, b).verdict == "execution_failed"


def test_missing_tests_and_versions_are_not_passes():
    a, b = side("baseline", tests={}), side("candidate", tests={})
    assert compare_environments(a, b).verdict == "inconclusive"
    assert verification.parse_packages('[{"name":"pydantic"}]')[1]
    assert verification.parse_packages("not json")[1]
    assert verification.parse_packages('[{"name":"Pydantic","version":"2.12.0"}]') == (
        {"pydantic": "2.12.0"},
        [],
    )


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "target"
    root.mkdir()
    (root / "requirements.txt").write_bytes(b"pydantic==1.10.13\r\n")
    (root / "app.py").write_text("from pydantic import BaseModel\n")
    return root


def test_preview_never_executes(repo, monkeypatch):
    run = Mock(side_effect=AssertionError("Execution without consent"))
    monkeypatch.setattr(verification, "run_environment", run)
    capsule = verification.verify_repository(repo, "pydantic", "pydantic>=2,<3")
    assert capsule.verification.verdict == "not_run"
    assert "pydantic>=2,<3" in capsule.verification.plan.unified_diff
    run.assert_not_called()


def test_isolated_copies_constraints_cleanup_and_original_preserved(repo, tmp_path, monkeypatch):
    original = (repo / "requirements.txt").read_bytes()
    (repo / ".env").write_text("private")
    monkeypatch.setattr(verification, "elevated", lambda: False)
    observed = []

    def fake_run(label, directory, requirements, constraints, *args):
        observed.append(directory)
        assert not (directory / "repo/.env").exists()
        assert directory / "repo" != repo
        assert (directory / "repo/app.py").read_text() == (repo / "app.py").read_text()
        assert (
            "1.10.13" in (directory / "repo/requirements.txt").read_text()
            if label == "baseline"
            else ">=2,<3" in (directory / "repo/requirements.txt").read_text()
        )
        if label == "candidate":
            assert constraints == ["pytest==8.4.0"]
        return side(label)

    monkeypatch.setattr(verification, "run_environment", fake_run)
    capsule = verification.verify_repository(
        repo, "pydantic", "pydantic>=2,<3", confirm_execution=True, work_parent=tmp_path / "runs"
    )
    assert capsule.verification.verdict == "verified_for_selected_checks"
    assert capsule.verification.cleanup_completed
    assert all(not p.exists() for p in observed)
    assert (repo / "requirements.txt").read_bytes() == original
    assert (repo / ".env").read_text() == "private"


def test_cleanup_after_preexecution_error(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(verification, "elevated", lambda: False)
    monkeypatch.setattr(
        verification,
        "install_requirements",
        Mock(side_effect=ValueError("invalid install profile")),
    )
    capsule = verification.verify_repository(
        repo, "pydantic", "pydantic>=2,<3", confirm_execution=True, work_parent=tmp_path / "runs"
    )
    assert capsule.verification.verdict == "execution_failed"
    assert capsule.verification.cleanup_completed
    assert not list((tmp_path / "runs").iterdir())


def test_elevated_and_unsafe_workspace_rejected(repo, monkeypatch):
    monkeypatch.setattr(verification, "elevated", lambda: True)
    with pytest.raises(ValueError, match="administrator"):
        verification.verify_repository(repo, "pydantic", "pydantic>=2,<3", confirm_execution=True)
    monkeypatch.setattr(verification, "elevated", lambda: False)
    with pytest.raises(ValueError, match="outside"):
        verification.verify_repository(
            repo, "pydantic", "pydantic>=2,<3", confirm_execution=True, work_parent=repo / "runs"
        )


def test_install_profile_rejects_urls_and_options(repo):
    (repo / "requirements.txt").write_text("pydantic @ https://example.test/a.whl\n")
    with pytest.raises(ValueError, match="Direct references"):
        verification.install_requirements(repo)
    (repo / "requirements.txt").write_text("--extra-index-url https://example.test\n")
    with pytest.raises(ValueError):
        verification.install_requirements(repo)


def test_junit_skipped_collection_errors_and_duplicate_ids(tmp_path):
    path = tmp_path / "results.xml"
    path.write_text(
        '<testsuite><testcase classname="x" name="a"><skipped/></testcase><testcase classname="x" name="b"><error/></testcase></testsuite>'
    )
    assert verification.parse_junit(path) == {"x::a": "skipped", "x::b": "error"}
    path.write_text('<testsuite><testcase name="a"/><testcase name="a"/></testsuite>')
    with pytest.raises(ValueError, match="Duplicate"):
        verification.parse_junit(path)


def test_probe_requires_explicit_expectation(repo):
    with pytest.raises(ValueError, match="expected"):
        verification.verify_repository(
            repo,
            "pydantic",
            "pydantic>=2,<3",
            probes=[ModelProbe(name="empty", module="app", class_name="Demo")],
        )


def test_install_failure_skips_all_target_code(tmp_path, monkeypatch):
    directory = tmp_path / "baseline"
    (directory / "repo").mkdir(parents=True)
    observed = []

    def fake_command(check, argv, cwd, env, timeout):
        observed.append(check)
        return CommandResult(
            check=check,
            argv=argv,
            status="failed" if check == "install" else "passed",
            stdout="[]" if check == "packages" else "3.12.14",
        )

    monkeypatch.setattr(verification, "run_command", fake_command)
    result = verification.run_environment(
        "baseline", directory, ["demo==1"], [], "demo", "demo", [], 10, 20
    )
    assert observed == ["venv", "python", "install", "packages"]
    assert not result.test_outcomes and not result.probe_outcomes
    assert any("installation failed" in item for item in result.limitations)


def test_missing_test_suite_recorded_without_execution(tmp_path, monkeypatch):
    directory = tmp_path / "baseline"
    (directory / "repo").mkdir(parents=True)
    observed = []

    def fake_command(check, argv, cwd, env, timeout):
        observed.append(check)
        return CommandResult(
            check=check,
            argv=argv,
            status="passed",
            stdout='[{"name":"demo","version":"1"}]' if check == "packages" else "3.12.14",
        )

    monkeypatch.setattr(verification, "run_command", fake_command)
    result = verification.run_environment(
        "baseline", directory, ["demo==1"], [], "demo", "demo", [], 10, 20
    )
    assert "pytest" not in observed
    assert next(c for c in result.commands if c.check == "pytest").status == "not_run"
    assert not result.test_outcomes
    assert compare_environments(result, side("candidate")).verdict == "inconclusive"
