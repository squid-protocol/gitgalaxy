# SOP-001: Rigorous Keyword-Family Decoy Testing Protocol (#8863)

**Protocol ID:** `SOP-001`  
**Current Version:** `SOP-001-v1`  
**Skill:** `.claude/skills/family-decoy-rigor/SKILL.md`  
**Next Tier (Spec-Grade Batch Hardening):** `SOP-002` (`docs/agents/decoy-spec-protocol.md`, `.claude/skills/family-decoy-spec/SKILL.md`)  
**Runner:** `tests/tools/family_decoy_runner.py`  
**Baseline:** `tests/family_validity_baseline.json`  
**Charts:** `docs/self_scan/family_validity_chart.svg`, `docs/self_scan/family_validity_matrix.svg`

---

## 1. Why SOP-001 Exists

GitGalaxy scores per-function keyword families (`branch`, `io`, `concurrency`, `cryptography`, etc.) across 73 code languages. Real AST/tree-sitter parser oracles only exist for 17 languages and only cover 9–24 of their ~55 defined families — we will not have parsers at the semantic resolution needed for the remaining 56 languages (or the remaining ~30–40 families per parser-backed language).

Superficial decoy tests (planting one keyword in a single-line comment) create false confidence:
- A language can pass `//` line comments while leaking `(* ... *)` or `/* ... */` block comments (e.g. F#).
- A language can pass full-line `^\s*#` comments while leaking inline trailing comments (`x = 1 # kw`).
- A regex can pass every comment decoy while matching inside ordinary identifiers (`my_if_val`, `file_open_count`) because it lacks `\b` or lookaround boundaries.
- A comment decoy that uses a foreign comment syntax (e.g. `//` in OCaml) hides real `Prism` bugs (`#9303`, `#9304`).

**SOP-001** establishes a single, versioned, 6-gate decoy battery that every new decoy test MUST pass and that every previously superficially-covered cell MUST be backfilled against.

---

## 2. Scope and Non-Decoy Families

SOP-001 applies to every `(language, family)` cell in `family_validity_chart.engine_grid()` where:
1. The language defines a compiled regex rule for `family`, AND
2. `family` is a **code-stream equation family** (not in `NON_DECOY_FAMILIES`).

**Excluded (`NON_DECOY_FAMILIES`)** — never run comment-stripping decoys on these:
- **Comment-stream rules** (intentionally read comments): `doc`, `ownership`, `dead_code`, `planned_debt`, `fragile_debt`, `spec_exposure`.
- **Structural / unit-extraction rules** (not `equations` counters): `calls_out`, `args`, `func_start`, `class_start`, `structural_boundaries`.
- **Security string / prose rules**: `hardcoded_secrets`, `lit_code_blocks`, `lit_diagrams`, `lit_headers`, `lit_links`.

All other defined families — across **all 56 parserless languages** AND the **unscored non-oracle families of the 17 parser-backed languages** — are in scope for SOP-001.

---

## 3. The 6-Gate Decoy Battery (`SOP-001-v1`)

Every gate MUST run through the **real GitGalaxy pipeline** (`Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams()` followed by `StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice()`), never raw `rule.search()` alone.

| Gate | Name | Input Shape | Expected | Baseline Field |
|---|---|---|---|---|
| **G1** | **Positive Control** | Authentic bare code snippet `<kw>` in the language | `equations[family] >= 1` | `keyword` (required; if G1 fails, emit no entry) |
| **G2** | **Primary Comment** | Language's real idiomatic full-line comment (`// <kw>`, `# <kw>`, `-- <kw>`, `(* <kw> *)`, `* <kw>`, etc.) | `0` hits | `comment: "pass" \| "leak"` |
| **G3** | **Block / Secondary Comment** | Language's block or secondary comment syntax (`/* \n <kw> \n */`, `(* \n <kw> \n *)`, `{- \n <kw> \n -}`, `#| \n <kw> \n |#`, `--[[ \n <kw> \n ]]`, `=begin \n <kw> \n =end`), or `null` if none | `0` hits | `block_comment: "pass" \| "leak" \| null` |
| **G4** | **Inline Trailing Comment** | Executable statement + trailing comment on the same line (`x = 1  // <kw>`, `x = 1  # <kw>`, etc.), or `null` if language has no trailing comments | `0` hits | `inline_comment: "pass" \| "leak" \| null` |
| **G5** | **Identifier-Substring Boundary** | Alphabetic bare keyword embedded inside an identifier (`my_<kw>_val`), or `null` for non-identifier / multi-token / operator triggers | `0` hits | `ident_boundary: "pass" \| "leak" \| null` |
| **G6a** | **String Literal** | `<kw>` inside the language's real string literal syntax, or `null` if stringless | Measured honestly (#2535) | `string_counts: true \| false \| null` |
| **G6b** | **String-to-Comment Boundary** | String containing comment-like text or escaped quote followed by a real comment (`"http://x" // <kw>`), or `null` if stringless or no trailing comments | `0` hits | `string_comment_boundary: "pass" \| "leak" \| null` |

Every entry written under this protocol MUST carry:
```json
{
  "comment": "pass",
  "block_comment": "pass",
  "inline_comment": "pass",
  "ident_boundary": "pass",
  "string_counts": true,
  "string_comment_boundary": "pass",
  "keyword": "if",
  "corpus": "decoy-suite",
  "protocol": "SOP-001-v1"
}
```

### Non-Negotiable Integrity Rules
1. **Never swap to a foreign comment syntax to make a gate pass.** If a language uses `(* ... *)` (OCaml) or column-1 `*` (Easytrieve), test that exact syntax. If `Prism` leaks it, record `"leak"` honestly and file a GitHub issue.
2. **Never claim a pass without G1.** If the bare trigger does not fire `equations[family] >= 1` through the full `Prism` + `StructuralExtractor` pipeline, the cell stays untested.
3. **Never silence a G5 (`ident_boundary`) leak by picking a different keyword.** If a rule matches `my_if_val` because it forgot `\b`, that is a real false-positive bug in the rule — record it and file an issue (or fix the rule in a dedicated rule-fix PR).
4. **Separate measurement PRs from engine-fix PRs** (unless the user explicitly asks to combine them): decoy measurement + baseline updates touch `tests/tools/`, `tests/family_validity_baseline.json`, and `docs/self_scan/family_validity_*.svg`; engine/rule fixes go through their own PR with golden-master attribution (`family-validity-fix`).

---

## 4. Tracking and Backfilling Superficially-Covered Cells

Any decoy entry in `tests/family_validity_baseline.json` that lacks `"protocol": "SOP-001-v1"` (for example, legacy `corpus: "keyword-rosetta"` entries or v0 single-line-only entries) is classified as **superficial**.

To audit which languages and cells still need SOP-001 backfill:
```sh
python tests/tools/family_decoy_runner.py --audit-superficial
```

Backfill priority order:
1. **Parserless languages with 0 cells or partial coverage** (highest blind-spot reduction).
2. **Legacy superficial entries** (`protocol` missing or `< SOP-001-v1`) on parserless languages.
3. **Unscored non-oracle families on the 17 parser-backed languages** (`--all-langs`).

---

## 5. Triage & Issue-Filing Protocol for Leaks

When any gate (`G2`, `G3`, `G4`, `G5`, or `G6b`) reports `"leak"`:
1. Reproduce directly in Python using `Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams()` and `StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice()`.
2. Classify the root cause:
   - **G2 / G3 / G4 leak** → `Prism` comment-stripping gap (`lexical_family` or comment regex in `gitgalaxy/standards/language_standards/languages/<lang>.py` / `gitgalaxy/core/prism.py`).
   - **G5 leak** → Missing word boundary (`\b` or lookaround) in the language's family regex.
   - **G6b leak** → Broken string-literal shielding in `Prism` (`SHIELD_PATTERN` / quote escaping).
3. Check for existing open issues (`gh issue list --state open --search "<lang> <cause>"`).
4. File one crisp issue per root cause citing `SOP-001` and `#8863` (examples: `#9303`, `#9304`), with the minimal repro snippet and affected family list.

---

## 6. PR Checklist (Paste into Every SOP-001 Decoy PR)

- [ ] Protocol referenced: `SOP-001-v1` (`docs/agents/decoy-testing-protocol.md`)
- [ ] All tested cells ran through `Prism.split_streams` + `StructuralExtractor.splice` (positive control G1 verified)
- [ ] Idiomatic language syntax used for G2/G3/G4/G6 (no foreign comment workarounds)
- [ ] Leaks reported honestly in `tests/family_validity_baseline.json`; GitHub issues filed for every new root-cause leak
- [ ] `python tests/tools/family_validity_chart.py --write` and `--check` pass
- [ ] `pytest tests/tools/test_family_decoy_runner.py tests/tools/test_family_validity_chart.py tests/tools/test_language_sheets.py` pass
- [ ] `ruff_audit.py --ci`, `mypy_audit.py --ci`, `dead_key_audit.py --ci`, `doc_refs_audit.py --ci` pass with 0 new findings
