// gitgalaxy-det-port: COBOL CAGMPT (CAGMPT.cbl), translated by rule, statement for statement
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
 * CAGMPT: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 46, translated 46, holes 0.
 */
@Service
public class CagmptService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D4 = new BigDecimal("4");
    private static final BigDecimal D0 = new BigDecimal("0");

    private static final byte[] IMAGE_s_WS_PTR = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAA="));
    private static final byte[] IMAGE_s_WS_PTR2 = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAA="));
    private static final byte[] IMAGE_s_WS_PSUB = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAA="));
    private static final byte[] IMAGE_s_WS_FILL = Base64.getDecoder().decode(String.join("",
            "Wg=="));
    private static final byte[] IMAGE_s_WS_RESP = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_RESP2 = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_LOG = Base64.getDecoder().decode(String.join("",
            "ICAgIDAwMDAwMCAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_LS_AREA = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_LS_TAIL = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_LS_SUB = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_PTR = new Storage(IMAGE_s_WS_PTR.length);
    private final Storage s_WS_PTR2 = new Storage(IMAGE_s_WS_PTR2.length);
    private final Storage s_WS_PSUB = new Storage(IMAGE_s_WS_PSUB.length);
    private final Storage s_WS_FILL = new Storage(IMAGE_s_WS_FILL.length);
    private final Storage s_WS_RESP = new Storage(IMAGE_s_WS_RESP.length);
    private final Storage s_WS_RESP2 = new Storage(IMAGE_s_WS_RESP2.length);
    private final Storage s_WS_LOG = new Storage(IMAGE_s_WS_LOG.length);
    private final Storage s_LS_AREA = new Storage(IMAGE_s_LS_AREA.length);
    private final Storage s_LS_TAIL = new Storage(IMAGE_s_LS_TAIL.length);
    private final Storage s_LS_SUB = new Storage(IMAGE_s_LS_SUB.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_PTR = Field.group(s_WS_PTR, 0, 8);
    private final Field f2_WS_PTR2 = Field.group(s_WS_PTR2, 0, 8);
    private final Field f4_WS_PSUB = Field.group(s_WS_PSUB, 0, 8);
    private final Field f5_WS_FILL = Field.alphanumeric(s_WS_FILL, 0, 1, false);
    private final Field f6_WS_RESP = Field.binary(s_WS_RESP, 0, 8, 0, true, false);
    private final Field f7_WS_RESP2 = Field.binary(s_WS_RESP2, 0, 8, 0, true, false);
    private final Field f8_WS_LOG = Field.group(s_WS_LOG, 0, 26);
    private final Field f9_LG_TAG = Field.alphanumeric(s_WS_LOG, 0, 4, false);
    private final Field f10_LG_RESP = Field.zoned(s_WS_LOG, 4, 3, 0, false, false, false);
    private final Field f11_LG_RESP2 = Field.zoned(s_WS_LOG, 7, 3, 0, false, false, false);
    private final Field f12_LG_DATA = Field.alphanumeric(s_WS_LOG, 10, 16, false);
    private final Field f13_LS_AREA = Field.group(s_LS_AREA, 0, 16);
    private final Field f14_LS_HEAD = Field.alphanumeric(s_LS_AREA, 0, 4, false);
    private final Field f15_LS_BODY = Field.alphanumeric(s_LS_AREA, 4, 12, false);
    private final Field f16_LS_TAIL = Field.alphanumeric(s_LS_TAIL, 0, 12, false);
    private final Field f17_LS_SUB = Field.alphanumeric(s_LS_SUB, 0, 12, false);
    private final Field f19_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f20_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f21_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f22_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f23_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f26_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f47_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f48_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f50_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

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



    public CagmptService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_PTR, 0, s_WS_PTR.bytes, 0, IMAGE_s_WS_PTR.length);
        System.arraycopy(IMAGE_s_WS_PTR2, 0, s_WS_PTR2.bytes, 0, IMAGE_s_WS_PTR2.length);
        System.arraycopy(IMAGE_s_WS_PSUB, 0, s_WS_PSUB.bytes, 0, IMAGE_s_WS_PSUB.length);
        System.arraycopy(IMAGE_s_WS_FILL, 0, s_WS_FILL.bytes, 0, IMAGE_s_WS_FILL.length);
        System.arraycopy(IMAGE_s_WS_RESP, 0, s_WS_RESP.bytes, 0, IMAGE_s_WS_RESP.length);
        System.arraycopy(IMAGE_s_WS_RESP2, 0, s_WS_RESP2.bytes, 0, IMAGE_s_WS_RESP2.length);
        System.arraycopy(IMAGE_s_WS_LOG, 0, s_WS_LOG.bytes, 0, IMAGE_s_WS_LOG.length);
        System.arraycopy(IMAGE_s_LS_AREA, 0, s_LS_AREA.bytes, 0, IMAGE_s_LS_AREA.length);
        System.arraycopy(IMAGE_s_LS_TAIL, 0, s_LS_TAIL.bytes, 0, IMAGE_s_LS_TAIL.length);
        System.arraycopy(IMAGE_s_LS_SUB, 0, s_LS_SUB.bytes, 0, IMAGE_s_LS_SUB.length);
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
        return Cobol.num(f50_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f21_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f23_EIBTRMID, CS);
            Cobol.store(f22_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f20_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f19_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            Cobol.store(f26_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
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
        region.run(task, "CAGMPT", this::runTask);
    }

    public void handleTransaction(String transid, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, null, area);
        region.run(task, "CAGMPT", this::runTask);
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
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f8_WS_LOG.storage(), f8_WS_LOG.offset() + 0, 4, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f8_WS_LOG.storage(), f8_WS_LOG.offset() + 4, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f8_WS_LOG.storage(), f8_WS_LOG.offset() + 7, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f8_WS_LOG.storage(), f8_WS_LOG.offset() + 10, 16, false), CS);
        // EXEC CICS GETMAIN SET(WS-PTR) FLENGTH(16) INITIMG(WS-FILL) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int[] storage1 = DetCics.getmain(task, f1_WS_PTR, 16, false, f5_WS_FILL);
        Cobol.store(f47_EIBRESP, BigDecimal.valueOf(storage1[0]), false, CS);
        Cobol.store(f48_EIBRESP2, BigDecimal.valueOf(storage1[1]), false, CS);
        Cobol.store(f6_WS_RESP, BigDecimal.valueOf(storage1[0]), false, CS);
        Cobol.store(f7_WS_RESP2, BigDecimal.valueOf(storage1[1]), false, CS);
        // MOVE 'GM01' TO LG-TAG
        Cobol.move("GM01", f9_LG_TAG, CS);
        // PERFORM LOG-RESP
        perform(1, 1);
        // SET ADDRESS OF LS-AREA TO WS-PTR
        DetCics.setAddress(task, f13_LS_AREA, f1_WS_PTR);
        // MOVE 'GM02' TO LG-TAG
        Cobol.move("GM02", f9_LG_TAG, CS);
        // MOVE LS-AREA TO LG-DATA
        Cobol.move(f13_LS_AREA, f12_LG_DATA, CS);
        // PERFORM LOG-RESP
        perform(1, 1);
        // MOVE 'HEAD' TO LS-HEAD
        Cobol.move("HEAD", f14_LS_HEAD, CS);
        // MOVE 'ABCDEFGHIJKL' TO LS-BODY
        Cobol.move("ABCDEFGHIJKL", f15_LS_BODY, CS);
        // MOVE 'GM03' TO LG-TAG
        Cobol.move("GM03", f9_LG_TAG, CS);
        // MOVE LS-AREA TO LG-DATA
        Cobol.move(f13_LS_AREA, f12_LG_DATA, CS);
        // PERFORM LOG-RESP
        perform(1, 1);
        // SET WS-PTR2 TO WS-PTR
        Cobol.move(f1_WS_PTR, f2_WS_PTR2, CS);
        // ADD 4 TO WS-PTR2-N
        DetCics.advancePointer(task, f2_WS_PTR2, (D4).longValueExact());
        // SET ADDRESS OF LS-TAIL TO WS-PTR2
        DetCics.setAddress(task, f16_LS_TAIL, f2_WS_PTR2);
        // MOVE 'GM04' TO LG-TAG
        Cobol.move("GM04", f9_LG_TAG, CS);
        // MOVE LS-TAIL TO LG-DATA
        Cobol.move(f16_LS_TAIL, f12_LG_DATA, CS);
        // PERFORM LOG-RESP
        perform(1, 1);
        // SET WS-PSUB TO ADDRESS OF LS-BODY
        DetCics.setPointerToItem(task, f4_WS_PSUB, f15_LS_BODY);
        // SET ADDRESS OF LS-SUB TO WS-PSUB
        DetCics.setAddress(task, f17_LS_SUB, f4_WS_PSUB);
        // MOVE 'GM05' TO LG-TAG
        Cobol.move("GM05", f9_LG_TAG, CS);
        // MOVE LS-SUB TO LG-DATA
        Cobol.move(f17_LS_SUB, f12_LG_DATA, CS);
        // PERFORM LOG-RESP
        perform(1, 1);
        // MOVE 'GM06' TO LG-TAG
        Cobol.move("GM06", f9_LG_TAG, CS);
        // MOVE 'EQ=N NEBASE=N' TO LG-DATA
        Cobol.move("EQ=N NEBASE=N", f12_LG_DATA, CS);
        // IF WS-PSUB = WS-PTR2
        if (DetCics.samePointer(task, f4_WS_PSUB, f2_WS_PTR2)) {
            // MOVE 'Y' TO LG-DATA(4:1)
            Cobol.move("Y", f12_LG_DATA.ref(4, Integer.valueOf(1)), CS);
        }
        // IF WS-PSUB NOT = WS-PTR
        if (!(DetCics.samePointer(task, f4_WS_PSUB, f1_WS_PTR))) {
            // MOVE 'Y' TO LG-DATA(13:1)
            Cobol.move("Y", f12_LG_DATA.ref(13, Integer.valueOf(1)), CS);
        }
        // PERFORM LOG-RESP
        perform(1, 1);
        // MOVE 'MNOPQRSTUVWX' TO LS-SUB
        Cobol.move("MNOPQRSTUVWX", f17_LS_SUB, CS);
        // MOVE 'GM07' TO LG-TAG
        Cobol.move("GM07", f9_LG_TAG, CS);
        // MOVE LS-AREA TO LG-DATA
        Cobol.move(f13_LS_AREA, f12_LG_DATA, CS);
        // PERFORM LOG-RESP
        perform(1, 1);
        // EXEC CICS FREEMAIN DATA(LS-AREA) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int[] storage2 = DetCics.freemainData(task, f13_LS_AREA);
        Cobol.store(f47_EIBRESP, BigDecimal.valueOf(storage2[0]), false, CS);
        Cobol.store(f48_EIBRESP2, BigDecimal.valueOf(storage2[1]), false, CS);
        Cobol.store(f6_WS_RESP, BigDecimal.valueOf(storage2[0]), false, CS);
        Cobol.store(f7_WS_RESP2, BigDecimal.valueOf(storage2[1]), false, CS);
        // MOVE 'FM01' TO LG-TAG
        Cobol.move("FM01", f9_LG_TAG, CS);
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
        // IF WS-RESP = 0
        if (Cobol.num(f6_WS_RESP, CS).compareTo(D0) == 0) {
            // MOVE 0 TO LG-RESP
            Cobol.move(D0, f10_LG_RESP, CS);
            // MOVE 0 TO LG-RESP2
            Cobol.move(D0, f11_LG_RESP2, CS);
        } else {
            // MOVE WS-RESP TO LG-RESP
            Cobol.move(f6_WS_RESP, f10_LG_RESP, CS);
            // MOVE WS-RESP2 TO LG-RESP2
            Cobol.move(f7_WS_RESP2, f11_LG_RESP2, CS);
        }
        // EXEC CICS WRITEQ TS QUEUE('GMLOG') FROM(WS-LOG) END-EXEC
        CicsTask.TsResult ts3 = task.writeqTs("GMLOG".strip(), DetCics.toRegion(DetCics.bytes(f8_WS_LOG, f8_WS_LOG.length()), CS, REGION));
        Cobol.store(f47_EIBRESP, BigDecimal.valueOf(DetCics.resp(ts3.resp())), false, CS);
        Cobol.store(f48_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(ts3.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(ts3.resp())));
            if (to >= 0) return GOTO | to;
        }
        // INITIALIZE WS-LOG
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f8_WS_LOG.storage(), f8_WS_LOG.offset() + 0, 4, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f8_WS_LOG.storage(), f8_WS_LOG.offset() + 4, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f8_WS_LOG.storage(), f8_WS_LOG.offset() + 7, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f8_WS_LOG.storage(), f8_WS_LOG.offset() + 10, 16, false), CS);
        return 2;
    }

}
