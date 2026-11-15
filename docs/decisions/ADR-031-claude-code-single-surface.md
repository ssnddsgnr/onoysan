---
id: ADR-031
tier: 5
role: decision
status: active
version: 1
updated: 2026-11-15
owner: Chyntemir
---

# ADR-031: Claude Code is the single working surface; roles split by tool permissions

## Context

workflow v1 splits work between a Chat Project (architect, reviewer) and Claude Code (implementer). The Chat Project cannot read WSL paths; reaching the repository needed an export bridge to `C:` (workflow Appendix G), git hooks, a script outside the repository and `allowWrite` on the export folder in the sandbox (workflow 11.4). Knowledge had to be refreshed by hand. All of that exists only to give a second surface a mirror of git.

## Decision

1. All work on the repository happens in Claude Code. The main session is conductor and architect: it talks to the owner, writes ADRs and task specs, delegates and integrates. It does not write product code itself.
2. Roles are separated by tool permissions, defined in `.claude/agents/*.md` and changed only through a PR:
   - `coder`: Read, Edit, Write, Bash (sandboxed); input a task spec, output a branch and a PR.
   - `reviewer`: Read, Grep, Glob; input the spec and the diff, never the coder's reasoning; output a verdict against invariants and the spec.
   - `security`: Read, Grep, Glob; input the diff; output findings on INV-SEC-*, secrets, RLS, logging of PII.
3. No separate conductor or architect subagent: orchestration is only possible from the top level session, and architecture needs the owner's context, which a fresh subagent does not have.
4. The export bridge (Appendix G) and its task are dropped. The rule to refresh Project Knowledge is removed. The Chat Project remains only for strategy outside the repository (brand, store strategy, negotiations) and is not a channel for architecture or review.

## Consequences

- One source of truth with no mirrors to keep in sync; agent definitions are versioned.
- Separation becomes technical: a reviewer without Edit or Write cannot fix what it reviews.
- Weak point: all roles run on the same model family, so their errors correlate. Independent checks remain CI with PL/pgSQL tests against a live PostgreSQL, `tools/check.py` and the owner's `merge`; agent review only complements them.
- Each subagent starts with an empty context and re-reads files; roles that differ only by prompt are not added.
- Lost: mobile access through the Chat Project and long strategic context there. Repository memory lives in dev-state, ADRs and docs.
- workflow sections 3, 7, 8, 11, 12, 13 and Appendix G are rewritten in a follow-up doc task.

## Rejected alternatives

- Keep the Chat Project as architect with the export bridge: extra moving parts and a sandbox write exception for a read-only mirror.
- GitHub as the Chat Project's only view: removes the bridge but still keeps two surfaces with no shared context.
- Five or more roles (separate conductor, architect, tester): prompt-only roles cost tokens without changing permissions or input.

## Approval

`согласовано` by the owner, 2026-11-15.
