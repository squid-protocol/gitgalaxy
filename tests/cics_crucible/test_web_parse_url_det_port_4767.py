"""#4767: the deterministic port of gt-web-parse-url's GTWPARS (72/72 statements, no holes) passes both Java sides with the
crucible's equal log. The committed ports/ hold only model ports, so the det port lives in det-ports/ and the proof is
`--ports det.ports_dir(...)`; the bare `java` side stays the generated skeleton (it fails for every case)."""

import os
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(TESTS))
import cics_crucible as runner  # noqa: E402
import cics_crucible_det as det  # noqa: E402

CASE = "gt-web-parse-url"
OVERLAY = det.DET_PORTS / CASE / "GTWPARS" / "overlay"
SERVICE = OVERLAY / "service" / "GtwparsService.java"


def test_the_case_is_registered_and_the_port_declares_itself_to_the_scanner():
    assert det.PROGRAMS[CASE] == ("GTWPARS", ("GTWPARS",))
    text = SERVICE.read_text(encoding="utf-8")
    assert text.startswith("// gitgalaxy-det-port: COBOL GTWPARS")
    assert max(len(line) for line in text.splitlines()) < 500


def test_the_port_runs_web_parse():
    text = SERVICE.read_text(encoding="utf-8")
    for call in ("task.webParse(",):
        assert call in text


def test_the_ports_dir_adds_the_runtime_and_keeps_the_service(tmp_path):
    out = det.ports_dir(CASE, tmp_path)
    overlay = out / "GTWPARS" / "overlay"
    assert (overlay / "service" / "GtwparsService.java").is_file() and (overlay / "cobolrt" / "Cobol.java").is_file()
    assert runner.case_overlays(out) == {"GTWPARS": overlay}


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
    assert cells == {
        (s, side): "pass" for s in ("parse", "errors", "lengerr") for side in ("java-ported", "java-facade")
    }
