# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Values several command families share (cics_command_spec.md section 2: "ordinary constants")."""

from __future__ import annotations

from collections.abc import Mapping

from gitgalaxy.standards.cics.model import Arg, Doc, Refusal

IBM = "https://www.ibm.com/docs/en/cics-ts/6.x?topic="


def ibm(title: str, topic: str) -> Doc:
    return Doc(title, IBM + topic)


# RESP / RESP2: fullword binary areas the command writes; NOHANDLE: no condition's default action
RESP_OPTIONS: Mapping[str, Arg] = {
    "RESP": Arg("area_out", width=4, binary=True),
    "RESP2": Arg("area_out", width=4, binary=True),
    "NOHANDLE": Arg("flag"),
}

# the translator's message for an option given no argument where it needs one (det/cics.py _arg), and for an option
# given in both its forms (LENGTH / FLENGTH, MAXLENGTH / MAXFLENGTH: det/cics.py _one_of)
NEEDS_ARGUMENT = "EXEC CICS option needs an argument"
BOTH_FORMS = "{} and {} together"

# det/cics.py's word-for-word reason for an option no corpus program uses (ASSIGN's and SEND TEXT's default)
NOT_MODELLED = Refusal("not modelled (no corpus program uses it)")

# #4270 slice 1: code-page conversion (det/cics.py _REFUSED_WHY)
CODEPAGE = Refusal("code-page conversion of a CHAR container is not modelled", "X17")
# a pointer to CICS's copy of the data (GET CONTAINER SET, RETRIEVE SET)
POINTER = "the address of CICS's copy of the data (a pointer) is not modelled"
REMOTE = "a remote system is not modelled"

# #4270 spec PR 2: the reasons det/cics.py's old global _REFUSED_WHY gave these options on every command, kept on the
# commands IBM documents them for, where they say why (a file / queue / program command's SYSID, a read's SET)
SYSID_REMOTE = Refusal(REMOTE)
SET_POINTER = Refusal(POINTER)
