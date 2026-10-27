"""#5233: the DL/I unit-of-work calls (SCHD / TERM / CHKP / XRST / ROLB / SYNC) the burned CardDemo IMS programs issue.
The programs use SCHD, TERM and CHKP only (all translated and run on both runtimes); XRST, ROLB and SYNC are issued by
no burned program, so they stay refused by name, and this pins both facts (a later program or a dropped refusal fails)."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from gitgalaxy.core.source_text import read_source

ROOT = Path(__file__).resolve().parents[2]
APP = "app/app-authorization-ims-db2-mq/cbl"
PROGRAMS = ["CBPAUP0C", "COPAUA0C", "COPAUS0C", "COPAUS1C", "COPAUS2C", "PAUDBUNL", "PAUDBLOD", "DBUNLDGS"]
UOW = {"SCHD", "TERM", "CHKP", "XRST", "ROLB", "ROLL", "ROLS", "SYNC"}
RUNTIME = ROOT / "gitgalaxy/tools/cobol_to_java/det/cobolrt/dli/DetDli.java"
ORACLE = ROOT / "tests/equivalence/ims/ggdli.c"
UNUSED = ("XRST", "ROLB", "ROLL", "ROLS", "SYNC")


def _source(name: str) -> str | None:
    corpora = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    for ext in ("cbl", "CBL"):
        path = corpora / "aws-mainframe-modernization-carddemo" / APP / f"{name}.{ext}"
        if path.is_file():
            return read_source(path).text
    return None


def _uow_verbs(text: str) -> set[str]:
    """The unit-of-work verbs a program issues: EXEC DLI <verb>, or a CBLTDLI function-code literal / FUNC- constant."""
    lines = [ln[6:72] for ln in text.splitlines() if len(ln) > 6 and ln[6] not in "*/"]
    code = "\n".join(lines)
    found = {v.upper() for v in re.findall(r"EXEC\s+DLI\s+([A-Z]+)", code, re.I)} & UOW
    for lit in re.findall(r"VALUE\s+'([A-Z ]{4})'", code, re.I):
        if lit.strip().upper() in UOW:
            found.add(lit.strip().upper())
    return found


def test_the_burned_ims_programs_issue_only_schd_term_and_chkp():
    used: dict[str, set[str]] = {}
    for name in PROGRAMS:
        text = _source(name)
        if text is None:
            pytest.skip("the CardDemo corpus is not available")
        used[name] = _uow_verbs(text)
    assert set().union(*used.values()) == {"SCHD", "TERM", "CHKP"}, used
    assert used["CBPAUP0C"] == {"CHKP"}
    for cics in ("COPAUA0C", "COPAUS0C", "COPAUS1C"):
        assert used[cics] == {"SCHD", "TERM"}


def test_each_used_verb_has_a_runtime_rule_and_the_rest_are_refused_by_name_on_both_runtimes():
    java = RUNTIME.read_text(encoding="utf-8")
    c = ORACLE.read_text(encoding="utf-8")
    for rule in ("RT-DLI-SCHD", "RT-DLI-TERM"):
        assert f"[rule {rule}]" in java
    assert "public static String checkpoint(" in java and "int GGDLICHKP(" in c
    for src in (java, c):
        other = re.search(r"OTHER\b[^=]*=[^{(]*[{(]([^;]*?)[})];", src, re.S)
        assert other is not None
        for verb in UNUSED:
            assert f'"{verb}' in other.group(1), verb
