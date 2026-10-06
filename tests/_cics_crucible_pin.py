r"""
Single source of truth for "which cics-crucible commit does GitGalaxy's CICS crucible runner
(tests/tools/cics_crucible.py, #3989) measure against".

cics-crucible (squid-protocol/cics-crucible) is the adversarial CICS benchmark: small original
CICS COBOL applications, each scenario with a hand-written expected event log derived from
IBM's documentation (format `cics-crucible/1`, its SPEC.md). The runner's baseline ratchet
(tests/cics_crucible/baseline.json) was measured at exactly this ref, so a crucible change can
never move cells under a gitgalaxy PR: moving the pin is its own PR that re-baselines.

Unlike tests/_crucible_pin.py (language-crucible), there is deliberately NO GitHub Actions
repository variable for this pin. The workflow (.github/workflows/cics-crucible.yml) reads
PINNED_REF straight out of this file with

    sed -n 's/^PINNED_REF = "\(.*\)"/\1/p' gitgalaxy/tests/_cics_crucible_pin.py

which works the same on a pull_request raised from a fork (GitHub withholds repository
variables there; the crucible is public and clones with no credentials). One place to bump,
not two. Practical consequence: **keep the assignment below on one line, in exactly that
literal form.** Reformatting it -- line wrapping, single quotes, a type annotation, a trailing
comment -- silently breaks the workflow's clone. If you must change the shape, update the sed
in cics-crucible.yml to match.

The ref is a release tag of the crucible (its RELEASING.md); a commit SHA also works, since CI
fetches either with `git fetch --depth 1 origin <ref>`. To move it: check the crucible out at the
new tag, run `python tests/tools/cics_crucible.py --update-baseline`, and commit this pin,
tests/cics_crucible/baseline.json and docs/language_status/cics_crucible.md in one PR (docs/
ecosystem.md, "CICS crucible release -> pin bump"). In the same PR, re-prove the committed ports
(`python tests/tools/crucible_port_provenance.py reprove`, #4308): each port's provenance.json must
name the pinned ref or say it is stale against it (tests/cics_crucible/test_port_provenance.py).

Local runs find the checkout through the `CICS_CRUCIBLE_PATH` environment variable (like
LANGUAGE_CRUCIBLE_PATH), else `../cics-crucible` beside the main gitgalaxy checkout.
"""

PINNED_REF = "v0.3.0"

# Where a local checkout lives when not beside the main gitgalaxy checkout.
PATH_ENV = "CICS_CRUCIBLE_PATH"

# Escape hatch for deliberate off-pin runs (e.g. preparing a pin bump, or measuring a crucible
# PR branch). Everything else treats a mismatch as an error.
ALLOW_UNPINNED_ENV = "CICS_CRUCIBLE_ALLOW_UNPINNED"


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
