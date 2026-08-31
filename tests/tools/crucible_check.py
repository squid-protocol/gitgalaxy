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

Also runs two environment-drift checks before every check/update (see
`tests/extraction/how_to_fix_an_extraction_issue.md`'s "known gotchas" section for the full
incident writeups -- both cost real hours on PR #2518, 2026-08-30, chasing phantom diffs that
had nothing to do with the actual code change under test):

    1. Corpus pin drift: warns if the local language-crucible sibling isn't on the tag
       `tests/_crucible_pin.py` names.
    2. Unsafe corpus path: warns if the corpus's own absolute path contains an
       IGNORED_DIRECTORIES name (e.g. "tmp") as ANY path component -- this silently zeroes
       out documentation-coverage scoring for the ENTIRE corpus with no error message.

Also prefers a `uv`-managed Python matching CI's own pin (see `.github/workflows/
golden-crucible.yml`) when building a venv for the first time, rather than whatever `python3`
happens to be running this script -- a version mismatch can resolve different versions of
unpinned optional deps (networkx/pandas/etc.) than CI's cached run did, producing numeric
drift unrelated to your change. Falls back to the current interpreter with a warning if `uv`
isn't available.

Every subprocess that must run as a SPECIFIC venv's python (as opposed to `git`/`uv` calls,
which don't care) goes through `_venv_env()`, which strips `PYTHONPATH` from the inherited
environment. This isn't theoretical: a caller (or a wrapper script) with `PYTHONPATH` set to
this repo's own root -- an easy thing to have set for unrelated reasons, e.g. to make a
one-off `python -c "import some_sibling_module"` work -- makes `import gitgalaxy` resolve
against THAT path instead of whichever venv you actually invoked, silently scanning the wrong
code with no error message. Confirmed to fully explain a run of false leads while building
`scope_check.py`'s two-venv comparison (a wheel-cache-collision theory, a setuptools_scm
worktree-root-detection theory, a `python -c` cwd-shadowing theory -- each plausible, each
fixed, none of which actually mattered) before the real cause turned up: the debugging
session's OWN ad hoc `PYTHONPATH=$PWD python3 -c "..."` one-liners were leaking into every
subprocess they spawned (PR #2518 follow-up, 2026-08-31). See `_venv_env`'s own docstring.

Exits non-zero if any checked mode fails (or if the corpus isn't found), so it's safe to use
as a CI/pre-PR gate directly.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
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


def _venv_env(py: Path) -> dict:
    """Environment for any subprocess that must run AS a specific venv's python (or a
    console-script installed into it, like `galaxyscope`) -- strips `PYTHONPATH` from
    whatever this process' own caller happens to have set, since an inherited `PYTHONPATH`
    entry pointing at a real `gitgalaxy/` package (e.g. this repo's own root) shadows the
    venv's own editable-install finder with NO error message at all (confirmed root cause of
    a real, hours-long chain of false leads -- see this module's own header comment). `PATH`
    is also prepended with the venv's own bin/ so a bare `galaxyscope`/`python` resolves to
    THIS venv first if anything downstream shells out without an absolute path.
    """
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["LANGUAGE_CRUCIBLE_PATH"] = str(CRUCIBLE_PATH)
    env["PATH"] = f"{py.parent}{os.pathsep}{env.get('PATH', '')}"
    return env


def _find_ci_python() -> str:
    """Locate a Python matching CI's own pinned interpreter (parsed straight from
    .github/workflows/golden-crucible.yml's `python-version:` line, so this can't drift out
    of sync with the actual CI config), preferring a `uv`-managed one -- `uv python install`
    is a single ~10s call, versus a manual pyenv/apt dance. Falls back to whichever python is
    currently running this script, with a loud warning: reusing a DIFFERENT Python version has
    produced real, hours-costing phantom drift (unpinned optional deps like networkx/pandas
    resolving a different release than CI's run did) that has nothing to do with the code
    change actually under test -- see PR #2518, 2026-08-30.
    """
    workflow = REPO_ROOT / ".github" / "workflows" / "golden-crucible.yml"
    wanted = "3.11"
    match = re.search(r"python-version:\s*['\"]?(\d+\.\d+)", workflow.read_text()) if workflow.exists() else None
    if match:
        wanted = match.group(1)

    uv = shutil.which("uv")
    if uv:
        found = subprocess.run([uv, "python", "find", wanted], capture_output=True, text=True)
        if found.returncode != 0 or not found.stdout.strip():
            print(f"[env] uv has no Python {wanted} yet -- installing (one-time, ~10s) ...")
            subprocess.run([uv, "python", "install", wanted], check=False)
            found = subprocess.run([uv, "python", "find", wanted], capture_output=True, text=True)
        if found.returncode == 0 and found.stdout.strip():
            return found.stdout.strip()

    current = f"{sys.version_info.major}.{sys.version_info.minor}"
    if current != wanted:
        print(
            f"⚠️  Building venv with Python {current} (this process' own interpreter), not CI's pinned "
            f"{wanted} -- no `uv` on PATH to fetch it. Install: curl -LsSf https://astral.sh/uv/install.sh | sh\n"
            f"   Version drift here has produced real, misleading crucible-audit diffs unrelated to your "
            f"change (unpinned deps resolving differently). If a diff looks huge/unrelated, suspect this first."
        )
    return sys.executable


def _check_corpus_pin() -> None:
    """Warns (never blocks -- someone may have a deliberate reason to point at a different
    ref) if the local corpus isn't on the pinned tag. A stale or wrong-branch sibling
    checkout produces thousands of unrelated diff lines with no error message of its own,
    easily mistaken for a real code regression (confirmed real, PR #2518, 2026-08-30: a
    corpus 20 commits past an old, different tag produced ~4000 phantom diffs)."""
    result = subprocess.run(
        ["git", "-C", str(CRUCIBLE_PATH), "describe", "--tags", "--exact-match"],
        capture_output=True,
        text=True,
    )
    current = result.stdout.strip() if result.returncode == 0 else None
    if current != PINNED_TAG:
        print(
            f"⚠️  language-crucible at {CRUCIBLE_PATH} is on {current or '(not exactly on any tag)'}, not the pinned {PINNED_TAG}."
        )
        print("   This alone can produce thousands of unrelated diff lines against the committed fixtures. Fix:")
        print(f"     git -C {CRUCIBLE_PATH} fetch --tags && git -C {CRUCIBLE_PATH} checkout {PINNED_TAG}")


def _check_unsafe_corpus_path(py: Path) -> None:
    """The corpus's OWN absolute path can silently poison scoring: guidestar_lens.py's
    _calculate_documentation_coverage skips any directory whose FULL path contains an
    IGNORED_DIRECTORIES name as ANY component (not just the immediate directory name) -- so a
    corpus cloned under e.g. /tmp/scratch/language-crucible silently zeroes out
    documentation-coverage for the ENTIRE corpus (every language, not just the one you're
    working on), producing 1000+ phantom diff lines with no error at all (confirmed real, PR
    #2518, 2026-08-30). Queried through the venv's own python so this always reflects the
    ACTUAL current IGNORED_DIRECTORIES set rather than a copy that can drift out of sync.
    """
    resolved = str(CRUCIBLE_PATH.resolve()).lower()
    script = (
        "from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG\n"
        "ignored = {d.lower() for d in APERTURE_CONFIG['IGNORED_DIRECTORIES']}\n"
        f"parts = {resolved!r}.split('/')\n"
        "print(','.join(p for p in parts if p in ignored))\n"
    )
    result = subprocess.run([str(py), "-c", script], cwd=py.parent, env=_venv_env(py), capture_output=True, text=True)
    hits = result.stdout.strip() if result.returncode == 0 else ""
    if hits:
        print(f"⚠️  Corpus path {CRUCIBLE_PATH.resolve()} contains ignored-directory name(s): {hits}")
        print("   This silently zeroes out documentation-coverage scoring repo-wide (every language, not just")
        print("   yours) with no error message. Move the corpus clone somewhere without 'tmp'/'temp'/'cache'/")
        print("   etc. as a path component -- e.g. as a true sibling of this checkout.")


def _editable_install_target(py: Path) -> str | None:
    """Returns what `gitgalaxy.__file__` actually resolves to inside this venv, or None on
    import failure. This is the exact manual check CLAUDE.md's Differential Scan section
    already tells a contributor to run by hand before trusting a venv -- automated here so
    every caller gets it for free instead of finding out the hard way.

    `cwd=py.parent` and `env=_venv_env(py)` are both load-bearing, not belt-and-suspenders:
    `python -c "..."` always puts `''` (the caller's own cwd) at `sys.path[0]`, and inherits
    the caller's full environment (including `PYTHONPATH`) unless told otherwise -- either one
    resolving to a directory/entry containing a real `gitgalaxy/` package shadows THIS venv's
    own editable-install finder with no error message. See this module's own header comment
    for the real incident this traces back to.
    """
    result = subprocess.run(
        [str(py), "-c", "import gitgalaxy; print(gitgalaxy.__file__)"],
        cwd=py.parent,
        env=_venv_env(py),
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def ensure_venv(mode_key: str, repo_root: Path = REPO_ROOT) -> Path:
    """Builds/reuses a venv scoped to `repo_root` (defaults to this checkout). Accepting an
    explicit repo_root -- rather than always using the module-global REPO_ROOT -- lets
    scope_check.py reuse this exact function against a SECOND, temporary worktree (a
    comparison ref like origin/main) without duplicating the venv-build logic, while every
    existing caller in this file keeps its original behavior unchanged (no repo_root passed).

    Verifies (via `_editable_install_target`) that the editable install actually resolves to
    `repo_root` before returning, retrying a few times as cheap insurance against a genuine
    transient issue -- see that function's and this module's header docstrings for the real
    (environment-leak, not install-logic) failure mode this guards against.
    """
    dir_name, extra_deps = MODES[mode_key]
    mode_dir = repo_root / ".crucible_venvs" / dir_name
    py = _venv_python(mode_dir)

    if not py.exists():
        interpreter = _find_ci_python()
        print(f"[{mode_key}] Creating venv at {mode_dir} (first run only, using {interpreter}) ...")
        subprocess.run([interpreter, "-m", "venv", str(mode_dir)], check=True)
        subprocess.run([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"], env=_venv_env(py), check=True)
        # Full (non --no-deps) install once so pyproject.toml's real dependency graph
        # resolves normally, then each mode's extra_deps (see MODES above) layers on
        # top -- PyYAML is a `pip install -e .` extra now (#1104), not a core
        # dependency, so both modes list it explicitly rather than getting it for free.
        subprocess.run([str(py), "-m", "pip", "install", "-q", "-e", str(repo_root)], env=_venv_env(py), check=True)
        if extra_deps:
            subprocess.run([str(py), "-m", "pip", "install", "-q", *extra_deps], env=_venv_env(py), check=True)
        subprocess.run([str(py), "-m", "pip", "install", "-q", "pytest"], env=_venv_env(py), check=True)

    expected = str((repo_root / "gitgalaxy" / "__init__.py").resolve())
    for attempt in range(4):
        # ALWAYS refresh the editable install. --no-deps makes this a ~1-2s no-op resolution,
        # not a full dependency install -- this is the step that prevents the #723 stale-pointer
        # bug this module's own header comment describes.
        subprocess.run(
            [str(py), "-m", "pip", "install", "-e", str(repo_root), "--no-deps", "-q"],
            env=_venv_env(py),
            check=True,
        )
        actual = _editable_install_target(py)
        if actual and Path(actual).resolve() == Path(expected).resolve():
            return py
        print(
            f"⚠️  [{mode_key}] editable install resolved to {actual!r}, expected {expected!r} -- retrying ({attempt + 1}/4) ..."
        )

    raise RuntimeError(
        f"venv at {mode_dir} would not stay pointed at {repo_root} after 4 attempts -- "
        "this venv is not safe to use for a scan; see ensure_venv's own docstring."
    )


def run_check(mode_key: str, py: Path) -> bool:
    result = subprocess.run(
        [str(py), "-m", "pytest", "-m", "golden_crucible", "tests/test_golden_crucible.py", "-q"],
        cwd=REPO_ROOT,
        env=_venv_env(py),
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


def run_update(mode_key: str, py: Path, yes: bool) -> None:
    args = [str(py), str(REPO_ROOT / "tests" / "tools" / "update_golden_master.py")]
    if yes:
        args.append("--yes")
    subprocess.run(args, cwd=REPO_ROOT, env=_venv_env(py), check=False)


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

    _check_corpus_pin()

    mode_keys = ["full", "zero"] if args.mode == "both" else [args.mode]

    if args.update:
        for mode_key in mode_keys:
            py = ensure_venv(mode_key)
            _check_unsafe_corpus_path(py)
            run_update(mode_key, py, args.yes)
        return 0

    results = []
    for mode_key in mode_keys:
        py = ensure_venv(mode_key)
        _check_unsafe_corpus_path(py)
        results.append(run_check(mode_key, py))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
