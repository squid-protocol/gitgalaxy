#!/usr/bin/env python3
"""
recall_audit.py

Enumerates every function tree-sitter OR universal-ctags reports that GitGalaxy does NOT, across
the whole language-crucible corpus, per language, at the OCCURRENCE level (a name GitGalaxy finds
3x and tree-sitter finds 5x is 2 non-detections, not 0). For each, prints the source line so the
only work left is reading it and sorting it into one of the two buckets in the
`tri-comparison-ledger-sweep` skill's step 2.6:

  1. a real GitGalaxy recall gap        -> file a GitHub issue with an isolated repro
  2. a comparison/audit-tool artifact   -> name the mechanism, fix the audit or document it

This is the standing answer to "is GitGalaxy missing anything?" -- run it with no arguments for
the full sweep, or name languages to scope it.

    python tests/tools/recall_audit.py                # every language
    python tests/tools/recall_audit.py cpp shell      # just these

It is verification-only tooling (needs tree-sitter-language-pack, optionally universal-ctags),
never imported by anything under gitgalaxy/. Same optional-dependency contract as
tri_comparison_gatherer.py.
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import tree_sitter_accuracy_audit as tsaa
from tri_comparison_gatherer import gather_language

# The languages with a tree-sitter baseline (NODE_MAPS) plus the ctags-comparable gg-only set --
# the exact universe where a "GitGalaxy misses X" question is answerable.
_TS_LANGS = sorted(tsaa.NODE_MAPS)


def _src_line(corpus_dir: Path, relpath: str, lineno: int) -> str:
    p = corpus_dir / relpath
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "<source unavailable>"
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()[:120]
    return "<line out of range>"


def audit_language(lang: str) -> dict:
    readings = gather_language(lang)
    corpus_dir = tsaa.ensure_corpus(lang)

    ts_misses: list[tuple[str, str, int]] = []  # (file, name, line)
    ct_misses: list[tuple[str, str, int]] = []

    for fr in readings:
        gg_by = collections.Counter(o.name for o in fr.gg_funcs)

        ts_lines: dict[str, list[int]] = collections.defaultdict(list)
        for o in fr.ts_funcs:
            ts_lines[o.name].append(o.line)
        ct_lines: dict[str, list[int]] = collections.defaultdict(list)
        for o in fr.ctags_funcs:
            ct_lines[o.name].append(o.line)

        for name, lines in ts_lines.items():
            surplus = sorted(lines)[gg_by.get(name, 0) :]
            ts_misses.extend((fr.file_path, name, ln) for ln in surplus)

        ts_names = set(ts_lines)
        for name, lines in ct_lines.items():
            if name in ts_names:
                continue  # already covered by the tree-sitter column
            surplus = sorted(lines)[gg_by.get(name, 0) :]
            ct_misses.extend((fr.file_path, name, ln) for ln in surplus)

    return {
        "lang": lang,
        "corpus_dir": corpus_dir,
        "ts_misses": sorted(ts_misses),
        "ct_misses": sorted(ct_misses),
    }


def _measure_counted_misses(lang: str) -> int | None:
    """The number the published accuracy table's recall is computed from:
    real_functions - found_functions from measure()."""
    if lang not in tsaa.NODE_MAPS:
        return None
    try:
        m = tsaa.measure(lang)
    except SystemExit:
        return None
    return m["real_functions"] - m["found_functions"]


def main(argv: list[str]) -> int:
    langs = argv[1:] or _TS_LANGS
    grand_ts = 0
    for lang in langs:
        try:
            res = audit_language(lang)
        except Exception as exc:
            print(f"\n{'=' * 78}\n{lang}: SKIPPED -- {exc}\n{'=' * 78}")
            continue

        counted = _measure_counted_misses(lang)
        n_ts = len(res["ts_misses"])
        n_ct = len(res["ct_misses"])
        grand_ts += n_ts
        print(f"\n{'=' * 78}\n{lang}\n{'=' * 78}")
        if counted is not None:
            note = ""
            if counted != n_ts:
                note = f"   <-- differs from raw name-diff ({n_ts}); check drop-rules / alignment"
            print(f"  measure() counted misses (recall denominator gap): {counted}{note}")

        print(f"\n  tree-sitter finds / GitGalaxy misses  ({n_ts}):")
        for f, name, ln in res["ts_misses"]:
            print(f"    {f}:{ln}  {name!r}")
            print(f"        | {_src_line(res['corpus_dir'], f, ln)}")

        if n_ct:
            print(f"\n  ctags-only finds / GitGalaxy misses  ({n_ct}):")
            per_file = collections.Counter(f for f, _, _ in res["ct_misses"])
            shown = collections.Counter()
            for f, name, ln in res["ct_misses"]:
                shown[f] += 1
                if shown[f] <= 8:
                    print(f"    {f}:{ln}  {name!r}  | {_src_line(res['corpus_dir'], f, ln)}")
            for f, c in per_file.items():
                if c > 8:
                    print(f"    ... {f}: +{c - 8} more")

    print(f"\n{'=' * 78}\nTOTAL tree-sitter-finds / GitGalaxy-misses across {len(langs)} language(s): {grand_ts}")
    print("Every one must be sorted into skill step 2.6's bucket 1 (issue) or bucket 2 (artifact).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
