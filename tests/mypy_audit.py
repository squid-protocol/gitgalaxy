#!/usr/bin/env python3
"""
Mypy Audit (#430)

Runs `mypy gitgalaxy/ --ignore-missing-imports` and gates the result against
a committed baseline, so CI enforces "no new type errors" without demanding
the pre-existing backlog be fixed first. Filed as part of #429 -- see that
epic for why mypy was worth adding despite NOT being the right tool for the
producer/consumer dict-key bugs `dead_key_audit.py` targets (mypy has no
visibility into which string keys are "correct" on a `Dict[str, Any]`).

USAGE
    python tests/mypy_audit.py          # full report, exits 1 if mypy finds
                                         # anything -- use this to regenerate
                                         # the baseline after a cleanup PR.
    python tests/mypy_audit.py --ci     # baseline-gated regression check
                                         # (see BASELINE below) -- this is
                                         # what CI runs.

IMPORTANT: regenerate the baseline in the SAME environment mypy-audit.yml
uses -- `pip install mypy PyYAML && pip install -e .`, nothing else.
Confirmed the hard way (PR #436): regenerating it in a "full-precision"
env (networkx/tiktoken/pandas/xgboost also installed) silently changed
mypy's resolution for at least one line (galaxyscope.py's `importlib.util`
usage stopped erroring), producing a baseline that passed locally but
failed in CI's leaner environment.

BASELINE
This repo had 235 pre-existing mypy errors across 31 files the day this
check was wired into CI (see mypy_audit_baseline.json, and #429/#431-#433
for the fix-up epic). Hard failing on those immediately would block every
unrelated PR, so `--ci` mode is a REGRESSION gate: it fails only on errors
not already in the baseline. Fixing a baselined error doesn't fail the
build either -- shrinking the baseline is a deliberate, reviewable edit you
make yourself (same "deliberate, reviewable updates instead of silent
overwrite" philosophy as #330's golden_master.json and dead_key_audit.py's
own baseline), not something this script does automatically. `--ci` prints
anything it notices has already been fixed as an FYI, so the baseline
doesn't silently go stale, but does not fail the build over it.

SCOPE & LIMITATIONS (read before treating the baseline as static)
Baseline keys are `{file}:{line}: {code}`. Line numbers are NOT stable --
an unrelated edit earlier in a file shifts every error below it, which
will look like "N new errors" even though nothing type-relevant changed.
This is a standard, accepted tradeoff for line-based mypy baselining (most
real-world baseline tools, including mypy's own `--baseline-file` used
elsewhere, have the same property), not a bug in this script. If a PR
that didn't touch type-relevant code trips `--ci`, regenerate the baseline
(`python tests/mypy_audit.py` and copy its output into
mypy_audit_baseline.json) rather than treating it as a real regression.

Also, the key doesn't disambiguate multiple distinct errors of the same
code on the same line (confirmed: 5 lines in the initial baseline each
carry 2-4 separate "operator" or "index" errors) -- those collapse into
one baseline entry each, so fixing some-but-not-all of them on such a
line won't show up as partial progress. Real, but rare (5/235 initially)
and not worth a more fragile per-occurrence key scheme to fully solve.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_ROOT = REPO_ROOT / "gitgalaxy"
BASELINE_PATH = Path(__file__).resolve().parent / "mypy_audit_baseline.json"

# Matches mypy's normal text output, e.g.:
#   gitgalaxy/galaxyscope.py:70: error: Module has no attribute "util"  [attr-defined]
_ERROR_LINE = re.compile(r"^(?P<file>[^:]+):(?P<line>\d+): error: (?P<message>.+?)\s*\[(?P<code>[a-z][a-z0-9-]*)\]$")


def run_mypy() -> Dict[str, str]:
    """Returns {"{file}:{line}: {code}": message} for every error mypy reports."""
    result = subprocess.run(
        ["mypy", str(SCAN_ROOT), "--ignore-missing-imports"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    errors: Dict[str, str] = {}
    for line in result.stdout.splitlines():
        match = _ERROR_LINE.match(line)
        if not match:
            continue
        key = f"{match['file']}:{match['line']}: {match['code']}"
        errors[key] = match["message"]
    return errors


def load_baseline() -> Dict[str, str]:
    if not BASELINE_PATH.exists():
        return {}
    with open(BASELINE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _print_errors(errors: Dict[str, str]) -> None:
    for key in sorted(errors):
        print(f"  {key}  -- {errors[key]}")


def run_full_report() -> int:
    errors = run_mypy()
    if not errors:
        print("Mypy Audit: no errors found.")
        return 0

    print(f"Mypy Audit: {len(errors)} error(s) found:\n")
    _print_errors(errors)
    print(
        "\nTo accept this as the new baseline (e.g. after a cleanup PR), regenerate it with:\n"
        '  python -c "from tests.mypy_audit import run_mypy; import json; '
        'json.dump(run_mypy(), open(\'tests/mypy_audit_baseline.json\', \'w\'), indent=2, sort_keys=True)"'
    )
    return 1


def run_ci_check() -> int:
    """
    Baseline-gated regression check (#430): fails only on errors NOT already
    in mypy_audit_baseline.json. See the module docstring's BASELINE section
    for why this isn't a zero-tolerance check.
    """
    errors = run_mypy()
    baseline = load_baseline()

    new_errors = {key: msg for key, msg in errors.items() if key not in baseline}
    resolved_keys = sorted(set(baseline) - set(errors))

    if resolved_keys:
        print("Mypy Audit: FYI -- these baselined errors are no longer flagged (fixed, or line-shifted).")
        print("Consider removing them from mypy_audit_baseline.json in this PR:\n")
        for key in resolved_keys:
            print(f"  {key}  -- {baseline[key]}")
        print()

    if not new_errors:
        print(f"Mypy Audit: no NEW type errors beyond the {len(baseline)}-error baseline.")
        return 0

    print(f"Mypy Audit: {len(new_errors)} NEW type error(s) beyond the {len(baseline)}-error baseline:\n")
    _print_errors(new_errors)
    print(
        "\nEach hit above is either a real new type error to fix, or a baseline that needs "
        "regenerating because unrelated edits shifted line numbers (see the module docstring's "
        "SCOPE & LIMITATIONS section) -- confirm which before assuming it's a regression."
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ci", action="store_true", help="Baseline-gated regression check (what CI runs).")
    args = parser.parse_args()

    return run_ci_check() if args.ci else run_full_report()


if __name__ == "__main__":
    sys.exit(main())
