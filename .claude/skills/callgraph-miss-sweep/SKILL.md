---
name: callgraph-miss-sweep
description: The fix loop for the Level 2 call graph (epic #3772) -- triage one language's missed and wrong call links against its compiler reference, pick the biggest bucket, recognise it against the known-pattern table, verify samples against source, root-cause one with explain_call.py, file or find the issue in milestone "Compiler call-graph comparison", fix it, and prove the NET change (fixed minus newly broken) before shipping. Use when the user says "work the call-graph misses", "improve <lang> call-graph recall/precision", "fix the next call-graph bucket", "run a call-graph sweep", or picks up a bug in that milestone (e.g. #3786-#3789). NOT for adding a language's reference (callgraph-language-onboarding) and not for Level 1 callee-name accuracy vs tree-sitter.
---

# Call-graph miss sweep

The tools: `callgraph_triage.py` (where the gap is), `explain_call.py` (why one link resolved as
it did), `callgraph_check.py` (is it ready). They're described in `docs/graph_accuracy.md`.
The mechanical part (run triage, report buckets, draft issue text) can go to the
`callgraph-triage-scout` agent (Haiku). Judgement stays here: which bucket, what the source
really says, and whether a fix is net positive.

A reference is not ground truth. Nothing is called an engine bug until a sample was read in
source (CLAUDE.md, "Comparative-correctness claims").

## 1. Start green, and keep a "before"

```
python tests/tools/callgraph_check.py --langs <lang> --skip crucible,tree-sitter   # gates must pass first
python tests/tools/callgraph_triage.py <lang> --samples 5 --json /tmp/before.json
```

Keep `/tmp/before.json`: it's the denominator for the net-change rule (step 7).

## 2. Pick one bucket

Rank by edges at stake (the count column), with two adjustments:
- **Precision before recall of the same size.** A `wrong` or `external` link is a confident
  edge: it feeds function PageRank, fan-in and cross-file `fcall` edges. A missed link only
  under-counts.
- **A bucket that matches a known pattern** (step 3) is cheaper than a new one.

Broad buckets (`resolved_outside`, `not_extracted/other`, `ambiguous/receiver`) mix causes, so
**split them before choosing:** `python tests/tools/callgraph_triage.py <lang> --split <bucket>`
classifies every sample's call site by shape (spread, `new X`, qualified with its receiver,
chained `)`, bare, template) and counts shape:receiver pairs. The first `resolved_outside` on
zod (269 edges) split into:
- `z.x()` self-imports: 133 (#3789);
- `processors.x()` namespace aliases: 53 (#3788);
- spreads: 64, 40 `...f()` and 24 `...errorUtil.f()` (#3787);
- the rest (19): `util.x()`, bare calls and noise.

## 3. Known patterns (check before diagnosing from scratch)

| triage bucket / shape | root cause | where to fix | issue |
|---|---|---|---|
| `unmapped_dst` on `x;`-terminated lines | links to bodyless signatures (interface / abstract / overload) | detector `def_shape` = `signature`, resolver skips it | #3757 (fixed) |
| `wrong`: bare call lands on an object-literal method | member treated as bare-callable | `def_shape` = `member` kept out of `bucket.free` | #3758 (fixed) |
| `wrong` among same-name defs in one file | block scopes (`const Node` per callback) | TS/JS nearest-preceding binding | #3759 (fixed) |
| `external` | untyped receiver's built-in (`str.trim()`, `map.get()`) hits a repo method | resolver untyped-receiver fallback | #3756 |
| `caller_unmapped` for `async "key"()` | modifier captured as the name | detector quoted-key naming | #3760 (fixed) |
| `resolved_outside`, site `...f()` | spread recorded as qualifier `<expr>` | TS/JS qualifier capture | #3787 |
| `resolved_outside`, `ns.f()` with an alias ≠ file stem | namespace-import alias not mapped | import graph / resolver | #3788 |
| `resolved_outside`, `pkg.f()` for the repo's own package name | self-import by package name unresolved | import graph (`package.json` exports, workspaces) | #3789 |
| `explain_call` WARNING: `class` fresh vs `file` rehydrated | delta scans lose class inheritance | `state_rehydrator.py` | #3786 |
| `not_extracted/in_string` | calls inside template-literal interpolation are blanked with the string | prism / detector calls_out | none yet |
| `not_extracted/after_nested_def` | the caller's span ends where a nested function starts | detector span / loc | none yet |
| `not_extracted/same_name` | a call to a different function of the caller's own name, dropped like recursion | detector calls_out | none yet |
| `ambiguous/receiver` | `x.m()` with an untyped receiver | receiver typing (Python has `typed`, #3693) | per language |
| `wrong` / `confident_other_target`, target in the same file as the reference's | a different overload of the right method (Java: 1,653 of 1,923 wrong on gson) | overload choice by argument count; the overload-blind metrics measure it | #3835 |
| `unmapped_dst` on Java interface / abstract methods | links to bodyless Java declarations | extend #3757's `def_shape` = `signature` beyond TS/JS | #3836 |
| `wrong` / `external`: `field.m()` inside a class that also has `m` | the explicit receiver is ignored and the caller's own class wins | resolver: a qualified call must not take the class step | #3837 |

A pattern found in one language usually exists in its neighbours. Bodyless signatures apply to
Java, C#, Go interfaces and Rust traits. String interpolation applies to Kotlin, Swift and Ruby.
When a fix is language-gated, say which languages it deliberately leaves out, and why.

## 4. Verify against source

For 10-20 samples of the chosen shape, open the site (`path:line` from triage) and decide:
- **engine defect:** the reference is right;
- **reference blind spot:** e.g. `any`, uninstalled packages, pyan's getter inferences;
- **both defensible.**

Only engine defects count. If the reference is wrong, record it in the issue and move on; don't
"fix" the engine toward it.

## 5. Root-cause one representative

```
python tests/tools/explain_call.py <master.db | repo> <file>:<function>[@line] <callee>
galaxyscope <repo> --db-only --debug --output /tmp/x && grep "WORKER-TRACE] extracted functions for <file>" <log>
```

`explain_call` prints the step, the qualifiers tried, and every candidate with owner,
`def_shape` and reach (bare/receiver). It also checks its re-run against the scan's recorded
rows; a WARNING there is itself a finding (that's how #3786 surfaced). Decide the layer:
- **detector:** names, spans, `calls_out_to`, qualifiers;
- **import graph:** which files the caller sees;
- **resolver:** the ladder.

## 6. File or find the issue, then fix

- **Issue:** search milestone "Compiler call-graph comparison" first. A new issue needs the
  bucket, count, 2-3 source-verified samples, the `explain_call` output and the likely fix.
  Labels `bug`, `core-engine`.
- **Fix:** the smallest change at the layer from step 5. Tests at that layer:
  - detector: `_slice_by_braces` names/shapes, as in `test_detector.py`;
  - resolver: a minimal `_file(...)`/`_fn(...)` universe, as in `test_call_resolver.py`.
- **A new persisted per-function field** needs all of: the recorder column, a `_heal_column`
  for old DBs, and a round-trip test in `test_fcall_data.py`. The rehydrator copies every
  column; `def_shape` in #3767 is the precedent.
- **Language scoping differs:** a rule that is right for TS/JS (nearest preceding binding) is
  wrong for Python (the last redefinition wins). Gate by language and add a guard test for the
  languages you left out.

## 7. The net-change rule (the one that bites)

Score the fix on the whole corpus, **fixed and newly broken**, not only on the shape it targets.
#3759's first attempt fixed 3 links and broke 3, which is zero net. It only worked once the
root cause (members counted as bindings) was fixed instead of the symptom.

```
python tests/tools/callgraph_triage.py <lang> --samples 5 --json /tmp/after.json
```

- **Compare bucket counts and precision verdicts, before against after.** Every bucket that
  grew needs an explanation.
- **Gated metrics:** `confident_precision_pct`, `recall_pct` and `resolution_recall_pct` must
  not drop more than 0.5 points in **any** language. Resolver changes are shared.
- **Ungated metrics** (ambiguous precision, strict precision, unmapped) can legitimately move.
  Say why in the PR. #3767 moved ambiguous precision from 54.5% to 32.1% because signature
  targets became ambiguous rows, and ambiguous rows are never edges.

## 8. Verify and ship

```
python tests/tools/callgraph_check.py --regenerate      # every gate + tests + crucible + tree-sitter + lint, then baselines
```

- **Golden masters:** confident links feed the blast-radius fields. `callgraph_check` runs
  crucible in both modes when tiktoken's encoding is reachable and zero-dependency otherwise.
  If it's zero-only, CI's `crucible-audit (full-precision)` is the check for the other half.
  Say so in the PR.
- **PR body:**
  - a before/after table covering every gated metric, the bucket it targeted, and the ungated
    moves with reasons;
  - `Fixes #N`;
  - milestone "Compiler call-graph comparison".
- **After pushing,** watch CI. The Windows matrix (`full-suite-gate.yml`) runs only on labelled
  PRs. A Windows-only failure in code you didn't touch is diagnosed on the PR with a proposed
  patch, not silently fixed in scope.
