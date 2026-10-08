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

    /** FUNCTION TRIM: leading and trailing spaces removed -- spaces only (low-values stay), and an all-space
     *  argument gives a zero-length result (GnuCOBOL, checked: test_det_programs.py TRIMS). */
    public static String trim(String s) {
        return trimTrailing(trimLeading(s));
    }

    /** FUNCTION TRIM(x LEADING). */
    public static String trimLeading(String s) {
        int i = 0;
        while (i < s.length() && s.charAt(i) == ' ') {
            i++;
        }
        return s.substring(i);
    }

    /** FUNCTION TRIM(x TRAILING). */
    public static String trimTrailing(String s) {
        int j = s.length();
        while (j > 0 && s.charAt(j - 1) == ' ') {
            j--;
        }
        return s.substring(0, j);
    }

    /** FUNCTION MOD: a - b * FLOOR(a / b); a zero b gives 0, no size error (the oracle, #4655). */
    public static BigDecimal mod(BigDecimal a, BigDecimal b) {
        if (b.signum() == 0) {
            return BigDecimal.ZERO;
        }
        BigDecimal q = a.divide(b, 0, RoundingMode.FLOOR);
        return a.subtract(b.multiply(q));
    }

    /** FUNCTION REM: a - b * INTEGER-PART(a / b); a zero b gives 0, no size error (the oracle, #4655). */
    public static BigDecimal rem(BigDecimal a, BigDecimal b) {
        if (b.signum() == 0) {
            return BigDecimal.ZERO;
        }
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

    /** FUNCTION RANDOM, one run unit's sequence (oracle_assumptions.md C12). IBM documents the interface only --
     *  argument-1 a seed, zero or a positive integer; a first reference with no argument-1 seeds zero; a reference
     *  with no argument-1 takes the next number of the current sequence -- not the generator. This is GnuCOBOL
     *  3.1.2's (the harness's oracle, libcob intrinsic.c cob_intr_random): glibc's srand(seed) / rand() (TYPE_3,
     *  random_r.c; seed 0 is seed 1) and rand() / RAND_MAX as a double, whose exact value the COMPUTE takes. So the
     *  port gives the oracle's numbers for a seed, NOT z/OS's: a proof shows what the program does with the numbers,
     *  not that z/OS draws them. A value can be 0 or 1 (IBM: exclusively between). A seed IBM does not allow
     *  (negative, not an integer) or one past the oracle's int (GnuCOBOL's cob_get_int) is refused at run time. */
    public static final class Random {
        private static final int RAND_MAX = 2147483647;
        private final int[] r = new int[31];
        private int f;
        private int b;

        public Random() {
            reset();
        }

        /** A new run unit: the sequence as a first reference with no argument-1 finds it (seed zero). */
        public void reset() {
            seed(0);
        }

        /** FUNCTION RANDOM(seed). */
        public BigDecimal next(BigDecimal seed) {
            BigDecimal s = seed.stripTrailingZeros();
            if (s.signum() < 0 || s.scale() > 0 || s.compareTo(BigDecimal.valueOf(RAND_MAX)) > 0) {
                throw new IllegalArgumentException("FUNCTION RANDOM seed " + seed.toPlainString()
                        + " not modelled: IBM takes zero or a positive integer, the oracle an int"
                        + " (oracle_assumptions.md C12)");
            }
            seed(s.intValueExact());
            return next();
        }

        /** FUNCTION RANDOM: the next number of the current sequence. */
        public BigDecimal next() {
            r[f] += r[b];
            int val = r[f] >>> 1;
            if (++f >= r.length) {
                f = 0;
                ++b;
            } else if (++b >= r.length) {
                b = 0;
            }
            return new BigDecimal((double) val / (double) RAND_MAX);
        }

        /** glibc __srandom_r for TYPE_3: the state from a 16807 LCG (Schrage), then 310 numbers discarded. */
        private void seed(int seed) {
            long word = seed == 0 ? 1 : seed;
            r[0] = (int) word;
            for (int i = 1; i < r.length; i++) {
                long hi = word / 127773;
                long lo = word % 127773;
                word = 16807 * lo - 2836 * hi;
                if (word < 0) {
                    word += 2147483647;
                }
                r[i] = (int) word;
            }
            f = 3;
            b = 0;
            for (int i = 0; i < 310; i++) {
                next();
            }
        }
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
