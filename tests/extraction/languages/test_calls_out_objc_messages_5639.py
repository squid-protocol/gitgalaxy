"""
#5639: Objective-C message sends are calls, recorded by selector.

`[self initialize]`, `[obj set:a withB:b]`, `[[Foo alloc] init]`, `[super x]` and a send inside a
C call's arguments each record their selector (first keyword for a keyword selector). `@selector(x:)`
is a reference to a selector, not a send, and records nothing; C calls are unchanged.

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _calls(body: str) -> list[str]:
    code = f"@implementation Thing\n- (void)run\n{{\n{body}\n}}\n@end\n"
    functions = StructuralExtractor("objective-c", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(f for f in functions if f["name"] == "run")["calls_out_to"]


@pytest.mark.parametrize(
    "body, expected",
    [
        # unary
        ("    [self initialize];", ["initialize"]),
        ("    selectedIWAD = [self getSelectedIWAD];", ["getSelectedIWAD"]),
        ("    [obj.view reload];", ["reload"]),
        ("    [self->owner ping];", ["ping"]),
        ("    [Foo sharedInstance];", ["sharedInstance"]),
        # keyword: the first keyword only
        ("    [mOwner updateParameters:p];", ["updateParameters"]),
        ("    [obj set:a withB:b andC:c];", ["set"]),
        ("    [obj set:\n        a\n     withB:b];", ["set"]),
        # super
        ("    [super awakeFromNib];", ["awakeFromNib"]),
        ("    [super initWithFrame:f];", ["initWithFrame"]),
        # nested
        ("    x = [[Foo alloc] init];", ["alloc", "init"]),
        ("    x = [[[Foo alloc] initWithX:1] autorelease];", ["alloc", "initWithX", "autorelease"]),
        ("    [self add:[other make:1]];", ["add", "make"]),
        ("    [arr[i] count];", ["count"]),
        ("    [(Foo *)obj bar:1];", ["bar"]),
        ("    [Lookup(x) fetch];", ["Lookup", "fetch"]),
        # inside a C call, beside a C call
        ("    return NameForIWAD([self getSelectedIWAD]);", ["NameForIWAD", "getSelectedIWAD"]),
        ("    free(x);\n    [self done];", ["free", "done"]),
        # not a call: a reference to a selector, a directive, a literal
        ("    [self performSelector:@selector(dataReady:)];", ["performSelector"]),
        ("    SEL s = @selector(updateTitle);", []),
        ("    @synchronized(self) { x = 1; }", []),
        ("    x = cond ? a : b;", []),
        ("    switch (n) { case 1: break; default: break; }", []),
        ("    y = arr[i + 1];", []),
    ],
)
def test_message_send_shapes(body, expected):
    assert _calls(body) == expected


def test_selector_reference_is_not_a_send():
    assert "dataReady" not in _calls("    [n addObserver:self selector:@selector(dataReady:) name:nil];")


def test_c_calls_unchanged():
    assert _calls("    int n = strlen(s);\n    foo(n, bar(n));") == ["strlen", "foo", "bar"]


def test_pattern_is_redos_immune():
    pattern = LANGUAGE_DEFINITIONS["objective-c"]["rules"]["calls_out"]
    assert_redos_immune(pattern, "[" + "a." * 5000 + " ")
    assert_redos_immune(pattern, "[" + " " * 20000 + "x")
    assert_redos_immune(pattern, "] " * 20000)
    assert_redos_immune(pattern, "[(" + "a" * 20000)


def _qualifiers(body: str) -> dict[str, list[str]]:
    code = f"@implementation Thing\n- (void)run\n{{\n{body}\n}}\n@end\n"
    functions = StructuralExtractor("objective-c", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(f for f in functions if f["name"] == "run")["calls_out_qualifiers"]


@pytest.mark.parametrize(
    "body, expected",
    [
        # the receiver is kept as the qualifier; a C call stays bare
        ("    [self initialize];", {"initialize": ["self"]}),
        ("    [super awakeFromNib];", {"awakeFromNib": ["super"]}),
        ("    [Foo sharedInstance];", {"sharedInstance": ["Foo"]}),
        ("    [obj.view reload];", {"reload": ["obj.view"]}),
        ("    [self->owner ping];", {"ping": ["self.owner"]}),
        ("    [mOwner updateParameters:p];", {"updateParameters": ["mOwner"]}),
        ("    [(Foo *)obj bar:1];", {"bar": ["obj"]}),
        # a receiver that is itself a send or a call has no name
        ("    x = [[Foo alloc] init];", {"alloc": ["Foo"], "init": ["<expr>"]}),
        ("    [Lookup(x) fetch];", {"Lookup": [""], "fetch": ["<expr>"]}),
        ("    free(x);\n    [self done];", {"free": [""], "done": ["self"]}),
        ("    [a go];\n    [b go];\n    [a go];", {"go": ["a", "b"]}),
    ],
)
def test_message_send_receiver_qualifiers(body, expected):
    assert _qualifiers(body) == expected
