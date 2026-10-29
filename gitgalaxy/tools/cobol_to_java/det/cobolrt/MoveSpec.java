// generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`; do not edit
package __PACKAGE__.cobolrt;

/**
 * The COBOL MOVE statement specification and permissible moves matrix (#4712, epic #4710).
 * Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06),
 * Chapter "MOVE statement" (Elementary moves, De-editing, Table 43: Permissible moves).
 */
public final class MoveSpec {
    private MoveSpec() {
    }

    public static final int GROUP = 0;
    public static final int ALNUM = 1;
    public static final int NUMERIC = 2;
    public static final int NUM_EDITED = 3;
    public static final int ALNUM_EDITED = 4;

    /** Map a Field.Kind to its runtime category (0: GROUP, 1: ALNUM, 2: NUMERIC, 3: NUM_EDITED, 4: ALNUM_EDITED). */
    public static int category(Field.Kind kind) {
        return switch (kind) {
            case GROUP -> GROUP;
            case ALPHANUMERIC -> ALNUM;
            case ALPHABETIC -> ALNUM;
            case NUMERIC_DISPLAY -> NUMERIC;
            case NUMERIC_PACKED -> NUMERIC;
            case NUMERIC_BINARY -> NUMERIC;
            case NUMERIC_EDITED -> NUM_EDITED;
            case ALPHANUMERIC_EDITED -> ALNUM_EDITED;
            case NUMERIC_FLOAT -> NUMERIC;
        };
    }

    /** The category name for diagnostic output and evidence reports. */
    public static String categoryName(int category) {
        return switch (category) {
            case GROUP -> "GROUP";
            case ALNUM -> "ALNUM";
            case NUMERIC -> "NUMERIC";
            case NUM_EDITED -> "NUM_EDITED";
            case ALNUM_EDITED -> "ALNUM_EDITED";
            default -> "UNKNOWN";
        };
    }

    /** Whether an elementary or group move between two kinds is permissible under IBM Enterprise COBOL rules. */
    public static boolean isPermissible(Field.Kind from, Field.Kind to) {
        return switch (from) {
            case GROUP -> switch (to) {
                case GROUP -> true;
                case ALPHANUMERIC -> true;
                case ALPHABETIC -> true;
                case NUMERIC_DISPLAY -> true;
                case NUMERIC_PACKED -> true;
                case NUMERIC_BINARY -> true;
                case NUMERIC_EDITED -> true;
                case ALPHANUMERIC_EDITED -> true;
                case NUMERIC_FLOAT -> true;
            };
            case ALPHANUMERIC -> switch (to) {
                case GROUP -> true;
                case ALPHANUMERIC -> true;
                case ALPHABETIC -> true;
                case NUMERIC_DISPLAY -> true;
                case NUMERIC_PACKED -> true;
                case NUMERIC_BINARY -> true;
                case NUMERIC_EDITED -> true;
                case ALPHANUMERIC_EDITED -> true;
                case NUMERIC_FLOAT -> false;
            };
            case ALPHABETIC -> switch (to) {
                case GROUP -> true;
                case ALPHANUMERIC -> true;
                case ALPHABETIC -> true;
                case NUMERIC_DISPLAY -> false;
                case NUMERIC_PACKED -> false;
                case NUMERIC_BINARY -> false;
                case NUMERIC_EDITED -> false;
                case ALPHANUMERIC_EDITED -> true;
                case NUMERIC_FLOAT -> false;
            };
            case NUMERIC_DISPLAY -> switch (to) {
                case GROUP -> true;
                case ALPHANUMERIC -> true;
                case ALPHABETIC -> false;
                case NUMERIC_DISPLAY -> true;
                case NUMERIC_PACKED -> true;
                case NUMERIC_BINARY -> true;
                case NUMERIC_EDITED -> true;
                case ALPHANUMERIC_EDITED -> true;
                case NUMERIC_FLOAT -> true;
            };
            case NUMERIC_PACKED -> switch (to) {
                case GROUP -> true;
                case ALPHANUMERIC -> true;
                case ALPHABETIC -> false;
                case NUMERIC_DISPLAY -> true;
                case NUMERIC_PACKED -> true;
                case NUMERIC_BINARY -> true;
                case NUMERIC_EDITED -> true;
                case ALPHANUMERIC_EDITED -> true;
                case NUMERIC_FLOAT -> true;
            };
            case NUMERIC_BINARY -> switch (to) {
                case GROUP -> true;
                case ALPHANUMERIC -> true;
                case ALPHABETIC -> false;
                case NUMERIC_DISPLAY -> true;
                case NUMERIC_PACKED -> true;
                case NUMERIC_BINARY -> true;
                case NUMERIC_EDITED -> true;
                case ALPHANUMERIC_EDITED -> true;
                case NUMERIC_FLOAT -> true;
            };
            case NUMERIC_EDITED -> switch (to) {
                case GROUP -> true;
                case ALPHANUMERIC -> true;
                case ALPHABETIC -> false;
                case NUMERIC_DISPLAY -> true;
                case NUMERIC_PACKED -> true;
                case NUMERIC_BINARY -> true;
                case NUMERIC_EDITED -> true;
                case ALPHANUMERIC_EDITED -> true;
                case NUMERIC_FLOAT -> true;
            };
            case ALPHANUMERIC_EDITED -> switch (to) {
                case GROUP -> true;
                case ALPHANUMERIC -> true;
                case ALPHABETIC -> true;
                case NUMERIC_DISPLAY -> true;
                case NUMERIC_PACKED -> true;
                case NUMERIC_BINARY -> true;
                case NUMERIC_EDITED -> true;
                case ALPHANUMERIC_EDITED -> true;
                case NUMERIC_FLOAT -> false;
            };
            case NUMERIC_FLOAT -> switch (to) {
                case GROUP -> true;
                case ALPHANUMERIC -> false;
                case ALPHABETIC -> false;
                case NUMERIC_DISPLAY -> true;
                case NUMERIC_PACKED -> true;
                case NUMERIC_BINARY -> true;
                case NUMERIC_EDITED -> true;
                case ALPHANUMERIC_EDITED -> false;
                case NUMERIC_FLOAT -> true;
            };
        };
    }

    /** The catalogued rule ID governing a MOVE between two kinds. */
    public static String ruleId(Field.Kind from, Field.Kind to) {
        return switch (from) {
            case GROUP -> switch (to) {
                case GROUP -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHANUMERIC -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHABETIC -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_DISPLAY -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_PACKED -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_BINARY -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_EDITED -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHANUMERIC_EDITED -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_FLOAT -> "RT-CBL-MOVE-ELEMENTARY";
            };
            case ALPHANUMERIC -> switch (to) {
                case GROUP -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHANUMERIC -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHABETIC -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_DISPLAY -> "RT-CBL-MOVE-ALPHANUMERIC-TO-NUMERIC";
                case NUMERIC_PACKED -> "RT-CBL-MOVE-ALPHANUMERIC-TO-NUMERIC";
                case NUMERIC_BINARY -> "RT-CBL-MOVE-ALPHANUMERIC-TO-NUMERIC";
                case NUMERIC_EDITED -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHANUMERIC_EDITED -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_FLOAT -> "RT-CBL-MOVE-FLOAT";
            };
            case ALPHABETIC -> switch (to) {
                case GROUP -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHANUMERIC -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHABETIC -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_DISPLAY -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_PACKED -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_BINARY -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_EDITED -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHANUMERIC_EDITED -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_FLOAT -> "RT-CBL-MOVE-FLOAT";
            };
            case NUMERIC_DISPLAY -> switch (to) {
                case GROUP -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHANUMERIC -> "RT-CBL-MOVE-NUMERIC-TO-ALPHANUMERIC";
                case ALPHABETIC -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_DISPLAY -> "RT-CBL-MOVE-SAME-ZONED-SHAPE";
                case NUMERIC_PACKED -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_BINARY -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_EDITED -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHANUMERIC_EDITED -> "RT-CBL-MOVE-NUMERIC-TO-ALPHANUMERIC";
                case NUMERIC_FLOAT -> "RT-CBL-MOVE-FLOAT";
            };
            case NUMERIC_PACKED -> switch (to) {
                case GROUP -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHANUMERIC -> "RT-CBL-MOVE-NUMERIC-TO-ALPHANUMERIC";
                case ALPHABETIC -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_DISPLAY -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_PACKED -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_BINARY -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_EDITED -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHANUMERIC_EDITED -> "RT-CBL-MOVE-NUMERIC-TO-ALPHANUMERIC";
                case NUMERIC_FLOAT -> "RT-CBL-MOVE-FLOAT";
            };
            case NUMERIC_BINARY -> switch (to) {
                case GROUP -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHANUMERIC -> "RT-CBL-MOVE-NUMERIC-TO-ALPHANUMERIC";
                case ALPHABETIC -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_DISPLAY -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_PACKED -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_BINARY -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_EDITED -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHANUMERIC_EDITED -> "RT-CBL-MOVE-NUMERIC-TO-ALPHANUMERIC";
                case NUMERIC_FLOAT -> "RT-CBL-MOVE-FLOAT";
            };
            case NUMERIC_EDITED -> switch (to) {
                case GROUP -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHANUMERIC -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHABETIC -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_DISPLAY -> "RT-CBL-MOVE-DEEDIT";
                case NUMERIC_PACKED -> "RT-CBL-MOVE-DEEDIT";
                case NUMERIC_BINARY -> "RT-CBL-MOVE-DEEDIT";
                case NUMERIC_EDITED -> "RT-CBL-MOVE-DEEDIT";
                case ALPHANUMERIC_EDITED -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_FLOAT -> "RT-CBL-MOVE-FLOAT";
            };
            case ALPHANUMERIC_EDITED -> switch (to) {
                case GROUP -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHANUMERIC -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHABETIC -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_DISPLAY -> "RT-CBL-MOVE-ALPHANUMERIC-TO-NUMERIC";
                case NUMERIC_PACKED -> "RT-CBL-MOVE-ALPHANUMERIC-TO-NUMERIC";
                case NUMERIC_BINARY -> "RT-CBL-MOVE-ALPHANUMERIC-TO-NUMERIC";
                case NUMERIC_EDITED -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHANUMERIC_EDITED -> "RT-CBL-MOVE-ELEMENTARY";
                case NUMERIC_FLOAT -> "RT-CBL-MOVE-FLOAT";
            };
            case NUMERIC_FLOAT -> switch (to) {
                case GROUP -> "RT-CBL-MOVE-ELEMENTARY";
                case ALPHANUMERIC -> "RT-CBL-MOVE-FLOAT";
                case ALPHABETIC -> "RT-CBL-MOVE-FLOAT";
                case NUMERIC_DISPLAY -> "RT-CBL-MOVE-FLOAT";
                case NUMERIC_PACKED -> "RT-CBL-MOVE-FLOAT";
                case NUMERIC_BINARY -> "RT-CBL-MOVE-FLOAT";
                case NUMERIC_EDITED -> "RT-CBL-MOVE-FLOAT";
                case ALPHANUMERIC_EDITED -> "RT-CBL-MOVE-FLOAT";
                case NUMERIC_FLOAT -> "RT-CBL-MOVE-FLOAT";
            };
        };
    }

    /** The runtime action name for a MOVE between two kinds. */
    public static String action(Field.Kind from, Field.Kind to) {
        return switch (from) {
            case GROUP -> switch (to) {
                case GROUP -> "GROUP_COPY";
                case ALPHANUMERIC -> "GROUP_COPY";
                case ALPHABETIC -> "GROUP_COPY";
                case NUMERIC_DISPLAY -> "GROUP_COPY";
                case NUMERIC_PACKED -> "GROUP_COPY";
                case NUMERIC_BINARY -> "GROUP_COPY";
                case NUMERIC_EDITED -> "GROUP_COPY";
                case ALPHANUMERIC_EDITED -> "GROUP_COPY";
                case NUMERIC_FLOAT -> "GROUP_COPY";
            };
            case ALPHANUMERIC -> switch (to) {
                case GROUP -> "GROUP_COPY";
                case ALPHANUMERIC -> "ALNUM_STORE";
                case ALPHABETIC -> "ALNUM_STORE";
                case NUMERIC_DISPLAY -> "ALNUM_TO_NUMERIC";
                case NUMERIC_PACKED -> "ALNUM_TO_NUMERIC";
                case NUMERIC_BINARY -> "ALNUM_TO_NUMERIC";
                case NUMERIC_EDITED -> "NUMERIC_EDIT";
                case ALPHANUMERIC_EDITED -> "ALNUM_EDIT_INSERT";
                case NUMERIC_FLOAT -> "FLOAT_REFUSED";
            };
            case ALPHABETIC -> switch (to) {
                case GROUP -> "GROUP_COPY";
                case ALPHANUMERIC -> "ALNUM_STORE";
                case ALPHABETIC -> "ALNUM_STORE";
                case NUMERIC_DISPLAY -> "ILLEGAL";
                case NUMERIC_PACKED -> "ILLEGAL";
                case NUMERIC_BINARY -> "ILLEGAL";
                case NUMERIC_EDITED -> "ILLEGAL";
                case ALPHANUMERIC_EDITED -> "ALNUM_EDIT_INSERT";
                case NUMERIC_FLOAT -> "FLOAT_REFUSED";
            };
            case NUMERIC_DISPLAY -> switch (to) {
                case GROUP -> "GROUP_COPY";
                case ALPHANUMERIC -> "NUMERIC_TO_ALNUM";
                case ALPHABETIC -> "ILLEGAL";
                case NUMERIC_DISPLAY -> "SAME_SHAPE_COPY";
                case NUMERIC_PACKED -> "NUMERIC_STORE";
                case NUMERIC_BINARY -> "NUMERIC_STORE";
                case NUMERIC_EDITED -> "NUMERIC_EDIT";
                case ALPHANUMERIC_EDITED -> "NUMERIC_TO_ALNUM";
                case NUMERIC_FLOAT -> "FLOAT_CONVERT";
            };
            case NUMERIC_PACKED -> switch (to) {
                case GROUP -> "GROUP_COPY";
                case ALPHANUMERIC -> "NUMERIC_TO_ALNUM";
                case ALPHABETIC -> "ILLEGAL";
                case NUMERIC_DISPLAY -> "NUMERIC_STORE";
                case NUMERIC_PACKED -> "NUMERIC_STORE";
                case NUMERIC_BINARY -> "NUMERIC_STORE";
                case NUMERIC_EDITED -> "NUMERIC_EDIT";
                case ALPHANUMERIC_EDITED -> "NUMERIC_TO_ALNUM";
                case NUMERIC_FLOAT -> "FLOAT_CONVERT";
            };
            case NUMERIC_BINARY -> switch (to) {
                case GROUP -> "GROUP_COPY";
                case ALPHANUMERIC -> "NUMERIC_TO_ALNUM";
                case ALPHABETIC -> "ILLEGAL";
                case NUMERIC_DISPLAY -> "NUMERIC_STORE";
                case NUMERIC_PACKED -> "NUMERIC_STORE";
                case NUMERIC_BINARY -> "NUMERIC_STORE";
                case NUMERIC_EDITED -> "NUMERIC_EDIT";
                case ALPHANUMERIC_EDITED -> "NUMERIC_TO_ALNUM";
                case NUMERIC_FLOAT -> "FLOAT_CONVERT";
            };
            case NUMERIC_EDITED -> switch (to) {
                case GROUP -> "GROUP_COPY";
                case ALPHANUMERIC -> "ALNUM_STORE";
                case ALPHABETIC -> "ILLEGAL";
                case NUMERIC_DISPLAY -> "DEEDIT_NUMERIC";
                case NUMERIC_PACKED -> "DEEDIT_NUMERIC";
                case NUMERIC_BINARY -> "DEEDIT_NUMERIC";
                case NUMERIC_EDITED -> "DEEDIT_NUMERIC";
                case ALPHANUMERIC_EDITED -> "ALNUM_STORE";
                case NUMERIC_FLOAT -> "FLOAT_CONVERT";
            };
            case ALPHANUMERIC_EDITED -> switch (to) {
                case GROUP -> "GROUP_COPY";
                case ALPHANUMERIC -> "ALNUM_STORE";
                case ALPHABETIC -> "ALNUM_STORE";
                case NUMERIC_DISPLAY -> "ALNUM_TO_NUMERIC";
                case NUMERIC_PACKED -> "ALNUM_TO_NUMERIC";
                case NUMERIC_BINARY -> "ALNUM_TO_NUMERIC";
                case NUMERIC_EDITED -> "NUMERIC_EDIT";
                case ALPHANUMERIC_EDITED -> "ALNUM_EDIT_INSERT";
                case NUMERIC_FLOAT -> "FLOAT_REFUSED";
            };
            case NUMERIC_FLOAT -> switch (to) {
                case GROUP -> "GROUP_COPY";
                case ALPHANUMERIC -> "FLOAT_REFUSED";
                case ALPHABETIC -> "FLOAT_REFUSED";
                case NUMERIC_DISPLAY -> "FLOAT_CONVERT";
                case NUMERIC_PACKED -> "FLOAT_CONVERT";
                case NUMERIC_BINARY -> "FLOAT_CONVERT";
                case NUMERIC_EDITED -> "FLOAT_CONVERT";
                case ALPHANUMERIC_EDITED -> "FLOAT_REFUSED";
                case NUMERIC_FLOAT -> "FLOAT_CONVERT";
            };
        };
    }

    /**
     * Whether two items of one length hold the same shape (digits, scale, sign, sign position, size)
     * and can be copied by memcpy under rule RT-CBL-MOVE-SAME-ZONED-SHAPE (register C11).
     */
    public static boolean sameZonedShape(Field a, Field b) {
        return a.digits == b.digits && a.scale == b.scale && a.signed == b.signed
                && a.signLeading == b.signLeading && a.signSeparate == b.signSeparate
                && a.len == b.len && a.blankWhenZero == b.blankWhenZero;
    }
}
