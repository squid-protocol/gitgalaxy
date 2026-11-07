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
from test_cics_runtimes import _cics_task, needs_javac  # noqa: E402


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


def test_a_token_read_keeps_the_event_free_search():
    out = _Events().command("READ FILE('KSDS') INTO(REC) RIDFLD(KEY) KEYLENGTH(10) GTEQ UPDATE TOKEN(TK) RESP(R)", "")
    assert not any("readSearchEvent" in ln for ln in out)


def test_the_gate_reads_a_tokenless_search_read_and_nothing_else():
    def gate(*execs):
        c = tdt._LenCics()
        c.g.p = type("P", (), {"proc": type("Q", (), {"execs": dict(enumerate(execs))})()})()
        return c._records_file_events()

    assert gate("READ FILE('F') INTO(R) RIDFLD(K) GTEQ")
    assert gate("READ FILE('F') INTO(R) RIDFLD(K) KEYLENGTH(2) GENERIC")
    assert not gate("READ FILE('F') INTO(R) RIDFLD(K)")
    assert not gate("READ FILE('F') INTO(R) RIDFLD(K) GTEQ UPDATE TOKEN(T)")
    assert not gate("READNEXT FILE('F') INTO(R) RIDFLD(K)")


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
