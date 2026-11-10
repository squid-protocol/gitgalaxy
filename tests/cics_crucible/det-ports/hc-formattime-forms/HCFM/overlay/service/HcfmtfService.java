// gitgalaxy-det-port: COBOL HCFMTF (HCFMTF.cbl), translated by rule, statement for statement
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
 * HCFMTF: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 92, translated 92, holes 0.
 */
@Service
public class HcfmtfService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D4070908799999 = new BigDecimal("4070908799999");

    private static final byte[] IMAGE_s_WS_INPUT = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_INLEN = Base64.getDecoder().decode(String.join("",
            "AAg="));
    private static final byte[] IMAGE_s_WS_MODE = Base64.getDecoder().decode(String.join("",
            "IA=="));
    private static final byte[] IMAGE_s_WS_ABS = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAw="));
    private static final byte[] IMAGE_s_WS_DATE = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_TIME = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_BIN = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_NUM = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDA="));
    private static final byte[] IMAGE_s_WS_DONE = Base64.getDecoder().decode(String.join("",
            "RE9ORSBPSyA="));
    private static final byte[] IMAGE_s_WS_LOG = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_INPUT = new Storage(IMAGE_s_WS_INPUT.length);
    private final Storage s_WS_INLEN = new Storage(IMAGE_s_WS_INLEN.length);
    private final Storage s_WS_MODE = new Storage(IMAGE_s_WS_MODE.length);
    private final Storage s_WS_ABS = new Storage(IMAGE_s_WS_ABS.length);
    private final Storage s_WS_DATE = new Storage(IMAGE_s_WS_DATE.length);
    private final Storage s_WS_TIME = new Storage(IMAGE_s_WS_TIME.length);
    private final Storage s_WS_BIN = new Storage(IMAGE_s_WS_BIN.length);
    private final Storage s_WS_NUM = new Storage(IMAGE_s_WS_NUM.length);
    private final Storage s_WS_DONE = new Storage(IMAGE_s_WS_DONE.length);
    private final Storage s_WS_LOG = new Storage(IMAGE_s_WS_LOG.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_INPUT = Field.alphanumeric(s_WS_INPUT, 0, 8, false);
    private final Field f2_WS_INLEN = Field.binary(s_WS_INLEN, 0, 4, 0, true, false);
    private final Field f3_WS_MODE = Field.alphanumeric(s_WS_MODE, 0, 1, false);
    private final Field f4_WS_ABS = Field.packed(s_WS_ABS, 0, 15, 0, true);
    private final Field f5_WS_DATE = Field.alphanumeric(s_WS_DATE, 0, 10, false);
    private final Field f6_WS_TIME = Field.alphanumeric(s_WS_TIME, 0, 8, false);
    private final Field f7_WS_BIN = Field.binary(s_WS_BIN, 0, 8, 0, true, false);
    private final Field f8_WS_NUM = Field.zoned(s_WS_NUM, 0, 8, 0, false, false, false);
    private final Field f9_WS_DONE = Field.alphanumeric(s_WS_DONE, 0, 8, false);
    private final Field f10_WS_LOG = Field.group(s_WS_LOG, 0, 13);
    private final Field f11_LOG_TAG = Field.alphanumeric(s_WS_LOG, 0, 2, false);
    private final Field f13_LOG_VAL = Field.alphanumeric(s_WS_LOG, 3, 10, false);
    private final Field f15_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f16_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f17_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f18_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f19_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f22_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f43_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f44_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f46_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

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
            java.util.Map.entry("LOG-WRITE", 8),
            java.util.Map.entry("LOG-BIN", 7),
            java.util.Map.entry("LOG-TIME", 6),
            java.util.Map.entry("LOG-DATE", 5),
            java.util.Map.entry("BIN-PARA", 4),
            java.util.Map.entry("LEAP-PARA", 3),
            java.util.Map.entry("TIME-PARA", 2),
            java.util.Map.entry("DATE-PARA", 1),
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



    public HcfmtfService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_INPUT, 0, s_WS_INPUT.bytes, 0, IMAGE_s_WS_INPUT.length);
        System.arraycopy(IMAGE_s_WS_INLEN, 0, s_WS_INLEN.bytes, 0, IMAGE_s_WS_INLEN.length);
        System.arraycopy(IMAGE_s_WS_MODE, 0, s_WS_MODE.bytes, 0, IMAGE_s_WS_MODE.length);
        System.arraycopy(IMAGE_s_WS_ABS, 0, s_WS_ABS.bytes, 0, IMAGE_s_WS_ABS.length);
        System.arraycopy(IMAGE_s_WS_DATE, 0, s_WS_DATE.bytes, 0, IMAGE_s_WS_DATE.length);
        System.arraycopy(IMAGE_s_WS_TIME, 0, s_WS_TIME.bytes, 0, IMAGE_s_WS_TIME.length);
        System.arraycopy(IMAGE_s_WS_BIN, 0, s_WS_BIN.bytes, 0, IMAGE_s_WS_BIN.length);
        System.arraycopy(IMAGE_s_WS_NUM, 0, s_WS_NUM.bytes, 0, IMAGE_s_WS_NUM.length);
        System.arraycopy(IMAGE_s_WS_DONE, 0, s_WS_DONE.bytes, 0, IMAGE_s_WS_DONE.length);
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
            perform(0, 8);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f46_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f17_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f19_EIBTRMID, CS);
            Cobol.store(f18_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f16_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f15_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (calen == 0 && task.linkArea() != null) {
                calen = cx(task, task.linkArea().length);
            }
            Cobol.store(f22_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                perform(0, 8);
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
        region.run(task, "HCFMTF", this::runTask);
    }

    public void handleTransaction(String transid, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, null, area);
        region.run(task, "HCFMTF", this::runTask);
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
                if (next >= 9) {
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
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** MAIN-PARA. */
    private int p0() {
        // EXEC CICS RECEIVE INTO(WS-INPUT) LENGTH(WS-INLEN) END-EXEC
        CicsTask.Received received1 = task.receive(Cobol.num(f2_WS_INLEN, CS).intValue(), false);
        DetCics.received(f1_WS_INPUT, received1.data(), CS);
        Cobol.store(f2_WS_INLEN, BigDecimal.valueOf(received1.length()), false, CS);
        Cobol.store(f43_EIBRESP, BigDecimal.valueOf(DetCics.resp(received1.resp())), false, CS);
        Cobol.store(f44_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(received1.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(received1.resp())));
            if (to >= 0) return GOTO | to;
        }
        // MOVE WS-INPUT(6:1) TO WS-MODE
        Cobol.move(f1_WS_INPUT.ref(6, Integer.valueOf(1)), f3_WS_MODE, CS);
        // EVALUATE WS-MODE
        if ((Cobol.compare(f3_WS_MODE, "D", CS) == 0)) {
            // PERFORM DATE-PARA
            perform(1, 1);
        } else if ((Cobol.compare(f3_WS_MODE, "T", CS) == 0)) {
            // PERFORM TIME-PARA
            perform(2, 2);
        } else if ((Cobol.compare(f3_WS_MODE, "L", CS) == 0)) {
            // PERFORM LEAP-PARA
            perform(3, 3);
        }
        // EXEC CICS SEND TEXT FROM(WS-DONE) LENGTH(8) ERASE END-EXEC
        String text2 = Cobol.text(f9_WS_DONE, CS);
        int[] planned3 = task.planned("SEND-TEXT", "-");
        if (planned3[0] == 0) task.sendText(text2.substring(0, Math.min(text2.length(), 8)), 8, "ERASE");
        Cobol.store(f43_EIBRESP, BigDecimal.valueOf(planned3[0]), false, CS);
        Cobol.store(f44_EIBRESP2, BigDecimal.valueOf(planned3[1]), false, CS);
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

    /** DATE-PARA. */
    private int p1() {
        // EXEC CICS ASKTIME ABSTIME(WS-ABS) END-EXEC
        Cobol.store(f4_WS_ABS, BigDecimal.valueOf(task.asktime()), false, CS);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) YYYYMMDD(WS-DATE) END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f4_WS_ABS, CS).longValue(), "YYYYMMDD", ""), f5_WS_DATE, CS);
        // MOVE 'D1' TO LOG-TAG
        Cobol.move("D1", f11_LOG_TAG, CS);
        // PERFORM LOG-DATE
        perform(5, 5);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) MMDDYYYY(WS-DATE) DATESEP('-') END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f4_WS_ABS, CS).longValue(), "MMDDYYYY", "-"), f5_WS_DATE, CS);
        // MOVE 'D2' TO LOG-TAG
        Cobol.move("D2", f11_LOG_TAG, CS);
        // PERFORM LOG-DATE
        perform(5, 5);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) DDMMYYYY(WS-DATE) DATESEP('.') END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f4_WS_ABS, CS).longValue(), "DDMMYYYY", "."), f5_WS_DATE, CS);
        // MOVE 'D3' TO LOG-TAG
        Cobol.move("D3", f11_LOG_TAG, CS);
        // PERFORM LOG-DATE
        perform(5, 5);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) YYMMDD(WS-DATE) DATESEP END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f4_WS_ABS, CS).longValue(), "YYMMDD", "/"), f5_WS_DATE, CS);
        // MOVE 'D4' TO LOG-TAG
        Cobol.move("D4", f11_LOG_TAG, CS);
        // PERFORM LOG-DATE
        perform(5, 5);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) MMDDYY(WS-DATE) END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f4_WS_ABS, CS).longValue(), "MMDDYY", ""), f5_WS_DATE, CS);
        // MOVE 'D5' TO LOG-TAG
        Cobol.move("D5", f11_LOG_TAG, CS);
        // PERFORM LOG-DATE
        perform(5, 5);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) DDMMYY(WS-DATE) DATESEP('-') END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f4_WS_ABS, CS).longValue(), "DDMMYY", "-"), f5_WS_DATE, CS);
        // MOVE 'D6' TO LOG-TAG
        Cobol.move("D6", f11_LOG_TAG, CS);
        // PERFORM LOG-DATE
        perform(5, 5);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) YYDDD(WS-DATE) END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f4_WS_ABS, CS).longValue(), "YYDDD", ""), f5_WS_DATE, CS);
        // MOVE 'D7' TO LOG-TAG
        Cobol.move("D7", f11_LOG_TAG, CS);
        // PERFORM LOG-DATE
        perform(5, 5);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) YYYYDDD(WS-DATE) DATESEP('-') END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f4_WS_ABS, CS).longValue(), "YYYYDDD", "-"), f5_WS_DATE, CS);
        // MOVE 'D8' TO LOG-TAG
        Cobol.move("D8", f11_LOG_TAG, CS);
        // PERFORM LOG-DATE
        perform(5, 5);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) YYDDMM(WS-DATE) DATESEP('.') END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f4_WS_ABS, CS).longValue(), "YYDDMM", "."), f5_WS_DATE, CS);
        // MOVE 'D9' TO LOG-TAG
        Cobol.move("D9", f11_LOG_TAG, CS);
        // PERFORM LOG-DATE
        perform(5, 5);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) YYYYDDMM(WS-DATE) END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f4_WS_ABS, CS).longValue(), "YYYYDDMM", ""), f5_WS_DATE, CS);
        // MOVE 'DA' TO LOG-TAG
        Cobol.move("DA", f11_LOG_TAG, CS);
        // PERFORM LOG-DATE
        perform(5, 5);
        return 2;
    }

    /** TIME-PARA. */
    private int p2() {
        // EXEC CICS ASKTIME ABSTIME(WS-ABS) END-EXEC
        Cobol.store(f4_WS_ABS, BigDecimal.valueOf(task.asktime()), false, CS);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) TIME(WS-TIME) END-EXEC
        Cobol.move(CicsTask.formatTime(Cobol.num(f4_WS_ABS, CS).longValue(), ""), f6_WS_TIME, CS);
        // MOVE 'T1' TO LOG-TAG
        Cobol.move("T1", f11_LOG_TAG, CS);
        // PERFORM LOG-TIME
        perform(6, 6);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) TIME(WS-TIME) TIMESEP('.') END-EXEC
        Cobol.move(CicsTask.formatTime(Cobol.num(f4_WS_ABS, CS).longValue(), "."), f6_WS_TIME, CS);
        // MOVE 'T2' TO LOG-TAG
        Cobol.move("T2", f11_LOG_TAG, CS);
        // PERFORM LOG-TIME
        perform(6, 6);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) TIME(WS-TIME) TIMESEP END-EXEC
        Cobol.move(CicsTask.formatTime(Cobol.num(f4_WS_ABS, CS).longValue(), ":"), f6_WS_TIME, CS);
        // MOVE 'T3' TO LOG-TAG
        Cobol.move("T3", f11_LOG_TAG, CS);
        // PERFORM LOG-TIME
        perform(6, 6);
        // PERFORM BIN-PARA
        perform(4, 4);
        return 3;
    }

    /** LEAP-PARA. */
    private int p3() {
        // MOVE 4070908799999 TO WS-ABS
        Cobol.move(D4070908799999, f4_WS_ABS, CS);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) MMDDYYYY(WS-DATE) DATESEP('/') END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f4_WS_ABS, CS).longValue(), "MMDDYYYY", "/"), f5_WS_DATE, CS);
        // MOVE 'L1' TO LOG-TAG
        Cobol.move("L1", f11_LOG_TAG, CS);
        // PERFORM LOG-DATE
        perform(5, 5);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) YYYYDDD(WS-DATE) END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f4_WS_ABS, CS).longValue(), "YYYYDDD", ""), f5_WS_DATE, CS);
        // MOVE 'L2' TO LOG-TAG
        Cobol.move("L2", f11_LOG_TAG, CS);
        // PERFORM LOG-DATE
        perform(5, 5);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) YYDDD(WS-DATE) DATESEP('-') END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f4_WS_ABS, CS).longValue(), "YYDDD", "-"), f5_WS_DATE, CS);
        // MOVE 'L3' TO LOG-TAG
        Cobol.move("L3", f11_LOG_TAG, CS);
        // PERFORM LOG-DATE
        perform(5, 5);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) TIME(WS-TIME) TIMESEP(':') END-EXEC
        Cobol.move(CicsTask.formatTime(Cobol.num(f4_WS_ABS, CS).longValue(), ":"), f6_WS_TIME, CS);
        // MOVE 'L4' TO LOG-TAG
        Cobol.move("L4", f11_LOG_TAG, CS);
        // PERFORM LOG-TIME
        perform(6, 6);
        // PERFORM BIN-PARA
        perform(4, 4);
        return 4;
    }

    /** BIN-PARA. */
    private int p4() {
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) DAYCOUNT(WS-BIN) END-EXEC
        Cobol.store(f7_WS_BIN, BigDecimal.valueOf(CicsTask.formatNumber(Cobol.num(f4_WS_ABS, CS).longValue(), "DAYCOUNT")), false, CS);
        // MOVE 'N1' TO LOG-TAG
        Cobol.move("N1", f11_LOG_TAG, CS);
        // PERFORM LOG-BIN
        perform(7, 7);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) DAYOFWEEK(WS-BIN) END-EXEC
        Cobol.store(f7_WS_BIN, BigDecimal.valueOf(CicsTask.formatNumber(Cobol.num(f4_WS_ABS, CS).longValue(), "DAYOFWEEK")), false, CS);
        // MOVE 'N2' TO LOG-TAG
        Cobol.move("N2", f11_LOG_TAG, CS);
        // PERFORM LOG-BIN
        perform(7, 7);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) DAYOFMONTH(WS-BIN) END-EXEC
        Cobol.store(f7_WS_BIN, BigDecimal.valueOf(CicsTask.formatNumber(Cobol.num(f4_WS_ABS, CS).longValue(), "DAYOFMONTH")), false, CS);
        // MOVE 'N3' TO LOG-TAG
        Cobol.move("N3", f11_LOG_TAG, CS);
        // PERFORM LOG-BIN
        perform(7, 7);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) MONTHOFYEAR(WS-BIN) END-EXEC
        Cobol.store(f7_WS_BIN, BigDecimal.valueOf(CicsTask.formatNumber(Cobol.num(f4_WS_ABS, CS).longValue(), "MONTHOFYEAR")), false, CS);
        // MOVE 'N4' TO LOG-TAG
        Cobol.move("N4", f11_LOG_TAG, CS);
        // PERFORM LOG-BIN
        perform(7, 7);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) YEAR(WS-BIN) END-EXEC
        Cobol.store(f7_WS_BIN, BigDecimal.valueOf(CicsTask.formatNumber(Cobol.num(f4_WS_ABS, CS).longValue(), "YEAR")), false, CS);
        // MOVE 'N5' TO LOG-TAG
        Cobol.move("N5", f11_LOG_TAG, CS);
        // PERFORM LOG-BIN
        perform(7, 7);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS) MILLISECONDS(WS-BIN) END-EXEC
        Cobol.store(f7_WS_BIN, BigDecimal.valueOf(CicsTask.formatNumber(Cobol.num(f4_WS_ABS, CS).longValue(), "MILLISECONDS")), false, CS);
        // MOVE 'N6' TO LOG-TAG
        Cobol.move("N6", f11_LOG_TAG, CS);
        // PERFORM LOG-BIN
        perform(7, 7);
        return 5;
    }

    /** LOG-DATE. */
    private int p5() {
        // MOVE WS-DATE TO LOG-VAL
        Cobol.move(f5_WS_DATE, f13_LOG_VAL, CS);
        // MOVE SPACES TO WS-DATE
        Cobol.moveFigurative(Figurative.SPACES, f5_WS_DATE, CS);
        // PERFORM LOG-WRITE
        perform(8, 8);
        return 6;
    }

    /** LOG-TIME. */
    private int p6() {
        // MOVE WS-TIME TO LOG-VAL
        Cobol.move(f6_WS_TIME, f13_LOG_VAL, CS);
        // MOVE SPACES TO WS-TIME
        Cobol.moveFigurative(Figurative.SPACES, f6_WS_TIME, CS);
        // PERFORM LOG-WRITE
        perform(8, 8);
        return 7;
    }

    /** LOG-BIN. */
    private int p7() {
        // MOVE WS-BIN TO WS-NUM
        Cobol.move(f7_WS_BIN, f8_WS_NUM, CS);
        // MOVE WS-NUM TO LOG-VAL
        Cobol.move(f8_WS_NUM, f13_LOG_VAL, CS);
        // PERFORM LOG-WRITE
        perform(8, 8);
        return 8;
    }

    /** LOG-WRITE. */
    private int p8() {
        // EXEC CICS WRITEQ TS QUEUE('HCLOG') FROM(WS-LOG) LENGTH(13) END-EXEC
        CicsTask.TsResult ts4 = task.writeqTs("HCLOG".strip(), DetCics.toRegion(DetCics.padded(f10_WS_LOG, 13, "WRITEQ TS", CS), CS, REGION));
        Cobol.store(f43_EIBRESP, BigDecimal.valueOf(DetCics.resp(ts4.resp())), false, CS);
        Cobol.store(f44_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(ts4.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(ts4.resp())));
            if (to >= 0) return GOTO | to;
        }
        return 9;
    }

}
