// gitgalaxy-det-port: COBOL GTWCLI (GTWCLI.cbl), translated by rule, statement for statement
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
 * GTWCLI: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 15, translated 15, holes 0.
 */
@Service
public class GtwcliService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D12 = new BigDecimal("12");
    private static final BigDecimal D14 = new BigDecimal("14");
    private static final BigDecimal D0 = new BigDecimal("0");

    private static final byte[] IMAGE_s_WS_IN = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_INLEN = Base64.getDecoder().decode(String.join("",
            "ABQ="));
    private static final byte[] IMAGE_s_WS_RESP = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_RESP2 = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_TOKEN = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAA="));
    private static final byte[] IMAGE_s_WS_HOST = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_HLEN = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_PATH = Base64.getDecoder().decode(String.join("",
            "L2d0L2l0ZW0="));
    private static final byte[] IMAGE_s_WS_PLEN = Base64.getDecoder().decode(String.join("",
            "AAAACA=="));
    private static final byte[] IMAGE_s_WS_BODY = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_MAX = Base64.getDecoder().decode(String.join("",
            "AAAAIA=="));
    private static final byte[] IMAGE_s_WS_TOLEN = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_STATUS = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private static final byte[] IMAGE_s_WS_OUT = Base64.getDecoder().decode(String.join("",
            "R1Q4NSBTPTAwMCBMPTAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_IN = new Storage(IMAGE_s_WS_IN.length);
    private final Storage s_WS_INLEN = new Storage(IMAGE_s_WS_INLEN.length);
    private final Storage s_WS_RESP = new Storage(IMAGE_s_WS_RESP.length);
    private final Storage s_WS_RESP2 = new Storage(IMAGE_s_WS_RESP2.length);
    private final Storage s_WS_TOKEN = new Storage(IMAGE_s_WS_TOKEN.length);
    private final Storage s_WS_HOST = new Storage(IMAGE_s_WS_HOST.length);
    private final Storage s_WS_HLEN = new Storage(IMAGE_s_WS_HLEN.length);
    private final Storage s_WS_PATH = new Storage(IMAGE_s_WS_PATH.length);
    private final Storage s_WS_PLEN = new Storage(IMAGE_s_WS_PLEN.length);
    private final Storage s_WS_BODY = new Storage(IMAGE_s_WS_BODY.length);
    private final Storage s_WS_MAX = new Storage(IMAGE_s_WS_MAX.length);
    private final Storage s_WS_TOLEN = new Storage(IMAGE_s_WS_TOLEN.length);
    private final Storage s_WS_STATUS = new Storage(IMAGE_s_WS_STATUS.length);
    private final Storage s_WS_OUT = new Storage(IMAGE_s_WS_OUT.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_IN = Field.alphanumeric(s_WS_IN, 0, 20, false);
    private final Field f2_WS_INLEN = Field.binary(s_WS_INLEN, 0, 4, 0, true, false);
    private final Field f3_WS_RESP = Field.binary(s_WS_RESP, 0, 8, 0, true, false);
    private final Field f4_WS_RESP2 = Field.binary(s_WS_RESP2, 0, 8, 0, true, false);
    private final Field f5_WS_TOKEN = Field.alphanumeric(s_WS_TOKEN, 0, 8, false);
    private final Field f6_WS_HOST = Field.alphanumeric(s_WS_HOST, 0, 16, false);
    private final Field f7_WS_HLEN = Field.binary(s_WS_HLEN, 0, 8, 0, true, false);
    private final Field f8_WS_PATH = Field.alphanumeric(s_WS_PATH, 0, 8, false);
    private final Field f9_WS_PLEN = Field.binary(s_WS_PLEN, 0, 8, 0, true, false);
    private final Field f10_WS_BODY = Field.alphanumeric(s_WS_BODY, 0, 32, false);
    private final Field f11_WS_MAX = Field.binary(s_WS_MAX, 0, 8, 0, true, false);
    private final Field f12_WS_TOLEN = Field.binary(s_WS_TOLEN, 0, 8, 0, true, false);
    private final Field f13_WS_STATUS = Field.binary(s_WS_STATUS, 0, 4, 0, true, false);
    private final Field f14_WS_OUT = Field.group(s_WS_OUT, 0, 48);
    private final Field f16_OUT_S = Field.zoned(s_WS_OUT, 7, 3, 0, false, false, false);
    private final Field f18_OUT_L = Field.zoned(s_WS_OUT, 13, 2, 0, false, false, false);
    private final Field f20_OUT_B = Field.alphanumeric(s_WS_OUT, 16, 32, false);
    private final Field f22_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f23_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f24_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f25_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f26_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f29_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f50_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f51_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f53_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

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



    public GtwcliService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_IN, 0, s_WS_IN.bytes, 0, IMAGE_s_WS_IN.length);
        System.arraycopy(IMAGE_s_WS_INLEN, 0, s_WS_INLEN.bytes, 0, IMAGE_s_WS_INLEN.length);
        System.arraycopy(IMAGE_s_WS_RESP, 0, s_WS_RESP.bytes, 0, IMAGE_s_WS_RESP.length);
        System.arraycopy(IMAGE_s_WS_RESP2, 0, s_WS_RESP2.bytes, 0, IMAGE_s_WS_RESP2.length);
        System.arraycopy(IMAGE_s_WS_TOKEN, 0, s_WS_TOKEN.bytes, 0, IMAGE_s_WS_TOKEN.length);
        System.arraycopy(IMAGE_s_WS_HOST, 0, s_WS_HOST.bytes, 0, IMAGE_s_WS_HOST.length);
        System.arraycopy(IMAGE_s_WS_HLEN, 0, s_WS_HLEN.bytes, 0, IMAGE_s_WS_HLEN.length);
        System.arraycopy(IMAGE_s_WS_PATH, 0, s_WS_PATH.bytes, 0, IMAGE_s_WS_PATH.length);
        System.arraycopy(IMAGE_s_WS_PLEN, 0, s_WS_PLEN.bytes, 0, IMAGE_s_WS_PLEN.length);
        System.arraycopy(IMAGE_s_WS_BODY, 0, s_WS_BODY.bytes, 0, IMAGE_s_WS_BODY.length);
        System.arraycopy(IMAGE_s_WS_MAX, 0, s_WS_MAX.bytes, 0, IMAGE_s_WS_MAX.length);
        System.arraycopy(IMAGE_s_WS_TOLEN, 0, s_WS_TOLEN.bytes, 0, IMAGE_s_WS_TOLEN.length);
        System.arraycopy(IMAGE_s_WS_STATUS, 0, s_WS_STATUS.bytes, 0, IMAGE_s_WS_STATUS.length);
        System.arraycopy(IMAGE_s_WS_OUT, 0, s_WS_OUT.bytes, 0, IMAGE_s_WS_OUT.length);
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
        return Cobol.num(f53_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f24_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f26_EIBTRMID, CS);
            Cobol.store(f25_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f23_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f22_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            Cobol.store(f29_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
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
        region.run(task, "GTWCLI", this::runTask);
    }

    public void handleTransaction(String transid, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, null, area);
        region.run(task, "GTWCLI", this::runTask);
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
        // EXEC CICS RECEIVE INTO(WS-IN) LENGTH(WS-INLEN) END-EXEC
        CicsTask.Received received1 = task.receive(Cobol.num(f2_WS_INLEN, CS).intValue(), false);
        DetCics.received(f1_WS_IN, received1.data(), CS);
        Cobol.store(f2_WS_INLEN, BigDecimal.valueOf(received1.length()), false, CS);
        Cobol.store(f50_EIBRESP, BigDecimal.valueOf(DetCics.resp(received1.resp())), false, CS);
        Cobol.store(f51_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(received1.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(received1.resp())));
            if (to >= 0) return GOTO | to;
        }
        // IF WS-IN(6:1) = 'B'
        if (Cobol.compare(f1_WS_IN.ref(6, Integer.valueOf(1)), "B", CS) == 0) {
            // MOVE 'gone.example' TO WS-HOST
            Cobol.move("gone.example", f6_WS_HOST, CS);
            // MOVE 12 TO WS-HLEN
            Cobol.move(D12, f7_WS_HLEN, CS);
        } else {
            // MOVE 'orders.example' TO WS-HOST
            Cobol.move("orders.example", f6_WS_HOST, CS);
            // MOVE 14 TO WS-HLEN
            Cobol.move(D14, f7_WS_HLEN, CS);
        }
        // EXEC CICS WEB OPEN HOST(WS-HOST) HOSTLENGTH(WS-HLEN) SCHEME(DFHVALUE(HTTP)) SESSTOKEN(WS-TOKEN) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        CicsTask.WebOpened web2 = task.webOpenHost(Cobol.text(f6_WS_HOST, CS), Cobol.num(f7_WS_HLEN, CS).intValue(), 0, false, 1096);
        if (web2.resp() == 0) DetCics.putText(f5_WS_TOKEN, web2.sesstoken(), CS);
        Cobol.store(f50_EIBRESP, BigDecimal.valueOf(web2.resp()), false, CS);
        Cobol.store(f51_EIBRESP2, BigDecimal.valueOf(web2.resp2()), false, CS);
        Cobol.store(f3_WS_RESP, BigDecimal.valueOf(web2.resp()), false, CS);
        Cobol.store(f4_WS_RESP2, BigDecimal.valueOf(web2.resp2()), false, CS);
        // EXEC CICS WEB CONVERSE SESSTOKEN(WS-TOKEN) PATH(WS-PATH) PATHLENGTH(WS-PLEN) METHOD(DFHVALUE(GET)) INTO(WS-BODY) MAXLENGTH(WS-MAX) TOLENGTH(WS-TOLEN) 
        CicsTask.WebResponse web3 = task.webConverse(Cobol.text(f5_WS_TOKEN, CS), 748, Cobol.text(f8_WS_PATH, CS), Cobol.num(f9_WS_PLEN, CS).intValue(), null, 0, null, 0, null, Cobol.num(f11_WS_MAX, CS).intValue(), -1, CS);
        if (web3.body() != null) {
            if (web3.body().length > f10_WS_BODY.length()) throw new DetCics.PastFrom("WEB CONVERSE INTO beyond its area: not modelled"); DetCics.put(f10_WS_BODY, web3.body());
            Cobol.store(f12_WS_TOLEN, BigDecimal.valueOf(web3.toLength()), false, CS);
            Cobol.store(f13_WS_STATUS, BigDecimal.valueOf(web3.status()), false, CS);
        }
        Cobol.store(f50_EIBRESP, BigDecimal.valueOf(web3.resp()), false, CS);
        Cobol.store(f51_EIBRESP2, BigDecimal.valueOf(web3.resp2()), false, CS);
        Cobol.store(f3_WS_RESP, BigDecimal.valueOf(web3.resp()), false, CS);
        Cobol.store(f4_WS_RESP2, BigDecimal.valueOf(web3.resp2()), false, CS);
        // IF WS-RESP = DFHRESP(NORMAL)
        if (Cobol.num(f3_WS_RESP, CS).compareTo(D0) == 0) {
            // MOVE WS-STATUS TO OUT-S
            Cobol.move(f13_WS_STATUS, f16_OUT_S, CS);
            // MOVE WS-TOLEN TO OUT-L
            Cobol.move(f12_WS_TOLEN, f18_OUT_L, CS);
            // MOVE WS-BODY TO OUT-B
            Cobol.move(f10_WS_BODY, f20_OUT_B, CS);
        }
        // EXEC CICS WEB CLOSE SESSTOKEN(WS-TOKEN) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int[] web4 = task.webClose(Cobol.text(f5_WS_TOKEN, CS));
        Cobol.store(f50_EIBRESP, BigDecimal.valueOf(web4[0]), false, CS);
        Cobol.store(f51_EIBRESP2, BigDecimal.valueOf(web4[1]), false, CS);
        Cobol.store(f3_WS_RESP, BigDecimal.valueOf(web4[0]), false, CS);
        Cobol.store(f4_WS_RESP2, BigDecimal.valueOf(web4[1]), false, CS);
        // EXEC CICS SEND TEXT FROM(WS-OUT) LENGTH(48) ERASE FREEKB WAIT END-EXEC
        String text5 = Cobol.text(f14_WS_OUT, CS);
        task.sendText(text5.substring(0, Math.min(text5.length(), 48)), 48, "ERASE", "FREEKB", "WAIT");
        Cobol.store(f50_EIBRESP, BigDecimal.valueOf(0), false, CS);
        Cobol.store(f51_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (0 != 0) {
            int to = condition(DetCics.condition(0));
            if (to >= 0) return GOTO | to;
        }
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        return 1;
    }

}
