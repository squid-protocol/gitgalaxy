#!/usr/bin/env python3
"""
Ruff Audit (#469)

Runs `ruff check gitgalaxy/` and gates the result against a committed
baseline, so CI enforces "no new lint findings" without demanding the
pre-existing backlog be fixed first. Same baseline-gated shape as
tests/mypy_audit.py (#430) and tests/dead_key_audit.py (#325) -- see
those for the "why a regression gate, not zero-tolerance" rationale;
it's identical here.

Also runs `ruff format --check`, which is NOT baseline-gated: the whole
repo was reformatted once when this was adopted (#469), so formatting
is a zero-tolerance floor from that point on -- there's no backlog to
carry forward, and letting formatting drift would just mean redoing
the same one-time cleanup later.

USAGE
    python tests/ruff_audit.py          # full report, exits 1 if ruff
                                         # finds anything -- use this to
                                         # regenerate the baseline after
                                         # a cleanup PR.
    python tests/ruff_audit.py --ci     # baseline-gated regression check
                                         # (see BASELINE below) plus the
                                         # zero-tolerance format check --
                                         # this is what CI runs.

RULE SELECTION
See pyproject.toml's [tool.ruff.lint] `select` list for the full set and
the comment above it for why each family was included/excluded --
briefly: this is a deliberately scoped selection (bugbear, pyflakes,
security/bandit, simplify, comprehensions, isort, pyupgrade, etc.), not
`ALL`. BLE/TRY/D/T20/G were measured and excluded because they
overwhelmingly flagged this codebase's deliberate design choices
(broad `except Exception:` fault isolation, prose docstrings, CLI
`print()` output, f-string logging) rather than real issues. E501
(line-too-long) is also excluded -- it was already explicitly ignored
in the old .flake8 config, and at 464 of the initial 705 raw findings,
it would have drowned out every other rule family's signal.

BASELINE
This repo had 241 pre-existing lint findings (240 unique baseline keys
-- two share a `{file}:{line}: {code}` key, same rare-but-accepted
collision mypy_audit.py's docstring already documents) across 27 rule
families the day this check was wired into CI, measured AFTER a one-time
`ruff check --fix` (+ `--unsafe-fixes` for the PEP 585 typing
modernization specifically) and `ruff format` pass across the whole
repo (see ruff_audit_baseline.json, and #469 for the adoption PR).
`--ci` mode is a REGRESSION gate: it fails only on findings not already
in the baseline. Fixing a baselined finding doesn't fail the build
either -- shrinking the baseline is a deliberate, reviewable edit you
make yourself, not something this script does automatically. `--ci`
prints anything it notices has already been fixed as an FYI, so the
baseline doesn't silently go stale, but does not fail the build over it.

SCOPE & LIMITATIONS (read before treating the baseline as static)
Baseline keys are `{file}:{line}: {code}`. Line numbers are NOT stable
-- an unrelated edit earlier in a file shifts every finding below it,
which will look like "N new findings" even though nothing lint-relevant
changed. Same accepted tradeoff as mypy_audit.py's baseline. If a PR
that didn't touch lint-relevant code trips `--ci`, regenerate the
baseline (`python tests/ruff_audit.py` and copy its output into
ruff_audit_baseline.json) rather than treating it as a real regression.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_ROOT = REPO_ROOT / "gitgalaxy"
BASELINE_PATH = Path(__file__).resolve().parent / "ruff_audit_baseline.json"


def run_ruff_check() -> Dict[str, str]:
    """Returns {"{file}:{line}: {code}": message} for every lint finding ruff reports."""
    result = subprocess.run(
        ["ruff", "check", str(SCAN_ROOT), "--output-format=json"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    errors: Dict[str, str] = {}
    for item in json.loads(result.stdout or "[]"):
        rel_path = Path(item["filename"]).resolve().relative_to(REPO_ROOT).as_posix()
        key = f"{rel_path}:{item['location']['row']}: {item['code']}"
        errors[key] = item["message"]
    return errors


def run_ruff_format_check() -> bool:
    """Returns True if every file already matches `ruff format`'s output (zero-tolerance, not baselined)."""
    result = subprocess.run(
        ["ruff", "format", str(SCAN_ROOT), "--check"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
    return result.returncode == 0


def load_baseline() -> Dict[str, str]:
    if not BASELINE_PATH.exists():
        return {}
    with open(BASELINE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _print_errors(errors: Dict[str, str]) -> None:
    for key in sorted(errors):
        print(f"  {key}  -- {errors[key]}")


def run_full_report() -> int:
    errors = run_ruff_check()
    if not errors:
        print("Ruff Audit: no lint findings.")
        return 0

    print(f"Ruff Audit: {len(errors)} finding(s):\n")
    _print_errors(errors)
    print(
        "\nTo accept this as the new baseline (e.g. after a cleanup PR), regenerate it with:\n"
        '  python -c "from tests.ruff_audit import run_ruff_check; import json; '
        'json.dump(run_ruff_check(), open(\'tests/ruff_audit_baseline.json\', \'w\'), indent=2, sort_keys=True)"'
    )
    return 1


def run_ci_check() -> int:
    """
    Baseline-gated regression check (#469) for lint, plus a zero-tolerance
    format check. See the module docstring's BASELINE section for why lint
    isn't a zero-tolerance check the way format is.
    """
    format_ok = run_ruff_format_check()
    if not format_ok:
        print("Ruff Audit: files are not `ruff format`-compliant (zero-tolerance -- run `ruff format` locally).")

    errors = run_ruff_check()
    baseline = load_baseline()

    new_errors = {key: msg for key, msg in errors.items() if key not in baseline}
    resolved_keys = sorted(set(baseline) - set(errors))

    if resolved_keys:
        print("Ruff Audit: FYI -- these baselined findings are no longer flagged (fixed, or line-shifted).")
        print("Consider removing them from ruff_audit_baseline.json in this PR:\n")
        for key in resolved_keys:
            print(f"  {key}  -- {baseline[key]}")
        print()

    if not new_errors:
        print(f"Ruff Audit: no NEW lint findings beyond the {len(baseline)}-finding baseline.")
        return 0 if format_ok else 1

    print(f"Ruff Audit: {len(new_errors)} NEW lint finding(s) beyond the {len(baseline)}-finding baseline:\n")
    _print_errors(new_errors)
    print(
        "\nEach hit above is either a real new lint finding to fix, or a baseline that needs "
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
