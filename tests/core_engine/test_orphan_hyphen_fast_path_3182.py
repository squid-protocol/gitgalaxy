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
another (`WS-EXIT` inside `WS-EXIT-DONE`). This test runs a fixture both ways
(fast path, then the admission guards monkeypatched back to `\\w+`-only, which
forces the fallback for hyphenated names) and asserts they agree.

#3198 changed what that shared answer IS for cobol, which is why this file moved
with it. cobol now declares `identifier_extra_chars: "-"`, so `-` is a name
character on BOTH paths: the index keys whole `[\\w-]+` tokens, and the fallback
boundary is `(?<![\\w-])name(?![\\w-])`. A shorter name no longer occurs inside a
longer hyphenated one, so `WS-EXIT` is unreferenced even though `WS-EXIT-DONE`
is PERFORMed. Parity remains the contract; the fixture's expected census is now
asserted outright below, so a future change to either path has to move a number
a human reads rather than merely agreeing with itself.
"""

from __future__ import annotations

from gitgalaxy.core import detector as detector_mod
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _unreferenced(code: str) -> int:
    return (
        StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(code, "")["equations"].get("unreferenced_by_name", 0)
    )


# A PROCEDURE DIVISION whose paragraph names are hyphenated and deliberately
# overlap at hyphen boundaries: CALC and CALC-TOTAL, WS-EXIT and WS-EXIT-DONE.
# Since #3198 those overlaps are NOT occurrences of the shorter name (`-` is a
# cobol name character), so CALC is referenced only by its own `PERFORM CALC.`
# and WS-EXIT by nothing at all. Some paragraphs are PERFORMed, some never are.
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

    # Force the fallback for hyphenated names by narrowing BOTH admission guards
    # back to single `\w+` tokens: `_INDEXABLE_NAME_RE` for a language with no
    # declared identifier lexicon, and the per-alphabet matcher cobol has used
    # since #3198. Hyphenated names then fail the guard and take `_is_orphan`'s
    # exact boundary-regex rescan.
    monkeypatch.setattr(detector_mod, "_INDEXABLE_NAME_RE", detector_mod._WORD_NAME_RE)
    monkeypatch.setattr(detector_mod, "_name_token_re", lambda _extra: detector_mod._WORD_NAME_RE)
    fallback = _unreferenced(COBOL_FIXTURE)

    assert fast == fallback, (
        f"hyphen orphan fast path diverged from the boundary-regex fallback: fast={fast} fallback={fallback}"
    )


def test_hyphen_boundary_census_is_the_3198_reading():
    """`-` is a cobol name character, so a longer paragraph name is not a mention
    of the shorter one it begins with (#3198)."""
    functions = StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(COBOL_FIXTURE, "")["functions"]
    status = {f["name"]: f["usage_status"] for f in functions}
    # PERFORMed by name -> referenced.
    assert status["CALC-TOTAL"] == 0
    assert status["WS-EXIT-DONE"] == 0
    assert status["CALC"] == 0  # `PERFORM CALC.` inside CALC-TOTAL
    # Named nowhere: `WS-EXIT-DONE` is a different name, and MAIN-PARA is the
    # entry, which nothing has to name. The census reports that; it does not
    # claim either one is dead (contract corollary 3).
    assert status["WS-EXIT"] == 1
    assert status["MAIN-PARA"] == 1


def test_hyphen_fixture_actually_exercises_orphans_3182():
    # Guard the guard: if the fixture stopped producing any hyphenated orphan the
    # parity test above would pass vacuously. WS-EXIT and CALC are never PERFORMed,
    # so at least the census must see some unreferenced units to be meaningful.
    assert _unreferenced(COBOL_FIXTURE) >= 1
