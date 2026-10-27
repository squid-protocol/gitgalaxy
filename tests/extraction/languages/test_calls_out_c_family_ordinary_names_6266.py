"""
#6266: `def`, `function` and `include` are keywords of other languages, not of C or C++.

The global calls-out ignore set drops them, so `def().set(..)` (doomsday's `Definition::def`), `function(..)` and
`include(..)` were missing callees in C and C++ (#5634 did the same for Rust, Go and Java). The C/C++ keywords that
share the set (`catch`, `class`, `using`, `sizeof`) are still dropped in C++.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_BODY = """
int f(void) {
  def().set("a", 1);
  x = function(2);
  include(3);
  return sizeof(int);
}
"""
_CPP_BODY = """
int f() {
  try { def().set("a", 1); } catch (int e) { include(e); }
  return sizeof(int) + function(1);
}
"""


def _calls(lang: str, code: str) -> list[str]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(f["calls_out_to"] for f in functions if f["name"] == "f")


@pytest.mark.parametrize("lang", ["c", "cpp"])
def test_def_function_include_are_callees(lang):
    calls = _calls(lang, _BODY)
    assert {"def", "function", "include"} <= set(calls)
    assert "sizeof" not in calls


def test_cpp_keywords_in_the_same_set_are_still_dropped():
    calls = _calls("cpp", _CPP_BODY)
    assert {"def", "include", "function"} <= set(calls)
    assert not {"catch", "sizeof", "try"} & set(calls)
