"""
Single source of truth for "which language-crucible tag does GitGalaxy's CI
currently pin to" -- see language-crucible's own RELEASING.md for the full
bump checklist (regenerate golden masters, then update the pin, in that
order).

This constant is the source of truth for every *human-facing* mention of the
pin (skip-reason messages, docstrings, README prose). It intentionally is
NOT the source of truth CI itself clones against -- that's the
`LANGUAGE_CRUCIBLE_REF` GitHub Actions repository variable (Settings ->
Secrets and variables -> Actions -> Variables), read directly by every
workflow step that does `git clone --branch`. Two places instead of one
because a GitHub Actions variable isn't importable from a local pytest run
or a docstring, and a Python constant isn't visible to workflow YAML -- but
two is a large, deliberate improvement over the ~11 independently-hardcoded
copies (6 workflow files, 4 scripts, 4 docs) this replaced.

**When bumping the pin: update both.** This constant, and the
`LANGUAGE_CRUCIBLE_REF` repo variable (`gh variable set LANGUAGE_CRUCIBLE_REF
--body vX.Y --repo squid-protocol/gitgalaxy`). Nothing enforces they match --
review the diff on this file as your reminder to also run that command.
"""

PINNED_TAG = "v1.2.0"
