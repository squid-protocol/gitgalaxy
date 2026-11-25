"""Node maps for crystal, erlang, nim, julia, r and fsharp in the tree-sitter accuracy audit: what counts as a function,
how each language's name and parameter count are read, and that a language sharing a node type is not disturbed."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tree_sitter_accuracy_audit as audit

ts = pytest.importorskip("tree_sitter_language_pack")


def _functions(lang, source: str):
    """[(name, params)] for every node the language's map treats as a function and that has a name."""
    tree = ts.get_parser(lang).parse(source.encode())
    types = audit.NODE_MAPS[lang]["func_node_types"]
    out = []

    def walk(node, continuation=False):
        if node.type in types:
            name = audit._get_node_name(node)
            if name and not (lang == "erlang" and continuation):
                out.append((name, audit._get_param_count(node, lang)))
        erlang_open = False
        for child in node.children:
            if lang == "erlang" and child.type == "fun_decl":
                walk(child, continuation=erlang_open)
                erlang_open = child.text.rstrip().endswith(b";")
            else:
                walk(child)

    walk(tree.root_node)
    return out


def test_every_new_language_is_mapped_and_no_longer_gitgalaxy_only():
    for lang in ("crystal", "erlang", "nim", "julia", "r", "fsharp"):
        assert lang in audit.NODE_MAPS
        assert lang not in audit._gg_only_langs()


def test_crystal_counts_def_not_abstract_and_counts_every_parameter_kind():
    src = (
        "class A\n  def foo(x, y)\n    x\n  end\n  abstract def baz(z)\n  def ==(o)\n    true\n  end\n"
        "  def self.make(a : Int32, *rest, &block)\n    a\n  end\nend\n"
    )
    assert _functions("crystal", src) == [("foo", 2), ("==", 1), ("make", 3)]


def test_crystal_rebuilds_a_setter_name_the_grammar_splits():
    src = "class A\n  def name=(value : String)\n    @n = value\n  end\nend\n"
    assert [n for n, _ in _functions("crystal", src)] == ["name="]


def test_erlang_groups_clauses_by_the_terminating_period():
    src = (
        "-module(m).\nf(0) -> 1;\nf(N) when N > 0 ->\n    G = fun(X) -> X end,\n    G(N).\n"
        "g(A, B) -> {A, B}.\ng() -> ok.\ng(X) -> X.\n"
    )
    # f is one function (its clauses are joined by `;`), the fun(X) is anonymous, g/2, g/0 and g/1 end in `.`
    assert _functions("erlang", src) == [("f", 1), ("g", 2), ("g", 0), ("g", 1)]


def test_nim_counts_every_routine_kind_including_forward_declarations_but_not_proc_types():
    src = (
        "proc foo*(x: int, y, z: string): int =\n  x\n"
        "func bar(a: int): int = a\nmacro mac(x: untyped): untyped =\n  x\n"
        "template tmpl(x: untyped) =\n  x\nproc fwd(x: int): int\n"
        "let p = proc (x: int): int = x\n"
    )
    assert _functions("nim", src) == [("foo", 3), ("bar", 1), ("mac", 1), ("tmpl", 1), ("fwd", 1)]


def test_julia_counts_blocks_and_call_shaped_assignments_but_not_plain_assignments_or_macros():
    src = (
        "function foo(x, y)\n    x + y\nend\n"
        "function Base.show(io::IO, x::T) where {T}\n    print(io, x)\nend\n"
        "bar(x) = x + 1\nBase.length(a::A) = 3\ny = f(3)\n"
        "macro mac(x)\n    x\nend\nfunction nobody end\n"
    )
    assert _functions("julia", src) == [("foo", 2), ("show", 2), ("bar", 1), ("length", 1), ("nobody", 0)]


def test_r_names_a_function_only_through_the_assignment_around_it():
    src = (
        "foo <- function(x, y = 2, ...) {\n  x + y\n}\nbar = function(a) a\n`my name` <- function(z) z\n"
        "obj$method <- function(self) self\nsq <- \\(x) x^2\nlapply(1:3, function(i) i)\n"
    )
    assert _functions("r", src) == [("foo", 3), ("bar", 1), ("my name", 1), ("method", 1), ("sq", 1)]


def test_fsharp_counts_let_functions_and_methods_not_values_or_properties():
    src = (
        "module M\n\nlet x = 1\nlet add a b = a + b\nlet f = fun x -> x + 1\nlet useIt () = 1\n"
        "type T() =\n    member this.Two(x: int, y: string) = x\n    member this.One(x) = x\n"
        "    member this.Prop = 1\n    member val P = 1 with get, set\n"
    )
    assert _functions("fsharp", src) == [("add", 2), ("useIt", 0), ("Two", 2), ("One", 1)]


def _fsharp_and(src: str):
    tree = ts.get_parser("fsharp").parse(src.encode())
    out = []

    def walk(node):
        if node.type == "function_or_value_defn":
            out.extend(audit._fsharp_and_bindings(node))
        for c in node.children:
            walk(c)

    walk(tree.root_node)
    return [(n, line, pc) for n, line, pc in out]


def test_fsharp_counts_each_and_binding_of_a_let_rec_chain():
    src = "let rec a x = x\nand b x y = a x\nand c () = 1\n\nlet plain z = z\n"
    assert _fsharp_and(src) == [("b", 2, 2), ("c", 3, 0)]


def test_fsharp_and_value_binding_and_lone_let_add_nothing():
    assert _fsharp_and("let rec a x = x\nand v = 1\n") == []
    assert _fsharp_and("let one x = x\nlet two y = y\n") == []


def test_python_function_names_are_not_disturbed_by_the_other_languages_branches():
    """function_definition is shared with python, c, matlab and others; none of the new branches may touch them."""
    tree = ts.get_parser("python").parse(
        b"def foo(a, b):\n    return a\n\nclass K:\n    def bar(self):\n        pass\n"
    )
    names = []

    def walk(node):
        if node.type == "function_definition":
            names.append(audit._get_node_name(node))
        for c in node.children:
            walk(c)

    walk(tree.root_node)
    assert names == ["foo", "bar"]
