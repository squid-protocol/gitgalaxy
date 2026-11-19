"""#8625 slice 4: extensionless REXX execs and CLIST members route by their dataset-qualifier directory or their body.

An exec proves itself by a first-line comment naming REXX (TSO/E REXX Reference, "Identifying a REXX exec"); a CLIST has
no marker, so it needs two statement shapes only CLIST has. Near-misses: prose, shell, one CLIST-looking line.
"""

import pytest

from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

REXX = '/* REXX */\nparse arg name\naddress TSO "ALLOC DA(X)"\nsay "hi" name\nexit 0\n'
REXX_MIXED_CASE = "/* Rexx exec: greet */\nparse arg name\nsay name\n"
CLIST = "PROC 1 NAME\nCONTROL NOMSG\nWRITE HELLO &NAME\nSET &RC = 0\nEXIT CODE(0)\n"
CLIST_NO_PROC = "SET &X = 1\nWRITE &X\n"

NOT_MEMBERS = [
    "Build notes\nrun it twice.\n",
    "#!/bin/sh\necho hi\n",
    "/* a C-style header comment */\nint x;\n",
    "WRITE HELLO &NAME\n",  # one CLIST shape is not enough
]


def _lang(path, text):
    return LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus(path, text)[0]


@pytest.mark.parametrize(
    "path", ["USER.SYSEXEC/HELLO", "export/user.rexx/hello", "SYS1.EXEC/HELLO", "REXXLIB/HELLO", "misc/HELLO"]
)
@pytest.mark.parametrize("text", [REXX, REXX_MIXED_CASE])
def test_extensionless_rexx_exec_routes_rexx(path, text):
    assert _lang(path, text) == "rexx"


@pytest.mark.parametrize(
    "path", ["USER.CLIST/HELLOC", "apps/prod.clistlib/HELLOC", "SYS1.SYSPROC/HELLOC", "misc/HELLOC"]
)
@pytest.mark.parametrize("text", [CLIST, CLIST_NO_PROC])
def test_extensionless_clist_member_routes_clist(path, text):
    assert _lang(path, text) == "clist"


@pytest.mark.parametrize("path", ["USER.CLIST/NOTES", "USER.SYSEXEC/NOTES", "misc/NOTES", "src/MEMB1"])
@pytest.mark.parametrize("text", NOT_MEMBERS)
def test_prose_and_near_misses_are_not_claimed(path, text):
    assert _lang(path, text) not in ("rexx", "clist")


def test_a_rexx_exec_in_a_clist_library_is_rexx():
    assert _lang("USER.CLIST/EXEC1", REXX) == "rexx"


def test_a_cobol_member_still_routes_cobol():
    text = "       01  ACCT-REC.\n           05  ACCT-ID      PIC 9(8).\n           05  ACCT-BAL  PIC S9(7)V99.\n"
    assert _lang("src/ACCTREC", text) == "cobol"
