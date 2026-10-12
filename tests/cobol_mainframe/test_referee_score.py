"""The referee panel's scoring logic (#4377): tests/tools/referees/{facts,score}.py.

No referee is run here -- the panel's tools (JVM / tree-sitter builds) live outside the repo and
run on demand. These tests pin the arithmetic the scorecard reports.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "referees"))

import cobrix_adapter
import facts as F
import score as S


def _key() -> dict:
    raw = {
        "corpus": "toy",
        "ref": "0123456789abcdef",
        "programs": {
            "A.cbl": {
                "program_id": "PROGA",
                "units": [
                    {"name": "P1", "kind": "paragraph", "line": 10, "end": 12,
                     "edges": [{"verb": "PERFORM_THRU", "target": "P2", "thru": "P2-EXIT", "line": 11}]},
                    {"name": "P2", "kind": "paragraph", "line": 14, "end": 15,
                     "edges": [{"verb": "GO_TO", "target": "P1", "line": 15}]},
                ],
                "main_line": {"line": 8, "end": 9, "edges": [{"verb": "PERFORM", "target": "P1", "line": 9}]},
                "siblings": {"PROGB": {"program_id": "PROGB", "units": [
                    {"name": "MAINLINE", "kind": "section", "line": 30, "end": 31, "edges": []}]}},
                "calls": [
                    {"verb": "CALL", "form": "literal", "operand": "SUBX", "target": "SUBX", "line": 12},
                    {"verb": "LINK", "form": "identifier", "operand": "WS-PGM", "target": "PROGC", "line": 13},
                ],
                "copybooks": [{"name": "CPY1"}],
                "records": [
                    {"line": 5, "level": 1, "name": "WS-A", "pic": "x(3)", "usage": None, "occurs_min": None,
                     "occurs_max": None, "occurs_depending_on": None, "redefines": None, "value": "abc"},
                    {"line": 6, "level": 5, "name": "WS-N", "pic": "S9(4)", "usage": "BINARY", "occurs_min": 1,
                     "occurs_max": 5, "occurs_depending_on": "WS-K", "redefines": None, "value": None},
                ],
            },
            "B.cbl": {"program_id": "PROGD", "units": [], "calls": [], "copybooks": [], "records": []},
        },
        "cics_resources": {"A.cbl": {"operations": [
            {"verb": "READ", "kind": "FILE", "name": "ACCTS", "line": 20},
            {"verb": "SEND", "kind": "MAP", "name": "M1", "line": 21},
        ]}},
        "cics_tasks": {"A.cbl": {"operations": [{"verb": "START ATTACH", "line": 22}]}},
        "sql_access": {"B.cbl": {"accesses": ["read T1"]}},
        "copybook_layouts": {"C.cpy": {"units": ["R/F1 @0+3", "R/F2 @3+2"]}},
    }  # fmt: skip
    return F.key_doc(raw)


def _doc(source: str, files: dict, channels=F.CHANNELS) -> dict:
    doc = F.new_doc(source, "v", "toy", channels)
    for rel, (status, facts) in files.items():
        F.add_file(doc, rel, facts, status=status, seconds=0.5)
    return doc


def test_key_doc_shapes() -> None:
    k = _key()["files"]["A.cbl"]["facts"]
    assert k["program_ids"] == ["PROGA", "PROGB"]
    assert "PROGB:MAINLINE" in k["units"] and "P1" in k["units"]
    assert "(procedure division) L8-9" in k["unit_extents"]
    assert set(k["edges"]) == {"P1 -> PERFORM P2", "P2 -> GO TO P1", "(procedure division) -> PERFORM P1"}
    assert set(k["calls"]) == {"CALL 'SUBX'", "LINK WS-PGM"}
    assert set(k["call_targets"]) == {"SUBX", "PROGC"}
    assert set(k["cics_commands"]) == {"L13 LINK", "L20 READ", "L21 SEND", "L22 START"}
    assert k["cics_files"] == ["READ ACCTS"]
    assert "L6 WS-N COMP" in k["usage"]  # BINARY folds to COMP
    assert "L6 WS-N 1..5 DEPENDING ON WS-K" in k["occurs"]
    assert "L5 WS-A X(3)" in k["pic"] and "L5 WS-A = ABC" in k["value"]
    assert _key()["files"]["C.cpy"]["facts"] == {"layouts": ["R/F1 @0+3", "R/F2 @3+2"]}


@pytest.mark.parametrize(
    "raw,norm",
    [("'  ab '", "AB"), ("+12", "12"), ("ZERO", "ZEROES"), ("spaces", "SPACES"), ("SPACE", "SPACES"), ("-3", "-3")],
)
def test_norm_value(raw: str, norm: str) -> None:
    assert F.norm_value(raw) == norm


def test_depending_on_qualifier_is_dropped() -> None:
    assert F.item_values(4, 5, "V", occurs_min=0, occurs_max=9, depending_on="LEN OF GRP")["occurs"] == "L4 V 0..9 DEPENDING ON LEN"


def test_call_value_strips_cics_padding() -> None:
    assert F.call_value("LINK", "literal", "'INQCUST '") == "LINK 'INQCUST'"
    assert F.call_value("CALL", "identifier", "ws-pgm") == "CALL WS-PGM"


def test_universe_programs_and_copybooks() -> None:
    key = _key()
    assert S.universe(key, "units") == ["A.cbl", "B.cbl"]
    assert S.universe(key, "layouts") == ["C.cpy"]


def test_score_channel_counts_and_failed_files() -> None:
    key = _key()
    ref = _doc("ref", {
        "A.cbl": ("ok", {"units": ["P1", "BOGUS"]}),
        "B.cbl": ("fail", {}),
    })  # fmt: skip
    sc = S.score_channel(key, ref, "units")
    assert sc == {"tp": 1, "reported": 2, "true": 3, "true_parsed": 3, "files": 2, "files_parsed": 1}
    # B.cbl has no units, so its failure costs nothing; program_ids shows the cost of a failed file
    pid = S.score_channel(key, _doc("ref", {"A.cbl": ("ok", {"program_ids": ["PROGA"]}), "B.cbl": ("fail", {})}), "program_ids")
    assert (pid["tp"], pid["true"], pid["true_parsed"]) == (1, 3, 2)


def test_channel_a_source_cannot_produce_is_na() -> None:
    assert S.score_channel(_key(), _doc("ref", {}, channels=["units"]), "layouts") is None
    assert S._cell(None) == "n/a"


def test_cics_commands_scored_over_key_verbs() -> None:
    key = _key()
    ref = _doc("ref", {"A.cbl": ("ok", {"cics_commands": ["L20 READ", "L23 ASKTIME", "L24 SEND-SEND_TEXT"]})})
    sc = S.score_channel(key, ref, "cics_commands")
    assert (sc["tp"], sc["reported"]) == (1, 1)  # ASKTIME / SEND TEXT are not censused: not false positives


def test_agreement_and_disagreements_only_on_files_both_parsed() -> None:
    key = _key()
    eng = _doc("engine", {"A.cbl": ("ok", {"units": ["P1", "P2"]}), "B.cbl": ("ok", {"units": ["X"]})})
    ref = _doc("ref", {"A.cbl": ("partial", {"units": ["P1", "P9"]}), "B.cbl": ("fail", {})})
    assert S.agreement(key, eng, ref, "units") == {"both": 1, "union": 3}
    dis = S.disagreements(key, eng, ref, "units")
    assert {(d["value"], d["only"], d["in_key"]) for d in dis} == {("P2", "engine", True), ("P9", "ref", False)}


def test_scorecard_markdown() -> None:
    key = _key()
    corpora = {"toy": {"key": key, "sources": {
        "engine": _doc("engine", {"A.cbl": ("ok", {"units": ["P1", "P2", "PROGB:MAINLINE"]}), "B.cbl": ("ok", {})}),
        "ref": _doc("ref", {"A.cbl": ("ok", {"units": ["P1"]}), "B.cbl": ("fail", {})}, channels=["units"]),
    }}}  # fmt: skip
    md, data, dis = S.scorecard(corpora)
    assert "| units | P 100.0% · R 100.0% | P 100.0% · R 33.3% (R parsed 33.3%) |" in md
    assert "| layouts | P — · R 0.0% (R parsed —) | n/a |" in md  # a keyed copybook the engine never read
    assert data["sources"]["ref"]["fail"] == 1 and data["sources"]["ref"]["ok"] == 1
    assert dis["ref"]["units"]["engine-only, in key"]["count"] == 2


def test_cobrix_layout_units_skip_overlays_and_fillers() -> None:
    fields = [
        {"root": "R", "name": "R", "level": 1, "group": True, "offset": 0, "size": 10},
        {"root": "R", "name": "A", "level": 5, "group": False, "offset": 0, "size": 4, "pic": "X(4)"},
        {"root": "R", "name": "B", "level": 5, "group": True, "offset": 0, "size": 4, "redefines": "A"},
        {"root": "R", "name": "B1", "level": 10, "group": False, "offset": 0, "size": 4, "pic": "9(4)"},
        {"root": "R", "name": "FILLER", "level": 5, "group": False, "offset": 4, "size": 2, "pic": "X(2)", "filler": True},
        {"root": "R", "name": "C", "level": 5, "group": False, "offset": 6, "size": 4, "pic": "X(2)"},
    ]
    assert cobrix_adapter.layout_units(fields) == {"R/A @0+4", "R/C @6+4"}
