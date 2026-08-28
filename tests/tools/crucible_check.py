#!/usr/bin/env python3
"""
One-command wrapper for the Golden Crucible verification workflow.

Why this exists: verifying golden_crucible correctly requires TWO purpose-built venvs
(zero-dependency and full-precision), and each one's `pip install -e .` must be scoped to
whichever checkout/worktree you're actually running from. Reusing a venv whose editable
install points at a *different* checkout silently scans the WRONG code -- `galaxyscope` is
invoked as a subprocess, so it resolves `gitgalaxy` via the venv's editable-install pointer,
not via the calling process's cwd. This is a confirmed root cause (2026-07-28, PR #723): a
long-lived personal venv's editable install pointed at the main checkout, so golden_crucible
silently scanned pre-fix code from `main` while running inside a PR worktree and reported a
false "zero diff" pass, which CI then correctly caught as a real failure. Building the two
venvs by hand each time is exactly the manual, error-prone, expensive-in-tokens dance this
script replaces with one call.

Usage:
    python tests/tools/crucible_check.py                  # check both modes, compact report
    python tests/tools/crucible_check.py --mode full       # just full-precision
    python tests/tools/crucible_check.py --mode zero       # just zero-dependency
    python tests/tools/crucible_check.py --update          # regenerate (bless) fixtures, interactive
    python tests/tools/crucible_check.py --update --yes    # bless without prompting (CI/agent use)

Venvs are cached at .crucible_venvs/{full_precision,zero_dependency} INSIDE the current
checkout (so each worktree gets its own venv -- they are never shared across worktrees,
which is what makes this safe). Every invocation re-runs a fast, no-dependency-resolution
`pip install -e . --no-deps` before use, so the editable pointer can never go stale even if
the venv directory is reused across branches/rebases within the same worktree.

Exits non-zero if any checked mode fails (or if the corpus isn't found), so it's safe to use
as a CI/pre-PR gate directly.
"""

import argparse
import os
import subprocess
import sys
import venv as venv_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _crucible_pin import PINNED_TAG

REPO_ROOT = Path(__file__).parent.parent.parent
VENV_BASE = REPO_ROOT / ".crucible_venvs"
CRUCIBLE_PATH = Path(os.environ.get("LANGUAGE_CRUCIBLE_PATH", REPO_ROOT.parent / "language-crucible"))

# mode key -> (venv dir name, extra deps beyond the bare editable install)
#
# PyYAML is in BOTH modes' list, not just "full": since #1104 it's an optional
# extra (`gitgalaxy[yaml]`), not a core pyproject.toml dependency, so a bare
# `pip install -e .` no longer pulls it in for either venv. "zero-dependency"
# here has only ever meant the optional networkx/tiktoken/pandas/xgboost stack
# is absent -- the golden-master zero-dep fixture (tests/golden_master_zero_dep_audit.json)
# expects PyYAML present even in that mode ("pyyaml": false, i.e. NOT missing).
MODES = {
    "full": ("full_precision", ["PyYAML", "networkx", "tiktoken", "pandas", "xgboost"]),
    "zero": ("zero_dependency", ["PyYAML"]),
}


def _venv_python(mode_dir: Path) -> Path:
    return mode_dir / "bin" / "python"


def ensure_venv(mode_key: str) -> Path:
    dir_name, extra_deps = MODES[mode_key]
    mode_dir = VENV_BASE / dir_name
    py = _venv_python(mode_dir)

    if not py.exists():
        print(f"[{mode_key}] Creating venv at {mode_dir} (first run only) ...")
        venv_module.create(mode_dir, with_pip=True)
        subprocess.run([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"], check=True)
        # Full (non --no-deps) install once so pyproject.toml's real dependency graph
        # resolves normally, then each mode's extra_deps (see MODES above) layers on
        # top -- PyYAML is a `pip install -e .` extra now (#1104), not a core
        # dependency, so both modes list it explicitly rather than getting it for free.
        subprocess.run([str(py), "-m", "pip", "install", "-q", "-e", str(REPO_ROOT)], check=True)
        if extra_deps:
            subprocess.run([str(py), "-m", "pip", "install", "-q", *extra_deps], check=True)
        subprocess.run([str(py), "-m", "pip", "install", "-q", "pytest"], check=True)

    # ALWAYS refresh the editable install. --no-deps makes this a ~1-2s no-op resolution,
    # not a full dependency install -- this is the step that prevents the stale-pointer bug.
    subprocess.run(
        [str(py), "-m", "pip", "install", "-e", str(REPO_ROOT), "--no-deps", "-q"],
        check=True,
    )
    return py


def _env_for(py: Path) -> dict:
    return {
        **os.environ,
        "LANGUAGE_CRUCIBLE_PATH": str(CRUCIBLE_PATH),
        "PATH": f"{py.parent}{os.pathsep}{os.environ.get('PATH', '')}",
    }


def run_check(mode_key: str) -> bool:
    py = ensure_venv(mode_key)
    result = subprocess.run(
        [str(py), "-m", "pytest", "-m", "golden_crucible", "tests/test_golden_crucible.py", "-q"],
        cwd=REPO_ROOT,
        env=_env_for(py),
        capture_output=True,
        text=True,
        timeout=300,
    )
    passed = result.returncode == 0
    label = MODES[mode_key][0]
    if passed:
        print(f"✅ {label}: PASS")
    else:
        print(f"❌ {label}: FAIL")
        # The galaxyscope subprocess spawned INSIDE the test emits its own verbose
        # INFO/WARNING logging, which drowns out the actual diff in a blind tail. Find
        # pytest.fail()'s own "Structural drift detected" message (already capped at 50
        # diff lines by the test itself) instead of guessing how many lines to keep.
        combined = result.stdout + result.stderr
        marker = "Structural drift detected"
        idx = combined.find(marker)
        if idx != -1:
            print(combined[idx : idx + 4000])
        else:
            print("\n".join(combined.splitlines()[-40:]))
    return passed


def run_update(mode_key: str, yes: bool) -> None:
    py = ensure_venv(mode_key)
    args = [str(py), str(REPO_ROOT / "tests" / "tools" / "update_golden_master.py")]
    if yes:
        args.append("--yes")
    subprocess.run(args, cwd=REPO_ROOT, env=_env_for(py), check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["full", "zero", "both"], default="both")
    parser.add_argument(
        "--update", action="store_true", help="Regenerate (bless) the fixture(s) instead of just checking."
    )
    parser.add_argument("--yes", action="store_true", help="Skip update_golden_master.py's confirmation prompt.")
    args = parser.parse_args()

    if not (CRUCIBLE_PATH / "data").exists():
        print(f"❌ language-crucible corpus not found at {CRUCIBLE_PATH}.")
        print(f"   Clone squid-protocol/language-crucible (pinned to {PINNED_TAG}) as a sibling directory,")
        print("   or set LANGUAGE_CRUCIBLE_PATH, then re-run.")
        return 1

    mode_keys = ["full", "zero"] if args.mode == "both" else [args.mode]

    if args.update:
        for mode_key in mode_keys:
            run_update(mode_key, args.yes)
        return 0

    results = [run_check(mode_key) for mode_key in mode_keys]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
