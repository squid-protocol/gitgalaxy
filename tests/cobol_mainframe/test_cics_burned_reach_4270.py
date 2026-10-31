"""#4270 [c:be2a7d55] (breadth): every EXEC CICS command a burned estate issues is a modelled spec entry and none of its
options is one the spec refuses, and each command the checklist item names is modelled or refused by name with a register
entry. The census reads names only (tests/tools/cics_census.py); the proof levels are the register's, not this test's."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

from gitgalaxy.standards.cics.commands import COMMANDS  # noqa: E402

REGISTER = ROOT / "docs" / "language_status" / "register"
# The item's verbs: modelled, or refused by name (the register entry says why and what reopens it).
MODELLED = ["GET CONTAINER", "PUT CONTAINER", "DELETE CONTAINER", "START", "RETRIEVE", "GETMAIN", "FREEMAIN", "CONVERSE",
            "ASSIGN", "INQUIRE PROGRAM", "HANDLE ABEND", "LOAD", "RELEASE"]  # (#6876)  # fmt: skip
REFUSED: dict[str, str] = {}


# Burned-estate commands the spec refuses on purpose: web services are out of scope of #4270 (X65).
OUT_OF_SCOPE = {"SOAPFAULT CREATE"}
# The spec's entry for a form the census reads from its first words: SEND is SEND TEXT, GET DCOUNTER is GET COUNTER's.
FORMS = {"SEND": "SEND TEXT", "GET DCOUNTER": "GET COUNTER"}


def _key(words: list[str]) -> str | None:
    """The longest leading run of the command's words that names a spec entry (`GET CONTAINER`, `ASSIGN`)."""
    for lead, form in FORMS.items():
        if " ".join(words[: len(lead.split())]) == lead:
            return form
    for n in range(min(3, len(words)), 0, -1):
        if " ".join(words[:n]) in COMMANDS:
            return " ".join(words[:n])
    return None


def _corpora() -> Path:
    env = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    root = Path(env) if env else ROOT / ".mainframe_corpora"
    if not root.is_dir():
        pytest.skip("no mainframe corpora checkout")
    return root


def test_the_items_verbs_are_modelled_or_refused_with_a_register_entry():
    for key in MODELLED:
        assert key in COMMANDS and COMMANDS[key].status == "modelled", key
    for key, reg in REFUSED.items():
        assert key in COMMANDS and COMMANDS[key].status != "modelled", key
        assert COMMANDS[key].register == reg and (REGISTER / f"{reg}.md").exists(), key


def test_every_command_a_burned_estate_issues_is_modelled_with_no_refused_option():
    import cics_census

    from gitgalaxy.core.source_text import read_source

    burned = cics_census.burned_names()
    bad: set[str] = set()
    seen = 0
    for name, corpus in cics_census.corpus_dirs([_corpora()]):
        if not cics_census.is_burned(name, burned):
            continue
        for prog in sorted(
            p for p in corpus.rglob("*") if p.is_file() and p.suffix.lower() in cics_census.PROGRAM_EXTS
        ):
            for words in cics_census.commands(read_source(prog).text):
                seen += 1
                key = _key(words)
                if " ".join(words[:2]) in OUT_OF_SCOPE:
                    continue
                cmd = COMMANDS.get(key) if key else None
                if cmd is None or cmd.status != "modelled":
                    bad.add(f"{name}: {' '.join(words[:3])}: not a modelled command")
                    continue
                for opt in words[1:]:
                    if opt in cmd.refused:
                        bad.add(f"{name}: {key} {opt}: a refused option")
    if not seen:
        pytest.skip("no burned estate in the corpora checkout")
    assert sorted(bad) == []


def test_soapfault_create_names_the_options_dbb_epscsmrd_issues_5235():
    """#5235: SOAPFAULT CREATE stays refused whole (web services, X65) but the spec names IBM's options, so CLIENT /
    FAULTSTRING / FAULTSTRLEN are known words, not unknown ones."""
    cmd = COMMANDS["SOAPFAULT CREATE"]
    assert cmd.status == "refused" and not cmd.options
    assert {"CLIENT", "FAULTSTRING", "FAULTSTRLEN"} <= set(cmd.refused)
    assert cmd.ibm.url.endswith("summary-soapfault-create")
    assert cmd.whole_message("SOAPFAULT CREATE").startswith("EXEC CICS SOAPFAULT CREATE not modelled (")
