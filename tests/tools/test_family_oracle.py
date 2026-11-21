# ruff: noqa: S101
"""#8863: the keyword-family validity tool scores a family against what a parser says the function does.

Small cases, one construct each, so a regression names itself; then a miniature scan database with known answers.
"""

import ast
import json
import sqlite3
import sys
import textwrap
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS.parents[1]))
sys.path.insert(0, str(TOOLS))
import family_oracle as fo  # noqa: E402


def _counts(src: str) -> dict:
    fn = ast.parse(textwrap.dedent(src)).body[0]
    return dict(fo.python_oracle(fn).n)


@pytest.mark.parametrize(
    ("src", "key", "want"),
    [
        ("@staticmethod\n@property\ndef f(): pass", "decorators", 2),
        ("def f():\n    return time.perf_counter()", "time", 1),
        ("def f(p):\n    return Path(p).read_text()", "io", 1),
        ("def f(a, b):\n    return os.path.join(a, b)", "io", 0),
        ("def f():\n    sys.exit(2)", "io", 0),
        ("def f():\n    return PAT.finditer(s)", "regex", 1),
        ('def f():\n    return re.compile(r"^a|~b<<")', "bitwise", 0),
        ("def f(x):\n    return x << 2", "bitwise", 1),
        ("def f(x):\n    return ~x", "bitwise", 1),
        ("def f(x):\n    return x & 3 | 1", "bitwise", 2),  # the contract counts and/or in operator position
        ("def f(a, b, *c, d=1, **e):\n    pass", "args", 5),
        ("def f():\n    time.sleep(1)", "sleep", 1),
        ("def f():\n    subprocess.run(['ls'])", "danger", 1),
        ("def f(s):\n    return eval(s)", "danger", 1),
        ("def f(s):\n    return json.loads(s)", "serialization", 1),  # json is a structured interchange format
        ("def f(s):\n    return pickle.loads(s)", "serialization", 1),
        ("def f(xs):\n    return [x for x in xs]", "closures", 0),
        (
            "def f(xs):\n    g = lambda x: x\n    def h(): pass",
            "closures",
            1,
        ),  # a lambda is anonymous; a nested def is a declaration
        ("def f(p):\n    p.close()", "cleanup", 1),
        ("def f(xs):\n    return map(str, xs)", "comprehensions", 1),
        ("def f() -> Generator[int, None, None]:\n    return g()", "lazy", 1),
        ("def f(xs):\n    return (x for x in xs)", "lazy", 0),
        ("def f():\n    yield 1", "lazy", 1),
        ("def f(a):\n    if a and a > 1:\n        return 1\n    return 0", "branch", 2),
        ("def f():\n    '''doc'''\n    return 1", "doc", 1),
    ],
)
def test_oracle_reads_one_construct(src, key, want):
    assert _counts(src).get(key, 0) == want


def test_missed_token_names_the_construct():
    fn = ast.parse("def f(s):\n    return PAT.fullmatch(s)").body[0]
    assert fo.python_oracle(fn).tokens["regex"]["fullmatch"] == 1


def test_spearman_ties_and_constants():
    assert fo.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert fo.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert fo.spearman([1, 1, 1], [1, 2, 3]) is None
    assert fo.spearman([1], [1]) is None


def test_status_labels():
    bars = {"recall_bar": 0.8, "precision_bar": 0.8}
    assert fo.status(0, 0, None, None, **bars) == "no-instances"
    assert fo.status(0, 3, None, 0.0, **bars) == "over-counts"
    assert fo.status(10, 0, 0.0, None, **bars) == "dead"
    assert fo.status(10, 10, 0.5, 1.0, **bars) == "misses"
    assert fo.status(10, 10, 1.0, 0.5, **bars) == "over-counts"
    assert fo.status(10, 10, 0.5, 0.5, **bars) == "both"
    assert fo.status(10, 10, 0.9, 0.9, **bars) == "ok"


SOURCE = textwrap.dedent(
    """\
    import re
    import time
    import os

    PAT = re.compile("a+")


    def finds(s):
        return PAT.finditer(s)


    def clock():
        return time.perf_counter()


    def joins(a, b):
        return os.path.join(a, b)


    @staticmethod
    def deco():
        return 1
    """
)


def _make_scan(tmp_path):
    """A scan database holding the columns the tool reads, with answers chosen to give known recall and precision."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "m.py").write_text(SOURCE, encoding="utf-8")
    db = tmp_path / "scan_master.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE file_data (id INTEGER PRIMARY KEY, file_path TEXT)")
    con.execute(
        "CREATE TABLE function_data (id INTEGER PRIMARY KEY, file_id INT, func_name TEXT, start_line INT, "
        "arch_regex INT, arch_time INT, arch_io INT, struct_decorators INT)"
    )
    con.execute("INSERT INTO file_data VALUES (1, 'scanned_copy/pkg/m.py')")  # the scan's path is not the on-disk path
    # name, line, arch_regex, arch_time, arch_io, struct_decorators
    rows = [
        ("finds", 8, 0, 0, 0, 0),  # a regex method the family misses
        ("clock", 12, 0, 0, 0, 0),  # a clock the family misses
        ("joins", 16, 0, 0, 1, 0),  # path string work the family counts as I/O
        ("deco", 20, 0, 0, 0, 0),  # decorator on the `def` line - 1
        ("ghost", 99, 0, 0, 0, 0),  # a function the parser cannot find
    ]
    con.executemany(
        "INSERT INTO function_data (file_id, func_name, start_line, arch_regex, arch_time, arch_io, struct_decorators) VALUES (1,?,?,?,?,?,?)",
        rows,
    )
    con.commit()
    con.close()
    return db


def test_score_known_answers(tmp_path):
    result = fo.score(_make_scan(tmp_path), tmp_path)
    by = {f["family"]: f for f in result["families"]}
    assert result["matched"] == 4
    assert result["unmatched"] == 1
    assert by["arch_regex"]["status"] == "dead"  # the oracle sees one regex method; the family never fires
    assert by["arch_regex"]["missed_tokens"] == [("finditer", 1)]
    assert by["arch_time"]["status"] == "dead"
    assert by["arch_time"]["missed_tokens"] == [("perf_counter", 1)]
    assert by["arch_io"]["oracle_functions"] == 0
    assert by["arch_io"]["family_functions"] == 1
    assert by["arch_io"]["status"] == "over-counts"
    assert by["struct_decorators"]["status"] == "dead"  # a decorated function, found by its first decorator's line


def test_families_missing_from_the_scan_are_skipped(tmp_path):
    result = fo.score(_make_scan(tmp_path), tmp_path)
    assert {f["family"] for f in result["families"]} == {"arch_regex", "arch_time", "arch_io", "struct_decorators"}


def test_gate_and_cli(tmp_path, capsys):
    db = _make_scan(tmp_path)
    floors = tmp_path / "floors.json"
    out = tmp_path / "out.json"
    floors.write_text(json.dumps({"arch_regex": {"recall": 0.5}}), encoding="utf-8")
    assert fo.main([str(db), "--src", str(tmp_path), "--json", str(out), "--gate", str(floors)]) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["matched"] == 4
    assert "GATE: arch_regex: recall" in capsys.readouterr().err
    floors.write_text(json.dumps({"arch_io": {"recall": 0.0}, "nope": {"recall": 1.0}}), encoding="utf-8")
    assert (
        fo.main([str(db), "--src", str(tmp_path), "--gate", str(floors)]) == 1
    )  # a family not in the scan fails the gate
    floors.write_text(json.dumps({"arch_io": {"precision": 0.0}}), encoding="utf-8")
    assert fo.main([str(db), "--src", str(tmp_path), "--gate", str(floors)]) == 0


def test_unknown_language_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="no oracle"):
        fo.score(_make_scan(tmp_path), tmp_path, "cobol")


def test_list_families(capsys):
    assert fo.main(["--list-families"]) == 0
    text = capsys.readouterr().out
    assert "arch_regex" in text and "structured interchange format" in text


# ---- tree-sitter oracles (#8863): one construct per case, per language ----
import family_oracle_ts as ts_oracle  # noqa: E402  (imports tree-sitter lazily, so this always loads)

try:
    import tree_sitter_language_pack  # noqa: F401

    HAVE_TS = True
except ImportError:
    HAVE_TS = False
needs_ts = pytest.mark.skipif(not HAVE_TS, reason="tree_sitter_language_pack (the translator extra) is not installed")


def _ts_counts(lang: str, src: str, name: str, line: int = 0) -> dict:
    oracle = ts_oracle.get_oracle(lang)
    index = oracle.index(textwrap.dedent(src))
    node = next(n for (nm, ln), n in index.items() if nm == name and (not line or ln == line))
    counts, _ = oracle.count(node)
    return dict(counts)


@needs_ts
@pytest.mark.parametrize(
    ("lang", "src", "name", "key", "want"),
    [
        (
            "java",
            "class A {\n  int f(Map<String, List<String>> m) { return 1; }\n}",
            "f",
            "bitwise",
            0,
        ),  # closing generics are not a shift
        ("java", "class A {\n  int f(int a) { return a << 2; }\n}", "f", "bitwise", 1),
        ("java", "class A {\n  int f() { try { return 1; } catch (Exception e) { return 2; } }\n}", "f", "branch", 1),
        ("java", "class A {\n  @Override @Deprecated\n  public int f() { return 1; }\n}", "f", "decorators", 2),
        ("java", "class A {\n  void f() { Thread.sleep(1); }\n}", "f", "sleep", 1),
        ("rust", 'fn f() { let s = ">> ^ ~ <<"; }', "f", "bitwise", 0),  # characters in a string
        ("rust", "fn f(a: u32) -> u32 { a << 2 ^ a }", "f", "bitwise", 2),
        ("rust", '#[inline]\nfn f() { println!("x"); }', "f", "decorators", 1),
        ("rust", "fn f() { std::process::exit(1); }", "f", "bailout", 1),
        ("rust", "fn f(a: i32, b: i32) { let c = |x: i32| x + a; }", "f", "closures", 1),
        ("go", "package m\nfunc F(a, b int, c string) {}", "F", "args", 3),  # `a, b int` is two parameters
        ("go", 'package m\nfunc F() { fmt.Println("x") }', "F", "print", 1),
        ("go", "package m\nfunc F() { g := func() {}; g() }", "F", "closures", 1),
        ("go", "package m\nfunc F(a int) int { if a > 1 && a < 5 { return 1 }; return 0 }", "F", "branch", 2),
        ("c", "int f(int a, char *b) { return a; }", "f", "args", 2),
        ("c", "int f(void) { return 1; }", "f", "args", 0),
        ("c", 'int f(void) { printf("a >> b"); return 1; }', "f", "bitwise", 0),
        ("c", "int f(int a) { return a ? 1 : 2; }", "f", "branch", 1),
        ("javascript", "function f(a) { return /a+/.test(a); }", "f", "regex", 2),  # the literal and the .test call
        ("javascript", "const f = (a) => { setTimeout(a, 1); };", "f", "sleep", 1),  # an arrow function bound to a name
        ("javascript", "function f() { return 1; }", "f", "closures", 0),  # the `function` keyword is not a closure
        ("typescript", "function f(m: Map<string, Array<string>>) { return m; }", "f", "bitwise", 0),
        ("typescript", "function f(a: number) { throw new Error('x'); }", "f", "bailout", 1),
        ("java", "class A {\n  int f(int a, int b) { return a & b | 1; }\n}", "f", "bitwise", 2),
        ("java", "class A {\n  int f(int a) { a |= 4; return a; }\n}", "f", "bitwise", 1),  # compound assignment
        (
            "go",
            "package m\nfunc F() time.Duration { return time.Duration(3) * time.Second }",
            "F",
            "time",
            1,
        ),  # duration arithmetic is time logic
        (
            "go",
            'package m\nfunc F(w io.Writer) { fmt.Fprintf(w, "x") }',
            "F",
            "print",
            0,
        ),  # output to a writer is not a debug print
        ("rust", "fn f() { let d = Instant::now(); }", "f", "time", 1),
        (
            "c",
            "int f(int a) { assert(a); return a; }",
            "f",
            "bailout",
            0,
        ),  # assert is a conditional check, not an abort statement
    ],
)
def test_treesitter_oracle_reads_one_construct(lang, src, name, key, want):
    assert _ts_counts(lang, src, name).get(key, 0) == want


@needs_ts
@pytest.mark.parametrize(
    ("lang", "src", "name", "want"),
    [
        ("c", "/* plain comment */\nint f(void) { return 1; }", "f", 0),
        ("c", "/** Doxygen */\nint f(void) { return 1; }", "f", 1),
        ("java", "class A {\n  /** javadoc */\n  int f() { return 1; }\n}", "f", 1),
        ("rust", "/// doc\nfn f() {}", "f", 1),
        ("rust", "// plain\nfn f() {}", "f", 0),
        ("go", "package m\n// F does a thing.\nfunc F() {}", "F", 1),
    ],
)
def test_documented_means_structured_documentation(lang, src, name, want):
    assert _ts_counts(lang, src, name).get("doc", 0) == want


@needs_ts
def test_decorated_rust_function_is_keyed_by_its_first_attribute_line():
    index = ts_oracle.get_oracle("rust").index("#[test]\n#[inline]\nfn f() {}\n")
    assert ("f", 1) in index  # a scan keys it by the first attribute's line
    assert ("f", 3) in index


def test_every_spec_lists_families_the_tool_can_score():
    for lang in ts_oracle.languages():
        columns = {f.column for f in ts_oracle.get_oracle(lang).families}
        assert {"struct_branch", "args", "bitwise_ops", "state_print_hits"} <= columns, lang


def test_update_baseline_merges_cells_and_never_demotes_a_pinned_one(tmp_path):
    result = fo.score(_make_scan(tmp_path), tmp_path)
    base = tmp_path / "baseline.json"
    assert fo.update_baseline(base, result, "crucible v1", pinned=True) == 4
    cells = json.loads(base.read_text(encoding="utf-8"))["cells"]["python"]
    assert set(cells) == {"regex_execution", "time_date_logic", "io", "decorators"}
    assert cells["regex_execution"]["status"] == "dead"
    assert cells["regex_execution"]["pinned"] is True
    # an exploratory rescan does not overwrite the pinned cells...
    fo.update_baseline(base, result, "some repo", pinned=False)
    assert json.loads(base.read_text(encoding="utf-8"))["cells"]["python"]["io"]["corpus"] == "crucible v1"
    # ...but a pinned rescan does
    fo.update_baseline(base, result, "crucible v2", pinned=True)
    assert json.loads(base.read_text(encoding="utf-8"))["cells"]["python"]["io"]["corpus"] == "crucible v2"


def test_a_no_instances_result_does_not_displace_an_informative_one_from_another_corpus():
    informative = {"recall": 0.5, "precision": 1.0, "status": "misses", "corpus": "a", "pinned": False, "n_oracle": 50}
    empty = {"recall": None, "precision": None, "status": "no-instances", "corpus": "b", "pinned": False, "n_oracle": 0}
    assert fo._keeps_old(informative, empty) is True
    assert fo._keeps_old(informative, {**empty, "corpus": "a"}) is False  # a rescan of the same corpus replaces itself
    assert fo._keeps_old(None, empty) is False
    thin_pinned = {"recall": 1.0, "precision": 1.0, "status": "ok", "corpus": "crucible", "pinned": True, "n_oracle": 3}
    assert fo._keeps_old(informative, thin_pinned) is True  # three functions do not displace fifty
    assert fo._keeps_old({**informative, "n_oracle": 4}, thin_pinned) is False  # both thin: the pinned one wins


def test_cli_writes_the_baseline(tmp_path):
    db = _make_scan(tmp_path)
    base = tmp_path / "b.json"
    assert fo.main([str(db), "--src", str(tmp_path), "--corpus", "x", "--update-baseline", str(base)]) == 0
    assert "io" in json.loads(base.read_text(encoding="utf-8"))["cells"]["python"]
