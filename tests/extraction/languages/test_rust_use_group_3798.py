"""#3798: a Rust `use { a::B, c::{D, E} };` (an unprefixed brace group) expands to its items."""

import pytest

from gitgalaxy.galaxyscope import extract_raw_imports
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANG = LANGUAGE_DEFINITIONS["rust"]
_REGEX = _LANG["rules"]["_dependency_capture"]


def _imports(src: str) -> set[str]:
    return extract_raw_imports(_REGEX, src, _LANG)


@pytest.mark.parametrize(
    "src",
    [
        "use { a::B, c::{D, E} };",
        "pub use { a::B, c::{D, E} };",
        "use {\n    a::B,\n    c::{D, E},\n};",
        "use {a::B, c::{D, E,}};",
    ],
)
def test_unprefixed_group_expands_nested_items(src):
    assert _imports(src) == {"a::B", "c::D", "c::E"}


def test_prefixed_and_nested_groups_are_unchanged():
    assert _imports("use a::{b, c::{d, e}};") == {"a::b", "a::c::d", "a::c::e"}


def test_group_inside_a_group_item_keeps_its_prefix():
    assert _imports("use { x::{y::{Z}, W} };") == {"x::y::Z", "x::W"}
