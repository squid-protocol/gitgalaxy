"""#6876 (X58): the deterministic port of hc-file-read-set's HCRDST (77/77 statements, no holes).

READ / STARTBR / READNEXT / READPREV SET(ADDRESS OF LS-REC) translate whole (#7260). The case now states the key of file HCRS
(jcl/DEFVSAM.jcl: IDCAMS KEYS(4 0), cics-crucible #51), and the forge resolves the `ADDRESS OF LS-REC` record operand to
LS-REC, so the generated project stores the file (entity LsRec, key from IDCAMS KEYS) and the port no longer stops at a Hole.
The four scenarios still fail on both Java sides, for one named reason: the port's file commands are the event-free
`CicsTask.read` forms, so the log has no READ / STARTBR event (the next event is the WRITEQ-TS of the HCLOG line)."""

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


def test_the_ledger_names_the_missing_file_event_not_a_hole_for_every_scenario_and_both_ported_sides():
    ledger = json.loads((TESTS / "cics_crucible" / "baseline.json").read_text(encoding="utf-8"))["cells"]
    for sc, command in FIRST.items():
        for side in ("java-ported", "java-facade"):
            reason = ledger[f"{CASE}/{sc}/{side}"]["reason"]
            assert f"{command} expected, got WRITEQ-TS" in reason
            assert "Hole" not in reason and "no port" not in reason


def test_the_translated_service_resolves_the_file_and_cites_no_missing_key():
    text = SERVICE.read_text(encoding="utf-8")
    assert (
        'case "HCRS" -> new DetCics.Store<LsRec>' in text and "no store in the generated project" in text
    )  # the default arm only
    assert 'throw new Hole("line' not in text


def test_an_address_of_record_operand_names_the_based_item():
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import _operand_name

    assert _operand_name("ADDRESS OF LS-REC") == ("LS-REC", None)
    assert _operand_name("ADDRESS OF LS-REC OF LS-GROUP") == ("LS-REC", "LS-GROUP")
    assert _operand_name("WS-REC") == ("WS-REC", None)
    assert _operand_name("ADDRESS") == ("ADDRESS", None)  # a data item named ADDRESS is still a name


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
        assert c["status"] == "fail" and f"{FIRST[c['scenario']]} expected, got WRITEQ-TS" in c["reason"]
