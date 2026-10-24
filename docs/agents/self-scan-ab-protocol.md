---
description: "Protocol and results ledger for the self-scan DB A/B experiment (#4479): how to run a paired agent comparison, which issues qualify, and what counts as a result."
---
# Self-scan DB A/B protocol (#4479)

Question: does the self-scan DB (`tests/tools/self_scan.py`, `self-scan-query`, `context_pack.py`) make an
agent cheaper or faster on this repo without hurting the result? One run per arm is an anecdote; a
gap under 10% needs a third run before concluding anything.

## Setup (identical for both arms except the DB)
- Same model, same base commit, each arm in its own worktree, launched together, same brief.
- **Arm A:** regenerate the DB in its worktree and use `self-scan-query` / `context_pack.py` first.
- **Arm B:** grep and Read only; the DB and `context_pack.py` are forbidden.
- Each arm opens a draft PR titled `[experiment A]` / `[experiment B]`. The better fix merges and the other
  closes. Neither arm gets `shepherd:merge`.

## Which task qualifies
Round 1 (#4472) named its file, function and fields, so the issue text had already done the navigation
the DB offers. A task qualifies only if the issue **names no file or function**: a cross-cutting "why does
X happen" or an impact question before a refactor. Check with `python tests/tools/context_pack.py <issue>
--body-file <f>`: if it resolves no paths from the body, the task qualifies.

Round 2 candidates (all open on 2026-10-24; re-check each is still open and unclaimed before launching):
- #4548 risk/security signal noise on C/C++ (spans metrics, security and recorders).
- #4991 untyped-receiver built-in method calls in other languages (spans the call-graph extractors).
- #3303 powershell functions missed in build scripts (spans aperture and the language rules).

## What is measured
Harness numbers only: total tokens, tool calls, wall-clock. Self-reported time was off by about 5x in
round 1. Record DB regeneration (~25 s) as part of arm A's cost, and the number of self-scan queries.
Quality is judged separately: tests added and passing, correctness on review, diff size, whether the
root cause is the same one.

## Verdict rule
Arm A wins only if it uses fewer tokens or less time AND its outcome is no worse. A worse outcome at lower
cost is a loss. Differences under 10% are inconclusive until a third paired run.

## Results
| Round | Task | A tokens | B tokens | A calls | B calls | A min | B min | Outcome | PRs |
|---|---|---|---|---|---|---|---|---|---|
| 1 | #4472 (named files) | 75,795 | 69,568 | 26 | 25 | 5.2 | 4.7 | same ledger result; A found the inverted `--corpus` filter; A +9% tokens | #4481 kept, #4480 closed |
| 2 | #4548 | | | | | | | | |
| 2 | #4991 | | | | | | | | |
| 2 | #3303 | | | | | | | | |

Fill the round 2 rows from the harness summaries, then state the verdict on #4479.
