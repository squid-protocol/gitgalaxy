# Self-Scan: Tree-sitter Accuracy Data

This folder holds two unrelated things that happen to share a name and a path. This README is
about the one that's committed to the repo: GitGalaxy's structural-extraction accuracy measured
against tree-sitter. The other is `gitgalaxy_master.db` — a gitignored, locally-regenerated
SQLite snapshot of *this repo's own* code (function/class counts, complexity, blast radius),
produced by `tests/tools/self_scan.py` for LLM coding sessions to query cheaply (see
`.claude/skills/self-scan-query/SKILL.md`). If you ran that script and see a `.db` file next to
these files, that's why — it has nothing to do with tree-sitter or language accuracy.

Both files below are generated, not hand-written. See
[`tests/tools/tree_sitter_accuracy_audit.py`](../../tests/tools/tree_sitter_accuracy_audit.py)'s
own module docstring for the authoritative methodology, corpus setup, and every known
per-language measurement caveat — this README is the short version; that docstring is the one
to trust if the two ever disagree.

## What's measured

[`tree-sitter-language-pack`](https://pypi.org/project/tree-sitter-language-pack/) parses every
file in the pinned [`language-crucible`](https://github.com/squid-protocol/language-crucible)
corpus (`v1.0` — ~120 real, disconnected subdirectories of production code: Godot's C++,
Roslyn's C#, curl, tokio, and more) into a real AST, per baselined language. That AST becomes the
reconciled ground truth for that language: real function/class names, their positions, and their
real parameter counts. GitGalaxy's own regex-based extraction is then diffed against it —
**recall** (did it find the real ones), **precision** (did it also report ones that aren't
there), and **args exact-match** (of the functions it found, did it also get the parameter count
right).

Tree-sitter's own name-matching is scored against that same reconciled ground truth too (the
`ts_*` CSV columns; the bottom bar in each chart panel). That's not tree-sitter under audit —
it's there because the ground truth isn't simply "whatever tree-sitter's grammar happened to
walk": occurrence pairing across same-named functions, Flow-typed JS the plain JS grammar can't
parse, Cython scope loss, and Rust functions hidden inside macro bodies all mean tree-sitter's
raw reading and the reconciled ground truth built from it can diverge. The audit script's SCOPE
& LIMITATIONS section has the specific, confirmed cases (file and function names included) —
read that before citing either side's number as more precise than the methodology supports.

31 languages currently have a committed baseline
(`tests/tree_sitter_accuracy_baseline_<lang>.json`) and appear scored here. 14 more that
GitGalaxy extracts structural signatures from but tree-sitter has no grammar for at all (COBOL,
JCL, assembly, and others) get a GitGalaxy-only row (`gg_only=1`) with every `ts_*` column left
blank, not scored as a loss.

## Files

- **`tree_sitter_accuracy_chart.svg`** — the current snapshot: a small-multiples bar chart, five
  metric panels (func recall/precision, class recall/precision, args exact-match), two bars per
  language per panel — GitGalaxy on top, tree-sitter's own reading on the bottom, both against
  the same ground truth. Regenerated from the CSV's latest batch on every push to `main` that
  touches the parsing engine, so it always reflects one specific commit (named in the CSV), not
  "current `main`" if you're reading this well after the fact.
- **`tree_sitter_accuracy_history.csv`** — the full time series: one row per language per
  measured batch, accumulating, nothing pruned or overwritten. The chart only ever renders the
  single most recent `timestamp_utc` batch — query this file directly to see a language's
  accuracy move over time instead.

## Reproducing or updating this locally

```bash
# from the gitgalaxy repo root
git clone --branch v1.0 --depth 1 https://github.com/squid-protocol/language-crucible.git ../language-crucible
pip install tree-sitter-language-pack

python tests/tools/tree_sitter_accuracy_audit.py --all --ci   # baseline-gated pass/fail, no writes
python tests/tools/tree_sitter_accuracy_audit.py --history    # appends a row per language to the CSV
python tests/tools/tree_sitter_accuracy_audit.py --chart      # re-renders the SVG from the latest CSV batch
```

`--history` is a no-op — prints a message and exits 0 without appending anything — when every
baselined language's fresh measurement is identical to the last recorded batch, so running it
twice with no engine change in between won't manufacture a duplicate row.

## Related reading

- [`docs/why_gitgalaxy_beats_ast_here.md`](../why_gitgalaxy_beats_ast_here.md) — the one
  documented case where GitGalaxy's `args` recall structurally beats a declaration-only AST read
  (bash, traditional-style Perl: functions with no formal parameter list at all for an AST to
  count).
- [`docs/language_status/README.md`](../language_status/README.md) — per-language status docs.
  `python.md` and `javascript.md` go one level deeper than this folder's aggregate numbers, with
  a real-corpus measurement section that found and closed several extraction defects
  ([#1182](https://github.com/squid-protocol/gitgalaxy/issues/1182),
  [#1183](https://github.com/squid-protocol/gitgalaxy/issues/1183),
  [#1184](https://github.com/squid-protocol/gitgalaxy/issues/1184)) plus one still open
  ([#1193](https://github.com/squid-protocol/gitgalaxy/issues/1193)).
- Root [`README.md`](../../README.md#proof-not-just-claims), item 4 under "Proof, Not Just
  Claims" — where this data is cited from.
