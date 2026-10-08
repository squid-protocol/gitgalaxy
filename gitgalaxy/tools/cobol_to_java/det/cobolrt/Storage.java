package __PACKAGE__.cobolrt;

import java.util.Base64;

/** A COBOL storage area: WORKING-STORAGE, LINKAGE, an FD record or a symbolic map, as bytes. */
public final class Storage {
    /** Not final for one use (#4270, oracle_assumptions.md X23): a CICS program's DFHCOMMAREA holds, for a task whose
     *  COMMAREA is shorter than the record (a stated EIBCALEN), only those bytes -- a reference past them fails. */
    public byte[] bytes;

    /** #4679: the bytes that follow this area's record when a COMMAREA longer than it was passed (a RETURN / XCTL /
     *  LINK LENGTH past the receiver's DFHCOMMAREA): CICS hands over LENGTH bytes, so the ones past the record are
     *  still there, opaque -- this program does not address them -- and a further RETURN / XCTL / LINK of the area
     *  with that LENGTH passes them on (DetCics.commareaOut, Cobol.commarea). Null: none. */
    public byte[] beyond;

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
