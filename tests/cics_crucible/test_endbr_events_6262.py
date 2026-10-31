"""#6262 (ENDBR): every shape of ENDBR as a SPEC 6.2 event, one command list held to one expected log on both legs.

IBM (CICS TS 6.x, EXEC CICS ENDBR): ENDBR ends the browse on FILE; INVREQ RESP2 35 when no browse is active on it (never
started, already ended, or STARTBR failed); a READNEXT / READPREV after it is INVREQ RESP2 34; a STARTBR after it starts a
fresh browse; ending one file's browse leaves another file's active; a condition (here a planned IOERR, RESP2 120) answers
without ending the browse. The Java leg (CicsTask.endbrEvent) and the C stub (GGCENBR) run the same list.
"""

import json
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
FILES = {"A": "HCBR", "B": "HCB2"}
_RESP = {0: "NORMAL", 13: "NOTFND", 16: "INVREQ", 17: "IOERR", 20: "ENDFILE"}

# op (S STARTBR, N READNEXT, P READPREV, X ENDBR) | file | key on entry | record delivered -> RESP/RESP2
_OPS = (
    ("X", "A", "K001", None, "16/35"),  # never browsed
    ("S", "A", "K001", None, "0/0"),
    ("X", "A", "K001", None, "0/0"),  # ended with nothing read
    ("N", "A", "K001", None, "16/34"),  # a read after ENDBR
    ("P", "A", "K001", None, "16/34"),
    ("S", "A", "K001", None, "0/0"),  # a fresh browse
    ("N", "A", "K001", "K001", "0/0"),
    ("N", "A", "K001", "K002", "0/0"),
    ("N", "A", "K002", None, "20/90"),
    ("X", "A", "K001", None, "0/0"),  # ended after ENDFILE
    ("S", "A", "K002", None, "0/0"),
    ("P", "A", "K002", "K002", "0/0"),
    ("X", "A", "K001", None, "17/120"),  # the planned IOERR (4th ENDBR on HCBR): the browse stays
    ("X", "A", "K001", None, "0/0"),  # ended after READPREV
    ("S", "A", "K999", None, "13/80"),  # a failed STARTBR starts no browse
    ("X", "A", "K001", None, "16/35"),
    ("S", "A", "K001", None, "0/0"),
    ("S", "B", "K001", None, "0/0"),
    ("X", "A", "K001", None, "0/0"),
    ("N", "B", "K001", "K001", "0/0"),  # the other file's browse is untouched
    ("X", "A", "K001", None, "16/35"),
    ("X", "B", "K001", None, "0/0"),
    ("X", "B", "K001", None, "16/35"),
    ("S", "A", "K002", None, "0/0"),
    ("N", "A", "K002", "K002", "0/0"),
    ("X", "A", "K002", None, "0/0"),
)
_PLAN = ec.fault_lines({"name": "s", "faults": [{"cmd": "ENDBR", "file": "HCBR", "nth": 4, "resp": "IOERR"}]})
_KIND = {"N": "READNEXT", "P": "READPREV"}


def _expected() -> list[dict]:
    out = []
    for op, f, key, got, want in _OPS:
        resp, resp2 = (int(x) for x in want.split("/"))
        extra = {"resp2": resp2} if resp2 else {}
        file = FILES[f]
        if op == "X":
            out.append({"event": "ENDBR", "file": file, "resp": _RESP[resp], **extra})
        elif op == "S":
            out.append({"event": "STARTBR", "file": file, "ridfld": key, "mode": "GTEQ", "resp": _RESP[resp], **extra})
        elif got:
            out.append({**java_leg._rd(_KIND[op], key, REC[got]), "file": file})
        else:
            out.append({"event": _KIND[op], "file": file, "ridfld": key, "resp": _RESP[resp], **extra, "data": None})
    return out


_EXPECTED = _expected()
_CTX = cc.Context(layouts={}, map_fields={})


def _verdict(actual: list[dict], caps, expected: list[dict] | None = None) -> cc.Verdict:
    return cc.compare(java_leg._log(expected or _EXPECTED), java_leg._log(actual), caps, _CTX)


@rt.needs_javac
def test_cics_task_records_every_endbr_shape(tmp_path):
    seed = " ".join(f'f.put("{k}", hex.apply("{java_leg._hex(v)}"));' for k, v in REC.items())
    ops = ", ".join(f'{{"{op}", "{f}", "{key}", "{java_leg._hex(key)}"}}' for op, f, key, *_ in _OPS)
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
            String file = p[1].equals("A") ? "HCBR" : "HCB2";
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
        t.endbr("HCBR");  // the event-free endbr records nothing
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
    out = rt._cics_task(tmp_path, body).splitlines()
    assert [ln[2:] for ln in out if ln.startswith("R ")] == [o[-1] for o in _OPS]
    raw = [json.loads(ln[2:]) for ln in out if ln.startswith("E ")]
    assert len(raw) == len(_EXPECTED)
    actual = [{"event": e["event"], **runner._java_file_event(e["event"], e)} for e in raw]
    v = _verdict(actual, runner.JAVA_CAPS)
    assert v.status == "pass", v.reason
    wrong_file = [{**e, "file": "HCB2"} if i == 18 else e for i, e in enumerate(actual)]
    assert _verdict(wrong_file, runner.JAVA_CAPS).status == "fail"


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
    for (int i = 1; i < argc; i++) {   /* OPF:KEY, F: A (HCBR) or B (HCB2) */
        char op = argv[i][0];
        memset(c.name1, ' ', 8);
        memcpy(c.name1, argv[i][1] == 'A' ? "HCBR" : "HCB2", 4);
        memset(c.flags, ' ', 40);
        memcpy(rid, argv[i] + 3, 4);
        memset(into, '.', sizeof into);
        if (op == 'S') GGCSTBR(&c, rid, 4);
        if (op == 'N') GGCRDNX(&c, rid, 4, into, 16);
        if (op == 'P') GGCRDPV(&c, rid, 4, into, 16);
        if (op == 'X') GGCENBR(&c);
    }
    return 0;
}
"""


@rt.needs_cc
def test_the_stub_records_every_endbr_shape_as_the_java_leg_does(tmp_path):
    data = b"".join(r.encode("latin-1") for r in REC.values())
    for name in ("hcbr", "hcb2"):
        (tmp_path / f"{name}.dat").write_bytes(data)
    (tmp_path / "files.cfg").write_text(
        "".join(f"{n.upper()} {tmp_path / (n + '.dat')} 16 0 4\n" for n in ("hcbr", "hcb2")), encoding="ascii"
    )
    (tmp_path / "faults.cfg").write_text("".join(ln + "\n" for ln in _PLAN), encoding="ascii")
    rt._run_stub(rt._stub(tmp_path, _MAIN), tmp_path, *[f"{op}{f}:{key}" for op, f, key, *_ in _OPS])
    events = runner._cobol_events(tmp_path / "out", "HCBR")
    assert len(events) == len(_EXPECTED)
    v = _verdict(events, runner.COBOL_CAPS)
    assert v.status == "pass", v.reason
    wrong_resp2 = [{**e, "resp2": 36} if i == 0 else e for i, e in enumerate(events)]
    assert _verdict(wrong_resp2, runner.COBOL_CAPS).status == "fail"


def test_both_legs_support_the_events_the_endbr_log_names():
    log = java_leg._log(_EXPECTED)
    assert cc.blockers(log, runner.JAVA_CAPS) == []
    assert cc.blockers(log, runner.COBOL_CAPS) == []
