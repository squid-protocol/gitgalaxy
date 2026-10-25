"""#3332 Level 1: the tree-sitter side of call_graph_accuracy.py names callees the
way the #3327 contract does (rightmost identifier, constructors and macros count)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
pytest.importorskip("tree_sitter_language_pack")

import call_graph_accuracy as cga
import tree_sitter_accuracy_audit as audit


def _calls(lang, src):
    return {name: calls for name, _, calls, _node in cga.ts_functions(src.encode(), lang, audit)}


def test_python_callees_rightmost_and_nested_attribution():
    got = _calls("python", "def run(x):\n    a.b.save(x)\n    Foo()\n    def inner():\n        helper()\n")
    assert got == {"run": {"save", "Foo"}, "inner": {"helper"}}


def test_rust_scoped_constructor_and_macro():
    got = _calls("rust", 'fn run() {\n    let x = ControlFlow::Continue(1);\n    println!("{}", x);\n}\n')
    assert got == {"run": {"Continue", "println"}}


def test_java_constructor_and_method():
    got = _calls("java", "class A {\n  void run() {\n    new Foo().save();\n  }\n}\n")
    assert got == {"run": {"Foo", "save"}}


def test_powershell_cmdlets_methods_and_static_calls():
    """cmdlets, `$o.Save(1)`, `[Foo]::Make(2)` and pipeline stages are calls; `& $g`, dot-sourcing and a
    property read name no call."""
    src = (
        "function Run {\n  Get-Item $x\n  $o.Save(1)\n  [Foo]::Make(2)\n  & $g\n  . ./a.ps1\n"
        "  $o.Name\n  Write-Host 'hi' | Out-Null\n}\n"
    )
    assert _calls("powershell", src) == {"Run": {"Get-Item", "Save", "Make", "Write-Host", "Out-Null"}}


def test_tcl_commands_substitutions_and_namespaced_commands():
    """a command, a `[subst]` inside `set`, and `ns::k` (rightmost segment) are calls; `set` is no call;
    a command after an ERROR node (`puts "x $a"`) is still seen."""
    src = "proc foo {a} {\n  set x [bar $a]\n  ns::k 1\n  puts \"x $a\"\n  baz\n}\n"
    assert _calls("tcl", src) == {"foo": {"bar", "k", "puts", "baz"}}


def test_powershell_and_tcl_are_measured():
    assert {"powershell", "tcl"} <= set(cga.LANGS)


def test_pairing_drops_recursion_and_needs_nearby_lines():
    gg = [("run", 1, ["run", "save"]), ("far", 50, ["x"])]
    ts = [("run", 2, {"run", "save", "load"}, "run-node"), ("far", 10, {"x"}, "far-node")]
    assert cga._pair(gg, ts) == [("run", {"save"}, {"save", "load"}, "run-node")]


def test_cause_labels_inner_function_calls_and_non_calls():
    """--buckets: a call tree-sitter gives to an inner function, and a name that is no call."""
    src = b"def outer(x):\n    def inner():\n        save(x)\n    return inner\n"
    fns = {n: node for n, _, _, node in cga.ts_functions(src, "python", audit)}
    assert cga._cause("fp", "save", fns["outer"], "python", audit, False)[0] == ("fp:inner-named-function_definition")
    assert cga._cause("fp", "x", fns["outer"], "python", audit, False)[0].startswith("fp:not-a-call-in-ts:")
    assert cga._cause("fp", "nowhere", fns["outer"], "python", audit, False)[0] == "fp:outside-ts-function"


def test_cause_labels_a_call_lost_to_a_tree_sitter_parse_error():
    """--buckets: tree-sitter-zig cannot parse tuple destructuring, so the callee after it is
    missing from the tree; that is a grammar gap (`fp:ts-parse-error`), not a call GitGalaxy invented."""
    src = b"fn run(zir: u32) void {\n    const a, _ = pair(zir);\n    use(a);\n}\nfn clean() void {\n    use(1);\n}\n"
    fns = {n: node for n, _, _, node in cga.ts_functions(src, "zig", audit)}
    assert cga._cause("fp", "use", fns["run"], "zig", audit, False)[0] == "fp:ts-parse-error"
    assert cga._cause("fp", "nowhere", fns["clean"], "zig", audit, False)[0] == "fp:outside-ts-function"


def test_regressions_respect_the_tolerance():
    base = {"c": {"matched_functions": 5, "precision_pct": 90.0, "recall_pct": 80.0}}
    assert cga.regressions({"c": {"precision_pct": 89.6, "recall_pct": 80.0}}, base) == []
    assert cga.regressions({"c": {"precision_pct": 89.0, "recall_pct": 80.0}}, base) == [
        "c: precision_pct 90.0 -> 89.0"
    ]


def test_c8_anonymous_function_calls_belong_to_the_enclosing_unit():
    """C8 (#3641): a callback is no unit of its own; its calls are the enclosing function's."""
    got = _calls(
        "javascript", "function run(xs) {\n  xs.forEach(function (x) { save(x); });\n  xs.map((y) => load(y));\n}\n"
    )
    assert got == {"run": {"forEach", "save", "map", "load"}}


def test_c8_nested_named_function_keeps_its_own_calls():
    got = _calls("python", "def outer(x):\n    def inner():\n        save(x)\n    return inner()\n")
    assert got["outer"] == {"inner"} and got["inner"] == {"save"}


def test_c3_go_conversion_is_a_call():
    got = _calls("go", "package m\nfunc Run(s string) {\n  w([]byte(s))\n}\n")
    assert got == {"Run": {"w", "byte"}}


@pytest.mark.parametrize(
    "lang, src, fn, callee",
    [
        ("rust", "fn run(xs: I) {\n  let v = xs.collect::<Vec<u8>>();\n}\n", "run", "collect"),
        ("csharp", "class A {\n  void Run(object[] xs) {\n    xs.OfType<Location>();\n  }\n}\n", "Run", "OfType"),
        ("java", "class A {\n  void run() {\n    Map m = new HashMap<String, Object>();\n  }\n}\n", "run", "HashMap"),
    ],
)
def test_generic_callee_is_the_function_not_its_type_argument(lang, src, fn, callee):
    assert _calls(lang, src)[fn] == {callee}


def test_cpp_qualified_unit_drops_its_own_leaf_recursion_only():
    # #3644: `Node::walk` calling bare `walk(`, `this->walk(` or `Node::walk(` is recursion;
    # `child->walk(` is another object's method and stays a call.
    src = (
        "int Node::walk(int a) {\n  walk(a - 1);\n  this->walk(a - 2);\n  Node::walk(0);\n"
        "  return other(a);\n}\n"
        "int Node::step(int a) {\n  return child->step(a);\n}\n"
    )
    got = _calls("cpp", src)
    assert got["Node::walk"] == {"other"}
    assert got["Node::step"] == {"step"}


@pytest.mark.parametrize(
    "lang, src, expected",
    [
        (
            "kotlin",
            "class A {\n  fun run(x: Int) {\n    a.b.save(x)\n    Foo(1)\n    xs.map { load(it) }\n  }\n}\n",
            {"save", "Foo", "map", "load"},
        ),
        (
            "scala",
            "object A {\n  def run(x: Int) = {\n    a.b.save(x)\n    new Foo(1)\n    Bar(2)\n    xs.map(y => load(y))\n  }\n}\n",
            {"save", "Foo", "Bar", "map", "load"},
        ),
        (
            "swift",
            "func run(x: Int) {\n  a.b.save(x)\n  Foo(1)\n  xs.map { load($0) }\n}\n",
            {"save", "Foo", "map", "load"},
        ),
        (
            "lua",
            "function run(x)\n  a.b.save(x)\n  obj:meth(1)\n  foo(2)\n  local f = function() load() end\nend\n",
            {"save", "meth", "foo", "load"},
        ),
    ],
)
def test_qualified_bare_constructor_and_callback_callees(lang, src, expected):
    """Step 2 of #3641: kotlin / scala / swift / lua name the rightmost identifier, count a
    constructor, and keep a callback's calls with the enclosing unit (C8)."""
    assert _calls(lang, src)["run"] == expected


@pytest.mark.parametrize("lang", cga.LANGS)
def test_every_measured_language_has_a_function_map_and_a_firing_call_node(lang):
    spec = audit.NODE_MAPS[lang]
    assert spec["func_node_types"] and cga.CALL_NODE_TYPES


def test_kotlin_decoys_in_string_and_comment_are_not_calls():
    got = _calls("kotlin", 'fun run() {\n  val s = "save(1)"\n  // load(2)\n  keep()\n}\n')
    assert got == {"run": {"keep"}}


def test_swift_subscript_is_not_a_call_but_a_call_on_one_is():
    got = _calls("swift", 'func run(r: R) {\n  let h = r.headers["k"]\n  r.items[0].save()\n}\n')
    assert got == {"run": {"save"}}


def test_scala_qualified_generic_constructor_names_the_type():
    got = _calls("scala", "object A {\n  def run() = new util.HashSet[T]()\n}\n")
    assert got == {"run": {"HashSet"}}


@pytest.mark.parametrize(
    "lang, src, expected",
    [
        (
            "zig",
            'fn run(x: u8) void {\n  a.b.save(x);\n  foo(1);\n  _ = @intCast(x);\n  _ = @import("x");\n}\n',
            {"save", "foo", "intCast", "import"},
        ),
        (
            "dart",
            "class A {\n  void run(int x) {\n    a.b.save(x);\n    w?.call(1);\n    xs..sort()..clear();\n"
            "    foo(1);\n    var f = Foo(2);\n    new Bar();\n    Baz<int>(1);\n    xs.map((y) => load(y));\n  }\n}\n",
            {"save", "call", "sort", "clear", "foo", "Foo", "Bar", "Baz", "map", "load"},
        ),
        (
            "haskell",
            "run x = do\n  save x\n  Map.insert 1 x\n  print $ load x\n  return (Just x)\n",
            {"save", "insert", "print", "load", "return", "Just"},
        ),
        (
            "perl",
            'sub run {\n  my $x = shift;\n  save($x);\n  $o->meth(1);\n  Foo::bar(2);\n  print "x";\n}\n',
            {"shift", "save", "meth", "bar", "print"},
        ),
    ],
)
def test_zig_dart_haskell_perl_callee_names(lang, src, expected):
    """Step 2 of #3641: zig / dart / haskell / perl name the rightmost identifier (a zig builtin
    without its `@`), count a constructor, and keep a callback's calls with the enclosing unit."""
    assert _calls(lang, src)["run"] == expected


def test_zig_and_dart_bodies_are_siblings_of_the_signature_yet_belong_to_it():
    assert _calls("zig", "fn a() void { x(); }\nfn b() void { y(); }\n") == {"a": {"x"}, "b": {"y"}}
    got = _calls("dart", "class A {\n  void a() { x(); }\n  int get b => y();\n}\nvoid c() { z(); }\n")
    assert got["a"] == {"x"} and got["c"] == {"z"}


def test_dart_constructor_initializer_list_and_const_callees_belong_to_the_constructor():
    """#6454: the `initializers` sit beside `constructor_signature`, and `const Foo.named()` names `named`."""
    src = (
        "class A {\n  A({Foo? f, Bar? b}) : _f = f ?? const Foo(), _b = b ?? const Bar.make() {\n    go();\n  }\n"
        "  A.n(int q) : w = Baz(q);\n}\n"
    )
    got = _calls("dart", src)
    assert got["A"] == {"Foo", "make", "go"}
    assert got["A.n"] == {"Baz"}


@pytest.mark.parametrize(
    "lang, src",
    [
        ("zig", 'fn run() void {\n  const s = "save(1)"; // load(2)\n  keep();\n}\n'),
        ("dart", "void run() {\n  var s = 'save(1)'; // load(2)\n  keep();\n}\n"),
        ("haskell", 'run x = keep "save 1" -- load 2\n'),
        ("perl", 'sub run {\n  my $s = "save(1)"; # load(2)\n  keep();\n}\n'),
    ],
)
def test_decoys_in_string_and_comment_are_not_calls(lang, src):
    assert _calls(lang, src)["run"] == {"keep"}


def test_dart_index_and_list_are_not_calls_and_only_the_dollar_operator_applies_in_haskell():
    assert _calls("dart", "void run(m) {\n  var a = m['k'];\n  var b = [1];\n}\n")["run"] == set()
    assert _calls("haskell", "run x = f $ g x\n")["run"] == {"f", "g"}
    assert _calls("haskell", "run x = f x <> g . h\n")["run"] == {"f"}


def test_solidity_value_call_names_the_call_and_apex_constructors_and_methods():
    sol = _calls("solidity", "contract A{function f() public{ require(a); t.call{value: v}(d); g(1); }}")
    assert sol == {"f": {"require", "call", "g"}}
    apex = _calls("apex", "class A{void f(){ Map<Id,A> m = new Map<Id,A>(x); new Foo(); x.go(); }}")
    assert apex == {"f": {"Map", "Foo", "go"}}


def test_solidity_and_apex_are_measured():
    assert {"solidity", "apex"} <= set(cga.LANGS)


def test_haskell_constructor_patterns_are_not_calls_but_constructor_applications_are():
    """C3: `Para _` on a clause's left side, a case alternative, a lambda or a do-bind pattern matches; it does not call."""
    src = (
        "isPara (Para _) = True\n"
        "isPara _ = False\n"
        "run m = case m of\n"
        "  Left e -> fail e\n"
        "  Just (Wrap k) -> keep (Box k)\n"
        "  _ -> Nothing\n"
        "lam z = (\\(Pair a b) -> mk a b) z\n"
        "dobind m = do\n"
        "  Just x <- m\n"
        "  return (Some x)\n"
    )
    got = _calls("haskell", src)
    assert got["isPara"] == set()
    assert got["run"] == {"fail", "keep", "Box"}
    assert got["lam"] == {"mk"}
    assert got["dobind"] == {"return", "Some"}
