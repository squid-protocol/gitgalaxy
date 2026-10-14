"""#5039 (register X53): REWIND / UPDATE COUNTER and DCOUNTER, GET COUNTER / DCOUNTER REDUCE / COMPAREMIN / COMPAREMAX, as IBM
documents them (CICS TS 6.x, EXEC CICS REWIND / UPDATE / GET COUNTER and DCOUNTER), run on the stub (ggcics.c) and on CicsTask
over ONE scenario list, once as fullword COUNTERs and once as doubleword DCOUNTERs (the same small numbers: both answer alike).

IBM: REWIND "resets a named counter that has reached its limit" to its minimum, SUPPRESSED RESP2 102 for one that has not, INVREQ
406 for an INCREMENT beyond (maximum - minimum) + 1; UPDATE sets the current value, INVREQ 406 below the minimum or above the maximum
plus 1; GET REDUCE: "the request succeeds with the current value set to the maximum plus 1"; GET COMPAREMIN / COMPAREMAX: the value
is returned when at or above / at or below them (either, when COMPAREMAX is below COMPAREMIN), else SUPPRESSED RESP2 103."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cics_runtimes import _cics_task, _stub, _stub_base_env, needs_cc, needs_javac  # noqa: E402

# a step: "def NAME POOL VALUE MIN MAX", "get NAME POOL INC WRAP REDUCE CMIN CMAX", "rew NAME POOL INC", "upd NAME POOL VALUE",
# "qry NAME POOL LIMITS", "del NAME POOL" ("-": omitted). A case: (the counter a scenario states, steps, answers, the refusal the
# last step ends in, the forms it holds for). Answer: "resp/resp2", then on NORMAL a get's / qry's values.
_CASES = [
    # REDUCE: an INCREMENT that carries the counter past MAXIMUM + 1 leaves it at MAXIMUM + 1 (and the value is handed out)
    (
        "",
        [
            "def A - 8 0 10",
            "get A - 5 0 1 - -",
            "qry A - 0",
            "get A - 1 0 0 - -",
            "rew A - -",
            "qry A - 1",
            "rew A - -",
        ],
        ["0/0", "0/0 8", "0/0 11", "72/101", "0/0", "0/0 0 0 10", "72/102"],
        None,
        "CD",
    ),
    # REWIND: only a counter at its limit (MAXIMUM + 1), to its minimum; 406 beyond the range; 201 / 403 / 404
    (
        "",
        [
            "def B - 3 2 9",
            "rew B - -",
            "get B - 6 0 0 - -",
            "rew B - -",
            "get B - 1 0 0 - -",
            "rew B - -",
            "qry B - 1",
            "rew B - -",
            "rew B - 1",
            "rew B - 9",
            "rew Z - -",
            "rew x - -",
            "rew B p -",
        ],
        [
            "0/0",
            "72/102",
            "0/0 3",
            "72/102",
            "0/0 9",
            "0/0",
            "0/0 2 2 9",
            "72/102",
            "72/102",
            "16/406",
            "16/201",
            "16/404",
            "16/403",
        ],
        None,
        "CD",
    ),
    # UPDATE: a value from MINIMUM to MAXIMUM + 1; 406 outside; 201 / 403 / 404
    (
        "",
        [
            "def U - 4 2 9",
            "upd U - 7",
            "qry U - 0",
            "upd U - 10",
            "get U - 1 0 0 - -",
            "upd U - 1",
            "upd U - 11",
            "upd U - 2",
            "get U - 1 0 0 - -",
            "upd Z - 1",
            "upd x - 1",
            "upd U p 1",
        ],
        ["0/0", "0/0", "0/0 7", "0/0", "72/101", "16/406", "16/406", "0/0", "0/0 2", "16/201", "16/404", "16/403"],
        None,
        "CD",
    ),
    # COMPAREMIN / COMPAREMAX test the value handed out: out of range is SUPPRESSED 103 and the counter stays; COMPAREMAX below
    # COMPAREMIN: in range when it meets either
    (
        "",
        [
            "def C - 5 0 10",
            "get C - 1 0 0 6 -",
            "qry C - 0",
            "get C - 1 0 0 5 -",
            "get C - 1 0 0 - 5",
            "get C - 1 0 0 - 6",
            "get C - 1 0 0 3 8",
            "get C - 1 0 0 9 2",
            "get C - 1 0 0 8 2",
            "get C - 1 0 0 9 2",
            "get C - 1 0 0 11 10",
            "get C - 1 0 0 - -",
        ],
        ["0/0", "72/103", "0/0 5", "0/0 5", "72/103", "0/0 6", "0/0 7", "72/103", "0/0 8", "0/0 9", "0/0 10", "72/101"],
        None,
        "CD",
    ),
    # a counter a scenario states (no limits): COMPARE still tests its value; REDUCE has nothing to reduce
    (
        "LEG 5",
        ["get LEG - 1 0 0 6 -", "get LEG - 1 0 0 5 5", "get LEG - 1 0 1 - -"],
        ["72/103", "0/0 5", "0/0 6"],
        None,
        "CD",
    ),
    # refused by name
    ("", ["def I - 5 0 10", "rew I - 0"], ["0/0"], "REWIND COUNTER with an INCREMENT not above zero", "CD"),
    ("", ["def I - 11 0 10", "rew I - 2"], ["0/0"], "REWIND COUNTER with an INCREMENT above 1", "CD"),
    ("LEG 5", ["rew LEG - -"], [], "REWIND COUNTER of a counter whose limits the run does not state", "CD"),
    ("LEG 5", ["upd LEG - 1"], [], "UPDATE COUNTER of a counter whose limits the run does not state", "CD"),
    ("", ["def I - 5 0 10", "get I - 1 1 1 - -"], ["0/0"], "GET COUNTER with both REDUCE and WRAP", "CD"),
    (
        "",
        ["def I - 11 0 10", "get I - 1 0 1 - -"],
        ["0/0"],
        "GET COUNTER REDUCE at a counter already at its limit",
        "CD",
    ),
    (
        "",
        ["def I - 11 0 10", "get I - 1 0 0 1 -"],
        ["0/0"],
        "GET COUNTER COMPAREMIN / COMPAREMAX at a counter already at its limit",
        "CD",
    ),
    # a negative number: refused for a fullword counter, an unsigned doubleword's huge value for a DCOUNTER
    ("", ["def I - 5 0 10", "upd I - -1"], ["0/0"], "UPDATE COUNTER with a VALUE below zero", "C"),
    ("", ["def I - 5 0 10", "upd I - -1"], ["0/0", "16/406"], None, "D"),
    ("", ["def I - 5 0 10", "get I - 1 0 0 -1 -"], ["0/0"], "GET COUNTER COMPAREMIN / COMPAREMAX below zero", "C"),
    ("", ["def I - 5 0 10", "get I - 1 0 0 -1 -"], ["0/0", "72/103"], None, "D"),
]

_MAIN = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCGCNX(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap, int reduce,
            unsigned char *cmin, int cminlen, unsigned char *cmax, int cmaxlen);
int GGCGDCX(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap, int reduce,
            unsigned char *cmin, int cminlen, unsigned char *cmax, int cmaxlen);
int GGCRCNT(gg_cics *c, unsigned char *inc, int inclen);
int GGCRDCN(gg_cics *c, unsigned char *inc, int inclen);
int GGCUCNT(gg_cics *c, unsigned char *val, int vallen);
int GGCUDCN(gg_cics *c, unsigned char *val, int vallen);
int GGCDCNT(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen);
int GGCDDCN(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen);
int GGCQCNT(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen);
int GGCQDCN(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen);
static gg_cics c;
#define W __W__
static void be(unsigned char *p, const char *w, int *len) {
    long long n = strtoll(w, NULL, 10);
    for (int j = W - 1; j >= 0; j--) { p[j] = (unsigned char)(n & 255); n >>= 8; }
    *len = strcmp(w, "-") == 0 ? 0 : W;
}
static unsigned long long un(const unsigned char *p) { unsigned long long v = 0; for (int j = 0; j < W; j++) v = v * 256 + p[j]; return v; }
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        char *w[8] = {0};
        int k = 0, vl, ll, hl;
        unsigned char v[8], lo[8], hi[8];
        for (char *t = strtok(argv[i], " "); t && k < 8; t = strtok(NULL, " ")) w[k++] = t;
        memset(c.qname, ' ', 16); memcpy(c.qname, w[1], strlen(w[1]));
        memset(c.name1, ' ', 8); if (strcmp(w[2], "-") != 0) memcpy(c.name1, w[2], strlen(w[2]) > 8 ? 8 : strlen(w[2]));
        if (strcmp(w[0], "def") == 0) {
            be(v, w[3], &vl); be(lo, w[4], &ll); be(hi, w[5], &hl);
            (W == 4 ? GGCDCNT : GGCDDCN)(&c, v, vl, lo, ll, hi, hl);
            printf("%d/%d\n", c.resp, c.resp2);
        } else if (strcmp(w[0], "get") == 0) {
            int cl, ch;
            unsigned char cmin[8], cmax[8];
            be(lo, w[3], &ll); be(cmin, w[6], &cl); be(cmax, w[7], &ch);
            (W == 4 ? GGCGCNX : GGCGDCX)(&c, v, W, lo, W, atoi(w[4]), atoi(w[5]), cmin, cl, cmax, ch);
            if (c.resp == 0) printf("0/0 %llu\n", un(v)); else printf("%d/%d\n", c.resp, c.resp2);
        } else if (strcmp(w[0], "rew") == 0) {
            be(lo, w[3], &ll);
            (W == 4 ? GGCRCNT : GGCRDCN)(&c, lo, ll);
            printf("%d/%d\n", c.resp, c.resp2);
        } else if (strcmp(w[0], "upd") == 0) {
            be(v, w[3], &vl);
            (W == 4 ? GGCUCNT : GGCUDCN)(&c, v, vl);
            printf("%d/%d\n", c.resp, c.resp2);
        } else {
            int lim = atoi(w[3]);
            (W == 4 ? GGCQCNT : GGCQDCN)(&c, v, W, lo, lim ? W : 0, hi, lim ? W : 0);
            if (c.resp != 0) printf("%d/%d\n", c.resp, c.resp2);
            else if (lim) printf("0/0 %llu %llu %llu\n", un(v), un(lo), un(hi));
            else printf("0/0 %llu\n", un(v));
        }
    }
    return 0;
}
"""

_FORMS = [("C", 4), ("D", 8)]


@needs_cc
@pytest.mark.parametrize(("form", "width"), _FORMS)
def test_the_stub_rewinds_updates_reduces_and_compares_a_counter(tmp_path, form, width):
    """#5039 (X53): the stub's GGCRCNT / GGCUCNT / GGCGCNX (fullword) and GGCRDCN / GGCUDCN / GGCGDCX (doubleword)."""
    exe = _stub(tmp_path, _MAIN.replace("__W__", str(width)))
    for n, (seed, steps, answers, refusal, forms) in enumerate(_CASES):
        if form not in forms:
            continue
        work = tmp_path / f"c{n}"
        (work / "out").mkdir(parents=True)
        (work / "counters.cfg").write_text(f"- {seed}\n" if seed else "", encoding="ascii")
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
@pytest.mark.parametrize(("form", "width"), _FORMS)
def test_cics_task_rewinds_updates_reduces_and_compares_a_counter_as_the_stub_does(tmp_path, form, width):
    """#5039 (X53): CicsTask.rewindCounter / updateCounter / getCounter(.., reduce, cmpMin, cmpMax) answer the scenarios above
    as the stub does and refuse what it refuses."""
    full = form == "C"

    def lng(x: str, dflt: str) -> str:
        return dflt if x == "-" else f'Long.parseLong("{x}")'

    def bound(x: str) -> str:
        return "null" if x == "-" else f'Long.valueOf(Long.parseLong("{x}"))'

    parts = []
    held = []
    for seed, steps, answers, refusal, forms in _CASES:
        if form not in forms:
            continue
        held.append((answers, refusal))
        counters = 'java.util.Map.of("/LEG", 5L)' if seed else "java.util.Map.of()"
        body = ""
        for st in steps:
            w = st.split()
            pool = '""' if w[2] == "-" else f'"{w[2]}"'
            nm = f'"{w[1]}"'
            if w[0] == "def":
                call = "defineCounter" if full else "defineDcounter"
                hi = "2147483647L" if full else "-1L"
                body += (f"r = t.{call}({pool}, {nm}, {lng(w[3], '0L')}, {lng(w[4], '0L')}, {lng(w[5], hi)}); "
                         'System.out.println(r[0] + "/" + r[1]);\n')  # fmt: skip
            elif w[0] == "get":
                body += (f"g = t.getCounter({pool}, {nm}, {lng(w[3], '1L')}, {'true' if w[4] == '1' else 'false'}, "
                         f"{'true' if w[5] == '1' else 'false'}, {bound(w[6])}, {bound(w[7])}, {'true' if full else 'false'}); "
                         'System.out.println(g[0] == 0 ? "0/0 " + g[2] : g[0] + "/" + g[1]);\n')  # fmt: skip
            elif w[0] == "rew":
                body += (f"r = t.rewindCounter({pool}, {nm}, {lng(w[3], '1L')}); "
                         'System.out.println(r[0] + "/" + r[1]);\n')  # fmt: skip
            elif w[0] == "upd":
                body += (f"r = t.updateCounter({pool}, {nm}, {lng(w[3], '0L')}, {'true' if full else 'false'}); "
                         'System.out.println(r[0] + "/" + r[1]);\n')  # fmt: skip
            else:
                lim = "true" if w[3] == "1" else "false"
                tail = ' + " " + q[3] + " " + q[4]' if lim == "true" else ""
                if full:
                    body += (f"q = t.queryCounter({pool}, {nm}, {lim}); "
                             f'System.out.println(q[0] == 0 ? "0/0 " + q[2]{tail} : q[0] + "/" + q[1]);\n')  # fmt: skip
                else:
                    tail = (
                        ' + " " + Long.toUnsignedString(d[3]) + " " + Long.toUnsignedString(d[4])'
                        if lim == "true"
                        else ""
                    )
                    body += (f"d = t.queryDcounter({pool}, {nm}, {lim}); "
                             f'System.out.println(d[0] == 0 ? "0/0 " + Long.toUnsignedString(d[2]){tail} : d[0] + "/" + d[1]);\n')  # fmt: skip
        parts.append(
            '{ CicsTask t = new CicsTask("ZC01", "ENTER", null, null).withCounters(new java.util.HashMap<>('
            + counters
            + "));\n"
            "int[] r, q; long[] g, d;\n"
            f'try {{\n{body}}} catch (UnsupportedOperationException e) {{ System.out.println("refused " + e.getMessage()); }} }}\n'
        )
    out = _cics_task(tmp_path, "\n".join(parts)).splitlines()
    pos = 0
    for answers, refusal in held:
        assert out[pos : pos + len(answers)] == answers, (answers, out[pos : pos + len(answers)])
        pos += len(answers)
        if refusal is not None:
            assert out[pos] == f"refused {refusal}: not modelled", (refusal, out[pos])
            pos += 1
