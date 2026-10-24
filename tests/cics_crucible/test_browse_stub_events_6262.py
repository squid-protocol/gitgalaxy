"""#6262 (slice A): the C stub's STARTBR / READNEXT / READPREV / ENDBR events (SPEC 6.2) and their comparison.

ggcics_filecontrol.c's browse_event and ENDBR line record the key on entry, STARTBR's mode, RESP2 where the command is
not NORMAL, and a browse read's length and bytes. The stub runs the same command sequence as the Java leg's test
(test_browse_events_6262.py) and its events are held to the same expected log, so the two legs agree on every key.
"""

import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402
import test_browse_events_6262 as java_leg  # noqa: E402
import test_cics_runtimes as rt  # noqa: E402

_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCSTBR(gg_cics *c, char *rid, int kl); int GGCRDNX(gg_cics *c, char *rid, int kl, char *into, int il);
int GGCRDPV(gg_cics *c, char *rid, int kl, char *into, int il); int GGCENBR(gg_cics *c);
int main(int argc, char **argv) {
    gg_cics c;
    char rid[4], into[16];
    memset(&c, 0, sizeof c);
    memset(c.name1, ' ', 8);
    memcpy(c.name1, "HCBR", 4);
    for (int i = 1; i < argc; i++) {   /* OP:KEY:INTO-LENGTH */
        char op = argv[i][0];
        memset(c.flags, ' ', 40);
        memcpy(rid, argv[i] + 2, 4);
        memset(into, '.', sizeof into);
        int il = atoi(argv[i] + 7);
        if (op == 'S') GGCSTBR(&c, rid, 4);
        if (op == 'Q') { memcpy(c.flags, "EQUAL", 5); GGCSTBR(&c, rid, 4); }
        if (op == 'N') GGCRDNX(&c, rid, 4, into, il);
        if (op == 'P') GGCRDPV(&c, rid, 4, into, il);
        if (op == 'X') GGCENBR(&c);
    }
    return 0;
}
"""


@rt.needs_cc
def test_the_stub_records_browse_commands_as_the_java_leg_does(tmp_path):
    (tmp_path / "hcbr.dat").write_bytes(b"".join(r.encode("latin-1") for r in java_leg.REC.values()))
    (tmp_path / "files.cfg").write_text(f"HCBR {tmp_path / 'hcbr.dat'} 16 0 4\n", encoding="ascii")
    ops = [f"{op}:{key}:{n}" for op, key, n, _ in java_leg._OPS if op.isupper()]
    rt._run_stub(rt._stub(tmp_path, _MAIN), tmp_path, *ops)
    events = runner._cobol_events(tmp_path / "out", "HCBR")
    assert len(events) == len(java_leg._EXPECTED)
    lengerr = events[6]
    assert lengerr["resp"] == "LENGERR" and "resp2" not in lengerr and lengerr["data"] is None  # RESP only (SPEC 2)
    v = cc.compare(
        java_leg._log(java_leg._EXPECTED),
        java_leg._log(events),
        runner.COBOL_CAPS,
        cc.Context(layouts={}, map_fields={}),
    )
    assert v.status == "pass", v.reason
    wrong_mode = [{**events[0], "mode": "EQUAL"}, *events[1:]]
    assert (
        cc.compare(
            java_leg._log(java_leg._EXPECTED),
            java_leg._log(wrong_mode),
            runner.COBOL_CAPS,
            cc.Context(layouts={}, map_fields={}),
        ).status
        == "fail"
    )


def test_both_legs_support_the_browse_events_the_expected_log_names():
    log = java_leg._log(java_leg._EXPECTED)
    assert cc.blockers(log, runner.JAVA_CAPS) == []
    assert cc.blockers(log, runner.COBOL_CAPS) == []


def test_an_rba_browse_event_is_left_unmodelled_not_misread_as_a_key(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "events.txt").write_text("001 STARTBR pgm=HCBR file=HCBR rba=0 resp=0\n", encoding="latin-1")
    (ev,) = runner._cobol_events(out, "HCBR")
    assert isinstance(ev["ridfld"], cc.Unmodelled) and "mode" not in ev
