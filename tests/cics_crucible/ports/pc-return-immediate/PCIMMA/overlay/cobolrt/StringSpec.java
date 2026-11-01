// generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`; do not edit
package com.gitgalaxy.modernized.cobolrt;

/**
 * Declarative COBOL String Manipulation specification (STRING, UNSTRING, INSPECT).
 *
 * <p>Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06).
 * Follows the table-driven code generation pattern established by CicsSpec.java (#4586, #4608).
 */
public final class StringSpec {
    private StringSpec() {
    }

    // Statements
    public static final int STATEMENT_STRING = 0;
    public static final int STATEMENT_UNSTRING = 1;
    public static final int STATEMENT_INSPECT = 2;

    // INSPECT evaluation modes
    public static final int INSPECT_CHARACTERS = 0;
    public static final int INSPECT_ALL = 1;
    public static final int INSPECT_LEADING = 2;
    public static final int INSPECT_FIRST = 3;

    // INSPECT phrase types
    public static final int PHRASE_TALLYING = 0;
    public static final int PHRASE_REPLACING = 1;
    public static final int PHRASE_CONVERTING = 2;

    /** COBOL standard clause name for inspect mode. */
    public static String inspectModeName(int mode) {
        return switch (mode) {
            case INSPECT_CHARACTERS -> "CHARACTERS";
            case INSPECT_ALL -> "ALL";
            case INSPECT_LEADING -> "LEADING";
            case INSPECT_FIRST -> "FIRST";
            default -> "UNKNOWN";
        };
    }

    /** Name of the inspect phrase type. */
    public static String phraseTypeName(int type) {
        return switch (type) {
            case PHRASE_TALLYING -> "TALLYING";
            case PHRASE_REPLACING -> "REPLACING";
            case PHRASE_CONVERTING -> "CONVERTING";
            default -> "UNKNOWN";
        };
    }

    /** Returns true if 1-based pointer is within bounds [1, length]. */
    public static boolean isPointerValid(int pointer, int length) {
        return pointer >= 1 && pointer <= length;
    }

    /** Get registered rule ID from key. */
    public static String ruleId(String key) {
        return switch (key) {
            case "RT-CBL-COUNTER-NONDIGIT-REFUSED" -> "RT-CBL-COUNTER-NONDIGIT-REFUSED";
            case "RT-CBL-INSPECT" -> "RT-CBL-INSPECT";
            case "RT-CBL-STRING" -> "RT-CBL-STRING";
            case "RT-CBL-UNSTRING" -> "RT-CBL-UNSTRING";
            default -> "UNKNOWN";
        };
    }
}
