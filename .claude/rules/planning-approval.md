---
name: require-plan-approval
description: Enforces a strategy-first workflow. The agent must document the root cause, fix, and regression test plan in an artifact and receive explicit user approval BEFORE making any code edits or running CI scripts.
---

# Mandatory Strategy-First Workflow

When given a new issue or task, you **MUST NOT** begin modifying source code, updating test fixtures, or running heavy CI scripts until you have presented a strategy and received explicit user approval.

## 1. Investigation Phase
* You may read files, grep the codebase, and read documentation to understand the problem.
* You may run *read-only* local tests or parsers to reproduce the issue (keep these sandboxed to avoid permission spam).

## 2. Planning Phase
* Once you understand the root cause, create a `fix_strategy.md` artifact.
* The artifact MUST include:
  1. **Root Cause**: Why is it failing?
  2. **Proposed Fix**: The exact file(s) and lines you intend to change, and the logic of the change.
  3. **Regression Strategy**: How you will prove the fix works (e.g., which specific test scripts you will run, and whether they require sandbox bypasses).
* Set `RequestFeedback: true` on the artifact so the user can review it.

## 3. Execution Phase
* **STOP** and wait for the user to approve the strategy.
* Only *after* explicit approval may you proceed to checkout a branch, edit files, bypass sandboxes for CI runs, and create pull requests.
* **CRITICAL**: Once the user approves the plan (e.g., "approve and proceed"), you MUST execute the entire approved plan **autonomously**. Do not pause to ask for permission for individual steps (like modifying code, running tests, or committing). Only pause and ask the user if you encounter an unexpected failure or if the plan requires a major deviation.
