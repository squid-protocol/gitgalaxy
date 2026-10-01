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

    private static final java.time.LocalDate DAY_ZERO = java.time.LocalDate.of(1600, 12, 31);

    /** FUNCTION INTEGER-OF-DATE: YYYYMMDD -> days since 31 December 1600 (1 January 1601 is day 1). */
    public static BigDecimal integerOfDate(BigDecimal yyyymmdd) {
        int v = yyyymmdd.intValue();
        java.time.LocalDate d = java.time.LocalDate.of(v / 10000, v / 100 % 100, v % 100);
        return BigDecimal.valueOf(java.time.temporal.ChronoUnit.DAYS.between(DAY_ZERO, d));
    }

    /** FUNCTION DATE-OF-INTEGER: days since 31 December 1600 -> YYYYMMDD. */
    public static BigDecimal dateOfInteger(BigDecimal days) {
        java.time.LocalDate d = DAY_ZERO.plusDays(days.longValue());
        return BigDecimal.valueOf(d.getYear() * 10000L + d.getMonthValue() * 100L + d.getDayOfMonth());
    }

    public static BigDecimal numvalC(String s) {
        return numval(s.replace("$", "").replace(",", ""));
    }
}
