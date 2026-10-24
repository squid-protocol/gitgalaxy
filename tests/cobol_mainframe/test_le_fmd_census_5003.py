"""#5003 (register L6), checklist [c:075d47cd]: CEEFMDA / CEEFMDT / CEEFMDV (country-default date, time and separator
formats) stay refused by name, because no burned program calls them. This census pins that, and the same for the two
other unmodelled members of the class: a null (default) picture on CEEDATE / CEEDATM / CEESECS, and an output item
shorter than the picture's result (CEE2526 / CEE2527). A burned program that starts to need one must fail here first.

The only LE date-format caller in the burned estates is CBSA BANKDATA: CEEDATM with a 14-byte picture
(`MOVE 14 TO datm-length`, 'YYYYMMDDHHMISS') into an 80-byte output."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.core.source_text import read_source  # noqa: E402

CORPORA = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
BURNED = ["aws-mainframe-modernization-carddemo", "cics-banking-sample-application-cbsa", "cics-genapp",
          "dbb-mortgage-application", "zecs", "cics-async-api-credit-card-application-example"]  # fmt: skip
EXTS = {".cbl", ".cob", ".cpy", ".jcl", ".asm", ".mac"}
BANKDATA = "cics-banking-sample-application-cbsa/src/base/cobol_src/BANKDATA.cbl"
FMD = ("CEEFMDA", "CEEFMDT", "CEEFMDV")
# the date-format services: the picture is the second argument of each (CEEDATE lilian, pic, out; CEEDATM secs, pic, out;
# CEESECS timestamp, pic, secs)
FORMAT_CALL = re.compile(r"CALL\s+['\"](CEEDATE|CEEDATM|CEESECS)['\"]\s+USING\b(.*?)(?:\.|END-CALL|\n\s*\n)", re.S)


def _code(text: str) -> str:
    """Source with its comment lines dropped (column 7 of COBOL, column 1 of assembler)."""
    return "\n".join(ln for ln in text.splitlines() if ln[:1] != "*" and not (len(ln) > 6 and ln[6] in "*/")).upper()


def _sources():
    for name in BURNED:
        for p in sorted((CORPORA / name).rglob("*")):
            if p.is_file() and p.suffix.lower() in EXTS:
                yield p, _code(read_source(p).text)


@pytest.fixture(scope="module")
def census():
    if not (CORPORA / BANKDATA).is_file():
        pytest.skip("the burned corpora are not checked out (GITGALAXY_MAINFRAME_CORPORA)")
    return list(_sources())


def _args(body: str) -> list[str]:
    """The USING arguments of a call, BY REFERENCE / BY CONTENT / BY VALUE dropped."""
    return [
        re.sub(r"^BY\s+(?:REFERENCE|CONTENT|VALUE)\s+", "", a.strip())
        for a in re.split(r"\s*,\s*|\s+(?=BY\s)", body.strip())
    ]


@pytest.mark.parametrize("service", FMD)
def test_no_burned_source_calls_a_country_default_format_service(census, service):
    hits = [p.name for p, text in census if service in text]
    assert hits == [], (
        f"{service} is now used by a burned program ({hits}): model it (register L6), then drop its refusal"
    )


def test_the_only_date_format_caller_is_bankdata_with_a_named_picture_and_an_80_byte_output(census):
    calls = [(p.name, m.group(1), _args(m.group(2))) for p, text in census for m in FORMAT_CALL.finditer(text)]
    assert [(n, s) for n, s, _ in calls] == [("BANKDATA.cbl", "CEEDATM")], calls
    pic = calls[0][2][1]
    assert pic not in {"OMITTED", "NULL", "NULLS", "ZERO", "ZEROS", "SPACE", "SPACES"}, "a null (default) picture"
    text = dict((p.name, t) for p, t in census)["BANKDATA.cbl"]
    assert re.search(r"MOVE 14\s+TO DATM-LENGTH", text) and re.search(r"MOVE 'YYYYMMDDHHMISS' TO DATM-FORMAT", text)
    assert re.search(r"05 DATM-CONV\s+PIC X\(80\)", text), (
        "the output is no longer 80 bytes: CEE2526 / CEE2527 is in reach"
    )
    assert re.search(r"10 DATM-FORMAT\s+PIC X\(14\)", text)  # the picture is 14 bytes, the result 14: no truncation


@pytest.mark.parametrize("service", FMD)
def test_the_translator_refuses_each_country_default_format_service_by_name(service, tmp_path):
    """Not a library routine, so the CALL is a hole that names it (never a silent no-op or a guessed answer)."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import gen as G
    from gitgalaxy.tools.cobol_to_java.det.program import translate

    assert service not in G.LIBRARY, f"{service} is modelled now: add its vectors and drop this census row"
    src = tmp_path / "FM.cbl"
    src.write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FM.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
        "       01 A PIC X(8).\n       01 FC PIC X(12).\n       PROCEDURE DIVISION.\n"
        f"           CALL '{service}' USING A, FC.\n           GOBACK.\n"
    )
    stats = translate(src, [], "package pk;\npublic class FM {\n}\n", "pk").stats
    assert len(stats["holes"]) == 1 and service in stats["holes"][0], stats["holes"]
