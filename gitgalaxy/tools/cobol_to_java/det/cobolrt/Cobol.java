package __PACKAGE__.cobolrt;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;
import java.nio.charset.Charset;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * COBOL data semantics over byte storage (IBM Enterprise COBOL, as GnuCOBOL implements it under
 * `-std=ibm -fsign=EBCDIC`; every rule here is checked against GnuCOBOL by tests/cobol_mainframe/test_cobolrt.py).
 *
 * <p>Every text conversion takes the record charset. Statements STRING, UNSTRING and INSPECT are the methods
 * {@link #string}, {@link #unstring} and {@link #inspect}; their operands are built with {@link StringPart},
 * {@link Delim}, {@link Into} and {@link Clause}.
 */
public final class Cobol {
    private Cobol() {}

    // ------------------------------------------------------------------------------------------ categories

    private static final int GROUP = 0;
    private static final int ALNUM = 1;
    private static final int NUMERIC = 2;
    private static final int NUM_EDITED = 3;
    private static final int ALNUM_EDITED = 4;

    private static int cat(Field f) {
        switch (f.kind) {
            case GROUP: return GROUP;
            case ALPHANUMERIC:
            case ALPHABETIC: return ALNUM;
            case NUMERIC_EDITED: return NUM_EDITED;
            case ALPHANUMERIC_EDITED: return ALNUM_EDITED;
            default: return NUMERIC;
        }
    }

    private static Field temp(byte[] b) {
        Storage s = new Storage(b.length);
        System.arraycopy(b, 0, s.bytes, 0, b.length);
        return Field.alphanumeric(s, 0, b.length, false);
    }

    /** A numeric literal as the DISPLAY item it is. */
    private static Field literalField(BigDecimal v) {
        if (v.scale() < 0) v = v.setScale(0);
        int digits = Math.max(Math.max(v.unscaledValue().abs().toString().length(), v.scale()), 1);
        // a literal written without a sign is unsigned: MOVE 23 TO a group gives "23", not an overpunched "2C"
        return Field.zoned(new Storage(digits), 0, digits, v.scale(), v.signum() < 0, false, false);
    }

    /** TRUNC(STD) for binary items (high-order digits beyond the PICTURE lost; size error beyond the PICTURE).
     *  Default false: as GnuCOBOL `-std=ibm` behaves, a binary item holds what its bytes hold. */
    public static void setTruncBinary(boolean on) {
        Codec.truncBinary = on;
    }

    // ------------------------------------------------------------------------------------------ ARITHMETIC
    /** An intermediate quotient as GnuCOBOL forms it (cob_decimal_div): the dividend shifted 38 digits, then
     *  divided and truncated -- the receiver's own truncation or ROUNDED then applies in store. */
    public static BigDecimal divide(BigDecimal a, BigDecimal b) {
        if (b.signum() == 0) {
            throw new ArithmeticException("division by zero");
        }
        int shift = 38 + Math.max(0, -a.scale());
        int scale = Math.max(0, a.scale() + shift - b.scale());
        return a.divide(b, scale, java.math.RoundingMode.DOWN);
    }

    /** A ** b: exact for a whole exponent, else through double. */
    public static BigDecimal power(BigDecimal a, BigDecimal b) {
        if (b.signum() >= 0 && b.stripTrailingZeros().scale() <= 0 && b.compareTo(BigDecimal.valueOf(999)) <= 0) {
            return a.pow(b.intValueExact());
        }
        if (b.signum() < 0 && b.stripTrailingZeros().scale() <= 0) {
            return divide(BigDecimal.ONE, a.pow(-b.intValueExact()));
        }
        return new BigDecimal(Math.pow(a.doubleValue(), b.doubleValue()));
    }

    // ------------------------------------------------------------------------------------------------ MOVE

    public static void move(Field from, Field to, Charset cs) {
        if (cat(to) == GROUP) {
            padCopy(from.raw(), to, false, cs);
            return;
        }
        int fc = cat(from);
        switch (cat(to)) {
            case ALNUM:
                padCopy(sourceText(from, fc, cs), to, to.justRight, cs);
                break;
            case ALNUM_EDITED:
                insertEdit(to, sourceText(from, fc, cs), cs);
                break;
            case NUMERIC:
                store(to, source(from, fc, cs), cs);
                break;
            default:
                edit(to, source(from, fc, cs), cs);
        }
    }

    public static void move(String nonnumericLiteral, Field to, Charset cs) {
        move(temp(nonnumericLiteral.getBytes(cs)), to, cs);
    }

    public static void move(BigDecimal numericLiteral, Field to, Charset cs) {
        move(fill(literalField(numericLiteral), numericLiteral, cs), to, cs);
    }

    private static Field fill(Field f, BigDecimal v, Charset cs) {
        if (v.scale() < 0) v = v.setScale(0);
        Codec.write(f, v.unscaledValue().abs(), v.signum() < 0, cs);
        return f;
    }

    public static void moveFigurative(Figurative fig, Field to, Charset cs) {
        byte b = figByte(fig, cs);
        switch (cat(to)) {
            case NUMERIC:
                if (fig == Figurative.ZEROS) {
                    Codec.write(to, BigInteger.ZERO, false, cs);
                } else {
                    Arrays.fill(to.st.bytes, to.off, to.off + to.len, b);
                }
                break;
            case NUM_EDITED:
                if (fig == Figurative.ZEROS) {
                    edit(to, new Codec.Num(BigInteger.ZERO, 0, false), cs);
                } else {
                    Arrays.fill(to.st.bytes, to.off, to.off + to.len, b);
                }
                break;
            default:
                Arrays.fill(to.st.bytes, to.off, to.off + to.len, b);
        }
    }

    private static byte figByte(Figurative f, Charset cs) {
        switch (f) {
            case SPACES: return Codec.space(cs);
            case ZEROS: return Codec.by('0', cs);
            case LOW_VALUES: return 0;
            case HIGH_VALUES: return (byte) 0xFF;
            default: return Codec.by('"', cs);
        }
    }

    /** MOVE ALL literal: the literal repeated to the receiver's size. */
    public static void moveAll(String allLiteral, Field to, Charset cs) {
        byte[] lit = allLiteral.getBytes(cs);
        if (lit.length == 0) return;
        byte[] b = new byte[to.len];
        for (int i = 0; i < b.length; i++) b[i] = lit[i % lit.length];
        switch (cat(to)) {
            case NUMERIC:
            case NUM_EDITED:
                // GnuCOBOL: the pattern ends at the right edge (ALL "12" to PIC 9(5) is 21212)
                for (int k = 0; k < b.length; k++) b[b.length - 1 - k] = lit[lit.length - 1 - k % lit.length];
                move(temp(b), to, cs);
                break;
            default:
                System.arraycopy(b, 0, to.st.bytes, to.off, b.length);
        }
    }

    /** The sending item as the bytes an alphanumeric receiver gets. */
    private static byte[] sourceText(Field from, int fc, Charset cs) {
        if (fc != NUMERIC) return from.raw();
        if (from.kind == Field.Kind.NUMERIC_DISPLAY) {
            // GnuCOBOL (as IBM for an integer): the digit bytes as they are -- invalid data included -- the
            // overpunched sign turned back into its digit, a separate sign dropped, no decimal point
            byte[] raw = from.raw();
            int start = from.signSeparate && from.signLeading ? 1 : 0;
            int end = from.signSeparate && !from.signLeading ? raw.length - 1 : raw.length;
            byte[] out = java.util.Arrays.copyOfRange(raw, start, end);
            if (from.signed && !from.signSeparate && out.length > 0) {
                int at = from.signLeading ? 0 : out.length - 1;
                out[at] = unpunch(out[at], cs);
            }
            return out;
        }
        Codec.Num n = Codec.read(from, cs);
        String s = n.mag.toString();
        if (s.length() < from.digits) s = "0".repeat(from.digits - s.length()) + s;
        return s.getBytes(cs);
    }

    /** An overpunched sign byte ({ A-I: +0..9, } J-R: -0..9 as -fsign=EBCDIC writes them) as its digit; any other
     *  byte as it is. */
    private static byte unpunch(byte b, Charset cs) {
        String c = new String(new byte[] {b}, cs);
        int i = "{ABCDEFGHI".indexOf(c);
        if (i < 0) {
            i = "}JKLMNOPQR".indexOf(c);
        }
        return i < 0 ? b : String.valueOf(i).getBytes(cs)[0];
    }

    /** The sending item's value as a number: numeric, de-edited, or an alphanumeric read as GnuCOBOL does. */
    private static Codec.Num source(Field from, int fc, Charset cs) {
        switch (fc) {
            case NUMERIC: return Codec.read(from, cs);
            case NUM_EDITED: return deedit(from, cs);
            default: return parseAlnum(from.raw(), cs);
        }
    }

    private static Codec.Num deedit(Field f, Charset cs) {
        String s = new String(f.raw(), cs);
        BigInteger v = BigInteger.ZERO;
        boolean neg = false;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c >= '0' && c <= '9') {
                v = v.multiply(BigInteger.TEN).add(BigInteger.valueOf(c - '0'));
            } else if (c == '-') {
                neg = true;
            } else if ((c == 'C' && i + 1 < s.length() && s.charAt(i + 1) == 'R')
                    || (c == 'D' && i + 1 < s.length() && s.charAt(i + 1) == 'B')) {
                neg = true;
            }
        }
        return new Codec.Num(v, f.scale, neg);
    }

    private static Codec.Num parseAlnum(byte[] raw, Charset cs) {
        String s = new String(raw, cs);
        int i = 0;
        int n = s.length();
        while (i < n && Character.isWhitespace(s.charAt(i))) i++;
        boolean neg = false;
        if (i < n && (s.charAt(i) == '+' || s.charAt(i) == '-')) neg = s.charAt(i++) == '-';
        StringBuilder digits = new StringBuilder();
        int frac = 0;
        boolean point = false;
        for (; i < n; i++) {
            char c = s.charAt(i);
            if (c >= '0' && c <= '9') {
                digits.append(c);
                if (point) frac++;
            } else if (c == '.' && !point) {
                point = true;
            } else if (!(Character.isWhitespace(c) || c == ',')) {
                return new Codec.Num(BigInteger.ZERO, 0, false);
            }
        }
        return new Codec.Num(digits.length() == 0 ? BigInteger.ZERO : new BigInteger(digits.toString()), frac, neg);
    }

    private static void padCopy(byte[] src, Field to, boolean right, Charset cs) {
        byte sp = Codec.space(cs);
        byte[] d = to.st.bytes;
        int n = to.len;
        if (!right) {
            for (int i = 0; i < n; i++) d[to.off + i] = i < src.length ? src[i] : sp;
        } else {
            for (int i = 0; i < n; i++) {
                int from = src.length - n + i;
                d[to.off + i] = from >= 0 ? src[from] : sp;
            }
        }
    }

    private static void insertEdit(Field to, byte[] src, Charset cs) {
        String pic = Editing.expandPic(to.pic);
        byte sp = Codec.space(cs);
        int k = 0;
        for (int i = 0; i < to.len; i++) {
            char c = i < pic.length() ? pic.charAt(i) : 'X';
            byte b;
            if (c == 'B') b = sp;
            else if (c == '0') b = Codec.by('0', cs);
            else if (c == '/') b = Codec.by('/', cs);
            else b = k < src.length ? src[k++] : sp;
            to.st.bytes[to.off + i] = b;
        }
    }

    /** Stores `n` into a numeric item: aligned on the decimal point, extra decimals and high digits dropped. */
    private static void store(Field to, Codec.Num n, Charset cs) {
        BigInteger m = new BigDecimal(n.mag, n.scale).setScale(to.scale, RoundingMode.DOWN).unscaledValue();
        Codec.write(to, m, n.neg, cs);
    }

    private static void edit(Field to, Codec.Num n, Charset cs) {
        BigDecimal v = new BigDecimal(n.mag, n.scale).setScale(to.scale, RoundingMode.DOWN);
        if (n.neg) v = v.negate();
        String s;
        if (to.blankWhenZero && v.signum() == 0) s = " ".repeat(to.len);
        else s = Editing.format(to.pic, v, false, null);
        padCopy(s.getBytes(cs), to, false, cs);
    }

    // ------------------------------------------------------------------------------------------------ values

    /** A numeric item's value (numeric-edited: de-edited). */
    public static BigDecimal num(Field f, Charset cs) {
        switch (cat(f)) {
            case NUMERIC: return Codec.read(f, cs).value();
            case NUM_EDITED: return deedit(f, cs).value();
            default: return parseAlnum(f.raw(), cs).value();
        }
    }

    /** The item's bytes as text. */
    public static String text(Field f, Charset cs) {
        return new String(f.st.bytes, f.off, f.len, cs);
    }

    /** A typed alphanumeric item's text back into its bytes (det-port typed groups): exactly its length, which a
     *  lifted String always has. */
    public static void putText(Field f, String s, Charset cs) {
        byte[] b = s.getBytes(cs);
        System.arraycopy(b, 0, f.st.bytes, f.off, Math.min(b.length, f.len));
    }

    // -------------------------------------------------------------------------------------- arithmetic store

    /** No ON SIZE ERROR: low-order digits beyond the scale dropped (or rounded half away from zero), high-order
     *  digits beyond the PICTURE lost. */
    public static void store(Field to, BigDecimal value, boolean rounded, Charset cs) {
        BigDecimal v = value.setScale(to.scale, rounded ? RoundingMode.HALF_UP : RoundingMode.DOWN);
        if (cat(to) == NUM_EDITED) {
            edit(to, Codec.Num.of(v), cs);
        } else {
            Codec.write(to, v.unscaledValue().abs(), v.signum() < 0, cs);
        }
    }

    /** ON SIZE ERROR: true, `to` unchanged, when the value does not fit. */
    public static boolean storeChecked(Field to, BigDecimal value, boolean rounded, Charset cs) {
        BigDecimal v = value.setScale(to.scale, rounded ? RoundingMode.HALF_UP : RoundingMode.DOWN);
        BigInteger m = v.unscaledValue().abs();
        if (cat(to) == NUM_EDITED ? m.compareTo(BigInteger.TEN.pow(to.digits)) >= 0 : !Codec.fits(to, m, v.signum() < 0)) {
            return true;
        }
        store(to, value, rounded, cs);
        return false;
    }

    // ---------------------------------------------------------------------------------------------- compare

    private static int cmpBytes(byte[] a, byte[] b, Charset cs) {
        byte sp = Codec.space(cs);
        int n = Math.max(a.length, b.length);
        for (int i = 0; i < n; i++) {
            int x = (i < a.length ? a[i] : sp) & 0xFF;
            int y = (i < b.length ? b[i] : sp) & 0xFF;
            if (x != y) return x < y ? -1 : 1;
        }
        return 0;
    }

    public static int compare(Field a, Field b, Charset cs) {
        if (cat(a) == NUMERIC && cat(b) == NUMERIC) return Integer.signum(num(a, cs).compareTo(num(b, cs)));
        return cmpBytes(a.raw(), b.raw(), cs);
    }

    // ------------------------------------------------------------------------------- typed (lifted) items
    /** An alphanumeric item held as a Java String of its length (det-port B3): `s` moved into it -- truncated on
     *  the right, or padded with spaces (COBOL's alphanumeric MOVE). */
    public static String fit(String s, int length) {
        if (s.length() >= length) {
            return s.substring(0, length);
        }
        return s + " ".repeat(length - s.length());
    }

    /** An arithmetic result stored in a binary item of `digits` (signed or not) and read back -- exactly what
     *  `store` leaves in such an item (truncation, ROUNDED, the byte width's wrap-around), through a scratch item. */
    public static long binary(BigDecimal value, int digits, boolean signed, boolean rounded, Charset cs) {
        int bytes = digits <= 4 ? 2 : digits <= 9 ? 4 : 8;
        Field t = Field.binary(new Storage(bytes), 0, digits, 0, signed, false);
        store(t, value, rounded, cs);
        return num(t, cs).longValue();
    }

    /** A numeric value stored in a zoned DISPLAY item (PIC S9(digits)V9(scale), sign overpunched) and read back:
     *  what `store` leaves there (high-order truncation, the scale, ROUNDED, an unsigned item's sign dropped). */
    public static BigDecimal zoned(BigDecimal value, int digits, int scale, boolean signed, boolean rounded,
                                   Charset cs) {
        Field t = Field.zoned(new Storage(digits), 0, digits, scale, signed, false, false);
        store(t, value, rounded, cs);
        return num(t, cs);
    }

    /** As zoned, for a packed-decimal (COMP-3) item. */
    public static BigDecimal packed(BigDecimal value, int digits, int scale, boolean signed, boolean rounded,
                                    Charset cs) {
        Field t = Field.packed(new Storage(digits / 2 + 1), 0, digits, scale, signed);
        store(t, value, rounded, cs);
        return num(t, cs);
    }

    /** The text a MOVE of `from` into an alphanumeric item of `length` bytes leaves there (any sender: COBOL's MOVE
     *  rules, through a scratch item). */
    public static String moveText(Field from, int length, Charset cs) {
        Field t = Field.alphanumeric(new Storage(length), 0, length, false);
        move(from, t, cs);
        return text(t, cs);
    }

    /** Two alphanumeric values compared as COBOL compares them: the shorter padded with spaces, byte by byte in the
     *  record charset (its collating sequence -- not Java's char order when the charset is EBCDIC). */
    public static int compareText(String a, String b, Charset cs) {
        byte[] x = a.getBytes(cs);
        byte[] y = b.getBytes(cs);
        byte sp = " ".getBytes(cs)[0];
        int n = Math.max(x.length, y.length);
        for (int i = 0; i < n; i++) {
            int u = (i < x.length ? x[i] : sp) & 0xFF;
            int v = (i < y.length ? y[i] : sp) & 0xFF;
            if (u != v) {
                return u < v ? -1 : 1;
            }
        }
        return 0;
    }

    /** Two texts compared as nonnumeric operands (a function's result, a literal): the shorter padded with
     *  spaces, character by character in their code (the record charset's byte order for a single-byte one). */
    public static int compareText(String a, String b) {
        int n = Math.max(a.length(), b.length());
        for (int i = 0; i < n; i++) {
            char x = i < a.length() ? a.charAt(i) : ' ';
            char y = i < b.length() ? b.charAt(i) : ' ';
            if (x != y) {
                return x < y ? -1 : 1;
            }
        }
        return 0;
    }

    public static int compare(Field a, String nonnumericLiteral, Charset cs) {
        return cmpBytes(a.raw(), nonnumericLiteral.getBytes(cs), cs);
    }

    public static int compare(Field a, BigDecimal numericLiteral, Charset cs) {
        if (cat(a) == ALNUM || cat(a) == GROUP || cat(a) == ALNUM_EDITED) {
            // GnuCOBOL: an alphanumeric item against a numeric literal is a text comparison with the literal's digits
            return cmpBytes(a.raw(), numericLiteral.unscaledValue().abs().toString().getBytes(cs), cs);
        }
        return Integer.signum(num(a, cs).compareTo(numericLiteral));
    }

    public static int compareFigurative(Field a, Figurative f, Charset cs) {
        if (f == Figurative.ZEROS && cat(a) == NUMERIC) return Integer.signum(num(a, cs).signum());
        byte[] b = new byte[a.len];
        Arrays.fill(b, figByte(f, cs));
        return cmpBytes(a.raw(), b, cs);
    }

    // ----------------------------------------------------------------------------------------- class tests

    public static boolean isNumeric(Field f, Charset cs) {
        byte[] d = f.st.bytes;
        switch (f.kind) {
            case NUMERIC_DISPLAY: {
                int start = f.off;
                if (f.signSeparate) {
                    char sc = Codec.ch(d[f.signLeading ? f.off : f.off + f.digits], cs);
                    if (sc != '+' && sc != '-') return false;
                    if (f.signLeading) start++;
                }
                for (int i = 0; i < f.digits; i++) {
                    char c = Codec.ch(d[start + i], cs);
                    boolean signPos = f.signed && !f.signSeparate && (f.signLeading ? i == 0 : i == f.digits - 1);
                    boolean ok = c >= '0' && c <= '9'
                            || signPos && (Codec.POSITIVE.indexOf(c) >= 0 || Codec.NEGATIVE.indexOf(c) >= 0);
                    if (!ok) return false;
                }
                return true;
            }
            case NUMERIC_PACKED: {
                for (int i = 0; i < f.len; i++) {
                    int b = d[f.off + i] & 0xFF;
                    if ((b >> 4) > 9) return false;
                    if (i < f.len - 1 && (b & 0x0F) > 9) return false;
                }
                int sign = d[f.off + f.len - 1] & 0x0F;
                return f.signed ? sign >= 0x0A : sign == 0x0F;
            }
            case NUMERIC_BINARY:
                return true;
            case NUMERIC_EDITED:
                return false;
            default: {
                if (f.len == 0) return false;
                for (int i = 0; i < f.len; i++) {
                    char c = Codec.ch(d[f.off + i], cs);
                    if (c < '0' || c > '9') return false;
                }
                return true;
            }
        }
    }

    private static boolean letters(Field f, Charset cs, boolean upper, boolean lower) {
        if (f.len == 0) return false;
        for (int i = 0; i < f.len; i++) {
            char c = Codec.ch(f.st.bytes[f.off + i], cs);
            boolean ok = c == ' ' || (upper && c >= 'A' && c <= 'Z') || (lower && c >= 'a' && c <= 'z');
            if (!ok) return false;
        }
        return true;
    }

    public static boolean isAlphabetic(Field f, Charset cs) {
        return letters(f, cs, true, true);
    }

    public static boolean isAlphabeticUpper(Field f, Charset cs) {
        return letters(f, cs, true, false);
    }

    public static boolean isAlphabeticLower(Field f, Charset cs) {
        return letters(f, cs, false, true);
    }

    // ------------------------------------------------------------------------------------------------ DISPLAY

    /**
     * The operand as IBM DISPLAY writes it (the model tests/equivalence/faults/ggdisplay.c applies to GnuCOBOL):
     * a signed zoned item with an embedded sign as its bytes, the sign overpunched; a binary or packed item as
     * zoned digits of its PICTURE (scale: no decimal point; signed: the last digit overpunched); an unsigned or
     * SIGN SEPARATE zoned item, a group, an alphanumeric or an edited item as libcob writes it.
     */
    public static String displayText(Field f, Charset cs) {
        switch (f.kind) {
            case NUMERIC_PACKED:
            case NUMERIC_BINARY: {
                Codec.Num n = Codec.read(f, cs);
                Storage s = new Storage(f.digits);
                Field z = Field.zoned(s, 0, f.digits, f.scale, f.signed, false, false);
                store(z, n, cs);
                return new String(s.bytes, cs);
            }
            default:
                return text(f, cs);
        }
    }

    // ------------------------------------------------------------------------------------------------ STRING

    /** One sending item of a STRING statement. */
    public static final class StringPart {
        final byte[] src;
        final byte[] delim; // null: DELIMITED BY SIZE

        private StringPart(byte[] src, byte[] delim) {
            this.src = src;
            this.delim = delim;
        }

        public static StringPart size(Field src) {
            return new StringPart(src.raw(), null);
        }

        public static StringPart size(String lit, Charset cs) {
            return new StringPart(lit.getBytes(cs), null);
        }

        public static StringPart delimited(Field src, Field delim) {
            return new StringPart(src.raw(), delim.raw());
        }

        public static StringPart delimited(Field src, String delim, Charset cs) {
            return new StringPart(src.raw(), delim.getBytes(cs));
        }

        public static StringPart delimited(String src, Field delim, Charset cs) {
            return new StringPart(src.getBytes(cs), delim.raw());
        }

        public static StringPart delimited(String src, String delim, Charset cs) {
            return new StringPart(src.getBytes(cs), delim.getBytes(cs));
        }
    }

    private static int indexOf(byte[] hay, int from, int to, byte[] pat) {
        for (int i = from; i + pat.length <= to; i++) {
            if (matches(hay, i, pat)) return i;
        }
        return -1;
    }

    private static boolean matches(byte[] hay, int at, byte[] pat) {
        if (at < 0 || at + pat.length > hay.length) return false;
        for (int j = 0; j < pat.length; j++) if (hay[at + j] != pat[j]) return false;
        return true;
    }

    /**
     * STRING parts... INTO into [WITH POINTER pointer]. Bytes are transferred in order; the receiving item is not
     * padded (only the bytes written change). `pointer` may be null (start at 1). Returns true on OVERFLOW (the
     * pointer is outside the receiver, or the data did not fit; what fits is transferred).
     */
    public static boolean string(Field into, Field pointer, Charset cs, StringPart... parts) {
        int off = 0;
        if (pointer != null) {
            BigDecimal p = num(pointer, cs);
            if (p.compareTo(BigDecimal.ONE) < 0 || p.compareTo(BigDecimal.valueOf(into.len)) > 0) return true;
            off = p.intValue() - 1;
        }
        boolean overflow = false;
        outer:
        for (StringPart part : parts) {
            int n = part.src.length;
            if (part.delim != null && part.delim.length > 0) {
                int at = indexOf(part.src, 0, part.src.length, part.delim);
                if (at >= 0) n = at;
            }
            int room = into.len - off;
            if (n > room) {
                System.arraycopy(part.src, 0, into.st.bytes, into.off + off, room);
                off = into.len;
                overflow = true;
                break outer;
            }
            System.arraycopy(part.src, 0, into.st.bytes, into.off + off, n);
            off += n;
        }
        if (pointer != null) store(pointer, BigDecimal.valueOf(off + 1), false, cs);
        return overflow;
    }

    // ---------------------------------------------------------------------------------------------- UNSTRING

    /** One DELIMITED BY operand of UNSTRING: a literal or an item, with ALL. */
    public static final class Delim {
        final byte[] bytes;
        final boolean all;

        private Delim(byte[] bytes, boolean all) {
            this.bytes = bytes;
            this.all = all;
        }

        public static Delim of(String lit, boolean all, Charset cs) {
            return new Delim(lit.getBytes(cs), all);
        }

        public static Delim of(Field f, boolean all) {
            return new Delim(f.raw(), all);
        }
    }

    /** One INTO operand of UNSTRING, with its optional DELIMITER IN and COUNT IN items. */
    public static final class Into {
        final Field target;
        Field delimiterIn;
        Field countIn;

        private Into(Field target) {
            this.target = target;
        }

        public static Into of(Field target) {
            return new Into(target);
        }

        public Into delimiterIn(Field f) {
            this.delimiterIn = f;
            return this;
        }

        public Into countIn(Field f) {
            this.countIn = f;
            return this;
        }
    }

    /**
     * UNSTRING src [DELIMITED BY delims] INTO intos... [WITH POINTER pointer] [TALLYING IN tallying]. `delims`
     * may be empty (the rest of the source goes to the first INTO); `pointer` and `tallying` may be null. The
     * tallying item is incremented by the number of receiving items filled. Returns true on OVERFLOW (the
     * pointer is outside the source, or source characters remain after the last INTO).
     */
    public static boolean unstring(Field src, Field pointer, Field tallying, List<Delim> delims, Charset cs,
                                   Into... intos) {
        byte[] data = src.raw();
        int off = 0;
        if (pointer != null) {
            BigDecimal p = num(pointer, cs);
            if (p.compareTo(BigDecimal.ONE) < 0 || p.compareTo(BigDecimal.valueOf(data.length)) > 0) return true;
            off = p.intValue() - 1;
        }
        int filled = 0;
        byte sp = Codec.space(cs);
        for (Into in : intos) {
            if (off >= data.length) break;
            int end = data.length;
            int dlen = 0;
            Delim hit = null;
            scan:
            for (int i = off; i < data.length; i++) {
                for (Delim d : delims) {
                    if (d.bytes.length > 0 && matches(data, i, d.bytes)) {
                        end = i;
                        dlen = d.bytes.length;
                        hit = d;
                        break scan;
                    }
                }
            }
            if (delims.isEmpty()) end = Math.min(data.length, off + in.target.len); // no DELIMITED BY: by size
            byte[] piece = Arrays.copyOfRange(data, off, end);
            move(temp(piece), in.target, cs);
            if (in.countIn != null) store(in.countIn, BigDecimal.valueOf(piece.length), false, cs);
            if (in.delimiterIn != null) {
                if (hit != null) move(temp(hit.bytes), in.delimiterIn, cs);
                else padCopy(new byte[0], in.delimiterIn, false, cs);
            }
            off = end + dlen;
            if (hit != null && hit.all) {
                while (matches(data, off, hit.bytes)) off += hit.bytes.length;
            }
            filled++;
        }
        if (pointer != null) store(pointer, BigDecimal.valueOf(off + 1), false, cs);
        if (tallying != null) store(tallying, num(tallying, cs).add(BigDecimal.valueOf(filled)), false, cs);
        return off < data.length;
    }

    // ----------------------------------------------------------------------------------------------- INSPECT

    public enum Mode { CHARACTERS, ALL, LEADING, FIRST }

    /** One TALLYING, REPLACING or CONVERTING phrase of INSPECT, with its BEFORE / AFTER INITIAL. */
    public static final class Clause {
        final Field counter; // tallying
        final Mode mode;
        final byte[] pattern; // null: CHARACTERS
        final byte[] by; // replacing
        final byte[] from; // converting
        final byte[] to;
        byte[] before;
        byte[] after;

        private Clause(Field counter, Mode mode, byte[] pattern, byte[] by, byte[] from, byte[] to) {
            this.counter = counter;
            this.mode = mode;
            this.pattern = pattern;
            this.by = by;
            this.from = from;
            this.to = to;
        }

        /** TALLYING counter FOR CHARACTERS | ALL pattern | LEADING pattern (pattern null for CHARACTERS). */
        public static Clause tally(Field counter, Mode mode, String pattern, Charset cs) {
            return new Clause(counter, mode, pattern == null ? null : pattern.getBytes(cs), null, null, null);
        }

        public static Clause tally(Field counter, Mode mode, Field pattern) {
            return new Clause(counter, mode, pattern == null ? null : pattern.raw(), null, null, null);
        }

        /** REPLACING CHARACTERS BY by | ALL / LEADING / FIRST pattern BY by. */
        public static Clause replace(Mode mode, String pattern, String by, Charset cs) {
            return new Clause(null, mode, pattern == null ? null : pattern.getBytes(cs), by.getBytes(cs), null, null);
        }

        public static Clause replace(Mode mode, Field pattern, Field by) {
            return new Clause(null, mode, pattern == null ? null : pattern.raw(), by.raw(), null, null);
        }

        /** CONVERTING from TO to. */
        public static Clause converting(String from, String to, Charset cs) {
            return new Clause(null, Mode.ALL, null, null, from.getBytes(cs), to.getBytes(cs));
        }

        public static Clause converting(Field from, Field to) {
            return new Clause(null, Mode.ALL, null, null, from.raw(), to.raw());
        }

        public Clause before(String s, Charset cs) {
            before = s.getBytes(cs);
            return this;
        }

        public Clause before(Field f) {
            before = f.raw();
            return this;
        }

        public Clause after(String s, Charset cs) {
            after = s.getBytes(cs);
            return this;
        }

        public Clause after(Field f) {
            after = f.raw();
            return this;
        }
    }

    /**
     * INSPECT target with its phrases in the order written. The phrases act on the original text; within the
     * TALLYING phrase, or the REPLACING phrase, the earlier clause takes the characters (libcob's mark array); the
     * two phrases are separate passes, as cobc emits them.
     */
    public static void inspect(Field target, Charset cs, Clause... clauses) {
        byte[] data = target.raw();
        int n = data.length;
        boolean[] mark = new boolean[n];
        byte[] out = data.clone();
        long[] counts = new long[clauses.length];
        int phase = -1;
        for (int ci = 0; ci < clauses.length; ci++) {
            Clause c = clauses[ci];
            // cobc emits TALLYING and REPLACING as separate passes: a new phase starts with fresh marks
            int ph = c.from != null ? 2 : c.by != null ? 1 : 0;
            if (ph != phase) {
                Arrays.fill(mark, false);
                phase = ph;
            }
            int start = 0;
            int end = n;
            if (c.before != null) {
                int at = indexOf(data, 0, n, c.before);
                if (at >= 0) end = at;
            }
            if (c.after != null) {
                int at = indexOf(data, 0, n, c.after);
                start = at >= 0 ? at + c.after.length : n;
            }
            if (c.from != null) {
                for (int i = start; i < end; i++) {
                    for (int j = 0; j < c.from.length; j++) {
                        if (data[i] == c.from[j]) {
                            out[i] = c.to[j];
                            break;
                        }
                    }
                }
                continue;
            }
            boolean replacing = c.by != null;
            if (c.pattern == null) {
                for (int i = start; i < end; i++) {
                    if (mark[i]) continue;
                    mark[i] = true;
                    counts[ci]++;
                    if (replacing) out[i] = c.by[0];
                }
                continue;
            }
            int pl = c.pattern.length;
            for (int i = start; i + pl <= end; i++) {
                if (!matches(data, i, c.pattern)) {
                    if (c.mode == Mode.LEADING) break;
                    continue;
                }
                boolean taken = false;
                for (int j = 0; j < pl; j++) if (mark[i + j]) taken = true;
                if (taken) continue;
                for (int j = 0; j < pl; j++) mark[i + j] = true;
                counts[ci]++;
                if (replacing) System.arraycopy(c.by, 0, out, i, Math.min(pl, c.by.length));
                i += pl - 1;
                if (c.mode == Mode.FIRST) break;
            }
        }
        System.arraycopy(out, 0, target.st.bytes, target.off, n);
        for (int ci = 0; ci < clauses.length; ci++) {
            Clause c = clauses[ci];
            if (c.counter != null) {
                store(c.counter, num(c.counter, cs).add(BigDecimal.valueOf(counts[ci])), false, cs);
            }
        }
    }
}
