"""
#3355: the CICS COMMAREA operands as a refraction-differential datum and a
drafted answer-key field.

No forge reads `COMMAREA(...)`, so -- as for the JCL DSN (#3345) -- the compared
side is the answer key's own reader (`cics_commareas`, over its fixed-format
Source model) against the engine's call_site_data. A delta is a real finding on
one side, never a stated absence, and it adjudicates only once a program is
signed off `commareas_validated`.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cobol_answer_key as ak  # noqa: E402
import refraction_differential as rd  # noqa: E402

KEY_DIR = Path(__file__).resolve().parent / "answer_key"

PROGRAM = """\
      * a comment naming EXEC CICS LINK PROGRAM('NOPE') COMMAREA(NOPE)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BNK1DCS.
       PROCEDURE DIVISION.
           EXEC CICS LINK PROGRAM('INQCUST ')
              COMMAREA(INQCUST-COMMAREA)
           END-EXEC.
           EXEC CICS RETURN
                     TRANSID (WS-TRANID)
                     COMMAREA (CARDDEMO-COMMAREA)
                     LENGTH(LENGTH OF CARDDEMO-COMMAREA)
           END-EXEC.
           EXEC CICS XCTL PROGRAM('X') COMMAREA(DFHCOMMAREA(1:EIBCALEN))
                DATALENGTH(+10) END-EXEC.
           EXEC CICS RETURN END-EXEC.
           EXEC CICS LINK PROGRAM('BARE') END-EXEC.
"""


@pytest.fixture(scope="module")
def mini_repo(tmp_path_factory):
    return tmp_path_factory.mktemp("commarea_repo")


def _row(old=(), db=()):
    return {"file": "src/BNK1DCS.cbl", "language": "commarea", "commareas": {"old": sorted(old), "db": sorted(db)}}


V_OK = "LINK@5=INQCUST-COMMAREA|-|-"
V_DB = "LINK@5=INQCUST-COMM|-|-"


def test_the_key_reader_reads_real_shapes(tmp_path):
    path = tmp_path / "BNK1DCS.cbl"
    path.write_text(PROGRAM)
    assert ak.commarea_values(ak.cics_commareas(ak.Source(path))) == {
        "LINK@5=INQCUST-COMMAREA|-|-",
        "RETURN TRANSID@8=CARDDEMO-COMMAREA|LENGTH OF CARDDEMO-COMMAREA|-",
        "XCTL@13=DFHCOMMAREA(1:EIBCALEN)|-|+10",
    }


def test_the_comparison_unit_reads_both_payload_shapes():
    key_row = {"verb": "LINK", "line": 7, "commarea": "X", "length": "10", "datalength": None}
    engine_row = {"verb": "LINK", "line": 7, "commarea": "X", "commarea_length": "10", "commarea_datalength": None}
    assert ak.commarea_values([key_row]) == ak.commarea_values([engine_row]) == {"LINK@7=X|10|-"}


def test_a_commarea_delta_is_a_real_finding_not_a_stated_absence(mini_repo):
    classified = rd.classify(mini_repo, [_row(old=[V_OK], db=[V_DB])], None)
    assert {(d["field"], d["side"], d["value"], d["cause"]) for d in classified} == {
        ("commarea", "old", V_OK, rd.UNEXPLAINED),
        ("commarea", "db", V_DB, rd.UNEXPLAINED),
    }


def test_agreeing_programs_produce_no_delta(mini_repo):
    assert rd.classify(mini_repo, [_row(old=[V_OK], db=[V_OK])], None) == []


def test_commarea_rows_stay_out_of_the_cobol_summary(mini_repo):
    assert rd.to_markdown({"repo": "r", "commit": "0" * 8}, [_row(old=[V_OK], db=[V_OK])]).count("BNK1DCS") == 0


def test_commarea_verdict_needs_explicit_validation(mini_repo):
    entry = {"commareas": [{"verb": "LINK", "line": 5, "commarea": "INQCUST-COMMAREA"}], "commareas_validated": False}
    key = {"programs": {"src/BNK1DCS.cbl": entry}}
    rows = [_row(old=[V_OK], db=[V_DB])]
    assert rd.summarize_causes(rd.classify(mini_repo, rows, key))["unexplained"] == 2

    entry["commareas_validated"] = True
    classified = rd.classify(mini_repo, rows, key)
    assert rd.summarize_causes(classified)["unexplained"] == 0
    assert {d["side"]: d["verdict"]["verdict"] for d in classified} == {"old": "engine defect", "db": "engine defect"}


@pytest.mark.parametrize("key_path", sorted(KEY_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_commarea_key_fields_are_drafts_until_signed_off(key_path):
    """Every keyed program carries the drafted field; none is signed off by this PR."""
    key = json.loads(key_path.read_text(encoding="utf-8"))
    for rel, entry in key.get("programs", {}).items():
        assert "commareas" in entry, rel
        assert entry.get("commareas_validated") is False, rel
