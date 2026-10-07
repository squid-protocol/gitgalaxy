r"""
Thin wrapper over tests/crucible_pins.toml ([cics]): `PINNED_REF` is the cics-crucible release tag
(squid-protocol/cics-crucible, format `cics-crucible/1`) GitGalaxy's CICS crucible runner
(tests/tools/cics_crucible.py, #3989) measures against. The baseline ratchet
(tests/cics_crucible/baseline.json) was measured at exactly this ref, so moving the pin is its own
PR that re-baselines. The value lives only in the manifest; bump with
`python tests/tools/crucible_pins.py bump cics <tag>`. A ref may also be a commit SHA (CI fetches
either with `git fetch --depth 1 origin <ref>`).

To move it: check the crucible out at the new tag, run
`python tests/tools/cics_crucible.py --update-baseline`, and commit the manifest,
tests/cics_crucible/baseline.json and docs/language_status/cics_crucible.md in one PR
(docs/ecosystem.md, "CICS crucible release -> pin bump"). In the same PR, re-prove the committed
ports (`python tests/tools/crucible_port_provenance.py reprove`, #4308): each port's
provenance.json must name the pinned ref or say it is stale against it
(tests/cics_crucible/test_port_provenance.py).

Local runs find the checkout through `CICS_CRUCIBLE_PATH`, else `../cics-crucible` beside the main
gitgalaxy checkout.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _crucible_manifest import entry  # noqa: E402

_PIN = entry("cics")

PINNED_REF = _PIN["ref"]

# Where a local checkout lives when not beside the main gitgalaxy checkout.
PATH_ENV = _PIN["path_env"]

ALLOW_UNPINNED_ENV = _PIN["allow_unpinned_env"]


def pin_mismatch(crucible_path):
    """None when the cics-crucible checkout at `crucible_path` is on PINNED_REF, else an actionable
    message ending in the exact commands that fix it. The baseline was measured at the pin, so an
    off-pin checkout reports phantom new failures (or phantom fixes) that no gitgalaxy change made.
    Compares commits, so any tag or branch pointing at the pinned commit passes. None for a
    directory that isn't a git checkout (an unpacked archive) or when ALLOW_UNPINNED_ENV is 1.
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
        f"cics-crucible at {path} is on {head or 'an unknown commit'}, but the runner pins {PINNED_REF} "
        f"(tests/_cics_crucible_pin.py); the baseline was measured there.\n"
        f"Fix: git -C {path} fetch origin {PINNED_REF} && git -C {path} checkout {PINNED_REF}\n"
        f"(Deliberately off-pin? Set {ALLOW_UNPINNED_ENV}=1.)"
    )
