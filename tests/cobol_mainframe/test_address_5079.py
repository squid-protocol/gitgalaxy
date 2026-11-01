"""#5079 (oracle_assumptions.md X59): EXEC CICS ADDRESS EIB / COMMAREA, and the old-style sweep refused by name.

IBM, EXEC CICS ADDRESS: EIB "returns a pointer reference set to the address of the EXEC interface block (EIB)"; COMMAREA
"returns a pointer reference, set to the address of the communication area (COMMAREA) available to the currently executing
program"; with no COMMAREA the pointer is X'FF000000' (no COBOL NULL, so refused). The pieces, each over the whole class:
- the det translator, over a whole program: ADDRESS EIB / COMMAREA translate with no hole; CWA, TWA, TCTUA, ACEE, the old
  ADDRESS SET form, a program with no DFHCOMMAREA and a pointer that is no plain USAGE POINTER are holes by name; so are
  SEND PAGE and PURGE MESSAGE (each with its reason and the register entry; CONVERSE,
  POST, WAIT EVENT, WAIT EXTERNAL and WAITCICS are modelled by X63, test_post_wait_converse_5079.py);
- the equivalence harness's translator (equivalence_cics): the same members onto the stub's GGCADDR, and the same refusals;
- both runtimes (the stub's GGCADDR, compiled; DetCics.addressCommarea, compiled): the pointer is the area's own address,
  and a task with no COMMAREA is refused by name.
(The two runtimes answering one program alike is tests/cobol_mainframe/test_address_e2e_5079.py.)
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "tests" / "tools"))
sys.path.insert(0, str(HERE.parents[1] / "tests" / "cics_crucible"))
import cics_crucible as CCR  # noqa: E402
import test_cics_runtimes as R  # noqa: E402  (bare imports: tests/ has no __init__.py, see CLAUDE.md)
import test_pointer_lane_4771 as PL  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PTRLN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  EIB-ADDRESS            USAGE POINTER.
       01  CA-ADDRESS             USAGE POINTER.
       01  WS-RESP                PIC S9(08) COMP VALUE 0.
       LINKAGE SECTION.
       01  DFHCOMMAREA            PIC  X(32).
       01  EIB-VIEW               PIC  X(100).
       PROCEDURE DIVISION.
           EXEC CICS ADDRESS EIB(EIB-ADDRESS) COMMAREA(CA-ADDRESS)
                RESP(WS-RESP)
           END-EXEC.
           SET ADDRESS OF EIB-VIEW TO EIB-ADDRESS.
           EXEC CICS RETURN END-EXEC.
"""


def test_a_program_addressing_the_eib_and_the_commarea_translates_whole(tmp_path):
    r = PL._translate(tmp_path, PROGRAM)
    assert r.stats["holes"] == [], r.stats["holes"]
    assert "DetCics.setPointerToRecord(task, " in r.java
    assert "DetCics.addressCommarea(task, " in r.java
    assert "Cobol.store(f3_WS_RESP, BigDecimal.valueOf(0), false, CS);" in r.java  # (RESP written: NORMAL)
    assert r.java.index("setPointerToRecord(task, ") < r.java.index(
        "addressCommarea(task, "
    )  # (the order IBM's options are taken)


def test_a_program_with_no_dfhcommarea_addresses_the_no_commarea_pointer(tmp_path):
    """#6876 (X59): no 01 DFHCOMMAREA is no hole (CAADDR / CAADSB / CAEBCA / CAEBSB name none): the pointer is set through
    DetCics.addressNoCommarea, with EIBCALEN, and a program that names one still addresses the record."""
    r = PL._translate(tmp_path, PROGRAM.replace("       01  DFHCOMMAREA            PIC  X(32).\n", ""))
    assert r.stats["holes"] == [], r.stats["holes"]
    assert "DetCics.addressNoCommarea(task, " in r.java
    assert "DetCics.addressCommarea(task, " not in r.java
    named = PL._translate(tmp_path, PROGRAM)
    assert "DetCics.addressCommarea(task, " in named.java
    assert "addressNoCommarea" not in named.java


@pytest.mark.parametrize(
    ("options", "calls"),
    [
        ("TWA(CA-ADDRESS)", ["addressTwa"]),
        ("TCTUA(CA-ADDRESS)", ["addressTctua"]),
        ("TWA(EIB-ADDRESS) TCTUA(CA-ADDRESS)", ["addressTwa", "addressTctua"]),
        (
            "EIB(EIB-ADDRESS) COMMAREA(CA-ADDRESS)\n           TWA(EIB-ADDRESS) TCTUA(CA-ADDRESS)",
            ["setPointerToRecord", "addressCommarea", "addressTwa", "addressTctua"],
        ),
    ],
)
def test_twa_and_tctua_translate_to_the_runtime_handles_in_option_order(tmp_path, options, calls):
    """#5079 slice 2 (X59): TWA / TCTUA are modelled, alone or beside EIB / COMMAREA; the areas are taken in IBM's order."""
    r = PL._translate(tmp_path, PROGRAM.replace("EIB(EIB-ADDRESS) COMMAREA(CA-ADDRESS)", options))
    assert r.stats["holes"] == [], r.stats["holes"]
    at = [r.java.index(f"{c}(task, ") for c in calls]
    assert at == sorted(at)
    assert "DetCics.addressTwa(task, " in r.java or "DetCics.addressTctua(task, " in r.java


@pytest.mark.parametrize(
    ("options", "calls"),
    [
        ("CWA(CA-ADDRESS)", ["addressCwa"]),
        ("CWA(EIB-ADDRESS) TWA(CA-ADDRESS)", ["addressCwa", "addressTwa"]),
        (
            "TCTUA(EIB-ADDRESS) CWA(CA-ADDRESS)\n           TWA(EIB-ADDRESS)",
            ["addressCwa", "addressTwa", "addressTctua"],
        ),
        (
            "EIB(EIB-ADDRESS) COMMAREA(CA-ADDRESS)\n           CWA(EIB-ADDRESS) TWA(EIB-ADDRESS) TCTUA(CA-ADDRESS)",
            ["setPointerToRecord", "addressCommarea", "addressCwa", "addressTwa", "addressTctua"],
        ),
    ],
)
def test_cwa_translates_to_the_region_wide_handle_in_option_order(tmp_path, options, calls):
    """#5079 slice 2a (X59): CWA is modelled, alone or beside the other areas, taken in the fixed order."""
    r = PL._translate(tmp_path, PROGRAM.replace("EIB(EIB-ADDRESS) COMMAREA(CA-ADDRESS)", options))
    assert r.stats["holes"] == [], r.stats["holes"]
    at = [r.java.index(f"{c}(task, ") for c in calls]
    assert at == sorted(at)


@pytest.mark.parametrize(
    ("edit", "why"),
    [
        (("EIB(EIB-ADDRESS) COMMAREA(CA-ADDRESS)", "ACEE(CA-ADDRESS)"), "ACEE: the access control environment element"),
        (("EIB(EIB-ADDRESS) COMMAREA(CA-ADDRESS)", "CWA(WS-RESP)"), "not a plain USAGE POINTER"),
        (("EIB(EIB-ADDRESS) COMMAREA(CA-ADDRESS)", "TWA(CA-ADDRESS) ACEE(CA-ADDRESS)"), "ACEE: the access control"),
        (("EIB(EIB-ADDRESS) COMMAREA(CA-ADDRESS)", "SET(CA-ADDRESS)"), "SET: ADDRESS SET"),
        (("EIB(EIB-ADDRESS) COMMAREA(CA-ADDRESS)", "NOHANDLE"), "ADDRESS without an area option"),
        (("EIB(EIB-ADDRESS) COMMAREA(CA-ADDRESS)", "EIB(WS-RESP)"), "not a plain USAGE POINTER"),
        (("EIB(EIB-ADDRESS) COMMAREA(CA-ADDRESS)", "COMMAREA(CA-MISSING)"), "CA-MISSING"),
        (
            (
                "       01  EIB-VIEW               PIC  X(100).\n",
                "       01  EIB-VIEW.\n           05  EV-A  PIC X(100).\n",
            ),
            None,
        ),
    ],
)
def test_what_the_command_cannot_model_is_refused_by_name(tmp_path, edit, why):
    old, new = edit
    assert old in PROGRAM
    r = PL._translate(tmp_path, PROGRAM.replace(old, new))
    if why is None:  # (a group record is still a whole LINKAGE 01 record: nothing to refuse)
        assert r.stats["holes"] == [], r.stats["holes"]
        return
    assert any(why in h for h in r.stats["holes"]), (why, r.stats["holes"])


def test_every_option_on_ibms_address_page_is_modelled_or_refused_by_name():
    """IBM's ADDRESS page (CICS TS 6.x) lists exactly ACEE, COMMAREA, CWA, EIB, TCTUA, TWA; SET is the old form."""
    from gitgalaxy.standards.cics.commands.storage import ADDRESS

    ibm_options = {"ACEE", "COMMAREA", "CWA", "EIB", "TCTUA", "TWA"}
    modelled = {k for k in ADDRESS.options if k in ibm_options}
    assert modelled | set(ADDRESS.refused) >= ibm_options
    assert ibm_options - modelled == {"ACEE"}
    for key in ("ACEE", "SET"):
        assert ADDRESS.refused[key].register == "X59"
    assert "DFLTUSER" in ADDRESS.refused["ACEE"].why
    assert "current ADDRESS page" in ADDRESS.refused["SET"].why


@pytest.mark.parametrize(
    ("command", "why"),
    [
        ("SEND PAGE", "a BMS logical message (ACCUM / PAGING, completed by SEND PAGE) is not modelled"),
        ("SEND PAGE RELEASE", "a BMS logical message"),
        ("PURGE MESSAGE", "a BMS logical message"),
        (
            "WAIT TERMINAL",
            "terminal control beyond the one 3270 display",
        ),  # (WAIT as a verb, not RETRIEVE's bare option)
    ],
)
def test_the_old_style_sweep_is_refused_whole_by_name(tmp_path, command, why):
    r = PL._translate(
        tmp_path,
        PROGRAM.replace(
            "EXEC CICS RETURN END-EXEC.",
            f"EXEC CICS {command}\n           END-EXEC.\n           EXEC CICS RETURN END-EXEC.",
        ),
    )
    assert any(why in h for h in r.stats["holes"]), (why, r.stats["holes"])


def test_each_sweep_member_is_a_register_entry_that_cites_its_ibm_page():
    from gitgalaxy.standards.cics.commands import COMMANDS

    register = (HERE.parents[1] / "docs/language_status/register/X59.md").read_text(encoding="utf-8")
    for key in ("SEND PAGE", "PURGE MESSAGE", "ADDRESS"):
        assert COMMANDS[key].register == "X59", key
        assert COMMANDS[key].ibm.url in register, key
    assert COMMANDS["ADDRESS"].status == "modelled" and COMMANDS["ADDRESS SET"].status == "refused"


# ---- the equivalence harness's translator ------------------------------------------------------------------------------------
def _ec():
    import equivalence_cics as ec

    return ec


@pytest.mark.parametrize(
    ("options", "areas"),
    [
        ("CWA(P)", ["CWA"]),
        ("TWA(P)", ["TWA"]),
        ("TCTUA(P)", ["TCTUA"]),
        ("TWA(P) TCTUA(Q)", ["TWA", "TCTUA"]),
        ("TCTUA(Q) TWA(P) CWA(R)", ["CWA", "TWA", "TCTUA"]),
        ("EIB(E) COMMAREA(C) CWA(R) TWA(P) TCTUA(Q)", ["CWA", "TWA", "TCTUA"]),
    ],
)
def test_the_harness_names_the_system_area_to_the_stub_in_option_order(options, areas):
    """#5079 slice 2b (X59): CWA / TWA / TCTUA reach GGCADDR as a GG-FLAGS name, after EIB and COMMAREA, one call each."""
    out = _ec().translate_command(f"ADDRESS {options} NOHANDLE")
    names = [
        ln.split("'")[1]
        for ln in out
        if ln.startswith("MOVE '") and "TO GG-FLAGS" in ln and ln.split("'")[1] in ("CWA", "TWA", "TCTUA")
    ]
    assert names == areas
    assert sum(ln.strip() == "CALL 'GGCADDR' USING GG-CICS" for ln in out) >= len(areas)


def test_the_harness_calls_the_stubs_entry_point_for_the_eib_and_the_commarea():
    out = _ec().translate_command("ADDRESS EIB(P) RESP(R)")
    assert out[:3] == ["MOVE SPACES TO GG-FLAGS", "CALL 'GGCADDR' USING GG-CICS", "    BY REFERENCE P"]
    assert "    BY REFERENCE DFHEIBLK" in out and "MOVE GG-RESP TO R" in out
    out = _ec().translate_command("ADDRESS COMMAREA(Q) NOHANDLE")
    assert out[:3] == ["MOVE EIBCALEN TO GG-NUM", "MOVE 'COMMAREA' TO GG-FLAGS", "IF EIBCALEN = 0"]
    assert "        BY REFERENCE DFHCOMMAREA" in out and out.count("    CALL 'GGCADDR' USING GG-CICS") == 2
    both = _ec().translate_command("ADDRESS EIB(P) COMMAREA(Q) RESP(R)")
    assert both.index("    BY REFERENCE DFHEIBLK") < both.index("IF EIBCALEN = 0")


@pytest.mark.parametrize(
    "text",
    [
        "ADDRESS ACEE(P)",
        "ADDRESS SET(P)",
        "ADDRESS NOHANDLE",
        "ADDRESS EIB(A(1))",
        "ADDRESS COMMAREA(A OF B)",
        "SEND PAGE",
        "PURGE MESSAGE",
    ],
)
def test_the_harness_refuses_what_the_translator_refuses(text):
    with pytest.raises(_ec().Unsupported):
        _ec().translate_command(text)


_NO_RECORD = PROGRAM.replace("       01  DFHCOMMAREA            PIC  X(32).\n", "")


def test_the_harness_gives_a_program_with_no_commarea_record_a_stand_in_to_address():
    """#5079 (X59): CAADSB-style callee: ADDRESS COMMAREA with no 01 DFHCOMMAREA. LINKAGE with other records, no LINKAGE
    section at all, and a record already there (no duplicate) are the whole input class."""
    ec = _ec()
    text, has_commarea = ec.translate(_NO_RECORD)  # LINKAGE SECTION holding other records
    assert has_commarea and len(re.findall(r"01\s+DFHCOMMAREA", text)) == 1
    assert (
        text.index("LINKAGE SECTION")
        < text.index("DFHCOMMAREA PIC X(1)")
        < text.index("PROCEDURE DIVISION USING DFHCOMMAREA")
    )
    bare = re.sub(r"       LINKAGE SECTION\.\n(       01  EIB-VIEW[^\n]*\n)", "", _NO_RECORD)
    assert "LINKAGE SECTION" not in bare
    text, has_commarea = ec.translate(bare)  # no LINKAGE SECTION: one is made before the PROCEDURE DIVISION
    assert has_commarea and text.index("LINKAGE SECTION") < text.index("DFHCOMMAREA PIC X(1)") < text.index(
        "PROCEDURE DIVISION USING"
    )
    text, has_commarea = ec.translate(PROGRAM)  # declared: untouched
    assert has_commarea and "PIC X(1)" not in text


def test_a_program_that_addresses_only_the_eib_gets_no_stand_in():
    ec = _ec()
    source = _NO_RECORD.replace(" COMMAREA(CA-ADDRESS)", "")
    text, has_commarea = ec.translate(source)
    assert not has_commarea and "DFHCOMMAREA" not in text


def _case_with(*events):
    class _C:
        expected = {"s": {"tasks": [{"events": list(events)}]}}

    return _C()


def test_the_runner_writes_an_empty_td_config_only_for_a_case_that_expects_qiderr():
    """#5079 (X57): READQ TD / WRITEQ TD / DELETEQ TD answered QIDERR by the oracle, with no TDQUEUE in the CSD."""
    for verb in ("READQ-TD", "WRITEQ-TD", "DELETEQ-TD"):
        assert CCR._expects_undefined_td_queue(_case_with({"event": verb, "resp": "QIDERR"}))
        assert not CCR._expects_undefined_td_queue(_case_with({"event": verb, "resp": "NORMAL"}))
    assert not CCR._expects_undefined_td_queue(_case_with({"event": "READQ-TS", "resp": "QIDERR"}))


# ---- both runtimes -------------------------------------------------------------------------------------------------------------
_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; char as[16], tochan[16]; } gg_cics;
int GGCADDR(gg_cics *c, void **slot, void *area);
static gg_cics c;
int main(int argc, char **argv) {
    static char eib[8], ca[4];
    void *p = NULL, *q = NULL;
    memset(&c, 0, sizeof c);
    memset(c.flags, ' ', 40);
    GGCADDR(&c, &p, eib);
    printf("eib %d/%d %d\n", c.resp, c.resp2, p == (void *)eib);
    memcpy(c.flags, "COMMAREA", 8);
    c.num = 4;
    GGCADDR(&c, &q, ca);
    printf("commarea %d/%d %d\n", c.resp, c.resp2, q == (void *)ca);
    c.num = 0;
    GGCADDR(&c, &q, ca);
    printf("not reached\n");
    return 0;
}
"""


_CWA_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; char as[16], tochan[16]; } gg_cics;
int GGCADDR(gg_cics *c, void **slot, void *area);
static gg_cics c;
int main(int argc, char **argv) {
    void *p = NULL, *q = NULL;
    unsigned char *b;
    memset(&c, 0, sizeof c);
    memset(c.flags, ' ', 40);
    memcpy(c.flags, "CWA", 3);
    GGCADDR(&c, &p, NULL);
    GGCADDR(&c, &q, NULL);
    printf("%d/%d same %d\n", c.resp, c.resp2, p == q);
    if ((size_t)p == 0xFF) { printf("null\n"); return 0; }
    b = (unsigned char *)p;
    printf("first %d size-ok %d\n", b[0], b[7]);
    if (argc > 1) { b[0] = (unsigned char)atoi(argv[1]); b[7] = 9; }
    return 0;
}
"""


@R.needs_cc
def test_the_stub_gives_the_cwa_its_wrkarea_bytes_for_the_region_and_null_when_unstated(tmp_path):
    """#5079 slice 2b (X59): GGCADDR CWA is a zeroed block of $GGCICS_WRKAREA bytes, the same one on every ADDRESS, kept in
    $GGCICS_CWA so the next task of the region sees what the last wrote; no stated size (unset, 0) is IBM's X'FF000000'."""
    exe = R._stub(tmp_path, "#include <stdlib.h>\n" + _CWA_MAIN)
    work = tmp_path / "w"
    out = work / "out"
    out.mkdir(parents=True)
    base = {**R._stub_base_env(), "GGCICS_DIR": str(work), "GGCICS_OUT": str(out)}
    keep = tmp_path / "region.cwa"

    def run(extra, *argv):
        r = subprocess.run([str(exe), *argv], env={**base, **extra}, capture_output=True, text=True, check=False)  # noqa: S603
        assert r.returncode == 0, (r.stdout, r.stderr)
        return r.stdout.splitlines()

    assert run({}) == ["0/0 same 1", "null"]
    assert run({"GGCICS_WRKAREA": "0", "GGCICS_CWA": str(keep)}) == ["0/0 same 1", "null"]
    assert run({"GGCICS_WRKAREA": "8"}) == ["0/0 same 1", "null"]  # no file to keep it in: no region area
    stated = {"GGCICS_WRKAREA": "8", "GGCICS_CWA": str(keep)}
    assert run(stated, "5") == ["0/0 same 1", "first 0 size-ok 0"]
    assert keep.read_bytes() == bytes([5, 0, 0, 0, 0, 0, 0, 9])
    assert run(stated) == ["0/0 same 1", "first 5 size-ok 9"]


@R.needs_cc
def test_the_stub_sets_the_pointer_to_the_area_and_refuses_a_missing_commarea(tmp_path):
    exe = R._stub(tmp_path, _MAIN)
    work = tmp_path / "w"
    out = work / "out"
    out.mkdir(parents=True)
    env = {**R._stub_base_env(), "GGCICS_DIR": str(work), "GGCICS_OUT": str(out)}
    run = subprocess.run([str(exe)], env=env, capture_output=True, text=True, check=False)  # noqa: S603
    assert run.returncode == 98, (run.stdout, run.stderr)
    assert run.stdout.splitlines() == [
        "eib 0/0 1",
        "commarea 0/0 1",
        "ADDRESS COMMAREA with no COMMAREA: not modelled",
    ]


def _javac() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


@pytest.mark.skipif(_javac() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_port_addresses_the_record_itself_and_refuses_a_missing_commarea(tmp_path):
    """DetCics.setPointerToRecord (EIB) and addressCommarea over a real CicsTask: a record set to the pointer shares the bytes
    of the record addressed, and EIBCALEN 0 is refused by name."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "src"
    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    files["Main.java"] = """
import t.cics.CicsTask;
import t.cobolrt.Field;
import t.cobolrt.Storage;
import t.cobolrt.cics.DetCics;
public class Main {
    static Field rec(int n) { return Field.alphanumeric(new Storage(n), 0, n, false); }
    public static void main(String[] a) {
        CicsTask t = new CicsTask("ZC01", "ENTER", null, null);
        Field ptr = rec(8), view = rec(4), ca = rec(4), calen = rec(4);
        ca.storage().bytes[0] = 'A';
        DetCics.addressCommarea(t, ptr, ca, 4);
        DetCics.setAddress(t, view, ptr);
        view.storage().bytes[1] = 'B';
        System.out.println((char) ca.storage().bytes[0] + "" + (char) ca.storage().bytes[1] + " " + (view.storage().bytes == ca.storage().bytes));
        DetCics.setPointerToRecord(t, ptr, calen);
        System.out.println(DetCics.pointerValue(ptr) != 0);
        Field none = rec(8);
        DetCics.addressNoCommarea(t, none, 0);
        System.out.println(DetCics.isNoCommareaAddress(none) + " " + DetCics.isNoCommareaAddress(ptr));
        try {
            DetCics.setAddress(t, view, none);
            System.out.println("not refused");
        } catch (UnsupportedOperationException e) {
            System.out.println(e.getMessage());
        }
        try {
            DetCics.addressNoCommarea(t, none, 4);
            System.out.println("not refused");
        } catch (UnsupportedOperationException e) {
            System.out.println(e.getMessage());
        }
        try {
            DetCics.addressCommarea(t, ptr, ca, 0);
            System.out.println("not refused");
        } catch (UnsupportedOperationException e) {
            System.out.println(e.getMessage());
        }
    }
}
"""
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    jdk = _javac()
    assert jdk is not None
    built = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                            *map(str, src.rglob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"], capture_output=True,  # noqa: S603
                         text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    assert out == [
        "AB true",
        "true",
        "true false",
        "SET ADDRESS OF a null or unknown pointer: not modelled",
        "ADDRESS COMMAREA with a COMMAREA in a program with no 01 DFHCOMMAREA: its bytes are not modelled",
        "ADDRESS COMMAREA with no COMMAREA: not modelled",
    ]


def _case(data, twasize=None):
    from types import SimpleNamespace

    return SimpleNamespace(csd={"twasize": twasize or {}, "userarealen": {}}, data={"terminal": "T001", **data})


@pytest.mark.parametrize(
    ("data", "twasize", "wanted", "absent"),
    [
        ({"wrkarea": 32}, None, ["GGCICS_WRKAREA=32 ", "GGCICS_CWA=/work/s1.cwa"], ["GGCICS_TWASIZE"]),
        ({"wrkarea": 8}, {"CA0K": 16}, ["GGCICS_WRKAREA=8 ", "GGCICS_TWASIZE=16"], []),
        ({}, None, [], ["GGCICS_WRKAREA", "GGCICS_CWA"]),  # none stated: the stub's own default (X'FF000000')
        ({"wrkarea": 0}, None, [], ["GGCICS_WRKAREA", "GGCICS_CWA"]),
    ],
)
def test_the_runner_hands_the_stub_a_wrkarea_only_when_the_case_states_one(data, twasize, wanted, absent):
    """#5079 slice 2b (X59): case.json `wrkarea` (the SIT WRKAREA) becomes GGCICS_WRKAREA and the file that keeps the CWA."""
    env = CCR.area_env(_case(data, twasize), "CA0K", "s1")
    for w in wanted:
        assert w in env
    for a in absent:
        assert a not in env


def test_every_crucible_case_that_addresses_the_cwa_states_its_wrkarea():
    """#5079: the crucible's `ca-address-cwa` (cics-crucible#47) is the cobol-stub proof of the CWA. Any checkout case whose
    COBOL issues ADDRESS CWA states a positive wrkarea (the pinned ref that predates it has no such case: skipped)."""
    from gitgalaxy.core.source_text import read_source

    root = CCR.crucible_path(None) / "cases"
    if not root.is_dir():
        pytest.skip("no cics-crucible checkout")
    seen = []
    for case_json in sorted(root.glob("*/*/case.json")):
        case = CCR.cc.load_case(case_json.parent)
        text = " ".join(read_source(case.dir / rel).text for rel in case.data["sources"]["cobol"])
        if re.search(r"ADDRESS\s+CWA\b", text):
            seen.append(case.id)
            assert int(case.data.get("wrkarea") or 0) >= 1, case.id
    if not seen:
        pytest.skip("the pinned cics-crucible ref has no ADDRESS CWA case yet (cics-crucible#47)")
