// generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`; do not edit
package __PACKAGE__.cobolrt;

/**
 * Declarative COBOL Numeric Editing specification (PICTURE clause editing, symbols, and shapes).
 *
 * <p>Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06),
 * Chapter "PICTURE clause" (Editing rules, Simple insertion, Special insertion,
 * Fixed insertion, Floating insertion, Zero suppression and replacement).
 * Follows the table-driven code generation pattern established by CicsSpec.java (#4586, #4608).
 */
public final class EditingSpec {
    private EditingSpec() {
    }

    // Editing categories
    public static final int CATEGORY_SIMPLE_INSERTION = 0;
    public static final int CATEGORY_SPECIAL_INSERTION = 1;
    public static final int CATEGORY_FIXED_INSERTION = 2;
    public static final int CATEGORY_FLOATING_INSERTION = 3;
    public static final int CATEGORY_ZERO_SUPPRESSION = 4;
    public static final int CATEGORY_DIGIT = 5;
    public static final int CATEGORY_IMPLICIT = 6;

    /** Standard COBOL editing symbols recognized in PICTURE clauses. */
    public static final String EDITING_SYMBOLS = "9Z*.,+-CRDBV0/$";

    /** Category name for diagnostics and evidence logging. */
    public static String categoryName(int cat) {
        return switch (cat) {
            case CATEGORY_SIMPLE_INSERTION -> "SIMPLE_INSERTION";
            case CATEGORY_SPECIAL_INSERTION -> "SPECIAL_INSERTION";
            case CATEGORY_FIXED_INSERTION -> "FIXED_INSERTION";
            case CATEGORY_FLOATING_INSERTION -> "FLOATING_INSERTION";
            case CATEGORY_ZERO_SUPPRESSION -> "ZERO_SUPPRESSION";
            case CATEGORY_DIGIT -> "DIGIT";
            case CATEGORY_IMPLICIT -> "IMPLICIT";
            default -> "UNKNOWN";
        };
    }

    /** Classification of an editing symbol into its functional category. */
    public static int symbolCategory(char symbol) {
        return switch (symbol) {
            case ',', 'B', '0', '/' -> CATEGORY_SIMPLE_INSERTION;
            case '.' -> CATEGORY_SPECIAL_INSERTION;
            case '+', '-', '$' -> CATEGORY_FIXED_INSERTION;
            case 'Z', '*' -> CATEGORY_ZERO_SUPPRESSION;
            case '9' -> CATEGORY_DIGIT;
            case 'V' -> CATEGORY_IMPLICIT;
            default -> -1;
        };
    }

    /** Returns true if character is a standard COBOL PICTURE editing symbol. */
    public static boolean isEditingSymbol(char ch) {
        return EDITING_SYMBOLS.indexOf(ch) != -1;
    }

    /** Returns true if character is a candidate for floating insertion. */
    public static boolean isFloatingCandidate(char ch) {
        return ch == '$' || ch == '+' || ch == '-';
    }

    /** Returns true if character is a zero-suppression symbol. */
    public static boolean isSuppressionSymbol(char ch) {
        return ch == 'Z' || ch == '*';
    }

    /** Get registered rule ID from key. */
    public static String ruleId(String key) {
        return switch (key) {
            case "RT-EDIT-CURRENCY-SIGN" -> "RT-EDIT-CURRENCY-SIGN";
            case "RT-EDIT-FLOATING-INSERTION" -> "RT-EDIT-FLOATING-INSERTION";
            case "RT-EDIT-NONDIGIT-SENDER" -> "RT-EDIT-NONDIGIT-SENDER";
            case "RT-EDIT-NUMERIC-EDITING" -> "RT-EDIT-NUMERIC-EDITING";
            case "RT-EDIT-PICTURE-SHAPE" -> "RT-EDIT-PICTURE-SHAPE";
            default -> "UNKNOWN";
        };
    }
}
