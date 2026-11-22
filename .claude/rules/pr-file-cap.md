---
description: "The 'at most 5 hand-written files per PR' cap applies to HEADLESS agents only (churn workers, unattended sessions). Headed agents, working with a person in the session, have NO file cap."
globs: "*"
---

# The PR file cap: headless agents follow it, headed agents do not

**Read this if you open pull requests in this repository. One sentence decides which rule you follow: is a person talking to you in this session?**

| You are | Examples | File cap |
|---|---|---|
| **Headed**: a person is working with you interactively | a Claude Code, Codex or Antigravity session where the owner or a maintainer is typing to you | **None.** Make the PR as many files as it takes to be clear. |
| **Headless**: nobody is in the loop | a `churn` worker, anything launched by the churn driver or promoter-bot (`claude -p`, `agy -p`), a scheduled or unattended session | **At most 5 hand-written files per PR**, as in `.claude/agents/gitgalaxy-pr-worker.md`. |

If no human has written to you in this session, you are headless. If you are unsure, ask one short question; do not assume you are exempt.

## Why the cap exists, and why it is not for headed agents

The cap is **data-driven**, from squid-bot's PR-size dashboard (the size-bucket split of 2026-11-18): the share of PRs that need a fix run climbs once a PR passes five hand-written files (about 50-58% at 6, 7 and 8+ files, against about 36% at five). An unattended worker cannot re-plan mid-flight, so keeping each PR small is what gets it merged with the least rework. A person working with an interactive agent can see the whole change, review it, and steer it, so splitting a coherent change just to hit five files makes the work worse (a test squeezed into another file, an artificial second PR). The owner confirmed on 2026-11-21: the cap is for headless agents; headed agents "can exceed the 5 file cap".

## What still applies to headed agents

No file cap does not mean no discipline. Still: one coherent change per PR (not unrelated work together), structure for the reviewer (tool, tests, fixtures and docs as separate files where that reads better), commit only your own files, run the lint, type, ratchet and audit gates in `CLAUDE.md`, open PRs as drafts, and never merge, force-push or rewrite history without the owner's say-so.

## What still applies to headless agents

The cap and its mechanics are unchanged and live in `.claude/agents/gitgalaxy-pr-worker.md`: regenerated files (goldens, baselines, ledgers, generated docs, pins) do not count; you cannot grant yourself an exception (the orchestrator grants one for an atomic rename, a pin bump, a new language profile, or a mechanical one-line change across many files, with `--file-cap-exception`); if the work needs more, ship the first self-contained slice and list the rest under **Remaining slices**.

## For agents that launch other agents

An agent you start with `Agent`, `claude -p` or `agy -p` and give no human channel is headless, even when you are headed: put the five-file cap in its brief.
