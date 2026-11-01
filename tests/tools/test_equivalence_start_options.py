"""#7475: a START data record carries RTRANSID / RTERMID / QUEUE to the stub's .opt input and the Java runner."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec  # noqa: E402
import equivalence_mq as eq  # noqa: E402


def recs(*records):
    return eq.start_records({}, {"start_data": list(records)}, "latin-1")


def test_plain_records_are_unchanged():
    r = recs({"text": "AB"}, {"hex": "00FF"})
    assert [x["data"] for x in r] == [b"AB", b"\0\xff"]
    assert all(eq.start_opt_text(x) is None for x in r)
    assert eq.start_data({}, {"start_data": [{"text": "AB"}]}, "latin-1") == [b"AB"]


def test_options_beside_from_and_without_from():
    full, bare = recs({"text": "X", "rtransid": "GTRD", "rtermid": "T001", "queue": "QQ"}, {"rtransid": "ABCD"})
    assert eq.start_opt_text(full) == "from=1 rtransid=47545244 rtermid=54303031 queue=5151\n"
    assert bare["data"] is None
    assert eq.start_opt_text(bare) == "from=0 rtransid=41424344\n"


def test_opt_text_matches_cics_crucible_writer(tmp_path):
    import cics_crucible as cc

    rec = {"data": b"X", "rtransid": "GTRD", "queue": "Q1"}
    expect = "from=1 rtransid=47545244 queue=5131\n"
    assert eq.start_opt_text(rec) == expect
    assert cc._record({"data": b"X", "rtransid": "GTRD", "queue": "Q1"}) == {**rec, "rtermid": None}


@pytest.mark.parametrize("bad", [{}, {"rtransid": "TOOLONG"}, {"queue": "NINECHARS"}])
def test_bad_records_are_refused(bad):
    with pytest.raises(ValueError):
        recs(bad)


def test_scenario_overrides_case():
    case = {"start_data": [{"text": "C"}]}
    assert eq.start_records(case, {"start_data": [{"rtermid": "T1"}]}, "latin-1")[0]["rtermid"] == "T1"


def test_java_record_shape():
    from_only, opts, bare = recs({"text": "A"}, {"text": "A", "rtransid": "TR"}, {"queue": "Q"})
    assert ec._java_start_record(from_only, "latin-1", "cp037") == "C1"
    assert ec._java_start_record(opts, "latin-1", "cp037") == {"from": "C1", "rtransid": "TR"}
    assert ec._java_start_record(bare, "latin-1", "cp037") == {"queue": "Q"}
