"""#8886 slice 25: the datasets a program step leaves (no GDG catalogs them) are compared with the chain's bytes.

`compare_program_outputs` reads the spec's `program_outputs`: the chain's `outputs/<case>/<DD>` against the bytes the linked
port left (`java_out` in the chain report) and against the file the javac Spring run left. `equivalence_job.java_outputs`
builds `java_out`. No JDK or Docker needed: both inputs are stubs.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "tools"))
import equivalence_forged_spring as efs  # noqa: E402
import equivalence_job as ej  # noqa: E402

SPEC = json.loads((REPO / "tests/equivalence/jobs/carddemo-nightly.forged.json").read_text(encoding="utf-8"))
ENTRY = SPEC["program_outputs"][1]  # POSTTRAN ACCTFILE
DATA = b"A" * 600


def _file(data: bytes) -> dict:
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _outputs(tmp_path: Path, data: bytes) -> Path:
    (tmp_path / ENTRY["case"]).mkdir()
    (tmp_path / ENTRY["case"] / ENTRY["dd"]).write_bytes(data)
    return tmp_path


def _report(java: bytes | None) -> dict:
    out = {ENTRY["dd"]: {**_file(java), "equal": True}} if java is not None else {}
    return {"steps": [{"case": ENTRY["case"], **({"java_out": out} if out else {})}]}


def _run(files: dict) -> dict:
    return {"datasets_by_job": {m: {ENTRY["job"]: files} for m in ("strict", "skip")}}


def test_the_spec_names_the_four_program_step_datasets():
    got = [(f["case"], f["dd"]) for f in SPEC["program_outputs"]]
    assert got == [
        ("carddemo-posttran", "DALYREJS"),
        ("carddemo-posttran", "ACCTFILE"),
        ("carddemo-posttran", "TCATBALF"),
        ("carddemo-intcalc", "ACCTFILE"),
    ]
    assert {f["case"] for f in SPEC["program_outputs"]} <= {m["case"] for m in SPEC["steps"]}


def test_a_port_with_the_chains_bytes_is_equal_and_the_stubbed_spring_run_still_differs(tmp_path):
    (row,) = [
        r
        for r in efs.compare_program_outputs(SPEC, _report(DATA), _outputs(tmp_path, DATA), _run({}))
        if r["dataset"] == ENTRY["dataset"] and r["case"] == ENTRY["case"]
    ]
    assert row["ported"]["status"] == "equal"
    assert "wrote nothing" in row["modes"]["strict"]["issue"]
    res = {"rows": [], "datasets": [row]}
    assert efs.differs(res) == [
        f"dataset {ENTRY['dataset']} [POSTTRAN] strict",
        f"dataset {ENTRY['dataset']} [POSTTRAN] skip",
    ]
    assert any("ported (linked port): equal" in ln for ln in efs.render({**res}, "x"))


def test_a_port_with_other_bytes_differs_and_is_listed(tmp_path):
    rows = efs.compare_program_outputs(SPEC, _report(b"B" * 600), _outputs(tmp_path, DATA), _run({}))
    row = next(r for r in rows if r["dataset"] == ENTRY["dataset"] and r["case"] == ENTRY["case"])
    assert row["ported"]["status"] == "differs"
    assert efs.differs({"rows": [], "datasets": [row]})[-1].endswith("ported")


def test_a_spring_file_with_the_chains_bytes_is_equal_in_both_modes(tmp_path):
    rows = efs.compare_program_outputs(
        SPEC, _report(DATA), _outputs(tmp_path, DATA), _run({ENTRY["dataset"]: _file(DATA)})
    )
    row = next(r for r in rows if r["dataset"] == ENTRY["dataset"] and r["case"] == ENTRY["case"])
    assert [row["modes"][m]["status"] for m in ("strict", "skip")] == ["equal", "equal"]
    assert efs.differs({"rows": [], "datasets": [row]}) == []


def test_no_java_bytes_or_no_chain_output_is_never_equal(tmp_path):
    rows = efs.compare_program_outputs(SPEC, _report(None), _outputs(tmp_path, DATA), _run({}))
    row = next(r for r in rows if r["dataset"] == ENTRY["dataset"] and r["case"] == ENTRY["case"])
    assert row["ported"]["status"] == "differs" and "left no bytes" in row["ported"]["issue"]
    (row,) = efs.compare_program_outputs({"program_outputs": [ENTRY]}, _report(DATA), None, _run({}))
    assert row["ported"]["status"] == "differs" and "exported no" in row["modes"]["skip"]["issue"]


def test_a_spec_without_program_outputs_adds_no_rows():
    assert efs.compare_program_outputs({}, {}, None, {}) == []


def test_java_outputs_digest_each_compared_dd_of_a_forged_step_only():
    case = {"datasets": {"ACCTFILE": {"compare": True}, "XREFFILE": {}, "DALYREJS": {"compare": True}}}
    cobol = {"ACCTFILE": b"abc", "DALYREJS": b"zz"}
    java = {"ACCTFILE": b"abc", "DALYREJS": b"zy", "XREFFILE": b"q"}
    got = ej.java_outputs({"forged_job": {}}, case, cobol, java)
    assert set(got) == {"ACCTFILE", "DALYREJS"}
    assert got["ACCTFILE"]["equal"] is True and got["DALYREJS"]["equal"] is False
    assert got["ACCTFILE"]["sha256"] == hashlib.sha256(b"abc").hexdigest()
    assert ej.java_outputs({}, case, cobol, java) == {}
    assert ej.java_outputs({"forged_job": {}}, case, {}, java) == {}
