package __PACKAGE__.cobolrt.dli;

import __PACKAGE__.cobolrt.Field;
import __PACKAGE__.cobolrt.Storage;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * IMS DL/I database calls (#4893) for a batch DL/I program -- IMS enters its ENTRY 'DLITCBL' with its PCBs, and it
 * issues CALL 'CBLTDLI' USING function pcb io-area [ssa ...]. The twin of the equivalence harness's COBOL-side model
 * (tests/equivalence/ims/ggdli.c): the same rules and the same refusals, register family I
 * (docs/language_status/register/I*.md); IBM's IMS Application Programming and IMS Messages and Codes ("DL/I status
 * codes") are the reference.
 *
 * The database is stated, not connected: {@code gitgalaxy.dli.dir} holds dbd.cfg, psb.cfg and each database's seed
 * (written by tests/tools/equivalence_ims.py from the DBD / PSB sources), and {@link #leave} writes each database to
 * {@code gitgalaxy.dli.out}. Modelled: GU GHU GN GHN GNP GHNP ISRT REPL DLET through a DB PCB, unqualified SSAs and
 * SSAs qualified by one field, status blank GA GK GE GB GP II DJ DA AC AJ AK AD AM; anything else stops the run by
 * name (UnsupportedOperationException "CBLTDLI: ... is not modelled").
 */
public final class DetDli {
    private DetDli() {
    }

    private static final class Segm {
        String name;
        int db;
        int parent;
        int bytes;
        int level;
        int key = -1;
    }

    private static final class Fld {
        String name;
        int seg;
        int start;
        int bytes;
        char type;
    }

    private static final class Node {
        int seg;
        byte[] data;
        Node parent;
        final List<Node> kids = new ArrayList<>();
    }

    private static final int POS_START = 0;
    private static final int POS_AT = 1;
    private static final int POS_UNKNOWN = 2;
    private static final int PAR_NONE = 0;
    private static final int PAR_AT = 1;
    private static final int PAR_UNKNOWN = 2;

    private static final class Pcb {
        int db;
        int keylen;
        int sensegs;
        String procopt;
        Field mask;
        int pos = POS_START;
        Node at;
        int par = PAR_NONE;
        Node parentage;
        Node hold;
        List<Node> holdPath; // #5233: the segments a D-coded get-hold returned, in I/O area order (null: only the held one)
        boolean[] holdSkip; // #5233: command code N, per holdPath entry: left out of the REPL
        boolean prevknown;
        boolean load; // #5233: PROCOPT L / LS on a DB PCB (load mode): ISRT only, in hierarchic and key order
        Node loadLast; // the segment the last successful load ISRT inserted
        boolean gsam; // #5233: a GSAM PCB (load mode): db is -1, out collects the records ISRT appended
        int reclen;
        String dbname;
        final ByteArrayOutputStream out = new ByteArrayOutputStream();
    }

    private static final class Ssa {
        int seg;
        int fld = -1; // the first qualification statement's field (-1: unqualified)
        int op;
        byte[] value;
        boolean first; // #5233: command code F
        boolean last; // #5233: command code L
        boolean par; // #5233: command code P
        boolean path; // #5233: command code D
        boolean enq; // #5233: command code Q
        boolean up; // #5233: command code U
        boolean vee; // #5233: command code V
        boolean noRepl; // #5233: command code N
        Node anchor; // #5233: U / V, the node at this level on the current position (set per call by get)
        byte[] cat; // #5233: command code C, the concatenated key in the parentheses
        // #5233: the statements after the first, each joined to the one before by AND (or == false) or OR
        final List<Term> more = new ArrayList<>();
    }

    private static final class Term {
        boolean or;
        int fld;
        int op;
        byte[] value;
    }

    private static final List<Segm> SEGS = new ArrayList<>();
    private static final List<Fld> FLDS = new ArrayList<>();
    private static final List<String> DBS = new ArrayList<>();
    private static final List<Node> ROOTS = new ArrayList<>(); // per database, a virtual node over its roots
    private static final List<Pcb> PCBS = new ArrayList<>();

    private static UnsupportedOperationException refuse(String what) {
        return new UnsupportedOperationException("CBLTDLI: " + what + " is not modelled");
    }

    private static Path dir() {
        String d = System.getProperty("gitgalaxy.dli.dir");
        if (d == null) {
            throw refuse("a run with no database stated (gitgalaxy.dli.dir)");
        }
        return Path.of(d);
    }

    private static String name8(byte[] b, int at) {
        return new String(b, at, 8, StandardCharsets.ISO_8859_1).replaceAll(" +$", "");
    }

    private static int findSeg(int db, String name) {
        for (int i = 0; i < SEGS.size(); i++) {
            if (SEGS.get(i).db == db && SEGS.get(i).name.equals(name)) {
                return i;
            }
        }
        return -1;
    }

    private static int findFld(int seg, String name) {
        for (int i = 0; i < FLDS.size(); i++) {
            if (FLDS.get(i).seg == seg && FLDS.get(i).name.equals(name)) {
                return i;
            }
        }
        return -1;
    }

    private static int keyCmp(Node a, byte[] b, int at) {
        Fld k = FLDS.get(SEGS.get(a.seg).key);
        return Arrays.compareUnsigned(a.data, k.start - 1, k.start - 1 + k.bytes, b, at, at + k.bytes);
    }

    private static int keyAt(Node n) {
        return FLDS.get(SEGS.get(n.seg).key).start - 1;
    }

    /** A child in its place: after the twins of earlier segment types (DBD order), among its own in key order. */
    private static void linkChild(Node parent, Node n) {
        int i = 0;
        while (i < parent.kids.size()) {
            Node c = parent.kids.get(i);
            if (c.seg > n.seg || (c.seg == n.seg && keyCmp(c, n.data, keyAt(n)) >= 0)) {
                break;
            }
            i++;
        }
        parent.kids.add(i, n);
        n.parent = parent;
    }

    // [rule RT-DLI-STATE]
    private static void load() throws IOException {
        SEGS.clear();
        FLDS.clear();
        DBS.clear();
        ROOTS.clear();
        PCBS.clear();
        for (String line : Files.readAllLines(dir().resolve("dbd.cfg"), StandardCharsets.ISO_8859_1)) {
            String[] w = line.trim().split("\\s+");
            if (w[0].equals("DBD")) {
                DBS.add(w[1]);
                Node root = new Node();
                root.seg = -1;
                ROOTS.add(root);
            } else if (w[0].equals("SEGM")) {
                Segm s = new Segm();
                s.db = DBS.size() - 1;
                s.name = w[2];
                s.bytes = Integer.parseInt(w[4]);
                s.parent = w[3].equals("0") ? -1 : findSeg(s.db, w[3]);
                s.level = s.parent < 0 ? 1 : SEGS.get(s.parent).level + 1;
                SEGS.add(s);
            } else if (w[0].equals("FIELD")) {
                Fld f = new Fld();
                f.seg = findSeg(DBS.size() - 1, w[2]);
                f.name = w[3];
                f.start = Integer.parseInt(w[4]);
                f.bytes = Integer.parseInt(w[5]);
                f.type = w[6].charAt(0);
                if (w[7].equals("S")) {
                    SEGS.get(f.seg).key = FLDS.size();
                }
                FLDS.add(f);
            }
        }
        for (Segm s : SEGS) {
            if (s.key < 0) {
                throw refuse("a segment with no sequence field");
            }
        }
        for (int d = 0; d < DBS.size(); d++) {
            loadDb(d);
        }
    }

    private static void loadDb(int d) throws IOException {
        Path seed = dir().resolve("seed." + DBS.get(d));
        if (!Files.exists(seed)) {
            return; // no seed: an empty database
        }
        byte[] b = Files.readAllBytes(seed);
        Node[] last = new Node[SEGS.size()];
        int i = 0;
        while (i + 8 <= b.length) {
            int s = findSeg(d, name8(b, i));
            if (s < 0) {
                throw refuse("a seed segment the DBD does not define");
            }
            Segm sg = SEGS.get(s);
            if (i + 8 + sg.bytes > b.length) {
                throw refuse("a truncated seed");
            }
            Node n = new Node();
            n.seg = s;
            n.data = Arrays.copyOfRange(b, i + 8, i + 8 + sg.bytes);
            i += 8 + sg.bytes;
            Node parent = sg.parent < 0 ? ROOTS.get(d) : last[sg.parent];
            if (parent == null) {
                throw refuse("a seed segment before its parent");
            }
            if (!parent.kids.isEmpty()) {
                Node prev = parent.kids.get(parent.kids.size() - 1);
                if (prev.seg > s || (prev.seg == s && keyCmp(prev, n.data, keyAt(n)) >= 0)) {
                    throw refuse("a seed not in hierarchic sequence (twins in byte order of their keys)");
                }
            }
            n.parent = parent;
            parent.kids.add(n);
            last[s] = n;
            for (int c = 0; c < SEGS.size(); c++) {
                if (SEGS.get(c).db == d && SEGS.get(c).level > sg.level) {
                    last[c] = null;
                }
            }
        }
    }

    private static void fullword(Field mask, int at, int v) {
        byte[] b = mask.storage().bytes;
        int o = mask.offset() + at;
        b[o] = (byte) (v >> 24);
        b[o + 1] = (byte) (v >> 16);
        b[o + 2] = (byte) (v >> 8);
        b[o + 3] = (byte) v;
    }

    private static void text(Field mask, int at, int len, String s) {
        byte[] b = mask.storage().bytes;
        int o = mask.offset() + at;
        Arrays.fill(b, o, o + len, (byte) ' ');
        byte[] t = s.getBytes(StandardCharsets.ISO_8859_1);
        System.arraycopy(t, 0, b, o, Math.min(t.length, len));
    }

    /** The PSB's DB PCBs, in order, each at its start (no position, status blank), from psb.cfg. */
    private static void buildPcbs() throws IOException {
        PCBS.clear();
        for (String line : Files.readAllLines(dir().resolve("psb.cfg"), StandardCharsets.ISO_8859_1)) {
            String[] w = line.trim().split("\\s+");
            boolean gsam = w[0].equals("GSAM");
            if (!gsam && !w[0].equals("PCB")) {
                continue;
            }
            Pcb p = new Pcb();
            p.procopt = w[2].length() > 4 ? w[2].substring(0, 4) : w[2];
            if (gsam) { // GSAM <dbd> <procopt> <record length> (tests/tools/equivalence_ims.py)
                for (Pcb o : PCBS) {
                    if (o.gsam && o.dbname.equals(w[1])) {
                        throw refuse("two GSAM PCBs on one database");
                    }
                }
                p.gsam = true;
                p.db = -1;
                p.dbname = w[1];
                p.reclen = Integer.parseInt(w[3]);
                PCBS.add(p);
                continue;
            }
            p.db = DBS.indexOf(w[1]);
            p.load = p.procopt.equals("L") || p.procopt.equals("LS");
            p.keylen = Integer.parseInt(w[3]);
            for (Segm s : SEGS) {
                if (s.db == p.db) {
                    p.sensegs++;
                }
            }
            PCBS.add(p);
        }
    }

    // ---- #5857: DL/I status faults ----------------------------------------------------------------------------
    private static final List<String[]> FAULTS = new ArrayList<>();
    private static final java.util.Map<String, Integer> CALLS = new java.util.HashMap<>();
    private static boolean faultsLoaded; // this task's plan is read and its counts started (reset() clears it)

    /**
     * The run's DL/I fault plan: the lines `# DLI FUNCTION NTH|* STATUS` of the file the property
     * gitgalaxy.faults.plan names (the file-fault plan the COBOL file layer also reads, which ignores them), counted
     * afresh for each run. The twin of ggdli.c's GGDLI_FAULTS.
     */
    // [rule RT-DLI-FAULT-INJECTION]
    private static void loadFaults() {
        faultsLoaded = true;
        FAULTS.clear();
        CALLS.clear();
        String plan = System.getProperty("gitgalaxy.faults.plan", "");
        if (plan.isEmpty()) {
            return;
        }
        try {
            for (String line : Files.readAllLines(Path.of(plan), StandardCharsets.US_ASCII)) {
                String[] w = line.trim().split("\\s+");
                if (w.length == 5 && w[0].equals("#") && w[1].equals("DLI")) {
                    FAULTS.add(w);
                }
            }
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    /**
     * The planned status of this call of `fn` (GU GN GNP ISRT REPL DLET CHKP SCHD; a get-hold counts as its get), or null.
     * Every call counts, whether or not it faults; a fault that fires is appended to gitgalaxy.faults.log. The call is
     * not performed: the PCB answers the status, as it answers any status it cannot do better than name.
     */
    private static String planned(String fn) {
        if (FAULTS.isEmpty()) {
            return null;
        }
        String key = fn.trim();
        if (key.startsWith("GH")) {
            key = "G" + key.substring(2);
        }
        int n = CALLS.merge(key, 1, Integer::sum);
        for (String[] f : FAULTS) {
            if (f[2].equals(key) && (f[3].equals("*") || Integer.parseInt(f[3]) == n)) {
                String log = System.getProperty("gitgalaxy.faults.log", "");
                if (!log.isEmpty()) {
                    try {
                        Files.writeString(Path.of(log), "DLI " + key + " " + n + " " + f[4] + System.lineSeparator(),
                            StandardCharsets.US_ASCII, java.nio.file.StandardOpenOption.CREATE,
                            java.nio.file.StandardOpenOption.APPEND);
                    } catch (IOException e) {
                        throw new UncheckedIOException(e);
                    }
                }
                return f[4];
            }
        }
        return null;
    }

    private static boolean loaded;
    private static boolean scheduled;
    private static int ioPcbs; // 1 in a BMP entered by USING its I/O PCB first (enterBmp): PCB(n) counts it

    /**
     * EXEC DLI SCHD PSB(name) under CICS (register I5): the stated databases are loaded at the first SCHD (they outlive
     * a TERM), the PSB's PCBs start with no position, and DIBSTAT is blank. A PSB already scheduled in the task is
     * DIBSTAT TC (IBM, IMS Application Programming, EXEC DLI SCHD) -- with NODHABEND, else the task would abend, which
     * is not modelled. The PSB is the one stated (psb.cfg), whatever name the program gives.
     */
    // [rule RT-DLI-SCHD]
    public static String schedule(String psb, boolean nodhabend) {
        if (!faultsLoaded) {
            loadFaults();
        }
        String fault = planned("SCHD"); // #5233: not performed, DIBSTAT answers the status (the twin of GGDLISCHD)
        if (fault != null && !(fault.equals("TC") && !scheduled)) {
            return fault;
        }
        // A planned TC says the task already holds the PSB: it is scheduled (so a TERM after it is valid), DIBSTAT TC.
        if (scheduled) {
            if (!nodhabend) {
                throw refuse("a SCHD of a PSB already scheduled, without NODHABEND (the task would abend)");
            }
            return "TC";
        }
        try {
            if (!loaded) {
                load();
                loaded = true;
            }
            buildPcbs();
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        for (Pcb p : PCBS) { // a CICS program names its PCB by number (PCB(n)): the mask is the runtime's own
            p.mask = Field.group(new Storage(36 + p.keylen), 0, 36 + p.keylen);
            initMask(p);
        }
        scheduled = true;
        return fault != null ? fault : "  ";
    }

    /** SCHD PSB((area)): the PSB name is the area's bytes (the name the program built there). */
    public static String schedule(Field psb, boolean nodhabend) {
        return schedule(new String(psb.storage().bytes, psb.offset(), psb.length(), StandardCharsets.ISO_8859_1).trim(),
            nodhabend);
    }

    /** A new task in one JVM (the equivalence harness runs scenarios in turn): no PSB scheduled, the databases to be read afresh. */
    public static void reset() {
        loaded = false;
        scheduled = false;
        faultsLoaded = false;
        ioPcbs = 0;
        SEGS.clear();
        FLDS.clear();
        DBS.clear();
        ROOTS.clear();
        PCBS.clear();
    }

    /** EXEC DLI TERM: the PSB is released (the databases keep what was written); DIBSTAT blank. */
    // [rule RT-DLI-TERM]
    public static String terminate() {
        if (!scheduled) {
            throw refuse("a TERM with no PSB scheduled");
        }
        scheduled = false;
        PCBS.clear();
        return "  ";
    }

    /**
     * The batch entry (ENTRY 'DLITCBL' USING pcb ...): the stated databases loaded, each DB PCB of the PSB (in order)
     * bound to the area passed, its mask filled -- DBD name, level '00', status blank, PROCOPT, the number of
     * sensitive segments, key feedback length 0 (register I4).
     */
    // [rule RT-DLI-ENTRY]
    public static void enter(Field... areas) {
        bind(false, areas);
    }

    private static void bind(boolean bmp, Field... areas) {
        loadFaults();
        try {
            load();
            loaded = true;
            scheduled = false;
            buildPcbs();
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        if (areas.length != PCBS.size()) {
            throw refuse("an entry whose USING does not list one area per PCB of the PSB");
        }
        for (int i = 0; i < areas.length; i++) {
            Pcb p = PCBS.get(i);
            p.mask = areas[i];
            if (p.mask.length() < 36 + p.keylen) {
                if (!bmp) {
                    throw refuse("a PCB mask shorter than the PCB (36 bytes and the KEYLEN)");
                }
                // a BMP's EXEC DLI names PCB(n), never the mask (CBPAUP0C declares it PIC X): the runtime's own mask
                p.mask = Field.group(new Storage(36 + p.keylen), 0, 36 + p.keylen);
            }
            initMask(p);
        }
    }

    /**
     * The entry of a BMP that issues EXEC DLI (register I5, #5857): PROCEDURE DIVISION USING io-pcb db-pcb ... (the PSB is
     * CMPAT=YES: IMS passes the I/O PCB first), so PCB(n) counts the I/O PCB and the PSB is scheduled from the start.
     * The DB PCBs are bound as {@link #enter} does (a mask shorter than the PCB, a PIC X the program never names, is replaced by the runtime's own); the I/O PCB's mask is not read or written, and a DB command on
     * PCB(1) stops the run by name.
     */
    public static void enterBmp(Field io, Field... areas) {
        bind(true, areas);
        scheduled = true;
        ioPcbs = 1;
    }

    /**
     * EXEC DLI CHKP ID(area) in a BMP (register I5): the basic checkpoint. DIBSTAT is blank, and IMS releases every
     * database position (the next GN starts at the beginning of the database). The ID is 8 bytes; a CHKP outside a BMP,
     * or an ID of another length, stops the run by name. The log record itself is not modelled.
     */
    public static String checkpoint(Field id) {
        if (ioPcbs == 0) {
            throw refuse("an EXEC DLI CHKP outside a BMP entered by USING its I/O PCB");
        }
        if (id.length() != 8) {
            throw refuse("a CHKP ID that is not 8 bytes");
        }
        String fault = planned("CHKP");
        if (fault != null) {
            return fault;
        }
        for (Pcb p : PCBS) {
            p.pos = POS_START;
            p.at = null;
            p.par = PAR_NONE;
            p.parentage = null;
            p.hold = null;
            p.prevknown = false;
        }
        return "  ";
    }

    /** A PCB mask at its start: DBD name, level '00', status blank, PROCOPT, sensitive segments, key feedback zero. */
    private static void initMask(Pcb p) {
        byte[] b = p.mask.storage().bytes;
        int o = p.mask.offset();
        Arrays.fill(b, o, o + 36, (byte) ' ');
        text(p.mask, 0, 8, p.gsam ? p.dbname : DBS.get(p.db));
        if (!p.gsam) { // a GSAM PCB has no segment level: blank (ASSUMED, register I5)
            text(p.mask, 8, 2, "00");
        }
        text(p.mask, 12, 4, p.procopt);
        fullword(p.mask, 16, 0);
        fullword(p.mask, 28, 0);
        fullword(p.mask, 32, p.sensegs);
        // the key feedback area, and the bytes past it the program's mask may name: X'00' (register I4)
        Arrays.fill(b, o + 36, o + p.mask.length(), (byte) 0);
    }

    private static Field area(byte[] b) {
        Storage st = new Storage(0);
        st.bytes = b;
        return Field.group(st, 0, b.length);
    }

    /** An SSA for EXEC DLI SEGMENT(seg): unqualified. */
    public static Field ssa(String seg) {
        byte[] b = new byte[9];
        Arrays.fill(b, (byte) ' ');
        System.arraycopy(seg.getBytes(StandardCharsets.ISO_8859_1), 0, b, 0, Math.min(8, seg.length()));
        return area(b);
    }

    /** An SSA for SEGMENT(seg) WHERE(fld op value): qualified (op: EQ GT LT GE LE NE), the value's bytes as they are. */
    public static Field ssa(String seg, String fld, String op, Field value) {
        int k = -1;
        for (int i = 0; i < OPS.length; i++) {
            if (OPS[i][0].equals(op)) {
                k = i;
            }
        }
        if (k < 0) {
            throw refuse("a WHERE operator other than EQ GT LT GE LE NE");
        }
        byte[] v = Arrays.copyOfRange(value.storage().bytes, value.offset(), value.offset() + value.length());
        byte[] b = new byte[19 + v.length + 1];
        Arrays.fill(b, (byte) ' ');
        System.arraycopy(seg.getBytes(StandardCharsets.ISO_8859_1), 0, b, 0, Math.min(8, seg.length()));
        b[8] = '(';
        System.arraycopy(fld.getBytes(StandardCharsets.ISO_8859_1), 0, b, 9, Math.min(8, fld.length()));
        System.arraycopy(OPS[k][1].getBytes(StandardCharsets.ISO_8859_1), 0, b, 17, 2);
        System.arraycopy(v, 0, b, 19, v.length);
        b[19 + v.length] = ')';
        return area(b);
    }

    /**
     * EXEC DLI GU / GN / GNP USING PCB(n) [SEGMENT(s) [WHERE(f op v)] ...] INTO(area) under CICS (register I5): the
     * CBLTDLI get of the same SSAs against PCB n of the scheduled PSB, DIBSTAT the PCB's status. A get is a get-hold
     * where the PCB's PROCOPT allows an update (A, R or D) -- ASSUMED, the command has no HOLD option (register I5).
     */
    // [rule RT-DLI-EXEC-GET]
    public static String get(String verb, int pcbNum, Field into, Field... ssas) {
        Pcb p = execPcb(pcbNum);
        boolean upd = p.procopt.indexOf('A') >= 0 || p.procopt.indexOf('R') >= 0 || p.procopt.indexOf('D') >= 0;
        String fn = switch (verb) {
            case "GU" -> upd ? "GHU " : "GU  ";
            case "GN" -> upd ? "GHN " : "GN  ";
            case "GNP" -> upd ? "GHNP" : "GNP ";
            default -> throw refuse("EXEC DLI " + verb);
        };
        Storage f = new Storage(4);
        f.bytes = fn.getBytes(StandardCharsets.ISO_8859_1);
        call(Field.group(f, 0, 4), p.mask, into, ssas);
        return new String(p.mask.storage().bytes, p.mask.offset() + 10, 2, StandardCharsets.ISO_8859_1);
    }

    private static Pcb execPcb(int pcbNum) {
        if (!scheduled) {
            throw refuse("an EXEC DLI command with no PSB scheduled");
        }
        if (ioPcbs > 0 && pcbNum == 1) {
            throw refuse("an EXEC DLI database command on PCB(1), the I/O PCB");
        }
        if (pcbNum - ioPcbs < 1 || pcbNum - ioPcbs > PCBS.size()) {
            throw refuse("a PCB number the scheduled PSB does not have");
        }
        return PCBS.get(pcbNum - ioPcbs - 1);
    }

    private static String execCall(String fn, Pcb p, Field io, Field... ssas) {
        Storage f = new Storage(4);
        f.bytes = fn.getBytes(StandardCharsets.ISO_8859_1);
        call(Field.group(f, 0, 4), p.mask, io, ssas);
        return new String(p.mask.storage().bytes, p.mask.offset() + 10, 2, StandardCharsets.ISO_8859_1);
    }

    /**
     * EXEC DLI ISRT USING PCB(n) SEGMENT(s) [WHERE(..)] ... SEGMENT(t) FROM(area) [SEGLENGTH(n)] under CICS (register
     * I5): the CBLTDLI ISRT of the same SSAs, the last one unqualified. Segments are fixed length (the DBD's): a
     * SEGLENGTH (seglen, -1 where absent) that differs from it stops the run by name.
     */
    // [rule RT-DLI-EXEC-ISRT]
    public static String execIsrt(int pcbNum, Field from, int seglen, Field... ssas) {
        Pcb p = execPcb(pcbNum);
        if (seglen >= 0 && ssas.length > 0) {
            String[] st = new String[1];
            Ssa[] s = parseSsas(p.db, ssas, st);
            if (st[0] == null && SEGS.get(s[s.length - 1].seg).bytes != seglen) {
                throw refuse("an ISRT whose SEGLENGTH is not the segment's fixed length");
            }
        }
        return execCall("ISRT", p, from, ssas);
    }

    /**
     * EXEC DLI REPL / DLET USING PCB(n) SEGMENT(s) FROM(area) under CICS (register I5): the CBLTDLI REPL / DLET of the
     * segment the previous command on this PCB held (a get is a get-hold where the PCB's PROCOPT allows an update, see
     * {@link #get}); SEGMENT must name that segment's type -- ASSUMED, the command form has no SSA.
     */
    // [rule RT-DLI-EXEC-CHANGE]
    public static String execChange(String verb, int pcbNum, Field from, String segment) {
        Pcb p = execPcb(pcbNum);
        if (p.hold != null && !SEGS.get(p.hold.seg).name.equals(segment)) {
            throw refuse("an EXEC DLI " + verb + " whose SEGMENT is not the held segment's type");
        }
        return execCall(verb.equals("DLET") ? "DLET" : "REPL", p, from);
    }

    /** The step ended: each database, in hierarchic sequence (8-byte segment name, then its data), to gitgalaxy.dli.out. */
    public static void leave() {
        String out = System.getProperty("gitgalaxy.dli.out");
        if (out == null) {
            return;
        }
        try {
            for (int d = 0; d < DBS.size(); d++) {
                ByteArrayOutputStream o = new ByteArrayOutputStream();
                dump(o, ROOTS.get(d));
                Files.write(Path.of(out).resolve(DBS.get(d) + ".out"), o.toByteArray());
            }
            for (Pcb p : PCBS) { // #5233: each GSAM database, the records its PCB took
                if (p.gsam) {
                    Files.write(Path.of(out).resolve(p.dbname + ".out"), p.out.toByteArray());
                }
            }
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    private static void dump(ByteArrayOutputStream o, Node n) {
        for (Node c : n.kids) {
            byte[] nm = new byte[8];
            Arrays.fill(nm, (byte) ' ');
            byte[] t = SEGS.get(c.seg).name.getBytes(StandardCharsets.ISO_8859_1);
            System.arraycopy(t, 0, nm, 0, t.length);
            o.writeBytes(nm);
            o.writeBytes(c.data);
            dump(o, c);
        }
    }

    // ---- the hierarchic sequence --------------------------------------------------------------------------------
    private static Node nextInSeq(Node n) {
        if (!n.kids.isEmpty()) {
            return n.kids.get(0);
        }
        while (n.parent != null) {
            List<Node> sib = n.parent.kids;
            int i = sib.indexOf(n);
            if (i + 1 < sib.size()) {
                return sib.get(i + 1);
            }
            n = n.parent;
        }
        return null;
    }

    private static Node dbFirst(int d) {
        List<Node> k = ROOTS.get(d).kids;
        return k.isEmpty() ? null : k.get(0);
    }

    private static boolean descends(Node n, Node anc) {
        for (Node p = n.parent; p != null; p = p.parent) {
            if (p == anc) {
                return true;
            }
        }
        return false;
    }

    private static boolean descendsType(int t, int anc) {
        for (; t >= 0; t = SEGS.get(t).parent) {
            if (t == anc) {
                return true;
            }
        }
        return false;
    }

    private static Node lastInSubtree(Node n) {
        while (!n.kids.isEmpty()) {
            n = n.kids.get(n.kids.size() - 1);
        }
        return n;
    }

    private static Node ancestorOfType(Node n, int seg) {
        for (; n != null && n.parent != null; n = n.parent) {
            if (n.seg == seg) {
                return n;
            }
        }
        return null;
    }

    // ---- SSAs ---------------------------------------------------------------------------------------------------
    private static final String[][] OPS = {{"EQ", " =", "= "}, {"GT", " >", "> "}, {"LT", " <", "< "},
        {"GE", ">=", "=>"}, {"LE", "<=", "=<"}, {"NE", "¬=", "=¬"}};

    /** The SSAs of a call; a status code that rejects them is returned in st[0]. */
    // [rule RT-DLI-SSA]
    private static Ssa[] parseSsas(int db, Field[] raw, String[] st) {
        Ssa[] out = new Ssa[raw.length];
        for (int i = 0; i < raw.length; i++) {
            byte[] b = raw[i].storage().bytes;
            int o = raw[i].offset();
            Ssa s = new Ssa();
            out[i] = s;
            s.seg = findSeg(db, name8(b, o));
            if (s.seg < 0) {
                st[0] = "AC";
                return out;
            }
            int q = b[o + 8] & 0xFF;
            if (q == ' ') {
                continue;
            }
            int at = o + 9;
            if (q == '*') {
                // #5233: command codes, each one of A-Z 0-9 or '-', then '(' or a blank; F, L, P, C, D, N, Q, U, V and - are modelled
                while (at < b.length && isCode(b[at] & 0xFF)) {
                    char c = (char) (b[at] & 0xFF);
                    if (c == 'F') {
                        s.first = true;
                    } else if (c == 'L') {
                        s.last = true;
                    } else if (c == 'P') {
                        s.par = true;
                    } else if (c == 'D') {
                        s.path = true;
                    } else if (c == 'Q') {
                        s.enq = true;
                    } else if (c == 'U') {
                        s.up = true;
                    } else if (c == 'V') {
                        s.vee = true;
                    } else if (c == 'N') {
                        s.noRepl = true;
                    } else if (c == 'C') {
                        s.cat = new byte[0];
                    } else if (c != '-') {
                        throw refuse("the command code " + c);
                    }
                    at++;
                }
                if (at >= b.length || (b[at] != ' ' && b[at] != '(')) {
                    st[0] = "AJ";
                    return out;
                }
                if (b[at] == ' ') {
                    if (s.cat != null) {
                        st[0] = "AJ";
                        return out;
                    }
                    continue;
                }
                at++;
                if (s.cat != null) {
                    // #5233: command code C, SEG*C(concatenated key): the keys from the root down to this segment
                    int len = catLength(s.seg);
                    if (at + len >= b.length || b[at + len] != ')') {
                        st[0] = "AJ";
                        return out;
                    }
                    s.cat = Arrays.copyOfRange(b, at, at + len);
                    continue;
                }
            } else if (q != '(') {
                st[0] = "AJ";
                return out;
            }
            for (int k = 0; ; k++) {
                int fld = findFld(s.seg, name8(b, at));
                if (fld < 0) {
                    st[0] = "AK";
                    return out;
                }
                String op = new String(b, at + 8, 2, StandardCharsets.ISO_8859_1);
                int opn = -1;
                for (int j = 0; j < OPS.length; j++) {
                    for (String v : OPS[j]) {
                        if (v.equals(op)) {
                            opn = j;
                        }
                    }
                }
                if (opn < 0) {
                    st[0] = "AJ";
                    return out;
                }
                Fld f = FLDS.get(fld);
                byte[] value = Arrays.copyOfRange(b, at + 10, at + 10 + f.bytes);
                if (k == 0) {
                    s.fld = fld;
                    s.op = opn;
                    s.value = value;
                } else {
                    Term m = s.more.get(k - 1);
                    m.fld = fld;
                    m.op = opn;
                    m.value = value;
                }
                int end = b[at + 10 + f.bytes] & 0xFF;
                if (f.type != 'C' && f.type != 'X' && f.type != 'P' && (end == ')' || isBool(end))) {
                    throw refuse("a qualification on a field of a type other than C, X or P");
                }
                if (end == ')') {
                    break;
                }
                if (end == '#') {
                    throw refuse("a boolean SSA with the independent AND operator (#)");
                }
                if (!isBool(end)) {
                    st[0] = "AJ";
                    return out;
                }
                if (k == MAX_TERMS - 1) {
                    throw refuse("a boolean SSA of more than " + MAX_TERMS + " qualification statements");
                }
                Term m = new Term();
                m.or = end == '+' || end == '|';
                s.more.add(m);
                at += 11 + f.bytes;
            }
        }
        return out;
    }

    private static final int MAX_TERMS = 16;

    /** The bytes of a concatenated key down to a segment type (#5233, command code C). */
    private static int catLength(int seg) {
        int len = 0;
        for (int t = seg; t >= 0; t = SEGS.get(t).parent) {
            if (SEGS.get(t).key < 0) {
                throw refuse("the command code C on a segment with no sequence field");
            }
            len += FLDS.get(SEGS.get(t).key).bytes;
        }
        return len;
    }

    /** Command code C (#5233): the concatenated key becomes one SSA per level, qualified EQ on that level's key. */
    private static Ssa[] expandCat(Ssa[] s) {
        if (s.length != 1 || s[0].cat == null) {
            return s;
        }
        List<Integer> path = new ArrayList<>();
        for (int t = s[0].seg; t >= 0; t = SEGS.get(t).parent) {
            path.add(0, t);
        }
        Ssa[] out = new Ssa[path.size()];
        int at = 0;
        for (int i = 0; i < out.length; i++) {
            Ssa x = new Ssa();
            x.seg = path.get(i);
            x.fld = SEGS.get(x.seg).key;
            x.op = 0;
            int n = FLDS.get(x.fld).bytes;
            x.value = Arrays.copyOfRange(s[0].cat, at, at + n);
            at += n;
            out[i] = x;
        }
        out[out.length - 1].par = s[0].par;
        out[out.length - 1].first = s[0].first;
        return out;
    }

    /** A character a command-code list may hold. */
    private static boolean isCode(int c) {
        return (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-';
    }

    /** Command codes (#5233): Q on a get (no effect: one program, so no other program to wait for); F and L on a GU / GHU or an ISRT, P on a GU / GHU (a unique sequence field: no effect on ISRT, and F none on
     *  GU, which starts from the first twin); L on a GU only as the last, unqualified SSA. Anything else is refused. */
    private static void checkCodes(String fn, Ssa[] s) {
        boolean gu = fn.startsWith("GU") || fn.startsWith("GHU");
        boolean isrt = fn.equals("ISRT");
        int ps = 0;
        for (int i = 0; i < s.length; i++) {
            if (s[i].cat != null && (!gu || s.length != 1 || s[i].last)) {
                throw refuse("the command code C other than alone on a GU, without L");
            }
            if (s[i].path && fn.charAt(0) != 'G' && !isrt) { // #5233: D on an ISRT is the path insert
                throw refuse("the command code D on a " + fn.trim());
            }
            if (s[i].path && s[i].cat != null) {
                throw refuse("the command code D beside C");
            }
            if (s[i].noRepl && (fn.charAt(0) != 'G' || fn.charAt(1) != 'H' || !s[i].path)) {
                throw refuse("the command code N other than with D on a get-hold call (" + fn.trim() + ")");
            }
            if (s[i].enq && fn.charAt(0) != 'G') {
                throw refuse("the command code Q on a " + fn.trim()); // #5233: Q (enqueue) is modelled on the gets, where it changes nothing
            }
            if ((s[i].up || s[i].vee) && (fn.charAt(0) != 'G' || s[i].cat != null)) {
                throw refuse("the command code " + (s[i].up ? "U" : "V") + (s[i].cat != null ? " beside C" : " on a " + fn.trim()));
            }
            if (s[i].par && (!gu || ++ps > 1)) {
                throw refuse(gu ? "the command code P on more than one SSA" : "the command code P on a " + fn.trim());
            }
            if (s[i].first && !gu && !isrt) {
                throw refuse("the command code F on a " + fn.trim());
            }
            if (s[i].last && (!(gu || isrt) || i != s.length - 1 || s[i].fld >= 0)) {
                throw refuse("the command code L other than on the last, unqualified SSA of a GU or ISRT");
            }
        }
    }

    /** A boolean operator that joins two qualification statements: AND is * or &, OR is + or | (# is refused apart). */
    private static boolean isBool(int c) {
        return c == '&' || c == '*' || c == '+' || c == '|';
    }

    private static int packedSign(byte[] p, int at, int n) {
        for (int i = 0; i < n; i++) {
            int v = p[at + i] & 0xFF;
            if ((v >> 4) > 9 || (i < n - 1 && (v & 15) > 9)) {
                return -1;
            }
        }
        return p[at + n - 1] & 15;
    }

    // [rule RT-DLI-QUALIFY]
    private static boolean qualifies(Node n, Ssa s) {
        if (s.fld < 0) {
            return true;
        }
        // IBM: statements joined by AND form a set, and the SSA holds when any set does. Every statement is evaluated
        // (no short circuit) so a refusal does not depend on the data.
        boolean any = false;
        boolean set = term(n, s.fld, s.op, s.value);
        for (Term m : s.more) {
            if (m.or) {
                any |= set;
                set = true;
            }
            set &= term(n, m.fld, m.op, m.value);
        }
        return any | set;
    }

    private static boolean term(Node n, int fld, int op, byte[] value) {
        Fld f = FLDS.get(fld);
        if (f.type == 'P') {
            int sa = packedSign(n.data, f.start - 1, f.bytes);
            int sb = packedSign(value, 0, f.bytes);
            if (sa < 0 || sb < 0 || sa != sb || (sa != 0xC && sa != 0xF)) {
                throw refuse("a P-field qualification on operands that are not both valid with one positive sign");
            }
        }
        int c = Arrays.compareUnsigned(n.data, f.start - 1, f.start - 1 + f.bytes, value, 0, f.bytes);
        switch (op) {
            case 0: return c == 0;
            case 1: return c > 0;
            case 2: return c < 0;
            case 3: return c >= 0;
            case 4: return c <= 0;
            default: return c != 0;
        }
    }

    private static boolean satisfies(Node n, Ssa[] s, int k) {
        if (k == 0) {
            return true;
        }
        if (n.seg != s[k - 1].seg) {
            return false;
        }
        for (int i = 0; i < k; i++) {
            Node a = ancestorOfType(n, s[i].seg);
            if (a == null || !qualifies(a, s[i])) {
                return false;
            }
            if (s[i].anchor != null && a != s[i].anchor) {
                return false; // #5233: U / V, the SSA's level must be the one the current position is on
            }
        }
        return true;
    }

    /** SSAs in hierarchic order, each the child of the one before: null, "AC", or a refusal. */
    private static String chain(Ssa[] s, int k) {
        for (int i = 1; i < k; i++) {
            int p = SEGS.get(s[i].seg).parent;
            if (p == s[i - 1].seg) {
                continue;
            }
            while (p >= 0 && p != s[i - 1].seg) {
                p = SEGS.get(p).parent;
            }
            if (p < 0) {
                return "AC";
            }
            throw refuse("SSAs that leave out an intermediate level");
        }
        return null;
    }

    // ---- the PCB mask -------------------------------------------------------------------------------------------
    private static void status(Pcb p, String st) {
        text(p.mask, 10, 2, st);
    }

    // [rule RT-DLI-FEEDBACK]
    private static void feedback(Pcb p, Node n) {
        if (n == null || n.parent == null) {
            text(p.mask, 8, 2, "00");
            text(p.mask, 20, 8, "");
            fullword(p.mask, 28, 0);
            return;
        }
        Segm sg = SEGS.get(n.seg);
        text(p.mask, 8, 2, String.format(java.util.Locale.ROOT, "%02d", sg.level));
        text(p.mask, 20, 8, sg.name);
        List<Node> path = new ArrayList<>();
        for (Node a = n; a != null && a.parent != null; a = a.parent) {
            path.add(0, a);
        }
        byte[] b = p.mask.storage().bytes;
        int len = 0;
        for (Node a : path) {
            Fld k = FLDS.get(SEGS.get(a.seg).key);
            if (len + k.bytes > p.keylen) {
                throw refuse("a concatenated key longer than the PCB's KEYLEN");
            }
            System.arraycopy(a.data, k.start - 1, b, p.mask.offset() + 36 + len, k.bytes);
            len += k.bytes;
        }
        fullword(p.mask, 28, len);
    }

    private static boolean allows(Pcb p, char what) {
        return p.procopt.indexOf('A') >= 0 || p.procopt.indexOf(what) >= 0;
    }

    private static Pcb findPcb(Field mask) {
        for (Pcb p : PCBS) {
            if (p.mask.storage() == mask.storage() && p.mask.offset() == mask.offset()) {
                return p;
            }
        }
        throw refuse("a PCB the program was not passed");
    }

    private static Node firstSatisfying(Node from, Node bound, Ssa[] s, int k) {
        for (Node c = from; c != null; c = nextInSeq(c)) {
            if (bound != null && !descends(c, bound)) {
                return null;
            }
            if (satisfies(c, s, k)) {
                return c;
            }
        }
        return null;
    }

    /** The deepest segment along the SSAs' path that IMS could satisfy (the feedback of an unsuccessful call). */
    private static Node deepest(int db, Ssa[] s, int upto) {
        for (int j = upto; j >= 1; j--) {
            Node c = firstSatisfying(dbFirst(db), null, s, j);
            if (c != null) {
                return c;
            }
        }
        return null;
    }

    /** GU / GN / GNP and their holds. */
    // [rule RT-DLI-GET]
    private static void get(Pcb p, String fn, Field io, Ssa[] s, boolean hold) {
        int k = s.length;
        if (!allows(p, 'G')) {
            status(p, "AM");
            return;
        }
        if (hold && p.procopt.indexOf('O') >= 0) {
            throw refuse("a get-hold call under PROCOPT O");
        }
        String bad = chain(s, k);
        if (bad != null) {
            status(p, bad);
            return;
        }
        // #5233: command codes U and V take the current position as qualification: U at its own level, V at its level and
        // every level above; the node there is the position's ancestor-or-self of that type
        int vee = -1;
        for (int i = 0; i < k; i++) {
            if (s[i].vee) {
                vee = i;
            }
        }
        for (int i = 0; i < k; i++) {
            s[i].anchor = null;
            if (s[i].up || i <= vee) {
                if (p.pos != POS_AT) {
                    throw refuse("the command code " + (i <= vee ? "V" : "U") + " with no established position");
                }
                s[i].anchor = ancestorOfType(p.at, s[i].seg);
                if (s[i].anchor == null) {
                    throw refuse("the command code " + (i <= vee ? "V" : "U") + " at a level the current position is not on");
                }
            }
        }
        boolean gu = fn.charAt(1) == 'U' || fn.charAt(2) == 'U';
        boolean gnp = !gu && fn.contains("NP");
        Node from;
        Node bound = null;
        if (gu) {
            if (k > 0 && SEGS.get(s[0].seg).parent >= 0) {
                throw refuse("a GU whose SSAs leave out the root level");
            }
            from = dbFirst(p.db);
        } else {
            if (gnp) {
                if (p.par == PAR_NONE) {
                    status(p, "GP");
                    return;
                }
                if (p.par == PAR_UNKNOWN) {
                    throw refuse("a GNP after a call that leaves parentage open");
                }
                bound = p.parentage;
                if (k > 0 && !descendsType(SEGS.get(s[0].seg).parent, bound.seg)) {
                    throw refuse("a GNP whose SSAs name a segment outside its parent");
                }
            }
            if (p.pos == POS_UNKNOWN) {
                throw refuse("a GN / GNP after a call that leaves position open");
            }
            if (bound != null && (p.pos != POS_AT || (p.at != bound && !descends(p.at, bound)))) {
                throw refuse("a GNP whose position is outside its parent");
            }
            from = p.pos == POS_START ? dbFirst(p.db) : nextInSeq(p.at);
        }
        Node n = firstSatisfying(from, bound, s, k);
        if (n != null && gu && k > 0 && s[k - 1].last) {
            // #5233: the last twin of the type under the parent the path found
            for (Node c : n.parent.kids) {
                if (c.seg == n.seg) {
                    n = c;
                }
            }
        }
        if (n == null) {
            boolean qualified = false;
            for (Ssa x : s) {
                qualified |= x.fld >= 0;
            }
            if (gu) {
                status(p, "GE");
                feedback(p, deepest(p.db, s, k - 1));
                p.pos = POS_UNKNOWN;
                p.par = PAR_UNKNOWN;
            } else if (gnp) {
                if (qualified) {
                    // #5233 (register I5): GE, the parent's feedback, parentage as it was; where IMS leaves position is
                    // not stated, so it is unknown and the next GN / GNP stops by name (the twin of ggdli.c)
                    status(p, "GE");
                    feedback(p, bound);
                    p.pos = POS_UNKNOWN;
                    return;
                }
                status(p, "GE");
                feedback(p, bound);
                p.pos = POS_AT;
                p.at = lastInSubtree(bound);
                p.prevknown = false;
            } else {
                if (qualified) {
                    throw refuse("a qualified GN that finds nothing (GE or GB: IMS's sequence-field search)");
                }
                status(p, "GB");
                p.pos = POS_START;
                p.prevknown = false;
            }
            return;
        }
        String st = "  ";
        if (!gu && k == 0 && p.prevknown && p.pos == POS_AT) {
            int was = SEGS.get(p.at.seg).level;
            int now = SEGS.get(n.seg).level;
            if (now < was) {
                st = "GA";
            } else if (now == was && n.seg != p.at.seg) {
                st = "GK";
            }
        }
        // #5233: command code D, a path call: each D-coded SSA's segment (the found one's ancestor of that type), in
        // hierarchic order, then the found segment itself; D on the last SSA adds nothing
        List<Node> out = new ArrayList<>();
        for (int i = 0; i < k - 1; i++) {
            if (s[i].path) {
                out.add(ancestorOfType(n, s[i].seg));
            }
        }
        out.add(n);
        int total = 0;
        for (Node o : out) {
            total += o.data.length;
        }
        if (io.storage().bytes.length - io.offset() < total) {
            throw refuse("an I/O area shorter than the segment");
        }
        int off = io.offset();
        for (Node o : out) {
            System.arraycopy(o.data, 0, io.storage().bytes, off, o.data.length);
            off += o.data.length;
        }
        status(p, st);
        feedback(p, n);
        p.pos = POS_AT;
        p.at = n;
        p.prevknown = true;
        if (!gnp) {
            p.par = PAR_AT;
            p.parentage = n;
            for (Ssa x : s) {
                if (x.par) {
                    // #5233: command code P sets parentage at the level of its SSA (a GU only, checkCodes)
                    p.parentage = ancestorOfType(n, x.seg);
                }
            }
        }
        if (hold) {
            p.hold = n;
            if (out.size() > 1 || s[k - 1].noRepl) {
                // #5233: a path get-hold: REPL replaces each segment returned, but those coded N
                p.holdPath = out;
                p.holdSkip = new boolean[out.size()];
                int j = 0;
                for (int i = 0; i < k - 1; i++) {
                    if (s[i].path) {
                        p.holdSkip[j++] = s[i].noRepl;
                    }
                }
                p.holdSkip[j] = s[k - 1].noRepl;
            }
        }
    }

    /** ISRT: the last SSA names the type inserted; the SSAs before it locate the parent from the root, or current
     *  position does. */
    // [rule RT-DLI-ISRT]
    private static void isrt(Pcb p, Field io, Ssa[] s) {
        int k = s.length;
        if (!p.load && !allows(p, 'I')) {
            status(p, "AM");
            return;
        }
        if (k == 0) {
            throw refuse("an ISRT with no SSA");
        }
        if (s[k - 1].fld >= 0) {
            throw refuse("an ISRT whose last SSA is qualified");
        }
        String bad = chain(s, k);
        if (bad != null) {
            status(p, bad);
            return;
        }
        if (p.load) {
            loadIsrt(p, io, s);
            return;
        }
        for (int i = 0; i < k - 1; i++) {
            if (s[i].path) {
                pathIsrt(p, io, s);
                return;
            }
        }
        int t = s[k - 1].seg;
        Segm sg = SEGS.get(t);
        Node parent;
        if (sg.parent < 0) {
            if (k > 1) {
                throw refuse("an ISRT of a root with SSAs before it");
            }
            parent = ROOTS.get(p.db);
        } else if (k == 1) {
            if (p.pos != POS_AT) {
                throw refuse("an ISRT that relies on a position left open");
            }
            parent = ancestorOfType(p.at, sg.parent);
            if (parent == null) {
                throw refuse("an ISRT whose parent is not on the current position's path");
            }
        } else {
            if (SEGS.get(s[0].seg).parent >= 0) {
                throw refuse("an ISRT whose SSAs leave out the root level");
            }
            parent = firstSatisfying(dbFirst(p.db), null, s, k - 1);
            if (parent == null) {
                status(p, "GE");
                feedback(p, deepest(p.db, s, k - 2));
                p.pos = POS_UNKNOWN;
                p.par = PAR_UNKNOWN;
                return;
            }
        }
        byte[] b = io.storage().bytes;
        int key = io.offset() + FLDS.get(sg.key).start - 1;
        for (Node c : parent.kids) {
            if (c.seg == t && keyCmp(c, b, key) == 0) {
                status(p, "II");
                feedback(p, parent.parent != null ? parent : null);
                p.pos = POS_UNKNOWN;
                p.par = PAR_UNKNOWN;
                return;
            }
        }
        Node n = new Node();
        n.seg = t;
        n.data = Arrays.copyOfRange(b, io.offset(), io.offset() + sg.bytes);
        linkChild(parent, n);
        status(p, "  ");
        feedback(p, n);
        p.pos = POS_AT;
        p.at = n;
        p.prevknown = false;
        p.par = PAR_UNKNOWN;
    }

    /** Load-mode ISRT (#5233, PROCOPT L / LS on a DB PCB; twin of ggdli.c's load_isrt). The database is built in hierarchic sequence: a
     *  segment goes under the last loaded segment of its parent's type (none: LD), after the twins already loaded under that parent
     *  and not before them (a segment type earlier in the DBD than one already there: LE; an equal sequence field: LB; a lower one:
     *  LC). ASSUMPTION (no IBM text quoted): which of LB / LC / LD / LE a call that breaks two rules answers (the order above), and the
     *  PCB's key feedback after a failed load ISRT (left as it was). */
    private static void loadIsrt(Pcb p, Field io, Ssa[] s) {
        int k = s.length;
        if (k > 1) {
            throw refuse("a load-mode ISRT with SSAs before the last");
        }
        int t = s[0].seg;
        Segm sg = SEGS.get(t);
        Node root = ROOTS.get(p.db);
        if (p.loadLast == null && !root.kids.isEmpty()) {
            throw refuse("load mode into a database that already holds segments");
        }
        Node parent = sg.parent < 0 ? root : ancestorOfType(p.loadLast, sg.parent);
        if (parent == null) {
            status(p, "LD");
            return;
        }
        byte[] b = io.storage().bytes;
        int key = io.offset() + FLDS.get(sg.key).start - 1;
        if (!parent.kids.isEmpty()) {
            Node last = parent.kids.get(parent.kids.size() - 1);
            String bad = null;
            if (last.seg > t) {
                bad = "LE";
            } else if (last.seg == t) {
                int c = keyCmp(last, b, key);
                bad = c == 0 ? "LB" : c > 0 ? "LC" : null;
            }
            if (bad != null) {
                status(p, bad);
                return;
            }
        }
        Node n = new Node();
        n.seg = t;
        n.data = Arrays.copyOfRange(b, io.offset(), io.offset() + sg.bytes);
        linkChild(parent, n);
        p.loadLast = n;
        status(p, "  ");
        feedback(p, n);
        p.pos = POS_AT;
        p.at = n;
        p.prevknown = false;
        p.par = PAR_UNKNOWN;
    }

    /** Path ISRT (#5233, command code D on an SSA before the last): the I/O area holds each D-coded segment and then the last
     *  one, fixed length, in hierarchic order. A level is found in its parent's children (a D-coded one by the sequence field in its
     *  slice, another by its SSA) and inserted from its slice when a D-coded one is missing. ASSUMPTION (no IBM text quoted): a
     *  D-coded segment that exists is kept as it is and its slice is not compared; the last segment is inserted as an ordinary ISRT. */
    // [rule RT-DLI-ISRT]
    private static void pathIsrt(Pcb p, Field io, Ssa[] s) {
        int k = s.length;
        if (SEGS.get(s[0].seg).parent >= 0) {
            throw refuse("an ISRT whose SSAs leave out the root level");
        }
        byte[] b = io.storage().bytes;
        int at = io.offset();
        Node parent = ROOTS.get(p.db);
        for (int i = 0; i < k; i++) {
            int t = s[i].seg;
            Segm sg = SEGS.get(t);
            boolean coded = i == k - 1 || s[i].path;
            int key = at + FLDS.get(sg.key).start - 1;
            if (coded && at + sg.bytes > b.length) {
                throw refuse("a path ISRT whose I/O area is shorter than the segments it names");
            }
            Node found = null;
            for (Node c : parent.kids) {
                if (c.seg == t && (coded ? keyCmp(c, b, key) == 0 : satisfies(c, s, i + 1))) {
                    found = c;
                    break;
                }
            }
            if (i == k - 1) {
                if (found != null) {
                    status(p, "II");
                    feedback(p, parent.parent != null ? parent : null);
                    p.pos = POS_UNKNOWN;
                    p.par = PAR_UNKNOWN;
                    return;
                }
                Node n = new Node();
                n.seg = t;
                n.data = Arrays.copyOfRange(b, at, at + sg.bytes);
                linkChild(parent, n);
                status(p, "  ");
                feedback(p, n);
                p.pos = POS_AT;
                p.at = n;
                p.prevknown = false;
                p.par = PAR_UNKNOWN;
                return;
            }
            if (found == null && !coded) {
                status(p, "GE");
                feedback(p, parent.parent != null ? parent : null);
                p.pos = POS_UNKNOWN;
                p.par = PAR_UNKNOWN;
                return;
            }
            if (found == null) {
                Node n = new Node();
                n.seg = t;
                n.data = Arrays.copyOfRange(b, at, at + sg.bytes);
                n.parent = parent; // so the SSA's qualification can be read before the segment is linked
                if (!satisfies(n, s, i + 1)) {
                    throw refuse("a path ISRT whose segment does not satisfy its own SSA");
                }
                linkChild(parent, n);
                found = n;
            } else if (!satisfies(found, s, i + 1)) {
                throw refuse("a path ISRT whose existing segment does not satisfy its own SSA");
            }
            if (coded) {
                at += sg.bytes;
            }
            parent = found;
        }
    }

    /** REPL / DLET: on the segment the previous call on this PCB held. */
    // [rule RT-DLI-CHANGE]
    private static void change(Pcb p, boolean dlet, Field io, Node held, int k, List<Node> path, boolean[] skip) {
        if (!allows(p, dlet ? 'D' : 'R')) {
            status(p, "AM");
            return;
        }
        if (k > 0) {
            throw refuse(dlet ? "a DLET with SSAs" : "a REPL with SSAs");
        }
        if (held == null) {
            status(p, "DJ");
            return;
        }
        byte[] b = io.storage().bytes;
        if (path != null) {
            changePath(p, dlet, io, path, skip);
            return;
        }
        if (keyCmp(held, b, io.offset() + keyAt(held)) != 0) {
            status(p, "DA");
            return;
        }
        status(p, "  ");
        if (!dlet) {
            System.arraycopy(b, io.offset(), held.data, 0, held.data.length);
            return;
        }
        Node prev = null;
        for (Node c = dbFirst(p.db); c != null && c != held; c = nextInSeq(c)) {
            prev = c;
        }
        held.parent.kids.remove(held);
        for (Pcb o : PCBS) {
            if (o != p && o.db == p.db && o.pos == POS_AT && (o.at == held || descends(o.at, held))) {
                o.pos = POS_UNKNOWN;
            }
            if (o.par == PAR_AT && (o.parentage == held || descends(o.parentage, held))) {
                o.par = PAR_UNKNOWN;
            }
        }
        p.pos = prev != null ? POS_AT : POS_START;
        p.at = prev;
        p.prevknown = false;
    }

    private static final List<String> KNOWN = List.of("GU  ", "GHU ", "GN  ", "GHN ", "GNP ", "GHNP", "ISRT", "REPL",
        "DLET");
    private static final List<String> OTHER = List.of("CHKP", "XRST", "ROLB", "ROLL", "ROLS", "SETS", "SETU", "SYNC",
        "LOG ", "STAT", "GSCD", "FLD ", "POS ", "INIT", "INQY", "SNAP", "PCB ", "TERM", "GMSG", "ICMD", "RCMD", "CMD ",
        "GCMD", "AUTH", "CHNG", "PURG", "DEQ ", "SETO", "APSB", "DPSB", "GSTA");

    /** A GSAM PCB (load mode, #5233; twin of ggdli.c's gsam_call): ISRT appends one record, any other function is AM. */
    // [rule RT-DLI-GSAM]
    static void gsamCall(Pcb p, String fn, Field io, Field[] ssas) {
        if (!fn.equals("ISRT")) {
            status(p, "AM");
            return;
        }
        if (ssas.length != 0) {
            throw refuse("a GSAM ISRT with an SSA");
        }
        if (io.storage().bytes.length - io.offset() < p.reclen) {
            throw refuse("a GSAM ISRT whose I/O area is shorter than the DBD's record");
        }
        p.out.write(io.storage().bytes, io.offset(), p.reclen);
        status(p, "  ");
    }

    /** REPL / DLET after a D-coded get-hold (#5233): the I/O area holds the segments the get returned, one after another. REPL
     *  replaces each segment from its slice of the area except those coded N; a changed sequence field in any replaced one is DA
     *  and nothing is replaced. A DLET after a path call is not modelled. */
    // [rule RT-DLI-CHANGE]
    private static void changePath(Pcb p, boolean dlet, Field io, List<Node> path, boolean[] skip) {
        if (dlet) {
            throw refuse("a DLET after a path call (command code D)");
        }
        byte[] b = io.storage().bytes;
        int off = io.offset();
        int total = 0;
        for (Node o : path) {
            total += o.data.length;
        }
        if (b.length - off < total) {
            throw refuse("an I/O area shorter than the segments of a path REPL");
        }
        int at = off;
        for (int i = 0; i < path.size(); i++) {
            Node o = path.get(i);
            if (!skip[i] && keyCmp(o, b, at + keyAt(o)) != 0) {
                status(p, "DA");
                return;
            }
            at += o.data.length;
        }
        status(p, "  ");
        at = off;
        for (int i = 0; i < path.size(); i++) {
            Node o = path.get(i);
            if (!skip[i]) {
                System.arraycopy(b, at, o.data, 0, o.data.length);
            }
            at += o.data.length;
        }
    }

    /** CALL 'CBLTDLI' USING function pcb io-area [ssa ...]. */
    // [rule RT-DLI-CALL]
    public static void call(Field function, Field pcb, Field io, Field... ssas) {
        if (PCBS.isEmpty()) {
            throw refuse("a call before the program's DL/I entry");
        }
        Pcb p = findPcb(pcb);
        String fn = new String(function.storage().bytes, function.offset(), 4, StandardCharsets.ISO_8859_1);
        Node held = p.hold;
        p.hold = null;
        List<Node> heldPath = p.holdPath;
        boolean[] heldSkip = p.holdSkip;
        p.holdPath = null;
        p.holdSkip = null;
        String fault = KNOWN.contains(fn) ? planned(fn) : null;
        if (fault != null) {
            status(p, fault);
            return;
        }
        if (!KNOWN.contains(fn)) {
            if (OTHER.contains(fn)) {
                throw refuse("a DL/I call other than GU GHU GN GHN GNP GHNP ISRT REPL DLET");
            }
            status(p, "AD");
            return;
        }
        if (p.gsam) { // #5233
            gsamCall(p, fn, io, ssas);
            return;
        }
        if (ssas.length > 15) {
            throw refuse("more than 15 SSAs");
        }
        String[] st = new String[1];
        Ssa[] s = parseSsas(p.db, ssas, st);
        if (st[0] != null) {
            status(p, st[0]);
            return;
        }
        checkCodes(fn, s);
        s = expandCat(s);
        if (fn.charAt(0) == 'G') {
            get(p, fn, io, s, fn.charAt(1) == 'H');
        } else if (fn.equals("ISRT")) {
            isrt(p, io, s);
        } else {
            change(p, fn.charAt(0) == 'D', io, held, s.length, heldPath, heldSkip);
        }
    }
}
