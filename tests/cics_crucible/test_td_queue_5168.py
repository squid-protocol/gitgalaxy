"""#5168 (register X61): the transient-data queue commands past X57's intrapartition READQ / DELETEQ, run on the stub (ggcics.c) and on
CicsTask over one operation list per scenario (IBM, CICS TS 6.x, READQ TD / TDQUEUE definitions):

* READQ TD SET(ptr): the record in a block, valid to the next READQ TD;
* extrapartition queues: closed (OPENTIME DEFERRED) NOTOPEN, open for output INVREQ, open for input read first in first out from
  the records a case seeds ("td"), QZERO at the end;
* RECOVSTATUS(LOGICAL): SYNCPOINT ROLLBACK puts a queue back as it was at the end of the last unit of work (reads, writes and
  deletes alike); NO commits at once; PHYSICAL refuses a rollback by name;
* INDIRECT queues route to INDIRECTNAME; no INDIRECTNAME, an undefined target, a loop, REMOTE: refused by name;
* TRANSID with a TRIGGERLEVEL a write reaches (automatic task initiation): refused by name;
* round 3: SET TDQUEUE OPENSTATUS(OPEN 18 / CLOSED 19) and INQUIRE TDQUEUE OPENSTATUS / TYPE (IBM, CICS TS 6.x): the run-time state
  replaces OPENTIME; QIDERR RESP2 1, INVREQ RESP2 8 (invalid CVDA) and 9 (intrapartition); INDIRECT / REMOTE, an invalid CVDA on a
  queue that is not extrapartition, OPEN with no TYPEFILE, OPEN of an input queue already read, and a queue with no TYPE: refused.
* round 5: SET TDQUEUE ENABLESTATUS(ENABLED 23 / DISABLED 24) and INQUIRE TDQUEUE ENABLESTATUS: a disabled queue answers DISABLED
  (84) to READQ, WRITEQ and DELETEQ TD, whatever its type or open state; INVREQ RESP2 10 (invalid CVDA), QIDERR RESP2 1; INDIRECT /
  REMOTE and an invalid CVDA on an undefined queue: refused. The state is not a unit-of-work resource (a rollback keeps it).
* round 7: SET TDQUEUE TRIGGERLEVEL(n) of an intrapartition queue overrides the definition's value (0: automatic task initiation off):
  the write that reaches the level with a TRANSID is refused, the others complete, INQUIRE reads the level back; QIDERR RESP2 1; a
  queue that is not intrapartition, INDIRECT, REMOTE, or a level below zero: refused. A rollback keeps the level.

* IOERR on READQ TD (a planned fault, "READQ-TD"; IBM states no RESP2): "the data record in error is skipped", so an open
  extrapartition input queue loses its next record and nothing reaches INTO / SET. Only an open extrapartition queue consults the
  plan (NOTOPEN, INVREQ, QZERO, LENGERR, QIDERR and DISABLED answer first and do not count); _PLANS names the faults per scenario.
* QBUSY on READQ TD NOSUSPEND (a planned fault, "READQ-TD", no RESP2): a LOGICAL intrapartition queue holding no record answers the
  plan ("another task is writing to or deleting from" it); a queue with a record, or that is not LOGICAL, does not consult it. The
  plan needs NOSUSPEND (N:queue:n; without it IBM suspends the task: refused); QBUSY on an extrapartition queue is refused, as is
  IOERR on a LOGICAL intrapartition one. ASSUMED: every record on the queue counts as committed (a record written in the same unit of work too).

Operations: W:queue:text writes, R:queue:n reads INTO an 8-byte area with LENGTH(n), P:queue reads SET, D:queue deletes, S is a
SYNCPOINT, B a SYNCPOINT ROLLBACK, O:queue:cvda SET TDQUEUE OPENSTATUS, Q:queue INQUIRE TDQUEUE OPENSTATUS and TYPE,
E:queue:cvda SET TDQUEUE ENABLESTATUS, F:queue INQUIRE TDQUEUE ENABLESTATUS, I:queue INQUIRE TDQUEUE TRIGGERLEVEL RECOVSTATUS
TRANSID, G:queue INQUIRE TDQUEUE RECOVSTATUS (round 6: an intrapartition queue answers by its definition, RECOVSTATUS is NOTAPPLIC 1
for the others, TRIGGERLEVEL / TRANSID of the others are refused), T:queue:n SET TDQUEUE TRIGGERLEVEL (round 7)."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_cics as ec  # noqa: E402
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
    "set open status of an output queue": (
        {"OOOO": "EXTRA TYPEFILE=OUTPUT OPENTIME=INITIAL", "DDDD": "EXTRA TYPEFILE=OUTPUT OPENTIME=DEFERRED"}, {},
        ["Q:OOOO", "W:OOOO:a", "O:OOOO:19", "Q:OOOO", "W:OOOO:b", "O:OOOO:19", "O:OOOO:18", "Q:OOOO", "W:OOOO:c", "O:OOOO:18",
         "Q:DDDD", "W:DDDD:a", "O:DDDD:18", "Q:DDDD", "W:DDDD:b"],
        ["Q:OOOO resp=0 resp2=0 open=18 type=221", "W:OOOO:a resp=0", "O:OOOO:19 resp=0 resp2=0",
         "Q:OOOO resp=0 resp2=0 open=19 type=221", "W:OOOO:b resp=19", "O:OOOO:19 resp=0 resp2=0", "O:OOOO:18 resp=0 resp2=0",
         "Q:OOOO resp=0 resp2=0 open=18 type=221", "W:OOOO:c resp=0", "O:OOOO:18 resp=0 resp2=0",
         "Q:DDDD resp=0 resp2=0 open=19 type=221", "W:DDDD:a resp=19", "O:DDDD:18 resp=0 resp2=0",
         "Q:DDDD resp=0 resp2=0 open=18 type=221", "W:DDDD:b resp=0"],
    ),
    "set open status of an input queue": (
        {"IIII": "EXTRA TYPEFILE=INPUT OPENTIME=DEFERRED", "JJJJ": "EXTRA TYPEFILE=INPUT OPENTIME=INITIAL"},
        {"IIII": ["x", "y"], "JJJJ": ["p", "q"]},
        ["R:IIII:8", "O:IIII:18", "R:IIII:8", "W:IIII:w", "O:IIII:19", "R:IIII:8", "O:JJJJ:19", "R:JJJJ:8", "O:JJJJ:18", "R:JJJJ:8"],
        [f"R:IIII:8 resp=19 len=-1 {R8}", "O:IIII:18 resp=0 resp2=0", "R:IIII:8 resp=0 len=1 into=x.......", "W:IIII:w resp=16",
         "O:IIII:19 resp=0 resp2=0", f"R:IIII:8 resp=19 len=-1 {R8}", "O:JJJJ:19 resp=0 resp2=0", f"R:JJJJ:8 resp=19 len=-1 {R8}",
         "O:JJJJ:18 resp=0 resp2=0", "R:JJJJ:8 resp=0 len=1 into=p......."],
    ),
    "reopening an input queue that was read": (
        {"IIII": _E}, {"IIII": ["a", "b"]}, ["R:IIII:8", "O:IIII:19", "O:IIII:18"],
        ["R:IIII:8 resp=0 len=1 into=a.......", "O:IIII:19 resp=0 resp2=0", "REFUSED"],
    ),
    "set open status of an intrapartition queue": (
        {"AAAA": "INTRA"}, {},
        ["O:AAAA:18", "O:AAAA:19", "Q:AAAA", "W:AAAA:a", "R:AAAA:8"],
        ["O:AAAA:18 resp=16 resp2=9", "O:AAAA:19 resp=16 resp2=9", "Q:AAAA resp=0 resp2=0 open=1 type=222", "W:AAAA:a resp=0",
         "R:AAAA:8 resp=0 len=1 into=a......."],
    ),
    "set open status with an invalid cvda": (
        {"XXXX": "EXTRA TYPEFILE=OUTPUT"}, {}, ["O:XXXX:7", "O:XXXX:0", "Q:XXXX", "O:XXXX:21", "W:XXXX:a"],
        ["O:XXXX:7 resp=16 resp2=8", "O:XXXX:0 resp=16 resp2=8", "Q:XXXX resp=0 resp2=0 open=18 type=221",
         "O:XXXX:21 resp=16 resp2=8", "W:XXXX:a resp=0"],
    ),
    "invalid cvda on an intrapartition queue": ({"AAAA": "INTRA"}, {}, ["O:AAAA:7"], ["REFUSED"]),
    "invalid cvda on an unknown queue": ({"AAAA": "INTRA"}, {}, ["O:ZZZZ:7"], ["REFUSED"]),
    "set and inquire an unknown queue": (
        {"AAAA": "INTRA"}, {}, ["O:ZZZZ:18", "O:ZZZZ:19", "Q:ZZZZ"],
        ["O:ZZZZ:18 resp=44 resp2=1", "O:ZZZZ:19 resp=44 resp2=1", "Q:ZZZZ resp=44 resp2=1 open=0 type=0"],
    ),
    "inquire with no csd": (None, {}, ["Q:ANYQ", "O:ANYQ:18"], ["Q:ANYQ resp=0 resp2=0 open=1 type=222", "O:ANYQ:18 resp=16 resp2=9"]),
    "inquire an indirect and a remote queue": (
        {"AAAA": "INTRA", "IIII": "INDIRECT INDIRECTNAME=AAAA", "RRRR": "REMOTE"}, {}, ["Q:IIII", "Q:RRRR", "Q:AAAA"],
        ["Q:IIII resp=0 resp2=0 open=1 type=122", "Q:RRRR resp=0 resp2=0 open=1 type=4", "Q:AAAA resp=0 resp2=0 open=1 type=222"],
    ),
    "set open status of an indirect queue": (
        {"AAAA": "INTRA", "IIII": "INDIRECT INDIRECTNAME=AAAA"}, {}, ["O:IIII:18"], ["REFUSED"]
    ),
    "set open status of a remote queue": ({"RRRR": "REMOTE"}, {}, ["O:RRRR:19"], ["REFUSED"]),
    "inquire a queue with no type": ({"NNNN": "-"}, {}, ["Q:NNNN"], ["REFUSED"]),
    "set open status with no typefile": (
        {"XXXX": "EXTRA OPENTIME=DEFERRED"}, {}, ["Q:XXXX", "O:XXXX:19", "Q:XXXX", "O:XXXX:18"],
        ["Q:XXXX resp=0 resp2=0 open=19 type=221", "O:XXXX:19 resp=0 resp2=0", "Q:XXXX resp=0 resp2=0 open=19 type=221", "REFUSED"],
    ),
    "set open status on a queue the rollback keeps": (
        {"OOOO": "EXTRA TYPEFILE=OUTPUT", "LLLL": _L}, {}, ["O:OOOO:19", "W:LLLL:a", "B", "Q:OOOO", "S", "Q:OOOO"],
        ["O:OOOO:19 resp=0 resp2=0", "W:LLLL:a resp=0", "B", "Q:OOOO resp=0 resp2=0 open=19 type=221", "S",
         "Q:OOOO resp=0 resp2=0 open=19 type=221"],
    ),
    # round 5 (X66): SET / INQUIRE TDQUEUE ENABLESTATUS (ENABLED 23, DISABLED 24); a disabled queue answers DISABLED (84)
    "disable and enable an intrapartition queue": (
        {"AAAA": "INTRA"}, {},
        ["F:AAAA", "W:AAAA:a", "E:AAAA:24", "F:AAAA", "W:AAAA:b", "R:AAAA:8", "D:AAAA", "E:AAAA:23", "F:AAAA", "R:AAAA:8",
         "W:AAAA:c", "R:AAAA:8"],
        ["F:AAAA resp=0 resp2=0 enable=23", "W:AAAA:a resp=0", "E:AAAA:24 resp=0 resp2=0", "F:AAAA resp=0 resp2=0 enable=24",
         "W:AAAA:b resp=84", f"R:AAAA:8 resp=84 len=-1 {R8}", "D:AAAA resp=84", "E:AAAA:23 resp=0 resp2=0",
         "F:AAAA resp=0 resp2=0 enable=23", "R:AAAA:8 resp=0 len=1 into=a.......", "W:AAAA:c resp=0",
         "R:AAAA:8 resp=0 len=1 into=c......."],
    ),
    "disable an extrapartition queue": (
        {"OOOO": "EXTRA TYPEFILE=OUTPUT OPENTIME=INITIAL", "IIII": "EXTRA TYPEFILE=INPUT OPENTIME=INITIAL"}, {"IIII": ["x"]},
        ["E:OOOO:24", "W:OOOO:a", "D:OOOO", "Q:OOOO", "E:OOOO:23", "W:OOOO:b", "E:IIII:24", "R:IIII:8", "E:IIII:23", "R:IIII:8"],
        ["E:OOOO:24 resp=0 resp2=0", "W:OOOO:a resp=84", "D:OOOO resp=84", "Q:OOOO resp=0 resp2=0 open=18 type=221",
         "E:OOOO:23 resp=0 resp2=0", "W:OOOO:b resp=0", "E:IIII:24 resp=0 resp2=0", f"R:IIII:8 resp=84 len=-1 {R8}",
         "E:IIII:23 resp=0 resp2=0", "R:IIII:8 resp=0 len=1 into=x......."],
    ),
    "enablestatus with an invalid cvda": (
        {"AAAA": "INTRA", "XXXX": "EXTRA TYPEFILE=OUTPUT"}, {},
        ["E:AAAA:7", "E:AAAA:18", "E:XXXX:0", "F:AAAA", "E:ZZZZ:24", "E:ZZZZ:23", "F:ZZZZ"],
        ["E:AAAA:7 resp=16 resp2=10", "E:AAAA:18 resp=16 resp2=10", "E:XXXX:0 resp=16 resp2=10", "F:AAAA resp=0 resp2=0 enable=23",
         "E:ZZZZ:24 resp=44 resp2=1", "E:ZZZZ:23 resp=44 resp2=1", "F:ZZZZ resp=44 resp2=1 enable=0"],
    ),
    "enablestatus with no csd": (
        None, {}, ["F:ANYQ", "E:ANYQ:24", "W:ANYQ:a", "F:ANYQ"],
        ["F:ANYQ resp=0 resp2=0 enable=23", "E:ANYQ:24 resp=0 resp2=0", "W:ANYQ:a resp=84", "F:ANYQ resp=0 resp2=0 enable=24"],
    ),
    "enablestatus survives a rollback": (
        {"LLLL": _L}, {}, ["W:LLLL:a", "E:LLLL:24", "B", "F:LLLL", "S", "F:LLLL"],
        ["W:LLLL:a resp=0", "E:LLLL:24 resp=0 resp2=0", "B", "F:LLLL resp=0 resp2=0 enable=24", "S",
         "F:LLLL resp=0 resp2=0 enable=24"],
    ),
    "enablestatus of an indirect queue": (
        {"AAAA": "INTRA", "IIII": "INDIRECT INDIRECTNAME=AAAA"}, {}, ["E:IIII:24"], ["REFUSED"]
    ),
    "enablestatus of a remote queue": ({"RRRR": "REMOTE"}, {}, ["E:RRRR:23"], ["REFUSED"]),
    "invalid enablestatus on an unknown queue": ({"AAAA": "INTRA"}, {}, ["E:ZZZZ:7"], ["REFUSED"]),
    "inquire enablestatus of an indirect queue": (
        {"AAAA": "INTRA", "IIII": "INDIRECT INDIRECTNAME=AAAA"}, {}, ["F:IIII"], ["F:IIII resp=0 resp2=0 enable=23"]
    ),
    # round 6 (X66): INQUIRE TDQUEUE TRIGGERLEVEL / RECOVSTATUS / TRANSID. I: all three; G: RECOVSTATUS alone
    "inquire ati options": (
        {"AAAA": "INTRA TRIGGERLEVEL=3 TRANSID=TRN1 RECOVSTATUS=LOGICAL", "BBBB": "INTRA", "CCCC": "INTRA RECOVSTATUS=PHYSICAL",
         "DDDD": "INTRA RECOVSTATUS=NO TRIGGERLEVEL=0"}, {},
        ["I:AAAA", "I:BBBB", "G:CCCC", "I:DDDD", "I:ZZZZ", "G:ZZZZ"],
        ["I:AAAA resp=0 resp2=0 trigger=3 recov=216 transid=[TRN1]", "I:BBBB resp=0 resp2=0 trigger=1 recov=30 transid=[    ]",
         "G:CCCC resp=0 resp2=0 recov=215", "I:DDDD resp=0 resp2=0 trigger=0 recov=30 transid=[    ]",
         "I:ZZZZ resp=44 resp2=1 trigger=0 recov=0 transid=[]", "G:ZZZZ resp=44 resp2=1 recov=0"],
    ),
    "inquire recovstatus of other queues": (
        {"XXXX": _E, "IIII": "INDIRECT INDIRECTNAME=XXXX", "RRRR": "REMOTE"}, {},
        ["G:XXXX", "G:IIII", "G:RRRR"],
        ["G:XXXX resp=0 resp2=0 recov=1", "G:IIII resp=0 resp2=0 recov=1", "G:RRRR resp=0 resp2=0 recov=1"],
    ),
    "inquire trigger level of an extrapartition queue": ({"XXXX": _E}, {}, ["I:XXXX"], ["REFUSED"]),
    "inquire trigger level of an indirect queue": (
        {"AAAA": "INTRA", "IIII": "INDIRECT INDIRECTNAME=AAAA"}, {}, ["I:IIII"], ["REFUSED"]
    ),
    "inquire trigger level of a remote queue": ({"RRRR": "REMOTE"}, {}, ["I:RRRR"], ["REFUSED"]),
    "set trigger level": (
        {"TTTT": "INTRA TRANSID=TRN1 TRIGGERLEVEL=1", "AAAA": "INTRA", "SSSS": "INTRA TRANSID=TRN1 TRIGGERLEVEL=9"},
        {"SSSS": ["s1", "s2"]},
        ["T:TTTT:3", "W:TTTT:a", "W:TTTT:b", "I:TTTT", "T:AAAA:2", "W:AAAA:p", "I:AAAA", "T:SSSS:3", "W:SSSS:x"],
        ["T:TTTT:3 resp=0 resp2=0", "W:TTTT:a resp=0", "W:TTTT:b resp=0", "I:TTTT resp=0 resp2=0 trigger=3 recov=30 transid=[TRN1]",
         "T:AAAA:2 resp=0 resp2=0", "W:AAAA:p resp=0", "I:AAAA resp=0 resp2=0 trigger=2 recov=30 transid=[    ]",
         "T:SSSS:3 resp=0 resp2=0", "REFUSED"],
    ),
    "set trigger level to zero and back": (
        {"UUUU": "INTRA TRANSID=TRN1 TRIGGERLEVEL=1"}, {},
        ["T:UUUU:0", "W:UUUU:a", "W:UUUU:b", "I:UUUU", "T:UUUU:1", "W:UUUU:c"],
        ["T:UUUU:0 resp=0 resp2=0", "W:UUUU:a resp=0", "W:UUUU:b resp=0", "I:UUUU resp=0 resp2=0 trigger=0 recov=30 transid=[TRN1]",
         "T:UUUU:1 resp=0 resp2=0", "REFUSED"],
    ),
    "set trigger level survives a rollback": (
        {"LLLL": _L + " TRANSID=TRN1 TRIGGERLEVEL=1"}, {},
        ["T:LLLL:5", "W:LLLL:a", "B", "I:LLLL", "R:LLLL:8"],
        ["T:LLLL:5 resp=0 resp2=0", "W:LLLL:a resp=0", "B", "I:LLLL resp=0 resp2=0 trigger=5 recov=216 transid=[TRN1]",
         f"R:LLLL:8 resp=23 len=-1 {R8}"],
    ),
    "set trigger level of an undefined queue": (
        {"AAAA": "INTRA"}, {}, ["T:NOPE:1", "T:NOPE:-1"], ["T:NOPE:1 resp=44 resp2=1", "T:NOPE:-1 resp=44 resp2=1"]
    ),
    "set trigger level below zero": ({"AAAA": "INTRA"}, {}, ["T:AAAA:-1"], ["REFUSED"]),
    "set trigger level of an extrapartition queue": ({"XXXX": _E}, {}, ["T:XXXX:1"], ["REFUSED"]),
    "set trigger level of an indirect queue": (
        {"AAAA": "INTRA", "IIII": "INDIRECT INDIRECTNAME=AAAA"}, {}, ["T:IIII:1"], ["REFUSED"]
    ),
    "set trigger level of a remote queue": ({"RRRR": "REMOTE"}, {}, ["T:RRRR:1"], ["REFUSED"]),
    # IOERR (X61): the planned fault of READQ TD on an open extrapartition input queue skips the record
    "planned ioerr skips a record": (
        {"XXXX": _E}, {"XXXX": ["one", "two", "three"]},
        ["R:XXXX:8", "R:XXXX:8", "R:XXXX:8", "R:XXXX:8"],
        [f"R:XXXX:8 resp=17 len=-1 {R8}", "R:XXXX:8 resp=0 len=3 into=two.....", "R:XXXX:8 resp=0 len=5 into=three...",
         f"R:XXXX:8 resp=23 len=-1 {R8}"],
    ),
    "planned ioerr on the second read": (
        {"XXXX": _E}, {"XXXX": ["one", "two", "three"]},
        ["R:XXXX:8", "R:XXXX:8", "R:XXXX:8", "R:XXXX:8"],
        ["R:XXXX:8 resp=0 len=3 into=one.....", f"R:XXXX:8 resp=17 len=-1 {R8}", "R:XXXX:8 resp=0 len=5 into=three...",
         f"R:XXXX:8 resp=23 len=-1 {R8}"],
    ),
    "planned ioerr on every read": (
        {"XXXX": _E}, {"XXXX": ["one", "two"]},
        ["R:XXXX:8", "R:XXXX:8", "R:XXXX:8"],
        [f"R:XXXX:8 resp=17 len=-1 {R8}", f"R:XXXX:8 resp=17 len=-1 {R8}", f"R:XXXX:8 resp=17 len=-1 {R8}"],
    ),
    "planned ioerr on a read with SET": (
        {"XXXX": _E}, {"XXXX": ["one", "two"]}, ["P:XXXX", "P:XXXX", "P:XXXX"],
        ["P:XXXX resp=17 len=-1 block=-", "P:XXXX resp=0 len=3 block=two", "P:XXXX resp=23 len=-1 block=-"],
    ),
    "planned ioerr is counted on an open queue only": (
        {"ZZZZ": "EXTRA TYPEFILE=INPUT OPENTIME=DEFERRED", "OOOO": "EXTRA TYPEFILE=OUTPUT", "DDDD": "EXTRA TYPEFILE=INPUT"},
        {"ZZZZ": ["x", "y"], "DDDD": ["d"]},
        ["R:ZZZZ:8", "O:ZZZZ:18", "R:ZZZZ:8", "R:ZZZZ:8", "R:OOOO:8", "R:DDDD:-1", "E:DDDD:24", "R:DDDD:8", "E:DDDD:23", "R:DDDD:8"],
        [f"R:ZZZZ:8 resp=19 len=-1 {R8}", "O:ZZZZ:18 resp=0 resp2=0", f"R:ZZZZ:8 resp=17 len=-1 {R8}",
         "R:ZZZZ:8 resp=0 len=1 into=y.......", f"R:OOOO:8 resp=16 len=-1 {R8}", f"R:DDDD:-1 resp=22 len=-1 {R8}",
         "E:DDDD:24 resp=0 resp2=0", f"R:DDDD:8 resp=84 len=-1 {R8}", "E:DDDD:23 resp=0 resp2=0",
         f"R:DDDD:8 resp=17 len=-1 {R8}"],
    ),
    "planned ioerr is not consulted by an intrapartition queue": (
        {"AAAA": "INTRA"}, {"AAAA": ["a", "b"]}, ["R:AAAA:8", "R:AAAA:8"],
        ["R:AAAA:8 resp=0 len=1 into=a.......", "R:AAAA:8 resp=0 len=1 into=b......."],
    ),
    "planned ioerr through an indirect queue": (
        {"XXXX": _E, "IIII": "INDIRECT INDIRECTNAME=XXXX"}, {"XXXX": ["one", "two"]}, ["R:IIII:8", "R:XXXX:8", "R:IIII:8"],
        [f"R:IIII:8 resp=17 len=-1 {R8}", "R:XXXX:8 resp=0 len=3 into=two.....", f"R:IIII:8 resp=23 len=-1 {R8}"],
    ),
    # QBUSY (X61): the planned fault of READQ TD NOSUSPEND on a LOGICAL intrapartition queue with no committed record
    "planned qbusy on an empty logical queue": (
        {"LLLL": _L}, {}, ["N:LLLL:8", "N:LLLL:8"], [f"N:LLLL:8 resp=25 len=-1 {R8}", f"N:LLLL:8 resp=23 len=-1 {R8}"],
    ),
    "planned qbusy waits for the records to be read": (
        {"LLLL": _L}, {"LLLL": ["a", "b"]}, ["N:LLLL:8", "N:LLLL:8", "N:LLLL:8", "N:LLLL:8"],
        ["N:LLLL:8 resp=0 len=1 into=a.......", "N:LLLL:8 resp=0 len=1 into=b.......", f"N:LLLL:8 resp=25 len=-1 {R8}",
         f"N:LLLL:8 resp=23 len=-1 {R8}"],
    ),
    "planned qbusy on every read": (
        {"LLLL": _L}, {}, ["N:LLLL:8", "N:LLLL:8"], [f"N:LLLL:8 resp=25 len=-1 {R8}", f"N:LLLL:8 resp=25 len=-1 {R8}"],
    ),
    "planned qbusy without NOSUSPEND": ({"LLLL": _L}, {}, ["R:LLLL:8"], ["REFUSED"]),
    "planned qbusy is not consulted by a queue that is not logical": (
        {"NNNN": "INTRA RECOVSTATUS=NO", "PPPP": "INTRA RECOVSTATUS=PHYSICAL", "AAAA": "INTRA"}, {},
        ["N:NNNN:8", "N:PPPP:8", "N:AAAA:8"], [f"N:{q}:8 resp=23 len=-1 {R8}" for q in ("NNNN", "PPPP", "AAAA")],
    ),
    "planned qbusy on an extrapartition queue": ({"XXXX": _E}, {"XXXX": ["x"]}, ["N:XXXX:8"], ["REFUSED"]),
    "planned qbusy follows a write of the same unit of work": (
        {"LLLL": _L}, {}, ["W:LLLL:w1", "N:LLLL:8", "N:LLLL:8"],
        ["W:LLLL:w1 resp=0", "N:LLLL:8 resp=0 len=2 into=w1......", f"N:LLLL:8 resp=25 len=-1 {R8}"],
    ),
}  # fmt: skip

# the faults a scenario plans (the equivalence harness's form; ec.fault_lines turns them into both runtimes' lines)
_PLANS: dict[str, list[dict]] = {
    "planned ioerr skips a record": [{"cmd": "READQ-TD", "queue": "XXXX", "resp": "IOERR"}],
    "planned ioerr on the second read": [{"cmd": "READQ-TD", "queue": "XXXX", "resp": "IOERR", "nth": 2}],
    "planned ioerr on every read": [{"cmd": "READQ-TD", "queue": "XXXX", "resp": "IOERR", "nth": "*"}],
    "planned ioerr on a read with SET": [{"cmd": "READQ-TD", "queue": "XXXX", "resp": "IOERR"}],
    "planned ioerr is counted on an open queue only": [
        {"cmd": "READQ-TD", "queue": "ZZZZ", "resp": "IOERR"},
        {"cmd": "READQ-TD", "queue": "OOOO", "resp": "IOERR"},
        {"cmd": "READQ-TD", "queue": "DDDD", "resp": "IOERR"},
    ],
    "planned ioerr is not consulted by an intrapartition queue": [
        {"cmd": "READQ-TD", "queue": "AAAA", "resp": "IOERR", "nth": "*"}
    ],
    "planned ioerr through an indirect queue": [{"cmd": "READQ-TD", "queue": "IIII", "resp": "IOERR"}],
}


_QB = {"cmd": "READQ-TD", "queue": "LLLL", "resp": "QBUSY"}
_PLANS.update(
    {
        "planned qbusy on an empty logical queue": [_QB],
        "planned qbusy waits for the records to be read": [_QB],
        "planned qbusy on every read": [{**_QB, "nth": "*"}],
        "planned qbusy without NOSUSPEND": [_QB],
        "planned qbusy is not consulted by a queue that is not logical": [
            {**_QB, "queue": q, "nth": "*"} for q in ("NNNN", "PPPP", "AAAA")
        ],
        "planned qbusy on an extrapartition queue": [{**_QB, "queue": "XXXX"}],
        "planned qbusy follows a write of the same unit of work": [_QB],
    }
)


def _plan_lines(name: str) -> list[str]:
    return ec.fault_lines({"name": name, "faults": _PLANS.get(name, [])})


_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCWRTD(gg_cics *c, char *from);
int GGCRDTD(gg_cics *c, char *into, int intolen);
int GGCRDTS(gg_cics *c, void **slot);
int GGCDLTD(gg_cics *c);
int GGCSTDQ(gg_cics *c);
int GGCSTDE(gg_cics *c);
int GGCSTDT(gg_cics *c);
int GGCITDQ(gg_cics *c);
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
        } else if (a[0] == 'O') {
            c.num = atoi(a + 7);
            GGCSTDQ(&c);
            printf("%s resp=%d resp2=%d\n", a, c.resp, c.resp2);
        } else if (a[0] == 'E') {
            c.num = atoi(a + 7);
            GGCSTDE(&c);
            printf("%s resp=%d resp2=%d\n", a, c.resp, c.resp2);
        } else if (a[0] == 'T') {
            c.num = atoi(a + 7);
            GGCSTDT(&c);
            printf("%s resp=%d resp2=%d\n", a, c.resp, c.resp2);
        } else if (a[0] == 'F') {
            strcpy(c.flags, "ENABLESTATUS");
            GGCITDQ(&c);
            printf("%s resp=%d resp2=%d enable=%d\n", a, c.resp, c.resp2, c.item);
        } else if (a[0] == 'I' || a[0] == 'G') {
            strcpy(c.flags, a[0] == 'I' ? "TRIGGERLEVEL RECOVSTATUS TRANSID" : "RECOVSTATUS");
            GGCITDQ(&c);
            if (a[0] == 'I') printf("%s resp=%d resp2=%d trigger=%d recov=%d transid=[%.4s]\n", a, c.resp, c.resp2, c.hours, c.mins, c.resp == 0 ? c.rtran : "");
            else printf("%s resp=%d resp2=%d recov=%d\n", a, c.resp, c.resp2, c.mins);
        } else if (a[0] == 'Q') {
            strcpy(c.flags, "OPENSTATUS TYPE");
            GGCITDQ(&c);
            printf("%s resp=%d resp2=%d open=%d type=%d\n", a, c.resp, c.resp2, c.num, c.len);
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
            if (a[0] == 'N') strcpy(c.flags, "TDNOSUSPEND");
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
    if _PLANS.get(name):
        (work / "faults.cfg").write_text("".join(x + "\n" for x in _plan_lines(name)), encoding="ascii")
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
    if _PLANS.get(name):
        chain += ".withFaults(java.util.List.of(" + ", ".join(f'"{x}"' for x in _plan_lines(name)) + "), null)"
    if queues is not None:
        names = ", ".join(f'"{q}"' for q in sorted(queues))
        types = ", ".join(f'"{q}", "{queues[q].split()[0]}"' for q in sorted(queues))
        attrs = ", ".join(f'"{q}", "{kv.split("=")[0]}", "{kv.split("=")[1]}"' for q in sorted(queues)
                          for kv in queues[q].split()[1:])  # fmt: skip
        chain += f".withTdQueues(java.util.Set.of({names})).withTdQueueTypes(java.util.Map.of({types}))"
        if attrs:
            chain += f".withTdQueueAttributes({attrs})"
    # one method per scenario: a single main for them all passes the JVM's 64 KB method limit
    return f"""
        new Object() {{ void go() {{
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
                    }} else if (p[0].equals("O")) {{
                        int[] r = t.setTdQueueOpenStatus(p[1], Long.parseLong(p[2]));
                        System.out.println(op + " resp=" + r[0] + " resp2=" + r[1]);
                    }} else if (p[0].equals("E")) {{
                        int[] r = t.setTdQueueEnableStatus(p[1], Long.parseLong(p[2]));
                        System.out.println(op + " resp=" + r[0] + " resp2=" + r[1]);
                    }} else if (p[0].equals("T")) {{
                        int[] r = t.setTdQueueTriggerLevel(p[1], Long.parseLong(p[2]));
                        System.out.println(op + " resp=" + r[0] + " resp2=" + r[1]);
                    }} else if (p[0].equals("F")) {{
                        int[] r = t.inquireTdQueue(p[1], false, false, true);
                        System.out.println(op + " resp=" + r[0] + " resp2=" + r[1] + " enable=" + r[4]);
                    }} else if (p[0].equals("I")) {{
                        int[] r = t.inquireTdQueue(p[1], false, false, false, true, true, true);
                        System.out.println(op + " resp=" + r[0] + " resp2=" + r[1] + " trigger=" + r[5] + " recov=" + r[6]
                                + " transid=[" + (r[0] == 0 ? String.format("%-4s", t.tdTransid(p[1])) : "") + "]");
                    }} else if (p[0].equals("G")) {{
                        int[] r = t.inquireTdQueue(p[1], false, false, false, false, true, false);
                        System.out.println(op + " resp=" + r[0] + " resp2=" + r[1] + " recov=" + r[6]);
                    }} else if (p[0].equals("Q")) {{
                        int[] r = t.inquireTdQueue(p[1], true, true);
                        System.out.println(op + " resp=" + r[0] + " resp2=" + r[1] + " open=" + r[2] + " type=" + r[3]);
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
                        CicsTask.TdResult r = t.readqTd(p[1], Integer.parseInt(p[2]), p[0].equals("N"));
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
        }} }}.go();"""


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
@pytest.mark.slow(
    reason="the module fixture compiles and runs every scenario in one javac task; the first test in a split part pays it"
)
@needs_javac
def test_cics_task_runs_each_scenario_as_the_stub_does(name, java_outputs):
    assert java_outputs[name] == _SCENARIOS[name][3]


def test_a_readq_td_fault_is_planned_as_ioerr_with_no_resp2_and_nothing_else():
    ok = {"name": "s", "faults": [{"cmd": "READQ-TD", "queue": "XXXX", "resp": "IOERR", "nth": 2}]}
    assert ec.fault_lines(ok) == [f"READQ-TD XXXX 2 {ec.CICS_RESP['IOERR']} 0"]
    busy = {
        "name": "s",
        "faults": [{"cmd": "READQ-TD", "queue": "LLLL", "resp": "QBUSY"}],
    }  # X61: QBUSY, no RESP2 either
    assert ec.fault_lines(busy) == [f"READQ-TD LLLL 1 {ec.CICS_RESP['QBUSY']} 0"]
    for bad in (
        {"resp": "NOTOPEN"},
        {"resp": "QZERO"},
        {"resp": "INVREQ"},
        {"resp": "IOERR", "resp2": 1},
        {"resp": "DUPKEY"},
    ):
        with pytest.raises(ec.Unsupported):
            ec.fault_lines({"name": "s", "faults": [{"cmd": "READQ-TD", "queue": "XXXX", **bad}]})
    with pytest.raises(ec.Unsupported, match="names no"):
        ec.fault_lines({"name": "s", "faults": [{"cmd": "READQ-TD", "resp": "IOERR"}]})
    assert "READQ-TD" not in ec.FAULT_COMMANDS  # the strengthening loop plans from that list
