"""The third-party port adapter's own logic (tests/tools/thirdparty_port.py): record framing, staging, fault
selection, clock masking. The ports themselves are fetched and judged by the tool, not here."""

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import thirdparty_port as tp  # noqa: E402


def test_records_and_lines_round_trip():
    data = b"A" * 5 + b"B" * 5 + b"C" * 5
    text = tp.lines_from_records(data, 5)
    assert text == b"AAAAA\nBBBBB\nCCCCC\n"
    assert tp.records_from_lines(text, 5) == data
    assert tp.records_from_lines(b"AAAAA\r\nBBBBB\r\n", 5) == b"AAAAABBBBB"  # CRLF is a newline
    assert tp.records_from_lines(b"", 5) == b""


def test_a_line_that_is_not_the_record_is_refused():
    with pytest.raises(ValueError, match="line 2: 4 bytes, the record is 5"):
        tp.records_from_lines(b"AAAAA\nBBBB\n", 5)
    with pytest.raises(ValueError):
        tp.lines_from_records(b"AAAAAB", 5)


def _case(tmp_path):
    (tmp_path / "in.txt").write_bytes(b"20x\n10y\n")
    return {
        "datasets": {
            "KSDS": {"input": str(tmp_path / "in.txt"), "organization": "indexed", "reclen": 3,
                     "keys": [{"offset": 0, "length": 2}]},
            "OUT": {"organization": "sequential", "reclen": 3, "compare": True},
        },
        "faults": [
            {"name": "open-ksds", "plan": [{"dd": "KSDS", "op": "OPEN", "nth": 1, "status": "35"}]},
            {"name": "open-out", "plan": [{"dd": "OUT", "op": "OPEN", "nth": 1, "status": "35"}]},
            {"name": "read-ksds", "plan": [{"dd": "KSDS", "op": "READ", "nth": 1, "status": "30"}]},
        ],
    }  # fmt: skip


def test_stage_writes_inputs_as_key_ordered_lines_and_leaves_an_absent_input_out(tmp_path, monkeypatch):
    monkeypatch.setattr(tp, "_input_path", lambda case, corpus, p: Path(p))
    monkeypatch.setattr(tp, "_fixed", lambda path, reclen, enc: path.read_bytes().replace(b"\n", b""))
    case = _case(tmp_path)
    dds = tp.stage(case, tmp_path, tmp_path / "run", {"KSDS": "k.txt"})
    assert dds["KSDS"].name == "k.txt" and dds["KSDS"].read_bytes() == b"10y\n20x\n"  # primary-key order
    assert not dds["OUT"].exists()  # an output: the port writes it
    dds = tp.stage(case, tmp_path, tmp_path / "run2", None, absent="KSDS")
    assert not dds["KSDS"].exists()


def test_external_faults_are_status_35_opens_of_inputs_only(tmp_path):
    assert [f["name"] for f in tp.external_faults(_case(tmp_path))] == ["open-ksds"]


def test_clock_mask_only_replaces_a_timestamp_the_run_wrote(monkeypatch):
    monkeypatch.setattr(tp.eq, "layout_fields", lambda corpus, cb, rec=None: [{"name": "TS", "offset": 2, "bytes": 26}])
    case = {"datasets": {"F": {"reclen": 28, "copybook": "x"}}}
    cobol = {"F": b"AA2022-07-18-10.30.15.000000"}
    ran_at = datetime(2026, 10, 3, 2, 0, 0)
    fresh = {"F": b"AA2026-10-03-01.59.59.123456"}
    out, n = tp.mask_clock(case, Path("."), cobol, fresh, {"F": ["TS"]}, ran_at)
    assert n == 1 and out["F"] == cobol["F"]
    for java in (
        {"F": b"AA2020-01-01-00.00.00.000000"},  # not this run's time
        {"F": b"AAnot a timestamp at all....."},
    ):  # not a timestamp
        out, n = tp.mask_clock(case, Path("."), cobol, java, {"F": ["TS"]}, ran_at)
        assert n == 0 and out["F"] == java["F"]
