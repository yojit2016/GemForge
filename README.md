# GemForge

By **Rogue One** for Hacktoberfest 2026 Track 1 — Gemma 4: Dependency Resilience.
Confirmed final repository name: `H26_RogueOne_GemForge`. Read-only Python
dependency facts and evidence-grounded Gemma 4 migration hypotheses are exported
as reusable JSON/Markdown Dependency Exit Capsules. Real Gemma 4 LinkWatch
generation has succeeded after a bounded retry of an intermittent HTTP 500.
Phase 3 adds explicit-consent baseline/candidate verification with temporary
Python 3.12 environments, manifest-only edits and observed comparison evidence.

Open `GemForge.code-workspace` for development. GemForge is the root repository;
the ignored `.dist/LinkWatch` clone is only a scan target. Workspace settings keep
that clone out of automatic Source Control discovery. See `REPOSITORIES.md` for
the repository audit, Git ownership fix and unresolved starter-fork requirement.

## Setup

Requires Python 3.12+ and Node.js 22.12+ (Node 24 is also suitable).
Windows PowerShell, from this directory:

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -e '.[dev,ai]'
.venv/Scripts/gemforge.exe scan C:/path/to/repository --json
```

If using uv: `uv venv --python 3.12` then
`uv pip install --python .venv/Scripts/python.exe -e '.[dev,ai]'`.
On Linux/macOS use `python3.12`, `.venv/bin/python`, and `.venv/bin/gemforge`.
Install development dependencies only for GemForge; scans do not install target dependencies.
The `ai` extra is optional for offline scans, but required for the full SDK test
suite and real inference. SDK-specific tests explicitly skip if it is absent.

```powershell
New-Item -ItemType Directory -Force capsules
.venv/Scripts/gemforge.exe scan C:/path/to/repository --json --output capsules/scan.json --markdown capsules/scan.md
# Explicit distribution/import name mapping, when needed:
.venv/Scripts/gemforge.exe scan C:/path/to/repository --import-map dateutil=python-dateutil
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/ruff.exe check src tests
```

Reports go to stderr and `--json` emits clean JSON on stdout. Export destinations
must be new files; existing files are never overwritten. Exit code 0 means the scan
completed, not that dependencies are safe; 2 means input/export failure. Partial
analysis is recorded in `limitations`. Risks do not change the exit code.

## Local API and frontend

```powershell
.venv/Scripts/python.exe -m uvicorn gemforge.api:app --host 127.0.0.1 --port 8000
# In a second terminal:
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open http://127.0.0.1:5173. The minimal React/TypeScript UI scans an explicit local
path through Vite's `/api` proxy. API docs: http://127.0.0.1:8000/docs.
`POST /scan` accepts `{"path":"C:/path/to/repo","import_map":{}}` and returns a capsule.
`GET /health` reports backend availability. `npm.cmd run build` typechecks and builds.
The production frontend needs a same-origin `/api` reverse proxy; the Vite proxy is
development-only. Keep this unauthenticated local filesystem API bound to loopback;
remote hosting/authentication is outside the current implementation.

`POST /analyze` accepts the scan fields plus `ai` (default false), `allow_hosted`
(default false), and `max_ai_packages` (default 10, range 1–50). It completes
synchronously and returns `{ "id": "...", "capsule": {...} }` with HTTP 201.
`GET /analyses/{id}` retrieves it; `GET /analyses/{id}/export?format=json` or
`format=markdown` exports it without filesystem writes. Only the latest 20 results
are held in process memory; restart/eviction returns 404. Hosted inference can make
this synchronous request slow. An HTTP 201 means an analysis capsule was created;
inspect `ai_status`, recommendations and inference errors to determine AI success.

## LinkWatch demo

LinkWatch is the confirmed analysis target; whether it is also the required
starter repository to fork remains unconfirmed:
https://github.com/rishrek/LinkWatch. Keep its checkout and history separate.
No target scripts or tests are run by scanning.

```powershell
git clone https://github.com/rishrek/LinkWatch .dist/LinkWatch
.venv/Scripts/gemforge.exe scan .dist/LinkWatch --json --import-map dateutil=python-dateutil --output capsules/linkwatch.json --markdown capsules/linkwatch.md
```

Observed manifests declare `pydantic==1.10.13` in requirements.txt and
`pydantic>=2` in pyproject.toml. The generic scanner detects this conflict from files;
it contains no LinkWatch-specific risk rules. No package is labeled abandoned or
vulnerable from its name/version alone.

## Contracts and limitations

- `gemforge.engine.scan_repository(path, import_map=None)` is shared by CLI and API.
- Capsules separate manifest facts, constraint assessments, usages, AI recommendations,
  verification, and limitations. Every at-risk package gets a recommendation record,
  initially `not_requested`, then `generated` or `unavailable` when AI is explicitly
  requested. AI hypotheses cannot modify observed facts. Verification is `not_run`.
- PEP 508 requirements and PEP 621 dependencies/optional dependencies are parsed with
  packaging and tomllib. Dependency groups containing strings are read; group includes
  are reported unsupported. Duplicate declarations retain individual sources.
- All discovered requirements*.txt and pyproject.toml declarations are compared together.
  Scan independent projects/profiles separately. Markers and optional groups remain
  uncertain until a target environment and install selection are defined.
- Exact pins and disjoint supported bounds can prove conflicts. A candidate satisfying
  every specifier proves metadata overlap only, not a published release or runtime
  compatibility. Unsupported/unsolved cases stay uncertain. Local versions and arbitrary
  equality are conservative; prereleases are considered for existential overlap.
- Source lines for TOML strings are best-effort and null when ambiguous. Pip options,
  includes, hashes, editable installs, Poetry tables, setup.py, lockfiles, dynamic
  metadata, build dependencies and transitive dependencies are not resolved.
- AST imports and straightforward module-level aliases are mapped. Name-based
  distribution mappings are labeled heuristic; supply explicit mappings for names such
  as `dateutil`. Dynamic/relative/star imports, nested references, conditional bindings,
  reassignment, local module shadowing and runtime reachability are not resolved.
- Ignored environments/build folders and symlinks/junctions are skipped. Discovery is
  capped at 20,000 files and individual source/manifest reads at 2 MB; partial reads and
  parse failures are reported. Repository code is never executed by the scanner.
- No PyPI, advisory or maintenance metadata fetch is implemented. An empty risk list
  is not a safety verdict. Scans need no network once GemForge is installed.

## Gemma 4 migration analysis

The organizer has permitted hosted Google Gemma 4 inference with relevant public
LinkWatch excerpts. The default is `gemma-4-26b-a4b-it`, configurable through
`GEMFORGE_MODEL`. Only Gemma 4 model IDs are accepted; there is no model substitution.
Google documents hosted access through the official Google GenAI SDK:
https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api.

```powershell
# Once only: copy the template, then edit .env locally to set GEMINI_API_KEY.
Copy-Item .env.example .env
.venv/Scripts/gemforge.exe analyze .dist/LinkWatch --ai --allow-hosted --json --import-map dateutil=python-dateutil
# Optional new-file exports:
.venv/Scripts/gemforge.exe analyze .dist/LinkWatch --ai --allow-hosted --output capsules/ai.json --markdown capsules/ai.md
```

Keep the key local; never paste it into an issue or commit it. `.env` is ignored.
Configuration reads only `.env` in the invocation directory (no parent/target
search), without interpolation or environment mutation. Shell values override
file values, including empty shell values. Legacy `GOOGLE_API_KEY` and
`GEMFORGE_MODEL_ID` remain aliases when the new names are absent; legacy model IDs
still must name Gemma 4. `--allow-hosted` or `GEMFORGE_ALLOW_HOSTED=true` explicitly
permits sending the selected evidence. Review disclosure permissions for other
repositories. `scan` and `analyze` without `--ai` make no AI/network requests.

Pipeline: deterministic scan/risk analysis → evidence builder → Gemma 4 → strict
Pydantic and provenance validation. Evidence includes actual declarations, risk
IDs, usage locations, up to eight relevant source excerpts per dependency (60
lines/4000 characters each), and filename-based test inventory. `.env` and unrelated
files are excluded; credential-like source assignments are redacted. Excerpt hashes
cover the text shown. Working-tree reads are not an atomic snapshot.

Every at-risk package receives either a validated AI hypothesis or an explicit
limitation. The default request budget is ten packages (`--max-ai-packages` changes
it); excess packages retain evidence with a request-budget limitation. Generated
objects must cite all observed risks and a manifest, use observed file paths, and
contain concerns, unknowns and limitations. Unknown file paths, fabricated evidence
IDs, malformed/truncated responses and claimed verification results are rejected.
JSON is requested in the prompt and validated locally; native JSON-schema mode is
not assumed to be supported by the chosen model.

The adapter checks model access with `models.get`, then calls `generate_content`
without custom generation settings, tools, native JSON schema or thinking settings.
It pins Google's Developer API endpoint, disables SDK retries, and defaults to two
attempts per operation with exponential backoff plus bounded jitter. Set
`GEMFORGE_TIMEOUT_MS` (1000–120000, default 60000), `GEMFORGE_MAX_ATTEMPTS` (1–4,
default 2), and `GEMFORGE_BACKOFF_SECONDS` (0–5, default 1) in the shell or local
`.env` to tune requests. The successful full live diagnostic used 90000 ms. Auth
and model-not-found failures are not retried. Rate limits, selected server errors
and transport timeouts get bounded retries. Model metadata, response ID, finish
reason, token counts, total call count/duration and prompt/response hashes are
recorded when available. Per-attempt API diagnostics preserve only sanitized status,
provider message and selected request IDs. A persistent server/rate/network/auth
failure stops further dependency requests within that analysis; remaining risks
receive explicit limitations. Raw error bodies, credentials and raw unvalidated
model responses are not exported.

An accepted recommendation is **an AI hypothesis**, not proof that its suggested
version exists, API advice is correct, or a migration is compatible. Structural
and citation checks cannot establish semantic truth. Suggested commands are text
only and are never executed. New-file proposals are currently limited to prose
steps; structured change paths must already occur in the observed evidence.

CLI exit codes: 0 = completed analysis, 2 = input/export failure, 3 = requested AI
analysis unavailable or partial. JSON and capsules remain available on exit 3.
Minimal text, dependency explanation, locally validated JSON and the full LinkWatch
pipeline have now succeeded with `gemma-4-26b-a4b-it`. Intermittent provider HTTP 500
errors were also observed and preserved; the final full request recovered on its
bounded retry. See `GEMMA-DIAGNOSTICS.md` and `PHASE2-VALIDATION.md` for actual results.

## Manifest-only migration verification

Preview a plan first; this executes no target code and installs nothing:

```powershell
.venv/Scripts/gemforge.exe verify .dist/LinkWatch --dependency pydantic --target 'pydantic>=2,<3' --import-module linkwatch.config
```

After reviewing the repository, dependencies, tests and probes, an explicit
`--confirm-execution` permits running those checks under your normal account.
Virtual environments isolate packages; they are **not an OS security sandbox**.
Administrator/root execution is rejected. For untrusted code, use an external
container/VM boundary. Keep the API local and do not accept requests from others.
The one approved demonstration uses this command shape:

```powershell
# This command performs a NEW run; it is not needed to read existing evidence.
.venv/Scripts/gemforge.exe verify .dist/LinkWatch --dependency pydantic --target 'pydantic>=2,<3' --analysis .dist/linkwatch-gemma-d-1.json --import-module linkwatch.config --probe-file examples/linkwatch-pydantic-probes.json --confirm-execution --timeout 60 --install-timeout 180 --output capsules/verification.json --markdown capsules/verification.md
```

`--analysis` retains a matching previous capsule's AI provenance without making
another inference request. Without `--target`, exactly one generated same-package
target recommendation must exist in that capsule. An explicit target can narrow
the AI proposal to the major version approved for testing. AI commands and source
patches are never executed. The candidate modifies unconditional declarations in
root requirements files and PEP 621 runtime dependencies only; unsupported or
ambiguous edits are rejected. Original file hashes guard against stale plans.

Each side gets a separate temporary repository, home directory and venv. Secret
files, Git metadata, caches, links and unsupported file types are excluded. Child
environments exclude parent API keys and credentials. This does not prevent
trusted target code from accessing the host; consent must reflect that boundary.
The install profile is root `requirements.txt` plus `requirements-dev.txt`, or
PEP 621 runtime dependencies if requirements.txt is absent, plus a pytest harness
`>=8.3,<10`. Installation uses only binary wheels from PyPI; no project build hooks
or global installation run. URL/editable/options-based requirements are rejected.
Other baseline package versions are pinned in the candidate; new transitives of
the selected dependency may be installed. This tests the recorded profile, not
every optional extra or installation route. A conflicting baseline pyproject is
retained as evidence rather than passed together to pip as an impossible input.

Fixed checks cover Python syntax, the selected import, discovered pytest tests,
and optionally reviewed data-only model-construction probes. Timeout and output
capture are bounded. Missing tests, missing version metadata, collection errors,
timeouts and installation failures cannot become passes. Capsules retain the
diff, snapshot hash, versions, wheel hashes, commands, sanitized output, per-test
and per-probe outcomes, comparison, limitations and cleanup status.

Verdicts: `verified_for_selected_checks`, `regression_detected`, `inconclusive`,
`not_run`, `execution_failed`. CLI exits: 0 = preview/selected-check verification,
2 = invalid input/export, 4 = observed regression, 5 = inconclusive, 6 = execution
failure. Evidence is exported even for verification failures. A selected-check
pass never means fully safe.

`POST /verify` accepts `path`, `dependency`, `target`, optional `analysis_id`,
`confirm_execution` (false by default), `import_module`, `probes`, `timeout`, and
`install_timeout`. It returns the same cached/exportable `{id,capsule}` shape as
`/analyze`; inspect the verdict even when HTTP 201 is returned. Requests are
synchronous. It accepts no arbitrary command/source-patch fields.

See `PHASE3-VALIDATION.md` for the actual approved LinkWatch run.

## Remaining work / Phase 4

1. Review the actual Gemma recommendation for semantic correctness before applying
   anything. Schema/citation validation does not prove its compatibility claims.
2. Address observed compatibility regressions in separately reviewed candidate
   source migrations. Expand behavioral tests and container-backed execution;
   host venv execution is limited to explicitly reviewed trusted repositories.
3. Add real release/advisory metadata with provenance and explicit network policy;
   expand import resolution and semantic recommendation checks.
4. Improve frontend analysis/review/export flows after backend verification.

MIT licensed. Submission metadata is recorded in `[tool.gemforge.submission]` in
`pyproject.toml`; it is declarative metadata, not a publishing integration. The final
repository must be public and named `H26_RogueOne_GemForge`. Creation and pushing
remain disabled pending confirmation of the official starter-fork requirement.
The local folder remains `GemForge`; no organizer fork history was present initially.
