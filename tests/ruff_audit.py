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
                                         # finds anything.
    python tests/ruff_audit.py --write-baseline
                                         # regenerate ruff_audit_baseline.json
                                         # from the current findings (e.g.
                                         # after a cleanup PR).
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
This repo had 241 pre-existing lint findings across 27 rule families the
day this check was wired into CI, measured AFTER a one-time
`ruff check --fix` (+ `--unsafe-fixes` for the PEP 585 typing
modernization specifically) and `ruff format` pass across the whole
repo (see ruff_audit_baseline.json, and #469 for the adoption PR).
`--ci` mode is a REGRESSION gate: it fails only on findings not already
in the baseline. Fixing a baselined finding doesn't fail the build
either -- shrinking the baseline is a deliberate, reviewable edit you
make yourself (`--write-baseline`), not something `--ci` does
automatically. `--ci` prints anything it notices has already been fixed
as an FYI, so the baseline doesn't silently go stale, but does not fail
the build over it.

BASELINE KEYS (#3384)
Keys are content-based, NOT line-based:
`{file}: {code} @{hash of the whitespace-stripped source line}#{occurrence}`
-- see tests/lint_baseline.py for the full scheme. An unrelated edit that
only shifts lines leaves every key (and so the baseline file) unchanged,
so the baseline no longer conflicts on rebase just because a sibling PR
moved code around. Editing the flagged line itself, or adding another
identical violating line in the same file (a new `#N` occurrence), IS a
new key and still fails `--ci`. Human-readable output still prints each
current finding's line number.
"""

import argparse
import json
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
BASELINE_PATH = Path(__file__).resolve().parent / "ruff_audit_baseline.json"


def parse_ruff_json(stdout: str, repo_root: Path) -> dict[str, Finding]:
    """Turns `ruff check --output-format=json` output into {content key: Finding}."""
    findings = []
    for item in json.loads(stdout or "[]"):
        rel_path = Path(item["filename"]).resolve().relative_to(repo_root).as_posix()
        location = item.get("location") or {}
        findings.append(
            Finding(
                file=rel_path,
                line=int(location.get("row") or 0),
                column=int(location.get("column") or 0),
                code=str(item.get("code")),
                message=item["message"],
            )
        )
    return lint_baseline.key_findings(findings, lint_baseline.source_reader(repo_root))


def run_ruff_findings(scan_root: Path = SCAN_ROOT, repo_root: Path = REPO_ROOT) -> dict[str, Finding]:
    """Returns {content key: Finding} for every lint finding ruff reports."""
    result = subprocess.run(
        ["ruff", "check", str(scan_root), "--output-format=json"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    return parse_ruff_json(result.stdout, repo_root)


def run_ruff_check() -> dict[str, str]:
    """Returns {content key: message} -- the committed baseline's shape."""
    return lint_baseline.to_baseline(run_ruff_findings())


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


def load_baseline() -> dict[str, str]:
    return lint_baseline.load_baseline(BASELINE_PATH)


def _print_findings(findings: dict[str, Finding]) -> None:
    for key, finding in sorted(findings.items(), key=lambda kv: (kv[1].file, kv[1].line, kv[1].column, kv[0])):
        print(f"  {lint_baseline.describe(key, finding)}")


def run_full_report() -> int:
    findings = run_ruff_findings()
    if not findings:
        print("Ruff Audit: no lint findings.")
        return 0

    print(f"Ruff Audit: {len(findings)} finding(s):\n")
    _print_findings(findings)
    print(
        "\nTo accept this as the new baseline (e.g. after a cleanup PR), regenerate it with:\n"
        "  python tests/ruff_audit.py --write-baseline"
    )
    return 1


def write_current_baseline() -> int:
    baseline = run_ruff_check()
    lint_baseline.write_baseline(BASELINE_PATH, baseline)
    print(f"Ruff Audit: wrote {len(baseline)}-finding baseline to {BASELINE_PATH.relative_to(REPO_ROOT)}.")
    return 0


def compare(findings: dict[str, Finding], baseline: dict[str, str]):
    """Returns (new findings not in the baseline, sorted stale baseline keys no longer flagged)."""
    new_findings = {key: f for key, f in findings.items() if key not in baseline}
    resolved_keys = sorted(set(baseline) - set(findings))
    return new_findings, resolved_keys


def run_ci_check() -> int:
    """
    Baseline-gated regression check (#469) for lint, plus a zero-tolerance
    format check. See the module docstring's BASELINE section for why lint
    isn't a zero-tolerance check the way format is.
    """
    format_ok = run_ruff_format_check()
    if not format_ok:
        print("Ruff Audit: files are not `ruff format`-compliant (zero-tolerance -- run `ruff format` locally).")

    findings = run_ruff_findings()
    baseline = load_baseline()
    new_findings, resolved_keys = compare(findings, baseline)

    if resolved_keys:
        print(
            "Ruff Audit: FYI -- these baselined findings are no longer flagged (fixed, or the flagged line was edited)."
        )
        print("Consider removing them from ruff_audit_baseline.json in this PR (`--write-baseline`):\n")
        for key in resolved_keys:
            print(f"  {key}  -- {baseline[key]}")
        print()

    if not new_findings:
        print(f"Ruff Audit: no NEW lint findings beyond the {len(baseline)}-finding baseline.")
        return 0 if format_ok else 1

    print(f"Ruff Audit: {len(new_findings)} NEW lint finding(s) beyond the {len(baseline)}-finding baseline:\n")
    _print_findings(new_findings)
    print(
        "\nBaseline keys are content-based (see the module docstring's BASELINE KEYS section), so a "
        "pure line shift can't cause these: each is a new finding, a new duplicate of a baselined "
        "line, or an edit to a baselined line. Fix it, or -- only if it's pre-existing debt you "
        "deliberately carry -- re-bless with `python tests/ruff_audit.py --write-baseline`."
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ci", action="store_true", help="Baseline-gated regression check (what CI runs).")
    parser.add_argument(
        "--write-baseline", action="store_true", help="Regenerate ruff_audit_baseline.json from current findings."
    )
    args = parser.parse_args()

    if args.write_baseline:
        return write_current_baseline()
    return run_ci_check() if args.ci else run_full_report()


if __name__ == "__main__":
    sys.exit(main())
