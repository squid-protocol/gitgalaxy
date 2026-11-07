"""cics_crucible_gap (#7956): det-modelled commands/options with no crucible case, ranked by use. Synthetic trees only."""

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")  # the det translator (OPTIONS, parse_exec) is read live

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_crucible_gap as gap


def fixed(*code: str) -> str:
    return "\n".join(f"{i * 100:06d}       {c}" for i, c in enumerate(code, 1)) + "\n"


def prog(*cmds: str) -> str:
    lines = []
    for c in cmds:
        lines += [f"EXEC CICS {c}", "END-EXEC."]
    return fixed(*lines)


def tree(tmp_path: Path):
    cr = tmp_path / "cr"
    case = cr / "cases" / "trap" / "case-a" / "src"
    case.mkdir(parents=True)
    (case / "A.cbl").write_text(prog("SEND MAP('M') MAPSET('S') ERASE", "GET CONTAINER('C') INTO(X)"))
    (case / "B.pli").write_text("EXEC CICS DELAY;")  # PL/I: not read
    roots = tmp_path / "corpora"
    (roots / "cics-banking-sample-application-cbsa").mkdir(parents=True)
    (roots / "cics-banking-sample-application-cbsa" / "P1.cbl").write_text(
        prog("DELAY FOR SECONDS(1)", "SEND MAP('M') MAPSET('S') FREEKB")
    )
    (roots / "cics-banking-sample-application-cbsa" / "P2.cbl").write_text(prog("DELAY FOR SECONDS(2)"))
    (roots / "other").mkdir()
    (roots / "other" / "Q.cbl").write_text(prog("DELAY FOR SECONDS(3) NOHANDLE"))
    return cr, roots


def test_command_uses_keys_and_options():
    u = gap.command_uses(prog("SEND MAP('M') MAPSET('S') ERASE RESP(R)", "GET DCOUNTER('D') VALUE(V)", "FOO BAR(1)"))
    assert u["SEND MAP"] >= {"", "MAPSET", "ERASE"}
    assert "RESP" not in u["SEND MAP"] and "MAP" not in u["SEND MAP"]
    assert "GET COUNTER" in u  # DCOUNTER is GET COUNTER's entry
    assert not any("FOO" in k for k in u)  # not modelled: not a use


def test_multi_word_form_option_keys():
    u = gap.command_uses(prog("WEB READ HTTPHEADER(N) NAMELENGTH(1) VALUE(V) VALUELENGTH(L)"))
    assert "WEB READ HTTPHEADER" in u


def test_gaps_rank_and_classes(tmp_path):
    cr, roots = tree(tmp_path)
    res = gap.gaps(cr, [roots])
    cmds = {r["command"]: r for r in res["commands"]}
    assert "DELAY" in cmds and "SEND MAP" not in cmds and "GET CONTAINER" not in cmds  # PL/I case ignored
    assert cmds["DELAY"]["burned_programs"] == 2  # CBSA is burned; "other" is census
    assert cmds["DELAY"]["census_programs"] == 1
    assert res["commands"][0]["command"] == "DELAY"  # most used first
    opts = {(r["command"], r["option"]): r for r in res["options"]}
    assert opts[("SEND MAP", "FREEKB")]["burned_programs"] == 1
    assert ("SEND MAP", "ERASE") not in opts  # a case issues it
    assert ("SEND MAP", "MAPSET") not in opts
    assert all(r["command_covered"] for r in res["options"])
    assert res["options_of_uncovered_commands"] > 0
    assert res["covered_commands"] == 2


def test_report_has_counts_only_for_census(tmp_path):
    cr, roots = tree(tmp_path)
    res = gap.gaps(cr, [roots])
    text = gap.format_report(res)
    assert "other" not in text and "Q.cbl" not in text and "P1" not in text  # no census / program names
    assert "cics-banking-sample-application-cbsa" in text  # burned corpora are named
    assert "census: not measured" in gap.format_report(res, census=False)
    assert "... " in gap.format_report(res, top=1)
    json.dumps(res)


def test_main_needs_a_crucible(monkeypatch, capsys):
    monkeypatch.delenv("CICS_CRUCIBLE_PATH", raising=False)
    assert gap.main([]) == 2
    assert "no cics-crucible checkout" in capsys.readouterr().err


def test_main_json(tmp_path, capsys, monkeypatch):
    cr, roots = tree(tmp_path)
    monkeypatch.delenv("CICS_CENSUS_CORPORA", raising=False)
    assert gap.main(["--crucible", str(cr), "--corpora", str(roots), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["census_measured"] is False
    assert out["commands"][0]["command"] == "DELAY"
