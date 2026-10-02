package com.ibm.jzos.fields;

/**
 * Compile shim for IBM JZOS's CobolDatatypeFactory (JZOS ships only with IBM's Java SDK for z/OS).
 *
 * <p>Written for tests/tools/ibm_wca4z_port.py: it carries the factory's offset bookkeeping, which IBM's generated
 * classes run in their static initialisers, and nothing else. Every byte conversion throws (see {@link Unsupported}):
 * the adapter hands IBM's code its values through the generated setters, never through record bytes, so a call
 * here would mean the run used a code path this shim does not model.
 */
public class CobolDatatypeFactory {
    private int offset;
    private String encoding = "IBM-1047";
    private boolean trim;

    public void setStringTrimDefault(boolean trim) {
        this.trim = trim;
    }

    public void setStringEncoding(String encoding) {
        this.encoding = encoding;
    }

    public String getStringEncoding() {
        return encoding;
    }

    public int getOffset() {
        return offset;
    }

    public void incrementOffset(int length) {
        offset += length;
    }

    private int take(int length) {
        int at = offset;
        offset += length;
        return at;
    }

    public StringField getStringField(int length) {
        return new StringField(take(length), length);
    }

    public StringField getStringField(int length, boolean trim) {  // JZOS's per-field trim flag
        return new StringField(take(length), length);
    }

    public ExternalDecimalAsIntField getExternalDecimalAsIntField(int digits, boolean signed) {
        return new ExternalDecimalAsIntField(take(digits), digits);
    }

    public ExternalDecimalAsLongField getExternalDecimalAsLongField(int digits, boolean signed) {
        return new ExternalDecimalAsLongField(take(digits), digits);
    }

    public ByteArrayField getByteArrayField(int length) {
        return new ByteArrayField(take(length), length);
    }
}
