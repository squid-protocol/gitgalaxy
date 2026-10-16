---
description: "Where GitGalaxy's agent knowledge lives, how a lesson gets there, and how far to trust a remembered status"
globs: "*"
---
# Agent Memory: the Repo Is the Memory

Churn workers, agy runs and scouts run in throwaway worktrees and load no personal Claude memory. Whatever a
future agent must know has to be in this repo, or it is lost when the worktree is deleted.

### 1. Where knowledge goes
| Kind | Home |
|---|---|
| How to work here: env traps, tool quirks, gates, owner policy every agent must follow | `.claude/rules/` (topic files), `.claude/agents/gitgalaxy-pr-worker.md`, a skill, or `CLAUDE.md` |
| State: what is open, merged, decided, blocked | GitHub issues and PRs (an epic's checklist, a PR body, an issue comment) |
| One issue's in-flight context | the handoff note named in the brief, and the PR body |
| Owner-only (business, legal, the box's other projects, personal preferences) | the owner's personal Claude memory, never the repo |

* **Rule:** If you would write "remember to ..." anywhere other than the first row's files, it belongs in those files.

### 2. Lessons flow: PR body -> rules
Workers record traps under `## Lessons for agents` in the PR body (`gitgalaxy-pr-worker.md`, "Lessons"). The
reviewing orchestrator copies each lesson that is durable and not already covered to
`lessons-inbox.md` in the churn handoffs dir (`$H`; on the owner's box `/srv/storage_16tb/projects/gitgalaxy/handoffs`). When that inbox holds 5 or more unpromoted lessons, it queues ONE docs item to promote
them: dedupe against `.claude/` and `CLAUDE.md`, put each in the narrowest existing file (a new
`.claude/rules/<topic>.md` only for a new topic), drop the ones the code has since made impossible, and mark the
promoted inbox entries with the PR number.

### 3. Status is a pointer, not a fact
A remembered or written-down status ("#4101 open", "PR #3187 must merge before the tag", "churn is paused") was
true when written. Before acting on one, check it: `gh api repos/squid-protocol/gitgalaxy/issues/N -q .state`, or
the PR's state and head. Write new status as a pointer ("Db2 det-port: see #4098 / #4101") rather than a copy of
the state.
