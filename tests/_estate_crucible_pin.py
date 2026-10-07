r"""
Thin wrapper over tests/crucible_pins.toml ([estate]): `PINNED_REF` is the estate-crucible release
tag (squid-protocol/estate-crucible, format `estate-crucible-key/1`) GitGalaxy's estate scorer
(tests/tools/estate_crucible.py, #4317) measures against. The value lives only in the manifest;
bump with `python tests/tools/crucible_pins.py bump estate <tag>`, then run
`python tests/tools/estate_crucible.py` against the new tag and commit the scorecard it prints
(PR body) with the bump, in one PR (estate-crucible RELEASING.md).

Local runs find the checkout through `ESTATE_CRUCIBLE_PATH`, else `../estate-crucible` beside the
main gitgalaxy checkout.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _crucible_manifest import entry  # noqa: E402

_PIN = entry("estate")

PINNED_REF = _PIN["ref"]

# Where a local checkout lives when not beside the main gitgalaxy checkout.
PATH_ENV = _PIN["path_env"]

ALLOW_UNPINNED_ENV = _PIN["allow_unpinned_env"]


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
