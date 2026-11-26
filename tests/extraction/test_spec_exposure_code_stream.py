"""spec_exposure reads a traceability tag, not bracketed code (#8862, unplanted_family_contracts.md).

The rule also runs over the code stream, where `[SPECIAL___ENTER__] = {` (C), a `[Spec=%v]` log string (Go) and a
`[spec, return]` list pattern (Elixir) matched.
"""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

LANGS = ("c", "go", "elixir", "matlab", "objective-c")
TAGS = ("[SPEC-123]", "[audit]", "[Spec 10.9.4]", "[audit: reviewed by QA]", "[spec]")
NOT_TAGS = (
    "[SPECIAL___ENTER__] = {",
    'log("[Spec=%v, podUID=%v]")',
    "{:when, _, [spec, guard]}",
    "[spec, return]",
    "[auditor]",
    "specdata = [specdata;[real(tmp) imag(tmp)]];",
    "[specs x]",
)


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("text", TAGS)
def test_a_traceability_tag_still_counts(lang, text):
    assert LANGUAGE_DEFINITIONS[lang]["rules"]["spec_exposure"].search(text)


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("text", NOT_TAGS)
def test_bracketed_code_is_not_a_tag(lang, text):
    assert not LANGUAGE_DEFINITIONS[lang]["rules"]["spec_exposure"].search(text)


def test_objective_c_product_name_still_counts():
    # a deliberate name alternation (design question in unplanted_family_contracts.md), not touched by the guard
    assert LANGUAGE_DEFINITIONS["objective-c"]["rules"]["spec_exposure"].search("WorldWideWeb")
