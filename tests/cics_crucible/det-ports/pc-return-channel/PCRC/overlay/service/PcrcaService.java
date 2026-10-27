// gitgalaxy-det-port: COBOL PCRCA (PCRCA.cbl), translated by rule, statement for statement
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
 * PCRCA: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 23, translated 23, holes 0.
 */
@Service
public class PcrcaService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;

    private static final byte[] IMAGE_s_WS_INPUT = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_INLEN = Base64.getDecoder().decode(String.join("",
            "AAg="));
    private static final byte[] IMAGE_s_WS_MODE = Base64.getDecoder().decode(String.join("",
            "IA=="));
    private static final byte[] IMAGE_s_WS_CHAN = Base64.getDecoder().decode(String.join("",
            "UENDSEFOICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_CARRY = Base64.getDecoder().decode(String.join("",
            "Q0FSUlktQTE="));
    private static final byte[] IMAGE_s_WS_MODIFY = Base64.getDecoder().decode(String.join("",
            "MU1PRElGWTA="));
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
    private final Storage s_WS_INPUT = new Storage(IMAGE_s_WS_INPUT.length);
    private final Storage s_WS_INLEN = new Storage(IMAGE_s_WS_INLEN.length);
    private final Storage s_WS_MODE = new Storage(IMAGE_s_WS_MODE.length);
    private final Storage s_WS_CHAN = new Storage(IMAGE_s_WS_CHAN.length);
    private final Storage s_WS_CARRY = new Storage(IMAGE_s_WS_CARRY.length);
    private final Storage s_WS_MODIFY = new Storage(IMAGE_s_WS_MODIFY.length);
    private final Storage s_WS_RESP = new Storage(IMAGE_s_WS_RESP.length);
    private final Storage s_WS_RESP2 = new Storage(IMAGE_s_WS_RESP2.length);
    private final Storage s_WS_LOG = new Storage(IMAGE_s_WS_LOG.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_INPUT = Field.alphanumeric(s_WS_INPUT, 0, 8, false);
    private final Field f2_WS_INLEN = Field.binary(s_WS_INLEN, 0, 4, 0, true, false);
    private final Field f3_WS_MODE = Field.alphanumeric(s_WS_MODE, 0, 1, false);
    private final Field f4_WS_CHAN = Field.alphanumeric(s_WS_CHAN, 0, 16, false);
    private final Field f5_WS_CARRY = Field.alphanumeric(s_WS_CARRY, 0, 8, false);
    private final Field f6_WS_MODIFY = Field.alphanumeric(s_WS_MODIFY, 0, 8, false);
    private final Field f7_WS_RESP = Field.binary(s_WS_RESP, 0, 8, 0, true, false);
    private final Field f8_WS_RESP2 = Field.binary(s_WS_RESP2, 0, 8, 0, true, false);
    private final Field f9_WS_LOG = Field.group(s_WS_LOG, 0, 31);
    private final Field f10_LG_TAG = Field.alphanumeric(s_WS_LOG, 0, 4, false);
    private final Field f11_LG_RESP = Field.zoned(s_WS_LOG, 4, 3, 0, false, false, false);
    private final Field f12_LG_RESP2 = Field.zoned(s_WS_LOG, 7, 3, 0, false, false, false);
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
            java.util.Map.entry("LOG-RESP", 4),
            java.util.Map.entry("LINK-PARA", 3),
            java.util.Map.entry("MODIFY-PARA", 2),
            java.util.Map.entry("CARRY-PARA", 1),
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



    public PcrcaService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_INPUT, 0, s_WS_INPUT.bytes, 0, IMAGE_s_WS_INPUT.length);
        System.arraycopy(IMAGE_s_WS_INLEN, 0, s_WS_INLEN.bytes, 0, IMAGE_s_WS_INLEN.length);
        System.arraycopy(IMAGE_s_WS_MODE, 0, s_WS_MODE.bytes, 0, IMAGE_s_WS_MODE.length);
        System.arraycopy(IMAGE_s_WS_CHAN, 0, s_WS_CHAN.bytes, 0, IMAGE_s_WS_CHAN.length);
        System.arraycopy(IMAGE_s_WS_CARRY, 0, s_WS_CARRY.bytes, 0, IMAGE_s_WS_CARRY.length);
        System.arraycopy(IMAGE_s_WS_MODIFY, 0, s_WS_MODIFY.bytes, 0, IMAGE_s_WS_MODIFY.length);
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
            perform(0, 4);
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
            Cobol.store(f23_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
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
        throw new UnsupportedOperationException("handleTransaction: the program has no task facade (a channel program); it runs as runTask");
    }

    public PcrcaChannelOut handleChannel() {
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
        // INITIALIZE WS-LOG
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f9_WS_LOG.storage(), f9_WS_LOG.offset() + 0, 4, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f9_WS_LOG.storage(), f9_WS_LOG.offset() + 4, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f9_WS_LOG.storage(), f9_WS_LOG.offset() + 7, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f9_WS_LOG.storage(), f9_WS_LOG.offset() + 10, 5, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f9_WS_LOG.storage(), f9_WS_LOG.offset() + 15, 16, false), CS);
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
        if ((Cobol.compare(f3_WS_MODE, "C", CS) == 0)) {
            // PERFORM CARRY-PARA
            perform(1, 1);
        } else if ((Cobol.compare(f3_WS_MODE, "M", CS) == 0)) {
            // PERFORM MODIFY-PARA
            perform(2, 2);
        } else if ((Cobol.compare(f3_WS_MODE, "L", CS) == 0)) {
            // PERFORM LINK-PARA
            perform(3, 3);
        }
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        return 1;
    }

    /** CARRY-PARA. */
    private int p1() {
        // EXEC CICS PUT CONTAINER('STATE') CHANNEL(WS-CHAN) FROM(WS-CARRY) CHAR RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int flen3 = 8;
        CicsTask.ContainerResult cont2 = task.putContainer(Cobol.text(f4_WS_CHAN, CS).strip(), "STATE".strip(), DetCics.containerData(f5_WS_CARRY, flen3), flen3, "CHAR", false);
        Cobol.store(f44_EIBRESP, BigDecimal.valueOf(DetCics.resp(cont2.resp())), false, CS);
        Cobol.store(f45_EIBRESP2, BigDecimal.valueOf(cont2.resp2()), false, CS);
        Cobol.store(f7_WS_RESP, BigDecimal.valueOf(DetCics.resp(cont2.resp())), false, CS);
        Cobol.store(f8_WS_RESP2, BigDecimal.valueOf(cont2.resp2()), false, CS);
        // MOVE 'PUT1' TO LG-TAG
        Cobol.move("PUT1", f10_LG_TAG, CS);
        // PERFORM LOG-RESP
        perform(4, 4);
        // EXEC CICS RETURN TRANSID('PC62') CHANNEL(WS-CHAN) END-EXEC
        int[] rr4 = task.returnChannel("PC62".strip(), Cobol.text(f4_WS_CHAN, CS).strip());
        if (rr4[0] == 0) { caBack.run(); throw new Goback(); }
        Cobol.store(f44_EIBRESP, BigDecimal.valueOf(rr4[0]), false, CS);
        Cobol.store(f45_EIBRESP2, BigDecimal.valueOf(rr4[1]), false, CS);
        if (rr4[0] != 0) {
            int to = condition(DetCics.condition(rr4[0]));
            if (to >= 0) return GOTO | to;
        }
        return 2;
    }

    /** MODIFY-PARA. */
    private int p2() {
        // EXEC CICS PUT CONTAINER('STATE') CHANNEL(WS-CHAN) FROM(WS-MODIFY) CHAR RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int flen6 = 8;
        CicsTask.ContainerResult cont5 = task.putContainer(Cobol.text(f4_WS_CHAN, CS).strip(), "STATE".strip(), DetCics.containerData(f6_WS_MODIFY, flen6), flen6, "CHAR", false);
        Cobol.store(f44_EIBRESP, BigDecimal.valueOf(DetCics.resp(cont5.resp())), false, CS);
        Cobol.store(f45_EIBRESP2, BigDecimal.valueOf(cont5.resp2()), false, CS);
        Cobol.store(f7_WS_RESP, BigDecimal.valueOf(DetCics.resp(cont5.resp())), false, CS);
        Cobol.store(f8_WS_RESP2, BigDecimal.valueOf(cont5.resp2()), false, CS);
        // MOVE 'PUT1' TO LG-TAG
        Cobol.move("PUT1", f10_LG_TAG, CS);
        // PERFORM LOG-RESP
        perform(4, 4);
        // EXEC CICS RETURN TRANSID('PC62') CHANNEL(WS-CHAN) END-EXEC
        int[] rr7 = task.returnChannel("PC62".strip(), Cobol.text(f4_WS_CHAN, CS).strip());
        if (rr7[0] == 0) { caBack.run(); throw new Goback(); }
        Cobol.store(f44_EIBRESP, BigDecimal.valueOf(rr7[0]), false, CS);
        Cobol.store(f45_EIBRESP2, BigDecimal.valueOf(rr7[1]), false, CS);
        if (rr7[0] != 0) {
            int to = condition(DetCics.condition(rr7[0]));
            if (to >= 0) return GOTO | to;
        }
        return 3;
    }

    /** LINK-PARA. */
    private int p3() {
        // EXEC CICS LINK PROGRAM('PCRCL') RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        String lr8 = task.link("PCRCL".strip());
        String exit10 = task.abendExit();
        if (exit10 != null) return GOTO | paragraph(exit10);
        if (task.ended()) throw abended();
        Cobol.store(f44_EIBRESP, BigDecimal.valueOf(DetCics.resp(lr8)), false, CS);
        Cobol.store(f45_EIBRESP2, BigDecimal.valueOf(task.transferResp2()), false, CS);
        Cobol.store(f7_WS_RESP, BigDecimal.valueOf(DetCics.resp(lr8)), false, CS);
        Cobol.store(f8_WS_RESP2, BigDecimal.valueOf(task.transferResp2()), false, CS);
        // MOVE 'LNK1' TO LG-TAG
        Cobol.move("LNK1", f10_LG_TAG, CS);
        // PERFORM LOG-RESP
        perform(4, 4);
        return 4;
    }

    /** LOG-RESP. */
    private int p4() {
        // MOVE WS-RESP TO LG-RESP
        Cobol.move(f7_WS_RESP, f11_LG_RESP, CS);
        // MOVE WS-RESP2 TO LG-RESP2
        Cobol.move(f8_WS_RESP2, f12_LG_RESP2, CS);
        // EXEC CICS WRITEQ TS QUEUE('PCRLOG') FROM(WS-LOG) END-EXEC
        CicsTask.TsResult ts11 = task.writeqTs("PCRLOG".strip(), DetCics.toRegion(DetCics.bytes(f9_WS_LOG, f9_WS_LOG.length()), CS, REGION));
        Cobol.store(f44_EIBRESP, BigDecimal.valueOf(DetCics.resp(ts11.resp())), false, CS);
        Cobol.store(f45_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(ts11.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(ts11.resp())));
            if (to >= 0) return GOTO | to;
        }
        // INITIALIZE WS-LOG
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f9_WS_LOG.storage(), f9_WS_LOG.offset() + 0, 4, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f9_WS_LOG.storage(), f9_WS_LOG.offset() + 4, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f9_WS_LOG.storage(), f9_WS_LOG.offset() + 7, 3, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f9_WS_LOG.storage(), f9_WS_LOG.offset() + 10, 5, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f9_WS_LOG.storage(), f9_WS_LOG.offset() + 15, 16, false), CS);
        return 5;
    }

}
