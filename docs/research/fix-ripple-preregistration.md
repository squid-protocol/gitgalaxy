# Fix history vs call graph: pre-registration (#8958)

Committed before any code that computes these. It records the hypotheses and decision rules of the one-off study (30 public
repositories in C, Go and Java) that `tests/tools/fix_ripple_study.py` reruns. Research only: it changes no engine output and no
score, and its results are associations, never a risk claim.

## Definitions

* **Graph:** `function_data` plus `fcall_data` rows that are resolved (`dst_func_id` set, step `scoped` or `unique`), self-calls
  dropped, duplicate caller-callee pairs counted once. fan-in = distinct callers, fan-out = distinct callees.
* **Orchestrator:** fan-in < 8 and fan-out >= 8. **Consumer-ish:** fan-in / (fan-in + fan-out) < 0.2. **Producer-ish:** > 0.8.
  Functions with no resolved edge are in neither group.
* **Fix definitions** (commit subject keyword match, case-insensitive, merges skipped, since 2021-01-01):
  `orig` fix/bug/cve/crash/overflow/leak/uaf/heap/stack; `B` fix/bug/regression with memory words removed; `D` any commit (churn control).
  Definition B is the primary one.
* **Touch:** a commit whose diff hunk header names the function (git's per-language diff driver), counted once per commit.
* **Size model:** Poisson regression of touches on log(1+LOC) and log(1+complexity), fitted per repository and definition.
  **Lift** = observed touches / model-predicted touches in a group. Pooled CI: within-repository bootstrap of functions.
* **Null for distance (H5):** co-changed fix pairs within 2 call hops, against a directory-matched random null.

## Hypotheses and decision rules

| id | hypothesis | pass rule |
|---|---|---|
| H1 | orchestrators have lift > 1 under def B | pooled CI excludes 1 AND, per repository, a majority of repositories have a CI excluding 1. Both clauses are reported; the verdict reads each |
| H2 | lifecycle-named (free/close/destroy/...) with fan-in >= 8 have lift > 1 under def B | pooled CI excludes 1 in a majority of repositories. Withdrawn after wave 1 (a churn effect); not rerun by default |
| H3 | fan-out partial Spearman (controls LOC, complexity) with touches > 0 | positive in a majority of repositories |
| H4 | consumer-ish lift > producer-ish lift under def B | consumer CI above 1 and producer CI below 1, or non-overlapping |
| H5 | co-changed pairs within 2 hops >= 1.5x a directory-matched null | in a majority of repositories (not implemented in slice 1) |

## Results recorded before the tool existed (the regression fixture)

Fresh C set (libuv, libgit2, git, haproxy), def B: H1 pooled 1.23x (1.14-1.32), per repo 2 of 4 with CI excluding 1, so **pooled pass,
per-repo majority clause fail**; H2 fail; H3 pass on sign (4 of 4); H4 pass (consumer 1.14x vs producer 0.73x). Wave 2 (22 repositories, C/Go/Java):
H1 pass in each language, H3 pass in each, H4 fail in Go, H5 fail in Go and Java. The any-commit control gives similar lifts, so these are
change-proneness effects. The tool must fail loudly if a verdict changes after an engine change.

## Limits

Keyword fix detection, HEAD-only graph, hunk-header attribution (renamed functions are dropped), test/doc/vendor removal is a choice
(an explicit flag, default off, recorded next to every number), effects of 10-25% are small.
