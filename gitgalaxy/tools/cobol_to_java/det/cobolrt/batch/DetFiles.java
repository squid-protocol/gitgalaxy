package __PACKAGE__.cobolrt.batch;

import __PACKAGE__.batch.CobolFiles;
import java.io.IOException;
import java.io.OutputStream;
import java.io.UncheckedIOException;
import java.nio.charset.Charset;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.Iterator;
import java.util.List;
import java.util.Optional;
import java.util.function.Function;
import java.util.function.Supplier;
import __PACKAGE__.cobolrt.Storage;

/**
 * The files of a deterministic port: each SELECT is one DetFile over its FD record's storage. Every operation goes
 * through CobolFiles (so planned statuses -- the harness's fault injection -- apply) and returns the FILE STATUS.
 */
public final class DetFiles {
    private DetFiles() {
    }

    public interface DetFile {
        String open(String mode);

        String close();

        String readNext();

        /** A keyed READ: the record whose bytes [keyOffset, keyOffset + keyLength) equal the record area's. */
        String readKey(int keyOffset, int keyLength);

        String write(int length);

        String rewrite(int length);
    }

    /** A keyed file with no store the translator could bind: OPEN and CLOSE (their statuses) only; a record
     *  operation is a hole. Exact for a program that opens the file and never reads or writes it. */
    public static final class Unbound implements DetFile {
        private final CobolFiles files;
        private final String dd;

        public Unbound(CobolFiles files, String dd) {
            this.files = files;
            this.dd = dd;
        }

        @Override
        public String open(String mode) {
            return files.open(dd);
        }

        @Override
        public String close() {
            return files.close(dd);
        }

        private static RuntimeException hole() {
            return new __PACKAGE__.cobolrt.Hole("a record operation on a file with no store bound");
        }

        @Override
        public String readNext() {
            throw hole();
        }

        @Override
        public String readKey(int keyOffset, int keyLength) {
            throw hole();
        }

        @Override
        public String write(int length) {
            throw hole();
        }

        @Override
        public String rewrite(int length) {
            throw hole();
        }
    }

    /** A sequential (QSAM) dataset: fixed-length records, read and written as raw bytes. */
    public static final class Sequential implements DetFile {
        private final CobolFiles files;
        private final String dd;
        private final Supplier<Path> path;
        private final Storage rec;
        private final int offset;
        private final int reclen;
        private Iterator<byte[]> cursor;
        private OutputStream out;

        public Sequential(CobolFiles files, String dd, Supplier<Path> path, Storage rec, int offset, int reclen) {
            this.files = files;
            this.dd = dd;
            this.path = path;
            this.rec = rec;
            this.offset = offset;
            this.reclen = reclen;
        }

        @Override
        public String open(String mode) {
            Path p = path.get();
            boolean input = mode.equals("INPUT") || mode.equals("I-O");
            String st = files.open(dd, p, input);
            if (!st.startsWith("0")) {
                return st;
            }
            try {
                if (input) {
                    List<byte[]> recs = new ArrayList<>();
                    byte[] all = Files.readAllBytes(p);
                    for (int i = 0; i + reclen <= all.length; i += reclen) {
                        recs.add(Arrays.copyOfRange(all, i, i + reclen));
                    }
                    cursor = recs.iterator();
                } else if (p != null) {
                    if (p.getParent() != null) {
                        Files.createDirectories(p.getParent());
                    }
                    out = mode.equals("EXTEND")
                            ? Files.newOutputStream(p, StandardOpenOption.CREATE, StandardOpenOption.APPEND)
                            : Files.newOutputStream(p);
                }
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
            return st;
        }

        @Override
        public String close() {
            return files.close(dd, () -> {
                if (out != null) {
                    out.close();
                    out = null;
                }
            });
        }

        @Override
        public String readNext() {
            CobolFiles.Read<byte[]> r = files.readNext(dd, cursor != null ? cursor : List.<byte[]>of().iterator());
            if (r.record() != null) {
                System.arraycopy(r.record(), 0, rec.bytes, offset, reclen);
            }
            return r.status();
        }

        @Override
        public String readKey(int keyOffset, int keyLength) {
            throw new UnsupportedOperationException("keyed READ of a sequential file");
        }

        @Override
        public String write(int length) {
            byte[] b = Arrays.copyOfRange(rec.bytes, offset, offset + reclen);
            return files.write(dd, () -> {
                if (out != null) {
                    out.write(b);
                }
            });
        }

        @Override
        public String rewrite(int length) {
            throw new UnsupportedOperationException("REWRITE of a sequential file");
        }
    }

    /**
     * An indexed (VSAM KSDS) file kept in a repository: records are entities, converted with the generated
     * fromRecord / toRecord. Records are found by comparing key bytes (any key, primary or alternate); the
     * sequential order is the primary key's EBCDIC (cp037) collating sequence, as VSAM's.
     */
    public static final class Indexed<E> implements DetFile {
        private static final Charset EBCDIC = Charset.forName("IBM037");
        private final CobolFiles files;
        private final String dd;
        private final Storage rec;
        private final int offset;
        private final int reclen;
        private final int keyOffset;
        private final int keyLength;
        private final Supplier<List<E>> all;
        private final Function<E, byte[]> toRecord;
        private final Function<byte[], E> fromRecord;
        private final java.util.function.Consumer<E> save;
        private final Charset cs;
        private Iterator<byte[]> cursor;
        private Function<byte[], Optional<E>> byId;  // the repository's findById on the key's id, when it has one

        /** A primary-key READ / WRITE / REWRITE through findById (verified against the key bytes). */
        public Indexed<E> withFindById(Function<byte[], Optional<E>> byId) {
            this.byId = byId;
            return this;
        }

        public Indexed(CobolFiles files, String dd, Storage rec, int offset, int reclen, int keyOffset, int keyLength,
                       Supplier<List<E>> all, Function<E, byte[]> toRecord, Function<byte[], E> fromRecord,
                       java.util.function.Consumer<E> save, Charset cs) {
            this.files = files;
            this.dd = dd;
            this.rec = rec;
            this.offset = offset;
            this.reclen = reclen;
            this.keyOffset = keyOffset;
            this.keyLength = keyLength;
            this.all = all;
            this.toRecord = toRecord;
            this.fromRecord = fromRecord;
            this.save = save;
            this.cs = cs;
        }

        private List<byte[]> records() {
            List<byte[]> out = new ArrayList<>();
            for (E e : all.get()) {
                byte[] b = Arrays.copyOf(toRecord.apply(e), reclen);
                out.add(b);
            }
            out.sort(Comparator.comparing(b -> new String(b, keyOffset, keyLength, cs).getBytes(EBCDIC),
                    Arrays::compareUnsigned));
            return out;
        }

        private Optional<byte[]> find(int off, int len, byte[] key) {
            if (byId != null && off == keyOffset && len == keyLength) {
                byte[] rec = new byte[keyOffset + keyLength];
                System.arraycopy(key, 0, rec, keyOffset, Math.min(key.length, keyLength));
                Optional<E> e;
                try {
                    e = byId.apply(rec);
                } catch (RuntimeException notAnId) {
                    return Optional.empty();
                }
                return e.map(x -> Arrays.copyOf(toRecord.apply(x), reclen))
                        .filter(b -> Arrays.equals(b, off, off + len, key, 0, len));
            }
            for (byte[] b : records()) {
                if (Arrays.equals(b, off, off + len, key, 0, len)) {
                    return Optional.of(b);
                }
            }
            return Optional.empty();
        }

        @Override
        public String open(String mode) {
            String st = files.open(dd);
            if (st.startsWith("0")) {
                cursor = records().iterator();
            }
            return st;
        }

        @Override
        public String close() {
            return files.close(dd);
        }

        @Override
        public String readNext() {
            CobolFiles.Read<byte[]> r = files.readNext(dd, cursor != null ? cursor : List.<byte[]>of().iterator());
            if (r.record() != null) {
                System.arraycopy(r.record(), 0, rec.bytes, offset, reclen);
            }
            return r.status();
        }

        @Override
        public String readKey(int off, int len) {
            byte[] key = Arrays.copyOfRange(rec.bytes, offset + off, offset + off + len);
            CobolFiles.Read<byte[]> r = files.read(dd, () -> find(off, len, key));
            if (r.record() != null) {
                System.arraycopy(r.record(), 0, rec.bytes, offset, reclen);
            }
            return r.status();
        }

        private byte[] area() {
            return Arrays.copyOfRange(rec.bytes, offset, offset + reclen);
        }

        @Override
        public String write(int length) {
            byte[] b = area();
            byte[] key = Arrays.copyOfRange(b, keyOffset, keyOffset + keyLength);
            return files.writeKeyed(dd, () -> find(keyOffset, keyLength, key).isPresent(),
                    () -> save.accept(fromRecord.apply(b)));
        }

        @Override
        public String rewrite(int length) {
            byte[] b = area();
            byte[] key = Arrays.copyOfRange(b, keyOffset, keyOffset + keyLength);
            return files.rewriteKeyed(dd, () -> find(keyOffset, keyLength, key).isPresent(),
                    () -> save.accept(fromRecord.apply(b)));
        }
    }
}
