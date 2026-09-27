"""#3814 / #3810: mainframe names carry national letters.

On national EBCDIC code pages the bytes behind `$ # @` display as `Å Æ Ø` (cp277), `Å Ä Ö` (cp278),
`§` (cp273), `Ñ` (cp284), `£` (cp285 / cp297) ... so exported JCL, CSD, HLASM, COBOL and BMS names
carry them. Each channel must read such a name whole -- and every letter class in the mainframe
readers must splice in identifiers.NATIONAL, so a new rule cannot quietly drop them again.
"""

import re
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

ROOT = Path(__file__).resolve().parents[2]
READERS = [
    *(f"gitgalaxy/standards/language_standards/languages/{n}.py" for n in ("jcl", "cobol", "hlasm", "bms", "csd")),
    *(f"gitgalaxy/core/{n}.py" for n in ("mainframe_boundary", "job_flow", "file_control")),
]


def _code(rel: str) -> str:
    """The file without its comment lines (a comment may quote an old, ASCII-only class)."""
    lines = (ROOT / rel).read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def test_every_mainframe_letter_class_accepts_the_national_letters():
    missing = [
        f"{rel}: {m.group(0)}"
        for rel in READERS
        for m in re.finditer(r"\[(?!\^)[^\]\[]*A-Z[^\]\[]*\]", _code(rel))
        if not re.search(r'"\s*\+\s*NATIONAL\s*\+\s*r"', m.group(0))  # the class splices the constant in
    ]
    assert not missing, "\n".join(missing)


def test_jcl_job_step_program_and_dataset_are_whole():
    out = extract_boundary(
        "jcl",
        "//ØKJOBB   JOB (ACCT),'X'\n//ÆSTEG1   EXEC PGM=ØKONOMI\n//INN      DD DSN=PROD.ÅRSOPPGJØR(+1),DISP=SHR\n",
    )
    assert [c["target"] for c in out["calls"]] == ["ØKONOMI"]
    assert [(d["step_name"], d["dsn"]) for d in out["datasets"]] == [("ÆSTEG1", "PROD.ÅRSOPPGJØR(+1)")]
    flow = {(f["kind"], f["name"] or f["step_name"] or f["dd_name"]) for f in out["job_flow"]}
    assert {("JOB", "ØKJOBB"), ("STEP", "ÆSTEG1"), ("DD", "ÆSTEG1")} <= flow


def test_a_csd_resource_and_its_dataset_are_whole():
    (res,) = extract_boundary("csd", "DEFINE FILE(KUNDÆR) GROUP(ØKGRP) DSNAME(PROD.KUNDEØ.DATA)\n")["csd_resources"]
    assert (res["name"], res["group"], res["dsname"]) == ("KUNDÆR", "ØKGRP", "PROD.KUNDEØ.DATA")


def test_cobol_calls_and_data_items_are_whole():
    src = (
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. RÄKNA.\n       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n       01  WS-HÄLSNING    PIC X(10).\n       PROCEDURE DIVISION.\n"
        "       100-RÄKNA.\n           CALL 'ØKONOMI' USING WS-HÄLSNING.\n"
    )
    out = extract_boundary("cobol", src)
    assert [c["target"] for c in out["calls"]] == ["ØKONOMI"]
    assert [r["name"] for r in out["records"]] == ["WS-HÄLSNING"]


def _units(lang: str, code: str) -> list[str]:
    streams = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams(code, lang)
    out = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(
        code_stream=streams["code_stream"], comment_stream=streams["comment_stream"], confidence=1.0
    )
    return [f["name"] for f in out["functions"]]


@pytest.mark.parametrize(
    "lang, code, name",
    [
        ("hlasm", "ØKASM    CSECT\n         BR    14\n         END\n", "ØKASM"),
        ("hlasm", "§PRUF    CSECT\n         BR    14\n         END\n", "§PRUF"),  # cp273's national `@`
        ("cobol", "       PROCEDURE DIVISION.\n       100-RÄKNA.\n           STOP RUN.\n", "100-RÄKNA"),
        ("jcl", "//ØKJOBB   JOB (ACCT)\n//ÆSTEG1   EXEC PGM=ØKONOMI\n", "ÆSTEG1"),
    ],
)
def test_a_national_unit_is_found_whole(lang, code, name):
    assert name in _units(lang, code)
