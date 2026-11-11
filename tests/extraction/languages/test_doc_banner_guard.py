"""The `doc` rule must not read `/*****` star banners or `////` dividers as doc blocks.

Banner shapes: a `/****` border (2+ extra stars) and a one-line `/*** title ***/` box. A `/***` +
newline docblock (Magento's style) is a real doc block and still counts. Pins the guard on every
language whose `doc` rule opens with `/**`.
"""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

SLASH_STAR_LANGS = [
    "apex", "c", "cpp", "dart", "groovy", "java", "javascript", "kotlin", "objective-c",
    "php", "scala", "solidity", "swift", "typescript", "yacc",
]  # fmt: skip
TRIPLE_SLASH_LANGS = ["c", "cpp", "dart", "objective-c", "solidity", "swift"]

BANNER = "/*******************************************************************\n * Section\n *******************************************************************/\n"


def _doc(lang):
    return LANGUAGE_DEFINITIONS[lang]["rules"]["doc"]


@pytest.mark.parametrize("lang", SLASH_STAR_LANGS)
def test_star_banner_is_not_a_doc_block(lang):
    assert _doc(lang).findall(BANNER) == []


@pytest.mark.parametrize("lang", SLASH_STAR_LANGS)
def test_real_doc_block_still_counts(lang):
    assert len(_doc(lang).findall("/** Explains the next function. */\n")) == 1


@pytest.mark.parametrize("lang", TRIPLE_SLASH_LANGS)
def test_slash_divider_is_not_a_doc_line_but_triple_slash_is(lang):
    assert _doc(lang).findall("////////////////////////////\n") == []
    assert len(_doc(lang).findall("/// Explains the next function.\n")) == 1


@pytest.mark.parametrize("lang", SLASH_STAR_LANGS)
def test_one_line_star_box_is_not_a_doc_block(lang):
    assert _doc(lang).findall("/*** dict_keys ***/\n") == []


@pytest.mark.parametrize("lang", SLASH_STAR_LANGS)
def test_triple_star_docblock_still_counts(lang):
    block = "/***\n * Get exact version of MySQL\n */\n"
    assert _doc(lang).findall(block) == [block[:-1]]
