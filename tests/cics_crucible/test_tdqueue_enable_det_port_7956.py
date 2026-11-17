"""#7956: the deterministic port of hc-tdqueue-enable's HCTDEN (52/52 statements, no holes) passes the java-ported side
with the crucible's equal log. The committed ports/ hold only model ports, so the det port lives in det-ports/.

The case turns on a harness fact, not on the port: the CSD defines HCQ1 and deliberately leaves HCNQ undefined, so an
INQUIRE / SET TDQUEUE naming HCNQ is QIDERR RESP2 1. `java_plan` carries the CSD's TDQUEUEs into plan.json and the
generated test hands them to CicsTask; without them the task takes every queue as defined and answers NORMAL, which
failed the `inquire` and `undefined` scenarios (2 of 4) while `toggle` and `badcvda` passed.
"""

import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(TESTS))
import cics_crucible as runner  # noqa: E402
import cics_crucible_det as det  # noqa: E402

CASE = "hc-tdqueue-enable"
OVERLAY = det.DET_PORTS / CASE / "HCTD" / "overlay"
SERVICE = OVERLAY / "service" / "HctdenService.java"


def test_the_case_is_registered_and_the_port_declares_itself_to_the_scanner():
    assert det.PROGRAMS[CASE] == ("HCTD", ("HCTDEN",))
    text = SERVICE.read_text(encoding="utf-8")
    assert text.startswith("// gitgalaxy-det-port: COBOL HCTDEN ")
    assert max(len(line) for line in text.splitlines()) < 500


def test_the_port_runs_the_tdqueue_lane_through_the_runtime():
    text = SERVICE.read_text(encoding="utf-8")
    for call in ("task.inquireTdQueue(", "task.setTdQueueEnableStatus("):
        assert call in text, call


def test_the_ports_dir_adds_the_runtime_and_keeps_the_service(tmp_path):
    out = det.ports_dir(CASE, tmp_path)
    overlay = out / "HCTD" / "overlay"
    assert (overlay / "service" / "HctdenService.java").is_file()
    assert (overlay / "cobolrt" / "cics" / "DetCics.java").is_file()


def test_the_java_plan_carries_the_csd_tdqueues_so_an_undefined_queue_is_qiderr():
    """The gap that held PR #8288: with no `tdqueues` in plan.json every queue looks defined and HCNQ answers NORMAL."""
    src = Path(runner.__file__).read_text(encoding="utf-8")
    # the plan emits them, only when the case's CSD defines some
    assert '**({"tdqueues": case.csd["tdqueues"]} if case.csd.get("tdqueues") else {}),' in src
    # the generated test hands them to the task, with the attributes that carry RECOVSTATUS (#5168, X61)
    assert 'if (plan.hasNonNull("tdqueues")) {' in src
    assert "t.withTdQueues(names).withTdQueueTypes(types);" in src
    assert "t.withTdQueueAttributes(attrs.toArray(new String[0]));" in src
