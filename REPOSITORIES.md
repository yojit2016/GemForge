# Repository ownership and workspace audit

Audit date: 15 October 2026. GemForge is the development project. LinkWatch is
an independently versioned analysis target. No final GitHub submission has been
created, configured or pushed.

| Location | Role | Git state at audit |
| --- | --- | --- |
| `.` | GemForge development | `main`; contains `e3dbd30`; no remote |
| `.dist/LinkWatch` | Direct clone of the analysis target | `main` tracking `origin/main`; clean at `f52f3930c8e7c33d934ccf614955a38e26984bd5` |

LinkWatch's origin is `https://github.com/rishrek/LinkWatch`, not a team-owned fork.
The clone was created during the assistant's earlier read-only demo workflow;
the user did not create or configure it. It is physically inside the workspace
but is not a submodule, tracked embedded repository or merged history. GemForge's
index contains no `160000` Git entries. `.dist/` is ignored in GemForge.

The uv download cache also contains an empty `.git` marker file at
`.dist/uv-cache/sdists-v9/.git`. Git reports it as an invalid gitfile; it is a
cache artifact, not another valid repository. It has been left untouched.

## Why LinkWatch appeared in Source Control

VS Code can discover nested repositories and repositories associated with open
editors independently of the parent repository's ignore rules. An ignored demo
clone can therefore appear in Source Control without becoming part of GemForge.
In addition, the initial GemForge `.git` directory was created by the sandbox
Windows account. Git run as the normal account reported dubious ownership.

The workspace now includes `.vscode/settings.json` and `GemForge.code-workspace`:

- Open `GemForge.code-workspace` or the root GemForge folder for development.
- Automatic nested/editor repository discovery is disabled; the workspace root
  remains the development repository.
- `.dist/LinkWatch` is explicitly ignored by VS Code's Git extension. Environment,
  cache and dependency folders are excluded from repository scanning.
- Publish/sync action buttons are hidden while submission provenance is pending.
  This is UI configuration, not a security mechanism preventing manual pushes.
- The project virtual environment and pytest are selected for Python development.

If the Git extension already has the clone open, reloading the VS Code window
applies the workspace settings to a fresh repository scan. Existing open-editor
or other-window state was not forcibly changed. No target files, refs or remotes
have been moved, removed or rewritten.

After verifying its origin, the exact path
`C:/Users/yojit/Documents/Hackathons/hacktober/GemForge` was added to the normal
Windows account's protected global `safe.directory` setting. Normal-account
`git status` now succeeds. No wildcard trust or ownership change was applied.
The command-scoped setting used in earlier assistant commits did not persist
that trust for VS Code. No credentials or remote configuration are needed for
local development.

## Boundaries and submission decision

GemForge scans explicit local paths. A root GemForge scan skips `.dist`, so it
does not accidentally analyze the demo target. A scan with `.dist/LinkWatch` as
its explicit root analyzes that clone and does not execute or modify its code.
Do not initialize additional repositories under source, frontend or tests.

The confirmed team is Rogue One and intended final public repository name is
`H26_RogueOne_GemForge`. Whether LinkWatch is also the mandatory starter fork is
still unresolved. Preserve this local setup until the official starter/fork
requirements are confirmed; see DEVELOPMENT.md for history-preserving integration.
