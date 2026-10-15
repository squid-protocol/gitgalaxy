"""#5078 (register X52): READ UPDATE TOKEN / REWRITE TOKEN / DELETE TOKEN / UNLOCK TOKEN, as IBM documents them (CICS TS
6.x, EXEC CICS READ, REWRITE, DELETE, UNLOCK), run on the stub (ggcics.c) and on CicsTask over one scenario list.

IBM: TOKEN on READ is "a unique identifier for this READ UPDATE request ... for use in associating a subsequent REWRITE or
DELETE (or UNLOCK) request with the record returned"; "If you specify TOKEN it implies update". A REWRITE / DELETE / UNLOCK
TOKEN "whose value cannot be matched against any token in use for an existing read for UPDATE" is INVREQ, RESP2 47. A
REWRITE without a token, with no READ UPDATE without a token before it, is INVREQ (RESP2 30, #5092). The token's value is IBM's to choose: ASSUMED, the task's 1, 2, 3, ... in both runtimes."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cics_runtimes import _cics_task, _run_stub, _stub, needs_cc, needs_javac  # noqa: E402

# R:file:key read update token | W:file:token:key rewrite token (FROM = key + "X") | D:file:token delete token
# U:file:token unlock token | T:file:key rewrite without a token
_OPS = (
    "R:F:100", "R:F:200", "W:F:2:200", "W:F:2:200", "D:F:1", "D:F:1", "W:F:77:200", "R:F:300", "D:G:3", "U:F:3",
    "U:F:3", "D:F:3", "R:F:999", "R:F:210", "T:F:210", "W:F:4:210", "R:G:900", "U:F:5",
)  # fmt: skip
_WANT = [
    "R:F:100 resp=0 resp2=0 tok=1",  # a read for update returns a token ...
    "R:F:200 resp=0 resp2=0 tok=2",  # ... and several are held at once, on one file
    "W:F:2:200 resp=0 resp2=0",  # the token rewrites ITS record, not the first one read
    "W:F:2:200 resp=16 resp2=47",  # a spent (reused) token matches none in use
    "D:F:1 resp=0 resp2=0",
    "D:F:1 resp=16 resp2=47",
    "W:F:77:200 resp=16 resp2=47",  # a token never issued
    "R:F:300 resp=0 resp2=0 tok=3",
    "D:G:3 resp=16 resp2=47",  # the token of another file's record
    "U:F:3 resp=0 resp2=0",  # an UNLOCK spends the token
    "U:F:3 resp=16 resp2=47",
    "D:F:3 resp=16 resp2=47",  # nothing left to delete by it
    "R:F:999 resp=13 resp2=80 tok=0",  # NOTFND: no token issued
    "R:F:210 resp=0 resp2=0 tok=4",
    "T:F:210 resp=16 resp2=30",  # a record held by a token is not the file's tokenless hold
    "W:F:4:210 resp=0 resp2=0",
    "R:G:900 resp=0 resp2=0 tok=5",
    "U:F:5 resp=16 resp2=47",  # file G's token, FILE(F)
]
_LEFT = b"300d210X200X"  # 100 deleted, 200 and 210 rewritten, 300 unlocked as it was

_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCREAD(gg_cics *c, char *rid, int kl, char *into, int il);
int GGCREWR(gg_cics *c, char *from, int fl);
int GGCDELT(gg_cics *c, char *rid, int kl);
int GGCUNLK(gg_cics *c);
int main(int argc, char **argv) {
    gg_cics c;
    for (int i = 1; i < argc; i++) {
        char op = argv[i][0], file[2] = {argv[i][2], 0}, key[8] = "", from[5] = "????";
        int tok = 0;
        memset(&c, 0, sizeof c);
        memset(c.name1, ' ', 8);
        c.name1[0] = file[0];
        memset(c.flags, ' ', 40);
        if (op == 'R' || op == 'T') sscanf(argv[i] + 4, "%7s", key);
        else if (op == 'W') sscanf(argv[i] + 4, "%d:%7s", &tok, key);
        else sscanf(argv[i] + 4, "%d", &tok);
        if (op == 'R') {
            char into[5] = "....";
            memcpy(c.flags, "UPDATE TOKEN", 12);
            c.len = 4;
            GGCREAD(&c, key, 3, into, 4);
            printf("%s resp=%d resp2=%d tok=%d\n", argv[i], c.resp, c.resp2, c.resp == 0 ? c.num : 0);
            continue;
        }
        if (op == 'W' || op == 'T') {
            memcpy(from, key, 3);
            from[3] = 'X';
            if (op == 'W') memcpy(c.flags, "TOKEN", 5);
            c.num = tok;
            GGCREWR(&c, from, 4);
        } else if (op == 'D') {
            memcpy(c.flags, "TOKEN", 5);
            c.num = tok;
            GGCDELT(&c, c.flags, 0);
        } else {
            memcpy(c.flags, "TOKEN", 5);
            c.num = tok;
            GGCUNLK(&c);
        }
        printf("%s resp=%d resp2=%d\n", argv[i], c.resp, c.resp2);
    }
    return 0;
}
"""


def _files(work: Path) -> None:
    (work / "f.dat").write_bytes(b"300d210c100a200b")
    (work / "g.dat").write_bytes(b"900z")
    (work / "files.cfg").write_text(f"F {work / 'f.dat'} 4 0 3\nG {work / 'g.dat'} 4 0 3\n", encoding="ascii")


@needs_cc
def test_the_stub_holds_records_under_tokens_as_ibm_documents(tmp_path):
    _files(tmp_path)
    exe = _stub(tmp_path, _MAIN)
    assert _run_stub(exe, tmp_path, *_OPS) == _WANT
    assert (tmp_path / "f.dat").read_bytes() == _LEFT


@needs_cc
def test_the_stub_refuses_a_token_rewrite_that_changes_the_key(tmp_path):
    """IBM does not say what a REWRITE TOKEN whose FROM has another key does: refused by name."""
    _files(tmp_path)
    exe = _stub(tmp_path, _MAIN)
    refused = subprocess.run([str(exe), "R:F:100", "W:F:1:200"], capture_output=True, text=True, check=False,  # noqa: S603
                             env={"PATH": "/usr/bin:/bin", "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out")})  # fmt: skip
    assert refused.returncode == 98 and "REWRITE TOKEN" in refused.stdout


@needs_cc
def test_the_stub_a_syncpoint_ends_every_token(tmp_path):
    _files(tmp_path)
    exe = _stub(tmp_path, _MAIN.replace("int main(", "int GGCSYNC(gg_cics *c);\nint main(").replace(
        "        if (op == 'R') {", "        if (op == 'S') { GGCSYNC(&c); printf(\"S\\n\"); continue; }\n        if (op == 'R') {", 1))  # fmt: skip
    assert _run_stub(exe, tmp_path, "R:F:100", "S:F:0", "U:F:1")[-1] == "U:F:1 resp=16 resp2=47"


_JAVA = """
        java.util.TreeMap<String, String> files = new java.util.TreeMap<>(java.util.Map.of(
                "300", "300d", "210", "210c", "100", "100a", "200", "200b"));
        java.util.TreeMap<String, String> g = new java.util.TreeMap<>(java.util.Map.of("900", "900z"));
        CicsTask t = new CicsTask("T", "ENTER", null, null);
        for (String op : new String[] {%s}) {
            String[] p = op.split(":");
            String file = p[1];
            java.util.TreeMap<String, String> f = file.equals("F") ? files : g;
            if (p[0].equals("R")) {
                CicsTask.FileRead<String> r = t.read(file, () -> java.util.Optional.ofNullable(f.get(p[2])));
                int tok = r.resp() == 0 ? t.holdToken(file, p[2].getBytes()) : 0;
                System.out.println(op + " resp=" + r.resp() + " resp2=" + r.resp2() + " tok=" + tok);
                continue;
            }
            int resp;
            if (p[0].equals("W")) {
                resp = t.rewriteToken(file, Integer.parseInt(p[2]), p[3].getBytes(), () -> f.put(p[3], p[3] + "X"));
            } else if (p[0].equals("T")) {
                resp = t.rewrite(file, () -> f.put(p[2], p[2] + "X"));
            } else if (p[0].equals("D")) {
                resp = t.deleteToken(file, Integer.parseInt(p[2]), k -> f.remove(new String(k)));
            } else {
                resp = t.unlockToken(file, Integer.parseInt(p[2]));
            }
            System.out.println(op + " resp=" + resp + " resp2=" + t.resp2());
        }
        System.out.println(String.join("", files.values()));"""


@needs_javac
def test_cics_task_holds_records_under_tokens_as_the_stub_does(tmp_path):
    ops = ", ".join(f'"{o}"' for o in _OPS)
    out = _cics_task(tmp_path, _JAVA % ops).splitlines()
    assert out[:-1] == _WANT
    assert out[-1] == "200X210X300d"  # key order: the same records as the stub's file


@needs_javac
def test_cics_task_refuses_a_token_rewrite_that_changes_the_key(tmp_path):
    out = _cics_task(tmp_path, """
        CicsTask t = new CicsTask("T", "ENTER", null, null);
        int tok = t.holdToken("F", "100".getBytes());
        try {
            t.rewriteToken("F", tok, "200".getBytes(), () -> {});
        } catch (UnsupportedOperationException e) {
            System.out.println("refused: " + e.getMessage());
        }""")  # fmt: skip
    assert "refused: REWRITE TOKEN" in out


@needs_javac
def test_cics_task_a_syncpoint_ends_every_token(tmp_path):
    out = _cics_task(tmp_path, """
        CicsTask t = new CicsTask("T", "ENTER", null, null);
        int tok = t.holdToken("F", "100".getBytes());
        t.syncpoint();
        System.out.println(t.unlockToken("F", tok) + " " + t.resp2());""")  # fmt: skip
    assert out.strip() == "16 47"
