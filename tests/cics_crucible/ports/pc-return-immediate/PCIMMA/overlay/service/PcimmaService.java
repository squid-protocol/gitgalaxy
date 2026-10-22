// gitgalaxy-det-port: COBOL PCIMMA (PCIMMA.cbl), translated by rule, statement for statement
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
import com.gitgalaxy.modernized.dto.contract.*;
import com.gitgalaxy.modernized.entity.vsam.*;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * PCIMMA: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 34, translated 34, holes 0.
 */
@Service
public class PcimmaService {

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
    private static final byte[] IMAGE_s_WS_R_D = Base64.getDecoder().decode(String.join("",
            "MDA="));
    private static final byte[] IMAGE_s_WS_CA = Base64.getDecoder().decode(String.join("",
            "MU1FTlUtQTE="));
    private static final byte[] IMAGE_s_WS_ALOG = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICBSPTAw"));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_INPUT = new Storage(IMAGE_s_WS_INPUT.length);
    private final Storage s_WS_INLEN = new Storage(IMAGE_s_WS_INLEN.length);
    private final Storage s_WS_MODE = new Storage(IMAGE_s_WS_MODE.length);
    private final Storage s_WS_RESP = new Storage(IMAGE_s_WS_RESP.length);
    private final Storage s_WS_RESP2 = new Storage(IMAGE_s_WS_RESP2.length);
    private final Storage s_WS_R_D = new Storage(IMAGE_s_WS_R_D.length);
    private final Storage s_WS_CA = new Storage(IMAGE_s_WS_CA.length);
    private final Storage s_WS_ALOG = new Storage(IMAGE_s_WS_ALOG.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_INPUT = Field.alphanumeric(s_WS_INPUT, 0, 8, false);
    private final Field f2_WS_INLEN = Field.binary(s_WS_INLEN, 0, 4, 0, true, false);
    private final Field f3_WS_MODE = Field.alphanumeric(s_WS_MODE, 0, 1, false);
    private final Field f4_WS_RESP = Field.binary(s_WS_RESP, 0, 8, 0, true, false);
    private final Field f5_WS_RESP2 = Field.binary(s_WS_RESP2, 0, 8, 0, true, false);
    private final Field f7_WS_CA = Field.group(s_WS_CA, 0, 8);
    private final Field f9_CA_TEXT = Field.alphanumeric(s_WS_CA, 1, 7, false);
    private final Field f10_WS_ALOG = Field.group(s_WS_ALOG, 0, 15);
    private final Field f11_ALOG_TAG = Field.alphanumeric(s_WS_ALOG, 0, 3, false);
    private final Field f12_ALOG_TEXT = Field.alphanumeric(s_WS_ALOG, 3, 7, false);
    private final Field f14_ALOG_RESP = Field.zoned(s_WS_ALOG, 13, 2, 0, false, false, false);
    private final Field f16_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f17_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f18_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f19_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f20_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f23_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f44_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f45_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f47_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

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
            java.util.Map.entry("LOG-A", 5),
            java.util.Map.entry("START-PARA", 4),
            java.util.Map.entry("NOCA-PARA", 3),
            java.util.Map.entry("LINK-PARA", 2),
            java.util.Map.entry("IMMEDIATE-PARA", 1),
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

    private void in_PcimmaWsCa(PcimmaWsCa d, Storage s, int base) {
        if (d == null) {
            return;
        }
        Cobol.move(d.getCaStage() == null ? "" : d.getCaStage(), Field.alphanumeric(s, base + 0, 1, false), CS);
        Cobol.move(d.getCaText() == null ? "" : d.getCaText(), Field.alphanumeric(s, base + 1, 7, false), CS);
    }

    private void fill_PcimmaWsCa(PcimmaWsCa d, Storage s, int base) {
        d.setCaStage(Cobol.text(Field.alphanumeric(s, base + 0, 1, false), CS));
        d.setCaText(Cobol.text(Field.alphanumeric(s, base + 1, 7, false), CS));
    }

    private PcimmaWsCa out_PcimmaWsCa(Storage s, int base) {
        PcimmaWsCa d = new PcimmaWsCa();
        fill_PcimmaWsCa(d, s, base);
        return d;
    }

    private void in_PcimmlDfhcommarea(PcimmlDfhcommarea d, Storage s, int base) {
        if (d == null) {
            return;
        }
        Cobol.move(d.getCaStage() == null ? "" : d.getCaStage(), Field.alphanumeric(s, base + 0, 1, false), CS);
        Cobol.move(d.getCaText() == null ? "" : d.getCaText(), Field.alphanumeric(s, base + 1, 7, false), CS);
    }

    private void fill_PcimmlDfhcommarea(PcimmlDfhcommarea d, Storage s, int base) {
        d.setCaStage(Cobol.text(Field.alphanumeric(s, base + 0, 1, false), CS));
        d.setCaText(Cobol.text(Field.alphanumeric(s, base + 1, 7, false), CS));
    }

    private PcimmlDfhcommarea out_PcimmlDfhcommarea(Storage s, int base) {
        PcimmlDfhcommarea d = new PcimmlDfhcommarea();
        fill_PcimmlDfhcommarea(d, s, base);
        return d;
    }



    public PcimmaService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_INPUT, 0, s_WS_INPUT.bytes, 0, IMAGE_s_WS_INPUT.length);
        System.arraycopy(IMAGE_s_WS_INLEN, 0, s_WS_INLEN.bytes, 0, IMAGE_s_WS_INLEN.length);
        System.arraycopy(IMAGE_s_WS_MODE, 0, s_WS_MODE.bytes, 0, IMAGE_s_WS_MODE.length);
        System.arraycopy(IMAGE_s_WS_RESP, 0, s_WS_RESP.bytes, 0, IMAGE_s_WS_RESP.length);
        System.arraycopy(IMAGE_s_WS_RESP2, 0, s_WS_RESP2.bytes, 0, IMAGE_s_WS_RESP2.length);
        System.arraycopy(IMAGE_s_WS_R_D, 0, s_WS_R_D.bytes, 0, IMAGE_s_WS_R_D.length);
        System.arraycopy(IMAGE_s_WS_CA, 0, s_WS_CA.bytes, 0, IMAGE_s_WS_CA.length);
        System.arraycopy(IMAGE_s_WS_ALOG, 0, s_WS_ALOG.bytes, 0, IMAGE_s_WS_ALOG.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 5);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f47_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f18_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f20_EIBTRMID, CS);
            Cobol.store(f19_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f17_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f16_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (ca instanceof PcimmaWsCa) {
                calen = cx(task, 8);
            }
            Cobol.store(f23_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                perform(0, 5);
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
        region.run(task, "PCIMMA", this::runTask);
    }

    public void handleTransaction(String transid, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, null, area);
        region.run(task, "PCIMMA", this::runTask);
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
                if (next >= 6) {
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
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** MAIN-PARA. */
    private int p0() {
        // EXEC CICS RECEIVE INTO(WS-INPUT) LENGTH(WS-INLEN) END-EXEC
        CicsTask.Received received1 = task.receive(Cobol.num(f2_WS_INLEN, CS).intValue(), false);
        DetCics.received(f1_WS_INPUT, received1.data(), CS);
        Cobol.store(f2_WS_INLEN, BigDecimal.valueOf(received1.length()), false, CS);
        Cobol.store(f44_EIBRESP, BigDecimal.valueOf(DetCics.resp(received1.resp())), false, CS);
        Cobol.store(f45_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(received1.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(received1.resp())));
            if (to >= 0) return GOTO | to;
        }
        // MOVE WS-INPUT(6:1) TO WS-MODE
        Cobol.move(f1_WS_INPUT.ref(6, Integer.valueOf(1)), f3_WS_MODE, CS);
        // EVALUATE WS-MODE
        if ((Cobol.compare(f3_WS_MODE, "I", CS) == 0)) {
            // PERFORM IMMEDIATE-PARA
            perform(1, 1);
        } else if ((Cobol.compare(f3_WS_MODE, "L", CS) == 0)) {
            // PERFORM LINK-PARA
            perform(2, 2);
        } else if ((Cobol.compare(f3_WS_MODE, "N", CS) == 0)) {
            // PERFORM NOCA-PARA
            perform(3, 3);
        } else if ((Cobol.compare(f3_WS_MODE, "S", CS) == 0)) {
            // PERFORM START-PARA
            perform(4, 4);
        }
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        return 1;
    }

    /** IMMEDIATE-PARA. */
    private int p1() {
        // MOVE 'A1 ' TO ALOG-TAG
        Cobol.move("A1 ", f11_ALOG_TAG, CS);
        // MOVE CA-TEXT TO ALOG-TEXT
        Cobol.move(f9_CA_TEXT, f12_ALOG_TEXT, CS);
        // MOVE 0 TO ALOG-RESP
        Cobol.move(D0, f14_ALOG_RESP, CS);
        // PERFORM LOG-A
        perform(5, 5);
        // EXEC CICS RETURN TRANSID('PC52') COMMAREA(WS-CA) LENGTH(8) IMMEDIATE RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int[] rr2 = task.returnImmediate("PC52".strip(), out_PcimmaWsCa(f7_WS_CA.storage(), f7_WS_CA.offset()), 8, Cobol.commarea(f7_WS_CA, 8).bytes);
        if (rr2[0] == 0) { caBack.run(); throw new Goback(); }
        Cobol.store(f44_EIBRESP, BigDecimal.valueOf(rr2[0]), false, CS);
        Cobol.store(f45_EIBRESP2, BigDecimal.valueOf(rr2[1]), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(rr2[0]), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(rr2[1]), false, CS);
        // MOVE 'A1X' TO ALOG-TAG
        Cobol.move("A1X", f11_ALOG_TAG, CS);
        // MOVE SPACES TO ALOG-TEXT
        Cobol.moveFigurative(Figurative.SPACES, f12_ALOG_TEXT, CS);
        // MOVE WS-RESP TO ALOG-RESP
        Cobol.move(f4_WS_RESP, f14_ALOG_RESP, CS);
        // PERFORM LOG-A
        perform(5, 5);
        return 2;
    }

    /** LINK-PARA. */
    private int p2() {
        // MOVE 'LINK-A1' TO CA-TEXT
        Cobol.move("LINK-A1", f9_CA_TEXT, CS);
        // EXEC CICS LINK PROGRAM('PCIMML') COMMAREA(WS-CA) LENGTH(8) SYNCONRETURN RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        Storage cw5 = Cobol.commarea(f7_WS_CA, 8);
        PcimmlDfhcommarea ca4 = out_PcimmlDfhcommarea(cw5, 0);
        String lr3 = task.link("PCIMML".strip(), ca4, 8, cw5.bytes);
        if ("NORMAL".equals(lr3)) {
            if (!task.linkAreaBack()) { in_PcimmlDfhcommarea(ca4, cw5, 0); }
            Cobol.commareaBack(cw5, f7_WS_CA);
        }
        String exit6 = task.abendExit();
        if (exit6 != null) return GOTO | paragraph(exit6);
        if (task.ended()) throw abended();
        Cobol.store(f44_EIBRESP, BigDecimal.valueOf(DetCics.resp(lr3)), false, CS);
        Cobol.store(f45_EIBRESP2, BigDecimal.valueOf(task.transferResp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(DetCics.resp(lr3)), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(task.transferResp2()), false, CS);
        // MOVE 'A2 ' TO ALOG-TAG
        Cobol.move("A2 ", f11_ALOG_TAG, CS);
        // MOVE CA-TEXT TO ALOG-TEXT
        Cobol.move(f9_CA_TEXT, f12_ALOG_TEXT, CS);
        // MOVE WS-RESP TO ALOG-RESP
        Cobol.move(f4_WS_RESP, f14_ALOG_RESP, CS);
        // PERFORM LOG-A
        perform(5, 5);
        return 3;
    }

    /** NOCA-PARA. */
    private int p3() {
        // EXEC CICS LINK PROGRAM('PCIMML') RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        String lr7 = task.link("PCIMML".strip());
        String exit9 = task.abendExit();
        if (exit9 != null) return GOTO | paragraph(exit9);
        if (task.ended()) throw abended();
        Cobol.store(f44_EIBRESP, BigDecimal.valueOf(DetCics.resp(lr7)), false, CS);
        Cobol.store(f45_EIBRESP2, BigDecimal.valueOf(task.transferResp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(DetCics.resp(lr7)), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(task.transferResp2()), false, CS);
        // MOVE 'A3 ' TO ALOG-TAG
        Cobol.move("A3 ", f11_ALOG_TAG, CS);
        // MOVE 'BACK' TO ALOG-TEXT
        Cobol.move("BACK", f12_ALOG_TEXT, CS);
        // MOVE WS-RESP TO ALOG-RESP
        Cobol.move(f4_WS_RESP, f14_ALOG_RESP, CS);
        // PERFORM LOG-A
        perform(5, 5);
        return 4;
    }

    /** START-PARA. */
    private int p4() {
        // EXEC CICS START TRANSID('PC54') INTERVAL(0) RESP(WS-RESP) END-EXEC
        CicsTask.StartResult start10 = task.startRequest("PC54".strip()).interval(0).issue();
        Cobol.store(f44_EIBRESP, BigDecimal.valueOf(DetCics.resp(start10.resp())), false, CS);
        Cobol.store(f45_EIBRESP2, BigDecimal.valueOf(start10.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(DetCics.resp(start10.resp())), false, CS);
        // MOVE 'A4 ' TO ALOG-TAG
        Cobol.move("A4 ", f11_ALOG_TAG, CS);
        // MOVE 'STARTED' TO ALOG-TEXT
        Cobol.move("STARTED", f12_ALOG_TEXT, CS);
        // MOVE WS-RESP TO ALOG-RESP
        Cobol.move(f4_WS_RESP, f14_ALOG_RESP, CS);
        // PERFORM LOG-A
        perform(5, 5);
        return 5;
    }

    /** LOG-A. */
    private int p5() {
        // EXEC CICS WRITEQ TS QUEUE('PCLOG') FROM(WS-ALOG) LENGTH(15) END-EXEC
        CicsTask.TsResult ts11 = task.writeqTs("PCLOG".strip(), DetCics.toRegion(DetCics.bytes(f10_WS_ALOG, DetCics.within(f10_WS_ALOG, 15, "WRITEQ TS")), CS, REGION));
        Cobol.store(f44_EIBRESP, BigDecimal.valueOf(DetCics.resp(ts11.resp())), false, CS);
        Cobol.store(f45_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(ts11.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(ts11.resp())));
            if (to >= 0) return GOTO | to;
        }
        return 6;
    }

}
