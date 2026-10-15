"""#5079 (register X57): READQ TD / DELETEQ TD on an intrapartition transient-data queue (IBM, CICS TS 6.x, EXEC CICS READQ TD:
"Each READQ TD consumes the record it reads"; QZERO (23) for an empty queue, QIDERR (44) for a queue that cannot be found,
LENGERR (22) for a record longer than LENGTH or a LENGTH of zero (the record is still read) or below zero (the queue is not read),
LENGTH set to the record's own length; EXEC CICS DELETEQ TD: all the data of an intrapartition queue, INVREQ (16) for an
extrapartition one), run on the stub (ggcics.c) and on CicsTask over one operation list.

W:queue:text writes a record (WRITEQ TD FROM LENGTH(its length)), R:queue:n reads INTO an 8-byte area with LENGTH(n), D:queue deletes."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cics_runtimes import _cics_task, _run_stub, _stub, _stub_base_env, needs_cc, needs_javac  # noqa: E402

_CFG = "AAAA INTRA\nBBBB INTRA\nXXXX EXTRA\n"  # CCCC is not defined
_OPS = (
    "R:AAAA:8",  # an empty queue: QZERO
    "W:AAAA:one", "W:AAAA:two", "W:BBBB:bee",
    "R:AAAA:8", "R:BBBB:8", "R:BBBB:8", "R:AAAA:8", "R:AAAA:8",  # first in first out, a queue each, a read consumes
    "W:AAAA:abcdefghij", "R:AAAA:4", "R:AAAA:8",  # a record longer than LENGTH: truncated, LENGERR, and lost
    "W:AAAA:xyz", "R:AAAA:0", "R:AAAA:8",  # LENGTH 0: LENGERR, and the record is read
    "W:AAAA:keep", "R:AAAA:-1", "R:AAAA:8",  # LENGTH below zero: LENGERR, and the queue is not read
    "W:AAAA:p", "W:AAAA:q", "D:AAAA", "R:AAAA:8",  # DELETEQ empties the queue
    "W:AAAA:after", "R:AAAA:8",  # and the queue goes on being written
    "D:CCCC", "R:CCCC:8", "W:CCCC:z", "D:XXXX", "D:BBBB", "W:XXXX:e",  # undefined: QIDERR; extrapartition DELETEQ: INVREQ
    "W:AAAA:", "R:AAAA:8",  # an empty record: NORMAL, length 0
    "W:AAAA:12345678", "R:AAAA:8", "W:AAAA:123456789", "R:AAAA:9",  # a record as long as INTO, then LENGTH past INTO
)  # fmt: skip
_WANT = [
    "R:AAAA:8 resp=23 len=-1 into=........",
    "W:AAAA:one resp=0", "W:AAAA:two resp=0", "W:BBBB:bee resp=0",
    "R:AAAA:8 resp=0 len=3 into=one.....",
    "R:BBBB:8 resp=0 len=3 into=bee.....",
    "R:BBBB:8 resp=23 len=-1 into=........",
    "R:AAAA:8 resp=0 len=3 into=two.....",
    "R:AAAA:8 resp=23 len=-1 into=........",
    "W:AAAA:abcdefghij resp=0",
    "R:AAAA:4 resp=22 len=10 into=abcd....",
    "R:AAAA:8 resp=23 len=-1 into=........",
    "W:AAAA:xyz resp=0",
    "R:AAAA:0 resp=22 len=3 into=........",
    "R:AAAA:8 resp=23 len=-1 into=........",
    "W:AAAA:keep resp=0",
    "R:AAAA:-1 resp=22 len=-1 into=........",
    "R:AAAA:8 resp=0 len=4 into=keep....",
    "W:AAAA:p resp=0", "W:AAAA:q resp=0", "D:AAAA resp=0",
    "R:AAAA:8 resp=23 len=-1 into=........",
    "W:AAAA:after resp=0",
    "R:AAAA:8 resp=0 len=5 into=after...",
    "D:CCCC resp=44", "R:CCCC:8 resp=44 len=-1 into=........", "W:CCCC:z resp=44", "D:XXXX resp=16", "D:BBBB resp=0",
    "W:XXXX:e resp=0",
    "W:AAAA: resp=0",
    "R:AAAA:8 resp=0 len=0 into=........",
    "W:AAAA:12345678 resp=0",
    "R:AAAA:8 resp=0 len=8 into=12345678",
    "W:AAAA:123456789 resp=0",
    "R:AAAA:9 resp=REFUSED",  # a record moved past INTO: refused by name (X57, X6), on both runtimes
]  # fmt: skip

_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCWRTD(gg_cics *c, char *from);
int GGCRDTD(gg_cics *c, char *into, int intolen);
int GGCDLTD(gg_cics *c);
int main(int argc, char **argv) {
    gg_cics c;
    for (int i = 1; i < argc; i++) {
        char q[5] = "", text[64] = "", into[9] = "........";
        memset(&c, 0, sizeof c);
        memset(c.qname, ' ', 16);
        memcpy(c.qname, argv[i] + 2, 4);
        if (argv[i][0] == 'W') {
            strcpy(text, argv[i] + 7);
            c.len = (int)strlen(text);
            GGCWRTD(&c, text);
            printf("%s resp=%d\n", argv[i], c.resp);
        } else if (argv[i][0] == 'D') {
            GGCDLTD(&c);
            printf("%s resp=%d\n", argv[i], c.resp);
        } else {
            c.len = atoi(argv[i] + 7);
            int max = c.len;
            fflush(stdout);
            GGCRDTD(&c, into, 8);
            printf("%s resp=%d len=%d into=%s\n", argv[i], c.resp, (c.resp == 0 || (c.resp == 22 && max >= 0)) ? c.len : -1, into);
        }
        (void)q;
    }
    return 0;
}
"""

_JAVA = """
        CicsTask t = new CicsTask("T", "ENTER", null, null)
                .withTdQueues(java.util.Set.of("AAAA", "BBBB", "XXXX"))
                .withTdQueueTypes(java.util.Map.of("AAAA", "INTRA", "BBBB", "INTRA", "XXXX", "EXTRA"));
        for (String op : new String[] {%s}) {
            String[] p = op.split(":", 3);
            if (p[0].equals("W")) {
                System.out.println(op + " resp=" + t.writeqTd(p[1], p[2]));
            } else if (p[0].equals("D")) {
                System.out.println(op + " resp=" + t.deleteqTd(p[1]));
            } else {
                CicsTask.TdResult r = t.readqTd(p[1], Integer.parseInt(p[2]));
                String into = "........";
                if (r.data() != null) {
                    if (r.data().length() > 8) {
                        throw new UnsupportedOperationException("a record moved past INTO");
                    }
                    into = r.data() + into.substring(r.data().length());
                }
                System.out.println(op + " resp=" + r.resp() + " len=" + r.length() + " into=" + into);
            }
        }"""


def _cut(ops: tuple[str, ...]) -> tuple[tuple[str, ...], list[str]]:
    """The operations a run completes: the last one is refused (its line says so), which stops the task."""
    return ops[:-1], _WANT[:-1]


@needs_cc
def test_the_stub_reads_a_transient_data_queue_first_in_first_out_and_destructively(tmp_path):
    (tmp_path / "tdqueues.cfg").write_text(_CFG, encoding="ascii")
    ops, want = _cut(_OPS)
    assert _run_stub(_stub(tmp_path, _MAIN), tmp_path, *ops) == want


@needs_javac
def test_cics_task_reads_a_transient_data_queue_as_the_stub_does(tmp_path):
    ops, want = _cut(_OPS)
    out = _cics_task(tmp_path, _JAVA % ", ".join(f'"{o}"' for o in ops)).splitlines()
    assert out == want


@needs_cc
def test_the_stub_refuses_a_record_moved_past_into_and_an_extrapartition_read_by_name(tmp_path):
    (tmp_path / "tdqueues.cfg").write_text(_CFG + "IIII REMOTE\n", encoding="ascii")
    exe = _stub(tmp_path, _MAIN)
    for ops, said in ((("W:AAAA:123456789", "R:AAAA:9"), "a record moved past INTO"),
                      (("R:XXXX:8",), "extrapartition queue"), (("R:IIII:8",), "TYPE is not INTRA"),
                      (("D:IIII",), "TYPE is not INTRA or EXTRA")):  # fmt: skip
        (tmp_path / "out").mkdir(exist_ok=True)
        env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out")}
        proc = subprocess.run([str(exe), *ops], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        assert proc.returncode != 0 and said in proc.stderr + proc.stdout, (ops, proc.stderr)
        assert "not modelled" in proc.stderr + proc.stdout


@needs_javac
def test_cics_task_refuses_the_same_reads_by_name(tmp_path):
    body = """
        CicsTask t = new CicsTask("T", "ENTER", null, null).withTdQueues(java.util.Set.of("XXXX", "IIII"))
                .withTdQueueTypes(java.util.Map.of("XXXX", "EXTRA", "IIII", "REMOTE"));
        for (String q : new String[] {"XXXX", "IIII"}) {
            try {
                t.readqTd(q, 8);
                System.out.println("read " + q + " ran");
            } catch (UnsupportedOperationException e) {
                System.out.println("read " + q + " refused: " + e.getMessage());
            }
        }
        try {
            t.deleteqTd("IIII");
            System.out.println("delete IIII ran");
        } catch (UnsupportedOperationException e) {
            System.out.println("delete IIII refused: " + e.getMessage());
        }
        System.out.println("delete XXXX " + t.deleteqTd("XXXX"));"""
    out = _cics_task(tmp_path, body).splitlines()
    assert out[0].startswith("read XXXX refused:") and "extrapartition" in out[0] and "not modelled" in out[0]
    assert out[1].startswith("read IIII refused:") and "not modelled" in out[1]
    assert out[2].startswith("delete IIII refused:") and "not modelled" in out[2]
    assert out[3] == "delete XXXX 16"


@needs_javac
def test_a_queue_with_no_csd_is_defined_and_intrapartition(tmp_path):
    body = """
        CicsTask t = new CicsTask("T", "ENTER", null, null);
        System.out.println(t.readqTd("ANYQ", 8).resp() + " " + t.deleteqTd("ANYQ") + " " + t.writeqTd("ANYQ", "hi"));
        CicsTask.TdResult r = t.readqTd("ANYQ", 8);
        System.out.println(r.resp() + " " + r.length() + " " + r.data());"""
    assert _cics_task(tmp_path, body).splitlines() == ["23 0 0", "0 2 hi"]


@needs_cc
def test_a_queue_with_no_csd_is_defined_and_intrapartition_on_the_stub_too(tmp_path):
    assert _run_stub(_stub(tmp_path, _MAIN), tmp_path, "R:ANYQ:8", "D:ANYQ", "W:ANYQ:hi", "R:ANYQ:8") == [
        "R:ANYQ:8 resp=23 len=-1 into=........",
        "D:ANYQ resp=0",
        "W:ANYQ:hi resp=0",
        "R:ANYQ:8 resp=0 len=2 into=hi......",
    ]


@needs_cc
def test_the_stub_keeps_a_queue_across_runs_of_one_conversation(tmp_path):
    """A transient-data queue outlives the task that writes it: a second process on the same region reads the record."""
    (tmp_path / "tdqueues.cfg").write_text(_CFG, encoding="ascii")
    exe = _stub(tmp_path, _MAIN)
    assert _run_stub(exe, tmp_path, "W:AAAA:one", "W:AAAA:two") == ["W:AAAA:one resp=0", "W:AAAA:two resp=0"]
    assert _run_stub(exe, tmp_path, "R:AAAA:8") == ["R:AAAA:8 resp=0 len=3 into=one....."]
    assert _run_stub(exe, tmp_path, "R:AAAA:8", "R:AAAA:8") == ["R:AAAA:8 resp=0 len=3 into=two.....",
                                                               "R:AAAA:8 resp=23 len=-1 into=........"]  # fmt: skip


@needs_cc
def test_the_stub_records_the_events_the_comparison_reads(tmp_path):
    (tmp_path / "tdqueues.cfg").write_text(_CFG, encoding="ascii")
    _run_stub(_stub(tmp_path, _MAIN), tmp_path, "W:AAAA:abc", "R:AAAA:2", "R:AAAA:8", "R:CCCC:8")
    lines = (tmp_path / "out" / "events.txt").read_text().splitlines()
    assert lines == ["001 WRITEQ-TD pgm= queue=AAAA len=3 resp=0",
                     "002 READQ-TD pgm= queue=41414141 resp=22 len=3 copied=2",
                     "003 READQ-TD pgm= queue=41414141 resp=23 len=-1 copied=0",
                     "004 READQ-TD pgm= queue=43434343 resp=44 len=-1 copied=0"]  # fmt: skip
    assert (tmp_path / "out" / "002.bin").read_bytes() == b"ab"


@needs_javac
def test_cics_task_records_the_same_events(tmp_path):
    body = """
        CicsTask t = new CicsTask("T", "ENTER", null, null).withTdQueues(java.util.Set.of("AAAA"));
        t.writeqTd("AAAA", "abc");
        t.readqTd("AAAA", 2);
        t.readqTd("AAAA", 8);
        t.readqTd("CCCC", 8);
        for (java.util.Map<String, Object> e : t.events()) System.out.println(e);"""
    assert _cics_task(tmp_path, body).splitlines() == [
        "{event=WRITEQ-TD, queue=AAAA, text=abc, resp=0}",
        "{event=READQ-TD, queue=AAAA, resp=LENGERR, data=ab}",
        "{event=READQ-TD, queue=AAAA, resp=QZERO, data=null}",
        "{event=READQ-TD, queue=CCCC, resp=QIDERR, data=null}",
    ]
