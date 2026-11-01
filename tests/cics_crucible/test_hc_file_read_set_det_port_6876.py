"""#6876 (X58): the deterministic port of hc-file-read-set's HCRDST (77/77 statements, no holes).

READ / STARTBR / READNEXT / READPREV SET(ADDRESS OF LS-REC) translate whole (#7260). The four scenarios still fail on both
Java sides, and for one named reason: the case states no key for file HCRS (the CSD has DSNAME only), so the generated
project stores no file and the port refuses by name (a Hole) at the first file command. That is the ledger's reason, not
"no port of any of its programs"; what lifts it is a stated key in the corpus plus a data seed on the Java sides."""

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

CASE = "hc-file-read-set"
OVERLAY = det.DET_PORTS / CASE / "HCRS" / "overlay"
SERVICE = OVERLAY / "service" / "HcrdstService.java"
HOLE = "the program names no file the generated project stores"
FIRST = {"read-set": "READ", "browse-fwd": "STARTBR", "browse-back": "STARTBR", "browse-notfnd": "STARTBR"}


def test_the_case_is_registered_and_the_port_declares_itself_to_the_scanner():
    assert det.PROGRAMS[CASE] == ("HCRS", ("HCRDST",))
    text = SERVICE.read_text(encoding="utf-8")
    assert text.startswith("// gitgalaxy-det-port: COBOL HCRDST ")
    assert max(len(line) for line in text.splitlines()) < 500
    assert ", holes 0." in text


def test_every_file_command_form_is_in_the_port():
    text = SERVICE.read_text(encoding="utf-8")
    for command in ("READ", "STARTBR", "READNEXT", "READPREV", "ENDBR"):
        assert command in text
    assert "setBlockAt" in text  # SET(ADDRESS OF LS-REC) re-bases the linkage record on the record CICS supplies


def test_the_ports_dir_adds_the_runtime_and_keeps_the_service(tmp_path):
    out = det.ports_dir(CASE, tmp_path)
    overlay = out / "HCRS" / "overlay"
    assert (overlay / "service" / "HcrdstService.java").is_file() and (overlay / "cobolrt" / "Cobol.java").is_file()
    assert runner.case_overlays(out) == {"HCRS": overlay}


def test_the_ledger_names_the_unstored_file_for_every_scenario_and_both_ported_sides():
    ledger = json.loads((TESTS / "cics_crucible" / "baseline.json").read_text(encoding="utf-8"))["cells"]
    for sc, command in FIRST.items():
        for side in ("java-ported", "java-facade"):
            reason = ledger[f"{CASE}/{sc}/{side}"]["reason"]
            assert f"{command} expected, got DRIVER-ERROR" in reason and HOLE in reason
            assert "no port" not in reason


E2E = os.environ.get("EQUIVALENCE_E2E") == "1" and bool(os.environ.get(runner.PATH_ENV))


@pytest.mark.slow(reason="a Maven build of the generated project with the det port, two sides")
@pytest.mark.e2e
@pytest.mark.skipif(not E2E, reason="needs EQUIVALENCE_E2E=1, a JDK + Maven and a cics-crucible checkout")
def test_each_scenario_stops_at_the_unstored_file_on_both_sides(tmp_path):
    crucible = Path(os.environ[runner.PATH_ENV])
    offline = os.environ.get("MAVEN_OFFLINE") == "1"
    res = runner.measure(crucible, {CASE}, {"java-ported", "java-facade"}, tmp_path / "w", offline,
                         runner.PortOptions(ports=det.ports_dir(CASE, tmp_path / "ports")))  # fmt: skip
    for c in res["cells"].values():
        assert c["status"] == "fail" and HOLE in c["reason"] and FIRST[c["scenario"]] in c["reason"]
