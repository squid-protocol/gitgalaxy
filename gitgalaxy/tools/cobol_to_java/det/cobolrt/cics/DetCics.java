package __PACKAGE__.cobolrt.cics;

import __PACKAGE__.cics.CicsSpec;
import __PACKAGE__.cics.CicsTask;
import __PACKAGE__.cobolrt.Cobol;
import __PACKAGE__.cobolrt.Field;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.NavigableSet;
import java.util.Optional;
import java.util.TreeSet;
import java.util.function.Consumer;
import java.util.function.Function;
import java.util.function.Supplier;

/** The CICS boundary of a deterministic port: file stores over the generated entities, a symbolic map's
 *  subfields, RECEIVE's input fields, and RESP condition names. */
public final class DetCics {

    /** A POINTER in a COMMAREA DTO into the port's storage: NULL (null / blank / "NULL") is all zero bytes. An address
     *  is not portable -- it names storage the port does not have -- so it stops the run by name. */
    // [rule RT-CICS-POINTER-IN-COMMAREA]
    public static void pointerIn(String value, __PACKAGE__.cobolrt.Storage s, int at, int len) {
        if (value != null && !value.isBlank() && !"NULL".equals(value.strip())) {
            throw new UnsupportedOperationException("a POINTER that is not NULL in a COMMAREA is not modelled");
        }
        Arrays.fill(s.bytes, at, at + len, (byte) 0);
    }

    /** A POINTER from the port's storage into a COMMAREA DTO: null for NULL (all zero bytes); an address, not
     *  portable, stops the run by name. */
    public static String pointerOut(__PACKAGE__.cobolrt.Storage s, int at, int len) {
        for (int i = at; i < at + len; i++) {
            if (s.bytes[i] != 0) {
                throw new UnsupportedOperationException("a POINTER that is not NULL in a COMMAREA is not modelled");
            }
        }
        return null;
    }
    private DetCics() {
    }

    private static final Charset EBCDIC = Charset.forName("IBM037");

    /** A CICS file over a repository: records as bytes (the entity's toRecord), found by the bytes at the file's
     *  key (the base cluster's, or an alternate index's), in the key's EBCDIC (cp037) order, as VSAM's. */
    public static final class Store<E> {
        private final Supplier<List<E>> all;
        private final Function<E, byte[]> toRecord;
        private final Function<byte[], E> fromRecord;
        private final Consumer<E> save;
        private final Consumer<E> delete;
        private final int keyOffset;
        private final int keyLength;
        private final Charset cs;
        private Function<byte[], Optional<E>> byId;  // the repository's findById on the key's id, when it has one

        public Store(Supplier<List<E>> all, Function<E, byte[]> toRecord, Function<byte[], E> fromRecord,
                     Consumer<E> save, Consumer<E> delete, int keyOffset, int keyLength, Charset cs) {
            this.all = all;
            this.toRecord = toRecord;
            this.fromRecord = fromRecord;
            this.save = save;
            this.delete = delete;
            this.keyOffset = keyOffset;
            this.keyLength = keyLength;
            this.cs = cs;
        }

        /** A keyed read through the repository's findById: `byId` gets a buffer with the key in its record place. */
        public Store<E> withFindById(Function<byte[], Optional<E>> byId) {
            this.byId = byId;
            return this;
        }

        private Optional<Object[]> findById(byte[] key) {
            byte[] rec = new byte[keyOffset + keyLength];
            System.arraycopy(key, 0, rec, keyOffset, Math.min(key.length, keyLength));
            Optional<E> e;
            try {
                e = byId.apply(rec);
            } catch (RuntimeException notAnId) {  // key bytes no stored key has (non-digits in a numeric key)
                return Optional.empty();
            }
            byte[] k = Arrays.copyOf(key, keyLength);
            // exactly the key bytes asked for, as VSAM compares them -- a loosely decoded id matches nothing
            return e.map(x -> new Object[] {x, toRecord.apply(x)}).filter(r -> Arrays.equals(key((byte[]) r[1]), k));
        }

        private byte[] key(byte[] rec) {
            return Arrays.copyOfRange(Arrays.copyOf(rec, Math.max(rec.length, keyOffset + keyLength)), keyOffset,
                    keyOffset + keyLength);
        }

        private Comparator<byte[]> order() {
            return Comparator.comparing(k -> new String(k, cs).getBytes(EBCDIC), Arrays::compareUnsigned);
        }

        private List<Object[]> rows() {
            List<Object[]> out = new ArrayList<>();
            for (E e : all.get()) {
                out.add(new Object[] {e, toRecord.apply(e)});
            }
            Comparator<byte[]> o = order();
            out.sort((a, b) -> o.compare(key((byte[]) a[1]), key((byte[]) b[1])));
            return out;
        }

        /** The first record (in key order) whose key equals `key` (its first keyLength bytes). */
        // [rule RT-CICS-FILE-KEY-ORDER]
        public Optional<byte[]> find(byte[] key) {
            if (byId != null) {
                return findById(key).map(r -> (byte[]) r[1]);
            }
            byte[] k = Arrays.copyOf(key, keyLength);
            for (Object[] r : rows()) {
                if (Arrays.equals(key((byte[]) r[1]), k)) {
                    return Optional.of((byte[]) r[1]);
                }
            }
            return Optional.empty();
        }

        /** #4270 READ GTEQ / GENERIC (IBM, EXEC CICS READ; oracle_assumptions.md X22): in key order (the browse's),
         *  the first record whose key's first `length` bytes equal `key`'s -- a generic key when `length` is shorter
         *  than the key -- or, with `gteq`, are greater ("the first record that has a greater key is retrieved"). */
        // [rule RT-CICS-READ-GTEQ-GENERIC]
        public Optional<byte[]> search(byte[] key, int length, boolean gteq) {
            byte[] k = Arrays.copyOf(key, length);
            Comparator<byte[]> o = order();
            for (Object[] r : rows()) {
                int c = o.compare(Arrays.copyOf(key((byte[]) r[1]), length), k);
                if (c == 0 || gteq && c > 0) {
                    return Optional.of((byte[]) r[1]);
                }
            }
            return Optional.empty();
        }

        /** A record's key bytes (what a READ UPDATE found by a search holds). */
        public byte[] keyOf(byte[] rec) {
            return key(rec);
        }

        public boolean exists(byte[] key) {
            return find(key).isPresent();
        }

        /** The keys as text in the record charset, ordered as the file is. */
        public NavigableSet<String> keys() {
            Comparator<byte[]> o = order();
            TreeSet<String> keys = new TreeSet<>((a, b) -> o.compare(a.getBytes(cs), b.getBytes(cs)));
            for (Object[] r : rows()) {
                keys.add(new String(key((byte[]) r[1]), cs));
            }
            return keys;
        }

        public void store(byte[] rec) {
            save.accept(fromRecord.apply(rec));
        }

        @SuppressWarnings("unchecked")
        public void remove(byte[] key) {
            if (byId != null) {
                findById(key).ifPresent(r -> delete.accept((E) r[0]));
                return;
            }
            byte[] k = Arrays.copyOf(key, keyLength);
            for (Object[] r : rows()) {
                if (Arrays.equals(key((byte[]) r[1]), k)) {
                    delete.accept((E) r[0]);
                    return;
                }
            }
        }

        public int keyLength() {
            return keyLength;
        }
    }

    /** The bytes of a field (a RIDFLD, a FROM area). */
    public static byte[] bytes(Field f) {
        return Arrays.copyOfRange(f.storage().bytes, f.offset(), f.offset() + f.length());
    }

    /** `n` bytes of storage from a field's first byte -- a command's FROM(area) LENGTH(n), which may run past the
     *  area into what follows it in its record (as CICS reads it: from the area's address, n bytes). */
    // [rule RT-CICS-FROM-LENGTH]
    public static byte[] bytes(Field f, int n) {
        return Arrays.copyOfRange(f.storage().bytes, f.offset(), f.offset() + n);
    }

    /** #4607 x X6: a WRITEQ TS / TD whose LENGTH runs past its FROM item. CICS writes the storage that follows the
     *  item, which GnuCOBOL lays out unlike IBM's compiler: the stub stops the task there ("not modelled") and the
     *  det port refuses at the same statement, so both sides' tasks are judged up to it (oracle_assumptions.md X6). */
    public static final class PastFrom extends UnsupportedOperationException {
        public PastFrom(String message) {
            super(message);
        }
    }

    /** The longest record a WRITEQ carries (the stub's GG-PADQ). */
    private static final int MAX_RECORD = 32767;

    /** X6 (ASSUMED, owner 2026-10-21): a WRITEQ's LENGTH n past FROM's own length writes FROM's bytes then SPACES (in the program's page `cs`) to n
     *  (IBM takes the storage that follows the item: undefined; GnuCOBOL's layout differs). The stub pads the same way.
     *  A LENGTH over the longest record is refused (PastFrom), as the stub refuses it. */
    // [rule RT-CICS-WRITEQ-PAST-FROM]
    public static byte[] padded(Field f, int n, String what, Charset cs) {
        if (n > MAX_RECORD) {
            throw new PastFrom(what + " LENGTH " + n + " > " + MAX_RECORD + ": not modelled");
        }
        byte[] out = new byte[Math.max(n, 0)];
        int own = Math.min(out.length, f.length());
        System.arraycopy(f.storage().bytes, f.offset(), out, 0, own);
        byte[] space = " ".getBytes(cs);
        for (int i = own; i < out.length; i++) {
            out[i] = space[i % space.length];
        }
        return out;
    }

    /** #4607 x X6: a LENGTH n, refused (PastFrom) when it runs past FROM's own length (DOCUMENT CREATE; a WRITEQ pads,
     *  see padded). */
    // [rule RT-CICS-DOCUMENT]
    public static int within(Field f, int n, String what) {
        if (n > f.length()) {
            throw new PastFrom(what + " LENGTH " + n + " > FROM's " + f.length() + " bytes: not modelled");
        }
        return n;
    }

    /** #4769 (X33): DOCUMENT CREATE TEXT / BINARY LENGTH(n): `n` bytes of the area, null for a negative `n` (the task
     *  answers LENGERR), refused (PastFrom) when `n` runs past the area, as a WRITEQ's LENGTH past FROM is. */
    // [rule RT-CICS-DOCUMENT]
    public static byte[] documentBytes(Field f, int n) {
        if (n < 0) {
            return null;
        }
        return bytes(f, within(f, n, "DOCUMENT CREATE"));
    }

    /** #4769 (X33): DOCUMENT RETRIEVE INTO(into): the document's bytes (at most MAXLENGTH of them) go INTO, the rest of INTO
     *  as it was. More bytes than INTO holds are refused (PastFrom): CICS writes the storage that follows INTO, which
     *  GnuCOBOL lays out unlike IBM's compiler (oracle_assumptions.md X6). */
    public static void putDocument(Field into, byte[] data) {
        if (data.length > into.length()) {
            throw new PastFrom("DOCUMENT RETRIEVE MAXLENGTH beyond INTO: " + data.length + " > " + into.length()
                    + " bytes: not modelled");
        }
        put(into, data);
    }

    /** #4270: `n` bytes from a field's first byte within its record -- a SEND TEXT FROM(f) LENGTH(n) past FROM sends
     *  the items that follow it in its record (GenApp LGICVS01). Past the record's end the bytes are those of the
     *  compiler's WORKING-STORAGE layout, unlike IBM's under GnuCOBOL: refused as X6 is (PastFrom). */
    // [rule RT-CICS-SEND-TEXT-PAST-FROM]
    public static byte[] withinRecord(Field f, int n, String what) {
        if (n < 0 || f.offset() + n > f.storage().bytes.length) {
            throw new PastFrom(what + " LENGTH " + n + " runs past FROM's record: not modelled");
        }
        return bytes(f, n);
    }

    /** #4501: an XCTL COMMAREA(area) LENGTH(n) with n past the target's DTO (`size` bytes). IBM passes n bytes
     *  from the area's first byte (EXEC CICS XCTL: LENGTH is the COMMAREA's length; the receiver sees EIBCALEN = n),
     *  and a receiver addresses them although its DFHCOMMAREA does not define them. The DTO cannot carry them, so
     *  they travel as the bytes: the area's storage from its first byte, up to its record's end, then LOW-VALUES
     *  (the storage that follows the record is not laid out by this port: oracle_assumptions.md X10). A length within
     *  the DTO keeps the DTO (`dto`). The bytes are the region's EBCDIC (cp037), as every COMMAREA a task carries
     *  is (the harness reads a byte[] so); commareaIn undoes it. Text round-trips; other bytes only where `cs`
     *  maps them to the same cp037 byte back (LOW-VALUES and SPACES do). */
    // [rule RT-CICS-XCTL-COMMAREA-LENGTH]
    public static Object commareaOut(Object dto, Field f, Integer length, int size, Charset cs) {
        if (length == null || length <= size) {
            return dto;
        }
        byte[] out = new byte[length];
        int n = Math.min(length, Math.max(0, f.storage().bytes.length - f.offset()));
        System.arraycopy(f.storage().bytes, f.offset(), out, 0, n);
        Cobol.beyond(f, out, n, false);  // #4679: opaque bytes a longer COMMAREA brought past the record go on
        return new String(out, cs).getBytes(EBCDIC);
    }

    /** #4679: a COMMAREA's bytes (in `cs`, the program's storage page) as one travels when no DTO types it: the
     *  region's EBCDIC, as commareaOut gives them (commareaIn undoes it). */
    public static byte[] commareaBytes(byte[] area, Charset cs) {
        return new String(area, cs).getBytes(EBCDIC);
    }

    /** #5053: the bytes of a COMMAREA that came as another program's DTO: its layout (toCommarea, #4449), in the record
     *  charset -- this port's page. A class with no layout is refused, never guessed. */
    public static byte[] layoutBytes(Object dto) {
        try {
            return (byte[]) dto.getClass().getMethod("toCommarea").invoke(dto);
        } catch (ReflectiveOperationException | ClassCastException e) {
            throw new IllegalStateException("the COMMAREA is a " + dto.getClass().getName()
                    + ", which this program does not take and no layout converts (#5053)", e);
        }
    }

    /** #4501: the bytes of a COMMAREA commareaOut passed, in the receiving program's storage charset. */
    public static byte[] commareaIn(byte[] ebcdic, Charset cs) {
        return new String(ebcdic, EBCDIC).getBytes(cs);
    }

    /** Bytes into a field's area, at most its length (a record READ INTO it; the rest is left as it was). */
    /** #4270: PUT CONTAINER FROM(f) FLENGTH(n): the first n bytes of the area, none below zero (CicsTask answers
     *  LENGERR RESP2 1). FLENGTH past FROM's end reads the bytes that follow the item in storage, which GnuCOBOL
     *  lays out unlike IBM's compiler: refused, as the stub refuses it (oracle_assumptions.md X6). */
    // [rule RT-CICS-CONTAINER-LENGTH]
    public static byte[] containerData(Field f, int n) {
        if (n > f.length()) {
            throw new UnsupportedOperationException("PUT CONTAINER FLENGTH " + n + " > FROM's " + f.length()
                    + " bytes: not modelled");
        }
        return n <= 0 ? new byte[0] : bytes(f, n);
    }

    /** #4270: GET CONTAINER INTO(into) FLENGTH(most): the most the area takes. A FLENGTH past INTO's end would have
     *  CICS write the storage that follows it (laid out unlike IBM's by GnuCOBOL), and one below zero is not
     *  documented: both refused. */
    public static int containerLimit(Field into, int most) {
        if (most < 0 || most > into.length()) {
            throw new UnsupportedOperationException("GET CONTAINER FLENGTH " + most + " for a " + into.length()
                    + "-byte INTO: not modelled");
        }
        return most;
    }

    /** #4270 slice 2: START FROM(f) LENGTH(n): the first n bytes of the area, none for n below one (CicsTask answers
     *  LENGERR: IBM, "Occurs if LENGTH is not greater than zero"). A LENGTH past FROM's end reads the bytes that
     *  follow the item in storage, which GnuCOBOL lays out unlike IBM's compiler: refused, as the stub refuses it
     *  (oracle_assumptions.md X6). */
    // [rule RT-CICS-START-LENGTH]
    public static byte[] startData(Field f, int n) {
        if (n > f.length()) {
            throw new UnsupportedOperationException("START LENGTH " + n + " > FROM's " + f.length()
                    + " bytes: not modelled");
        }
        return n <= 0 ? new byte[0] : bytes(f, n);
    }

    /** #4270 slice 2: text into a whole field, padded with spaces or truncated -- a COBOL MOVE of the 4- / 8-byte
     *  value RETRIEVE RTRANSID / RTERMID / QUEUE returns into the program's area. */
    // [rule RT-CICS-RETRIEVE-INTO]
    public static void putPadded(Field f, String text, Charset cs) {
        StringBuilder b = new StringBuilder(text);
        while (b.length() < f.length()) {
            b.append(' ');
        }
        byte[] data = b.toString().getBytes(cs);
        System.arraycopy(data, 0, f.storage().bytes, f.offset(), f.length());
    }

    public static void put(Field f, byte[] data) {
        System.arraycopy(data, 0, f.storage().bytes, f.offset(), Math.min(data.length, f.length()));
    }

    /** READ ... INTO(into) LENGTH(max) (#4436; IBM, EXEC CICS READ): the record goes INTO, truncated to `max` when
     *  longer, the rest of INTO left as it was. Returns the RESP: 0 (NORMAL), or 22 (LENGERR, RESP2 11) for a record
     *  longer than `max`. Refused, as not modelled: a negative LENGTH; a record moved past INTO (CICS writes the
     *  storage that follows it, which GnuCOBOL lays out unlike IBM's compiler: oracle_assumptions.md X6); LENGERR on
     *  READ UPDATE (`update`), since IBM does not say whether the record is then held. */
    // [rule RT-CICS-READ-INTO-LENGTH]
    public static int readInto(Field into, byte[] record, int max, boolean update) {
        if (max < 0) {
            throw new UnsupportedOperationException("READ LENGTH " + max + " (negative): not modelled");
        }
        int moved = Math.min(record.length, max);
        if (moved > into.length()) {
            throw new UnsupportedOperationException("READ INTO LENGTH: " + moved + " bytes past INTO's "
                    + into.length() + ": not modelled");
        }
        boolean lengerr = record.length > max;
        if (lengerr && update) {
            throw new UnsupportedOperationException("READ UPDATE LENGERR (whether the record is held): not modelled");
        }
        System.arraycopy(record, 0, into.storage().bytes, into.offset(), moved);
        return lengerr ? 22 : 0;
    }

    /** #5079 (X57): READQ TD QUEUE INTO: the record's bytes (already cut to LENGTH) go INTO, the rest of INTO left as it
     *  was. Refused, as not modelled, a record moved past INTO (CICS writes the storage that follows it, which GnuCOBOL
     *  lays out unlike IBM's compiler: oracle_assumptions.md X6), as READ INTO's is. */
    // [rule RT-CICS-READQ-TD-INTO]
    public static void readTd(Field into, byte[] record) {
        if (record.length > into.length()) {
            throw new UnsupportedOperationException("READQ TD INTO LENGTH: " + record.length + " bytes past INTO's "
                    + into.length() + ": not modelled");
        }
        System.arraycopy(record, 0, into.storage().bytes, into.offset(), record.length);
    }

    /** #4415 slice 1: EXEC CICS BIF DEEDIT FIELD(f) LENGTH(n) (IBM CICS TS, "BIF DEEDIT"): the first `n` bytes of the
     *  field, as the region's EBCDIC page (`region`) holds them, edited in place -- the characters other than the
     *  digits X'F0'-X'F9' removed, the digits right-aligned and padded on the left with zeros; a field that ends in a
     *  minus sign (X'60') or CR gets the negative zone X'D' in its rightmost byte; a rightmost byte whose zone is
     *  X'A'-X'F' is returned unaltered ("This permits the application program to operate on a zoned numeric field");
     *  a 1-byte field is returned unaltered. Refused by name (register X26): characters beyond 7-bit ASCII, a LENGTH
     *  past the field. A field in which no digit remains becomes all zeros (ASSUMED: IBM does not say, its rule read
     *  literally gives that). */
    // [rule RT-CICS-BIF-DEEDIT]
    public static void deedit(Field f, int n, Charset cs, Charset region) {
        if (n > f.length()) {
            throw new PastFrom("BIF DEEDIT LENGTH " + n + " > FIELD's " + f.length() + " bytes: not modelled");
        }
        String chars = new String(bytes(f, n), cs);
        for (int i = 0; i < chars.length(); i++) {
            if (chars.charAt(i) >= 0x80) {
                throw new UnsupportedOperationException(String.format("BIF DEEDIT of U+%04X, beyond 7-bit ASCII:"
                        + " not modelled", (int) chars.charAt(i)));
            }
        }
        byte[] edited = new String(deeditEbcdic(chars.getBytes(region)), region).getBytes(cs);
        System.arraycopy(edited, 0, f.storage().bytes, f.offset(), n);
    }

    static byte[] deeditEbcdic(byte[] e) {
        int n = e.length;
        if (n == 1) {
            return e.clone();
        }
        boolean cr = n >= 2 && (e[n - 2] & 0xFF) == 0xC3 && (e[n - 1] & 0xFF) == 0xD9;
        boolean negative = (e[n - 1] & 0xFF) == 0x60 || cr;
        int end = n;
        int kept = -1;
        if (negative) {
            end = n - (cr ? 2 : 1);
        } else if ((e[n - 1] & 0xF0) >= 0xA0) {
            kept = e[n - 1] & 0xFF;
            end = n - 1;
        }
        byte[] digits = new byte[n];
        int k = 0;
        for (int i = 0; i < end; i++) {
            int b = e[i] & 0xFF;
            if (b >= 0xF0 && b <= 0xF9) {
                digits[k++] = e[i];
            }
        }
        // a field with no digit left: IBM's rule read literally (non-digits removed, the digits right-aligned and
        // padded on the left with zeros) leaves all zeros (ASSUMED, register X26)
        byte[] out = new byte[n];
        Arrays.fill(out, (byte) 0xF0);
        int last = n - 1;
        if (kept >= 0) {
            out[last] = (byte) kept;
            last--;
        }
        for (int j = k - 1; j >= 0; j--, last--) {
            out[last] = digits[j];
        }
        if (negative) {
            out[n - 1] = (byte) (0xD0 | (out[n - 1] & 0x0F));
        }
        return out;
    }

    /** #4528: the region's code page -- the one TS items are in (CicsTask: "the bytes the program wrote, in the
     *  region's code page"). `declared` is the estate's EBCDIC page for the program, else CCSID 037; the system
     *  property gitgalaxy.cics.charset names another. A deployment fact, like CobolRecords.charset(). */
    // [rule RT-CICS-REGION-CODE-PAGE]
    public static Charset region(String declared) {
        return Charset.forName(System.getProperty("gitgalaxy.cics.charset", declared));
    }

    /** #4528: the program's bytes (in `cs`, its storage's page) as the region's (`region`), byte by byte: how the
     *  COBOL side's region moves a TS item between its storage and the queue. Each byte must be one character of
     *  both pages: anything else stops the run by name, never a substituted byte. */
    public static byte[] toRegion(byte[] data, Charset cs, Charset region) {
        return transcode(data, cs, region);
    }

    /** #4528: a region's bytes (a TS item read) in the program's page: toRegion's inverse. */
    public static byte[] fromRegion(byte[] data, Charset region, Charset cs) {
        return transcode(data, region, cs);
    }

    private static byte[] transcode(byte[] data, Charset from, Charset to) {
        if (data == null || from.equals(to)) {
            return data;
        }
        java.nio.charset.CharsetEncoder enc = to.newEncoder()
                .onMalformedInput(java.nio.charset.CodingErrorAction.REPORT)
                .onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT);
        byte[] out = new byte[data.length];
        for (int i = 0; i < data.length; i++) {
            char c = character(from, data[i]);
            if (usesLfForNl(to) && (c == '\n' || c == '\u0085')) {
                out[i] = (byte) (c == '\n' ? 0x25 : 0x15);  // CDRA's LF and NEL, as the COBOL side's cp037
                continue;
            }
            try {
                java.nio.ByteBuffer b = enc.encode(java.nio.CharBuffer.wrap(new char[] {c}));
                if (b.remaining() != 1) {
                    throw new java.nio.charset.CharacterCodingException();
                }
                out[i] = b.get();
            } catch (java.nio.charset.CharacterCodingException e) {
                throw new UnsupportedOperationException(String.format("byte %02X in %s is U+%04X, not one byte in %s:"
                        + " not modelled", data[i] & 0xFF, from, (int) c, to), e);
            }
        }
        return out;
    }

    /** Whether `page` is one of the JDK's EBCDIC pages that take NL (X'15') for LF -- decoding both X'15' and X'25'
     *  as LF and encoding LF as X'15' (a USS convenience). CDRA's -- and the COBOL side's (Python's cp037) -- NL is
     *  NEL (U+0085) and LF is X'25': transcode keeps those. */
    private static boolean usesLfForNl(Charset page) {
        return new String(new byte[] {0x15}, page).equals("\n") && new String(new byte[] {0x25}, page).equals("\n");
    }

    /** The one character a byte is in `page` (X'15' NEL on a page usesLfForNl). */
    private static char character(Charset page, byte b) {
        java.nio.charset.CharsetDecoder dec = page.newDecoder()
                .onMalformedInput(java.nio.charset.CodingErrorAction.REPORT)
                .onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT);
        try {
            java.nio.CharBuffer c = dec.decode(java.nio.ByteBuffer.wrap(new byte[] {b}));
            if (c.remaining() != 1) {
                throw new java.nio.charset.CharacterCodingException();
            }
            char ch = c.get();
            return b == 0x15 && usesLfForNl(page) ? '\u0085' : ch;
        } catch (java.nio.charset.CharacterCodingException e) {
            throw new UnsupportedOperationException(String.format("byte %02X is no character of %s on its own: not"
                    + " modelled", b & 0xFF, page), e);
        }
    }

    /** Text into the first bytes of a field, the rest left as it was (ASSIGN SYSID: 4 bytes into an 8-byte area). */
    // [rule RT-CICS-ASSIGN-TEXT]
    public static void putText(Field f, String text, Charset cs) {
        put(f, text.getBytes(cs));
    }

    /** A symbolic map field's subfields as the program set them: the attribute (<f>A / <f>F), colour (<f>C),
     *  highlight (<f>H) bytes -- X'00' and a space are "not set" -- and length -1 (<f>L: the cursor). */
    // [rule RT-CICS-BMS-SUBFIELDS]
    public static void subfields(CicsTask.MapSubfields sub, String name, Field len, Field attr, Field color,
                                 Field hilight, Charset cs) {
        byte space = " ".getBytes(cs)[0];
        if (len != null && Cobol.num(len, cs).compareTo(BigDecimal.ONE.negate()) == 0) {
            sub.cursor(name);
        }
        if (attr != null) {
            byte b = attr.storage().bytes[attr.offset()];
            if (b != 0 && b != space) {
                sub.attr(name, b & 0xFF);
            }
        }
        if (color != null) {
            byte b = color.storage().bytes[color.offset()];
            if (b != 0 && b != space) {
                sub.color(name, b & 0xFF);
            }
        }
        if (hilight != null) {
            byte b = hilight.storage().bytes[hilight.offset()];
            if (b != 0 && b != space) {
                sub.hilight(name, b & 0xFF);
            }
        }
    }

    /** RECEIVE MAP: a typed field -- its text (padded with spaces) and its length (the text without trailing
     *  blanks), as BMS sets <f>I and <f>L. */
    public static void typed(Field input, Field len, String text, Charset cs) {
        byte[] t = text.getBytes(cs);
        byte[] area = new byte[input.length()];
        Arrays.fill(area, " ".getBytes(cs)[0]);
        System.arraycopy(t, 0, area, 0, Math.min(t.length, area.length));
        put(input, area);
        if (len != null) {
            Cobol.store(len, BigDecimal.valueOf(text.stripTrailing().length()), false, cs);
        }
    }

    /** FUNCTION CURRENT-DATE from the task's clock: YYYYMMDDHHMMSShh and the UTC offset (the region's zone,
     *  as MainframeClock's default: UTC). */
    // [rule RT-CICS-CURRENT-DATE]
    public static String currentDate(java.time.LocalDateTime now) {
        return now.format(java.time.format.DateTimeFormatter.ofPattern("yyyyMMddHHmmss", java.util.Locale.ROOT))
                + String.format(java.util.Locale.ROOT, "%02d", now.getNano() / 10_000_000) + "+0000";
    }

    /** The condition a RESP value names (IBM CICS TS, RESP values: DFHRESP; the spec's table, CicsSpec). */
    // [rule RT-CICS-RESP-VALUES]
    public static String condition(int resp) {
        return CicsSpec.condition(resp);
    }

    /** The RESP value of a condition (IBM CICS TS, RESP values; the spec's table, CicsSpec). */
    public static int resp(String condition) {
        return CicsSpec.resp(condition);
    }

    /** #4413: a condition whose default action -- with no HANDLE CONDITION label for it -- is to ignore it, the
     *  command going on as if it had completed normally (IBM CICS TS, EXEC CICS RECEIVE (LUTYPE2/LUTYPE3): EOC,
     *  "Default action: ignore the condition"). Every other condition's default is an abend. */
    // [rule RT-CICS-DEFAULT-ACTION]
    public static boolean ignoredByDefault(String condition) {
        return "EOC".equals(condition);
    }

    /** #4414: the label HANDLE AID gives the key pressed (EIBAID's name: ENTER, CLEAR, PA1-PA3, PF1-PF24), else
     *  ANYKEY's -- "any PA key, any PF key, or the CLEAR key, but not ENTER" (IBM CICS TS, EXEC CICS HANDLE AID);
     *  null when neither has one ("control returns to the application program at the instruction immediately
     *  following the input command"). A key deactivated by a HANDLE AID without a label is -1 in `aids`: IBM
     *  ("This deactivates the effect of that option") does not say whether ANYKEY's label then takes it, so that
     *  is refused by name. */
    // [rule RT-CICS-HANDLE-AID]
    public static Integer aidLabel(java.util.Map<String, Integer> aids, String key) {
        if (key == null) {
            return null;
        }
        Integer h = aids.get(key);
        if (h != null && h >= 0) {
            return h;
        }
        Integer any = key.startsWith("PA") || key.startsWith("PF") || "CLEAR".equals(key) ? aids.get("ANYKEY") : null;
        if (any == null || any < 0) {
            return null;
        }
        if (h != null) {
            throw new IllegalStateException("HANDLE AID " + key + " deactivated while ANYKEY has a label: whether "
                    + "ANYKEY takes the key is not documented");
        }
        return any;
    }

    /** #4414: what PUSH HANDLE saves of a program's own handler state (IBM CICS TS, EXEC CICS PUSH HANDLE: "suspend
     *  the current effect of the IGNORE CONDITION, HANDLE ABEND, HANDLE AID, and HANDLE CONDITION commands"): its
     *  HANDLE / IGNORE CONDITION entries and its HANDLE AID labels, copied; HANDLE ABEND is CicsTask's own. */
    public record Handlers(java.util.Map<String, Integer> conditions, java.util.Map<String, Integer> aids) {
        public Handlers {
            conditions = new java.util.HashMap<>(conditions);
            aids = new java.util.HashMap<>(aids);
        }

        /** POP HANDLE: the state saved replaces the program's. */
        public void restore(java.util.Map<String, Integer> intoConditions, java.util.Map<String, Integer> intoAids) {
            intoConditions.clear();
            intoConditions.putAll(conditions);
            intoAids.clear();
            intoAids.putAll(aids);
        }
    }

    /** #4413: a terminal RECEIVE INTO: the data received into the first bytes of the area, the rest left as it was
     *  (IBM moves the data it received, no more). */
    // [rule RT-CICS-TERMINAL-RECEIVE]
    public static void received(Field into, String data, Charset cs) {
        put(into, data.getBytes(cs));
    }

    /** #4413: a terminal RECEIVE SET(ADDRESS OF record): the record now addresses the data CICS received (valid "until
     *  the next receive command or the end of task"). The port's record keeps its own storage, so the data is copied
     *  into it; a byte past the data is not CICS's to define and is X'00' here (a program reading past LENGTH reads
     *  undefined storage on CICS, docs/language_status/oracle_assumptions.md X15). */
    public static void receivedSet(Field record, String data, Charset cs) {
        byte[] b = data.getBytes(cs);
        Arrays.fill(record.storage().bytes, record.offset(), record.offset() + record.length(), (byte) 0);
        System.arraycopy(b, 0, record.storage().bytes, record.offset(), Math.min(b.length, record.length()));
    }

    // ---- #4771 (register X47): pointers to task storage. A POINTER item holds the handle of a block the task owns
    //      (CicsTask.getmain / acquireReceived / addressOf), 8 bytes big-endian, NULL all zero. An address is never an
    //      int the program can do arithmetic on: the translator refuses a pointer that a REDEFINES overlays. ------------

    /** The handle a POINTER item holds (0: NULL). */
    public static long pointerValue(Field ptr) {
        long h = 0;
        for (int i = 0; i < 8; i++) {
            h = (h << 8) | (ptr.storage().bytes[ptr.offset() + i] & 0xFF);
        }
        return h;
    }

    /** Store a handle into a POINTER item. */
    public static void setPointer(Field ptr, long handle) {
        for (int i = 7; i >= 0; i--) {
            ptr.storage().bytes[ptr.offset() + i] = (byte) handle;
            handle >>>= 8;
        }
    }

    /** GETMAIN SET(ptr) FLENGTH / LENGTH INITIMG(area) (IBM, EXEC CICS GETMAIN; X47): the pointer takes the new block's
     *  handle; under LENGERR (RESP2 1) it is set to zero. Returns {RESP, RESP2}. INITIMG is one byte. */
    // [rule RT-CICS-POINTER-LANE]
    public static int[] getmain(CicsTask task, Field ptr, long length, boolean halfword, Field initimg) {
        if (initimg.length() != 1) {
            throw new PastFrom("GETMAIN INITIMG is not one byte: not modelled");
        }
        long[] r = task.getmain(length, halfword, initimg.storage().bytes[initimg.offset()] & 0xFF);
        setPointer(ptr, r[2]);
        return new int[] {(int) r[0], (int) r[1]};
    }

    /** WEB RECEIVE SET(ptr) (X47): the body becomes a block of task storage the pointer addresses. */
    public static void receivedBlock(CicsTask task, Field ptr, String body, Charset cs) {
        setPointer(ptr, task.acquireReceived(body.getBytes(cs)));
    }

    /** SET(ptr) of a RECEIVE, RETRIEVE, READQ TS, GET CONTAINER or file read (X58): a new block of task storage holding the
     *  data, its handle in the pointer. `key` is what ends the pointer's validity (CicsTask.acquireSet). */
    // [rule RT-CICS-SET-BLOCK]
    public static void setBlock(CicsTask task, Field ptr, String key, byte[] data) {
        setPointer(ptr, task.acquireSet(key, data));
    }

    /** As above; `syncEnds`: a SYNCPOINT also ends the pointer (a READ UPDATE SET, a READNEXT / READPREV SET). */
    public static void setBlock(CicsTask task, Field ptr, String key, byte[] data, boolean syncEnds) {
        setPointer(ptr, task.acquireSet(key, data, syncEnds));
    }

    public static void setBlock(CicsTask task, Field ptr, String key, String data, Charset cs) {
        setBlock(task, ptr, key, data.getBytes(cs));
    }

    /** SET ADDRESS OF record TO ptr: the record's bytes are the block's, so a write through either shows in the other. */
    public static void setAddress(CicsTask task, Field record, Field ptr) {
        wholeRecord(record, "SET ADDRESS OF");
        long handle = pointerValue(ptr);
        record.storage().bytes = task.storageAt(handle, record.length());
        record.storage().base = task.offsetAt(handle);
    }

    /** SET ADDRESS OF record TO ADDRESS OF other: both are one storage from here on. */
    public static void setAddressOfRecord(CicsTask task, Field record, Field other) {
        wholeRecord(record, "SET ADDRESS OF");
        wholeRecord(other, "ADDRESS OF");
        if (other.storage().bytes.length < record.length()) {
            throw new UnsupportedOperationException("SET ADDRESS OF a record longer than its storage: not modelled");
        }
        record.storage().bytes = other.storage().bytes;
        record.storage().base = other.storage().base;
    }

    /** SET ADDRESS OF record TO ADDRESS OF item, an item inside a larger storage (ZECS001's ZF-DATA in ZF-RECORD; #4771,
     *  X47): the record's bytes are the storage's from the item on, through a Storage window, so a write through either
     *  shows in the other. A record longer than what follows the item is refused (IBM: bytes that are not the program's). */
    public static void setAddressOfItem(CicsTask task, Field record, Field item) {
        wholeRecord(record, "SET ADDRESS OF");
        if (item.storage().bytes.length - item.offset() < record.length()) {
            throw new UnsupportedOperationException("SET ADDRESS OF a record longer than the storage after the item: not modelled");
        }
        record.storage().bytes = item.storage().bytes;
        record.storage().base = item.offset();
    }

    /** SET ptr TO ADDRESS OF record: the handle of the record's bytes. */
    public static void setPointerToRecord(CicsTask task, Field ptr, Field record) {
        wholeRecord(record, "ADDRESS OF");
        setPointer(ptr, task.addressOf(record.storage().bytes, record.storage().base));
    }

    /** SET ptr TO ADDRESS OF item (an item that is not a whole 01 record; #4771): the handle of the item's bytes, the same
     *  one each time (CicsTask.addressOf with the item's offset). */
    public static void setPointerToItem(CicsTask task, Field ptr, Field item) {
        setPointer(ptr, task.addressOf(item.storage().bytes, item.offset()));
    }

    /** `MOVE view TO view` over two numeric views of pointers (#4771, X47): the address is copied, as the handle is. */
    public static void copyPointer(Field to, Field from) {
        setPointer(to, pointerValue(from));
    }

    /** `ADD n TO view` / `SUBTRACT n FROM view` over a numeric view of a pointer (#4771, X47): the pointer addresses the
     *  same storage n bytes further on (or back), the handle of that offset (CicsTask.addressOf). Refused: a null or
     *  freed pointer, and a result outside the storage (IBM: an address that is not the program's). */
    // [rule RT-CICS-POINTER-LANE]
    public static void advancePointer(CicsTask task, Field ptr, long n) {
        long handle = pointerValue(ptr);
        byte[] bytes = task.storageAt(handle, 0);
        long at = task.offsetAt(handle) + n;
        if (at < 0 || at > bytes.length) {
            throw new UnsupportedOperationException(
                "pointer arithmetic leaves the storage the pointer addresses (" + at + " of " + bytes.length + " bytes)");
        }
        setPointer(ptr, task.addressOf(bytes, (int) at));
    }

    /** `IF ptr-a = ptr-b` (#5042, X56): the two pointers address the same storage (CicsTask.samePointer). */
    public static boolean samePointer(CicsTask task, Field a, Field b) {
        return task.samePointer(pointerValue(a), pointerValue(b));
    }

    /** ADDRESS COMMAREA(ptr) (X59): the handle of the DFHCOMMAREA record's bytes; a task with no COMMAREA (EIBCALEN 0) is
     *  refused (IBM sets X'FF000000', not the COBOL NULL a handle can hold). */
    // [rule RT-CICS-ADDRESS]
    public static void addressCommarea(CicsTask task, Field ptr, Field record, int eibcalen) {
        if (eibcalen == 0) {
            throw new PastFrom("ADDRESS COMMAREA with no COMMAREA: not modelled");
        }
        setPointerToRecord(task, ptr, record);
    }

    /** #5119 (X56): OS/VS COBOL's `MOVE cell TO fullword` (a chained storage area's pointer to the next area): the fullword
     *  takes the token standing for the cell's address (CicsTask.bllToken), 4 bytes big-endian. */
    // [rule RT-CICS-BLL-ADDRESS]
    public static void bllToData(CicsTask task, Field cell, Field data) {
        int v = task.bllToken(pointerValue(cell));
        for (int i = 3; i >= 0; i--) {
            data.storage().bytes[data.offset() + i] = (byte) v;
            v >>>= 8;
        }
    }

    /** #5119 (X56): `MOVE fullword TO cell`: the cell takes the address the fullword's token stands for (0: NULL). */
    public static void bllFromData(CicsTask task, Field data, Field cell) {
        int v = 0;
        for (int i = 0; i < 4; i++) {
            v = (v << 8) | (data.storage().bytes[data.offset() + i] & 0xFF);
        }
        setPointer(cell, task.bllPointer(v));
    }

    /** #5119 (X56): a paragraph name re-addresses a record through its BLL cell (IBM: "Insertion of a paragraph name causes
     *  the compiler to generate code to reestablish addressability"); a null cell leaves the record as it is (ASSUMED). */
    public static void bllReload(CicsTask task, Field record, Field cell) {
        if (pointerValue(cell) != 0) {
            setAddress(task, record, cell);
        }
    }

    private static void wholeRecord(Field record, String what) {
        if (record.offset() != record.storage().base) {
            throw new UnsupportedOperationException(what + " an item that is not a whole 01 record: not modelled");
        }
    }
}
