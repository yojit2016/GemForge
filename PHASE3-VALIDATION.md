# Phase 3 — observed migration verification

Date: 15 October 2026. Team: Rogue One. Final submission name:
`H26_RogueOne_GemForge`. No submission repository was created or pushed.
The required starter-fork URL remains unconfirmed.

Organizer clarification: hosted/cloud Gemma 4 inference is explicitly permitted
for Track 1. The existing Google GenAI SDK adapter and model
`gemma-4-26b-a4b-it` remain unchanged. No local inference runtime is required.
This clarification preserves the approved verification scope; the results below
come from the completed single comparison, not an additional target run.

## Implementation

- Shared `verify_repository` engine used by Typer `verify` and FastAPI `/verify`.
- Default preview performs no installations or target-code execution. Explicit
  consent, Python 3.12 and a non-administrator token are required for execution.
- Separate temporary baseline/candidate source copies, homes and virtual
  environments. Git metadata, secret files, caches and links are excluded.
- Narrow, hash-guarded root manifest edits; readable unified diff. No AI commands,
  source patches, global installations or target project build hooks execute.
- Binary-wheel-only PyPI installation. Candidate constrains all existing baseline
  package versions except the selected dependency and pip; new required
  transitives are allowed and recorded.
- Fixed syntax/import/pytest/data-only model probes, bounded command time/output,
  sanitized logs, JUnit test identities, explicit missing/failed/inconclusive
  states, paired comparisons and cleanup.
- Typed JSON/Markdown capsules preserve deterministic facts, AI hypotheses and
  observed verification results separately. Probe inputs, import module,
  configured timeouts, versions and wheel hashes support reproducing the scope.

## Exactly one approved live comparison

Target: separate `.dist/LinkWatch` clone, clean at
`f52f3930c8e7c33d934ccf614955a38e26984bd5`.

Started 08:35:29 UTC / 14:05:29 IST; completed 08:38:59 UTC / 14:08:59 IST.
Python **3.12.14**, normal Windows account, administrator token **false**.
The user explicitly approved this host run after disclosure that a virtual
environment is not an OS security sandbox. Docker's daemon was unavailable.

Baseline installation used root `requirements.txt` and `requirements-dev.txt`,
plus pytest `>=8.3,<10`. Baseline `pyproject.toml` independently declares
`pydantic>=2`, conflicting with requirements' `pydantic==1.10.13`. Passing both
declarations to pip would be unsatisfiable; this comparison tests the documented
requirements-file profile, rather than pretending every baseline installation
route works. The original conflict remains visible in the capsule.

Candidate changed only these declarations in its temporary copy:

```diff
--- requirements.txt
-pydantic==1.10.13
+pydantic>=2,<3
--- pyproject.toml
-    "pydantic>=2",
+    "pydantic>=2,<3",
```

This explicitly narrows the accepted Gemma proposal `pydantic>=2` to major 2 as
approved by the user. No source code or unrelated dependency declarations changed.
No new inference request was made during verification. The earlier genuine Gemma
analysis and response ID `4obQav-dAZ6qg8UPkfm--AM` remain in the capsule.

Checks used 60-second timeouts; each installation/venv setup used 180 seconds.
No timeout occurred. Existing tests used their localhost HTTP server; no LinkWatch
application command was run against public websites.

| Observed check | Baseline | Candidate |
| --- | --- | --- |
| Virtual environment / binary-wheel installation | Passed | Passed |
| Pydantic installed | 1.10.13 | 2.14.1 |
| pytest installed | 9.1.1 | 9.1.1 |
| Python syntax | Passed | Passed |
| `linkwatch.config` import | Passed | Passed, configuration warning |
| Existing pytest suite | 9 passed, 1 failed | 9 passed, 1 failed |
| Compatibility probes | 5 passed | 4 passed, 1 failed |

All shared package versions other than Pydantic were identical. Candidate added
`annotated-types==0.8.0`, `pydantic-core==2.50.1` and
`typing-inspection==0.4.4` as Pydantic transitives. Wheel SHA256 hashes were captured
for 26 baseline and 29 candidate installations; bootstrap pip has version metadata
but no downloaded-wheel hash in these install reports.

## Five reviewed probes

Specifications: `examples/linkwatch-pydantic-probes.json` and the final capsules.

| Probe | Baseline | Candidate |
| --- | --- | --- |
| `site_strips_whitespace` | Passed: `"alpha"` | **Failed**: `"  alpha  "` |
| `site_rejects_empty_name` | Passed: ValidationError | Passed: ValidationError |
| `site_rejects_invalid_url` | Passed: ValidationError | Passed: ValidationError |
| `settings_forbids_extra` | Passed: ValidationError | Passed: ValidationError |
| `settings_defaults` | Passed | Passed |

The candidate warning identifies `anystr_strip_whitespace` as renamed to
`str_strip_whitespace`. Together with the observed value, this establishes a
behavioral regression in the manifest-only candidate. The source configuration
needs a separately reviewed migration; none was applied here. V1-style validators
and class-based Config still execute in this tested version but emit deprecation
warnings. They are not universally broken merely because Gemma suggested changes.
Settings' extra-field rejection remained intact in the selected probe.

## Existing failure and verdict

`tests.test_report::test_report_renders_all_sites` fails in **both** environments:
Jinja2 **2.11.3** imports `soft_unicode` from MarkupSafe **3.0.4**, raising
`ImportError`. This is an observed baseline failure, not a Pydantic regression.
The other nine existing test identities pass in both environments.

- Newly failing existing pytest tests: **0**.
- Newly failing compatibility probes: **1**, whitespace stripping.
- Existing pytest tests repaired: **0**.
- Final verdict: **`regression_detected`**.

The candidate is not established as compatible. Installation/import success and
four passing probes do not establish full migration safety. The shared reporting
failure also prevents end-to-end HTML-report validation. No unrelated dependency
fix or source rewrite was attempted, and no second target run occurred.

## Evidence and integrity

Final user-facing exports, ignored by Git:

- `capsules/linkwatch-phase3.json`
- `capsules/linkwatch-phase3.md`

Both include original constraints/usages/risks and prior AI provenance, candidate
manifest contents/diff/hashes, installation profiles and pinned controls, exact
argument vectors, exit codes, durations, bounded sanitized stdout/stderr, Python
and package versions, wheel hashes, individual test/probe outcomes, **23** paired
comparison records, verdict, limitations and cleanup evidence.

Snapshot SHA256:
`0722e3403726984523f1c34bbcf1d3da8c42588211752ef79bb7211f5e958999`.

The original raw run capsule is retained at `.dist/linkwatch-phase3-1.json`/`.md`.
Post-run integrity audit: `.dist/linkwatch-phase3-1-integrity.json`.
Reviewed probe specifications, timeouts and integrity evidence were attached to
the final exports afterward without changing observed outcomes or rerunning code.

- Complete original LinkWatch file hashes, including Git metadata: **unchanged**.
- GemForge active environment installed package versions: **unchanged**.
- Temporary copies, homes and virtual environments: **removed**; cleanup true.
- `.dist/verification` has no remaining run directory.
- Original LinkWatch Git status: **clean**, same commit/origin.
- No secrets, temporary environments or generated capsules were committed.

The snapshot intentionally omits Dockerfile, Makefile, `.dockerignore` and
`.gitignore`; these were not needed by the fixed Python checks. This exclusion
is recorded as a scope limitation, not a claim about Docker/build compatibility.
Runtime checks cover one Windows/Python/install profile and one selected Pydantic
version, not every version admitted by `>=2,<3`. Tests run under the host account;
credential exclusion and venv separation are not host filesystem/network isolation.

## GemForge quality checks and commits

- Full regression suite: **132 passed**, one existing Starlette/httpx deprecation
  warning, using `--basetemp .dist/pytest-phase3-final`.
- After the final Markdown evidence adjustment: focused verification suite
  **23 passed**, the same warning, using
  `--basetemp .dist/pytest-phase3-reproduction`.
- Ruff lint: **passed**. Ruff formatting: **27 files already formatted**.
- Git whitespace checks: **passed**.
- An initial test invocation using the default OS temporary directory had 109
  fixture setup errors due to sandbox directory permissions. No application
  assertions ran in that invocation. Workspace-local basetemp runs resolved it.
- Frontend unchanged in this phase; no new frontend functionality/build claim.

Implementation commits:

- `f6920c0 feat(migration): prepare safe manifest-only verification candidates`
- `b41f965 feat(verification): add consent-gated isolated comparison engine`
- `06b50c1 feat(capsule): expose verification through CLI API and evidence reports`
- `129e79a fix(verification): retain reproducible check inputs and integrity evidence`

Git branch remains `main`; GemForge has no remote. The separate LinkWatch origin
is `https://github.com/rishrek/LinkWatch`. Existing history, including `e3dbd30`,
is preserved. Documentation is committed separately after this result audit.

## Phase 4 readiness

The manifest-only verification engine and one approved evidence-producing
comparison are complete. The Pydantic migration itself is **not approved as safe**.
Next work: review a source migration preserving whitespace normalization and
Settings.extra forbid, address the independently observed Jinja2/MarkupSafe issue
as a separate candidate, expand behavioral coverage, add container-backed
execution, then connect frontend analysis/review/verification/export flows.
Future target-code runs need their own authorization reflecting any changed code,
dependencies or checks. Starter-fork provenance must be confirmed before publishing.
