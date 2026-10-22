"""#5005 (register X17): GET CONTAINER BYTEOFFSET and PUT CONTAINER PREPEND (BIT containers only), run alike by the stub
(ggcics.c) and CicsTask from one list of steps.

IBM, GET CONTAINER (CHANNEL): BYTEOFFSET is "the offset in bytes where the data returned starts"; "If the value specified is less
than zero, zero is assumed"; "The maximum length returned is equal to the length of the data in the container minus the BYTEOFFSET
value"; FLENGTH is set to "the length of the data returned"; an offset "greater than, or equal to, the length of the container"
is LENGERR RESP2 12. PUT CONTAINER (CHANNEL), PREPEND ("6.2 and later"): "the data passed to the container is prepended to the
existing data in the container". The expected lines are hand-derived from those sentences, not read from either runtime.

A step is ("put", label, container, hex, ccsid-or-None, flags) / ("get", label, container, max, offset-or-None, flags); flags are
the words the stub's GG-FLAGS carries (CHANNEL, BIT, CHAR, PREPEND). A get without an offset is the plain GET (no BYTEOFFSET)."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_cics_runtimes as R  # noqa: E402  (bare import: tests/ has no __init__.py, see CLAUDE.md)

needs_cc, needs_javac = R.needs_cc, R.needs_javac

_TEN = "0102030405060708090A"
_C = ["CHANNEL"]
_STEPS = [
    ("put", "p-new", "A", _TEN, None, _C + ["BIT"]),
    ("get", "off-0", "A", 16, 0, _C),
    ("get", "off-3", "A", 16, 3, _C),
    ("get", "off-last", "A", 16, 9, _C),
    ("get", "off-7", "A", 16, 7, _C),
    ("get", "off-neg", "A", 16, -1, _C),
    ("get", "off-neg-big", "A", 16, -2147483648, _C),
    ("get", "flength-exact", "A", 7, 3, _C),  # FLENGTH equal to what is left: no truncation
    ("get", "flength-exact-0", "A", 10, 0, _C),
    ("get", "off-end", "A", 16, 10, _C),  # LENGERR RESP2 12: FLENGTH and INTO left alone (ASSUMED)
    ("get", "off-past", "A", 16, 15, _C),
    ("get", "off-max", "A", 16, 2147483647, _C),
    ("get", "after-fail", "A", 16, 0, _C),  # the failed reads changed nothing
    ("get", "no-offset", "A", 16, None, _C),  # the plain GET is unchanged
    ("put", "pre-bit", "A", "E7E8", None, _C + ["BIT", "PREPEND"]),
    ("get", "pre-0", "A", 16, 0, _C),
    ("get", "pre-10", "A", 16, 10, _C),  # past the end of the 10 bytes, inside the 12 now
    ("put", "pre-twice", "A", "F1", None, _C + ["PREPEND"]),  # no data type: the existing container's own
    ("get", "pre-twice-0", "A", 16, 0, _C),
    ("put", "pre-new", "B", "AABB", None, _C + ["BIT", "PREPEND"]),  # a new container: the data alone
    ("get", "pre-new-0", "B", 16, 0, _C),
    ("put", "pre-new-untyped", "C", "11", None, _C + ["PREPEND"]),  # a new container is BIT by default
    ("get", "pre-untyped-0", "C", 16, 0, _C),
    ("put", "empty", "D", "", None, _C + ["BIT"]),
    ("get", "empty-0", "D", 16, 0, _C),  # offset 0 equals the length 0: LENGERR RESP2 12
    ("put", "pre-empty", "D", "55", None, _C + ["BIT", "PREPEND"]),
    ("get", "pre-empty-0", "D", 16, 0, _C),
    ("get", "no-container", "Z", 16, 0, _C),
    ("get", "no-channel", "A", 16, 0, []),  # INVREQ RESP2 4
]


def _expected_lines() -> list[str]:
    ten = bytes.fromhex(_TEN)
    h = lambda b: b.hex().upper()  # noqa: E731
    twelve = bytes.fromhex("E7E8") + ten
    return [
        "p-new=NORMAL/0",
        f"off-0=NORMAL/0/10/{h(ten)}",
        f"off-3=NORMAL/0/7/{h(ten[3:])}",
        f"off-last=NORMAL/0/1/{h(ten[9:])}",
        f"off-7=NORMAL/0/3/{h(ten[7:])}",
        f"off-neg=NORMAL/0/10/{h(ten)}",
        f"off-neg-big=NORMAL/0/10/{h(ten)}",
        f"flength-exact=NORMAL/0/7/{h(ten[3:])}",
        f"flength-exact-0=NORMAL/0/10/{h(ten)}",
        "off-end=LENGERR/12/16",
        "off-past=LENGERR/12/16",
        "off-max=LENGERR/12/16",
        f"after-fail=NORMAL/0/10/{h(ten)}",
        f"no-offset=NORMAL/0/10/{h(ten)}",
        "pre-bit=NORMAL/0",
        f"pre-0=NORMAL/0/12/{h(twelve)}",
        f"pre-10=NORMAL/0/2/{h(twelve[10:])}",
        "pre-twice=NORMAL/0",
        f"pre-twice-0=NORMAL/0/13/{h(bytes([0xF1]) + twelve)}",
        "pre-new=NORMAL/0",
        "pre-new-0=NORMAL/0/2/AABB",
        "pre-new-untyped=NORMAL/0",
        "pre-untyped-0=NORMAL/0/1/11",
        "empty=NORMAL/0",
        "empty-0=LENGERR/12/16",
        "pre-empty=NORMAL/0",
        "pre-empty-0=NORMAL/0/1/55",
        "no-container=CONTAINERERR/10/16",
        "no-channel=INVREQ/4/16",
    ]


# what both runtimes refuse with (register X17): a CHAR container's offset and prepend are counted in its code page; an FLENGTH below
# the data left (LENGERR RESP2 11, and what FLENGTH then holds is not said); a negative FLENGTH
_REFUSALS = [
    (
        [("put", "x", "A", "4142", None, _C + ["CHAR"]), ("get", "y", "A", 16, 0, _C)],
        "GET CONTAINER BYTEOFFSET on a CHAR container",
    ),
    (
        [("put", "x", "A", "4142", 37, _C), ("get", "y", "A", 16, 0, _C)],
        "GET CONTAINER BYTEOFFSET on a CHAR container",
    ),
    (
        [("put", "x", "A", "4142", None, _C + ["BIT"]), ("get", "y", "A", 1, 0, _C)],
        "GET CONTAINER BYTEOFFSET with an FLENGTH below the data left",
    ),
    (
        [("put", "x", "A", "4142", None, _C + ["BIT"]), ("get", "y", "A", 1, 1, _C), ("get", "z", "A", 0, 1, _C)],
        "GET CONTAINER BYTEOFFSET with an FLENGTH below the data left",
    ),
    (
        [("put", "x", "A", "4142", None, _C + ["BIT"]), ("get", "y", "A", -1, 0, _C)],
        "FLENGTH",
    ),
    (
        [("put", "x", "A", "4142", None, _C + ["CHAR"]), ("put", "y", "A", "41", None, _C + ["PREPEND"])],
        "PUT CONTAINER PREPEND on a CHAR container",
    ),
    ([("put", "x", "A", "41", None, _C + ["CHAR", "PREPEND"])], "PUT CONTAINER PREPEND on a CHAR container"),
    ([("put", "x", "A", "41", 37, _C + ["PREPEND"])], "PUT CONTAINER PREPEND on a CHAR container"),
]


def _c_main(steps: list[tuple]) -> str:
    body = []
    for kind, label, cont, arg, extra, flags in steps:
        words = " ".join(flags)
        if kind == "put":
            data = bytes.fromhex(arg)
            ccsid = -1 if extra is None else extra
            words += " FROMCCSID" if extra is not None else ""
            body.append(
                f"    {{ static const unsigned char d[] = {{{', '.join(str(b) for b in data) or '0'}}}; "
                f'put("{label}", "{cont}", (const char *)d, {len(data)}, {ccsid}, "{words}"); }}'
            )
        else:
            words += " BYTEOFFSET" if extra is not None else ""
            body.append(f'    get("{label}", "{cont}", {arg}, {0 if extra is None else extra}, "{words}");')
    return (
        r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; char as[16], tochan[16]; } gg_cics;
int GGCPUTC(gg_cics *c, char *from); int GGCGETC(gg_cics *c, char *into);
int GGCTASK(gg_cics *c); int GGCNEXT(gg_cics *c, char **area);
static gg_cics c;
static void blank(char *f, int n, const char *v) { memset(f, ' ', n); memcpy(f, v, strlen(v)); }
static const char *nm(int r) {
    switch (r) { case 0: return "NORMAL"; case 16: return "INVREQ"; case 22: return "LENGERR"; case 110: return "CONTAINERERR"; }
    return "?";
}
static void put(const char *label, const char *cont, const char *data, int n, int ccsid, const char *words) {
    blank(c.qname, 16, cont); blank(c.chan, 16, "CH"); blank(c.flags, 40, words); c.len = n; c.num = ccsid;
    GGCPUTC(&c, (char *)data);
    printf("%s=%s/%d\n", label, nm(c.resp), c.resp2);
}
static void get(const char *label, const char *cont, int max, int offset, const char *words) {
    char into[64]; memset(into, '.', sizeof into);
    blank(c.qname, 16, cont); blank(c.chan, 16, "CH"); blank(c.flags, 40, words); c.len = max; c.num = offset;
    GGCGETC(&c, into);
    printf("%s=%s/%d/%d", label, nm(c.resp), c.resp2, c.len);
    if (c.resp == 0) {
        printf("/");
        for (int i = 0; i < c.len; i++) printf("%02X", (unsigned char)into[i]);
    }
    printf("\n");
}
int main(void) {
    char *area = NULL;
    blank(c.name1, 8, "MAIN"); c.len = 0; GGCTASK(&c); GGCNEXT(&c, &area);
"""
        + "\n".join(body)
        + "\n    return 0;\n}\n"
    )


_HEX_OF = (
    "java.util.function.Function<String, byte[]> hexOf = h -> { byte[] d = new byte[h.length() / 2]; "
    "for (int i = 0; i < d.length; i++) d[i] = (byte) Integer.parseInt(h.substring(2 * i, 2 * i + 2), 16); return d; };"
)


def _java_body(steps: list[tuple]) -> str:
    lines = [
        _HEX_OF,
        'CicsTask t = new CicsTask("CA05", "ENTER", null, null).withProgram("MAIN");',
        "java.util.function.Function<byte[], String> hex = d -> { StringBuilder b = new StringBuilder(); "
        'for (byte x : d) b.append(String.format("%02X", x & 0xFF)); return b.toString(); };',
    ]
    for kind, label, cont, arg, extra, flags in steps:
        chan = '"CH"' if "CHANNEL" in flags else "null"
        if kind == "put":
            data = bytes.fromhex(arg)
            typ = '"BIT"' if "BIT" in flags else ('"CHAR"' if "CHAR" in flags else "null")
            n = -1 if extra is None else extra
            lines.append(
                f'{{ byte[] d = hexOf.apply("{arg}"); CicsTask.ContainerResult r = t.putContainer({chan}, "{cont}", d, {len(data)}, '
                f'{typ}, false, {n}, {str("PREPEND" in flags).lower()}); System.out.println("{label}=" + r.resp() + "/" + r.resp2()); }}'
            )
        else:
            call = (
                f't.getContainer({chan}, "{cont}", {arg})'
                if extra is None
                else f't.getContainerAt({chan}, "{cont}", {arg}, {extra})'
            )
            lines.append(
                f'{{ CicsTask.ContainerResult r = {call}; String o = "{label}=" + r.resp() + "/" + r.resp2() + "/" '
                f"+ (r.length() < 0 ? {arg} : r.length()); "
                f'if (r.resp().equals("NORMAL")) o += "/" + hex.apply(r.data()); System.out.println(o); }}'
            )
    return "\n".join(lines)


@needs_cc
def test_the_stub_reads_a_bit_container_from_a_byte_offset_and_prepends(tmp_path):
    """#5005 (X17): offsets from -2^31 to 2^31-1, FLENGTH equal to the data left, PREPEND on a new, an empty and an existing
    container, LENGERR RESP2 12 for an offset at or past the end (FLENGTH and INTO left alone)."""
    assert R._run_stub(R._stub(tmp_path, _c_main(_STEPS)), tmp_path) == _expected_lines()


@needs_javac
def test_cics_task_reads_from_a_byte_offset_and_prepends_as_the_stub_does(tmp_path):
    assert R._cics_task(tmp_path, _java_body(_STEPS)).splitlines() == _expected_lines()


@needs_cc
@pytest.mark.parametrize(("steps", "why"), _REFUSALS)
def test_the_stub_refuses_what_ibm_leaves_open_about_offsets_and_prepend(tmp_path, steps, why):
    exe = R._stub(tmp_path, _c_main(steps))
    done = subprocess.run([str(exe)], capture_output=True, text=True, check=False, env={"PATH": "/usr/bin:/bin"})  # noqa: S603
    assert done.returncode != 0 and why in done.stdout + done.stderr


@needs_javac
@pytest.mark.parametrize(("steps", "why"), _REFUSALS)
def test_cics_task_refuses_the_same(tmp_path, steps, why):
    body = _java_body(steps).replace(_HEX_OF + "\n", "")
    wrapped = (
        _HEX_OF + "\ntry {\n" + body
        + "\n} catch (UnsupportedOperationException e) { System.out.println(\"REFUSED \" + e.getMessage()); }"
    )  # fmt: skip
    out = R._cics_task(tmp_path, wrapped)
    assert "REFUSED" in out and why in out
