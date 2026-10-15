# Phase 2 implementation and live validation

Date: 15 October 2026. Team: Rogue One. Track: Gemma 4 — Dependency Resilience.
Work was performed during the user-confirmed 10:30 AM–4:30 PM IST window.
Phase 1 code/history, deterministic CLI/API contracts and the independent target
checkout were preserved. No Phase 3 execution engine was built.

## Implemented data flow

Deterministic repository scan/risk detection → bounded evidence → hosted Gemma 4
adapter → typed structure/provenance validation → CLI/API → JSON/Markdown capsule.

- `ai.py`: official Google GenAI SDK, default `gemma-4-26b-a4b-it`, configurable
  `GEMFORGE_MODEL`, secret `GEMINI_API_KEY`, invocation-local `.env`, explicit hosted
  opt-in, access check, timeout, bounded backoff and sanitized failures. The endpoint
  is pinned to Google's Developer API; proprietary or other-model substitution is
  refused. Legacy environment names are supported as aliases, not model fallbacks.
- `evidence.py`: actual manifests, risk and usage records, relevant bounded source
  excerpts with hashes, test-file inventory and explicit missing-metadata limits.
  No .env or unrelated source files are selected as evidence. Credential-like
  source assignments are redacted; the configured API key is also removed from
  the final prompt if it occurs in selected text.
- `recommendations.py`: prompt contract and strict Pydantic/provenance checks.
  All risk IDs and a manifest must be cited. Unknown files/IDs, duplicate JSON
  keys, malformed responses and claimed passing verification states are rejected.
  Concerns, unknowns and limitations are required. This cannot prove semantic truth.
- `analysis.py`: one hypothesis or explicit limitation per at-risk package; separate
  observed facts, AI status and per-package model/request provenance. Default budget
  is ten packages; remaining packages receive explicit request-budget limitations.
- `cli.py`: `analyze --ai --allow-hosted --json`, preserving `scan`; new-file-only
  capsule exports; exit 3 for requested but unavailable/partial AI analysis.
- `api.py`: synchronous `POST /analyze`, `GET /analyses/{id}` and export endpoint,
  preserving `/scan` and `/health`. Latest 20 analyses retained only in process memory.
- `schemas.py` and `exporters.py`: typed hypotheses, steps, proposed changes/checks,
  excerpt evidence and inference provenance. Original/candidate verification stays
  `not_run`; commands are proposed text and are never executed.

Hosted inference with relevant public LinkWatch excerpts is organizer-authorized,
per the user's confirmation. Google documents this model and SDK method at:
https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api.
This documentation is not evidence that this account has model access.

## Actual validation

Runtime: CPython 3.12.14; installed Google GenAI SDK 2.31.0; python-dotenv 1.2.4.

| Check | Result |
| --- | --- |
| `python -m pytest -q --basetemp=.dist/pytest-phase2-release` | **91 passed**, one unsuppressed Starlette/httpx dependency deprecation warning |
| `ruff check src tests` | Passed |
| `ruff format --check src tests` after formatting correction | 18 files already formatted |
| `uv build --offline --out-dir .dist/package-phase2` | Wheel and source distribution built successfully |
| Real LinkWatch `analyze --ai` command | Capsule produced; AI explicitly blocked; exit 3 |
| Frontend | Unchanged in Phase 2; previous production build passed; not rerun for backend-only work |

The first pipeline test found that a Pydantic `model_copy(update=...)` retained
nested verification dictionaries without converting them to typed checks. Assembly
now revalidates the complete recommendation. One formatting check required a final
formatting correction. A normal package build could not refresh setuptools metadata
inside the network sandbox; the cached offline build then succeeded.

SDK tests use explicit mocked clients and representative typed SDK response fixtures.
Pipeline and API success tests also use synthetic unit fixtures. These validate
data flow and failure handling, **not real inference or target compatibility**.
SDK-specific tests explicitly skip without the AI extra; this run installed it and
ran the full suite. Regression coverage includes missing keys, model validation,
.env precedence/no interpolation, consent boundaries, model mismatch, HTTP errors,
timeouts/backoff, malformed/truncated/ungrounded responses, unchanged facts,
per-risk limitations, CLI exit codes, exports, API retrieval and cache eviction.

## Initial credential-blocked LinkWatch result

```powershell
.venv/Scripts/gemforge.exe analyze .dist/LinkWatch --ai --allow-hosted --json --import-map dateutil=python-dateutil --output .dist/linkwatch-phase2.json --markdown .dist/linkwatch-phase2.md
```

Target commit: `f52f3930c8e7c33d934ccf614955a38e26984bd5`; target tree clean.
The command found 26 declarations, 14 packages and the genuine Pydantic manifest
conflict (`requirements.txt:5` pins 1.10.13, `pyproject.toml:17` requires >=2).
It built 20 evidence items, including Pydantic's actual `linkwatch/config.py`
excerpt and test inventory. Only that package was identified at risk by current
implemented checks; no abandonment/vulnerability claim was added.

Actual inference record:

- Configured initial model: `gemma-4-26b-a4b-it`.
- Access method: `google_genai_developer_api`.
- AI analysis: `unavailable`; Pydantic recommendation: `unavailable`.
- Inference: `blocked`; model access: `not_checked`; SDK calls: **0**.
- Error: `configuration` — set `GEMINI_API_KEY` in the local .env or shell.
- No response ID/model version/token usage or model response exists.
- No actual AI-generated LinkWatch migration recommendation exists.
- Overall, original and candidate compatibility verification: **not_run**.

There is no local `.env` and no key in the current shell. No genuine API request
was possible, and no authentication/model availability result was fabricated.
The ignored demo capsules preserve the actual blocker and deterministic evidence;
they are not source-controlled model-output examples.

## Subsequent live request with configured credentials

On 15 October 2026, the user added the local `.env`. Configuration loaded the key
without displaying it, and `git check-ignore` confirmed `.env` remains ignored.
The following real command was executed against Google's official endpoint:

```powershell
.venv/Scripts/gemforge.exe analyze .dist/LinkWatch --ai --allow-hosted --json --import-map dateutil=python-dateutil --output .dist/linkwatch-phase2-live-1.json --markdown .dist/linkwatch-phase2-live-1.md
```

- Model: `gemma-4-26b-a4b-it`; access method: `google_genai_developer_api`.
- `models.get` succeeded and model access was **confirmed**.
- Generation failed with **HTTP 500** after three bounded generation attempts.
- Four SDK calls total (one access check plus three generation attempts).
- Total recorded duration: 64,948.1 ms. CLI exit code: **3**.
- Inference status: `failed`; error code: `provider_error`.
- AI analysis and Pydantic recommendation: `unavailable`.
- No model response, response ID, model version or generated recommendation exists.
- Prompt SHA256: `ed6628121dd93a318f0ab9a7eb8de15439b4a1ee8b22f1e3005b41eea12fc68d`.
- No model substitution or repository-code execution occurred. Verification remains
  `not_run`. Both Git working trees remained clean during the request.
- The configured API key was checked for absence from both JSON and Markdown
  artifacts; neither contains it. No credentials or generated artifacts were staged.

This establishes successful authentication/model metadata access, not successful
generation. The provider returned HTTP 500; no finer cause was established.
The missing-key blocker above is historical and has now been resolved.

## Completion boundary at the first failed generation

Phase 2 implementation and validated application data flow are present with an
explicit provider-generation blocker. Real Gemma 4 model access is confirmed,
but successful generation is **not verified**. Keep credentials local, rerun to
new export filenames when appropriate, and inspect structured output/provider provenance before
claiming a live demonstration. Do not substitute another model on failure.

Phase 3 can consume the typed hypotheses/checks/capsules but must introduce an
explicit execution/sandbox boundary, isolated original/candidate environments,
real test discovery/execution evidence and truthful missing-test/failure/timeout
states. No repository edit, patch application, test command or target install was
performed in Phase 2. Release/advisory metadata, deeper scope resolution and
semantic validation of suggested APIs/versions remain limitations.

GemForge remains local on `main`, with no remote or publication. The confirmed
name is `H26_RogueOne_GemForge`; official starter-fork requirements remain pending.

## Subsequent progressive diagnosis and successful full generation

The missing-key and persistent-generation blockers above describe earlier runs.
The subsequent diagnostic run established real Gemma 4 generation:

- Test A: exact `GEMFORGE_OK` response with no generation settings.
- Test B: first plain dependency-question request returned HTTP 500 / INTERNAL;
  one later identical request succeeded with the correct conflict explanation.
- Test C: first plain JSON request returned the same provider error; one later
  identical request succeeded and its object passed strict local Pydantic validation.
- Test D: actual LinkWatch pipeline, 20 evidence items / 11,254 prompt characters,
  model unchanged; one generation HTTP 500 followed by a successful bounded retry.
- Full request: 65,646.4 ms, three SDK calls (access check plus two generation calls),
  response ID `4obQav-dAZ6qg8UPkfm--AM`, finish STOP, 3449 input / 1028 output tokens.
- The real recommendation proposes alignment to `pydantic>=2`, migration of the
  validator/configuration patterns, and tests. It remains an AI hypothesis. No
  package was installed, target modified or verification command executed.
- Actual capsule: `.dist/linkwatch-gemma-d-1.json` and corresponding `.md`.
  Credentials were checked for absence from both. LinkWatch remains clean.
- Reliability regressions: **97 passed**, one dependency deprecation warning;
  Ruff lint and formatting passed. No frontend change/build was needed.

The provider's internal cause was not established; parameter-free requests both
failed and succeeded. This is evidence of intermittent failure, not proof that
the former temperature/output-token settings caused it. SDK 2.31.0 was current
according to the live PyPI check. No model substitution or dependency upgrade occurred.

Phase 2 now has a real, structure/provenance-validated LinkWatch recommendation.
Semantic review and all original/candidate execution remain pending. See
GEMMA-DIAGNOSTICS.md for the full result table, sanitized errors and review caveats.
