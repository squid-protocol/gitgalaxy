"""#5079 (register X52): UNLOCK without TOKEN releases the file's tokenless READ UPDATE hold (IBM, CICS TS 6.x, EXEC CICS
UNLOCK: "releases exclusive control of a record in a file that was acquired by a previous READ UPDATE"), run on the stub
(ggcics.c) and on CicsTask over one scenario list. A REWRITE after the UNLOCK is INVREQ RESP2 30 (#5092)
(no hold to rewrite). IBM: an UNLOCK that matches no tokenless READ UPDATE (or WRITE
MASSINSERT, not modelled) "takes no action and a NORMAL response is returned". A record held under a token is not the tokenless hold."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cics_runtimes import _cics_task, _run_stub, _stub, needs_cc, needs_javac  # noqa: E402

# H:file:key read update, no token | N:file unlock, no token | T:file:key rewrite, no token | R:file:key read update token
# U:file:token unlock token | S:file:0 syncpoint
_OPS = (
    "N:F:0", "H:F:100", "N:F:0", "T:F:100", "N:F:0", "H:F:200", "H:G:900", "N:G:0", "T:F:200", "H:F:300", "N:F:0",
    "R:F:210", "N:F:0", "U:F:1", "H:F:999", "N:F:0", "H:F:100", "S:F:0", "N:F:0", "H:F:100", "N:F:0", "H:F:100",
)  # fmt: skip
_WANT = [
    "N:F:0 resp=0 resp2=0",  # nothing held: no action, NORMAL (IBM)
    "H:F:100 resp=0 resp2=0",
    "N:F:0 resp=0 resp2=0",  # released ...
    "T:F:100 resp=16 resp2=30",  # ... so a REWRITE finds nothing held (INVREQ RESP2 30, #5092)
    "N:F:0 resp=0 resp2=0",  # and a second UNLOCK is NORMAL too
    "H:F:200 resp=0 resp2=0",
    "H:G:900 resp=0 resp2=0",
    "N:G:0 resp=0 resp2=0",  # another file's UNLOCK leaves F's hold
    "T:F:200 resp=0 resp2=0",
    "H:F:300 resp=0 resp2=0",
    "N:F:0 resp=0 resp2=0",  # unlocked as it was
    "R:F:210 resp=0 resp2=0 tok=1",
    "N:F:0 resp=0 resp2=0",  # a token hold is not the file's tokenless hold
    "U:F:1 resp=0 resp2=0",
    "H:F:999 resp=13 resp2=80",  # NOTFND holds nothing
    "N:F:0 resp=0 resp2=0",
    "H:F:100 resp=0 resp2=0",
    "S:F:0 resp=0 resp2=0",  # a SYNCPOINT ends the hold
    "N:F:0 resp=0 resp2=0",
    "H:F:100 resp=0 resp2=0",
    "N:F:0 resp=0 resp2=0",
    "H:F:100 resp=0 resp2=0",  # the record can be read for update again
]
_LEFT = b"300d210c100a200X"

_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCREAD(gg_cics *c, char *rid, int kl, char *into, int il);
int GGCREWR(gg_cics *c, char *from, int fl);
int GGCUNLK(gg_cics *c);
int GGCSYNC(gg_cics *c);
int main(int argc, char **argv) {
    gg_cics c;
    for (int i = 1; i < argc; i++) {
        char op = argv[i][0], key[8] = "", from[5] = "????", into[5] = "....";
        int tok = 0;
        memset(&c, 0, sizeof c);
        memset(c.name1, ' ', 8);
        c.name1[0] = argv[i][2];
        memset(c.flags, ' ', 40);
        if (op == 'H' || op == 'T' || op == 'R') sscanf(argv[i] + 4, "%7s", key);
        if (op == 'H' || op == 'R') {
            memcpy(c.flags, op == 'H' ? "UPDATE" : "UPDATE TOKEN", op == 'H' ? 6 : 12);
            c.len = 4;
            GGCREAD(&c, key, 3, into, 4);
            printf("%s resp=%d resp2=%d", argv[i], c.resp, c.resp2);
            if (op == 'R') printf(" tok=%d", c.resp == 0 ? c.num : 0);
            printf("\n");
            continue;
        }
        if (op == 'T') {
            memcpy(from, key, 3);
            from[3] = 'X';
            GGCREWR(&c, from, 4);
        } else if (op == 'S') {
            GGCSYNC(&c);
        } else {
            if (argv[i][4] != '0') { sscanf(argv[i] + 4, "%d", &tok); memcpy(c.flags, "TOKEN", 5); c.num = tok; }
            GGCUNLK(&c);
        }
        printf("%s resp=%d resp2=%d\n", argv[i], c.resp, c.resp2);
    }
    return 0;
}
"""

_JAVA = """
        java.util.TreeMap<String, String> files = new java.util.TreeMap<>(java.util.Map.of(
                "300", "300d", "210", "210c", "100", "100a", "200", "200b"));
        java.util.TreeMap<String, String> g = new java.util.TreeMap<>(java.util.Map.of("900", "900z"));
        CicsTask t = new CicsTask("T", "ENTER", null, null);
        for (String op : new String[] {%s}) {
            String[] p = op.split(":");
            String file = p[1];
            java.util.TreeMap<String, String> f = file.equals("F") ? files : g;
            if (p[0].equals("H") || p[0].equals("R")) {
                CicsTask.FileRead<String> r = p[0].equals("H")
                        ? t.readForUpdate(file, () -> java.util.Optional.ofNullable(f.get(p[2])))
                        : t.read(file, () -> java.util.Optional.ofNullable(f.get(p[2])));
                String tok = p[0].equals("R") ? " tok=" + (r.resp() == 0 ? t.holdToken(file, p[2].getBytes()) : 0) : "";
                System.out.println(op + " resp=" + r.resp() + " resp2=" + r.resp2() + tok);
                continue;
            }
            int resp;
            if (p[0].equals("T")) {
                resp = t.rewrite(file, () -> f.put(p[2], p[2] + "X"));
            } else if (p[0].equals("S")) {
                t.syncpoint();
                resp = 0;
            } else if (p[0].equals("U")) {
                resp = t.unlockToken(file, Integer.parseInt(p[2]));
            } else {
                resp = t.unlockHeld(file);
            }
            System.out.println(op + " resp=" + resp + " resp2=" + t.resp2());
        }
        System.out.println(String.join("", files.values()));"""


def _files(work: Path) -> None:
    (work / "f.dat").write_bytes(b"300d210c100a200b")
    (work / "g.dat").write_bytes(b"900z")
    (work / "files.cfg").write_text(f"F {work / 'f.dat'} 4 0 3\nG {work / 'g.dat'} 4 0 3\n", encoding="ascii")


@needs_cc
def test_the_stub_unlocks_the_files_tokenless_hold(tmp_path):
    _files(tmp_path)
    assert _run_stub(_stub(tmp_path, _MAIN), tmp_path, *_OPS) == _WANT
    assert (tmp_path / "f.dat").read_bytes() == _LEFT


@needs_javac
def test_cics_task_unlocks_the_files_tokenless_hold_as_the_stub_does(tmp_path):
    ops = ", ".join(f'"{o}"' for o in _OPS)
    out = _cics_task(tmp_path, _JAVA % ops).splitlines()
    assert out[:-1] == _WANT
    assert out[-1] == "100a200X210c300d"
