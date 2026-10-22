"""#4270 (register X17): PUT CONTAINER FROMCCSID / FROMCODEPAGE and GET CONTAINER INTOCCSID / INTOCODEPAGE / CONVERTST(NOCONVERT) /
CCSID -- the container's code-page conversion, run alike by the stub (ggcics.c) and CicsTask from one list of steps.

The expected bytes are NOT read from either runtime: `_truth` is the character map between two code pages that Python's own
codecs give (cp037, cp500, cp1140) for a program whose bytes are read as the region's page 037 (the port's convention, #4528).
What IBM leaves open is refused by name, on both sides (`_REFUSALS`).

A step is a tuple: ("put", label, container, hex, ccsid-or-None, flags) / ("get", label, container, max, ccsid-or-None, flags);
flags are the words the stub's GG-FLAGS carries (BIT, CHAR, APPEND, NODATA, NOCONVERT)."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_cics_runtimes as R  # noqa: E402  (bare import: tests/ has no __init__.py, see CLAUDE.md)

needs_cc, needs_javac = R.needs_cc, R.needs_javac

_PAGE = {37: "cp037", 500: "cp500", 1140: "cp1140", 1208: "ascii"}  # (1208: ASCII data only, one byte a character)


def _truth(data: bytes, src: int, dst: int) -> bytes:
    """What a program reading its bytes as CCSID 037 sees after IBM converts them from `src` to `dst`."""
    if src == dst:
        return data
    out = bytearray()
    for b in data:
        real = bytes([b]).decode("latin-1").encode("cp037")
        out += bytes([ord(real.decode(_PAGE[src]).encode(_PAGE[dst]).decode("cp037"))])
    return bytes(out)


def _storage_of(real: bytes) -> bytes:
    """The storage bytes a program holds when the region's bytes are `real` (the region's page 037 decodes them)."""
    return bytes(ord(bytes([r]).decode("cp037")) for r in real)


def _hex(data: bytes) -> str:
    return data.hex().upper()


# "A[B]!|^" and the cent and not signs (A2, AC): every character cp500 reads differently from cp037
_SAMPLE = "A[B]!|^".encode("latin-1") + b"\xa2\xac"
_STEPS = [
    ("put", "p-new500", "A", _hex(_SAMPLE), 500, ["CHANNEL"]),
    ("get", "g-region", "A", 16, None, ["CHANNEL"]),
    ("get", "g-500", "A", 16, 500, ["CHANNEL", "INTOCCSID"]),
    ("get", "g-1140", "A", 16, 1140, ["CHANNEL", "INTOCCSID"]),
    ("get", "g-noconvert", "A", 16, None, ["CHANNEL", "NOCONVERT"]),
    ("get", "g-short", "A", 3, 37, ["CHANNEL", "INTOCCSID"]),
    ("get", "g-nodata", "A", -1, 1140, ["CHANNEL", "NODATA", "INTOCCSID"]),
    ("put", "p-plain-char", "B", _hex(_SAMPLE), None, ["CHANNEL", "CHAR"]),
    ("get", "b-own", "B", 16, None, ["CHANNEL", "NOCONVERT"]),
    ("get", "b-as-500", "B", 16, 500, ["CHANNEL", "INTOCCSID"]),
    ("get", "b-as-37", "B", 16, 37, ["CHANNEL", "INTOCCSID"]),
    ("put", "p-bit", "C", _hex(_SAMPLE), None, ["CHANNEL", "BIT"]),
    ("get", "c-raw", "C", 16, None, ["CHANNEL"]),
    ("get", "c-noconvert", "C", 16, None, ["CHANNEL", "NOCONVERT"]),
    ("put", "p-bit-ccsid", "D", "41", 37, ["CHANNEL", "BIT"]),  # IBM: INVREQ RESP2 34
    ("get", "d-not-made", "D", 16, None, ["CHANNEL"]),
    # "converted (if required)": a put onto an existing CHAR container comes in as the container's CCSID
    ("put", "p-37-onto-500", "A", _hex(b"[]"), 37, ["CHANNEL"]),
    ("get", "a-after-37", "A", 16, None, ["CHANNEL", "NOCONVERT"]),
    ("put", "p-1140-append", "A", _hex(b"!"), 1140, ["CHANNEL", "APPEND"]),
    ("get", "a-after-append", "A", 16, None, ["CHANNEL", "NOCONVERT"]),
    ("put", "p-default-onto-500", "A", _hex(b"|"), None, ["CHANNEL", "CHAR", "APPEND"]),
    ("get", "a-after-default", "A", 16, None, ["CHANNEL", "NOCONVERT"]),
    ("get", "no-container", "Z", 16, 500, ["CHANNEL", "INTOCCSID"]),
    # CCSID 1208 (ASCII): the region's bytes X'414243313233' and X'5B..' as the program sees them
    ("put", "p-1208", "E", _hex(_storage_of(b"ABC123[]")), 1208, ["CHANNEL"]),
    ("get", "e-1208", "E", 16, 1208, ["CHANNEL", "INTOCCSID"]),
    ("get", "e-37", "E", 16, 37, ["CHANNEL", "INTOCCSID"]),
    ("get", "e-region", "E", 16, None, ["CHANNEL"]),
    ("get", "e-500", "E", 16, 500, ["CHANNEL", "INTOCCSID"]),
    ("put", "p-37-onto-1208", "E", _hex(b"A[~"), None, ["CHANNEL", "CHAR"]),
    ("get", "e-after", "E", 16, None, ["CHANNEL", "NOCONVERT"]),
    ("put", "p-1140-to-1208", "F", _hex(b"ok"), 1140, ["CHANNEL"]),
    ("get", "f-1208", "F", 16, 1208, ["CHANNEL", "INTOCCSID"]),
    # IBM: INVREQ RESP2 2 -- the code-page option needs a channel; CCSIDERR RESP2 3 -- a BIT container comes back unconverted
    ("get", "g-nochannel", "A", 4, 37, ["INTOCCSID"]),
    ("put", "p-nochannel", "A", "41", 37, []),
    ("get", "bit-intoccsid", "C", 9, 1208, ["CHANNEL", "INTOCCSID"]),
    ("get", "bit-nodata", "C", -1, 1208, ["CHANNEL", "NODATA", "INTOCCSID"]),
]


def _expected_lines() -> list[str]:
    """The lines both runtimes print, from the hand-written conditions and `_truth`'s bytes."""
    s = _SAMPLE
    return [
        "p-new500=NORMAL/0",
        f"g-region=NORMAL/0/9/500/{_hex(_truth(s, 500, 37))}",
        f"g-500=NORMAL/0/9/500/{_hex(s)}",
        f"g-1140=NORMAL/0/9/500/{_hex(_truth(s, 500, 1140))}",
        f"g-noconvert=NORMAL/0/9/500/{_hex(s)}",
        f"g-short=LENGERR/11/9/500/{_hex(_truth(s, 500, 37)[:3])}",
        "g-nodata=NORMAL/0/9/500/",
        "p-plain-char=NORMAL/0",
        f"b-own=NORMAL/0/9/37/{_hex(s)}",
        f"b-as-500=NORMAL/0/9/37/{_hex(_truth(s, 37, 500))}",
        f"b-as-37=NORMAL/0/9/37/{_hex(s)}",
        "p-bit=NORMAL/0",
        f"c-raw=NORMAL/0/9/0/{_hex(s)}",
        f"c-noconvert=NORMAL/0/9/0/{_hex(s)}",
        "p-bit-ccsid=INVREQ/34",
        "d-not-made=CONTAINERERR/10",
        "p-37-onto-500=NORMAL/0",
        "a-after-37=NORMAL/0/2/500/" + _hex(_truth(b"[]", 37, 500)),
        "p-1140-append=NORMAL/0",
        "a-after-append=NORMAL/0/3/500/" + _hex(_truth(b"[]", 37, 500) + _truth(b"!", 1140, 500)),
        "p-default-onto-500=NORMAL/0",
        "a-after-default=NORMAL/0/4/500/"
        + _hex(_truth(b"[]", 37, 500) + _truth(b"!", 1140, 500) + _truth(b"|", 37, 500)),
        "no-container=CONTAINERERR/10",
        "p-1208=NORMAL/0",
        f"e-1208=NORMAL/0/8/1208/{_hex(_storage_of(b'ABC123[]'))}",
        f"e-37=NORMAL/0/8/1208/{_hex(_truth(_storage_of(b'ABC123[]'), 1208, 37))}",
        f"e-region=NORMAL/0/8/1208/{_hex(_truth(_storage_of(b'ABC123[]'), 1208, 37))}",
        f"e-500=NORMAL/0/8/1208/{_hex(_truth(_storage_of(b'ABC123[]'), 1208, 500))}",
        "p-37-onto-1208=NORMAL/0",
        f"e-after=NORMAL/0/3/1208/{_hex(_truth(b'A[~', 37, 1208))}",
        "p-1140-to-1208=NORMAL/0",
        f"f-1208=NORMAL/0/2/1140/{_hex(_truth(b'ok', 1140, 1208))}",
        "g-nochannel=INVREQ/2",
        "p-nochannel=INVREQ/2",
        f"bit-intoccsid=CCSIDERR/3/{_hex(s)}",
        "bit-nodata=CCSIDERR/3/",
    ]


# (steps, what both runtimes refuse with): what IBM leaves open, or this model does not cover (register X17)
_REFUSALS = [
    ([("put", "x", "A", "41", 273, ["CHANNEL"])], "only the CCSIDs 37, 500, 1140 and 1208 are modelled"),
    (
        [("put", "x", "A", "41", 500, ["CHANNEL"]), ("get", "y", "A", 4, 273, ["CHANNEL", "INTOCCSID"])],
        "only the CCSIDs 37, 500, 1140 and 1208 are modelled",
    ),  # fmt: skip
    (
        [("put", "x", "B", "A4", 1140, ["CHANNEL"]), ("get", "y", "B", 4, None, ["CHANNEL"])],
        "code-page conversion of a character the target CCSID lacks",
    ),  # fmt: skip
    (
        [("put", "x", "A", "41", 37, ["CHANNEL"]), ("put", "y", "A", "A4", 1140, ["CHANNEL"])],
        "code-page conversion of a character the target CCSID lacks",
    ),  # fmt: skip
    (
        [("put", "x", "A", "FF", 1208, ["CHANNEL"]), ("get", "y", "A", 4, None, ["CHANNEL"])],
        "code-page conversion of a CCSID 1208 byte beyond ASCII",
    ),  # fmt: skip
    (
        [("put", "x", "A", "A2", 37, ["CHANNEL"]), ("get", "y", "A", 4, 1208, ["CHANNEL", "INTOCCSID"])],
        "code-page conversion to CCSID 1208 of a character beyond ASCII",
    ),  # fmt: skip
    (
        [("put", "x", "A", "4142", None, ["CHANNEL", "BIT"]), ("get", "y", "A", 1, 37, ["CHANNEL", "INTOCCSID"])],
        "GET CONTAINER INTOCCSID on a BIT container longer than INTO",
    ),  # fmt: skip
    (
        [("put", "x", "A", "41", None, ["CHANNEL", "BIT"]), ("put", "y", "A", "41", 37, ["CHANNEL"])],
        "PUT CONTAINER FROMCCSID onto an existing BIT container",
    ),  # fmt: skip
    ([("put", "x", "A", "41", 37, ["BIT"])], "PUT CONTAINER FROMCCSID with a data type and no channel"),
]


def _c_main(steps: list[tuple]) -> str:
    body = []
    for step in steps:
        kind, label, cont, arg, ccsid, flags = step
        words = " ".join(flags)
        if kind == "put":
            data = bytes.fromhex(arg)
            body.append(
                f"    {{ static const unsigned char d[] = {{{', '.join(str(b) for b in data) or '0'}}}; "
                f'put("{label}", "{cont}", (const char *)d, {len(data)}, {-1 if ccsid is None else ccsid}, "{words}"); }}'
            )
        else:
            body.append(f'    get("{label}", "{cont}", {arg}, {-1 if ccsid is None else ccsid}, "{words}");')
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
    switch (r) { case 0: return "NORMAL"; case 16: return "INVREQ"; case 22: return "LENGERR"; case 110: return "CONTAINERERR"; case 123: return "CCSIDERR"; }
    return "?";
}
static void put(const char *label, const char *cont, const char *data, int n, int ccsid, const char *words) {
    char fl[64]; snprintf(fl, sizeof fl, "%s%s%s", words, ccsid >= 0 ? " " : "", ccsid >= 0 ? "FROMCCSID" : "");
    blank(c.qname, 16, cont); blank(c.chan, 16, "CH"); blank(c.flags, 40, fl); c.len = n; c.num = ccsid;
    GGCPUTC(&c, (char *)data);
    printf("%s=%s/%d\n", label, nm(c.resp), c.resp2);
}
static void get(const char *label, const char *cont, int max, int ccsid, const char *words) {
    char into[64]; memset(into, '.', sizeof into);
    blank(c.qname, 16, cont); blank(c.chan, 16, "CH"); blank(c.flags, 40, words); c.len = max < 0 ? 0 : max; c.num = ccsid;
    GGCGETC(&c, into);
    printf("%s=%s/%d", label, nm(c.resp), c.resp2);
    if (c.resp == 0 || c.resp == 22) {
        int n = max < 0 ? 0 : (c.len < max ? c.len : max);
        printf("/%d/%d/", c.len, c.num);
        for (int i = 0; i < n; i++) printf("%02X", (unsigned char)into[i]);
    } else if (c.resp == 123) {  /* CCSIDERR: the data comes back unconverted; its length is the step's (FLENGTH is not stated) */
        printf("/");
        for (int i = 0; i < (max < 0 ? 0 : max); i++) printf("%02X", (unsigned char)into[i]);
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


def _java_body(steps: list[tuple]) -> str:  # noqa: C901
    lines = [
        _HEX_OF,
        'CicsTask t = new CicsTask("CA05", "ENTER", null, null).withProgram("MAIN");',
        "java.util.function.Function<byte[], String> hex = d -> { StringBuilder b = new StringBuilder(); "
        'for (byte x : d) b.append(String.format("%02X", x & 0xFF)); return b.toString(); };',
    ]
    for kind, label, cont, arg, ccsid, flags in steps:
        chan = '"CH"' if "CHANNEL" in flags else "null"
        n = -1 if ccsid is None else ccsid
        if kind == "put":
            data = bytes.fromhex(arg)
            typ = '"BIT"' if "BIT" in flags else ('"CHAR"' if "CHAR" in flags else "null")
            lines.append(
                f'{{ byte[] d = hexOf.apply("{arg}"); CicsTask.ContainerResult r = t.putContainer({chan}, "{cont}", d, {len(data)}, '
                f'{typ}, {str("APPEND" in flags).lower()}, {n}); System.out.println("{label}=" + r.resp() + "/" + r.resp2()); }}'
            )
        else:
            noconv = str("NOCONVERT" in flags).lower()
            lines.append(
                f'{{ CicsTask.ContainerResult r = t.getContainer({chan}, "{cont}", {arg}, {n}, {noconv}); '
                f'String o = "{label}=" + r.resp() + "/" + r.resp2(); '
                f'if (r.resp().equals("NORMAL") || r.resp().equals("LENGERR")) o += "/" + r.length() + "/" + t.containerCcsid() + "/" '
                f'+ (r.data() == null ? "" : hex.apply(r.data())); else if (r.resp().equals("CCSIDERR")) o += "/" '
                f'+ (r.data() == null ? "" : hex.apply(r.data())); System.out.println(o); }}'
            )
    return "\n".join(lines)


@needs_cc
def test_the_stub_converts_a_char_container_between_code_pages(tmp_path):
    """#4270 (X17), IBM PUT / GET CONTAINER: FROMCCSID tags the data (CHAR implied, BIT with it is INVREQ RESP2 34); GET converts to
    INTOCCSID, else to the region's CCSID (037); CONVERTST(NOCONVERT) returns the container's own, CCSID(area) says which; a put
    onto an existing CHAR container is converted to its CCSID; the data is returned with LENGERR when INTO is short."""
    out = R._run_stub(R._stub(tmp_path, _c_main(_STEPS)), tmp_path)
    assert out == _expected_lines()


@needs_javac
def test_cics_task_converts_a_char_container_as_the_stub_does(tmp_path):
    """#4270 (X17): CicsTask answers the scenario above line for line."""
    assert R._cics_task(tmp_path, _java_body(_STEPS)).splitlines() == _expected_lines()


@needs_cc
@pytest.mark.parametrize(("steps", "why"), _REFUSALS)
def test_the_stub_refuses_what_ibm_leaves_open_about_container_conversion(tmp_path, steps, why):
    """#4270 (X17): a CCSID outside 37 / 500 / 1140 / 1208, a character the target lacks (CCSIDERR RESP2 4), 1208 beyond ASCII, a BIT
    container longer than INTO under INTOCCSID, and FROMCCSID onto an existing BIT container or with a data type and no channel are
    refused by name."""
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
