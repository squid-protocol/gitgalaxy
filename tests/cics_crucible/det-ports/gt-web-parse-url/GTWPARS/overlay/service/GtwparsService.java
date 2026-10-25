// gitgalaxy-det-port: COBOL GTWPARS (GTWPARS.cbl), translated by rule, statement for statement
package com.gitgalaxy.modernized.service;

import com.gitgalaxy.modernized.cobolrt.standalone.CobolAbend;
import com.gitgalaxy.modernized.cobolrt.standalone.Sysout;
import com.gitgalaxy.modernized.cobolrt.Cobol;
import com.gitgalaxy.modernized.cobolrt.Field;
import com.gitgalaxy.modernized.cobolrt.Figurative;
import com.gitgalaxy.modernized.cobolrt.Funcs;
import com.gitgalaxy.modernized.cobolrt.Hole;
import com.gitgalaxy.modernized.cobolrt.Storage;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.cobolrt.cics.DetCics;
import com.gitgalaxy.modernized.entity.vsam.*;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * GTWPARS: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 72, translated 72, holes 0.
 */
@Service
public class GtwparsService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D36 = new BigDecimal("36");
    private static final BigDecimal D27 = new BigDecimal("27");
    private static final BigDecimal D25 = new BigDecimal("25");
    private static final BigDecimal D29 = new BigDecimal("29");
    private static final BigDecimal D17 = new BigDecimal("17");
    private static final BigDecimal D30 = new BigDecimal("30");
    private static final BigDecimal D4 = new BigDecimal("4");
    private static final BigDecimal D116 = new BigDecimal("116");
    private static final BigDecimal D1 = new BigDecimal("1");
    private static final BigDecimal D256 = new BigDecimal("256");
    private static final BigDecimal D0 = new BigDecimal("0");

    private static final byte[] IMAGE_s_WS_INPUT = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_INLEN = Base64.getDecoder().decode(String.join("",
            "AAg="));
    private static final byte[] IMAGE_s_WS_MODE = Base64.getDecoder().decode(String.join("",
            "IA=="));
    private static final byte[] IMAGE_s_WS_RESP = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_RESP2 = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_DONE = Base64.getDecoder().decode(String.join("",
            "RE9ORSBPSyA="));
    private static final byte[] IMAGE_s_WS_URL = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_ULEN = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_SCHEME = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_HOST = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_HLEN = Base64.getDecoder().decode(String.join("",
            "AAAAdA=="));
    private static final byte[] IMAGE_s_WS_PORT = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_PATH = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_PLEN = Base64.getDecoder().decode(String.join("",
            "AAABAA=="));
    private static final byte[] IMAGE_s_WS_QRY = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_QLEN = Base64.getDecoder().decode(String.join("",
            "AAABAA=="));
    private static final byte[] IMAGE_s_WS_HIN = Base64.getDecoder().decode(String.join("",
            "AAAAdA=="));
    private static final byte[] IMAGE_s_WS_PIN = Base64.getDecoder().decode(String.join("",
            "AAABAA=="));
    private static final byte[] IMAGE_s_WS_QIN = Base64.getDecoder().decode(String.join("",
            "AAABAA=="));
    private static final byte[] IMAGE_s_WS_CLOG = Base64.getDecoder().decode(String.join("",
            "ICAgIFI9MDAgUz0wMDAgU0NIPSAgICAgIFA9MDAwMDAgSEw9MDAwIEg9ICAgICAgICAgICAgICAgICAgICAgUD0gICAgICAgICAgIFE9ICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_INPUT = new Storage(IMAGE_s_WS_INPUT.length);
    private final Storage s_WS_INLEN = new Storage(IMAGE_s_WS_INLEN.length);
    private final Storage s_WS_MODE = new Storage(IMAGE_s_WS_MODE.length);
    private final Storage s_WS_RESP = new Storage(IMAGE_s_WS_RESP.length);
    private final Storage s_WS_RESP2 = new Storage(IMAGE_s_WS_RESP2.length);
    private final Storage s_WS_DONE = new Storage(IMAGE_s_WS_DONE.length);
    private final Storage s_WS_URL = new Storage(IMAGE_s_WS_URL.length);
    private final Storage s_WS_ULEN = new Storage(IMAGE_s_WS_ULEN.length);
    private final Storage s_WS_SCHEME = new Storage(IMAGE_s_WS_SCHEME.length);
    private final Storage s_WS_HOST = new Storage(IMAGE_s_WS_HOST.length);
    private final Storage s_WS_HLEN = new Storage(IMAGE_s_WS_HLEN.length);
    private final Storage s_WS_PORT = new Storage(IMAGE_s_WS_PORT.length);
    private final Storage s_WS_PATH = new Storage(IMAGE_s_WS_PATH.length);
    private final Storage s_WS_PLEN = new Storage(IMAGE_s_WS_PLEN.length);
    private final Storage s_WS_QRY = new Storage(IMAGE_s_WS_QRY.length);
    private final Storage s_WS_QLEN = new Storage(IMAGE_s_WS_QLEN.length);
    private final Storage s_WS_HIN = new Storage(IMAGE_s_WS_HIN.length);
    private final Storage s_WS_PIN = new Storage(IMAGE_s_WS_PIN.length);
    private final Storage s_WS_QIN = new Storage(IMAGE_s_WS_QIN.length);
    private final Storage s_WS_CLOG = new Storage(IMAGE_s_WS_CLOG.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_INPUT = Field.alphanumeric(s_WS_INPUT, 0, 8, false);
    private final Field f2_WS_INLEN = Field.binary(s_WS_INLEN, 0, 4, 0, true, false);
    private final Field f3_WS_MODE = Field.alphanumeric(s_WS_MODE, 0, 1, false);
    private final Field f4_WS_RESP = Field.binary(s_WS_RESP, 0, 8, 0, true, false);
    private final Field f5_WS_RESP2 = Field.binary(s_WS_RESP2, 0, 8, 0, true, false);
    private final Field f6_WS_DONE = Field.alphanumeric(s_WS_DONE, 0, 8, false);
    private final Field f7_WS_URL = Field.alphanumeric(s_WS_URL, 0, 64, false);
    private final Field f8_WS_ULEN = Field.binary(s_WS_ULEN, 0, 8, 0, true, false);
    private final Field f9_WS_SCHEME = Field.alphanumeric(s_WS_SCHEME, 0, 16, false);
    private final Field f10_WS_HOST = Field.alphanumeric(s_WS_HOST, 0, 116, false);
    private final Field f11_WS_HLEN = Field.binary(s_WS_HLEN, 0, 8, 0, true, false);
    private final Field f12_WS_PORT = Field.binary(s_WS_PORT, 0, 8, 0, true, false);
    private final Field f13_WS_PATH = Field.alphanumeric(s_WS_PATH, 0, 256, false);
    private final Field f14_WS_PLEN = Field.binary(s_WS_PLEN, 0, 8, 0, true, false);
    private final Field f15_WS_QRY = Field.alphanumeric(s_WS_QRY, 0, 256, false);
    private final Field f16_WS_QLEN = Field.binary(s_WS_QLEN, 0, 8, 0, true, false);
    private final Field f17_WS_HIN = Field.binary(s_WS_HIN, 0, 8, 0, true, false);
    private final Field f18_WS_PIN = Field.binary(s_WS_PIN, 0, 8, 0, true, false);
    private final Field f19_WS_QIN = Field.binary(s_WS_QIN, 0, 8, 0, true, false);
    private final Field f20_WS_CLOG = Field.group(s_WS_CLOG, 0, 88);
    private final Field f21_CLOG_TAG = Field.alphanumeric(s_WS_CLOG, 0, 3, false);
    private final Field f23_CLOG_RESP = Field.zoned(s_WS_CLOG, 6, 2, 0, false, false, false);
    private final Field f25_CLOG_RESP2 = Field.zoned(s_WS_CLOG, 11, 3, 0, false, false, false);
    private final Field f27_CLOG_SCH = Field.alphanumeric(s_WS_CLOG, 19, 5, false);
    private final Field f29_CLOG_PORT = Field.zoned(s_WS_CLOG, 27, 5, 0, false, false, false);
    private final Field f31_CLOG_HL = Field.zoned(s_WS_CLOG, 36, 3, 0, false, false, false);
    private final Field f33_CLOG_HOST = Field.alphanumeric(s_WS_CLOG, 42, 20, false);
    private final Field f35_CLOG_PATH = Field.alphanumeric(s_WS_CLOG, 65, 10, false);
    private final Field f37_CLOG_QRY = Field.alphanumeric(s_WS_CLOG, 78, 10, false);
    private final Field f39_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f40_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f41_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f42_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f43_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f46_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f67_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f68_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f70_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

    private CicsTask task;
    private static final Charset REGION = DetCics.region("IBM037");
    private final java.util.Map<String, Integer> handlers = new java.util.HashMap<>();
    private final java.util.Map<String, DetCics.Store<?>> stores = new java.util.HashMap<>();
    private final java.util.Map<String, byte[]> heldKey = new java.util.HashMap<>();
    /** Writes the COMMAREA's bytes back into the object the task carries (a LINKed program's is its caller's). */
    private Runnable caBack = () -> { };

    /** The program ends because of an abend: a LINKed program's COMMAREA writes stay its caller's. */
    private Goback abended() {
        if (task.level() > 1) {
            caBack.run();
        }
        return new Goback();
    }

    @SuppressWarnings("unchecked")
    private <E> DetCics.Store<E> store(String name) {
        throw new Hole("CICS file " + name + ": the program names no file the generated project stores");
    }

    private static final java.util.Map<String, Integer> PARAGRAPHS = java.util.Map.ofEntries(
            java.util.Map.entry("DO-PARSE", 4),
            java.util.Map.entry("LENGTH-PARA", 3),
            java.util.Map.entry("ERROR-PARA", 2),
            java.util.Map.entry("PARSE-PARA", 1),
            java.util.Map.entry("MAIN-PARA", 0)
    );

    private static int paragraph(String name) {
        Integer i = PARAGRAPHS.get(name);
        if (i == null) {
            throw new IllegalStateException("no paragraph " + name);
        }
        return i;
    }

    /** A condition the command did not return in RESP: its HANDLE CONDITION label, or -1 (go on) when IGNOREd
     *  (#4414); else CICS's default action -- -1 for one whose default is to ignore it (#4413: EOC); else the
     *  ERROR label (#4502: IBM, HANDLE CONDITION: "if the default action for such a condition terminates the
     *  task abnormally, and the condition ERROR has been specified, the action for ERROR is taken"); else an
     *  abend, to this program's HANDLE ABEND exit or ending the task. */
    private int condition(String cond) {
        Integer h = handlers.get(cond);
        if (h != null) {
            return h;
        }
        if (DetCics.ignoredByDefault(cond)) {
            return -1;
        }
        Integer error = handlers.get("ERROR");
        if (error != null) {
            return error;
        }
        String label = task.abendOnCondition(cond);
        if (label == null) {
            throw abended();
        }
        return paragraph(label);
    }

    private static int cx(CicsTask task, int whole) {
        return task.eibcalen() == null ? whole : task.eibcalen();
    }



    public GtwparsService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_INPUT, 0, s_WS_INPUT.bytes, 0, IMAGE_s_WS_INPUT.length);
        System.arraycopy(IMAGE_s_WS_INLEN, 0, s_WS_INLEN.bytes, 0, IMAGE_s_WS_INLEN.length);
        System.arraycopy(IMAGE_s_WS_MODE, 0, s_WS_MODE.bytes, 0, IMAGE_s_WS_MODE.length);
        System.arraycopy(IMAGE_s_WS_RESP, 0, s_WS_RESP.bytes, 0, IMAGE_s_WS_RESP.length);
        System.arraycopy(IMAGE_s_WS_RESP2, 0, s_WS_RESP2.bytes, 0, IMAGE_s_WS_RESP2.length);
        System.arraycopy(IMAGE_s_WS_DONE, 0, s_WS_DONE.bytes, 0, IMAGE_s_WS_DONE.length);
        System.arraycopy(IMAGE_s_WS_URL, 0, s_WS_URL.bytes, 0, IMAGE_s_WS_URL.length);
        System.arraycopy(IMAGE_s_WS_ULEN, 0, s_WS_ULEN.bytes, 0, IMAGE_s_WS_ULEN.length);
        System.arraycopy(IMAGE_s_WS_SCHEME, 0, s_WS_SCHEME.bytes, 0, IMAGE_s_WS_SCHEME.length);
        System.arraycopy(IMAGE_s_WS_HOST, 0, s_WS_HOST.bytes, 0, IMAGE_s_WS_HOST.length);
        System.arraycopy(IMAGE_s_WS_HLEN, 0, s_WS_HLEN.bytes, 0, IMAGE_s_WS_HLEN.length);
        System.arraycopy(IMAGE_s_WS_PORT, 0, s_WS_PORT.bytes, 0, IMAGE_s_WS_PORT.length);
        System.arraycopy(IMAGE_s_WS_PATH, 0, s_WS_PATH.bytes, 0, IMAGE_s_WS_PATH.length);
        System.arraycopy(IMAGE_s_WS_PLEN, 0, s_WS_PLEN.bytes, 0, IMAGE_s_WS_PLEN.length);
        System.arraycopy(IMAGE_s_WS_QRY, 0, s_WS_QRY.bytes, 0, IMAGE_s_WS_QRY.length);
        System.arraycopy(IMAGE_s_WS_QLEN, 0, s_WS_QLEN.bytes, 0, IMAGE_s_WS_QLEN.length);
        System.arraycopy(IMAGE_s_WS_HIN, 0, s_WS_HIN.bytes, 0, IMAGE_s_WS_HIN.length);
        System.arraycopy(IMAGE_s_WS_PIN, 0, s_WS_PIN.bytes, 0, IMAGE_s_WS_PIN.length);
        System.arraycopy(IMAGE_s_WS_QIN, 0, s_WS_QIN.bytes, 0, IMAGE_s_WS_QIN.length);
        System.arraycopy(IMAGE_s_WS_CLOG, 0, s_WS_CLOG.bytes, 0, IMAGE_s_WS_CLOG.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 4);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f70_GG_RETURN_CODE, CS).intValue();
    }

    /** One task of the program: the EIB and COMMAREA from the task, then the PROCEDURE DIVISION. */
    public void runTask(CicsTask task) {
        boolean truncBefore = Cobol.swapTruncBinary(true);  // TRUNC(STD)
        boolean pfdBefore = Cobol.swapNumprocPfd(false);  // NUMPROC(NOPFD)
        try {
            this.task = task;
            caBack = () -> { };
            handlers.clear();
            heldKey.clear();
            initialState();
            Cobol.move(task.transid(), f41_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f43_EIBTRMID, CS);
            Cobol.store(f42_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f40_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f39_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            Cobol.store(f46_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                perform(0, 4);
            } catch (Goback g) {
                // RETURN / XCTL / an abend ended the program
            }
            if (!task.ended()) {
                caBack.run();
                task.returnTransid(null, null);  // a GOBACK is a RETURN
            }
        } finally {
            Cobol.swapTruncBinary(truncBefore);
            Cobol.swapNumprocPfd(pfdBefore);
        }
    }

    public void handleTransaction(String transid) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, null);
        region.run(task, "GTWPARS", this::runTask);
    }

    public void handleTransaction(String transid, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, null, area);
        region.run(task, "GTWPARS", this::runTask);
        lastAnswerBytes = task.returnedBytes();
    }

    // @facade-helper: the bytes the last byte-carrying handleTransaction answered
    private byte[] lastAnswerBytes;

    /** The bytes the last byte-carrying handleTransaction's RETURN passed on (a copy; null: none).
     *  @facade-helper */
    public byte[] lastAnswerBytes() {
        return lastAnswerBytes == null ? null : java.util.Arrays.copyOf(lastAnswerBytes, lastAnswerBytes.length);
    }


    /** GOBACK / STOP RUN. */
    private static final class Goback extends RuntimeException {
        private static final long serialVersionUID = 1L;

        Goback() {
            super(null, null, false, false);
        }
    }

    /** The active PERFORMs' last paragraphs, outermost first. */
    private int[] performThru = new int[64];
    private int performDepth = 0;

    /** Control reached the end of an outer active PERFORM's range: that PERFORM returns (`depth`). */
    private static final class PerformExit extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final int depth;

        PerformExit(int depth) {
            super(null, null, false, false);
            this.depth = depth;
        }
    }

    /** PERFORM from THRU thru. When control falls off the end of a paragraph, the innermost active PERFORM
     *  whose range ends there returns -- this one, or an outer one a GO TO reached the end of, abandoning
     *  the PERFORMs inside it (GnuCOBOL, as IBM: test_det_programs.py, GOTOOUT). */
    private void perform(int from, int thru) {
        int mine = performDepth;
        if (mine == performThru.length) {
            performThru = java.util.Arrays.copyOf(performThru, mine * 2);
        }
        performThru[performDepth++] = thru;
        try {
            int i = from;
            while (true) {
                int next = run(i);
                boolean jumped = (next & GOTO) != 0;
                next &= ~GOTO;
                if (!jumped) {
                    if (i == thru) {
                        return;
                    }
                    for (int d = mine - 1; d >= 0; d--) {
                        if (performThru[d] == i) {
                            throw new PerformExit(d);
                        }
                    }
                }
                if (next >= 5) {
                    throw new Goback();
                }
                i = next;
            }
        } catch (PerformExit e) {
            if (e.depth != mine) {
                throw e;
            }
        } finally {
            performDepth = mine;
        }
    }

    private int run(int i) {
        switch (i) {
            case 0: return p0();
            case 1: return p1();
            case 2: return p2();
            case 3: return p3();
            case 4: return p4();
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** MAIN-PARA. */
    private int p0() {
        // EXEC CICS RECEIVE INTO(WS-INPUT) LENGTH(WS-INLEN) END-EXEC
        CicsTask.Received received1 = task.receive(Cobol.num(f2_WS_INLEN, CS).intValue(), false);
        DetCics.received(f1_WS_INPUT, received1.data(), CS);
        Cobol.store(f2_WS_INLEN, BigDecimal.valueOf(received1.length()), false, CS);
        Cobol.store(f67_EIBRESP, BigDecimal.valueOf(DetCics.resp(received1.resp())), false, CS);
        Cobol.store(f68_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(received1.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(received1.resp())));
            if (to >= 0) return GOTO | to;
        }
        // MOVE WS-INPUT(6:1) TO WS-MODE
        Cobol.move(f1_WS_INPUT.ref(6, Integer.valueOf(1)), f3_WS_MODE, CS);
        // EVALUATE WS-MODE
        if ((Cobol.compare(f3_WS_MODE, "P", CS) == 0)) {
            // PERFORM PARSE-PARA
            perform(1, 1);
        } else if ((Cobol.compare(f3_WS_MODE, "E", CS) == 0)) {
            // PERFORM ERROR-PARA
            perform(2, 2);
        } else if ((Cobol.compare(f3_WS_MODE, "L", CS) == 0)) {
            // PERFORM LENGTH-PARA
            perform(3, 3);
        }
        // EXEC CICS SEND TEXT FROM(WS-DONE) LENGTH(8) ERASE END-EXEC
        String text2 = Cobol.text(f6_WS_DONE, CS);
        task.sendText(text2.substring(0, Math.min(text2.length(), 8)), 8, "ERASE");
        Cobol.store(f67_EIBRESP, BigDecimal.valueOf(0), false, CS);
        Cobol.store(f68_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (0 != 0) {
            int to = condition(DetCics.condition(0));
            if (to >= 0) return GOTO | to;
        }
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        return 1;
    }

    /** PARSE-PARA. */
    private int p1() {
        // MOVE 'P1 ' TO CLOG-TAG
        Cobol.move("P1 ", f21_CLOG_TAG, CS);
        // MOVE 'https://example.com:8443/a/b?x=1&y=2' TO WS-URL
        Cobol.move("https://example.com:8443/a/b?x=1&y=2", f7_WS_URL, CS);
        // MOVE 36 TO WS-ULEN
        Cobol.move(D36, f8_WS_ULEN, CS);
        // PERFORM DO-PARSE
        perform(4, 4);
        // MOVE 'P2 ' TO CLOG-TAG
        Cobol.move("P2 ", f21_CLOG_TAG, CS);
        // MOVE 'HtTp://example.org/docs?q=7' TO WS-URL
        Cobol.move("HtTp://example.org/docs?q=7", f7_WS_URL, CS);
        // MOVE 27 TO WS-ULEN
        Cobol.move(D27, f8_WS_ULEN, CS);
        // PERFORM DO-PARSE
        perform(4, 4);
        // MOVE 'P3 ' TO CLOG-TAG
        Cobol.move("P3 ", f21_CLOG_TAG, CS);
        // MOVE 'hTTps://example.net/s?k=v' TO WS-URL
        Cobol.move("hTTps://example.net/s?k=v", f7_WS_URL, CS);
        // MOVE 25 TO WS-ULEN
        Cobol.move(D25, f8_WS_ULEN, CS);
        // PERFORM DO-PARSE
        perform(4, 4);
        // MOVE 'P4 ' TO CLOG-TAG
        Cobol.move("P4 ", f21_CLOG_TAG, CS);
        // MOVE 'http://192.0.2.7:8080/a?b=c' TO WS-URL
        Cobol.move("http://192.0.2.7:8080/a?b=c", f7_WS_URL, CS);
        // MOVE 27 TO WS-ULEN
        Cobol.move(D27, f8_WS_ULEN, CS);
        // PERFORM DO-PARSE
        perform(4, 4);
        // MOVE 'P5 ' TO CLOG-TAG
        Cobol.move("P5 ", f21_CLOG_TAG, CS);
        // MOVE 'http://[2001:db8::1]:81/a?b=c' TO WS-URL
        Cobol.move("http://[2001:db8::1]:81/a?b=c", f7_WS_URL, CS);
        // MOVE 29 TO WS-ULEN
        Cobol.move(D29, f8_WS_ULEN, CS);
        // PERFORM DO-PARSE
        perform(4, 4);
        return 2;
    }

    /** ERROR-PARA. */
    private int p2() {
        // MOVE 'E1 ' TO CLOG-TAG
        Cobol.move("E1 ", f21_CLOG_TAG, CS);
        // MOVE 'example.com/a?x=1' TO WS-URL
        Cobol.move("example.com/a?x=1", f7_WS_URL, CS);
        // MOVE 17 TO WS-ULEN
        Cobol.move(D17, f8_WS_ULEN, CS);
        // PERFORM DO-PARSE
        perform(4, 4);
        // MOVE 'E2 ' TO CLOG-TAG
        Cobol.move("E2 ", f21_CLOG_TAG, CS);
        // MOVE 'http://example.com/a%zz?x=1' TO WS-URL
        Cobol.move("http://example.com/a%zz?x=1", f7_WS_URL, CS);
        // MOVE 27 TO WS-ULEN
        Cobol.move(D27, f8_WS_ULEN, CS);
        // PERFORM DO-PARSE
        perform(4, 4);
        return 3;
    }

    /** LENGTH-PARA. */
    private int p3() {
        // MOVE 'http://example.com/a/b?x=1&y=2' TO WS-URL
        Cobol.move("http://example.com/a/b?x=1&y=2", f7_WS_URL, CS);
        // MOVE 30 TO WS-ULEN
        Cobol.move(D30, f8_WS_ULEN, CS);
        // MOVE 'L1 ' TO CLOG-TAG
        Cobol.move("L1 ", f21_CLOG_TAG, CS);
        // MOVE 4 TO WS-HIN
        Cobol.move(D4, f17_WS_HIN, CS);
        // PERFORM DO-PARSE
        perform(4, 4);
        // MOVE 116 TO WS-HIN
        Cobol.move(D116, f17_WS_HIN, CS);
        // MOVE 'L2 ' TO CLOG-TAG
        Cobol.move("L2 ", f21_CLOG_TAG, CS);
        // MOVE 1 TO WS-PIN
        Cobol.move(D1, f18_WS_PIN, CS);
        // PERFORM DO-PARSE
        perform(4, 4);
        // MOVE 256 TO WS-PIN
        Cobol.move(D256, f18_WS_PIN, CS);
        // MOVE 'L3 ' TO CLOG-TAG
        Cobol.move("L3 ", f21_CLOG_TAG, CS);
        // MOVE 1 TO WS-QIN
        Cobol.move(D1, f19_WS_QIN, CS);
        // PERFORM DO-PARSE
        perform(4, 4);
        // MOVE 256 TO WS-QIN
        Cobol.move(D256, f19_WS_QIN, CS);
        return 4;
    }

    /** DO-PARSE. */
    private int p4() {
        // MOVE SPACES TO WS-SCHEME WS-HOST WS-PATH WS-QRY
        Cobol.moveFigurative(Figurative.SPACES, f9_WS_SCHEME, CS);
        Cobol.moveFigurative(Figurative.SPACES, f10_WS_HOST, CS);
        Cobol.moveFigurative(Figurative.SPACES, f13_WS_PATH, CS);
        Cobol.moveFigurative(Figurative.SPACES, f15_WS_QRY, CS);
        // MOVE 0 TO WS-PORT
        Cobol.move(D0, f12_WS_PORT, CS);
        // MOVE WS-HIN TO WS-HLEN
        Cobol.move(f17_WS_HIN, f11_WS_HLEN, CS);
        // MOVE WS-PIN TO WS-PLEN
        Cobol.move(f18_WS_PIN, f14_WS_PLEN, CS);
        // MOVE WS-QIN TO WS-QLEN
        Cobol.move(f19_WS_QIN, f16_WS_QLEN, CS);
        // EXEC CICS WEB PARSE URL(WS-URL) URLLENGTH(WS-ULEN) SCHEMENAME(WS-SCHEME) HOST(WS-HOST) HOSTLENGTH(WS-HLEN) PORTNUMBER(WS-PORT) PATH(WS-PATH) PATHLENGT
        CicsTask.WebParsed web3 = task.webParse(Cobol.text(f7_WS_URL, CS), Cobol.num(f8_WS_ULEN, CS).intValue(), 16, Integer.valueOf(Cobol.num(f11_WS_HLEN, CS).intValue()), 116, Integer.valueOf(Cobol.num(f14_WS_PLEN, CS).intValue()), 256, Integer.valueOf(Cobol.num(f16_WS_QLEN, CS).intValue()), 256);
        if (web3.resp() == 0) {
            DetCics.putText(f9_WS_SCHEME, web3.scheme(), CS);
            DetCics.putText(f10_WS_HOST, web3.host(), CS);
            Cobol.store(f11_WS_HLEN, BigDecimal.valueOf(web3.host().length()), false, CS);
            DetCics.putText(f13_WS_PATH, web3.path(), CS);
            Cobol.store(f14_WS_PLEN, BigDecimal.valueOf(web3.path().length()), false, CS);
            DetCics.putText(f15_WS_QRY, web3.query(), CS);
            Cobol.store(f16_WS_QLEN, BigDecimal.valueOf(web3.query().length()), false, CS);
            Cobol.store(f12_WS_PORT, BigDecimal.valueOf(web3.port()), false, CS);
        }
        Cobol.store(f67_EIBRESP, BigDecimal.valueOf(web3.resp()), false, CS);
        Cobol.store(f68_EIBRESP2, BigDecimal.valueOf(web3.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(web3.resp()), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(web3.resp2()), false, CS);
        // MOVE SPACES TO CLOG-SCH CLOG-HOST CLOG-PATH CLOG-QRY
        Cobol.moveFigurative(Figurative.SPACES, f27_CLOG_SCH, CS);
        Cobol.moveFigurative(Figurative.SPACES, f33_CLOG_HOST, CS);
        Cobol.moveFigurative(Figurative.SPACES, f35_CLOG_PATH, CS);
        Cobol.moveFigurative(Figurative.SPACES, f37_CLOG_QRY, CS);
        // MOVE 0 TO CLOG-PORT CLOG-HL CLOG-RESP2
        Cobol.move(D0, f29_CLOG_PORT, CS);
        Cobol.move(D0, f31_CLOG_HL, CS);
        Cobol.move(D0, f25_CLOG_RESP2, CS);
        // MOVE WS-RESP TO CLOG-RESP
        Cobol.move(f4_WS_RESP, f23_CLOG_RESP, CS);
        // IF WS-RESP = 0
        if (Cobol.num(f4_WS_RESP, CS).compareTo(D0) == 0) {
            // MOVE WS-SCHEME(1:5) TO CLOG-SCH
            Cobol.move(f9_WS_SCHEME.ref(1, Integer.valueOf(5)), f27_CLOG_SCH, CS);
            // MOVE WS-PORT TO CLOG-PORT
            Cobol.move(f12_WS_PORT, f29_CLOG_PORT, CS);
            // MOVE WS-HLEN TO CLOG-HL
            Cobol.move(f11_WS_HLEN, f31_CLOG_HL, CS);
            // MOVE WS-HOST(1:20) TO CLOG-HOST
            Cobol.move(f10_WS_HOST.ref(1, Integer.valueOf(20)), f33_CLOG_HOST, CS);
            // IF WS-PATH(1:1) = '/'
            if (Cobol.compare(f13_WS_PATH.ref(1, Integer.valueOf(1)), "/", CS) == 0) {
                // MOVE WS-PATH(2:10) TO CLOG-PATH
                Cobol.move(f13_WS_PATH.ref(2, Integer.valueOf(10)), f35_CLOG_PATH, CS);
            } else {
                // MOVE WS-PATH(1:10) TO CLOG-PATH
                Cobol.move(f13_WS_PATH.ref(1, Integer.valueOf(10)), f35_CLOG_PATH, CS);
            }
            // IF WS-QRY(1:1) = '?'
            if (Cobol.compare(f15_WS_QRY.ref(1, Integer.valueOf(1)), "?", CS) == 0) {
                // MOVE WS-QRY(2:10) TO CLOG-QRY
                Cobol.move(f15_WS_QRY.ref(2, Integer.valueOf(10)), f37_CLOG_QRY, CS);
            } else {
                // MOVE WS-QRY(1:10) TO CLOG-QRY
                Cobol.move(f15_WS_QRY.ref(1, Integer.valueOf(10)), f37_CLOG_QRY, CS);
            }
        } else {
            // MOVE WS-RESP2 TO CLOG-RESP2
            Cobol.move(f5_WS_RESP2, f25_CLOG_RESP2, CS);
        }
        // EXEC CICS WRITEQ TS QUEUE('GTWLOG') FROM(WS-CLOG) LENGTH(88) END-EXEC
        CicsTask.TsResult ts4 = task.writeqTs("GTWLOG".strip(), DetCics.toRegion(DetCics.bytes(f20_WS_CLOG, DetCics.within(f20_WS_CLOG, 88, "WRITEQ TS")), CS, REGION));
        Cobol.store(f67_EIBRESP, BigDecimal.valueOf(DetCics.resp(ts4.resp())), false, CS);
        Cobol.store(f68_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(ts4.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(ts4.resp())));
            if (to >= 0) return GOTO | to;
        }
        return 5;
    }

}
