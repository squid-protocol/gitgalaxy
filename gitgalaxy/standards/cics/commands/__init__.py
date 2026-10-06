# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Every command the spec has an entry for, by its key (#4270 spec PR 1: the slice 1-4 commands)."""

from __future__ import annotations

from collections.abc import Mapping

from gitgalaxy.standards.cics.commands import assign, containers, interval, send_text
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


COMMANDS: Mapping[str, Command] = _registry(containers.COMMANDS, interval.COMMANDS, assign.COMMANDS, send_text.COMMANDS)
