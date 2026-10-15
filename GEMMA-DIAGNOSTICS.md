# Gemma 4 HTTP 500 diagnosis — 15 October 2026

Team: Rogue One. Model throughout: `gemma-4-26b-a4b-it`.
SDK installed and latest published version checked via PyPI: **google-genai 2.31.0**.
No SDK upgrade or model switch was needed. No LinkWatch file or Git history changed.

## Findings

The adapter uses Google's official `client.models.generate_content` method and
supported model ID. See the official example:
https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api.

Previously it supplied temperature=0 and max_output_tokens=6000. It supplied no
native structured-output schema, tools or thinking configuration. The simplified
diagnostic requests omitted **all** custom generation settings, as does the updated
adapter. There is no evidence that the former optional parameters were the cause:
identical parameter-free B and C requests each failed once and later succeeded.

Observed failures were real HTTP **500**, provider status **INTERNAL**, message
**Internal error encountered.** These came through the SDK's APIError from the
configured Google endpoint, not from GemForge's local Pydantic/parser logic.
The available failed responses exposed no request IDs in the supported header/detail
fields. Google's underlying internal cause is not established. The evidence shows
intermittent generation failures, not universal model unavailability.

## Ordered real requests

Each B/C diagnostic invocation made one generation attempt with SDK retries disabled.
After an initial failure, only one later retry was made, with a pause. No later stage
ran until its predecessor succeeded. The initial network approval timed out before
process creation; the permitted approval retry succeeded and did not duplicate A.

| Stage | Actual result | Calls / time | Response ID |
| --- | --- | --- | --- |
| A: exact plain text | `GEMFORGE_OK` | 1 generation; 3471.2 ms | `pITQauCmCse3g8UP-Nyk-Q0` |
| B first: constraint explanation | HTTP 500 / INTERNAL | 1 generation; 861.4 ms | Not supplied |
| B later: identical question | Correct non-overlapping-constraints explanation | 1 generation; 15322.9 ms | `RYbQav63FpOvg8UPhaS0kQU` |
| C first: minimal JSON in prompt | HTTP 500 / INTERNAL | 1 generation; 1845.7 ms | Not supplied |
| C later: identical JSON prompt | Strict Pydantic validation passed | 1 generation; 4264.8 ms | `p4bQaqKkH9asg8UP0djeoAY` |
| D: actual LinkWatch pipeline | First generation 500; bounded retry succeeded; recommendation validated | 1 access check + 2 generation calls; 65646.4 ms | `4obQav-dAZ6qg8UPkfm--AM` |

Test C's actual validated object was `{"package":"pydantic","incompatible":true}`.
It used a plain JSON instruction and local Pydantic validation, not native schema mode.
Test D retained the schema, citation and file-path validators. Its evidence was
20 items / 11,254 prompt characters, with source excerpts only from
`pyproject.toml`, `requirements.txt` and `linkwatch/config.py` plus test inventory.
It used a 90-second transport timeout and at most two generation attempts.

Full response model version: `gemma-4-26b-a4b-it`; finish reason: STOP; usage:
3449 input tokens / 1028 output tokens. Prompt SHA256:
`ed6628121dd93a318f0ab9a7eb8de15439b4a1ee8b22f1e3005b41eea12fc68d`.
Response SHA256:
`7b6cda54e7ec3c942c2742bbf7883b00e663f678b45792cc3036585e9271b97e`.
The accepted capsule retains the first generation's sanitized HTTP 500 diagnostic.

## Real recommendation and semantic limits

Gemma proposed aligning manifests to `pydantic>=2`, changing the v1 validator and
configuration patterns in `linkwatch/config.py`, then checking configuration tests.
It explicitly assumes the pyproject declaration reflects intended version policy.
This target choice is not an organizer/user decision or verified compatibility.

Manual review found important caveats; the original AI output has been preserved:

- The model calls `@validator` and `class Config` incompatible with v2. That is too
  broad: Pydantic documents these as deprecated patterns, with behavior/signature
  changes. `anystr_strip_whitespace` was renamed to `str_strip_whitespace`.
- The actual target also has `Settings.Config.extra = "forbid"`. Any candidate must
  preserve that behavior alongside Site whitespace handling, name/URL validators
  and settings defaults. The generated generic ConfigDict advice is not a complete patch.
- Its proposed `pip install "pydantic>=2"` is not proof that the full target
  environment resolves or behaves correctly. No suggested command was executed.

Primary semantic review source:
https://docs.pydantic.dev/latest/migration/.
Schema/provenance validation passed; semantic completeness and runtime compatibility
have **not** passed. Overall, original and candidate verification remain `not_run`.

## Reliability changes and regression checks

- No custom generation parameters, native output schema, thinking settings or tools.
- Environment-configurable timeout, attempts and base backoff. Defaults: 60 seconds,
  two attempts per operation, one-second base delay plus bounded random jitter.
- SDK retries disabled so retry layers do not multiply calls.
- Sanitized per-attempt HTTP status, provider status/message and selected request
  IDs captured when supplied. Raw exceptions, credentials, cookies and headers are
  not serialized. Authentication, model configuration, server, timeout and malformed
  response failures remain distinguishable.
- A persistent service/auth failure stops network requests for subsequent
  dependencies in that analysis while preserving all deterministic findings and
  explicit per-dependency limitations. No persistent/background retry service added.
- Tests now isolate local configuration from the user's real .env.

`pytest -q --basetemp=.dist/pytest-gemma-reliability`: **97 passed**, one existing
Starlette/httpx deprecation warning. Ruff check and format check passed. The tests
cover configurable bounds, jitter, sanitized provider fields/request IDs, the
parameter-free request shape and stopping subsequent dependency calls after outage.
Unit fixtures remain separate from the real results above.

Ignored local evidence: `.dist/gemma-test-a-1.json`, `.dist/gemma-test-b-1.json`,
`.dist/gemma-test-b-2.json`, `.dist/gemma-test-c-1.json`, `.dist/gemma-test-c-2.json`,
`.dist/linkwatch-gemma-d-1.json` and `.md`. These are genuine observations, not mocks.
The key was checked for absence from the exported full capsule. No secrets or
generated artifacts were staged. No alternate model was tried or configured.
