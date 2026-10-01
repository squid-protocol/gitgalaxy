package __PACKAGE__.cobolrt;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Locale;

/** Intrinsic functions (IBM Enterprise COBOL Language Reference, Intrinsic functions) the translator uses. */
public final class Funcs {
    private Funcs() {
    }

    public static String upperCase(String s) {
        return s.toUpperCase(Locale.ROOT);
    }

    public static String lowerCase(String s) {
        return s.toLowerCase(Locale.ROOT);
    }

    public static String reverse(String s) {
        return new StringBuilder(s).reverse().toString();
    }

    /** FUNCTION TRIM: leading and trailing spaces removed (an all-space argument gives one space). */
    public static String trim(String s) {
        String t = s.strip();
        return t.isEmpty() && !s.isEmpty() ? " " : t;
    }

    /** FUNCTION MOD: a - b * FLOOR(a / b). */
    public static BigDecimal mod(BigDecimal a, BigDecimal b) {
        BigDecimal q = a.divide(b, 0, RoundingMode.FLOOR);
        return a.subtract(b.multiply(q));
    }

    /** FUNCTION REM: a - b * INTEGER-PART(a / b). */
    public static BigDecimal rem(BigDecimal a, BigDecimal b) {
        BigDecimal q = a.divide(b, 0, RoundingMode.DOWN);
        return a.subtract(b.multiply(q));
    }

    public static BigDecimal integer(BigDecimal a) {
        return a.setScale(0, RoundingMode.FLOOR);
    }

    public static BigDecimal integerPart(BigDecimal a) {
        return a.setScale(0, RoundingMode.DOWN);
    }

    public static BigDecimal abs(BigDecimal a) {
        return a.abs();
    }

    public static BigDecimal min(BigDecimal... a) {
        BigDecimal m = a[0];
        for (BigDecimal x : a) {
            m = x.compareTo(m) < 0 ? x : m;
        }
        return m;
    }

    public static BigDecimal max(BigDecimal... a) {
        BigDecimal m = a[0];
        for (BigDecimal x : a) {
            m = x.compareTo(m) > 0 ? x : m;
        }
        return m;
    }

    /** FUNCTION NUMVAL: the number in a text (leading / trailing spaces, a sign + - CR DB, a decimal point). */
    public static BigDecimal numval(String s) {
        String t = s.strip().toUpperCase(Locale.ROOT);
        boolean neg = false;
        if (t.endsWith("CR") || t.endsWith("DB")) {
            neg = true;
            t = t.substring(0, t.length() - 2).strip();
        }
        if (t.startsWith("-") || t.endsWith("-")) {
            neg = true;
            t = t.replace("-", "").strip();
        }
        t = t.replace("+", "").strip();
        if (t.isEmpty() || t.equals(".")) {
            return BigDecimal.ZERO;
        }
        BigDecimal v = new BigDecimal(t);
        return neg ? v.negate() : v;
    }

    public static BigDecimal numvalC(String s) {
        return numval(s.replace("$", "").replace(",", ""));
    }
}
