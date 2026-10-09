# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Every command the spec has an entry for, by its key: full entries for the 51 commands det/cics.py models and
LOAD / RELEASE (engine-only), and name-only entries for every other CICS application (API) command (api.py)."""

from __future__ import annotations

from collections.abc import Mapping

from gitgalaxy.standards.cics.commands import (
    api,
    assign,
    containers,
    files,
    handles,
    interval,
    program,
    queues,
    send_text,
    task,
    terminal,
)
from gitgalaxy.standards.cics.model import Command
from gitgalaxy.standards.cics.resp import DFHRESP


def _registry(*families: tuple[Command, ...]) -> Mapping[str, Command]:
    out: dict[str, Command] = {}
    for family in families:
        for c in family:
            if c.key in out:
                raise ValueError(f"{c.key}: two entries")
            unknown = [o.condition for o in c.outcomes if o.condition not in DFHRESP]
            if unknown:
                raise ValueError(f"{c.key}: outcomes name {unknown}, not DFHRESP conditions")
            out[c.key] = c
    return out


COMMANDS: Mapping[str, Command] = _registry(
    containers.COMMANDS,
    interval.COMMANDS,
    assign.COMMANDS,
    send_text.COMMANDS,
    files.COMMANDS,
    terminal.COMMANDS,
    program.COMMANDS,
    handles.COMMANDS,
    queues.COMMANDS,
    task.COMMANDS,
    api.COMMANDS,
)


def whole_refusal(key: str, verb: str, first_option: str | None) -> Command | None:
    """The name-only / engine-only entry of a command the translator does not model, by how the program wrote it:
    its OPTIONS key, its verb words, or its verb with the first option (IBM's WAIT JOURNALNAME, GETNEXT CONTAINER,
    ADDRESS SET are a verb and an option to the parser). None: not a CICS application command we list."""
    tries = [key, verb] + ([f"{verb} {first_option}"] if first_option else [])
    for k in sorted(set(tries), key=lambda t: -len(t)):  # the most specific form first
        c = COMMANDS.get(k)
        if c is not None and c.status != "modelled":
            return c
    return None
