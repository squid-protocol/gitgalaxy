#!/usr/bin/env python3
"""
One-command wrapper for the three baseline-gated audits (ruff, mypy,
dead-key) plus the zero-tolerance ruff format check.

Why this exists: after any regex/detector.py change, the established workflow
is to run all three `--ci` checks separately, then manually eyeball each
failure to decide "is this a real new finding, or did an earlier edit in the
same file just shift everything below it by N lines" (see each script's own
SCOPE & LIMITATIONS docstring section -- baseline keys embed line numbers,
which aren't stable). That eyeballing is mechanical (same file/code/message,
different line number) and was done by hand, from scratch, on every one of
this session's language passes -- exactly the kind of repeated judgment call
worth automating so it's not re-derived 42+ more times.

USAGE
    python tests/tools/audit_check.py               # run all checks, report
    python tests/tools/audit_check.py --regenerate   # additionally: for any
                                                      # audit whose new
                                                      # findings are ALL pure
                                                      # line-shifts, regenerate
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

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TESTS_DIR = REPO_ROOT / "tests"

# tests/ has no __init__.py anywhere in this repo (see
# tests/extraction/how_to_harden_extraction.md's import-convention note) --
# insert its directory onto sys.path so ruff_audit.py/mypy_audit.py import as
# plain top-level modules, regardless of how this script itself is invoked.
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import mypy_audit  # noqa: E402
import ruff_audit  # noqa: E402


def _identity(key: str, message: str) -> tuple:
    """
    Strips the line number out of a "{file}:{line}: {code}" baseline key,
    leaving (file, code, message) -- the part of a finding's identity that's
    stable across an unrelated line-shift elsewhere in the same file.
    """
    file_part, _, rest = key.partition(":")
    code_part = rest.rsplit(": ", 1)[-1] if ": " in rest else rest
    return (file_part, code_part, message)


def _classify(new: dict, resolved: dict) -> tuple:
    """Splits `new` findings into (pure_shifts, genuine) against `resolved`."""
    resolved_identities = {_identity(k, v) for k, v in resolved.items()}
    shifts, genuine = {}, {}
    for k, v in new.items():
        (shifts if _identity(k, v) in resolved_identities else genuine)[k] = v
    return shifts, genuine


def _report(label: str, new: dict, resolved: dict, baseline_path: Path, regenerate: bool, current: dict) -> bool:
    if not new:
        return True

    shifts, genuine = _classify(new, resolved)
    if shifts:
        print(f"[{label}] {len(shifts)} finding(s) look like pure line-shifts (same file/code/message, moved):")
        for k, v in sorted(shifts.items()):
            print(f"    {k}  -- {v}")
    if genuine:
        print(f"[{label}] {len(genuine)} finding(s) need real review (no matching baseline entry by message):")
        for k, v in sorted(genuine.items()):
            print(f"    {k}  -- {v}")

    if regenerate and not genuine:
        with open(baseline_path, "w") as baseline_file:
            json.dump(current, baseline_file, indent=2, sort_keys=True)
        print(f"[{label}] Regenerated baseline ({len(current)} findings, all were pure line-shifts).")
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


def main() -> int:
    regenerate = "--regenerate" in sys.argv[1:]

    results = {
        "ruff": check_ruff(regenerate),
        "mypy": check_mypy(regenerate),
        "dead-key": check_dead_key(),
    }

    print()
    if all(results.values()):
        print("audit_check: all clear.")
        return 0

    failing = [name for name, ok in results.items() if not ok]
    print(f"audit_check: {', '.join(failing)} need attention (see above).")
    if not regenerate:
        print("Re-run with --regenerate to auto-fix any that are pure line-shifts.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
