"""Explicit, bounded Google GenAI calls. Never substitute another model."""

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator

from .schemas import Schema


class GemmaConfig(Schema):
    model_id: str = "gemma-4-26b-a4b-it"
    api_key: SecretStr
    timeout_ms: int = Field(default=60_000, ge=1000, le=120_000)
    max_attempts: int = Field(default=3, ge=1, le=4)
    backoff_seconds: float = Field(default=1, ge=0, le=5)
    allow_hosted: bool = False

    @field_validator("model_id")
    @classmethod
    def gemma_four_only(cls, value: str) -> str:
        if not re.fullmatch(r"(?:models/)?gemma-4-[a-z0-9][a-z0-9.-]*", value):
            raise ValueError(
                "Configure an explicit Gemma 4 model ID; other models are not allowed."
            )
        return value

    @classmethod
    def from_environment(cls, env_file: Path | None = None) -> "GemmaConfig":
        """Read only the invocation directory's .env, never the target's file.

        Environment values win, including explicit empty values. No interpolation
        or mutation of process environment. Old variable names remain aliases.
        """
        values: dict[str, Any] = {}
        path = env_file if env_file is not None else Path.cwd() / ".env"
        if path.is_file():
            try:
                from dotenv import dotenv_values
            except ImportError:
                raise ValueError("Install AI support: pip install -e '.[ai]'.") from None
            values.update(dotenv_values(path, interpolate=False, encoding="utf-8-sig"))
        values.update(os.environ)
        model = values.get("GEMFORGE_MODEL", values.get("GEMFORGE_MODEL_ID", "gemma-4-26b-a4b-it"))
        key = str(values.get("GEMINI_API_KEY", values.get("GOOGLE_API_KEY", "")) or "").strip()
        if not key:
            raise ValueError(
                "Set GEMINI_API_KEY in your shell or local .env (see .env.example); "
                "install AI support with pip install -e '.[ai]'. No inference was made."
            )
        # Validate separately to avoid exposing configuration values through errors.
        try:
            return cls(
                model_id=str(model),
                api_key=SecretStr(key),
                allow_hosted=str(values.get("GEMFORGE_ALLOW_HOSTED", "")).lower() == "true",
            )
        except ValueError:
            raise ValueError(
                "GEMFORGE_MODEL must identify a Gemma 4 model; no model fallback."
            ) from None


class InferenceError(RuntimeError):
    """Safe error details: raw SDK exceptions may contain credentials or URLs."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        attempts: int = 0,
        duration_ms: float = 0,
        model_access: str = "not_checked",
    ):
        super().__init__(message)
        self.code = code
        self.attempts = attempts
        self.duration_ms = duration_ms
        self.model_access = model_access


@dataclass(frozen=True)
class ModelReply:
    text: str
    attempts: int
    duration_ms: float
    response_id: str | None = None
    model_version: str | None = None
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class GemmaAdapter:
    def __init__(self, config: GemmaConfig):
        self.config = config

    def generate_text(self, prompt: str) -> str:
        return self.generate(prompt).text

    def generate(self, prompt: str) -> ModelReply:
        """Check model access then generate; at most max_attempts per operation."""
        if not self.config.allow_hosted:
            raise InferenceError(
                "hosted_not_allowed",
                "Confirm hosted inference is permitted and use --allow-hosted or GEMFORGE_ALLOW_HOSTED=true.",
            )
        if not self.config.api_key.get_secret_value().strip():
            raise InferenceError("missing_key", "Set GEMINI_API_KEY; no inference was made.")
        try:
            import httpx
            from google import genai
            from google.genai import errors, types
        except ImportError:
            raise InferenceError(
                "sdk_missing", "Install AI support: pip install -e '.[ai]'."
            ) from None
        started = time.perf_counter()
        attempts = 0
        access = "not_checked"

        def call(operation):
            nonlocal attempts
            for attempt in range(self.config.max_attempts):
                attempts += 1
                try:
                    return operation()
                except errors.APIError as error:
                    code = error.code
                    transient = code in {408, 429, 500, 502, 503, 504}
                    category, message = {
                        401: (
                            "authentication",
                            "Gemma authentication failed (HTTP 401); check GEMINI_API_KEY.",
                        ),
                        403: (
                            "permission",
                            "Gemma access denied (HTTP 403); check account/model permissions.",
                        ),
                        404: (
                            "model_unavailable",
                            "Configured Gemma 4 model was not found (HTTP 404); no fallback was attempted.",
                        ),
                        429: ("rate_limit", "Gemma rate limit exhausted (HTTP 429); retry later."),
                    }.get(
                        code,
                        (
                            "provider_error",
                            f"Gemma API request failed (HTTP {code}); no fallback was attempted.",
                        ),
                    )
                except (httpx.TimeoutException, TimeoutError):
                    transient = True
                    category, message = (
                        "timeout",
                        "Gemma request timed out; no successful response was recorded.",
                    )
                except httpx.TransportError:
                    transient = True
                    category, message = (
                        "network",
                        "Gemma network request failed; check connectivity.",
                    )
                if not transient or attempt == self.config.max_attempts - 1:
                    raise InferenceError(category, message) from None
                time.sleep(min(self.config.backoff_seconds * (2**attempt), 10))

        try:
            # Disable SDK retries so application backoff is the single bounded layer.
            with genai.Client(
                api_key=self.config.api_key.get_secret_value(),
                vertexai=False,
                http_options=types.HttpOptions(
                    base_url="https://generativelanguage.googleapis.com",
                    api_version="v1beta",
                    timeout=self.config.timeout_ms,
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            ) as client:
                try:
                    model = call(lambda: client.models.get(model=self.config.model_id))
                except InferenceError:
                    access = "failed"
                    raise
                if not model.name or model.name.removeprefix(
                    "models/"
                ) != self.config.model_id.removeprefix("models/"):
                    access = "failed"
                    raise InferenceError(
                        "model_mismatch",
                        "Provider returned a different model; refusing substitution.",
                    )
                if model.supported_actions and "generateContent" not in model.supported_actions:
                    access = "failed"
                    raise InferenceError(
                        "model_unavailable",
                        "Configured model does not advertise generateContent support.",
                    )
                access = "confirmed"
                response = call(
                    lambda: client.models.generate_content(
                        model=self.config.model_id,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0, max_output_tokens=6000),
                    )
                )
            candidates = response.candidates or []
            finish = (
                str(candidates[0].finish_reason.value)
                if candidates and candidates[0].finish_reason
                else None
            )
            if finish and finish != "STOP":
                raise InferenceError(
                    "invalid_response",
                    f"Gemma response did not finish normally ({finish}); not accepted.",
                )
            if response.model_version and "gemini" in response.model_version.lower():
                raise InferenceError(
                    "model_mismatch",
                    "Provider identified a different model; refusing substitution.",
                )
            text = response.text
            if not text or not text.strip() or len(text) > 100_000:
                raise InferenceError(
                    "invalid_response",
                    "Gemma response was empty or exceeded the response size limit.",
                )
            usage = response.usage_metadata
            return ModelReply(
                text=text,
                attempts=attempts,
                duration_ms=(time.perf_counter() - started) * 1000,
                response_id=response.response_id,
                model_version=response.model_version,
                finish_reason=finish,
                input_tokens=usage.prompt_token_count if usage else None,
                output_tokens=usage.candidates_token_count if usage else None,
            )
        except InferenceError as error:
            error.attempts = attempts
            error.duration_ms = (time.perf_counter() - started) * 1000
            error.model_access = access
            raise
        except Exception:
            raise InferenceError(
                "sdk_error",
                "Unexpected SDK/transport response; no recommendation accepted. Check installed SDK compatibility.",
                attempts=attempts,
                duration_ms=(time.perf_counter() - started) * 1000,
                model_access=access,
            ) from None
