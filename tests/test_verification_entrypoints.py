import json
import sys
from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient
from typer.testing import CliRunner

import gemforge.api as api
from gemforge.cli import app
from gemforge.execution import execution_environment, run_command
from gemforge.exporters import capsule_markdown
from gemforge.verification import verify_repository


def repository(tmp_path):
    root = tmp_path / "target"
    root.mkdir()
    (root / "requirements.txt").write_text("pydantic==1.10.13\n")
    return root


def test_cli_preview_and_export_no_execution(tmp_path, monkeypatch):
    root = repository(tmp_path)
    run = Mock(side_effect=AssertionError("No target execution allowed"))
    monkeypatch.setattr("gemforge.verification.run_environment", run)
    output = tmp_path / "capsule.json"
    result = CliRunner().invoke(
        app,
        [
            "verify",
            str(root),
            "--dependency",
            "pydantic",
            "--target",
            "pydantic>=2,<3",
            "--json",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["verification"]["verdict"] == "not_run"
    assert json.loads(output.read_text()) == data
    assert "Manifest-only candidate" in capsule_markdown(
        verify_repository(root, "pydantic", "pydantic>=2,<3")
    )
    capsule = verify_repository(
        root, "pydantic", "pydantic>=2,<3", import_module="pydantic", timeout=12, install_timeout=30
    )
    capsule.verification.evidence.append("Synthetic integrity audit fixture")
    markdown = capsule_markdown(capsule)
    assert "Synthetic integrity audit fixture" in markdown
    assert "Import module: pydantic; check timeout: 12; install timeout: 30" in markdown
    run.assert_not_called()


def test_cli_existing_export_prevents_execution(tmp_path, monkeypatch):
    root = repository(tmp_path)
    output = tmp_path / "existing.json"
    output.write_text("keep")
    verify = Mock()
    monkeypatch.setattr("gemforge.cli.verify_repository", verify)
    result = CliRunner().invoke(
        app,
        [
            "verify",
            str(root),
            "--dependency",
            "pydantic",
            "--target",
            "pydantic>=2,<3",
            "--confirm-execution",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 2
    verify.assert_not_called()


def test_api_preview_retrieval_and_consent_forwarding(tmp_path, monkeypatch):
    root = repository(tmp_path)
    client = TestClient(api.app)
    request = {"path": str(root), "dependency": "pydantic", "target": "pydantic>=2,<3"}
    response = client.post("/verify", json=request)
    assert response.status_code == 201
    data = response.json()
    assert data["capsule"]["verification"]["verdict"] == "not_run"
    assert client.get(f"/analyses/{data['id']}/export").json() == data["capsule"]
    assert (
        "Manifest-only candidate"
        in client.get(f"/analyses/{data['id']}/export?format=markdown").text
    )
    mock = Mock(return_value=verify_repository(root, "pydantic", "pydantic>=2,<3"))
    monkeypatch.setattr(api, "verify_repository", mock)
    assert client.post("/verify", json={**request, "confirm_execution": True}).status_code == 201
    assert mock.call_args.kwargs["confirm_execution"] is True
    assert client.post("/verify", json={**request, "analysis_id": "missing"}).status_code == 404
    assert client.post("/verify", json={**request, "command": "untrusted"}).status_code == 422


def test_trusted_runner_data_probes_and_pytest(tmp_path):
    """Run our own tiny fixture only; no installs, network or LinkWatch execution."""
    root = repository(tmp_path)
    (root / "fixture_models.py").write_text(
        "class Demo:\n def __init__(self, name='alpha'):\n  if not name: raise ValueError('empty')\n  self.name=name.strip()\n"
    )
    (root / "test_fixture.py").write_text("def test_fixture():\n assert 1 + 1 == 2\n")
    control = tmp_path / "control"
    control.mkdir()
    (control / "pytest.ini").write_text("[pytest]\n")
    specs = control / "specs.json"
    specs.write_text(
        json.dumps(
            [
                {
                    "name": "strip",
                    "module": "fixture_models",
                    "class_name": "Demo",
                    "kwargs": {"name": " alpha "},
                    "expected_attributes": {"name": "alpha"},
                },
                {
                    "name": "error",
                    "module": "fixture_models",
                    "class_name": "Demo",
                    "kwargs": {"name": ""},
                    "expected_attributes": {},
                    "expected_exception": "builtins.ValueError",
                },
            ]
        )
    )
    runner = Path(__file__).resolve().parents[1] / "src/gemforge/verification_runner.py"
    env = execution_environment(tmp_path / "home", Path(sys.executable))
    for action in ("syntax", "import", "pytest", "probes"):
        output = control / ("pytest.xml" if action == "pytest" else action + ".json")
        args = [sys.executable, "-I", "-B", str(runner), action, str(root), str(output)]
        args += (
            ["fixture_models"] if action == "import" else [str(specs)] if action == "probes" else []
        )
        result = run_command(action, args, root, env, 15)
        assert result.status == "passed", result.stderr + result.stdout
    assert all(
        row["status"] == "passed" for row in json.loads((control / "probes.json").read_text())
    )
    assert not (root / "__pycache__").exists()
