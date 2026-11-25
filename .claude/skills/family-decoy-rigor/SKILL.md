---
name: family-decoy-rigor
description: Design, run, and backfill rigorous SOP-001 keyword-family decoy tests for languages and families without parser oracles (epic #8863) -- positive controls, full-line/block/inline comment decoys, identifier-substring boundary decoys, and string-comment boundary decoys through the real Prism + StructuralExtractor pipeline, plus issue filing for leaks and SVG chart refresh. Use when the user asks to "make decoy tests", "upgrade superficial decoy tests to SOP-001", "measure keyword detection quality without a parser", or "backfill decoy coverage". NOT for fixing red parser-measured cells (family-validity-fix) or refreshing parser oracle sweeps (family-validity-remeasure).
---

# Rigorous Keyword-Family Decoy Testing (SOP-001)

Because most languages (and ~30–40 families even in parser-backed languages) will not have AST parsers at the semantic resolution required, **SOP-001** (`docs/agents/decoy-testing-protocol.md`) defines the 6-gate decoy protocol that measures keyword-detection quality honestly without a parser. **Read `docs/agents/decoy-testing-protocol.md` first.**

## Workflow

1. **Audit current coverage and superficial cells:**
   ```sh
   python tests/tools/family_decoy_runner.py --audit-superficial
   ```
   Identify languages with 0 coverage, partial coverage, or legacy pre-`SOP-001-v1` superficial entries.

2. **Verify idiomatic syntax before running (`LANG_SYNTAX`):**
   For every target language in `tests/tools/family_decoy_runner.py`, confirm its real syntax for:
   - **G2** primary full-line comment (`//`, `#`, `--`, `(* *)`, `*`, `%`, `;`, `REM`, `//*`, `dnl`, `<!-- -->`)
   - **G3** block / secondary comment (`/* */`, `(* *)`, `{- -}`, `#| |#`, `--[[ ]]`, `=begin =end`, or `None`)
   - **G4** inline trailing comment (`x = 1  <comment>`, or `None` if unsupported)
   - **G6** string literal wrapper (`"..."`, `'...'`, or `None` if stringless)

   **Never** substitute a foreign comment syntax to make `Prism` pass.

3. **Expand positive-control trigger coverage (G1) where needed:**
   If a language has defined code-stream families that the scraper misses (e.g. structured/multi-token forms like HTML tags, HCL blocks, JCL cards, Erlang `mod:fn()`, Dockerfile instructions), add general pattern normalization or language-authentic trigger contexts in `tests/tools/family_decoy_runner.py` and verify G1 fires through the real `Prism` + `StructuralExtractor` pipeline.

4. **Run the 6-gate SOP-001-v1 battery:**
   ```sh
   python tests/tools/family_decoy_runner.py --lang <langs>            # dry run
   python tests/tools/family_decoy_runner.py --lang <langs> --write    # merge into baseline
   python tests/tools/family_decoy_runner.py --all-langs --write       # full sweep incl. unscored families on parser langs
   ```

5. **Triage and file issues for every leak (G2, G3, G4, G5, G6b):**
   - Do **not** hide leaks or cherry-pick weaker triggers.
   - Reproduce via `Prism.split_streams` + `StructuralExtractor.splice`, check for duplicate open issues, and file one GitHub issue per root cause citing **SOP-001** and **#8863**.

6. **Regenerate validity charts and verify:**
   ```sh
   python tests/tools/family_validity_chart.py --write
   python tests/tools/family_validity_chart.py --check
   pytest -q tests/tools/test_family_decoy_runner.py tests/tools/test_family_validity_chart.py tests/tools/test_language_sheets.py
   ```
   Run `ruff format`, `ruff_audit.py --ci`, `mypy_audit.py --ci`, `dead_key_audit.py --ci`, and `doc_refs_audit.py --ci`.

7. **Open a PR** citing `SOP-001-v1` and `#8863`, with the SOP-001 PR checklist from `docs/agents/decoy-testing-protocol.md` filled in.

## Do not
- record a decoy pass when G1 (positive control) did not fire through the real pipeline
- use a foreign comment syntax to hide a `Prism` comment-stripping bug
- silence a G5 (`ident_boundary`) leak by switching to a different keyword instead of reporting the missing boundary
- mix unrelated engine regex fixes into a decoy-measurement PR without explicit approval and golden-master attribution
- hand-edit `docs/self_scan/family_validity_*.svg` (always generate with `family_validity_chart.py --write`)

## Report back
- Protocol version (`SOP-001-v1`)
- Cells before vs after (new, backfilled from superficial, remaining untested)
- Leak summary by gate (`G2` comment, `G3` block comment, `G4` inline comment, `G5` ident boundary, `G6b` string-comment boundary) and GitHub issue links filed
- Verification results and PR link
