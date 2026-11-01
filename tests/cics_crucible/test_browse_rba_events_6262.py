"""#6262 (READNEXT event, RBA browse): the Java leg records STARTBR / READNEXT / READPREV ... RBA as SPEC 6.2 events.

CicsTask.startbrRbaEvent / readnextRbaEvent / readprevRbaEvent record what the stub's `rba=` lines carry (ggcics_filecontrol.c
rba_event): the file, the fullword RBA (the record's, once one was read) and RESP. IBM (CICS TS 6.x, EXEC CICS READNEXT /
READPREV, option RBA): ENDFILE past the last record, LENGERR when INTO is too short. The SPEC has no RBA form of RIDFLD, so the
stub marks it Unmodelled and the comparison holds the events' count, order, file and RESP.
"""

import base64
import json
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402
from test_cics_runtimes import _cics_task, needs_javac  # noqa: E402

_JAVA = """
        java.util.List<byte[]> recs = new java.util.ArrayList<>();
        for (String r : new String[] {"10aa", "20bb", "30cc"}) recs.add(r.getBytes());
        CicsTask t = new CicsTask("T", "ENTER", null, null).withEsds("HCBR", 4, recs);
        t.startbrRbaEvent("HCBR", 0);
        long rid = 0;
        for (int i = 0; i < 4; i++) {
            CicsTask.BrowsedRba b = t.readnextRbaEvent("HCBR", rid, 4);
            if (b.record() != null) rid = b.rba();
        }
        t.readprevRbaEvent("HCBR", rid, 4);
        t.endbrEvent("HCBR");
        t.endbrEvent("HCBR");
        t.startbrRbaEvent("HCBR", 0xFFFFFFFFL);
        t.readprevRbaEvent("HCBR", 0xFFFFFFFFL, 4);
        t.endbrEvent("HCBR");
        t.startbrRbaEvent("HCBR", 0);
        t.readnextRbaEvent("HCBR", 0, 2);
        t.endbrEvent("HCBR");
        t.startbr("HCBR2", "K", false, () -> new java.util.TreeSet<>());
        for (java.util.Map<String, Object> e : t.events()) {
            StringBuilder b = new StringBuilder("E {");
            String sep = "";
            for (java.util.Map.Entry<String, Object> kv : e.entrySet()) {
                Object v = kv.getValue();
                String s = v == null ? "null" : v instanceof byte[] d ? "\\"" + java.util.Base64.getEncoder().encodeToString(d) + "\\""
                        : v instanceof String str ? "\\"" + str + "\\"" : String.valueOf(v);
                b.append(sep).append("\\"").append(kv.getKey()).append("\\":").append(s);
                sep = ",";
            }
            System.out.println(b.append("}"));
        }"""

# the stub's lines for the same sequence: verb, RBA (the record's once read), RESP
_STUB = [
    "STARTBR pgm=HCBR file=HCBR rba=0 resp=0",
    "READNEXT pgm=HCBR file=HCBR rba=0 resp=0",
    "READNEXT pgm=HCBR file=HCBR rba=4 resp=0",
    "READNEXT pgm=HCBR file=HCBR rba=8 resp=0",
    "READNEXT pgm=HCBR file=HCBR rba=8 resp=20",  # ENDFILE: the RBA stays
    "READPREV pgm=HCBR file=HCBR rba=8 resp=0",  # after a READNEXT: back to RIDFLD, the same record again
    "ENDBR pgm=HCBR file=HCBR resp=0",
    "ENDBR pgm=HCBR file=HCBR resp=16 resp2=35",
    "STARTBR pgm=HCBR file=HCBR rba=4294967295 resp=0",
    "READPREV pgm=HCBR file=HCBR rba=8 resp=0",  # X'FFFFFFFF': the last record
    "ENDBR pgm=HCBR file=HCBR resp=0",
    "STARTBR pgm=HCBR file=HCBR rba=0 resp=0",
    "READNEXT pgm=HCBR file=HCBR rba=0 resp=22",  # LENGERR
    "ENDBR pgm=HCBR file=HCBR resp=0",
]


def _log(events: list[dict]) -> dict:
    task = {
        "seq": 1, "transid": "HC83", "program": "HCBR", "termid": "T001", "at": "2026-03-02T10:00:00",
        "trigger": {"kind": "terminal", "step": 0}, "eibaid": "ENTER", "eibcalen": 0, "commarea": None,
        "events": [{**e, "program": "HCBR"} for e in events], "end": "normal",
    }  # fmt: skip
    return {"tasks": [task], "final": {}}


def _java_events(tmp_path: Path) -> list[dict]:
    out = _cics_task(tmp_path, _JAVA).splitlines()
    return [json.loads(ln[2:]) for ln in out if ln.startswith("E ")]


def _stub_events(tmp_path: Path) -> list[dict]:
    out = tmp_path / "out"
    out.mkdir()
    (out / "events.txt").write_text("".join(f"{i + 1:03d} {ln}\n" for i, ln in enumerate(_STUB)), encoding="latin-1")
    return runner._cobol_events(out, "HCBR")


def _verdict(expected: list[dict], raw: list[dict]) -> cc.Verdict:
    actual = _log([{"event": e["event"], **runner._java_file_event(e["event"], e)} for e in raw])
    return cc.compare(_log(expected), actual, runner.JAVA_CAPS, cc.Context(layouts={}, map_fields={}))


@needs_javac
def test_cics_task_records_rba_browse_commands_as_the_stub_does(tmp_path):
    raw = _java_events(tmp_path)
    assert len(raw) == len(_STUB)  # the keyed startbr on another file recorded nothing
    assert [(e["event"], e["resp"]) for e in raw][:6] == [
        ("STARTBR", "NORMAL"), ("READNEXT", "NORMAL"), ("READNEXT", "NORMAL"), ("READNEXT", "NORMAL"),
        ("READNEXT", "ENDFILE"), ("READPREV", "NORMAL"),
    ]  # fmt: skip
    assert [base64.b64decode(e["ridfld"]).hex() for e in raw if "ridfld" in e][:5] == [
        "00000000", "00000000", "00000004", "00000008", "00000008",
    ]  # fmt: skip
    assert raw[12]["resp"] == "LENGERR"
    expected = [{**e, "ridfld": b"\0\0\0\0"} if "ridfld" in e else e for e in _stub_events(tmp_path)]
    v = _verdict(expected, raw)
    assert v.status == "unsupported" and "an RBA browse's event" in v.reason, v.reason  # every modelled key agreed


def test_the_java_mapping_of_an_rba_event_keeps_only_what_the_stub_records():
    raw = {"event": "READNEXT", "file": "HCBR", "ridfld": base64.b64encode(b"\0\0\0\4").decode(), "rba": True,
           "resp": "ENDFILE", "resp2": None}  # fmt: skip
    ev = runner._java_file_event("READNEXT", raw)
    assert ev.keys() == {"file", "resp", "ridfld"} and isinstance(ev["ridfld"], cc.Unmodelled)  # fmt: skip
    sb = runner._java_file_event("STARTBR", {**raw, "event": "STARTBR", "resp": "NORMAL"})
    assert "mode" not in sb


def test_a_wrong_rba_event_resp_fails_the_comparison():
    raw = [{"event": "READNEXT", "file": "HCBR", "ridfld": base64.b64encode(b"\0\0\0\0").decode(), "rba": True,
            "resp": "ENDFILE"}]  # fmt: skip
    stub = [{"event": "READNEXT", "file": "HCBR", "ridfld": b"\0\0\0\0", "resp": "NORMAL"}]
    assert _verdict(stub, raw).status == "fail"
