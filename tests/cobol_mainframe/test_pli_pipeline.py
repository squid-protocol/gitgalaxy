"""#3623: PL/I programs through the COBOL -> Java pipeline.

A PL/I program has no PROGRAM-ID: it is a program when its external procedure is
OPTIONS(MAIN | FETCHABLE) (the raw_arch_api signal), named after its member. A real scan
of a small PL/I CICS estate pins: GalaxyIR recognising the programs (and not an %INCLUDE
member), the refractor writing an engine-built IR dump and a verified skeleton for each,
and the Java: a @Transactional service per program with its LINK, TS queue and SYNCPOINT
wired from the facts, in the traceability manifest. DSF (431 PL/I programs) compiles in
java_target_matrix.
"""

import json
import shutil
import sys
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

ACCTP = """\
 ACCTP: PROC(COMMAREA_PTR) OPTIONS(MAIN);
   DCL COMMAREA_PTR PTR;
   DCL 1 ACCT_REC,
         2 ACCT_ID  CHAR(8),
         2 ACCT_BAL FIXED DEC(9,2);
   %INCLUDE ACCTINC;
   EXEC CICS LINK PROGRAM('OTHERP') COMMAREA(ACCT_REC);
   EXEC CICS WRITEQ TS QUEUE('STATEQ') FROM(ACCT_REC);
   EXEC CICS SYNCPOINT;
   CALL HELPER(ACCT_REC);
   EXEC CICS RETURN;
 HELPER: PROC(R);
   DCL 1 R LIKE ACCT_REC;
 END HELPER;
 END ACCTP;
"""

OTHERP = """\
 OTHERP: PROC OPTIONS(MAIN);
   EXEC CICS RETURN;
 END OTHERP;
"""

ACCTINC = """\
   DCL WS_FLAG CHAR(1) INIT('N');
"""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("pli_pipeline")
    repo = base / "estate"
    for rel, text in {"src/ACCTP.pli": ACCTP, "src/OTHERP.pli": OTHERP, "inc/ACCTINC.pli": ACCTINC}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo, scan_to_db(repo, base / "scan")


def test_pli_programs_are_the_main_procedures_named_by_member(scanned):
    ir = load_galaxy_ir(scanned[1])
    assert [(f.file_path, f.program_ids) for f in ir.programs("pli")] == [
        ("src/ACCTP.pli", ["ACCTP"]),
        ("src/OTHERP.pli", ["OTHERP"]),
    ]
    assert not ir.files["inc/ACCTINC.pli"].is_program  # an %INCLUDE member, like a copybook


def test_the_pipeline_generates_the_pli_programs(scanned, tmp_path):
    repo, db = scanned
    work = tmp_path / "estate"
    shutil.copytree(repo, work)
    with patch.object(sys, "argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = tmp_path.glob("estate_gitgalaxy_clean_*")
    ir_dump = json.loads((clean / "04_ir_state_dumps/ACCTP_ir.json").read_text(encoding="utf-8"))
    assert ir_dump["metadata"]["language"] == "pli" and ir_dump["metadata"]["ir_source"] == "galaxy_db"
    assert ir_dump["analysis"]["base_intent"]["is_cics"] is True
    skeleton = json.loads((clean / "06_skeleton/ACCTP_skeleton.json").read_text(encoding="utf-8"))
    assert skeleton["program"]["language"] == "pli" and skeleton["program"]["program_ids"] == ["ACCTP"]
    verbs = {(f["kind"], f["verb"], f["name"]) for f in skeleton["sections"]["cics_resources"]["facts"]}
    assert ("QUEUE", "WRITEQ", "STATEQ") in verbs
    audit = next(clean.rglob("master_refraction_audit.txt")).read_text(encoding="utf-8")
    assert "2 programs: engine IR + skeleton (#3623)" in audit

    with patch.object(sys, "argv", ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]):
        java_controller.main()
    (java,) = tmp_path.glob("estate_gitgalaxy_java_spring_*")
    svc = (java / "src/main/java/com/gitgalaxy/modernized/service/AcctpService.java").read_text(encoding="utf-8")
    assert "@Transactional" in svc  # the SYNCPOINT's unit of work (#3621)
    assert 'tempStorage.writeItem("STATEQ", record)' in svc  # the TS queue (#3620)
    assert "OtherpService" in svc  # the LINK to OTHERP, wired to its service (#3616)
    assert (java / "src/main/java/com/gitgalaxy/modernized/service/OtherpService.java").is_file()
    manifest = json.loads((java / "traceability.json").read_text(encoding="utf-8"))
    assert any(f["source"].startswith("src/ACCTP.pli:") for a in manifest["artifacts"] for f in a["facts"])
