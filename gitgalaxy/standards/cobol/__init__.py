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
(cobolrt), covering MOVE, COMPARE, ARITH, STRING, FUNC, EDIT, SORT, and HFP families (#4712, epic #4710).

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
    "COMPARE_RULES": "gitgalaxy.standards.cobol.compare",
    "COMPARE_MATRIX": "gitgalaxy.standards.cobol.compare",
    "COMPARE_VECTORS": "gitgalaxy.standards.cobol.compare",
    "COMPARE_MODES": "gitgalaxy.standards.cobol.compare",
    "ARITH_RULES": "gitgalaxy.standards.cobol.arith",
    "ARITH_VECTORS": "gitgalaxy.standards.cobol.arith",
    "ROUNDING_MODES": "gitgalaxy.standards.cobol.arith",
    "SIZE_ERROR_CONDITIONS": "gitgalaxy.standards.cobol.arith",
    "STRING_RULES": "gitgalaxy.standards.cobol.string_ops",
    "STRING_VECTORS": "gitgalaxy.standards.cobol.string_ops",
    "INSPECT_MODES": "gitgalaxy.standards.cobol.string_ops",
    "PHRASE_TYPES": "gitgalaxy.standards.cobol.string_ops",
    "FUNC_RULES": "gitgalaxy.standards.cobol.func",
    "FUNC_VECTORS": "gitgalaxy.standards.cobol.func",
    "FUNC_SPECS": "gitgalaxy.standards.cobol.func",
    "FUNC_CATEGORIES": "gitgalaxy.standards.cobol.func",
    "EDITING_RULES": "gitgalaxy.standards.cobol.editing",
    "EDITING_SYMBOLS": "gitgalaxy.standards.cobol.editing",
    "EDITING_VECTORS": "gitgalaxy.standards.cobol.editing",
    "EDIT_CATEGORY_NAMES": "gitgalaxy.standards.cobol.editing",
    "SORT_RULES": "gitgalaxy.standards.cobol.sort_ops",
    "SORT_VECTORS": "gitgalaxy.standards.cobol.sort_ops",
    "DIRECTION_NAMES": "gitgalaxy.standards.cobol.sort_ops",
    "COLLATING_NAMES": "gitgalaxy.standards.cobol.sort_ops",
    "PHRASE_NAMES": "gitgalaxy.standards.cobol.sort_ops",
    "HFP_RULES": "gitgalaxy.standards.cobol.hfp",
    "HFP_VECTORS": "gitgalaxy.standards.cobol.hfp",
    "PRECISION_SHORT": "gitgalaxy.standards.cobol.hfp",
    "PRECISION_LONG": "gitgalaxy.standards.cobol.hfp",
    "BYTES_SHORT": "gitgalaxy.standards.cobol.hfp",
    "BYTES_LONG": "gitgalaxy.standards.cobol.hfp",
    "BIAS_CHARACTERISTIC": "gitgalaxy.standards.cobol.hfp",
    "SIGNIFICANT_DIGITS_SHORT": "gitgalaxy.standards.cobol.hfp",
    "SIGNIFICANT_DIGITS_LONG": "gitgalaxy.standards.cobol.hfp",
}

__all__ = sorted(_LAZY)


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        return getattr(importlib.import_module(_LAZY[name]), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
