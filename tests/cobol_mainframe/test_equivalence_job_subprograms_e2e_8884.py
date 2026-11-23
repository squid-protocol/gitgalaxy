"""#8884: a job step that is a case with `subprograms` (CardDemo CBSTM03A CALLs CBSTM03B), run for real.

The stubbed job tests (`test_equivalence_job_4268.py`) pin that both sides are handed the step's `subprograms`; this runs
the lowered SORT step (`carddemo-sort-tranrept`) and then CBSTM03A in JCL order through `equivalence_job.run_case` with
GnuCOBOL and the port, both compiled with CBSTM03B. The real run needs Docker, a JDK and Maven (`EQUIVALENCE_E2E=1`)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "tools"))
import equivalence as eq  # noqa: E402
import equivalence_job as ej  # noqa: E402

SORT, CALLER = "carddemo-sort-tranrept", "carddemo-cbstm03a"


def _job():
    return {"name": "carddemo-job-sort-then-cbstm03a", "kind": "job", "job": "CREASTMT",
            "steps": [{"case": SORT}, {"case": CALLER}]}  # fmt: skip


def test_a_sort_step_then_a_subprograms_step_passes_check_job_over_the_real_cases():
    job = _job()
    cases = ej.load_steps(job, eq.load_case)
    ej.check_job(job, cases)
    assert ej.step_names(job) == [SORT, CALLER]
    assert cases[CALLER]["subprograms"] == ["app/cbl/CBSTM03B.CBL"]
    assert "subprograms" not in cases[SORT]


def test_a_subprograms_path_the_step_also_names_as_its_program_is_refused_by_name():
    job = _job()
    cases = ej.load_steps(job, eq.load_case)
    cases[CALLER] = {**cases[CALLER], "subprograms": [cases[CALLER]["program_source"]]}
    with pytest.raises(ej.Unsupported, match="own program"):
        ej.check_job(job, cases)


def test_the_called_program_source_is_in_the_case_corpus():
    import mainframe_corpus as mc

    case = eq.load_case(CALLER)
    (entry,) = mc.select([case["corpus"]])
    try:
        corpus = mc.require_clone(entry)
    except (Exception, SystemExit) as e:  # no CardDemo clone at its pinned ref (require_clone exits)
        pytest.skip(f"no corpus clone: {e}")
    for rel in case["subprograms"]:
        assert (Path(corpus) / rel).is_file(), rel


@pytest.mark.slow(reason="a real GnuCOBOL + Java run of two job steps (~30 s)")
@pytest.mark.skipif(
    os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL), a JDK + Maven and the CardDemo corpus"
)
def test_a_sort_step_then_a_subprograms_step_is_proved_end_to_end(tmp_path):
    code = ej.run_case(eq, _job(), tmp_path)
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert [s["case"] for s in report["steps"]] == [SORT, CALLER]
    assert code == 0 and report["proven"], report
    assert report["steps"][1]["subprograms"] == ["app/cbl/CBSTM03B.CBL"]
    for step in report["steps"]:
        assert step["ok"] and step["outputs"], step
        assert all(d["equal"] == d["records"] and d["records"] > 0 for d in step["outputs"].values()), step


@pytest.mark.slow(reason="a real GnuCOBOL + Java run of the padded CREASTMT job: SORT, IDCAMS, CBSTM03A + CBSTM03B")
@pytest.mark.skipif(
    os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL), a JDK + Maven and the CardDemo corpus"
)
def test_the_padded_creastmt_job_runs_sort_idcams_and_the_subprograms_step_in_order(tmp_path):
    code = ej.run_case(eq, eq.load_case("carddemo-job-creastmt-padded"), tmp_path)
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert [s["case"] for s in report["steps"]] == [
        "carddemo-sort-creastmt-padded",
        "creastmt-step020",
        "carddemo-cbstm03a",
    ]
    assert code == 0 and report["proven"], report
    assert report["steps"][2]["subprograms"] == ["app/cbl/CBSTM03B.CBL"]
