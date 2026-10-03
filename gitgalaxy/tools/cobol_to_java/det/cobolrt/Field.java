package __PACKAGE__.cobolrt;

/** A data item: a view over a {@link Storage} with its COBOL category, size and USAGE. Immutable. */
public final class Field {
    public enum Kind {
        GROUP, ALPHANUMERIC, ALPHABETIC, NUMERIC_DISPLAY, NUMERIC_PACKED, NUMERIC_BINARY, NUMERIC_EDITED,
        ALPHANUMERIC_EDITED
    }

    final Storage st;
    final int off;
    final int len;
    final Kind kind;
    final int digits;
    final int scale;
    final boolean signed;
    final boolean signLeading;
    final boolean signSeparate;
    final boolean nativeBin;
    final boolean justRight;
    final boolean blankWhenZero;
    final String pic;

    private Field(Storage st, int off, int len, Kind kind, int digits, int scale, boolean signed, boolean signLeading,
                  boolean signSeparate, boolean nativeBin, boolean justRight, boolean blankWhenZero, String pic) {
        this.st = st;
        this.off = off;
        this.len = len;
        this.kind = kind;
        this.digits = digits;
        this.scale = scale;
        this.signed = signed;
        this.signLeading = signLeading;
        this.signSeparate = signSeparate;
        this.nativeBin = nativeBin;
        this.justRight = justRight;
        this.blankWhenZero = blankWhenZero;
        this.pic = pic;
    }

    public static Field group(Storage s, int offset, int length) {
        return new Field(s, offset, length, Kind.GROUP, 0, 0, false, false, false, false, false, false, null);
    }

    public static Field alphanumeric(Storage s, int offset, int length, boolean justifiedRight) {
        return new Field(s, offset, length, Kind.ALPHANUMERIC, 0, 0, false, false, false, false, justifiedRight,
                false, null);
    }

    public static Field alphabetic(Storage s, int offset, int length, boolean justifiedRight) {
        return new Field(s, offset, length, Kind.ALPHABETIC, 0, 0, false, false, false, false, justifiedRight,
                false, null);
    }

    /** PIC S9(n)V9(m) DISPLAY. `digits` includes the decimals. */
    public static Field zoned(Storage s, int offset, int digits, int scale, boolean signed, boolean signLeading,
                              boolean signSeparate) {
        int len = digits + (signed && signSeparate ? 1 : 0);
        return new Field(s, offset, len, Kind.NUMERIC_DISPLAY, digits, scale, signed, signLeading,
                signed && signSeparate, false, false, false, null);
    }

    /** COMP-3. */
    public static Field packed(Storage s, int offset, int digits, int scale, boolean signed) {
        return new Field(s, offset, digits / 2 + 1, Kind.NUMERIC_PACKED, digits, scale, signed, false, false, false,
                false, false, null);
    }

    /** COMP / COMP-4 / BINARY (big-endian, truncating to the PICTURE's digits) or, with `native_`, COMP-5. */
    public static Field binary(Storage s, int offset, int digits, int scale, boolean signed, boolean native_) {
        return new Field(s, offset, binaryLength(digits), Kind.NUMERIC_BINARY, digits, scale, signed, false, false,
                native_, false, false, null);
    }

    /** GnuCOBOL's BINARY-CHAR / -SHORT / -LONG / -DOUBLE: native (little-endian) binary of exactly `length` bytes,
     *  never truncated to digits (`digits` is the full range's, for conversions only). */
    public static Field binaryNative(Storage s, int offset, int length, int digits, boolean signed) {
        return new Field(s, offset, length, Kind.NUMERIC_BINARY, digits, 0, signed, false, false, true, false, false,
                null);
    }

    public static Field numericEdited(Storage s, int offset, int length, String picture, boolean blankWhenZero) {
        int[] shape = Editing.shape(picture);
        return new Field(s, offset, length, Kind.NUMERIC_EDITED, shape[0] + shape[1], shape[1], false, false, false,
                false, false, blankWhenZero, picture);
    }

    public static Field alphanumericEdited(Storage s, int offset, int length, String picture) {
        return new Field(s, offset, length, Kind.ALPHANUMERIC_EDITED, 0, 0, false, false, false, false, false, false,
                picture);
    }

    static int binaryLength(int digits) {
        return digits <= 4 ? 2 : digits <= 9 ? 4 : 8;
    }

    /** A subscript, 1-based: offset + (index - 1) * stride. */
    public Field at(int index, int stride) {
        return new Field(st, off + (index - 1) * stride, len, kind, digits, scale, signed, signLeading, signSeparate,
                nativeBin, justRight, blankWhenZero, pic);
    }

    /** Reference modification (start 1-based; a null length means to the end): an ALPHANUMERIC view. */
    public Field ref(int start, Integer length) {
        int n = length == null ? len - (start - 1) : length;
        return new Field(st, off + start - 1, n, Kind.ALPHANUMERIC, 0, 0, false, false, false, false, false, false,
                null);
    }

    public Storage storage() {
        return st;
    }

    public int offset() {
        return off;
    }

    public int length() {
        return len;
    }

    public Kind kind() {
        return kind;
    }

    public int digits() {
        return digits;
    }

    public int scale() {
        return scale;
    }

    public boolean isSigned() {
        return signed;
    }

    public boolean isNumeric() {
        return kind == Kind.NUMERIC_DISPLAY || kind == Kind.NUMERIC_PACKED || kind == Kind.NUMERIC_BINARY;
    }

    /** A copy of the item's bytes. */
    public byte[] raw() {
        byte[] b = new byte[len];
        System.arraycopy(st.bytes, off, b, 0, len);
        return b;
    }

    /** Overwrites the item's bytes (at most its length) with `b`. */
    public void putRaw(byte[] b) {
        System.arraycopy(b, 0, st.bytes, off, Math.min(b.length, len));
    }
}
