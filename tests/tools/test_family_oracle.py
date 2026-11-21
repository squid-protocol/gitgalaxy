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
        ("def f(x):\n    return x & 3 | 1", "bitwise", 0),
        ("def f():\n    time.sleep(1)", "sleep", 1),
        ("def f():\n    subprocess.run(['ls'])", "danger", 1),
        ("def f(s):\n    return eval(s)", "danger", 1),
        ("def f(s):\n    return json.loads(s)", "unsafe_deserialize", 0),
        ("def f(s):\n    return pickle.loads(s)", "unsafe_deserialize", 1),
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
    assert "arch_regex" in text and "unsafe deserialization only" in text
