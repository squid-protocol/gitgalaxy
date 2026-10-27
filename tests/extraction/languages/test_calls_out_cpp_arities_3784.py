"""#3784: the C++ detector records each callee's argument counts, so the resolver can choose among overloads."""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

SRC = """class G {
 public:
  int f(int x) { return x; }
  int f(int x, int y) { return x; }
  int g(int a) { return f(a) + f(a, 1); }
  int h(int a) { return ns::free(a, 2, 3); }
};
void run(G& g) { g.f(1); }
int none() { return h0(); }
"""


def _funcs():
    out = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(SRC, "")
    return {f["start_line"]: f for f in out["functions"]}


def test_member_free_qualified_and_zero_arg_calls_record_their_counts():
    fns = _funcs()
    assert fns[5]["calls_out_arities"] == {"f": [1, 2]}
    assert fns[6]["calls_out_arities"] == {"free": [3]}
    assert fns[8]["calls_out_arities"] == {"f": [1]}
    assert fns[9]["calls_out_arities"] == {"h0": [0]}


def test_the_declarations_own_parameter_list_is_not_a_call():
    fns = _funcs()
    assert fns[3]["calls_out_arities"] == {}
    assert fns[4]["calls_out_arities"] == {}
