package __PACKAGE__.cobolrt;

import java.nio.charset.Charset;
import java.nio.charset.CharsetEncoder;
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
 * <li>The collating sequence is the data's byte order -- NATIVE, STANDARD-1, STANDARD-2 -- unless the SORT / MERGE
 * (or the program's PROGRAM COLLATING SEQUENCE) names an EBCDIC or a literal alphabet: then a {@link Collating}
 * orders the alphanumeric keys (a group, alphanumeric, alphabetic or edited item; a numeric key still compares by
 * value). The harness's data is ASCII (ISO-8859-1), where z/OS's NATIVE is EBCDIC: register D1.</li>
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

    /**
     * A COLLATING SEQUENCE alphabet (IBM Enterprise COBOL for z/OS 6.4 Language Reference, "ALPHABET clause"): each
     * byte of the data its position in the sequence. It is kept twice -- as IBM orders it and as GnuCOBOL (the
     * harness's oracle) does -- and a comparison the two decide differently stops the run by name: the port sorts as
     * IBM does where the oracle can prove it, and nowhere else.
     * <ul>
     * <li>EBCDIC: IBM, each character's code in EBCDIC (code page 037, the default CODEPAGE(1140)'s order); GnuCOBOL,
     * its own ASCII-to-EBCDIC table ({@link #GNU_EBCDIC}), which places [ ] ^ | and every byte above X'7F'
     * elsewhere.</li>
     * <li>A literal alphabet: the characters named take positions in the order named (ALSO: the same position;
     * THRU: the contiguous characters of the native character set), every other character after them in native
     * order. IBM's native set is EBCDIC; GnuCOBOL's is the data's bytes (register D1). 'A' THRU 'Z', say, holds
     * seven more characters in EBCDIC than in ASCII.</li>
     * </ul>
     */
    public static final class Collating {
        /** GnuCOBOL 3.x's EBCDIC alphabet: per ASCII / ISO-8859-1 byte, its position (measured: a SORT of all 256
         *  bytes under ALPHABET ... IS EBCDIC, released in both orders WITH DUPLICATES, gives one order). */
        static final int[] GNU_EBCDIC = {
            0, 1, 2, 3, 55, 45, 46, 47, 22, 5, 37, 11, 12, 13, 14, 15,
            16, 17, 18, 19, 60, 61, 50, 38, 24, 25, 63, 39, 28, 29, 30, 31,
            64, 90, 127, 123, 91, 108, 80, 125, 77, 93, 92, 78, 107, 96, 75, 97,
            240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 122, 94, 76, 126, 110, 111,
            124, 193, 194, 195, 196, 197, 198, 199, 200, 201, 209, 210, 211, 212, 213, 214,
            215, 216, 217, 226, 227, 228, 229, 230, 231, 232, 233, 173, 224, 189, 95, 109,
            121, 129, 130, 131, 132, 133, 134, 135, 136, 137, 145, 146, 147, 148, 149, 150,
            151, 152, 153, 162, 163, 164, 165, 166, 167, 168, 169, 192, 106, 208, 161, 7,
            104, 220, 81, 66, 67, 68, 71, 72, 82, 83, 84, 87, 86, 88, 99, 103,
            113, 156, 158, 203, 204, 205, 219, 221, 223, 236, 252, 176, 177, 178, 62, 180,
            69, 85, 206, 222, 73, 105, 154, 155, 171, 159, 186, 184, 183, 170, 138, 139,
            182, 181, 98, 79, 100, 101, 102, 32, 33, 34, 112, 35, 114, 115, 116, 190,
            118, 119, 120, 128, 36, 21, 140, 141, 142, 65, 6, 23, 40, 41, 157, 42,
            43, 44, 9, 10, 172, 74, 174, 175, 27, 48, 49, 250, 26, 51, 52, 53,
            54, 89, 8, 56, 188, 57, 160, 191, 202, 58, 254, 59, 4, 207, 218, 20,
            225, 143, 70, 117, 253, 235, 238, 237, 144, 239, 179, 251, 185, 234, 187, 255,
        };

        final String name;
        final int[] ibm;
        final int[] oracle;

        private Collating(String name, int[] ibm, int[] oracle) {
            this.name = name;
            this.ibm = ibm;
            this.oracle = oracle;
        }

        /** ALPHABET name IS EBCDIC, over data in `cs`. */
        public static Collating ebcdic(String name, Charset cs) {
            int[] ibm = new int[256];
            int[] oracle = new int[256];
            for (int b = 0; b < 256; b++) {
                ibm[b] = ebcdicCode(b, cs);
                oracle[b] = GNU_EBCDIC[b];
            }
            return new Collating(name, ibm, oracle);
        }

        /**
         * A literal alphabet over data in `cs`. Each entry is "A" and the characters that share the next position
         * (one character, or several joined by ALSO), or "T" and two characters: literal-1 THRU literal-2, each
         * character between them (descending when literal-1 is the greater) its own position.
         */
        public static Collating alphabet(String name, Charset cs, String... entries) {
            int[] ebcdic = new int[256];
            int[] bytes = new int[256];
            for (int b = 0; b < 256; b++) {
                ebcdic[b] = ebcdicCode(b, cs);
                bytes[b] = b;
            }
            CharsetEncoder ibmEnc = Charset.forName("IBM037").newEncoder();
            CharsetEncoder dataEnc = cs.newEncoder();
            return new Collating(name, positions(name, entries, ibmEnc, ebcdic), positions(name, entries, dataEnc, bytes));
        }

        /** Per data byte, its position: the entries' characters coded by `enc` into a native set of 256 codes, the
         *  codes no entry names after them in code order; `codeOf[b]` is data byte b's code (-1: none). */
        private static int[] positions(String name, String[] entries, CharsetEncoder enc, int[] codeOf) {
            int[] pos = new int[256];
            Arrays.fill(pos, -1);
            int next = 0;
            for (String e : entries) {
                if (e.charAt(0) == 'T') {
                    int from = code(name, e.charAt(1), enc);
                    int to = code(name, e.charAt(2), enc);
                    int step = from <= to ? 1 : -1;
                    for (int c = from; ; c += step) {
                        next = place(name, pos, c, next) + 1;
                        if (c == to) {
                            break;
                        }
                    }
                } else {
                    for (int i = 1; i < e.length(); i++) {
                        place(name, pos, code(name, e.charAt(i), enc), next);
                    }
                    next++;
                }
            }
            for (int c = 0; c < 256; c++) {
                if (pos[c] < 0) {
                    pos[c] = next++;
                }
            }
            int[] out = new int[256];
            for (int b = 0; b < 256; b++) {
                out[b] = codeOf[b] < 0 ? -1 : pos[codeOf[b]];
            }
            return out;
        }

        private static int place(String name, int[] pos, int code, int at) {
            if (pos[code] >= 0) {
                throw new NotModelled("ALPHABET " + name + ": a character named twice");
            }
            pos[code] = at;
            return at;
        }

        private static int code(String name, char ch, CharsetEncoder enc) {
            if (!enc.canEncode(ch)) {
                throw new NotModelled("ALPHABET " + name + ": U+" + Integer.toHexString(ch) + " has no "
                        + enc.charset().name() + " code");
            }
            return enc.charset().encode(String.valueOf(ch)).get(0) & 0xFF;
        }

        /** Data byte b's character in `cs`, as its code-page-037 code (-1: it has none). */
        private static int ebcdicCode(int b, Charset cs) {
            String ch = new String(new byte[] {(byte) b}, cs);
            CharsetEncoder enc = Charset.forName("IBM037").newEncoder();
            if (ch.length() != 1 || !enc.canEncode(ch)) {
                return -1;
            }
            return Charset.forName("IBM037").encode(ch).get(0) & 0xFF;
        }

        private static int compare(byte[] a, byte[] b, int[] w) {
            for (int i = 0; i < a.length; i++) {
                int x = w[a[i] & 0xFF];
                int y = w[b[i] & 0xFF];
                if (a[i] != b[i] && (x < 0 || y < 0)) {
                    return Integer.MIN_VALUE;
                }
                if (x != y) {
                    return x < y ? -1 : 1;
                }
            }
            return 0;
        }

        /** Two keys' bytes (one item: the same length) in this sequence; a comparison IBM's sequence and GnuCOBOL's
         *  decide differently, or one over a byte with no EBCDIC character, stops the run by name. */
        int compare(byte[] a, byte[] b, String sort) {
            int i = compare(a, b, ibm);
            int o = compare(a, b, oracle);
            if (i == Integer.MIN_VALUE || i != o) {
                throw new NotModelled(sort + " COLLATING SEQUENCE " + name + ": keys " + Arrays.toString(a) + " and "
                        + Arrays.toString(b) + (i == Integer.MIN_VALUE ? " hold a byte with no EBCDIC character"
                        : " are ordered differently by IBM and by GnuCOBOL") + " (register D1)");
            }
            return i;
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
    private final Collating collating;
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
        this(name, length, duplicatesInOrder, cs, null, keys);
    }

    /**
     * @param collating the COLLATING SEQUENCE's alphabet for the alphanumeric keys, or null for the data's byte order
     */
    public Sort(String name, int length, boolean duplicatesInOrder, Charset cs, Collating collating, Key... keys) {
        this.name = name;
        this.collating = collating;
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
            int c = collating != null && !leftKeys[k].isNumeric()
                    ? collating.compare(leftKeys[k].raw(), rightKeys[k].raw(), name)
                    : Cobol.compare(leftKeys[k], rightKeys[k], cs);
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
        if (!duplicatesInOrder || collating != null) {
            for (int i = 1; i < all.size(); i++) {
                // under a Collating, every neighbour pair compared once more: the order is then IBM's and the
                // oracle's (a pair the two decide differently stops the run), whichever pairs the sort compared
                if (compare(all.get(i - 1), all.get(i)) == 0 && !duplicatesInOrder
                        && !Arrays.equals(all.get(i - 1), all.get(i))) {
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
        if (collating != null) {
            for (int i = 1; i < all.size(); i++) {
                compare(all.get(i - 1), all.get(i));  // as in sort(): the neighbours in both orders
            }
        }
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
