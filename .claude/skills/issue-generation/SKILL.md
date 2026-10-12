---
name: issue-generation
description: Turn a findings source (failing tests, an audit run, a lint baseline diff, a security scan, an epic that needs sub-issues, a worker's sibling gaps) into filed GitHub issues on squid-protocol/gitgalaxy, each scoped to the whole CLASS of the finding (a class sweep lists every sibling and its status), not just the reported example. Use when the user asks to "file issues for X", "break this epic into sub-issues", "open issues for these findings", or when a reviewer files the sibling gaps a worker reported.
---

Delegate this to the `issue-triage` subagent (`.claude/agents/issue-triage.md`) via the Agent
tool -- it runs on a cheaper/faster model and its own isolated context, so it doesn't inherit
this conversation's full history for what is fundamentally a read-and-write-issues task.

Before delegating:
1. Identify the actual findings source (a file, command output, or something already in this
   conversation) and make sure it's concrete enough to hand off -- don't delegate on a vague
   pointer like "the failures from earlier," paste or point to the actual content.
2. Write a self-contained prompt for the agent: what the findings source is, any relevant repo
   conventions already established in this conversation (label choices, title format, an epic
   number to link against), and whether to run in the foreground or background.
   - Foreground (`run_in_background: false`) if the user is waiting on the issue numbers to do
     something next.
   - Background otherwise.
3. Ask for the **class sweep** (issue-triage.md, "Class sweep"): every issue names its class, lists the members
   from the authoritative source with a status each, scopes its acceptance to the members that share one mechanism,
   and files the rest as linked sibling issues. Owner rule (2026-10-11): file the gap, not the example -- an issue for
   `DOCUMENT READ` alone, with the rest of the DOCUMENT family also missing, is the failure this prevents.
4. If the finding set is large and spans genuinely independent sub-topics, it's fine to split
   across multiple agent calls -- but don't split so finely that duplicate-checking (the agent
   searches existing issues before filing) gets bypassed by parallel runs racing each other.

After the agent reports back, check each issue carries its class table (send it back if not), then relay its punch list (filed / skipped-as-duplicate / flagged-as-
ambiguous) to the user. Resolve anything the agent flagged as ambiguous yourself or by asking
the user -- don't silently drop it.
