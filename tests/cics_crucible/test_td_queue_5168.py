"""#5168 (register X61): the transient-data queue commands past X57's intrapartition READQ / DELETEQ, run on the stub (ggcics.c) and on
CicsTask over one operation list per scenario (IBM, CICS TS 6.x, READQ TD / TDQUEUE definitions):

* READQ TD SET(ptr): the record in a block, valid to the next READQ TD;
* extrapartition queues: closed (OPENTIME DEFERRED) NOTOPEN, open for output INVREQ, open for input read first in first out from
  the records a case seeds ("td"), QZERO at the end;
* RECOVSTATUS(LOGICAL): SYNCPOINT ROLLBACK puts a queue back as it was at the end of the last unit of work (reads, writes and
  deletes alike); NO commits at once; PHYSICAL refuses a rollback by name;
* INDIRECT queues route to INDIRECTNAME; no INDIRECTNAME, an undefined target, a loop, REMOTE: refused by name;
* TRANSID with a TRIGGERLEVEL a write reaches (automatic task initiation): refused by name.

Operations: W:queue:text writes, R:queue:n reads INTO an 8-byte area with LENGTH(n), P:queue reads SET, D:queue deletes, S is a
SYNCPOINT, B a SYNCPOINT ROLLBACK."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cics_runtimes import _cics_task, _stub, _stub_base_env, needs_cc, needs_javac  # noqa: E402

_E = "EXTRA TYPEFILE=INPUT OPENTIME=INITIAL"
_L = "INTRA RECOVSTATUS=LOGICAL"
R8 = "into=........"

# name: (queues {name: "TYPE KEY=VALUE ..."} or None, seed {queue: [records]}, operations, expected lines)
_SCENARIOS: dict[str, tuple[dict[str, str] | None, dict[str, list[str]], list[str], list[str]]] = {
    "set": (
        {"AAAA": "INTRA"}, {},
        ["W:AAAA:hello", "P:AAAA", "P:AAAA", "W:AAAA:abcdefghij", "P:AAAA"],
        ["W:AAAA:hello resp=0", "P:AAAA resp=0 len=5 block=hello", "P:AAAA resp=23 len=-1 block=-",
         "W:AAAA:abcdefghij resp=0", "P:AAAA resp=0 len=10 block=abcdefghij"],
    ),
    "seeded intrapartition": (
        {"AAAA": "INTRA", "BBBB": "INTRA"}, {"AAAA": ["s1", "s2"]},
        ["R:AAAA:8", "W:AAAA:s3", "R:AAAA:8", "R:AAAA:8", "R:BBBB:8"],
        ["R:AAAA:8 resp=0 len=2 into=s1......", "W:AAAA:s3 resp=0", "R:AAAA:8 resp=0 len=2 into=s2......",
         "R:AAAA:8 resp=0 len=2 into=s3......", f"R:BBBB:8 resp=23 len=-1 {R8}"],
    ),
    "seeded with no csd": (
        None, {"ANYQ": ["a"]}, ["R:ANYQ:8", "R:ANYQ:8"],
        ["R:ANYQ:8 resp=0 len=1 into=a.......", f"R:ANYQ:8 resp=23 len=-1 {R8}"],
    ),
    "extrapartition input": (
        {"XXXX": _E}, {"XXXX": ["one", "twotwotwo"]},
        ["R:XXXX:8", "R:XXXX:4", "R:XXXX:8", "D:XXXX"],
        ["R:XXXX:8 resp=0 len=3 into=one.....", "R:XXXX:4 resp=22 len=9 into=twot....",
         f"R:XXXX:8 resp=23 len=-1 {R8}", "D:XXXX resp=16"],
    ),
    "extrapartition states": (
        {"YYYY": "EXTRA TYPEFILE=OUTPUT OPENTIME=INITIAL", "ZZZZ": "EXTRA TYPEFILE=INPUT OPENTIME=DEFERRED",
         "OOOO": "EXTRA TYPEFILE=OUTPUT OPENTIME=DEFERRED", "IIII": "EXTRA TYPEFILE=INPUT"},
        {"ZZZZ": ["x"], "IIII": ["y"]},
        ["R:YYYY:8", "R:ZZZZ:8", "R:OOOO:8", "R:IIII:8", "R:IIII:-1", "R:IIII:8"],
        [f"R:YYYY:8 resp=16 len=-1 {R8}", f"R:ZZZZ:8 resp=19 len=-1 {R8}", f"R:OOOO:8 resp=19 len=-1 {R8}",
         "R:IIII:8 resp=0 len=1 into=y.......", f"R:IIII:-1 resp=22 len=-1 {R8}", f"R:IIII:8 resp=23 len=-1 {R8}"],
    ),
    "logical rollback": (
        {"LLLL": _L, "NNNN": "INTRA RECOVSTATUS=NO"}, {"LLLL": ["old"]},
        ["R:LLLL:8", "W:LLLL:new1", "W:NNNN:n1", "B", "R:LLLL:8", "R:NNNN:8", "R:LLLL:8", "D:LLLL", "B", "R:LLLL:8"],
        ["R:LLLL:8 resp=0 len=3 into=old.....", "W:LLLL:new1 resp=0", "W:NNNN:n1 resp=0", "B",
         "R:LLLL:8 resp=0 len=3 into=old.....", "R:NNNN:8 resp=0 len=2 into=n1......", f"R:LLLL:8 resp=23 len=-1 {R8}",
         "D:LLLL resp=0", "B", "R:LLLL:8 resp=0 len=3 into=old....."],
    ),
    "logical commit": (
        {"LLLL": _L}, {},
        ["W:LLLL:c1", "S", "R:LLLL:8", "R:LLLL:8"],
        ["W:LLLL:c1 resp=0", "S", "R:LLLL:8 resp=0 len=2 into=c1......", f"R:LLLL:8 resp=23 len=-1 {R8}"],
    ),
    "physical committed": (
        {"PPPP": "INTRA RECOVSTATUS=PHYSICAL"}, {},
        ["W:PPPP:x", "S", "R:PPPP:8"],
        ["W:PPPP:x resp=0", "S", "R:PPPP:8 resp=0 len=1 into=x......."],
    ),
    "physical rollback": ({"PPPP": "INTRA RECOVSTATUS=PHYSICAL"}, {}, ["W:PPPP:x", "B"], ["W:PPPP:x resp=0", "REFUSED"]),
    "indirect": (
        {"AAAA": "INTRA", "IIII": "INDIRECT INDIRECTNAME=JJJJ", "JJJJ": "INDIRECT INDIRECTNAME=AAAA"}, {},
        ["W:IIII:via", "R:AAAA:8", "W:JJJJ:jay", "R:IIII:8", "W:AAAA:q", "D:IIII", "R:AAAA:8"],
        ["W:IIII:via resp=0", "R:AAAA:8 resp=0 len=3 into=via.....", "W:JJJJ:jay resp=0",
         "R:IIII:8 resp=0 len=3 into=jay.....", "W:AAAA:q resp=0", "D:IIII resp=0", f"R:AAAA:8 resp=23 len=-1 {R8}"],
    ),
    "indirect without a name": ({"IIII": "INDIRECT"}, {}, ["R:IIII:8"], ["REFUSED"]),
    "indirect to an undefined queue": ({"IIII": "INDIRECT INDIRECTNAME=GONE"}, {}, ["W:IIII:a"], ["REFUSED"]),
    "indirect loop": (
        {"IIII": "INDIRECT INDIRECTNAME=JJJJ", "JJJJ": "INDIRECT INDIRECTNAME=IIII"}, {}, ["D:IIII"], ["REFUSED"]
    ),
    "remote": ({"RRRR": "REMOTE"}, {}, ["R:RRRR:8"], ["REFUSED"]),
    "extrapartition with no typefile": ({"XXXX": "EXTRA"}, {}, ["R:XXXX:8"], ["REFUSED"]),
    "ati": (
        {"TTTT": "INTRA TRANSID=TRN1 TRIGGERLEVEL=3", "UUUU": "INTRA TRANSID=TRN1 TRIGGERLEVEL=0", "VVVV": "INTRA TRIGGERLEVEL=1"},
        {},
        ["W:TTTT:a", "W:TTTT:b", "W:UUUU:a", "W:UUUU:b", "W:VVVV:v", "R:UUUU:8", "W:TTTT:c"],
        ["W:TTTT:a resp=0", "W:TTTT:b resp=0", "W:UUUU:a resp=0", "W:UUUU:b resp=0", "W:VVVV:v resp=0",
         "R:UUUU:8 resp=0 len=1 into=a.......", "REFUSED"],
    ),
    "write to extrapartition": (
        {"IIII": "EXTRA TYPEFILE=INPUT", "CCCC": "EXTRA TYPEFILE=INPUT OPENTIME=DEFERRED",
         "DDDD": "EXTRA TYPEFILE=OUTPUT OPENTIME=DEFERRED", "OOOO": "EXTRA TYPEFILE=OUTPUT", "NNNN": "EXTRA"},
        {"IIII": ["keep"]},
        ["W:IIII:w", "W:CCCC:w", "W:DDDD:w", "W:OOOO:w", "W:NNNN:w", "R:IIII:8", "D:IIII"],
        ["W:IIII:w resp=16", "W:CCCC:w resp=19", "W:DDDD:w resp=19", "W:OOOO:w resp=0", "W:NNNN:w resp=0",
         "R:IIII:8 resp=0 len=4 into=keep....", "D:IIII resp=16"],
    ),
    "abend backs out logical": (
        {"LLLL": _L, "NNNN": "INTRA RECOVSTATUS=NO", "CCCC": _L}, {"LLLL": ["old"]},
        ["R:LLLL:8", "W:LLLL:new", "W:NNNN:n1", "W:CCCC:c1", "S", "W:CCCC:c2", "W:LLLL:x", "A", "R:LLLL:8", "R:LLLL:8", "R:NNNN:8", "R:CCCC:8",
         "R:CCCC:8"],
        ["R:LLLL:8 resp=0 len=3 into=old.....", "W:LLLL:new resp=0", "W:NNNN:n1 resp=0", "W:CCCC:c1 resp=0", "S",
         "W:CCCC:c2 resp=0", "W:LLLL:x resp=0", "A",
         "R:LLLL:8 resp=0 len=3 into=new.....", f"R:LLLL:8 resp=23 len=-1 {R8}",
         "R:NNNN:8 resp=0 len=2 into=n1......", "R:CCCC:8 resp=0 len=2 into=c1......", f"R:CCCC:8 resp=23 len=-1 {R8}"],
    ),
    "abend with a physical queue": ({"PPPP": "INTRA RECOVSTATUS=PHYSICAL"}, {}, ["W:PPPP:x", "A"], ["W:PPPP:x resp=0", "REFUSED"]),
    "ati default trigger level": ({"VVVV": "INTRA TRANSID=TRN1"}, {}, ["W:VVVV:a"], ["REFUSED"]),
}  # fmt: skip

_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCWRTD(gg_cics *c, char *from);
int GGCRDTD(gg_cics *c, char *into, int intolen);
int GGCRDTS(gg_cics *c, void **slot);
int GGCDLTD(gg_cics *c);
int GGCSYNC(gg_cics *c);
int GGCABND(gg_cics *c);
int main(int argc, char **argv) {
    gg_cics c;
    setvbuf(stdout, NULL, _IONBF, 0);
    for (int i = 1; i < argc; i++) {
        char text[64] = "", into[9] = "........";
        char *a = argv[i];
        memset(&c, 0, sizeof c);
        memset(c.qname, ' ', 16);
        if (a[0] == 'A') {
            memcpy(c.name1, "ABCD    ", 8);
            GGCABND(&c);
            printf("A\n");
            continue;
        }
        if (a[0] == 'S' || a[0] == 'B') {
            if (a[0] == 'B') strcpy(c.flags, "ROLLBACK");
            GGCSYNC(&c);
            printf("%s\n", a);
            continue;
        }
        memcpy(c.qname, a + 2, 4);
        if (a[0] == 'W') {
            strcpy(text, a + 7);
            c.len = (int)strlen(text);
            GGCWRTD(&c, text);
            printf("%s resp=%d\n", a, c.resp);
        } else if (a[0] == 'D') {
            GGCDLTD(&c);
            printf("%s resp=%d\n", a, c.resp);
        } else if (a[0] == 'P') {
            void *p = NULL;
            GGCRDTS(&c, &p);
            if (p) printf("%s resp=%d len=%d block=%.*s\n", a, c.resp, c.len, c.len, (char *)p);
            else printf("%s resp=%d len=-1 block=-\n", a, c.resp);
        } else {
            int max;
            c.len = atoi(a + 7);
            max = c.len;
            GGCRDTD(&c, into, 8);
            printf("%s resp=%d len=%d into=%s\n", a, c.resp, (c.resp == 0 || (c.resp == 22 && max >= 0)) ? c.len : -1, into);
        }
    }
    return 0;
}
"""


def _ops(name: str) -> list[str]:
    return _SCENARIOS[name][2]


def _run_stub_scenario(exe: Path, work: Path, name: str) -> list[str]:
    queues, seed, ops, _ = _SCENARIOS[name]
    if queues is not None:
        (work / "tdqueues.cfg").write_text("".join(f"{q} {queues[q]}\n" for q in sorted(queues)), encoding="ascii")
    for q, records in seed.items():
        qdir = work / "ts" / ("td-" + q.encode("ascii").hex().upper())
        qdir.mkdir(parents=True)
        for i, rec in enumerate(records, 1):
            (qdir / f"{i:06d}.bin").write_bytes(rec.encode("ascii"))
    (work / "out").mkdir(parents=True, exist_ok=True)
    env = {**_stub_base_env(), "GGCICS_DIR": str(work), "GGCICS_OUT": str(work / "out")}
    proc = subprocess.run([str(exe), *ops], env=env, capture_output=True, text=True, check=False)  # noqa: S603
    lines = [x for x in proc.stdout.splitlines() if "not modelled" not in x]
    if proc.returncode != 0:
        assert "not modelled" in proc.stderr + proc.stdout, (name, proc.stderr)
        lines.append("REFUSED")
    return lines


@pytest.fixture(scope="module")
def stub_exe(tmp_path_factory):
    return _stub(tmp_path_factory.mktemp("stub5168"), _MAIN)


@pytest.mark.parametrize("name", list(_SCENARIOS))
@needs_cc
def test_the_stub_runs_each_scenario(name, stub_exe, tmp_path):
    assert _run_stub_scenario(stub_exe, tmp_path, name) == _SCENARIOS[name][3]


def _java_scenario(name: str, queues, seed, ops) -> str:
    quoted = ", ".join(f'"{o}"' for o in ops)
    setup = ["CicsTask.TempStorage ts = new CicsTask.TempStorage();"]
    for q, records in seed.items():
        setup.append(f'ts.seedTd("{q}", java.util.List.of({", ".join(chr(34) + r + chr(34) for r in records)}));')
    chain = ".withTempStorage(ts)"
    if queues is not None:
        names = ", ".join(f'"{q}"' for q in sorted(queues))
        types = ", ".join(f'"{q}", "{queues[q].split()[0]}"' for q in sorted(queues))
        attrs = ", ".join(f'"{q}", "{kv.split("=")[0]}", "{kv.split("=")[1]}"' for q in sorted(queues)
                          for kv in queues[q].split()[1:])  # fmt: skip
        chain += f".withTdQueues(java.util.Set.of({names})).withTdQueueTypes(java.util.Map.of({types}))"
        if attrs:
            chain += f".withTdQueueAttributes({attrs})"
    return f"""
        {{
            System.out.println("== {name}");
            {" ".join(setup)}
            CicsTask t = new CicsTask("T", "ENTER", null, null){chain};
            run: for (String op : new String[] {{{quoted}}}) {{
                String[] p = op.split(":", 3);
                try {{
                    if (op.equals("S")) {{
                        t.syncpoint();
                        System.out.println(op);
                    }} else if (op.equals("A")) {{
                        t.abend("ABCD");
                        System.out.println(op);
                    }} else if (op.equals("B")) {{
                        t.rollback();
                        System.out.println(op);
                    }} else if (p[0].equals("W")) {{
                        System.out.println(op + " resp=" + t.writeqTd(p[1], p[2]));
                    }} else if (p[0].equals("D")) {{
                        System.out.println(op + " resp=" + t.deleteqTd(p[1]));
                    }} else if (p[0].equals("P")) {{
                        CicsTask.TdResult r = t.readqTd(p[1], Integer.MAX_VALUE);
                        String block = "-";
                        if (r.data() != null) {{
                            block = new String(t.storageAt(t.acquireSet("READQ TD", r.data().getBytes()), r.length()));
                        }}
                        System.out.println(op + " resp=" + r.resp() + " len=" + r.length() + " block=" + block);
                    }} else {{
                        CicsTask.TdResult r = t.readqTd(p[1], Integer.parseInt(p[2]));
                        String into = "........";
                        if (r.data() != null) {{
                            into = r.data() + into.substring(r.data().length());
                        }}
                        System.out.println(op + " resp=" + r.resp() + " len=" + r.length() + " into=" + into);
                    }}
                }} catch (UnsupportedOperationException e) {{
                    System.out.println("REFUSED");
                    break run;
                }}
            }}
        }}"""


@pytest.fixture(scope="module")
def java_outputs(tmp_path_factory):
    body = "".join(_java_scenario(n, q, s, o) for n, (q, s, o, _) in _SCENARIOS.items())
    out: dict[str, list[str]] = {}
    for line in _cics_task(tmp_path_factory.mktemp("java5168"), body).splitlines():
        if line.startswith("== "):
            out[line[3:]] = current = []
        else:
            current.append(line)
    return out


@pytest.mark.parametrize("name", list(_SCENARIOS))
@needs_javac
def test_cics_task_runs_each_scenario_as_the_stub_does(name, java_outputs):
    assert java_outputs[name] == _SCENARIOS[name][3]
