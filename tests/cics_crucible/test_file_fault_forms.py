"""#4623: the file faults the equivalence harness injects, one test per fault form.

IBM CICS TS lists each condition per command ("Conditions" of READ, READNEXT, READPREV, WRITE, REWRITE, DELETE ...).
The duplicate-key pair is where the harness used DUPREC for a condition IBM gives a READ: DUPKEY (RESP2 140, a record
retrieved through a NONUNIQUEKEY alternate index with another of the same key following) delivers the record, DUPREC
(RESP2 150) is a WRITE / REWRITE that does nothing. Pure parts first, then both runtimes (the C stub and the generated
CicsTask) against the same plan (register X48).
"""

import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec  # noqa: E402
import test_cics_runtimes as rt  # noqa: E402  (its compile / run helpers)

FILE_COMMANDS = ("READ", "READNEXT", "READPREV", "STARTBR", "ENDBR", "WRITE", "REWRITE", "DELETE")
# IBM, per command: the duplicate-key conditions it documents, with the RESP2
DOCUMENTED = {
    ("READ", "DUPKEY"): 140,
    ("READNEXT", "DUPKEY"): 140,
    ("READPREV", "DUPKEY"): 140,
    ("WRITE", "DUPREC"): 150,
    ("REWRITE", "DUPREC"): 150,
}


def _plan(cmd, resp, **extra):
    return {"name": "s", "faults": [{"cmd": cmd, "file": "XREF", "resp": resp, **extra}]}


def test_dupkey_is_an_injectable_condition_with_ibms_number():
    assert ec.CICS_RESP["DUPKEY"] == 15 and ec.CICS_RESP["DUPREC"] == 14


@pytest.mark.parametrize("resp", ("DUPKEY", "DUPREC"))
@pytest.mark.parametrize("cmd", FILE_COMMANDS)
def test_a_duplicate_key_fault_is_planned_only_where_ibm_documents_it(cmd, resp):
    if (cmd, resp) in DOCUMENTED:
        ibm = DOCUMENTED[(cmd, resp)]
        n = ec.CICS_RESP[resp]
        assert ec.fault_lines(_plan(cmd, resp)) == [f"{cmd} XREF 1 {n} {ibm}"]  # RESP2 defaults to IBM's
        assert ec.fault_lines(_plan(cmd, resp, resp2=ibm)) == [f"{cmd} XREF 1 {n} {ibm}"]
        assert ec.fault_lines(_plan(cmd, resp, nth="*")) == [f"{cmd} XREF * {n} {ibm}"]
        with pytest.raises(ec.Unsupported, match=f"RESP2 {ibm}"):
            ec.fault_lines(_plan(cmd, resp, resp2=ibm + 1))
    else:
        with pytest.raises(ec.Unsupported, match="IBM documents|register X48"):
            ec.fault_lines(_plan(cmd, resp))


def test_dupkey_on_delete_is_refused_by_name_and_other_commands_are_not_read_by_the_rule():
    with pytest.raises(ec.Unsupported, match="X48"):
        ec.fault_lines(_plan("DELETE", "DUPKEY"))
    for cmd in ("XCTL", "LINK", "WRITEQ-TS", "START", "RETRIEVE", "CANCEL", "WRITEQ-TD", "INQUIRE"):
        with pytest.raises(ec.Unsupported):
            ec.fault_lines({"name": "s", "faults": [{"cmd": cmd, "program": "P", "queue": "Q", "transid": "T",
                                                     "reqid": "R", "file": "F", "resp": "DUPKEY"}]})  # fmt: skip
    # the other file conditions have their own per-command table (#5044, test_file_fault_conditions.py): IBM's RESP2 80
    assert ec.fault_lines(_plan("READ", "NOTFND")) == ["READ XREF 1 13 80"]


@pytest.mark.parametrize("path", ("equivalence/carddemo-billpay/case.json", "equivalence/carddemo-tranadd/case.json"))
def test_the_carddemo_cases_plan_a_dupkey_on_their_alternate_index_read(path):
    import json

    case = json.loads((TESTS / path).read_text(encoding="utf-8"))
    sc = next(s for s in case["scenarios"] if s["name"] == "xref-aix-dupkey")
    assert ec.fault_lines(sc) == ["READ CXACAIX 1 15 140"]
    for other in case["scenarios"]:  # every planned fault in the case is one the harness accepts
        if other.get("faults"):
            ec.fault_lines(other)


# ---- the stub ---------------------------------------------------------------------------------------------
_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len; } gg_cics;
int GGCREAD(gg_cics *c, char *ridfld, int keylen, char *into, int intolen);
int GGCSTBR(gg_cics *c, char *ridfld, int keylen);
int GGCRDNX(gg_cics *c, char *ridfld, int keylen, char *into, int intolen);
int GGCRDPV(gg_cics *c, char *ridfld, int keylen, char *into, int intolen);
static void show(const char *what, gg_cics *c, const char *into) {
    printf("%s resp=%d resp2=%d into=%.4s\n", what, c->resp, c->resp2, into);
}
int main(void) {
    gg_cics c;
    char into[8], key[3];
    memset(&c, 0, sizeof c);
    memcpy(c.name1, "XREF    ", 8);
    c.len = 4;
    memset(into, '.', sizeof into);
    memcpy(key, "01", 2);
    GGCREAD(&c, key, 2, into, 4);  show("read1", &c, into);  /* planned DUPKEY: the record is delivered */
    memset(into, '.', sizeof into);
    GGCREAD(&c, key, 2, into, 4);  show("read2", &c, into);  /* the plan was for the first only */
    memset(into, '.', sizeof into);
    memcpy(key, "99", 2);
    GGCREAD(&c, key, 2, into, 4);  show("read3", &c, into);  /* no record: NOTFND, DUPKEY has nothing to qualify */
    memcpy(key, "01", 2);
    GGCSTBR(&c, key, 2);
    memset(into, '.', sizeof into);
    GGCRDNX(&c, key, 2, into, 4);  show("next1", &c, into);
    memset(into, '.', sizeof into);
    GGCRDNX(&c, key, 2, into, 4);  show("next2", &c, into);  /* planned DUPKEY on the 2nd READNEXT */
    memset(into, '.', sizeof into);
    GGCRDPV(&c, key, 2, into, 4);  show("prev1", &c, into);
    return 0;
}
"""


@rt.needs_cc
def test_the_stub_reads_the_record_and_answers_dupkey(tmp_path):
    exe = rt._stub(tmp_path, _MAIN)
    (tmp_path / "x.dat").write_bytes(b"01AA02BB03CC")
    (tmp_path / "files.cfg").write_text(f"XREF {tmp_path / 'x.dat'} 4 0 2\n", encoding="ascii")
    (tmp_path / "faults.cfg").write_text(
        "".join(x + "\n" for x in ec.fault_lines({"name": "s", "faults": [
            {"cmd": "READ", "file": "XREF", "resp": "DUPKEY"},
            {"cmd": "READ", "file": "XREF", "nth": 3, "resp": "DUPKEY"},  # on the READ that finds nothing
            {"cmd": "READNEXT", "file": "XREF", "nth": 2, "resp": "DUPKEY"}]})),
        encoding="ascii")  # fmt: skip
    assert rt._run_stub(exe, tmp_path) == [
        "read1 resp=15 resp2=140 into=01AA",
        "read2 resp=0 resp2=0 into=01AA",
        "read3 resp=13 resp2=80 into=....",
        "next1 resp=0 resp2=0 into=01AA",
        "next2 resp=15 resp2=140 into=02BB",
        "prev1 resp=0 resp2=0 into=02BB",
    ]
    # what fired: the two reads that found a record; the READ that found nothing never fired (the harness flags it)
    assert (tmp_path / "out" / "faults.txt").read_text().splitlines() == [
        "READ XREF 1 15 140",
        "READNEXT XREF 2 15 140",
    ]


# ---- the generated CicsTask ---------------------------------------------------------------------------------
@rt.needs_javac
def test_cics_task_reads_the_record_and_answers_dupkey(tmp_path):
    plan = ec.fault_lines({"name": "s", "faults": [
        {"cmd": "READ", "file": "XREF", "resp": "DUPKEY"},
        {"cmd": "READ", "file": "XREF", "nth": 3, "resp": "DUPKEY"},
        {"cmd": "READNEXT", "file": "XREF", "nth": 2, "resp": "DUPKEY"}]})  # fmt: skip
    log = tmp_path / "fired.txt"
    lines = ", ".join(f'"{ln}"' for ln in plan)
    out = rt._cics_task(
        tmp_path,
        f"""
        java.util.TreeSet<String> keys = new java.util.TreeSet<>(java.util.List.of("01", "02", "03"));
        CicsTask t = new CicsTask("HC01", "ENTER", null, null).withFaults(java.util.List.of({lines}),
                java.nio.file.Path.of("{log.as_posix()}"));
        CicsTask.FileRead<String> r1 = t.read("XREF", () -> java.util.Optional.of("01AA"));
        System.out.println("read1 " + r1.resp() + " " + r1.resp2() + " " + r1.record() + " " + r1.normal());
        CicsTask.FileRead<String> r2 = t.read("XREF", () -> java.util.Optional.of("01AA"));
        System.out.println("read2 " + r2.resp() + " " + r2.resp2() + " " + r2.record());
        CicsTask.FileRead<String> r3 = t.read("XREF", () -> java.util.Optional.<String>empty());
        System.out.println("read3 " + r3.resp() + " " + r3.resp2() + " " + r3.record());
        t.startbr("XREF", "01", false, () -> keys);
        CicsTask.Browsed n1 = t.readnext("XREF", "01");
        System.out.println("next1 " + n1.resp() + " " + n1.resp2() + " " + n1.key());
        CicsTask.Browsed n2 = t.readnext("XREF", "01");
        System.out.println("next2 " + n2.resp() + " " + n2.resp2() + " " + n2.key() + " " + n2.normal());
        CicsTask.Browsed p1 = t.readprev("XREF", "02");
        System.out.println("prev1 " + p1.resp() + " " + p1.resp2() + " " + p1.key());""",
    )
    assert out.splitlines() == [
        "read1 15 140 01AA true",
        "read2 0 0 01AA",
        "read3 13 80 null",
        "next1 0 0 01",
        "next2 15 140 02 true",
        "prev1 0 0 02",
    ]
    assert log.read_text().splitlines() == ["READ XREF 1 15 140", "READNEXT XREF 2 15 140"]  # as the stub's log


def test_both_runtimes_hold_a_planned_dupkey_back_instead_of_returning_it_early():
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_TASK_JAVA

    stub = rt.STUB.read_text(encoding="utf-8") + (rt.STUB.parent / "ggcics_filecontrol.c").read_text(encoding="utf-8")
    assert "dupkey_apply(c)" in stub and "DFHRESP_DUPKEY" in stub
    assert "dupkeyOr()" in CICS_TASK_JAVA and "resp == 15" in CICS_TASK_JAVA
