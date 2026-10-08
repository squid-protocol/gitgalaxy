package __PACKAGE__.cobolrt;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.MathContext;
import java.math.RoundingMode;

/**
 * COMP-1 and COMP-2 as z/OS holds them: IBM hexadecimal floating point (HFP), #4271, register C6 of
 * docs/language_status/oracle_assumptions.md.
 *
 * <p>Format (z/Architecture Principles of Operation, SA22-7832, "Hexadecimal-Floating-Point Number Representation"):
 * bit 0 the sign, bits 1-7 the characteristic (the exponent of 16, excess 64), then the fraction -- 6 hexadecimal
 * digits in a short (COMP-1, 4 bytes), 14 in a long (COMP-2, 8 bytes) number, big-endian. The value is
 * (-1)^sign x 0.fraction x 16^(characteristic - 64). A normalized number has a nonzero leading fraction digit; zero
 * is all zero bytes ("true zero").
 *
 * <p>Every value here is a {@link BigDecimal} holding the HFP number exactly (16^-k is a finite decimal), so a float
 * item reads as an exact decimal and the rest of the runtime works on it unchanged. The rules:
 * <ul>
 * <li>Arithmetic (Principles of Operation, chapter "Hexadecimal-Floating-Point Instructions"): ADD / SUBTRACT
 *     NORMALIZED align the operands with one hexadecimal guard digit, then normalize and truncate; MULTIPLY and
 *     DIVIDE truncate the exact result. {@link #add}, {@link #subtract}, {@link #multiply}, {@link #divide}.
 * <li>Long to short: LOAD ROUNDED -- a one added at the first discarded bit (half away from zero), IBM's "if a
 *     USAGE COMP-2 data item is moved to a USAGE COMP-1 data item, rounding occurs" (Enterprise COBOL 6.4
 *     Programming Guide, SC27-8714-03, "Conversions and precision"). {@link #toShort}.
 * <li>Fixed point to float: the exact value truncated to long ({@link #of}), then rounded to short for a COMP-1.
 *     IBM does not document the generated conversion; this is the model's ASSUMED choice (register C6).
 * <li>Float to fixed point: "rounding occurs in the low-order position of the target", and a COMP-1 gives at most 9,
 *     a COMP-2 at most 18 significant digits (the same Programming Guide section). {@link #toFixed}.
 * <li>DISPLAY: "A COMP-1 item will display as if it had an external floating-point PICTURE clause of -.9(8)E-99. A
 *     COMP-2 item [...] -.9(17)E-99" (Enterprise COBOL 6.4 Language Reference, DISPLAY statement). {@link #display}.
 * </ul>
 * An exponent overflow or underflow is refused by name: what z/OS does then depends on the program mask and on
 * Language Environment, which no oracle here runs.
 */
public final class Hfp {
    private Hfp() {}

    /** Hexadecimal digits of a short (COMP-1) and a long (COMP-2) fraction. */
    static final int SHORT = 6;
    static final int LONG = 14;

    private static final BigInteger SIXTEEN = BigInteger.valueOf(16);
    private static final BigDecimal SIXTEENTH = new BigDecimal("0.0625");

    /** A nonzero HFP number: the value is (neg ? -1 : 1) x f x 16^(e - digits), f of exactly `digits` hex digits. */
    private static final class H {
        final boolean neg;
        final int e;
        final BigInteger f;

        H(boolean neg, int e, BigInteger f) {
            this.neg = neg;
            this.e = e;
            this.f = f;
        }
    }

    private static BigInteger p16(int k) {
        return BigInteger.ONE.shiftLeft(4 * k);
    }

    private static BigDecimal pow16(int k) {
        return k >= 0 ? new BigDecimal(p16(k)) : SIXTEENTH.pow(-k);
    }

    private static BigDecimal value(boolean neg, BigInteger f, int exp16) {
        BigDecimal v = new BigDecimal(f).multiply(pow16(exp16)).stripTrailingZeros();
        if (v.scale() < 0) v = v.setScale(0);
        return neg ? v.negate() : v;
    }

    private static BigDecimal value(H h, int digits) {
        return value(h.neg, h.f, h.e - digits);
    }

    /** The exponent range: a characteristic of 0..127. */
    private static void range(int e) {
        if (e > 63) {
            throw new UnsupportedOperationException("HFP exponent overflow (the result exceeds 16**63): what z/OS "
                    + "does then depends on the program mask and Language Environment, not modelled (register C6)");
        }
        if (e < -64) {
            throw new UnsupportedOperationException("HFP exponent underflow (the result is below 16**-65): what z/OS "
                    + "does then depends on the program mask and Language Environment, not modelled (register C6)");
        }
    }

    /** The rational num / den (num, den > 0) truncated to `digits` hex digits: its H, normalized. */
    private static H chop(boolean neg, BigInteger num, BigInteger den, int digits) {
        // e with 16^(e-1) <= num/den < 16^e, from the bit lengths, then corrected
        int e = Math.floorDiv(num.bitLength() - den.bitLength(), 4) + 1;
        while (cmpScaled(num, den, e) >= 0) e++; // num/den >= 16^e
        while (cmpScaled(num, den, e - 1) < 0) e--; // num/den < 16^(e-1)
        int k = digits - e; // f = floor(num/den x 16^k)
        BigInteger f = k >= 0 ? num.multiply(p16(k)).divide(den) : num.divide(den.multiply(p16(-k)));
        range(e);
        return new H(neg, e, f);
    }

    /** num/den against 16^e. */
    private static int cmpScaled(BigInteger num, BigInteger den, int e) {
        return e >= 0 ? num.compareTo(den.multiply(p16(e))) : num.multiply(p16(-e)).compareTo(den);
    }

    /** An exact decimal as a rational: (num, den). */
    private static BigInteger[] rational(BigDecimal v) {
        BigInteger u = v.unscaledValue().abs();
        if (v.scale() <= 0) return new BigInteger[] {u.multiply(BigInteger.TEN.pow(-v.scale())), BigInteger.ONE};
        return new BigInteger[] {u, BigInteger.TEN.pow(v.scale())};
    }

    /** `v` (exact) truncated to `digits` hex digits; null for zero. */
    private static H chop(BigDecimal v, int digits) {
        if (v.signum() == 0) return null;
        BigInteger[] r = rational(v);
        return chop(v.signum() < 0, r[0], r[1], digits);
    }

    /** A value already of `digits` hex digits, decomposed (the arithmetic's operands). */
    private static H exact(BigDecimal v, int digits) {
        H h = chop(v, digits);
        if (h != null && value(h, digits).compareTo(v) != 0) {
            throw new IllegalArgumentException("not an HFP value of " + digits + " digits: " + v);
        }
        return h;
    }

    // ------------------------------------------------------------------------------------------ conversions

    /** A fixed-point value converted to long HFP: the exact value truncated to 14 hexadecimal digits. */
    public static BigDecimal of(BigDecimal v) {
        H h = chop(v, LONG);
        return h == null ? BigDecimal.ZERO : value(h, LONG);
    }

    /** A long value rounded to short (LOAD ROUNDED): a one added at the first discarded bit, carry propagated. */
    public static BigDecimal toShort(BigDecimal v) {
        H h = chop(v, LONG);
        if (h == null) return BigDecimal.ZERO;
        BigInteger f = h.f.add(BigInteger.ONE.shiftLeft(4 * (LONG - SHORT) - 1)).shiftRight(4 * (LONG - SHORT));
        int e = h.e;
        if (f.equals(p16(SHORT))) {
            f = p16(SHORT - 1);
            e++;
        }
        range(e);
        return value(h.neg, f, e - SHORT);
    }

    /** The value an item of `shortItem` (COMP-1) or long (COMP-2) precision holds for `v`. */
    public static BigDecimal forItem(BigDecimal v, boolean shortItem) {
        return shortItem ? toShort(of(v)) : of(v);
    }

    /** A float's value moved to a fixed-point item of `scale`: rounded half away from zero in the low-order
     *  position, at most `significant` digits (9 for COMP-1, 18 for COMP-2) and the rest zero. */
    public static BigDecimal toFixed(BigDecimal v, int scale, int significant) {
        BigDecimal r = v.setScale(scale, RoundingMode.HALF_UP);
        if (r.unscaledValue().abs().toString().length() > significant && r.signum() != 0) {
            r = v.round(new MathContext(significant, RoundingMode.HALF_UP)).setScale(scale, RoundingMode.HALF_UP);
        }
        return r;
    }

    // ------------------------------------------------------------------------------------------- arithmetic

    private static int digits(boolean longP) {
        return longP ? LONG : SHORT;
    }

    /** ADD NORMALIZED: the operand with the smaller exponent shifted right keeping one guard digit, the sum
     *  normalized (the guard digit shifted in), then truncated. */
    public static BigDecimal add(BigDecimal a, BigDecimal b, boolean longP) {
        int d = digits(longP);
        H x = exact(a, d);
        H y = exact(b, d);
        if (x == null) return y == null ? BigDecimal.ZERO : value(y, d);
        if (y == null) return value(x, d);
        if (x.e < y.e) {
            H t = x;
            x = y;
            y = t;
        }
        int shift = x.e - y.e;
        BigInteger fx = x.f.shiftLeft(4);
        BigInteger fy = y.f.shiftLeft(4).shiftRight(4 * shift);
        BigInteger s = (x.neg ? fx.negate() : fx).add(y.neg ? fy.negate() : fy);
        if (s.signum() == 0) return BigDecimal.ZERO;
        boolean neg = s.signum() < 0;
        s = s.abs();
        int e = x.e;
        if (s.compareTo(p16(d + 1)) >= 0) {
            s = s.shiftRight(4);
            e++;
        }
        while (s.compareTo(p16(d)) < 0) {
            s = s.shiftLeft(4);
            e--;
        }
        range(e);
        return value(neg, s.shiftRight(4), e - d);
    }

    public static BigDecimal subtract(BigDecimal a, BigDecimal b, boolean longP) {
        return add(a, b.negate(), longP);
    }

    /** MULTIPLY: the exact product truncated. */
    public static BigDecimal multiply(BigDecimal a, BigDecimal b, boolean longP) {
        int d = digits(longP);
        exact(a, d);
        exact(b, d);
        H h = chop(a.multiply(b), d);
        return h == null ? BigDecimal.ZERO : value(h, d);
    }

    /** DIVIDE: the exact quotient truncated. A zero divisor is libcob's NaN with the size error raised, as in
     *  Cobol.divide (#4675, oracle_assumptions C14): the oracle converts a float to a decimal and divides it, so a
     *  receiver is left unchanged; z/OS leaves the result undefined. Only a division that is a statement's whole
     *  value (COMPUTE x = a / b, DIVIDE): inside a larger expression divideNested refuses. */
    public static BigDecimal divide(BigDecimal a, BigDecimal b, boolean longP) {
        if (b.signum() == 0) {
            Cobol.raiseSize();
            return Cobol.nan(a);
        }
        int d = digits(longP);
        H x = exact(a, d);
        H y = exact(b, d);
        if (y == null) { // a divisor that is HFP zero
            Cobol.raiseSize();
            return Cobol.nan(a);
        }
        if (x == null) return BigDecimal.ZERO;
        // (fx 16^(ex-d)) / (fy 16^(ey-d)) = (fx / fy) 16^(ex-ey)
        BigInteger num = x.f;
        BigInteger den = y.f;
        int shift = x.e - y.e;
        if (shift >= 0) num = num.multiply(p16(shift));
        else den = den.multiply(p16(-shift));
        H h = chop(x.neg != y.neg, num, den, d);
        return value(h, d);
    }

    /** DIVIDE inside a larger floating-point expression: a zero divisor is refused by name. The oracle's NaN meets
     *  cob_decimal_align there (NaN * x is 0, 2 - NaN is 2, NaN + 1 unchanged: measured, #4675) and the HFP model
     *  does not replay that (oracle_assumptions C14). */
    public static BigDecimal divideNested(BigDecimal a, BigDecimal b, boolean longP) {
        if (b.signum() == 0) {
            throw new ArithmeticException("division by zero inside a floating-point expression (oracle_assumptions C14)");
        }
        BigDecimal q = divide(a, b, longP);
        if (Cobol.isNan(q)) throw new ArithmeticException("division by zero inside a floating-point expression (oracle_assumptions C14)");
        return q;
    }

    // ------------------------------------------------------------------------------------------- storage

    /** The item's bytes as an exact value. An unnormalized fraction reads as its value too. */
    static BigDecimal read(Field f) {
        byte[] d = f.st.bytes;
        int digits = f.len == 4 ? SHORT : LONG;
        boolean neg = (d[f.off] & 0x80) != 0;
        int e = (d[f.off] & 0x7F) - 64;
        BigInteger frac = BigInteger.ZERO;
        for (int i = 1; i < f.len; i++) frac = frac.shiftLeft(8).or(BigInteger.valueOf(d[f.off + i] & 0xFF));
        if (frac.signum() == 0) return BigDecimal.ZERO;
        return value(neg, frac, e - digits);
    }

    /** `v` stored in the item: converted to its precision (fixed point: truncated to long, then rounded to short
     *  for a COMP-1; a long value into a COMP-1: rounded). */
    static void store(Field f, BigDecimal v) {
        boolean shortItem = f.len == 4;
        BigDecimal x = forItem(v, shortItem);
        byte[] d = f.st.bytes;
        java.util.Arrays.fill(d, f.off, f.off + f.len, (byte) 0);
        H h = chop(x, shortItem ? SHORT : LONG);
        if (h == null) return; // true zero: all zero bytes
        d[f.off] = (byte) ((h.neg ? 0x80 : 0) | (h.e + 64));
        byte[] fr = h.f.toByteArray();
        for (int i = 0; i < f.len - 1; i++) {
            int from = fr.length - (f.len - 1) + i;
            d[f.off + 1 + i] = from >= 0 ? fr[from] : 0;
        }
    }

    // ------------------------------------------------------------------------------------------- DISPLAY

    /** -.9(8)E-99 (COMP-1) or -.9(17)E-99 (COMP-2): a space or '-', the point, the mantissa's digits rounded half
     *  away from zero (ASSUMED), 'E', a space or '-', two exponent digits. Zero: " .000...E 00". */
    static String display(BigDecimal v, boolean longP) {
        int n = longP ? 17 : 8;
        if (v.signum() == 0) return " ." + "0".repeat(n) + "E 00";
        BigDecimal a = v.abs();
        int k = a.precision() - a.scale(); // a = 0.ddd x 10^k
        BigDecimal m = a.movePointLeft(k).setScale(n, RoundingMode.HALF_UP);
        if (m.compareTo(BigDecimal.ONE) >= 0) {
            m = m.movePointLeft(1).setScale(n, RoundingMode.HALF_UP);
            k++;
        }
        String digits = m.unscaledValue().toString();
        digits = "0".repeat(n - digits.length()) + digits;
        String exp = String.valueOf(Math.abs(k));
        return (v.signum() < 0 ? "-" : " ") + "." + digits + "E" + (k < 0 ? "-" : " ") + (exp.length() < 2 ? "0" : "")
                + exp;
    }
}
