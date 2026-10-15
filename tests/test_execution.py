import sys
from pathlib import Path

from gemforge.execution import copy_snapshot, execution_environment, run_command


def test_snapshot_excludes_secrets_git_and_generated_files(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "module.py").write_text("x=1\n")
    (source / ".env").write_text("private")
    (source / "credentials.json").write_text("private")
    (source / ".git").mkdir()
    (source / ".git/HEAD").write_text("history")
    (source / "node_modules").mkdir()
    (source / "node_modules/a.py").write_text("not source")
    digest, _ = copy_snapshot(source, tmp_path / "copy")
    assert len(digest) == 64
    assert sorted(p.name for p in (tmp_path / "copy").iterdir()) == ["module.py"]
    assert (source / ".env").read_text() == "private"


def test_child_environment_has_no_parent_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-private-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-aws-key")
    env = execution_environment(tmp_path / "home", Path(sys.executable))
    assert "GEMINI_API_KEY" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "PYTHONPATH" not in env


def test_real_bounded_output_capture_and_timeout(tmp_path):
    env = execution_environment(tmp_path / "home", Path(sys.executable))
    result = run_command(
        "fixture", [sys.executable, "-I", "-c", "print('x'*100000)"], tmp_path, env, 10
    )
    assert result.status == "passed"
    assert result.output_truncated
    assert len(result.stdout) <= 65536
    result = run_command(
        "timeout", [sys.executable, "-I", "-c", "import time; time.sleep(5)"], tmp_path, env, 0.2
    )
    assert result.status == "timeout"
    assert result.duration_ms < 12000


def test_sanitizes_child_output(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "private-unit-credential")
    env = execution_environment(tmp_path / "home", Path(sys.executable))
    result = run_command(
        "fixture",
        [sys.executable, "-I", "-c", "print('private-unit-credential')"],
        tmp_path,
        env,
        10,
    )
    assert "private-unit-credential" not in result.stdout
    assert "REDACTED" in result.stdout
