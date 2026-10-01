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

    /** FUNCTION CURRENT-DATE where the project has no clock bean: YYYYMMDDHHMMSShh and the UTC offset. */
    public static String currentDate(java.time.LocalDateTime now) {
        return now.format(java.time.format.DateTimeFormatter.ofPattern("yyyyMMddHHmmss", java.util.Locale.ROOT))
                + String.format(java.util.Locale.ROOT, "%02d", now.getNano() / 10_000_000) + "+0000";
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

    /** FUNCTION TEST-NUMVAL: 0 when the argument is valid for NUMVAL, else the (1-based) position of the first
     *  character that makes it invalid -- the argument's length + 1 when it ends before a digit (GnuCOBOL,
     *  checked: one sign, leading or trailing; + - CR DB in upper case; nothing but spaces after a trailing one). */
    public static BigDecimal testNumval(String s) {
        return BigDecimal.valueOf(testNumval(s, false));
    }

    /** FUNCTION TEST-NUMVAL-C: as TEST-NUMVAL, a currency sign ($) allowed before the number and commas in its
     *  integer part. */
    public static BigDecimal testNumvalC(String s) {
        return BigDecimal.valueOf(testNumval(s, true));
    }

    private static int testNumval(String s, boolean currency) {
        final int start = 0, afterSign = 1, afterCurrency = 2, integer = 3, fraction = 4, trailing = 5, done = 6;
        int state = start;
        boolean leadingSign = false;
        boolean digits = false;
        int n = s.length();
        for (int i = 0; i < n; i++) {
            char c = s.charAt(i);
            boolean digit = c >= '0' && c <= '9';
            switch (state) {
                case start, afterSign, afterCurrency -> {
                    if (c == ' ') {
                        continue;
                    }
                    if (digit) {
                        state = integer;
                        digits = true;
                    } else if (c == '.') {
                        state = fraction;
                    } else if (!leadingSign && state != afterSign && (c == '+' || c == '-')) {
                        leadingSign = true;
                        state = afterSign;
                    } else if (currency && state != afterCurrency && c == '$') {
                        state = afterCurrency;
                    } else {
                        return i + 1;
                    }
                }
                case integer, fraction, trailing -> {
                    if (digit && state != trailing) {
                        digits = true;
                    } else if (c == '.' && state == integer) {
                        state = fraction;
                    } else if (c == ',' && currency && state == integer) {
                        // a thousands separator
                    } else if (c == ' ') {
                        state = trailing;
                    } else if (!leadingSign && (c == '+' || c == '-')) {
                        state = done;
                    } else if (!leadingSign && i + 1 < n && ((c == 'C' && s.charAt(i + 1) == 'R')
                            || (c == 'D' && s.charAt(i + 1) == 'B'))) {
                        state = done;
                        i++;
                    } else {
                        return i + 1;
                    }
                }
                default -> {
                    if (c != ' ') {
                        return i + 1;
                    }
                }
            }
        }
        return digits ? 0 : n + 1;
    }

    public static BigDecimal numvalC(String s) {
        return numval(s.replace("$", "").replace(",", ""));
    }
}
