"""#4770 (register X30): a COUNTER and a DCOUNTER share one namespace, so a fullword GET / QUERY COUNTER can meet a counter that
holds more than a signed fullword. IBM (CICS TS 6.x, GET COUNTER and GET DCOUNTER, QUERY COUNTER and QUERY DCOUNTER): "LENGERR
occurs for COUNTER commands only", for "a counter that was defined by a DCOUNTER command ... [with] a value that is too large to be
correctly represented as a fullword signed binary value"; "the named counter server completes the operation, and returns a warning
response"; "the data area contains the low-order 32 bits ... which could be a negative number"; RESP2 1 the value overflowed into the
sign bit, 2 "too large ... by only 1 bit ... exactly 1", 3 "greater than 1"; at counter-at-limit LENGERR cannot occur (the value is the
maximum plus one).

The stub (ggcics.c) and CicsTask answer one scenario list. A step is "defc NAME VALUE [MIN MAX]" (DEFINE COUNTER), "defd NAME VALUE
[MIN MAX]" (DEFINE DCOUNTER), "getc NAME INC" / "getd NAME INC" (GET COUNTER / DCOUNTER), "qc NAME LIMITS" (QUERY COUNTER, LIMITS 1:
with MINIMUM and MAXIMUM). An answer is "resp/resp2", then on NORMAL or LENGERR the value (a COUNTER's as a signed fullword, a
DCOUNTER's unsigned)."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cics_runtimes import _cics_task, _stub, _stub_base_env, needs_cc, needs_javac  # noqa: E402

_BIG = "9223372036854775813"  # 2**63 + 5: past a signed doubleword
_LIMIT_MSG = "QUERY COUNTER MINIMUM / MAXIMUM of a counter whose limits are beyond a fullword"

# (steps, answers, the refusal the last step ends in)
_CASES = [
    # the boundary at 2**31: the last value a fullword holds, then the sign bit (RESP2 1); the counter went on (the GET completed)
    (
        ["defd A 2147483647", "getc A 1", "getc A 1", "qc A 0", "getd A 1"],
        ["0/0", "0/0 2147483647", "22/1 -2147483648", "22/1 -2147483647", "0/0 2147483649"],
        None,
    ),
    # 2**32 - 1 is still the sign bit (RESP2 1, -1); 2**32 is exactly one bit more (RESP2 2); the DCOUNTER form reads it whole
    (
        ["defd B 4294967295", "getc B 1", "qc B 0", "getc B 1", "getd B 1"],
        ["0/0", "22/1 -1", "22/2 0", "22/2 0", "0/0 4294967297"],
        None,
    ),
    # past 2**33 the overflow is above 1 (RESP2 3); the low 32 bits are the VALUE
    (["defd C 8589934592", "qc C 0", "getc C 1"], ["0/0", "22/3 0", "22/3 0"], None),
    (["defd D 1099511627777", "qc D 0", "getc D 1"], ["0/0", "22/3 1", "22/3 1"], None),
    # a value past a signed doubleword (a DCOUNTER holds an unsigned one)
    (["defd E " + _BIG, "qc E 0", "getc E 1"], ["0/0", "22/3 5", "22/3 5"], None),
    # counter-at-limit: LENGERR cannot occur, the value is the maximum plus one (a COUNTER: the largest negative number)
    (
        ["defc F 2147483647 0 2147483647", "getc F 1", "qc F 0", "qc F 1", "getc F 1", "getd F 1"],
        ["0/0", "0/0 2147483647", "0/0 -2147483648", "0/0 -2147483648 0 2147483647", "72/101", "72/101"],
        None,
    ),
    # a DCOUNTER with limits past a fullword: its value past 31 bits is LENGERR; its limits do not fit a COUNTER's MINIMUM / MAXIMUM
    (["defd G 2147483648 0 2147483658", "qc G 0"], ["0/0", "22/1 -2147483648"], None),
    (["defd G 2147483648 0 2147483658", "qc G 1"], ["0/0"], _LIMIT_MSG),
    # one namespace: the other form's DEFINE of a name is a duplicate (202), and either form's GET reads the counter
    (
        ["defc H 5", "defd H 7", "defd I 1", "defc I 1", "defc J 3", "getd J 1", "getc J 1", "getc Z 1", "qc Z 0"],
        ["0/0", "16/202", "0/0", "16/202", "0/0", "0/0 3", "0/0 4", "16/201", "16/201"],
        None,
    ),
]

_MAIN = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCGCNT(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap);
int GGCGDCN(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap);
int GGCDCNT(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen);
int GGCDDCN(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen);
int GGCQCNT(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen);
static gg_cics c;
static void be(unsigned char *p, const char *w, int width, int *len) {
    unsigned long long n = strtoull(w, NULL, 10);
    for (int j = width - 1; j >= 0; j--) { p[j] = (unsigned char)(n & 255); n >>= 8; }
    *len = width;
}
static unsigned long long un(const unsigned char *p, int w) { unsigned long long v = 0; for (int j = 0; j < w; j++) v = v * 256 + p[j]; return v; }
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        char *w[8] = {0};
        int k = 0, vl, ll, hl;
        unsigned char v[8], lo[8], hi[8];
        for (char *t = strtok(argv[i], " "); t && k < 8; t = strtok(NULL, " ")) w[k++] = t;
        memset(c.qname, ' ', 16); memcpy(c.qname, w[1], strlen(w[1]));
        memset(c.name1, ' ', 8);
        if (w[0][0] == 'd') {
            int width = w[0][3] == 'd' ? 8 : 4;
            be(v, w[2], width, &vl);
            if (w[3]) { be(lo, w[3], width, &ll); be(hi, w[4], width, &hl); } else { ll = hl = 0; }
            (width == 8 ? GGCDDCN : GGCDCNT)(&c, v, vl, lo, ll, hi, hl);
            printf("%d/%d\n", c.resp, c.resp2);
        } else if (w[0][0] == 'g') {
            int dbl = w[0][3] == 'd', width = dbl ? 8 : 4;
            be(lo, w[2], width, &ll);
            (dbl ? GGCGDCN : GGCGCNT)(&c, v, width, lo, width, 0);
            if (c.resp == 0 || c.resp == 22) printf("%d/%d %lld\n", c.resp, c.resp2, dbl ? (long long)un(v, 8) : (long long)(int)un(v, 4));
            else printf("%d/%d\n", c.resp, c.resp2);
        } else {
            int lim = atoi(w[2]);
            GGCQCNT(&c, v, 4, lo, lim ? 4 : 0, hi, lim ? 4 : 0);
            if (c.resp != 0 && c.resp != 22) printf("%d/%d\n", c.resp, c.resp2);
            else if (lim) printf("%d/%d %d %d %d\n", c.resp, c.resp2, (int)un(v, 4), (int)un(lo, 4), (int)un(hi, 4));
            else printf("%d/%d %d\n", c.resp, c.resp2, (int)un(v, 4));
        }
    }
    return 0;
}
"""


@needs_cc
def test_the_stub_answers_a_fullword_command_over_a_counter_past_31_bits_with_lengerr(tmp_path):
    exe = _stub(tmp_path, _MAIN)
    for n, (steps, answers, refusal) in enumerate(_CASES):
        work = tmp_path / f"c{n}"
        (work / "out").mkdir(parents=True)
        (work / "counters.cfg").write_text("", encoding="ascii")
        env = {**_stub_base_env(), "GGCICS_DIR": str(work), "GGCICS_OUT": str(work / "out")}
        run = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        got = run.stdout.splitlines()
        if refusal is None:
            assert run.returncode == 0 and got == answers, (steps, got)
        else:
            assert run.returncode == 98 and got[: len(answers)] == answers and refusal in run.stdout, (
                steps,
                run.stdout,
            )


@needs_javac
def test_cics_task_answers_as_the_stub_does(tmp_path):
    """CicsTask.fullwordGet (the det translator's call after a COUNTER GET) and queryCounter answer the scenarios above."""
    parts = []
    for steps, answers, refusal in _CASES:
        body = ""
        for st in steps:
            w = st.split()
            nm = f'"{w[1]}"'
            if w[0] in ("defc", "defd"):
                dbl = w[0] == "defd"
                lo = f'Long.parseUnsignedLong("{w[3]}")' if len(w) > 3 else "0L"
                hi = f'Long.parseUnsignedLong("{w[4]}")' if len(w) > 3 else ("-1L" if dbl else "2147483647L")
                call = "defineDcounter" if dbl else "defineCounter"
                body += (f'r = t.{call}("", {nm}, Long.parseUnsignedLong("{w[2]}"), {lo}, {hi}); '
                         'System.out.println(r[0] + "/" + r[1]);\n')  # fmt: skip
            elif w[0] == "getd":
                body += (f'g = t.getCounter("", {nm}, {w[2]}L, false); '
                         'System.out.println(g[0] == 0 ? "0/0 " + Long.toUnsignedString(g[2]) : g[0] + "/" + g[1]);\n')  # fmt: skip
            elif w[0] == "getc":
                body += (f'g = t.fullwordGet("", {nm}, t.getCounter("", {nm}, {w[2]}L, false)); '
                         'System.out.println(g[0] == 0 || g[0] == 22 ? g[0] + "/" + g[1] + " " + g[2] : g[0] + "/" + g[1]);\n')  # fmt: skip
            else:
                lim = "true" if w[2] == "1" else "false"
                tail = ' + " " + q[3] + " " + q[4]' if lim == "true" else ""
                body += (f'q = t.queryCounter("", {nm}, {lim}); '
                         f'System.out.println(q[0] == 0 || q[0] == 22 ? q[0] + "/" + q[1] + " " + q[2]{tail} : q[0] + "/" + q[1]);\n')  # fmt: skip
        parts.append(
            '{ CicsTask t = new CicsTask("ZC01", "ENTER", null, null);\n'
            "int[] r, q; long[] g;\n"
            f'try {{\n{body}}} catch (UnsupportedOperationException e) {{ System.out.println("refused " + e.getMessage()); }} }}\n'
        )
    out = _cics_task(tmp_path, "\n".join(parts)).splitlines()
    pos = 0
    for _steps, answers, refusal in _CASES:
        assert out[pos : pos + len(answers)] == answers, (answers, out[pos : pos + len(answers)])
        pos += len(answers)
        if refusal is not None:
            assert out[pos] == f"refused {refusal}: not modelled", (refusal, out[pos])
            pos += 1
    assert pos == len(out)
