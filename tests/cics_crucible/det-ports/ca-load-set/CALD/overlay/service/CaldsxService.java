// gitgalaxy-det-port: COBOL CALDSX (CALDSX.cbl), translated by rule, statement for statement
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
 * CALDSX: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 27, translated 27, holes 0.
 */
@Service
public class CaldsxService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D0 = new BigDecimal("0");

    private static final byte[] IMAGE_s_WS_PTR = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAA="));
    private static final byte[] IMAGE_s_WS_LEN = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private static final byte[] IMAGE_s_WS_RESP = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_RESP2 = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_LOG = Base64.getDecoder().decode(String.join("",
            "ICAgIDAwMDAwMCAg"));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_PTR = new Storage(IMAGE_s_WS_PTR.length);
    private final Storage s_WS_LEN = new Storage(IMAGE_s_WS_LEN.length);
    private final Storage s_WS_RESP = new Storage(IMAGE_s_WS_RESP.length);
    private final Storage s_WS_RESP2 = new Storage(IMAGE_s_WS_RESP2.length);
    private final Storage s_WS_LOG = new Storage(IMAGE_s_WS_LOG.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_PTR = Field.group(s_WS_PTR, 0, 8);
    private final Field f2_WS_LEN = Field.binary(s_WS_LEN, 0, 4, 0, true, false);
    private final Field f3_WS_RESP = Field.binary(s_WS_RESP, 0, 8, 0, true, false);
    private final Field f4_WS_RESP2 = Field.binary(s_WS_RESP2, 0, 8, 0, true, false);
    private final Field f5_WS_LOG = Field.group(s_WS_LOG, 0, 12);
    private final Field f6_LG_TAG = Field.alphanumeric(s_WS_LOG, 0, 4, false);
    private final Field f7_LG_RESP = Field.zoned(s_WS_LOG, 4, 3, 0, false, false, false);
    private final Field f8_LG_RESP2 = Field.zoned(s_WS_LOG, 7, 3, 0, false, false, false);
    private final Field f9_LG_PTR = Field.alphanumeric(s_WS_LOG, 10, 1, false);
    private final Field f10_LG_LEN = Field.alphanumeric(s_WS_LOG, 11, 1, false);
    private final Field f12_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f13_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f14_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f15_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f16_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f19_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f40_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f41_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f43_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

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
        if (CicsTask.undefinableFile(name)) {
            return DetCics.Store.undefined(CS);
        }
        throw new Hole("CICS file " + name + ": the program names no file the generated project stores");
    }

    private static final java.util.Map<String, Integer> PARAGRAPHS = java.util.Map.ofEntries(
            java.util.Map.entry("LOG-RESP", 1),
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



    public CaldsxService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_PTR, 0, s_WS_PTR.bytes, 0, IMAGE_s_WS_PTR.length);
        System.arraycopy(IMAGE_s_WS_LEN, 0, s_WS_LEN.bytes, 0, IMAGE_s_WS_LEN.length);
        System.arraycopy(IMAGE_s_WS_RESP, 0, s_WS_RESP.bytes, 0, IMAGE_s_WS_RESP.length);
        System.arraycopy(IMAGE_s_WS_RESP2, 0, s_WS_RESP2.bytes, 0, IMAGE_s_WS_RESP2.length);
        System.arraycopy(IMAGE_s_WS_LOG, 0, s_WS_LOG.bytes, 0, IMAGE_s_WS_LOG.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 1);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f43_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f14_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f16_EIBTRMID, CS);
            Cobol.store(f15_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f13_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f12_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            Cobol.store(f19_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                perform(0, 1);
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
        region.run(task, "CALDSX", this::runTask);
    }

    public void handleTransaction(String transid, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, null, area);
        region.run(task, "CALDSX", this::runTask);
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
                if (next >= 2) {
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
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** MAIN-PARA. */
    private int p0() {
        // INITIALIZE WS-LOG
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f5_WS_LOG.storage(), f5_WS_LOG.offset() + 0, 4, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f5_WS_LOG.storage(), f5_WS_LOG.offset() + 4, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f5_WS_LOG.storage(), f5_WS_LOG.offset() + 7, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f5_WS_LOG.storage(), f5_WS_LOG.offset() + 10, 1, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f5_WS_LOG.storage(), f5_WS_LOG.offset() + 11, 1, false), CS);
        // SET WS-PTR TO NULL
        Cobol.moveFigurative(Figurative.LOW_VALUES, f1_WS_PTR, CS);
        // MOVE 0 TO WS-LEN
        Cobol.move(D0, f2_WS_LEN, CS);
        // EXEC CICS LOAD PROGRAM('CALDXX') SET(WS-PTR) LENGTH(WS-LEN) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        long[] load1g = task.loadProgram("CALDXX".strip());
        int[] load1 = new int[] {(int) load1g[0], (int) load1g[1]};
        if (load1[0] == 0) {
            DetCics.setPointer(f1_WS_PTR, load1g[2]);
            Cobol.store(f2_WS_LEN, BigDecimal.valueOf(load1g[3]), false, CS);
        }
        Cobol.store(f40_EIBRESP, BigDecimal.valueOf(load1[0]), false, CS);
        Cobol.store(f41_EIBRESP2, BigDecimal.valueOf(load1[1]), false, CS);
        Cobol.store(f3_WS_RESP, BigDecimal.valueOf(load1[0]), false, CS);
        Cobol.store(f4_WS_RESP2, BigDecimal.valueOf(load1[1]), false, CS);
        // MOVE 'PG01' TO LG-TAG
        Cobol.move("PG01", f6_LG_TAG, CS);
        // MOVE '-' TO LG-PTR
        Cobol.move("-", f9_LG_PTR, CS);
        // MOVE '-' TO LG-LEN
        Cobol.move("-", f10_LG_LEN, CS);
        // PERFORM LOG-RESP
        perform(1, 1);
        // EXEC CICS LOAD PROGRAM('CALDTG') SET(WS-PTR) LENGTH(WS-LEN) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        long[] load2g = task.loadProgram("CALDTG".strip());
        int[] load2 = new int[] {(int) load2g[0], (int) load2g[1]};
        if (load2[0] == 0) {
            DetCics.setPointer(f1_WS_PTR, load2g[2]);
            Cobol.store(f2_WS_LEN, BigDecimal.valueOf(load2g[3]), false, CS);
        }
        Cobol.store(f40_EIBRESP, BigDecimal.valueOf(load2[0]), false, CS);
        Cobol.store(f41_EIBRESP2, BigDecimal.valueOf(load2[1]), false, CS);
        Cobol.store(f3_WS_RESP, BigDecimal.valueOf(load2[0]), false, CS);
        Cobol.store(f4_WS_RESP2, BigDecimal.valueOf(load2[1]), false, CS);
        // MOVE 'OK01' TO LG-TAG
        Cobol.move("OK01", f6_LG_TAG, CS);
        // IF WS-PTR = NULL
        if (Cobol.compareFigurative(f1_WS_PTR, Figurative.LOW_VALUES, CS) == 0) {
            // MOVE 'N' TO LG-PTR
            Cobol.move("N", f9_LG_PTR, CS);
        } else {
            // MOVE 'Y' TO LG-PTR
            Cobol.move("Y", f9_LG_PTR, CS);
        }
        // IF WS-LEN > 0
        if (Cobol.num(f2_WS_LEN, CS).compareTo(D0) > 0) {
            // MOVE 'Y' TO LG-LEN
            Cobol.move("Y", f10_LG_LEN, CS);
        } else {
            // MOVE 'N' TO LG-LEN
            Cobol.move("N", f10_LG_LEN, CS);
        }
        // PERFORM LOG-RESP
        perform(1, 1);
        // EXEC CICS RELEASE PROGRAM('CALDTG') RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int[] load3 = task.releaseProgram("CALDTG".strip());
        Cobol.store(f40_EIBRESP, BigDecimal.valueOf(load3[0]), false, CS);
        Cobol.store(f41_EIBRESP2, BigDecimal.valueOf(load3[1]), false, CS);
        Cobol.store(f3_WS_RESP, BigDecimal.valueOf(load3[0]), false, CS);
        Cobol.store(f4_WS_RESP2, BigDecimal.valueOf(load3[1]), false, CS);
        // MOVE 'RL01' TO LG-TAG
        Cobol.move("RL01", f6_LG_TAG, CS);
        // MOVE '-' TO LG-PTR
        Cobol.move("-", f9_LG_PTR, CS);
        // MOVE '-' TO LG-LEN
        Cobol.move("-", f10_LG_LEN, CS);
        // PERFORM LOG-RESP
        perform(1, 1);
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        return 1;
    }

    /** LOG-RESP. */
    private int p1() {
        // MOVE WS-RESP TO LG-RESP
        Cobol.move(f3_WS_RESP, f7_LG_RESP, CS);
        // MOVE WS-RESP2 TO LG-RESP2
        Cobol.move(f4_WS_RESP2, f8_LG_RESP2, CS);
        // EXEC CICS WRITEQ TS QUEUE('LDLOG') FROM(WS-LOG) END-EXEC
        CicsTask.TsResult ts4 = task.writeqTs("LDLOG".strip(), DetCics.toRegion(DetCics.bytes(f5_WS_LOG, f5_WS_LOG.length()), CS, REGION));
        Cobol.store(f40_EIBRESP, BigDecimal.valueOf(DetCics.resp(ts4.resp())), false, CS);
        Cobol.store(f41_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(ts4.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(ts4.resp())));
            if (to >= 0) return GOTO | to;
        }
        // INITIALIZE WS-LOG
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f5_WS_LOG.storage(), f5_WS_LOG.offset() + 0, 4, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f5_WS_LOG.storage(), f5_WS_LOG.offset() + 4, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f5_WS_LOG.storage(), f5_WS_LOG.offset() + 7, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f5_WS_LOG.storage(), f5_WS_LOG.offset() + 10, 1, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f5_WS_LOG.storage(), f5_WS_LOG.offset() + 11, 1, false), CS);
        return 2;
    }

}
