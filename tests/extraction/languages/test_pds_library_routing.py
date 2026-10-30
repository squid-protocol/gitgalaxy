# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

"""
#7064: an extensionless PDS member under a dataset-qualifier directory (`PAYR.COBOL/`, `SYS1.COPYLIB/`) routes to the
language the directory suffix names, but only with content evidence. The same input class as hlasm's `asm`/`maclib`
(pinned in test_hlasm_strict.py): every cobol and pli suffix, upper and lower case, nested, plus the negatives.
"""

import pytest

from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_COBOL_PROGRAM = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. PAYROLL.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  WS-ID  PIC 9(5).\n"
    "       PROCEDURE DIVISION.\n"
    "           MOVE 1 TO WS-ID.\n"
    "           STOP RUN.\n"
)
_COBOL_COPYBOOK = (
    "       01  ACCT-REC.\n"
    "           05  ACCT-ID      PIC 9(8).\n"
    "           05  ACCT-NAME    PIC X(30).\n"
    "           05  ACCT-BAL     PIC S9(7)V99 COMP-3.\n"
)
_PLI_PROGRAM = "PAYROLL: PROCEDURE OPTIONS(MAIN);\n  DECLARE X FIXED BIN(31);\n  X = 1;\nEND PAYROLL;\n"
_PLI_INCLUDE = "DCL 1 CUSTREC,\n      2 ID CHAR(8),\n      2 NAME CHAR(30);\n"

_MEMBERS = {
    "cobol": [_COBOL_PROGRAM, _COBOL_COPYBOOK],
    "pli": [_PLI_PROGRAM, _PLI_INCLUDE],
}


def _cases():
    for lang, texts in _MEMBERS.items():
        for suffix in LANGUAGE_DEFINITIONS[lang]["library_directory_suffixes"]:
            for template in ("PAYR.{u}/MEMB1", "apps/sys1.{l}/MEMB1", "export/USER.PROD.{u}/WORK/MEMB1"):
                path = template.format(u=suffix.upper(), l=suffix)
                for i, text in enumerate(texts):
                    yield pytest.param(lang, path, text, id=f"{lang}-{path}-{i}")


@pytest.mark.parametrize(("lang", "path", "text"), list(_cases()))
def test_extensionless_member_in_a_library_directory_routes_its_language(lang, path, text):
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    assert detector.focus(path, text)[0] == lang


def test_no_directory_suffix_is_listed_by_two_languages():
    seen = {}
    for lid, d in LANGUAGE_DEFINITIONS.items():
        for suffix in d.get("library_directory_suffixes", ()):
            assert suffix not in seen, f"{suffix} listed by {seen[suffix]} and {lid}"
            seen[suffix] = lid


@pytest.mark.parametrize("text", [_COBOL_PROGRAM, _COBOL_COPYBOOK, _PLI_PROGRAM, _PLI_INCLUDE])
def test_extensionless_member_outside_a_library_directory_is_not_claimed(text):
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    assert detector.focus("src/MEMB1", text)[0] not in ("cobol", "pli")


@pytest.mark.parametrize("path", ["PAYR.COBOL/README", "PAYR.COPYLIB/NOTES", "PAYR.PLI/README", "PAYR.PL1/NOTES"])
@pytest.mark.parametrize("text", ["Build notes\nrun it twice.\n", "int main(void) { return 0; }\n"])
def test_non_member_text_in_a_library_directory_is_not_claimed(path, text):
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    assert detector.focus(path, text)[0] not in ("cobol", "pli")


def test_a_pli_member_in_a_cobol_library_is_not_claimed_as_cobol():
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    assert detector.focus("PAYR.COBOL/MEMB1", _PLI_PROGRAM)[0] != "cobol"
