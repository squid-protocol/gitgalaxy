"""#5005 (register X42 / X65): the BTS forms of STARTBROWSE / GETNEXT / ENDBROWSE (ACTIVITY / PROCESS, and the EVENT / TIMER
browses) are refused by name, and no burned estate needs them. IBM treats STARTBROWSE CONTAINER with no CHANNEL as the BTS
form only when the task has no current channel; with one it is the modelled channel browse (DBB `epscsmrd.cbl` does this).

A burned COBOL program that issues any command refused for the BTS reason fails here, so it gets modelled (or a stated
disposition) before it ships, instead of silently hitting the by-name refusal."""

import os
import re
from pathlib import Path

import pytest

from gitgalaxy.core.source_text import read_source
from gitgalaxy.standards.cics import COMMANDS
from gitgalaxy.standards.cics.commands import whole_refusal

BURNED_DIRS = (
    "aws-mainframe-modernization-carddemo",
    "cics-banking-sample-application-cbsa",
    "cics-genapp",
    "zecs",
    "dbb-mortgage-application",
    "cics-async-api-credit-card-application-example",
)
SOURCE_SUFFIXES = {".cbl", ".cob", ".cobol", ".cpy"}
BROWSE_BTS = tuple(f"{v} {t}" for v in ("STARTBROWSE", "GETNEXT", "ENDBROWSE") for t in ("ACTIVITY", "PROCESS"))
_BTS_WHY = "business transaction services"
_EXEC = re.compile(r"EXEC\s+CICS\s+(.*?)(?:END-EXEC|$)", re.IGNORECASE | re.DOTALL)


def _bts_keys() -> set[str]:
    return {k for k, c in COMMANDS.items() if c.status == "refused" and _BTS_WHY in (c.why or "")}


def cics_statements(cobol: str) -> list[str]:
    """Upper-cased text of each EXEC CICS statement in the code area (columns 8-72) of fixed-format COBOL."""
    code = []
    for line in cobol.splitlines():
        if len(line) > 6 and line[6] in "*/":
            continue
        code.append(line[7:72])
    return [" ".join(m.group(1).upper().split()) for m in _EXEC.finditer("\n".join(code))]


def bts_commands(cobol: str) -> set[str]:
    keys = _bts_keys()
    found = set()
    for stmt in cics_statements(cobol):
        words = stmt.split()
        for n in (3, 2, 1):
            if " ".join(words[:n]) in keys:
                found.add(" ".join(words[:n]))
                break
    return found


def _burned_sources() -> list[Path]:
    env = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    root = Path(env) if env else Path(__file__).resolve().parents[2] / ".mainframe_corpora"
    out: list[Path] = []
    for d in BURNED_DIRS:
        base = root / d
        if base.is_dir():
            out += [p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in SOURCE_SUFFIXES]
    return sorted(out)


@pytest.mark.parametrize("key", BROWSE_BTS)
def test_a_bts_browse_is_refused_by_name_in_every_form(key):
    c = COMMANDS[key]
    assert c.status == "refused" and not c.options and not c.outcomes
    assert _BTS_WHY in c.why
    verb, target = key.split()
    for first in (None, target, "BROWSETOKEN", "ACTIVITY", "PROCESS"):
        r = whole_refusal(key, verb, first)
        assert r is not None and r.status == "refused", first


def test_the_channel_browse_is_not_a_bts_form():
    for key in ("STARTBROWSE CONTAINER", "GETNEXT CONTAINER", "ENDBROWSE CONTAINER"):
        assert COMMANDS[key].status == "modelled", key
        assert key not in _bts_keys()
    assert set(BROWSE_BTS) <= _bts_keys()


def test_the_scanner_reads_statements_not_comments_or_the_channel_browse():
    src = (
        "      * EXEC CICS STARTBROWSE ACTIVITY END-EXEC\n"
        "           EXEC CICS STARTBROWSE CONTAINER\n"
        "             BROWSETOKEN (TOK)\n"
        "           END-EXEC\n"
        "           EXEC CICS GETNEXT\n"
        "             PROCESS (P) BROWSETOKEN (TOK)\n"
        "           END-EXEC\n"
        "           EXEC CICS DEFINE ACTIVITY (A) END-EXEC\n"
    )
    assert bts_commands(src) == {"GETNEXT PROCESS", "DEFINE ACTIVITY"}
    assert "STARTBROWSE ACTIVITY" not in bts_commands(src)
    assert "STARTBROWSE CONTAINER" not in bts_commands(src)
    assert bts_commands("           EXEC CICS ENDBROWSE PROCESS BROWSETOKEN(T) END-EXEC\n") == {"ENDBROWSE PROCESS"}


def test_the_burned_estates_issue_no_bts_command():
    sources = _burned_sources()
    if not sources:
        pytest.skip("no burned estate under GITGALAXY_MAINFRAME_CORPORA")
    assert len(sources) > 100, "the scan found too few burned sources to mean anything"
    seen = {}
    for p in sources:
        found = bts_commands(read_source(p).text)
        if found:
            seen[p.name] = sorted(found)
    assert not seen, f"a burned program issues a BTS command, which is refused by name (X42 / X65): {seen}"
