"""
#6266: a unit's brace scan reaches past the 50 KB embedded-block lookahead, and a destructor's header is no call.

doomretro's `M_Responder` is ~1,600 lines (~60 KB): the scan stopped at 50 KB and every call after the cut was lost.
`Scanner::~Scanner()` and an inline `~ParserState()` recorded their own header `Scanner(` as a call.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _calls(lang: str, code: str, name: str) -> list[str]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(f["calls_out_to"] for f in functions if f["name"] == name)


@pytest.mark.parametrize("lang", ["c", "cpp"])
def test_call_after_a_body_longer_than_the_handshake_lookahead_is_kept(lang):
    filler = "  total += step(total);  /* padding to push the body past the old lookahead */\n" * 1000
    code = "void f(int total) {\n" + filler + "  late_callee(total);\n}\n"
    assert len(code) > 60000
    calls = _calls(lang, code, "f")
    assert calls == ["step", "late_callee"]


def test_cpp_destructor_header_is_not_a_call_to_the_class():
    out_of_line = "Scanner::~Scanner()\n{\n  if (s != NULL) delete[] s;\n  release(data);\n}\n"
    inline = "struct P {\n  ~P()\n  {\n    if (s != NULL) free(s);\n  }\n};\n"
    assert _calls("cpp", out_of_line, "Scanner::~Scanner") == ["release"]
    assert _calls("cpp", inline, "~P") == ["free"]


def test_a_bitwise_not_of_a_real_call_is_still_a_call():
    code = "int f(int x) {\n  return ~g(x);\n}\n"
    assert _calls("cpp", code, "f") == ["g"]


@pytest.mark.parametrize(
    "stmt",
    ["p->~Node();", "x.~Node();", "this->~Node();", "p-> ~Node();", "Node::~Node();"],
)
def test_cpp_explicit_destructor_call_is_a_call_to_the_destructor_unit(stmt):
    # #5630: gzdoom's `p->~player_t()` named the class, not the `~player_t` unit it runs
    code = "void f(Node *p) {\n  " + stmt + "\n  g(p);\n}\n"
    assert _calls("cpp", code, "f") == ["~Node", "g"]


def test_cpp_explicit_destructor_call_in_a_destructor_of_another_class_is_kept():
    code = "Owner::~Owner()\n{\n  item->~Item();\n  free(item);\n}\n"
    assert _calls("cpp", code, "Owner::~Owner") == ["~Item", "free"]
