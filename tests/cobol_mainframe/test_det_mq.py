"""#4892: the IBM MQ calls MQOPEN, MQGET, MQPUT, MQPUT1 and MQCLOSE in the det runtime (cobolrt/mq/QueueManager.java)
and in the harness's COBOL-side model (tests/equivalence/mq/ggmq.c), so a CICS program that CALLs them (CardDemo
CODATE01 / COACCT01) translates and is proven.

One table of scripts drives three checks. A script is one task's calls on one queue manager (the queues a case states,
equivalence_mq.cfg), each step a call and the completion and reason code IBM documents for it:

1. **IBM's documented outcomes** (`want`, "cc/rc"): every reason code the models return, the unit of work (a get or a
   put under syncpoint undone by a backout, kept by a commit; NO-SYNCPOINT at once), delivery order, truncation, MsgId
   generation, and the refusals by name (exit 98 / "... is not modelled") of what is not modelled.
2. **The runtime against the oracle's model**: the same scripts through the Java runtime and through the C model; every
   output -- the structures as the call left them, the buffer, the events, the queues left -- byte-for-byte equal.
3. **The wiring**: the translator's calls and arities (gitgalaxy/standards/mq.py), the stand-in copybooks' lengths and
   initial values against IBM's, and their GitGalaxy header.
"""

from __future__ import annotations

import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_mq as EQ  # noqa: E402

from gitgalaxy.standards import mq as SPEC  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

MQ_C = ROOT / "tests/equivalence/mq/ggmq.c"
RT = ROOT / "gitgalaxy/tools/cobol_to_java/det/cobolrt"
COPY = ROOT / "gitgalaxy/tools/cobol_to_java/det/copy"
CLOCK = "2022/07/18 10:30:15.25"
REFUSED = "REFUSED"
QM = {"qmgr": "CSQ1", "ccsid": 37}


def _l(v: int) -> bytes:
    return struct.pack(">i", v)


def _c(s: str, n: int, fill: bytes = b" ") -> bytes:
    return s.encode("latin-1") + fill * (n - len(s))


# ---- IBM's initial values of each structure (IBM MQ documentation, "Initial values" of MQMD / MQOD / MQGMO / MQPMO) --
def md(**f) -> bytes:
    v = {"msgtype": 8, "expiry": -1, "encoding": 785, "ccsid": 0, "format": "", "priority": -1, "persistence": 2,
         "msgid": b"", "correlid": b"", "report": 0, "version": 1, "strucid": "MD  "} | f  # fmt: skip
    ids = [x if isinstance(x, bytes) else x.encode() for x in (v["msgid"], v["correlid"])]
    return b"".join([
        _c(v["strucid"], 4), _l(v["version"]), _l(v["report"]), _l(v["msgtype"]), _l(v["expiry"]), _l(0),
        _l(v["encoding"]), _l(v["ccsid"]), _c(v["format"], 8), _l(v["priority"]), _l(v["persistence"]),
        ids[0] + b"\0" * (24 - len(ids[0])), ids[1] + b"\0" * (24 - len(ids[1])), _l(0), _c("", 48), _c("", 48),
        _c("", 12), b"\0" * 32, _c("", 32), _l(0), _c("", 28), _c("", 8), _c("", 8), _c("", 4),
    ])  # fmt: skip


def od(name: str, qmgr: str = "", objtype: int = 1, version: int = 1) -> bytes:
    return b"".join([_c("OD  ", 4), _l(version), _l(objtype), _c(name, 48), _c(qmgr, 48), _c("CSQ.*", 48), _c("", 12)])


def gmo(options: int = 0, wait: int = 0, version: int = 1) -> bytes:
    return b"".join([_c("GMO ", 4), _l(version), _l(options), _l(wait), _l(0), _l(0), _c("", 48)])


def pmo(options: int = 0, version: int = 1) -> bytes:
    return b"".join(
        [_c("PMO ", 4), _l(version), _l(options), _l(-1), _l(0), _l(0), _l(0), _l(0), _c("", 48), _c("", 48)]
    )


# MQI constants (IBM MQ documentation, "Constants"), as CMQV.cpy declares them
INPUT_AS_Q_DEF, INPUT_SHARED, INPUT_EXCLUSIVE, OUTPUT, SAVE_ALL, PASS_ALL, FIQ = 1, 2, 4, 16, 128, 512, 8192
BROWSE, INQUIRE = 8, 32
G_WAIT, G_SYNC, G_NOSYNC, G_TRUNC, G_CONVERT, G_BROWSE_FIRST = 1, 2, 4, 64, 16384, 16
P_SYNC, P_NOSYNC, P_DEFAULT, P_NOCONTEXT, P_NEW_MSG_ID = 2, 4, 32, 16384, 64


def q(name: str, *msgs: str, priority: int = 0, persistence: int = 0, **_) -> tuple[str, dict]:
    return name, {"priority": priority, "persistence": persistence,
                  "messages": [{"data": m, "format": "MQSTR"} for m in msgs]}  # fmt: skip


def state(*queues: tuple[str, dict]) -> dict:
    return {**QM, "queues": dict(queues)}


# Steps: OPEN od options | CLOSE hobj options | GET hobj md gmo buflen | PUT hobj md pmo data | PUT1 od md pmo data |
# UOW 0 (commit) / 1 (backout) | HCONN n. `want`: "cc/rc", None (no IBM value: the two models agree), or REFUSED.
def OPEN(name, options, **k):
    return ("OPEN", od(name, **k).hex(), str(options))


def CLOSE(h, options=0):
    return ("CLOSE", str(h), str(options))


def GET(h, options=0, buflen=100, m=None, wait=0, gversion=1):
    return ("GET", str(h), (m or md()).hex(), gmo(options, wait, gversion).hex(), str(buflen))


def PUT(h, data, options=0, m=None, pversion=1):
    return ("PUT", str(h), (m or md(format="MQSTR")).hex(), pmo(options, pversion).hex(), data.encode().hex() or "-")


def PUT1(name, data, options=0, m=None, **k):
    return (
        "PUT1",
        od(name, **k).hex(),
        (m or md(format="MQSTR")).hex(),
        pmo(options).hex(),
        data.encode().hex() or "-",
    )


def UOW(rollback):
    return ("UOW", str(rollback))


SCRIPTS: list[tuple[str, dict, list[tuple[tuple[str, ...], str | None]]]] = [
    (
        "open-modes",
        state(q("A")),
        [
            (OPEN("A", INPUT_SHARED), "0/0"),
            (OPEN("A", OUTPUT), "0/0"),
            (OPEN("A", INPUT_AS_Q_DEF | OUTPUT | FIQ), "0/0"),
            (OPEN("A", INPUT_EXCLUSIVE), REFUSED),  # a second input handle beside an exclusive one: OBJECT_IN_USE
        ],
    ),
    (
        "open-errors",
        state(q("A")),
        [
            (OPEN("NOPE", INPUT_SHARED), "2/2085"),  # MQRC_UNKNOWN_OBJECT_NAME
            (OPEN("A", INPUT_SHARED | INPUT_EXCLUSIVE), "2/2046"),  # two MQOO_INPUT_*: MQRC_OPTIONS_ERROR
            (OPEN("A", 0), "2/2046"),  # neither input nor output
            (OPEN("A", OUTPUT | SAVE_ALL), "2/2046"),  # SAVE_ALL_CONTEXT without an input option
            (OPEN("A", INPUT_SHARED | PASS_ALL), "2/2046"),  # PASS_ALL_CONTEXT without MQOO_OUTPUT
            (OPEN("A", OUTPUT, qmgr="CSQ1"), "0/0"),  # this queue manager, named
        ],
    ),
    ("open-browse-refused", state(q("A")), [(OPEN("A", BROWSE), REFUSED)]),
    ("open-inquire-refused", state(q("A")), [(OPEN("A", INQUIRE | OUTPUT), REFUSED)]),
    ("open-remote-qmgr-refused", state(q("A")), [(OPEN("A", OUTPUT, qmgr="OTHER"), REFUSED)]),
    ("open-not-a-queue-refused", state(q("A")), [(OPEN("A", OUTPUT, objtype=5), REFUSED)]),
    ("open-od-v2-refused", state(q("A")), [(OPEN("A", OUTPUT, version=2), REFUSED)]),
    (
        "get-fifo-and-empty",
        state(q("A", "one", "two")),
        [
            (OPEN("A", INPUT_SHARED), "0/0"),
            (GET(1, G_NOSYNC), "0/0"),
            (GET(1, G_NOSYNC), "0/0"),
            (GET(1, G_NOSYNC), "2/2033"),  # MQRC_NO_MSG_AVAILABLE
            (GET(1, G_NOSYNC | G_WAIT, wait=5000), "2/2033"),  # no other producer: the wait ends empty (W2)
        ],
    ),
    (
        "get-wait-unlimited-refused",
        state(q("A")),
        [
            (OPEN("A", INPUT_SHARED), "0/0"),
            (GET(1, G_WAIT, wait=-1), REFUSED),
        ],
    ),
    (
        "get-handle-errors",
        state(q("A", "x")),
        [
            (GET(7), "2/2019"),  # MQRC_HOBJ_ERROR
            (OPEN("A", OUTPUT), "0/0"),
            (GET(1), "2/2037"),  # MQRC_NOT_OPEN_FOR_INPUT
            (OPEN("A", INPUT_SHARED), "0/0"),
            (GET(2, G_SYNC | G_NOSYNC), "2/2046"),
            (GET(2, buflen=-1), "2/2005"),  # MQRC_BUFFER_LENGTH_ERROR
            (CLOSE(2), "0/0"),
            (GET(2), "2/2019"),
            (CLOSE(2), "2/2019"),  # a closed handle
        ],
    ),
    (
        "get-truncation",
        state(q("A", "abcdefghij")),
        [
            (OPEN("A", INPUT_SHARED), "0/0"),
            (GET(1, G_NOSYNC, buflen=4), "1/2080"),  # MQRC_TRUNCATED_MSG_FAILED: MQCC_WARNING, the message stays
            (GET(1, G_NOSYNC | G_TRUNC, buflen=4), "1/2079"),  # MQRC_TRUNCATED_MSG_ACCEPTED: removed
            (GET(1, G_NOSYNC), "2/2033"),
            (("END",), None),
        ],
    ),
    (
        "get-zero-length-buffer",
        state(q("A", "")),
        [
            (OPEN("A", INPUT_SHARED), "0/0"),
            (GET(1, G_NOSYNC, buflen=0), "0/0"),
        ],
    ),
    (
        "get-match-refused",
        state(q("A", "x")),
        [
            (OPEN("A", INPUT_SHARED), "0/0"),
            (GET(1, m=md(msgid=b"WANTED")), REFUSED),
        ],
    ),
    (
        "get-browse-refused",
        state(q("A", "x")),
        [
            (OPEN("A", INPUT_SHARED), "0/0"),
            (GET(1, G_BROWSE_FIRST), REFUSED),
        ],
    ),
    ("get-gmo-v2-refused", state(q("A", "x")), [(OPEN("A", INPUT_SHARED), "0/0"), (GET(1, gversion=2), REFUSED)]),
    (
        "get-convert-same-ccsid",
        state(q("A", "x")),
        [
            (OPEN("A", INPUT_SHARED), "0/0"),
            (GET(1, G_CONVERT), "0/0"),  # MQCCSI_Q_MGR is the message's own: a no-op
        ],
    ),
    (
        "get-convert-other-ccsid-refused",
        state(q("A", "x")),
        [
            (OPEN("A", INPUT_SHARED), "0/0"),
            (GET(1, G_CONVERT, m=md(ccsid=500)), REFUSED),
        ],
    ),
    (
        "priority-order",
        state(q("A")),
        [
            (OPEN("A", OUTPUT | INPUT_SHARED), "0/0"),
            (PUT(1, "low", P_NOSYNC, m=md(format="MQSTR", priority=1)), "0/0"),
            (PUT(1, "high", P_NOSYNC, m=md(format="MQSTR", priority=8)), "0/0"),
            (PUT(1, "high2", P_NOSYNC, m=md(format="MQSTR", priority=8)), "0/0"),
            (GET(1, G_NOSYNC), "0/0"),
            (GET(1, G_NOSYNC), "0/0"),
            (GET(1, G_NOSYNC), "0/0"),
        ],
    ),
    (
        "put-errors",
        state(q("A")),
        [
            (PUT(3, "x"), "2/2019"),
            (OPEN("A", INPUT_SHARED), "0/0"),
            (PUT(1, "x"), "2/2039"),  # NOT_OPEN_FOR_OUTPUT
            (OPEN("A", OUTPUT), "0/0"),
            (PUT(2, "x", P_SYNC | P_NOSYNC), "2/2046"),
            (PUT(2, "x", P_DEFAULT | P_NOCONTEXT), "2/2046"),
        ],
    ),
    ("put-new-msg-id-refused", state(q("A")), [(OPEN("A", OUTPUT), "0/0"), (PUT(1, "x", P_NEW_MSG_ID), REFUSED)]),
    ("put-report-refused", state(q("A")), [(OPEN("A", OUTPUT), "0/0"), (PUT(1, "x", m=md(report=1)), REFUSED)]),
    ("put-pmo-v2-refused", state(q("A")), [(OPEN("A", OUTPUT), "0/0"), (PUT(1, "x", pversion=2), REFUSED)]),
    (
        "put-msgid-and-context",
        state(q("A", priority=3, persistence=1)),
        [
            (OPEN("A", OUTPUT), "0/0"),
            (PUT(1, "generated", P_DEFAULT | P_NOSYNC), "0/0"),  # MQMI_NONE: a MsgId is made, context set (W4, W8)
            (PUT(1, "given", P_NOCONTEXT | P_NOSYNC, m=md(format="MQSTR", msgid=b"MINE")), "0/0"),
            (PUT(1, "", P_NOSYNC), "0/0"),  # an empty message; no context option is DEFAULT_CONTEXT
            (("END",), None),
        ],
    ),
    (
        "syncpoint-commit-and-backout",
        state(q("IN", "r1", "r2"), q("OUT")),
        [
            (OPEN("IN", INPUT_SHARED), "0/0"),
            (OPEN("OUT", OUTPUT | INPUT_SHARED), "0/0"),
            (GET(1, G_SYNC), "0/0"),
            (PUT(2, "reply1", P_SYNC), "0/0"),
            (GET(2, G_NOSYNC), "2/2033"),  # an uncommitted put is not available to a get, even the task's own
            (UOW(0), None),
            (GET(2, G_NOSYNC), "0/0"),  # committed: available
            (GET(1, G_SYNC), "0/0"),
            (PUT(2, "reply2", P_SYNC), "0/0"),
            (UOW(1), None),  # backed out: r2 back with BackoutCount 1, reply2 gone
            (GET(1, G_SYNC), "0/0"),
            (PUT(2, "reply3", P_NOSYNC), "0/0"),
            (("END",), None),
        ],
    ),
    (
        "zos-default-is-syncpoint",
        state(q("IN", "r1"), q("OUT")),
        [
            (OPEN("IN", INPUT_SHARED), "0/0"),
            (OPEN("OUT", OUTPUT), "0/0"),
            (GET(1, 0), "0/0"),
            (PUT(2, "x", 0), "0/0"),
            (UOW(1), None),
            (("END",), None),  # both in the unit of work
        ],
    ),
    (
        "put1",
        state(q("A")),
        [
            (PUT1("A", "one", P_NOSYNC), "0/0"),
            (PUT1("NOPE", "x"), "2/2085"),
            (PUT1("A", "two", P_SYNC), "0/0"),
            (UOW(1), None),
            (("END",), None),
        ],
    ),
    ("close-options-refused", state(q("A")), [(OPEN("A", OUTPUT), "0/0"), (CLOSE(1, 1), REFUSED)]),
    ("hconn-refused", state(q("A")), [(("HCONN", "5"), None), (OPEN("A", OUTPUT), REFUSED)]),
]

C_DRIVER = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int MQOPEN(unsigned char*, unsigned char*, unsigned char*, unsigned char*, unsigned char*, unsigned char*);
int MQCLOSE(unsigned char*, unsigned char*, unsigned char*, unsigned char*, unsigned char*);
int MQGET(unsigned char*, unsigned char*, unsigned char*, unsigned char*, unsigned char*, unsigned char*, unsigned char*,
          unsigned char*, unsigned char*);
int MQPUT(unsigned char*, unsigned char*, unsigned char*, unsigned char*, unsigned char*, unsigned char*, unsigned char*,
          unsigned char*);
int MQPUT1(unsigned char*, unsigned char*, unsigned char*, unsigned char*, unsigned char*, unsigned char*, unsigned char*,
           unsigned char*);
void ggmq_uow_end(int);
static void hx(const unsigned char *p, int n) { for (int i = 0; i < n; i++) printf("%02X", p[i]); }
void ggcics_event(const char *line, const char *data, int len) {
    printf("EV %s", line);
    if (data) { printf(" data="); hx((const unsigned char *)data, len); }
    printf("\n");
}
static int unhex(const char *h, unsigned char *o) { int n = 0; unsigned v; if (!strcmp(h, "-")) return 0;
    while (h[0] && h[1] && sscanf(h, "%2x", &v) == 1) { o[n++] = (unsigned char)v; h += 2; } return n; }
static void l(unsigned char *p, int v) { p[0] = (unsigned char)((unsigned)v >> 24); p[1] = (unsigned char)((unsigned)v >> 16);
    p[2] = (unsigned char)((unsigned)v >> 8); p[3] = (unsigned char)v; }
static int g(const unsigned char *p) { return (int)((unsigned)p[0] << 24 | (unsigned)p[1] << 16 | (unsigned)p[2] << 8 | p[3]); }
int main(void) {
    static char line[100000], a[50000], b[2000], c[2000], d[50000];
    static unsigned char x1[50000], x2[2000], x3[2000], buf[50000];
    unsigned char hconn[4], opt[4], hobj[4], cc[4], rc[4], bl[4], dl[4];
    l(hconn, 0);
    setvbuf(stdout, NULL, _IONBF, 0);
    while (fgets(line, sizeof line, stdin)) {
        char verb[16];
        memset(a, 0, sizeof a); memset(b, 0, sizeof b); memset(c, 0, sizeof c); memset(d, 0, sizeof d);
        if (sscanf(line, "%15s %49999s %1999s %1999s %49999s", verb, a, b, c, d) < 1) continue;
        l(cc, -9); l(rc, -9);
        if (!strcmp(verb, "HCONN")) { l(hconn, atoi(a)); continue; }
        if (!strcmp(verb, "UOW")) { ggmq_uow_end(atoi(a)); printf("UOW\n"); continue; }
        if (!strcmp(verb, "END")) { exit(0); }
        if (!strcmp(verb, "OPEN")) {
            int n = unhex(a, x1); l(opt, atoi(b)); l(hobj, 0);
            MQOPEN(hconn, x1, opt, hobj, cc, rc);
            printf("OPEN %d/%d hobj=%d od=", g(cc), g(rc), g(hobj)); hx(x1, n); printf("\n");
        } else if (!strcmp(verb, "CLOSE")) {
            l(hobj, atoi(a)); l(opt, atoi(b));
            MQCLOSE(hconn, hobj, opt, cc, rc);
            printf("CLOSE %d/%d hobj=%d\n", g(cc), g(rc), g(hobj));
        } else if (!strcmp(verb, "GET")) {
            l(hobj, atoi(a)); int n1 = unhex(b, x2), n2 = unhex(c, x3), n = atoi(d); l(bl, n); l(dl, -7);
            memset(buf, '.', sizeof buf);
            MQGET(hconn, hobj, x2, x3, bl, buf, dl, cc, rc);
            printf("GET %d/%d datalen=%d buf=", g(cc), g(rc), g(dl)); hx(buf, n > 0 ? n : 0);
            printf(" md="); hx(x2, n1); printf(" gmo="); hx(x3, n2); printf("\n");
        } else if (!strcmp(verb, "PUT") || !strcmp(verb, "PUT1")) {
            int put1 = !strcmp(verb, "PUT1"), n0 = 0;
            if (put1) n0 = unhex(a, x1); else l(hobj, atoi(a));
            int n1 = unhex(b, x2), n2 = unhex(c, x3), n = unhex(d, buf); l(bl, n);
            if (put1) MQPUT1(hconn, x1, x2, x3, bl, buf, cc, rc); else MQPUT(hconn, hobj, x2, x3, bl, buf, cc, rc);
            printf("%s %d/%d md=", verb, g(cc), g(rc)); hx(x2, n1); printf(" pmo="); hx(x3, n2); printf("\n");
            (void)n0;
        }
    }
    return 0;
}
"""

JAVA_PROBE = r"""
import p.cobolrt.mq.QueueManager;
import p.cobolrt.mq.QueueManager.Ref;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.file.Path;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;

public class Probe {
    static final HexFormat H = HexFormat.of().withUpperCase();
    static byte[] l(int v) { return new byte[] {(byte) (v >>> 24), (byte) (v >>> 16), (byte) (v >>> 8), (byte) v}; }
    static int g(byte[] b) { return (b[0] & 0xFF) << 24 | (b[1] & 0xFF) << 16 | (b[2] & 0xFF) << 8 | (b[3] & 0xFF); }
    static byte[] x(String h) { return h.equals("-") ? new byte[0] : H.parseHex(h); }
    static Ref r(byte[] b) { return new Ref(b, 0); }
    public static void main(String[] a) throws Exception {
        QueueManager qm = new QueueManager(Path.of(a[0]), (kind, kv) -> {
            StringBuilder s = new StringBuilder("EV " + kind);
            String data = null;
            for (int i = 0; i < kv.length; i += 2) {
                if (kv[i].equals("data")) { data = (String) kv[i + 1]; continue; }
                s.append(' ').append(kv[i]).append('=').append(kv[i + 1]);
            }
            if (data != null) s.append(" data=").append(data);
            System.out.println(s);
        }, a[1], a[2]);
        byte[] hconn = l(0);
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        String line;
        try {
            while ((line = in.readLine()) != null) {
                String[] t = line.trim().split(" ");
                byte[] cc = l(-9), rc = l(-9);
                switch (t[0]) {
                    case "HCONN" -> hconn = l(Integer.parseInt(t[1]));
                    case "UOW" -> { qm.uowEnd(t[1].equals("1")); System.out.println("UOW"); }
                    case "END" -> {
                        for (Map.Entry<String, List<String>> e : qm.end().entrySet()) {
                            System.out.println("Q " + e.getKey());
                            e.getValue().forEach(m -> System.out.println("M " + m));
                        }
                        return;
                    }
                    case "OPEN" -> {
                        byte[] od = x(t[1]), hobj = l(0);
                        qm.mqopen(r(hconn), r(od), r(l(Integer.parseInt(t[2]))), r(hobj), r(cc), r(rc));
                        System.out.println("OPEN " + g(cc) + "/" + g(rc) + " hobj=" + g(hobj) + " od=" + H.formatHex(od));
                    }
                    case "CLOSE" -> {
                        byte[] hobj = l(Integer.parseInt(t[1]));
                        qm.mqclose(r(hconn), r(hobj), r(l(Integer.parseInt(t[2]))), r(cc), r(rc));
                        System.out.println("CLOSE " + g(cc) + "/" + g(rc) + " hobj=" + g(hobj));
                    }
                    case "GET" -> {
                        byte[] md = x(t[2]), gmo = x(t[3]), dl = l(-7);
                        int n = Integer.parseInt(t[4]);
                        byte[] buf = new byte[50000];
                        java.util.Arrays.fill(buf, (byte) '.');
                        qm.mqget(r(hconn), r(l(Integer.parseInt(t[1]))), r(md), r(gmo), r(l(n)), r(buf), r(dl), r(cc), r(rc));
                        System.out.println("GET " + g(cc) + "/" + g(rc) + " datalen=" + g(dl) + " buf="
                                + H.formatHex(buf, 0, Math.max(n, 0)) + " md=" + H.formatHex(md) + " gmo=" + H.formatHex(gmo));
                    }
                    default -> {  // PUT, PUT1
                        byte[] md = x(t[2]), pmo = x(t[3]), data = x(t[4]);
                        if (t[0].equals("PUT1")) {
                            qm.mqput1(r(hconn), r(x(t[1])), r(md), r(pmo), r(l(data.length)), r(data), r(cc), r(rc));
                        } else {
                            qm.mqput(r(hconn), r(l(Integer.parseInt(t[1]))), r(md), r(pmo), r(l(data.length)), r(data), r(cc), r(rc));
                        }
                        System.out.println(t[0] + " " + g(cc) + "/" + g(rc) + " md=" + H.formatHex(md) + " pmo=" + H.formatHex(pmo));
                    }
                }
            }
        } catch (UnsupportedOperationException e) {
            if (!e.getMessage().matches("^MQ[A-Z0-9]*: .* is not modelled$")) throw e;
            System.out.println(REFUSED_LINE);
        }
    }
    static final String REFUSED_LINE = "REFUSED";
}
"""


def _jdk() -> Path | None:
    for var in ("JDK_17", "JAVA_HOME"):
        home = os.environ.get(var)
        if home and (Path(home) / "bin" / "javac").is_file():
            return Path(home) / "bin"
    return None


def _feed(steps) -> str:
    return "".join(" ".join(step) + "\n" for step, _ in steps)


@pytest.fixture(scope="module")
def c_driver(tmp_path_factory):
    if not shutil.which("gcc"):
        pytest.skip("needs a C compiler")
    d = tmp_path_factory.mktemp("mq_c")
    (d / "driver.c").write_text(C_DRIVER, newline="\n")
    run = subprocess.run(  # noqa: S603
        ["gcc", "-O0", "-Wall", "-o", str(d / "t"), str(d / "driver.c"), str(MQ_C)],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert run.returncode == 0, run.stderr
    return d / "t"


def _run_c(exe: Path, name: str, st: dict, steps, tmp: Path) -> list[str]:
    d = tmp / f"c-{name}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "mq.cfg").write_text(EQ.cfg(st, "latin-1"), encoding="ascii")
    (d / "mq.out").unlink(missing_ok=True)
    env = {**{k: os.environ[k] for k in ("SYSTEMROOT", "PATH") if k in os.environ},
           "GGCICS_DIR": str(d), "GGCICS_OUT": str(d), "COB_CURRENT_DATE": CLOCK}  # fmt: skip
    run = subprocess.run([str(exe)], input=_feed(steps), capture_output=True, text=True, check=False, env=env)  # noqa: S603
    out = run.stdout.splitlines()
    if run.returncode == 98:
        assert re.search(r"^MQ[A-Z0-9]*: .* is not modelled$", run.stderr.strip()), run.stderr
        return out + [REFUSED]
    assert run.returncode == 0, run.stderr
    if steps and steps[-1][0] == ("END",):
        out += (d / "mq.out").read_text(encoding="ascii").splitlines()
    return out


def _results(out: list[str]) -> list[str]:
    """The lines that answer a step (the events aside)."""
    return [x for x in out if not x.startswith(("EV ", "Q ", "M "))]


@pytest.mark.parametrize("name, st, steps", SCRIPTS, ids=[s[0] for s in SCRIPTS])
def test_the_oracle_model_gives_ibms_answers(c_driver, tmp_path, name, st, steps):
    got = _results(_run_c(c_driver, name, st, steps, tmp_path))
    wants = [w for step, w in steps if step[0] not in ("HCONN", "END")]
    if got and got[-1] == REFUSED:
        assert wants[len(got) - 1] == REFUSED, (name, got)
        assert all(w != REFUSED for w in wants[: len(got) - 1])
        return
    assert REFUSED not in wants, (name, got)
    assert len(got) == len(wants), (name, got)
    for line, want in zip(got, wants, strict=True):
        if want is not None:
            assert line.split()[1] == want, (name, line)


def test_the_unit_of_work_moves_messages_as_ibm_says(c_driver, tmp_path):
    """syncpoint-commit-and-backout, read: the backed-out request is got again with BackoutCount 1; only committed and
    NO-SYNCPOINT puts remain; an uncommitted put is invisible."""
    name, st, steps = next(s for s in SCRIPTS if s[0] == "syncpoint-commit-and-backout")
    out = _run_c(c_driver, name, st, steps, tmp_path)
    gets = [x for x in out if x.startswith("GET 0/0")]
    md_of_last = bytes.fromhex(gets[-1].split(" md=")[1].split()[0])
    assert md_of_last[96:100] == _l(1)  # BackoutCount
    assert b"r2" in bytes.fromhex(gets[-1].split(" buf=")[1].split()[0])
    left = "\n".join(x for x in out if x.startswith(("Q ", "M ")))
    assert "Q IN\nQ OUT\nM " in left and left.count("\nM ") == 1  # IN empty; OUT: reply3 only (reply1 was got)
    assert "7265706C7933" in left  # 'reply3'


def test_a_generated_msgid_and_the_default_context(c_driver, tmp_path):
    name, st, steps = next(s for s in SCRIPTS if s[0] == "put-msgid-and-context")
    out = _run_c(c_driver, name, st, steps, tmp_path)
    puts = [bytes.fromhex(x.split(" md=")[1].split()[0]) for x in out if x.startswith("PUT 0/0")]
    assert puts[0][48:72] == b"GGMQ" + b"%020d" % 1  # W4
    assert puts[0][272:276] == _l(1) and puts[0][304:320] == b"2022071810301525"  # MQAT_CICS, PutDate / PutTime (W8)
    assert puts[1][48:52] == b"MINE" and puts[1][272:276] == _l(0) and puts[1][304:320] == b" " * 16  # NO_CONTEXT
    stored = [x for x in out if x.startswith("M ")]
    md0 = bytes.fromhex(stored[0].split()[1])
    assert md0[40:44] == _l(3) and md0[44:48] == _l(1) and md0[28:32] == _l(37)  # the queue's defaults, the QM's CCSID
    assert stored[2].split()[2] == "-"  # the empty message


@pytest.mark.slow(reason="javac-compiles the MQ runtime, then starts one JVM and one C driver per script (18 s on CI)")
@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_runtime_is_the_oracle_model_byte_for_byte(c_driver, tmp_path):
    src = tmp_path / "src"
    (src / "p/cobolrt/mq").mkdir(parents=True)
    for f in (RT / "mq").glob("QueueManager.java"):
        (src / "p/cobolrt/mq" / f.name).write_text(f.read_text(encoding="utf-8").replace("__PACKAGE__", "p"))
    (src / "Probe.java").write_text(JAVA_PROBE)
    jdk = _jdk()
    javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"), *map(str, src.rglob("*.java"))],
                   check=True)  # fmt: skip
    bad = []
    for name, st, steps in SCRIPTS:
        cfg = tmp_path / f"{name}.cfg"
        cfg.write_text(EQ.cfg(st, "latin-1"), encoding="ascii")
        java = subprocess.run(  # noqa: S603
            [str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Probe", str(cfg),
             "20220718", "10301525"],
            input=_feed(steps), capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout.splitlines()  # fmt: skip
        c = _run_c(c_driver, name, st, steps, tmp_path)
        if java != c:
            bad.append(f"{name}\n  java {java}\n  c    {c}")
    assert not bad, "\n".join(bad)


SHORT_PROBE = r"""
import p.cobolrt.mq.QueueManager;
import p.cobolrt.mq.QueueManager.Ref;
import java.nio.file.Path;
import java.util.HexFormat;

public class Short {
    static final HexFormat H = HexFormat.of().withUpperCase();
    static byte[] l(int v) { return new byte[] {(byte) (v >>> 24), (byte) (v >>> 16), (byte) (v >>> 8), (byte) v}; }
    static int g(byte[] b) { return (b[0] & 0xFF) << 24 | (b[1] & 0xFF) << 16 | (b[2] & 0xFF) << 8 | (b[3] & 0xFF); }
    static Ref r(byte[] b) { return new Ref(b, 0); }
    public static void main(String[] a) throws Exception {
        QueueManager qm = new QueueManager(Path.of(a[0]), (kind, kv) -> {
            for (int i = 0; i < kv.length; i += 2) {
                if (kv[i].equals("data")) System.out.println("EV " + kind + " data=" + kv[i + 1]);
            }
        }, "20220718", "10301525");
        byte[] od = H.parseHex(a[1]), hobj = l(0), cc = l(-9), rc = l(-9), hconn = l(0);
        qm.mqopen(r(hconn), r(od), r(l(16)), r(hobj), r(cc), r(rc));
        for (int bl : new int[] {-1, 0, 5, 6, 7, 400}) {  // a 5-byte field; BufferLength less than, equal and past it
            byte[] data = {0x41, 0x42, 0x43, 0x44, 0x45};
            qm.mqput(r(hconn), r(hobj), r(H.parseHex(a[2])), r(H.parseHex(a[3])), r(l(bl)), r(data), r(cc), r(rc));
            System.out.println("PUT " + bl + " " + g(cc) + "/" + g(rc));
        }
        byte[] data = {0x41, 0x42, 0x43, 0x44, 0x45};
        qm.mqput1(r(hconn), r(od), r(H.parseHex(a[2])), r(H.parseHex(a[3])), r(l(8)), r(data), r(cc), r(rc));
        System.out.println("PUT1 8 " + g(cc) + "/" + g(rc));
        for (var e : qm.end().entrySet()) {
            e.getValue().forEach(m -> System.out.println("M " + m));
        }
    }
}
"""


@pytest.mark.slow(reason="javac-compiles the MQ runtime and starts one JVM (a few s on CI)")
@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_a_put_longer_than_the_callers_field_stores_and_reports_the_same_bytes(tmp_path):
    """The 501-request COPAUA0C scenario: BufferLength past the 200-byte field threw IndexOutOfBounds in the put event
    while the stored message was zero-padded. Every length class: negative, 0, short, equal, +1, far past; MQPUT and MQPUT1."""
    src = tmp_path / "src"
    (src / "p/cobolrt/mq").mkdir(parents=True)
    (src / "p/cobolrt/mq/QueueManager.java").write_text(
        (RT / "mq/QueueManager.java").read_text(encoding="utf-8").replace("__PACKAGE__", "p"), encoding="utf-8"
    )
    (src / "Short.java").write_text(SHORT_PROBE, encoding="utf-8")  # fmt: skip
    jdk = _jdk()
    javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"), *map(str, src.rglob("*.java"))],
              check=True)  # fmt: skip
    cfg = tmp_path / "short.cfg"
    cfg.write_text(EQ.cfg(state(q("OUT")), "latin-1"), encoding="ascii")
    out = subprocess.run(  # noqa: S603
        [str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Short", str(cfg),
         od("OUT").hex(), md().hex(), pmo().hex()],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.splitlines()  # fmt: skip

    def data(n: int) -> str:
        return (b"ABCDE" + bytes(max(n - 5, 0))).hex().upper()[: 2 * n]

    assert "PUT -1 2/2005" in out
    assert [ln.split("data=")[1] for ln in out if ln.startswith("EV MQPUT ")] == [
        "",
        "",
        data(5),
        data(6),
        data(7),
        data(400),
    ]
    assert [ln.split("data=")[1] for ln in out if ln.startswith("EV MQPUT1 ")] == [data(8)]
    assert "PUT1 8 0/0" in out
    stored = [ln.split()[-1] for ln in out if ln.startswith("M ")]
    assert [m.upper() for m in stored if m != "-"] == [data(n) for n in (0, 5, 6, 7, 400, 8) if n]  # event == stored


def test_every_reason_code_and_refusal_is_reached_by_a_script():
    wants = {w for _, _, steps in SCRIPTS for _, w in steps if w}
    assert {f"{SPEC.COMPLETION['MQCC_WARNING'] if r in SPEC.WARNINGS else 2}/{r}" for r in SPEC.REASONS if r} <= wants
    assert REFUSED in wants and "0/0" in wants
    calls = {step[0] for _, _, steps in SCRIPTS for step, _ in steps}
    assert {"OPEN", "CLOSE", "GET", "PUT", "PUT1", "UOW"} <= calls


# ---- 3. the wiring ------------------------------------------------------------------------------------------------
def _copybook(name: str) -> list[tuple[str, str, str | None]]:
    """(name, picture, value) of every elementary item of a stand-in copybook."""
    out = []
    for line in (COPY / f"{name}.cpy").read_text(encoding="ascii").splitlines():
        if line[6:7] == "*" or not line.strip():
            continue
        m = re.match(r"\s+\d+\s+([A-Z0-9-]+)(?:\s+PIC\s+(\S+)(?:\s+BINARY)?(?:\s+VALUE\s+(.+?))?)?\.\s*$", line)
        assert m, line
        if m.group(2):
            out.append((m.group(1), m.group(2), m.group(3)))
    return out


def _image(name: str) -> bytes:
    """The bytes a stand-in's VALUE clauses give its structure (S9(9) BINARY big-endian, X(n) padded with spaces)."""
    out = b""
    for _, pic, value in _copybook(name):
        if pic == "S9(9)":
            out += _l(int(value))
            continue
        n = int(re.fullmatch(r"X\((\d+)\)", pic).group(1))
        if value == "SPACES":
            out += b" " * n
        elif value == "LOW-VALUES":
            out += b"\0" * n
        else:
            out += _c(value.strip("'"), n)
    return out


@pytest.mark.parametrize("name, length", sorted(SPEC.LENGTHS.items()))
def test_each_stand_in_is_ibms_version_1_structure(name, length):
    assert len(_image(name)) == length  # MQ*_LENGTH_1


def test_the_stand_ins_hold_ibms_initial_values():
    assert _image("CMQMDV") == md()
    assert _image("CMQODV") == od("")
    assert _image("CMQGMOV") == gmo()
    assert _image("CMQPMOV") == pmo()
    assert _image("CMQTML") == EQ.mqtm({"appltype": 0}, "latin-1")


def test_cmqv_declares_only_the_modelled_constants_with_ibms_values():
    values = {n: v for n, _, v in _copybook("CMQV")}
    assert {values[f"MQRC-{SPEC.REASONS[r][5:].replace('_', '-')}"] for r in SPEC.REASONS} == {
        str(r) for r in SPEC.REASONS
    }
    assert values["MQRC-NO-MSG-AVAILABLE"] == "2033" and values["MQCC-WARNING"] == "1"
    assert (
        values["MQOO-INPUT-SHARED"] == "2"
        and values["MQOO-OUTPUT"] == "16"
        and values["MQOO-FAIL-IF-QUIESCING"] == "8192"
    )
    assert values["MQGMO-SYNCPOINT"] == "2" and values["MQGMO-WAIT"] == "1" and values["MQGMO-CONVERT"] == "16384"
    assert values["MQPMO-SYNCPOINT"] == "2" and values["MQPMO-DEFAULT-CONTEXT"] == "32"
    assert values["MQFMT-STRING"] == "'MQSTR   '" and values["MQMI-NONE"] == "LOW-VALUES"
    assert not any(n.startswith(("MQOO-BROWSE", "MQGMO-BROWSE", "MQPMO-NEW", "MQOO-INQUIRE")) for n in values)


@pytest.mark.parametrize("name", SPEC.STAND_INS)
def test_each_stand_in_says_it_is_gitgalaxys_not_ibms(name):
    head = (COPY / f"{name}.cpy").read_text(encoding="ascii").splitlines()[0]
    assert f"{name} stand-in (GitGalaxy-written, NOT IBM's member)" in head
    assert all(len(x) <= 72 for x in (COPY / f"{name}.cpy").read_text(encoding="ascii").splitlines())


def test_every_modelled_call_is_in_both_models_with_its_arity():
    c = MQ_C.read_text(encoding="utf-8")
    java = (RT / "cics" / "DetMq.java").read_text(encoding="utf-8")
    for call, params in SPEC.CALLS.items():
        sig = re.search(rf"^int {call}\(([^)]*)\)", c, re.M | re.S)
        assert sig and sig.group(1).count("unsigned char *") == len(params), call
        m = re.search(rf"public static void {call.lower()}\(CicsTask task, ([^)]*)\)", java, re.S)
        assert m and m.group(1).count("Field ") == len(params), call
    assert not set(SPEC.CALLS) & set(SPEC.UNMODELLED)


# ---- the translator ------------------------------------------------------------------------------------------------
def _gen(cics: bool):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import gen as G
    from gitgalaxy.tools.cobol_to_java.det import layout as L

    class Fake:
        def __init__(self):
            self.cics = object() if cics else None
            self.items = {}

        def resolve(self, ref):
            return self.items[ref.name]

        def field_expr(self, ref):
            return f"f_{ref.name}"

    g = Fake()
    for n, (usage, pic) in {
        "HC": ("BINARY", "S9(9)"), "HO": ("BINARY", "S9(9)"), "OPT": ("BINARY", "S9(9)"), "CC": ("BINARY", "S9(9)"),
        "RC": ("BINARY", "S9(9)"), "OD": ("DISPLAY", None), "C5": ("COMP-5", "S9(9)"), "HALF": ("BINARY", "S9(4)"),
    }.items():  # fmt: skip
        it = L.Item(level=1, name=n, section="WORKING-STORAGE", pic=pic, usage=usage)
        it.size = 4 if pic != "S9(4)" else 2
        g.items[n] = it
    return g, G


def _args(*names, mode="REFERENCE"):
    from gitgalaxy.tools.cobol_to_java.det import expr as E

    return [(mode, E.Ref(n)) for n in names]


def test_a_cics_mqopen_is_a_runtime_call_with_every_item_by_reference():
    from gitgalaxy.tools.cobol_to_java.det import mq

    g, _ = _gen(True)
    out = mq.call(g, "MQOPEN", _args("HC", "OD", "OPT", "HO", "CC", "RC"), "  ")
    assert out == ["  __PACKAGE__.cobolrt.cics.DetMq.mqopen(task, f_HC, f_OD, f_OPT, f_HO, f_CC, f_RC);"]


@pytest.mark.parametrize("prog, args, why", [
    ("MQOPEN", ("HC", "OD", "OPT", "HO", "CC"), "6 items BY REFERENCE"),  # arity
    ("MQCLOSE", ("HC", "HO", "C5", "CC", "RC"), "not a fullword BINARY item"),  # COMP-5: native on the oracle
    ("MQCLOSE", ("HC", "HO", "HALF", "CC", "RC"), "not a fullword BINARY item"),
    ("MQINQ", ("HC", "HO"), "object attributes"),
    ("MQCONN", ("OD", "HC", "CC", "RC"), "batch MQ"),
    ("MQCONNX", ("OD", "HC", "CC", "RC"), "batch MQ"),
    ("MQDISC", ("HC", "CC", "RC"), "batch MQ"),
    ("MQCMIT", ("HC", "CC", "RC"), "a unit of work of MQ's own"),
    ("MQBACK", ("HC", "CC", "RC"), "a unit of work of MQ's own"),
    ("MQBEGIN", ("HC", "OD", "CC", "RC"), "a unit of work of MQ's own"),
])  # fmt: skip
def test_what_the_runtime_does_not_model_is_a_named_hole(prog, args, why):
    from gitgalaxy.tools.cobol_to_java.det import mq

    g, G = _gen(True)
    with pytest.raises(G.Untranslatable, match=why):
        mq.call(g, prog, _args(*args), "")


def test_by_content_and_batch_mq_are_named_holes():
    from gitgalaxy.tools.cobol_to_java.det import mq

    g, G = _gen(True)
    with pytest.raises(G.Untranslatable, match="BY REFERENCE"):
        mq.call(g, "MQCLOSE", _args("HC", "HO", "OPT", "CC", "RC", mode="CONTENT"), "")
    g, G = _gen(False)
    with pytest.raises(G.Untranslatable, match="outside CICS: batch MQ"):
        mq.call(g, "MQCLOSE", _args("HC", "HO", "OPT", "CC", "RC"), "")


def test_every_mq_name_is_handled_and_a_dynamic_call_may_name_one():
    from gitgalaxy.tools.cobol_to_java.det import dyncall, mq

    assert all(mq.handles(n) for n in (*SPEC.CALLS, *SPEC.UNMODELLED))
    assert not mq.handles("MQSTUFF")
    assert "MQ_CALLS" in Path(dyncall.__file__).read_text(encoding="utf-8")  # targets() accepts a modelled MQI name


# ---- the harness (tests/tools/equivalence_mq.py, equivalence_cics._numbered) -------------------------------------------
def test_a_stated_message_has_ibms_initial_mqmd_with_the_queue_defaults():
    st = state(
        ("A", {"priority": 4, "persistence": 1, "messages": [{"data": "hi", "correlid": "C1", "replytoq": "R"}]})
    )
    line = EQ.cfg(st, "latin-1").splitlines()[-1].split()
    image = bytes.fromhex(line[2])
    assert line[:2] == ["M", "A"] and bytes.fromhex(line[3]) == b"hi"
    assert image[:8] == b"MD  " + _l(1) and image[40:48] == _l(4) + _l(1) and image[28:32] == _l(37)
    assert image[48:72] == b"GGMQSTATED" + b"%014d" % 1 and image[72:74] == b"C1" and image[74:96] == b"\0" * 22
    assert image[100:101] == b"R" and image[148:152] == b"CSQ1"  # a ReplyToQ stated: the local queue manager
    assert len(image) == EQ.MDLEN


def test_a_scenario_states_its_own_messages_or_queues():
    case = {"mq": state(q("A", "x"), q("B"))}
    assert EQ.state(case, {"mq_messages": {"B": [{"data": "y"}]}})["queues"]["B"]["messages"] == [{"data": "y"}]
    assert EQ.state(case, {})["queues"]["A"]["messages"][0]["data"] == "x"
    assert EQ.state(case, {"mq": state(q("C"))})["queues"].keys() == {"C"}
    assert EQ.state({}, {}) is None
    with pytest.raises(ValueError, match="a queue the"):
        EQ.state(case, {"name": "s", "mq_messages": {"NOPE": []}})
    with pytest.raises(ValueError, match="not a queue name"):
        EQ.cfg(state(q("BAD NAME")), "latin-1")


def test_start_data_is_the_trigger_message_text_or_bytes():
    tm = EQ.start_data({}, {"start_data": [{"mqtm": {"qname": "IN.Q", "applid": "CDRD"}}]}, "latin-1")[0]
    assert len(tm) == 684 and tm[:8] == b"TM  " + _l(1) and tm[8:12] == b"IN.Q" and tm[168:172] == _l(1)
    assert tm[172:176] == b"CDRD"  # ApplType MQAT_CICS, ApplId
    case = {"start_data": [{"text": "AB"}]}
    assert EQ.start_data(case, {}, "latin-1") == [b"AB"]
    assert EQ.start_data(case, {"start_data": [{"hex": "00FF"}]}, "latin-1") == [b"\0\xff"]
    assert EQ.start_data(case, {"start_data": []}, "latin-1") == []


def test_the_oracles_events_read_as_the_runtime_records_them(tmp_path):
    e = EQ.cobol_event("MQGET", {"queue": "A", "cc": "1", "rc": "2080", "len": "10"}, b"abcd")
    assert e == {"event": "MQGET", "queue": "A", "cc": 1, "rc": 2080, "len": 10, "data": "61626364"}
    o = EQ.cobol_event("MQOPEN", {"queue": "A", "cc": "0", "rc": "0", "options": "8194", "hobj": "1"}, b"")
    assert o == {"event": "MQOPEN", "queue": "A", "cc": 0, "rc": 0, "options": 8194, "hobj": 1}
    assert EQ.compare(o, {**o, "rc": 2085}) == [{"field": "rc", "cobol": 0, "java": 2085}]
    (tmp_path / "mq.out").write_text("Q A\nM 00 -\nQ B\n", encoding="ascii")
    assert EQ.queues_left(tmp_path / "mq.out") == {"A": ["00 -"], "B": []}
    assert EQ.queues_left(tmp_path / "none") is None
    left = {"event": "MQ-QUEUES", "queues": {"A": []}}
    assert EQ.compare(left, {**left, "queues": {"A": ["00 -"]}})[0]["field"] == "queues"


def test_a_resp_number_keeps_the_sequence_area_in_columns_73_to_80():
    import equivalence_cics as ec

    line = "016100     IF WS-CICS-RESP1-CD =  DFHRESP(NORMAL)                       01450012"
    out = ec._numbered(line)
    assert out[72:] == "01450012" and len(out) == 80 and out[:72].rstrip().endswith("=  0")
    assert ec._numbered("           IF X = DFHRESP(NOTFND)") == "           IF X = 13"  # no sequence area: as before


# ---- #5278: the burned estates ---------------------------------------------------------------------------------------
BURNED_CORPORA = (
    "aws-mainframe-modernization-carddemo",
    "cics-banking-sample-application-cbsa",
    "cics-genapp",
    "zecs",
    "dbb-mortgage-application",
    "cics-async-api-credit-card-application-example",
)
MQ_CALL = re.compile(r"\bCALL\s+['\"](MQ[A-Z0-9]+)['\"]", re.IGNORECASE)


def _burned_mq_calls() -> dict[str, set[str]]:
    corpora = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    found: dict[str, set[str]] = {}
    for name in BURNED_CORPORA:
        for p in (corpora / name).rglob("*") if (corpora / name).is_dir() else ():
            if p.suffix.lower() not in (".cbl", ".cob", ".cobol") or not p.is_file():
                continue
            for line in p.read_text(encoding="latin-1").splitlines():
                if len(line) > 6 and line[6] not in "*/":  # a comment line names no call
                    for m in MQ_CALL.finditer(line[6:72]):
                        found.setdefault(p.stem.upper(), set()).add(m.group(1).upper())
    return found


def test_no_burned_program_calls_an_mq_routine_the_models_lack():
    """The MQI calls the burned estates make are all modelled (MQINQ / MQSET, used by none, stay refused: #4892)."""
    calls = _burned_mq_calls()
    if not calls:
        pytest.skip("needs the burned mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    assert {"CODATE01", "COACCT01", "COPAUA0C"} <= set(calls)
    used = set().union(*calls.values())
    assert used <= set(SPEC.CALLS), sorted(used - set(SPEC.CALLS))
    assert not used & set(SPEC.UNMODELLED)
    assert not used & {"MQINQ", "MQSET"}
    assert calls["COPAUA0C"] == {"MQOPEN", "MQGET", "MQPUT1", "MQCLOSE"}


BATCH_MQ_NAME = re.compile(r"\bMQ(?:CONNX?|DISC)\b", re.IGNORECASE)


def test_no_burned_program_is_batch_mq():
    """#5259 (W6): every burned MQ program is a CICS program, and no burned source names MQCONN / MQCONNX / MQDISC
    in code (a literal or a data item a dynamic CALL could hold), so batch MQ has no burned consumer to prove."""
    corpora = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    calls = _burned_mq_calls()
    if not calls:
        pytest.skip("needs the burned mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    named: list[str] = []
    cics: dict[str, bool] = {}
    for name in BURNED_CORPORA:
        for p in (corpora / name).rglob("*") if (corpora / name).is_dir() else ():
            if p.suffix.lower() not in (".cbl", ".cob", ".cobol", ".cpy") or not p.is_file():
                continue
            code = [
                ln[6:72] for ln in p.read_text(encoding="latin-1").splitlines() if len(ln) > 6 and ln[6] not in "*/"
            ]
            if any(BATCH_MQ_NAME.search(ln) for ln in code):
                named.append(p.name)
            if p.stem.upper() in calls:
                cics[p.stem.upper()] = any(re.search(r"\bEXEC\s+CICS\b", ln, re.IGNORECASE) for ln in code)
    assert not named, named
    assert cics and all(cics.values()), cics


UOW_MQ_NAME = re.compile(r"\bMQ(?:BEGIN|CMIT|BACK)\b", re.IGNORECASE)


def test_no_burned_program_names_an_mq_unit_of_work_call():
    """#5259 (W5): no burned source names MQBEGIN / MQCMIT / MQBACK in code (a literal or a data item a dynamic CALL could
    hold): every burned MQ unit of work is the CICS task's (SYNCPOINT / ROLLBACK), which is modelled, so MQ's own has no
    burned consumer to prove."""
    corpora = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    if not _burned_mq_calls():
        pytest.skip("needs the burned mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    named: list[str] = []
    for name in BURNED_CORPORA:
        for p in (corpora / name).rglob("*") if (corpora / name).is_dir() else ():
            if p.suffix.lower() not in (".cbl", ".cob", ".cobol", ".cpy") or not p.is_file():
                continue
            code = [
                ln[6:72] for ln in p.read_text(encoding="latin-1").splitlines() if len(ln) > 6 and ln[6] not in "*/"
            ]
            if any(UOW_MQ_NAME.search(ln) for ln in code):
                named.append(p.name)
    assert not named, named


def _c_masks(*names: str) -> dict[str, int]:
    """The `#define NAME expr` integer masks of ggmq.c (an expression of numbers and earlier defines)."""
    defs: dict[str, int] = {}
    for m in re.finditer(r"^#define\s+(\w+)\s+(\(?[\w |()]+\)?)\s*(?:/\*.*)?$", MQ_C.read_text(), re.MULTILINE):
        try:
            defs[m.group(1)] = eval(m.group(2), {"__builtins__": {}}, dict(defs))  # noqa: S307 -- numbers, | and names
        except NameError:
            continue
    return {n: defs[n] for n in names}


def test_copaua0c_options_sit_inside_what_the_oracle_models():
    """#5278: the option words CardDemo COPAUA0C builds (MQOPEN, MQGET, MQPUT1, MQCLOSE) are all inside the modelled
    sets, so the oracle would not stop its run by name; the values are CMQV's, the masks ggmq.c's own."""
    v = {n: int(val) for n, _, val in _copybook("CMQV") if val is not None and val.lstrip("-").isdigit()}
    masks = _c_masks("OO_MODELLED", "GMO_MODELLED", "PMO_MODELLED")
    get = v["MQGMO-NO-SYNCPOINT"] | v["MQGMO-WAIT"] | v["MQGMO-CONVERT"] | v["MQGMO-FAIL-IF-QUIESCING"]
    put1 = v["MQPMO-NO-SYNCPOINT"] | v["MQPMO-DEFAULT-CONTEXT"]
    assert v["MQOO-INPUT-SHARED"] & ~masks["OO_MODELLED"] == 0
    assert get & ~masks["GMO_MODELLED"] == 0
    assert put1 & ~masks["PMO_MODELLED"] == 0
    assert v["MQCO-NONE"] == 0  # the only MQCLOSE option modelled (W6)


def test_every_burned_program_includes_only_copybooks_the_models_ship():
    """#5278: every CMQ* member a burned program COPYs is a GitGalaxy stand-in, so no MQ copybook gap (CMQGMOV, CMQODV)
    is left to refuse any of them whole; COPAUA0C, CODATE01 and COACCT01 are among them."""
    calls = _burned_mq_calls()
    if not calls:
        pytest.skip("needs the burned mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    corpora = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    copied: dict[str, set[str]] = {}
    for name in BURNED_CORPORA:
        for p in (corpora / name).rglob("*") if (corpora / name).is_dir() else ():
            if p.suffix.lower() in (".cbl", ".cob", ".cobol") and p.is_file():
                text = p.read_text(encoding="latin-1")
                for m in re.findall(r"^.{6}[ \t]+COPY\s+(CMQ\w*)", text, re.M | re.IGNORECASE):
                    copied.setdefault(p.stem.upper(), set()).add(m.upper())
    assert {"CODATE01", "COACCT01", "COPAUA0C"} <= set(copied), sorted(copied)
    used = set().union(*copied.values())
    assert used <= set(SPEC.STAND_INS), sorted(used - set(SPEC.STAND_INS))
    assert all((COPY / f"{n}.cpy").is_file() for n in used)


def test_copaua0c_translates_with_no_mq_hole(tmp_path):
    """#5278: no hole of CardDemo COPAUA0C is an MQ one -- its MQOPEN / MQGET / MQPUT1 / MQCLOSE and the CMQ* layouts
    translate under CICS; EXEC DLI (ISRT, REPL, DLET, #5278) no longer holds it either, and the remaining holes are not
    MQ's (they are named here so a change that moves them is seen)."""
    pytest.importorskip("tree_sitter_language_pack")
    corpora = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    corpus = corpora / "aws-mainframe-modernization-carddemo"
    src = corpus / "app/app-authorization-ims-db2-mq/cbl/COPAUA0C.cbl"
    if not src.is_file():
        pytest.skip("needs the burned mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    stub = "public class COPAUA0C { void f() { runTask(CicsTask t); } }"  # the marker that makes it a CICS port
    res = P.translate(
        src, [corpus / "app/cpy", corpus / "app/app-authorization-ims-db2-mq/cpy"], stub, "pkg", None, tmp_path
    )
    holes = [str(h) for h in res.stats["holes"]]
    assert holes
    assert not [h for h in holes if re.search(r"\bMQ|CMQ|batch MQ|copybook", h, re.IGNORECASE)], holes
    assert not [h for h in holes if "EXEC DLI" in h], holes
    assert not [h for h in holes if "DIBSTAT" not in h and "KEYLENGTH" not in h
                and "INITIALIZE REPLACING" not in h], holes  # fmt: skip
