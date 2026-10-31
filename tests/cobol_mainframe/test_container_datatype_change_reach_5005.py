"""#5005 [c:6daa978d] (X17): a PUT CONTAINER naming the other data type for an existing container. IBM says DATATYPE
"applies only to new containers" yet lists INVREQ RESP2 33 for an attempt to change the data type, and no IBM source
settles which; so it is refused by name. The census reads names only (tests/tools/cics_census.py): no burned program
names a data type on a PUT, and the one FROMCCSID PUT (DBB epscsmrd.cbl) writes back a container it read as CHAR."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_container_options_reach_5005 import _burned_container_commands  # noqa: E402

from gitgalaxy.standards.cics.commands import COMMANDS  # noqa: E402

DATA_TYPE_WORDS = {"BIT", "CHAR", "DATATYPE"}


def _puts():
    return [(n, p, w) for n, p, w in _burned_container_commands() if w[:2] == ["PUT", "CONTAINER"]]


def test_the_data_type_change_is_refused_by_name_on_both_put_forms():
    for key in ("PUT CONTAINER", "PUT64 CONTAINER"):
        reasons = [r.situation for r in COMMANDS[key].runtime_refusals]
        assert any("INVREQ RESP2 33" in r and "existing container of the other type" in r for r in reasons), key


def test_no_burned_put_names_a_data_type():
    hits = [f"{n}: {p}: {' '.join(w[:4])}" for n, p, w in _puts() if DATA_TYPE_WORDS & set(w[2:])]
    assert hits == []


def test_the_only_fromccsid_put_is_epscsmrd_writing_back_a_char_container():
    users = {(n, p) for n, p, w in _puts() if "FROMCCSID" in w}
    assert users == {("dbb-mortgage-application", "epscsmrd.cbl")}


def test_the_x17_note_quotes_the_ibm_wording():
    note = " ".join((ROOT / "docs/language_status/register/X17.md").read_text(encoding="utf-8").split())
    for quote in (
        "This option applies only to new containers.",
        "its data type was established when it was created and cannot be changed.",
        "An attempt was made to change the data-type of an existing container.",
    ):
        assert quote in note, quote
