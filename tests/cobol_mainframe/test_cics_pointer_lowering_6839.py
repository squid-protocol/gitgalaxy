"""#6839 slice 3 (register X47): the CICS oracle's lowering of a POINTER's numeric view (equivalence_cics_pointer.py).

1. **The lowering** over the whole input class: ADD / SUBTRACT with a literal, a BINARY item, a negative literal; MOVE view
   TO view; views at level 02 in a group, declared over one line or two; several pointer / view pairs; a program with no
   view untouched; every other use of a view refused by name; ZECS001's real source (when the corpus is present).
2. **The stub's GGCPTRADV** (compiled with a C compiler): the pointer moves inside its block (one past the last byte
   allowed, as DetCics.advancePointer); a null, freed, unknown pointer or a result outside the block is refused (exit 98).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/tools"))

import equivalence_cics_pointer as P  # noqa: E402

STUB = ROOT / "tests/equivalence/cics/ggcics.c"
CC = shutil.which("cc") or shutil.which("gcc")


def prog(*decl: str, body: tuple[str, ...] = ()) -> str:
    head = ["       WORKING-STORAGE SECTION.", "       01  ADDRS.", *decl]
    head += ["       01  N-BYTES  PIC S9(08) COMP.", "       01  N-DISP   PIC 9(04).", "       PROCEDURE DIVISION."]
    return "\n".join([*head, *("           " + b for b in body)])


PAIR = (
    "           02  CACHE-ADDRESS  USAGE POINTER.",
    "           02  CACHE-ADDRESS-X REDEFINES CACHE-ADDRESS",
    "                              PIC S9(08) COMP.",
    "           02  SAVE-ADDRESS   USAGE POINTER.",
    "           02  SAVE-ADDRESS-X REDEFINES SAVE-ADDRESS PIC S9(08) COMP.",
)


def code(text: str) -> str:
    return "\n".join(ln[6:] for ln in text.split("\n") if not ln.startswith("      *"))


@pytest.mark.parametrize(
    ("stmt", "want"),
    [
        ("ADD N-BYTES TO CACHE-ADDRESS-X.", 'CALL "GGCPTRADV" USING CACHE-ADDRESS BY VALUE N-BYTES.'),
        ("ADD 32 TO CACHE-ADDRESS-X", 'CALL "GGCPTRADV" USING CACHE-ADDRESS BY VALUE 32'),
        ("ADD -4 TO SAVE-ADDRESS-X.", 'CALL "GGCPTRADV" USING SAVE-ADDRESS BY VALUE -4.'),
        ("SUBTRACT 8 FROM SAVE-ADDRESS-X", 'CALL "GGCPTRADV" USING SAVE-ADDRESS BY VALUE -8'),
        ("SUBTRACT -8 FROM SAVE-ADDRESS-X", 'CALL "GGCPTRADV" USING SAVE-ADDRESS BY VALUE 8'),
        ("MOVE CACHE-ADDRESS-X TO SAVE-ADDRESS-X.", "SET SAVE-ADDRESS TO CACHE-ADDRESS."),
        ("MOVE SAVE-ADDRESS-X TO CACHE-ADDRESS-X", "SET CACHE-ADDRESS TO SAVE-ADDRESS"),
    ],
)
def test_each_modelled_statement_becomes_pointer_arithmetic(stmt, want):
    out = P.lower(prog(*PAIR, body=(stmt,)))
    assert want in re.sub(r"\s+", " ", code(out))
    assert "-X" not in code(out).replace("REDEFINES", "")  # no view is left, declarations included


@pytest.mark.parametrize(
    "stmt",
    [
        "COMPUTE CACHE-ADDRESS-X = CACHE-ADDRESS-X + 4.",
        "IF CACHE-ADDRESS-X > 0 DISPLAY 'X' END-IF.",
        "MOVE 0 TO CACHE-ADDRESS-X.",
        "MOVE CACHE-ADDRESS-X TO N-BYTES.",
        "ADD N-BYTES TO CACHE-ADDRESS-X GIVING N-BYTES.",
        "ADD N-BYTES TO CACHE-ADDRESS-X ROUNDED.",
        "ADD N-BYTES TO CACHE-ADDRESS-X SAVE-ADDRESS-X.",
        "ADD CACHE-ADDRESS-X TO CACHE-ADDRESS-X.",
        "ADD N-DISP TO CACHE-ADDRESS-X.",
        "ADD N-BYTES TO CACHE-ADDRESS-X ON SIZE ERROR DISPLAY 'E'.",
        "SUBTRACT N-BYTES FROM CACHE-ADDRESS-X.",
        "ADD N-BYTES",
    ],
)
def test_every_other_use_of_a_view_is_refused_by_name(stmt):
    body = (stmt, "TO CACHE-ADDRESS-X.") if stmt == "ADD N-BYTES" else (stmt,)
    with pytest.raises(P.Unsupported):
        P.lower(prog(*PAIR, body=body))


def test_a_program_with_no_view_is_untouched():
    text = prog("           02  CACHE-ADDRESS  USAGE POINTER.", body=("SET ADDRESS OF X TO CACHE-ADDRESS.",))
    assert P.lower(text) == text
    plain = prog("           02  F PIC S9(08) COMP.", body=("ADD N-BYTES TO F.",))
    assert P.lower(plain) == plain


def test_a_redefines_of_a_non_pointer_is_no_view():
    text = prog(
        "           02  A PIC S9(08) COMP.", "           02  B REDEFINES A PIC S9(08) COMP.", body=("ADD 1 TO B.",)
    )
    assert P.lower(text) == text


def test_the_clause_after_a_modelled_statement_is_kept():
    body = (
        "IF N-BYTES > 0",
        "    ADD N-BYTES TO CACHE-ADDRESS-X",
        "ELSE",
        "    MOVE CACHE-ADDRESS-X TO SAVE-ADDRESS-X",
        "END-IF.",
    )
    out = P.lower(prog(*PAIR, body=body))
    assert "ELSE" in out and "END-IF." in out and "SET SAVE-ADDRESS TO CACHE-ADDRESS" in out
    assert all(len(ln) <= 72 for ln in out.split("\n"))


def test_zecs001_source_lowers_with_no_view_left():
    corpora = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    src = Path(corpora or "/nonexistent") / "zecs/Source/ZECS001.cbl"
    if not src.is_file():
        pytest.skip("the zecs corpus is not checked out")
    out = P.lower(src.read_text(encoding="latin-1"))
    assert not re.search(
        r"CACHE-ADDRESS-X|SAVE-ADDRESS-X", "\n".join(ln[6:72] for ln in out.split("\n") if ln[6:7] != "*")
    )
    assert out.count('CALL "GGCPTRADV"') == 3 and out.count("SET SAVE-ADDRESS TO CACHE-ADDRESS") == 2
    assert all(len(ln) <= 72 for ln in out.split("\n"))


_MAIN = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCGETM(gg_cics *c, void **slot, char *img, int imglen);
int GGCFREM(gg_cics *c, void **slot);
int GGCPTRADV(void **slot, int n);
int main(int argc, char **argv) {
    static gg_cics c;
    static void *p[2], *base[2];
    for (int i = 1; i < argc; i++) {
        char *w[3];
        int k = 0;
        for (char *t = strtok(argv[i], " "); t && k < 3; t = strtok(NULL, " ")) w[k++] = t;
        int s = atoi(w[1]);
        if (strcmp(w[0], "gm") == 0) {
            char img = 0;
            c.num = atoi(w[2]);
            GGCGETM(&c, &p[s], &img, 1);
            base[s] = p[s];
        } else if (strcmp(w[0], "adv") == 0) {
            GGCPTRADV(&p[s], atoi(w[2]));
            printf("at %ld\n", (long)((char *)p[s] - (char *)base[s]));
        } else if (strcmp(w[0], "fm") == 0) {
            GGCFREM(&c, &base[s]);
        } else if (strcmp(w[0], "nul") == 0) {
            p[s] = NULL;
        } else if (strcmp(w[0], "raw") == 0) {
            p[s] = &c;
        }
    }
    return 0;
}
"""


def run_stub(tmp_path: Path, *steps: str) -> subprocess.CompletedProcess[str]:
    exe = tmp_path / "stub"
    if not exe.exists():
        src = tmp_path / "main.c"
        src.write_text(_MAIN, encoding="ascii")
        built = subprocess.run([CC, "-o", str(exe), str(src), str(STUB)], check=False, capture_output=True, text=True)  # noqa: S603
        assert built.returncode == 0, built.stderr
    (tmp_path / "out").mkdir(exist_ok=True)
    env = {"PATH": "/usr/bin:/bin", "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out")}
    return subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603


@pytest.mark.skipif(CC is None, reason="needs a C compiler")
@pytest.mark.parametrize(
    ("steps", "want"),
    [
        (["gm 0 64", "adv 0 10", "adv 0 22", "adv 0 -32"], ["at 10", "at 32", "at 0"]),
        (["gm 0 64", "adv 0 64"], ["at 64"]),  # one past the last byte
        (["gm 0 64", "adv 0 64", "adv 0 -64"], ["at 64", "at 0"]),
        (["gm 0 8", "gm 1 8", "adv 0 8", "adv 1 3"], ["at 8", "at 3"]),
    ],
)
def test_the_stub_moves_a_pointer_inside_its_block(tmp_path, steps, want):
    run = run_stub(tmp_path, *steps)
    assert run.returncode == 0 and run.stdout.splitlines() == want, run.stdout


@pytest.mark.skipif(CC is None, reason="needs a C compiler")
@pytest.mark.parametrize(
    ("steps", "why"),
    [
        (["gm 0 64", "adv 0 65"], "leaves the storage"),
        (["gm 0 64", "adv 0 -1"], "leaves the storage"),
        (["gm 0 64", "adv 0 64", "adv 0 1"], "leaves the storage"),
        (["nul 0", "adv 0 1"], "null pointer"),
        (["raw 0", "adv 0 1"], "no block of task storage holds"),
        (["gm 0 64", "fm 0", "adv 0 1"], "freed storage"),
    ],
)
def test_the_stub_refuses_pointer_arithmetic_outside_a_live_block(tmp_path, steps, why):
    run = run_stub(tmp_path, *steps)
    assert run.returncode == 98 and why in run.stdout and "not modelled" in run.stdout, (run.returncode, run.stdout)


def test_a_view_name_is_not_found_inside_a_longer_hyphenated_name():
    """INQACC declares WS-POINTER-NUMBER (never used) beside WS-POINTER-NUMBER-DISPLAY: the sibling is no use of the view."""
    text = prog(
        "           02  WS-POINTER USAGE POINTER.",
        "           02  WS-POINTER-NUMBER REDEFINES WS-POINTER PIC 9(8) BINARY.",
        "           02  WS-POINTER-NUMBER-DISPLAY PIC 9(8) DISPLAY.",
        body=("MOVE 1 TO WS-POINTER-NUMBER-DISPLAY.",),
    )
    out = P.lower(text)
    assert "WS-POINTER-NUMBER-DISPLAY" in out and "lowered (register X47)" in out
    assert not re.search(r"REDEFINES WS-POINTER ", code(out))
