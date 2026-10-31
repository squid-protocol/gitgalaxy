"""#6839 (row D): a variable-length (RECORDFORMAT V) VSAM file keeps each record's own length. The harness states those
lengths as the stub's `<file>.len` ("HEXKEY LENGTH" per record) and as the Java side's input; every way a case can state
them (a map, "lines", nothing) and every refusal is pinned here."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec

FILE = {"base": "VFILE", "reclen": 20, "key_offset": 0, "key_length": 4}


def _case(**datasets) -> dict:
    return {"name": "variable-lengths-test", "datasets": datasets}


def test_variable_file_is_only_a_stated_true():
    assert ec.variable_file(_case(VFILE={"vsam": {"variable": True}}), "VFILE")
    assert not ec.variable_file(_case(VFILE={"vsam": {"variable": False}}), "VFILE")
    assert not ec.variable_file(_case(VFILE={"vsam": {"variable": "yes"}}), "VFILE")
    assert not ec.variable_file(_case(VFILE={"vsam": {}}), "VFILE")
    assert not ec.variable_file(_case(VFILE={}), "VFILE")
    assert not ec.variable_file(_case(), "VFILE")


def test_a_stated_map_is_written_sorted_with_upper_case_keys(tmp_path):
    spec = {"lengths": {"6b32": 7, "6B31": 12}}
    out = ec.record_lengths(_case(), tmp_path, spec, FILE)
    assert out == b"6B31 12\n6B32 7\n"


def test_no_lengths_is_an_empty_file(tmp_path):
    assert ec.record_lengths(_case(), tmp_path, {}, FILE) == b""


def test_a_malformed_lengths_value_is_refused_by_name(tmp_path):
    for bad in (["6B31", 3], 5, "other"):
        with pytest.raises(ec.Unsupported, match="lengths"):
            ec.record_lengths(_case(), tmp_path, {"lengths": bad}, FILE)


def test_lines_take_each_record_as_long_as_its_line(tmp_path):
    seed = tmp_path / "seed.dat"
    seed.write_bytes(
        b"k001abc\r\n\nk002\nk003" + b"x" * 40 + b"\n"
    )  # CRLF, a blank line, a short key, an over-long line
    app = tmp_path / "more.dat"
    app.write_bytes(b"k004zz\n")
    spec = {"input": str(seed), "append": str(app), "lengths": "lines"}
    got = ec.parse_lengths(ec.record_lengths(_case(), tmp_path, spec, FILE))
    k = lambda s: s.encode().hex().upper()  # noqa: E731
    assert got == {k("k001"): 7, k("k002"): 4, k("k003"): 20, k("k004"): 6}  # capped at reclen; blank line skipped


def test_lines_without_input_state_nothing(tmp_path):
    assert ec.record_lengths(_case(), tmp_path, {"lengths": "lines"}, FILE) == b""


def test_lines_in_a_non_ascii_page_is_refused(tmp_path):
    seed = tmp_path / "seed.dat"
    seed.write_bytes(b"k001abc\n")
    case = _case()
    case["data_encoding"] = "cp037"
    with pytest.raises(ec.Unsupported, match="not ASCII-compatible"):
        ec.record_lengths(case, tmp_path, {"input": str(seed), "lengths": "lines"}, FILE)


def test_stated_lengths_round_trip_through_parse(tmp_path):
    spec = {"lengths": {"AB": 3, "0F": 0, "7F7F": 32700}}
    assert ec.parse_lengths(ec.record_lengths(_case(), tmp_path, spec, FILE)) == {"AB": 3, "0F": 0, "7F7F": 32700}


def test_parse_ignores_lines_that_are_not_a_key_and_a_length():
    assert ec.parse_lengths(b"ab 5\n\njunk\nCD 9 extra\n") == {"AB": 5}
