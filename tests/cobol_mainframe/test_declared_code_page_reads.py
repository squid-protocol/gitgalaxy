"""#3908 / #3909: the estate's declared code page reaches every read after the scan, and the generated decoder.

The fixture is what a binary transfer of a Danish PDS member delivers: cp277, fixed-block 80, no line
ends. The scan decodes it with the declared page (`--source-encoding cp277`) and records that per file
(file_data.source_decode 'declared'); the refractor's passes and the port tickets must decode it the same
way. Unaided, the bytes fall to the cp1252 guess: one line of garbage, no paragraphs, no facts.
"""

import json
from pathlib import Path

import pytest

from gitgalaxy.cobol_refractor_controller import IRStateManager, process_payload
from gitgalaxy.core.ebcdic_codecs import java_charset_name
from gitgalaxy.tools.cobol_to_cobol.cobol_dag_architect import extract_lineage
from gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder import x_ray_dead_code
from gitgalaxy.tools.cobol_to_cobol.cobol_jcl_forge import analyze_cobol_intent
from gitgalaxy.tools.cobol_to_cobol.cobol_microservice_slicer import slice_business_logic
from gitgalaxy.tools.cobol_to_cobol.cobol_schema_forge import forge_schemas
from gitgalaxy.tools.cobol_to_cobol.cobol_system_limits_reporter import scan_system_limits
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import GalaxyIR
from gitgalaxy.tools.cobol_to_java.cobol_to_java_decoder_forge import generate_decoder_util
from gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets import build_ticket, write_port_tickets

PAGE = "cp277"
PROGRAM = """\
       CBL INTDATE(LILIAN)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. NORDPGM.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT KUNDE-FIL ASSIGN TO KUNDEDD.
       DATA DIVISION.
       FILE SECTION.
       FD  KUNDE-FIL.
       01  KUNDE-REC           PIC X(80).
       WORKING-STORAGE SECTION.
           COPY NORDCPY.
       01  WS-BY               PIC X(10) VALUE 'ÅRHUS'.
       01  WS-INT              PIC S9(7)V99.
       01  WS-UBRUGT           PIC X(4).
       PROCEDURE DIVISION.
       HOVED.
           OPEN INPUT KUNDE-FIL
           READ KUNDE-FIL
           COMPUTE WS-INT ROUNDED = WS-SALDO * 2
           DISPLAY WS-BY
           CLOSE KUNDE-FIL
           GOBACK.
       DOED-AFSNIT.
           ALTER HOVED TO PROCEED TO DOED-AFSNIT
           DISPLAY 'ALDRIG'.
"""
COPYBOOK = """\
       01  WS-SALDO            PIC S9(7)V99.
       01  WS-KOPI-UBRUGT      PIC X(3).
"""


def fixed_block(text: str, page: str = PAGE) -> bytes:
    """A raw FB80 download: each line padded with the EBCDIC space (0x40), no line ends."""
    return b"".join(line.encode(page).ljust(80, b"\x40") for line in text.splitlines())


@pytest.fixture
def estate(tmp_path: Path) -> Path:
    root = tmp_path / "estate"
    (root / "cbl").mkdir(parents=True)
    (root / "cpy").mkdir()
    (root / "cbl" / "NORDPGM.cbl").write_bytes(fixed_block(PROGRAM))
    (root / "cpy" / "NORDCPY.cpy").write_bytes(fixed_block(COPYBOOK))
    return root


# ---- #3908: the generated decoder decodes with the declared page -------------------------------
@pytest.mark.parametrize(
    ("codec", "java"),
    [("cp037", "IBM037"), ("cp1047", "IBM1047"), ("cp273", "IBM273"), ("cp277", "IBM277"), ("cp278", "IBM278"),
     ("cp280", "IBM280"), ("cp284", "IBM284"), ("cp285", "IBM285"), ("cp297", "IBM297"), ("cp500", "IBM500"),
     ("cp1140", "IBM01140"), ("ibm-277", "IBM277"), ("cp1252", "windows-1252"), ("latin-1", "ISO-8859-1"),
     ("utf-8", "UTF-8")],
)  # fmt: skip
def test_the_jdk_name_of_each_code_page(codec, java):
    assert java_charset_name(codec) == java


def test_an_unknown_code_page_has_no_jdk_name():
    with pytest.raises(LookupError):
        java_charset_name("cp9999")


def test_the_decoder_defaults_to_the_default_page_cp037():
    java = generate_decoder_util("com.acme")
    assert 'Charset.forName("IBM037")' in java and "Cp1047" not in java


@pytest.mark.parametrize(("page", "java"), [("cp277", "IBM277"), ("cp1047", "IBM1047"), ("cp1140", "IBM01140")])
def test_the_decoder_decodes_with_the_declared_page(page, java):
    assert f'private static final Charset EBCDIC_CHARSET = Charset.forName("{java}");' in generate_decoder_util(
        "com.acme", page
    )


# ---- #3909: the refractor's passes read the program and its copybooks in the declared page --------
def test_the_dead_code_pass_reads_the_program_and_its_copybook_in_the_page(estate):
    program = estate / "cbl" / "NORDPGM.cbl"
    assert x_ray_dead_code(program, copybook_root=estate) is None  # unaided: one line of cp1252 garbage
    found = x_ray_dead_code(program, copybook_root=estate, declared=PAGE)
    assert found["dead_paras"] == {"DOED-AFSNIT"}
    # WS-KOPI-UBRUGT is declared in the copybook: it is only seen when the COPY member decodes too
    assert found["orphaned_vars"] == {"KUNDE-REC", "WS-UBRUGT", "WS-KOPI-UBRUGT"}


def test_a_utf8_working_copy_still_reads_its_ebcdic_copybook_in_the_page(estate, tmp_path):
    """The lexical patcher's copy is UTF-8; the COPY members it names stay raw EBCDIC in the estate."""
    work = tmp_path / "NORDPGM.cbl"
    work.write_text(PROGRAM, encoding="utf-8")
    assert "WS-KOPI-UBRUGT" not in x_ray_dead_code(work, copybook_root=estate)["orphaned_vars"]
    assert "WS-KOPI-UBRUGT" in x_ray_dead_code(work, copybook_root=estate, declared=PAGE)["orphaned_vars"]


def test_the_forge_passes_read_the_program_in_the_page(estate):
    program = estate / "cbl" / "NORDPGM.cbl"
    assert extract_lineage(program) is None
    assert extract_lineage(program, declared=PAGE)["inputs"] == {"KUNDEDD"}
    assert analyze_cobol_intent(program)["files_requested"] == []
    assert analyze_cobol_intent(program, declared=PAGE)["files_requested"] == [
        {"internal": "KUNDE-FIL", "dd_name": "KUNDEDD"}
    ]
    assert scan_system_limits(program) == []
    (alter,) = scan_system_limits(program, declared=PAGE)
    assert alter.startswith("[NORDPGM.cbl : Line 0026] CRITICAL")
    assert forge_schemas(program) is None
    assert "WS_BY                          VARCHAR(10)" in forge_schemas(program, declared=PAGE)["sql"]
    assert slice_business_logic(program, "WS-INT") is None
    logic, _ = slice_business_logic(program, "WS-INT", declared=PAGE)
    assert [s["statement"] for s in logic] == ["COMPUTE WS-INT ROUNDED = WS-SALDO * 2"]


def test_process_payload_reads_every_line_and_carries_the_page(estate, tmp_path):
    program = estate / "cbl" / "NORDPGM.cbl"
    unaided = process_payload(program, IRStateManager("RAM", tmp_path), source_root=estate)
    assert unaided["metadata"]["loc"] == 1 and "source_encoding" not in unaided["metadata"]
    ir = process_payload(program, IRStateManager("RAM", tmp_path), source_root=estate, declared=PAGE)
    assert ir["metadata"]["loc"] == len(PROGRAM.splitlines())
    assert ir["metadata"]["source_encoding"] == PAGE  # the port tickets read it from here
    assert ir["analysis"]["dead_code"]["dead_paras"] == {"DOED-AFSNIT"}
    assert ir["analysis"]["base_intent"]["files_requested"] == [{"internal": "KUNDE-FIL", "dd_name": "KUNDEDD"}]


def test_a_systsin_member_is_read_in_the_page_of_its_job(tmp_path):
    (tmp_path / "ctl").mkdir()
    (tmp_path / "ctl" / "RUNNORD.ctl").write_bytes(
        fixed_block("  DSN SYSTEM(DB2P)\n  RUN PROGRAM(NORDPGM) PLAN(NORD)\n")
    )
    ir = GalaxyIR(tmp_path / "x.db", "estate", "c0", {}, source_root=tmp_path, source_pages={"jcl/NORD.jcl": PAGE})
    assert "RUN PROGRAM(NORDPGM)" in ir._systsin_member_text("RUNNORD", "jcl/NORD.jcl")
    assert ir.source_page("jcl/NORD.jcl") == PAGE and ir.source_page("jcl/OTHER.jcl") is None


# ---- #3909: the port ticket reads the program in the page -----------------------------------------
def _skeleton() -> dict:
    return {"program": {"file": "cbl/NORDPGM.cbl", "language": "cobol", "program_ids": ["NORDPGM"],
                        "copybooks": ["cpy/NORDCPY.cpy"]}, "sections": {}}  # fmt: skip


def test_the_ticket_reads_rounding_and_cbl_options_in_the_page(estate, tmp_path):
    unaided = build_ticket("NORDPGM", _skeleton(), tmp_path, "com.acme", estate, None, [], {}, None)
    assert unaided["rounding"] == [] and unaided["compiler_options"] == []
    t = build_ticket("NORDPGM", _skeleton(), tmp_path, "com.acme", estate, None, [], {}, None, PAGE)
    assert [(r["verb"], r["targets"][0]["java"]) for r in t["rounding"]] == [("COMPUTE", "HALF_UP")]
    assert [(o["option"], o["value"]) for o in t["compiler_options"]] == [("INTDATE", "LILIAN")]
    assert any("INTDATE(LILIAN)" in rule for rule in t["rules"])


def test_the_ticket_listings_are_readable(estate, tmp_path):
    """write_port_tickets finds the page where it finds the program's path: the refractor's IR dump."""
    clean = tmp_path / "clean"
    (clean / "04_ir_state_dumps").mkdir(parents=True)
    (clean / "06_skeleton").mkdir()
    ir = {"metadata": {"path": str(estate / "cbl" / "NORDPGM.cbl"), "source_encoding": PAGE}}
    (clean / "04_ir_state_dumps" / "NORDPGM_ir.json").write_text(json.dumps(ir), encoding="utf-8")
    skeleton = clean / "06_skeleton" / "NORDPGM_skeleton.json"
    skeleton.write_text(json.dumps(_skeleton()), encoding="utf-8")
    java = tmp_path / "java"
    java.mkdir()
    worklist = {"items": [{"nature": "port", "program": "cbl/NORDPGM.cbl", "id": "W1", "category": "logic",
                           "file": "x.java", "line": 1, "text": "port"}]}  # fmt: skip
    write_port_tickets(java, {"NORDPGM": skeleton}, worklist, None, "com.acme", {}, clean / "04_ir_state_dumps",
                       "clean", budget=0)  # fmt: skip
    jobs = java / "ai_agent_jobs"
    program = (jobs / "sources" / "cbl" / "NORDPGM.cbl.lst").read_text(encoding="utf-8")
    assert "    3 |        PROGRAM-ID. NORDPGM." in program and "'ÅRHUS'" in program
    assert "    1 |        01  WS-SALDO" in (jobs / "sources" / "cpy" / "NORDCPY.cpy.lst").read_text(encoding="utf-8")
    ticket = json.loads((jobs / "NORDPGM_port_ticket.json").read_text(encoding="utf-8"))
    assert [(o["option"], o["value"]) for o in ticket["compiler_options"]] == [("INTDATE", "LILIAN")]


# ---- end to end: the scan records the page, the refractor reads it back ---------------------------
def test_the_refractor_scan_declares_the_page_and_reads_the_program_in_it(estate, monkeypatch):
    """`cobol-refractor --scan --source-encoding cp277`: the scan decodes the estate in the page and
    records it per file; the refractor re-reads each program in the page the scan used."""
    from gitgalaxy import cobol_refractor_controller as refractor
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

    monkeypatch.setenv("GITGALAXY_DISABLE_GIT_HISTORY", "1")
    monkeypatch.setattr("sys.argv", ["cobol-refractor", str(estate), "--scan", "--source-encoding", PAGE])
    refractor.main()
    (clean,) = estate.parent.glob("estate_gitgalaxy_clean_*")
    (db,) = (clean / "04_ir_state_dumps").glob("*.db")
    ir = load_galaxy_ir(db)
    assert ir.source_page("cbl/NORDPGM.cbl") == PAGE and ir.source_page("cpy/NORDCPY.cpy") == PAGE
    dump = json.loads((clean / "04_ir_state_dumps" / "NORDPGM_ir.json").read_text(encoding="utf-8"))
    assert dump["metadata"]["loc"] == len(PROGRAM.splitlines())
    assert dump["metadata"]["source_encoding"] == PAGE
    assert dump["analysis"]["dead_code"]["dead_paras"] == ["DOED-AFSNIT"]


def test_source_encoding_without_scan_is_refused(estate, monkeypatch, tmp_path):
    from gitgalaxy import cobol_refractor_controller as refractor

    argv = ["cobol-refractor", str(estate), "--galaxy-db", str(tmp_path / "x.db"), "--source-encoding", PAGE]
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit):
        refractor.main()
