# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4270: the EIB fields whose value is a stated fact of the run (oracle_assumptions.md X21), not a command's.

A command's facts live on its entry (ASSIGN's startcode, userid, ...). EIBTASKN is read straight from the EIB, by no
command: whoever runs the task states it on both sides -- the Java runtime's `CicsTask.withTaskNumber`, the stub's
`$GGCICS_TASKN` (GGCTASKN, which the harness drivers CALL before the program) -- never derived inside a runtime.
`region_default` is the value the equivalence harness states when a case or scenario does not (its `"taskn"`)."""

from __future__ import annotations

from collections.abc import Mapping

from gitgalaxy.standards.cics.commands.shared import ibm
from gitgalaxy.standards.cics.model import Doc, Fact

# IBM: "EIBTASKN Contains the task number assigned to the task by CICS. ... COBOL: PIC S9(7) COMP-3."
EIB_DOC: Doc = ibm("EIB fields including EIBRESP and EIBRESP2", "reference-eib-fields")
TASKN_MAX = 9_999_999  # PIC S9(7) COMP-3

EIB_FACTS: Mapping[str, Fact] = {
    "EIBTASKN": Fact("taskn", java="withTaskNumber", env="GGCICS_TASKN", region_default="0", options=()),
}
