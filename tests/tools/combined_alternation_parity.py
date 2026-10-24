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
Combined-alternation candidate finder: the parity harness for #3073.

#3073 stays deferred as an engine change (docs/perf_speed_testing.md): the cost is a few hot single
rules, not the number of passes. Its one shape worth prototyping is a first-pass candidate finder,
and the precondition for ever reopening it is an exact parity proof. This is that proof, built on
the same corpora as `gate_parity_audit.py`; it changes no engine behaviour.

One combined regex of the rules' required literals (rule_prefilter.derive_literal_gate) is swept
over a segment ONCE and yields the set of candidate rules. Contract: every rule whose
`finditer` finds a match is a candidate (a superset; never an undercount).

Two traps of a naive alternation, both handled here and pinned by the tests:
  * leftmost-wins consumption: in `ab|bc` over "abc" the match "ab" eats the "b" that "bc" needs.
    The finder scans with a zero-width lookahead (a hit at every start position) and reduces the
    literals to those with no other literal as a substring, so two literals can never share a
    start position and the first alternative can never hide a second. A rule whose literal
    contains a reduced one is credited when the shorter one is found (a widening: a false
    candidate, never a missed one).
  * flag mixes: a case-insensitive gate is matched against `fold_haystack(text)`, so those
    literals live in a second combined regex over the folded text.
Rules with no safe gate (`derive_literal_gate` is None) are always candidates.

USAGE
    python tests/tools/combined_alternation_parity.py                 # both corpora
    python tests/tools/combined_alternation_parity.py --corpus rosetta
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gitgalaxy.core.rule_prefilter import derive_literal_gate, fold_haystack  # noqa: E402


def _reduce(literals: set[str]) -> dict[str, str]:
    """Map each literal to the shortest literal it contains (itself when none)."""
    ordered = sorted(literals, key=lambda s: (len(s), s))
    mapping: dict[str, str] = {}
    minimal: list[str] = []
    for lit in ordered:
        rep = next((m for m in minimal if m in lit), None)
        if rep is None:
            minimal.append(lit)
            rep = lit
        mapping[lit] = rep
    return mapping


class _Side:
    """The combined regex for one haystack form (exact text or folded text)."""

    def __init__(self) -> None:
        self.rule_literals: dict[str, set[str]] = {}
        self.regex: re.Pattern[str] | None = None
        self.rules_by_rep: dict[str, set[str]] = {}

    def freeze(self) -> None:
        all_lits = set().union(*self.rule_literals.values()) if self.rule_literals else set()
        mapping = _reduce(all_lits)
        for rule, lits in self.rule_literals.items():
            for lit in lits:
                self.rules_by_rep.setdefault(mapping[lit], set()).add(rule)
        reps = sorted(self.rules_by_rep, key=lambda s: (-len(s), s))
        if reps:
            self.regex = re.compile("(?=(" + "|".join(re.escape(r) for r in reps) + "))")

    def hit(self, text: str) -> set[str]:
        if self.regex is None:
            return set()
        found = {m.group(1) for m in self.regex.finditer(text)}
        out: set[str] = set()
        for rep in found:
            out |= self.rules_by_rep[rep]
        return out


class CandidateFinder:
    def __init__(self, rules: dict[str, Any]) -> None:
        self.always: set[str] = set()
        self._exact, self._folded = _Side(), _Side()
        for name, pat in rules.items():
            gate = derive_literal_gate(pat)
            if gate is None:
                self.always.add(name)
                continue
            side = self._folded if gate[1] else self._exact
            side.rule_literals[name] = set(gate[0])
        self._exact.freeze()
        self._folded.freeze()

    def candidates(self, text: str) -> set[str]:
        out = set(self.always) | self._exact.hit(text)
        if self._folded.regex is not None:
            out |= self._folded.hit(fold_haystack(text))
        return out


def gate_accepted(rules: dict[str, Any], text: str) -> set[str]:
    """The per-rule gate's accept set (what detector.py runs today); candidates must contain it."""
    out = set()
    for name, pat in rules.items():
        gate = derive_literal_gate(pat)
        if gate is None:
            out.add(name)
            continue
        hay = fold_haystack(text) if gate[1] else text
        if any(lit in hay for lit in gate[0]):
            out.add(name)
    return out


def check_text(rules: dict[str, Any], finder: CandidateFinder, text: str) -> tuple[set[str], set[str], set[str]]:
    """Return (missed, widened, candidates): missed must be empty; widened = candidates the gate rejects."""
    cands = finder.candidates(text)
    matching = {n for n, p in rules.items() if p.search(text) is not None}
    return matching - cands, cands - gate_accepted(rules, text), cands


def _rules_of(defn: dict) -> dict[str, Any]:
    return {
        n: p
        for n, p in (defn.get("rules") or {}).items()
        if not n.startswith("_") and p is not None and hasattr(p, "finditer")
    }


def audit(corpus: str) -> tuple[dict[str, dict], list[dict]]:
    from rule_probe import corpus_files

    from gitgalaxy.core.prism import Prism
    from gitgalaxy.core.source_text import read_source
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    report: dict[str, dict] = {}
    violations: list[dict] = []
    for lang in sorted(LANGUAGE_DEFINITIONS):
        rules = _rules_of(LANGUAGE_DEFINITIONS[lang])
        if not rules:
            continue
        finder = CandidateFinder(rules)
        stats = {"files": 0, "rules": len(rules), "checks": 0, "candidates": 0, "widened": 0}
        for _name, root, path in corpus_files(lang, corpus):
            try:
                src = read_source(path).text
            except OSError:
                continue
            stats["files"] += 1
            for surface, text in (("raw", src), ("code_stream", prism.split_streams(src, lang)["code_stream"])):
                missed, widened, cands = check_text(rules, finder, text)
                stats["checks"] += 1
                stats["candidates"] += len(cands)
                stats["widened"] += len(widened)
                for rule in sorted(missed):
                    violations.append(
                        {"lang": lang, "rule": rule, "file": str(path.relative_to(root)), "surface": surface}
                    )
        if stats["files"]:
            report[lang] = stats
    return report, violations


def time_rules(rules: dict[str, Any], finder: CandidateFinder, texts: list[str]) -> dict[str, Any]:
    """Seconds spent by each stage over `texts`: the per-rule gate, the combined finder, and the real `finditer`
    sweeps of the gate-accepted rules (per rule). `residual_s` is the sweep time outside the five costliest rules,
    the most a merged scan could ever remove; `finder_s` is what it would cost to find the candidates."""
    gates = {n: derive_literal_gate(p) for n, p in rules.items()}
    gate_s = finder_s = 0.0
    sweep: dict[str, float] = dict.fromkeys(rules, 0.0)
    for text in texts:
        t0 = time.perf_counter()
        folded = fold_haystack(text)
        accepted = [n for n, g in gates.items() if g is None or any(lit in (folded if g[1] else text) for lit in g[0])]
        gate_s += time.perf_counter() - t0
        t0 = time.perf_counter()
        finder.candidates(text)
        finder_s += time.perf_counter() - t0
        for n in accepted:
            t0 = time.perf_counter()
            for _m in rules[n].finditer(text):
                pass
            sweep[n] += time.perf_counter() - t0
    ranked = sorted(sweep.values(), reverse=True)
    return {
        "gate_s": gate_s,
        "finder_s": finder_s,
        "sweep_s": sum(ranked),
        "top5_s": sum(ranked[:5]),
        "residual_s": sum(ranked[5:]),
    }


def time_audit(corpus: str) -> dict[str, dict]:
    """Per-language `time_rules` over the corpus files' code streams (what coding_analysis sweeps)."""
    from rule_probe import corpus_files

    from gitgalaxy.core.prism import Prism
    from gitgalaxy.core.source_text import read_source
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    out: dict[str, dict] = {}
    for lang in sorted(LANGUAGE_DEFINITIONS):
        rules = _rules_of(LANGUAGE_DEFINITIONS[lang])
        if not rules:
            continue
        texts = []
        for _name, _root, path in corpus_files(lang, corpus):
            try:
                texts.append(prism.split_streams(read_source(path).text, lang)["code_stream"])
            except OSError:
                continue
        if texts:
            out[lang] = {"files": len(texts), **time_rules(rules, CandidateFinder(rules), texts)}
    return out


def _print_times(report: dict[str, dict]) -> None:
    print(f"{'language':16s} {'files':>5s} {'gate':>8s} {'finder':>8s} {'sweep':>8s} {'top5':>8s} {'residual':>8s}")
    totals = dict.fromkeys(("gate_s", "finder_s", "sweep_s", "top5_s", "residual_s"), 0.0)
    for lang, s in sorted(report.items()):
        print(
            f"{lang:16s} {s['files']:5d} {s['gate_s']:8.3f} {s['finder_s']:8.3f} "
            f"{s['sweep_s']:8.3f} {s['top5_s']:8.3f} {s['residual_s']:8.3f}"
        )
        for k in totals:
            totals[k] += s[k]
    print(
        f"{'TOTAL':16s} {'':5s} {totals['gate_s']:8.3f} {totals['finder_s']:8.3f} "
        f"{totals['sweep_s']:8.3f} {totals['top5_s']:8.3f} {totals['residual_s']:8.3f}"
    )
    sweep = totals["sweep_s"] or 1.0
    print(f"residual / (gate + sweep) = {totals['residual_s'] / (totals['gate_s'] + sweep):.1%}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--corpus", choices=("crucible", "rosetta", "both"), default="both")
    ap.add_argument("--time", action="store_true", help="report stage timings (gate / finder / sweep) instead")
    args = ap.parse_args(argv)
    if args.time:
        _print_times(time_audit(args.corpus))
        return 0
    report, violations = audit(args.corpus)
    print(f"{'language':16s} {'files':>5s} {'rules':>5s} {'checks':>7s} {'cand/check':>10s} {'widened':>8s}")
    for lang, s in sorted(report.items()):
        per = s["candidates"] / s["checks"] if s["checks"] else 0.0
        print(f"{lang:16s} {s['files']:5d} {s['rules']:5d} {s['checks']:7d} {per:10.1f} {s['widened']:8d}")
    if violations:
        print(f"*** {len(violations)} MISSED CANDIDATES ***", file=sys.stderr)
        for v in violations[:50]:
            print(f"  {v['lang']}::{v['rule']} {v['file']} [{v['surface']}]", file=sys.stderr)
        return 1
    print("zero violations: every rule with a real match was a candidate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
