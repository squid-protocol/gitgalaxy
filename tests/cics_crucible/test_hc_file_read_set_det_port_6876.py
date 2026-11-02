"""#6876 (X58), #7434: the deterministic port of hc-file-read-set's HCRDST (77/77 statements, no holes).

READ / STARTBR / READNEXT / READPREV SET(ADDRESS OF LS-REC) translate whole (#7260). The case states the key of file HCRS
(jcl/DEFVSAM.jcl: IDCAMS KEYS(4 0), cics-crucible #51), and the forge resolves the `ADDRESS OF LS-REC` record operand to
LS-REC, so the generated project stores the file (entity LsRec, key from IDCAMS KEYS) and the port no longer stops at a Hole.
Since #7434 the file commands are the SPEC 6.2 event forms (`readSetEvent`, `startbrEvent`, `readnextSetEvent`,
`readprevSetEvent`, `endbrEvent`), so the log carries the READ / STARTBR event. Since #6876 the
Java sides pass all four scenarios: the runner reads the event's `ridfld` / `data` bytes in the runtime's page (the
program's ASCII bytes, as the stub's) and the Java driver seeds the repository from the case's data/HCRS.dat."""

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
RIDFLD = {"read-set": "D2F0F3F0", "browse-fwd": "D2F0F1F5", "browse-back": "D2F0F4F0", "browse-notfnd": "D2F0F6F0"}


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
    for event_form in ("readSetEvent(", "startbrEvent(", "readnextSetEvent(", "readprevSetEvent(", "endbrEvent("):
        assert event_form in text  # #7434: not the event-free read / startbr / readnext / endbr
    assert "setBlockAt" in text  # SET(ADDRESS OF LS-REC) re-bases the linkage record on the record CICS supplies


def test_the_ports_dir_adds_the_runtime_and_keeps_the_service(tmp_path):
    out = det.ports_dir(CASE, tmp_path)
    overlay = out / "HCRS" / "overlay"
    assert (overlay / "service" / "HcrdstService.java").is_file() and (overlay / "cobolrt" / "Cobol.java").is_file()
    assert runner.case_overlays(out) == {"HCRS": overlay}


def test_no_scenario_is_ledgered_as_failing_on_either_ported_side():
    ledger = json.loads((TESTS / "cics_crucible" / "baseline.json").read_text(encoding="utf-8"))["cells"]
    for sc in RIDFLD:
        for side in ("java-ported", "java-facade"):
            assert f"{CASE}/{sc}/{side}" not in ledger  # the ledger holds failures only


def test_a_java_file_event_reads_its_key_and_record_in_the_runtime_page():
    import base64

    def b64(b: bytes) -> str:
        return base64.b64encode(b).decode()

    for kind in ("READ", "WRITE", "DELETE", "STARTBR", "READNEXT", "READPREV"):
        ev = runner._java_file_event(
            kind, {"file": "F", "resp": "NORMAL", "ridfld": b64(b"K030"), "data": b64(b"K030 X")}, "latin-1"
        )
        assert ev["ridfld"] == bytes.fromhex("D2F0F3F0"), kind  # the log's CCSID 037
        if "data" in ev:
            assert ev["data"].encoding == "latin-1" and ev["data"].data == b"K030 X", kind
    high = runner._java_file_event("STARTBR", {"file": "F", "resp": "NORMAL", "ridfld": b64(b"\xff\xff")}, "latin-1")
    assert high["ridfld"] == b"\xff\xff"  # HIGH-VALUES is no text on either leg
    kept = runner._java_file_event("READ", {"file": "F", "resp": "NORMAL", "ridfld": b64(b"\xd2\xf0")})
    assert kept["ridfld"] == b"\xd2\xf0"  # a CicsTask's own events are EBCDIC already: no page, no change
    assert runner._java_file_event("READ", {"file": "F", "resp": "NORMAL"})["ridfld"] is None
    assert runner._java_file_event("DELETE", {"file": "F", "resp": "NORMAL"}).get("ridfld") is None


def test_the_java_plan_seeds_the_files_the_case_has_data_for(tmp_path):
    case = type("C", (), {})()
    case.csd = {"files": {"A": {}, "B": {}, "C": {}}}
    case.dir = tmp_path
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "A.dat").write_bytes(b"K1 a\nK2 b\n")
    (tmp_path / "data" / "B.dat").write_bytes(b"short\nlonger\n")  # not fixed-length: no seed, as the stub's
    assert runner.java_file_seeds(case) == {"A": [b"K1 a".hex(), b"K2 b".hex()]}


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
def test_each_scenario_passes_on_both_sides(tmp_path):
    crucible = Path(os.environ[runner.PATH_ENV])
    offline = os.environ.get("MAVEN_OFFLINE") == "1"
    res = runner.measure(crucible, {CASE}, {"java-ported", "java-facade"}, tmp_path / "w", offline,
                         runner.PortOptions(ports=det.ports_dir(CASE, tmp_path / "ports")))  # fmt: skip
    assert {c["status"] for c in res["cells"].values()} == {"pass"}
