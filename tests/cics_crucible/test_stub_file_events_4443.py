"""#4443 (slice A0b): the C stub (ggcics.c) records READ / REWRITE / UNLOCK with the SPEC 6.2 keys and the runner parses them.

READ: update (READ UPDATE only), length (NORMAL and LENGERR: the record's), data (NORMAL only: the bytes INTO took), resp2
(where not NORMAL; a LENGERR READ asserts its RESP only, SPEC section 2). REWRITE: file, FROM bytes, resp, resp2. UNLOCK: file,
resp, resp2 (IBM, EXEC CICS UNLOCK: nothing held is NORMAL; a TOKEN matching none is INVREQ RESP2 47). One stub run over every
outcome; the events are compared with a hand-written log and each key's mismatch must fail the comparison."""

import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402
from test_cics_runtimes import _run_stub, _stub, needs_cc  # noqa: E402

# op:file:key:into -- R read, H read update, W rewrite (FROM key + "X"), U unlock, T unlock token 9, P syncpoint
_OPS = (
    "R:F:K002:8", "R:F:K002:16", "R:F:K009:16", "W:F:K002:0", "U:F:0:0", "H:F:K002:16", "H:F:K001:16", "W:F:K002:0",
    "R:F:K002:16", "H:F:K001:16", "U:F:0:0", "W:F:K001:0", "T:F:0:0", "R:Z:K001:16", "W:Z:K001:0",
)  # fmt: skip

_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCREAD(gg_cics *c, char *rid, int kl, char *into, int il);
int GGCREWR(gg_cics *c, char *from, int fl);
int GGCUNLK(gg_cics *c);
int main(int argc, char **argv) {
    gg_cics c;
    for (int i = 1; i < argc; i++) {
        char op = argv[i][0], key[8] = "", into[17] = "";
        int il = 0;
        memset(&c, 0, sizeof c);
        memset(c.name1, ' ', 8);
        c.name1[0] = argv[i][2];
        memset(c.flags, ' ', 40);
        sscanf(argv[i] + 4, "%7[^:]:%d", key, &il);
        if (op == 'R' || op == 'H') {
            if (op == 'H') memcpy(c.flags, "UPDATE", 6);
            c.len = il;
            GGCREAD(&c, key, 4, into, il);
        } else if (op == 'W') {
            char from[17] = "K002BRAVO   0099";
            memcpy(from, key, 4);
            GGCREWR(&c, from, 16);
        } else {
            if (op == 'T') { memcpy(c.flags, "TOKEN", 5); c.num = 9; }
            GGCUNLK(&c);
        }
    }
    return 0;
}
"""


def _ev(event, **kw):
    return {"event": event, "program": "P", **kw}


def _read(resp, key, file="F", **kw):
    return _ev("READ", file=file, ridfld=key, resp=resp, **kw)


def _rec(text):  # the case files' spelling of an area (SPEC 6.1 text)
    return {"length": len(text), "text": text}


_B2, _B1 = "K002BRAVO   0020", "K001ALPHA   0010"
_WANT = [
    _read("LENGERR", "K002", length=16, data=None),  # resp2 11 is not asserted
    _read("NORMAL", "K002", length=16, data=_rec(_B2)),
    _read("NOTFND", "K009", resp2=80, data=None),
    _ev("REWRITE", file="F", data=_rec("K002BRAVO   0099"), resp="INVREQ", resp2=30),  # nothing held
    _ev("UNLOCK", file="F", resp="NORMAL"),  # nothing held: no action
    _read("NORMAL", "K002", update=True, length=16, data=_rec(_B2)),
    _read("INVREQ", "K001", update=True, resp2=28, data=None),
    _ev("REWRITE", file="F", data=_rec("K002BRAVO   0099"), resp="NORMAL"),
    _read("NORMAL", "K002", length=16, data=_rec("K002BRAVO   0099")),
    _read("NORMAL", "K001", update=True, length=16, data=_rec(_B1)),
    _ev("UNLOCK", file="F", resp="NORMAL"),
    _ev("REWRITE", file="F", data=_rec("K001BRAVO   0099"), resp="INVREQ", resp2=30),  # the UNLOCK released it
    _ev("UNLOCK", file="F", resp="INVREQ", resp2=47),  # a token matching none
    _read("FILENOTFOUND", "K001", file="Z", resp2=1, data=None),  # IBM: RESP2 1, the file is not defined to CICS (X75)
    _ev("REWRITE", file="Z", data=_rec("K001BRAVO   0099"), resp="FILENOTFOUND", resp2=1),
]


def _events(tmp_path):
    (tmp_path / "f.dat").write_bytes((_B1 + _B2).encode("latin-1"))
    (tmp_path / "files.cfg").write_text(f"F {tmp_path / 'f.dat'} 16 0 4\n", encoding="ascii")
    _run_stub(_stub(tmp_path, _MAIN), tmp_path, *_OPS)
    return runner._cobol_events(tmp_path / "out", "P")


def _log(events):
    task = {"seq": 1, "transid": "T", "program": "P", "termid": "T001", "at": "2026-03-02T10:00:00",
            "trigger": {"kind": "terminal", "step": 0}, "eibaid": "ENTER", "eibcalen": 0, "commarea": None,
            "events": events, "end": "normal"}  # fmt: skip
    return {"tasks": [task], "final": {}}


def _verdict(expected, actual):
    return cc.compare(_log(expected), _log(actual), runner.COBOL_CAPS, cc.Context(layouts={}, map_fields={}))


@needs_cc
def test_the_stub_records_read_rewrite_and_unlock_with_their_spec_keys(tmp_path):
    got = _events(tmp_path)
    assert [(e["event"], e["resp"]) for e in got] == [(e["event"], e["resp"]) for e in _WANT]
    assert got[1]["data"] == cc.RawArea(_B2.encode(), "latin-1") and got[1]["length"] == 16 and "update" not in got[1]
    assert "data" in got[0] and got[0]["data"] is None and "resp2" not in got[0]  # LENGERR: length only
    assert got[6]["resp2"] == 28 and got[5]["update"] is True
    assert got[11]["data"] == cc.RawArea(b"K001BRAVO   0099", "latin-1") and got[11]["resp2"] == 30
    assert got[12] == {"event": "UNLOCK", "program": "P", "file": "F", "resp": "INVREQ", "resp2": 47}
    v = _verdict(_WANT, got)
    assert v.status == "pass", v


@needs_cc
def test_the_cobol_leg_compares_every_key_and_each_mismatch_fails(tmp_path):
    got = _events(tmp_path)
    for n, ev in enumerate(_WANT):
        for key, val in ev.items():
            if key in ("event", "program", "file"):
                continue
            bad = [dict(e) for e in _WANT]
            bad[n][key] = (
                "INVREQ" if key == "resp" and val != "INVREQ" else "NORMAL" if key == "resp" else
                "zz" if key == "ridfld" else (not val) if key == "update" else val + 1 if isinstance(val, int) else _rec("?")
            )  # fmt: skip
            assert _verdict(bad, got).status != "pass", (n, key)
