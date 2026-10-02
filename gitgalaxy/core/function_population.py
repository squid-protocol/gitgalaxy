# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""
The one definition of "a function" for counting and listing (#4110).

The slicer emits units that are not functions -- a file's top-level bucket
(``__global_context__``), ``Anonymous_Block``, and Mode E statement slices
(``CREATE_Statement``, ``Declarative_Block``, ...). ``detector`` stamps every
one of them ``is_synthetic_slice`` (``_is_uncountable_slice``). A narrower flag,
``calls_only``, marks only Python's module-level bucket.

Consumers used to choose between the two flags by hand, and they disagreed: the
scan DB's ``function_data`` (and every per-function statistic, #2691) excluded
all synthetic slices, while the audit's "Function Analysis", the LLM brief's
function lists, the function rankings and the folder roll-up excluded only
``calls_only`` -- 48,318 "functions" in the audit against 45,550 in the DB on
language-crucible. Anything that COUNTS or LISTS functions goes through
``is_population_function``.

Synthetic slices still carry signals and mass at file level; consumers that
sum file impact deliberately keep them and do not use this predicate.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def is_population_function(unit: Any) -> bool:
    """True for a real function/method; False for a slicer-synthesized unit.
    ``calls_only`` units are always synthetic slices, so they are excluded too."""
    return isinstance(unit, dict) and not unit.get("is_synthetic_slice") and not unit.get("calls_only")


def population_functions(units: Iterable[Any] | None) -> list[dict[str, Any]]:
    return [u for u in units or [] if is_population_function(u)]
