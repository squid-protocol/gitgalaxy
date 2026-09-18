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
Gate parity audit (#3069/#3072): prove the required-literal prefilter
one-sided AND the per-line gate exactly equivalent on the real corpora, rule
by rule, file by file.

For every language folder in the language-crucible AND keyword-rosetta corpora,
and for every compiled rule of that language, this derives the rule's gate
(rule_prefilter.derive_literal_gate) and checks the contract the detector
relies on: wherever the gate REJECTS a text, `pattern.finditer(text)` must
find nothing. One violation means a silently undercounted rule -- the audit
exits 1 and prints the exact (language, rule, file) triple.

Each file is checked as BOTH surfaces a rule can see in production: the raw
content and the Prism code stream (coding_analysis runs over segments of the
code stream; raw content is the stricter superset). A gate sound on both is
sound on any segment substring of them -- rejection is monotone under taking
substrings (fewer literals present, and a regex match inside a segment would
be a match inside the whole stream for these flat, non-anchored-to-EOF rules;
the assert on the full text is therefore the harder test).

The per-language reject rate it prints is the win metric for #3069: the
fraction of (rule x file) finditer sweeps the gate eliminates outright.

The #3072 leg is stricter: for every rule a language opts into `_line_gates`,
the per-line evaluation (rule_prefilter.line_gated_finditer) claims EXACT
equivalence, so every corpus file x surface must produce the identical
`[(span, groups)]` list as a whole-text finditer. Its printed metric is the
surviving-line rate -- the fraction of lines the heavy pattern still sweeps.

USAGE
    python tests/tools/gate_parity_audit.py                 # both corpora
    python tests/tools/gate_parity_audit.py --corpus rosetta
    python tests/tools/gate_parity_audit.py --json /tmp/gate_audit.json

Environment: LANGUAGE_CRUCIBLE_PATH / KEYWORD_ROSETTA_PATH override the
default sibling-checkout discovery (same as rule_probe.py, whose corpus
helpers this reuses).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rule_probe import corpus_files  # noqa: E402

from gitgalaxy.core.prism import Prism  # noqa: E402
from gitgalaxy.core.rule_prefilter import (  # noqa: E402
    build_line_gate,
    derive_literal_gate,
    fold_haystack,
    line_gated_finditer,
)
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS  # noqa: E402
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402


def _gate_rejects(gate, text: str) -> bool:
    literals, needs_casefold = gate
    hay = fold_haystack(text) if needs_casefold else text
    return not any(lit in hay for lit in literals)


def audit(corpus: str) -> tuple[dict, list[dict]]:
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    violations: list[dict] = []
    report: dict[str, dict] = {}

    for lang in sorted(LANGUAGE_DEFINITIONS):
        rules = [
            (name, pat, derive_literal_gate(pat))
            for name, pat in (LANGUAGE_DEFINITIONS[lang].get("rules") or {}).items()
            if not name.startswith("_") and pat is not None and hasattr(pat, "finditer")
        ]
        if not rules:
            continue
        lang_rules = LANGUAGE_DEFINITIONS[lang].get("rules") or {}
        line_rules = []
        for name in lang_rules.get("_line_gates") or ():
            if not hasattr(lang_rules.get(name), "finditer"):
                continue
            gate = build_line_gate(lang_rules[name])
            if gate is None:
                violations.append(
                    {
                        "kind": "line_gate_refused",
                        "lang": lang,
                        "rule": name,
                        "file": "",
                        "surface": "",
                        "gate": [],
                        "first_match": "declared in _line_gates but build_line_gate refused",
                    }
                )
                continue
            line_rules.append((name, lang_rules[name], gate))
        gated_rules = sum(1 for _n, _p, g in rules if g is not None)
        stats = {
            "files": 0,
            "rules": len(rules),
            "gated_rules": gated_rules,
            "checks": 0,
            "rejects": 0,
            "line_gate_rules": len(line_rules),
            "line_checks": 0,
            "line_total": 0,
            "line_surviving": 0,
        }

        for _corpus_name, root, path in corpus_files(lang, corpus):
            try:
                src = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            stats["files"] += 1
            code_stream = prism.split_streams(src, lang)["code_stream"]
            for rule_name, pattern, gate in rules:
                if gate is None:
                    continue
                for surface, text in (("raw", src), ("code_stream", code_stream)):
                    stats["checks"] += 1
                    if not _gate_rejects(gate, text):
                        continue
                    stats["rejects"] += 1
                    first = pattern.search(text)
                    if first is not None:
                        violations.append(
                            {
                                "lang": lang,
                                "rule": rule_name,
                                "file": str(path.relative_to(root)),
                                "surface": surface,
                                "gate": list(gate[0]),
                                "first_match": first.group(0)[:120],
                            }
                        )
            for rule_name, pattern, line_gate in line_rules:
                for surface, text in (("raw", src), ("code_stream", code_stream)):
                    stats["line_checks"] += 1
                    stats["line_total"] += text.count("\n") + 1
                    stats["line_surviving"] += sum(1 for _ in line_gate.finditer(text))
                    expected = [(m.span(), m.groups()) for m in pattern.finditer(text)]
                    actual = [(m.span(), m.groups()) for m in line_gated_finditer(pattern, line_gate, text)]
                    if actual != expected:
                        diff = next(
                            (i for i, pair in enumerate(zip(expected, actual)) if pair[0] != pair[1]),
                            min(len(expected), len(actual)),
                        )
                        violations.append(
                            {
                                "kind": "line_gate_parity",
                                "lang": lang,
                                "rule": rule_name,
                                "file": str(path.relative_to(root)),
                                "surface": surface,
                                "gate": [line_gate.pattern],
                                "first_match": f"first divergence at index {diff}: "
                                f"expected={expected[diff] if diff < len(expected) else None} "
                                f"actual={actual[diff] if diff < len(actual) else None}",
                            }
                        )
        if stats["files"]:
            report[lang] = stats

    return report, violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--corpus", choices=("crucible", "rosetta", "both"), default="both")
    ap.add_argument("--json", type=Path, help="write the full report + violations as JSON")
    args = ap.parse_args(argv)

    report, violations = audit(args.corpus)

    total_checks = sum(s["checks"] for s in report.values())
    total_rejects = sum(s["rejects"] for s in report.values())
    print(f"{'language':16s} {'files':>5s} {'gated/rules':>12s} {'checks':>8s} {'rejects':>8s} {'reject%':>8s}")
    for lang, s in sorted(
        report.items(), key=lambda kv: -(kv[1]["rejects"] / kv[1]["checks"] if kv[1]["checks"] else 0)
    ):
        pct = 100.0 * s["rejects"] / s["checks"] if s["checks"] else 0.0
        print(
            f"{lang:16s} {s['files']:5d} {s['gated_rules']:5d}/{s['rules']:<5d} {s['checks']:8d} {s['rejects']:8d} {pct:7.1f}%"
        )
    overall = 100.0 * total_rejects / total_checks if total_checks else 0.0
    print(f"\nTOTAL: {total_rejects}/{total_checks} gate rejections ({overall:.1f}% of rule sweeps eliminated)")

    line_langs = {lang: s for lang, s in report.items() if s.get("line_gate_rules")}
    if line_langs:
        print(f"\nper-line gates (#3072): exact-parity leg")
        print(f"{'language':16s} {'rules':>5s} {'checks':>8s} {'lines':>10s} {'surviving':>10s} {'survive%':>9s}")
        for lang, s in sorted(line_langs.items()):
            pct = 100.0 * s["line_surviving"] / s["line_total"] if s["line_total"] else 0.0
            print(
                f"{lang:16s} {s['line_gate_rules']:5d} {s['line_checks']:8d} "
                f"{s['line_total']:10d} {s['line_surviving']:10d} {pct:8.1f}%"
            )

    if args.json:
        args.json.write_text(json.dumps({"report": report, "violations": violations}, indent=2))
        print(f"wrote {args.json}")

    if violations:
        print(f"\n*** {len(violations)} INVARIANT VIOLATIONS ***", file=sys.stderr)
        for v in violations[:50]:
            print(
                f"  [{v.get('kind', 'one_sided')}] {v['lang']}::{v['rule']} {v['file']} [{v['surface']}] "
                f"gate={v['gate']} first_match={v['first_match']!r}",
                file=sys.stderr,
            )
        return 1
    print("zero violations: every gate rejection corresponds to zero real matches,")
    print("and every line-gated sweep is exactly equivalent to its whole-text finditer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
