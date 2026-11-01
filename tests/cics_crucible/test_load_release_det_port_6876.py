"""#6876 (X65): the deterministic port of ca-load-set's CALDST, CALDSX and CALDTG (23/23, 27/27 and 1/1 statements, no holes)
passes both Java sides with the crucible's equal log. CALDTG (a bare RETURN, LOADed and never run) is a CICS program only
through the LOAD edge the call-site reader now records: without it the forge gave it a plain service and a hole."""

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
SERVICES = {p: OVERLAY / "service" / f"{p.capitalize()}Service.java" for p in ("CALDST", "CALDSX", "CALDTG")}


def test_the_case_is_registered_and_each_port_declares_itself_to_the_scanner():
    assert det.PROGRAMS[CASE] == ("CALD", ("CALDST", "CALDSX", "CALDTG"))
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
    assert (overlay / "service" / "CaldtgService.java").is_file()


@pytest.mark.parametrize(
    ("source", "verb", "form", "operand"),
    [
        ("EXEC CICS LOAD PROGRAM('CALDTG') SET(P) LENGTH(L) END-EXEC", "LOAD", "literal", "CALDTG"),
        ("EXEC CICS LOAD PROGRAM(WS-PGM) NOHANDLE END-EXEC", "LOAD", "identifier", "WS-PGM"),
        ("EXEC CICS LOAD\n   PROGRAM ( 'CALDTG' )\n   SET(P)\n END-EXEC", "LOAD", "literal", "CALDTG"),
        ("EXEC CICS LOAD SET(P) END-EXEC", "LOAD", "unknown", None),
        ("EXEC CICS LINK PROGRAM('CALDTG') END-EXEC", "LINK", "literal", "CALDTG"),
    ],
)
def test_the_call_site_reader_records_a_load_as_an_edge_without_a_commarea_contract(source, verb, form, operand):
    from gitgalaxy.core.mainframe_boundary import _cobol_calls

    (site,) = _cobol_calls(source, {}, loads=True)
    assert (site["verb"], site["form"], site["operand"]) == (verb, form, operand)
    if verb == "LOAD":  # LOAD's LENGTH is the image's, never a COMMAREA length
        assert "commarea_length" not in site and "commarea" not in site


def test_a_load_is_read_for_cobol_hosts_only():
    from gitgalaxy.core.mainframe_boundary import _cobol_calls

    src = "EXEC CICS LOAD PROGRAM('X') END-EXEC"
    assert _cobol_calls(src, {}) == [] and _cobol_calls(src, {}, cics_only=True) == []  # PL/I, HLASM: unchanged


def test_release_is_not_an_edge():
    from gitgalaxy.core.mainframe_boundary import _cobol_calls

    assert _cobol_calls("EXEC CICS RELEASE PROGRAM('CALDTG') END-EXEC", {}, loads=True) == []


def _skeleton(nav):
    return {"program": {"file": "src/CALDTG.cbl"}, "sections": {"navigation": {"facts": nav}}}


def test_a_loaded_only_program_is_a_cics_program_and_has_no_link_handler():
    from gitgalaxy.tools.cobol_to_java import cobol_to_java_transaction_forge as F

    load = {"from": "src/CALDST.cbl", "line": 9, "verb": "LOAD", "to": "src/CALDTG.cbl", "via": "static"}
    assert F.is_cics_program(_skeleton([load])) and F.loaded_by(_skeleton([load])) == ["src/CALDST.cbl"]
    assert F.incoming_links(_skeleton([load])) == []  # a LOAD is not a LINK: no handler, no contract
    assert not F.is_cics_program(_skeleton([]))
    other = dict(load, to="src/OTHER.cbl")
    assert not F.is_cics_program(_skeleton([other]))


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
