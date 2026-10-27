"""#4972 (register X38): EXTRACT TCPIP over the connection the run states, on both runtimes the crucible drives.

IBM CICS TS, EXEC CICS EXTRACT TCPIP (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-extract-tcpip): the client's and
the server's address, name, address number and address family, the port in binary and the SSL type, the lengths "set to the
returned length on output"; LENGERR RESP2 1 "specified, but its length field is missing or less than or equal to zero",
RESP2 3 / 4 / 6 / 7 "too small". The stub C (tests/equivalence/cics/ggcics.c) and the generated CicsTask answer one grid of
steps alike -- every length token (missing, zero, negative, fitting, too small, past its area) for every area alone, in pairs
and all four together, every number option alone and together -- against a reference model written here from IBM's page and
the register's decisions. The grid is the whole input class of the command's options; five stated connections (a named one,
one the DNS knows nothing of, an address past a signed fullword, IPv6, and malformed IPv4) cover the data.
"""

import itertools
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cics_runtimes import _cics_task, _stub, needs_cc, needs_javac  # noqa: E402

_CAPS = (16, 20, 16, 20)  # the areas: client address, client name, server address, server name
# (client addr, client name, server addr, server name, port, SSL type); a name None: the DNS knows none
_FIXTURES = {
    "named": ("10.1.2.3", "client.example", "10.9.8.7", "srv.example", 8080, "SSL"),
    "dns": ("127.0.0.1", None, "10.0.0.1", None, 443, "NOSSL"),
    "high": ("192.168.1.5", "c", "10.0.0.2", "s", 80, "CLIENTAUTH"),
    "ipv6": ("2001:db8::1", "c6", "10.0.0.3", "s6", 8, "ATTLSAWARE"),
    "bad4": ("10.1.2", "c", "010.0.0.1", "s", 65535, "SSL"),
}
_SSL = {"SSL": 1030, "NOSSL": 1031, "CLIENTAUTH": 1032, "ATTLSAWARE": 1205}
_NUMBERS = ("cnu", "snu", "cfam", "sfam", "port", "ssl")
_BEYOND = "EXTRACT TCPIP length beyond its area"
_ADDRESS = "EXTRACT TCPIP address"
_OPEN = "EXTRACT TCPIP"
_TWO = "EXTRACT TCPIP with more than one condition at once"


def _ipv4(addr: str) -> int:
    """The address as a number, -1 when it is not four decimal parts 0-255 without a leading zero."""
    parts = addr.split(".")
    if len(parts) != 4 or any(
        not (p.isdigit() and p.isascii()) or len(p) > 3 or (len(p) > 1 and p[0] == "0") for p in parts
    ):
        return -1
    if any(int(p) > 255 for p in parts):
        return -1
    value = 0
    for p in parts:
        value = value * 256 + int(p)
    return value


def _reference(fixture: str, step: str) -> str:
    """What a runtime answers one step (`x L1 L2 L3 L4 numbers`): the line, or `refused <what>`. Written from IBM's page."""
    caddr, cname, saddr, sname, port, ssl = _FIXTURES[fixture]
    _, *tokens, numbers = step.split(" ")
    asked = [t != "-" for t in tokens]
    lens = [None if t == "-" else 0 if t == "m" else int(t) for t in tokens]
    wanted = set(numbers.split(","))
    piece = [caddr, cname or "", saddr, sname or ""]
    if any(a and n > cap for a, n, cap in zip(asked, lens, _CAPS, strict=True) if n is not None):
        return f"refused {_BEYOND}"
    cnum, snum = _ipv4(caddr), _ipv4(saddr)
    if ((asked[0] or wanted & {"cnu", "cfam"}) and cnum < 0) or ((asked[2] or wanted & {"snu", "sfam"}) and snum < 0):
        return f"refused {_ADDRESS}"
    if ("cnu" in wanted and cnum > 2**31 - 1) or ("snu" in wanted and snum > 2**31 - 1):
        return f"refused {_ADDRESS}"
    if asked[3] and sname is None:
        return f"refused {_OPEN}"
    bad = any(a and n <= 0 for a, n in zip(asked, lens, strict=True) if n is not None)
    small = any(a and n > 0 and len(p) > n for a, n, p in zip(asked, lens, piece, strict=True) if n is not None)
    if bad and small:
        return f"refused {_TWO}"
    if bad:
        return "x 22/1"
    if small:
        return f"refused {_OPEN}"
    areas = "|".join(((piece[j] if asked[j] else "") + "." * 40)[: _CAPS[j]] for j in range(4))
    numbers_out = [str(cnum) if "cnu" in wanted else "-", str(snum) if "snu" in wanted else "-",
                   "300" if "cfam" in wanted else "-", "300" if "sfam" in wanted else "-",
                   str(port) if "port" in wanted else "-", str(_SSL[ssl]) if "ssl" in wanted else "-"]  # fmt: skip
    out_lens = ",".join(str(len(piece[j])) if asked[j] else "0" for j in range(4))
    return f"x 0/0 {areas}|{'|'.join(numbers_out)}|{out_lens}"


def _steps(fixture: str) -> list[str]:
    """The grid: each area's length token alone, in pairs, all four alike, each number alone / together, areas with numbers."""
    piece = [_FIXTURES[fixture][0], _FIXTURES[fixture][1] or "", _FIXTURES[fixture][2], _FIXTURES[fixture][3] or ""]

    def token(j: int, kind: str) -> str:
        return {"-": "-", "m": "m", "0": "0", "neg": "-1", "fit": str(len(piece[j])), "cap": str(_CAPS[j]),
                "small": str(max(len(piece[j]) - 1, 0)), "over": str(_CAPS[j] + 1)}[kind]  # fmt: skip

    kinds = ("-", "m", "0", "neg", "fit", "cap", "small", "over")
    out: set[str] = set()

    def add(ts: list[str], numbers: str = "_") -> None:
        out.add("x " + " ".join(ts) + " " + numbers)

    for j in range(4):
        for k in kinds:
            add([token(i, k) if i == j else "-" for i in range(4)])
    for k in kinds:
        add([token(i, k) for i in range(4)])
    for i, j in itertools.combinations(range(4), 2):
        for ki, kj in itertools.product(("m", "small", "cap", "0"), repeat=2):
            add([token(x, ki) if x == i else token(x, kj) if x == j else "-" for x in range(4)])
    nums = [",".join(c) for r in (1, 2, 3) for c in itertools.combinations(_NUMBERS, r)] + [",".join(_NUMBERS)]
    for n in nums:
        add(["-"] * 4, n)
        add([token(i, "cap") for i in range(4)], n)
    for n in ("cnu", "port,ssl", ",".join(_NUMBERS)):  # an area with a missing / too small length beside a number
        add([token(0, "m"), "-", "-", "-"], n)
        add([token(0, "small"), "-", "-", "-"], n)
    return sorted(out)


_C_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; } gg_cics;
int GGCTCPX(gg_cics *c, char *caddr, int caddrcap, char *cname, int cnamecap, char *saddr, int saddrcap, char *sname,
            int snamecap);
int GGCTCPN(gg_cics *c);
static gg_cics c;
static void flags(const char *s) { memset(c.flags, ' ', 40); memcpy(c.flags, s, strlen(s)); }
static int number(const char *what) { flags(what); GGCTCPN(&c); return c.num; }
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        char *w[7], caddr[16], cname[20], saddr[16], sname[20], fl[80] = "";
        int k = 0;
        const char *names[4] = {"A1 ", "N1 ", "A2 ", "N2 "};
        int *len[4] = {&c.len, &c.hours, &c.mins, &c.secs};
        for (char *t = strtok(argv[i], " "); t && k < 7; t = strtok(NULL, " ")) w[k++] = t;
        memset(caddr, '.', 16); memset(cname, '.', 20); memset(saddr, '.', 16); memset(sname, '.', 20);
        for (int j = 0; j < 4; j++) {
            *len[j] = strcmp(w[1 + j], "-") == 0 || strcmp(w[1 + j], "m") == 0 ? 0 : atoi(w[1 + j]);
            if (strcmp(w[1 + j], "-") != 0) strcat(fl, names[j]);
        }
        if (strstr(w[5], "cnu")) strcat(fl, "U1 ");
        if (strstr(w[5], "snu")) strcat(fl, "U2 ");
        if (strstr(w[5], "cfam")) strcat(fl, "F1 ");
        if (strstr(w[5], "sfam")) strcat(fl, "F2 ");
        flags(fl);
        GGCTCPX(&c, caddr, 16, cname, 20, saddr, 16, sname, 20);
        printf("x %d/%d", c.resp, c.resp2);
        if (c.resp == 0) {
            printf(" %.16s|%.20s|%.16s|%.20s|", caddr, cname, saddr, sname);
            strstr(w[5], "cnu") ? printf("%d|", number("CNU")) : printf("-|");
            strstr(w[5], "snu") ? printf("%d|", number("SNU")) : printf("-|");
            strstr(w[5], "cfam") ? printf("300|") : printf("-|");
            strstr(w[5], "sfam") ? printf("300|") : printf("-|");
            strstr(w[5], "port") ? printf("%d|", number("PORT")) : printf("-|");
            strstr(w[5], "ssl") ? printf("%d|", number("SSL")) : printf("-|");
            printf("%d,%d,%d,%d", c.len, c.hours, c.mins, c.secs);
        }
        printf("\n");
    }
    return 0;
}
"""


def _cfg(fixture: str) -> str:
    caddr, cname, saddr, sname, port, ssl = _FIXTURES[fixture]
    hx = lambda v: v.encode("latin-1").hex().upper() if v else "-"  # noqa: E731
    return f"T {caddr} {hx(cname)} {saddr} {hx(sname)} {port} {ssl}\n"


def _base_env() -> dict[str, str]:
    """What the stub needs to start: Windows wants its own PATH (the MinGW runtime) and SYSTEMROOT."""
    if os.name == "nt":
        return {k: os.environ[k] for k in ("PATH", "SYSTEMROOT") if k in os.environ}
    return {"PATH": "/usr/bin:/bin"}


@needs_cc
def test_the_stub_extracts_the_stated_connection(tmp_path):
    exe = _stub(tmp_path, _C_MAIN)
    for fixture in _FIXTURES:
        cfg = tmp_path / f"tcpip-{fixture}.cfg"
        cfg.write_text(_cfg(fixture), encoding="ascii", newline="\n")
        env = {
            **_base_env(),
            "GGCICS_DIR": str(tmp_path),
            "GGCICS_OUT": str(tmp_path),
            "GGCICS_TCPIP": str(cfg),
        }
        steps = _steps(fixture)
        answers = {s: _reference(fixture, s) for s in steps}
        normal = [s for s in steps if not answers[s].startswith("refused")]
        run = subprocess.run([str(exe), *normal], env=env, capture_output=True, text=True, check=True)  # noqa: S603
        assert run.stdout.splitlines() == [answers[s] for s in normal], fixture
        for s in steps:
            if answers[s].startswith("refused"):
                bad = subprocess.run([str(exe), s], env=env, capture_output=True, text=True, check=False)  # noqa: S603
                assert (
                    bad.returncode == 98 and bad.stdout == answers[s].removeprefix("refused ") + ": not modelled\n"
                ), (
                    fixture,
                    s,
                    bad.stdout,
                )
    unstated = subprocess.run([str(exe), "x 16 - - - _"], env=_base_env(), capture_output=True,  # noqa: S603
                              text=True, check=False)  # fmt: skip
    assert unstated.returncode == 98 and "TCP/IP connection is not stated" in unstated.stdout


_JAVA_HELPERS = r"""
    static String area(String piece, int cap) {
        StringBuilder b = new StringBuilder(piece);
        while (b.length() < cap) b.append('.');
        return b.substring(0, cap);
    }
    static void step(CicsTask t, String line) {
        String[] w = line.split(" ");
        Integer[] l = new Integer[4];
        for (int j = 0; j < 4; j++) l[j] = w[1 + j].equals("-") ? null : w[1 + j].equals("m") ? Integer.valueOf(0) : Integer.valueOf(w[1 + j]);
        String n = w[5];
        CicsTask.TcpipExtracted r = t.extractTcpip(l[0], 16, l[1], 20, l[2], 16, l[3], 20, n.contains("cnu"), n.contains("snu"),
                n.contains("cfam"), n.contains("sfam"));
        if (r.resp() != 0) { System.out.println("x " + r.resp() + "/" + r.resp2()); return; }
        String[] p = {r.clientAddr(), r.clientName(), r.serverAddr(), r.serverName()};
        int[] cap = {16, 20, 16, 20};
        StringBuilder o = new StringBuilder("x 0/0 ");
        StringBuilder lens = new StringBuilder();
        for (int j = 0; j < 4; j++) {
            o.append(area(l[j] == null ? "" : p[j], cap[j])).append('|');
            lens.append(j > 0 ? "," : "").append(l[j] == null ? 0 : p[j].length());
        }
        o.append(n.contains("cnu") ? "" + r.clientNu() : "-").append('|');
        o.append(n.contains("snu") ? "" + r.serverNu() : "-").append('|');
        o.append(n.contains("cfam") ? "300" : "-").append('|');
        o.append(n.contains("sfam") ? "300" : "-").append('|');
        o.append(n.contains("port") ? "" + r.port() : "-").append('|');
        o.append(n.contains("ssl") ? "" + r.ssl() : "-").append('|');
        System.out.println(o + "" + lens);
    }
    static CicsTask task(String ca, String cn, String sa, String sn, int port, String ssl) {
        return new CicsTask("ZC01", "ENTER", null, null).withTcpip(new CicsTask.Tcpip(ca, cn, sa, sn, port, ssl));
    }
"""


def _java_str(v: str | None) -> str:
    return "null" if v is None else f'"{v}"'


@needs_javac
def test_cics_task_extracts_the_stated_connection_as_the_stub_does(tmp_path):
    parts = []
    expected: list[str] = []
    for fixture, (ca, cn, sa, sn, port, ssl) in _FIXTURES.items():
        steps = _steps(fixture)
        parts.append(
            f"{{ CicsTask t = task({_java_str(ca)}, {_java_str(cn)}, {_java_str(sa)}, {_java_str(sn)}, {port}, "
            f"{_java_str(ssl)});\n for (String s : new String[] {{{', '.join(_java_str(s) for s in steps)}}}) {{\n"
            ' try { step(t, s); } catch (UnsupportedOperationException e) { System.out.println("refused " + e.getMessage()); }\n'
            "} }"
        )
        expected += [_reference(fixture, s) for s in steps]
    parts.append(
        'try { step(new CicsTask("ZC01", "ENTER", null, null), "x 16 - - - _"); }'
        ' catch (UnsupportedOperationException e) { System.out.println("refused " + e.getMessage()); }'
    )
    out = _cics_task(tmp_path, "\n".join(parts) + "\n    }\n" + _JAVA_HELPERS + "\n    static void unused() {")
    got = [ln.removesuffix(": not modelled") if ln.startswith("refused ") else ln for ln in out.splitlines()]
    assert got[-1] == "refused the TCP/IP connection is not stated (withTcpip)"
    assert got[:-1] == expected


def test_the_grid_covers_every_condition_and_refusal():
    """The reference model reaches each documented outcome and each refusal by name (the grid is not vacuous)."""
    seen: set[str] = set()
    for fixture in _FIXTURES:
        for s in _steps(fixture):
            ans = _reference(fixture, s)
            seen.add(ans if ans.startswith("refused") else ans.split(" ")[1])
    assert seen == {"22/1", "0/0", f"refused {_BEYOND}", f"refused {_ADDRESS}", f"refused {_OPEN}", f"refused {_TWO}"}
    assert len(_steps("named")) > 150


@pytest.mark.parametrize(
    ("fixture", "step", "line"),
    [
        # IBM's own words, pinned by hand (not through the reference model): the addresses and names as stated, their lengths
        # the real ones, the binary address 10.1.2.3 = 0x0A010203, the port, the SSL type's CVDA, the client family IPV4 (300)
        ("named", "x 16 20 16 20 cnu,snu,cfam,sfam,port,ssl",
         "x 0/0 10.1.2.3........|client.example......|10.9.8.7........|srv.example.........|167838211|168364039|300|300|8080|1030|8,14,8,11"),
        # "or zero if the DNS does not know the client": length 0, the area left alone, NORMAL
        ("dns", "x - 20 - - _", "x 0/0 ................|....................|................|....................|-|-|-|-|-|-|0,0,0,0"),
        # a length "missing or less than or equal to zero": LENGERR RESP2 1
        ("named", "x m - - - _", "x 22/1"),
        ("named", "x - - 0 - _", "x 22/1"),
    ],
)  # fmt: skip
def test_ibm_documented_answers(fixture, step, line):
    assert _reference(fixture, step) == line


def test_the_stub_holds_an_ipv4_address_in_64_bits():
    """`long` is 32 bits on Windows (LLP64): 192.168.1.5 is above 2^31, wrapped negative there, and the stub refused a
    connection IBM answers (the Windows leg's exit 98). The number must be a `long long`."""
    text = (Path(__file__).resolve().parents[1] / "equivalence" / "cics" / "ggcics_web.c").read_text(encoding="utf-8")
    assert "static long long ipv4_value(" in text
    assert re.search(r"^\s*long long cnum, snum;", text, re.MULTILINE)
