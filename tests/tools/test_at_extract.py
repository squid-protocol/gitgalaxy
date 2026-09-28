"""#3806: at_extract turns a GNU Autotest suite into one directory per test case, the way autom4te reads it."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import at_extract

# a Shift-JIS suite: 表 is 0x95 0x5C and ソ is 0x83 0x5C -- a trail byte that is ASCII '\'
_SJIS_NAME = "表ソ日本語".encode("shift_jis")

_TOP = b"""AT_INIT([Synthetic])
# m4_include([commented-out.at]) -- a comment, never followed
m4_include([cases.at])
"""

_CASES = (
    b"""AT_SETUP([Two programs, nested quotes])
AT_KEYWORDS([call sub])
AT_SKIP_IF([test -n "$IS_WINDOWS"])
dnl AT_CHECK([never run])
AT_DATA([prog.cob], [
       PROGRAM-ID. prog.
       01 T PIC X(3) VALUE "@<:@1@:>@".
       01 U PIC X(4) VALUE "[[x]]" [y].
       CALL "sub" USING T, U.
])
AT_DATA([sub.cob], [
       PROGRAM-ID. sub.
])
AT_CHECK([${COBJ} prog.cob sub.cob])
#AT_CHECK([java old], [0], [gone])
AT_CHECK([java prog], [0], [@<:@1@:>@ x (y), @S|@
keep\x20\x20@&t@
drop\x20\x20\x20
])
AT_CLEANUP

AT_SETUP([Negative compile])
AT_DATA([prog.cob], [
       PROGRAM-ID. prog.
])
AT_CHECK([${COMPILE} prog.cob], [1], [],
[prog.cob:2: Error: syntax error
])
AT_CHECK([java prog], [ignore], [ignore])
AT_DATA([prog.cob], [second version
])
AT_CLEANUP

AT_SETUP([Japanese """
    + _SJIS_NAME
    + b"""])
AT_DATA([prog.cob], [
       01 """
    + _SJIS_NAME
    + b""" PIC N(5).
])
AT_CHECK([java prog], [0], ["""
    + _SJIS_NAME
    + b"""])
AT_CLEANUP
"""
)


def _suite(tmp: Path) -> tuple[Path, Path]:
    src = tmp / "src"
    (src / "t.src").mkdir(parents=True)
    (src / "t.at").write_bytes(_TOP)
    (src / "t.src" / "cases.at").write_bytes(_CASES)
    return src / "t.at", src / "t.src"


def test_extracts_cases_files_and_expected_output(tmp_path: Path) -> None:
    at, inc = _suite(tmp_path)
    manifest = at_extract.extract("t", at, [inc], "shift_jis", tmp_path / "out", {"commit": "abc"})
    assert [c["case"] for c in manifest["cases"]] == ["001-two-programs-nested-quotes", "002-negative-compile",
                                                      "003-japanese"]  # fmt: skip
    assert manifest["commit"] == "abc"
    root = tmp_path / "out" / "t"

    one = json.loads((root / "001-two-programs-nested-quotes" / "expected.json").read_text(encoding="utf-8"))
    assert one["keywords"] == ["call", "sub"]
    assert one["encoding"] == "ascii"
    kinds = [s["kind"] for s in one["steps"]]
    assert kinds == ["skip_if", "data", "data", "check", "check"]  # dnl / # lines are not steps
    assert one["steps"][0]["condition"] == 'test -n "$IS_WINDOWS"'
    prog = (root / "001-two-programs-nested-quotes" / "prog.cob").read_bytes()
    # quadrigraphs become brackets; inside the quoted argument, AT_DATA's rescan strips one more level
    # (autom4te 2.71 writes `"[x]" y` for `"[[x]]" [y]`)
    assert b'VALUE "[1]".' in prog and b'VALUE "[x]" y.' in prog
    assert prog.startswith(b"\n       PROGRAM-ID. prog.\n")
    assert (root / "001-two-programs-nested-quotes" / "sub.cob").is_file()
    run = one["steps"][4]
    assert run["command"] == "java prog" and run["status"] == 0
    # trailing blanks go (as autom4te writes the testsuite) unless @&t@ protects them
    assert run["stdout"] == {"mode": "exact", "text": "[1] x (y), $\nkeep  \ndrop\n"}
    assert run["stderr"] == {"mode": "exact", "text": ""}  # omitted: must be empty

    two = json.loads((root / "002-negative-compile" / "expected.json").read_text(encoding="utf-8"))
    compile_step = two["steps"][1]
    assert compile_step["status"] == 1
    assert compile_step["stderr"]["text"] == "prog.cob:2: Error: syntax error\n"
    assert two["steps"][2]["status"] == "ignore" and two["steps"][2]["stdout"] == {"mode": "ignore"}
    # the same file written twice: the later version is kept beside the first, not over it
    assert [f["path"] for f in two["files"]] == ["prog.cob", "v2/prog.cob"]
    assert (root / "002-negative-compile" / "v2" / "prog.cob").read_bytes() == b"second version\n"


def test_shift_jis_bytes_are_kept_raw_and_verified(tmp_path: Path) -> None:
    at, inc = _suite(tmp_path)
    at_extract.extract("t", at, [inc], "shift_jis", tmp_path / "out")
    case = tmp_path / "out" / "t" / "003-japanese"
    rec = json.loads((case / "expected.json").read_text(encoding="utf-8"))
    assert rec["encoding"] == "shift_jis" and rec["encoding_error"] == []
    assert rec["name"] == "Japanese 表ソ日本語"
    assert _SJIS_NAME in (case / "prog.cob").read_bytes()  # never decoded and re-encoded
    out = rec["steps"][1]["stdout"]
    assert out["text"] == "表ソ日本語" and base64.b64decode(out["b64"]) == _SJIS_NAME


def test_a_wrong_declared_encoding_is_reported_not_replaced(tmp_path: Path) -> None:
    at, inc = _suite(tmp_path)
    manifest = at_extract.extract("t", at, [inc], "utf-8", tmp_path / "out")
    bad = {c["case"]: c["encoding_error"] for c in manifest["cases"] if c["encoding_error"]}
    assert list(bad) == ["003-japanese"]
    assert (tmp_path / "out" / "t" / "003-japanese" / "prog.cob").read_bytes().count(_SJIS_NAME) == 1


def test_m4_argument_collection() -> None:
    args, end = at_extract._collect_args(b"[a, b], (c, d) [e]f, [x]) tail", 0)
    assert args == [b"a, b", b"(c, d) ef", b"x"]
    assert end == len(b"[a, b], (c, d) [e]f, [x])")
