"""#5005 (register X42): every CICS command that names a channel or a container has a stated disposition for a CICS-defined
(DFH...) name, so a new member of the family fails here until someone classifies it.

IBM's MOVE / DELETE / PUT CONTAINER and DELETE CHANNEL pages give INVREQ RESP2 30 / 31 and CHANNELERR RESP2 3 for a read-only
CICS-defined item but list no names; LINK / XCTL / RETURN say CHANNEL(DFHTRANSACTION) is the transaction channel. Nothing is
modelled as read-only, so a writing command refuses a DFH name by name on both runtimes (the runtime proofs are in
test_cics_runtimes.py); a reading command is unchanged, because reading a read-only item is legal."""

import pytest

from gitgalaxy.standards.cics import COMMANDS

_NAMING = {"CHANNEL", "CONTAINER", "TOCHANNEL", "AS"}

# Commands that write, move, delete or hand on a channel / container: a DFH name is refused by name.
_REFUSES_DFH = {
    "PUT CONTAINER",
    "PUT64 CONTAINER",
    "DELETE CONTAINER",
    "MOVE CONTAINER",
    "DELETE CHANNEL",
    "START",
    "RUN",
    "LINK",
    "XCTL",
    "RETURN",
}

# Commands that only read (or only name a channel to read from): unchanged on a DFH name, with the reason.
_READS = {
    "GET CONTAINER": "reading a read-only container is legal",
    "GET64 CONTAINER": "the 64-bit GET: reading is legal",
    "STARTBROWSE CONTAINER": "a browse only reads",
    "GETNEXT CONTAINER": "a browse only reads",
    "QUERY CHANNEL": "reads the channel's container count / names",
    "FETCH ANY": "receives a child's channel; creates no channel of its own name",
    "FETCH CHILD": "receives a child's channel; creates no channel of its own name",
    "ASSIGN": "ASSIGN CHANNEL returns the current channel's name",
    "WEB CONVERSE": "AS / CHANNEL here are HTTP options, not channel names",
    "WEB SEND": "AS / CHANNEL here are HTTP options, not channel names",
    "WEB RECEIVE": "AS / CHANNEL here are HTTP options, not channel names",
}


def _naming_commands() -> set[str]:
    return {k for k, c in COMMANDS.items() if _NAMING & (set(c.options) | set(c.refused))}


def _dfh_refusals(key: str) -> list:
    return [r for r in COMMANDS[key].runtime_refusals if "DFH" in (r.java or "") + (r.c or "") + r.situation]


def test_every_channel_or_container_command_has_a_dfh_disposition():
    naming = _naming_commands()
    unclassified = naming - _REFUSES_DFH - set(_READS)
    assert not unclassified, (
        f"classify these for a DFH name (refuse by name, or state why reading is unchanged): {sorted(unclassified)}"
    )
    assert not (_REFUSES_DFH & set(_READS))
    stale = (_REFUSES_DFH | set(_READS)) - naming
    assert not stale, f"no longer a channel / container command: {sorted(stale)}"


@pytest.mark.parametrize("key", sorted(_REFUSES_DFH))
def test_a_writing_command_refuses_a_dfh_name_on_both_runtimes(key):
    refusals = _dfh_refusals(key)
    assert refusals, f"{key} has no DFH refusal"
    assert all(r.register for r in refusals)
    assert any(r.java for r in refusals) and any(r.c for r in refusals)


@pytest.mark.parametrize("key", sorted(_READS))
def test_a_reading_command_carries_no_dfh_refusal(key):
    assert not _dfh_refusals(key), f"{key} refuses a DFH name, but reading a read-only item is legal: {_READS[key]}"


def test_the_64_bit_put_keeps_the_put_refusal():
    put, put64 = _dfh_refusals("PUT CONTAINER"), _dfh_refusals("PUT64 CONTAINER")
    assert put and [r.situation for r in put] == [r.situation for r in put64]
