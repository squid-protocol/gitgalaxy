"""#5119 (register X56): an OS/VS COBOL address held in data -- IBM's chained storage areas, `MOVE NEXTAREA TO USERPTR`
(CICS/MVS 2.1.2 APRM SC33-0512-1, p. 22) -- answered alike by the stub (ggcics.c GGCBLLP / GGCBLLG) and CicsTask
(bllToken / bllPointer), from one list of steps.

A step is a word-line; pointer slots 0 and 1. `gm S N` GETMAIN SET FLENGTH(N), `tp S` MOVE cell TO fullword (the fullword's
bytes, hex), `tg S HEX` MOVE fullword TO cell, `eq` whether slots 0 and 1 hold one address, `nl S` whether slot S is NULL. A
real address does not fit a fullword in the instrument, so the fullword holds a token both runtimes number alike (ASSUMED,
X56); a value no `tp` gave is refused by name (a last answer that is no step line)."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_cics_runtimes as R  # noqa: E402  (bare import: tests/ has no __init__.py, see CLAUDE.md)

needs_cc, needs_javac = R.needs_cc, R.needs_javac

_UNKNOWN = "an address in data that no BLL cell gave"
_TOO_MANY = "more than 1525 BLL addresses held in data"
_REFUSALS = (_UNKNOWN, _TOO_MANY)

# (steps, what both runtimes answer)
_CASES = [
    (["tp 0"], ["tp 00000000"]),  # NULL is zero, as IBM's end of a chain
    (["tg 0 00000000", "nl 0"], ["tg", "nl 1"]),
    (["gm 0 8", "tp 0", "tp 0"], ["gm 0", "tp 00010000", "tp 00010000"]),  # one address, one token
    (  # the n-th distinct address moved into data is n * 65536, and moves back to the same address
        ["gm 0 8", "gm 1 8", "tp 1", "tp 0", "tg 0 00010000", "eq"],
        ["gm 0", "gm 0", "tp 00010000", "tp 00020000", "tg", "eq 1"],
    ),
    (["gm 0 8", "gm 1 8", "tp 0", "tg 1 00010000", "eq"], ["gm 0", "gm 0", "tp 00010000", "tg", "eq 1"]),
    (["gm 0 8", "gm 1 8", "eq"], ["gm 0", "gm 0", "eq 0"]),
    # an address computed in data (IBM's long record: ADD 4096 to it) is no token: refused, never a wrong address
    (["gm 0 8", "tp 0", "tg 1 00011000"], ["gm 0", "tp 00010000", _UNKNOWN]),
    (["tg 0 00010000"], [_UNKNOWN]),
    (["tg 0 FFFF0000"], [_UNKNOWN]),
    (["gm 0 1", "tp 0"] * 1526, ["gm 0", None] * 1525 + ["gm 0", _TOO_MANY]),
]


def _answers(answers: list) -> list:
    """The case's answers with the token of each `tp` in the long case filled in (None: the n-th token)."""
    out, n = [], 0
    for a in answers:
        if a is None:
            n += 1
            a = f"tp {n * 65536:08X}"
        out.append(a)
    return out


_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; char as[16], tochan[16]; } gg_cics;
int GGCGETM(gg_cics *c, void **slot, char *img, int imglen);
int GGCBLLP(void **cell, unsigned char *data);
int GGCBLLG(unsigned char *data, void **cell);
static gg_cics c;
int main(int argc, char **argv) {
    static void *p[2];
    unsigned char d[4];
    char img = ' ';
    for (int i = 1; i < argc; i++) {
        char *w[3] = {"", "", ""};
        int k = 0;
        for (char *t = strtok(argv[i], " "); t && k < 3; t = strtok(NULL, " ")) w[k++] = t;
        int s = atoi(w[1]);
        if (strcmp(w[0], "gm") == 0) {
            memset(&c, 0, sizeof c);
            memset(c.flags, ' ', 40);
            c.num = atoi(w[2]);
            GGCGETM(&c, &p[s], &img, 1);
            printf("gm %d\n", c.resp);
        } else if (strcmp(w[0], "tp") == 0) {
            GGCBLLP(&p[s], d);
            printf("tp %02X%02X%02X%02X\n", d[0], d[1], d[2], d[3]);
        } else if (strcmp(w[0], "tg") == 0) {
            for (int j = 0; j < 4; j++) {
                unsigned int b;
                sscanf(w[2] + 2 * j, "%2x", &b);
                d[j] = (unsigned char)b;
            }
            GGCBLLG(d, &p[s]);
            printf("tg\n");
        } else if (strcmp(w[0], "eq") == 0) {
            printf("eq %d\n", p[0] == p[1]);
        } else {
            printf("nl %d\n", p[s] == NULL);
        }
        fflush(stdout);
    }
    return 0;
}
"""

_JAVA = r"""
    static long[] slot = new long[2];
    static void step(CicsTask t, String line) {
        String[] w = line.split(" ");
        int s = w.length > 1 ? Integer.parseInt(w[1]) : 0;
        switch (w[0]) {
            case "gm" -> {
                long[] r = t.getmain(Long.parseLong(w[2]), false, ' ');
                slot[s] = r[2];
                System.out.println("gm " + r[0]);
            }
            case "tp" -> System.out.println(String.format("tp %08X", t.bllToken(slot[s])));
            case "tg" -> {
                slot[s] = t.bllPointer((int) Long.parseLong(w[2], 16));
                System.out.println("tg");
            }
            case "eq" -> System.out.println("eq " + (slot[0] == slot[1] ? 1 : 0));
            default -> System.out.println("nl " + (slot[s] == 0 ? 1 : 0));
        }
    }
"""


@needs_cc
def test_the_stub_numbers_addresses_held_in_data(tmp_path):
    """#5119 (X56): GGCBLLP / GGCBLLG, step list by step list; a value no cell gave is refused by name."""
    exe = R._stub(tmp_path, _MAIN)
    for n, (steps, answers) in enumerate(_CASES):
        work = tmp_path / f"w{n}"
        (work / "out").mkdir(parents=True)
        env = {**R._stub_base_env(), "GGCICS_DIR": str(work), "GGCICS_OUT": str(work / "out")}
        run = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        want = _answers(answers)
        if want[-1] not in _REFUSALS:
            assert run.returncode == 0 and run.stdout.splitlines() == want, (steps[:6], run.stdout[-400:], run.stderr)
        else:
            assert run.returncode == 98 and want[-1] + ": not modelled" in run.stdout, (steps[:6], run.stdout[-400:])
            assert run.stdout.splitlines()[:-1] == want[:-1], steps[:6]


@needs_javac
@pytest.mark.slow(reason="one javac compile of the CICS runtime plus the stub run; 16.8s on a CI runner (#5119)")
def test_cics_task_numbers_them_as_the_stub_does(tmp_path):
    """#5119 (X56): CicsTask.bllToken / bllPointer answer the same steps as the stub."""
    parts = []
    for steps, _ in _CASES:
        run = "\n".join(f'step(t, "{st}");' for st in steps)
        parts.append(
            f'{{ CicsTask t = new CicsTask("BLL1", "ENTER", null, null); slot = new long[2];\n try {{\n{run}\n}}'
            ' catch (UnsupportedOperationException e) { System.out.println("refused " + e.getMessage()); }\n'
            'System.out.println("--"); }'
        )
    out = R._cics_task(tmp_path, "\n".join(parts) + "\n    }\n" + _JAVA + "\n    static void unused() {")
    lines = out.splitlines()
    pos = 0
    for steps, answers in _CASES:
        end = lines.index("--", pos)
        want = _answers(answers)
        if want[-1] in _REFUSALS:
            want = want[:-1] + [f"refused {want[-1]}: not modelled"]
        assert lines[pos:end] == want, (steps[:6], lines[pos:end][-3:], want[-3:])
        pos = end + 1
