"""gap_prevalence (#5865): per-gap estate / program counts by era over synthetic survey rows and inventories."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gap_prevalence as gp

A, B = "zecs", "cics-genapp"  # burned estates


def inv(root: Path, corpus: str, eras: dict[str, int | None]) -> None:
    progs = {p: {"era": e, "earliest": e, "mixed": False, "tells": []} for p, e in eras.items()}
    (root / f"{corpus}.json").write_text(json.dumps({"eras": {"programs": progs}}), encoding="utf-8")


def row(*holes: str) -> dict:
    return {"statements": 3, "holes": list(holes)}


@pytest.fixture
def rows_and_inv(tmp_path):
    inv(tmp_path, A, {"a1.cbl": 1, "a2.cbl": 4, "a3.cbl": None, "a4.cbl": 2, "a5.cbl": 2})
    inv(tmp_path, B, {"b1.cbl": 2})
    rows = {
        (A, "a1.cbl"): row("line 3: EXEC CICS: GETMAIN not modelled"),
        (A, "a2.cbl"): row(
            "line 3: EXEC CICS: GETMAIN not modelled", "line 9: EXEC EXEC SQL: DECLARE CURSOR WITH HOLD"
        ),
        (A, "a3.cbl"): row(),
        (A, "a4.cbl"): {"error": "CopyNotFound: COPY BAQRI not found"},
        (A, "a5.cbl"): {"error": "NotSupported: m.cbl:4: CICS Assembler not supported"},
        (B, "b1.cbl"): row("line 5: EXEC CICS: GETMAIN not modelled"),
        (B, "b2.cbl"): row("line 7: HOLE does not parse"),  # no inventory era for it
    }
    return rows, tmp_path


def test_counts_estates_programs_and_eras(rows_and_inv):
    rows, d = rows_and_inv
    res = gp.measure(rows, d, top=(1, 2))
    by = {g["gap"]: g for g in res["gaps"]}
    g = by["EXEC CICS GETMAIN"]
    assert (g["estates"], g["programs"]) == (2, 3)
    assert g["by_era"] == {"0": 0, "1": 1, "2": 1, "3": 0, "4": 1, "none": 0}
    assert g["estates_by_era"]["2"] == 1 and g["estates_by_era"]["1"] == 1
    assert res["gaps"][0]["gap"] == "EXEC CICS GETMAIN"  # estates first
    assert by["missing copybook BAQRI"]["status"] == "unknown"
    assert by["refused: CICS Assembler"]["status"] == "refused by name"
    assert by["refused: CICS Assembler"]["owner"] == "#5121"
    assert by["EXEC CICS GETMAIN"]["status"] == "not modelled"
    assert by["EXEC SQL: DECLARE CURSOR WITH HOLD"]["owner"].startswith("#4098")
    assert by["grammar: does not parse"]["owner"] == "#4462"
    assert by["grammar: does not parse"]["by_era"]["none"] == 1  # program absent from the inventory


def test_program_with_no_era_tell_counts_under_none(rows_and_inv):
    rows, d = rows_and_inv
    res = gp.measure(rows, d)
    assert res["by_era_programs"] == {"0": 0, "1": 1, "2": 3, "3": 0, "4": 1, "none": 1 + 1}


def test_coverage_if_closed(rows_and_inv):
    rows, d = rows_and_inv
    res = gp.measure(rows, d, top=(1, 2, 99))
    assert res["programs"] == 7 and res["whole_now"] == 1
    cov = {c["top"]: c for c in res["coverage_if_closed"]}
    assert cov[1]["whole"] == 1 + 2  # a3 whole already; a1 and b1 once GETMAIN is closed
    assert not cov[1]["upper_bound"]
    assert 99 not in cov  # fewer gaps than N: not reported
    assert max(cov) == 2


def test_refusal_in_top_makes_coverage_an_upper_bound(tmp_path):
    inv(tmp_path, A, {"x.cbl": 1})
    rows = {(A, "x.cbl"): {"error": "NotSupported: m.cbl:4: macro-level CICS not supported"}}
    res = gp.measure(rows, tmp_path, top=(1,))
    assert res["coverage_if_closed"][0]["upper_bound"] is True
    assert res["coverage_if_closed"][0]["whole"] == 1


def test_non_burned_corpus_is_refused(tmp_path):
    with pytest.raises(ValueError, match="not burned"):
        gp.measure({("some-census-repo", "p.cbl"): row("line 1: EXEC SQL: X")}, tmp_path)


def test_missing_inventory_and_deterministic_render(rows_and_inv):
    rows, d = rows_and_inv
    first, second = gp.render(gp.measure(rows, d)), gp.render(gp.measure(dict(reversed(rows.items())), d))
    assert first == second
    assert "| `EXEC CICS GETMAIN` | 2 | 3 |" in first
    assert gp.eras_of("no-such-corpus", d) == {}


@pytest.mark.parametrize("service", ["CEEHDLR", "CEEHDLU", "CEEMGET", "CEESGL", "CEENCOD", "CEEMRCE", "CEE3SRP"])
def test_every_le_condition_service_gap_is_owned_by_5106(service):
    assert gp.owner_of(f"{service}: an LE condition service is not modelled") == "#5106 (le-condition-handling)"
    assert gp.owner_of("CEEIGZCT: x") == "unowned"  # the stand-in copybook is not a condition service
