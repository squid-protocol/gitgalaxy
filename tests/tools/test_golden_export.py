"""#4052 slice 1: golden export of a case's COBOL outputs, and the byte-exact check of a Java run against it."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import golden_export as g

CASE = {"name": "demo", "program": "DEMO"}
MAIN_RUN = {"OUT": b"AB\x00\xc1\n" * 3, "RETURN-CODE": b"0\n", "SYSOUT": b"hi\n"}
FAULT_RUN = {"OUT": b"", "ABEND": b"U0016\n", "FAULTS": b"OUT READ 1\n"}


def _java(tmp: Path, runs: dict) -> Path:
    for name, files in runs.items():
        (tmp / name).mkdir(parents=True)
        for k, v in files.items():
            (tmp / name / k).write_bytes(v)
    return tmp


@pytest.fixture
def golden(tmp_path):
    d = tmp_path / "golden"
    g.export(CASE, {"main": MAIN_RUN, "fault-x": FAULT_RUN}, d, "cp037")
    return d


def test_export_writes_bytes_hashes_and_status(golden):
    m = g.json.loads((golden / "golden.json").read_text())
    assert m["data_encoding"] == "cp037"
    assert m["runs"]["main"]["return_code"] == "0"
    assert m["runs"]["main"]["outputs"]["OUT"]["bytes"] == 15
    assert m["runs"]["fault-x"]["abend"] == "U0016"
    assert (golden / "main" / "OUT").read_bytes() == MAIN_RUN["OUT"]
    assert "RETURN-CODE" not in m["runs"]["main"]["outputs"]


def test_a_byte_identical_java_run_passes(golden, tmp_path):
    java = _java(tmp_path / "j", {"main": MAIN_RUN, "fault-x": {"ABEND": b"U0016\n", "FAULTS": b"x"}})
    assert g.check(golden, java) == []


def test_one_changed_byte_is_named_with_its_offset(golden, tmp_path):
    bad = dict(MAIN_RUN, OUT=MAIN_RUN["OUT"][:7] + b"Z" + MAIN_RUN["OUT"][8:])
    java = _java(tmp_path / "j", {"main": bad, "fault-x": {"ABEND": b"U0016\n"}})
    assert g.check(golden, java) == ["main/OUT: differs at byte 7 (Java 15 bytes, golden 15)"]


def test_return_code_abend_missing_and_extra_outputs_all_fail(golden, tmp_path):
    java = _java(
        tmp_path / "j", {"main": {"RETURN-CODE": b"8\n", "EXTRA": b"x"}, "fault-x": {"RETURN-CODE": b"0\n", "OUT": b""}}
    )
    got = g.check(golden, java)
    assert "main: return code '8', golden '0'" in got
    assert "main/OUT: missing from the Java run" in got
    assert "main/EXTRA: a Java output the golden run does not have" in got
    assert "fault-x: abend None, golden 'U0016'" in got


def test_a_run_missing_from_java_and_a_tampered_golden_file_fail(golden, tmp_path):
    (golden / "main" / "OUT").write_bytes(b"tampered")
    java = _java(tmp_path / "j", {"main": MAIN_RUN})
    got = g.check(golden, java)
    assert "main/OUT: the golden file no longer matches its manifest hash" in got
    assert "fault-x: the Java run has no outputs" in got


def test_an_abended_run_does_not_compare_its_datasets(golden, tmp_path):
    java = _java(tmp_path / "j", {"main": MAIN_RUN, "fault-x": {"ABEND": b"U0016\n", "OUT": b"junk"}})
    assert g.check(golden, java) == []


def test_export_needs_the_main_run_and_a_plain_dd_name(tmp_path):
    with pytest.raises(ValueError):
        g.export(CASE, {"fault-x": FAULT_RUN}, tmp_path / "a")
    with pytest.raises(ValueError):
        g.export(CASE, {"main": {"../X": b""}}, tmp_path / "b")


def test_cli_check_exit_codes(golden, tmp_path, capsys):
    java = _java(tmp_path / "j", {"main": MAIN_RUN, "fault-x": {"ABEND": b"U0016\n"}})
    assert g.main(["check", str(golden), "--java", str(java)]) == 0
    (java / "main" / "OUT").write_bytes(b"")
    assert g.main(["check", str(golden), "--java", str(java)]) == 1
    assert "DIFFERS" in capsys.readouterr().out
