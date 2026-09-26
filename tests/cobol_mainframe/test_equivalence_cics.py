"""#3754: the CICS half of the equivalence harness, without a container.

The translator is pinned per command (what each EXEC CICS becomes, and that an unknown one
is refused by name, never skipped), the stub's file table is derived from a real scan of a
small estate -- CSD DEFINE FILE -> DSNAME -> IDCAMS KEYS, a PATH through its AIX -- and the
pieces the comparison stands on are pinned: field encoding round-trips, a DTO's shape read
from its comments, and events compared field by field.
"""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence as eq  # noqa: E402
import equivalence_cics as ec  # noqa: E402

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db  # noqa: E402


def test_a_read_becomes_a_stub_call_and_its_resp_is_the_programs():
    got = ec.translate_command(" READ DATASET (LIT-ACCTFILENAME) RIDFLD (WS-KEY) KEYLENGTH (LENGTH OF WS-KEY)"
                               " INTO (ACCOUNT-RECORD) RESP (WS-RESP-CD) RESP2 (WS-REAS-CD) ")  # fmt: skip
    assert got[:2] == ["MOVE LIT-ACCTFILENAME TO GG-NAME1", "CALL 'GGCREAD' USING GG-CICS"]
    assert "    BY VALUE LENGTH OF WS-KEY" in got and "    BY REFERENCE ACCOUNT-RECORD" in got
    assert got[-2:] == ["MOVE GG-RESP TO WS-RESP-CD", "MOVE GG-RESP2 TO WS-REAS-CD"]


def test_an_untested_condition_abends_as_cics_does():
    got = ec.translate_command("RECEIVE MAP('MAP1') MAPSET('SET1') INTO(MAP1I)")
    assert got[-4:] == ["IF GG-RESP NOT = 0", "    CALL 'GGCUNHD' USING GG-CICS", "    GOBACK", "END-IF"]


def test_return_xctl_and_abend_end_the_task():
    ret = ec.translate_command("RETURN TRANSID (LIT-TRAN) COMMAREA (WS-CA) LENGTH(LENGTH OF WS-CA)")
    assert ret[0] == "MOVE LIT-TRAN TO GG-NAME1" and ret[-1] == "GOBACK" and "    BY VALUE LENGTH OF WS-CA" in ret
    assert ec.translate_command("RETURN")[-3:] == ["    BY REFERENCE GG-FLAGS", "    BY VALUE 0", "GOBACK"]
    assert ec.translate_command("XCTL PROGRAM (WS-PGM) COMMAREA(CA)")[-1] == "GOBACK"
    assert ec.translate_command("ABEND ABCODE('9999')")[0] == "MOVE '9999' TO GG-NAME1"


def test_send_map_records_its_options_and_area():
    got = ec.translate_command("SEND MAP(M) MAPSET(S) FROM(MO) CURSOR ERASE FREEKB")
    assert "MOVE 'CURSOR ERASE FREEKB' TO GG-FLAGS" in got and "    BY REFERENCE MO" in got


@pytest.mark.parametrize("body", ["READ FILE(F) RIDFLD(K) INTO(R) GENERIC", "STARTBR FILE(F) RIDFLD(K)",
                                  "SYNCPOINT", "LINK PROGRAM('X')"])  # fmt: skip
def test_an_unmodelled_command_is_refused_by_name(body):
    with pytest.raises(ec.Unsupported):
        ec.translate_command(body)


PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTINQ.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RESP                PIC S9(8) COMP.
       01  ACCT-REC               PIC X(20).
       01  WS-KEY                 PIC X(5).
       LINKAGE SECTION.
       01  DFHCOMMAREA            PIC X(10).
       PROCEDURE DIVISION.
       MAIN-PARA.
           MOVE DFHCOMMAREA(1:5) TO WS-KEY
           EXEC CICS READ FILE('ACCT') RIDFLD(WS-KEY)
                INTO(ACCT-REC) RESP(WS-RESP)
           END-EXEC.
           IF WS-RESP = DFHRESP(NOTFND)
              MOVE SPACES TO ACCT-REC
           END-IF
           EXEC CICS RETURN END-EXEC.
"""


def test_a_program_is_translated_whole():
    text, has_commarea = ec.translate(PROGRAM)
    assert has_commarea
    assert "       COPY DFHEIBLK." in text and "PROCEDURE DIVISION USING DFHCOMMAREA." in text
    assert "IF WS-RESP = 13" in text and "EXEC CICS" not in text
    assert all(len(line) <= 72 for line in text.splitlines())


def test_an_unknown_command_in_a_program_names_its_line():
    with pytest.raises(ec.Unsupported, match="line 13: EXEC CICS SYNCPOINT"):
        ec.translate(PROGRAM.replace("READ FILE('ACCT') RIDFLD(WS-KEY)", "SYNCPOINT"))


CSD = """\
 DEFINE FILE(ACCT) GROUP(APP) DSNAME(APP.ACCT.KSDS)
 DEFINE FILE(ACCTAIX) GROUP(APP) DSNAME(APP.ACCT.PATH)
"""
# IDCAMS reads columns 2-72: a longer statement continues with "-", as real decks do.
IDCAMS = """\
//DEFINE   JOB (ACCT),'DEFINE'
//STEP1    EXEC PGM=IDCAMS
//SYSIN    DD *
  DEFINE CLUSTER (NAME(APP.ACCT.KSDS) INDEXED -
         KEYS(5 0) RECORDSIZE(20 20))
  DEFINE ALTERNATEINDEX (NAME(APP.ACCT.AIX) -
         RELATE(APP.ACCT.KSDS) KEYS(4 5) NONUNIQUEKEY)
  DEFINE PATH (NAME(APP.ACCT.PATH) PATHENTRY(APP.ACCT.AIX))
/*
"""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("cics_harness")
    repo = base / "estate"
    program = PROGRAM.replace("RETURN END-EXEC.", "READ FILE('ACCTAIX') RIDFLD(WS-KEY) INTO(ACCT-REC)\n"
                                                  "                RESP(WS-RESP) END-EXEC.\n"
                                                  "           EXEC CICS RETURN END-EXEC.")  # fmt: skip
    for rel, text in {"cbl/ACCTINQ.cbl": program, "csd/APP.csd": CSD, "jcl/DEFINE.jcl": IDCAMS}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return load_galaxy_ir(scan_to_db(repo, base / "scan"))


def test_the_stub_file_table_comes_from_the_engines_facts(scanned):
    files = {f["file"]: f for f in ec.stub_files(scanned, "cbl/ACCTINQ.cbl")}
    assert files["ACCT"] == {"file": "ACCT", "dsname": "APP.ACCT.KSDS", "base": "APP.ACCT.KSDS", "key_offset": 0,
                             "key_length": 5, "reclen": 20, "via": []}  # fmt: skip
    aix = files["ACCTAIX"]
    assert (aix["base"], aix["key_offset"], aix["key_length"]) == ("APP.ACCT.KSDS", 5, 4)
    assert aix["via"] == ["PATH APP.ACCT.PATH", "AIX APP.ACCT.AIX"]


def test_fields_round_trip_through_their_storage():
    for value, pic, usage, n in [("12.34", "S9(5)V99", None, 7), ("-5", "S9(3)", "COMP-3", 2),
                                 ("300", "S9(4)", "COMP", 2), ("AB", "X(4)", None, 4), ("7", "9(1)", None, 1)]:  # fmt: skip
        raw = ec.encode_field(value, pic, usage, n)
        assert len(raw) == n
        back = eq.decode_field(raw, pic, usage)
        assert (back.rstrip() == value) if isinstance(back, str) else back == Decimal(value)


def test_map_input_sets_the_typed_field_and_its_length():
    fields = [{"name": "ACCTL", "offset": 0, "bytes": 2, "pic": "S9(4)", "usage": "COMP"},
              {"name": "ACCTF", "offset": 2, "bytes": 1, "pic": "X", "usage": None},
              {"name": "ACCTI", "offset": 3, "bytes": 5, "pic": "99999", "usage": None}]  # fmt: skip
    assert ec.map_input(fields, {"ACCTI": "ABC"}) == b"\x00\x03\x00ABC  "


def test_a_dtos_shape_is_read_from_its_comments(tmp_path):
    (tmp_path / "Part.java").write_text("public class Part {\n    // CA-ID: PIC 9(4), offset 0, 4 bytes (x.cpy)\n"
                                        "    private Integer caId;\n}\n")  # fmt: skip
    (tmp_path / "Whole.java").write_text("public class Whole {\n    // DFHCOMMAREA(1:4) at line 9: offset 0, 4 bytes"
                                         " -> CA-PART (x.cpy)\n    private Part caPart;\n}\n")  # fmt: skip
    shape = ec.dto_shape(tmp_path, "Whole")
    assert shape == {"caPart": ("Part", {"caId": "CA-ID"})}
    assert ec.to_java({"CA-ID": "12"}, shape) == {"caPart": {"caId": 12}}
    assert ec.from_java({"caPart": {"caId": 12}}, shape) == {"CA-ID": 12}


def test_events_are_compared_field_by_field():
    cobol = [{"event": "SEND-MAP", "map": "M", "screen": {"NAME": "Ann", "BAL": "+   1.00"}},
             {"event": "RETURN", "transid": "T1", "commarea": {"CA-CTX": "1"}}]  # fmt: skip
    java = [{"event": "SEND-MAP", "map": "M", "screen": {"NAME": "Ann  ", "BAL": "+1.00"}},
            {"event": "RETURN", "transid": "T1", "commarea": {"CA-CTX": 1}}]  # fmt: skip
    d = ec.compare_events(cobol, java)
    assert (d["equal"], d["events"]) == (1, 2)
    assert d["diffs"] == [{"event": 1, "kind": "SEND-MAP",
                           "fields": [{"field": "screen.BAL", "cobol": "+   1.00", "java": "+1.00"}]}]  # fmt: skip
    assert ec.compare_events(cobol, java[:1])["diffs"][-1] == {"event": 2, "cobol": "RETURN", "java": None}


@pytest.mark.skipif(__import__("os").environ.get("EQUIVALENCE_E2E") != "1",
                    reason="needs Docker (GnuCOBOL) and a JDK + Maven")  # fmt: skip
def test_carddemo_account_view_is_equivalent_end_to_end(tmp_path):
    """COACTVWC as COBOL under the stub runtime and as the generated Java plus the case's port: every
    scenario's every event (screen, COMMAREA, XCTL) equal, field by field."""
    import json
    import subprocess

    proc = subprocess.run([sys.executable, str(Path(eq.__file__)), "run", "carddemo-acctview", "--keep",  # noqa: S603
                           str(tmp_path)], capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    report = json.loads((tmp_path / "report.json").read_text())
    assert {n: (o["equal"], o["records"]) for n, o in report["outputs"].items()} == {
        "enter-from-menu": (2, 2), "view-account": (2, 2), "account-not-on-file": (2, 2),
        "account-not-numeric": (2, 2), "pf3-back-to-menu": (1, 1)}  # fmt: skip
