"""The engine-vs-translator fact cross-check (#4273): tests/tools/fact_crosscheck.py and
tests/tools/referees/translator_adapter.py.

No corpus is scanned here (the Fact Cross-check workflow does that); these tests pin the comparison
rules, the gate, the committed ledger's integrity, and the translator adapter on a toy program.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
for p in (str(TOOLS), str(TOOLS / "referees")):
    if p not in sys.path:
        sys.path.insert(0, p)

import fact_crosscheck as X
import translator_adapter as TA


def _doc(source: str, files: dict) -> dict:
    return {
        "schema": "referee-facts/1",
        "source": source,
        "channels": list(X.COMPARED) + ["program_ids"],
        "files": files,
    }


def _file(facts: dict, status: str = "ok", failed: list | None = None, error: str | None = None) -> dict:
    return {"status": status, "error": error, "failed": failed or [], "facts": {"program_ids": ["P"], **facts}}


def _key(files: dict) -> dict:
    return {"files": files}


# ------------------------------------------------------------------------------
# compare
# ------------------------------------------------------------------------------
def test_compare_lists_each_side_only_value_with_an_id() -> None:
    eng = _doc("engine", {"A.cbl": _file({"units": ["P1", "P2"], "edges": ["P1 -> PERFORM P2"]})})
    tr = _doc("translator", {"A.cbl": _file({"units": ["P1", "P3"], "edges": ["P1 -> PERFORM P2"]})})
    res = X.compare("toy", eng, tr, _key({}), set())
    ids = sorted(d["id"] for d in res["disagreements"])
    assert ids == ["toy :: units | A.cbl | engine | P2", "toy :: units | A.cbl | translator | P3"]
    assert res["stats"]["units"]["both"] == 1 and res["stats"]["edges"]["both"] == 1


def test_a_refused_division_is_one_status_disagreement_not_a_flood() -> None:
    eng = _doc("engine", {"A.cbl": _file({"units": ["P1"], "data_items": ["L5 01 X"], "pic": ["L5 X X"]})})
    tr = _doc("translator", {"A.cbl": _file({"units": ["P1"]}, "partial", ["data"], "layout: LayoutError: x")})
    res = X.compare("toy", eng, tr, _key({}), set())
    assert [(d["channel"], d["only"]) for d in res["disagreements"]] == [("status", "engine")]
    assert "data_items" not in {d["channel"] for d in res["disagreements"]}
    assert res["stats"]["units"]["both"] == 1


def test_a_program_refused_whole_compares_no_copy_channels() -> None:
    eng = _doc("engine", {"A.cbl": _file({"copybooks": ["X"], "copy_resolution": ["X -> c/X.cpy"]})})
    tr = _doc("translator", {"A.cbl": _file({}, "fail", ["data", "procedure"], "layout: ...; procedure: ...")})
    res = X.compare("toy", eng, tr, _key({}), set())
    assert {d["channel"] for d in res["disagreements"]} == {"status"}


def test_cics_commands_compare_only_the_verbs_the_key_censuses() -> None:
    key = _key({"A.cbl": {"facts": {"program_ids": ["P"], "cics_commands": ["L9 READ"]}}})
    eng = _doc("engine", {"A.cbl": _file({"cics_commands": ["L9 READ"]})})
    tr = _doc("translator", {"A.cbl": _file({"cics_commands": ["L9 READ", "L12 ASKTIME"]})})
    res = X.compare("toy", eng, tr, key, {"A.cbl"})
    assert res["disagreements"] == []
    assert res["stats"]["cics_commands"]["engine_tp"] == 1 and res["stats"]["cics_commands"]["translator_tp"] == 1


def test_offsets_are_scored_against_the_key_on_records_all_three_lay_out() -> None:
    key = _key({"A.cbl": {"facts": {"program_ids": ["P"], "offsets": ["R (record) +4", "R/F @0+4", "K (record) +2"]}}})
    eng = _doc("engine", {"A.cbl": _file({"offsets": ["R (record) +4", "R/F @0+4", "S (record) +1"]})})
    tr = _doc("translator", {"A.cbl": _file({"offsets": ["R (record) +8", "R/F @0+8", "S (record) +1"]})})
    s = X.compare("toy", eng, tr, key, {"A.cbl"})["stats"]["offsets"]
    assert (s["true"], s["engine_tp"], s["translator_tp"]) == (2, 2, 0)


# ------------------------------------------------------------------------------
# the gate and the ledger
# ------------------------------------------------------------------------------
def _ledger(disagreements: dict, causes: dict | None = None) -> dict:
    causes = causes if causes is not None else {"c": {"side": "engine", "issue": 1, "summary": "s"}}
    return {"schema": X.SCHEMA, "causes": causes, "disagreements": disagreements}


def test_gate_fails_on_new_and_lists_gone_without_failing() -> None:
    led = _ledger({"a": "c", "b": "c"})
    new, problems, gone = X.gate(led, [{"id": "a"}, {"id": "z"}])
    assert new == ["z"] and gone == ["b"] and problems == []


def test_check_is_a_two_way_ratchet() -> None:
    led = _ledger({"a": "c", "b": "c"})
    new, problems, gone = X.gate(led, [{"id": "a"}])
    fail = X.gate_failures(new, problems, gone)
    assert gone == ["b"] and len(fail) == 1 and "fact_crosscheck.py update" in fail[0]
    assert X.gate_failures(*X.gate(led, [{"id": "a"}, {"id": "b"}])) == []
    assert X.gate_failures(*X.gate(led, [{"id": "a"}, {"id": "b"}, {"id": "z"}]))[0].startswith("1 new")


def test_check_fails_on_a_stale_ledger_entry(monkeypatch, tmp_path: Path, capsys) -> None:
    ledger = tmp_path / "ledger.json"
    X.save_ledger(
        _ledger({"toy :: units | A.cbl | engine | P2": "c", "toy :: units | A.cbl | engine | P9": "c"}), ledger
    )
    now = [{"id": "toy :: units | A.cbl | engine | P2"}]
    monkeypatch.setattr(X, "run_all", lambda *a, **k: {"corpora": {}, "disagreements": now, "seconds": {}})
    assert X.main(["check", "--no-crucible", "--ledger", str(ledger)]) == 1
    out = capsys.readouterr().out
    assert "GONE toy :: units | A.cbl | engine | P9" in out and "fact_crosscheck.py update" in out
    X.save_ledger(_ledger({"toy :: units | A.cbl | engine | P2": "c"}), ledger)
    assert X.main(["check", "--no-crucible", "--ledger", str(ledger)]) == 0


def test_update_without_corpus_drops_stale_entries(monkeypatch, tmp_path: Path) -> None:
    """#4472: a plain `update` lowers the ledger; a --corpus one only touches its own corpora."""
    ledger = tmp_path / "ledger.json"
    old = {
        "toy :: units | A.cbl | engine | P2": "c",
        "toy :: units | A.cbl | engine | P9": "c",
        "zoo :: units | B.cbl | engine | Q": "c",
    }
    now = [{"id": "toy :: units | A.cbl | engine | P2"}]
    monkeypatch.setattr(X, "run_all", lambda *a, **k: {"corpora": {}, "disagreements": now, "seconds": {}})
    X.save_ledger(_ledger(old), ledger)
    assert X.main(["update", "--no-crucible", "--corpus", "toy", "--ledger", str(ledger)]) == 0
    assert set(X.load_ledger(ledger)["disagreements"]) == {
        "toy :: units | A.cbl | engine | P2",
        "zoo :: units | B.cbl | engine | Q",
    }
    X.save_ledger(_ledger(old), ledger)
    assert X.main(["update", "--no-crucible", "--ledger", str(ledger)]) == 0
    assert set(X.load_ledger(ledger)["disagreements"]) == {"toy :: units | A.cbl | engine | P2"}


def test_engine_extras_lays_out_the_replaced_records_of_a_section_copy() -> None:
    """#4472: the copybook's own item sits at the translator's (file, line); the replaced record
    (ef.copied_items / ef.records, at the COPY line) is what the engine lays out."""
    from types import SimpleNamespace as NS

    def item(name: str, line: int) -> NS:
        return NS(name=name, level=1, line=line)

    own, replaced = item("CB-COMMAREA", 8), item("DFHCOMMAREA", 200)
    cb = NS(file_path="cb.cpy", data_items=[own], records=[own])
    ef = NS(file_path="p.cbl", data_items=[], copied_items=[replaced], records=[replaced], data_moves=[], copy_deps=[])
    laid: list[str] = []

    class IR:
        def _copy_files(self, f: object) -> list:
            return [cb] if f is ef else []

        def record_layout(self, owner: object, it: NS, ext: object) -> dict:
            laid.append(it.name)
            return {"fields": [{"pic": "X", "name": "F", "offset": 0, "bytes": 4}], "bytes": 4}

    rec = NS(name="DFHCOMMAREA", level=1)
    out = X.engine_extras(IR(), ef, [(rec, "cb.cpy", 8)])
    assert laid == ["DFHCOMMAREA"]
    assert out["offsets"] == {"DFHCOMMAREA/F @0+4", "DFHCOMMAREA (record) +4"}


def test_ledger_rejects_untriaged_unknown_and_incomplete_causes() -> None:
    led = _ledger({"a": None, "b": "nope", "c": "bad"}, {"bad": {"side": "neither", "issue": "x", "summary": ""}})
    errs = X.validate_ledger(led)
    assert any(e.startswith("UNTRIAGED a") for e in errs)
    assert any("unknown cause 'nope'" in e for e in errs)
    assert any("cause bad: side" in e for e in errs) and any("cause bad: no issue" in e for e in errs)


def test_committed_ledger_is_triaged_and_portable() -> None:
    led = X.load_ledger()
    assert X.validate_ledger(led) == []
    for did in led["disagreements"]:
        assert "/srv/" not in did and "/home/" not in did and "/tmp/" not in did, did
        corpus, rest = did.split(" :: ", 1)
        assert rest.count(" | ") >= 3, did
    sides = {c["side"] for c in led["causes"].values()}
    assert sides <= set(X.SIDES)


# ------------------------------------------------------------------------------
# canonical operands (engine text and translator AST meet here)
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "canon"),
    [
        ("'N'", "'N'"),
        ("ZERO", "ZEROES"),
        ("SPACES", "SPACES"),
        ("+1", "1"),
        ("5.50", "5.50"),
        ("0010", "10"),
        ("WS-X(1:2)", "WS-X"),
        ("A IN B", "A OF B"),
        ("LENGTH OF WS-REC", "LENGTH OF WS-REC"),
        ("FUNCTION CURRENT-DATE", "FUNCTION CURRENT-DATE"),
        ("X'0D'", "X'0D'"),
    ],
)
def test_canon_text_operand(text: str, canon: str) -> None:
    assert TA.canon_text_operand(text) == canon


def test_move_value_folds_case_like_the_key() -> None:
    assert TA.move_value(7, "'Abc'", "WS-X") == "L7 MOVE 'ABC' -> WS-X"


def test_census_kind() -> None:
    assert TA.census_kind(["READ"], {"FILE": "'F'"}) == "FILE"
    assert TA.census_kind(["SEND"], {"MAP": "'M'"}) == "MAP"
    assert TA.census_kind(["SEND"], {"TEXT": None}) is None
    assert TA.census_kind(["GET"], {"COUNTER": "X"}) is None
    assert TA.census_kind(["WEB", "PARSE"], {"URL": "U"}) is None
    assert TA.census_kind(["WEB", "OPEN"], {}) == "WEB"


# ------------------------------------------------------------------------------
# the translator adapter on a toy program
# ------------------------------------------------------------------------------
TOY = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TOY.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-REC.
           05  WS-A               PIC X(4) VALUE 'AB'.
           05  WS-B               PIC S9(4) COMP.
           05  WS-P               POINTER.
       01  WS-T.
           COPY TOYCPY.
       PROCEDURE DIVISION.
           PERFORM P1 THRU P1-EXIT.
           GOBACK.
       P1.
           MOVE 'x' TO WS-A
           GO TO P1-EXIT.
       P1-EXIT.
           EXIT.
"""
TOYCPY = """\
           05  T-ONE              PIC 9(3).
           05  T-TWO              PIC X(2).
"""


def test_translator_adapter_on_a_toy_program(tmp_path: Path) -> None:
    pytest.importorskip("tree_sitter_language_pack")
    (tmp_path / "TOY.cbl").write_text(TOY, encoding="latin-1")
    (tmp_path / "TOYCPY.cpy").write_text(TOYCPY, encoding="latin-1")
    r = TA.program_facts(tmp_path, tmp_path / "TOY.cbl", [tmp_path])
    f = r["facts"]
    assert r["status"] == "ok", r["error"]
    assert f["units"] == {"P1", "P1-EXIT"}
    assert f["unit_extents"] == {"(procedure division) L11-13", "P1 L14-16", "P1-EXIT L17-18"}
    # PERFORM A THRU B is one edge, to A (the key's shape)
    assert f["edges"] == {"(procedure division) -> PERFORM P1", "P1 -> GO TO P1-EXIT"}
    assert f["moves"] == {"L15 MOVE 'X' -> WS-A"}
    assert f["copybooks"] == {"TOYCPY"} and f["copy_resolution"] == {"TOYCPY -> TOYCPY.cpy"}
    assert "L7 WS-B COMP" in f["usage"] and "L6 WS-A = AB" in f["value"]
    # the translator's storage: POINTER is 8 bytes (GnuCOBOL x86-64), so WS-REC is 4 + 2 + 8
    assert {"WS-REC (record) +14", "WS-REC/WS-A @0+4", "WS-REC/WS-B @4+2", "WS-T/T-TWO @3+2"} <= f["offsets"]


def test_translator_extent_stops_before_end_program(tmp_path: Path) -> None:
    """#4630: a lone program's last unit ends at its last code line, not at `END PROGRAM 'X'.`"""
    pytest.importorskip("tree_sitter_language_pack")
    src = TOY + "       END PROGRAM 'TOY'.\n"
    (tmp_path / "TOY.cbl").write_text(src, encoding="latin-1")
    (tmp_path / "TOYCPY.cpy").write_text(TOYCPY, encoding="latin-1")
    f = TA.program_facts(tmp_path, tmp_path / "TOY.cbl", [tmp_path])["facts"]
    assert f["unit_extents"] == {"(procedure division) L11-13", "P1 L14-16", "P1-EXIT L17-18"}
