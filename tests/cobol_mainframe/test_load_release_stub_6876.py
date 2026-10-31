"""#6876 (oracle_assumptions.md X65): EXEC CICS LOAD / RELEASE modelled by the stub and the harness's translator.

IBM, EXEC CICS LOAD: SET "specifies the pointer reference that is to be set to the address at which a program, table, or map is
loaded"; LENGTH "specifies a halfword binary value to be set to the length of the loaded program"; PGMIDERR for a program that is
not defined. RELEASE lists INVREQ (not loaded by this task), NOTAUTH and PGMIDERR. The pieces:
- the harness's translator (equivalence_cics): LOAD / RELEASE onto GGCLDPG / GGCRLPG, and HOLD / ENTRY / FLENGTH refused by name;
- the stub (ggcics.c, compiled): the pointer and LENGTH set for a defined program, left alone under PGMIDERR, RELEASE's three outcomes.
The det translator models both (test_pointer_lane_5042.py); the det ports of ca-load-set: test_load_release_det_port_6876.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tests" / "tools"))
sys.path.insert(0, str(HERE.parents[1] / "tests" / "cics_crucible"))
import test_cics_runtimes as R  # noqa: E402  (bare imports: tests/ has no __init__.py, see CLAUDE.md)


def _ec():
    import equivalence_cics as ec

    return ec


def test_load_lowers_onto_the_stub_with_the_options_named_in_gg_flags():
    out = _ec().translate_command("LOAD PROGRAM('CALDTG') SET(WS-PTR) LENGTH(WS-LEN) RESP(WS-RESP) RESP2(WS-RESP2)")
    assert out[0] == "MOVE 'CALDTG' TO GG-NAME1"
    assert "MOVE 'SET LENGTH' TO GG-FLAGS" in out
    assert out[out.index("CALL 'GGCLDPG' USING GG-CICS") + 1 :][:2] == [
        "    BY REFERENCE WS-PTR",
        "    BY REFERENCE WS-LEN",
    ]
    assert "MOVE GG-RESP TO WS-RESP" in out and "MOVE GG-RESP2 TO WS-RESP2" in out


def test_load_without_set_or_length_passes_neither_area():
    out = _ec().translate_command("LOAD PROGRAM('CALDTG') NOHANDLE")
    assert "MOVE SPACES TO GG-FLAGS" in out
    assert out.count("    BY REFERENCE GG-FLAGS") == 2


def test_release_lowers_onto_the_stub():
    out = _ec().translate_command("RELEASE PROGRAM('CALDTG') RESP(R)")
    assert out[:2] == ["MOVE 'CALDTG' TO GG-NAME1", "CALL 'GGCRLPG' USING GG-CICS"]


@pytest.mark.parametrize(
    "text", ["LOAD PROGRAM('P') HOLD", "LOAD PROGRAM('P') ENTRY(E)", "LOAD PROGRAM('P') FLENGTH(L)"]
)
def test_the_options_the_stub_does_not_model_are_refused_by_name(text):
    with pytest.raises(_ec().Unsupported) as e:
        _ec().translate_command(text)
    assert "option not modelled" in str(e.value)  # #6876: the spec Refusal names it


@pytest.mark.parametrize("text", ["LOAD SET(P)", "RELEASE", "LOAD PROGRAM('P') SET", "LOAD PROGRAM('P') SET(P(1))"])
def test_a_missing_or_non_plain_operand_is_refused(text):
    with pytest.raises(_ec().Unsupported):
        _ec().translate_command(text)


_LOAD_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCLDPG(gg_cics *c, void **slot, unsigned char *len);
int GGCRLPG(gg_cics *c);
static void name(gg_cics *c, const char *n) { memset(c->name1, ' ', 8); memcpy(c->name1, n, strlen(n)); }
static void flags(gg_cics *c, const char *f) { memset(c->flags, ' ', 40); memcpy(c->flags, f, strlen(f)); }
int main(void) {
    gg_cics c;
    void *p = NULL;
    unsigned char len[2] = {0, 0};
    memset(&c, 0, sizeof c);
    name(&c, "GONE"); flags(&c, "SET LENGTH");
    GGCLDPG(&c, &p, len);
    printf("undefined %d/%d ptr=%d len=%d\n", c.resp, c.resp2, p != NULL, len[0] * 256 + len[1]);
    name(&c, "CAXA");
    GGCRLPG(&c);
    printf("release-unloaded %d\n", c.resp);
    GGCLDPG(&c, &p, len);
    printf("defined %d/%d ptr=%d len=%d\n", c.resp, c.resp2, p != NULL, len[0] * 256 + len[1]);
    GGCRLPG(&c);
    printf("release %d\n", c.resp);
    GGCRLPG(&c);
    printf("release-again %d\n", c.resp);
    name(&c, "GONE");
    GGCRLPG(&c);
    printf("release-undefined %d/%d\n", c.resp, c.resp2);
    p = NULL; len[0] = len[1] = 0;
    name(&c, "CAXA"); flags(&c, "");
    GGCLDPG(&c, &p, len);
    printf("no-options %d ptr=%d len=%d\n", c.resp, p != NULL, len[0] + len[1]);
    return 0;
}
"""


@R.needs_cc
def test_the_stub_loads_a_defined_program_and_answers_pgmiderr_for_another(tmp_path):
    """IBM LOAD: the pointer and LENGTH are set for a defined program and left alone for an undefined one (PGMIDERR RESP2 1);
    RELEASE is NORMAL once, INVREQ for a program this task did not load (or released already), PGMIDERR for an undefined one."""
    exe = R._stub(tmp_path, _LOAD_MAIN)
    (tmp_path / "programs.cfg").write_text("CAXA\n")
    got = [ln.strip() for ln in R._run_stub(exe, tmp_path)]
    assert got == [
        "undefined 27/1 ptr=0 len=0",
        "release-unloaded 16",
        "defined 0/0 ptr=1 len=256",
        "release 0",
        "release-again 16",
        "release-undefined 27/1",
        "no-options 0 ptr=0 len=0",
    ]
