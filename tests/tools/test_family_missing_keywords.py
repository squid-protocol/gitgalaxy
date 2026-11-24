# ruff: noqa: S101
"""#8863: the missing-keyword mining report is a pure function of family_oracle.score() results."""

import json
import sqlite3
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import family_missing_keywords as fmk


def _fam(name, n, recall, tokens, status="misses"):
    return {
        "family": name,
        "rule": name.replace("arch_", ""),
        "oracle_functions": n,
        "recall": recall,
        "status": status,
        "missed_tokens": tokens,
    }


def _res(*fams):
    return {"families": list(fams)}


def test_tokens_rank_by_count_then_name_and_share_uses_missed_functions():
    r = {"go": _res(_fam("arch_io", 20, 0.5, [["b", 4], ["a", 4], ["c", 20]]))}
    cell = fmk.mine(r)["cells"][0]
    assert cell["missed"] == 10
    assert [t["token"] for t in cell["tokens"]] == ["c", "a", "b"]
    assert cell["tokens"][0]["per_fn"] == 2.0


def test_dead_family_misses_every_oracle_function():
    r = {"go": _res(_fam("arch_io", 12, 0.0, [["open", 12]], "dead"))}
    assert fmk.mine(r)["cells"][0]["missed"] == 12


def test_cell_without_misses_is_omitted():
    r = {"go": _res(_fam("arch_io", 20, 1.0, []), _fam("arch_time", 0, None, [], "no-instances"))}
    assert fmk.mine(r)["cells"] == []


def test_thin_cell_is_listed_but_not_ranked_or_merged():
    r = {
        "go": _res(_fam("arch_io", 3, 0.0, [["open", 3]], "dead")),
        "rust": _res(_fam("arch_io", 30, 0.0, [["open", 30]], "dead")),
    }
    m = fmk.mine(r)
    assert [c["thin"] for c in m["cells"]] == [True, False]
    assert m["shared"] == {}
    md = fmk.render_markdown(m)
    assert "go/arch_io (3 fn)" in md


def test_token_missed_in_several_languages_is_merged():
    r = {
        "go": _res(_fam("arch_io", 20, 0.0, [["open", 5], ["x", 1]], "dead")),
        "java": _res(_fam("arch_io", 20, 0.0, [["open", 7]], "dead")),
        "c": _res(_fam("arch_regex", 20, 0.0, [["open", 7]], "dead")),
    }
    shared = fmk.mine(r)["shared"]
    assert shared == {"arch_io": [{"token": "open", "count": 12, "languages": ["go", "java"]}]}


def test_top_limits_tokens_and_marks_a_result_capped_at_five():
    toks = [[f"t{i}", 10 - i] for i in range(5)]
    res = {"go": _res(_fam("arch_io", 20, 0.0, toks, "dead"))}
    assert len(fmk.mine(res, top=3)["cells"][0]["tokens"]) == 3
    assert fmk.mine(res)["cells"][0]["capped"] is True
    plain = fmk.mine({"go": _res(_fam("arch_io", 20, 0.0, toks[:2], "dead"))})["cells"][0]
    assert "capped" not in plain


def test_markdown_names_the_cell_and_the_timing_caveat():
    md = fmk.render_markdown(fmk.mine({"go": _res(_fam("arch_io", 20, 0.5, [["open", 4]]))}), skipped=["cobol"])
    assert "### go / arch_io: 10 of 20 missed" in md
    assert "| `open` | 4 | 0.4 |" in md
    assert "timed" in md
    assert "cobol" in md


SOURCE = textwrap.dedent(
    """\
    import re
    import time

    def finds(s):
        return re.finditer("a", s)

    def clock():
        return time.perf_counter()
    """
)


def _make_scan(tmp_path):
    (tmp_path / "m.py").write_text(SOURCE, encoding="utf-8")
    db = tmp_path / "scan_master.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE file_data (id INTEGER PRIMARY KEY, file_path TEXT)")
    con.execute(
        "CREATE TABLE function_data (id INTEGER PRIMARY KEY, file_id INT, func_name TEXT, start_line INT, "
        "arch_regex INT, arch_time INT)"
    )
    con.execute("INSERT INTO file_data VALUES (1, 'm.py')")
    con.executemany(
        "INSERT INTO function_data (file_id, func_name, start_line, arch_regex, arch_time) VALUES (1,?,?,0,0)",
        [("finds", 4), ("clock", 7)],
    )
    con.commit()
    con.close()
    return db


def test_scan_end_to_end_names_the_missing_callees(tmp_path, capsys):
    db = _make_scan(tmp_path)
    out = tmp_path / "out.json"
    assert fmk.main(["--scan", f"python:{db}:{tmp_path}", "--json", str(out), "--min-functions", "1"]) == 0
    got = {(c["family"], t["token"]) for c in json.loads(out.read_text())["cells"] for t in c["tokens"]}
    assert ("arch_regex", "finditer") in got
    assert ("arch_time", "perf_counter") in got
    assert "finditer" in capsys.readouterr().out


def test_result_file_round_trips(tmp_path, capsys):
    f = tmp_path / "r.json"
    f.write_text(json.dumps(_res(_fam("arch_io", 20, 0.0, [["open", 3]], "dead"))))
    assert fmk.main(["--result", f"go:{f}"]) == 0
    assert "`open`" in capsys.readouterr().out


def test_no_input_bad_spec_and_unreadable_result_exit_two(tmp_path):
    assert fmk.main([]) == 2
    assert fmk.main(["--scan", "go:onlytwo"]) == 2
    assert fmk.main(["--result", f"go:{tmp_path / 'missing.json'}"]) == 2
    assert fmk.main(["--result", "nocolon"]) == 2


def test_language_without_an_oracle_is_skipped_and_alone_exits_two(tmp_path):
    db = _make_scan(tmp_path)
    assert fmk.main(["--scan", f"cobol:{db}:{tmp_path}"]) == 2
    f = tmp_path / "r.json"
    f.write_text(json.dumps(_res(_fam("arch_io", 20, 0.0, [["open", 3]], "dead"))))
    assert fmk.main(["--scan", f"cobol:{db}:{tmp_path}", "--result", f"go:{f}"]) == 0


def test_split_keeps_a_windows_drive_letter_with_its_path():
    assert fmk._split("python:C:\\a\\s.db:D:/src", 3) == ["python", "C:\\a\\s.db", "D:/src"]
    assert fmk._split("go:C:\\r.json", 2) == ["go", "C:\\r.json"]
    assert fmk._split("go:/data/s.db:/src", 3) == ["go", "/data/s.db", "/src"]
    assert fmk._split("c:C:\\s.db:C:\\src", 3) == ["c", "C:\\s.db", "C:\\src"]
    with pytest.raises(ValueError):
        fmk._split("go:onlytwo", 3)
