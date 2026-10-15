"""Synthetic model replies only; no fixture repository code or network executes."""

import json
from copy import deepcopy
from unittest.mock import Mock

import pytest
from pydantic import SecretStr

from gemforge.ai import GemmaConfig, InferenceError, ModelReply
from gemforge.engine import scan_repository
from gemforge.evidence import build_evidence, digest
from gemforge.migrations import prepare_migration
from gemforge.repairs import repair_evidence, repair_prompt, suggest_repair, validate_repair
from gemforge.schemas import (
    AIRecommendation,
    CheckComparison,
    CommandResult,
    EnvironmentResult,
    ModelProbe,
    VerificationStatus,
)
from gemforge.verification_views import verification_view


@pytest.fixture
def regression(tmp_path):
    (tmp_path / "requirements.txt").write_text("pydantic==1.10.13\n")
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies=["pydantic>=2"]\n')
    (tmp_path / "config.py").write_text(
        'from pydantic import BaseModel\nclass Site(BaseModel):\n    class Config:\n        anystr_strip_whitespace = True\nraise RuntimeError("fixture must never execute")\n'
    )
    (tmp_path / ".env").write_text("GEMINI_API_KEY=target-private-key")
    (tmp_path / "private.txt").write_text("unrelated-private-file")
    capsule = scan_repository(tmp_path)
    capsule.evidence = build_evidence(capsule)
    capsule.recommendations = [
        AIRecommendation(
            package="pydantic",
            status="generated",
            replacement="pydantic>=2",
            migration_steps=["SYNTHETIC prior advice: consider ConfigDict and field_validator."],
        )
    ]
    plan = prepare_migration(tmp_path, "pydantic", "pydantic>=2,<3", capsule)

    def side(label):
        passed = label == "baseline"
        rows = [
            {
                "name": "strip",
                "status": "passed" if passed else "failed",
                "actual": {"name": "alpha" if passed else "  alpha  "},
            }
        ]
        return EnvironmentResult(
            label=label,
            probe_outcomes={"strip": "passed" if passed else "failed"},
            commands=[
                CommandResult(
                    check="probes",
                    argv=["SYNTHETIC-FIXTURE"],
                    status="passed" if passed else "failed",
                    stdout=json.dumps(rows),
                )
            ],
        )

    capsule.verification = VerificationStatus(
        status="failed",
        verdict="regression_detected",
        plan=plan,
        baseline=side("baseline"),
        candidate=side("candidate"),
        comparisons=[
            CheckComparison(
                check="probe:strip", status="regression", explanation="Synthetic observed mismatch"
            )
        ],
        probes=[
            ModelProbe(
                name="strip",
                module="config",
                class_name="Site",
                kwargs={"name": "  alpha  "},
                expected_attributes={"name": "alpha"},
            )
        ],
    )
    return capsule


def payload(capsule):
    evidence = repair_evidence(capsule, "pydantic")
    source = next(e for e in evidence if e.kind == "source")
    return {
        "package": "pydantic",
        "evidence_ids": [e.id for e in evidence],
        "failure_explanation": "Synthetic fixture: renamed whitespace config key.",
        "changes": [
            {
                "source_evidence_id": source.id,
                "file": "config.py",
                "start_line": 4,
                "end_line": 4,
                "before": "        anystr_strip_whitespace = True",
                "after": "        str_strip_whitespace = True",
                "explanation": "Synthetic minimal key rename; not executed.",
            }
        ],
        "verification_plan": [
            "After separate authorization, repeat the original probes in a temporary candidate."
        ],
        "compatibility_concerns": ["Selected probe coverage is limited."],
        "limitations": ["UNIT FIXTURE: no real inference or repaired-code execution."],
    }


def config():
    return GemmaConfig(api_key=SecretStr("unit-key-for-repair"), allow_hosted=True)


def test_preview_offline_preserves_every_original_field(regression, monkeypatch):
    generate = Mock(side_effect=AssertionError("No offline inference"))
    monkeypatch.setattr("gemforge.repairs.GemmaAdapter.generate", generate)
    before = regression.model_dump_json()
    result = suggest_repair(regression, "Pydantic")
    assert regression.model_dump_json() == before
    assert result.model_dump(exclude={"repairs"}) == regression.model_dump(exclude={"repairs"})
    assert result.repairs[-1].verification_status == "unverified"
    assert result.repairs[-1].status == "not_requested"
    assert result.repairs[-1].parent_verification_sha256 == digest(
        regression.verification.model_dump_json()
    )
    prompt = repair_prompt("pydantic", result.repairs[-1].evidence)
    assert "anystr_strip_whitespace" in prompt and "SYNTHETIC prior advice" in prompt
    assert "  alpha  " in prompt and "target-private-key" not in prompt
    assert "unrelated-private-file" not in prompt
    generate.assert_not_called()


def test_validated_mock_suggestion_not_applied(regression, monkeypatch):
    reply = ModelReply(
        json.dumps(payload(regression)), attempts=2, duration_ms=5, response_id="synthetic-repair"
    )
    monkeypatch.setattr("gemforge.repairs.GemmaAdapter.generate", Mock(return_value=reply))
    result = suggest_repair(regression, "pydantic", ai=True, config=config())
    repair = result.repairs[-1]
    assert repair.status == "generated" and repair.verification_status == "unverified"
    assert repair.inference.response_id == "synthetic-repair"
    assert result.verification == regression.verification
    from pathlib import Path

    assert (
        "anystr_strip_whitespace = True" in (Path(regression.repository) / "config.py").read_text()
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(package="requests"),
        lambda p: p.update(evidence_ids=["invented"]),
        lambda p: p.update(evidence_ids=[p["changes"][0]["source_evidence_id"]]),
        lambda p: p["changes"][0].update(file="../outside.py"),
        lambda p: p["changes"][0].update(start_line=999, end_line=999),
        lambda p: p["changes"][0].update(before="invented original text"),
        lambda p: p["changes"][0].update(after=p["changes"][0]["before"]),
        lambda p: p.update(verified=True),
        lambda p: p.update(commands=["untrusted command"]),
        lambda p: p["changes"].append(deepcopy(p["changes"][0])),
    ],
)
def test_reject_ungrounded_or_executable_contract_fields(regression, mutation):
    value = payload(regression)
    mutation(value)
    with pytest.raises(ValueError):
        validate_repair(json.dumps(value), "pydantic", repair_evidence(regression, "pydantic"))


def test_duplicate_json_and_invalid_response_discarded(regression, monkeypatch):
    with pytest.raises(ValueError, match="Duplicate"):
        validate_repair('{"package":"pydantic","package":"pydantic"}', "pydantic", [])
    monkeypatch.setattr(
        "gemforge.repairs.GemmaAdapter.generate",
        Mock(return_value=ModelReply('{"verified":true}', attempts=1, duration_ms=1)),
    )
    result = suggest_repair(regression, "pydantic", ai=True, config=config())
    assert result.repairs[-1].proposal is None
    assert result.repairs[-1].inference.status == "invalid_response"
    assert result.verification.verdict == "regression_detected"


def test_stale_source_rejected_before_inference(regression, monkeypatch):
    from pathlib import Path

    (Path(regression.repository) / "config.py").write_text(
        "from pydantic import BaseModel\n# changed\n"
    )
    generate = Mock()
    monkeypatch.setattr("gemforge.repairs.GemmaAdapter.generate", generate)
    with pytest.raises(ValueError, match="stale"):
        suggest_repair(regression, "pydantic", ai=True, config=config())
    generate.assert_not_called()


def test_service_failure_keeps_regression_and_no_suggestion(regression, monkeypatch):
    monkeypatch.setattr(
        "gemforge.repairs.GemmaAdapter.generate",
        Mock(side_effect=InferenceError("server_error", "Sanitized service failure", attempts=2)),
    )
    result = suggest_repair(regression, "pydantic", ai=True, config=config())
    assert result.repairs[-1].status == "unavailable" and result.repairs[-1].proposal is None
    assert result.repairs[-1].inference.error_code == "server_error"
    assert result.verification == regression.verification


def test_missing_hosted_permission_never_calls_sdk(regression, monkeypatch):
    create = Mock(side_effect=AssertionError("No SDK call without hosted opt-in"))
    monkeypatch.setattr("google.genai.Client", create)
    cfg = config().model_copy(update={"allow_hosted": False})
    result = suggest_repair(regression, "pydantic", ai=True, config=cfg)
    assert result.repairs[-1].inference.status == "blocked"
    create.assert_not_called()


def test_typed_probe_view_preserves_actual_values_and_original(regression):
    before = regression.model_dump_json()
    view = verification_view(regression)
    assert view.probes[0].baseline.actual == {"name": "alpha"}
    assert view.probes[0].candidate.actual == {"name": "  alpha  "}
    assert view.probes[0].comparison.status == "regression"
    assert regression.model_dump_json() == before
    regression.verification.candidate.commands[0].stdout = "incomplete JSON"
    view = verification_view(regression)
    assert view.probes[0].candidate.status == "failed"
    assert view.probes[0].candidate.actual is None and view.limitations
    with pytest.raises(ValueError, match="detailed"):
        suggest_repair(regression, "pydantic")


def test_api_import_typed_view_and_repair_preserve_parent(regression, monkeypatch):
    from fastapi.testclient import TestClient

    import gemforge.api as api

    client = TestClient(api.app)
    imported = client.post("/analyses/import", json=regression.model_dump(mode="json"))
    assert imported.status_code == 201
    id = imported.json()["id"]
    original = client.get(f"/analyses/{id}").json()
    view = client.get(f"/analyses/{id}/verification")
    assert view.status_code == 200
    assert view.json()["probes"][0]["candidate"]["actual"] == {"name": "  alpha  "}
    preview = client.post("/repairs", json={"analysis_id": id, "dependency": "pydantic"})
    assert preview.status_code == 201
    assert preview.json()["capsule"]["repairs"][-1]["status"] == "not_requested"
    monkeypatch.setattr("gemforge.repairs.GemmaConfig.from_environment", lambda: config())
    monkeypatch.setattr(
        "gemforge.repairs.GemmaAdapter.generate",
        Mock(return_value=ModelReply(json.dumps(payload(regression)), attempts=2, duration_ms=1)),
    )
    response = client.post(
        "/repairs",
        json={"analysis_id": id, "dependency": "pydantic", "ai": True, "allow_hosted": True},
    )
    assert response.status_code == 201
    child = response.json()
    assert child["capsule"]["repairs"][-1]["status"] == "generated"
    assert child["capsule"]["verification"] == original["verification"]
    assert client.get(f"/analyses/{id}").json() == original
    assert client.get(f"/analyses/{child['id']}/export").json() == child["capsule"]
    text = client.get(f"/analyses/{child['id']}/export?format=markdown").text
    assert "unverified, unapplied" in text and "str_strip_whitespace" in text
    assert (
        client.post(
            "/repairs",
            json={"analysis_id": id, "dependency": "pydantic", "confirm_execution": True},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/repairs", json={"analysis_id": "missing", "dependency": "pydantic"}
        ).status_code
        == 404
    )


def test_cli_repair_preview_and_no_overwrite(regression, tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from gemforge.cli import app

    saved = tmp_path / "parent.json"
    saved.write_text(regression.model_dump_json())
    result = CliRunner().invoke(app, ["repair", str(saved), "--dependency", "pydantic", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["repairs"][-1]["status"] == "not_requested"
    output = tmp_path / "existing.json"
    output.write_text("preserved")
    generate = Mock()
    monkeypatch.setattr("gemforge.repairs.GemmaAdapter.generate", generate)
    result = CliRunner().invoke(
        app, ["repair", str(saved), "--dependency", "pydantic", "--ai", "--output", str(output)]
    )
    assert result.exit_code == 2 and output.read_text() == "preserved"
    generate.assert_not_called()


def test_openapi_contract_has_typed_complete_responses():
    from gemforge.api import app

    schema = app.openapi()
    definitions = schema["components"]["schemas"]
    assert {
        "Dependency",
        "DetectedRisk",
        "UsageLocation",
        "AIRecommendation",
        "VerificationStatus",
        "CheckComparison",
        "ProbeObservation",
        "RepairRecommendation",
        "RepairChange",
        "VerificationView",
    }.issubset(definitions)
    for path, method, code, expected in [
        ("/scan", "post", "200", "ExitCapsule"),
        ("/analyze", "post", "201", "AnalysisResponse"),
        ("/verify", "post", "201", "AnalysisResponse"),
        ("/repairs", "post", "201", "AnalysisResponse"),
        ("/analyses/{analysis_id}/verification", "get", "200", "VerificationView"),
    ]:
        assert schema["paths"][path][method]["responses"][code]["content"]["application/json"][
            "schema"
        ]["$ref"].endswith("/" + expected)
    assert (
        definitions["RepairRecommendation"]["properties"]["verification_status"]["const"]
        == "unverified"
    )
    assert definitions["RepairRequest"]["additionalProperties"] is False
    exports = schema["paths"]["/analyses/{analysis_id}/export"]["get"]["responses"]["200"][
        "content"
    ]
    assert exports["application/json"]["schema"]["$ref"].endswith("/ExitCapsule")
    assert exports["text/markdown"]["schema"]["type"] == "string"
