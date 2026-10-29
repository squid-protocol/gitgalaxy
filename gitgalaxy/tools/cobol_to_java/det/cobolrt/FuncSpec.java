// generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`; do not edit
package __PACKAGE__.cobolrt;

/**
 * Declarative COBOL Intrinsic Functions specification.
 *
 * <p>Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06).
 * Follows the table-driven code generation pattern established by CicsSpec.java (#4586, #4608).
 */
public final class FuncSpec {
    private FuncSpec() {
    }

    public static final int CATEGORY_STRING = 0;
    public static final int CATEGORY_MATH = 1;
    public static final int CATEGORY_PARSING = 2;
    public static final int CATEGORY_DATE_TIME = 3;
    public static final int CATEGORY_IO = 4;

    /** Category name for diagnostics and evidence logging. */
    public static String categoryName(int cat) {
        return switch (cat) {
            case CATEGORY_STRING -> "STRING";
            case CATEGORY_MATH -> "MATH";
            case CATEGORY_PARSING -> "PARSING";
            case CATEGORY_DATE_TIME -> "DATE_TIME";
            case CATEGORY_IO -> "IO";
            default -> "UNKNOWN";
        };
    }

    /** Functional classification of an intrinsic function. */
    public static int functionCategory(String funcName) {
        return switch (funcName) {
            case "UPPER-CASE", "LOWER-CASE", "REVERSE", "TRIM" -> CATEGORY_STRING;
            case "MOD", "REM", "INTEGER", "INTEGER-PART", "ABS", "MIN", "MAX", "RANDOM" -> CATEGORY_MATH;
            case "NUMVAL", "NUMVAL-C", "TEST-NUMVAL", "TEST-NUMVAL-C" -> CATEGORY_PARSING;
            case "CURRENT-DATE", "INTEGER-OF-DATE", "DATE-OF-INTEGER", "ACCEPT-DATE" -> CATEGORY_DATE_TIME;
            case "ACCEPT-SYSIN" -> CATEGORY_IO;
            default -> -1;
        };
    }

    /** Get registered rule ID from key. */
    public static String ruleId(String key) {
        return switch (key) {
            case "RT-FUNC-ACCEPT-DATE" -> "RT-FUNC-ACCEPT-DATE";
            case "RT-FUNC-ACCEPT-SYSIN" -> "RT-FUNC-ACCEPT-SYSIN";
            case "RT-FUNC-CASE" -> "RT-FUNC-CASE";
            case "RT-FUNC-CURRENT-DATE" -> "RT-FUNC-CURRENT-DATE";
            case "RT-FUNC-DATE-INTEGER" -> "RT-FUNC-DATE-INTEGER";
            case "RT-FUNC-INTEGER-ABS-MIN-MAX" -> "RT-FUNC-INTEGER-ABS-MIN-MAX";
            case "RT-FUNC-MOD-REM" -> "RT-FUNC-MOD-REM";
            case "RT-FUNC-NUMVAL" -> "RT-FUNC-NUMVAL";
            case "RT-FUNC-RANDOM" -> "RT-FUNC-RANDOM";
            case "RT-FUNC-REVERSE" -> "RT-FUNC-REVERSE";
            case "RT-FUNC-TEST-NUMVAL" -> "RT-FUNC-TEST-NUMVAL";
            case "RT-FUNC-TRIM" -> "RT-FUNC-TRIM";
            default -> "UNKNOWN";
        };
    }
}
