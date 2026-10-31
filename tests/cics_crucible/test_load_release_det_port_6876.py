"""#6876 (X65): the deterministic port of ca-load-set's CALDST and CALDSX (23/23 and 27/27 statements, no holes) passes both
Java sides with the crucible's equal log. CALDTG (a bare RETURN, LOADed and never run) gets a plain service from the forge
(no LOAD edge in the engine yet), so it has no det port: its translation is a hole, pinned here so a forge fix shows up."""

import os
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(TESTS))
import cics_crucible as runner  # noqa: E402
import cics_crucible_det as det  # noqa: E402

CASE = "ca-load-set"
OVERLAY = det.DET_PORTS / CASE / "CALD" / "overlay"
SERVICES = {"CALDST": OVERLAY / "service" / "CaldstService.java", "CALDSX": OVERLAY / "service" / "CaldsxService.java"}


def test_the_case_is_registered_and_each_port_declares_itself_to_the_scanner():
    assert det.PROGRAMS[CASE] == ("CALD", ("CALDST", "CALDSX"))
    for prog, path in SERVICES.items():
        text = path.read_text(encoding="utf-8")
        assert text.startswith(f"// gitgalaxy-det-port: COBOL {prog} ")
        assert max(len(line) for line in text.splitlines()) < 500
        assert ", holes 0." in text


def test_the_ports_load_and_release_through_the_task():
    st = SERVICES["CALDST"].read_text(encoding="utf-8")
    sx = SERVICES["CALDSX"].read_text(encoding="utf-8")
    assert 'task.loadProgram("CALDTG".strip())' in st and 'task.releaseProgram("CALDTG".strip())' in st
    assert 'task.loadProgram("CALDXX".strip())' in sx  # the undefined program: PGMIDERR
    assert 'task.loadProgram("CALDTG".strip())' in sx and 'task.releaseProgram("CALDTG".strip())' in sx


def test_the_ports_dir_adds_the_runtime_and_keeps_the_services(tmp_path):
    out = det.ports_dir(CASE, tmp_path)
    overlay = out / "CALD" / "overlay"
    assert (overlay / "service" / "CaldstService.java").is_file() and (overlay / "cobolrt" / "Cobol.java").is_file()
    assert runner.case_overlays(out) == {"CALD": overlay}
    assert not (overlay / "service" / "CaldtgService.java").exists()


E2E = os.environ.get("EQUIVALENCE_E2E") == "1" and bool(os.environ.get(runner.PATH_ENV))


@pytest.mark.slow(reason="a Maven build of the generated project with the det port, two sides")
@pytest.mark.e2e
@pytest.mark.skipif(not E2E, reason="needs EQUIVALENCE_E2E=1, a JDK + Maven and a cics-crucible checkout")
def test_the_crucible_passes_every_scenario_on_the_java_ported_and_facade_sides(tmp_path):
    crucible = Path(os.environ[runner.PATH_ENV])
    offline = os.environ.get("MAVEN_OFFLINE") == "1"
    res = runner.measure(crucible, {CASE}, {"java-ported", "java-facade"}, tmp_path / "w", offline,
                         runner.PortOptions(ports=det.ports_dir(CASE, tmp_path / "ports")))  # fmt: skip
    cells = {(c["scenario"], c["side"]): c["status"] for c in res["cells"].values()}
    assert cells == {(s, side): "pass" for s in ("load", "pgmiderr") for side in ("java-ported", "java-facade")}
