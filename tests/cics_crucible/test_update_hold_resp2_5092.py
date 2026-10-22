"""#5092 (register X52): the INVREQ RESP2 of the tokenless update hold, on the stub (ggcics.c) and on CicsTask over one scenario list.

IBM (CICS TS 6.x, EXEC CICS REWRITE / DELETE / READ): a REWRITE with no READ UPDATE (without TOKEN) before it is INVREQ RESP2 30; a
DELETE without RIDFLD, likewise, INVREQ RESP2 31; a READ UPDATE without TOKEN while an earlier one on the file has had no REWRITE,
DELETE, UNLOCK or SYNCPOINT is INVREQ RESP2 28. A record held under a TOKEN is not the file's tokenless hold."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cics_runtimes import _cics_task, _run_stub, _stub, needs_cc, needs_javac  # noqa: E402

# R:file:key read update | N:file:key plain read | K:file:key read update token | T:file:key rewrite | D:file delete (no RIDFLD)
# S: syncpoint. (UNLOCK without TOKEN, the other release, is #5079.)
_SCENARIO = (
    ("T:F:100", "resp=16 resp2=30"),  # nothing read for update yet
    ("D:F:0", "resp=16 resp2=31"),
    ("R:F:100", "resp=0 resp2=0"),
    ("R:F:200", "resp=16 resp2=28"),  # a second READ UPDATE on the file, nothing released between
    ("R:G:900", "resp=0 resp2=0"),  # another file has its own hold
    ("T:F:100", "resp=0 resp2=0"),  # the REWRITE spends the hold ...
    ("T:F:100", "resp=16 resp2=30"),  # ... so a second one has none
    ("R:F:100", "resp=0 resp2=0"),  # and the next READ UPDATE is fine
    ("S:F:0", "resp=0 resp2=0"),
    ("T:F:100", "resp=16 resp2=30"),  # a SYNCPOINT ends the hold
    ("D:F:0", "resp=16 resp2=31"),
    ("R:F:999", "resp=13 resp2=80"),  # a NOTFND holds nothing ...
    ("R:F:100", "resp=0 resp2=0"),  # ... so this one is the first
    ("N:F:200", "resp=0 resp2=0"),  # a plain READ is no hold, and not blocked by one
    ("R:F:200", "resp=16 resp2=28"),
    ("T:F:100", "resp=0 resp2=0"),
    ("K:F:200", "resp=0 resp2=0"),  # READ UPDATE TOKEN: held under its token, not the file's tokenless hold
    ("T:F:200", "resp=16 resp2=30"),
    ("D:F:0", "resp=16 resp2=31"),
    ("R:F:100", "resp=0 resp2=0"),  # ... so a tokenless READ UPDATE is not a second one
    ("D:F:0", "resp=0 resp2=0"),  # the DELETE takes the held record, and releases
    ("D:F:0", "resp=16 resp2=31"),
    ("R:F:100", "resp=13 resp2=80"),
)
_OPS = [o for o, _ in _SCENARIO]
_WANT = [f"{o} {w}" for o, w in _SCENARIO]
_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCREAD(gg_cics *c, char *rid, int kl, char *into, int il);
int GGCREWR(gg_cics *c, char *from, int fl);
int GGCDELT(gg_cics *c, char *rid, int kl);
int GGCSYNC(gg_cics *c);
int main(int argc, char **argv) {
    gg_cics c;
    for (int i = 1; i < argc; i++) {
        char op = argv[i][0], key[8] = "", from[5] = "????";
        memset(&c, 0, sizeof c);
        memset(c.name1, ' ', 8);
        c.name1[0] = argv[i][2];
        memset(c.flags, ' ', 40);
        sscanf(argv[i] + 4, "%7s", key);
        if (op == 'S') GGCSYNC(&c);
        else if (op == 'R' || op == 'N' || op == 'K') {
            char into[5] = "....";
            if (op == 'R') memcpy(c.flags, "UPDATE", 6);
            if (op == 'K') memcpy(c.flags, "UPDATE TOKEN", 12);
            c.len = 4;
            GGCREAD(&c, key, 3, into, 4);
        } else if (op == 'T') {
            memcpy(from, key, 3);
            from[3] = 'X';
            GGCREWR(&c, from, 4);
        } else {
            memcpy(c.flags, "HELD", 4);
            GGCDELT(&c, c.flags, 0);
        }
        printf("%s resp=%d resp2=%d\n", argv[i], c.resp, c.resp2);
    }
    return 0;
}
"""


def _files(work: Path) -> None:
    (work / "f.dat").write_bytes(b"100a200b")
    (work / "g.dat").write_bytes(b"900z")
    (work / "files.cfg").write_text(f"F {work / 'f.dat'} 4 0 3\nG {work / 'g.dat'} 4 0 3\n", encoding="ascii")


@needs_cc
def test_the_stub_records_resp2_28_30_31_for_the_tokenless_hold(tmp_path):
    _files(tmp_path)
    got = _run_stub(_stub(tmp_path, _MAIN), tmp_path, *_OPS)
    assert got == _WANT
    assert (tmp_path / "f.dat").read_bytes() == b"200b"  # 100 deleted, 200 never rewritten


_JAVA = """
        java.util.TreeMap<String, String> files = new java.util.TreeMap<>(java.util.Map.of("100", "100a", "200", "200b"));
        java.util.TreeMap<String, String> g = new java.util.TreeMap<>(java.util.Map.of("900", "900z"));
        java.util.Map<String, String> heldKey = new java.util.HashMap<>();
        CicsTask t = new CicsTask("T", "ENTER", null, null);
        for (String op : new String[] {%s}) {
            String[] p = op.split(":");
            String file = p[1];
            java.util.TreeMap<String, String> f = file.equals("F") ? files : g;
            int resp = 0;
            int resp2 = 0;
            if (p[0].equals("S")) {
                t.syncpoint();
                heldKey.clear();
            } else if (p[0].equals("R") || p[0].equals("N") || p[0].equals("K")) {
                CicsTask.FileRead<String> r = p[0].equals("R")
                        ? t.readForUpdate(file, () -> java.util.Optional.ofNullable(f.get(p[2])))
                        : t.read(file, () -> java.util.Optional.ofNullable(f.get(p[2])));
                resp = r.resp();
                resp2 = r.resp2();
                if (resp == 0 && p[0].equals("R")) heldKey.put(file, p[2]);
                if (resp == 0 && p[0].equals("K")) t.holdToken(file, p[2].getBytes());
            } else if (p[0].equals("T")) {
                resp = t.rewrite(file, () -> f.put(p[2], p[2] + "X"));
                resp2 = t.resp2();
                heldKey.remove(file);
            } else {
                String k = heldKey.remove(file);
                resp = t.deleteHeld(file, () -> f.remove(k));
                resp2 = t.resp2();
            }
            System.out.println(op + " resp=" + resp + " resp2=" + resp2);
        }
        System.out.println(String.join("", files.values()));"""


@needs_javac
def test_cics_task_records_resp2_28_30_31_as_the_stub_does(tmp_path):
    ops = ", ".join(f'"{o}"' for o in _OPS)
    out = _cics_task(tmp_path, _JAVA % ops).splitlines()
    assert out[:-1] == _WANT
    assert out[-1] == "200b"


@needs_javac
def test_cics_task_a_gteq_read_update_is_a_second_read_update_too(tmp_path):
    out = _cics_task(tmp_path, """
        CicsTask t = new CicsTask("T", "ENTER", null, null);
        CicsTask.FileRead<String> r1 = t.readSearch("F", true, () -> java.util.Optional.of("100a"));
        CicsTask.FileRead<String> r2 = t.readSearch("F", true, () -> java.util.Optional.of("200b"));
        CicsTask.FileRead<String> r3 = t.readForUpdate("F", () -> java.util.Optional.of("200b"));
        CicsTask.FileRead<String> r4 = t.readSearch("F", false, () -> java.util.Optional.of("200b"));
        System.out.println(r1.resp() + "/" + r1.resp2() + " " + r2.resp() + "/" + r2.resp2() + " " + r3.resp() + "/" + r3.resp2()
                + " " + r4.resp() + "/" + r4.resp2());""")  # fmt: skip
    assert out.strip() == "0/0 16/28 16/28 0/0"


@needs_cc
def test_the_stub_a_gteq_read_update_is_a_second_read_update_too(tmp_path):
    _files(tmp_path)
    main = _MAIN.replace('if (op == \'R\') memcpy(c.flags, "UPDATE", 6);',
                         'if (op == \'R\') memcpy(c.flags, "UPDATE GTEQ", 11);')  # fmt: skip
    got = _run_stub(_stub(tmp_path, main), tmp_path, "R:F:100", "R:F:200", "R:F:100")
    assert got == ["R:F:100 resp=0 resp2=0", "R:F:200 resp=16 resp2=28", "R:F:100 resp=16 resp2=28"]
