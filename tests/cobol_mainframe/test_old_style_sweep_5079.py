"""#5079 (register X59): the old-style CICS sweep, every member modelled or refused by name, on both translators.

The members (issue #5079 checklist): READQ TD / DELETEQ TD (X57), UNLOCK (X52), READ / RECEIVE / RETRIEVE SET (X58),
ADDRESS (X59), CONVERSE / POST / WAIT EVENT / WAIT EXTERNAL / WAITCICS (X63) are modelled; SEND PAGE, PURGE MESSAGE, ROUTE,
SEND PARTNSET and RECEIVE PARTN are refused whole by name (X59, owner 2026-10-14: no crucible cases for the BMS paging
family). The BMS logical message they complete is built by SEND MAP / SEND TEXT with ACCUM / PAGING: SEND MAP used to pass
those on as plain flags and sent the map at once, where IBM keeps the message back until SEND PAGE; it now refuses them
(and the printer-only NLEOM / FORMFEED) as SEND TEXT does. The det port (check_options) and the equivalence harness
(equivalence_cics.translate_command) must answer alike."""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tests" / "tools"))
import equivalence_cics as ec  # noqa: E402

from gitgalaxy.standards.cics.commands import COMMANDS  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402

_MODELLED = {
    "READQ TD": "X57",
    "DELETEQ TD": "X57",
    "UNLOCK": "X52",
    "READ": "X14",
    "RECEIVE": "X15",
    "RETRIEVE": "X18",
    "ADDRESS": "X59",
    "CONVERSE": "X63",
    "POST": "X63",
    "WAIT EVENT": "X63",
    "WAIT EXTERNAL": "X63",
    "WAITCICS": "X63",
}
_REFUSED_WHOLE = ("SEND PAGE", "PURGE MESSAGE", "ROUTE", "SEND PARTNSET", "RECEIVE PARTN")
_LOGICAL = "a BMS logical message"


@pytest.mark.parametrize(("key", "register"), sorted(_MODELLED.items()))
def test_each_modelled_member_is_modelled_and_has_a_register_entry(key, register):
    assert COMMANDS[key].status == "modelled"
    assert COMMANDS[key].register == register
    assert (ROOT / "docs/language_status/register" / f"{register}.md").is_file()


@pytest.mark.parametrize("key", _REFUSED_WHOLE)
def test_each_refused_member_is_refused_by_name_with_a_register_entry_citing_ibm(key):
    command = COMMANDS[key]
    assert command.status == "refused" and command.register == "X59"
    register = (ROOT / "docs/language_status/register/X59.md").read_text(encoding="utf-8")
    assert command.ibm.url in register


@pytest.mark.parametrize("key", _REFUSED_WHOLE)
def test_each_refused_member_is_refused_on_the_harness_translator(key):
    with pytest.raises(ec.Unsupported, match="not modelled"):
        ec.translate_command(key)


@pytest.mark.parametrize(
    ("option", "why"),
    [
        ("ACCUM", _LOGICAL),
        ("PAGING", "terminal paging"),
        ("NLEOM", "printer formatting"),
        ("FORMFEED", "printer formatting"),
    ],
)
@pytest.mark.parametrize("verb", ["SEND MAP", "SEND TEXT"])
def test_the_logical_message_and_printer_options_are_refused_by_name_on_both_translators(verb, option, why):
    """SEND MAP and SEND TEXT answer alike, on the det port and on the harness."""
    words = verb.split()
    arg = {"MAP": "'M'"} if verb == "SEND MAP" else {"FROM": "REC"}
    with pytest.raises(C.CicsError, match=rf"{verb} {option}: option not modelled .*{why}"):
        C.check_options(words, {**arg, option: ""})
    text = f"{verb}('M') MAPSET('S') {option}" if verb == "SEND MAP" else f"{verb} FROM(REC) LENGTH(5) {option}"
    with pytest.raises(ec.Unsupported, match=rf"{verb} {option}: option not modelled .*{why}"):
        ec.translate_command(text)


@pytest.mark.parametrize("flags", ["ERASE", "ERASE ALARM FREEKB", "WAIT LAST TERMINAL", "PRINT", "MAPONLY", "DATAONLY"])
def test_the_flags_the_region_honours_still_translate_on_send_map(flags):
    assert ec.translate_command(f"SEND MAP('M') MAPSET('S') {flags}")
    C.check_options(["SEND", "MAP"], {"MAP": "'M'", **{f: "" for f in flags.split()}})


def test_a_refused_flag_is_refused_among_modelled_ones():
    with pytest.raises(C.CicsError, match="SEND MAP ACCUM: option not modelled"):
        C.check_options(["SEND", "MAP"], {"MAP": "'M'", "ERASE": "", "ACCUM": "", "RESP": "R"})
