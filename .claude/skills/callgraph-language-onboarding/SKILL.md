---
name: callgraph-language-onboarding
description: Add a compiler/type-checker call-graph REFERENCE for a new language to the Level 2 call-resolution comparison (epic #3772) -- pick the reference tool and a corpus repo it can resolve, write the adapter to the callgraph_refs.py contract, register and pin it, establish the baseline, wire CI and the session hook, then triage and file what it finds. Use when the user says "add <lang> to the call-graph comparison", "measure the <lang> call graph", "onboard <lang>" for call resolution, or picks up one of #3781-#3785. NOT for fixing what a reference finds (that's callgraph-miss-sweep), not for adding a language to the engine itself (add-language), and not for Level 1 callee-name accuracy vs tree-sitter (call_graph_accuracy.py).
---

# Onboarding a language's call-graph reference

The comparison scores the engine's `fcall_data` links against a reference that resolves calls
with more information than a regex engine has: pyan3 for Python, the TypeScript compiler's type
checker for TypeScript (#3761). Everything language-specific lives in one **adapter** that emits
the contract `tests/tools/callgraph_refs.py` documents, plus one **registry entry**. The scorer,
triage (`callgraph_triage.py`), the explainer (`explain_call.py`) and the one-command check
(`callgraph_check.py`) never change per language. `docs/graph_accuracy.md` ("Adding a language,
and finding what to fix") has the overview. This file is the checklist, with the traps the
TypeScript onboarding actually hit.

Numbers from a reference are "vs <tool>", never ground truth (CLAUDE.md, "Comparative-
correctness claims"). A reference is silent where it can't resolve (`any` receivers, packages
not installed), and those links are `unconfirmed`, never `wrong`.

## 1. Pick the reference tool

- **What it must do:** resolve a call site to the **declaration** it runs, not just name it.
  Prefer the language's own compiler or type checker: TypeScript's checker, Go's
  `golang.org/x/tools` call graph, clang, Roslyn. SCIP indexers are a shared route for several
  languages (#3783). A reference edge is a call inside a definition's range that resolves to
  another definition.
- **Pin an exact version,** and check the API **at that version.** TypeScript 7 (npm's
  `latest`) is the native Go port and ships **no JavaScript compiler API**. CI's preinstalled
  global broke the first TypeScript PR for exactly this reason. The adapter must fail loudly
  with an install hint when the API is absent, and the registry's `installed` probe must return
  `None` in that case (see `_tsc_version`).
- **Libraries:** can it tell a call resolved **only outside the repo** (a built-in or library
  method)? If so, emit `external` and set `reports_external=True`. That's how #3756's
  built-in-shadowing links became provable.

## 2. Pick a corpus repo the reference can resolve

- **Not language-crucible.** Its samples are flattened into one directory per repo, so no
  relative import resolves and a compiler reference knows almost nothing (28 TypeScript files,
  no graph). The exception is a reference that doesn't need imports, as pyan3 on Python
  doesn't.
- **Prefer the language's entry in `tests/import_graph_corpus.json`.** It's already pinned,
  fetched by `import_graph_accuracy.py --fetch-only`, and has a real directory tree. The
  registry's `corpus="import_graph"` uses it.
- **Dependencies:** does the reference need them installed (Maven/Gradle, `go mod download`,
  `npm install`)? That means network access and CI time. Record it in the adapter docstring.
  Without them, calls into packages come back `unconfirmed` or `resolved_outside`, and that is
  not an engine error.

## 3. Write the adapter

Put it in `tests/tools/<lang>_callgraph.<ext>` (or in-process in `callgraph_refs.py`, as pyan's
is). It emits:

```
{"defs": [[path, name, line]], "edges": [[caller_key, callee_key, first_call_line]],
 "external": [[caller_key, callee_name]], "files": N}        # tool/version are filled in by the registry
```

**Name units the way the engine names them,** or everything lands in `caller_unmapped` /
`unmapped_*` and looks like an engine gap. First check what the engine produced for a sample
file: `galaxyscope <sample> --db-only --debug`, then grep `[WORKER-TRACE] extracted functions
for`. Then match that naming:

- **Constructors:** the engine's name for them, e.g. `constructor`, `__init__`, or the class
  name for Java/C#/C++.
- **Accessors:** by property name (`get kids()` is `kids`).
- **Arrow or function expressions bound to a name:** `const f = () =>` is `f`, anchored on the
  **declaration's** line.
- **Member assignments:** `x.f = () =>` is `f`. Missing this left 139 TypeScript callers
  unmapped; adding it brought that to 13.
- **Quoted keys:** keep their quotes (`"array-objects"`, #3760), as the engine does.
- **Anonymous callbacks:** their calls belong to the **enclosing named** function.
- **Bodyless declarations** (interface members, `abstract`, overload signatures, prototypes):
  not `defs`, because no code runs there (#3757).

Other rules:

- **Paths:** repo-relative with `/` on every platform. Compilers report forward slashes on
  Windows too; compare case-folded on win32 (the second fix to `ts_callgraph.js`).
- **Lines:** 1-based, `line` being where the declaration starts. Emit each edge's **first call
  site**, which `callgraph_triage.py` uses for its source excerpts.

## 4. Register it

Add a `Reference(...)` to `REFERENCES` in `tests/tools/callgraph_refs.py`:
- `tool` and pinned `version`;
- `corpus`;
- `build`, which returns the contract;
- `installed`, which returns the installed version or `None` when the tool or its API is
  missing;
- `adapter_files`: every file whose edit must invalidate the cache;
- `reports_external` and `install_hint`.

`python tests/tools/callgraph_refs.py --list` shows it. The cache is keyed on the corpus repo's
git tree, the tool version and the adapter files, so an adapter edit rebuilds and a second run
is a cache hit.

## 5. Test the adapter

Add a fixture test like `test_ts_callgraph_resolves_calls_with_the_type_checker`
(`tests/tools/test_call_graph_resolution_gate.py`):
- a tiny repo in `tmp_path` with one resolved call, one call into a library (for `external`),
  one method, and one construct the engine names specially;
- assert the exact `defs`, `edges` (with lines) and `external`;
- **skip** when the tool or its API is absent, so the smoke matrix on Windows and macOS stays
  green.

Run it as plain `pytest` from an unrelated directory (CLAUDE.md, "Testing conventions").

## 6. First measurement and sanity checks

```
python tests/tools/call_graph_resolution.py <lang> --samples 10
python tests/tools/callgraph_triage.py <lang> --samples 5 --json /tmp/<lang>_triage.json
```

Before believing any number:
- **A large `caller_unmapped`, `unmapped_src` or `unmapped_dst` is usually adapter naming, not
  the engine.** Explain a few with `explain_call.py`, fix the adapter, and re-run.
- **Hand-check about 10 samples each of `wrong`, `external` and `unconfirmed` against source.**
  `unconfirmed` is often the reference's own blind spot.
- **The recall buckets must add up to the gap.** Triage refuses to print otherwise.

## 7. Baseline, CI and the session hook

- `python tests/tools/call_graph_resolution.py <lang> --regenerate` writes
  `tests/call_graph_resolution_<lang>_baseline.json`. It refuses when the installed version
  isn't the pin.
- In `.github/workflows/graph-accuracy-audit.yml`, add:
  - a pinned install step;
  - a gate step: `call_graph_resolution.py <lang> --ci --samples 5 --summary "$GITHUB_STEP_SUMMARY"`;
  - the adapter and baseline files in `paths:`.
- Add the pinned install to `.claude/hooks/session-start.sh`. Keep it idempotent and quiet, and
  check the version first as the typescript block does.

## 8. Document

- `docs/graph_accuracy.md`: a row in the checks table, and a short section on what this
  reference can't see.
- `docs/function_call_graph.md`: the language's numbers in the limits list.

## 9. File what it finds, then verify

- Run triage and file each real bucket as an issue in milestone **"Compiler call-graph
  comparison"** (labels `bug`, `core-engine`). Every one needs its count and 2-3 source-checked
  samples. Before filing, look for the patterns other languages already produced; the
  `callgraph-miss-sweep` skill's table lists them. The `callgraph-triage-scout` agent can draft
  these.
- Tick the language's box on epic #3772.
- `python tests/tools/callgraph_check.py` must pass (every gate, including the other
  languages', which the shared registry touches), and it goes in the PR's Verification section.
- PR conventions: before/after or first numbers in a table, the milestone, and "vs <tool>" on
  every number.
