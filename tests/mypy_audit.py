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
                                         # anything.
    python tests/mypy_audit.py --write-baseline
                                         # regenerate mypy_audit_baseline.json
                                         # from the current errors (e.g. after
                                         # a cleanup PR).
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
make yourself (`--write-baseline`) (same "deliberate, reviewable updates instead of silent
overwrite" philosophy as #330's golden_master.json and dead_key_audit.py's
own baseline), not something this script does automatically. `--ci` prints
anything it notices has already been fixed as an FYI, so the baseline
doesn't silently go stale, but does not fail the build over it.

BASELINE KEYS (#3384)
Keys are content-based, NOT line-based, using the same scheme as
ruff_audit.py (see tests/lint_baseline.py):
`{file}: {code} @{hash of the whitespace-stripped source line}#{occurrence}`.
An unrelated edit that only shifts lines leaves the baseline unchanged;
editing the flagged line itself, or adding another identical erroring line
in the same file, is a new key and still fails `--ci`. The per-(file, code,
line-hash) occurrence index also means several errors of the same code on
one line are each their own entry now, instead of collapsing into one the
way the old `{file}:{line}: {code}` key did (5 lines in the initial 235-error
baseline carried 2-4 each), so partial progress on such a line is visible.
Human-readable output still prints each current error's line number.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# tests/ has no __init__.py -- make the sibling helper importable no matter how
# this file is loaded (script, audit_check.py, or a test's sys.path insert).
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import lint_baseline

Finding = lint_baseline.Finding

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_ROOT = REPO_ROOT / "gitgalaxy"
BASELINE_PATH = Path(__file__).resolve().parent / "mypy_audit_baseline.json"

# Matches mypy's normal text output, e.g.:
#   gitgalaxy/galaxyscope.py:70: error: Module has no attribute "util"  [attr-defined]
_ERROR_LINE = re.compile(r"^(?P<file>[^:]+):(?P<line>\d+): error: (?P<message>.+?)\s*\[(?P<code>[a-z][a-z0-9-]*)\]$")


def parse_mypy_output(stdout: str, repo_root: Path) -> dict[str, Finding]:
    """Turns mypy's text output into {content key: Finding}."""
    findings = []
    for line in stdout.splitlines():
        match = _ERROR_LINE.match(line)
        if not match:
            continue
        findings.append(
            Finding(
                file=Path(match["file"]).as_posix(),
                line=int(match["line"]),
                column=0,
                code=match["code"],
                message=match["message"],
            )
        )
    return lint_baseline.key_findings(findings, lint_baseline.source_reader(repo_root))


def run_mypy_findings() -> dict[str, Finding]:
    """Returns {content key: Finding} for every error mypy reports."""
    result = subprocess.run(
        ["mypy", str(SCAN_ROOT), "--ignore-missing-imports"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return parse_mypy_output(result.stdout, REPO_ROOT)


def run_mypy() -> dict[str, str]:
    """Returns {content key: message} -- the committed baseline's shape."""
    return lint_baseline.to_baseline(run_mypy_findings())


def load_baseline() -> dict[str, str]:
    return lint_baseline.load_baseline(BASELINE_PATH)


def _print_findings(findings: dict[str, Finding]) -> None:
    for key, finding in sorted(findings.items(), key=lambda kv: (kv[1].file, kv[1].line, kv[0])):
        print(f"  {lint_baseline.describe(key, finding)}")


def run_full_report() -> int:
    findings = run_mypy_findings()
    if not findings:
        print("Mypy Audit: no errors found.")
        return 0

    print(f"Mypy Audit: {len(findings)} error(s) found:\n")
    _print_findings(findings)
    print(
        "\nTo accept this as the new baseline (e.g. after a cleanup PR), regenerate it with:\n"
        "  python tests/mypy_audit.py --write-baseline"
    )
    return 1


def write_current_baseline() -> int:
    baseline = run_mypy()
    lint_baseline.write_baseline(BASELINE_PATH, baseline)
    print(f"Mypy Audit: wrote {len(baseline)}-error baseline to {BASELINE_PATH.relative_to(REPO_ROOT)}.")
    return 0


def run_ci_check() -> int:
    """
    Baseline-gated regression check (#430): fails only on errors NOT already
    in mypy_audit_baseline.json. See the module docstring's BASELINE section
    for why this isn't a zero-tolerance check.
    """
    findings = run_mypy_findings()
    baseline = load_baseline()

    new_findings = {key: f for key, f in findings.items() if key not in baseline}
    resolved_keys = sorted(set(baseline) - set(findings))

    if resolved_keys:
        print(
            "Mypy Audit: FYI -- these baselined errors are no longer flagged (fixed, or the flagged line was edited)."
        )
        print("Consider removing them from mypy_audit_baseline.json in this PR (`--write-baseline`):\n")
        for key in resolved_keys:
            print(f"  {key}  -- {baseline[key]}")
        print()

    if not new_findings:
        print(f"Mypy Audit: no NEW type errors beyond the {len(baseline)}-error baseline.")
        return 0

    print(f"Mypy Audit: {len(new_findings)} NEW type error(s) beyond the {len(baseline)}-error baseline:\n")
    _print_findings(new_findings)
    print(
        "\nBaseline keys are content-based (see the module docstring's BASELINE KEYS section), so a "
        "pure line shift can't cause these: each is a new error, a new duplicate of a baselined "
        "line, or an edit to a baselined line. Fix it, or -- only if it's pre-existing debt you "
        "deliberately carry -- re-bless with `python tests/mypy_audit.py --write-baseline` (in "
        "mypy-audit.yml's environment, see IMPORTANT above)."
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ci", action="store_true", help="Baseline-gated regression check (what CI runs).")
    parser.add_argument(
        "--write-baseline", action="store_true", help="Regenerate mypy_audit_baseline.json from current errors."
    )
    args = parser.parse_args()

    if args.write_baseline:
        return write_current_baseline()
    return run_ci_check() if args.ci else run_full_report()


if __name__ == "__main__":
    sys.exit(main())
