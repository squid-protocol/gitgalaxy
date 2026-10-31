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

    /** #4771 (X47): where this area's record starts in `bytes`. 0 for every area but a LINKAGE record set onto a block
     *  at an offset (SET ADDRESS OF record TO ADDRESS OF a subordinate item): the record's item at offset k is then
     *  `bytes[base + k]`, so a write through the record or through the item it addresses is seen by both. Every
     *  byte reader indexes with Field.at() / offset(), never the item's own offset alone. */
    public int base;

    /** #4767: the area's own bytes while `bytes` is aliased onto another storage's (SET ADDRESS OF); null when never aliased. */
    private byte[] home;

    /** SET ADDRESS OF: this area's record is `to` from `at` on. The first alias remembers the area's own bytes. */
    public void alias(byte[] to, int at) {
        if (home == null) {
            home = bytes;
        }
        bytes = to;
        base = at;
    }

    /** Whether `bytes` is aliased onto another storage's (SET ADDRESS OF): the record is a window on a larger block. */
    public boolean aliased() {
        return home != null && bytes != home;
    }

    /** Back to the area's own bytes (a new task: the service keeps its storages, the addresses a task set are gone). */
    public void unalias() {
        if (home != null) {
            bytes = home;
            base = 0;
        }
    }

    /** All zero bytes; the translator's initial image sets every byte. */
    public Storage(int size) {
        this.bytes = new byte[size];
    }

    /** A storage holding a copy of `data` (a record, a key in its record's place). */
    // [rule RT-DATA-STORAGE-AREA]
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
