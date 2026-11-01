// generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`; do not edit
package com.gitgalaxy.modernized.cobolrt;

/**
 * The COBOL relation condition and comparison specification (#4712, epic #4710).
 * Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06),
 * Chapter "Conditional expressions" -> "Relation conditions".
 */
public final class CompareSpec {
    private CompareSpec() {
    }

    public static final int MODE_NUMERIC = 0;
    public static final int MODE_FLOAT = 1;
    public static final int MODE_NONNUMERIC = 2;
    public static final int MODE_NUMERIC_WITH_NONNUMERIC = 3;
    public static final int MODE_FLOAT_REFUSED = 4;

    /** The comparison evaluation mode between two operand kinds. */
    public static int comparisonMode(Field.Kind left, Field.Kind right) {
        return switch (left) {
            case GROUP -> switch (right) {
                case GROUP -> MODE_NONNUMERIC;
                case ALPHANUMERIC -> MODE_NONNUMERIC;
                case ALPHABETIC -> MODE_NONNUMERIC;
                case NUMERIC_DISPLAY -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_PACKED -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_BINARY -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_EDITED -> MODE_NONNUMERIC;
                case ALPHANUMERIC_EDITED -> MODE_NONNUMERIC;
                case NUMERIC_FLOAT -> MODE_FLOAT_REFUSED;
            };
            case ALPHANUMERIC -> switch (right) {
                case GROUP -> MODE_NONNUMERIC;
                case ALPHANUMERIC -> MODE_NONNUMERIC;
                case ALPHABETIC -> MODE_NONNUMERIC;
                case NUMERIC_DISPLAY -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_PACKED -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_BINARY -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_EDITED -> MODE_NONNUMERIC;
                case ALPHANUMERIC_EDITED -> MODE_NONNUMERIC;
                case NUMERIC_FLOAT -> MODE_FLOAT_REFUSED;
            };
            case ALPHABETIC -> switch (right) {
                case GROUP -> MODE_NONNUMERIC;
                case ALPHANUMERIC -> MODE_NONNUMERIC;
                case ALPHABETIC -> MODE_NONNUMERIC;
                case NUMERIC_DISPLAY -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_PACKED -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_BINARY -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_EDITED -> MODE_NONNUMERIC;
                case ALPHANUMERIC_EDITED -> MODE_NONNUMERIC;
                case NUMERIC_FLOAT -> MODE_FLOAT_REFUSED;
            };
            case NUMERIC_DISPLAY -> switch (right) {
                case GROUP -> MODE_NUMERIC_WITH_NONNUMERIC;
                case ALPHANUMERIC -> MODE_NUMERIC_WITH_NONNUMERIC;
                case ALPHABETIC -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_DISPLAY -> MODE_NUMERIC;
                case NUMERIC_PACKED -> MODE_NUMERIC;
                case NUMERIC_BINARY -> MODE_NUMERIC;
                case NUMERIC_EDITED -> MODE_NUMERIC_WITH_NONNUMERIC;
                case ALPHANUMERIC_EDITED -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_FLOAT -> MODE_FLOAT;
            };
            case NUMERIC_PACKED -> switch (right) {
                case GROUP -> MODE_NUMERIC_WITH_NONNUMERIC;
                case ALPHANUMERIC -> MODE_NUMERIC_WITH_NONNUMERIC;
                case ALPHABETIC -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_DISPLAY -> MODE_NUMERIC;
                case NUMERIC_PACKED -> MODE_NUMERIC;
                case NUMERIC_BINARY -> MODE_NUMERIC;
                case NUMERIC_EDITED -> MODE_NUMERIC_WITH_NONNUMERIC;
                case ALPHANUMERIC_EDITED -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_FLOAT -> MODE_FLOAT;
            };
            case NUMERIC_BINARY -> switch (right) {
                case GROUP -> MODE_NUMERIC_WITH_NONNUMERIC;
                case ALPHANUMERIC -> MODE_NUMERIC_WITH_NONNUMERIC;
                case ALPHABETIC -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_DISPLAY -> MODE_NUMERIC;
                case NUMERIC_PACKED -> MODE_NUMERIC;
                case NUMERIC_BINARY -> MODE_NUMERIC;
                case NUMERIC_EDITED -> MODE_NUMERIC_WITH_NONNUMERIC;
                case ALPHANUMERIC_EDITED -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_FLOAT -> MODE_FLOAT;
            };
            case NUMERIC_EDITED -> switch (right) {
                case GROUP -> MODE_NONNUMERIC;
                case ALPHANUMERIC -> MODE_NONNUMERIC;
                case ALPHABETIC -> MODE_NONNUMERIC;
                case NUMERIC_DISPLAY -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_PACKED -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_BINARY -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_EDITED -> MODE_NONNUMERIC;
                case ALPHANUMERIC_EDITED -> MODE_NONNUMERIC;
                case NUMERIC_FLOAT -> MODE_FLOAT_REFUSED;
            };
            case ALPHANUMERIC_EDITED -> switch (right) {
                case GROUP -> MODE_NONNUMERIC;
                case ALPHANUMERIC -> MODE_NONNUMERIC;
                case ALPHABETIC -> MODE_NONNUMERIC;
                case NUMERIC_DISPLAY -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_PACKED -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_BINARY -> MODE_NUMERIC_WITH_NONNUMERIC;
                case NUMERIC_EDITED -> MODE_NONNUMERIC;
                case ALPHANUMERIC_EDITED -> MODE_NONNUMERIC;
                case NUMERIC_FLOAT -> MODE_FLOAT_REFUSED;
            };
            case NUMERIC_FLOAT -> switch (right) {
                case GROUP -> MODE_FLOAT_REFUSED;
                case ALPHANUMERIC -> MODE_FLOAT_REFUSED;
                case ALPHABETIC -> MODE_FLOAT_REFUSED;
                case NUMERIC_DISPLAY -> MODE_FLOAT;
                case NUMERIC_PACKED -> MODE_FLOAT;
                case NUMERIC_BINARY -> MODE_FLOAT;
                case NUMERIC_EDITED -> MODE_FLOAT_REFUSED;
                case ALPHANUMERIC_EDITED -> MODE_FLOAT_REFUSED;
                case NUMERIC_FLOAT -> MODE_FLOAT;
            };
        };
    }

    /** The comparison mode name for diagnostic output and evidence reports. */
    public static String modeName(int mode) {
        return switch (mode) {
            case MODE_NUMERIC -> "NUMERIC";
            case MODE_FLOAT -> "FLOAT";
            case MODE_NONNUMERIC -> "NONNUMERIC";
            case MODE_NUMERIC_WITH_NONNUMERIC -> "NUMERIC_WITH_NONNUMERIC";
            case MODE_FLOAT_REFUSED -> "FLOAT_REFUSED";
            default -> "UNKNOWN";
        };
    }

    /** The catalogued rule ID governing a comparison between two kinds. */
    public static String ruleId(Field.Kind left, Field.Kind right) {
        return switch (left) {
            case GROUP -> switch (right) {
                case GROUP -> "RT-CBL-COMPARE-NONNUMERIC";
                case ALPHANUMERIC -> "RT-CBL-COMPARE-NONNUMERIC";
                case ALPHABETIC -> "RT-CBL-COMPARE-NONNUMERIC";
                case NUMERIC_DISPLAY -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_PACKED -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_BINARY -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_EDITED -> "RT-CBL-COMPARE-NONNUMERIC";
                case ALPHANUMERIC_EDITED -> "RT-CBL-COMPARE-NONNUMERIC";
                case NUMERIC_FLOAT -> "RT-CBL-COMPARE-FLOAT";
            };
            case ALPHANUMERIC -> switch (right) {
                case GROUP -> "RT-CBL-COMPARE-NONNUMERIC";
                case ALPHANUMERIC -> "RT-CBL-COMPARE-NONNUMERIC";
                case ALPHABETIC -> "RT-CBL-COMPARE-NONNUMERIC";
                case NUMERIC_DISPLAY -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_PACKED -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_BINARY -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_EDITED -> "RT-CBL-COMPARE-NONNUMERIC";
                case ALPHANUMERIC_EDITED -> "RT-CBL-COMPARE-NONNUMERIC";
                case NUMERIC_FLOAT -> "RT-CBL-COMPARE-FLOAT";
            };
            case ALPHABETIC -> switch (right) {
                case GROUP -> "RT-CBL-COMPARE-NONNUMERIC";
                case ALPHANUMERIC -> "RT-CBL-COMPARE-NONNUMERIC";
                case ALPHABETIC -> "RT-CBL-COMPARE-NONNUMERIC";
                case NUMERIC_DISPLAY -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_PACKED -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_BINARY -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_EDITED -> "RT-CBL-COMPARE-NONNUMERIC";
                case ALPHANUMERIC_EDITED -> "RT-CBL-COMPARE-NONNUMERIC";
                case NUMERIC_FLOAT -> "RT-CBL-COMPARE-FLOAT";
            };
            case NUMERIC_DISPLAY -> switch (right) {
                case GROUP -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case ALPHANUMERIC -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case ALPHABETIC -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_DISPLAY -> "RT-CBL-COMPARE-NUMERIC";
                case NUMERIC_PACKED -> "RT-CBL-COMPARE-NUMERIC";
                case NUMERIC_BINARY -> "RT-CBL-COMPARE-NUMERIC";
                case NUMERIC_EDITED -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case ALPHANUMERIC_EDITED -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_FLOAT -> "RT-CBL-COMPARE-FLOAT";
            };
            case NUMERIC_PACKED -> switch (right) {
                case GROUP -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case ALPHANUMERIC -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case ALPHABETIC -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_DISPLAY -> "RT-CBL-COMPARE-NUMERIC";
                case NUMERIC_PACKED -> "RT-CBL-COMPARE-NUMERIC";
                case NUMERIC_BINARY -> "RT-CBL-COMPARE-NUMERIC";
                case NUMERIC_EDITED -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case ALPHANUMERIC_EDITED -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_FLOAT -> "RT-CBL-COMPARE-FLOAT";
            };
            case NUMERIC_BINARY -> switch (right) {
                case GROUP -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case ALPHANUMERIC -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case ALPHABETIC -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_DISPLAY -> "RT-CBL-COMPARE-NUMERIC";
                case NUMERIC_PACKED -> "RT-CBL-COMPARE-NUMERIC";
                case NUMERIC_BINARY -> "RT-CBL-COMPARE-NUMERIC";
                case NUMERIC_EDITED -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case ALPHANUMERIC_EDITED -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_FLOAT -> "RT-CBL-COMPARE-FLOAT";
            };
            case NUMERIC_EDITED -> switch (right) {
                case GROUP -> "RT-CBL-COMPARE-NONNUMERIC";
                case ALPHANUMERIC -> "RT-CBL-COMPARE-NONNUMERIC";
                case ALPHABETIC -> "RT-CBL-COMPARE-NONNUMERIC";
                case NUMERIC_DISPLAY -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_PACKED -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_BINARY -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_EDITED -> "RT-CBL-COMPARE-NONNUMERIC";
                case ALPHANUMERIC_EDITED -> "RT-CBL-COMPARE-NONNUMERIC";
                case NUMERIC_FLOAT -> "RT-CBL-COMPARE-FLOAT";
            };
            case ALPHANUMERIC_EDITED -> switch (right) {
                case GROUP -> "RT-CBL-COMPARE-NONNUMERIC";
                case ALPHANUMERIC -> "RT-CBL-COMPARE-NONNUMERIC";
                case ALPHABETIC -> "RT-CBL-COMPARE-NONNUMERIC";
                case NUMERIC_DISPLAY -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_PACKED -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_BINARY -> "RT-CBL-COMPARE-NUMERIC-WITH-NONNUMERIC";
                case NUMERIC_EDITED -> "RT-CBL-COMPARE-NONNUMERIC";
                case ALPHANUMERIC_EDITED -> "RT-CBL-COMPARE-NONNUMERIC";
                case NUMERIC_FLOAT -> "RT-CBL-COMPARE-FLOAT";
            };
            case NUMERIC_FLOAT -> switch (right) {
                case GROUP -> "RT-CBL-COMPARE-FLOAT";
                case ALPHANUMERIC -> "RT-CBL-COMPARE-FLOAT";
                case ALPHABETIC -> "RT-CBL-COMPARE-FLOAT";
                case NUMERIC_DISPLAY -> "RT-CBL-COMPARE-FLOAT";
                case NUMERIC_PACKED -> "RT-CBL-COMPARE-FLOAT";
                case NUMERIC_BINARY -> "RT-CBL-COMPARE-FLOAT";
                case NUMERIC_EDITED -> "RT-CBL-COMPARE-FLOAT";
                case ALPHANUMERIC_EDITED -> "RT-CBL-COMPARE-FLOAT";
                case NUMERIC_FLOAT -> "RT-CBL-COMPARE-FLOAT";
            };
        };
    }

    /** Whether both comparands are numeric (algebraic comparison). */
    public static boolean isNumericComparison(Field.Kind left, Field.Kind right) {
        int mode = comparisonMode(left, right);
        return mode == MODE_NUMERIC || mode == MODE_FLOAT;
    }

    /** Whether one operand must be converted to unsigned digits before comparison. */
    public static boolean requiresDigitConversion(Field.Kind left, Field.Kind right) {
        return comparisonMode(left, right) == MODE_NUMERIC_WITH_NONNUMERIC;
    }

    /** Byte-by-byte comparison of two byte arrays, padding the shorter with spaceByte. */
    public static int compareBytes(byte[] a, byte[] b, byte spaceByte) {
        int n = Math.max(a.length, b.length);
        for (int i = 0; i < n; i++) {
            int x = (i < a.length ? a[i] : spaceByte) & 0xFF;
            int y = (i < b.length ? b[i] : spaceByte) & 0xFF;
            if (x != y) return x < y ? -1 : 1;
        }
        return 0;
    }
}
