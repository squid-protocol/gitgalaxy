"""#6876: the deterministic port of hc-file-unlock's HCUNLK (70/70 statements, no holes), proved on both Java sides.

UNLOCK with no TOKEN translates whole and records the SPEC 6.2 UNLOCK event (`task.unlock`, not the event-free `unlockHeld`).
The case states the key of file HCUF (jcl/DEFVSAM.jcl: IDCAMS KEYS(4 0), cics-crucible #51). A program with such an UNLOCK
also records its `READ INTO LENGTH` (`task.readInto`, the READ event with `length`) and its `REWRITE FROM`
(`task.rewriteFrom`) as events, so the four scenarios' logs hold the READ and REWRITE the COBOL stub records: all eight
ported / facade cells pass. The facade's byte-carrying second pass seeds the file again, as the first pass does."""

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


def test_the_port_records_the_read_and_rewrite_events():
    text = SERVICE.read_text(encoding="utf-8")
    assert text.count("task.readInto(") == 4 and text.count("task.rewriteFrom(") == 3
    assert "task.readForUpdate(" not in text and "task.rewrite(" not in text  # the event-free forms drop the events


def test_a_program_without_a_tokenless_unlock_keeps_the_event_free_calls():
    from gitgalaxy.tools.cobol_to_java.det.cics_filecontrol import FileControlCommands as FileControl  # noqa: PLC0415

    class G:
        class p:  # noqa: N801
            class proc:  # noqa: N801
                execs = {1: "READ FILE('F') INTO(R) LENGTH(L) RIDFLD(K) UPDATE", 2: "UNLOCK FILE('F') TOKEN(T)"}

    fc = FileControl.__new__(FileControl)
    fc.g = G
    assert fc._records_file_events() is False
    G.p.proc.execs[3] = "UNLOCK FILE('F')"
    del fc._file_events
    assert fc._records_file_events() is True


def test_the_ledger_no_longer_holds_a_ported_or_facade_cell():
    ledger = json.loads((TESTS / "cics_crucible" / "baseline.json").read_text(encoding="utf-8"))["cells"]
    for sc in SCENARIOS:
        for side in ("java-ported", "java-facade"):
            assert f"{CASE}/{sc}/{side}" not in ledger


E2E = os.environ.get("EQUIVALENCE_E2E") == "1" and bool(os.environ.get(runner.PATH_ENV))


@pytest.mark.slow(reason="a Maven build of the generated project with the det port, two sides")
@pytest.mark.e2e
@pytest.mark.skipif(not E2E, reason="needs EQUIVALENCE_E2E=1, a JDK + Maven and a cics-crucible checkout")
def test_each_scenario_passes_on_both_sides(tmp_path):
    crucible = Path(os.environ[runner.PATH_ENV])
    offline = os.environ.get("MAVEN_OFFLINE") == "1"
    res = runner.measure(crucible, {CASE}, {"java-ported", "java-facade"}, tmp_path / "w", offline,
                         runner.PortOptions(ports=det.ports_dir(CASE, tmp_path / "ports")))  # fmt: skip
    for c in res["cells"].values():
        assert c["status"] == "pass", c["reason"]
