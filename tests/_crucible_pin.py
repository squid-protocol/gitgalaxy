r"""
Thin wrapper over tests/crucible_pins.toml ([language]): `PINNED_TAG` is the language-crucible tag
GitGalaxy's golden masters and accuracy audits are measured at. The value lives ONLY in the
manifest; bump it with `python tests/tools/crucible_pins.py bump language <tag>` (RELEASING.md of
language-crucible: regenerate the golden masters first, then bump the pin).

Workflows read it with `python3 gitgalaxy/tests/tools/crucible_pins.py get language`, which works
on a pull_request from a fork too. The `LANGUAGE_CRUCIBLE_REF` repository variable is no longer an
input to any workflow; `crucible_pins.py check` warns when it differs from the manifest.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _crucible_manifest import entry  # noqa: E402

_PIN = entry("language")

PINNED_TAG = _PIN["ref"]

PATH_ENV = _PIN["path_env"]

ALLOW_UNPINNED_ENV = _PIN["allow_unpinned_env"]


def pin_mismatch(crucible_path):
    """Returns None when the language-crucible checkout at `crucible_path` is on
    PINNED_TAG, else an actionable message ending in the exact commands that fix
    it (#3386). A stale checkout produces thousands of phantom golden-master
    diffs with no error of its own (PR #2518), so callers fail on this rather
    than warn. Compares commits, not tag names, so any tag pointing at the pinned
    commit passes. Returns None for a checkout that isn't a git repo (e.g. an
    unpacked release archive) or when ALLOW_UNPINNED_ENV is set to 1.
    """
    import os
    import subprocess
    from pathlib import Path

    if os.environ.get(ALLOW_UNPINNED_ENV) == "1":
        return None
    path = Path(crucible_path)

    def rev(ref):
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    if not (path / ".git").exists():
        return None
    head, pinned = rev("HEAD"), rev(PINNED_TAG)
    if head and head == pinned:
        return None
    described = subprocess.run(
        ["git", "-C", str(path), "describe", "--tags", "--always"], capture_output=True, text=True
    ).stdout.strip()
    return (
        f"language-crucible at {path} is on {described or 'an unknown commit'}, but CI pins {PINNED_TAG} "
        f"(tests/_crucible_pin.py). An off-pin corpus yields thousands of unrelated golden-master diffs.\n"
        f"Fix: git -C {path} fetch --tags origin && git -C {path} checkout {PINNED_TAG}\n"
        f"(Deliberately off-pin? Set {ALLOW_UNPINNED_ENV}=1.)"
    )
