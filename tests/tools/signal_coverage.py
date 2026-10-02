#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""
Signal-coverage floor for the golden master (#4108).

The golden-master diff can only catch a regression in a signal the corpus
actually exercises: a signal that is 0 on every crucible file stays 0 when its
rule breaks, and the diff shows nothing. This tool counts, per structural
signature, how many crucible files it fires on in a committed fixture, and
checks the zero-coverage set against ``tests/signal_coverage_baseline.json``,
where every zero carries the reason it is zero.

``check`` fails when:
  * a signal that HAD coverage now fires on no file (it lost its only
    regression guard -- usually a broken rule blessed into the golden master);
  * a baselined zero now fires (good news -- ratchet it out of the baseline).

Usage::

    python tests/tools/signal_coverage.py report            # coverage table
    python tests/tools/signal_coverage.py check             # CI gate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_HERE.parent))  # tests/ -- golden_store (no tests/__init__.py)
import golden_store  # noqa: E402

BASELINE_PATH = REPO_ROOT / "tests" / "signal_coverage_baseline.json"
FIXTURES = (golden_store.FULL_PRECISION, golden_store.ZERO_DEPENDENCY)
PARSED = "6. Parsed Files (Scanned Artifacts)"
SIGNATURES = "7. Structural Signatures (Net Mitigated Signals)"


def coverage(fixture: str | Path) -> tuple[int, dict[str, int]]:
    """(file count, {signal label: number of files it fires on})."""
    audit = golden_store.load(str(fixture))
    files = 0
    counts: dict[str, int] = {}
    for group in (audit.get(PARSED) or {}).values():
        for f in (group.get("Files") or {}).values():
            files += 1
            for label, value in (f.get(SIGNATURES) or {}).items():
                counts.setdefault(label, 0)
                if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                    counts[label] += 1
    return files, counts


def problems(counts: dict[str, int], baseline: dict[str, str]) -> list[str]:
    out = []
    for label, n in sorted(counts.items()):
        if n == 0 and label not in baseline:
            out.append(
                f"{label!r} now fires on no crucible file -- the golden master can no longer catch a regression "
                "in it. If its rule broke, fix it; if the corpus lost its only example, restore coverage; only "
                "baseline it with a reason if zero is genuinely expected."
            )
        if n > 0 and label in baseline:
            out.append(
                f"{label!r} now fires on {n} file(s) but is baselined as zero ({baseline[label]}) -- remove it from "
                "tests/signal_coverage_baseline.json."
            )
    for label in sorted(set(baseline) - set(counts)):
        out.append(
            f"baselined signal {label!r} is no longer reported at all -- renamed or removed? Update the baseline."
        )
    return out


def load_baseline() -> dict[str, str]:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))["zero_coverage"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cmd", choices=("report", "check"))
    args = parser.parse_args(argv)
    baseline = load_baseline()
    failed = False
    for fixture in FIXTURES:
        files, counts = coverage(REPO_ROOT / fixture)
        if args.cmd == "report":
            print(f"== {fixture} ({files} files)")
            for label, n in sorted(counts.items(), key=lambda kv: (kv[1], kv[0])):
                note = f"  [{baseline[label]}]" if label in baseline else ""
                print(f"{n:6d} {n / files:7.2%}  {label}{note}")
            continue
        found = problems(counts, baseline)
        for p in found:
            print(f"{fixture}: {p}")
        failed = failed or bool(found)
    if args.cmd == "check" and not failed:
        print(f"signal coverage OK: {len(baseline)} baselined zero(s), no signal lost coverage")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
