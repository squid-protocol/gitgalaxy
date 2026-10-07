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

    /** #4607 x X6: a WRITEQ's LENGTH n, refused (PastFrom) when it runs past FROM's own length. */
    public static int within(Field f, int n, String what) {
        if (n > f.length()) {
            throw new PastFrom(what + " LENGTH " + n + " > FROM's " + f.length() + " bytes: not modelled");
        }
        return n;
    }

    /** Bytes into a field's area, at most its length (a record READ INTO it; the rest is left as it was). */
    /** #4270: PUT CONTAINER FROM(f) FLENGTH(n): the first n bytes of the area, none below zero (CicsTask answers
     *  LENGERR RESP2 1). FLENGTH past FROM's end reads the bytes that follow the item in storage, which GnuCOBOL
     *  lays out unlike IBM's compiler: refused, as the stub refuses it (oracle_assumptions.md X6). */
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
    public static byte[] startData(Field f, int n) {
        if (n > f.length()) {
            throw new UnsupportedOperationException("START LENGTH " + n + " > FROM's " + f.length()
                    + " bytes: not modelled");
        }
        return n <= 0 ? new byte[0] : bytes(f, n);
    }

    /** #4270 slice 2: text into a whole field, padded with spaces or truncated -- a COBOL MOVE of the 4- / 8-byte
     *  value RETRIEVE RTRANSID / RTERMID / QUEUE returns into the program's area. */
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

    /** #4528: the region's code page -- the one TS items are in (CicsTask: "the bytes the program wrote, in the
     *  region's code page"). `declared` is the estate's EBCDIC page for the program, else CCSID 037; the system
     *  property gitgalaxy.cics.charset names another. A deployment fact, like CobolRecords.charset(). */
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
    public static void putText(Field f, String text, Charset cs) {
        put(f, text.getBytes(cs));
    }

    /** A symbolic map field's subfields as the program set them: the attribute (<f>A / <f>F), colour (<f>C),
     *  highlight (<f>H) bytes -- X'00' and a space are "not set" -- and length -1 (<f>L: the cursor). */
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
    public static String currentDate(java.time.LocalDateTime now) {
        return now.format(java.time.format.DateTimeFormatter.ofPattern("yyyyMMddHHmmss", java.util.Locale.ROOT))
                + String.format(java.util.Locale.ROOT, "%02d", now.getNano() / 10_000_000) + "+0000";
    }

    /** The condition a RESP value names (IBM CICS TS, RESP values: DFHRESP; the spec's table, CicsSpec). */
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
    public static boolean ignoredByDefault(String condition) {
        return "EOC".equals(condition);
    }

    /** #4414: the label HANDLE AID gives the key pressed (EIBAID's name: ENTER, CLEAR, PA1-PA3, PF1-PF24), else
     *  ANYKEY's -- "any PA key, any PF key, or the CLEAR key, but not ENTER" (IBM CICS TS, EXEC CICS HANDLE AID);
     *  null when neither has one ("control returns to the application program at the instruction immediately
     *  following the input command"). A key deactivated by a HANDLE AID without a label is -1 in `aids`: IBM
     *  ("This deactivates the effect of that option") does not say whether ANYKEY's label then takes it, so that
     *  is refused by name. */
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
}
