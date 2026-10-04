package com.ibm.jzos.fields;

/** Compile shim for JZOS's ExternalDecimalAsIntField: its place in the record only (see {@link CobolDatatypeFactory}). */
public class ExternalDecimalAsIntField {
    private final int offset;
    private final int length;

    ExternalDecimalAsIntField(int offset, int length) {
        this.offset = offset;
        this.length = length;
    }

    public int getOffset() {
        return offset;
    }

    public int getByteLength() {
        return length;
    }

    public int getInt(byte[] bytes, int base) {
        throw Unsupported.of("ExternalDecimalAsIntField.getInt");
    }

    public void putInt(int value, byte[] bytes, int base) {
        throw Unsupported.of("ExternalDecimalAsIntField.putInt");
    }
}
