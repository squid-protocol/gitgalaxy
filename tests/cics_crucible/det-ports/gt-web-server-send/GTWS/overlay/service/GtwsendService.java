// gitgalaxy-det-port: COBOL GTWSEND (GTWSEND.cbl), translated by rule, statement for statement
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
 * GTWSEND: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 22, translated 22, holes 0.
 */
@Service
public class GtwsendService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D201 = new BigDecimal("201");
    private static final BigDecimal D7 = new BigDecimal("7");
    private static final BigDecimal D404 = new BigDecimal("404");
    private static final BigDecimal D9 = new BigDecimal("9");
    private static final BigDecimal D2 = new BigDecimal("2");

    private static final byte[] IMAGE_s_WS_RESP = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_RESP2 = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_CODE_X = Base64.getDecoder().decode(String.join("",
            "ICAg"));
    private static final byte[] IMAGE_s_WS_CODE_N = Base64.getDecoder().decode(String.join("",
            "MDAw"));
    private static final byte[] IMAGE_s_WS_CODE = Base64.getDecoder().decode(String.join("",
            "AMg="));
    private static final byte[] IMAGE_s_WS_QRY = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_QLEN = Base64.getDecoder().decode(String.join("",
            "AAABAA=="));
    private static final byte[] IMAGE_s_WS_OUT = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_STAT = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAg"));
    private static final byte[] IMAGE_s_WS_SLEN = Base64.getDecoder().decode(String.join("",
            "AAAAAg=="));
    private static final byte[] IMAGE_s_WS_MT = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_RPLY = Base64.getDecoder().decode(String.join("",
            "cmVwbHktICAg"));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_RESP = new Storage(IMAGE_s_WS_RESP.length);
    private final Storage s_WS_RESP2 = new Storage(IMAGE_s_WS_RESP2.length);
    private final Storage s_WS_CODE_X = new Storage(IMAGE_s_WS_CODE_X.length);
    private final Storage s_WS_CODE_N = new Storage(IMAGE_s_WS_CODE_N.length);
    private final Storage s_WS_CODE = new Storage(IMAGE_s_WS_CODE.length);
    private final Storage s_WS_QRY = new Storage(IMAGE_s_WS_QRY.length);
    private final Storage s_WS_QLEN = new Storage(IMAGE_s_WS_QLEN.length);
    private final Storage s_WS_OUT = new Storage(IMAGE_s_WS_OUT.length);
    private final Storage s_WS_STAT = new Storage(IMAGE_s_WS_STAT.length);
    private final Storage s_WS_SLEN = new Storage(IMAGE_s_WS_SLEN.length);
    private final Storage s_WS_MT = new Storage(IMAGE_s_WS_MT.length);
    private final Storage s_WS_RPLY = new Storage(IMAGE_s_WS_RPLY.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_RESP = Field.binary(s_WS_RESP, 0, 8, 0, true, false);
    private final Field f2_WS_RESP2 = Field.binary(s_WS_RESP2, 0, 8, 0, true, false);
    private final Field f3_WS_CODE_X = Field.alphanumeric(s_WS_CODE_X, 0, 3, false);
    private final Field f4_WS_CODE_N = Field.zoned(s_WS_CODE_N, 0, 3, 0, false, false, false);
    private final Field f5_WS_CODE = Field.binary(s_WS_CODE, 0, 4, 0, true, false);
    private final Field f6_WS_QRY = Field.alphanumeric(s_WS_QRY, 0, 256, false);
    private final Field f7_WS_QLEN = Field.binary(s_WS_QLEN, 0, 8, 0, true, false);
    private final Field f8_WS_OUT = Field.alphanumeric(s_WS_OUT, 0, 20, false);
    private final Field f9_WS_STAT = Field.alphanumeric(s_WS_STAT, 0, 9, false);
    private final Field f10_WS_SLEN = Field.binary(s_WS_SLEN, 0, 8, 0, true, false);
    private final Field f11_WS_MT = Field.alphanumeric(s_WS_MT, 0, 56, false);
    private final Field f12_WS_RPLY = Field.group(s_WS_RPLY, 0, 9);
    private final Field f14_RPLY_CODE = Field.alphanumeric(s_WS_RPLY, 6, 3, false);
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



    public GtwsendService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_RESP, 0, s_WS_RESP.bytes, 0, IMAGE_s_WS_RESP.length);
        System.arraycopy(IMAGE_s_WS_RESP2, 0, s_WS_RESP2.bytes, 0, IMAGE_s_WS_RESP2.length);
        System.arraycopy(IMAGE_s_WS_CODE_X, 0, s_WS_CODE_X.bytes, 0, IMAGE_s_WS_CODE_X.length);
        System.arraycopy(IMAGE_s_WS_CODE_N, 0, s_WS_CODE_N.bytes, 0, IMAGE_s_WS_CODE_N.length);
        System.arraycopy(IMAGE_s_WS_CODE, 0, s_WS_CODE.bytes, 0, IMAGE_s_WS_CODE.length);
        System.arraycopy(IMAGE_s_WS_QRY, 0, s_WS_QRY.bytes, 0, IMAGE_s_WS_QRY.length);
        System.arraycopy(IMAGE_s_WS_QLEN, 0, s_WS_QLEN.bytes, 0, IMAGE_s_WS_QLEN.length);
        System.arraycopy(IMAGE_s_WS_OUT, 0, s_WS_OUT.bytes, 0, IMAGE_s_WS_OUT.length);
        System.arraycopy(IMAGE_s_WS_STAT, 0, s_WS_STAT.bytes, 0, IMAGE_s_WS_STAT.length);
        System.arraycopy(IMAGE_s_WS_SLEN, 0, s_WS_SLEN.bytes, 0, IMAGE_s_WS_SLEN.length);
        System.arraycopy(IMAGE_s_WS_MT, 0, s_WS_MT.bytes, 0, IMAGE_s_WS_MT.length);
        System.arraycopy(IMAGE_s_WS_RPLY, 0, s_WS_RPLY.bytes, 0, IMAGE_s_WS_RPLY.length);
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
            Cobol.store(f23_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
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
        region.run(task, "GTWSEND", this::runTask);
    }

    public void handleTransaction(String transid, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, null, area);
        region.run(task, "GTWSEND", this::runTask);
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
        // EXEC CICS WEB READ HTTPHEADER('X-Crucible-Code') NAMELENGTH(15) VALUE(WS-CODE-X) VALUELENGTH(3) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        CicsTask.WebHeader web1 = task.webReadHeader("X-Crucible-Code", 15, 3, 3);
        if (web1.resp() == 0) {
            if (web1.value().getBytes(CS).length > f3_WS_CODE_X.length()) throw new DetCics.PastFrom("WEB READ HTTPHEADER VALUE beyond its area: not modelled"); DetCics.put(f3_WS_CODE_X, web1.value().getBytes(CS));
        }
        Cobol.store(f44_EIBRESP, BigDecimal.valueOf(web1.resp()), false, CS);
        Cobol.store(f45_EIBRESP2, BigDecimal.valueOf(web1.resp2()), false, CS);
        Cobol.store(f1_WS_RESP, BigDecimal.valueOf(web1.resp()), false, CS);
        Cobol.store(f2_WS_RESP2, BigDecimal.valueOf(web1.resp2()), false, CS);
        // IF WS-CODE-X IS NUMERIC
        if (Cobol.isNumeric(f3_WS_CODE_X, CS)) {
            // MOVE WS-CODE-X TO WS-CODE-N
            Cobol.move(f3_WS_CODE_X, f4_WS_CODE_N, CS);
            // MOVE WS-CODE-N TO WS-CODE
            Cobol.move(f4_WS_CODE_N, f5_WS_CODE, CS);
        }
        // MOVE WS-CODE-X TO RPLY-CODE
        Cobol.move(f3_WS_CODE_X, f14_RPLY_CODE, CS);
        // EVALUATE WS-CODE
        if ((Cobol.num(f5_WS_CODE, CS).compareTo(D201) == 0)) {
            // MOVE 'Created' TO WS-STAT
            Cobol.move("Created", f9_WS_STAT, CS);
            // MOVE 7 TO WS-SLEN
            Cobol.move(D7, f10_WS_SLEN, CS);
            // MOVE 'application/json' TO WS-MT
            Cobol.move("application/json", f11_WS_MT, CS);
        } else if ((Cobol.num(f5_WS_CODE, CS).compareTo(D404) == 0)) {
            // MOVE 'Not Found' TO WS-STAT
            Cobol.move("Not Found", f9_WS_STAT, CS);
            // MOVE 9 TO WS-SLEN
            Cobol.move(D9, f10_WS_SLEN, CS);
            // MOVE 'text/plain' TO WS-MT
            Cobol.move("text/plain", f11_WS_MT, CS);
        } else if (true) {
            // MOVE 'OK' TO WS-STAT
            Cobol.move("OK", f9_WS_STAT, CS);
            // MOVE 2 TO WS-SLEN
            Cobol.move(D2, f10_WS_SLEN, CS);
            // MOVE 'text/plain' TO WS-MT
            Cobol.move("text/plain", f11_WS_MT, CS);
        }
        // EXEC CICS WEB EXTRACT QUERYSTRING(WS-QRY) QUERYSTRLEN(WS-QLEN) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        CicsTask.WebExtracted web2 = task.webExtract(null, 0, null, 0, null, 0, null, 0, Integer.valueOf(Cobol.num(f7_WS_QLEN, CS).intValue()), 256);
        if (web2.resp() == 0) {
            if (web2.query().getBytes(CS).length > f6_WS_QRY.length()) throw new DetCics.PastFrom("WEB EXTRACT QUERYSTRING beyond its area: not modelled"); DetCics.put(f6_WS_QRY, web2.query().getBytes(CS));
            Cobol.store(f7_WS_QLEN, BigDecimal.valueOf(web2.query().length()), false, CS);
        }
        Cobol.store(f44_EIBRESP, BigDecimal.valueOf(web2.resp()), false, CS);
        Cobol.store(f45_EIBRESP2, BigDecimal.valueOf(web2.resp2()), false, CS);
        Cobol.store(f1_WS_RESP, BigDecimal.valueOf(web2.resp()), false, CS);
        Cobol.store(f2_WS_RESP2, BigDecimal.valueOf(web2.resp2()), false, CS);
        // IF WS-QRY(1:1) = '?'
        if (Cobol.compare(f6_WS_QRY.ref(1, Integer.valueOf(1)), "?", CS) == 0) {
            // MOVE WS-QRY(2:20) TO WS-OUT
            Cobol.move(f6_WS_QRY.ref(2, Integer.valueOf(20)), f8_WS_OUT, CS);
        } else {
            // MOVE WS-QRY(1:20) TO WS-OUT
            Cobol.move(f6_WS_QRY.ref(1, Integer.valueOf(20)), f8_WS_OUT, CS);
        }
        // EXEC CICS WEB WRITE HTTPHEADER('X-Crucible-Reply') NAMELENGTH(16) VALUE(WS-RPLY) VALUELENGTH(9) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int[] web3 = task.webWriteHeader("X-Crucible-Reply", 16, Cobol.text(f12_WS_RPLY, CS), 9);
        Cobol.store(f44_EIBRESP, BigDecimal.valueOf(web3[0]), false, CS);
        Cobol.store(f45_EIBRESP2, BigDecimal.valueOf(web3[1]), false, CS);
        Cobol.store(f1_WS_RESP, BigDecimal.valueOf(web3[0]), false, CS);
        Cobol.store(f2_WS_RESP2, BigDecimal.valueOf(web3[1]), false, CS);
        // EXEC CICS WEB SEND FROM(WS-OUT) FROMLENGTH(20) MEDIATYPE(WS-MT) STATUSCODE(WS-CODE) STATUSTEXT(WS-STAT) STATUSLEN(WS-SLEN) ACTION(DFHVALUE(IMMEDIATE))
        int[] web4 = task.webSend(Cobol.text(f8_WS_OUT, CS), 20, Cobol.text(f11_WS_MT, CS), 2, Cobol.num(f5_WS_CODE, CS).intValue(), Cobol.text(f9_WS_STAT, CS), Cobol.num(f10_WS_SLEN, CS).intValue(), 1);
        Cobol.store(f44_EIBRESP, BigDecimal.valueOf(web4[0]), false, CS);
        Cobol.store(f45_EIBRESP2, BigDecimal.valueOf(web4[1]), false, CS);
        Cobol.store(f1_WS_RESP, BigDecimal.valueOf(web4[0]), false, CS);
        Cobol.store(f2_WS_RESP2, BigDecimal.valueOf(web4[1]), false, CS);
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        return 1;
    }

}
