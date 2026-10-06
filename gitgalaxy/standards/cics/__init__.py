# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The CICS command spec (#4270, docs/language_status/cics_command_spec.md): one declarative description of each
EXEC CICS command we model -- its options, refusals and their reasons, option rules, conditions with RESP2, stated
facts -- for the engine, the det translator, both runtimes and the equivalence harness to read.

Data only, standard library only, and nothing imports it at engine start: `import gitgalaxy.standards.cics` loads
this file alone; COMMANDS, DFHRESP, CONDITION_ABEND ... load on first use. It is never the oracle (section 6): the
cics-crucible's expected logs are traced by hand from IBM's documentation, and its log scripts may not import it.

Spec PR 1: nothing reads the spec yet. tests/core_engine/test_cics_spec_equality.py proves it equal to every copy
it will replace."""

from __future__ import annotations

from typing import Any

_LAZY = {
    "COMMANDS": "gitgalaxy.standards.cics.commands",
    "DFHRESP": "gitgalaxy.standards.cics.resp",
    "RESP_NAME": "gitgalaxy.standards.cics.resp",
    "ALIASES": "gitgalaxy.standards.cics.resp",
    "CONDITION_ABEND": "gitgalaxy.standards.cics.resp",
}

__all__ = sorted(_LAZY)


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        return getattr(importlib.import_module(_LAZY[name]), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
