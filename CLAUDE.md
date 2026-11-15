# CLAUDE.md — onoysan

Law: docs/tier-0/workflow.md. Roles and delegation: docs/decisions/ADR-031-claude-code-single-surface.md. This file only lists what Claude Code needs every session.

## Session start
1. Read docs/dev-state.yaml. First line of output: stage and next tasks, one line.
2. Run `git status` and `git fetch` as separate calls; report a dirty tree or a branch behind origin before acting.
3. Run `python3 tools/check.py` once it exists (T-004); report errors before acting.

## Roles (ADR-031)
- The main session is conductor and architect: talks to the owner, writes ADRs and task specs, delegates, integrates. It does not write product code itself.
- `coder` implements one task spec on one branch and opens the PR.
- `reviewer` and `security` are read-only. Give them the spec and the diff only, never the coder's reasoning.
- Agent review complements, never replaces, CI, `tools/check.py` and the owner's `merge`.

## Sources of truth
- Git is the master copy. There are no mirrors the agent maintains.
- Rules: docs/tier-0/*. Architecture: docs/tier-1, docs/tier-2, docs/tier-3/arch-<crate>.md.
- Russian sources: archive/concept-docs-ru/ — read-only, never edited, never indexed.
- Rule changes go to "Session decisions" at the end of the answer and wait for `согласовано` / `approve`.

## Tasks
- One task = one branch `dev/T-NNN-<slug>` = one PR into main.
- Check a T-NNN or Q-NNN id is free (`python3 tools/check.py --git`) before using it.
- Small blocks; commit after each finished logical block.
- Fast loop: `cargo test -p <crate>`. Before any commit handed off for push: `cargo fmt --all --check`, `cargo clippy --workspace --all-targets --all-features -- -D warnings`, `cargo test --workspace --all-features`, `python3 tools/check.py`.
- Push, open and merge the PR yourself only when local checks and CI are green. Merge method: squash. PRs touching Tier 0, contracts or invariants wait for `merge`.
- Never force-push. Never push to main. Never use admin merge.
- `human` tasks: prepare exact instructions for the owner; never perform them.

## Commands outside the sandbox
- `git push`, `git pull`, `git fetch`, `gh pr ...`, `gh run ...` must be standalone calls: no `&&`, `;`, `|`, redirects, `cd`, `$(...)` or env-var prefixes.

## Owner words
согласовано/approve · согласовано в ADR/approve decision · отклонить/reject · доработать/revise · пауза/pause · стоп/Esc · merge.

## Pause
On `пауза` / `pause`: finish the current block (compiles, tests pass), run checks, commit (`wip:` plus what is not green if needed), update dev-state with the next step, report in at most five lines.

## Code
- `pub` only what arch-<crate> "Public contract" lists. Dependencies downward only per docs/tier-0/dna.md.
- Financial math only in PL/pgSQL; Rust calls procedures and maps results (INV-LOGIC-01).
- Errors with thiserror; no `todo!()` or `unimplemented!()` in merged code.
- Comments reference invariants and documents: `inv: INV-<area>-NN`, `ref: <doc-id>#<section>`.
- Secrets only by environment variable name. Never use the word "sana" in new identifiers.

## Documents
- English; YAML header; version + 1 on every content change; regenerate docs/INDEX.md with tools/gen-index.
- External versions, APIs and policies only from a search with source and date; otherwise "verify at adoption".
- Chat with the owner: Russian.

## Session end
Update dev-state (tasks, open_questions, waiting_on_owner, log). Summary lists merged PRs (number, title, task id; mandatory even if empty), open PRs, next tasks, pending approvals.
