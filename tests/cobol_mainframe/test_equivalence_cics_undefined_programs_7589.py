"""#7589: a case states a program undefined ("undefined_programs"): a LINK / XCTL / INQUIRE / LOAD / RELEASE of it is
PGMIDERR (RESP2 1) on both sides (IBM, EXEC CICS LINK), not the "case runs one program" refusal."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_cics as ec  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CASE = {"program": "CALINK", "programs": [{"program": "CASUB"}]}


def test_absent_means_none():
    assert ec.undefined_programs(CASE) == []


def test_the_names_are_a_sorted_deduplicated_list():
    assert ec.undefined_programs({**CASE, "undefined_programs": ["CAGONE", "AB@#$1", "CAGONE"]}) == ["AB@#$1", "CAGONE"]


@pytest.mark.parametrize("bad", ["CAGONE", [1], ["lower"], ["TOOLONGNAME"], [""], [["X"]]])
def test_a_malformed_list_is_refused_by_name(bad):
    with pytest.raises(ec.Unsupported, match="undefined_programs"):
        ec.undefined_programs({**CASE, "undefined_programs": bad})


@pytest.mark.parametrize("own", ["CALINK", "CASUB"])
def test_a_program_the_case_runs_cannot_be_undefined(own):
    with pytest.raises(ec.Unsupported, match=own):
        ec.undefined_programs({**CASE, "undefined_programs": [own]})


def test_the_stub_denies_the_listed_programs_for_every_verb():
    """One `program_defined` serves LINK, XCTL, INQUIRE PROGRAM, LOAD and RELEASE: reading the deny-list there covers all."""
    src = (ROOT / "tests/equivalence/cics/ggcics_program.c").read_text(encoding="utf-8")
    assert "noprograms.cfg" in src
    storage = (ROOT / "tests/equivalence/cics/ggcics_storage.c").read_text(encoding="utf-8")
    assert storage.count("!program_defined(program)") == 2  # LOAD, RELEASE
    assert src.count("program_defined(program)") >= 3  # INQUIRE, XCTL, LINK


def test_the_ca_link_lengths_case_states_cagone_and_runs_the_scenario():
    case = json.loads(
        (ROOT / "tests" / "equivalence" / "cruc-ca-link-lengths" / ("case" + ".json")).read_text(encoding="utf-8")
    )
    assert ec.undefined_programs(case) == ["CAGONE"]
    assert {"name": "undefined-program", "terminal": "CA01 P"}.items() <= next(
        s for s in case["scenarios"] if s["name"] == "undefined-program"
    ).items()


def test_the_java_side_denies_them_with_and_without_a_csd(tmp_path):
    """The generated Programs.defined() is false for a stated-undefined name, and keeps the CSD allowlist otherwise."""
    src = Path(ec.__file__).read_text(encoding="utf-8")
    assert "if gone:" in src and ".contains(program) && {defined}" in src


def test_a_failed_link_of_the_callers_bytes_is_read_in_a_case_with_no_commarea(tmp_path):
    """The Java LINK event of an undefined program carries the caller's bytes (no DTO to map them to); a case with no
    COMMAREA layout does not refuse them: a LINK is compared by its target, its RESP through the program's report."""
    (tmp_path / "undef.json").write_text(
        json.dumps([{"event": "LINK", "target": "CAGONE", "length": 100, "commarea": "wcHA", "resp": "PGMIDERR",
                     "resp2": 1, "area": "QUJD"}]),
        encoding="utf-8",
    )  # fmt: skip
    got = ec._java_events({"scenarios": [{"name": "undef"}], "data_encoding": "ascii"}, tmp_path, {}, [])
    assert [(e["event"], e["target"], e["resp"], e["resp2"]) for e in got["undef"]] == [
        ("LINK", "CAGONE", "PGMIDERR", 1)
    ]
    assert ec._link_as_compared(got["undef"][0]) == {"event": "LINK", "program": "CAGONE"}
