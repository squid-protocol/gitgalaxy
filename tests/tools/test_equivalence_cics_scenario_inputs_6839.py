"""#6839 (row A): the Java side of a scenario that states its own datasets starts from those stated records -- the bytes
the COBOL task started with -- never from the COBOL task's working copy, which the stub updates in place."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec
import equivalence_common as common

CASE = "zecs-zecs001"
KEY = "ZECS.ZC01KEY.TEST"
FILE = "ZECS.ZC01FILE.TEST"


def _case() -> dict:
    case = json.loads((common.CASES / CASE / "case.json").read_text(encoding="utf-8"))
    case["name"] = CASE
    return case


def test_a_scenario_file_is_staged_from_its_stated_records(tmp_path):
    case = _case()
    case["scenarios"] = [s for s in case["scenarios"] if s["name"] == "delete-stored"]
    files = [{"base": KEY, "reclen": 512}, {"base": FILE, "reclen": 32700}]
    ec.stage_scenario_inputs(case, tmp_path / "corpus-unused", files, tmp_path)
    staged = (tmp_path / f"{KEY}.delete-stored.in").read_bytes()
    stated = ec.case_file_records(case, tmp_path, {"input": "@case/zckey-ops.bin"}, 512, common.data_encoding(case))
    assert staged == stated
    assert staged.startswith(b"delkey")  # the record the scenario DELETEs is there for the Java task too


def test_staging_reads_nothing_the_cobol_task_wrote(tmp_path):
    case = _case()
    case["scenarios"] = [s for s in case["scenarios"] if s["name"] == "post-existing"]
    files = [{"base": KEY, "reclen": 512}, {"base": FILE, "reclen": 32700}]
    # a COBOL work dir holding an end state: if staging read it, the staged file would be these bytes
    done = tmp_path / "cobol" / "scenarios" / "post-existing" / "files"
    done.mkdir(parents=True)
    (done / KEY).write_bytes(b"\x00" * 512)
    ec.stage_scenario_inputs(case, tmp_path / "corpus-unused", files, tmp_path)
    assert (tmp_path / f"{KEY}.post-existing.in").read_bytes().startswith(b"delkey")
