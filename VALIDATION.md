# Phase 1 validation — 15 October 2026

Environment: Windows, CPython 3.12.14, Node 24.13.0, npm 11.6.2.
Python runtime/download caches, target checkout and generated artifacts are ignored.
No existing project files or starter Git history were present; the original empty
`.dist` directory was retained and a new local Git repository was initialized.
No remote was configured and no repository/folder rename was performed.

## Final checks

| Check | Actual result |
| --- | --- |
| `python -m pytest -q --basetemp=.dist/pytest-run-2` | 34 passed, 1 dependency deprecation warning |
| `ruff check src tests` | Passed |
| `ruff format --check src tests` | 12 files already formatted |
| `npm.cmd run build` in frontend | TypeScript check and Vite production build passed |
| `uv build --out-dir .dist/package` | Source distribution and wheel built successfully |
| Installed `gemforge --help` | Passed; exposes `scan` command |
| Google GenAI SDK import/configuration | Imports, context-manager support and timeout configuration checked; no API request |
| LinkWatch CLI scan and JSON/Markdown export | Completed; results below |

Tests cover normalized duplicate declarations, source locations, conflicting pins,
inequality bounds, compatible releases, wildcard pins, exclusions, epochs,
prereleases/postreleases, local versions, arbitrary equality, marker/group uncertainty,
direct references, pip syntax limitations, malformed manifests/Python, read limits,
import aliases, rebinding, explicit import mappings, CLI output/export refusal,
API validation, configuration secrecy and absence of repository modifications.

The first pytest invocation could not use the system temporary directory inside
the filesystem sandbox. Using an explicit workspace `--basetemp` resolved that
environment restriction. The first runnable suite found the Typer single-command
collapse issue; a root callback fixed the documented `gemforge scan` syntax.
Lint findings were corrected before the passing final checks. The frontend build
initially hit an esbuild ancestor-directory access restriction; the same build
passed with an approved sandbox escalation. No browser interaction/visual QA was
performed. Starlette warns that its httpx test-client transport is deprecated;
tests still pass. This warning was not suppressed.

## Read-only LinkWatch demo

Target: https://github.com/rishrek/LinkWatch

Checkout: `.dist/LinkWatch`, commit
`f52f3930c8e7c33d934ccf614955a38e26984bd5`.
The target working tree remained clean. Its tests/build/install scripts were not run.

```powershell
.venv/Scripts/gemforge.exe scan .dist/LinkWatch --import-map dateutil=python-dateutil --json --output .dist/linkwatch-phase1.json --markdown .dist/linkwatch-phase1.md
```

- 26 dependency declarations, retaining duplicates across three manifests.
- 14 distinct normalized packages.
- 22 static import/reference locations, including the explicit dateutil mapping.
- One proven manifest conflict: `pydantic==1.10.13` at `requirements.txt:5`
  versus `pydantic>=2` at `pyproject.toml:17`.
- Pydantic recommendation is explicitly `not_requested` with a Phase 2 limitation.
- Original, candidate and overall verification are all `not_run`.

Generated demo capsules are local artifacts under `.dist`, not source-controlled
snapshots. No vulnerability, abandonment, migration success or runtime compatibility
claim is implied by this scan.

## Still unverified / Phase 2

No real Gemma request has succeeded or been attempted. Model availability, Gemma 4
support, structured recommendations, external risk metadata, candidate patches and
original-vs-candidate execution remain Phase 2 work. The adapter never silently
substitutes a Gemini model. See README.md for scanner limits and the execution
confirmation/sandbox boundary required before any target code may run.
