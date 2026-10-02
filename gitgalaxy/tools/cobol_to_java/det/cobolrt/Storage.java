package __PACKAGE__.cobolrt;

import java.util.Base64;

/** A COBOL storage area: WORKING-STORAGE, LINKAGE, an FD record or a symbolic map, as bytes. */
public final class Storage {
    public final byte[] bytes;

    /** All zero bytes; the translator's initial image sets every byte. */
    public Storage(int size) {
        this.bytes = new byte[size];
    }

    /** A storage holding a copy of `data` (a record, a key in its record's place). */
    public static Storage of(byte[] data) {
        Storage s = new Storage(data.length);
        System.arraycopy(data, 0, s.bytes, 0, data.length);
        return s;
    }

    /** The initial image computed by the translator, base64. */
    public static Storage image(String base64) {
        byte[] b = Base64.getDecoder().decode(base64);
        Storage s = new Storage(b.length);
        System.arraycopy(b, 0, s.bytes, 0, b.length);
        return s;
    }
}
