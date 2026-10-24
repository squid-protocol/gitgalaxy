"""#4767: the deterministic port of gt-web-client's GTWCLI (15/15 statements, no holes) passes both Java sides with the
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

CASE = "gt-web-client"
OVERLAY = det.DET_PORTS / CASE / "GTWCLI" / "overlay"
SERVICE = OVERLAY / "service" / "GtwcliService.java"


def test_the_case_is_registered_and_the_port_declares_itself_to_the_scanner():
    assert det.PROGRAMS[CASE] == ("GTWCLI", ("GTWCLI",))
    text = SERVICE.read_text(encoding="utf-8")
    assert text.startswith("// gitgalaxy-det-port: COBOL GTWCLI")
    assert max(len(line) for line in text.splitlines()) < 500


def test_the_port_runs_each_web_verb():
    text = SERVICE.read_text(encoding="utf-8")
    for call in ("task.webOpenHost(", "task.webConverse(", "task.webClose("):
        assert call in text


def test_the_ports_dir_adds_the_runtime_and_keeps_the_service(tmp_path):
    out = det.ports_dir(CASE, tmp_path)
    overlay = out / "GTWCLI" / "overlay"
    assert (overlay / "service" / "GtwcliService.java").is_file() and (overlay / "cobolrt" / "Cobol.java").is_file()
    assert runner.case_overlays(out) == {"GTWCLI": overlay}


E2E = os.environ.get("EQUIVALENCE_E2E") == "1" and bool(os.environ.get(runner.PATH_ENV))


@pytest.mark.slow(reason="a Maven build of the generated project with the det port, two sides")
@pytest.mark.e2e
@pytest.mark.skipif(not E2E, reason="needs EQUIVALENCE_E2E=1, a JDK + Maven and a cics-crucible checkout")
def test_the_crucible_passes_both_scenarios_on_the_cobol_stub_and_both_java_sides(tmp_path):
    crucible = Path(os.environ[runner.PATH_ENV])
    offline = os.environ.get("MAVEN_OFFLINE") == "1"
    res = runner.measure(crucible, {CASE}, {"cobol-stub", "java-ported", "java-facade"}, tmp_path / "w", offline,
                         runner.PortOptions(ports=det.ports_dir(CASE, tmp_path / "ports")))  # fmt: skip
    cells = {(c["scenario"], c["side"]): c["status"] for c in res["cells"].values()}
    assert cells == {(s, side): "pass" for s in ("ok", "notfound") for side in ("cobol-stub", "java-ported", "java-facade")}
