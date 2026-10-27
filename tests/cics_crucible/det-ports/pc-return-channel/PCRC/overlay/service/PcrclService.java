// gitgalaxy-det-port: COBOL PCRCL (PCRCL.cbl), translated by rule, statement for statement
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
 * PCRCL: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 12, translated 12, holes 0.
 */
@Service
public class PcrclService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;

    private static final byte[] IMAGE_s_WS_CHAN = Base64.getDecoder().decode(String.join("",
            "UENDSEFOICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_LINKED = Base64.getDecoder().decode(String.join("",
            "Q0FSUlktTDI="));
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
    private final Storage s_WS_CHAN = new Storage(IMAGE_s_WS_CHAN.length);
    private final Storage s_WS_LINKED = new Storage(IMAGE_s_WS_LINKED.length);
    private final Storage s_WS_RESP = new Storage(IMAGE_s_WS_RESP.length);
    private final Storage s_WS_RESP2 = new Storage(IMAGE_s_WS_RESP2.length);
    private final Storage s_WS_LOG = new Storage(IMAGE_s_WS_LOG.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_CHAN = Field.alphanumeric(s_WS_CHAN, 0, 16, false);
    private final Field f2_WS_LINKED = Field.alphanumeric(s_WS_LINKED, 0, 8, false);
    private final Field f3_WS_RESP = Field.binary(s_WS_RESP, 0, 8, 0, true, false);
    private final Field f4_WS_RESP2 = Field.binary(s_WS_RESP2, 0, 8, 0, true, false);
    private final Field f5_WS_LOG = Field.group(s_WS_LOG, 0, 31);
    private final Field f6_LG_TAG = Field.alphanumeric(s_WS_LOG, 0, 4, false);
    private final Field f7_LG_RESP = Field.zoned(s_WS_LOG, 4, 3, 0, false, false, false);
    private final Field f8_LG_RESP2 = Field.zoned(s_WS_LOG, 7, 3, 0, false, false, false);
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



    public PcrclService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_CHAN, 0, s_WS_CHAN.bytes, 0, IMAGE_s_WS_CHAN.length);
        System.arraycopy(IMAGE_s_WS_LINKED, 0, s_WS_LINKED.bytes, 0, IMAGE_s_WS_LINKED.length);
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

    public void handleLink() {
        throw new UnsupportedOperationException("handleLink: the program has no task facade (a channel program); it runs as runTask");
    }

    public PcrclChannelOut handleChannel() {
        throw new UnsupportedOperationException("handleChannel: a channel entry has no task facade; the program runs as runTask or handleTransaction / handleLink");
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
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f5_WS_LOG.storage(), f5_WS_LOG.offset() + 10, 5, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f5_WS_LOG.storage(), f5_WS_LOG.offset() + 15, 16, false), CS);
        // EXEC CICS PUT CONTAINER('STATE') CHANNEL(WS-CHAN) FROM(WS-LINKED) CHAR RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int flen2 = 8;
        CicsTask.ContainerResult cont1 = task.putContainer(Cobol.text(f1_WS_CHAN, CS).strip(), "STATE".strip(), DetCics.containerData(f2_WS_LINKED, flen2), flen2, "CHAR", false);
        Cobol.store(f40_EIBRESP, BigDecimal.valueOf(DetCics.resp(cont1.resp())), false, CS);
        Cobol.store(f41_EIBRESP2, BigDecimal.valueOf(cont1.resp2()), false, CS);
        Cobol.store(f3_WS_RESP, BigDecimal.valueOf(DetCics.resp(cont1.resp())), false, CS);
        Cobol.store(f4_WS_RESP2, BigDecimal.valueOf(cont1.resp2()), false, CS);
        // MOVE 'PUT2' TO LG-TAG
        Cobol.move("PUT2", f6_LG_TAG, CS);
        // PERFORM LOG-RESP
        perform(1, 1);
        // EXEC CICS RETURN TRANSID('PC62') CHANNEL(WS-CHAN) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int[] rr3 = task.returnChannel("PC62".strip(), Cobol.text(f1_WS_CHAN, CS).strip());
        if (rr3[0] == 0) { caBack.run(); throw new Goback(); }
        Cobol.store(f40_EIBRESP, BigDecimal.valueOf(rr3[0]), false, CS);
        Cobol.store(f41_EIBRESP2, BigDecimal.valueOf(rr3[1]), false, CS);
        Cobol.store(f3_WS_RESP, BigDecimal.valueOf(rr3[0]), false, CS);
        Cobol.store(f4_WS_RESP2, BigDecimal.valueOf(rr3[1]), false, CS);
        // MOVE 'RET1' TO LG-TAG
        Cobol.move("RET1", f6_LG_TAG, CS);
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
        // EXEC CICS WRITEQ TS QUEUE('PCRLOG') FROM(WS-LOG) END-EXEC
        CicsTask.TsResult ts4 = task.writeqTs("PCRLOG".strip(), DetCics.toRegion(DetCics.bytes(f5_WS_LOG, f5_WS_LOG.length()), CS, REGION));
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
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f5_WS_LOG.storage(), f5_WS_LOG.offset() + 10, 5, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f5_WS_LOG.storage(), f5_WS_LOG.offset() + 15, 16, false), CS);
        return 2;
    }

}
