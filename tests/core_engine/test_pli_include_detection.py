# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

"""#3867: a PL/I `%INCLUDE` member named `.inc` resolves to `pli`.

PL/I does not claim `.inc` (PHP, Pascal, NASM and C use it too), so the
Unicode Gauntlet's one-line member `INCA.inc` (`DCL CODEA CHAR(2);`) fell to
the estate-wide language mix: `c` on the ASCII seed and `assembly` on the
German / Nordic variants. The folder's own PL/I program plus a PL/I statement
in the body now decide it; other `.inc` languages beside a PL/I program keep
their own identity.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PGMA = """ PGMA: PROC OPTIONS(MAIN);
   DCL 1 CUSTREC,
         2 CUSTNO        CHAR(8),
         2 AMOUNTA       FIXED DEC(9,2);
   %INCLUDE {member};
   CALL PROCA;
 END PGMA;
"""

# An estate where C dominates, as in the full gauntlet run that shares one
# estate with every keyword-rosetta language.
_C_HEAVY_TALLY = {".c": 40, ".h": 30, ".inc": 3, ".s": 5, ".php": 4, ".pli": 1}


def _detect(path: Path, tally: dict[str, int] | None = None) -> dict:
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    text = path.read_text(encoding="utf-8")
    return detector.inspect(path, content_sample=text, ext_tally=tally if tally is not None else _C_HEAVY_TALLY)


def _pli_folder(tmp_path: Path, member: str, body: str) -> Path:
    (tmp_path / "PGMA.pli").write_text(_PGMA.format(member=member), encoding="utf-8")
    inc = tmp_path / f"{member}.inc"
    inc.write_text(body, encoding="utf-8")
    return inc


@pytest.mark.parametrize("member", ["INCA", "INCAÆØÅ", "INCAÄÖÜ"])
def test_one_line_pli_include_beside_its_program_is_pli(tmp_path, member):
    inc = _pli_folder(tmp_path, member, f"   DCL CODE{member[3:]} CHAR(2);\n")
    for tally in (_C_HEAVY_TALLY, {}):
        result = _detect(inc, tally)
        assert result["lang_id"] == "pli", result
        # a confident lock, so the statistical auditor's C-family fallback leaves it alone
        assert result["lock_tier"] < 4
        assert "Collision" not in result["source_proof"]


@pytest.mark.parametrize(
    "body",
    [
        "   DCL 1 CUSTREC,\n     2 CUSTNO CHAR(8);\n",
        "   DECLARE AMOUNT FIXED DECIMAL(9,2);\n",
        " SUBA: PROC;\n END SUBA;\n",
        "   %INCLUDE INCB;\n",
    ],
)
def test_pli_statement_shapes(tmp_path, body):
    assert _detect(_pli_folder(tmp_path, "INCA", body))["lang_id"] == "pli"


def test_pli_body_without_a_pli_sibling_is_not_forced(tmp_path):
    inc = tmp_path / "INCA.inc"
    inc.write_text("   DCL CODEA CHAR(2);\n", encoding="utf-8")
    assert _detect(inc)["lang_id"] != "pli"


# (language, its own ecosystem sibling, body)
_OTHER_INCLUDES = [
    ("php", "index.php", "<?php\n$config = array('db' => 'main');\nfunction load_config() { return $config; }\n"),
    (
        "assembly",
        "main.s",
        "        MACRO\n&LABEL   SAVEREGS\n        STM   14,12,12(13)\n        MEND\n"
        "PROGA    CSECT\n         USING PROGA,15\n         BR    14\n         END\n",
    ),
    ("c", "util.c", "#define MAX_ITEMS 64\n#define MIN_ITEMS 1\nextern int item_count;\n"),
]


@pytest.mark.parametrize(("name", "sibling", "body"), _OTHER_INCLUDES, ids=[n for n, _, _ in _OTHER_INCLUDES])
def test_other_includes_beside_a_pli_program_keep_their_language(tmp_path, name, sibling, body):
    # The same file resolves identically with and without the PL/I sibling:
    # the PL/I anchor only ever claims a PL/I body.
    alone = tmp_path / "alone"
    alone.mkdir()
    (alone / sibling).write_text("\n", encoding="utf-8")
    (alone / "defs.inc").write_text(body, encoding="utf-8")
    beside = tmp_path / "beside"
    beside.mkdir()
    (beside / sibling).write_text("\n", encoding="utf-8")
    (beside / "PGMA.pli").write_text(_PGMA.format(member="INCA"), encoding="utf-8")
    (beside / "defs.inc").write_text(body, encoding="utf-8")

    lang_alone = _detect(alone / "defs.inc")["lang_id"]
    lang_beside = _detect(beside / "defs.inc")["lang_id"]
    assert lang_beside == lang_alone
    assert lang_beside != "pli"
    if name == "php":
        assert lang_beside == "php"
    if name == "c":
        # c vs cpp for a bare `#define` header is the C-family's own call, not this anchor's
        assert lang_beside in ("c", "cpp")
