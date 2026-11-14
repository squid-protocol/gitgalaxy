// gitgalaxy-det-port: COBOL HCTDEN (HCTDEN.cbl), translated by rule, statement for statement
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
 * HCTDEN: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 52, translated 52, holes 0.
 */
@Service
public class HctdenService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
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
    private static final byte[] IMAGE_s_WS_Q = Base64.getDecoder().decode(String.join("",
            "SENRMQ=="));
    private static final byte[] IMAGE_s_WS_QN = Base64.getDecoder().decode(String.join("",
            "SENOUQ=="));
    private static final byte[] IMAGE_s_WS_TYPE = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_ENABLE = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_RECOV = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_DONE = Base64.getDecoder().decode(String.join("",
            "RE9ORSBPSyA="));
    private static final byte[] IMAGE_s_WS_ILOG = Base64.getDecoder().decode(String.join("",
            "ICAgIFI9MDAgVD0wMDAwMDAwMDAgRT0wMDAwMDAwMDAgVj0wMDAwMDAwMDA="));
    private static final byte[] IMAGE_s_WS_ELOG = Base64.getDecoder().decode(String.join("",
            "ICAgIFI9MDAgRT0wMDAwMDAwMDA="));
    private static final byte[] IMAGE_s_WS_DLOG = Base64.getDecoder().decode(String.join("",
            "ICAgIFI9MDA="));
    private static final byte[] IMAGE_s_WS_FLOG = Base64.getDecoder().decode(String.join("",
            "ICAgIFI9MDAgUjI9MDA="));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_INPUT = new Storage(IMAGE_s_WS_INPUT.length);
    private final Storage s_WS_INLEN = new Storage(IMAGE_s_WS_INLEN.length);
    private final Storage s_WS_MODE = new Storage(IMAGE_s_WS_MODE.length);
    private final Storage s_WS_RESP = new Storage(IMAGE_s_WS_RESP.length);
    private final Storage s_WS_RESP2 = new Storage(IMAGE_s_WS_RESP2.length);
    private final Storage s_WS_Q = new Storage(IMAGE_s_WS_Q.length);
    private final Storage s_WS_QN = new Storage(IMAGE_s_WS_QN.length);
    private final Storage s_WS_TYPE = new Storage(IMAGE_s_WS_TYPE.length);
    private final Storage s_WS_ENABLE = new Storage(IMAGE_s_WS_ENABLE.length);
    private final Storage s_WS_RECOV = new Storage(IMAGE_s_WS_RECOV.length);
    private final Storage s_WS_DONE = new Storage(IMAGE_s_WS_DONE.length);
    private final Storage s_WS_ILOG = new Storage(IMAGE_s_WS_ILOG.length);
    private final Storage s_WS_ELOG = new Storage(IMAGE_s_WS_ELOG.length);
    private final Storage s_WS_DLOG = new Storage(IMAGE_s_WS_DLOG.length);
    private final Storage s_WS_FLOG = new Storage(IMAGE_s_WS_FLOG.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_INPUT = Field.alphanumeric(s_WS_INPUT, 0, 8, false);
    private final Field f2_WS_INLEN = Field.binary(s_WS_INLEN, 0, 4, 0, true, false);
    private final Field f3_WS_MODE = Field.alphanumeric(s_WS_MODE, 0, 1, false);
    private final Field f4_WS_RESP = Field.binary(s_WS_RESP, 0, 8, 0, true, false);
    private final Field f5_WS_RESP2 = Field.binary(s_WS_RESP2, 0, 8, 0, true, false);
    private final Field f6_WS_Q = Field.alphanumeric(s_WS_Q, 0, 4, false);
    private final Field f7_WS_QN = Field.alphanumeric(s_WS_QN, 0, 4, false);
    private final Field f8_WS_TYPE = Field.binary(s_WS_TYPE, 0, 8, 0, true, false);
    private final Field f9_WS_ENABLE = Field.binary(s_WS_ENABLE, 0, 8, 0, true, false);
    private final Field f10_WS_RECOV = Field.binary(s_WS_RECOV, 0, 8, 0, true, false);
    private final Field f11_WS_DONE = Field.alphanumeric(s_WS_DONE, 0, 8, false);
    private final Field f12_WS_ILOG = Field.group(s_WS_ILOG, 0, 44);
    private final Field f13_ILOG_TAG = Field.alphanumeric(s_WS_ILOG, 0, 3, false);
    private final Field f15_ILOG_RESP = Field.zoned(s_WS_ILOG, 6, 2, 0, false, false, false);
    private final Field f17_ILOG_TYPE = Field.zoned(s_WS_ILOG, 11, 9, 0, false, false, false);
    private final Field f19_ILOG_ENABLE = Field.zoned(s_WS_ILOG, 23, 9, 0, false, false, false);
    private final Field f21_ILOG_RECOV = Field.zoned(s_WS_ILOG, 35, 9, 0, false, false, false);
    private final Field f22_WS_ELOG = Field.group(s_WS_ELOG, 0, 20);
    private final Field f23_ELOG_TAG = Field.alphanumeric(s_WS_ELOG, 0, 3, false);
    private final Field f25_ELOG_RESP = Field.zoned(s_WS_ELOG, 6, 2, 0, false, false, false);
    private final Field f27_ELOG_ENABLE = Field.zoned(s_WS_ELOG, 11, 9, 0, false, false, false);
    private final Field f28_WS_DLOG = Field.group(s_WS_DLOG, 0, 8);
    private final Field f29_DLOG_TAG = Field.alphanumeric(s_WS_DLOG, 0, 3, false);
    private final Field f31_DLOG_RESP = Field.zoned(s_WS_DLOG, 6, 2, 0, false, false, false);
    private final Field f32_WS_FLOG = Field.group(s_WS_FLOG, 0, 14);
    private final Field f33_FLOG_TAG = Field.alphanumeric(s_WS_FLOG, 0, 3, false);
    private final Field f35_FLOG_RESP = Field.zoned(s_WS_FLOG, 6, 2, 0, false, false, false);
    private final Field f37_FLOG_RESP2 = Field.zoned(s_WS_FLOG, 12, 2, 0, false, false, false);
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
        if (CicsTask.undefinableFile(name) || task.undefinedInRegion(name)) {
            return DetCics.Store.undefined(CS);
        }
        throw new Hole("CICS file " + name + ": the program names no file the generated project stores");
    }

    private static final java.util.Map<String, Integer> PARAGRAPHS = java.util.Map.ofEntries(
            java.util.Map.entry("LOG-F", 9),
            java.util.Map.entry("LOG-E", 8),
            java.util.Map.entry("LOG-D", 7),
            java.util.Map.entry("INQ-ENABLE", 6),
            java.util.Map.entry("INQ-UNDEFINED", 5),
            java.util.Map.entry("BADCVDA-PARA", 4),
            java.util.Map.entry("UNDEF-PARA", 3),
            java.util.Map.entry("TOGGLE-PARA", 2),
            java.util.Map.entry("INQ-PARA", 1),
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



    public HctdenService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_INPUT, 0, s_WS_INPUT.bytes, 0, IMAGE_s_WS_INPUT.length);
        System.arraycopy(IMAGE_s_WS_INLEN, 0, s_WS_INLEN.bytes, 0, IMAGE_s_WS_INLEN.length);
        System.arraycopy(IMAGE_s_WS_MODE, 0, s_WS_MODE.bytes, 0, IMAGE_s_WS_MODE.length);
        System.arraycopy(IMAGE_s_WS_RESP, 0, s_WS_RESP.bytes, 0, IMAGE_s_WS_RESP.length);
        System.arraycopy(IMAGE_s_WS_RESP2, 0, s_WS_RESP2.bytes, 0, IMAGE_s_WS_RESP2.length);
        System.arraycopy(IMAGE_s_WS_Q, 0, s_WS_Q.bytes, 0, IMAGE_s_WS_Q.length);
        System.arraycopy(IMAGE_s_WS_QN, 0, s_WS_QN.bytes, 0, IMAGE_s_WS_QN.length);
        System.arraycopy(IMAGE_s_WS_TYPE, 0, s_WS_TYPE.bytes, 0, IMAGE_s_WS_TYPE.length);
        System.arraycopy(IMAGE_s_WS_ENABLE, 0, s_WS_ENABLE.bytes, 0, IMAGE_s_WS_ENABLE.length);
        System.arraycopy(IMAGE_s_WS_RECOV, 0, s_WS_RECOV.bytes, 0, IMAGE_s_WS_RECOV.length);
        System.arraycopy(IMAGE_s_WS_DONE, 0, s_WS_DONE.bytes, 0, IMAGE_s_WS_DONE.length);
        System.arraycopy(IMAGE_s_WS_ILOG, 0, s_WS_ILOG.bytes, 0, IMAGE_s_WS_ILOG.length);
        System.arraycopy(IMAGE_s_WS_ELOG, 0, s_WS_ELOG.bytes, 0, IMAGE_s_WS_ELOG.length);
        System.arraycopy(IMAGE_s_WS_DLOG, 0, s_WS_DLOG.bytes, 0, IMAGE_s_WS_DLOG.length);
        System.arraycopy(IMAGE_s_WS_FLOG, 0, s_WS_FLOG.bytes, 0, IMAGE_s_WS_FLOG.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 9);
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
            if (calen == 0 && task.linkArea() != null) {
                calen = cx(task, task.linkArea().length);
            }
            Cobol.store(f46_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                perform(0, 9);
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
        region.run(task, "HCTDEN", this::runTask);
    }

    public void handleTransaction(String transid, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, null, area);
        region.run(task, "HCTDEN", this::runTask);
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
                if (next >= 10) {
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
            case 5: return p5();
            case 6: return p6();
            case 7: return p7();
            case 8: return p8();
            case 9: return p9();
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
        if ((Cobol.compare(f3_WS_MODE, "I", CS) == 0)) {
            // PERFORM INQ-PARA
            perform(1, 1);
        } else if ((Cobol.compare(f3_WS_MODE, "S", CS) == 0)) {
            // PERFORM TOGGLE-PARA
            perform(2, 2);
        } else if ((Cobol.compare(f3_WS_MODE, "U", CS) == 0)) {
            // PERFORM UNDEF-PARA
            perform(3, 3);
        } else if ((Cobol.compare(f3_WS_MODE, "V", CS) == 0)) {
            // PERFORM BADCVDA-PARA
            perform(4, 4);
        }
        // EXEC CICS SEND TEXT FROM(WS-DONE) LENGTH(8) ERASE END-EXEC
        String text2 = Cobol.text(f11_WS_DONE, CS);
        int[] planned3 = task.planned("SEND-TEXT", "-");
        if (planned3[0] == 0) task.sendText(text2.substring(0, Math.min(text2.length(), 8)), 8, "ERASE");
        Cobol.store(f67_EIBRESP, BigDecimal.valueOf(planned3[0]), false, CS);
        Cobol.store(f68_EIBRESP2, BigDecimal.valueOf(planned3[1]), false, CS);
        if (planned3[0] != 0) {
            int to = condition(DetCics.condition(planned3[0]));
            if (to >= 0) return GOTO | to;
        }
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        return 1;
    }

    /** INQ-PARA. */
    private int p1() {
        // EXEC CICS INQUIRE TDQUEUE(WS-Q) TYPE(WS-TYPE) ENABLESTATUS(WS-ENABLE) RECOVSTATUS(WS-RECOV) RESP(WS-RESP) END-EXEC
        int[] tdq4 = task.inquireTdQueue(Cobol.text(f6_WS_Q, CS).strip(), false, true, true, false, true, false);
        if (tdq4[0] == 0) {
            Cobol.store(f8_WS_TYPE, BigDecimal.valueOf(tdq4[3]), false, CS);
            Cobol.store(f9_WS_ENABLE, BigDecimal.valueOf(tdq4[4]), false, CS);
            Cobol.store(f10_WS_RECOV, BigDecimal.valueOf(tdq4[6]), false, CS);
        }
        Cobol.store(f67_EIBRESP, BigDecimal.valueOf(tdq4[0]), false, CS);
        Cobol.store(f68_EIBRESP2, BigDecimal.valueOf(tdq4[1]), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(tdq4[0]), false, CS);
        // MOVE 'I1 ' TO ILOG-TAG
        Cobol.move("I1 ", f13_ILOG_TAG, CS);
        // MOVE WS-RESP TO ILOG-RESP
        Cobol.move(f4_WS_RESP, f15_ILOG_RESP, CS);
        // MOVE WS-TYPE TO ILOG-TYPE
        Cobol.move(f8_WS_TYPE, f17_ILOG_TYPE, CS);
        // MOVE WS-ENABLE TO ILOG-ENABLE
        Cobol.move(f9_WS_ENABLE, f19_ILOG_ENABLE, CS);
        // MOVE WS-RECOV TO ILOG-RECOV
        Cobol.move(f10_WS_RECOV, f21_ILOG_RECOV, CS);
        // EXEC CICS WRITEQ TS QUEUE('HCLOG') FROM(WS-ILOG) LENGTH(44) END-EXEC
        CicsTask.TsResult ts5 = task.writeqTs("HCLOG".strip(), DetCics.toRegion(DetCics.padded(f12_WS_ILOG, 44, "WRITEQ TS", CS), CS, REGION));
        Cobol.store(f67_EIBRESP, BigDecimal.valueOf(DetCics.resp(ts5.resp())), false, CS);
        Cobol.store(f68_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(ts5.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(ts5.resp())));
            if (to >= 0) return GOTO | to;
        }
        // MOVE 'I2 ' TO FLOG-TAG
        Cobol.move("I2 ", f33_FLOG_TAG, CS);
        // PERFORM INQ-UNDEFINED
        perform(5, 5);
        return 2;
    }

    /** TOGGLE-PARA. */
    private int p2() {
        // EXEC CICS SET TDQUEUE(WS-Q) ENABLESTATUS(DFHVALUE(DISABLED)) RESP(WS-RESP) END-EXEC
        int[] tdq6 = task.setTdQueueEnableStatus(Cobol.text(f6_WS_Q, CS).strip(), 24);
        Cobol.store(f67_EIBRESP, BigDecimal.valueOf(tdq6[0]), false, CS);
        Cobol.store(f68_EIBRESP2, BigDecimal.valueOf(tdq6[1]), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(tdq6[0]), false, CS);
        // MOVE 'S1 ' TO DLOG-TAG
        Cobol.move("S1 ", f29_DLOG_TAG, CS);
        // PERFORM LOG-D
        perform(7, 7);
        // PERFORM INQ-ENABLE
        perform(6, 6);
        // MOVE 'S2 ' TO ELOG-TAG
        Cobol.move("S2 ", f23_ELOG_TAG, CS);
        // PERFORM LOG-E
        perform(8, 8);
        // EXEC CICS SET TDQUEUE(WS-Q) ENABLESTATUS(DFHVALUE(ENABLED)) RESP(WS-RESP) END-EXEC
        int[] tdq7 = task.setTdQueueEnableStatus(Cobol.text(f6_WS_Q, CS).strip(), 23);
        Cobol.store(f67_EIBRESP, BigDecimal.valueOf(tdq7[0]), false, CS);
        Cobol.store(f68_EIBRESP2, BigDecimal.valueOf(tdq7[1]), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(tdq7[0]), false, CS);
        // MOVE 'S3 ' TO DLOG-TAG
        Cobol.move("S3 ", f29_DLOG_TAG, CS);
        // PERFORM LOG-D
        perform(7, 7);
        // PERFORM INQ-ENABLE
        perform(6, 6);
        // MOVE 'S4 ' TO ELOG-TAG
        Cobol.move("S4 ", f23_ELOG_TAG, CS);
        // PERFORM LOG-E
        perform(8, 8);
        return 3;
    }

    /** UNDEF-PARA. */
    private int p3() {
        // EXEC CICS SET TDQUEUE(WS-QN) ENABLESTATUS(DFHVALUE(ENABLED)) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int[] tdq8 = task.setTdQueueEnableStatus(Cobol.text(f7_WS_QN, CS).strip(), 23);
        Cobol.store(f67_EIBRESP, BigDecimal.valueOf(tdq8[0]), false, CS);
        Cobol.store(f68_EIBRESP2, BigDecimal.valueOf(tdq8[1]), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(tdq8[0]), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(tdq8[1]), false, CS);
        // MOVE 'U1 ' TO FLOG-TAG
        Cobol.move("U1 ", f33_FLOG_TAG, CS);
        // PERFORM LOG-F
        perform(9, 9);
        return 4;
    }

    /** BADCVDA-PARA. */
    private int p4() {
        // EXEC CICS SET TDQUEUE(WS-Q) ENABLESTATUS(DFHVALUE(OPEN)) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int[] tdq9 = task.setTdQueueEnableStatus(Cobol.text(f6_WS_Q, CS).strip(), 18);
        Cobol.store(f67_EIBRESP, BigDecimal.valueOf(tdq9[0]), false, CS);
        Cobol.store(f68_EIBRESP2, BigDecimal.valueOf(tdq9[1]), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(tdq9[0]), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(tdq9[1]), false, CS);
        // MOVE 'V1 ' TO FLOG-TAG
        Cobol.move("V1 ", f33_FLOG_TAG, CS);
        // PERFORM LOG-F
        perform(9, 9);
        // PERFORM INQ-ENABLE
        perform(6, 6);
        // MOVE 'V2 ' TO ELOG-TAG
        Cobol.move("V2 ", f23_ELOG_TAG, CS);
        // PERFORM LOG-E
        perform(8, 8);
        return 5;
    }

    /** INQ-UNDEFINED. */
    private int p5() {
        // MOVE 0 TO WS-RESP2
        Cobol.move(D0, f5_WS_RESP2, CS);
        // EXEC CICS INQUIRE TDQUEUE(WS-QN) ENABLESTATUS(WS-ENABLE) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int[] tdq10 = task.inquireTdQueue(Cobol.text(f7_WS_QN, CS).strip(), false, false, true);
        if (tdq10[0] == 0) {
            Cobol.store(f9_WS_ENABLE, BigDecimal.valueOf(tdq10[4]), false, CS);
        }
        Cobol.store(f67_EIBRESP, BigDecimal.valueOf(tdq10[0]), false, CS);
        Cobol.store(f68_EIBRESP2, BigDecimal.valueOf(tdq10[1]), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(tdq10[0]), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(tdq10[1]), false, CS);
        // PERFORM LOG-F
        perform(9, 9);
        return 6;
    }

    /** INQ-ENABLE. */
    private int p6() {
        // MOVE 0 TO WS-ENABLE
        Cobol.move(D0, f9_WS_ENABLE, CS);
        // EXEC CICS INQUIRE TDQUEUE(WS-Q) ENABLESTATUS(WS-ENABLE) RESP(WS-RESP) END-EXEC
        int[] tdq11 = task.inquireTdQueue(Cobol.text(f6_WS_Q, CS).strip(), false, false, true);
        if (tdq11[0] == 0) {
            Cobol.store(f9_WS_ENABLE, BigDecimal.valueOf(tdq11[4]), false, CS);
        }
        Cobol.store(f67_EIBRESP, BigDecimal.valueOf(tdq11[0]), false, CS);
        Cobol.store(f68_EIBRESP2, BigDecimal.valueOf(tdq11[1]), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(tdq11[0]), false, CS);
        return 7;
    }

    /** LOG-D. */
    private int p7() {
        // MOVE WS-RESP TO DLOG-RESP
        Cobol.move(f4_WS_RESP, f31_DLOG_RESP, CS);
        // EXEC CICS WRITEQ TS QUEUE('HCLOG') FROM(WS-DLOG) LENGTH(8) END-EXEC
        CicsTask.TsResult ts12 = task.writeqTs("HCLOG".strip(), DetCics.toRegion(DetCics.padded(f28_WS_DLOG, 8, "WRITEQ TS", CS), CS, REGION));
        Cobol.store(f67_EIBRESP, BigDecimal.valueOf(DetCics.resp(ts12.resp())), false, CS);
        Cobol.store(f68_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(ts12.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(ts12.resp())));
            if (to >= 0) return GOTO | to;
        }
        return 8;
    }

    /** LOG-E. */
    private int p8() {
        // MOVE WS-RESP TO ELOG-RESP
        Cobol.move(f4_WS_RESP, f25_ELOG_RESP, CS);
        // MOVE WS-ENABLE TO ELOG-ENABLE
        Cobol.move(f9_WS_ENABLE, f27_ELOG_ENABLE, CS);
        // EXEC CICS WRITEQ TS QUEUE('HCLOG') FROM(WS-ELOG) LENGTH(20) END-EXEC
        CicsTask.TsResult ts13 = task.writeqTs("HCLOG".strip(), DetCics.toRegion(DetCics.padded(f22_WS_ELOG, 20, "WRITEQ TS", CS), CS, REGION));
        Cobol.store(f67_EIBRESP, BigDecimal.valueOf(DetCics.resp(ts13.resp())), false, CS);
        Cobol.store(f68_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(ts13.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(ts13.resp())));
            if (to >= 0) return GOTO | to;
        }
        return 9;
    }

    /** LOG-F. */
    private int p9() {
        // MOVE WS-RESP TO FLOG-RESP
        Cobol.move(f4_WS_RESP, f35_FLOG_RESP, CS);
        // MOVE WS-RESP2 TO FLOG-RESP2
        Cobol.move(f5_WS_RESP2, f37_FLOG_RESP2, CS);
        // EXEC CICS WRITEQ TS QUEUE('HCLOG') FROM(WS-FLOG) LENGTH(14) END-EXEC
        CicsTask.TsResult ts14 = task.writeqTs("HCLOG".strip(), DetCics.toRegion(DetCics.padded(f32_WS_FLOG, 14, "WRITEQ TS", CS), CS, REGION));
        Cobol.store(f67_EIBRESP, BigDecimal.valueOf(DetCics.resp(ts14.resp())), false, CS);
        Cobol.store(f68_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(ts14.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(ts14.resp())));
            if (to >= 0) return GOTO | to;
        }
        return 10;
    }

}
