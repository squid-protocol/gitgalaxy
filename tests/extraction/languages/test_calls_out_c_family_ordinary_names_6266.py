"""
#6266: `def`, `function`, `include` and `import` are keywords of other languages, not of C or C++.

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
  d->import(file);
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
    assert {"def", "function", "include", "import"} <= set(calls)
    assert "sizeof" not in calls


def test_cpp_keywords_in_the_same_set_are_still_dropped():
    calls = _calls("cpp", _CPP_BODY)
    assert {"def", "include", "function"} <= set(calls)
    assert not {"catch", "sizeof", "try"} & set(calls)


_LOG_AS_BODY = """
struct A {
    void finished(Req &) override
    {
        LOG_AS("Updater")
        try
        {
            handleReply();
        }
        catch (const Error &er) { LOG_WARNING("x") << er.asText(); }
    }
    A() try : x(1) { init(); } catch (...) { fail(); }
};
"""


def test_log_as_statement_before_try_is_not_a_function_try_block_head():
    # doomsday updater.cpp: `LOG_AS("Updater")` has no `;`, so the `try` after it is not a function-try-block.
    functions = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(_LOG_AS_BODY, "")["functions"]
    by_name = {f["name"]: f["calls_out_to"] for f in functions}
    assert "LOG_AS" not in by_name
    assert {"LOG_AS", "handleReply", "asText"} <= set(by_name["finished"])
    assert {"x", "init"} <= set(by_name["A"])  # a real function-try-block constructor is still one unit


def test_a_template_argument_holding_an_unevaluated_operand_is_still_a_call():
    # doomsday line.cpp: `de::map<decltype(segments)>(sorted, f)`: the `(..)` of decltype is part of the argument list.
    code = """
int f() {
  segments = de::map<decltype(segments)>(sorted, g);
  n = pick<sizeof(int)>(b);
  m = take<noexcept(h)>(c);
  return a < sizeof(int) > (b);
}
"""
    calls = _calls("cpp", code)
    assert {"map", "pick", "take"} <= set(calls)
    assert "a" not in calls
