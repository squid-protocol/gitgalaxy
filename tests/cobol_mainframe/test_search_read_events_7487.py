"""#7487 slice 2: a READ GTEQ / GENERIC is recorded as the SPEC 6.2 READ event (CicsTask.readSearchEvent), so its RESP,
RESP2, length and data reach the event comparison instead of being dropped with the verb the port recorded none of.

IBM, EXEC CICS READ: GTEQ / GENERIC retrieve the first record whose (generic) key is equal or greater; NOTFND RESP2 80
when none is; a record longer than INTO's LENGTH is LENGERR RESP2 11 (register X22)."""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "cics_crucible"))
sys.path.insert(0, str(HERE.parent / "tools"))
import equivalence_cics as ec  # noqa: E402
import equivalence_cics_filecontrol as fc  # noqa: E402
import test_det_translate as tdt  # noqa: E402
from test_cics_runtimes import _cics_task, _run_stub, _stub, needs_cc, needs_javac  # noqa: E402


class _Events(tdt._LenCics):
    """A program that records file events (a tokenless GTEQ READ turns them on, `_records_file_events`)."""

    def _records_file_events(self):
        return True


OPTS = "READ FILE('KSDS') INTO(REC) RIDFLD(KEY) KEYLENGTH(10) GTEQ RESP(R)"


def test_a_program_without_events_keeps_the_event_free_search():
    out = tdt._LenCics().command(OPTS, "")
    assert any("task.readSearch('KSDS'" in ln for ln in out)
    assert not any("readSearchEvent" in ln for ln in out)


@pytest.mark.parametrize("update", ["", " UPDATE"])
@pytest.mark.parametrize("key", ["KEYLENGTH(10) GTEQ", "KEYLENGTH(6) GENERIC", "KEYLENGTH(6) GENERIC GTEQ"])
def test_into_forms_record_the_event(key, update):
    out = _Events().command(f"READ FILE('KSDS') INTO(REC) RIDFLD(KEY) {key}{update} RESP(R)", "")
    call = next(ln for ln in out if "task.readSearchEvent(" in ln)
    assert f"task.readSearchEvent('KSDS'.stripTrailing(), rec2, {'true' if update else 'false'}, null, false, " in call
    assert "heldKey.put" in " ".join(out) if update else "heldKey.put" not in " ".join(out)


def test_into_length_passes_the_length_and_sets_it_back():
    out = _Events().command(f"{OPTS[:-8]} LENGTH(VARLEN) RESP(R)", "")
    call = next(ln for ln in out if "task.readSearchEvent(" in ln)
    assert ", INT(VARLEN), false, " in call
    assert "    STORE(VARLEN, BigDecimal.valueOf(read1.record().length));" in out


def test_set_form_records_the_event_without_a_gate():
    c = tdt._LenCics()
    c.g.pointer_item = lambda name, sub=None: f"f_{name}"
    out = c.command("READ FILE('KSDS') SET(PTR) RIDFLD(KEY) KEYLENGTH(10) GTEQ RESP(R)", "")
    assert any(", null, true, () -> store(F).search(" in ln for ln in out)


@pytest.mark.parametrize("update", ["", " UPDATE"])
def test_a_token_search_read_records_the_event_held_by_its_token(update):
    """#7965: the event carries the written UPDATE only (the stub's `upd=1`); nothing is held as the file's one hold."""
    out = _Events().command(f"READ FILE('KSDS') INTO(REC) RIDFLD(KEY) KEYLENGTH(10) GTEQ{update} TOKEN(TK) RESP(R)", "")
    call = next(ln for ln in out if "task.readSearchEvent(" in ln)
    assert f"rec2, {'true' if update else 'false'}, true, null, false, " in call
    assert "heldKey.put" not in " ".join(out) and any("task.holdToken(" in ln for ln in out)


@pytest.mark.parametrize("update", ["", " UPDATE"])
def test_a_token_into_read_records_the_event(update):
    out = _Events().command(f"READ FILE('KSDS') INTO(REC) LENGTH(VARLEN) RIDFLD(KEY){update} TOKEN(TK) RESP(R)", "")
    assert any(
        f"task.readInto('KSDS'.stripTrailing(), rec2, {'true' if update else 'false'}, true, INT(VARLEN)" in ln
        for ln in out
    )
    assert any("task.holdToken(" in ln for ln in out)


def test_a_token_set_read_records_the_event():
    c = tdt._LenCics()
    c.g.pointer_item = lambda name, sub=None: f"f_{name}"
    out = c.command("READ FILE('KSDS') SET(PTR) RIDFLD(KEY) UPDATE TOKEN(TK) RESP(R)", "")
    assert any("task.readSetEvent(" in ln and ", true, true, " in ln for ln in out)


def test_a_tokenless_read_keeps_the_old_call_shape():
    out = _Events().command("READ FILE('KSDS') INTO(REC) LENGTH(VARLEN) RIDFLD(KEY) UPDATE RESP(R)", "")
    assert any("task.readInto('KSDS'.stripTrailing(), rec2, true, INT(VARLEN)" in ln for ln in out)


@pytest.mark.parametrize("update", ["", " UPDATE"])
@pytest.mark.parametrize("key", ["KEYLENGTH(6)", "KEYLENGTH(10) GENERIC", "KEYLENGTH(-1) GENERIC"])
def test_an_invalid_keylength_read_records_the_event(key, update):
    """#7965: the stub logs a READ for a command CICS refuses (INVREQ RESP2 25 / 26 / 42); the port records it too."""
    out = _Events().command(f"READ FILE('KSDS') INTO(REC) RIDFLD(KEY) {key}{update} RESP(R)", "")
    call = next(ln for ln in out if "task.readInvalid" in ln)
    assert "task.readInvalidEvent('KSDS'.stripTrailing(), " in call
    assert f", {'true' if update else 'false'}, {'true' if update else 'false'}, false, " in call


def test_an_invalid_keylength_read_without_events_keeps_the_event_free_call():
    out = tdt._LenCics().command("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) KEYLENGTH(6) RESP(R)", "")
    assert any("task.readInvalid(" in ln for ln in out) and not any("readInvalidEvent" in ln for ln in out)


def test_the_gate_reads_a_tokenless_search_read_and_nothing_else():
    def gate(*execs):
        c = tdt._LenCics()
        c.g.p = type("P", (), {"proc": type("Q", (), {"execs": dict(enumerate(execs))})()})()
        return c._records_file_events()

    assert gate("READ FILE('F') INTO(R) RIDFLD(K) GTEQ")
    assert gate("READ FILE('F') INTO(R) RIDFLD(K) KEYLENGTH(2) GENERIC")
    assert not gate("READ FILE('F') INTO(R) RIDFLD(K)")
    assert gate("READ FILE('F') INTO(R) RIDFLD(K) GTEQ UPDATE TOKEN(T)")  # #7965: a token read is recorded
    assert gate("READ FILE('F') INTO(R) RIDFLD(K) UPDATE TOKEN(T)")
    assert not gate("UNLOCK FILE('F') TOKEN(T)")
    assert not gate("READNEXT FILE('F') INTO(R) RIDFLD(K)")


def test_a_rewrite_no_longer_turns_a_search_reads_events_off():
    """#7487: ZECS000 (READ UPDATE LENGTH ... GTEQ + REWRITE FROM) was the one program the gate left out."""

    def gate(*execs):
        c = tdt._LenCics()
        c.g.p = type("P", (), {"proc": type("Q", (), {"execs": dict(enumerate(execs))})()})()
        return c._records_file_events()

    both = ("READ FILE('F') UPDATE INTO(R) LENGTH(L) RIDFLD(K) GTEQ", "REWRITE FILE('F') FROM(R) LENGTH(L)")
    assert gate(*both)
    assert not gate(both[1])  # a REWRITE alone records nothing
    assert gate("READ FILE('F') UPDATE INTO(R) RIDFLD(K) GTEQ TOKEN(T)", both[1])  # #7965: a TOKEN read does too


@pytest.mark.parametrize(
    ("verb", "args", "file"),
    [
        (
            "READ",
            "file=     FILE key=AB resp=0",
            "     FILE",
        ),  # leading blanks survive (ZECS000 after a NOTFND RETRIEVE)
        ("READ", "file=KSDS key=AB resp=0", "KSDS"),
        ("REWRITE", "file=    FILE resp=0", "    FILE"),
        ("UNLOCK", "file=  F resp=13", "  F"),
        ("STARTBR", "file=  F rid=4142 resp=0", "  F"),
        ("READ", "file= key=AB resp=0", ""),  # an empty name
        ("READ", "file=F", "F"),  # last key on the line
        (
            "READ",
            "pgm=ZECS000 file=    FILE key= resp=12 resp2=1",
            "    FILE",
        ),  # the stub's real line: pgm= comes first
    ],
)
def test_the_harness_keeps_a_file_names_leading_blanks(verb, args, file):
    kv = ec.event_kv(verb, args)
    assert kv["file"] == file


def test_a_non_file_event_keeps_the_plain_split():
    assert ec.event_kv("SEND-MAP", "map=M1 mapset=S1") == {"map": "M1", "mapset": "S1"}


_ABEND_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len; } gg_cics;
int GGCREAD(gg_cics *c, char *ridfld, int keylen, char *into, int intolen);
int GGCSTBR(gg_cics *c, char *ridfld, int keylen);
int GGCRDNX(gg_cics *c, char *ridfld, int keylen, char *into, int intolen);
int GGCDELT(gg_cics *c, char *ridfld, int keylen);
int main(void) {
    gg_cics c;
    char into[8], key[3] = "01";
    memset(&c, 0, sizeof c);
    memcpy(c.name1, "XREF    ", 8);
    memset(c.flags, ' ', sizeof c.flags);
    c.len = 4;
    GGCREAD(&c, key, 2, into, 4);   /* 1st READ: planned ABEND (or NOTFND) */
    GGCSTBR(&c, key, 2);            /* 1st STARTBR */
    GGCRDNX(&c, key, 2, into, 4);   /* 1st READNEXT */
    GGCDELT(&c, key, 2);            /* 1st DELETE */
    return 0;
}
"""


def _stub_events(tmp_path, resp):
    exe = _stub(tmp_path, _ABEND_MAIN)
    (tmp_path / "x.dat").write_bytes(b"01AA02BB03CC")
    (tmp_path / "files.cfg").write_text(f"XREF {tmp_path / 'x.dat'} 4 0 2\n", encoding="ascii")
    plan = [{"cmd": c, "file": "XREF", "resp": resp, **({"abcode": "AFCR"} if resp == "ABEND" else {})}
            for c in ("READ", "STARTBR", "READNEXT", "DELETE")]  # fmt: skip
    (tmp_path / "faults.cfg").write_text(
        "".join(x + "\n" for x in ec.fault_lines({"name": "s", "faults": plan})), encoding="ascii"
    )
    _run_stub(exe, tmp_path)
    log = tmp_path / "out" / "events.txt"
    return [ln.partition(" ")[2].partition(" ")[0] for ln in log.read_text(encoding="latin-1").splitlines()]


@needs_cc
def test_an_abend_planned_file_command_logs_the_abend_and_no_file_event(tmp_path):
    """#7487: IBM never completes a command that abends the task, so the stub logs no READ / STARTBR / READNEXT /
    DELETE event for it (the port logs none); ZECS000's ABEND-planned READ UPDATE was the burned case."""
    verbs = _stub_events(tmp_path, "ABEND")
    assert "ABEND" in verbs
    assert not {"READ", "STARTBR", "READNEXT", "DELETE"} & set(verbs), verbs


@needs_cc
def test_a_condition_planned_file_command_still_logs_its_event(tmp_path):
    verbs = _stub_events(tmp_path, "NOTFND")
    assert "ABEND" not in verbs
    assert {"READ", "STARTBR", "READNEXT", "DELETE"} <= set(verbs), verbs


def test_the_harness_pairs_a_search_read_and_a_differing_response_is_a_diff():
    c = fc.cobol_file_event("READ", {"file": "KSDS", "resp": "13", "resp2": "80"}, b"")
    assert fc.recorded_file_events([c], [c]) == [c]
    j = {**c, "resp": "NORMAL"}
    j.pop("resp2")
    assert [d["fields"][0]["field"] for d in ec.compare_events([c], [j])["diffs"]][:1] == ["resp"]


@needs_javac
@pytest.mark.slow(
    reason="a javac build of the shared CicsTask plus one JVM run (cold on a CI runner, as test_file_events_4443)"
)
def test_the_runtime_records_normal_notfnd_lengerr_and_set(tmp_path):
    body = r"""
        java.util.Map<String, byte[]> f = new java.util.HashMap<>();
        f.put("K002", "K002BRAVO   0020".getBytes());
        CicsTask t = new CicsTask("T", "ENTER", null, null);
        byte[] rid = "K001".getBytes();
        t.readSearchEvent("F", rid, false, 16, false, () -> java.util.Optional.ofNullable(f.get("K002")));
        t.readSearchEvent("F", rid, false, 8, false, () -> java.util.Optional.ofNullable(f.get("K002")));
        t.readSearchEvent("F", rid, false, null, true, () -> java.util.Optional.ofNullable(f.get("K002")));
        t.readSearchEvent("F", rid, true, 16, false, () -> java.util.Optional.ofNullable(f.get("K009")));
        for (java.util.Map<String, Object> e : t.events()) {
            System.out.println("E " + e.get("resp") + " " + e.get("resp2") + " " + e.get("length") + " " + e.get("set")
                + " " + e.get("update") + " " + (e.get("data") != null));
        }"""
    got = [ln[2:] for ln in _cics_task(tmp_path, body).splitlines() if ln.startswith("E ")]
    assert got == [
        "NORMAL null 16 null null true",
        "LENGERR 11 16 null null false",
        "NORMAL null null true null true",
        "NOTFND 80 null null true false",
    ]
    assert json.dumps(got)


@needs_javac
@pytest.mark.slow(
    reason="a javac build of the shared CicsTask plus one JVM run (cold on a CI runner, as the test above)"
)
def test_the_runtime_records_token_reads_and_invalid_keylength_reads(tmp_path):
    """#7965: a TOKEN read records the event and holds nothing as the file's one hold (a second token read is not INVREQ 28);
    a refused READ records INVREQ with its RESP2, and a READ UPDATE on a held file is INVREQ 28 first."""
    body = r"""
        java.util.Map<String, byte[]> f = new java.util.HashMap<>();
        f.put("K001", "K001ALPHA   0010".getBytes());
        CicsTask t = new CicsTask("T", "ENTER", null, null);
        byte[] rid = "K001".getBytes();
        java.util.function.Supplier<java.util.Optional<byte[]>> look = () -> java.util.Optional.ofNullable(f.get("K001"));
        t.readInto("F", rid, true, true, 16, look);
        t.readInto("F", rid, false, true, 16, look);
        t.readSetEvent("F", rid, true, true, look);
        t.readSearchEvent("F", rid, false, true, 16, false, look);
        t.readInvalidEvent("F", rid, false, false, false, 26);
        t.readForUpdate("F", look);
        t.readInvalidEvent("F", rid, true, true, false, 25);
        for (java.util.Map<String, Object> e : t.events()) {
            System.out.println("E " + e.get("resp") + " " + e.get("resp2") + " " + e.get("length") + " " + e.get("set")
                + " " + e.get("update") + " " + (e.get("data") != null));
        }"""
    got = [ln[2:] for ln in _cics_task(tmp_path, body).splitlines() if ln.startswith("E ")]
    assert got == [
        "NORMAL null 16 null true true",
        "NORMAL null 16 null null true",
        "NORMAL null null true true true",
        "NORMAL null 16 null null true",
        "INVREQ 26 null null null false",
        "INVREQ 28 null null true false",
    ]
