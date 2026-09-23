"""
#3345: the JCL resolved DSN as a refraction-differential datum and a drafted
answer-key field.

No JCL forge exists, so -- as for PL/I (#3250) -- the compared side is the answer
key's own JCL reader (`jcl_dataset_bindings`) over the raw member, against the
engine's dataset_data. A delta is a real finding on one side, never a stated
absence, and it adjudicates only once a member is signed off `dsns_validated`.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cobol_answer_key as ak  # noqa: E402
import refraction_differential as rd  # noqa: E402

KEY_DIR = Path(__file__).resolve().parent / "answer_key"


@pytest.fixture(scope="module")
def mini_repo(tmp_path_factory):
    return tmp_path_factory.mktemp("jcl_repo")


def _jcl_row(old=(), db=()):
    return {"file": "JCL/RUN.jcl", "language": "jcl", "jcl_dsns": {"old": sorted(old), "db": sorted(db)}}


V_OK = "SAM1/CUSTFILE@154=IBMUSER.SAMPLE.CUSTFILE[resolved]"
V_DB = "SAM1/CUSTFILE@154=?[unresolved]"


def test_a_jcl_dsn_delta_is_a_real_finding_not_a_stated_absence(mini_repo):
    classified = rd.classify(mini_repo, [_jcl_row(old=[V_OK], db=[V_DB])], None)
    assert {(d["field"], d["side"], d["value"], d["cause"]) for d in classified} == {
        ("jcl_dsn", "old", V_OK, rd.UNEXPLAINED),
        ("jcl_dsn", "db", V_DB, rd.UNEXPLAINED),
    }


def test_agreeing_members_produce_no_delta(mini_repo):
    assert rd.classify(mini_repo, [_jcl_row(old=[V_OK], db=[V_OK])], None) == []


def test_jcl_rows_stay_out_of_the_cobol_summary(mini_repo):
    rows = [_jcl_row(old=[V_OK], db=[V_OK])]
    assert rd.to_markdown({"repo": "r", "commit": "0" * 8}, rows).count("JCL/RUN.jcl") == 0


def test_jcl_dsn_verdict_needs_explicit_validation(mini_repo):
    bindings = [
        {
            "line": 154,
            "step": "SAM1",
            "dd": "CUSTFILE",
            "dsn": "&HLQ..SAMPLE.CUSTFILE",
            "resolved": "IBMUSER.SAMPLE.CUSTFILE",
            "status": "resolved",
        }
    ]
    key = {"programs": {}, "jcl_jobs": {"JCL/RUN.jcl": {"bindings": bindings, "dsns_validated": False}}}
    rows = [_jcl_row(old=[V_OK], db=[V_DB])]
    assert rd.summarize_causes(rd.classify(mini_repo, rows, key))["unexplained"] == 2

    key["jcl_jobs"]["JCL/RUN.jcl"]["dsns_validated"] = True
    classified = rd.classify(mini_repo, rows, key)
    assert rd.summarize_causes(classified)["unexplained"] == 0
    assert {d["side"]: d["verdict"]["verdict"] for d in classified} == {"old": "engine defect", "db": "engine defect"}


def test_the_comparison_unit_reads_both_payload_shapes():
    """The key's rows and the engine's dataset_data dicts land on the same value."""
    key_row = {"line": 7, "step": None, "dd": "D", "resolved": None, "status": "unresolved"}
    engine_row = {"line": 7, "step_name": None, "dd_name": "D", "dsn_resolved": None, "dsn_resolution": "unresolved"}
    assert ak.jcl_dsn_values([key_row]) == ak.jcl_dsn_values([engine_row]) == {"-/D@7=?[unresolved]"}


def test_draft_jcl_reads_every_jcl_member(tmp_path):
    (tmp_path / "JCL").mkdir()
    (tmp_path / "JCL" / "RUN.jcl").write_text(
        "//J JOB\n//    SET HLQ='IBMUSER'   *TSO USER ID\n//S EXEC PGM=X\n//D DD DSN=&HLQ..F,DISP=SHR\n"
    )
    (tmp_path / "JCL" / "EMPTY.jcl").write_text("//J JOB\n//S EXEC PGM=IEFBR14\n")
    drafted = ak.draft_jcl(tmp_path)
    assert list(drafted) == ["JCL/RUN.jcl"]  # a member with no binding is not a key entry
    (row,) = drafted["JCL/RUN.jcl"]["bindings"]
    assert (row["resolved"], row["status"]) == ("IBMUSER.F", "resolved")
    assert drafted["JCL/RUN.jcl"]["dsns_validated"] is False


@pytest.mark.parametrize("key_path", sorted(KEY_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_jcl_key_entries_are_drafts_until_signed_off(key_path):
    """A drafted field never adjudicates, so a sign-off is an explicit, reviewed edit."""
    key = json.loads(key_path.read_text(encoding="utf-8"))
    for rel, entry in key.get("jcl_jobs", {}).items():
        assert entry["bindings"], rel
        if not entry.get("dsns_validated"):
            assert entry["verification"]["status"] == "draft", rel
