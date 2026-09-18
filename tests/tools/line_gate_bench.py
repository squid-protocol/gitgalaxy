#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
Per-line gate micro-benchmark (#3072): gated vs ungated rule-sweep wall time.

For every rule a language opts into `_line_gates`, times `pattern.finditer`
against `line_gated_finditer` on three inputs:

- corpus: the language's language-crucible files (the shipping distribution
  of hit densities -- the number that decides whether a gate ships);
- sparse: a synthetic 100k-line comment/declaration-heavy file where almost
  no line survives (the gate's best case);
- dense: a synthetic 100k-line all-assignments file where EVERY line survives
  (the adversarial worst case -- a per-line gate cannot win here by
  construction; the run-coalescing evaluation exists to BOUND this loss).

Acceptance (#3072): a gated rule must WIN on corpus; its dense-case loss must
stay within --max-dense-loss (default 35%). A rule that fails either test
should have its `_line_gates` entry removed, not shipped. Exit 1 on failure.

USAGE
    python tests/tools/line_gate_bench.py [--repeat 3] [--max-dense-loss 0.35]

Environment: LANGUAGE_CRUCIBLE_PATH overrides the default sibling-checkout
discovery (same as rule_probe.py, whose corpus helper this reuses).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rule_probe import corpus_files  # noqa: E402

from gitgalaxy.core.rule_prefilter import build_line_gate, line_gated_finditer  # noqa: E402
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402

_SPARSE_BLOCK = (
    "/* threshold accounting for the outer retry loop; see RFC-1149 */\n"
    "struct flux_capacitor_stats;\n"
    "extern void recompute_flux(struct flux_capacitor_stats *stats);\n"
    "/* nine of these ten lines contain none of the gate's operators and\n"
    "   reject at candidate-scan speed; this line's own -- keeps exactly\n"
    "   one genuine survivor per block so windows are still exercised */\n"
    "typedef unsigned long long tick_counter_t;\n"
    "void log_tick(tick_counter_t tick);\n"
    "#include \"flux.h\"\n"
    "int classify(int levels);\n"
)

_DENSE_BLOCK = (
    "total = total + step;\n"
    "cursor += stride;\n"
    "count++;\n"
    "flags &= mask;\n"
    "ptr->field = value;\n"
    "matrix[i][j] = matrix[j][i];\n"
    "checksum ^= word;\n"
    "--remaining;\n"
    "head = head->next;\n"
    "acc <<= 1;\n"
)


def _synthetic(block: str, lines: int) -> str:
    reps = lines // block.count("\n") + 1
    return block * reps


def _time_best(fn, repeat: int) -> float:
    best = float("inf")
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--repeat", type=int, default=3, help="take the best of N timings")
    ap.add_argument("--lines", type=int, default=100_000, help="synthetic input size in lines")
    ap.add_argument(
        "--max-dense-loss",
        type=float,
        default=0.35,
        help="acceptable slowdown fraction on the all-surviving adversarial input",
    )
    args = ap.parse_args(argv)

    sparse = _synthetic(_SPARSE_BLOCK, args.lines)
    dense = _synthetic(_DENSE_BLOCK, args.lines)

    failures: list[str] = []
    header = (
        f"{'lang::rule':24s} {'input':7s} {'ungated':>9s} {'gated':>9s} {'speedup':>8s} {'matches':>9s}"
    )
    print(header)
    print("-" * len(header))

    for lang in sorted(LANGUAGE_DEFINITIONS):
        rules = LANGUAGE_DEFINITIONS[lang].get("rules") or {}
        for rule_name in rules.get("_line_gates") or ():
            pattern = rules.get(rule_name)
            if not hasattr(pattern, "finditer"):
                continue
            line_gate = build_line_gate(pattern)
            if line_gate is None:
                failures.append(f"{lang}::{rule_name}: declared but build_line_gate refused")
                continue

            corpus_texts = []
            for _corpus_name, _root, path in corpus_files(lang, "crucible"):
                try:
                    corpus_texts.append(path.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    continue

            for input_name, texts in (("corpus", corpus_texts), ("sparse", [sparse]), ("dense", [dense])):
                if not texts:
                    continue
                t_ungated = _time_best(lambda: [list(pattern.finditer(t)) for t in texts], args.repeat)
                t_gated = _time_best(lambda: [line_gated_finditer(pattern, line_gate, t) for t in texts], args.repeat)
                n_matches = sum(len(list(pattern.finditer(t))) for t in texts)
                speedup = t_ungated / t_gated if t_gated else float("inf")
                print(
                    f"{lang + '::' + rule_name:24s} {input_name:7s} {t_ungated * 1e3:8.1f}m {t_gated * 1e3:8.1f}m "
                    f"{speedup:7.2f}x {n_matches:9d}"
                )
                if input_name == "corpus" and t_gated >= t_ungated:
                    failures.append(
                        f"{lang}::{rule_name}: LOSES on corpus ({t_gated * 1e3:.1f}ms vs {t_ungated * 1e3:.1f}ms) "
                        "-- remove its _line_gates entry"
                    )
                if input_name == "dense" and t_gated > t_ungated * (1 + args.max_dense_loss):
                    failures.append(
                        f"{lang}::{rule_name}: dense-case loss {t_gated / t_ungated - 1:.0%} exceeds "
                        f"--max-dense-loss {args.max_dense_loss:.0%}"
                    )

    if failures:
        print(f"\n*** {len(failures)} ACCEPTANCE FAILURES ***", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print("\nall line-gated rules pass: corpus win + bounded dense-case loss.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
