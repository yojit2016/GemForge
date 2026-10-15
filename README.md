# GemForge

By **Rogue One** for Hacktoberfest 2026 Track 1 — Gemma 4: Dependency Resilience.
Confirmed final repository name: `H26_RogueOne_GemForge`. Phase 1 delivers
read-only Python repository facts and reusable JSON/Markdown Dependency Exit
Capsules. Gemma 4 recommendations and migration verification are Phase 2 work.

Open `GemForge.code-workspace` for development. GemForge is the root repository;
the ignored `.dist/LinkWatch` clone is only a scan target. Workspace settings keep
that clone out of automatic Source Control discovery. See `REPOSITORIES.md` for
the repository audit, Git ownership fix and unresolved starter-fork requirement.

## Setup

Requires Python 3.12+ and Node.js 22.12+ (Node 24 is also suitable).
Windows PowerShell, from this directory:

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -e '.[dev]'
.venv/Scripts/gemforge.exe scan C:/path/to/repository --json
```

If using uv: `uv venv --python 3.12` then
`uv pip install --python .venv/Scripts/python.exe -e '.[dev]'`.
On Linux/macOS use `python3.12`, `.venv/bin/python`, and `.venv/bin/gemforge`.
Install development dependencies only for GemForge; scans do not install target dependencies.

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
remote hosting/authentication is outside Phase 1.

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
  initially `not_requested` with a Phase 2 limitation. Verification is `not_run`.
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
- No PyPI, advisory or maintenance metadata fetch exists in Phase 1. An empty risk list
  is not a safety verdict. Scans need no network once GemForge is installed.

## Gemma adapter preparation

Install `.[ai]` for the Google GenAI SDK. Set `GOOGLE_API_KEY` and
`GEMFORGE_MODEL_ID` in your shell (see `.env.example`; files are not auto-loaded).
There is no default model, proprietary Gemini fallback, or mock recommendation.
`GemmaAdapter(GemmaConfig.from_environment()).generate_text(prompt)` makes an explicit
real request; errors propagate. It is deliberately not invoked during scanning.
Do not send private repository contents without authorization.

No real Gemma API request has been verified. Model availability and Gemma 4 support
must be confirmed with the chosen service/account in Phase 2; the adapter does not
assert a model exists or that a response is factually correct.

## Phase 2

1. Fetch/cache real release and advisory metadata with provenance, timestamps and
   explicit network policy; enumerate all detected risks dynamically.
2. Confirm a supported Gemma 4 model with a real request; validate structured migration
   recommendations against capsule facts, with explicit limitations for every risk.
3. Improve distribution/import resolution and scope-aware usage analysis.
4. Add opt-in isolated candidate workspaces and an explicit confirmation/sandbox
   boundary before executing original/candidate tests. Record commands, outputs,
   missing tests, execution failures and inconclusive results truthfully.
5. Enrich capsule evidence and frontend review/export flows. No automatic target edits.

MIT licensed. Submission metadata is recorded in `[tool.gemforge.submission]` in
`pyproject.toml`; it is declarative metadata, not a publishing integration. The final
repository must be public and named `H26_RogueOne_GemForge`. Creation and pushing
remain disabled pending confirmation of the official starter-fork requirement.
The local folder remains `GemForge`; no organizer fork history was present initially.
