"""#6876: the deterministic port of hc-file-unlock's HCUNLK (70/70 statements, no holes).

UNLOCK with no TOKEN translates whole and records the SPEC 6.2 UNLOCK event (`task.unlock`, not the event-free `unlockHeld`).
The case now states the key of file HCUF (jcl/DEFVSAM.jcl: IDCAMS KEYS(4 0), cics-crucible #51), so the generated entity has a
key and the READ UPDATE / REWRITE / READ no longer stop at a named hole (X58). The four scenarios still fail on both Java sides:
the port's READ UPDATE / REWRITE are the event-free `CicsTask.readForUpdate` / `rewrite` forms, so the log has no READ or
REWRITE event (the next event is the WRITEQ-TS of the HCLOG line)."""

import json
import os
import re
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(TESTS))
import cics_crucible as runner  # noqa: E402
import cics_crucible_det as det  # noqa: E402

CASE = "hc-file-unlock"
OVERLAY = det.DET_PORTS / CASE / "HCUF" / "overlay"
SERVICE = OVERLAY / "service" / "HcunlkService.java"
SCENARIOS = ("update-rewrite", "unlock-rewrite", "unlock-nothing", "read-short")


def test_the_case_is_registered_and_the_port_declares_itself_to_the_scanner():
    assert det.PROGRAMS[CASE] == ("HCUF", ("HCUNLK",))
    text = SERVICE.read_text(encoding="utf-8")
    assert text.startswith("// gitgalaxy-det-port: COBOL HCUNLK ")
    assert max(len(line) for line in text.splitlines()) < 500
    assert "Statements: 70, translated 70, holes 0." in text


def test_a_tokenless_unlock_is_the_recorded_event_and_the_port_has_no_hole():
    text = SERVICE.read_text(encoding="utf-8")
    assert text.count('task.unlock("HCUF".stripTrailing())') == 2  # UNLOCK-PARA and NOTHING-PARA
    assert "unlockHeld" not in text  # the event-free form would drop the UNLOCK event from the log
    assert not re.findall(r'throw new Hole\("line (\d+): ', text)


def test_the_ports_dir_adds_the_runtime_and_keeps_the_service(tmp_path):
    out = det.ports_dir(CASE, tmp_path)
    overlay = out / "HCUF" / "overlay"
    assert (overlay / "service" / "HcunlkService.java").is_file() and (overlay / "cobolrt" / "Cobol.java").is_file()
    assert runner.case_overlays(out) == {"HCUF": overlay}


def test_the_ledger_names_the_missing_file_event_not_a_hole_on_both_ported_sides():
    ledger = json.loads((TESTS / "cics_crucible" / "baseline.json").read_text(encoding="utf-8"))["cells"]
    for sc in SCENARIOS:
        for side in ("java-ported", "java-facade"):
            reason = ledger[f"{CASE}/{sc}/{side}"]["reason"]
            assert "expected, got WRITEQ-TS" in reason
            assert "Hole" not in reason and "no port" not in reason


E2E = os.environ.get("EQUIVALENCE_E2E") == "1" and bool(os.environ.get(runner.PATH_ENV))


@pytest.mark.slow(reason="a Maven build of the generated project with the det port, two sides")
@pytest.mark.e2e
@pytest.mark.skipif(not E2E, reason="needs EQUIVALENCE_E2E=1, a JDK + Maven and a cics-crucible checkout")
def test_each_scenario_stops_at_the_missing_file_event_on_both_sides(tmp_path):
    crucible = Path(os.environ[runner.PATH_ENV])
    offline = os.environ.get("MAVEN_OFFLINE") == "1"
    res = runner.measure(crucible, {CASE}, {"java-ported", "java-facade"}, tmp_path / "w", offline,
                         runner.PortOptions(ports=det.ports_dir(CASE, tmp_path / "ports")))  # fmt: skip
    for c in res["cells"].values():
        assert c["status"] == "fail" and "expected, got WRITEQ-TS" in c["reason"] and "Hole" not in c["reason"]
