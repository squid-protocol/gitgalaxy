// gitgalaxy-det-port: COBOL CARCST (CARCST.cbl), translated by rule, statement for statement
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
 * CARCST: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 14, translated 14, holes 0.
 */
@Service
public class CarcstService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D0 = new BigDecimal("0");

    private static final byte[] IMAGE_s_WS_PTR = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAA="));
    private static final byte[] IMAGE_s_WS_LEN = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private static final byte[] IMAGE_s_WS_RESP = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_MODE = Base64.getDecoder().decode(String.join("",
            "IA=="));
    private static final byte[] IMAGE_s_WS_MSG = Base64.getDecoder().decode(String.join("",
            "T1JERVIgMDAwMyBSRUFEWSAgICA="));
    private static final byte[] IMAGE_s_WS_LOG = Base64.getDecoder().decode(String.join("",
            "ICAgIDAwMDAwMDAgICAgICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_LS_IN = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_PTR = new Storage(IMAGE_s_WS_PTR.length);
    private final Storage s_WS_LEN = new Storage(IMAGE_s_WS_LEN.length);
    private final Storage s_WS_RESP = new Storage(IMAGE_s_WS_RESP.length);
    private final Storage s_WS_MODE = new Storage(IMAGE_s_WS_MODE.length);
    private final Storage s_WS_MSG = new Storage(IMAGE_s_WS_MSG.length);
    private final Storage s_WS_LOG = new Storage(IMAGE_s_WS_LOG.length);
    private final Storage s_LS_IN = new Storage(IMAGE_s_LS_IN.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_PTR = Field.group(s_WS_PTR, 0, 8);
    private final Field f2_WS_LEN = Field.binary(s_WS_LEN, 0, 4, 0, true, false);
    private final Field f3_WS_RESP = Field.binary(s_WS_RESP, 0, 8, 0, true, false);
    private final Field f4_WS_MODE = Field.alphanumeric(s_WS_MODE, 0, 1, false);
    private final Field f5_WS_MSG = Field.alphanumeric(s_WS_MSG, 0, 20, false);
    private final Field f6_WS_LOG = Field.group(s_WS_LOG, 0, 31);
    private final Field f7_LG_TAG = Field.alphanumeric(s_WS_LOG, 0, 4, false);
    private final Field f8_LG_RESP = Field.zoned(s_WS_LOG, 4, 3, 0, false, false, false);
    private final Field f9_LG_LEN = Field.zoned(s_WS_LOG, 7, 4, 0, false, false, false);
    private final Field f10_LG_DATA = Field.alphanumeric(s_WS_LOG, 11, 20, false);
    private final Field f11_LS_IN = Field.alphanumeric(s_LS_IN, 0, 80, false);
    private final Field f13_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f14_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f15_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f16_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f17_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f20_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f41_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f42_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f44_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

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



    public CarcstService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        s_WS_PTR.unalias();
        s_WS_LEN.unalias();
        s_WS_RESP.unalias();
        s_WS_MODE.unalias();
        s_WS_MSG.unalias();
        s_WS_LOG.unalias();
        s_LS_IN.unalias();
        s_DFHEIBLK.unalias();
        s_GG_RETURN_CODE.unalias();
        System.arraycopy(IMAGE_s_WS_PTR, 0, s_WS_PTR.bytes, 0, IMAGE_s_WS_PTR.length);
        System.arraycopy(IMAGE_s_WS_LEN, 0, s_WS_LEN.bytes, 0, IMAGE_s_WS_LEN.length);
        System.arraycopy(IMAGE_s_WS_RESP, 0, s_WS_RESP.bytes, 0, IMAGE_s_WS_RESP.length);
        System.arraycopy(IMAGE_s_WS_MODE, 0, s_WS_MODE.bytes, 0, IMAGE_s_WS_MODE.length);
        System.arraycopy(IMAGE_s_WS_MSG, 0, s_WS_MSG.bytes, 0, IMAGE_s_WS_MSG.length);
        System.arraycopy(IMAGE_s_WS_LOG, 0, s_WS_LOG.bytes, 0, IMAGE_s_WS_LOG.length);
        System.arraycopy(IMAGE_s_LS_IN, 0, s_LS_IN.bytes, 0, IMAGE_s_LS_IN.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 0);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f44_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f15_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f17_EIBTRMID, CS);
            Cobol.store(f16_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f14_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f13_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            Cobol.store(f20_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                perform(0, 0);
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
        region.run(task, "CARCST", this::runTask);
    }

    public void handleTransaction(String transid, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, null, area);
        region.run(task, "CARCST", this::runTask);
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
                if (next >= 1) {
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
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** MAIN-PARA. */
    private int p0() {
        // INITIALIZE WS-LOG
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f6_WS_LOG.storage(), f6_WS_LOG.offset() + 0, 4, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f6_WS_LOG.storage(), f6_WS_LOG.offset() + 4, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f6_WS_LOG.storage(), f6_WS_LOG.offset() + 7, 4, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f6_WS_LOG.storage(), f6_WS_LOG.offset() + 11, 20, false), CS);
        // EXEC CICS RECEIVE SET(WS-PTR) LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC
        CicsTask.Received received1 = task.receive(Integer.MAX_VALUE, false);
        DetCics.setBlock(task, f1_WS_PTR, "RECEIVE", received1.data(), CS);
        Cobol.store(f2_WS_LEN, BigDecimal.valueOf(received1.length()), false, CS);
        Cobol.store(f41_EIBRESP, BigDecimal.valueOf(DetCics.resp(received1.resp())), false, CS);
        Cobol.store(f42_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        Cobol.store(f3_WS_RESP, BigDecimal.valueOf(DetCics.resp(received1.resp())), false, CS);
        // MOVE 'RC01' TO LG-TAG
        Cobol.move("RC01", f7_LG_TAG, CS);
        // MOVE WS-RESP TO LG-RESP
        Cobol.move(f3_WS_RESP, f8_LG_RESP, CS);
        // IF WS-RESP = 0
        if (Cobol.num(f3_WS_RESP, CS).compareTo(D0) == 0) {
            // SET ADDRESS OF LS-IN TO WS-PTR
            DetCics.setAddress(task, f11_LS_IN, f1_WS_PTR);
            // MOVE WS-LEN TO LG-LEN
            Cobol.move(f2_WS_LEN, f9_LG_LEN, CS);
            // MOVE LS-IN(1:WS-LEN) TO LG-DATA
            Cobol.move(f11_LS_IN.ref(1, Integer.valueOf(Cobol.num(f2_WS_LEN, CS).intValue())), f10_LG_DATA, CS);
            // MOVE LS-IN(6:1) TO WS-MODE
            Cobol.move(f11_LS_IN.ref(6, Integer.valueOf(1)), f4_WS_MODE, CS);
        }
        // EXEC CICS WRITEQ TS QUEUE('RSLOG') FROM(WS-LOG) END-EXEC
        CicsTask.TsResult ts2 = task.writeqTs("RSLOG".strip(), DetCics.toRegion(DetCics.bytes(f6_WS_LOG, f6_WS_LOG.length()), CS, REGION));
        Cobol.store(f41_EIBRESP, BigDecimal.valueOf(DetCics.resp(ts2.resp())), false, CS);
        Cobol.store(f42_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(ts2.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(ts2.resp())));
            if (to >= 0) return GOTO | to;
        }
        // EVALUATE WS-MODE
        if ((Cobol.compare(f4_WS_MODE, "E", CS) == 0)) {
            // EXEC CICS START TRANSID('CA0E') INTERVAL(0) FROM(WS-MSG) LENGTH(20) END-EXEC
            CicsTask.StartResult start3 = task.startRequest("CA0E".strip()).interval(0).from(DetCics.toRegion(DetCics.startData(f5_WS_MSG, 20), CS, REGION)).issue();
            Cobol.store(f41_EIBRESP, BigDecimal.valueOf(DetCics.resp(start3.resp())), false, CS);
            Cobol.store(f42_EIBRESP2, BigDecimal.valueOf(start3.resp2()), false, CS);
            if (DetCics.resp(start3.resp()) != 0) {
                int to = condition(DetCics.condition(DetCics.resp(start3.resp())));
                if (to >= 0) return GOTO | to;
            }
        } else if ((Cobol.compare(f4_WS_MODE, "N", CS) == 0)) {
            // EXEC CICS START TRANSID('CA0E') INTERVAL(0) END-EXEC
            CicsTask.StartResult start4 = task.startRequest("CA0E".strip()).interval(0).issue();
            Cobol.store(f41_EIBRESP, BigDecimal.valueOf(DetCics.resp(start4.resp())), false, CS);
            Cobol.store(f42_EIBRESP2, BigDecimal.valueOf(start4.resp2()), false, CS);
            if (DetCics.resp(start4.resp()) != 0) {
                int to = condition(DetCics.condition(DetCics.resp(start4.resp())));
                if (to >= 0) return GOTO | to;
            }
        }
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        return 1;
    }

}
