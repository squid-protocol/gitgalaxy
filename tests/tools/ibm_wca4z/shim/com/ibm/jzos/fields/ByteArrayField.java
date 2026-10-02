package com.ibm.jzos.fields;

/** Compile shim for JZOS's ByteArrayField: its place in the record only (see {@link CobolDatatypeFactory}). */
public class ByteArrayField {
    private final int offset;
    private final int length;

    ByteArrayField(int offset, int length) {
        this.offset = offset;
        this.length = length;
    }

    public int getOffset() {
        return offset;
    }

    public int getByteLength() {
        return length;
    }
}
