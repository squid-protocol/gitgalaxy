"""#3772: a class written with its namespace qualifier (`struct fmt::formatter<T>`) is the unit `formatter<T>`."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

RULES = LANGUAGE_DEFINITIONS["cpp"]["rules"]

CASES = [
    ("struct fmt::formatter<Foo> {", "formatter<Foo>"),
    ("template <> struct std::hash<Foo> {", "hash<Foo>"),
    ("class a::b::C : public Base {", "C"),
    ("struct Plain {", "Plain"),
    ("class Vec<int> {", "Vec<int>"),
    # #6266: an export macro between the keyword and the name is not the class
    ("class LIBGUI_PUBLIC ImageItem : public Item {", "ImageItem"),
    ("struct DE_PUBLIC Rect\n{", "Rect"),
    ("template <class T> class Q_DECL_EXPORT Box final : Base {", "Box"),
    ("class API Wrap<int> {", "Wrap<int>"),
    ("enum class COLOR_T : int {", "COLOR_T"),
    ("class FOO final : Base {", "FOO"),
    ("class FOO : public Base {", "FOO"),
    ("struct POI {", "POI"),
]


@pytest.mark.parametrize("payload,name", CASES)
def test_class_start_takes_the_last_qualified_segment(payload, name):
    m = RULES["class_start"].search(payload)
    got = m.group(1) if m else None
    if got != name:
        pytest.fail(f"{payload!r}: got {got!r}, want {name!r}")


def test_class_start_qualifier_walk_is_bounded():
    payload = "struct " + "a::" * 5000 + "{"
    RULES["class_start"].search(payload)


def test_a_constructor_base_initializer_reaches_a_class_written_with_an_export_macro():
    # doomsday (#6266): `class LIBGUI_PUBLIC ImageItem` was the class `LIBGUI_PUBLIC`, so `ActionItem() : ImageItem(x)`
    # found no class named ImageItem and the resolver dropped the base-constructor edge.
    from gitgalaxy.core.call_resolver import resolve_calls
    from gitgalaxy.core.detector import StructuralExtractor

    code = (
        "class LIBGUI_PUBLIC ImageItem : public Item {\npublic:\n    ImageItem(int s) {}\n};\n"
        "class LIBGUI_PUBLIC ActionItem : public ImageItem {\npublic:\n    ActionItem(int s) : ImageItem(s) {}\n};\n"
    )
    out = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")
    assert {c["name"] for c in out["classes"]} == {"ImageItem", "ActionItem"}
    parsed = [{"path": "a.h", "lang_id": "cpp", "functions": out["functions"], "classes": out["classes"]}]
    sites, _ = resolve_calls(parsed, [])
    assert ("ActionItem", "ImageItem") in {(s["src_name"], s["dst_name"]) for s in sites}
