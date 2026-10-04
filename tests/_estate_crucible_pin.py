r"""
Single source of truth for "which estate-crucible commit does GitGalaxy's estate scorer
(tests/tools/estate_crucible.py, #4317) measure against".

estate-crucible (squid-protocol/estate-crucible) is a synthetic z/OS estate whose answer key is
written by the same generator that writes the code (format `estate-crucible-key/1`, its README).
Every planted "horror" carries the IBM citation for what its key asserts. The scorer scans the
estate, reads the master DB through GalaxyIR, and diffs every fact channel against the key.

Like tests/_cics_crucible_pin.py there is deliberately NO GitHub Actions repository variable:
when the scorer becomes a CI gate (phase 5 of #4317), the workflow reads PINNED_REF straight
out of this file with

    sed -n 's/^PINNED_REF = "\(.*\)"/\1/p' gitgalaxy/tests/_estate_crucible_pin.py

so **keep the assignment below on one line, in exactly that literal form.**

The ref is a release tag of the crucible (its RELEASING.md). To move it: check the crucible out
at the new tag, run `python tests/tools/estate_crucible.py`, and commit the pin with the
scorecard it prints (in the PR body) in one PR.

Local runs find the checkout through the `ESTATE_CRUCIBLE_PATH` environment variable, else
`../estate-crucible` beside the main gitgalaxy checkout.
"""

PINNED_REF = "v0.3.0"

# Where a local checkout lives when not beside the main gitgalaxy checkout.
PATH_ENV = "ESTATE_CRUCIBLE_PATH"

# Escape hatch for deliberate off-pin runs (preparing a pin bump, measuring a crucible PR).
ALLOW_UNPINNED_ENV = "ESTATE_CRUCIBLE_ALLOW_UNPINNED"


def pin_mismatch(crucible_path):
    """None when the estate-crucible checkout at `crucible_path` is on PINNED_REF, else an
    actionable message ending in the commands that fix it. Compares commits, so any tag or branch
    at the pinned commit passes. None for a directory that is not a git checkout, or when
    ALLOW_UNPINNED_ENV is 1.
    """
    import os
    import subprocess
    from pathlib import Path

    if os.environ.get(ALLOW_UNPINNED_ENV) == "1":
        return None
    path = Path(crucible_path)

    def rev(ref):
        result = subprocess.run(  # noqa: S603 -- fixed argv
            ["git", "-C", str(path), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    if not (path / ".git").exists():
        return None
    head, pinned = rev("HEAD"), rev(PINNED_REF)
    if head and head == pinned:
        return None
    return (
        f"estate-crucible at {path} is on {head or 'an unknown commit'}, but the scorer pins {PINNED_REF} "
        f"(tests/_estate_crucible_pin.py).\n"
        f"Fix: git -C {path} fetch origin {PINNED_REF} && git -C {path} checkout {PINNED_REF}\n"
        f"(Deliberately off-pin? Set {ALLOW_UNPINNED_ENV}=1.)"
    )
