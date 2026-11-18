---
description: "Step-by-step LLM workflow for validating ctags/tree-sitter disagreement cells, filtering parser noise, and generating standard or PII-stripped GitGalaxy Epic issues."
---
# LLM Agent Playbook: Triaging Parser Disagreements & Filing Privacy-Safe Epic Issues

When `sfs quality --verify` flags a language as `WARN` or `FAIL`, most raw discrepancies between GitGalaxy and `ctags` / `tree-sitter` are **expected false positives** (header prototypes, `< 3` LOC helpers, lambdas, or macros). This playbook defines the exact LLM triage loop to separate true scanner gaps from noise before filing an issue.

---

## 1. Generate the Disagreement Cell List & Triage Prompt

```bash
sfs quality ./my-scan --source ./my-repo --verify --triage-out triage.md --json
```

`triage.md` contains:
- **Slicing System Instructions** (GitGalaxy intentionally skips `< 3` LOC functions, top-level scopes, and bodyless declarations),
- **A JSON array of `DisagreementCell` items** (`cell_id`, `language`, `kind`, `source_tool`, `file_path`, `func_name`, `line_start`, `line_end`, `loc`, `note`).

---

## 2. Classify Each Cell (Worked Examples)

Inspect the referenced `file_path` and `line_start..line_end` in the local repository and assign one of three verdicts:

| Cell Example | Verdict | Why |
|---|---|---|
| `missed_by_gitgalaxy` via `ctags` on `include/r_defs.h:42` (`void R_Init(void);`, `loc=1`) | `FALSE_PARSER_NOISE` | C header forward declaration with no function body. |
| `missed_by_gitgalaxy` via `tree-sitter` on `src/util.rs:18-19` (`fn id(x: i32) -> i32 { x }`, `loc=2`) | `FALSE_PARSER_NOISE` | Below GitGalaxy's `min_loc=3` threshold. |
| `missed_by_gitgalaxy` via `tree-sitter` on `src/engine.zig:104-142` (`pub fn step(...) !void`, `loc=39`) | `TRUE_GG_MISS` | Real, multi-line function with a body missed by GitGalaxy's slicer regex. |
| `zero_signal_function` via `internal` on `src/solver.cob:88` (`SOLVE-GRID`, `loc=28`) | `TRUE_GG_SIGNAL_GAP` | Non-trivial function where none of the 32 keyword-family regexes matched. |

### Output Contract for the LLM
Return a JSON array of verdicts and a one-line recommendation:

```json
[
  {"cell_id": "cell_0001", "verdict": "FALSE_PARSER_NOISE", "symptom": "header prototype"},
  {"cell_id": "cell_0002", "verdict": "TRUE_GG_MISS", "symptom": "pub fn with error union return"}
]
```

- **If all/most cells are `FALSE_PARSER_NOISE`:** Inform the user that downstream `sfs` comparison metrics are safe to use.
- **If `TRUE_GG_MISS` or `TRUE_GG_SIGNAL_GAP` are confirmed:** Proceed to Step 3.

---

## 3. Generate the Outbound `gitgalaxy` Epic Issue

Choose the privacy mode appropriate for the repository:

```bash
# Internal / open-source repos: keep repo name, file paths, and function names for exact tracing
sfs quality ./my-scan --source ./my-repo --verify --epic-issue --privacy standard --issue-out epic.md

# Proprietary / enterprise repos: strip all repo, file-path, and function-name PII
sfs quality ./my-scan --source ./my-repo --verify --epic-issue --privacy paranoid --issue-out epic-paranoid.md
```

- **`standard`:** Outputs exact file paths, function names, and recall/zero-signal tables so maintainers can reproduce and confirm the fix directly.
- **`paranoid`:** Replaces the repo name with `[REDACTED_REPO]` and strips all file paths and function names, retaining only language, file extensions, aggregate recall/zero-signal rates, and disagreement-kind counts.

---

**[⬅️ Back to Master Index](../index.md)**
