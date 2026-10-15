# Evidence-grounded repair workflow validation

15 October 2026 — Rogue One, GemForge Track 1. Hosted Google Gemma 4 inference
is organizer-authorized. No original LinkWatch source or frontend files changed;
no target code or repaired source was executed in this milestone.

## Investigation and engineer-reviewed suggestion

The preserved Phase 3 capsule records Pydantic **1.10.13** in the baseline and
**2.14.1** in the manifest-only candidate. The `site_strips_whitespace` probe
expected `name="alpha"` from input `name="  alpha  "`. Baseline returned
`"alpha"`; candidate returned `"  alpha  "`. This remains an actual regression.

At LinkWatch commit `f52f3930c8e7c33d934ccf614955a38e26984bd5`,
`linkwatch/config.py:11–12` contains:

```python
    class Config:
        anystr_strip_whitespace = True
```

The recorded candidate import warning explicitly identifies the rename from
`anystr_strip_whitespace` to `str_strip_whitespace`. An engineer-reviewed minimal
**suggestion for a future Pydantic 2 candidate only** is the one-line replacement
at `linkwatch/config.py:12`:

```diff
-        anystr_strip_whitespace = True
+        str_strip_whitespace = True
```

This suggestion is **unverified, unapplied and not a generated Gemma response**.
It follows the observed key-renaming warning and failing value, but no repaired
model has been instantiated and no repaired test pass is claimed. Keep the
original v1 baseline and both original failing artifacts unchanged.

The previous successful Gemma migration recommendation proposed broader
`ConfigDict`/`field_validator` migration. It is included as an AI hypothesis in
the new repair evidence. The actual Phase 3 import/probe results show that
class-based Config and v1-style validators still execute in the tested v2 version
while emitting deprecation warnings. A broad rewrite is not necessary to explain
the demonstrated whitespace failure. Any broader migration needs its own review.
In particular, preserve `Settings.Config.extra = "forbid"` at lines 32–33: its
compatibility probe passed in both environments.

Future verification, after explicit approval of the candidate source change,
should repeat all five original probes and the same suite, inspect URL and
whitespace-only-name normalization as additional reviewed coverage, and compare
the same dependency profile. The existing Jinja2/MarkupSafe report failure is
independent and must not be attributed to or silently fixed by this suggestion.
No source-change application endpoint or automatic patch runner was added.

## Implemented workflow

- `suggest_repair` shared by `gemforge repair` and `POST /repairs`.
- Offline evidence preview by default; explicit hosted opt-in for real inference.
- Requires an actual reported paired probe regression with input/expected/actual
  details, matching dependency declarations and current Python source excerpts
  matching captured anchors. No file path supplied by the model is read.
- Selected source/probes/import diagnostics/prior recommendations form bounded
  evidence. Secret-like data is redacted and the configured key is excluded.
- Typed `RepairProposal` contains exact file/line ranges, before text, suggested
  after text, rationale, evidence IDs, verification plan, concerns and limitations.
- Strict structure/reference/range/before-text validation rejects invented paths,
  evidence IDs, duplicate JSON keys, overlapping changes and verification/command
  fields. Semantic and syntax correctness remain explicitly unverified.
- Deep-copy result appends `repairs` without replacing migration recommendations,
  old inference records, baseline/candidate outcomes or verification verdict.
- `RepairRecommendation.verification_status` can only be `unverified`. Model and
  API failures record sanitized diagnostics; no fallback or fabricated proposal.
- JSON/Markdown exporters include the suggestion/evidence/provenance when present,
  or the actual failure reason, alongside original verification evidence.

## Genuine hosted repair inference result

New output files (Git-ignored):

- `capsules/linkwatch-repair-1.json`
- `capsules/linkwatch-repair-1.md`

The request started at approximately **14:37:22 IST**. It used the unchanged
official Google GenAI SDK adapter and **`gemma-4-26b-a4b-it`**, 90-second timeout,
at most two attempts per operation, existing exponential backoff/jitter, no native
JSON schema/thinking/tools/custom generation settings, and no alternate model.

| Actual operation | Result |
| --- | --- |
| Model metadata access | Confirmed |
| Generation attempt 1 | HTTP **504**, `DEADLINE_EXCEEDED` |
| Generation attempt 2 | HTTP **504**, `DEADLINE_EXCEEDED` |
| Provider message | Deadline expired before operation could complete. |
| Total calls | **3**: one access check, two generation attempts |
| Total duration | **181112.2 ms** |
| Request IDs / response ID | Not supplied |
| Repair status | **`unavailable`**, proposal **null** |
| Repair verification status | **`unverified`** |
| Original verdict | **`regression_detected`**, unchanged |

Prompt SHA256:
`1466f7b66af0aa46bb6ff0b30665cf794ea8b201b69c0d228fbf04792b7293eb`.

No valid repair response was returned. The engineering suggestion above must not
be presented as Gemma-generated or verified. No additional generation loop or
model substitution was attempted after these bounded failures. Earlier successful
Gemma migration inference remains historical evidence, not success of this request.

## Evidence preservation and API readiness

Hashes were recorded before the hosted request for all four original artifacts:
`capsules/linkwatch-phase3.json`, `.md`, and `.dist/linkwatch-phase3-1.json`, `.md`.
All four remain byte-for-byte unchanged. The new capsule's typed `verification`
also equals the parent's. Original LinkWatch Git status remains clean.
The hash inventory is `.dist/repair-parent-hashes-1.json` (ignored).

The additive API contract is documented in `API-CONTRACT.md` and OpenAPI:

- Existing typed scan/risk/usage/migration/verification/export responses retained.
- `POST /analyses/import` restores a saved capsule without another target run.
- `GET /analyses/{id}/verification` returns typed expected/actual probe details and
  existing comparisons. Malformed/incomplete stored details remain null with
  explicit limitations; the parent is never rewritten.
- `POST /repairs` creates a new cached capsule; defaults to offline preview.
- JSON and Markdown exports carry explicit OpenAPI media types.
- Source application/commands/execution-consent fields are not accepted by repair.
- Root `ai_status` still describes original migration analysis; repair status is
  separate. HTTP 201 is not a statement of successful inference or compatibility.

Antigravity's frontend worktree/branch was not edited or operated on. Backend
contracts are ready for frontend integration on its independent schedule; this
milestone does not claim dashboard completion or frontend build validation.

## Tests and commits

Complete Python suite: **152 passed**, one existing Starlette/httpx deprecation
warning. Command: `.venv/Scripts/python.exe -m pytest -q --basetemp
.dist/pytest-repair-api-full`.

The **20 repair/view/API tests** use explicitly synthetic replies and do not make
network calls or execute fixture repository code. Coverage includes exact source
grounding, malformed/invented locations, stale source, missing detailed probes,
duplicate JSON, overlapping suggestions, command/verification fields, offline
consent, service failures, unchanged parent results, typed actual values, CLI
overwrite protection, import/export and OpenAPI contracts. Existing verification
regression tests remain intact.

Ruff lint: **passed**. Ruff format check: **30 files already formatted**.
Git whitespace checks: **passed**. Documentation-only completion changes do not
alter tested Python code. No frontend files, secret configuration, generated
capsules or temporary environments were committed.

- `5c56d52 feat(repair): ground unverified source suggestions in regression evidence`
- `8cf077f feat(api): expose repair suggestions and typed verification views`

Documentation and actual hosted failure evidence are committed separately.
GemForge development remains on `main`, with no publication or push performed.
