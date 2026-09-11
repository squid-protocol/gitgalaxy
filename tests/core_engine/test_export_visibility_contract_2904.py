# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The `export_visibility` contract (#2904), pinned in one cross-language module.

The registry key answers one question: does a language's export construct name
EXTERNAL entry points (a makefile `.PHONY:` target, invoked by a human, CI, or a
Dockerfile -- never by an in-repo caller or import), or ordinary public symbols?

The default is `standard`: an exported-but-uncalled unit is still measured as
`unreferenced_by_name` (the #2774 dead-code population). Only where the export
construct is NARROW and CURATED (`.PHONY:`) may a language opt into
`external_entry_points`, which lets galaxyscope's Contextual Baseline Fix credit
those declared orphans as api surface instead of tech debt (tier 3). Opting in a
language whose `export` decorates every symbol (JS/TS) would blind #2774, so the
opted-in family is pinned here as a literal -- adding to it is a deliberate edit
reviewed against the contract, never a side effect of a registry tweak.

Like the #2806 `invocation_model` contract, this is a cross-language table, not a
per-language test: a language that disagrees shows up as a row, not a missing file.
"""

from __future__ import annotations

from gitgalaxy.core.detector import (
    EXPORT_VISIBILITY_EXTERNAL_ENTRY_POINTS,
    EXPORT_VISIBILITY_MODELS,
    EXPORT_VISIBILITY_STANDARD,
)
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _declared_visibility(lang: str) -> str:
    return LANGUAGE_DEFINITIONS[lang].get("export_visibility", EXPORT_VISIBILITY_STANDARD)


# The languages whose export construct names external entry points. Kept as a
# literal so ADDING a language is a deliberate edit reviewed against #2904's
# "narrow and curated" constraint, never a side effect of a registry tweak.
EXTERNAL_ENTRY_POINT_LANGUAGES = {"makefile"}


def test_export_visibility_values_are_a_closed_set():
    """A typo in a registry must not silently mean `standard`.

    `export_visibility` is read with a default, so a misspelt
    `"external_entrypoints"` would take the default branch and the language
    would go on being censused as dead code with nobody noticing -- or, worse,
    a misspelt opt-in would silently fail to exempt a real external interface.
    The set is closed here instead.
    """
    for lang, defn in LANGUAGE_DEFINITIONS.items():
        model = defn.get("export_visibility", EXPORT_VISIBILITY_STANDARD)
        assert model in EXPORT_VISIBILITY_MODELS, f"{lang} declares an unknown export_visibility {model!r}"


def test_exactly_the_declared_family_opts_into_external_entry_points():
    declared = {
        lang for lang in LANGUAGE_DEFINITIONS if _declared_visibility(lang) == EXPORT_VISIBILITY_EXTERNAL_ENTRY_POINTS
    }
    assert declared == EXTERNAL_ENTRY_POINT_LANGUAGES, (
        "the external-entry-point family changed; read #2904 before widening it -- the exemption is "
        "only sound where the export construct is narrow and curated (makefile `.PHONY:`), not where "
        "it decorates every symbol in the file (a JS/TS `export`), which would blind the #2774 "
        "dead-exported-code census"
    )


def test_the_family_is_opt_in_and_leaves_every_other_language_standard():
    """Every language NOT in the family reads as `standard` (the census-everything default)."""
    for lang in LANGUAGE_DEFINITIONS:
        if lang not in EXTERNAL_ENTRY_POINT_LANGUAGES:
            assert _declared_visibility(lang) == EXPORT_VISIBILITY_STANDARD, (
                f"{lang} is not in the external-entry-point family but does not read as standard"
            )
