"""#6876: the deterministic port of hc-file-unlock's HCUNLK (63/70 statements; the 7 holes are the READ UPDATE / REWRITE / READ).

UNLOCK with no TOKEN translates whole and records the SPEC 6.2 UNLOCK event (`task.unlock`, not the event-free `unlockHeld`):
before this the `unlock-nothing` scenario stopped at event 2 (UNLOCK expected, got WRITEQ-TS). The READ / REWRITE statements
are refused by name: the case states no key for file HCUF (the CSD DEFINE FILE has DSNAME only; the key is 4 bytes only in
the case's NOTES), WS-KEY is a RIDFLD outside the record, and a KSDS key's offset is the cluster's definition, so the port does
not guess offset 0 (X58). What lifts the four scenarios is a stated key in the cics-crucible case plus a pin bump."""

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
HOLE = "no key (the generated entity states none"
SCENARIOS = ("update-rewrite", "unlock-rewrite", "unlock-nothing", "read-short")


def test_the_case_is_registered_and_the_port_declares_itself_to_the_scanner():
    assert det.PROGRAMS[CASE] == ("HCUF", ("HCUNLK",))
    text = SERVICE.read_text(encoding="utf-8")
    assert text.startswith("// gitgalaxy-det-port: COBOL HCUNLK ")
    assert max(len(line) for line in text.splitlines()) < 500
    assert "Statements: 70, translated 63, holes 7." in text


def test_a_tokenless_unlock_is_the_recorded_event_and_every_hole_is_a_named_missing_key():
    text = SERVICE.read_text(encoding="utf-8")
    assert text.count('task.unlock("HCUF".stripTrailing())') == 2  # UNLOCK-PARA and NOTHING-PARA
    assert "unlockHeld" not in text  # the event-free form would drop the UNLOCK event from the log
    holes = re.findall(r'throw new Hole\("line (\d+): [^"]*"\)', text)
    assert len(holes) == 7
    assert all(HOLE in line for line in text.splitlines() if 'throw new Hole("line ' in line)


def test_the_ports_dir_adds_the_runtime_and_keeps_the_service(tmp_path):
    out = det.ports_dir(CASE, tmp_path)
    overlay = out / "HCUF" / "overlay"
    assert (overlay / "service" / "HcunlkService.java").is_file() and (overlay / "cobolrt" / "Cobol.java").is_file()
    assert runner.case_overlays(out) == {"HCUF": overlay}


def test_the_ledger_names_the_missing_key_not_a_missing_port_on_both_ported_sides():
    ledger = json.loads((TESTS / "cics_crucible" / "baseline.json").read_text(encoding="utf-8"))["cells"]
    for sc in SCENARIOS:
        for side in ("java-ported", "java-facade"):
            reason = ledger[f"{CASE}/{sc}/{side}"]["reason"]
            assert "DRIVER-ERROR" in reason and HOLE in reason
            assert "no port" not in reason
    # the UNLOCK event matches the log: unlock-nothing now fails at its REWRITE (event 4), not at the UNLOCK (event 2)
    assert "event 4: REWRITE expected" in ledger[f"{CASE}/unlock-nothing/java-ported"]["reason"]


E2E = os.environ.get("EQUIVALENCE_E2E") == "1" and bool(os.environ.get(runner.PATH_ENV))


@pytest.mark.slow(reason="a Maven build of the generated project with the det port, two sides")
@pytest.mark.e2e
@pytest.mark.skipif(not E2E, reason="needs EQUIVALENCE_E2E=1, a JDK + Maven and a cics-crucible checkout")
def test_each_scenario_stops_at_the_missing_key_on_both_sides(tmp_path):
    crucible = Path(os.environ[runner.PATH_ENV])
    offline = os.environ.get("MAVEN_OFFLINE") == "1"
    res = runner.measure(crucible, {CASE}, {"java-ported", "java-facade"}, tmp_path / "w", offline,
                         runner.PortOptions(ports=det.ports_dir(CASE, tmp_path / "ports")))  # fmt: skip
    for c in res["cells"].values():
        assert c["status"] == "fail" and HOLE in c["reason"]
