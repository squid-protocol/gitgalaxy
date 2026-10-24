"""#4952: LE CEEDAYS pictures (register L1) in the det runtime (cobolrt/le/Ceedays.java) and in the harness's COBOL-side
model (tests/equivalence/le/ceedays.c), so CBSA CRECUST's CEEDAYS (picture 'YYYYMMDD' declared length 10 over 8 bytes, a date
of length 10 over 8 digits) is modelled with the 2 slack bytes ruled blank (owner decision 2026-10-23), as is CardDemo's
blank-padded 'YYYYMMDD  ' (register L1, owner decision 2026-10-14); a non-blank byte inside the item is still refused.

One vector table drives three checks, as test_det_le_time.py does for the other LE services:

1. **IBM's documented answers** (`want`): the Lilian day or the feedback message number for the input.
2. **The runtime against the oracle's model**: the same table through the Java runtime and the C model, every output
   and every refusal equal.
3. **The picture's tail**: exactly the span, a tail of blanks (ASSUMED ignored), a tail with any non-blank byte, and a
   declared length that overruns the item (slack ruled blank: NUL padding on the C side, never read on the Java side)
   are each their own rows; only a tail of blanks or slack converts. The date past its span is never read (IBM).

The input class: every token order (YYYY MM DD in all six orders, YYYY DDD in both), adjacent and each separator, the
declared length equal to / past the span (item exactly that long, or a longer item with blanks, or an overrunning
declared length), a date shorter than the span, each invalid field, the range ends, and what is refused by name.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

ROOT = Path(__file__).resolve().parents[2]
CEEDAYS_C = ROOT / "tests/equivalence/le/ceedays.c"
RT = ROOT / "gitgalaxy/tools/cobol_to_java/det/cobolrt"
REFUSED = "REFUSED"


def _lil(y: int, m: int, d: int) -> int:
    return (dt.date(y, m, d) - dt.date(1582, 10, 14)).days


def _hex_fc(msgno: int) -> str:
    return "000000000000000000000000" if msgno == 0 else f"0003{msgno:04X}59C3C5C500000000"


def _ok(y: int, m: int, d: int) -> str:
    return f"0|{_lil(y, m, d)}"


# (date text, declared date length, picture text, declared picture length, want "<msgno>|<lilian>" or REFUSED).
# The storage behind each text is exactly the text, then NUL padding: a declared length past the text overruns the item.
VECTORS = [
    # the modelled shape before #4952, all three separators
    ("1988-05-16", 10, "YYYY-MM-DD", 10, _ok(1988, 5, 16)),
    ("1988/05/16", 10, "YYYY/MM/DD", 10, _ok(1988, 5, 16)),
    ("1988.05.16", 10, "YYYY.MM.DD", 10, _ok(1988, 5, 16)),
    # CRECUST: 'YYYYMMDD' declared length 10 over 8 bytes: the 2 bytes past the picture are slack, ruled blank (L1, ASSUMED)
    ("19880516", 10, "YYYYMMDD", 10, _ok(1988, 5, 16)),
    ("20000229", 10, "YYYYMMDD", 10, _ok(2000, 2, 29)),
    ("19880516", 9, "YYYYMMDD", 9, _ok(1988, 5, 16)),  # one byte past the item
    ("19880516", 8, "YYYYMMDD", 100, _ok(1988, 5, 16)),  # far past it
    ("19880516", 10, "YYYYMMDDX", 12, REFUSED),  # a non-blank byte inside the item, then slack
    ("19880516", 8, "YYYYMMDD", 8, _ok(1988, 5, 16)),
    # a picture longer than its span with real blanks (CardDemo CSUTLDTC): the tail is ignored (L1, ASSUMED)
    ("19880516  ", 10, "YYYYMMDD  ", 10, _ok(1988, 5, 16)),
    ("19880516", 8, "YYYYMMDD  ", 10, _ok(1988, 5, 16)),
    ("19880516", 8, "YYYYMMDD ", 9, _ok(1988, 5, 16)),  # a one-byte blank tail
    ("19880516", 8, "YYYYMMDD    ", 12, _ok(1988, 5, 16)),
    ("1988-05-16", 10, "YYYY-MM-DD   ", 13, _ok(1988, 5, 16)),
    ("1988137", 7, "YYYYDDD  ", 9, _ok(1988, 5, 16)),
    ("05161988", 8, "MMDDYYYY  ", 10, _ok(1988, 5, 16)),
    # a tail with any non-blank byte is refused by name, wherever the byte sits
    ("19880516", 8, "YYYYMMDDX", 9, REFUSED),
    ("19880516", 8, "YYYYMMDD X", 10, REFUSED),
    ("19880516", 8, "YYYYMMDDX ", 10, REFUSED),
    ("19880516", 8, "YYYYMMDD00", 10, REFUSED),
    ("1988-05-16", 10, "YYYY-MM-DD.", 11, REFUSED),
    ("1988137", 7, "YYYYDDDX", 8, REFUSED),
    # a blank tail whose declared length overruns the item: the blanks, then the slack
    ("19880516", 8, "YYYYMMDD ", 12, _ok(1988, 5, 16)),
    ("1988-05-16 x", 12, "YYYY-MM-DD", 10, _ok(1988, 5, 16)),  # IBM: remaining characters of the DATE are ignored
    # every token order and separator
    ("05161988", 8, "MMDDYYYY", 8, _ok(1988, 5, 16)),
    ("16051988", 8, "DDMMYYYY", 8, _ok(1988, 5, 16)),
    ("05-16-1988", 10, "MM-DD-YYYY", 10, _ok(1988, 5, 16)),
    ("16/05/1988", 10, "DD/MM/YYYY", 10, _ok(1988, 5, 16)),
    ("1988.16.05", 10, "YYYY.DD.MM", 10, _ok(1988, 5, 16)),
    ("1988 0516", 9, "YYYY MMDD", 9, REFUSED),  # a blank separator
    ("19881605", 8, "YYYYDDMM", 8, _ok(1988, 5, 16)),
    # Julian
    ("1988137", 7, "YYYYDDD", 7, _ok(1988, 5, 16)),
    ("1988.137", 8, "YYYY.DDD", 8, _ok(1988, 5, 16)),
    ("137/1988", 8, "DDD/YYYY", 8, _ok(1988, 5, 16)),
    ("1988366", 7, "YYYYDDD", 7, _ok(1988, 12, 31)),
    ("1989366", 7, "YYYYDDD", 7, "2508|"),
    ("1988000", 7, "YYYYDDD", 7, "2508|"),
    ("1988367", 7, "YYYYDDD", 7, "2508|"),
    ("1582287", 7, "YYYYDDD", 7, "2513|"),  # day 287 of 1582 is 14 October, the day before Lilian day 1
    ("1582288", 7, "YYYYDDD", 7, _ok(1582, 10, 15)),
    # IBM's documented conditions, one invalid field at a time
    ("19000229", 8, "YYYYMMDD", 8, "2508|"),  # 1900 is not a Gregorian leap year
    ("19880230", 8, "YYYYMMDD", 8, "2508|"),
    ("19880431", 8, "YYYYMMDD", 8, "2508|"),
    ("19880500", 8, "YYYYMMDD", 8, "2508|"),
    ("1988051", 7, "YYYYMMDD", 8, "2507|"),  # shorter than the span
    ("1988-05", 7, "YYYY-MM-DD", 10, "2507|"),
    ("1988x0516", 9, "YYYY-MM-DD", 10, "2507|"),
    ("1988x05x16", 10, "YYYY-MM-DD", 10, "2520|"),  # not the separator
    ("19880x16", 8, "YYYYMMDD", 8, "2520|"),  # non-numeric
    ("1988-05-1x", 10, "YYYY-MM-DD", 10, "2520|"),
    ("15821014", 8, "YYYYMMDD", 8, "2513|"),  # before 15 October 1582
    ("15821015", 8, "YYYYMMDD", 8, _ok(1582, 10, 15)),
    ("99991231", 8, "YYYYMMDD", 8, _ok(9999, 12, 31)),
    ("00010101", 8, "YYYYMMDD", 8, "2513|"),
    # refused by name: what IBM leaves open
    ("19881316", 8, "YYYYMMDD", 8, REFUSED),  # a month outside 1-12: 2508 or 2517
    ("19880016", 8, "YYYYMMDD", 8, REFUSED),
    ("1988051 ", 8, "YYYYMMDD", 8, REFUSED),  # a trailing blank on the covered part (#4049)
    ("2022-07- 8", 10, "YYYY-MM-DD", 10, "2520|"),  # a blank inside it is a non-numeric position (CardDemo dateutil)
    ("1988 516", 8, "YYYYMMDD", 8, "2520|"),
    ("        ", 8, "YYYYMMDD", 8, REFUSED),
    ("1988-05- ", 9, "YYYY-MM-DD", 10, REFUSED),
    ("880516", 6, "YYMMDD", 6, REFUSED),  # a century window
    ("88-05-16", 8, "YY-MM-DD", 8, REFUSED),
    ("1988MAY16", 9, "YYYYMMMDD", 9, REFUSED),  # month names
    ("19880516", 8, "YYYYMM", 6, REFUSED),  # an incomplete picture
    ("1988", 4, "YYYY", 4, REFUSED),
    ("19880516", 8, "", 0, REFUSED),  # a null picture
    ("19880516", 8, "        ", 8, REFUSED),
    ("19880516", 8, "YYYYYYYY", 8, REFUSED),  # a repeated token
    ("1988-05/16", 10, "YYYY-MM/DD", 10, REFUSED),  # mixed separators
    ("1988051698", 10, "YYYYMM-DD", 9, REFUSED),
    (
        "19880516888",
        11,
        "YYYYMMDDDDD",
        11,
        REFUSED,
    ),  # after YYYY MM the last token is DD; the tail 'DDD' is not blank
    ("1988.05.137", 11, "YYYY.MM.DDD", 11, REFUSED),  # the tail 'D' after YYYY.MM.DD
    ("198805161988", 12, "YYYYMMDDYYYY", 12, REFUSED),  # a complete set, then a non-blank tail
    ("1988137", 7, "YYYYDDDMM", 9, REFUSED),  # YYYY DDD, then a non-blank tail
    ("05137", 5, "MMDDD", 5, REFUSED),  # DDD with MM
]


def _vid(v):
    return f"{v[0]!r}/{v[1]}:{v[2]!r}/{v[3]}"


C_DRIVER = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int CEEDAYS(unsigned char*, unsigned char*, unsigned char*, unsigned char*);
/* argv: date text, declared length, picture text, declared length. The item is its text (2 + n bytes, on the heap),
 * then 256 NUL bytes (cobc's padding after a 01 item) for a declared length that overruns the item, as
 * CRECUST's does. */
static unsigned char *vstr(const char *s, int declared) {
    size_t n = strlen(s);
    unsigned char *o = malloc(2 + n + 256);
    o[0] = declared >> 8; o[1] = declared & 255; memcpy(o + 2, s, n);
    memset(o + 2 + n, 0, 256);
    return o;
}
int main(int argc, char **argv) {
    unsigned char l[4] = {9, 9, 9, 9}, fc[12];
    memset(fc, 0xEE, 12);
    unsigned char *date = vstr(argv[1], atoi(argv[2])), *pic = vstr(argv[3], atoi(argv[4]));
    CEEDAYS(date, pic, l, fc);
    for (int i = 0; i < 12; i++) printf("%02X", fc[i]);
    printf("|%ld\n", (long)((l[0] << 24) | (l[1] << 16) | (l[2] << 8) | l[3]));
    return 0;
}
"""

JAVA_PROBE = """
import java.io.*;
import java.nio.charset.StandardCharsets;
import p.cobolrt.*;
import p.cobolrt.le.*;

public class Probe {
    static Field vstr(String t, int declared) {
        byte[] b = t.getBytes(StandardCharsets.ISO_8859_1);
        Storage s = new Storage(2 + b.length + 256); // the item, then storage the runtime must not read (0xFF: a read would show)
        java.util.Arrays.fill(s.bytes, 2 + b.length, s.bytes.length, (byte) 0xFF);
        s.bytes[0] = (byte) (declared >> 8);
        s.bytes[1] = (byte) declared;
        System.arraycopy(b, 0, s.bytes, 2, b.length);
        return Field.alphanumeric(s, 0, 2 + b.length, false);
    }
    public static void main(String[] a) throws Exception {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        String line;
        while ((line = in.readLine()) != null) {
            String[] t = line.split("\\\\|", -1);
            Storage ls = new Storage(4);
            java.util.Arrays.fill(ls.bytes, (byte) 9);
            Storage fs = new Storage(12);
            java.util.Arrays.fill(fs.bytes, (byte) 0xEE);
            try {
                Ceedays.call(vstr(t[0], Integer.parseInt(t[1])), vstr(t[2], Integer.parseInt(t[3])),
                    Field.alphanumeric(ls, 0, 4, false), Field.alphanumeric(fs, 0, 12, false));
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < 12; i++) sb.append(String.format("%02X", fs.bytes[i] & 0xff));
                int v = ((ls.bytes[0] & 0xff) << 24) | ((ls.bytes[1] & 0xff) << 16) | ((ls.bytes[2] & 0xff) << 8) | (ls.bytes[3] & 0xff);
                System.out.println(sb + "|" + v);
            } catch (UnsupportedOperationException e) {
                if (!e.getMessage().startsWith("CEEDAYS: ")) throw e;
                System.out.println("REFUSED");
            }
        }
    }
}
"""


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


def _check_want(row: str, want: str) -> None:
    if want == REFUSED:
        assert row == REFUSED, row
        return
    msgno, lilian = want.split("|", 1)
    fc, got = row.split("|", 1)
    assert fc == _hex_fc(int(msgno)), (row, want)
    # a failed conversion leaves the Lilian output 0 (IBM)
    assert got == (lilian if int(msgno) == 0 else "0"), (row, want)


@pytest.fixture(scope="module")
def c_driver(tmp_path_factory):
    if not shutil.which("gcc"):
        pytest.skip("needs a C compiler")
    d = tmp_path_factory.mktemp("ceedays_c")
    (d / "driver.c").write_text(C_DRIVER, newline="\n")
    for flags in (["-fsanitize=address"], []):  # without a sanitizer runtime the Java side still checks the overrun
        run = subprocess.run(  # noqa: S603
            ["gcc", "-O0", *flags, "-o", str(d / "t"), str(d / "driver.c"), str(CEEDAYS_C)],
            capture_output=True,
            text=True,
            check=False,
        )
        if run.returncode == 0:
            break
    assert run.returncode == 0, run.stderr
    return d / "t"


def _run_c(exe: Path, v) -> str:
    env = {**os.environ, "ASAN_OPTIONS": "detect_leaks=0"}  # the driver exits without freeing, as a refusal does
    run = subprocess.run(  # noqa: S603
        [str(exe), v[0], str(v[1]), v[2], str(v[3])], capture_output=True, text=True, check=False, env=env
    )
    if run.returncode == 98:
        assert "not modelled" in run.stderr, run.stderr
        return REFUSED
    assert run.returncode == 0, run.stderr
    return run.stdout.rstrip("\n")


@pytest.mark.parametrize("v", VECTORS, ids=[_vid(v) for v in VECTORS])
def test_the_oracle_model_gives_ibms_answers(c_driver, v):
    _check_want(_run_c(c_driver, v), v[4])


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_runtime_is_the_oracle_model_byte_for_byte(c_driver, tmp_path):
    out = tmp_path / "src/p/cobolrt"
    (out / "le").mkdir(parents=True)
    for f in RT.glob("*.java"):
        (out / f.name).write_text(f.read_text(encoding="utf-8").replace("__PACKAGE__", "p"), encoding="utf-8")
    for f in (RT / "le").glob("*.java"):
        (out / "le" / f.name).write_text(f.read_text(encoding="utf-8").replace("__PACKAGE__", "p"), encoding="utf-8")
    (tmp_path / "src/Probe.java").write_text(JAVA_PROBE)
    jdk = _jdk()
    files = [str(f) for f in (tmp_path / "src").rglob("*.java")]
    javac_run(
        [str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"), *files], check=True
    )  # noqa: S603
    feed = "\n".join(f"{v[0]}|{v[1]}|{v[2]}|{v[3]}" for v in VECTORS) + "\n"
    got = subprocess.run(  # noqa: S603
        [
            str(jdk / "java"),
            "-Dfile.encoding=UTF-8",
            "-Dstdout.encoding=UTF-8",
            "-cp",
            str(tmp_path / "classes"),
            "Probe",
        ],
        input=feed,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout.splitlines()
    assert len(got) == len(VECTORS)
    bad = []
    for v, java in zip(VECTORS, got, strict=True):
        c = _run_c(c_driver, v)
        if java != c:
            bad.append(f"{_vid(v)}\n  java {java}\n  c    {c}")
        _check_want(java, v[4])
    assert not bad, "\n".join(bad)


def test_every_outcome_is_in_the_table():
    wants = {v[4].split("|")[0] for v in VECTORS}
    assert {"0", "2507", "2508", "2513", "2520", REFUSED} <= wants


# #5003: the sweep of the burned estates for a vstring declared longer than its text (register L1). The LE date/time
# services read the declared length, so a length VALUE past the PIC X(n) text beside it reads the storage after the item.
BURNED = (
    "aws-mainframe-modernization-carddemo",
    "cics-async-api-credit-card-application-example",
    "cics-banking-sample-application-cbsa",
    "cics-genapp",
    "dbb-mortgage-application",
    "zecs",
)
LE_DATE_CALL = re.compile(r"CALL\s+['\"](CEE(?:DAYS|DATM|SECS|DATE))['\"]", re.IGNORECASE)
# a halfword length item with a VALUE, then the PIC X(n) text item that follows it
VSTRING_DECL = re.compile(
    r"PIC\s+S9\(4\)\s+(?:BINARY|COMP(?:-4|-5)?)\s+VALUE\s+(\d+)\s*\.\s*\n\s*\d+\s+\S+\s+PIC\s+X\((\d+)\)", re.IGNORECASE
)


def _burned_sources():
    base = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    if not base or not Path(base).is_dir():
        pytest.skip("needs the mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    for estate in BURNED:
        for f in sorted((Path(base) / estate).rglob("*")):
            if f.suffix.lower() in {".cbl", ".cob", ".cobol"} and f.is_file():
                yield estate, f, f.read_text(encoding="latin-1")


def test_only_cbsa_crecust_declares_a_vstring_length_past_its_text():
    callers, overruns = set(), set()
    for estate, f, text in _burned_sources():
        for m in LE_DATE_CALL.finditer(text):
            callers.add((f.name, m.group(1).upper()))
        if LE_DATE_CALL.search(text):
            for m in VSTRING_DECL.finditer(text):
                if int(m.group(1)) > int(m.group(2)):
                    overruns.add((estate, f.name, int(m.group(1)), int(m.group(2))))
    assert callers >= {("CSUTLDTC.cbl", "CEEDAYS"), ("CRECUST.cbl", "CEEDAYS"), ("BANKDATA.cbl", "CEEDATM")}
    # CRECUST's picture ('YYYYMMDD', length 10 over 8) is the one overrun: its slack is ruled blank (register L1); CardDemo builds
    # its length from LENGTH OF the format item and BANKDATA's CEEDATM picture is exactly 14 over 14
    crecust = {o for o in overruns if o[1] == "CRECUST.cbl"}
    assert ("cics-banking-sample-application-cbsa", "CRECUST.cbl", 10, 8) in crecust
    assert {o[1] for o in overruns} == {"CRECUST.cbl"}


def test_the_dateutil_case_calls_every_julian_day_boundary_the_model_documents():
    """#4049: CSUTLDTC's case grows the YYYYDDD calls (day 000, 366 in a leap and a non-leap year, the Lilian and 9999
    ends, a non-digit), each on a picture the model documents; the port answers them too (a DDD token)."""
    import json

    case = json.loads((ROOT / "tests/equivalence/carddemo-dateutil/case.json").read_text(encoding="utf-8"))
    julian = {c["name"]: c["args"] for c in case["calls"] if c["name"].startswith("julian-")}
    modelled = {"YYYYDDD   ", "DDDYYYY   ", "YYYY-DDD  "}
    assert {a[1] for a in julian.values()} <= modelled
    dates = {a[0].strip() for a in julian.values()}
    assert {"2022000", "2023366", "2024366", "1900366", "2000366", "2024367", "1582287", "1582288", "9999365"} <= dates
    assert any(not d.isdigit() for d in dates), "a non-digit in the date"
    port = ROOT / "tests/equivalence/carddemo-dateutil/port/service/CsutldtcService.java"
    assert '"DDD"' in port.read_text(encoding="utf-8")
