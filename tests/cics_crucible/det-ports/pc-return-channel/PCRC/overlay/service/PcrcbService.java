// gitgalaxy-det-port: COBOL PCRCB (PCRCB.cbl), translated by rule, statement for statement
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
 * PCRCB: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 45, translated 45, holes 0.
 */
@Service
public class PcrcbService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D8 = new BigDecimal("8");
    private static final BigDecimal D5 = new BigDecimal("5");
    private static final BigDecimal D0 = new BigDecimal("0");

    private static final byte[] IMAGE_s_WS_CUR = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_STATE = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_NEW1 = Base64.getDecoder().decode(String.join("",
            "MkNIQU5HRUQ="));
    private static final byte[] IMAGE_s_WS_NEW2 = Base64.getDecoder().decode(String.join("",
            "M0FHQUlOLTI="));
    private static final byte[] IMAGE_s_WS_EXTRA = Base64.getDecoder().decode(String.join("",
            "RVhUUkE="));
    private static final byte[] IMAGE_s_WS_LEN = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_RESP = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_RESP2 = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_LOG = Base64.getDecoder().decode(String.join("",
            "ICAgIDAwMDAwMDAwMDAwICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_CUR = new Storage(IMAGE_s_WS_CUR.length);
    private final Storage s_WS_STATE = new Storage(IMAGE_s_WS_STATE.length);
    private final Storage s_WS_NEW1 = new Storage(IMAGE_s_WS_NEW1.length);
    private final Storage s_WS_NEW2 = new Storage(IMAGE_s_WS_NEW2.length);
    private final Storage s_WS_EXTRA = new Storage(IMAGE_s_WS_EXTRA.length);
    private final Storage s_WS_LEN = new Storage(IMAGE_s_WS_LEN.length);
    private final Storage s_WS_RESP = new Storage(IMAGE_s_WS_RESP.length);
    private final Storage s_WS_RESP2 = new Storage(IMAGE_s_WS_RESP2.length);
    private final Storage s_WS_LOG = new Storage(IMAGE_s_WS_LOG.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_CUR = Field.alphanumeric(s_WS_CUR, 0, 16, false);
    private final Field f2_WS_STATE = Field.group(s_WS_STATE, 0, 8);
    private final Field f3_ST_STAGE = Field.alphanumeric(s_WS_STATE, 0, 1, false);
    private final Field f5_WS_NEW1 = Field.alphanumeric(s_WS_NEW1, 0, 8, false);
    private final Field f6_WS_NEW2 = Field.alphanumeric(s_WS_NEW2, 0, 8, false);
    private final Field f7_WS_EXTRA = Field.alphanumeric(s_WS_EXTRA, 0, 5, false);
    private final Field f8_WS_LEN = Field.binary(s_WS_LEN, 0, 8, 0, true, false);
    private final Field f9_WS_RESP = Field.binary(s_WS_RESP, 0, 8, 0, true, false);
    private final Field f10_WS_RESP2 = Field.binary(s_WS_RESP2, 0, 8, 0, true, false);
    private final Field f11_WS_LOG = Field.group(s_WS_LOG, 0, 31);
    private final Field f12_LG_TAG = Field.alphanumeric(s_WS_LOG, 0, 4, false);
    private final Field f13_LG_RESP = Field.zoned(s_WS_LOG, 4, 3, 0, false, false, false);
    private final Field f14_LG_RESP2 = Field.zoned(s_WS_LOG, 7, 3, 0, false, false, false);
    private final Field f15_LG_LEN = Field.zoned(s_WS_LOG, 10, 5, 0, false, false, false);
    private final Field f16_LG_DATA = Field.alphanumeric(s_WS_LOG, 15, 16, false);
    private final Field f18_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f19_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f20_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f21_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f22_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f25_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f46_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f47_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f49_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

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
            java.util.Map.entry("LOG-ENTRY", 6),
            java.util.Map.entry("LOG-RESP", 5),
            java.util.Map.entry("GET-EXTRA", 4),
            java.util.Map.entry("STAGE-3", 3),
            java.util.Map.entry("STAGE-2", 2),
            java.util.Map.entry("STAGE-1", 1),
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



    public PcrcbService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_CUR, 0, s_WS_CUR.bytes, 0, IMAGE_s_WS_CUR.length);
        System.arraycopy(IMAGE_s_WS_STATE, 0, s_WS_STATE.bytes, 0, IMAGE_s_WS_STATE.length);
        System.arraycopy(IMAGE_s_WS_NEW1, 0, s_WS_NEW1.bytes, 0, IMAGE_s_WS_NEW1.length);
        System.arraycopy(IMAGE_s_WS_NEW2, 0, s_WS_NEW2.bytes, 0, IMAGE_s_WS_NEW2.length);
        System.arraycopy(IMAGE_s_WS_EXTRA, 0, s_WS_EXTRA.bytes, 0, IMAGE_s_WS_EXTRA.length);
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
            perform(0, 6);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f49_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f20_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f22_EIBTRMID, CS);
            Cobol.store(f21_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f19_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f18_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (ca instanceof PcrcaWsCarry) {
                calen = cx(task, 8);
            } else if (ca instanceof PcrcaWsModify) {
                calen = cx(task, 8);
            } else if (ca instanceof PcrcbWsExtra) {
                calen = cx(task, 5);
            } else if (ca instanceof PcrcbWsNew1) {
                calen = cx(task, 8);
            } else if (ca instanceof PcrcbWsNew2) {
                calen = cx(task, 8);
            } else if (ca instanceof PcrcbWsState) {
                calen = cx(task, 8);
            } else if (ca instanceof PcrclWsLinked) {
                calen = cx(task, 8);
            }
            Cobol.store(f25_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                perform(0, 6);
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

    public PcrcbChannelOut handleTransaction(String transid, PcrcbChannelIn request) {
        throw new UnsupportedOperationException("handleTransaction: the program has no task facade (a channel program); it runs as runTask");
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
                if (next >= 7) {
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
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** MAIN-PARA. */
    private int p0() {
        // INITIALIZE WS-LOG
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f11_WS_LOG.storage(), f11_WS_LOG.offset() + 0, 4, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f11_WS_LOG.storage(), f11_WS_LOG.offset() + 4, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f11_WS_LOG.storage(), f11_WS_LOG.offset() + 7, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f11_WS_LOG.storage(), f11_WS_LOG.offset() + 10, 5, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f11_WS_LOG.storage(), f11_WS_LOG.offset() + 15, 16, false), CS);
        // EXEC CICS ASSIGN CHANNEL(WS-CUR) END-EXEC
        DetCics.putText(f1_WS_CUR, task.assignChannel(), CS);
        // MOVE 'ASGB' TO LG-TAG
        Cobol.move("ASGB", f12_LG_TAG, CS);
        // MOVE WS-CUR TO LG-DATA
        Cobol.move(f1_WS_CUR, f16_LG_DATA, CS);
        // PERFORM LOG-ENTRY
        perform(6, 6);
        // MOVE 8 TO WS-LEN
        Cobol.move(D8, f8_WS_LEN, CS);
        // EXEC CICS GET CONTAINER('STATE') INTO(WS-STATE) FLENGTH(WS-LEN) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        CicsTask.ContainerResult cont1 = task.getContainer(null, "STATE".strip(), DetCics.containerLimit(f2_WS_STATE, Cobol.num(f8_WS_LEN, CS).intValue()));
        if (cont1.data() != null) DetCics.put(f2_WS_STATE, cont1.data());
        if (cont1.length() >= 0) Cobol.store(f8_WS_LEN, BigDecimal.valueOf(cont1.length()), false, CS);
        Cobol.store(f46_EIBRESP, BigDecimal.valueOf(DetCics.resp(cont1.resp())), false, CS);
        Cobol.store(f47_EIBRESP2, BigDecimal.valueOf(cont1.resp2()), false, CS);
        Cobol.store(f9_WS_RESP, BigDecimal.valueOf(DetCics.resp(cont1.resp())), false, CS);
        Cobol.store(f10_WS_RESP2, BigDecimal.valueOf(cont1.resp2()), false, CS);
        // MOVE 'GETB' TO LG-TAG
        Cobol.move("GETB", f12_LG_TAG, CS);
        // MOVE WS-LEN TO LG-LEN
        Cobol.move(f8_WS_LEN, f15_LG_LEN, CS);
        // MOVE WS-STATE TO LG-DATA
        Cobol.move(f2_WS_STATE, f16_LG_DATA, CS);
        // PERFORM LOG-RESP
        perform(5, 5);
        // EVALUATE ST-STAGE
        if ((Cobol.compare(f3_ST_STAGE, "1", CS) == 0)) {
            // PERFORM STAGE-1
            perform(1, 1);
        } else if ((Cobol.compare(f3_ST_STAGE, "2", CS) == 0)) {
            // PERFORM STAGE-2
            perform(2, 2);
        } else if ((Cobol.compare(f3_ST_STAGE, "3", CS) == 0)) {
            // PERFORM STAGE-3
            perform(3, 3);
        }
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        return 1;
    }

    /** STAGE-1. */
    private int p1() {
        // EXEC CICS PUT CONTAINER('STATE') FROM(WS-NEW1) CHAR RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int flen3 = 8;
        CicsTask.ContainerResult cont2 = task.putContainer(null, "STATE".strip(), DetCics.containerData(f5_WS_NEW1, flen3), flen3, "CHAR", false);
        Cobol.store(f46_EIBRESP, BigDecimal.valueOf(DetCics.resp(cont2.resp())), false, CS);
        Cobol.store(f47_EIBRESP2, BigDecimal.valueOf(cont2.resp2()), false, CS);
        Cobol.store(f9_WS_RESP, BigDecimal.valueOf(DetCics.resp(cont2.resp())), false, CS);
        Cobol.store(f10_WS_RESP2, BigDecimal.valueOf(cont2.resp2()), false, CS);
        // MOVE 'PUTS' TO LG-TAG
        Cobol.move("PUTS", f12_LG_TAG, CS);
        // PERFORM LOG-RESP
        perform(5, 5);
        // EXEC CICS PUT CONTAINER('EXTRA') FROM(WS-EXTRA) CHAR RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int flen5 = 5;
        CicsTask.ContainerResult cont4 = task.putContainer(null, "EXTRA".strip(), DetCics.containerData(f7_WS_EXTRA, flen5), flen5, "CHAR", false);
        Cobol.store(f46_EIBRESP, BigDecimal.valueOf(DetCics.resp(cont4.resp())), false, CS);
        Cobol.store(f47_EIBRESP2, BigDecimal.valueOf(cont4.resp2()), false, CS);
        Cobol.store(f9_WS_RESP, BigDecimal.valueOf(DetCics.resp(cont4.resp())), false, CS);
        Cobol.store(f10_WS_RESP2, BigDecimal.valueOf(cont4.resp2()), false, CS);
        // MOVE 'PUTX' TO LG-TAG
        Cobol.move("PUTX", f12_LG_TAG, CS);
        // PERFORM LOG-RESP
        perform(5, 5);
        // EXEC CICS RETURN TRANSID('PC62') CHANNEL(WS-CUR) END-EXEC
        int[] rr6 = task.returnChannel("PC62".strip(), Cobol.text(f1_WS_CUR, CS).strip());
        if (rr6[0] == 0) { caBack.run(); throw new Goback(); }
        Cobol.store(f46_EIBRESP, BigDecimal.valueOf(rr6[0]), false, CS);
        Cobol.store(f47_EIBRESP2, BigDecimal.valueOf(rr6[1]), false, CS);
        if (rr6[0] != 0) {
            int to = condition(DetCics.condition(rr6[0]));
            if (to >= 0) return GOTO | to;
        }
        return 2;
    }

    /** STAGE-2. */
    private int p2() {
        // PERFORM GET-EXTRA
        perform(4, 4);
        // EXEC CICS DELETE CONTAINER('EXTRA') RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        CicsTask.ContainerResult cont7 = task.deleteContainer(null, "EXTRA".strip());
        Cobol.store(f46_EIBRESP, BigDecimal.valueOf(DetCics.resp(cont7.resp())), false, CS);
        Cobol.store(f47_EIBRESP2, BigDecimal.valueOf(cont7.resp2()), false, CS);
        Cobol.store(f9_WS_RESP, BigDecimal.valueOf(DetCics.resp(cont7.resp())), false, CS);
        Cobol.store(f10_WS_RESP2, BigDecimal.valueOf(cont7.resp2()), false, CS);
        // MOVE 'DELE' TO LG-TAG
        Cobol.move("DELE", f12_LG_TAG, CS);
        // PERFORM LOG-RESP
        perform(5, 5);
        // EXEC CICS PUT CONTAINER('STATE') FROM(WS-NEW2) CHAR RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int flen9 = 8;
        CicsTask.ContainerResult cont8 = task.putContainer(null, "STATE".strip(), DetCics.containerData(f6_WS_NEW2, flen9), flen9, "CHAR", false);
        Cobol.store(f46_EIBRESP, BigDecimal.valueOf(DetCics.resp(cont8.resp())), false, CS);
        Cobol.store(f47_EIBRESP2, BigDecimal.valueOf(cont8.resp2()), false, CS);
        Cobol.store(f9_WS_RESP, BigDecimal.valueOf(DetCics.resp(cont8.resp())), false, CS);
        Cobol.store(f10_WS_RESP2, BigDecimal.valueOf(cont8.resp2()), false, CS);
        // MOVE 'PUTS' TO LG-TAG
        Cobol.move("PUTS", f12_LG_TAG, CS);
        // PERFORM LOG-RESP
        perform(5, 5);
        // EXEC CICS RETURN TRANSID('PC62') CHANNEL(WS-CUR) END-EXEC
        int[] rr10 = task.returnChannel("PC62".strip(), Cobol.text(f1_WS_CUR, CS).strip());
        if (rr10[0] == 0) { caBack.run(); throw new Goback(); }
        Cobol.store(f46_EIBRESP, BigDecimal.valueOf(rr10[0]), false, CS);
        Cobol.store(f47_EIBRESP2, BigDecimal.valueOf(rr10[1]), false, CS);
        if (rr10[0] != 0) {
            int to = condition(DetCics.condition(rr10[0]));
            if (to >= 0) return GOTO | to;
        }
        return 3;
    }

    /** STAGE-3. */
    private int p3() {
        // PERFORM GET-EXTRA
        perform(4, 4);
        return 4;
    }

    /** GET-EXTRA. */
    private int p4() {
        // MOVE 5 TO WS-LEN
        Cobol.move(D5, f8_WS_LEN, CS);
        // MOVE SPACES TO WS-EXTRA
        Cobol.moveFigurative(Figurative.SPACES, f7_WS_EXTRA, CS);
        // EXEC CICS GET CONTAINER('EXTRA') INTO(WS-EXTRA) FLENGTH(WS-LEN) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        CicsTask.ContainerResult cont11 = task.getContainer(null, "EXTRA".strip(), DetCics.containerLimit(f7_WS_EXTRA, Cobol.num(f8_WS_LEN, CS).intValue()));
        if (cont11.data() != null) DetCics.put(f7_WS_EXTRA, cont11.data());
        if (cont11.length() >= 0) Cobol.store(f8_WS_LEN, BigDecimal.valueOf(cont11.length()), false, CS);
        Cobol.store(f46_EIBRESP, BigDecimal.valueOf(DetCics.resp(cont11.resp())), false, CS);
        Cobol.store(f47_EIBRESP2, BigDecimal.valueOf(cont11.resp2()), false, CS);
        Cobol.store(f9_WS_RESP, BigDecimal.valueOf(DetCics.resp(cont11.resp())), false, CS);
        Cobol.store(f10_WS_RESP2, BigDecimal.valueOf(cont11.resp2()), false, CS);
        // MOVE 'GETX' TO LG-TAG
        Cobol.move("GETX", f12_LG_TAG, CS);
        // IF WS-RESP = 0
        if (Cobol.num(f9_WS_RESP, CS).compareTo(D0) == 0) {
            // MOVE WS-LEN TO LG-LEN
            Cobol.move(f8_WS_LEN, f15_LG_LEN, CS);
            // MOVE WS-EXTRA TO LG-DATA
            Cobol.move(f7_WS_EXTRA, f16_LG_DATA, CS);
        }
        // PERFORM LOG-RESP
        perform(5, 5);
        return 5;
    }

    /** LOG-RESP. */
    private int p5() {
        // MOVE WS-RESP TO LG-RESP
        Cobol.move(f9_WS_RESP, f13_LG_RESP, CS);
        // MOVE WS-RESP2 TO LG-RESP2
        Cobol.move(f10_WS_RESP2, f14_LG_RESP2, CS);
        // PERFORM LOG-ENTRY
        perform(6, 6);
        return 6;
    }

    /** LOG-ENTRY. */
    private int p6() {
        // EXEC CICS WRITEQ TS QUEUE('PCRLOG') FROM(WS-LOG) END-EXEC
        CicsTask.TsResult ts12 = task.writeqTs("PCRLOG".strip(), DetCics.toRegion(DetCics.bytes(f11_WS_LOG, f11_WS_LOG.length()), CS, REGION));
        Cobol.store(f46_EIBRESP, BigDecimal.valueOf(DetCics.resp(ts12.resp())), false, CS);
        Cobol.store(f47_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(ts12.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(ts12.resp())));
            if (to >= 0) return GOTO | to;
        }
        // INITIALIZE WS-LOG
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f11_WS_LOG.storage(), f11_WS_LOG.offset() + 0, 4, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f11_WS_LOG.storage(), f11_WS_LOG.offset() + 4, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f11_WS_LOG.storage(), f11_WS_LOG.offset() + 7, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f11_WS_LOG.storage(), f11_WS_LOG.offset() + 10, 5, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f11_WS_LOG.storage(), f11_WS_LOG.offset() + 15, 16, false), CS);
        return 7;
    }

}
