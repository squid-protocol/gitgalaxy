"""
#5639: an Objective-C method header ended by a stray `;` and followed by its `{` body is a definition.

`- (void)setOn:(BOOL)on;` then `{ ... }` (doom-ios, prboom-plus) used to be taken for a bodyless declaration, a
one-line unit whose body's message sends belonged to nobody. A real declaration (an `@interface` list, followed
by another method or `@end`) is still a bodyless one-line unit.

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _units(code: str) -> dict[str, dict]:
    functions = StructuralExtractor("objective-c", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


@pytest.mark.parametrize(
    "header, name",
    [
        ("- (void)setOn:(BOOL)turnOn;", "setOn"),
        ("-(void) removeAllPathsFromQueue;", "removeAllPathsFromQueue"),
        ("+ (id)make;", "make"),
        ("- (void)a:(int)x b:(int)y;", "a"),
        ("- (void)run  ;  ", "run"),
    ],
)
def test_semicolon_header_with_a_body_is_a_definition(header, name):
    code = f"@implementation Foo\n{header}\n{{\n    [self ping];\n}}\n- (void)next\n{{\n    [self pong];\n}}\n@end\n"
    units = _units(code)
    assert units[name]["calls_out_to"] == ["ping"]
    assert units[name]["loc"] > 1
    assert units["next"]["calls_out_to"] == ["pong"]


def test_interface_declarations_stay_bodyless():
    code = "@interface Foo\n- (void)a;\n- (int)b:(int)x;\n@end\n@implementation Foo\n- (void)a\n{\n    [self c];\n}\n@end\n"
    functions = StructuralExtractor("objective-c", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    assert {f["name"]: f["loc"] for f in functions if not f["calls_out_to"]} == {"a": 1, "b": 1}
    assert [f["loc"] > 1 for f in functions if f["calls_out_to"] == ["c"]] == [True]


def test_declaration_before_a_c_function_is_not_merged_with_its_body():
    code = "@interface Foo\n- (void)a;\n@end\nvoid f()\n{\n    [x g];\n}\n"
    units = _units(code)
    assert units["a"]["loc"] == 1
    assert units["f"]["calls_out_to"] == ["g"]
