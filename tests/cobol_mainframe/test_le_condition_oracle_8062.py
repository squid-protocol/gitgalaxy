"""#8062 (register L8): the oracle's model of LE condition handling, tests/equivalence/le_conditions/ceecond.c.

The model is driven from a C driver standing in for GnuCOBOL (a PROCEDURE-POINTER's bytes hold the entry address;
the driver states the live stack frames). What is pinned: every outcome IBM documents for CEEHDLR / CEEHDLU / CEESGL
and the handler result codes 10 / 20 / 21 (each byte of the feedback token), the stated assumptions of L8, and that
everything else is refused by name (exit 98, "... not modelled"), never answered. What z/OS does is not observed."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "tests/equivalence/le_conditions/ceecond.c"
CC = shutil.which("gcc") or shutil.which("cc")
pytestmark = pytest.mark.skipif(CC is None or sys.platform == "win32", reason="needs a C compiler (gcc / cc)")

DRIVER = r"""
#include <stdio.h>
#include <string.h>
typedef int (*gg_le_frames_fn)(void **, int);
void gg_le_set_frames(gg_le_frames_fn);
int CEEHDLR(unsigned char *, unsigned char *, unsigned char *);
int CEEHDLU(unsigned char *, unsigned char *);
int CEESGL(unsigned char *, unsigned char *, unsigned char *);

static int A, B;                     /* two activations: A the caller, B the program it CALLed */
static void *live[2];
static int depth;
static int frames(void **chain, int max) { for (int i = 0; i < depth && i < max; i++) chain[i] = live[i]; return depth; }
static void in_b(void) { live[0] = &B; live[1] = &A; depth = 2; }
static void in_a(void) { live[0] = &A; depth = 1; }

static int answer[8];                 /* the result_code each handler sets; 0 = leaves the preset value */
static void hex(const char *tag, const unsigned char *b, int n) {
    printf("%s=", tag);
    for (int i = 0; i < n; i++) printf("%02X", b[i]);
    printf("\n");
}
static int run(int id, unsigned char *c, unsigned char *t, unsigned char *rc, unsigned char *nc) {
    int got; memcpy(&got, rc, 4);
    printf("h%d preset=%d token=%02X%02X%02X%02X\n", id, got, t[0], t[1], t[2], t[3]);
    hex("ctok", c, 12);
    if (answer[id]) memcpy(rc, &answer[id], 4);
    if (answer[id] == 77) { unsigned char fc[12]; CEESGL(c, NULL, fc); }
    (void)nc;
    return 0;
}
#define H(n) static int h##n(unsigned char *c, unsigned char *t, unsigned char *r, unsigned char *x) { return run(n, c, t, r, x); }
H(1) H(2) H(3)
typedef int (*hp)(unsigned char *, unsigned char *, unsigned char *, unsigned char *);
static unsigned char P1[sizeof(hp)], P2[sizeof(hp)], P3[sizeof(hp)], NUL[sizeof(hp)];
static unsigned char fc[12], tok[4] = {0, 0, 0, 7};

static void cond(unsigned char *c, int sev, int msg) {   /* a user condition: case 1, facility USR (ASCII is fine) */
    memset(c, 0, 12);
    c[1] = sev; c[2] = msg >> 8; c[3] = msg & 255; c[4] = 0x40 | (sev << 3); memcpy(c + 5, "USR", 3);
}

int main(int argc, char **argv) {
    hp f1 = h1, f2 = h2, f3 = h3;
    memcpy(P1, &f1, sizeof f1); memcpy(P2, &f2, sizeof f2); memcpy(P3, &f3, sizeof f3); memset(NUL, 0, sizeof NUL);
    for (int i = 2; i < argc; i++) sscanf(argv[i], "h%*d=%d", &answer[argv[i][1] - '0']);
    const char *s = argv[1];
    unsigned char c[12];
    if (strcmp(s, "no-frames") != 0) gg_le_set_frames(frames);
    in_a();
    if (!strcmp(s, "no-frames")) { CEEHDLR(P1, tok, fc); return 0; }
    if (!strcmp(s, "signal")) {            /* argv: h1=.. h2=..; h1 then h2 in A; signal severity 3 with an fc */
        CEEHDLR(P1, tok, fc); CEEHDLR(P2, tok, fc);
        cond(c, 3, 9); CEESGL(c, NULL, fc); hex("fc", fc, 12); return 0;
    }
    if (!strcmp(s, "frames")) {            /* h1 in A, h2 and h3 in B; signal from B */
        CEEHDLR(P1, tok, fc); in_b(); CEEHDLR(P2, tok, fc); CEEHDLR(P3, tok, fc);
        cond(c, 2, 9); CEESGL(c, NULL, fc); hex("fc", fc, 12); return 0;
    }
    if (!strcmp(s, "frame-gone")) {        /* h2 in B; B returns; signal from A */
        in_b(); CEEHDLR(P2, tok, fc); in_a();
        cond(c, 3, 9); CEESGL(c, NULL, fc); hex("fc", fc, 12); return 0;
    }
    if (!strcmp(s, "twice")) {
        CEEHDLR(P1, tok, fc); hex("fc1", fc, 12); CEEHDLR(P1, tok, fc); hex("fc2", fc, 12);
        cond(c, 1, 9); CEESGL(c, NULL, fc); hex("fc", fc, 12); return 0;
    }
    if (!strcmp(s, "null-entry")) { CEEHDLR(NUL, tok, fc); hex("fc", fc, 12); return 0; }
    if (!strcmp(s, "unregister")) {
        CEEHDLU(P1, fc); hex("fc1", fc, 12); CEEHDLR(P1, tok, fc); CEEHDLU(P1, fc); hex("fc2", fc, 12);
        cond(c, 3, 9); CEESGL(c, NULL, fc); hex("fc", fc, 12); return 0;
    }
    if (!strcmp(s, "unregister-other-frame")) {
        CEEHDLR(P1, tok, fc); in_b(); CEEHDLU(P1, fc); hex("fc", fc, 12); return 0;
    }
    if (!strcmp(s, "hdlu-no-fc")) { CEEHDLU(P1, NULL); return 0; }
    if (!strcmp(s, "hdlr-no-fc-dup")) { CEEHDLR(P1, tok, NULL); CEEHDLR(P1, tok, NULL); return 0; }
    if (!strcmp(s, "hdlr-no-fc")) { CEEHDLR(P1, tok, NULL); printf("ok\n"); return 0; }
    if (!strncmp(s, "nofc-sev", 8)) { cond(c, s[8] - '0', 9); CEESGL(c, NULL, NULL); printf("resumed\n"); return 0; }
    if (!strncmp(s, "fc-sev", 6)) { cond(c, s[6] - '0', 9); CEESGL(c, NULL, fc); hex("fc", fc, 12); return 0; }
    if (!strcmp(s, "mismatch")) { cond(c, 3, 9); c[1] = 1; CEESGL(c, NULL, fc); return 0; }
    if (!strcmp(s, "nested")) { CEEHDLR(P1, tok, fc); cond(c, 1, 9); CEESGL(c, NULL, fc); return 0; }
    return 2;
}
"""


def tok(sev: int, msg: int) -> str:
    """IBM's case-1 token for a CEE condition: severity, message number, case 1 / sev / control 1, CEE in EBCDIC."""
    return f"{0:02X}{sev:02X}{msg:04X}{0x40 | (sev << 3) | 1:02X}C3C5C5" + "00" * 4


CEE000 = "00" * 12
CEE069 = tok(0, 201)  # an unhandled condition was returned in a feedback code
CEE080 = tok(1, 256)  # already registered for this stack frame; registered again
CEE081 = tok(3, 257)  # the specified routine contained an invalid entry variable
CEE07S = tok(1, 252)  # CEEHDLU was unable to find the requested user-written condition handler routine


@pytest.fixture(scope="module")
def driver(tmp_path_factory):
    d = tmp_path_factory.mktemp("ceecond")
    (d / "driver.c").write_text(DRIVER, encoding="utf-8")
    exe = d / "driver"
    subprocess.run([CC, "-std=c99", "-Wall", "-Werror", "-o", str(exe), str(d / "driver.c"), str(MODEL)],
                   check=True, capture_output=True, text=True)  # fmt: skip
    return exe


def _run(driver, *args):
    p = subprocess.run([str(driver), *args], capture_output=True, text=True, timeout=30)
    return p.returncode, p.stdout.splitlines(), p.stderr


def _refused(driver, *args, why: str):
    rc, out, err = _run(driver, *args)
    assert rc == 98 and "not modelled" in err and why in err, (rc, out, err)
    return out


def test_the_ibm_symbolic_codes_are_their_message_numbers():
    """The symbolic name is the message number in base 32 (0-9, A-V): the tokens below are IBM's, not ours."""

    def sym(msg):
        digits = "0123456789ABCDEFGHIJKLMNOPQRSTUV"
        return "CEE" + digits[msg // 1024] + digits[msg // 32 % 32] + digits[msg % 32]

    assert [sym(m) for m in (201, 256, 257, 252, 2531)] == ["CEE069", "CEE080", "CEE081", "CEE07S", "CEE2F3"]
    assert tok(3, 2531)[:16] == "000309E359C3C5C5"  # CEELOCT's CEE2F3 in ceeloct.c (L7): the same layout


def test_no_frame_source_refuses(driver):
    _refused(driver, "no-frames", why="stack frame (no frame source")


def test_handlers_run_lifo_with_the_registered_token_and_the_condition(driver):
    rc, out, _ = _run(driver, "signal", "h1=10")
    assert rc == 0, out
    assert [ln.split()[0] for ln in out if ln.startswith("h")] == ["h2", "h1"]  # later registration first
    assert out.count("h2 preset=20 token=00000007") == 1  # result_code preset to 20, IBM's default
    ctok = [ln for ln in out if ln.startswith("ctok=")]
    assert ctok == ["ctok=0003000958555352" + "00" * 4] * 2  # the signalled token, unchanged
    assert out[-1] == f"fc={CEE000}"  # resumed by h1 (assumed: the CEESGL fc is CEE000)


def test_a_handler_that_sets_no_result_percolates_and_the_condition_is_unhandled(driver):
    rc, out, _ = _run(driver, "signal")
    assert rc == 0 and [ln.split()[0] for ln in out if ln.startswith("h")] == ["h2", "h1"]
    assert out[-1] == f"fc={CEE069}"  # Table 34: severity 3 signalled with an fc returns CEE069 and resumes


@pytest.mark.parametrize("sev", [0, 1, 2, 3])
def test_an_unhandled_condition_with_an_fc_returns_cee069_for_severity_0_to_3(driver, sev):
    assert _run(driver, f"fc-sev{sev}")[:2] == (0, [f"fc={CEE069}"])  # no handler registered


def test_percolation_crosses_frames_and_21_skips_the_rest_of_the_frame(driver):
    rc, out, _ = _run(driver, "frames", "h1=10")
    assert rc == 0 and [ln.split()[0] for ln in out if ln.startswith("h")] == ["h3", "h2", "h1"]
    assert out[-1] == f"fc={CEE000}"
    rc, out, _ = _run(driver, "frames", "h3=21", "h1=10")
    assert rc == 0 and [ln.split()[0] for ln in out if ln.startswith("h")] == ["h3", "h1"]  # h2 skipped
    rc, out, _ = _run(driver, "frames", "h3=10")
    assert rc == 0 and [ln.split()[0] for ln in out if ln.startswith("h")] == ["h3"]


def test_a_frame_that_left_the_stack_takes_its_handlers_with_it(driver):
    rc, out, _ = _run(driver, "frame-gone")
    assert rc == 0 and not [ln for ln in out if ln.startswith("h")] and out[-1] == f"fc={CEE069}"


def test_registering_twice_is_cee080_and_registers_again(driver):
    rc, out, _ = _run(driver, "twice")
    assert rc == 0 and out[0] == f"fc1={CEE000}" and out[1] == f"fc2={CEE080}"
    assert [ln.split()[0] for ln in out if ln.startswith("h")] == ["h1", "h1"]


def test_a_null_entry_is_cee081_and_not_registered(driver):
    rc, out, _ = _run(driver, "null-entry")
    assert rc == 0 and out == [f"fc={CEE081}"]


def test_unregister(driver):
    rc, out, _ = _run(driver, "unregister")
    assert rc == 0 and out[0] == f"fc1={CEE07S}" and out[1] == f"fc2={CEE000}"
    assert not [ln for ln in out if ln.startswith("h")] and out[-1] == f"fc={CEE069}"
    rc, out, _ = _run(driver, "unregister-other-frame")  # IBM: registered by the same stack frame
    assert rc == 0 and out == [f"fc={CEE07S}"]


def test_an_omitted_fc_succeeds_silently_and_is_refused_when_the_service_fails(driver):
    assert _run(driver, "hdlr-no-fc")[:2] == (0, ["ok"])
    _refused(driver, "hdlu-no-fc", why="omitted fc")
    _refused(driver, "hdlr-no-fc-dup", why="omitted fc")


@pytest.mark.parametrize("sev", ["0", "1"])
def test_an_unhandled_safe_condition_without_an_fc_is_ignored(driver, sev):
    assert _run(driver, f"nofc-sev{sev}")[:2] == (0, ["resumed"])


@pytest.mark.parametrize("args", [("nofc-sev2",), ("nofc-sev3",), ("fc-sev4",)])
def test_termination_imminent_is_refused(driver, args):
    _refused(driver, *args, why="T_I_U")


@pytest.mark.parametrize("code", ["30", "31", "32", "60", "11", "-1"])
def test_promote_fixup_and_unknown_result_codes_are_refused(driver, code):
    out = _refused(driver, "signal", f"h2={code}", why=f"result_code {code}")
    assert [ln.split()[0] for ln in out if ln.startswith("h")] == ["h2"]


def test_a_condition_signalled_inside_a_handler_is_refused(driver):
    _refused(driver, "nested", "h1=77", why="inside a handler")


def test_a_case1_token_whose_severities_differ_is_refused(driver):
    _refused(driver, "mismatch", why="two severities differ")


def test_the_model_is_not_linked_into_every_program():
    """The LE directory every program links is tests/equivalence/le; this model stays out of it until a frame source
    exists (L8 Remaining slices), so no proof can rest on it yet."""
    le = ROOT / "tests/equivalence/le"
    assert MODEL.parent != le and not any("CEESGL" in p.read_text(encoding="utf-8") for p in le.glob("*.c"))
