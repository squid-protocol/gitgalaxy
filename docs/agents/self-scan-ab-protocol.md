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
| 2 | #4548 (item 1 only) | 50,705 | 49,817 | 14 | 11 | 1.4 | 0.75 | no PR from either arm: item 1 already fixed on main (#4983, #5574); both confirmed it on fixtures. A did one more e2e SARIF scan | none |
| 2 | #4991 | 69,991 | 71,193 | 19 | 26 | 2.3 | 1.7 | same root cause (untyped-receiver fallback has lists for TS/JS/Java only); both added Kotlin, C#, Ruby lists + tests, same sibling gaps; A +353 lines, B +339 | #6388 (A), #6387 (B) |
| 2 | #3303 | 71,435 | 90,827 | 35 | 27 | 2.7 | 2.4 | both fixed the glued-return-type method rule (`\]\s+` to `\]\s*`); A also found the `script:` scope-name audit artifact (444 to 474 of 487 exact vs B 444 to 460); A 3 files +62, B 2 files +10 | #6386 (A), #6385 (B) |

Minutes and tokens are the harness numbers; A's minutes include the ~25 s DB regeneration. Golden bless,
crucible_check and pr_gates were not run in any arm (cost cap), so the fixes are unmeasured on the goldens.

**Round 2 qualification.** None of the three strictly qualified: `context_pack.py` resolved paths from each issue
body (#4548: `rust.py`, `shell.py`; #4991: `call_resolver.py` and four more; #3303: `powershell.py`). #4548 is
a multi-item issue with earlier PRs, so the slice (item 1) had already landed and the pair measured only the
"is it still broken" check. Treat the round as weaker evidence than a vague-issue round.

## Verdict on #4479 (2026-10-24, provisional)
Across the four paired runs, tokens for arm A versus B were +9%, -1.7%, -21% and +1.8% (#4472, #4991, #3303,
#4548); only #3303 clears the 10% bar, and there arm A also had the better outcome (it found the audit
artifact B missed). Arm A was slower in wall-clock in every pair (+10% to +88%), the DB regeneration being
the fixed cost. By the verdict rule that is one win and three inconclusive: **no evidence the DB saves cost
on these tasks, weak evidence it improves the outcome when the issue is vague about where the fault is.**
Keep the self-scan step optional in agent briefs. Candidates that resolve no paths from the issue body were
not available in round 2 (all three resolved paths); a round 3 on an issue that names no file or function
is the remaining open test, and n is still too small for a firm conclusion.
