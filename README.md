# GemForge

By **Rogue One** for Hacktoberfest 2026 Track 1 — Gemma 4: Dependency Resilience.
Confirmed final repository name: `H26_RogueOne_GemForge`. Read-only Python
dependency facts and evidence-grounded Gemma 4 migration hypotheses are exported
as reusable JSON/Markdown Dependency Exit Capsules. Phase 2 data flow is implemented;
real inference remains blocked until an API key is configured. Compatibility
execution is Phase 3 work and has not been implemented.

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

The adapter checks model access with `models.get`, then calls `generate_content`.
It pins Google's Developer API endpoint, disables SDK retries, and permits three
attempts per operation with 1/2-second backoff (60-second timeout per call). Auth
and model-not-found failures are not retried. Rate limits, selected server errors
and transport timeouts get bounded retries. Model metadata, response ID, finish
reason, token counts, total call count/duration and prompt/response hashes are
recorded when available. Raw error bodies, credentials and raw unvalidated model
responses are not exported.

An accepted recommendation is **an AI hypothesis**, not proof that its suggested
version exists, API advice is correct, or a migration is compatible. Structural
and citation checks cannot establish semantic truth. Suggested commands are text
only and are never executed. New-file proposals are currently limited to prose
steps; structured change paths must already occur in the observed evidence.

CLI exit codes: 0 = completed analysis, 2 = input/export failure, 3 = requested AI
analysis unavailable or partial. JSON and capsules remain available on exit 3.
No real Gemma request has succeeded: the current environment lacks credentials.
See `PHASE2-VALIDATION.md` for the actual LinkWatch blocker and test evidence.

## Remaining work / Phase 3

1. Configure credentials and complete a genuine Gemma 4 LinkWatch request; inspect
   its actual recommendation and provider metadata. Unit fixtures are not inference evidence.
2. Implement opt-in isolated original/candidate workspaces, with explicit execution
   authorization/sandbox boundaries. Record missing tests, command output, failures,
   timeouts and inconclusive results. Do not infer runtime compatibility from AI text.
3. Add real release/advisory metadata with provenance and explicit network policy;
   expand import resolution and semantic recommendation checks.
4. Improve frontend analysis/review/export flows after backend verification.

MIT licensed. Submission metadata is recorded in `[tool.gemforge.submission]` in
`pyproject.toml`; it is declarative metadata, not a publishing integration. The final
repository must be public and named `H26_RogueOne_GemForge`. Creation and pushing
remain disabled pending confirmation of the official starter-fork requirement.
The local folder remains `GemForge`; no organizer fork history was present initially.
