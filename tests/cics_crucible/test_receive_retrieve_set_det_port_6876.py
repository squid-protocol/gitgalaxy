"""#6876 (X15): the deterministic port of ca-receive-retrieve-set's CARCST and CARTWK (14/14 statements each, no holes).

RECEIVE SET(pointer) LENGTH(data-area) without MAXLENGTH takes the whole input (X15, #5079), RETRIEVE SET likewise. The
java-ported and java-facade sides pass `short-input`. `retrieve-equal` and `enddata` differ from the crucible's hand-written
log in one place only, the same place as the cobol-stub: the log gives CARTWK's WRITEQ TS RSLOG item 1, but the queue
already holds CARCST's record, so IBM's item is 2 (the log's own `final.ts_queues.RSLOG` lists both records). That is a
corpus defect, ledgered in tests/cics_crucible/baseline.json, not a port difference."""

import json
import os
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(TESTS))
import cics_crucible as runner  # noqa: E402
import cics_crucible_det as det  # noqa: E402

CASE = "ca-receive-retrieve-set"
OVERLAY = det.DET_PORTS / CASE / "CARR" / "overlay"
SERVICES = {p: OVERLAY / "service" / f"{p.capitalize()}Service.java" for p in ("CARCST", "CARTWK")}
ITEM = "task 2 (CA0E) event 2: item 1 expected, got 2"


def test_the_case_is_registered_and_each_port_declares_itself_to_the_scanner():
    assert det.PROGRAMS[CASE] == ("CARR", ("CARCST", "CARTWK"))
    for prog, path in SERVICES.items():
        text = path.read_text(encoding="utf-8")
        assert text.startswith(f"// gitgalaxy-det-port: COBOL {prog} ")
        assert max(len(line) for line in text.splitlines()) < 500
        assert ", holes 0." in text


def test_receive_set_is_unbounded_and_length_is_an_output():
    rc = SERVICES["CARCST"].read_text(encoding="utf-8")
    tw = SERVICES["CARTWK"].read_text(encoding="utf-8")
    assert "task.receive(Integer.MAX_VALUE, false)" in rc  # no MAXLENGTH: nothing bounds the data (X15)
    assert 'DetCics.setBlock(task, f1_WS_PTR, "RECEIVE"' in rc
    assert "BigDecimal.valueOf(received1.length())" in rc  # LENGTH is set to the data's length
    assert "task.retrieve(Integer.MAX_VALUE, false, false, false)" in tw


def test_the_ports_dir_adds_the_runtime_and_keeps_the_services(tmp_path):
    out = det.ports_dir(CASE, tmp_path)
    overlay = out / "CARR" / "overlay"
    assert (overlay / "service" / "CarcstService.java").is_file() and (overlay / "cobolrt" / "Cobol.java").is_file()
    assert runner.case_overlays(out) == {"CARR": overlay}


def test_the_ledger_names_the_log_item_not_a_missing_port_for_the_two_logged_scenarios():
    ledger = json.loads((TESTS / "cics_crucible" / "baseline.json").read_text(encoding="utf-8"))["cells"]
    for side in ("java-ported", "java-facade"):
        assert f"{CASE}/short-input/{side}" not in ledger
        for sc in ("retrieve-equal", "enddata"):
            assert ledger[f"{CASE}/{sc}/{side}"]["reason"] == ITEM == ledger[f"{CASE}/{sc}/cobol-stub"]["reason"]


E2E = os.environ.get("EQUIVALENCE_E2E") == "1" and bool(os.environ.get(runner.PATH_ENV))


@pytest.mark.slow(reason="a Maven build of the generated project with the det port, two sides")
@pytest.mark.e2e
@pytest.mark.skipif(not E2E, reason="needs EQUIVALENCE_E2E=1, a JDK + Maven and a cics-crucible checkout")
def test_short_input_passes_and_the_others_differ_only_at_the_log_item(tmp_path):
    crucible = Path(os.environ[runner.PATH_ENV])
    offline = os.environ.get("MAVEN_OFFLINE") == "1"
    res = runner.measure(crucible, {CASE}, {"java-ported", "java-facade"}, tmp_path / "w", offline,
                         runner.PortOptions(ports=det.ports_dir(CASE, tmp_path / "ports")))  # fmt: skip
    got = {(c["scenario"], c["side"]): (c["status"], c["reason"]) for c in res["cells"].values()}
    for side in ("java-ported", "java-facade"):
        assert got[("short-input", side)][0] == "pass"
        for sc in ("retrieve-equal", "enddata"):
            assert got[(sc, side)] == ("fail", ITEM)
