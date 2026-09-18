# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#3182: the hyphenated-name orphan fast path must be byte-identical to the
boundary-regex fallback it replaces.

`_is_orphan` answers "does this name occur outside its own span?" via an
O(log n) bisect over a precomputed occurrence index. Before #3182 the index
only covered single `\\w+` tokens, so hyphenated identifier names (COBOL
paragraphs, Lisp/Scheme, the column_sensitive family) fell to an O(filesize)
per-function `(?<!\\w)name(?!\\w)` rescan. #3182 indexes the segment-aligned
hyphenated sub-runs of every `[\\w-]+` token so those names bisect too.

The contract is exactness, not speed: the fast path must return the SAME
`unreferenced_by_name` census as the fallback for every fixture -- including the
adversarial cases where one paragraph name is a hyphen-boundary prefix/suffix of
another (`WS-CALC` inside `WS-CALC-TOTAL`), where the boundary semantics let a
shorter name match inside a longer hyphenated token. This test runs a fixture
both ways (fast path, then the guard monkeypatched back to `\\w+`-only, which
forces the pre-#3182 fallback for hyphenated names) and asserts they agree.
"""

from __future__ import annotations

from gitgalaxy.core import detector as detector_mod
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _unreferenced(code: str) -> int:
    return StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(code, "")["equations"].get(
        "unreferenced_by_name", 0
    )


# A PROCEDURE DIVISION whose paragraph names are hyphenated and deliberately
# overlap at hyphen boundaries. CALC and CALC-TOTAL, WS-EXIT and WS-EXIT-DONE:
# a naive `[\w-]+` token-equality index would miss CALC where it appears as a
# prefix of CALC-TOTAL, and a naive alternation would mis-attribute it. Some
# paragraphs are PERFORMed (referenced), some never are (orphans).
COBOL_FIXTURE = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. HYPHENTEST.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM CALC-TOTAL.
           PERFORM WS-EXIT-DONE.
           GOBACK.
       CALC.
           MOVE 1 TO WS-A.
       CALC-TOTAL.
           ADD WS-A TO WS-B.
           PERFORM CALC.
       WS-EXIT.
           DISPLAY 'NEVER REACHED BY NAME'.
       WS-EXIT-DONE.
           DISPLAY 'DONE'.
"""


def test_hyphen_orphan_fast_path_matches_fallback_3182(monkeypatch):
    # Fast path (default #3182 behavior): hyphenated names bisect the index.
    fast = _unreferenced(COBOL_FIXTURE)

    # Force the pre-#3182 fallback for hyphenated names by narrowing the fast
    # path's admission regex back to single `\w+` tokens -- hyphenated names then
    # fail the guard and take `_is_orphan`'s exact boundary-regex rescan.
    monkeypatch.setattr(detector_mod, "_INDEXABLE_NAME_RE", detector_mod._WORD_NAME_RE)
    fallback = _unreferenced(COBOL_FIXTURE)

    assert fast == fallback, (
        f"hyphen orphan fast path diverged from the boundary-regex fallback: "
        f"fast={fast} fallback={fallback}"
    )


def test_hyphen_fixture_actually_exercises_orphans_3182():
    # Guard the guard: if the fixture stopped producing any hyphenated orphan the
    # parity test above would pass vacuously. WS-EXIT and CALC are never PERFORMed,
    # so at least the census must see some unreferenced units to be meaningful.
    assert _unreferenced(COBOL_FIXTURE) >= 1
