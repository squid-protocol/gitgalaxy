"""C/C++ call-graph oracle (#5630): call shapes, the misparse fallbacks, recall/precision, family consensus, the gate.

Synthetic sources only (no DOOM code); each fake port is a source tree plus a minimal scan DB. The tool dir goes on
sys.path and the module is imported as a bare name (tests/ has no __init__.py).
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

sys.path.insert(0, str(Path(__file__).resolve().parent / "doom_speedrun"))

import callgraph_oracle as co  # noqa: E402

SHA = "abc123def"


def body_of(src, lang="c", line=1):
    data = src.encode()
    node = co.definition_at(co.function_nodes(co._parser(lang).parse(data)), line)
    return co.Body(node) if node is not None else co.TextBody(data, line)


def test_each_shape_is_named_by_the_calls_parent():
    body = body_of(
        """void f(int *x, int a)
{
    stmt();
    use(nested());
    if (cond()) return;
    while (loop() > 0) {}
    a = rhs();
    int b = init();
    a = (int)cast();
    a = 1 + op();
    a = !neg();
    x[sub()] = 0;
    --x[pre()];
    return ret();
}
"""
    )
    assert body.calls == {
        "stmt": "statement", "use": "statement", "nested": "nested-argument", "cond": "condition/return",
        "loop": "after-operator", "rhs": "assignment-rhs", "init": "assignment-rhs", "cast": "after-cast",
        "op": "after-operator", "neg": "after-operator", "sub": "subscript", "pre": "subscript",
        "ret": "condition/return",
    }  # fmt: skip


def test_references_macros_comments_and_absence_are_told_apart():
    body = body_of(
        """void f(void)
{
    handler = target;
#define CALL_IT() hidden()
    /* commented() */
    puts("quoted()");
}
"""
    )
    assert body.presence("target") == "function-pointer"
    assert body.presence("hidden") == "macro"
    assert body.presence("commented") == "comment/string"
    assert body.presence("quoted") == "comment/string"
    assert body.presence("nowhere") is None


def test_cpp_callees_templates_members_and_a_declaration_that_is_not_a_call():
    body = body_of(
        """void S::run(std::mutex &m)
{
    std::unique_lock<std::mutex> lock(m);
    convert<int>(1);
    obj.method();
    ptr->other();
    ns::free_fn();
    auto l = [&]() { inner(); };
}
""",
        lang="cpp",
    )
    assert set(body.calls) == {"convert", "method", "other", "free_fn", "inner"}
    assert "lock" not in body.calls and body.presence("unique_lock") == "type"


def test_an_ifdef_split_else_if_is_read_by_the_text_fallback():
    body = body_of(
        """void f(void)
{
    if (a())
    {
        b();
    }
#ifdef _WIN32
    else if (win_only("-x"))
    {
        c();
    }
#endif
}
"""
    )
    assert body.calls["win_only"] == "unparsed"
    assert {"a", "b", "c"} <= set(body.calls)


def test_a_nested_function_gets_its_own_calls_not_the_outer_function():
    """Owner ruling nyx-o8 (#5630): the engine credits a nested function's calls to the nested function."""
    src = "void outer(void)\n{\n    void inner(void)\n    {\n        a();\n    }\n    c();\n}\n"
    nodes = co.function_nodes(co._parser("c").parse(src.encode()))
    assert set(co.Body(co.definition_at(nodes, 1)).calls) == {"c"}
    assert set(co.Body(co.definition_at(nodes, 3)).calls) == {"a"}


def test_a_function_swallowed_by_a_macro_table_uses_the_brace_fallback():
    src = """TABLE_START(x)
  TABLE_ROW("a", b)
TABLE_END

static void *Start(int c)
{
    // not_this()
#define LATER() skipped()
    real(c);
    return lookup(c) ? 0 : 0;
}
"""
    body = co.TextBody(src.encode(), 5)
    assert set(body.calls) == {"real", "lookup"}  # directive lines only: code under #if 0 is read, like the engine
    assert body.calls["real"] == "unparsed"
    assert body.presence("not_this") == "comment/string"
    assert body.presence("skipped") == "macro"


def make_port(work, name, files, funcs):
    """files: {rel: source}; funcs: [(rel, name, start_line, [callees])]."""
    repo = work / "repos" / name
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    scan = work / "scans" / SHA / name
    scan.mkdir(parents=True)
    con = sqlite3.connect(scan / f"{name}_master.db")
    con.execute("create table file_data (id integer primary key, file_path text, language text)")
    con.execute("create table function_data (file_id integer, func_name text, start_line integer, calls_out_to text)")
    ids = {}
    for rel in files:
        lang = "cpp" if rel.endswith(".cpp") else "c"
        ids[rel] = con.execute("insert into file_data (file_path, language) values (?, ?)", (rel, lang)).lastrowid
    for rel, fname, start, calls in funcs:
        con.execute("insert into function_data values (?, ?, ?, ?)", (ids[rel], fname, start, json.dumps(calls)))
    con.commit()
    con.close()
    return repo, scan


SRC = """int helper(int x) { return x; }
int other(void) { return 0; }
void cb(void) {}
void top(void)
{
    helper(other());
    register_cb(cb);
}
"""


def test_body_oracle_counts_a_miss_by_shape_and_an_engine_only_reference(tmp_path):
    funcs = [("m.c", "helper", 1, []), ("m.c", "other", 2, []), ("m.c", "cb", 3, []),
             ("m.c", "top", 4, ["helper", "cb", "printf"])]  # fmt: skip
    repo, scan = make_port(tmp_path, "linuxdoom", {"m.c": SRC}, funcs)
    port = co.Port("linuxdoom", repo, co.load_port(repo, co.find_db(scan)))
    r = co.body_oracle(port)
    assert (r["oracle_calls"], r["engine_calls"], r["agree"]) == (2, 2, 1)  # printf is not a defined name
    assert (r["recall"], r["precision"]) == (0.5, 0.5)
    assert r["misses_by_shape"] == {"nested-argument": 1}
    assert r["engine_only_by_kind"] == {"function-pointer": 1}
    assert r["examples"]["miss:nested-argument"] == ["m.c:4 top -> other"]


RECURSE_SRC = """int fact(int n) { return n ? n * fact(n - 1) : 1; }
void a(void) { fact(3); }
"""


def test_a_self_edge_is_ignored_on_both_sides_and_in_the_consensus(tmp_path):
    """Recursion stays dropped from calls_out_to (#3327): the oracle must not score it as a miss or an extra edge."""
    ports = []
    for name, fact_calls in [("p1", []), ("p2", []), ("p3", []), ("p4", []), ("rec", ["fact"])]:
        repo, scan = make_port(
            tmp_path, name, {"m.c": RECURSE_SRC}, [("m.c", "fact", 1, fact_calls), ("m.c", "a", 2, ["fact"])]
        )
        ports.append(co.Port(name, repo, co.load_port(repo, co.find_db(scan))))
    for p in ports:  # engine records the recursion (rec) or not (the rest): neither changes the score
        r = co.body_oracle(p)
        assert (r["oracle_calls"], r["engine_calls"], r["agree"]) == (1, 1, 1)
        assert (r["recall"], r["precision"], r["misses_by_shape"], r["engine_only_by_kind"]) == (1.0, 1.0, {}, {})
        assert p.edges == {("a", "fact")}
    c = co.consensus(ports)
    assert (c["holes"], c["false_edge_suspects"]) == (0, 0)


VOTE_SRC = """void a(void) { b(); }
void b(void) {}
"""
NO_CALL_SRC = """void a(void) { }
void b(void) {}
"""


def test_consensus_splits_engine_misses_from_divergences_and_flags_lone_edges(tmp_path):
    ports = []
    for name, src, calls in [
        ("p1", VOTE_SRC, ["b"]), ("p2", VOTE_SRC, ["b"]), ("p3", VOTE_SRC, ["b"]), ("p4", VOTE_SRC, ["b"]),
        ("miss", VOTE_SRC, []), ("diverge", NO_CALL_SRC, []),
    ]:  # fmt: skip
        repo, scan = make_port(tmp_path, name, {"m.c": src}, [("m.c", "a", 1, calls), ("m.c", "b", 2, [])])
        ports.append(co.Port(name, repo, co.load_port(repo, co.find_db(scan))))
    c = co.consensus(ports)
    assert (c["holes"], c["engine_missed"], c["divergent"]) == (2, 1, 1)
    assert c["missed"] == [{"port": "miss", "edge": "a -> b", "votes": "4/5", "at": "m.c:1", "shape": "statement"}]
    # a lone a->b edge in the diverging port, with no call in its body, is a suspect
    lone = ports[-1]
    lone.edges.add(("b", "a"))
    assert co.consensus(ports)["suspects"][0]["edge"] == "b -> a"


def test_regressions_gate_on_recall_precision_and_consensus_counts():
    fam = ["p1", "p2"]
    base = {"ports": {"x": {"recall": 1.0, "precision": 1.0}, "gone": {"recall": 1.0, "precision": 1.0}},
            "consensus": {"family": fam, "engine_missed": 2, "false_edge_suspects": 0}}  # fmt: skip
    cur = {"ports": {"x": {"recall": 0.9995, "precision": 0.99}},
           "consensus": {"family": fam, "engine_missed": 3, "false_edge_suspects": 0}}  # fmt: skip
    assert co.regressions(cur, base) == [
        "gone: in the baseline, not in this run",
        "x: precision 1.0000 -> 0.9900",
        "consensus: engine_missed 2 -> 3",
    ]
    assert co.regressions(base, base) == []


def test_unlicensed_ports_are_refused():
    with pytest.raises(SystemExit, match="licensed"):
        co.main(["--only", "linuxdoom,not-a-licensed-port"])


def test_main_writes_results_and_fails_on_regression(tmp_path, capsys):
    funcs = [("m.c", "helper", 1, []), ("m.c", "other", 2, []), ("m.c", "cb", 3, []),
             ("m.c", "top", 4, ["helper", "other"])]  # fmt: skip
    make_port(tmp_path, "linuxdoom", {"m.c": SRC}, funcs)
    args = ["--only", "linuxdoom", "--family", "linuxdoom", "--work", str(tmp_path), "--sha", SHA]
    base = tmp_path / "baseline.json"
    assert co.main([*args, "--write-baseline", str(base)]) == 0
    written = json.loads(base.read_text())
    assert written["ports"]["linuxdoom"]["recall"] == 1.0 and "examples" not in written["ports"]["linuxdoom"]
    assert (tmp_path / "results" / SHA / "callgraph.md").read_text().startswith("# C/C++ call-graph oracle")
    written["ports"]["linuxdoom"]["precision"] = 1.0
    written["ports"]["doomgeneric"] = {"recall": 1.0, "precision": 1.0}
    base.write_text(json.dumps(written))
    assert co.main([*args, "--baseline", str(base), "--fail-on-regression"]) == 1
    assert "REGRESSION doomgeneric: in the baseline, not in this run" in capsys.readouterr().out


EARLY_CLOSE_SRC = """int helper(int x) { return x; }
char *f(void)
{
  COUNTER_MACRO
  if (!base)
    log_it(base);
  return helper(1);
}
void log_it(char *s) {}
"""


def test_a_body_tree_sitter_closes_early_on_a_parse_error_uses_the_brace_fallback(tmp_path, monkeypatch):
    # tree-sitter's error recovery around a bare macro statement is too fickle to pin with synthetic text, so stand in
    # a one-line erroneous definition for what it returned on the real port
    broken = co.function_nodes(co._parser("c").parse(b"char *f(void) { x = ) ; }"))[0]
    assert co.Body(broken).broken
    real = co.definition_at
    monkeypatch.setattr(co, "definition_at", lambda nodes, line: broken if line == 2 else real(nodes, line))
    funcs = [("m.c", "helper", 1, []), ("m.c", "f", 2, ["log_it", "helper"]), ("m.c", "log_it", 9, [])]
    repo, scan = make_port(tmp_path, "linuxdoom", {"m.c": EARLY_CLOSE_SRC}, funcs)
    r = co.body_oracle(co.Port("linuxdoom", repo, co.load_port(repo, co.find_db(scan))))
    # 2: log_it too, whose only parse is the bare-macro `if` "definition" below (see the next test)
    assert (r["recall"], r["precision"], r["text_fallback_functions"]) == (1.0, 1.0, 2)


def test_a_bare_macro_statement_misparsed_as_a_definition_named_if_neither_swallows_nor_matches(tmp_path):
    # srb2's lua_baselib.c (#6266): `COUNTER_MACRO\n if (!base)` parses as a K&R definition named `if` whose head runs
    # over the functions below. Matching it gave later functions the wrong body; walking it gave f the file's calls.
    tree = co._parser("c").parse(EARLY_CLOSE_SRC.encode())
    nodes = co.function_nodes(tree)
    assert [co._keyword_named(n) for n in nodes] == [False, False, True]
    assert co.Body(nodes[1]).broken
    assert co.definition_at(nodes, 9) is None
    funcs = [("m.c", "helper", 1, []), ("m.c", "f", 2, ["log_it", "helper"]), ("m.c", "log_it", 9, [])]
    repo, scan = make_port(tmp_path, "linuxdoom", {"m.c": EARLY_CLOSE_SRC}, funcs)
    r = co.body_oracle(co.Port("linuxdoom", repo, co.load_port(repo, co.find_db(scan))))
    assert (r["recall"], r["precision"]) == (1.0, 1.0)


CTOR_SRC = """struct Base { Base(int v); virtual ~Base(); };
struct Mid : public Base { Mid(int v) : Base(v), mode(v) { setup(); } int mode; void setup(); };
template <class T> class Wrap final : Base { Wrap() : Base(1), T(2) {} };
int mode(int x) { return x; }
"""


def test_a_base_class_initializer_is_a_constructor_call_and_a_member_entry_is_not(tmp_path):
    # doom3-bfg / gzdoom / doomsday (#6266): `: Base(v)` is a field_initializer, outside the body tree-sitter walks, so
    # the engine's real constructor edge read as engine-only. A member entry naming a function stays engine-only.
    funcs = [
        ("m.cpp", "Base", 1, []),
        ("m.cpp", "Mid", 2, ["Base", "mode", "setup"]),
        ("m.cpp", "mode", 4, []),
    ]
    repo, scan = make_port(tmp_path, "doom3-bfg", {"m.cpp": CTOR_SRC}, funcs)
    bases = co.class_names(repo)  # class -> the base classes its head lists
    assert bases["Mid"] == {"Base"} and bases["Wrap"] == {"Base"}
    port = co.Port("doom3-bfg", repo, co.load_port(repo, co.find_db(scan)))
    mid = next(f for f in port.functions if f[1] == "Mid")
    assert mid[4].calls["Base"] == "ctor-init" and "mode" not in mid[4].calls
    r = co.body_oracle(port)
    assert r["engine_only_by_kind"] == {"absent": 1}  # `mode(v)`, the member
    assert "ctor-init" not in r["misses_by_shape"] and r["recall"] == 1.0


@pytest.mark.parametrize("vendor_dir", ["third_party_sdl", "3rdparty-png", "zlib", "jpeg-6"])
def test_vendored_functions_are_neither_callers_nor_defined_names(tmp_path, vendor_dir):
    """Every engine vendor rule, whole input class (#6097): a library's function is not an oracle edge target or source."""
    files = {"m.c": "void top(void) { inflate(); }\n", f"{vendor_dir}/z.c": "void inflate(void) {}\n"}
    funcs = [("m.c", "top", 1, ["inflate"]), (f"{vendor_dir}/z.c", "inflate", 1, [])]
    repo, scan = make_port(tmp_path, "linuxdoom", files, funcs)
    db = co.find_db(scan)
    assert {r[2] for r in co.load_port(repo, db)} == {"top", "inflate"}  # no test: nothing dropped
    rows = co.load_port(repo, db, co.doom_scorer._engine_vendor_test(repo))
    assert [r[2] for r in rows] == ["top"]
    r = co.body_oracle(co.Port("linuxdoom", repo, rows))
    assert (r["oracle_calls"], r["engine_calls"]) == (0, 0)  # inflate is no longer a name the port defines


def test_the_ts_oracle_loader_drops_vendored_code_too(tmp_path):
    import ts_callgraph_oracle as ts

    files = {"m.c": "void top(void) {}\n", "zlib/z.c": "void inflate(void) {}\n"}
    funcs = [("m.c", "top", 1, []), ("zlib/z.c", "inflate", 1, [])]
    repo, scan = make_port(tmp_path, "linuxdoom", files, funcs)
    db = co.find_db(scan)
    con = sqlite3.connect(db)
    con.execute("update file_data set language = 'go'")
    con.commit()
    con.close()
    assert len(ts.load_port(repo, db)) == 2
    assert [r[2] for r in ts.load_port(repo, db, co.doom_scorer._engine_vendor_test(repo))] == ["top"]


def test_the_objc_oracle_drops_vendored_code_too(tmp_path):
    import objc_callgraph_oracle as oc

    repo = tmp_path / "repo"
    (repo / "zlib").mkdir(parents=True)  # the vendor detector reads the directory on disk
    db = tmp_path / "scan.db"
    con = sqlite3.connect(db)
    con.execute("create table file_data (id integer primary key, file_path text, language text)")
    con.execute(
        "create table function_data (file_id integer, func_name text, start_line integer, loc integer, calls_out_to text)"
    )
    for fid, rel in enumerate(["Game.m", "zlib/z.m"], 1):
        con.execute("insert into file_data values (?, ?, 'objective-c')", (fid, f"{repo}/{rel}"))
        con.execute("insert into function_data values (?, 'f', 1, 1, '[]')", (fid,))
    con.commit()
    con.close()
    assert oc.score(repo, db)["units"] == 2  # no test: nothing dropped
    assert oc.score(repo, db, vendored=co.doom_scorer._engine_vendor_test(repo))["units"] == 1


@pytest.mark.parametrize(
    "method",
    [
        "Hash &hashFor(int s) { return lookup(s); }",
        "Item *find(int s) const { return lookup(s); }",
        "Item **findAll(int s) { return lookup(s); }",
        "const Item &get(int s) const { return lookup(s); }",
        "void plain(int s) { lookup(s); }",
        "~Impl() { lookup(0); }",
    ],
)
def test_a_macro_class_method_with_a_pointer_or_reference_return_is_its_own_unit(method):
    """`DE_PIMPL(X) { ... };` reads as one definition; its methods own their calls whatever they return (#6266)."""
    body = body_of(f"DE_PIMPL(X)\n{{\n    {method}\n    int field = direct();\n}};\n", "cpp")
    assert set(body.calls) == {"direct"}
    assert len(body.nested) == 1


@pytest.mark.parametrize(
    ("init", "calls", "types"),
    [
        (": d(new Impl(this))", set(), {"Impl"}),  # doomsday's PIMPL idiom: a construction, not a named call
        (": size(count(v))", {"count"}, set()),  # a call in the argument list is a call; the member `size` is not
        (": Base(v), d(make(v), new Impl(this))", {"make"}, {"Impl"}),
        (": a{helper(v)}", {"helper"}, set()),  # brace initialisation
    ],
)
def test_the_arguments_of_a_member_initializer_are_part_of_the_constructor(init, calls, types):
    """`: d(new Impl(this))` sits outside the body tree-sitter walks; its arguments still belong to the constructor (#6266)."""
    body = body_of(f"Widget::Widget(int v) {init}\n{{\n}}\n", "cpp")
    assert set(body.calls) == calls
    assert body.types == types


@pytest.mark.parametrize(
    ("head", "owner"),
    [
        ("Widget::Widget(int v) : Base(v) {}", "Widget"),
        ("Dialog::ButtonItem::ButtonItem(int v) : ui::ActionItem(v) {}", "ButtonItem"),  # doomsday: `A::B::B` nests
        ("a::b::C::C(int v) : Base(v) {}", "C"),
    ],
)
def test_a_nested_qualified_constructor_belongs_to_its_innermost_scope(head, owner):
    """The class a base-class entry is checked against is the one named last before the constructor (#6266)."""
    node = co.definition_at(co.function_nodes(co._parser("cpp").parse(head.encode())), 1)
    assert co._owner(node) == owner
    classes = {owner: {"Base", "ActionItem"}, "Dialog": {"Other"}}
    assert set(co.Body(node, classes).calls) >= {"ActionItem" if "ui::" in head else "Base"}


MACRO_CLASS = """DE_PIMPL(Surface),
DE_OBSERVES(Variable, Deletion)
{
    Mat3f tangent = makeTangent();
    bool isValid() const;
    void update() override;
    int slot = 0;

    Impl(Public *i)
        : Base(i)
        , var(&variable)
    {
        nestedCall();
    }

    void other()
    {
        moreCalls();
    }
};
"""


def test_a_macro_class_owns_only_its_member_initializer_calls():
    body = co.TextBody(MACRO_CLASS.encode(), 1)
    assert set(body.calls) == {"makeTangent"}  # not the declarations, the ctor head, or the methods' calls


def test_a_macro_statement_with_a_brace_body_keeps_every_call():
    src = "DE_FOR_EACH(i, list)\n{\n    stmt();\n    other(1);\n}\n"
    assert set(co.TextBody(src.encode(), 1).calls) == {"stmt", "other"}


@pytest.mark.parametrize(
    "stmt",
    [
        "DE_FOR_EACH_CONST(Map::Elements, i, dict.elements())\n    {\n        inner(i);\n    }",
        "DE_NOTIFY_PUBLIC(Swap, i) { inner(i); }",
        "DE_FOR_OBSERVERS(i, audience())\n        inner(i);",
    ],
)
def test_a_macro_statement_loop_is_part_of_its_function_not_a_nested_one(stmt):
    """The engine reads `DE_FOR_EACH*` / `DE_NOTIFY*` as a statement of the enclosing function; so does the oracle."""
    body = body_of(f"void run(Dict &d)\n{{\n    {stmt}\n}}\n", "cpp")
    assert "inner" in body.calls
    assert body.nested == []


GATED = """void build(int ver)
{
    first();
    GATE(7)
    {
        gated();
    }
    else
    {
        other();
    }
    for (int i = 0; i < 3; i++)
    {
        late(i);
    }
}
"""


def test_an_if_macro_that_closes_the_node_early_is_flagged_and_the_braces_reach_the_real_end():
    """`GATE(7) {..} else {..}` ends the tree-sitter node with no ERROR; the loop below it parses as file-scope code."""
    body = body_of(GATED, "cpp")
    assert body.broken  # the oracle then reads the brace-matched text, which reaches the closing line
    text = co.TextBody(GATED.encode(), 1)
    assert text.end_line == GATED.count("\n")
    assert {"first", "gated", "other", "late"} <= set(text.calls)


def test_a_function_followed_by_a_declaration_is_not_flagged():
    assert not body_of("void f()\n{\n    g();\n}\n\nint x = 1;\n", "cpp").broken


@pytest.mark.parametrize(
    "stmt",
    [
        "IFVM(Runner, CanWipe)\n    {\n        inner(1);\n    }",
        'IFVIRTUALPTRNAME(act, "SectorAction", TriggerAction)\n        {\n            inner(act);\n        }',
        "IFVIRTUAL(DObject, Tick) { inner(); }",
    ],
)
def test_a_vm_call_macro_block_is_part_of_its_function_not_a_nested_one(stmt):
    """The engine reads gzdoom's `IFVM` / `IFVIRTUAL*` blocks as a statement of the enclosing function; so does the oracle."""
    body = body_of(f"bool run(AActor *act)\n{{\n    {stmt}\n    return true;\n}}\n", "cpp")
    assert "inner" in body.calls
    assert body.nested == []


def test_text_fallback_names_an_explicit_destructor_call_by_its_unit():
    # a `<` in `->~TArray<T>()` makes tree-sitter misparse the body; the text view must still name `~T`, not `T`
    body = body_of("void f(Node *p, int a)\n{\n    p->~Node();\n    a = ~g(a);\n}\n", "cpp")
    assert body.calls["~Node"] == "statement" and body.calls["g"] != "statement"
    body = co.TextBody(b"void f() { p->~Node(); q.~Item (); a = ~g(a); }", 1)
    assert {"~Node", "~Item", "g"} <= set(body.calls)
    assert "Node" not in body.calls and "Item" not in body.calls
