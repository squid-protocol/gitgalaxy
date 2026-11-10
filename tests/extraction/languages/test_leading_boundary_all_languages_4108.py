"""#4108 slice 25: every language, not only go/java. No alternation member that starts with a non-word char may sit
behind a leading `\\b(...)` unless it is a recorded harmless case. Fixed here: csharp `[Inject]`, lua `:close`."""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_go_java_leading_boundary_4108 import SHARED, _bad_alternatives, _compiled  # noqa: E402

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402

# Recorded as not a functional miss (the guard sees a non-word-first alternative, the rule still fires):
# dart `!is` (bare `is` catches its tail), ruby `::T::` (the whole prefix group is optional), dart/acs/crystal
# arguments `(`/`//` in non-boundary positions, agc `#REF:` and objective-c's split-out top-level alternatives.
HARMLESS = {
    ("acs", "dead_code"),
    ("agc_assembly", "spec_exposure"),
    ("crystal", "comprehensions"),
    ("dart", "func_start"),
    ("dart", "class_start"),
    ("dart", "safety"),
    ("objective-c", "globals"),
    ("ruby", "generics"),
}


def test_no_new_offender_in_any_language():
    found = {
        (lang, k)
        for lang in LANGUAGE_DEFINITIONS
        for k, p in _compiled(lang)
        if k not in SHARED and _bad_alternatives(p)
    }
    assert found <= HARMLESS, sorted(found - HARMLESS)


CS = LANGUAGE_DEFINITIONS["csharp"]["rules"]["dependency_injection"]
LUA = LANGUAGE_DEFINITIONS["lua"]["rules"]["cleanup"]


@pytest.mark.parametrize(
    "line",
    ["    [Inject]", "[Inject] IFoo foo;", "public X([Inject] IFoo f)", "services.AddScoped<A>();", "x(FromServices)"],
)
def test_csharp_di_fires(line):
    assert CS.search(line)


@pytest.mark.parametrize("line", ["Inject foo", "InjectX y", "var a = 1;", "AddScopedX"])
def test_csharp_di_no_fire(line):
    assert not CS.search(line)


@pytest.mark.parametrize(
    "line", ["f:close()", "(f):close()", "  :close()", "a() :  close()", "io.close(f)", "local x <close> = y"]
)
def test_lua_close_fires(line):
    assert LUA.search(line)


@pytest.mark.parametrize("line", ["f:closed()", "f:closer()", "local x = 1", "x.close"])
def test_lua_close_no_fire(line):
    assert not LUA.search(line)
