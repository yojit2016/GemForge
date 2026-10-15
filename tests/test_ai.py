"""SDK doubles in this file are unit fixtures, never real inference evidence."""

from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from gemforge.ai import GemmaAdapter, GemmaConfig, InferenceError

errors = pytest.importorskip("google.genai.errors", reason="Install .[ai] for SDK tests")
types = pytest.importorskip("google.genai.types", reason="Install .[ai] for SDK tests")
pytest.importorskip("dotenv", reason="Install .[ai] for .env tests")


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    for key in (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMFORGE_MODEL",
        "GEMFORGE_MODEL_ID",
        "GEMFORGE_ALLOW_HOSTED",
        "GEMFORGE_TIMEOUT_MS",
        "GEMFORGE_MAX_ATTEMPTS",
        "GEMFORGE_BACKOFF_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def sdk(monkeypatch):
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.models.get.return_value = types.Model(
        name="models/gemma-4-26b-a4b-it",
        supported_actions=["generateContent"],
    )
    client.models.generate_content.return_value = types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                finish_reason="STOP",
                content=types.Content(parts=[types.Part(text='{"unit_fixture": true}')]),
            )
        ],
        model_version="gemma-4-26b-a4b-it",
        response_id="unit-fixture-response",
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=10, candidates_token_count=5
        ),
    )
    factory = Mock(return_value=client)
    monkeypatch.setattr("google.genai.Client", factory)
    sleeper = Mock()
    monkeypatch.setattr("gemforge.ai.time.sleep", sleeper)
    monkeypatch.setattr("gemforge.ai.random.uniform", Mock(return_value=0))
    return SimpleNamespace(client=client, factory=factory, sleep=sleeper)


def config(**kwargs):
    kwargs.setdefault("max_attempts", 3)
    return GemmaConfig(api_key=SecretStr("unit-test-key"), allow_hosted=True, **kwargs)


def test_missing_key_and_default_model(monkeypatch):
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GemmaConfig.from_environment()
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-key")
    result = GemmaConfig.from_environment()
    assert result.model_id == "gemma-4-26b-a4b-it"
    assert "unit-test-key" not in repr(result)


@pytest.mark.parametrize(
    "model", ["", "gemini-4-pro", "gemma-3-27b-it", "https://host/model", "gemma-4-model\n"]
)
def test_invalid_model(model):
    with pytest.raises(ValidationError):
        config(model_id=model)


def test_env_file_environment_precedence_and_no_interpolation(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text(
        "GEMINI_API_KEY=literal-${HOME}\nGEMFORGE_MODEL=gemma-4-31b-it\n"
    )
    assert GemmaConfig.from_environment().api_key.get_secret_value() == "literal-${HOME}"
    monkeypatch.setenv("GEMINI_API_KEY", "shell-key")
    assert GemmaConfig.from_environment().api_key.get_secret_value() == "shell-key"
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with pytest.raises(ValueError):
        GemmaConfig.from_environment()


def test_no_hosted_request_without_consent(sdk):
    adapter = GemmaAdapter(GemmaConfig(api_key=SecretStr("unit-test-key")))
    with pytest.raises(InferenceError, match="hosted inference"):
        adapter.generate("unit fixture")
    sdk.factory.assert_not_called()


def test_representative_sdk_response_metadata(sdk):
    result = GemmaAdapter(config()).generate("unit fixture")
    assert result.text == '{"unit_fixture": true}'
    assert result.attempts == 2  # access check + generation, not retries
    assert result.duration_ms >= 0
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.response_id == "unit-fixture-response"
    opts = sdk.factory.call_args.kwargs["http_options"]
    assert opts.retry_options.attempts == 1
    assert opts.base_url == "https://generativelanguage.googleapis.com"
    assert sdk.client.models.generate_content.call_args.kwargs["model"] == "gemma-4-26b-a4b-it"


@pytest.mark.parametrize(
    ("status", "category", "calls"),
    [
        (401, "authentication", 1),
        (403, "permission", 1),
        (404, "model_unavailable", 1),
        (429, "rate_limit", 3),
        (503, "server_error", 3),
        (400, "model_configuration", 1),
    ],
)
def test_api_errors_are_bounded_and_sanitized(sdk, status, category, calls):
    sdk.client.models.get.side_effect = errors.APIError(
        status, {"error": {"message": "unit-test-key"}}
    )
    with pytest.raises(InferenceError) as raised:
        GemmaAdapter(config()).generate("fixture")
    assert raised.value.code == category
    assert raised.value.attempts == calls
    assert "unit-test-key" not in str(raised.value)
    assert sdk.client.models.get.call_count == calls
    sdk.client.models.generate_content.assert_not_called()


def test_timeout_and_successful_retry(sdk):
    response = sdk.client.models.generate_content.return_value
    sdk.client.models.generate_content.side_effect = [
        httpx.ReadTimeout("private transport detail"),
        response,
    ]
    result = GemmaAdapter(config()).generate("fixture")
    assert result.attempts == 3
    sdk.sleep.assert_called_once_with(1)


def test_exhausted_timeout(sdk):
    sdk.client.models.generate_content.side_effect = TimeoutError("unit-test-key")
    with pytest.raises(InferenceError) as raised:
        GemmaAdapter(config()).generate("fixture")
    assert raised.value.code == "timeout"
    assert raised.value.model_access == "confirmed"
    assert raised.value.attempts == 4


@pytest.mark.parametrize(
    "response",
    [
        types.GenerateContentResponse(),
        types.GenerateContentResponse(candidates=[types.Candidate(finish_reason="MAX_TOKENS")]),
        types.GenerateContentResponse(model_version="gemini-pro"),
        types.GenerateContentResponse(model_version="gemma-4-31b-it"),
    ],
)
def test_invalid_sdk_responses(sdk, response):
    sdk.client.models.generate_content.return_value = response
    with pytest.raises(InferenceError):
        GemmaAdapter(config()).generate("fixture")


def test_model_access_mismatch_rejected(sdk):
    sdk.client.models.get.return_value = types.Model(name="models/gemini-pro")
    with pytest.raises(InferenceError, match="different model"):
        GemmaAdapter(config()).generate("fixture")
    sdk.client.models.generate_content.assert_not_called()


def test_no_custom_generation_parameters(sdk):
    GemmaAdapter(config()).generate("fixture")
    assert set(sdk.client.models.generate_content.call_args.kwargs) == {"model", "contents"}


def test_timeout_and_retry_configuration_from_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-key")
    assert GemmaConfig.from_environment().max_attempts == 2
    monkeypatch.setenv("GEMFORGE_TIMEOUT_MS", "45000")
    monkeypatch.setenv("GEMFORGE_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("GEMFORGE_BACKOFF_SECONDS", "2")
    cfg = GemmaConfig.from_environment()
    assert (cfg.timeout_ms, cfg.max_attempts, cfg.backoff_seconds) == (45000, 1, 2)
    monkeypatch.setenv("GEMFORGE_TIMEOUT_MS", "unit-test-key")
    with pytest.raises(ValueError, match="GEMFORGE_TIMEOUT_MS") as raised:
        GemmaConfig.from_environment()
    assert "unit-test-key" not in str(raised.value)


def test_exponential_backoff_has_bounded_jitter(sdk, monkeypatch):
    monkeypatch.setattr("gemforge.ai.random.uniform", Mock(return_value=0.25))
    sdk.client.models.get.side_effect = errors.APIError(503, {"error": {"message": "outage"}})
    with pytest.raises(InferenceError):
        GemmaAdapter(config()).generate("fixture")
    assert [call.args[0] for call in sdk.sleep.call_args_list] == [1.25, 2.25]


def test_sanitized_provider_diagnostics_and_request_id(sdk):
    response = httpx.Response(
        500,
        headers={
            "x-request-id": "fixture-request-id",
            "x-goog-api-key": "unit-test-key",
            "set-cookie": "private-cookie",
        },
    )
    sdk.client.models.generate_content.side_effect = errors.APIError(
        500,
        {
            "error": {
                "status": "INTERNAL",
                "message": "Internal error unit-test-key https://host/?key=unit-test-key",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RequestInfo",
                        "requestId": "fixture-body-id",
                    }
                ],
            },
        },
        response=response,
    )
    with pytest.raises(InferenceError) as raised:
        GemmaAdapter(config(max_attempts=1)).generate("fixture")
    error = raised.value
    assert error.code == "server_error"
    assert len(error.diagnostics) == 1
    diagnostic = error.diagnostics[0]
    assert diagnostic.http_status == 500
    assert diagnostic.provider_status == "INTERNAL"
    assert diagnostic.operation == "generation"
    assert diagnostic.request_ids == {
        "x-request-id": "fixture-request-id",
        "google.rpc.RequestInfo": "fixture-body-id",
    }
    assert "unit-test-key" not in diagnostic.model_dump_json()
    assert "private-cookie" not in diagnostic.model_dump_json()
    assert "https://host" not in diagnostic.model_dump_json()
