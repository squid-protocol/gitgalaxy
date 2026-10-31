"""#7207: COBOL dead_code counts a comment only when it has a statement's shape, not just its first word."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

RULE = LANGUAGE_DEFINITIONS["cobol"]["rules"]["dead_code"]

POSITIVES = [
    "      * MOVE X TO Y.",
    "      * MOVE CORRESPONDING A TO B",
    "      * COMPUTE WS-N = WS-A + 1.",
    "      * COMPUTE WS-N ROUNDED = WS-A / 3",
    "      * IF WS-A > 0",
    "      * IF WS-A NOT = SPACES",
    "      * IF WS-A IS NUMERIC",
    "      * PERFORM 100-INIT.",
    "      * PERFORM 100-INIT THRU 100-EXIT",
    "      * PERFORM 100-INIT 5 TIMES",
    "      * PERFORM UNTIL WS-EOF = 'Y'",
    "      * PERFORM VARYING I FROM 1 BY 1 UNTIL I > 9",
    "      * CALL 'SUBPGM' USING A B.",
    "      * CALL WS-PGM USING A",
    "      * EXEC SQL SELECT 1 END-EXEC",
    "      * EXEC CICS RETURN END-EXEC",
    "*>     move a to b.",
    "*> if ws-a = 1",
]

NEGATIVES = [
    "* Move the piece",
    "* if last iteration used > 40% of remaining time",
    "*> If king moved, clear both rights for that side.",
    "*> Compute truth state of WS-OTHER-LIT under current",
    "*    If per-field CODEC unspecified, apply --codec:",
    "* MOVE REPRESENTATION",
    "*> MOVE LIST",
    "*>     if conflict:",
    "*            if c & 1: c = (c>>1) XOR 0xEDB88320 else c >>= 1",
    "      * call this once at startup",
    "      * perform the following steps in order",
    "      * PERFORM the validation",
    "      * EXEC the plan",
]


@pytest.mark.parametrize("line", POSITIVES)
def test_commented_out_statement_counts(line):
    assert RULE.search(line + "\n")


@pytest.mark.parametrize("line", NEGATIVES)
def test_prose_heading_pseudocode_does_not_count(line):
    assert not RULE.search(line + "\n")
