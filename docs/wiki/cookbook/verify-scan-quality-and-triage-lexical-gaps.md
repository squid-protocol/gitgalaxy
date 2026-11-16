---
description: "Verify GitGalaxy function and keyword-signal yield with ctags and Tree-sitter, triage disagreements with an LLM, and emit standard or PII-stripped Epic issues."
---
# How to Verify Scan Quality & Triage GitGalaxy Lexical Gaps

Downstream structural comparisons depend on parser completeness: **Layer 1 (Seed-and-Extend)** degrades if a slicer misses `50–75%` of functions or call edges, while **Layer 2 (32-Keyword Lattice)** breaks if `>= 25%` of keyword-family regexes fail to fire.

`sfs quality` provides a 3-step verification and reporting workflow so you know immediately whether your numbers are trustworthy—and can send clean, optional PII-stripped bug reports back to `gitgalaxy`.

---

## 1. Run Quality Verification (`sfs quality --verify`)

Install the optional verification dependencies (`tree-sitter` + `tree-sitter-language-pack`; Universal `ctags` is auto-detected if on `PATH`):

```bash
pip install 'structural-fingerprint-scanner[verify]'
sfs quality ./my-scan --source ./my-repo --verify
```

- **Internal checks (zero extra deps):** Flags languages with `>= 20 LOC` files yielding `0` functions, `loc >= 5` functions with `0` keyword-signal hits, or `0` resolved call edges.
- **External checks (`--verify`):** Compares GitGalaxy extracted function counts per language against `ctags` and `tree-sitter` (`< 50%` recall = `FAIL`, `< 75%` = `WARN`).

---

## 2. Triage Disagreements Immediately (`--triage-out`)

Raw parser-vs-slicer comparisons naturally contain false positives (C/C++ header prototypes, `< 3` LOC helpers, lambdas, macros). Generate a **disagreement cell list + LLM validation prompt** to separate real scanner bugs from parser noise:

```bash
sfs quality ./my-scan --source ./my-repo --verify --triage-out triage.md
```

The generated prompt includes GitGalaxy's slicing rules and asks an LLM to classify each cell into `TRUE_GG_MISS`, `TRUE_GG_SIGNAL_GAP`, or `FALSE_PARSER_NOISE`.

---

## 3. File a `gitgalaxy` Epic Issue (`--privacy standard | paranoid`)

Once you confirm a real lexical or slicer gap, emit a single Markdown Epic issue for `gitgalaxy`:

```bash
# Specific mode (keeps repo name, file paths, and function names for exact tracing)
sfs quality ./my-scan --source ./my-repo --verify --epic-issue --privacy standard --issue-out epic.md

# Ultra-paranoid mode (strips all repo, file-path, and function-name PII)
sfs quality ./my-scan --source ./my-repo --verify --epic-issue --privacy paranoid --issue-out epic-paranoid.md
```

In `paranoid` mode, only language names, file extensions, aggregate recall/zero-signal rates, and disagreement-kind counts are included.

---

**[⬅️ Back to Master Index](../index.md)**
