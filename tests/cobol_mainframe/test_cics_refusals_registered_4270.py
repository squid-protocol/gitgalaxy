"""#4270 (oracle_assumptions.md X65): every EXEC CICS command the spec refuses or leaves engine-only names a register
entry, and that entry's file exists, so a refusal always has a reason on record."""

from __future__ import annotations

from pathlib import Path

from gitgalaxy.standards.cics.commands import COMMANDS

REGISTER = Path(__file__).resolve().parents[2] / "docs" / "language_status" / "register"


def test_every_refused_command_names_an_existing_register_entry():
    missing = [k for k, c in COMMANDS.items() if c.status != "modelled" and not c.register]
    assert missing == []
    unknown = sorted(
        {
            c.register
            for c in COMMANDS.values()
            if c.status != "modelled" and not (REGISTER / f"{c.register}.md").exists()
        }
    )
    assert unknown == []


def test_x65_is_the_default_and_the_exceptions_are_the_named_ones():
    other = {k: c.register for k, c in COMMANDS.items() if c.status != "modelled" and c.register != "X65"}
    assert set(other.values()) <= {"X46", "X59", "X63"}
    assert other["DUMP TRANSACTION"] == "X46"


def test_every_refused_option_with_a_register_entry_names_an_existing_one():
    unknown = sorted(
        {
            f"{k} {o}: {r.register}"
            for k, c in COMMANDS.items()
            for o, r in c.refused.items()
            if r.register and not (REGISTER / f"{r.register}.md").exists()
        }
    )
    assert unknown == []
    assert COMMANDS["HANDLE ABEND"].refused["PROGRAM"].register == "X67"


def test_the_bms_routing_and_partition_commands_are_refused_under_x59_5079():
    for key in ("ROUTE", "SEND PARTNSET", "RECEIVE PARTN"):
        cmd = COMMANDS[key]
        assert (cmd.status, cmd.register) == ("refused", "X59"), key
    text = (REGISTER / "X59.md").read_text(encoding="utf-8")
    assert all(f"**{n}**" in text for n in ("ROUTE", "SEND PARTNSET", "RECEIVE PARTN"))
    assert "GGCECBW" in (REGISTER / "X63.md").read_text(encoding="utf-8")
