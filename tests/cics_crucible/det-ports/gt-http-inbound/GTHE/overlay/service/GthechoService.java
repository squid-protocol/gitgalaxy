// gitgalaxy-det-port: COBOL GTHECHO (GTHECHO.cbl), translated by rule, statement for statement
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
 * GTHECHO: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 5, translated 5, holes 0.
 */
@Service
public class GthechoService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private final Cobol.Dc DC_5 = new Cobol.Dc("5");

    private static final byte[] IMAGE_s_WS_IN = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_LEN = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_MAX = Base64.getDecoder().decode(String.join("",
            "AAAAIA=="));
    private static final byte[] IMAGE_s_WS_OUT = Base64.getDecoder().decode(String.join("",
            "RUNITzogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_OUTLEN = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_STAT = Base64.getDecoder().decode(String.join("",
            "T0s="));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_IN = new Storage(IMAGE_s_WS_IN.length);
    private final Storage s_WS_LEN = new Storage(IMAGE_s_WS_LEN.length);
    private final Storage s_WS_MAX = new Storage(IMAGE_s_WS_MAX.length);
    private final Storage s_WS_OUT = new Storage(IMAGE_s_WS_OUT.length);
    private final Storage s_WS_OUTLEN = new Storage(IMAGE_s_WS_OUTLEN.length);
    private final Storage s_WS_STAT = new Storage(IMAGE_s_WS_STAT.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_IN = Field.alphanumeric(s_WS_IN, 0, 32, false);
    private final Field f2_WS_LEN = Field.binary(s_WS_LEN, 0, 8, 0, true, false);
    private final Field f3_WS_MAX = Field.binary(s_WS_MAX, 0, 8, 0, true, false);
    private final Field f4_WS_OUT = Field.alphanumeric(s_WS_OUT, 0, 40, false);
    private final Field f5_WS_OUTLEN = Field.binary(s_WS_OUTLEN, 0, 8, 0, true, false);
    private final Field f6_WS_STAT = Field.alphanumeric(s_WS_STAT, 0, 2, false);
    private final Field f8_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f9_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f10_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f11_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f12_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f15_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f36_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f37_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f39_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

    private CicsTask task;
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



    public GthechoService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_IN, 0, s_WS_IN.bytes, 0, IMAGE_s_WS_IN.length);
        System.arraycopy(IMAGE_s_WS_LEN, 0, s_WS_LEN.bytes, 0, IMAGE_s_WS_LEN.length);
        System.arraycopy(IMAGE_s_WS_MAX, 0, s_WS_MAX.bytes, 0, IMAGE_s_WS_MAX.length);
        System.arraycopy(IMAGE_s_WS_OUT, 0, s_WS_OUT.bytes, 0, IMAGE_s_WS_OUT.length);
        System.arraycopy(IMAGE_s_WS_OUTLEN, 0, s_WS_OUTLEN.bytes, 0, IMAGE_s_WS_OUTLEN.length);
        System.arraycopy(IMAGE_s_WS_STAT, 0, s_WS_STAT.bytes, 0, IMAGE_s_WS_STAT.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
        DC_5.reset();
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
        return Cobol.num(f39_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f10_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f12_EIBTRMID, CS);
            Cobol.store(f11_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f9_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f8_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            Cobol.store(f15_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
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
        region.run(task, "GTHECHO", this::runTask);
    }

    public void handleTransaction(String transid, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, null, area);
        region.run(task, "GTHECHO", this::runTask);
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
        // EXEC CICS WEB RECEIVE INTO(WS-IN) LENGTH(WS-LEN) MAXLENGTH(WS-MAX) SRVCONVERT CHARACTERSET('iso-8859-1') HOSTCODEPAGE('037') END-EXEC
        CicsTask.WebReceived web1 = task.webReceive(Cobol.num(f3_WS_MAX, CS).intValue(), 32, 1);
        if (web1.body() != null) {
            if (web1.body().getBytes(CS).length > f1_WS_IN.length()) throw new DetCics.PastFrom("WEB RECEIVE INTO beyond its area: not modelled"); DetCics.put(f1_WS_IN, web1.body().getBytes(CS));
            Cobol.store(f2_WS_LEN, BigDecimal.valueOf(web1.body().length()), false, CS);
        }
        Cobol.store(f36_EIBRESP, BigDecimal.valueOf(web1.resp()), false, CS);
        Cobol.store(f37_EIBRESP2, BigDecimal.valueOf(web1.resp2()), false, CS);
        if (web1.resp() != 0) {
            int to = condition(DetCics.condition(web1.resp()));
            if (to >= 0) return GOTO | to;
        }
        // MOVE WS-IN(1:WS-LEN) TO WS-OUT(6:WS-LEN)
        Cobol.move(f1_WS_IN.ref(1, Integer.valueOf(Cobol.num(f2_WS_LEN, CS).intValue())), f4_WS_OUT.ref(6, Integer.valueOf(Cobol.num(f2_WS_LEN, CS).intValue())), CS);
        // COMPUTE WS-OUTLEN = WS-LEN + 5
        BigDecimal v2 = Cobol.add(Cobol.num(f2_WS_LEN, CS), DC_5);
        Cobol.store(f5_WS_OUTLEN, v2, false, CS);
        // EXEC CICS WEB SEND FROM(WS-OUT) FROMLENGTH(WS-OUTLEN) MEDIATYPE('text/plain') STATUSCODE(200) STATUSTEXT(WS-STAT) STATUSLEN(2) SRVCONVERT CHARACTERSET
        int[] web3 = task.webSend(Cobol.text(f4_WS_OUT, CS), Cobol.num(f5_WS_OUTLEN, CS).intValue(), "text/plain", 0, 200, Cobol.text(f6_WS_STAT, CS), 2, 1);
        Cobol.store(f36_EIBRESP, BigDecimal.valueOf(web3[0]), false, CS);
        Cobol.store(f37_EIBRESP2, BigDecimal.valueOf(web3[1]), false, CS);
        if (web3[0] != 0) {
            int to = condition(DetCics.condition(web3[0]));
            if (to >= 0) return GOTO | to;
        }
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        return 1;
    }

}
