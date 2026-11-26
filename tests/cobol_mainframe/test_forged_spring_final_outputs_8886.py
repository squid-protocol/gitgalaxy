"""#8886 slice 24: a dataset no GDG catalogs (the KSDS after COMBTRAN STEP10's REPRO) is compared with the chain's bytes.

`compare_final` reads the spec's `final_outputs` entries: the chain's `outputs/<case>/<DD>` against the file the forged job
left under the dataset's name. These tests need no JDK: the Spring run's listing is a stub.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "tools"))
import equivalence_forged_spring as efs  # noqa: E402

SPEC = json.loads((REPO / "tests/equivalence/jobs/carddemo-nightly.forged.json").read_text(encoding="utf-8"))
ENTRY = SPEC["final_outputs"][0]


def _file(data: bytes) -> dict:
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _run(job_files: dict) -> dict:
    return {"datasets_by_job": {m: {ENTRY["job"]: job_files} for m in ("strict", "skip")}}


def _outputs(tmp_path: Path, data: bytes) -> Path:
    (tmp_path / ENTRY["case"]).mkdir()
    (tmp_path / ENTRY["case"] / ENTRY["dd"]).write_bytes(data)
    return tmp_path


def test_the_nightly_spec_names_the_ksds_comtran_step10_leaves():
    assert (ENTRY["job"], ENTRY["case"], ENTRY["dd"]) == ("COMBTRAN", "combtran-step10-idcams", "TRANVSAM")
    assert {m["case"] for m in SPEC["steps"]} >= {ENTRY["case"]}


def test_equal_bytes_are_equal_in_both_modes(tmp_path):
    data = b"A" * 700
    (row,) = efs.compare_final(SPEC, _outputs(tmp_path, data), _run({ENTRY["dataset"]: _file(data)}))
    assert [row["modes"][m]["status"] for m in ("strict", "skip")] == ["equal", "equal"]
    assert efs.differs({"rows": [], "datasets": [row]}) == []


def test_other_bytes_differ_and_name_both_digests(tmp_path):
    (row,) = efs.compare_final(SPEC, _outputs(tmp_path, b"A" * 700), _run({ENTRY["dataset"]: _file(b"B" * 700)}))
    md = row["modes"]["strict"]
    assert md["status"] == "differs" and "chain 700 bytes" in md["issue"]
    assert len(efs.differs({"rows": [], "datasets": [row]})) == 2


def test_a_missing_file_or_missing_chain_output_differs(tmp_path):
    (row,) = efs.compare_final(SPEC, _outputs(tmp_path, b"A"), _run({}))
    assert "left no" in row["modes"]["skip"]["issue"]
    (row,) = efs.compare_final(SPEC, None, _run({ENTRY["dataset"]: _file(b"A")}))
    assert row["modes"]["strict"]["status"] == "differs" and "exported no" in row["modes"]["strict"]["issue"]


def test_a_spec_without_final_outputs_adds_no_rows():
    assert efs.compare_final({}, None, {}) == []
