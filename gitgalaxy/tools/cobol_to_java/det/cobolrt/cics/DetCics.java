package __PACKAGE__.cobolrt.cics;

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

    /** Bytes into a field's area, at most its length (a record READ INTO it; the rest is left as it was). */
    public static void put(Field f, byte[] data) {
        System.arraycopy(data, 0, f.storage().bytes, f.offset(), Math.min(data.length, f.length()));
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

    /** The condition a RESP value names (IBM CICS TS, RESP values: DFHRESP). */
    public static String condition(int resp) {
        return switch (resp) {
            case 0 -> "NORMAL";
            case 12 -> "FILENOTFOUND";
            case 13 -> "NOTFND";
            case 14 -> "DUPREC";
            case 15 -> "DUPKEY";
            case 16 -> "INVREQ";
            case 17 -> "IOERR";
            case 18 -> "NOSPACE";
            case 19 -> "NOTOPEN";
            case 20 -> "ENDFILE";
            case 22 -> "LENGERR";
            case 26 -> "ITEMERR";
            case 27 -> "PGMIDERR";
            case 36 -> "MAPFAIL";
            case 44 -> "QIDERR";
            case 70 -> "NOTAUTH";
            case 84 -> "DISABLED";
            default -> "RESP" + resp;
        };
    }

    public static int resp(String condition) {
        return switch (condition) {
            case "NORMAL" -> 0;
            case "LENGERR" -> 22;
            case "PGMIDERR" -> 27;
            case "INVREQ" -> 16;
            case "NOTAUTH" -> 70;
            default -> -1;
        };
    }
}
