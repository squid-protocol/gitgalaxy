// generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`; do not edit
package __PACKAGE__.cobolrt;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;

/**
 * Declarative COBOL Arithmetic, Rounding, Intermediate Precision, and Size Error specification.
 *
 * <p>Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06).
 * Follows the table-driven code generation pattern established by CicsSpec.java (#4586, #4608).
 */
public final class ArithSpec {
    private ArithSpec() {
    }

    // Rounding modes (IBM Enterprise COBOL ROUNDED / ROUNDED MODE IS ...)
    public static final int ROUND_TRUNCATION = 0;
    public static final int ROUND_NEAREST_AWAY_FROM_ZERO = 1;
    public static final int ROUND_NEAREST_EVEN = 2;
    public static final int ROUND_NEAREST_TOWARD_ZERO = 3;
    public static final int ROUND_TOWARD_GREATER = 4;
    public static final int ROUND_TOWARD_LESSER = 5;
    public static final int ROUND_PROHIBITED = 6;

    public static final int NAN_SCALE = -32768;

    /** Map integer rounding mode to java.math.RoundingMode. */
    public static RoundingMode roundingMode(int mode) {
        return switch (mode) {
            case ROUND_TRUNCATION -> RoundingMode.DOWN;
            case ROUND_NEAREST_AWAY_FROM_ZERO -> RoundingMode.HALF_UP;
            case ROUND_NEAREST_EVEN -> RoundingMode.HALF_EVEN;
            case ROUND_NEAREST_TOWARD_ZERO -> RoundingMode.HALF_DOWN;
            case ROUND_TOWARD_GREATER -> RoundingMode.CEILING;
            case ROUND_TOWARD_LESSER -> RoundingMode.FLOOR;
            case ROUND_PROHIBITED -> RoundingMode.UNNECESSARY;
            default -> throw new IllegalArgumentException("Unknown rounding mode: " + mode);
        };
    }

    /** COBOL standard clause name for rounding mode. */
    public static String modeName(int mode) {
        return switch (mode) {
            case ROUND_TRUNCATION -> "TRUNCATION";
            case ROUND_NEAREST_AWAY_FROM_ZERO -> "NEAREST-AWAY-FROM-ZERO";
            case ROUND_NEAREST_EVEN -> "NEAREST-EVEN";
            case ROUND_NEAREST_TOWARD_ZERO -> "NEAREST-TOWARD-ZERO";
            case ROUND_TOWARD_GREATER -> "TOWARD-GREATER";
            case ROUND_TOWARD_LESSER -> "TOWARD-LESSER";
            case ROUND_PROHIBITED -> "PROHIBITED";
            default -> "UNKNOWN";
        };
    }

    /** Intermediate division quotient scale: 38 + max(scaleA - scaleB, 0). */
    public static int divideIntermediateScale(int scaleA, int scaleB) {
        return 38 + Math.max(scaleA - scaleB, 0);
    }

    /** DIVIDE ... REMAINDER formula: dividend - (quotient.setScale(scale, DOWN) * divisor). */
    public static BigDecimal divideRemainder(BigDecimal a, BigDecimal q, BigDecimal b, int scale) {
        if (q.scale() == NAN_SCALE) {
            return q;
        }
        return a.subtract(q.setScale(scale, RoundingMode.DOWN).multiply(b));
    }

    /** True if scaled value exceeds the receiver's PICTURE integer capacity. */
    public static boolean isOverflow(BigDecimal value, int digits, int scale) {
        BigDecimal v = value.setScale(scale, RoundingMode.DOWN);
        return v.unscaledValue().abs().compareTo(BigInteger.TEN.pow(digits)) >= 0;
    }

    /** Get registered rule ID from key. */
    public static String ruleId(String key) {
        return switch (key) {
            case "RT-CBL-DECIMAL-CONSTANT-SCALE" -> "RT-CBL-DECIMAL-CONSTANT-SCALE";
            case "RT-CBL-DIVIDE-IN-FUNCTION-ARGUMENT" -> "RT-CBL-DIVIDE-IN-FUNCTION-ARGUMENT";
            case "RT-CBL-DIVIDE-INTERMEDIATE" -> "RT-CBL-DIVIDE-INTERMEDIATE";
            case "RT-CBL-DIVIDE-REMAINDER" -> "RT-CBL-DIVIDE-REMAINDER";
            case "RT-CBL-EXPONENTIATION" -> "RT-CBL-EXPONENTIATION";
            case "RT-CBL-OSVS-INTERMEDIATE-ALIGN" -> "RT-CBL-OSVS-INTERMEDIATE-ALIGN";
            case "RT-CBL-SIZE-ERROR" -> "RT-CBL-SIZE-ERROR";
            case "RT-CBL-STORE-RESULT" -> "RT-CBL-STORE-RESULT";
            case "RT-CBL-UNSIGNED-BINARY-ABSOLUTE" -> "RT-CBL-UNSIGNED-BINARY-ABSOLUTE";
            case "RT-CBL-ZERO-DIVISOR-NAN" -> "RT-CBL-ZERO-DIVISOR-NAN";
            default -> "UNKNOWN";
        };
    }
}
