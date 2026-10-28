# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The COBOL standards and rules-as-data package (#4712).

Declarative tables for the COBOL language standards and deterministic runtime rules
(cobolrt), starting with the MOVE family (#4712, epic #4710).

Follows the table-driven code generation pattern established by CicsSpec.java (#4586, #4608).
"""

from __future__ import annotations

from typing import Any

_LAZY = {
    "MOVE_RULES": "gitgalaxy.standards.cobol.move",
    "MOVE_MATRIX": "gitgalaxy.standards.cobol.move",
    "MOVE_VECTORS": "gitgalaxy.standards.cobol.move",
    "CATEGORIES": "gitgalaxy.standards.cobol.move",
    "KINDS": "gitgalaxy.standards.cobol.move",
    "ACTIONS": "gitgalaxy.standards.cobol.move",
}

__all__ = sorted(_LAZY)


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        return getattr(importlib.import_module(_LAZY[name]), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
