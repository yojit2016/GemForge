"""CLI/API data-flow tests. Model outputs here are explicit synthetic fixtures."""

import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

import gemforge.api as api_module
from gemforge.ai import ModelReply
from gemforge.cli import app
from gemforge.engine import scan_repository
from gemforge.evidence import build_evidence
from gemforge.schemas import ExitCapsule


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMFORGE_MODEL",
        "GEMFORGE_MODEL_ID",
        "GEMFORGE_ALLOW_HOSTED",
    ):
        monkeypatch.delenv(name, raising=False)
    target = tmp_path / "target"
    target.mkdir()
    (target / "requirements.txt").write_text("demo==1\ndemo>=2\n")
    with api_module._analysis_lock:
        api_module._analyses.clear()
    return target


def fixture_reply(repo):
    evidence = build_evidence(scan_repository(repo))
    return ModelReply(
        json.dumps(
            {
                "package": "demo",
                "evidence_ids": [e.id for e in evidence if e.kind in {"risk", "manifest"}],
                "risk_explanation": "Conflicting declared constraints.",
                "target": None,
                "rationale": "Choose a tested version alignment.",
                "affected_files": ["requirements.txt"],
                "proposed_changes": [],
                "migration_steps": ["Review requirements."],
                "compatibility_concerns": ["Unknown APIs."],
                "verification_checks": [
                    {"command": "python -m pytest", "purpose": "Run original tests after opt-in."}
                ],
                "unknowns": ["No runtime verification."],
                "limitations": ["UNIT FIXTURE, NOT REAL INFERENCE"],
            }
        ),
        attempts=2,
        duration_ms=10,
        response_id="unit-fixture",
    )


def test_cli_ai_missing_key_emits_capsule_and_nonzero(repo):
    result = CliRunner().invoke(app, ["analyze", str(repo), "--ai", "--allow-hosted", "--json"])
    assert result.exit_code == 3
    capsule = json.loads(result.stdout)
    assert capsule["ai_status"] == "unavailable"
    assert capsule["verification"]["status"] == "not_run"
    assert "GEMINI_API_KEY" in result.stderr


def test_cli_without_ai_is_offline(repo, monkeypatch):
    generate = Mock(side_effect=AssertionError("Offline mode must not infer"))
    monkeypatch.setattr("gemforge.analysis.GemmaAdapter.generate", generate)
    result = CliRunner().invoke(app, ["analyze", str(repo), "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["ai_status"] == "not_requested"
    assert json.loads(result.stdout)["evidence"]
    generate.assert_not_called()


def test_cli_validated_mock_response_exports_both_formats(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-key")
    generate = Mock(return_value=fixture_reply(repo))
    monkeypatch.setattr("gemforge.analysis.GemmaAdapter.generate", generate)
    output, markdown = tmp_path / "capsule.json", tmp_path / "capsule.md"
    result = CliRunner().invoke(
        app,
        [
            "analyze",
            str(repo),
            "--ai",
            "--allow-hosted",
            "--json",
            "--output",
            str(output),
            "--markdown",
            str(markdown),
        ],
    )
    assert result.exit_code == 0, result.output
    capsule = ExitCapsule.model_validate_json(output.read_text())
    assert capsule.ai_status == "generated"
    assert capsule.recommendations[0].verification_checks[0].status == "not_run"
    text = markdown.read_text(encoding="utf-8")
    assert "Observed evidence" in text
    assert "Inference provenance" in text
    assert "UNIT FIXTURE, NOT REAL INFERENCE" in text
    assert "Proposed verification (not_run)" in text
    assert "unit-test-key" not in text
    assert json.loads(result.stdout)["ai_status"] == "generated"


def test_cli_overwrite_preflight_happens_before_inference(repo, tmp_path, monkeypatch):
    generate = Mock()
    monkeypatch.setattr("gemforge.analysis.GemmaAdapter.generate", generate)
    output = tmp_path / "existing.json"
    output.write_text("keep")
    result = CliRunner().invoke(app, ["analyze", str(repo), "--ai", "--output", str(output)])
    assert result.exit_code == 2
    assert output.read_text() == "keep"
    generate.assert_not_called()


def test_api_analysis_retrieval_and_exports(repo):
    client = TestClient(api_module.app)
    response = client.post("/analyze", json={"path": str(repo)})
    assert response.status_code == 201
    id = response.json()["id"]
    capsule = response.json()["capsule"]
    assert capsule["ai_status"] == "not_requested"
    assert client.get(f"/analyses/{id}").json() == capsule
    assert client.get(f"/analyses/{id}/export").json() == capsule
    markdown = client.get(f"/analyses/{id}/export?format=markdown")
    assert "Observed evidence" in markdown.text
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert client.get(f"/analyses/{id}/export?format=html").status_code == 422
    assert client.get("/analyses/missing").status_code == 404
    assert (
        client.post("/analyze", json={"path": str(repo), "max_ai_packages": 0}).status_code == 422
    )


def test_api_ai_returns_explicit_external_blocker(repo):
    response = TestClient(api_module.app).post(
        "/analyze", json={"path": str(repo), "ai": True, "allow_hosted": True}
    )
    assert response.status_code == 201
    capsule = response.json()["capsule"]
    assert capsule["ai_status"] == "unavailable"
    assert capsule["inferences"][0]["attempts"] == 0
    assert capsule["inferences"][0]["status"] == "blocked"
    assert "GEMINI_API_KEY" in capsule["inferences"][0]["message"]


def test_api_successful_mock_data_flow(repo, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-key")
    monkeypatch.setattr(
        "gemforge.analysis.GemmaAdapter.generate", Mock(return_value=fixture_reply(repo))
    )
    client = TestClient(api_module.app)
    result = client.post(
        "/analyze", json={"path": str(repo), "ai": True, "allow_hosted": True}
    ).json()
    capsule = client.get(f"/analyses/{result['id']}").json()
    assert capsule["ai_status"] == "generated"
    assert capsule["inferences"][0]["response_id"] == "unit-fixture"
    assert capsule["verification"]["status"] == "not_run"
    assert "unit-test-key" not in json.dumps(capsule)


def test_api_cache_is_bounded(repo):
    client = TestClient(api_module.app)
    first = client.post("/analyze", json={"path": str(repo)}).json()["id"]
    for _ in range(20):
        client.post("/analyze", json={"path": str(repo)})
    assert len(api_module._analyses) == 20
    assert client.get(f"/analyses/{first}").status_code == 404
