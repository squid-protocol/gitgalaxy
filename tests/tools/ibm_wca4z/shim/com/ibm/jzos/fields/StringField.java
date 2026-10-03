package com.ibm.jzos.fields;

/** Compile shim for JZOS's StringField: its place in the record only (see {@link CobolDatatypeFactory}). */
public class StringField {
    private final int offset;
    private final int length;

    StringField(int offset, int length) {
        this.offset = offset;
        this.length = length;
    }

    public int getOffset() {
        return offset;
    }

    public int getByteLength() {
        return length;
    }

    public String getString(byte[] bytes, int base) {
        throw Unsupported.of("StringField.getString");
    }

    public void putString(String value, byte[] bytes, int base) {
        throw Unsupported.of("StringField.putString");
    }
}
