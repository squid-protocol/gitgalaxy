# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The language-registration invariants, enforced from one place (#3093).

Adding a language touches surfaces far from its `languages/<lang>.py` file, and
the #2511 (db2_sql) landing paid two CI round-trips for surfaces nothing
enumerated: the LANGUAGE_STRICTNESS row and the POSITIONAL_LANGUAGES pin. The
checks live in `tests/tools/language_addition_audit.py` -- one command an
author runs in seconds BEFORE the first full-suite run:

    python tests/tools/language_addition_audit.py --lang <lang>

and this module runs the same functions in CI, so the tool and the gate can
never drift apart. Per-surface detail is in each check's own message; the
overlap with test_language_strictness / test_unreferenced_by_name_contract_2806
is deliberate redundancy in the cheap direction (those tests explain their
surface deeply; this one points an author at the audit tool).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TOOLS_DIR = str(Path(__file__).resolve().parents[1] / "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import language_addition_audit as audit  # noqa: E402


@pytest.mark.parametrize("check", audit.HARD_CHECKS, ids=lambda c: c.__name__)
def test_registration_invariant(check):
    failures = check()
    assert not failures, (
        "language-registration invariant violated -- run "
        "`python tests/tools/language_addition_audit.py --lang <lang>` for the full surface:\n" + "\n".join(failures)
    )
