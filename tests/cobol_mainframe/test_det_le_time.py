"""#4949: the Language Environment date/time callable services CEEGMT / CEEUTC, CEEDATM, CEESECS, CEEDATE, CEEISEC and
CEEQCEN in the det runtime (cobolrt/le/LeTime.java) and in the harness's COBOL-side model (tests/equivalence/le/
le_time.c), so a program that CALLs them (CBSA BANKDATA: CEEGMT + CEEDATM) translates.

One vector table drives three checks:

1. **IBM's own examples and the documented condition codes** (`want`): the value or feedback message number IBM's
   reference gives for the input (register L6 names the source of each); the byte layout of the token is checked too.
2. **The runtime against the oracle's model**: the same table run through the Java runtime and through the C model;
   every output byte-for-byte equal, every refusal ("NAME: ... is not modelled") on both sides.
3. **The translator's wiring** (`gen.LIBRARY`): arity, the clock, the COMP-2 arguments by value.

The input class per service: the valid range ends, every documented condition (one invalid field at a time), the
picture tokens modelled, and what is refused by name (what IBM leaves open: more than one invalid field, a short
or leading-blank timestamp, omitted leading zeros, a century-window YY, names / AP / Z pictures, a null picture).
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import shutil
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gitgalaxy.tools.cobol_to_java.det import gen as G  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import le_out_size  # noqa: E402 -- #5003
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

LE_C = ROOT / "tests/equivalence/le/le_time.c"
RT = ROOT / "gitgalaxy/tools/cobol_to_java/det/cobolrt"
CLOCK_C = "2026/10/01 10:30:15.25"
REFUSED = "REFUSED"
D = "1988-05-16"  # day 148138 (IBM: "16 May 1988 is day number 148 138")
SECS_1988 = 148138 * 86400 + 19 * 3600 + 1  # 19:00:01 on 16 May 1988 (IBM: second 12 799 191 601)
CLOCK_2000 = "2000/01/01 00:00:00.00"


def _midnight(y: int, m: int, d: int) -> str:
    """The CEESECS answer for a date with no time: "0|<Lilian seconds>.000"."""
    return f"0|{(_dt.date(y, m, d) - _dt.date(1582, 10, 14)).days * 86400}.000"


# (service, args, want): want is "<msgno>|<value>" -- msgno 0 on success; REFUSED for a call the model refuses by name;
# None where the table only checks that the two models agree. Value: CEEGMT "lilian,seconds", CEEQCEN the century, CEEDATE
# / CEEDATM the text, CEESECS / CEEISEC the seconds to the millisecond, "0.000" when the call fails.
VECTORS: list[tuple[str, list[str], str | None]] = [
    # CEEQCEN: the ILE / LE default window starts 80 years before the system date
    ("CEEQCEN", [], "0|80"),
    # CEESCEN (#5003): sets the window's start (0 to 100), CEEQCEN reads it back; CEE2533 outside, the setting kept.
    # Each row sets in order then queries: "<token of the last set>|<the value CEEQCEN returns>". Nothing reads the window yet.
    ("CEESCEN", ["80"], "0|80"),
    ("CEESCEN", ["0"], "0|0"),
    ("CEESCEN", ["100"], "0|100"),
    ("CEESCEN", ["50"], "0|50"),
    ("CEESCEN", ["101"], "2533|80"),
    ("CEESCEN", ["-1"], "2533|80"),
    ("CEESCEN", ["50", "101"], "2533|50"),
    ("CEESCEN", ["50", "-1"], "2533|50"),
    ("CEESCEN", ["100", "0"], "0|0"),
    ("CEESCEN", ["0", "100", "101"], "2533|100"),
    # CEEGMT / CEEUTC: the pinned clock as GMT (the det runtime's CURRENT-DATE carries +0000)
    (
        "CEEGMT",
        [CLOCK_C],
        f"0|{(__import__('datetime').date(2026, 10, 1) - __import__('datetime').date(1582, 10, 14)).days},"
        f"{(__import__('datetime').date(2026, 10, 1) - __import__('datetime').date(1582, 10, 14)).days * 86400 + 37815}.250",
    ),
    ("CEEUTC", [CLOCK_C], None),
    # CEEGMTO / CEEUTCO (#5003): the offset from GMT; the clock is GMT, so hours, minutes and seconds are zero
    ("CEEGMTO", [], "0|0,0,0.000"),
    ("CEEUTCO", [], "0|0,0,0.000"),
    ("CEEGMT", ["1582/10/15 00:00:00.00"], "0|1,86400.000"),
    ("CEEGMT", ["9999/12/31 23:59:59.99"], "0|3074324,265621679999.990"),
    # CEEDATE (IBM's sample output table)
    ("CEEDATE", ["148138", "YYYY-MM-DD"], "0|1988-05-16"),
    ("CEEDATE", ["148138", "YYYYMMDD"], "0|19880516"),
    ("CEEDATE", ["148138", "YYMMDD"], "0|880516"),
    ("CEEDATE", ["148138", "YY-MM"], "0|88-05"),
    ("CEEDATE", ["148139", "MM/DD/YYYY"], "0|05/17/1988"),
    ("CEEDATE", ["148139", "MMDD"], "0|0517"),
    ("CEEDATE", ["148140", "DD.MM.YYYY"], "0|18.05.1988"),
    ("CEEDATE", ["148140", "DDMMYY"], "0|180588"),
    ("CEEDATE", ["148141", "YYYY.DDD"], "0|1988.140"),
    ("CEEDATE", ["148141", "YYDDD"], "0|88140"),
    ("CEEDATE", ["148142", "YY/MM/DD HH:MI:SS.99"], "0|88/05/20 00:00:00.00"),
    ("CEEDATE", ["1", "YYYYMMDD"], "0|15821015"),
    ("CEEDATE", ["3074324", "YYYY-MM-DD"], "0|9999-12-31"),
    ("CEEDATE", ["3074324", "YYYY.DDD"], "0|9999.365"),
    ("CEEDATE", ["2", "YYYY.DDD"], "0|1582.289"),
    ("CEEDATE", ["200000", "YYYY.DDD"], None),  # a leap year's day 366 and the year change
    ("CEEDATE", ["0", "YYYY-MM-DD"], "2512|"),
    ("CEEDATE", ["-1", "YYYY-MM-DD"], "2512|"),
    ("CEEDATE", ["3074325", "YYYY-MM-DD"], "2512|"),
    ("CEEDATE", ["148138", "Www"], REFUSED),  # day names: not modelled
    ("CEEDATE", ["148138", "MMM"], REFUSED),
    ("CEEDATE", ["148138", "ZM/ZD/YYYY"], REFUSED),
    ("CEEDATE", ["148138", "<JJJJ> YY.MM.DD"], REFUSED),  # eras
    ("CEEDATE", ["148138", ""], REFUSED),  # IBM: the country default
    ("CEEDATE", ["148138", "YYYY YYYY"], REFUSED),  # a repeated token
    ("CEEDATE", ["148138", "YYYY-M"], REFUSED),  # a lone M
    # CEEDATM (IBM's sample output table)
    ("CEEDATM", [str(SECS_1988), "YYYY-MM-DD HH:MI:SS"], "0|1988-05-16 19:00:01"),
    ("CEEDATM", [str(SECS_1988), "YYYYMMDDHHMISS"], "0|19880516190001"),
    ("CEEDATM", [str(SECS_1988), "YYMMDDHHMISS"], "0|880516190001"),
    ("CEEDATM", [str(SECS_1988), "YY-MM-DD HH:MI:SS"], "0|88-05-16 19:00:01"),
    ("CEEDATM", [str(SECS_1988), "YYMMDD"], "0|880516"),
    ("CEEDATM", [str(SECS_1988), "YYYY/MM/DD HH.MI.SS"], "0|1988/05/16 19.00.01"),  # IBM's CEEDATM example picture
    ("CEEDATM", [str(SECS_1988 + 0.5), "HH:MI:SS.99"], "0|19:00:01.50"),
    ("CEEDATM", [str(SECS_1988 + 0.125), "SS.999"], "0|01.125"),
    ("CEEDATM", [str(SECS_1988 + 0.125), "SS.99"], "0|01.12"),  # the hundredths are cut, not rounded
    ("CEEDATM", [str(SECS_1988), "DDD"], "0|137"),
    ("CEEDATM", ["86400", "YYYYMMDDHHMISS"], "0|15821015000000"),
    ("CEEDATM", ["86399", "YYYYMMDDHHMISS"], "2505|"),
    ("CEEDATM", ["86399.5", "YYYYMMDDHHMISS"], "2505|"),
    ("CEEDATM", ["0", "YYYYMMDDHHMISS"], "2505|"),
    ("CEEDATM", ["-86400", "YYYYMMDDHHMISS"], "2505|"),
    ("CEEDATM", ["265621679999", "YYYYMMDDHHMISS"], "0|99991231235959"),
    ("CEEDATM", ["265621679999.5", "YYYYMMDDHHMISS.999"], "0|99991231235959.500"),
    ("CEEDATM", ["265621680000", "YYYYMMDDHHMISS"], "2505|"),
    ("CEEDATM", [str(SECS_1988), "Mmm"], REFUSED),
    ("CEEDATM", [str(SECS_1988), "HH:MI AP"], REFUSED),
    ("CEEDATM", [str(SECS_1988), ""], REFUSED),
    ("CEEDATM", [str(SECS_1988), "SS SS"], REFUSED),
    # CEESECS (IBM's examples: 19:00:01 on 16 May 1988 is 12 799 191 601; a time omitted is zeros)
    ("CEESECS", ["1988-05-16 19:00:01", "YYYY-MM-DD HH:MI:SS"], f"0|{SECS_1988}.000"),
    ("CEESECS", ["1988-05-16 19:00:01.12", "YYYY-MM-DD HH:MI:SS.99"], f"0|{SECS_1988}.120"),
    ("CEESECS", ["1988-05-16 19:00:01.125", "YYYY-MM-DD HH:MI:SS.999"], f"0|{SECS_1988}.125"),
    ("CEESECS", ["19880516190001", "YYYYMMDDHHMISS"], f"0|{SECS_1988}.000"),
    ("CEESECS", ["05/16/1988", "MM/DD/YYYY"], f"0|{148138 * 86400}.000"),
    ("CEESECS", ["16.05.1988 19:00", "DD.MM.YYYY HH:MI"], f"0|{148138 * 86400 + 19 * 3600}.000"),
    ("CEESECS", ["1988-05-16 trailing text", "YYYY-MM-DD"], f"0|{148138 * 86400}.000"),  # the rest is ignored
    ("CEESECS", ["1582-10-15", "YYYY-MM-DD"], "0|86400.000"),
    ("CEESECS", ["9999-12-31 23:59:59", "YYYY-MM-DD HH:MI:SS"], "0|265621679999.000"),
    (
        "CEESECS",
        ["2000-02-29", "YYYY-MM-DD"],
        f"0|{(__import__('datetime').date(2000, 2, 29) - __import__('datetime').date(1582, 10, 14)).days * 86400}.000",
    ),
    ("CEESECS", ["1988-13-16", "YYYY-MM-DD"], "2517|0.000"),
    ("CEESECS", ["1988-00-16", "YYYY-MM-DD"], "2517|0.000"),
    ("CEESECS", ["1988-02-30", "YYYY-MM-DD"], "2508|0.000"),
    ("CEESECS", ["1900-02-29", "YYYY-MM-DD"], "2508|0.000"),
    ("CEESECS", ["1988-04-31", "YYYY-MM-DD"], "2508|0.000"),
    ("CEESECS", ["1988-05-00", "YYYY-MM-DD"], "2508|0.000"),
    ("CEESECS", ["1988-05-16 24:00:00", "YYYY-MM-DD HH:MI:SS"], "2510|0.000"),
    ("CEESECS", ["1988-05-16 19:60:00", "YYYY-MM-DD HH:MI:SS"], "2516|0.000"),
    ("CEESECS", ["1988-05-16 19:00:60", "YYYY-MM-DD HH:MI:SS"], "2519|0.000"),
    ("CEESECS", ["1581-12-31", "YYYY-MM-DD"], "2521|0.000"),
    ("CEESECS", ["0000-01-01", "YYYY-MM-DD"], "2521|0.000"),
    ("CEESECS", ["1582-10-14", "YYYY-MM-DD"], "2513|0.000"),  # before the first Lilian day
    ("CEESECS", ["1582-01-01", "YYYY-MM-DD"], "2513|0.000"),
    ("CEESECS", ["1988-05-1x", "YYYY-MM-DD"], "2525|0.000"),  # ASSUMED: a non-digit is a picture mismatch
    ("CEESECS", ["1988/05/16", "YYYY-MM-DD"], "2525|0.000"),
    ("CEESECS", ["abcd-05-16", "YYYY-MM-DD"], "2525|0.000"),
    ("CEESECS", ["1988-05-16", "YYYY-MM-DD HH:MI:SS"], REFUSED),  # shorter than its picture
    ("CEESECS", ["1988-5-16", "YYYY-MM-DD"], REFUSED),  # leading zeros omitted (IBM allows it)
    ("CEESECS", ["1988-05-1", "YYYY-MM-DD"], REFUSED),
    ("CEESECS", [" 1988-05-16", "YYYY-MM-DD"], REFUSED),  # leading blank
    # a YY is windowed: [system year - start, + 99], the start 80 until CEESCEN sets it. The row's extra arguments are the
    # CEESCEN value called first ("" for none) and the pinned clock (the system year: 2026, or 2000 below)
    ("CEESECS", ["88-05-16", "YY-MM-DD", "", CLOCK_C], _midnight(1988, 5, 16)),  # window 1946 .. 2045
    ("CEESECS", ["45-05-16", "YY-MM-DD", "", CLOCK_C], _midnight(2045, 5, 16)),
    ("CEESECS", ["46-05-16", "YY-MM-DD", "", CLOCK_C], _midnight(1946, 5, 16)),
    ("CEESECS", ["00-01-01", "YY-MM-DD", "", CLOCK_C], _midnight(2000, 1, 1)),
    ("CEESECS", ["99-12-31", "YY-MM-DD", "", CLOCK_C], _midnight(1999, 12, 31)),
    ("CEESECS", ["880516190001", "YYMMDDHHMISS", "", CLOCK_C], f"0|{SECS_1988}.000"),
    ("CEESECS", ["88-05-16", "YY-MM-DD", "0", CLOCK_C], _midnight(2088, 5, 16)),  # start 0: 2026 .. 2125
    ("CEESECS", ["26-05-16", "YY-MM-DD", "0", CLOCK_C], _midnight(2026, 5, 16)),
    ("CEESECS", ["25-05-16", "YY-MM-DD", "0", CLOCK_C], _midnight(2125, 5, 16)),
    ("CEESECS", ["26-05-16", "YY-MM-DD", "100", CLOCK_C], _midnight(1926, 5, 16)),  # start 100: 1926 .. 2025
    ("CEESECS", ["25-05-16", "YY-MM-DD", "100", CLOCK_C], _midnight(2025, 5, 16)),
    ("CEESECS", ["75-05-16", "YY-MM-DD", "50", CLOCK_C], _midnight(2075, 5, 16)),  # start 50: 1976 .. 2075
    ("CEESECS", ["76-05-16", "YY-MM-DD", "50", CLOCK_C], _midnight(1976, 5, 16)),
    ("CEESECS", ["88-05-16", "YY-MM-DD", "101", CLOCK_C], _midnight(1988, 5, 16)),  # CEE2533: the window stays 80
    ("CEESECS", ["19-06-01", "YY-MM-DD", "", CLOCK_2000], _midnight(2019, 6, 1)),  # the clock's year, not 2026
    ("CEESECS", ["20-06-01", "YY-MM-DD", "", CLOCK_2000], _midnight(1920, 6, 1)),
    ("CEESECS", ["00-02-29", "YY-MM-DD", "100", CLOCK_2000], "2508|0.000"),  # window 1900: no 29 February
    ("CEESECS", ["00-02-29", "YY-MM-DD", "", CLOCK_2000], _midnight(2000, 2, 29)),
    ("CEESECS", ["8a-05-16", "YY-MM-DD", "", CLOCK_C], "2525|0.000"),
    ("CEESECS", ["88.137", "YY.DDD", "", CLOCK_C], REFUSED),  # a Julian date: still refused
    ("CEESECS", ["1988.137", "YYYY.DDD"], REFUSED),  # a Julian date
    ("CEESECS", ["19:00", "HH:MI"], REFUSED),  # no date
    ("CEESECS", ["1988-13-32", "YYYY-MM-DD"], REFUSED),  # two invalid fields: which condition comes first is open
    ("CEESECS", ["1988-05-16", ""], REFUSED),
    ("CEESECS", ["1988-May-16", "YYYY-Mmm-DD"], REFUSED),
    # CEEISEC
    ("CEEISEC", ["1988", "5", "16", "19", "0", "1", "0"], f"0|{SECS_1988}.000"),
    ("CEEISEC", ["1988", "5", "16", "19", "0", "1", "120"], f"0|{SECS_1988}.120"),
    ("CEEISEC", ["1582", "10", "15", "0", "0", "0", "0"], "0|86400.000"),
    ("CEEISEC", ["9999", "12", "31", "23", "59", "59", "999"], "0|265621679999.999"),
    (
        "CEEISEC",
        ["2000", "2", "29", "0", "0", "0", "0"],
        "0|"
        + str((__import__("datetime").date(2000, 2, 29) - __import__("datetime").date(1582, 10, 14)).days * 86400)
        + ".000",
    ),
    ("CEEISEC", ["1988", "0", "16", "0", "0", "0", "0"], "2517|0.000"),
    ("CEEISEC", ["1988", "13", "16", "0", "0", "0", "0"], "2517|0.000"),
    ("CEEISEC", ["1988", "4", "31", "0", "0", "0", "0"], "2511|0.000"),
    ("CEEISEC", ["1900", "2", "29", "0", "0", "0", "0"], "2511|0.000"),
    ("CEEISEC", ["1988", "5", "0", "0", "0", "0", "0"], "2511|0.000"),
    ("CEEISEC", ["1988", "5", "32", "0", "0", "0", "0"], "2511|0.000"),
    ("CEEISEC", ["1988", "5", "-1", "0", "0", "0", "0"], "2511|0.000"),
    ("CEEISEC", ["1988", "5", "16", "24", "0", "0", "0"], "2510|0.000"),
    ("CEEISEC", ["1988", "5", "16", "-1", "0", "0", "0"], "2510|0.000"),
    ("CEEISEC", ["1988", "5", "16", "0", "60", "0", "0"], "2516|0.000"),
    ("CEEISEC", ["1988", "5", "16", "0", "0", "60", "0"], "2519|0.000"),
    ("CEEISEC", ["1988", "5", "16", "0", "0", "0", "1000"], "2515|0.000"),
    ("CEEISEC", ["1988", "5", "16", "0", "0", "0", "-1"], "2515|0.000"),
    ("CEEISEC", ["1581", "12", "31", "0", "0", "0", "0"], "2514|0.000"),
    ("CEEISEC", ["10000", "1", "1", "0", "0", "0", "0"], "2514|0.000"),
    ("CEEISEC", ["0", "1", "1", "0", "0", "0", "0"], "2514|0.000"),
    ("CEEISEC", ["1582", "10", "14", "0", "0", "0", "0"], "2513|0.000"),
    ("CEEISEC", ["1582", "1", "1", "0", "0", "0", "0"], "2513|0.000"),
    ("CEEISEC", ["1988", "13", "32", "0", "0", "0", "0"], REFUSED),  # more than one invalid field
    ("CEEISEC", ["1988", "5", "16", "24", "60", "0", "0"], REFUSED),
    ("CEEISEC", ["1500", "13", "1", "0", "0", "0", "0"], REFUSED),  # a year and a month invalid
]


def _lilian(y: int, m: int, d: int) -> int:
    return (_dt.date(y, m, d) - _dt.date(1582, 10, 14)).days


def _dow(n: int) -> int:
    """IBM's CEEDYWK number for Lilian day n: 1 Sunday .. 7 Saturday (Python's weekday() is Monday 0)."""
    return ((_dt.date(1582, 10, 14) + _dt.timedelta(days=n)).weekday() + 1) % 7 + 1


def _ymd_row(y, mo, d, h, mi, s, ms):
    return f"0|{y},{mo},{d},{h},{mi},{s},0.{ms:03d}"


_FAILED_SECI = "2505|0,0,0,0,0,0,0.000"
# CEESECI (#5003): Lilian seconds to year, month, day, hours, minutes, seconds, milliseconds (shown as 0.mmm). The
# fractions are exact in binary (.125, .5): HFP and IEEE floor the same millisecond.
VECTORS += [
    ("CEESECI", [str(SECS_1988)], _ymd_row(1988, 5, 16, 19, 0, 1, 0)),
    ("CEESECI", [f"{SECS_1988}.125"], _ymd_row(1988, 5, 16, 19, 0, 1, 125)),
    ("CEESECI", ["86400"], _ymd_row(1582, 10, 15, 0, 0, 0, 0)),  # the first valid second
    ("CEESECI", ["86400.9995"], _ymd_row(1582, 10, 15, 0, 0, 0, 999)),  # floored, never rounded
    ("CEESECI", ["265621679999.5"], _ymd_row(9999, 12, 31, 23, 59, 59, 500)),  # the last valid second
    ("CEESECI", [str(_lilian(2000, 2, 29) * 86400)], _ymd_row(2000, 2, 29, 0, 0, 0, 0)),
    ("CEESECI", [str(_lilian(1900, 3, 1) * 86400 - 1)], _ymd_row(1900, 2, 28, 23, 59, 59, 0)),  # 1900 is not leap
    ("CEESECI", [str(_lilian(1900, 3, 1) * 86400)], _ymd_row(1900, 3, 1, 0, 0, 0, 0)),
    ("CEESECI", [str(_lilian(1989, 1, 1) * 86400 + 86399)], _ymd_row(1989, 1, 1, 23, 59, 59, 0)),
    ("CEESECI", ["86399.999"], _FAILED_SECI),
    ("CEESECI", ["0"], _FAILED_SECI),
    ("CEESECI", ["-1"], _FAILED_SECI),
    ("CEESECI", ["265621680000"], _FAILED_SECI),
]
# CEEDYWK (#5003): the day of the week, 1 Sunday .. 7 Saturday; Lilian day 1 (15 October 1582) was a Friday and
# 16 May 1988 (day 148 138) a Monday. Every weekday from both ends, then the bounds and the failures.
VECTORS += [("CEEDYWK", [str(n)], f"0|{_dow(n)}") for n in [*range(1, 15), *range(148138, 148145)]]
VECTORS += [
    ("CEEDYWK", ["3074324"], f"0|{_dow(3074324)}"),  # 31 December 9999
    ("CEEDYWK", ["3074323"], f"0|{_dow(3074323)}"),
    ("CEEDYWK", ["0"], "2512|0"),
    ("CEEDYWK", ["-1"], "2512|0"),
    ("CEEDYWK", ["3074325"], "2512|0"),
]


def _hex_fc(msgno: int) -> str:
    """The 12-byte token: severity 3, message number, case 1 / severity 3 / control 1, 'CEE' in EBCDIC, ISI zero."""
    return "000000000000000000000000" if msgno == 0 else f"0003{msgno:04X}59C3C5C500000000"


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


def _norm(value: str) -> str:
    """Seconds to the millisecond (the float's last bits differ between HFP and IEEE by design, register C6)."""
    out = []
    for part in value.split(","):
        try:
            out.append(str(Decimal(part).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)))
        except ArithmeticError:
            out.append(part)
    return ",".join(out)


def _check_want(row: str, want: str | None) -> None:
    if want is None or want == REFUSED:
        assert (want is None) or row == REFUSED, row
        return
    msgno, value = want.split("|", 1)
    fc, got = row.split("|", 1)
    assert fc == _hex_fc(int(msgno)), (row, want)
    if int(msgno) == 0 or value:
        assert (_norm(got) if "," in want or "." in want else got) == (_norm(value) if "." in value else value), (
            row,
            want,
        )


# ---- 1 + 2. the C model and the Java runtime, one table -----------------------------------------------------------


C_DRIVER = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#define setenv(k, v, o) _putenv_s((k), (v)) /* MinGW has no setenv */
#endif
int CEEGMT(unsigned char*, unsigned char*, unsigned char*);
int CEEUTC(unsigned char*, unsigned char*, unsigned char*);
int CEEQCEN(unsigned char*, unsigned char*);
int CEESCEN(unsigned char*, unsigned char*);
int CEEGMTO(unsigned char*, unsigned char*, unsigned char*, unsigned char*);
int CEEUTCO(unsigned char*, unsigned char*, unsigned char*, unsigned char*);
int CEEDATE(unsigned char*, unsigned char*, unsigned char*, unsigned char*);
int CEEDATM(unsigned char*, unsigned char*, unsigned char*, unsigned char*);
int CEESECS(unsigned char*, unsigned char*, unsigned char*, unsigned char*);
int CEEISEC(unsigned char*, unsigned char*, unsigned char*, unsigned char*, unsigned char*, unsigned char*,
            unsigned char*, unsigned char*, unsigned char*);
int CEESECI(unsigned char*, unsigned char*, unsigned char*, unsigned char*, unsigned char*, unsigned char*,
            unsigned char*, unsigned char*, unsigned char*);
int CEEDYWK(unsigned char*, unsigned char*, unsigned char*);
static long rd4(const unsigned char *b) { return (int)(((unsigned)b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]); }
static void vstr(unsigned char *o, const char *s) { size_t n = strlen(s); o[0] = n >> 8; o[1] = n & 255; memcpy(o + 2, s, n); }
static void i4(unsigned char *o, long v) { o[0] = v >> 24; o[1] = v >> 16; o[2] = v >> 8; o[3] = v; }
static void hexfc(const unsigned char *fc) { for (int i = 0; i < 12; i++) printf("%02X", fc[i]); }
int main(int argc, char **argv) {
    const char *svc = argv[1];
    unsigned char fc[12], out[600], sec[8], pic[300], in[300], l[4], a[7][4];
    double d;
    memset(fc, 0xEE, 12); memset(out, ' ', sizeof out); memset(sec, 0, 8); memset(l, 0, 4);
    if (!strcmp(svc, "CEEQCEN")) { CEEQCEN(l, fc); hexfc(fc); printf("|%ld\n", (long)((l[0] << 24) | (l[1] << 16) | (l[2] << 8) | l[3])); return 0; }
    if (!strcmp(svc, "CEESCEN")) { /* each argument in turn, then the window read back: the last token and the value */
        unsigned char c[4]; for (int i = 2; i < argc; i++) { i4(c, atol(argv[i])); CEESCEN(c, fc); }
        unsigned char q[4], qfc[12]; CEEQCEN(q, qfc); hexfc(fc); printf("|%ld\n", rd4(q)); return 0; }
    if (!strcmp(svc, "CEEGMTO") || !strcmp(svc, "CEEUTCO")) {
        unsigned char h[4], m[4]; memset(h, 0x55, 4); memset(m, 0x55, 4); memset(sec, 0x55, 8);
        (!strcmp(svc, "CEEGMTO") ? CEEGMTO : CEEUTCO)(h, m, sec, fc); memcpy(&d, sec, 8); hexfc(fc);
        printf("|%ld,%ld,%.3f\n", (long)((h[0] << 24) | (h[1] << 16) | (h[2] << 8) | h[3]),
               (long)((m[0] << 24) | (m[1] << 16) | (m[2] << 8) | m[3]), d); return 0; }
    if (!strcmp(svc, "CEEGMT") || !strcmp(svc, "CEEUTC")) {
        setenv("COB_CURRENT_DATE", argv[2], 1);
        (!strcmp(svc, "CEEGMT") ? CEEGMT : CEEUTC)(l, sec, fc); memcpy(&d, sec, 8);
        hexfc(fc); printf("|%ld,%.3f\n", (long)((l[0] << 24) | (l[1] << 16) | (l[2] << 8) | l[3]), d); return 0; }
    if (!strcmp(svc, "CEEDATE")) { i4(l, atol(argv[2])); vstr(pic, argv[3]); CEEDATE(l, pic, out, fc);
        hexfc(fc); int n = (out[0] << 8) | out[1]; printf("|%.*s\n", n, out + 2); return 0; }
    if (!strcmp(svc, "CEEDATM")) { d = atof(argv[2]); memcpy(sec, &d, 8); vstr(pic, argv[3]); CEEDATM(sec, pic, out, fc);
        hexfc(fc); int n = (out[0] << 8) | out[1]; printf("|%.*s\n", n, out + 2); return 0; }
    if (!strcmp(svc, "CEESECS")) { vstr(in, argv[2]); vstr(pic, argv[3]); memset(sec, 0x55, 8);
        if (argc > 4 && *argv[4]) { unsigned char c[4], cfc[12]; i4(c, atol(argv[4])); CEESCEN(c, cfc); }
        if (argc > 5) setenv("COB_CURRENT_DATE", argv[5], 1);
        CEESECS(in, pic, sec, fc);
        memcpy(&d, sec, 8); hexfc(fc); printf("|%.3f\n", d); return 0; }
    if (!strcmp(svc, "CEEDYWK")) { i4(l, atol(argv[2])); memset(a[0], 0x55, 4); CEEDYWK(l, a[0], fc);
        hexfc(fc); printf("|%ld\n", rd4(a[0])); return 0; }
    if (!strcmp(svc, "CEESECI")) { d = atof(argv[2]); memcpy(sec, &d, 8); for (int i = 0; i < 7; i++) memset(a[i], 0x55, 4);
        CEESECI(sec, a[0], a[1], a[2], a[3], a[4], a[5], a[6], fc); hexfc(fc);
        printf("|%ld,%ld,%ld,%ld,%ld,%ld,0.%03ld\n", rd4(a[0]), rd4(a[1]), rd4(a[2]), rd4(a[3]), rd4(a[4]), rd4(a[5]), rd4(a[6]));
        return 0; }
    for (int i = 0; i < 7; i++) i4(a[i], atol(argv[2 + i]));
    memset(sec, 0x55, 8);
    CEEISEC(a[0], a[1], a[2], a[3], a[4], a[5], a[6], sec, fc); memcpy(&d, sec, 8); hexfc(fc); printf("|%.3f\n", d);
    return 0;
}
"""

JAVA_PROBE = """
import java.io.*;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import p.cobolrt.*;
import p.cobolrt.le.*;

public class Probe {
    static final java.nio.charset.Charset CS = StandardCharsets.ISO_8859_1;
    static Field raw(int n) {
        Storage s = new Storage(n);
        java.util.Arrays.fill(s.bytes, (byte) ' ');
        return Field.alphanumeric(s, 0, n, false);
    }
    static Field vstr(String t) {
        byte[] b = t.getBytes(CS);
        Field f = raw(2 + b.length);
        f.storage().bytes[0] = (byte) (b.length >> 8);
        f.storage().bytes[1] = (byte) b.length;
        System.arraycopy(b, 0, f.storage().bytes, 2, b.length);
        return f;
    }
    static Field i4(long v) {
        Field f = raw(4);
        for (int i = 0; i < 4; i++) f.storage().bytes[i] = (byte) (v >> (24 - 8 * i));
        return f;
    }
    static Field flt() {
        return Field.hfp(new Storage(8), 0, true);
    }
    static int outSize(String[] t) { // the output item's size: an optional last column, a roomy 600 by default
        return t.length > 3 && !t[3].isEmpty() ? Integer.parseInt(t[3]) : 600;
    }
    static String hex(Field fc) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 12; i++) sb.append(String.format("%02X", fc.storage().bytes[i] & 0xff));
        return sb.toString();
    }
    static String text(Field o) {
        int n = ((o.storage().bytes[0] & 0xff) << 8) | (o.storage().bytes[1] & 0xff);
        return new String(o.storage().bytes, 2, n, CS);
    }
    static String secs(Field f) {
        return Cobol.num(f, CS).setScale(3, java.math.RoundingMode.HALF_UP).toPlainString();
    }
    static int lil(Field f) {
        byte[] b = f.storage().bytes;
        return ((b[0] & 0xff) << 24) | ((b[1] & 0xff) << 16) | ((b[2] & 0xff) << 8) | (b[3] & 0xff);
    }
    public static void main(String[] a) throws Exception {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        String line;
        while ((line = in.readLine()) != null) {
            String[] t = line.split("\\\\|", -1);
            Field fc = raw(12);
            java.util.Arrays.fill(fc.storage().bytes, (byte) 0xEE);
            try {
                switch (t[0]) {
                    case "CEEQCEN" -> { Field c = raw(4); Ceeqcen.call(c, fc, CS); System.out.println(hex(fc) + "|" + lil(c)); }
                    case "CEESCEN" -> {
                        for (int i = 1; i < t.length; i++) Ceeqcen.set(i4(Long.parseLong(t[i])), fc, CS);
                        Field q = raw(4); Ceeqcen.call(q, raw(12), CS); System.out.println(hex(fc) + "|" + lil(q));
                        Ceeqcen.set(i4(80), raw(12), CS); // the window is the run's: put the default back for the next row
                    }
                    case "CEEGMTO", "CEEUTCO" -> {
                        Field h = raw(4), m = raw(4), s = flt();
                        java.util.Arrays.fill(h.storage().bytes, (byte) 0x55); java.util.Arrays.fill(m.storage().bytes, (byte) 0x55);
                        Ceegmto.call(h, m, s, fc, CS);
                        System.out.println(hex(fc) + "|" + lil(h) + "," + lil(m) + "," + secs(s));
                    }
                    case "CEEGMT", "CEEUTC" -> {
                        Field l = raw(4), s = flt();
                        if (t[0].equals("CEEGMT")) Ceegmt.call(t[1], l, s, fc, CS); else Ceeutc.call(t[1], l, s, fc, CS);
                        System.out.println(hex(fc) + "|" + lil(l) + "," + secs(s));
                    }
                    case "CEEDATE" -> { Field o = raw(outSize(t)); Ceedate.call(i4(Long.parseLong(t[1])), vstr(t[2]), o, fc, CS);
                        System.out.println(hex(fc) + "|" + text(o)); }
                    case "CEEDATM" -> { Field s = flt(); Cobol.store(s, new BigDecimal(t[1]), false, CS); Field o = raw(outSize(t));
                        Ceedatm.call(s, vstr(t[2]), o, fc, CS); System.out.println(hex(fc) + "|" + text(o)); }
                    case "CEESECS" -> {
                        if (t.length > 3 && !t[3].isEmpty()) Ceeqcen.set(i4(Long.parseLong(t[3])), raw(12), CS);
                        Field s = flt(); Ceesecs.call(t.length > 4 ? t[4] : "", vstr(t[1]), vstr(t[2]), s, fc, CS);
                        System.out.println(hex(fc) + "|" + secs(s));
                        Ceeqcen.set(i4(80), raw(12), CS); // the window is the run's: put the default back for the next row
                    }
                    case "CEEDYWK" -> { Field o = raw(4); Ceedywk.call(i4(Long.parseLong(t[1])), o, fc);
                        System.out.println(hex(fc) + "|" + lil(o)); }
                    case "CEESECI" -> {
                        Field s = flt(); Cobol.store(s, new BigDecimal(t[1]), false, CS);
                        Field[] o = {raw(4), raw(4), raw(4), raw(4), raw(4), raw(4), raw(4)};
                        for (Field f : o) java.util.Arrays.fill(f.storage().bytes, (byte) 0x55);
                        Ceeseci.call(s, o[0], o[1], o[2], o[3], o[4], o[5], o[6], fc, CS);
                        System.out.println(hex(fc) + "|" + lil(o[0]) + "," + lil(o[1]) + "," + lil(o[2]) + "," + lil(o[3]) + ","
                            + lil(o[4]) + "," + lil(o[5]) + "," + String.format("0.%03d", lil(o[6])));
                    }
                    default -> { Field s = flt(); Ceeisec.call(i4(Long.parseLong(t[1])), i4(Long.parseLong(t[2])), i4(Long.parseLong(t[3])),
                        i4(Long.parseLong(t[4])), i4(Long.parseLong(t[5])), i4(Long.parseLong(t[6])), i4(Long.parseLong(t[7])), s, fc, CS);
                        System.out.println(hex(fc) + "|" + secs(s)); }
                }
            } catch (UnsupportedOperationException e) {
                if (!e.getMessage().matches("^[A-Z0-9 /]+: .* is not modelled$")) throw e;
                System.out.println("REFUSED");
            }
        }
    }
}
"""


def _vec_id(v):
    return f"{v[0]}:{'/'.join(v[1])}"


@pytest.fixture(scope="module")
def c_driver(tmp_path_factory):
    if not shutil.which("gcc"):
        pytest.skip("needs a C compiler")
    d = tmp_path_factory.mktemp("le_c")
    (d / "driver.c").write_text(C_DRIVER, newline="\n")
    run = subprocess.run(  # noqa: S603
        ["gcc", "-O0", "-o", str(d / "t"), str(d / "driver.c"), str(LE_C), "-lm"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    return d / "t"


def _bare_env() -> dict[str, str]:
    """An environment with no clock pinned. Windows will not start a process from an empty one, so it keeps SYSTEMROOT."""
    return {k: os.environ[k] for k in ("SYSTEMROOT",) if k in os.environ} if os.name == "nt" else {}


def _run_c(exe: Path, svc: str, args: list[str], sizes: str | None = None) -> str:
    env = {**_bare_env(), **({"GG_LE_OUT_SIZES": sizes} if sizes is not None else {})}
    run = subprocess.run([str(exe), svc, *args], capture_output=True, text=True, check=False, env=env)  # noqa: S603
    if run.returncode == 98:
        assert run.stderr.rstrip().endswith("is not modelled"), run.stderr
        return REFUSED
    assert run.returncode == 0, run.stderr
    return run.stdout.rstrip("\n")


@pytest.mark.parametrize("svc, args, want", VECTORS, ids=[_vec_id(v) for v in VECTORS])
def test_the_oracle_model_gives_ibms_answers(c_driver, svc, args, want):
    row = _run_c(c_driver, svc, args)
    _check_want(row, want)


def _java_line(svc: str, args: list[str]) -> str:
    if svc == "CEESECS" and len(args) > 2:  # timestamp, picture, the CEESCEN value, the clock as CURRENT-DATE text
        return "|".join([svc, args[0], args[1], args[2], re.sub("[/: .]", "", args[3]) + "+0000"])
    if svc in ("CEEGMT", "CEEUTC"):
        return f"{svc}|{re.sub('[/: .]', '', args[0])}+0000"  # the run's CURRENT-DATE text
    return "|".join([svc, *args])


@pytest.fixture(scope="module")
def java_probe(tmp_path_factory):
    """A function feeding the probe's rows (one per line) to the compiled runtime and returning its output lines."""
    jdk = _jdk()
    if jdk is None:
        pytest.skip("needs a JDK 17 (JAVA_HOME / JDK_17)")
    tmp_path = tmp_path_factory.mktemp("le_java")
    out = tmp_path / "src/p/cobolrt"
    (out / "le").mkdir(parents=True)
    for f in RT.glob("*.java"):
        (out / f.name).write_text(f.read_text(encoding="utf-8").replace("__PACKAGE__", "p"), encoding="utf-8")
    for f in (RT / "le").glob("*.java"):
        (out / "le" / f.name).write_text(f.read_text(encoding="utf-8").replace("__PACKAGE__", "p"), encoding="utf-8")
    (tmp_path / "src/Probe.java").write_text(JAVA_PROBE)
    files = [str(f) for f in (tmp_path / "src").rglob("*.java")]
    javac_run(
        [str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"), *files], check=True
    )  # noqa: S603

    def run(rows: list[str]) -> list[str]:
        return subprocess.run(  # noqa: S603
            [
                str(jdk / "java"),
                "-Dfile.encoding=UTF-8",
                "-Dstdout.encoding=UTF-8",
                "-cp",
                str(tmp_path / "classes"),
                "Probe",
            ],
            input="\n".join(rows) + "\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout.splitlines()

    return run


@pytest.mark.slow(reason="translates, javac-compiles and runs a program per case (#5178, #5606)")
def test_the_runtime_is_the_oracle_model_byte_for_byte(c_driver, java_probe):
    got = java_probe([_java_line(s, a) for s, a, _ in VECTORS])
    assert len(got) == len(VECTORS)
    bad = []
    for (svc, args, want), java in zip(VECTORS, got, strict=True):
        c = _run_c(c_driver, svc, args)
        same = (java == c) if REFUSED in (java, c) else (_norm_row(java) == _norm_row(c))
        if not same:
            bad.append(f"{svc} {args}\n  java {java}\n  c    {c}")
        _check_want(java, want)
    assert not bad, "\n".join(bad)


def _norm_row(row: str) -> str:
    fc, _, value = row.partition("|")
    return f"{fc}|{_norm(value)}" if value and value[0] in "0123456789-" and ("." in value or "," in value) else row


def test_the_offset_services_take_no_clock():
    """The offset is a constant of the model (GMT, +0000), so neither name reads the run's clock (#5003)."""
    assert not {"CEEGMTO", "CEEUTCO"} & G.LIBRARY_CLOCK
    assert G.LIBRARY["CEEGMTO"][0] == G.LIBRARY["CEEUTCO"][0]


def test_the_zero_offset_is_the_clocks_offset():
    """The time-zone decision (#5003, register L6 assumption 6): CEEGMTO answers zero because the det runtime's clock is
    GMT (FUNCTION CURRENT-DATE ends in +0000). Both are read from source, so a zoned clock cannot land without the
    offset service being revisited; the vectors above prove the zero on both sides."""
    funcs = (RT / "Funcs.java").read_text(encoding="utf-8")
    body = funcs.split("public static String currentDate", 1)[1].split("}", 1)[0]
    assert re.findall(r'"([+-]\d{4})"', body) == ["+0000"]
    ceegmto = (RT / "le" / "Ceegmto.java").read_text(encoding="utf-8")
    assert "putInt(hours, 0)" in ceegmto and "putInt(minutes, 0)" in ceegmto and "BigDecimal.ZERO" in ceegmto
    assert [v[2] for v in VECTORS if v[0] in ("CEEGMTO", "CEEUTCO")] == ["0|0,0,0.000"] * 2


def test_the_clock_services_refuse_without_a_pinned_clock(c_driver):
    run = subprocess.run([str(c_driver), "CEEGMT", ""], capture_output=True, text=True, check=False, env=_bare_env())  # noqa: S603
    assert run.returncode == 98 and run.stderr.rstrip().endswith("is not modelled")


def test_a_century_window_without_a_pinned_clock_is_refused(c_driver):
    """A YY needs the system year; the model has no host clock to fall back on (like CEEGMT), so it refuses by name."""
    assert _run_c(c_driver, "CEESECS", ["88-05-16", "YY-MM-DD"]) == REFUSED
    # no YY, no clock needed
    assert _run_c(c_driver, "CEESECS", ["1988-05-16", "YYYY-MM-DD"]) == f"{_hex_fc(0)}|{148138 * 86400}.000"


# ---- 3. the translator's wiring ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prog, args",
    [
        ("CEEGMT", 3),
        ("CEEUTC", 3),
        ("CEEDATM", 4),
        ("CEESECS", 4),
        ("CEEDATE", 4),
        ("CEEISEC", 9),
        ("CEESECI", 9),
        ("CEEDYWK", 3),
        ("CEEQCEN", 2),
        ("CEESCEN", 2),
        ("CEEGMTO", 4),
        ("CEEUTCO", 4),
    ],
)
def test_every_service_is_a_library_routine_with_its_arity(prog, args):
    # CEEUTCO is CEEGMTO's service, as CEEUTC is CEEGMT's; CEESCEN is CEEQCEN's class (one setting), its set entry
    cls = {"CEEUTCO": "Ceegmto", "CEESCEN": "Ceeqcen"}.get(prog, prog.title())
    assert G.LIBRARY[prog][1] == args
    assert G.LIBRARY[prog][0].endswith(f".{cls}.{'set' if prog == 'CEESCEN' else 'call'}")
    assert (RT / "le" / f"{cls}.java").is_file()
    assert (prog in G.LIBRARY_CHARSET) == (prog != "CEEDYWK")  # CEEDYWK has no float, so it takes no charset


def test_ceescen_is_the_set_entry_of_the_ceeqcen_class():
    """CEESCEN shares CEEQCEN's class (the window is one setting); the translator calls its set entry, charset last."""
    assert "public static void set(Field century, Field fc, Charset cs)" in (RT / "le/Ceeqcen.java").read_text()
    assert G.LIBRARY["CEESCEN"][0] == "__PACKAGE__.cobolrt.le.Ceeqcen.set"
    assert "CEESCEN" in G.LIBRARY_CHARSET and "CEESCEN" not in G.LIBRARY_FLOATS


def test_a_ceescen_call_translates_to_the_set_entry_with_the_charset_last(tmp_path):
    src = tmp_path / "SC.cbl"
    src.write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. SC.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
        "       01 CENT PIC S9(9) BINARY.\n       01 FC PIC X(12).\n       PROCEDURE DIVISION.\n"
        "           CALL 'CEESCEN' USING CENT, FC.\n           CALL 'CEEQCEN' USING CENT, FC.\n           GOBACK.\n"
    )
    from gitgalaxy.tools.cobol_to_java.det.program import translate

    out = str(translate(src, [], "package pk;\npublic class SC {\n}\n", "pk").__dict__)
    assert "pk.cobolrt.le.Ceeqcen.set(f1_CENT, f2_FC, CS);" in out
    assert "pk.cobolrt.le.Ceeqcen.call(f1_CENT, f2_FC, CS);" in out


def test_a_ceesecs_call_takes_the_run_clock_first_for_its_century_window(tmp_path):
    assert "CEESECS" in G.LIBRARY_CLOCK
    src = tmp_path / "SE.cbl"
    src.write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. SE.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
        "       01 TS PIC X(8).\n       01 PIC1 PIC X(8).\n       01 SECS COMP-2.\n       01 FC PIC X(12).\n"
        "       PROCEDURE DIVISION.\n           CALL 'CEESECS' USING TS, PIC1, SECS, FC.\n           GOBACK.\n"
    )
    from gitgalaxy.tools.cobol_to_java.det.program import translate

    out = str(translate(src, [], "package pk;\npublic class SE {\n}\n", "pk").__dict__)
    assert "pk.cobolrt.le.Ceesecs.call(clock.currentDate(), f1_TS, f2_PIC1, f3_SECS, f4_FC, CS);" in out


def test_the_comp2_arguments_are_by_value_and_the_clock_services_take_the_clock():
    assert G.LIBRARY_FLOATS == {
        "CEELOCT": {1}, "CEEGMT": {1}, "CEEUTC": {1}, "CEEDATM": {0}, "CEESECS": {2}, "CEEISEC": {7}, "CEESECI": {0},
        "CEEGMTO": {2}, "CEEUTCO": {2},
    }  # fmt: skip
    assert G.LIBRARY_CLOCK == {"CEELOCT", "CEEGMT", "CEEUTC", "CEESECS"}


def test_every_vector_service_is_covered_and_every_service_has_vectors():
    assert {v[0] for v in VECTORS} == {
        "CEEGMT", "CEEUTC", "CEEQCEN", "CEEDATE", "CEEDATM", "CEESECS", "CEEISEC", "CEEGMTO", "CEEUTCO",
        "CEESECI", "CEEDYWK", "CEESCEN",
    }  # fmt: skip
    # CEESECI / CEEDYWK take no picture and no field combination, so there is nothing to refuse by name
    for svc in {v[0] for v in VECTORS} - {
        "CEEUTC",
        "CEEQCEN",
        "CEEGMT",
        "CEEGMTO",
        "CEEUTCO",
        "CEESECI",
        "CEEDYWK",
        "CEESCEN",
    }:
        mine = [v for v in VECTORS if v[0] == svc]
        assert any(v[2] and v[2].startswith("0|") for v in mine), svc  # a valid call
        assert any(v[2] == REFUSED for v in mine), svc  # a refusal by name
        assert any(v[2] and not v[2].startswith("0|") and v[2] != REFUSED for v in mine), svc  # a condition code


def test_ceeseci_is_the_inverse_of_ceeisec(c_driver):
    """Every CEEISEC row that succeeds, fed back through CEESECI, gives the fields it was made from."""
    n = 0
    for svc, args, want in VECTORS:
        if svc != "CEEISEC" or not want or not want.startswith("0|") or args[6] != "0":
            continue  # a fraction such as .12 is not exact in binary: the millisecond floor can differ by one
        seconds = _run_c(c_driver, svc, args).split("|", 1)[1]
        back = _run_c(c_driver, "CEESECI", [seconds]).split("|", 1)[1]
        y, mo, d, h, mi, sec, ms = args
        assert back == f"{y},{mo},{d},{h},{mi},{sec},0.{int(ms):03d}", (args, seconds, back)
        n += 1
    assert n >= 3


# CEE2526 / CEE2527 (#5003 [c:a06ff706]): IBM cuts a result longer than its output item. The C model is handed a bare
# pointer and cannot see the item's end, so only the Java runtime knows the size: it refuses a VSTRING item shorter than
# its halfword length plus the text (2 + the result) rather than cut it, and writes it whole at exactly that size.
# (service, the input, the picture, the result's length)
SHORT_OUTPUT = [
    ("CEEDATE", "148138", "YYYYMMDD", 8),
    ("CEEDATE", "148141", "YYYY.DDD", 8),
    ("CEEDATE", "148142", "YY/MM/DD HH:MI:SS.99", 20),
    ("CEEDATM", "13312800000.000", "YYYYMMDDHHMISS", 14),
    ("CEEDATM", "13312800000.000", "YYYY-MM-DD HH:MI:SS.999", 23),
]


@pytest.mark.slow(reason="javac-compiles and runs the probe (#5178)")
@pytest.mark.parametrize("svc, value, pic, n", SHORT_OUTPUT, ids=[f"{v[0]}:{v[2]}" for v in SHORT_OUTPUT])
def test_the_runtime_refuses_an_output_item_shorter_than_the_result_and_fills_one_that_fits(
    java_probe, svc, value, pic, n
):
    sizes = [2 + n - 1, 2 + n, 2 + n + 1]
    rows = java_probe([f"{svc}|{value}|{pic}|{k}" for k in sizes])
    assert rows[0] == REFUSED, f"a {sizes[0]}-byte output cannot hold {2 + n} bytes: refuse, never truncate"
    for row in rows[1:]:
        fc, text = row.split("|")
        assert fc == "0" * 24 and len(text) == n, row  # a zero feedback token and the whole result


@pytest.mark.parametrize("svc, value, pic, n", SHORT_OUTPUT, ids=[f"{v[0]}:{v[2]}" for v in SHORT_OUTPUT])
def test_the_oracle_refuses_a_stated_output_size_shorter_than_the_result_and_fills_one_that_fits(
    c_driver, java_probe, svc, value, pic, n
):
    """The C model of #5003 [c:a06ff706]: the size comes from the harness (GG_LE_OUT_SIZES), as the Java item's does."""
    sizes = [2 + n - 1, 2 + n, 2 + n + 1]
    java = java_probe([f"{svc}|{value}|{pic}|{k}" for k in sizes])
    for k, want in zip(sizes, java, strict=True):
        got = _run_c(c_driver, svc, [value, pic], sizes=f"{svc}={k}")
        if want == REFUSED:
            assert got == REFUSED, (k, got)
        else:
            assert got == "0" * 24 + "|" + want.split("|")[1], (k, got, want)
    assert _run_c(c_driver, svc, [value, pic], sizes=f"{svc}={2 + n - 1}") == REFUSED
    assert _run_c(c_driver, svc, [value, pic], sizes=f"{svc}={2 + n}") != REFUSED
    other = "CEEDATM" if svc == "CEEDATE" else "CEEDATE"
    assert (
        _run_c(c_driver, svc, [value, pic], sizes=f"{other}=1") != REFUSED
    )  # another service's size is not this one's
    assert _run_c(c_driver, svc, [value, pic]) != REFUSED  # no size stated: as before


def _src(*lines: str) -> str:
    """Fixed-format source: each line in columns 8-72."""
    return "".join("       " + ln + "\n" for ln in lines)


def test_the_harness_states_the_declared_output_size_of_each_call():
    src = _src(
        "01  WS-DATE.",
        "    05  DATM-LEN      PIC S9(4) COMP.",
        "    05  DATM-CONV     PIC X(80).",
        "01  SMALL-OUT         PIC X(12).",
        "01  GRP.",
        "    05  A             PIC X(10).",
        "    05  B             PIC XX.",
        "PROCEDURE DIVISION.",
        "    CALL 'CEEDATM' USING SECS, PIC, DATM-CONV, FC.",
        "    CALL 'CEEDATE' USING BY REFERENCE LIL BY REFERENCE PIC",
        "         BY REFERENCE GRP BY REFERENCE FC.",
        "    CALL 'CEEDATE' USING LIL, PIC, SMALL-OUT, FC.",
    )
    assert le_out_size.output_sizes(src) == {"CEEDATM": 80, "CEEDATE": 12}  # the smallest of a service's calls
    assert le_out_size.env(src) == "GG_LE_OUT_SIZES=CEEDATE=12,CEEDATM=80 "


@pytest.mark.parametrize(
    "decl",
    [
        ["01  OUT-A REDEFINES OTHER PIC X(80)."],
        ["01  OUT-A PIC X(80) OCCURS 3."],
        ["01  OUT-A PIC S9(4) COMP."],
        ["01  OUT-A PIC X(80).", "01  OUT-A PIC X(4)."],  # declared twice
        ["01  OUT-A.", "    05  BODY PIC X(80).", "    05  MORE PIC X(4) OCCURS 2."],  # a group with an unsized child
        [],  # a COPY member or LINKAGE item the source does not declare
    ],
    ids=["redefines", "occurs", "comp", "twice", "group-with-occurs", "undeclared"],
)
def test_the_harness_states_no_size_it_cannot_state_exactly(decl):
    src = _src(*decl, "PROCEDURE DIVISION.", "    CALL 'CEEDATM' USING SECS, PIC, OUT-A, FC.")
    assert le_out_size.output_sizes(src) == {}
    assert le_out_size.env(src) == ""
