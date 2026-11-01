"""#6876: the deterministic port of ca-getmain-pointer's CAGMPT and CAGMZ (46/46 and 43/43 statements, no holes) passes both
Java sides with the crucible's equal log. The committed ports/ hold only model ports, so the det port lives in det-ports/ and
the proof is `--ports det.ports_dir(...)`; the bare `java` side stays the generated skeleton (it fails for every case)."""

import os
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(TESTS))
import cics_crucible as runner  # noqa: E402
import cics_crucible_det as det  # noqa: E402

CASE = "ca-getmain-pointer"
OVERLAY = det.DET_PORTS / CASE / "CAGM" / "overlay"
SERVICES = {"CAGMPT": OVERLAY / "service" / "CagmptService.java", "CAGMZ": OVERLAY / "service" / "CagmzService.java"}


def test_the_case_is_registered_and_each_port_declares_itself_to_the_scanner():
    assert det.PROGRAMS[CASE] == ("CAGM", ("CAGMPT", "CAGMZ"))
    for prog, path in SERVICES.items():
        text = path.read_text(encoding="utf-8")
        assert text.startswith(f"// gitgalaxy-det-port: COBOL {prog} ")
        assert max(len(line) for line in text.splitlines()) < 500


def test_the_ports_run_the_pointer_lane_through_the_runtime():
    pt = SERVICES["CAGMPT"].read_text(encoding="utf-8")
    zero = SERVICES["CAGMZ"].read_text(encoding="utf-8")
    for call in ("DetCics.getmain(", "DetCics.setAddress(", "DetCics.freemainData("):
        assert call in pt
    assert "DetCics.getmain(" in zero and "DetCics.freemainData(" in zero


def test_the_ports_dir_adds_the_runtime_and_keeps_the_services(tmp_path):
    out = det.ports_dir(CASE, tmp_path)
    overlay = out / "CAGM" / "overlay"
    assert (overlay / "service" / "CagmptService.java").is_file() and (overlay / "cobolrt" / "Cobol.java").is_file()
    assert runner.case_overlays(out) == {"CAGM": overlay}


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
    assert cells == {(s, side): "pass" for s in ("alloc", "zero-length") for side in ("java-ported", "java-facade")}
