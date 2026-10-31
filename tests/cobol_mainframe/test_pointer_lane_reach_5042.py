"""#5042: the pointer-lane members still refused by name, and their reach in the burned estates. Each stays refused in the
command spec (the translator's refusal tests are test_pointer_lane_5042.py), and no burned program issues one, so none moves
a port. The census reads names only (tests/tools/cics_census.py); the evidence levels are the register's (X47, X58, X65)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

from gitgalaxy.standards.cics.commands import COMMANDS  # noqa: E402

# command key -> the words that make a burned issue of it a member of the refused class (None: any use of the command)
WHOLE_COMMANDS = ("GETMAIN64", "FREEMAIN64")
SET_REFUSED = ("GET64 CONTAINER", "SEND MAP", "RECEIVE MAP", "SEND CONTROL")
RELATIVE_BYTE = {"RBA", "RRN", "XRBA"}


def test_the_refused_members_are_not_modelled_commands_or_options():
    for key in ("GETMAIN64", "FREEMAIN64"):
        assert COMMANDS[key].status == "refused", key
    for key in SET_REFUSED:
        assert "SET" in COMMANDS[key].refused and "SET" not in COMMANDS[key].options, key
    for key in ("READ", "READNEXT", "READPREV", "GET CONTAINER"):
        assert COMMANDS[key].options["SET"].kind == "pointer", key


def _is_member(words: list[str]) -> bool:
    lead = " ".join(words[:2])
    if words[0] in WHOLE_COMMANDS:
        return True
    if any(lead.startswith(k) for k in SET_REFUSED) and "SET" in words[1:]:
        return True
    if words[0] in ("READ", "READNEXT", "READPREV") and "SET" in words[1:]:
        return bool(RELATIVE_BYTE & set(words[1:]))
    return lead == "GET CONTAINER" and "SET" in words[1:] and "BYTEOFFSET" in words[1:]


def test_no_burned_program_issues_a_member_still_refused():
    import cics_census

    from gitgalaxy.core.source_text import read_source

    env = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    root = Path(env) if env else ROOT / ".mainframe_corpora"
    if not root.is_dir():
        pytest.skip("no mainframe corpora checkout")
    burned = cics_census.burned_names()
    seen = 0
    hits: list[str] = []
    for name, corpus in cics_census.corpus_dirs([root]):
        if not cics_census.is_burned(name, burned):
            continue
        for prog in sorted(
            p for p in corpus.rglob("*") if p.is_file() and p.suffix.lower() in cics_census.PROGRAM_EXTS
        ):
            for words in cics_census.commands(read_source(prog).text):
                seen += 1
                if _is_member(words):
                    hits.append(f"{name}: {prog.name}: {' '.join(words[:3])}")
    if not seen:
        pytest.skip("no burned estate in the corpora checkout")
    assert hits == []
