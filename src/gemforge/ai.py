"""Explicit Google GenAI adapter. Not called by Phase 1 scans.

No default model, network probing, fallback, fabricated recommendation or mock output.
An SDK response is unverified model text; Phase 2 must validate structured recommendations.
"""

import os

from pydantic import Field, SecretStr

from .schemas import Schema


class GemmaConfig(Schema):
    model_id: str = Field(min_length=1)
    api_key: SecretStr

    @classmethod
    def from_environment(cls) -> "GemmaConfig":
        model = os.getenv("GEMFORGE_MODEL_ID", "").strip()
        key = os.getenv("GOOGLE_API_KEY", "").strip()
        if not model or not key:
            raise ValueError(
                "Set GEMFORGE_MODEL_ID and GOOGLE_API_KEY explicitly; no fallback is configured."
            )
        if "gemma" not in model.lower() or "gemini" in model.lower():
            raise ValueError("GEMFORGE_MODEL_ID must explicitly identify a Gemma model.")
        return cls(model_id=model, api_key=SecretStr(key))


class GemmaAdapter:
    def __init__(self, config: GemmaConfig):
        self.config = config

    def generate_text(self, prompt: str) -> str:
        """Perform a real explicit request. Errors propagate; never retry another model."""
        from google import genai
        from google.genai import types

        with genai.Client(
            api_key=self.config.api_key.get_secret_value(),
            http_options=types.HttpOptions(timeout=60_000),
        ) as client:
            response = client.models.generate_content(model=self.config.model_id, contents=prompt)
        if not response.text:
            raise RuntimeError("Gemma returned no text; no recommendation was generated.")
        return response.text
