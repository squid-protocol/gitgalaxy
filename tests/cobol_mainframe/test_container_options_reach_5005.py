"""#5005 [c:cb576bca] (X17): the container options still refused by name -- CHAR BYTEOFFSET / PREPEND, a CCSID outside the
modelled four, the code-page names, CONVERTST / CCSID(area), GET SET with a CCSID on a BIT container -- and their reach in the
burned estates. No burned program issues one, so each stays refused until one does. The census reads names only
(tests/tools/cics_census.py); the evidence levels are the register's (X17)."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

from gitgalaxy.standards.cics.commands import COMMANDS  # noqa: E402

MODELLED_CCSIDS = {37, 500, 1140, 1208}
# Options no burned program may issue on a container command (each is refused, or modelled for BIT only, with no burned user).
UNUSED = {"BYTEOFFSET", "PREPEND", "FROMCODEPAGE", "INTOCODEPAGE", "CONVERTST", "CCSID"}
CCSID_ARG = re.compile(r"\b(?:FROM|INTO)CCSID\s*\(\s*([^)\s]*)\s*\)")


def test_the_still_refused_options_are_refused_or_not_offered_by_name():
    for key in ("GET CONTAINER", "PUT CONTAINER", "GET64 CONTAINER", "PUT64 CONTAINER"):
        spec = COMMANDS[key]
        for opt in ("FROMCODEPAGE", "INTOCODEPAGE"):
            if opt in spec.refused or opt in spec.options:
                assert opt in spec.refused, (key, opt)
    assert "SET" in COMMANDS["GET64 CONTAINER"].refused
    assert "SET" not in COMMANDS["GET64 CONTAINER"].options
    for opt in ("FROMCODEPAGE", "INTOCODEPAGE"):
        assert opt in COMMANDS["PUT CONTAINER"].refused or opt in COMMANDS["GET CONTAINER"].refused


def _burned_container_commands():
    import cics_census

    from gitgalaxy.core.source_text import read_source

    env = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    root = Path(env) if env else ROOT / ".mainframe_corpora"
    if not root.is_dir():
        pytest.skip("no mainframe corpora checkout")
    burned = cics_census.burned_names()
    found = []
    for name, corpus in cics_census.corpus_dirs([root]):
        if not cics_census.is_burned(name, burned):
            continue
        for prog in sorted(
            p for p in corpus.rglob("*") if p.is_file() and p.suffix.lower() in cics_census.PROGRAM_EXTS
        ):
            text = read_source(prog).text
            pli = prog.suffix.lower() in (".pli", ".pl1")
            found.extend(
                (name, prog.name, words)
                for words in cics_census.commands(text, pli=pli)
                if " ".join(words[:2]) in ("GET CONTAINER", "PUT CONTAINER") or words[0] in ("GET64", "PUT64")
            )
            # the CCSID arguments sit inside parentheses, which the census's top-level words drop
            found.extend(
                (name, prog.name, ["CCSIDARG", m.group(1)])
                for m in CCSID_ARG.finditer(cics_census.fixed_format_text(text))
            )
    if not found:
        pytest.skip("no burned estate in the corpora checkout")
    return found


def test_no_burned_program_issues_a_still_refused_container_option():
    hits = []
    for name, prog, words in _burned_container_commands():
        if words[0] == "CCSIDARG":
            continue
        if words[0] in ("GET64", "PUT64") or UNUSED & set(words[2:]):
            hits.append(f"{name}: {prog}: {' '.join(words[:3])}")
    assert hits == []


def test_every_burned_ccsid_is_one_of_the_four_modelled_pages():
    values = {w[1] for _, _, w in _burned_container_commands() if w[0] == "CCSIDARG"}
    assert values, "the census found no CCSID argument (DBB epscsmrd.cbl has two)"
    assert {int(v) for v in values if v.isdigit()} <= MODELLED_CCSIDS
    assert all(v.isdigit() for v in values), values  # a data-name CCSID would need a run-time value


def test_get_container_set_with_a_ccsid_is_only_dbb_epscsmrd():
    users = {
        (n, p)
        for n, p, w in _burned_container_commands()
        if w[:2] == ["GET", "CONTAINER"] and "SET" in w and "INTOCCSID" in w
    }
    assert users == {("dbb-mortgage-application", "epscsmrd.cbl")}
