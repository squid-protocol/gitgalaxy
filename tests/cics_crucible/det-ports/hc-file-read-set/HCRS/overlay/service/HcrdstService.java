// gitgalaxy-det-port: COBOL HCRDST (HCRDST.cbl), translated by rule, statement for statement
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
 * HCRDST: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 77, translated 77, holes 0.
 */
@Service
public class HcrdstService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D1 = new BigDecimal("1");
    private static final BigDecimal D5 = new BigDecimal("5");
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
    private static final byte[] IMAGE_s_WS_KEY = Base64.getDecoder().decode(String.join("",
            "ICAgIA=="));
    private static final byte[] IMAGE_s_WS_N = Base64.getDecoder().decode(String.join("",
            "MA=="));
    private static final byte[] IMAGE_s_WS_DONE = Base64.getDecoder().decode(String.join("",
            "RE9ORSBPSyA="));
    private static final byte[] IMAGE_s_WS_CLOG = Base64.getDecoder().decode(String.join("",
            "ICAgIFI9MDAgUz0wMDAgSz0gICAgIEQ9ICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_LS_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_INPUT = new Storage(IMAGE_s_WS_INPUT.length);
    private final Storage s_WS_INLEN = new Storage(IMAGE_s_WS_INLEN.length);
    private final Storage s_WS_MODE = new Storage(IMAGE_s_WS_MODE.length);
    private final Storage s_WS_RESP = new Storage(IMAGE_s_WS_RESP.length);
    private final Storage s_WS_RESP2 = new Storage(IMAGE_s_WS_RESP2.length);
    private final Storage s_WS_KEY = new Storage(IMAGE_s_WS_KEY.length);
    private final Storage s_WS_N = new Storage(IMAGE_s_WS_N.length);
    private final Storage s_WS_DONE = new Storage(IMAGE_s_WS_DONE.length);
    private final Storage s_WS_CLOG = new Storage(IMAGE_s_WS_CLOG.length);
    private final Storage s_LS_REC = new Storage(IMAGE_s_LS_REC.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_INPUT = Field.alphanumeric(s_WS_INPUT, 0, 8, false);
    private final Field f2_WS_INLEN = Field.binary(s_WS_INLEN, 0, 4, 0, true, false);
    private final Field f3_WS_MODE = Field.alphanumeric(s_WS_MODE, 0, 1, false);
    private final Field f4_WS_RESP = Field.binary(s_WS_RESP, 0, 8, 0, true, false);
    private final Field f5_WS_RESP2 = Field.binary(s_WS_RESP2, 0, 8, 0, true, false);
    private final Field f6_WS_KEY = Field.alphanumeric(s_WS_KEY, 0, 4, false);
    private final Field f7_WS_N = Field.zoned(s_WS_N, 0, 1, 0, false, false, false);
    private final Field f8_WS_DONE = Field.alphanumeric(s_WS_DONE, 0, 8, false);
    private final Field f9_WS_CLOG = Field.group(s_WS_CLOG, 0, 40);
    private final Field f10_CLOG_TAG = Field.alphanumeric(s_WS_CLOG, 0, 3, false);
    private final Field f12_CLOG_RESP = Field.zoned(s_WS_CLOG, 6, 2, 0, false, false, false);
    private final Field f14_CLOG_RESP2 = Field.zoned(s_WS_CLOG, 11, 3, 0, false, false, false);
    private final Field f16_CLOG_KEY = Field.alphanumeric(s_WS_CLOG, 17, 4, false);
    private final Field f18_CLOG_DATA = Field.alphanumeric(s_WS_CLOG, 24, 16, false);
    private final Field f19_LS_REC = Field.alphanumeric(s_LS_REC, 0, 16, false);
    private final Field f21_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f22_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f23_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f24_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f25_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f28_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f49_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f50_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f52_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

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
            java.util.Map.entry("LOG-W", 7),
            java.util.Map.entry("LOG-R", 6),
            java.util.Map.entry("LOG-D", 5),
            java.util.Map.entry("NOTFND-PARA", 4),
            java.util.Map.entry("BACK-PARA", 3),
            java.util.Map.entry("FWD-PARA", 2),
            java.util.Map.entry("READ-PARA", 1),
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



    public HcrdstService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_INPUT, 0, s_WS_INPUT.bytes, 0, IMAGE_s_WS_INPUT.length);
        System.arraycopy(IMAGE_s_WS_INLEN, 0, s_WS_INLEN.bytes, 0, IMAGE_s_WS_INLEN.length);
        System.arraycopy(IMAGE_s_WS_MODE, 0, s_WS_MODE.bytes, 0, IMAGE_s_WS_MODE.length);
        System.arraycopy(IMAGE_s_WS_RESP, 0, s_WS_RESP.bytes, 0, IMAGE_s_WS_RESP.length);
        System.arraycopy(IMAGE_s_WS_RESP2, 0, s_WS_RESP2.bytes, 0, IMAGE_s_WS_RESP2.length);
        System.arraycopy(IMAGE_s_WS_KEY, 0, s_WS_KEY.bytes, 0, IMAGE_s_WS_KEY.length);
        System.arraycopy(IMAGE_s_WS_N, 0, s_WS_N.bytes, 0, IMAGE_s_WS_N.length);
        System.arraycopy(IMAGE_s_WS_DONE, 0, s_WS_DONE.bytes, 0, IMAGE_s_WS_DONE.length);
        System.arraycopy(IMAGE_s_WS_CLOG, 0, s_WS_CLOG.bytes, 0, IMAGE_s_WS_CLOG.length);
        System.arraycopy(IMAGE_s_LS_REC, 0, s_LS_REC.bytes, 0, IMAGE_s_LS_REC.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 7);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f52_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f23_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f25_EIBTRMID, CS);
            Cobol.store(f24_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f22_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f21_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            Cobol.store(f28_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                perform(0, 7);
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
        region.run(task, "HCRDST", this::runTask);
    }

    public void handleTransaction(String transid, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, null, area);
        region.run(task, "HCRDST", this::runTask);
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
                if (next >= 8) {
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
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** MAIN-PARA. */
    private int p0() {
        // EXEC CICS RECEIVE INTO(WS-INPUT) LENGTH(WS-INLEN) END-EXEC
        CicsTask.Received received1 = task.receive(Cobol.num(f2_WS_INLEN, CS).intValue(), false);
        DetCics.received(f1_WS_INPUT, received1.data(), CS);
        Cobol.store(f2_WS_INLEN, BigDecimal.valueOf(received1.length()), false, CS);
        Cobol.store(f49_EIBRESP, BigDecimal.valueOf(DetCics.resp(received1.resp())), false, CS);
        Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(received1.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(received1.resp())));
            if (to >= 0) return GOTO | to;
        }
        // MOVE WS-INPUT(6:1) TO WS-MODE
        Cobol.move(f1_WS_INPUT.ref(6, Integer.valueOf(1)), f3_WS_MODE, CS);
        // EVALUATE WS-MODE
        if ((Cobol.compare(f3_WS_MODE, "R", CS) == 0)) {
            // PERFORM READ-PARA
            perform(1, 1);
        } else if ((Cobol.compare(f3_WS_MODE, "F", CS) == 0)) {
            // PERFORM FWD-PARA
            perform(2, 2);
        } else if ((Cobol.compare(f3_WS_MODE, "B", CS) == 0)) {
            // PERFORM BACK-PARA
            perform(3, 3);
        } else if ((Cobol.compare(f3_WS_MODE, "N", CS) == 0)) {
            // PERFORM NOTFND-PARA
            perform(4, 4);
        }
        // EXEC CICS SEND TEXT FROM(WS-DONE) LENGTH(8) ERASE END-EXEC
        String text2 = Cobol.text(f8_WS_DONE, CS);
        int[] planned3 = task.planned("SEND-TEXT", "-");
        if (planned3[0] == 0) task.sendText(text2.substring(0, Math.min(text2.length(), 8)), 8, "ERASE");
        Cobol.store(f49_EIBRESP, BigDecimal.valueOf(planned3[0]), false, CS);
        Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(planned3[1]), false, CS);
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

    /** READ-PARA. */
    private int p1() {
        // MOVE 'K030' TO WS-KEY
        Cobol.move("K030", f6_WS_KEY, CS);
        // EXEC CICS READ FILE('HCRS') SET(ADDRESS OF LS-REC) RIDFLD(WS-KEY) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        byte[] rec5 = DetCics.bytes(f6_WS_KEY);
        CicsTask.FileRead<byte[]> read4 = task.read("HCRS".stripTrailing(), () -> store("HCRS".stripTrailing()).find(rec5));
        if (read4.record() != null) {
            DetCics.setBlockAt(task, f19_LS_REC, "READ " + "HCRS".stripTrailing(), read4.record(), false);
        }
        Cobol.store(f49_EIBRESP, BigDecimal.valueOf(read4.resp()), false, CS);
        Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(read4.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(read4.resp()), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(read4.resp2()), false, CS);
        // MOVE 'R1 ' TO CLOG-TAG
        Cobol.move("R1 ", f10_CLOG_TAG, CS);
        // PERFORM LOG-D
        perform(5, 5);
        // MOVE 'K035' TO WS-KEY
        Cobol.move("K035", f6_WS_KEY, CS);
        // EXEC CICS READ FILE('HCRS') SET(ADDRESS OF LS-REC) RIDFLD(WS-KEY) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        byte[] rec7 = DetCics.bytes(f6_WS_KEY);
        CicsTask.FileRead<byte[]> read6 = task.read("HCRS".stripTrailing(), () -> store("HCRS".stripTrailing()).find(rec7));
        if (read6.record() != null) {
            DetCics.setBlockAt(task, f19_LS_REC, "READ " + "HCRS".stripTrailing(), read6.record(), false);
        }
        Cobol.store(f49_EIBRESP, BigDecimal.valueOf(read6.resp()), false, CS);
        Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(read6.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(read6.resp()), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(read6.resp2()), false, CS);
        // MOVE 'R2 ' TO CLOG-TAG
        Cobol.move("R2 ", f10_CLOG_TAG, CS);
        // PERFORM LOG-D
        perform(5, 5);
        // MOVE 'K050' TO WS-KEY
        Cobol.move("K050", f6_WS_KEY, CS);
        // EXEC CICS READ FILE('HCRS') SET(ADDRESS OF LS-REC) RIDFLD(WS-KEY) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        byte[] rec9 = DetCics.bytes(f6_WS_KEY);
        CicsTask.FileRead<byte[]> read8 = task.read("HCRS".stripTrailing(), () -> store("HCRS".stripTrailing()).find(rec9));
        if (read8.record() != null) {
            DetCics.setBlockAt(task, f19_LS_REC, "READ " + "HCRS".stripTrailing(), read8.record(), false);
        }
        Cobol.store(f49_EIBRESP, BigDecimal.valueOf(read8.resp()), false, CS);
        Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(read8.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(read8.resp()), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(read8.resp2()), false, CS);
        // MOVE 'R3 ' TO CLOG-TAG
        Cobol.move("R3 ", f10_CLOG_TAG, CS);
        // PERFORM LOG-D
        perform(5, 5);
        return 2;
    }

    /** FWD-PARA. */
    private int p2() {
        // MOVE 'K015' TO WS-KEY
        Cobol.move("K015", f6_WS_KEY, CS);
        // EXEC CICS STARTBR FILE('HCRS') RIDFLD(WS-KEY) GTEQ RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int resp10 = task.startbr("HCRS".stripTrailing(), new String(DetCics.bytes(f6_WS_KEY), CS), false, () -> store("HCRS".stripTrailing()).keys());
        Cobol.store(f49_EIBRESP, BigDecimal.valueOf(resp10), false, CS);
        Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp10), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        // MOVE 'F0 ' TO CLOG-TAG
        Cobol.move("F0 ", f10_CLOG_TAG, CS);
        // PERFORM LOG-R
        perform(6, 6);
        // PERFORM VARYING WS-N FROM 1 BY 1 UNTIL WS-N > 5
        Cobol.move(D1, f7_WS_N, CS);
        while (!(Cobol.cmpNum(f7_WS_N, CS).compareTo(D5) > 0)) {
            // EXEC CICS READNEXT FILE('HCRS') SET(ADDRESS OF LS-REC) RIDFLD(WS-KEY) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
            CicsTask.Browsed read11 = task.readnext("HCRS".stripTrailing(), new String(DetCics.bytes(f6_WS_KEY), CS));
            if (read11.normal()) {
                DetCics.put(f6_WS_KEY, read11.key().getBytes(CS));
                byte[] rec13 = store("HCRS".stripTrailing()).find(read11.key().getBytes(CS)).orElse(null);
                if (rec13 != null) DetCics.setBlockAt(task, f19_LS_REC, "BROWSE " + "HCRS".stripTrailing(), rec13, true);
            }
            Cobol.store(f49_EIBRESP, BigDecimal.valueOf(read11.resp()), false, CS);
            Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(read11.resp2()), false, CS);
            Cobol.store(f4_WS_RESP, BigDecimal.valueOf(read11.resp()), false, CS);
            Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(read11.resp2()), false, CS);
            // MOVE 'F ' TO CLOG-TAG
            Cobol.move("F  ", f10_CLOG_TAG, CS);
            // MOVE WS-N TO CLOG-TAG(2:1)
            Cobol.move(f7_WS_N, f10_CLOG_TAG.ref(2, Integer.valueOf(1)), CS);
            // PERFORM LOG-D
            perform(5, 5);
            Cobol.store(f7_WS_N, Cobol.receiverNum(f7_WS_N, CS).add(D1), false, CS);
        }
        // EXEC CICS ENDBR FILE('HCRS') RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int resp14 = task.endbr("HCRS".stripTrailing());
        Cobol.store(f49_EIBRESP, BigDecimal.valueOf(resp14), false, CS);
        Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp14), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        // MOVE 'F6 ' TO CLOG-TAG
        Cobol.move("F6 ", f10_CLOG_TAG, CS);
        // PERFORM LOG-R
        perform(6, 6);
        return 3;
    }

    /** BACK-PARA. */
    private int p3() {
        // MOVE 'K040' TO WS-KEY
        Cobol.move("K040", f6_WS_KEY, CS);
        // EXEC CICS STARTBR FILE('HCRS') RIDFLD(WS-KEY) GTEQ RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int resp15 = task.startbr("HCRS".stripTrailing(), new String(DetCics.bytes(f6_WS_KEY), CS), false, () -> store("HCRS".stripTrailing()).keys());
        Cobol.store(f49_EIBRESP, BigDecimal.valueOf(resp15), false, CS);
        Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp15), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        // MOVE 'B0 ' TO CLOG-TAG
        Cobol.move("B0 ", f10_CLOG_TAG, CS);
        // PERFORM LOG-R
        perform(6, 6);
        // PERFORM VARYING WS-N FROM 1 BY 1 UNTIL WS-N > 5
        Cobol.move(D1, f7_WS_N, CS);
        while (!(Cobol.cmpNum(f7_WS_N, CS).compareTo(D5) > 0)) {
            // EXEC CICS READPREV FILE('HCRS') SET(ADDRESS OF LS-REC) RIDFLD(WS-KEY) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
            CicsTask.Browsed read16 = task.readprev("HCRS".stripTrailing(), new String(DetCics.bytes(f6_WS_KEY), CS));
            if (read16.normal()) {
                DetCics.put(f6_WS_KEY, read16.key().getBytes(CS));
                byte[] rec18 = store("HCRS".stripTrailing()).find(read16.key().getBytes(CS)).orElse(null);
                if (rec18 != null) DetCics.setBlockAt(task, f19_LS_REC, "BROWSE " + "HCRS".stripTrailing(), rec18, true);
            }
            Cobol.store(f49_EIBRESP, BigDecimal.valueOf(read16.resp()), false, CS);
            Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(read16.resp2()), false, CS);
            Cobol.store(f4_WS_RESP, BigDecimal.valueOf(read16.resp()), false, CS);
            Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(read16.resp2()), false, CS);
            // MOVE 'B ' TO CLOG-TAG
            Cobol.move("B  ", f10_CLOG_TAG, CS);
            // MOVE WS-N TO CLOG-TAG(2:1)
            Cobol.move(f7_WS_N, f10_CLOG_TAG.ref(2, Integer.valueOf(1)), CS);
            // PERFORM LOG-D
            perform(5, 5);
            Cobol.store(f7_WS_N, Cobol.receiverNum(f7_WS_N, CS).add(D1), false, CS);
        }
        // EXEC CICS ENDBR FILE('HCRS') RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int resp19 = task.endbr("HCRS".stripTrailing());
        Cobol.store(f49_EIBRESP, BigDecimal.valueOf(resp19), false, CS);
        Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp19), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        // MOVE 'B6 ' TO CLOG-TAG
        Cobol.move("B6 ", f10_CLOG_TAG, CS);
        // PERFORM LOG-R
        perform(6, 6);
        return 4;
    }

    /** NOTFND-PARA. */
    private int p4() {
        // MOVE 'K060' TO WS-KEY
        Cobol.move("K060", f6_WS_KEY, CS);
        // EXEC CICS STARTBR FILE('HCRS') RIDFLD(WS-KEY) GTEQ RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int resp20 = task.startbr("HCRS".stripTrailing(), new String(DetCics.bytes(f6_WS_KEY), CS), false, () -> store("HCRS".stripTrailing()).keys());
        Cobol.store(f49_EIBRESP, BigDecimal.valueOf(resp20), false, CS);
        Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp20), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        // MOVE 'N1 ' TO CLOG-TAG
        Cobol.move("N1 ", f10_CLOG_TAG, CS);
        // PERFORM LOG-R
        perform(6, 6);
        // MOVE 'K025' TO WS-KEY
        Cobol.move("K025", f6_WS_KEY, CS);
        // EXEC CICS STARTBR FILE('HCRS') RIDFLD(WS-KEY) EQUAL RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int resp21 = task.startbr("HCRS".stripTrailing(), new String(DetCics.bytes(f6_WS_KEY), CS), true, () -> store("HCRS".stripTrailing()).keys());
        Cobol.store(f49_EIBRESP, BigDecimal.valueOf(resp21), false, CS);
        Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp21), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        // MOVE 'N2 ' TO CLOG-TAG
        Cobol.move("N2 ", f10_CLOG_TAG, CS);
        // PERFORM LOG-R
        perform(6, 6);
        // MOVE 'K030' TO WS-KEY
        Cobol.move("K030", f6_WS_KEY, CS);
        // EXEC CICS STARTBR FILE('HCRS') RIDFLD(WS-KEY) EQUAL RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int resp22 = task.startbr("HCRS".stripTrailing(), new String(DetCics.bytes(f6_WS_KEY), CS), true, () -> store("HCRS".stripTrailing()).keys());
        Cobol.store(f49_EIBRESP, BigDecimal.valueOf(resp22), false, CS);
        Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp22), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        // MOVE 'N3 ' TO CLOG-TAG
        Cobol.move("N3 ", f10_CLOG_TAG, CS);
        // PERFORM LOG-R
        perform(6, 6);
        // EXEC CICS READNEXT FILE('HCRS') SET(ADDRESS OF LS-REC) RIDFLD(WS-KEY) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        CicsTask.Browsed read23 = task.readnext("HCRS".stripTrailing(), new String(DetCics.bytes(f6_WS_KEY), CS));
        if (read23.normal()) {
            DetCics.put(f6_WS_KEY, read23.key().getBytes(CS));
            byte[] rec25 = store("HCRS".stripTrailing()).find(read23.key().getBytes(CS)).orElse(null);
            if (rec25 != null) DetCics.setBlockAt(task, f19_LS_REC, "BROWSE " + "HCRS".stripTrailing(), rec25, true);
        }
        Cobol.store(f49_EIBRESP, BigDecimal.valueOf(read23.resp()), false, CS);
        Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(read23.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(read23.resp()), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(read23.resp2()), false, CS);
        // MOVE 'N4 ' TO CLOG-TAG
        Cobol.move("N4 ", f10_CLOG_TAG, CS);
        // PERFORM LOG-D
        perform(5, 5);
        // EXEC CICS ENDBR FILE('HCRS') RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int resp26 = task.endbr("HCRS".stripTrailing());
        Cobol.store(f49_EIBRESP, BigDecimal.valueOf(resp26), false, CS);
        Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp26), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        // MOVE 'N5 ' TO CLOG-TAG
        Cobol.move("N5 ", f10_CLOG_TAG, CS);
        // PERFORM LOG-R
        perform(6, 6);
        return 5;
    }

    /** LOG-D. */
    private int p5() {
        // MOVE SPACES TO CLOG-DATA
        Cobol.moveFigurative(Figurative.SPACES, f18_CLOG_DATA, CS);
        // MOVE SPACES TO CLOG-KEY
        Cobol.moveFigurative(Figurative.SPACES, f16_CLOG_KEY, CS);
        // IF WS-RESP = 0
        if (Cobol.num(f4_WS_RESP, CS).compareTo(D0) == 0) {
            // MOVE LS-REC TO CLOG-DATA
            Cobol.move(f19_LS_REC, f18_CLOG_DATA, CS);
            // MOVE WS-KEY TO CLOG-KEY
            Cobol.move(f6_WS_KEY, f16_CLOG_KEY, CS);
        }
        // PERFORM LOG-W
        perform(7, 7);
        return 6;
    }

    /** LOG-R. */
    private int p6() {
        // MOVE SPACES TO CLOG-DATA
        Cobol.moveFigurative(Figurative.SPACES, f18_CLOG_DATA, CS);
        // MOVE SPACES TO CLOG-KEY
        Cobol.moveFigurative(Figurative.SPACES, f16_CLOG_KEY, CS);
        // PERFORM LOG-W
        perform(7, 7);
        return 7;
    }

    /** LOG-W. */
    private int p7() {
        // MOVE WS-RESP TO CLOG-RESP
        Cobol.move(f4_WS_RESP, f12_CLOG_RESP, CS);
        // MOVE 0 TO CLOG-RESP2
        Cobol.move(D0, f14_CLOG_RESP2, CS);
        // IF WS-RESP NOT = 0
        if (!(Cobol.num(f4_WS_RESP, CS).compareTo(D0) == 0)) {
            // MOVE WS-RESP2 TO CLOG-RESP2
            Cobol.move(f5_WS_RESP2, f14_CLOG_RESP2, CS);
        }
        // EXEC CICS WRITEQ TS QUEUE('HCLOG') FROM(WS-CLOG) LENGTH(40) END-EXEC
        CicsTask.TsResult ts27 = task.writeqTs("HCLOG".strip(), DetCics.toRegion(DetCics.padded(f9_WS_CLOG, 40, "WRITEQ TS", CS), CS, REGION));
        Cobol.store(f49_EIBRESP, BigDecimal.valueOf(DetCics.resp(ts27.resp())), false, CS);
        Cobol.store(f50_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(ts27.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(ts27.resp())));
            if (to >= 0) return GOTO | to;
        }
        return 8;
    }

}
