#!/usr/bin/env python3
"""
One-command wrapper for the four baseline-gated audits (ruff, mypy,
dead-key, ast-accuracy) plus the zero-tolerance ruff format check.

Why this exists: after any regex/detector.py change, the established workflow
was to run all three `--ci` checks separately, then eyeball each failure to
decide whether it was a real new finding or an unrelated line shift.

Since #3384, ruff/mypy baseline keys are content-based
(`{file}: {code} @{line-hash}#{occurrence}`, see tests/lint_baseline.py), so a
pure line shift no longer changes any key at all -- there is nothing to
regenerate for it. What's left for `--regenerate` to recognise mechanically is
an EDITED baselined line: a new key whose (file, code, message) exactly matches
a now-stale baseline entry (e.g. the flagged line was reformatted or touched,
but the same pre-existing finding is still there). Matching is one-for-one, so
a genuinely new duplicate on top of the old finding is still "genuine".

USAGE
    python tests/tools/audit_check.py               # run all checks, report
    python tests/tools/audit_check.py --regenerate   # additionally: for any
                                                      # audit whose new
                                                      # findings ALL pair
                                                      # one-for-one with a
                                                      # stale entry (same file/
                                                      # code/message), regenerate
                                                      # its baseline automatically.
                                                      # Audits with a genuine
                                                      # new finding are left
                                                      # untouched and still
                                                      # fail the run -- this
                                                      # never silently accepts
                                                      # a real regression.

Exits non-zero if anything needs attention after --regenerate is applied (or
always, without it), so it's safe to use as a pre-PR gate.
"""

import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TESTS_DIR = REPO_ROOT / "tests"

# tests/ has no __init__.py anywhere in this repo (see
# tests/extraction/how_to_harden_extraction.md's import-convention note) --
# insert its directory onto sys.path so ruff_audit.py/mypy_audit.py import as
# plain top-level modules, regardless of how this script itself is invoked.
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import lint_baseline  # noqa: E402
import mypy_audit  # noqa: E402
import ruff_audit  # noqa: E402


def _identity(key: str, message: str) -> tuple:
    """
    (file, code, message) of a content key (tests/lint_baseline.py) -- the part
    of a finding's identity that survives an edit to the flagged line itself.
    """
    file_part, code_part, _digest, _occurrence = lint_baseline.parse_key(key)
    return (file_part, code_part, message)


def _classify(new: dict, resolved: dict) -> tuple:
    """Splits `new` findings into (edited_lines, genuine), pairing each new
    finding with at most ONE stale entry of the same identity (multiset match),
    so N+1 identical findings against N stale entries still leaves one genuine."""
    available = Counter(_identity(k, v) for k, v in resolved.items())
    edited, genuine = {}, {}
    for k, v in sorted(new.items()):
        ident = _identity(k, v)
        if available[ident] > 0:
            available[ident] -= 1
            edited[k] = v
        else:
            genuine[k] = v
    return edited, genuine


def _report(label: str, new: dict, resolved: dict, baseline_path: Path, regenerate: bool, current: dict) -> bool:
    if not new:
        return True

    edited, genuine = _classify(new, resolved)
    if edited:
        print(
            f"[{label}] {len(edited)} finding(s) look like an edited baselined line "
            "(same file/code/message as a now-stale entry):"
        )
        for k, v in sorted(edited.items()):
            print(f"    {k}  -- {v}")
    if genuine:
        print(f"[{label}] {len(genuine)} finding(s) need real review (no matching stale baseline entry):")
        for k, v in sorted(genuine.items()):
            print(f"    {k}  -- {v}")

    if regenerate and not genuine:
        lint_baseline.write_baseline(baseline_path, current)
        print(f"[{label}] Regenerated baseline ({len(current)} findings, all new keys were edited baselined lines).")
        return True

    return False


def check_ruff(regenerate: bool) -> bool:
    format_ok = ruff_audit.run_ruff_format_check()
    if not format_ok:
        print("[ruff] FAIL -- formatting is not clean (zero-tolerance; run `ruff format .` to fix).")

    current = ruff_audit.run_ruff_check()
    baseline = ruff_audit.load_baseline()
    new = {k: v for k, v in current.items() if k not in baseline}
    resolved = {k: v for k, v in baseline.items() if k not in current}

    lint_ok = _report("ruff", new, resolved, ruff_audit.BASELINE_PATH, regenerate, current)
    if lint_ok and not new:
        print(f"[ruff] OK -- {len(baseline)}-finding baseline, format clean." if format_ok else "")
    return format_ok and lint_ok


def check_mypy(regenerate: bool) -> bool:
    current = mypy_audit.run_mypy()
    baseline = mypy_audit.load_baseline()
    new = {k: v for k, v in current.items() if k not in baseline}
    resolved = {k: v for k, v in baseline.items() if k not in current}

    ok = _report("mypy", new, resolved, mypy_audit.BASELINE_PATH, regenerate, current)
    if ok and not new:
        print(f"[mypy] OK -- {len(baseline)}-error baseline.")
    return ok


def check_dead_key() -> bool:
    """
    No shift-auto-detection for this one (different data shape than
    ruff/mypy's flat key->message dict, and this audit has stayed clean
    throughout the epic so far -- add shift-detection here if that changes).
    """
    result = subprocess.run(
        [sys.executable, str(TESTS_DIR / "dead_key_audit.py"), "--ci"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    ok = result.returncode == 0
    print("[dead-key] OK" if ok else "[dead-key] FAIL -- see details below:")
    if not ok:
        print(result.stdout)
    return ok


def check_ast_accuracy() -> bool:
    """
    Numeric-metric regression gate (#1200), not a per-finding dict --
    no line-shift auto-detection applies here (there are no line numbers in
    the baseline at all). Run as a subprocess, same as check_dead_key(),
    since it needs its own corpus-extraction/galaxyscope-subprocess
    machinery rather than a simple importable function.
    """
    result = subprocess.run(
        [sys.executable, str(TESTS_DIR / "ast_accuracy_audit.py"), "--ci"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    ok = result.returncode == 0
    print(f"[ast-accuracy] {result.stdout.strip()}" if ok else "[ast-accuracy] FAIL -- see details below:")
    if not ok:
        print(result.stdout)
        print(result.stderr)
    return ok


def main() -> int:
    regenerate = "--regenerate" in sys.argv[1:]

    results = {
        "ruff": check_ruff(regenerate),
        "mypy": check_mypy(regenerate),
        "dead-key": check_dead_key(),
        "ast-accuracy": check_ast_accuracy(),
    }

    print()
    if all(results.values()):
        print("audit_check: all clear.")
        return 0

    failing = [name for name, ok in results.items() if not ok]
    print(f"audit_check: {', '.join(failing)} need attention (see above).")
    if not regenerate:
        print("Re-run with --regenerate to auto-accept edited baselined lines (never genuine new findings).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
