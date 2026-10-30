"""#6262 (slice C): browse events under conditions -- a planned fault, DUPKEY and a file CICS does not define -- on both legs.

test_browse_events_6262.py and test_browse_stub_events_6262.py hold the NORMAL / ENDFILE / LENGERR / INVREQ / NOTFND paths.
Here the Java leg (CicsTask.*Event) and the C stub (ggcics_filecontrol.c) run one command list against the same expected
log, traced from IBM (CICS TS 6.x, EXEC CICS STARTBR / READNEXT / READPREV / ENDBR, "Conditions"): NOTOPEN (RESP2 60) on
STARTBR; DUPKEY (RESP2 140) on READNEXT / READPREV, which delivers the record; ENDFILE (RESP2 90) on READPREV; FILENOTFOUND
(RESP2 1, the file is not defined to CICS) on all four. A failed browse read delivers no data; a DUPKEY one does.
"""

import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402
import equivalence_cics as ec  # noqa: E402
import test_browse_events_6262 as java_leg  # noqa: E402
import test_cics_runtimes as rt  # noqa: E402

REC = java_leg.REC
GONE = "NO FILE"  # a name with a blank is defined in no region (IBM: 1-8 characters of A-Z 0-9 and a few symbols)

# op (S STARTBR, N READNEXT, P READPREV, X ENDBR) | file (H: HCBR, G: GONE) | key on entry -> RESP/RESP2
_OPS = (
    ("S", "H", "K001", "19/60"),  # the planned NOTOPEN: no browse starts
    ("S", "H", "K001", "0/0"),
    ("N", "H", "K001", "0/0"),
    ("N", "H", "K001", "15/140"),  # the planned DUPKEY on the 2nd READNEXT: K002 is delivered
    ("P", "H", "K002", "20/90"),  # the planned ENDFILE on the 1st READPREV
    ("P", "H", "K002", "15/140"),  # the planned DUPKEY on the 2nd READPREV
    ("X", "H", "K001", "0/0"),  # the planned faults did not end the browse
    ("S", "G", "K001", "12/1"),
    ("N", "G", "K001", "12/1"),
    ("P", "G", "K001", "12/1"),
    ("X", "G", "K001", "12/1"),
)
_PLAN = ec.fault_lines(
    {
        "name": "s",
        "faults": [
            {"cmd": "STARTBR", "file": "HCBR", "nth": 1, "resp": "NOTOPEN"},
            {"cmd": "READNEXT", "file": "HCBR", "nth": 2, "resp": "DUPKEY"},
            {"cmd": "READPREV", "file": "HCBR", "nth": 1, "resp": "ENDFILE"},
            {"cmd": "READPREV", "file": "HCBR", "nth": 2, "resp": "DUPKEY"},
        ],
    }
)


def _ev(kind: str, key: str, file: str = "HCBR", **kv) -> dict:
    return {"event": kind, "file": file, "ridfld": key, **kv}


def _got(kind: str, key: str, data: str | None, resp: str = "DUPKEY", resp2: int = 140) -> dict:
    area = None if data is None else {"length": len(data), "text": data}
    return _ev(kind, key, resp=resp, resp2=resp2, length=16, data=area)


def _gone(kind: str, key: str, **kv) -> dict:
    return _ev(kind, key, GONE, resp="FILENOTFOUND", resp2=1, **kv)


_EXPECTED = [
    _ev("STARTBR", "K001", mode="GTEQ", resp="NOTOPEN", resp2=60),
    _ev("STARTBR", "K001", mode="GTEQ", resp="NORMAL"),
    java_leg._rd("READNEXT", "K001", REC["K001"]),
    _got("READNEXT", "K001", REC["K002"]),
    _ev("READPREV", "K002", resp="ENDFILE", resp2=90, data=None),
    _got("READPREV", "K002", REC["K002"]),
    {"event": "ENDBR", "file": "HCBR", "resp": "NORMAL"},
    _gone("STARTBR", "K001", mode="GTEQ"),
    _gone("READNEXT", "K001", data=None),
    _gone("READPREV", "K001", data=None),
    {"event": "ENDBR", "file": GONE, "resp": "FILENOTFOUND", "resp2": 1},
]
_CTX = cc.Context(layouts={}, map_fields={})


def _verdict(actual: list[dict], caps, expected: list[dict] | None = None) -> cc.Verdict:
    return cc.compare(java_leg._log(expected or _EXPECTED), java_leg._log(actual), caps, _CTX)


@rt.needs_javac
def test_cics_task_answers_each_browse_condition_and_records_it(tmp_path):
    seed = " ".join(f'f.put("{k}", hex.apply("{java_leg._hex(v)}"));' for k, v in REC.items())
    ops = ", ".join(f'{{"{op}", "{f}", "{key}", "{java_leg._hex(key)}"}}' for op, f, key, _ in _OPS)
    lines = ", ".join(f'"{ln}"' for ln in _PLAN)
    body = f"""
        java.util.function.Function<String, byte[]> hex = s -> java.util.HexFormat.of().parseHex(s);
        java.util.Map<String, byte[]> f = new java.util.TreeMap<>();
        {seed}
        java.util.function.Supplier<java.util.NavigableSet<String>> keys = () -> new java.util.TreeSet<>(f.keySet());
        java.util.function.Function<String, java.util.Optional<byte[]>> look = k -> java.util.Optional.ofNullable(f.get(k));
        CicsTask t = new CicsTask("T", "ENTER", null, null).withFaults(java.util.List.of({lines}), null);
        String[][] ops = {{{ops}}};
        for (String[] p : ops) {{
            String file = p[1].equals("H") ? "HCBR" : "{GONE}";
            byte[] rid = hex.apply(p[3]);
            int resp;
            int resp2;
            if (p[0].equals("S")) {{
                resp = t.startbrEvent(file, rid, p[2], false, keys);
                resp2 = t.resp2();
            }} else if (p[0].equals("X")) {{
                resp = t.endbrEvent(file);
                resp2 = t.resp2();
            }} else {{
                CicsTask.Browsed b = p[0].equals("N") ? t.readnextInto(file, rid, p[2], 16, look)
                        : t.readprevInto(file, rid, p[2], 16, look);
                resp = b.resp();
                resp2 = b.resp2();
            }}
            System.out.println("R " + resp + "/" + resp2);
        }}
        for (java.util.Map<String, Object> e : t.events()) {{
            StringBuilder b = new StringBuilder("E {{");
            String sep = "";
            for (java.util.Map.Entry<String, Object> kv : e.entrySet()) {{
                Object v = kv.getValue();
                String s = v == null ? "null" : v instanceof byte[] d ? "\\"" + java.util.Base64.getEncoder().encodeToString(d) + "\\""
                        : v instanceof String str ? "\\"" + str + "\\"" : String.valueOf(v);
                b.append(sep).append("\\"").append(kv.getKey()).append("\\":").append(s);
                sep = ",";
            }}
            System.out.println(b.append("}}"));
        }}"""
    import json

    out = rt._cics_task(tmp_path, body).splitlines()
    assert [ln[2:] for ln in out if ln.startswith("R ")] == [w for *_, w in _OPS]
    raw = [json.loads(ln[2:]) for ln in out if ln.startswith("E ")]
    assert len(raw) == len(_EXPECTED)
    actual = [{"event": e["event"], **runner._java_file_event(e["event"], e)} for e in raw]
    v = _verdict(actual, runner.JAVA_CAPS)
    assert v.status == "pass", v.reason


_MAIN = r"""
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCSTBR(gg_cics *c, char *rid, int kl); int GGCRDNX(gg_cics *c, char *rid, int kl, char *into, int il);
int GGCRDPV(gg_cics *c, char *rid, int kl, char *into, int il); int GGCENBR(gg_cics *c);
int main(int argc, char **argv) {
    gg_cics c;
    char rid[4], into[16];
    memset(&c, 0, sizeof c);
    for (int i = 1; i < argc; i++) {   /* OPF:KEY:INTO-LENGTH, F: H (HCBR) or G (a file nobody defines) */
        char op = argv[i][0];
        memset(c.name1, ' ', 8);
        if (argv[i][1] == 'H') memcpy(c.name1, "HCBR", 4); else memcpy(c.name1, "NOFILE", 6);
        memset(c.flags, ' ', 40);
        memcpy(rid, argv[i] + 3, 4);
        memset(into, '.', sizeof into);
        int il = atoi(argv[i] + 8);
        if (op == 'S') GGCSTBR(&c, rid, 4);
        if (op == 'N') GGCRDNX(&c, rid, 4, into, il);
        if (op == 'P') GGCRDPV(&c, rid, 4, into, il);
        if (op == 'X') GGCENBR(&c);
    }
    return 0;
}
"""


@rt.needs_cc
def test_the_stub_answers_each_browse_condition_and_records_it_as_the_java_leg_does(tmp_path):
    (tmp_path / "hcbr.dat").write_bytes(b"".join(r.encode("latin-1") for r in REC.values()))
    (tmp_path / "files.cfg").write_text(f"HCBR {tmp_path / 'hcbr.dat'} 16 0 4\n", encoding="ascii")
    (tmp_path / "faults.cfg").write_text("".join(ln + "\n" for ln in _PLAN), encoding="ascii")
    ops = [f"{op}{f}:{key}:16" for op, f, key, _ in _OPS]
    rt._run_stub(rt._stub(tmp_path, _MAIN), tmp_path, *ops)
    events = runner._cobol_events(tmp_path / "out", "HCBR")
    # the stub's event line is whitespace-split, so its undefined file is a name without a blank (it answers FILENOTFOUND
    # for any name absent from files.cfg; the Java leg decides it only for names no region can define, register X75)
    expected = [{**e, "file": "NOFILE"} if e["file"] == GONE else e for e in _EXPECTED]
    assert len(events) == len(expected)
    v = _verdict(events, runner.COBOL_CAPS, expected)
    assert v.status == "pass", v.reason


def test_a_dupkey_browse_read_must_carry_its_record_and_a_failed_one_none():
    def raw(e):  # an actual event carries its area as the runner maps it
        d = e.get("data")
        return {**e, "data": cc.RawArea(d["text"].encode("latin-1"), "latin-1")} if d else e

    java = [raw(e) for e in _EXPECTED]
    assert _verdict(java, runner.JAVA_CAPS).status == "pass"
    no_data = [{**e, "data": None} if e["event"] == "READNEXT" and e["resp"] == "DUPKEY" else e for e in java]
    assert _verdict(no_data, runner.JAVA_CAPS).status == "fail"
    wrong_resp2 = [{**e, "resp2": 141} if e["resp"] == "NOTOPEN" else e for e in java]
    assert _verdict(wrong_resp2, runner.JAVA_CAPS).status == "fail"


def test_both_legs_support_the_events_the_conditions_log_names():
    log = java_leg._log(_EXPECTED)
    assert cc.blockers(log, runner.JAVA_CAPS) == []
    assert cc.blockers(log, runner.COBOL_CAPS) == []
