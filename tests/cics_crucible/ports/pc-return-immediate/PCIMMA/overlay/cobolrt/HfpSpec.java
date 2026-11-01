// generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`; do not edit
package com.gitgalaxy.modernized.cobolrt;

/**
 * Declarative COBOL Hexadecimal Floating Point specification (COMP-1 and COMP-2 data items).
 *
 * <p>Reference: IBM z/Architecture Principles of Operation (SA22-7832),
 * Chapter "Hexadecimal-Floating-Point Number Representation" and "Hexadecimal-Floating-Point Instructions";
 * IBM Enterprise COBOL for z/OS 6.4 Programming Guide (SC27-8714-03), Chapter "Conversions and precision";
 * IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06), Chapter "DISPLAY statement".
 * Follows the table-driven code generation pattern established by CicsSpec.java (#4586, #4608).
 */
public final class HfpSpec {
    private HfpSpec() {
    }

    public static final int PRECISION_SHORT = 6;
    public static final int PRECISION_LONG = 14;
    public static final int BYTES_SHORT = 4;
    public static final int BYTES_LONG = 8;
    public static final int BIAS_CHARACTERISTIC = 64;
    public static final int MAX_CHARACTERISTIC = 127;
    public static final int MAX_EXPONENT = 63;
    public static final int MIN_EXPONENT = -64;
    public static final int SIGNIFICANT_DIGITS_SHORT = 9;
    public static final int SIGNIFICANT_DIGITS_LONG = 18;
    public static final int DISPLAY_DIGITS_SHORT = 8;
    public static final int DISPLAY_DIGITS_LONG = 17;

    /** Number of fraction hex digits for short (COMP-1) or long (COMP-2). */
    public static int precisionDigits(boolean isShort) {
        return isShort ? PRECISION_SHORT : PRECISION_LONG;
    }

    /** Number of storage bytes for short (COMP-1) or long (COMP-2). */
    public static int precisionBytes(boolean isShort) {
        return isShort ? BYTES_SHORT : BYTES_LONG;
    }

    /** Maximum significant digits when converting to fixed point. */
    public static int maxSignificantDigits(boolean isShort) {
        return isShort ? SIGNIFICANT_DIGITS_SHORT : SIGNIFICANT_DIGITS_LONG;
    }

    /** Number of fractional digits in DISPLAY format (-.9(N)E-99). */
    public static int displayMantissaDigits(boolean isShort) {
        return isShort ? DISPLAY_DIGITS_SHORT : DISPLAY_DIGITS_LONG;
    }

    /** COBOL usage type name. */
    public static String typeName(boolean isShort) {
        return isShort ? "COMP-1" : "COMP-2";
    }

    /** True if the exponent (unbiased) is within valid HFP range [-64, 63]. */
    public static boolean isExponentInRange(int exp) {
        return exp >= MIN_EXPONENT && exp <= MAX_EXPONENT;
    }

    /** Get registered rule ID from key. */
    public static String ruleId(String key) {
        return switch (key) {
            case "RT-HFP-ADD-NORMALIZED" -> "RT-HFP-ADD-NORMALIZED";
            case "RT-HFP-DISPLAY" -> "RT-HFP-DISPLAY";
            case "RT-HFP-DIVIDE" -> "RT-HFP-DIVIDE";
            case "RT-HFP-EXPONENT-RANGE" -> "RT-HFP-EXPONENT-RANGE";
            case "RT-HFP-FIXED-TO-FLOAT" -> "RT-HFP-FIXED-TO-FLOAT";
            case "RT-HFP-FLOAT-STATEMENT-STORE" -> "RT-HFP-FLOAT-STATEMENT-STORE";
            case "RT-HFP-FLOAT-TO-FIXED" -> "RT-HFP-FLOAT-TO-FIXED";
            case "RT-HFP-FORMAT" -> "RT-HFP-FORMAT";
            case "RT-HFP-IEEE-CONVERSION" -> "RT-HFP-IEEE-CONVERSION";
            case "RT-HFP-LONG-TO-SHORT" -> "RT-HFP-LONG-TO-SHORT";
            case "RT-HFP-MULTIPLY" -> "RT-HFP-MULTIPLY";
            case "RT-HFP-NUMVAL-FLOAT" -> "RT-HFP-NUMVAL-FLOAT";
            case "RT-HFP-POWER" -> "RT-HFP-POWER";
            case "RT-HFP-ZERO-DIVISOR" -> "RT-HFP-ZERO-DIVISOR";
            default -> "UNKNOWN";
        };
    }
}
