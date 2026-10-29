"""#6967: a batch case's fault entry states its own IMS seed (`ims_seed`, as a CICS scenario does, #6072): the COBOL run
stages its own `dli` directory and the Java run is pointed at it. Pure Python: no Java, no Docker."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence as eq  # noqa: E402
import equivalence_cics as ec  # noqa: E402
import equivalence_common as common  # noqa: E402
import equivalence_ims as ims  # noqa: E402

CASE = ROOT / "tests" / "equivalence" / "carddemo-cbpaup0c" / "case.json"
APP = "app/app-authorization-ims-db2-mq"
INSERT = {"DBPAUTP0": {"insert": [{"after": 8, "segment": "PAUTDTL1",
                                   "fields": {"PA-AUTH-TIME-9C": 835153124, "PA-AUTH-RESP-CODE": "05"}}]}}  # fmt: skip


def _case() -> dict:
    return json.loads(CASE.read_text(encoding="utf-8"))


def _corpus() -> Path | None:
    corpora = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    corpus = corpora / "aws-mainframe-modernization-carddemo"
    return corpus if (corpus / APP / "cbl/CBPAUP0C.cbl").is_file() else None


needs_corpus = pytest.mark.skipif(_corpus() is None, reason="the CardDemo corpus is not checked out")


def _stage(tmp_path: Path, fault: dict | None, name: str = "d") -> Path:
    case, corpus = _case(), _corpus()
    source, _ = common.read_program(case, corpus / case["program_source"])
    ims.stage(case, corpus, source, tmp_path / name, fault)
    return tmp_path / name / "seed.DBPAUTP0"


@needs_corpus
def test_a_fault_with_an_ims_seed_stages_its_own_database_and_the_others_keep_the_case_seed(tmp_path):
    plain = _stage(tmp_path, None, "plain").read_bytes()
    assert _stage(tmp_path, {"name": "other"}, "other").read_bytes() == plain
    seeded = _stage(tmp_path, {"name": "declined", "ims_seed": INSERT}, "declined").read_bytes()
    assert len(seeded) == len(plain) + 8 + 200
    segs = ims.split(seeded, {"PAUTSUM0": 100, "PAUTDTL1": 200})
    assert segs[9][0] == "PAUTDTL1" and len(segs) == len(ims.split(plain, {"PAUTSUM0": 100, "PAUTDTL1": 200})) + 1


@needs_corpus
def test_the_seed_a_fault_cannot_keep_in_order_is_refused_by_name(tmp_path):
    bad = {"DBPAUTP0": {"insert": [{**INSERT["DBPAUTP0"]["insert"][0], "after": 9999}]}}
    with pytest.raises(ims.Unsupported, match="no unload record 9999"):
        _stage(tmp_path, {"name": "f", "ims_seed": bad})


@needs_corpus
@pytest.mark.parametrize("stager", ["batch", "cics"])
def test_an_ims_seed_naming_a_dbd_the_case_does_not_have_is_refused(tmp_path, stager):
    fault = {"name": "f", "ims_seed": {"NOSUCHDB": {"insert": []}}}
    with pytest.raises(Exception, match="DBD NOSUCHDB is not in the case"):
        if stager == "batch":
            _stage(tmp_path, fault)
        else:
            ec.dli_stage(_case(), _corpus(), tmp_path / "c", fault)


def test_a_stated_segments_seed_has_nothing_to_insert_into():
    dbds = {"DB": {"name": "DB", "segments": [{"name": "S", "bytes": 2, "fields": []}]}}
    case = {"ims": {"seed": {"DB": {"segments": [{"segment": "S", "hex": "0102"}]}}}}
    assert ims.seed(case, Path("."), "DB", dbds["DB"], None) == b"S       \x01\x02"
    with pytest.raises(ims.Unsupported, match="nothing to insert into"):
        ims.seed(case, Path("."), "DB", dbds["DB"], {"ims_seed": {"DB": {"insert": []}}})
    with pytest.raises(ims.Unsupported, match="has no seed to add to"):
        ims.seed({"ims": {}}, Path("."), "DB", dbds["DB"], {"ims_seed": {"DB": {"insert": []}}})


def test_the_java_run_is_pointed_at_the_dir_only_for_a_seeded_fault(tmp_path):
    assert eq.fault_dli_dir(tmp_path, {"name": "a"}) == ""
    assert eq.fault_dli_dir(tmp_path, {"name": "a", "ims_seed": INSERT}) == str(tmp_path / "faults/a/cobol/dli")


def test_a_fault_with_an_ims_seed_in_a_case_without_ims_is_not_runnable(tmp_path):
    case = {"program": "P", "program_source": "p.cbl", "datasets": {}}
    (tmp_path / "p.cbl").write_text("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n", encoding="ascii")
    with pytest.raises(RuntimeError, match="not runnable faithfully: fault f states an ims_seed"):
        eq.run_cobol(case, tmp_path, tmp_path / "w", {"name": "f", "ims_seed": INSERT})
