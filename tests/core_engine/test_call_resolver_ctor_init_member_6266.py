"""#6266: a C++ constructor's initializer-list entry that names a data member the class declares is no call, even
when a class of that name exists elsewhere in the repo (gzdoom `PSymbolTreeNode(...) : PSymbol(name), Node(node)`)."""

import pytest

from gitgalaxy.core.detector import StructuralExtractor, _cpp_data_member_names
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


@pytest.mark.parametrize(
    ("body", "names"),
    [
        ("{ public: struct ZCC_TreeNode *Node = nullptr; PSymbolTreeNode(FName n) : Node(n) {} };", {"Node"}),
        ("{ int a, b; std::map<Base, X> m; };", {"a", "b", "m"}),
        ("{ void f() { int local; } int after; };", {"after"}),
        ("{ using Node = Foo; friend class Bar; class Fwd; typedef int T; };", set()),
        ("{ int bits : 3; char buf[4]; Foo x{1}; };", {"bits", "buf", "x"}),
        ("{ private: Foo *p; protected: Bar q; };", {"p", "q"}),
    ],
)
def test_data_member_names(body, names):
    assert _cpp_data_member_names(body) == names


@pytest.mark.parametrize(
    ("code", "kept", "dropped"),
    [
        (
            "class Sym : public Base {\npublic:\n  struct T *Node = nullptr;\n  Sym(int n) : Base(n), Node(n) {}\n};\n",
            ["Base"],
            ["Node"],
        ),
        # no such member: the entry may be a base (declared elsewhere), so it stays
        ("class Sym : public Base {\npublic:\n  Sym(int n) : Base(n), Node(n) {}\n};\n", ["Base", "Node"], []),
        # a body call that shares the member's name is still a call
        ("class S {\n  int Node;\n  S(int n) : Node(n) { Node(2); }\n};\n", ["Node"], []),
    ],
)
def test_a_declared_data_member_is_not_an_init_call(code, kept, dropped):
    functions = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    (ctor,) = [f for f in functions if f["name"] in ("Sym", "S")]
    assert sorted(ctor["calls_out_to"]) == sorted(kept)
    assert not set(dropped) & set(ctor["calls_out_to"])
