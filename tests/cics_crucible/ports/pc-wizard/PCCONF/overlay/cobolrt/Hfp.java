package com.gitgalaxy.modernized.cobolrt;

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
    // [rule RT-HFP-EXPONENT-RANGE]
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
    // [rule RT-HFP-FIXED-TO-FLOAT]
    public static BigDecimal of(BigDecimal v) {
        H h = chop(v, LONG);
        return h == null ? BigDecimal.ZERO : value(h, LONG);
    }

    /** FUNCTION NUMVAL / NUMVAL-C in a floating-point expression, under ARITH(COMPAT): "NUMVAL, NUMVAL-C and
     *  NUMVAL-F return long (64-bit) floating-point values in compatibility mode" (Enterprise COBOL 6.4 Programming
     *  Guide, SC27-8714-03, "Converting to numbers"; Language Reference, NUMVAL: "a floating-point approximation of
     *  the numeric value represented by argument-1"). The value is converted as any fixed-point value ({@link #of}:
     *  truncated to 14 hexadecimal digits, ASSUMED, register C6). IBM bounds what it describes, and the rest is
     *  refused by name: argument-1 holds at most 18 digits under ARITH(COMPAT) (Language Reference, NUMVAL), and "at
     *  most 15 decimal digits can be converted accurately to long-precision floating point [...] Otherwise, the
     *  result may lose precision in an unexpected manner" (Programming Guide, same section): more than 15 digits
     *  from the first nonzero one (trailing zeros written included) are not modelled. */
    // [rule RT-HFP-NUMVAL-FLOAT]
    public static BigDecimal numval(String s, boolean currency) {
        int digits = 0;
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) >= '0' && s.charAt(i) <= '9') digits++;
        }
        if (digits > 18) {
            throw new UnsupportedOperationException("FUNCTION NUMVAL argument of " + digits + " digits: IBM allows at"
                    + " most 18 under ARITH(COMPAT), not modelled (register C6)");
        }
        BigDecimal v = currency ? Funcs.numvalC(s) : Funcs.numval(s);
        if (v.signum() != 0 && v.precision() > 15) { // (a trailing zero written counts: IBM converts the digits)
            throw new UnsupportedOperationException("FUNCTION NUMVAL of " + v.toPlainString() + " in floating point:"
                    + " more than 15 significant digits, which IBM's long-precision conversion may not keep (Programming"
                    + " Guide, \"Converting to numbers\"), not modelled (register C6)");
        }
        return of(v);
    }

    /** The store of a floating-point result into a FIXED-POINT receiver of `scale` decimals, in a statement that is
     *  floating point only because an operand is FUNCTION NUMVAL / NUMVAL-C (#4741). IBM documents that such a
     *  statement is evaluated in floating point and that a float moved to a fixed-point item is ROUNDED in the
     *  low-order position (Programming Guide, SC27-8714-03, "Conversions and precision"); it does not document an
     *  arithmetic statement's store. The model ASSUMES the same rule (pending z/OS calibration, #4702; register C6):
     *  the value is rounded half away from zero to the receiver's scale, so NUMVAL('0.10') (0.0999... in long HFP)
     *  stores 0.10 even without ROUNDED. */
    // [rule RT-HFP-FLOAT-STATEMENT-STORE]
    public static BigDecimal fixedStore(BigDecimal v, int scale, boolean rounded) {
        return v.setScale(scale, RoundingMode.HALF_UP);
    }

    /** A long value rounded to short (LOAD ROUNDED): a one added at the first discarded bit, carry propagated. */
    // [rule RT-HFP-LONG-TO-SHORT]
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
    // [rule RT-HFP-FLOAT-TO-FIXED]
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
    // [rule RT-HFP-ADD-NORMALIZED]
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
    // [rule RT-HFP-MULTIPLY]
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
    // [rule RT-HFP-DIVIDE]
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

    /** Decimal digits of exp(b ln a) for a fractional exponent (det/hfp.py POW_PRECISION), and the working precision. */
    private static final int POW_PRECISION = 60;
    private static final MathContext POW_MC = new MathContext(POW_PRECISION, RoundingMode.HALF_EVEN);
    private static final MathContext WORK = new MathContext(130, RoundingMode.HALF_EVEN);
    /** An integer exponent beyond this is refused by name (det/hfp.py POW_MAX_EXPONENT). */
    private static final int POW_MAX_EXPONENT = 1000;

    /** ln(x), x > 0, at WORK precision: x = r 2^k with r in [0.75, 1.5), ln r = 2 atanh((r-1)/(r+1)), plus k ln 2. */
    private static BigDecimal ln(BigDecimal x) {
        BigDecimal two = BigDecimal.valueOf(2);
        int k = 0;
        BigDecimal r = x;
        while (r.compareTo(new BigDecimal("1.5")) >= 0) {
            r = r.divide(two, WORK);
            k++;
        }
        while (r.compareTo(new BigDecimal("0.75")) < 0) {
            r = r.multiply(two, WORK);
            k--;
        }
        BigDecimal result = atanh2(r.subtract(BigDecimal.ONE).divide(r.add(BigDecimal.ONE), WORK));
        if (k != 0) {
            BigDecimal ln2 = atanh2(BigDecimal.ONE.divide(BigDecimal.valueOf(3), WORK));
            result = result.add(ln2.multiply(BigDecimal.valueOf(k), WORK), WORK);
        }
        return result;
    }

    /** 2 atanh(z) = 2 (z + z^3/3 + z^5/5 + ...) for |z| < 1/3. */
    private static BigDecimal atanh2(BigDecimal z) {
        BigDecimal z2 = z.multiply(z, WORK);
        BigDecimal term = z;
        BigDecimal sum = BigDecimal.ZERO;
        BigDecimal eps = new BigDecimal(BigInteger.ONE, 140);
        for (int n = 1; term.abs().compareTo(eps) > 0; n += 2) {
            sum = sum.add(term.divide(BigDecimal.valueOf(n), WORK), WORK);
            term = term.multiply(z2, WORK);
        }
        return sum.multiply(BigDecimal.valueOf(2), WORK);
    }

    /** exp(y) at WORK precision: y / 2^j (|.| < 1/100) by Taylor series, squared j times. */
    private static BigDecimal exp(BigDecimal y) {
        int j = 0;
        BigDecimal r = y;
        BigDecimal limit = new BigDecimal("0.01");
        while (r.abs().compareTo(limit) >= 0) {
            r = r.divide(BigDecimal.valueOf(2), WORK);
            j++;
        }
        BigDecimal sum = BigDecimal.ONE;
        BigDecimal term = BigDecimal.ONE;
        BigDecimal eps = new BigDecimal(BigInteger.ONE, 140);
        for (int n = 1; term.abs().compareTo(eps) > 0; n++) {
            term = term.multiply(r, WORK).divide(BigDecimal.valueOf(n), WORK);
            sum = sum.add(term, WORK);
        }
        for (int i = 0; i < j; i++) sum = sum.multiply(sum, WORK);
        return sum;
    }

    /** `a ** b` in long HFP, ASSUMED (register C6; IBM documents no result): the capture kit's reference
     *  (tests/tools/hfp_capture_kit.power) and det/hfp.py power. The exact power for an integer exponent, exp(b ln a)
     *  at 60 digits for a fractional one (a must be positive), truncated to long. Not evidence until a z/OS run
     *  agrees (#4050). A zero base with a non-positive exponent is Cobol.raiseSize's NaN as in divide; an exponent
     *  beyond +-1000 or a range overflow is refused by name. */
    // [rule RT-HFP-POWER]
    public static BigDecimal power(BigDecimal a, BigDecimal b) {
        exact(a, LONG);
        exact(b, LONG);
        if (b.signum() == 0 && a.signum() == 0 || a.signum() == 0 && b.signum() < 0) {
            throw new ArithmeticException("0 raised to a non-positive power in a floating-point expression (register C6)");
        }
        if (a.signum() == 0) return BigDecimal.ZERO;
        BigDecimal frac = b.remainder(BigDecimal.ONE);
        if (frac.signum() == 0) {
            BigInteger n = b.toBigIntegerExact();
            boolean unit = a.abs().compareTo(BigDecimal.ONE) == 0;
            if (!unit && n.abs().compareTo(BigInteger.valueOf(POW_MAX_EXPONENT)) > 0) {
                throw new UnsupportedOperationException("exponentiation by " + n + ": beyond the modelled exponent "
                        + "magnitude " + POW_MAX_EXPONENT + " (register C6)");
            }
            int m = n.abs().intValue();
            BigInteger[] r = rational(a);
            BigInteger num = r[0].pow(m);
            BigInteger den = r[1].pow(m);
            if (n.signum() < 0) {
                BigInteger t = num;
                num = den;
                den = t;
            }
            return value(chop(a.signum() < 0 && (m & 1) == 1, num, den, LONG), LONG);
        }
        if (a.signum() < 0) {
            throw new UnsupportedOperationException("a fractional exponent of a non-positive base (register C6)");
        }
        BigDecimal lnA = ln(a).round(POW_MC);
        BigDecimal y = lnA.multiply(b, POW_MC);
        // 16**63 = e**174.7 and 16**-65 = e**-180.2: outside, refuse by name before the series
        if (y.compareTo(BigDecimal.valueOf(200)) > 0) range(64);
        if (y.compareTo(BigDecimal.valueOf(-200)) < 0) range(-65);
        return value(chop(exp(y).round(POW_MC), LONG), LONG);
    }

    /** DIVIDE inside a larger floating-point expression: a zero divisor is refused by name. The oracle's NaN meets
     *  cob_decimal_align there (NaN * x is 0, 2 - NaN is 2, NaN + 1 unchanged: measured, #4675) and the HFP model
     *  does not replay that (oracle_assumptions C14). */
    // [rule RT-HFP-ZERO-DIVISOR]
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
    // [rule RT-HFP-FORMAT]
    static BigDecimal read(Field f) {
        byte[] d = f.st.bytes;
        int digits = f.len == 4 ? SHORT : LONG;
        boolean neg = (d[f.at()] & 0x80) != 0;
        int e = (d[f.at()] & 0x7F) - 64;
        BigInteger frac = BigInteger.ZERO;
        for (int i = 1; i < f.len; i++) frac = frac.shiftLeft(8).or(BigInteger.valueOf(d[f.at() + i] & 0xFF));
        if (frac.signum() == 0) return BigDecimal.ZERO;
        return value(neg, frac, e - digits);
    }

    /** `v` stored in the item: converted to its precision (fixed point: truncated to long, then rounded to short
     *  for a COMP-1; a long value into a COMP-1: rounded). */
    static void store(Field f, BigDecimal v) {
        boolean shortItem = f.len == 4;
        byte[] img = image(forItem(v, shortItem), shortItem);
        System.arraycopy(img, 0, f.st.bytes, f.at(), f.len);
    }

    /** The bytes (4 short / 8 long) of `x`, a value already of the item's precision: true zero is all zero bytes. */
    private static byte[] image(BigDecimal x, boolean shortItem) {
        int len = shortItem ? 4 : 8;
        byte[] d = new byte[len];
        H h = chop(x, shortItem ? SHORT : LONG);
        if (h == null) return d;
        d[0] = (byte) ((h.neg ? 0x80 : 0) | (h.e + 64));
        byte[] fr = h.f.toByteArray();
        for (int i = 0; i < len - 1; i++) {
            int from = fr.length - (len - 1) + i;
            d[1 + i] = from >= 0 ? fr[from] : 0;
        }
        return d;
    }

    // ------------------------------------------------------------------------------------- IEEE conversion

    /** IEEE exponent and fraction bits by item bytes: binary32 (8, 23), binary64 (11, 52). */
    private static int ebits(int size) {
        return size == 4 ? 8 : 11;
    }

    private static int fbits(int size) {
        return size == 4 ? 23 : 52;
    }

    /** The exact value of an IEEE binary32 (size 4) / binary64 (size 8) pattern. NaN, infinity and subnormals have no
     *  HFP value and are refused by name. */
    // [rule RT-HFP-IEEE-CONVERSION]
    public static BigDecimal ieeeValue(long bits, int size) {
        int eb = ebits(size), fb = fbits(size);
        int e = (int) ((bits >>> fb) & ((1L << eb) - 1));
        long f = bits & ((1L << fb) - 1);
        if (e == (1 << eb) - 1) throw new UnsupportedOperationException("IEEE NaN or infinity has no HFP value");
        if (e == 0 && f != 0) throw new UnsupportedOperationException("IEEE subnormal has no modelled HFP value");
        if (e == 0) return BigDecimal.ZERO;
        BigInteger mant = BigInteger.valueOf((1L << fb) | f);
        int k = e - ((1 << (eb - 1)) - 1) - fb; // value = mant x 2^k
        BigDecimal v = k >= 0 ? new BigDecimal(mant.shiftLeft(k))
                : new BigDecimal(mant.multiply(BigInteger.valueOf(5).pow(-k)), -k);
        v = v.stripTrailingZeros();
        if (v.scale() < 0) v = v.setScale(0);
        return (bits >>> (eb + fb)) != 0 ? v.negate() : v;
    }

    /** The HFP bytes for an IEEE pattern of the same width: a binary64 fits long HFP exactly; a binary32 takes the
     *  fixed-point-to-float rule (ASSUMED: IBM documents no IEEE converter). */
    public static byte[] fromIeee(long bits, int size) {
        return image(forItem(ieeeValue(bits, size), size == 4), size == 4);
    }

    /** The IEEE pattern (binary32 for 4 bytes, binary64 for 8) nearest an HFP image, ties to even. A value outside the
     *  IEEE format's normal range is refused by name. */
    public static long toIeee(byte[] hfp) {
        int size = hfp.length, eb = ebits(size), fb = fbits(size);
        boolean neg = (hfp[0] & 0x80) != 0;
        BigInteger frac = BigInteger.ZERO;
        for (int i = 1; i < size; i++) frac = frac.shiftLeft(8).or(BigInteger.valueOf(hfp[i] & 0xFF));
        if (frac.signum() == 0) return 0;
        BigInteger[] r = rational(value(neg, frac, (hfp[0] & 0x7F) - 64 - (size == 4 ? SHORT : LONG)).abs());
        BigInteger num = r[0], den = r[1];
        int e = num.bitLength() - den.bitLength();
        if (cmp2(num, den, e) < 0) e--; // num/den < 2^e
        int k = fb - e; // m = num/den x 2^k, 2^fb <= m < 2^(fb+1)
        BigInteger mn = k >= 0 ? num.shiftLeft(k) : num, md = k >= 0 ? den : den.shiftLeft(-k);
        BigInteger[] qr = mn.divideAndRemainder(md);
        BigInteger q = qr[0];
        int twice = qr[1].shiftLeft(1).compareTo(md);
        if (twice > 0 || (twice == 0 && q.testBit(0))) q = q.add(BigInteger.ONE);
        if (q.bitLength() > fb + 1) {
            q = q.shiftRight(1);
            e++;
        }
        int bias = (1 << (eb - 1)) - 1;
        if (e + bias >= (1 << eb) - 1) throw new UnsupportedOperationException("HFP value too large for the IEEE format");
        if (e + bias < 1) throw new UnsupportedOperationException("HFP value too small for a normal IEEE number");
        long bits = ((long) (e + bias) << fb) | (q.longValue() & ((1L << fb) - 1));
        return neg ? bits | (1L << (eb + fb)) : bits;
    }

    /** num/den against 2^e. */
    private static int cmp2(BigInteger num, BigInteger den, int e) {
        return e >= 0 ? num.compareTo(den.shiftLeft(e)) : num.shiftLeft(-e).compareTo(den);
    }

    // ------------------------------------------------------------------------------------------- DISPLAY

    /** -.9(8)E-99 (COMP-1) or -.9(17)E-99 (COMP-2): a space or '-', the point, the mantissa's digits rounded half
     *  away from zero (ASSUMED), 'E', a space or '-', two exponent digits. Zero: " .000...E 00". */
    // [rule RT-HFP-DISPLAY]
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
