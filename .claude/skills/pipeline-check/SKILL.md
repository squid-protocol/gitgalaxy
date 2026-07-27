---
name: pipeline-check
description: Sweep CI/pipeline health on squid-protocol/gitgalaxy -- open PR status, stale or misconfigured Dependabot PRs, failing workflow runs. Use when the user asks to "check the pipeline", "see what's failing", "check on the PRs", "babysit PRs", or similar status/triage requests. Not for actually merging, closing, or fixing things -- that's a follow-up step after reviewing the report.
---

Delegate this to the `pipeline-manager` subagent (`.claude/agents/pipeline-manager.md`) via the
Agent tool -- it runs on a cheaper/faster model and its own isolated context, appropriate for
what is fundamentally a read-only `gh`/`git` status sweep.

Tell it what to focus on if the user was specific (e.g. "just Dependabot PRs", "just check if
CI is green on PR #N"); otherwise ask it for a general sweep.

Run it in the background (`run_in_background: true`) unless the user is actively waiting on
the result before doing something else.

The agent will not merge, close, force-push, or post action-triggering comments (like
`@dependabot rebase`) on its own -- it reports a punch list with recommendations. When it
reports back:
1. Relay the punch list to the user.
2. For anything the agent recommends as an action, confirm with the user before taking it
   yourself (per this project's standing risk-of-action guidance) -- the agent's
   recommendation is not itself authorization to act.
