"""#6876: the deterministic ports of the three WEB server cases (GTHECHO, GTWRECV, GTWSEND: every statement translated, no
holes) pass both Java sides with the crucible's equal log. The committed ports/ hold only model ports, so the det ports
live in det-ports/ and the proof is `--ports det.ports_dir(...)`; the bare `java` side stays the generated skeleton."""

import os
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(TESTS))
import cics_crucible as runner  # noqa: E402
import cics_crucible_det as det  # noqa: E402

# case -> (program, service class, the verbs its port must call, its scenarios)
CASES = {
    "gt-http-inbound": ("GTHECHO", "GthechoService", ("task.webReceive(", "task.webSend("), ("echo",)),
    "gt-web-server-receive": (
        "GTWRECV",
        "GtwrecvService",
        ("task.webReceive(",),
        ("extract", "header", "lengerr", "receive"),
    ),
    "gt-web-server-send": ("GTWSEND", "GtwsendService", ("task.webSend(",), ("send",)),
}


@pytest.mark.parametrize("case", CASES)
def test_the_case_is_registered_and_the_port_declares_itself_to_the_scanner(case):
    program, service, _, _ = CASES[case]
    assert det.PROGRAMS[case][1] == (program,)
    path = det.DET_PORTS / case / det.PROGRAMS[case][0] / "overlay" / "service" / f"{service}.java"
    text = path.read_text(encoding="utf-8")
    assert text.startswith(f"// gitgalaxy-det-port: COBOL {program}")
    assert max(len(line) for line in text.splitlines()) < 500


@pytest.mark.parametrize("case", CASES)
def test_the_port_runs_the_web_server_verbs(case):
    program, service, verbs, _ = CASES[case]
    path = det.DET_PORTS / case / det.PROGRAMS[case][0] / "overlay" / "service" / f"{service}.java"
    text = path.read_text(encoding="utf-8")
    for call in verbs:
        assert call in text


@pytest.mark.parametrize("case", CASES)
def test_the_ports_dir_adds_the_runtime_and_keeps_the_service(case, tmp_path):
    program, service, _, _ = CASES[case]
    out = det.ports_dir(case, tmp_path)
    overlay = out / det.PROGRAMS[case][0] / "overlay"
    assert (overlay / "service" / f"{service}.java").is_file() and (overlay / "cobolrt" / "Cobol.java").is_file()
    assert runner.case_overlays(out) == {det.PROGRAMS[case][0]: overlay}


E2E = os.environ.get("EQUIVALENCE_E2E") == "1" and bool(os.environ.get(runner.PATH_ENV))


@pytest.mark.slow(reason="a Maven build of the generated project with the det port, two sides, per case")
@pytest.mark.e2e
@pytest.mark.skipif(not E2E, reason="needs EQUIVALENCE_E2E=1, a JDK + Maven and a cics-crucible checkout")
@pytest.mark.parametrize("case", CASES)
def test_the_crucible_passes_every_scenario_on_the_cobol_stub_and_both_java_sides(case, tmp_path):
    crucible = Path(os.environ[runner.PATH_ENV])
    offline = os.environ.get("MAVEN_OFFLINE") == "1"
    res = runner.measure(crucible, {case}, {"cobol-stub", "java-ported", "java-facade"}, tmp_path / "w", offline,
                         runner.PortOptions(ports=det.ports_dir(case, tmp_path / "ports")))  # fmt: skip
    cells = {(c["scenario"], c["side"]): c["status"] for c in res["cells"].values()}
    scenarios = CASES[case][3]
    assert cells == {(s, side): "pass" for s in scenarios for side in ("cobol-stub", "java-ported", "java-facade")}
