package com.ibm.jzos.fields;

/** Compile shim for JZOS's ExternalDecimalAsLongField: its place in the record only (see {@link CobolDatatypeFactory}). */
public class ExternalDecimalAsLongField {
    private final int offset;
    private final int length;

    ExternalDecimalAsLongField(int offset, int length) {
        this.offset = offset;
        this.length = length;
    }

    public int getOffset() {
        return offset;
    }

    public int getByteLength() {
        return length;
    }

    public long getLong(byte[] bytes, int base) {
        throw Unsupported.of("ExternalDecimalAsLongField.getLong");
    }

    public void putLong(long value, byte[] bytes, int base) {
        throw Unsupported.of("ExternalDecimalAsLongField.putLong");
    }
}
