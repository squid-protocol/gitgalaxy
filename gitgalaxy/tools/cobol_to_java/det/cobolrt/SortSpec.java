// generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`; do not edit
package __PACKAGE__.cobolrt;

/**
 * Declarative COBOL SORT and MERGE specification (collating sequences, keys, and procedures).
 *
 * <p>Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06),
 * Chapters: "SORT statement", "MERGE statement", "RELEASE statement", "RETURN statement",
 * "ALPHABET clause", "PROGRAM COLLATING SEQUENCE clause".
 * Follows the table-driven code generation pattern established by CicsSpec.java (#4586, #4608).
 */
public final class SortSpec {
    private SortSpec() {
    }

    // Sort directions
    public static final int DIRECTION_ASCENDING = 1;
    public static final int DIRECTION_DESCENDING = 2;

    // Collating sequence modes
    public static final int COLLATING_NATIVE = 0;
    public static final int COLLATING_EBCDIC = 1;
    public static final int COLLATING_LITERAL = 2;

    // Procedure phrases
    public static final int PHRASE_USING = 1;
    public static final int PHRASE_GIVING = 2;
    public static final int PHRASE_INPUT_PROCEDURE = 3;
    public static final int PHRASE_OUTPUT_PROCEDURE = 4;

    // SORT-RETURN special register values
    public static final int SORT_RETURN_SUCCESS = 0;
    public static final int SORT_RETURN_ABORT = 16;

    /** Name of direction. */
    public static String directionName(int direction) {
        return switch (direction) {
            case DIRECTION_ASCENDING -> "ASCENDING";
            case DIRECTION_DESCENDING -> "DESCENDING";
            default -> "UNKNOWN";
        };
    }

    /** Name of collating sequence mode. */
    public static String collatingModeName(int mode) {
        return switch (mode) {
            case COLLATING_NATIVE -> "NATIVE";
            case COLLATING_EBCDIC -> "EBCDIC";
            case COLLATING_LITERAL -> "LITERAL";
            default -> "UNKNOWN";
        };
    }

    /** Name of phrase type. */
    public static String phraseName(int phrase) {
        return switch (phrase) {
            case PHRASE_USING -> "USING";
            case PHRASE_GIVING -> "GIVING";
            case PHRASE_INPUT_PROCEDURE -> "INPUT_PROCEDURE";
            case PHRASE_OUTPUT_PROCEDURE -> "OUTPUT_PROCEDURE";
            default -> "UNKNOWN";
        };
    }

    /** Returns true if SORT-RETURN value requests terminating the sort (16). */
    public static boolean isAbortReturn(int sortReturn) {
        return sortReturn == SORT_RETURN_ABORT;
    }

    /** Get registered rule ID from key. */
    public static String ruleId(String key) {
        return switch (key) {
            case "RT-SORT-ALPHABET" -> "RT-SORT-ALPHABET";
            case "RT-SORT-COLLATING-DISAGREE-REFUSED" -> "RT-SORT-COLLATING-DISAGREE-REFUSED";
            case "RT-SORT-COLLATING-RELATION" -> "RT-SORT-COLLATING-RELATION";
            case "RT-SORT-KEYS" -> "RT-SORT-KEYS";
            case "RT-SORT-PROCEDURES" -> "RT-SORT-PROCEDURES";
            case "RT-SORT-RETURN" -> "RT-SORT-RETURN";
            case "RT-SORT-STABLE-ORDER" -> "RT-SORT-STABLE-ORDER";
            default -> "UNKNOWN";
        };
    }
}
