package __PACKAGE__.cobolrt;

import java.nio.charset.Charset;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;

/**
 * One execution of a SORT or MERGE statement over its SD file (IBM Enterprise COBOL for z/OS 6.4 Language
 * Reference, "SORT statement", "MERGE statement", "RELEASE statement", "RETURN statement"). Records go in -- RELEASE
 * from the SD record area, or each record of a USING file -- are ordered by the KEY phrases, and come out -- RETURN
 * into the SD record area, or written to each GIVING file.
 *
 * <ul>
 * <li>Keys compare as a relation condition compares their items ("the rules for comparison of operands in a relation
 * condition"): a numeric key by value (zoned, packed and binary alike), any other key byte by byte in the data's code
 * page, the shorter padded with spaces. The first key named is the major key. ASCENDING / DESCENDING per key.</li>
 * <li>The collating sequence is the data's byte order. The harness's data is ASCII (ISO-8859-1), where z/OS's NATIVE
 * is EBCDIC: register D1. A COLLATING SEQUENCE other than NATIVE / STANDARD-1 is refused by the translator.</li>
 * <li>WITH DUPLICATES IN ORDER: records with equal keys come out in the order they went in (USING files in the order
 * named, each file's records in read order; an input procedure's in RELEASE order). The sort is stable.</li>
 * <li>Without DUPLICATES, IBM leaves the order of records with equal keys undefined: two such records whose bytes
 * differ stop the run by name ({@link NotModelled}); equal records are indistinguishable, so their order is not.</li>
 * <li>MERGE: records with equal keys come out in the order of the USING files. IBM's result is predictable only when
 * each input is already in key order: an input out of order stops the run by name.</li>
 * </ul>
 */
public final class Sort {

    /** A key item laid over a record's bytes: the translator's Field factory with the record storage swapped in. */
    @FunctionalInterface
    public interface KeyAt {
        Field at(Storage record);
    }

    /** One KEY data item and its direction. */
    public static final class Key {
        final KeyAt at;
        final boolean ascending;

        public Key(KeyAt at, boolean ascending) {
            this.at = at;
            this.ascending = ascending;
        }
    }

    /** What IBM leaves open, refused by name rather than guessed (the harness's "not modelled"). */
    public static final class NotModelled extends RuntimeException {
        private static final long serialVersionUID = 1L;

        public NotModelled(String message) {
            super(message + ": not modelled");
        }
    }

    private final String name;
    private final int length;
    private final boolean duplicatesInOrder;
    private final Charset cs;
    private final Key[] keys;
    private final Storage left;
    private final Storage right;
    private final Field[] leftKeys;
    private final Field[] rightKeys;
    private final List<List<byte[]>> inputs = new ArrayList<>();
    private List<byte[]> sorted;
    private int next;

    /**
     * @param name the SD file's name (for the refusals' messages)
     * @param length the SD record's length: every record is this many bytes
     */
    public Sort(String name, int length, boolean duplicatesInOrder, Charset cs, Key... keys) {
        this.name = name;
        this.length = length;
        this.duplicatesInOrder = duplicatesInOrder;
        this.cs = cs;
        this.keys = keys;
        this.left = new Storage(length);
        this.right = new Storage(length);
        this.leftKeys = new Field[keys.length];
        this.rightKeys = new Field[keys.length];
        for (int k = 0; k < keys.length; k++) {
            leftKeys[k] = keys[k].at.at(left);
            rightKeys[k] = keys[k].at.at(right);
        }
        inputs.add(new ArrayList<>());
    }

    /** RELEASE: a copy of the SD record area's bytes (`record` is the SD record), into the sort. */
    public void release(Field record) {
        if (sorted != null) {
            throw new IllegalStateException("RELEASE " + name + " after its input phase");
        }
        byte[] r = record.raw();
        if (r.length != length) {
            throw new NotModelled("RELEASE " + name + ": a record of " + r.length + " bytes, the sort's are " + length);
        }
        inputs.get(inputs.size() - 1).add(r);
    }

    /** A record of a USING file. Its bytes go in as they are (the translator refuses a USING file whose records are
     *  not the SD record's length). */
    public void add(Field record) {
        release(record);
    }

    /** MERGE: the next USING file's records start here (called between files). */
    public void nextInput() {
        inputs.add(new ArrayList<>());
    }

    private int compare(byte[] a, byte[] b) {
        System.arraycopy(a, 0, left.bytes, 0, length);
        System.arraycopy(b, 0, right.bytes, 0, length);
        for (int k = 0; k < keys.length; k++) {
            int c = Cobol.compare(leftKeys[k], rightKeys[k], cs);
            if (c != 0) {
                return keys[k].ascending ? c : -c;
            }
        }
        return 0;
    }

    /** The end of the input phase of a SORT: the records in key order (a stable sort). */
    public void sort() {
        List<byte[]> all = new ArrayList<>();
        inputs.forEach(all::addAll);
        Comparator<byte[]> order = this::compare;
        all.sort(order);  // List.sort is stable (a merge sort)
        if (!duplicatesInOrder) {
            for (int i = 1; i < all.size(); i++) {
                if (compare(all.get(i - 1), all.get(i)) == 0 && !Arrays.equals(all.get(i - 1), all.get(i))) {
                    throw new NotModelled("SORT " + name + " without DUPLICATES: records with equal keys (IBM: "
                            + "their order is undefined)");
                }
            }
        }
        sorted = all;
        next = 0;
    }

    /** MERGE: every USING file's records, merged in key order; equal keys in the order the files are named. */
    public void merge() {
        for (int f = 0; f < inputs.size(); f++) {
            List<byte[]> in = inputs.get(f);
            for (int i = 1; i < in.size(); i++) {
                if (compare(in.get(i - 1), in.get(i)) > 0) {
                    throw new NotModelled("MERGE " + name + ": an input file out of key order (IBM: the result is "
                            + "unpredictable)");
                }
            }
        }
        // the inputs are each in order: a stable sort of them, file after file, is their merge
        List<byte[]> all = new ArrayList<>();
        inputs.forEach(all::addAll);
        all.sort(this::compare);
        sorted = all;
        next = 0;
    }

    /** RETURN: the next record into the SD record area; false (AT END) when none is left. */
    public boolean returnInto(Field record) {
        byte[] r = next();
        if (r == null) {
            return false;
        }
        record.putRaw(r);
        return true;
    }

    /** The next record in order (a RETURN, or a GIVING file's next record), or null at the end. */
    public byte[] next() {
        if (sorted == null) {
            throw new IllegalStateException("RETURN " + name + " before its output phase");
        }
        return next < sorted.size() ? sorted.get(next++) : null;
    }

    /** GIVING: the records again from the first (each GIVING file receives them all). */
    public void rewind() {
        next = 0;
    }

    /** The SD file's sort in progress: RELEASE belongs in an input procedure, RETURN in an output procedure (IBM);
     *  outside one there is none, and the run stops by name. */
    public static Sort active(Sort sort, String what) {
        if (sort == null) {
            throw new NotModelled(what);
        }
        return sort;
    }

    /** An implicit OPEN / READ / CLOSE of a USING or GIVING file must succeed; any other status stops by name. */
    public static void expect(String status, String what, String... ok) {
        for (String s : ok) {
            if (s.equals(status)) {
                return;
            }
        }
        throw new NotModelled(what + " gave FILE STATUS " + status);
    }
}
