# Development workflow and submission handoff

## Current provenance

This workspace began as an empty `GemForge` directory containing only an empty
`.dist` directory. There was no starter checkout, Git history or remote. Phase 1
was implemented locally and a new Git repository was initialized on `main`.
The organizer's LinkWatch analysis target was cloned separately under ignored
`.dist/LinkWatch`; it has not been identified as the official submission starter.

The following local commits already existed when the continuous-commit workflow
was requested. Their original messages, hashes, authorship and timestamps are
preserved; they will not be amended merely to change message style.

| Commit | Completed work | Recorded local commit time (UTC+05:30) |
| --- | --- | --- |
| `1eef749` | Read-only engine, typed capsules, CLI/API and setup | 15 October 2026, 12:09:48 |
| `c51599a` | Minimal React/TypeScript frontend and UI foundations | 15 October 2026, 12:10:31 |
| `10a82ee` | Regression tests and actual validation record | 15 October 2026, 12:11:41 |

These times are Git's recorded commit times, not proof of hackathon eligibility
or the precise time every line was written. No dates or authors were fabricated.
See `VALIDATION.md` for the checks actually performed and Phase 1 limitations.

## Confirmed event details and pending submission requirements

The user confirmed these details from the Hacktoberfest Hack Day Mumbai × ISTE
KJSSE handbook: Track 1 — Gemma 4: Dependency Resilience; event date 15 October
2026; permitted development window 10:30 AM–4:30 PM IST (05:00–11:00 UTC); final
team name **Rogue One** and final repository name `H26_RogueOne_GemForge`.
The three commit times
above fall within the confirmed window. Continue genuine local implementation
and commits during that window; do not backdate later work.

LinkWatch is confirmed as the analysis target, but the handbook's mandatory
starter-fork relationship remains unclear. The official starter/approved fork URL
is still pending. A public final submission and
disclosure of pre-existing work are required. No handbook link/content was
independently reviewed; this record attributes those details to the user.

Confirmed submission metadata is stored in `[tool.gemforge.submission]` in
`pyproject.toml`. Publication is explicitly disabled there; this metadata does not
create a repository, configure a remote or authorize a push.

Until those details are confirmed:

- Keep this as a local development repository; do not create or push a final submission.
- Do not rename the folder/repository or configure an assumed submission remote.
- Do not claim this independent local repository satisfies fork provenance.
- Preserve actual development history and disclose any work that predates the
  confirmed allowed period. Commit timestamps alone do not prove all eligibility rules.

## Incremental local workflow

For each coherent feature, fix, test improvement or documentation milestone:

1. Inspect `git status --short --branch` and the working diff before editing.
2. Implement only that milestone; preserve unrelated work. Check with the user
   before replacing, deleting or moving existing project files.
3. Add/update meaningful tests when needed and run applicable checks. Never label
   missing tests, execution failures or incomplete checks as passing.
4. Stage explicit paths relevant to the milestone, then inspect `git diff --cached`
   and `git diff --cached --check`. Check status again for unrelated staged changes.
5. Commit with an accurate conventional message such as `feat(scanner): ...`,
   `fix(cli): ...`, `test: ...`, or `docs: ...`. Normal local commits are authorized;
   create no empty commits and do not split finished work artificially for count.
6. Preserve completed commits. Do not rewrite timestamps/authors, repeatedly
   amend/squash, rebase published history, or force-push. Push only to the approved
   remote after the starter-fork requirements are confirmed.

Never stage `.env`, credentials, API keys, environments, caches, dependency installs
or generated builds/capsules. `.gitignore` excludes these. Review staged content
even when ignore rules exist. A coherent documentation-only change does not need
another run of unchanged application tests.

## Eventual integration with the approved starter fork

This is a preparation procedure, not an action already performed:

1. Confirm the official starter URL and GitHub fork relationship. Use the confirmed
   team name Rogue One, repository name `H26_RogueOne_GemForge`, and event window
   above. Confirm how work
   created before integration must be disclosed.
2. Create or select the approved public GitHub fork only after confirmation. Clone
   it into a separate directory; inspect its history, file layout, license,
   contribution instructions and required submission files before making changes.
3. Keep this workspace intact. In the separate fork checkout, fetch this local
   repository's `main` as an integration branch. Review overlapping file paths and
   decide their handling with the user before replacing any starter content.
4. Integrate through a reviewed merge that retains the starter ancestry and these
   original local commits. Because the histories are independent, an explicit
   unrelated-history merge may be needed. Do not replace the starter's `.git`,
   copy this Git directory over it, discard organizer files, or resolve conflicts
   blindly in favor of either side. Verify that the handbook permits this approach.
5. Run the applicable tests/build in the integrated checkout. Inspect the staged
   merge diff, commit the actual integration, and verify both histories remain
   reachable. Document the real provenance and any pre-existing work.
6. Verify the approved remote and public visibility before an ordinary push.
   Never force-push. Keep submission publication separate from local implementation.

## Current implementation boundary

Phase 1 static scanning and Phase 2 evidence-grounded AI data flow, SDK adapter,
structured migration hypotheses, CLI/API integration and capsule exports are
implemented. Hosted Google Gemma 4 inference on relevant public LinkWatch excerpts
is organizer-authorized, per the user's confirmation. Real model access, minimal
text/JSON probes and full LinkWatch generation have succeeded with configured
credentials. Intermittent HTTP 500 errors were observed; the full pipeline
recovered on its bounded retry. The generated recommendation is an unverified
migration hypothesis; its correctness must be evaluated against observed checks.
Phase 3 implements consent-gated, manifest-only baseline/candidate verification
through the shared engine, CLI and local API, with bounded execution, cleanup and
JSON/Markdown evidence. External registry metadata, scope-aware import improvements,
source migrations, container-backed execution and frontend review flows remain
future work. See PHASE2-VALIDATION.md, GEMMA-DIAGNOSTICS.md and PHASE3-VALIDATION.md
for actual results and the approved demonstration's limits.

The organizer's explicit hosted/cloud permission was reaffirmed on 15 October
2026. Retain the working Google GenAI SDK adapter and `gemma-4-26b-a4b-it`,
including bounded retries, structured validation and sanitized diagnostics.
Ollama, llama.cpp and other local runtimes are not required for this track.
Hosted inference permission does not expand target-code execution consent: the
single approved Phase 3 comparison is complete, and its saved evidence can be
read/exported without repeating the run. Changed checks or source migrations
require an execution scope appropriate to those changes.
