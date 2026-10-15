"""Migration fixtures are synthetic unit-test outputs, not Gemma inference results."""

import json
from copy import deepcopy
from unittest.mock import Mock

import pytest
from pydantic import SecretStr

from gemforge.ai import GemmaConfig, InferenceError, ModelReply
from gemforge.analysis import analyze_repository
from gemforge.engine import scan_repository
from gemforge.evidence import build_evidence, digest
from gemforge.recommendations import build_prompt, validate_proposal


@pytest.fixture
def repository(tmp_path):
    (tmp_path / "requirements.txt").write_text("pydantic==1.10.13\n")
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies=["pydantic>=2"]\n')
    (tmp_path / "config.py").write_text(
        "from pydantic import BaseModel as BM\nAPI_KEY = 'must-not-transmit'\nclass Site(BM):\n url: str\n"
    )
    (tmp_path / ".env").write_text("GEMINI_API_KEY=must-not-read-target-env\n")
    (tmp_path / "private.txt").write_text("unrelated private text")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_site.py").write_text("raise RuntimeError('must not run')\n")
    return tmp_path


@pytest.fixture
def evidence(repository):
    return build_evidence(scan_repository(repository))


def payload(evidence):
    return {
        "package": "pydantic",
        "evidence_ids": [
            e.id for e in evidence if e.kind in {"manifest", "risk", "usage", "source"}
        ],
        "risk_explanation": "The supplied constraints cannot overlap.",
        "target": None,
        "rationale": "Choose an alignment only after inspecting actual APIs and tests.",
        "affected_files": ["requirements.txt", "pyproject.toml", "config.py"],
        "proposed_changes": [
            {
                "file": "requirements.txt",
                "description": "Align with selected major version after validation.",
            }
        ],
        "migration_steps": [
            "Inspect Site model behavior, then choose one consistent major version."
        ],
        "compatibility_concerns": ["Model parsing behavior may differ between majors."],
        "verification_checks": [
            {
                "command": "python -m pytest tests/test_site.py",
                "purpose": "Check site configuration parsing.",
            }
        ],
        "unknowns": ["Runtime compatibility has not been tested."],
        "limitations": ["Synthetic unit fixture, not a real inference recommendation."],
    }


def cfg():
    return GemmaConfig(api_key=SecretStr("unit-test-key"), allow_hosted=True)


def test_evidence_is_bounded_grounded_and_excludes_secrets(evidence, repository):
    prompt = build_prompt("pydantic", evidence)
    assert "BaseModel" in prompt
    assert "pydantic==1.10.13" in prompt
    assert "must-not-transmit" not in prompt
    assert "must-not-read-target-env" not in prompt
    assert "unrelated private text" not in prompt
    assert str(repository) not in prompt
    assert "Test file detected" in prompt
    assert all(e.excerpt_sha256 == digest(e.excerpt) for e in evidence if e.excerpt is not None)
    assert len({e.id for e in evidence}) == len(evidence)


def test_representative_proposal_parsing(evidence):
    proposal = validate_proposal(json.dumps(payload(evidence)), "pydantic", evidence)
    assert proposal.target is None
    assert proposal.verification_checks[0].status == "not_run"
    fenced = "```json\n" + json.dumps(payload(evidence)) + "\n```"
    assert validate_proposal(fenced, "pydantic", evidence) == proposal


@pytest.mark.parametrize(
    "change",
    [
        {"package": "requests"},
        {"evidence_ids": ["fabricated"]},
        {"affected_files": ["../../private.py"]},
        {"proposed_changes": [{"file": "missing.py", "description": "Change"}]},
        {"verification_checks": [{"command": "pytest", "purpose": "test", "status": "passed"}]},
        {"unknowns": []},
        {"limitations": []},
        {"verification": {"status": "passed"}},
        {"migration_steps": [""]},
    ],
)
def test_invalid_structured_recommendations(evidence, change):
    data = payload(evidence)
    data.update(change)
    with pytest.raises(ValueError):
        validate_proposal(json.dumps(data), "pydantic", evidence)


@pytest.mark.parametrize(
    "text",
    ["not JSON", "{}", "[]", '{"package":"pydantic","package":"other"}', "```json\n{bad}\n```"],
)
def test_malformed_responses(evidence, text):
    with pytest.raises(ValueError):
        validate_proposal(text, "pydantic", evidence)


def test_validated_pipeline_preserves_observed_facts(monkeypatch, repository, evidence):
    before = scan_repository(repository)
    data = payload(evidence)
    generate = Mock(
        return_value=ModelReply(json.dumps(data), attempts=2, duration_ms=42, response_id="fixture")
    )
    monkeypatch.setattr("gemforge.analysis.GemmaAdapter.generate", generate)
    result = analyze_repository(repository, ai=True, config=cfg())
    assert result.dependencies == before.dependencies
    assert result.risks == before.risks
    assert result.usages == before.usages
    assert result.ai_status == "generated"
    assert result.recommendations[0].origin == "ai_hypothesis"
    assert result.recommendations[0].replacement is None
    assert result.recommendations[0].original_constraints == ["==1.10.13", ">=2"]
    assert result.inferences[0].response_id == "fixture"
    assert result.inferences[0].response_sha256 == digest(json.dumps(data))
    assert result.verification.status == "not_run"
    assert result.verification.original_status == result.verification.candidate_status == "not_run"
    assert result.recommendations[0].verification_checks[0].status == "not_run"
    generate.assert_called_once()


def test_invalid_response_is_discarded_not_repaired(monkeypatch, repository):
    generate = Mock(return_value=ModelReply("bad output", 2, 5))
    monkeypatch.setattr("gemforge.analysis.GemmaAdapter.generate", generate)
    result = analyze_repository(repository, ai=True, config=cfg())
    assert result.ai_status == "unavailable"
    assert result.recommendations[0].status == "unavailable"
    assert result.inferences[0].status == "invalid_response"
    assert result.inferences[0].model_access == "confirmed"
    assert result.verification.status == "not_run"


def test_api_error_preserves_capsule_facts(monkeypatch, repository):
    monkeypatch.setattr(
        "gemforge.analysis.GemmaAdapter.generate",
        Mock(side_effect=InferenceError("rate_limit", "HTTP 429", attempts=3)),
    )
    result = analyze_repository(repository, ai=True, config=cfg())
    assert result.risks[0].certainty == "proven"
    assert result.inferences[0].status == "failed"
    assert result.inferences[0].error_code == "rate_limit"
    assert result.recommendations[0].status == "unavailable"


def test_missing_credentials_actionable_and_no_target_env_loading(
    monkeypatch, repository, tmp_path
):
    invocation = tmp_path / "invocation"
    invocation.mkdir()
    monkeypatch.chdir(invocation)
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMFORGE_MODEL", "GEMFORGE_MODEL_ID"):
        monkeypatch.delenv(key, raising=False)
    generate = Mock()
    monkeypatch.setattr("gemforge.analysis.GemmaAdapter.generate", generate)
    result = analyze_repository(repository, ai=True, allow_hosted=True)
    assert result.ai_status == "unavailable"
    assert "GEMINI_API_KEY" in result.recommendations[0].limitations[0]
    generate.assert_not_called()


def test_every_risk_gets_explicit_budget_limitation(monkeypatch, repository):
    with (repository / "requirements.txt").open("a") as file:
        file.write("zlibdemo==1\nzlibdemo>=2\n")
    monkeypatch.setattr(
        "gemforge.analysis.GemmaAdapter.generate",
        Mock(side_effect=InferenceError("timeout", "fixture timeout", attempts=3)),
    )
    result = analyze_repository(repository, ai=True, config=cfg(), max_ai_packages=1)
    assert {r.package for r in result.risks} == {r.package for r in result.recommendations}
    assert result.inferences[1].error_code == "request_budget"
    assert result.recommendations[1].limitations


def test_no_ai_mode_and_no_risks_never_call_sdk(monkeypatch, repository, tmp_path):
    generate = Mock()
    monkeypatch.setattr("gemforge.analysis.GemmaAdapter.generate", generate)
    assert analyze_repository(repository).ai_status == "not_requested"
    empty = tmp_path / "empty"
    empty.mkdir()
    assert analyze_repository(empty, ai=True).ai_status == "no_risks"
    generate.assert_not_called()


def test_prompt_size_limit(evidence):
    items = deepcopy(evidence)
    items[0].description = "x" * 60_000
    with pytest.raises(ValueError, match="prompt size"):
        build_prompt("pydantic", items)


def test_service_failure_stops_further_dependency_requests(monkeypatch, repository):
    with (repository / "requirements.txt").open("a") as file:
        file.write("zlibdemo==1\nzlibdemo>=2\n")
    generate = Mock(side_effect=InferenceError("server_error", "HTTP 500", attempts=2))
    monkeypatch.setattr("gemforge.analysis.GemmaAdapter.generate", generate)
    result = analyze_repository(repository, ai=True, config=cfg())
    generate.assert_called_once()
    assert result.inferences[1].error_code == "service_unavailable"
    assert result.inferences[1].attempts == 0
    assert len(result.recommendations) == 2
    assert len(result.risks) == 2
    assert result.verification.status == "not_run"
