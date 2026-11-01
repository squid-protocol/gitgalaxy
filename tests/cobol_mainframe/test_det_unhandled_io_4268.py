"""#4268: a READ / WRITE / REWRITE that fails on a file with no FILE STATUS and no phrase for that condition is a
run-time error on IBM; the det port stops by name instead of carrying on (the oracle ends RETURN-CODE 1, the port had
ended 0). Translation only (no GnuCOBOL, no javac)."""

from __future__ import annotations

import pytest

PKG = "p"


def _program(proc: list[str], status: bool) -> str:
    lines = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. UNHIO.", "       ENVIRONMENT DIVISION.",
             "       INPUT-OUTPUT SECTION.", "       FILE-CONTROL.", "           SELECT IO-FILE ASSIGN TO IODD",
             "               ORGANIZATION IS SEQUENTIAL" + ("" if status else "."),
             *(["               FILE STATUS WS-ST."] if status else []),
             "       DATA DIVISION.", "       FILE SECTION.", "       FD  IO-FILE.", "       01  IO-REC PIC X(10).",
             "       WORKING-STORAGE SECTION.", "       77  WS-ST PIC XX.", "       PROCEDURE DIVISION."]  # fmt: skip
    return "\n".join(lines + [f"           {x}" for x in proc] + ["           GOBACK."]) + "\n"


def _java(tmp_path, source: str) -> str:
    pytest.importorskip("tree_sitter_language_pack")  # the translator's parser (not in every CI job)
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "UNHIO.cbl").write_text(source)
    r = P.translate(tmp_path / "UNHIO.cbl", [], "public class UnhioService {\n}\n", PKG)
    assert not r.stats["holes"], r.stats["holes"]
    return r.java


def _checks(java: str) -> list[str]:
    return [ln.strip() for ln in java.splitlines() if "with no FILE STATUS" in ln]


@pytest.mark.parametrize(("stmt", "verb", "ok"), [
    ("WRITE IO-REC.", "WRITE", []),
    ("REWRITE IO-REC.", "REWRITE", []),
    ("READ IO-FILE.", "READ", ['"10"']),
    ("READ IO-FILE AT END DISPLAY 'E' END-READ.", "READ", ['"10"']),
])  # fmt: skip
def test_a_failing_io_without_a_file_status_stops_by_name(tmp_path, stmt, verb, ok):
    checks = _checks(_java(tmp_path, _program([stmt], status=False)))
    assert len(checks) == 1
    assert f"{verb} IO-FILE: FILE STATUS " in checks[0] and "IBM abends" in checks[0]
    for code in ok:
        assert f".equals({code})" in checks[0]
    assert checks[0].count(".equals(") == len(ok)  # no other status is waved through


def test_an_invalid_key_phrase_handles_its_own_statuses_only(tmp_path):
    java = _java(tmp_path, _program(["WRITE IO-REC INVALID KEY DISPLAY 'K' END-WRITE."], False))
    (check,) = _checks(java)
    assert [c for c in ("21", "22", "23", "24") if f'.equals("{c}")' in check] == ["21", "22", "23", "24"]


def test_a_file_status_or_a_plain_clean_write_gets_no_check(tmp_path):
    assert _checks(_java(tmp_path, _program(["WRITE IO-REC.", "READ IO-FILE."], status=True))) == []
