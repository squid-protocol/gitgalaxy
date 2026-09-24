r"""
Single source of truth for "which language-crucible tag does GitGalaxy's CI
currently pin to" -- see language-crucible's own RELEASING.md for the full
bump checklist (regenerate golden masters, then update the pin, in that
order).

This constant is the source of truth for every *human-facing* mention of the
pin (skip-reason messages, docstrings, README prose). CI normally clones
against the `LANGUAGE_CRUCIBLE_REF` GitHub Actions repository variable
(Settings -> Secrets and variables -> Actions -> Variables) instead, read by
every workflow step that does `git clone --branch`. Two places instead of one
because a GitHub Actions variable isn't importable from a local pytest run
or a docstring, and a Python constant isn't visible to workflow YAML -- but
two is a large, deliberate improvement over the ~11 independently-hardcoded
copies (6 workflow files, 4 scripts, 4 docs) this replaced.

Since the fork-PR fallback landed, this constant is ALSO a real CI input, not
just a human-facing one: GitHub withholds repository variables from
`pull_request` runs raised from a fork, so on those runs the corpus-backed
workflows scrape `PINNED_TAG` out of this file with

    sed -n 's/^PINNED_TAG = "\(.*\)"/\1/p' gitgalaxy/tests/_crucible_pin.py

and clone the (public, credential-free) corpus at whatever it says. Practical
consequence: **keep the assignment below on one line, in exactly that
literal form.** Reformatting it -- black-style line wrapping, single quotes,
a type annotation, a trailing comment -- silently breaks the fork-PR corpus
clone. If you must change the shape, update the sed in all six workflows
(golden-crucible, tree-sitter-accuracy-audit, tri-comparison-audit, the two
*-history workflows, release-crucible-archive) to match.

**When bumping the pin: update both.** This constant, and the
`LANGUAGE_CRUCIBLE_REF` repo variable (`gh variable set LANGUAGE_CRUCIBLE_REF
--body vX.Y --repo squid-protocol/gitgalaxy`). Nothing enforces they match --
review the diff on this file as your reminder to also run that command.
"""

PINNED_TAG = "v1.5.0"

# Escape hatch for deliberate off-pin runs (e.g. preparing a pin bump against an
# untagged crucible commit). Everything else treats a mismatch as an error.
ALLOW_UNPINNED_ENV = "LANGUAGE_CRUCIBLE_ALLOW_UNPINNED"


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
