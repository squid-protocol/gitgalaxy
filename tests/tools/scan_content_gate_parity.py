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
Security-lens gate parity audit (#3173): prove the SecurityLens.THREAT_SIGNATURES
literal prefilter one-sided on the real corpora, signature by signature, file by
file.

`SecurityLens.scan_content` gates each threat signature with a required-literal
set derived once in __init__ (rule_prefilter.derive_literal_gate, prefer_selective
=True). This audit checks the exact contract scan_content relies on: wherever a
signature's gate REJECTS the ReDoS-armored haystack (`safe_content` -- the same
250-char-line-stripped join the regex runs on), `regex.finditer(safe_content)`
must find nothing. One violation means a silently undercounted threat signal --
the audit exits 1 and prints the exact (signature, file) pair.

Unlike the coding-rule gates, the 13 signatures are language-agnostic (they run
on every file), so this sweeps every file of every language in the crucible +
keyword-rosetta corpora once.

The per-signature reject rate it prints is the win metric for #3173: the fraction
of (signature x file) finditer sweeps the gate eliminates outright.

USAGE
    python tests/tools/scan_content_gate_parity.py                 # both corpora
    python tests/tools/scan_content_gate_parity.py --corpus rosetta
    python tests/tools/scan_content_gate_parity.py --json /tmp/sec_audit.json

Environment: LANGUAGE_CRUCIBLE_PATH / KEYWORD_ROSETTA_PATH override the default
sibling-checkout discovery (same as rule_probe.py, whose corpus helpers this
reuses).
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

from gitgalaxy.core.rule_prefilter import fold_haystack  # noqa: E402
from gitgalaxy.security.security_lens import SecurityLens  # noqa: E402
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402


def _safe_content(content: str) -> str:
    """The ReDoS-armored haystack scan_content actually sweeps (security_lens.py):
    lines >= 250 chars dropped, the rest stripped and re-joined."""
    return "\n".join(line.strip() for line in content.splitlines() if len(line) < 250)


def _all_corpus_files(corpus: str):
    """Every file of every language, de-duplicated (a signature is language-agnostic)."""
    seen: set[Path] = set()
    for lang in sorted(LANGUAGE_DEFINITIONS):
        for corpus_name, root, path in corpus_files(lang, corpus):
            if path in seen:
                continue
            seen.add(path)
            yield corpus_name, root, path


def audit(corpus: str) -> tuple[dict, list[dict]]:
    lens = SecurityLens()
    gated = {k: g for k, g in lens._signature_gates.items() if g is not None}
    stats = {k: {"checks": 0, "rejects": 0} for k in lens.THREAT_SIGNATURES}
    violations: list[dict] = []
    files = 0

    for _corpus_name, root, path in _all_corpus_files(corpus):
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files += 1
        safe = _safe_content(src)
        folded: str | None = None
        for key, gate in gated.items():
            literals, needs_fold = gate
            if needs_fold:
                if folded is None:
                    folded = fold_haystack(safe)
                hay = folded
            else:
                hay = safe
            stats[key]["checks"] += 1
            if any(lit in hay for lit in literals):
                continue  # gate lets it through -- no claim to check
            stats[key]["rejects"] += 1
            # gate rejects -> the regex MUST find nothing on the same haystack
            first = lens.THREAT_SIGNATURES[key].search(safe)
            if first is not None:
                violations.append(
                    {
                        "signature": key,
                        "file": str(path.relative_to(root)),
                        "gate": list(literals),
                        "first_match": first.group(0)[:120],
                    }
                )
    return {"files": files, "gated": sorted(gated), "signatures": stats}, violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--corpus", choices=("crucible", "rosetta", "both"), default="both")
    ap.add_argument("--json", type=Path, help="write the full report + violations as JSON")
    args = ap.parse_args(argv)

    report, violations = audit(args.corpus)
    sig = report["signatures"]
    total_checks = sum(s["checks"] for s in sig.values())
    total_rejects = sum(s["rejects"] for s in sig.values())

    print(f"scanned {report['files']} corpus files; {len(report['gated'])}/13 signatures gate\n")
    print(f"{'signature':28s} {'gated':>6s} {'checks':>8s} {'rejects':>8s} {'reject%':>8s}")
    for key, s in sorted(sig.items(), key=lambda kv: -(kv[1]["rejects"] / kv[1]["checks"] if kv[1]["checks"] else 0)):
        is_gated = key in report["gated"]
        pct = 100.0 * s["rejects"] / s["checks"] if s["checks"] else 0.0
        print(f"{key:28s} {('yes' if is_gated else '--'):>6s} {s['checks']:8d} {s['rejects']:8d} {pct:7.1f}%")
    overall = 100.0 * total_rejects / total_checks if total_checks else 0.0
    print(f"\nTOTAL: {total_rejects}/{total_checks} gate rejections ({overall:.1f}% of signature sweeps eliminated)")

    if args.json:
        args.json.write_text(json.dumps({"report": report, "violations": violations}, indent=2))
        print(f"wrote {args.json}")

    if violations:
        print(f"\n*** {len(violations)} ONE-SIDED-INVARIANT VIOLATIONS ***", file=sys.stderr)
        for v in violations[:50]:
            print(
                f"  {v['signature']} {v['file']} gate={v['gate']} first_match={v['first_match']!r}",
                file=sys.stderr,
            )
        return 1
    print("zero violations: every gate rejection corresponds to zero real matches on safe_content.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
