"""#6262 (slice E): the C stub's WRITE / DELETE events (SPEC 6.2) and their comparison.

ggcics.c's file_event records a WRITE or DELETE with the RIDFLD on entry (`rid=`, left out for a DELETE of the held or the
token's record), `generic=1`, RESP2 where the command is not NORMAL and, for a WRITE, the FROM bytes. The stub runs the Java
leg's command sequence (test_write_delete_events_6262.py) and its events are held to the same expected log. A stub sees only
KEYLENGTH, so a generic DELETE logs the KEYLENGTH-byte prefix: it is run apart, on a file whose key is longer than its RIDFLD.
"""

import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402
import test_browse_events_6262 as browse  # noqa: E402
import test_cics_runtimes as rt  # noqa: E402
import test_write_delete_events_6262 as java_leg  # noqa: E402

_CTX = cc.Context(layouts={}, map_fields={})
_GENERIC = 6  # the index of the generic DELETE in the Java leg's expected log

_MAIN = r"""
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCWRIT(gg_cics *c, char *rid, int kl, char *from, int fl); int GGCDELT(gg_cics *c, char *rid, int kl);
int GGCREAD(gg_cics *c, char *rid, int kl, char *into, int il);
int main(int argc, char **argv) {
    gg_cics c;
    char rid[4], into[16];
    int token = 0;
    memset(&c, 0, sizeof c);
    for (int i = 1; i < argc; i++) {   /* OP FILE KEY(4) KEYLENGTH(1) FROM(16); FILE is H (HCBR), N (NOFILE) or E (ESDS) */
        char *a = argv[i];
        memset(c.name1, ' ', 8);
        if (a[1] == 'H') memcpy(c.name1, "HCBR", 4);
        else if (a[1] == 'E') memcpy(c.name1, "ESDS", 4);
        else memcpy(c.name1, "NOFILE", 6);
        memset(c.flags, ' ', 40);
        c.len = 16;
        memcpy(rid, a + 2, 4);
        int kl = a[6] - '0';
        if (a[0] == 'W') GGCWRIT(&c, rid, 4, a + 7, 16);
        if (a[0] == 'D') GGCDELT(&c, rid, 4);
        if (a[0] == 'G') { memcpy(c.flags, "GENERIC", 7); GGCDELT(&c, rid, kl); }
        if (a[0] == 'H') { memcpy(c.flags, "HELD", 4); GGCDELT(&c, c.flags, 0); }
        if (a[0] == 'U') { memcpy(c.flags, "UPDATE", 6); GGCREAD(&c, rid, 4, into, 16); }
        if (a[0] == 'T') { memcpy(c.flags, "UPDATE TOKEN", 12); GGCREAD(&c, rid, 4, into, 16); token = c.num; }
        if (a[0] == 'K') { memcpy(c.flags, "TOKEN", 5); c.num = token; GGCDELT(&c, c.flags, 0); }
    }
    return 0;
}
"""


def _setup(work: Path, key_length: int, plan: bool = True) -> None:
    (work / "hcbr.dat").write_bytes(b"".join(r.encode("latin-1") for r in java_leg.REC.values()))
    (work / "esds.dat").write_bytes(b"aaaabbbb")
    (work / "files.cfg").write_text(
        f"HCBR {work / 'hcbr.dat'} 16 0 {key_length}\nESDS {work / 'esds.dat'} 4 0 0 ESDS\n", encoding="ascii"
    )
    if plan:
        (work / "faults.cfg").write_text("".join(ln + "\n" for ln in java_leg._PLAN), encoding="ascii")


def _ops(rows) -> list[str]:
    out = []
    for op, key, _ in rows:
        code = {"U": "T" if key == "K005" else "U", "I": "G"}.get(
            op, op
        )  # I: a generic DELETE whose KEYLENGTH is the key
        out.append(f"{code}H{key}4{java_leg.NEW.get(key, '')}")
    return out


def _run(work: Path, *ops: str) -> list[dict]:
    rt._run_stub(rt._stub(work, _MAIN), work, *ops)
    return runner._cobol_events(work / "out", "HCBR")


def _compare(expected: list[dict], events: list[dict]) -> cc.Verdict:
    return cc.compare(browse._log(expected), browse._log(events), runner.COBOL_CAPS, _CTX)


def _without_reads(events: list[dict]) -> list[dict]:
    return [e for e in events if e["event"] != "READ"]  # a READ UPDATE is the Java leg's event-free `U`


@rt.needs_cc
def test_the_stub_records_each_write_and_delete_form_as_the_java_leg_does(tmp_path):
    _setup(tmp_path, 4)
    rows = [r for i, r in enumerate(java_leg._OPS) if r[0] != "G"]
    events = _without_reads(_run(tmp_path, *_ops(rows)))
    expected = [e for i, e in enumerate(java_leg._EXPECTED) if i != _GENERIC]
    assert len(events) == len(expected)
    held = events[-3:]
    assert all("ridfld" not in e for e in held)  # a held or token DELETE has no RIDFLD
    v = _compare(expected, events)
    assert v.status == "pass", v.reason


@rt.needs_cc
def test_every_stub_write_and_delete_key_is_compared(tmp_path):
    _setup(tmp_path, 4)
    rows = [r for r in java_leg._OPS if r[0] != "G"]
    events = _without_reads(_run(tmp_path, *_ops(rows)))
    expected = [e for i, e in enumerate(java_leg._EXPECTED) if i != _GENERIC]
    for i, key, bad in (
        (0, "data", cc.RawArea(java_leg.NEW["K004"].encode(cc.EBCDIC), cc.EBCDIC)),
        (0, "ridfld", "K999".encode(cc.EBCDIC)),
        (1, "resp", "NORMAL"),
        (2, "resp2", 61),
        (5, "resp2", 81),
    ):
        changed = [dict(e) for e in events]
        changed[i][key] = bad
        assert _compare(expected, changed).status == "fail", (i, key)
    assert _compare(expected, [*events[:4], {**events[4], "generic": True}, *events[5:]]).status == "fail"


@rt.needs_cc
def test_a_stub_generic_delete_records_its_prefix_and_generic(tmp_path):
    _setup(tmp_path, 8, plan=False)  # the key is longer than the RIDFLD, so a 4-byte prefix is a valid KEYLENGTH
    events = _run(tmp_path, "GHK0014")
    (generic,) = events
    assert generic["generic"] is True and generic["resp"] == "NORMAL"
    expected = [java_leg._EXPECTED[_GENERIC]]
    v = _compare(expected, events)
    assert v.status == "pass", v.reason
    assert (tmp_path / "hcbr.dat").read_bytes() == java_leg.REC["K002"].encode("latin-1")
    assert _compare(expected, [{k: v for k, v in generic.items() if k != "generic"}]).status == "fail"


@rt.needs_cc
def test_a_stub_delete_of_an_undefined_file_and_of_an_esds_names_the_condition(tmp_path):
    _setup(tmp_path, 4, plan=False)
    nofile, esds, esds_generic = _run(tmp_path, "DNK0014", "DEK0014", "GEK0011")
    assert (nofile["resp"], nofile["resp2"], nofile["file"]) == ("FILENOTFOUND", 1, "NOFILE")
    assert nofile["ridfld"] == "K001".encode(cc.EBCDIC)
    assert (esds["resp"], esds["resp2"]) == ("INVREQ", 21) and "ridfld" not in esds  # an ESDS has no key
    assert (esds_generic["resp"], esds_generic["resp2"]) == ("INVREQ", 22) and esds_generic["generic"] is True


def test_both_legs_support_the_write_and_delete_events_the_expected_log_names():
    log = browse._log(java_leg._EXPECTED)
    assert cc.blockers(log, runner.JAVA_CAPS) == []
    assert cc.blockers(log, runner.COBOL_CAPS) == []
