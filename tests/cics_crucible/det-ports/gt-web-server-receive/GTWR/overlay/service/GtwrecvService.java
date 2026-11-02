// gitgalaxy-det-port: COBOL GTWRECV (GTWRECV.cbl), translated by rule, statement for statement
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
 * GTWRECV: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 21, translated 21, holes 0.
 */
@Service
public class GtwrecvService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D0 = new BigDecimal("0");

    private static final byte[] IMAGE_s_WS_IN = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_LEN = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_MAX = Base64.getDecoder().decode(String.join("",
            "AAAACA=="));
    private static final byte[] IMAGE_s_WS_RESP = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_RESP2 = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_METH = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_MLEN = Base64.getDecoder().decode(String.join("",
            "AAAACA=="));
    private static final byte[] IMAGE_s_WS_HOST = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_HLEN = Base64.getDecoder().decode(String.join("",
            "AAAAdA=="));
    private static final byte[] IMAGE_s_WS_PATH = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_PLEN = Base64.getDecoder().decode(String.join("",
            "AAABAA=="));
    private static final byte[] IMAGE_s_WS_QRY = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_QLEN = Base64.getDecoder().decode(String.join("",
            "AAABAA=="));
    private static final byte[] IMAGE_s_WS_TAG = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_TLEN = Base64.getDecoder().decode(String.join("",
            "AAAACg=="));
    private static final byte[] IMAGE_s_WS_STAT = Base64.getDecoder().decode(String.join("",
            "T0s="));
    private static final byte[] IMAGE_s_WS_OUT = Base64.getDecoder().decode(String.join("",
            "UkNWPTAwLzAwMCBMPTAwMCBCPSAgICAgICAgIE09ICAgICAgIEg9ICAgICAgICAgICAgICAgICAgICAgUD0gICAgICAgICAgIFE9ICAgICAgICAgICBUPTAwLzAwMCBWPSAgICAgICAgICA="));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_IN = new Storage(IMAGE_s_WS_IN.length);
    private final Storage s_WS_LEN = new Storage(IMAGE_s_WS_LEN.length);
    private final Storage s_WS_MAX = new Storage(IMAGE_s_WS_MAX.length);
    private final Storage s_WS_RESP = new Storage(IMAGE_s_WS_RESP.length);
    private final Storage s_WS_RESP2 = new Storage(IMAGE_s_WS_RESP2.length);
    private final Storage s_WS_METH = new Storage(IMAGE_s_WS_METH.length);
    private final Storage s_WS_MLEN = new Storage(IMAGE_s_WS_MLEN.length);
    private final Storage s_WS_HOST = new Storage(IMAGE_s_WS_HOST.length);
    private final Storage s_WS_HLEN = new Storage(IMAGE_s_WS_HLEN.length);
    private final Storage s_WS_PATH = new Storage(IMAGE_s_WS_PATH.length);
    private final Storage s_WS_PLEN = new Storage(IMAGE_s_WS_PLEN.length);
    private final Storage s_WS_QRY = new Storage(IMAGE_s_WS_QRY.length);
    private final Storage s_WS_QLEN = new Storage(IMAGE_s_WS_QLEN.length);
    private final Storage s_WS_TAG = new Storage(IMAGE_s_WS_TAG.length);
    private final Storage s_WS_TLEN = new Storage(IMAGE_s_WS_TLEN.length);
    private final Storage s_WS_STAT = new Storage(IMAGE_s_WS_STAT.length);
    private final Storage s_WS_OUT = new Storage(IMAGE_s_WS_OUT.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_IN = Field.alphanumeric(s_WS_IN, 0, 8, false);
    private final Field f2_WS_LEN = Field.binary(s_WS_LEN, 0, 8, 0, true, false);
    private final Field f3_WS_MAX = Field.binary(s_WS_MAX, 0, 8, 0, true, false);
    private final Field f4_WS_RESP = Field.binary(s_WS_RESP, 0, 8, 0, true, false);
    private final Field f5_WS_RESP2 = Field.binary(s_WS_RESP2, 0, 8, 0, true, false);
    private final Field f6_WS_METH = Field.alphanumeric(s_WS_METH, 0, 8, false);
    private final Field f7_WS_MLEN = Field.binary(s_WS_MLEN, 0, 8, 0, true, false);
    private final Field f8_WS_HOST = Field.alphanumeric(s_WS_HOST, 0, 116, false);
    private final Field f9_WS_HLEN = Field.binary(s_WS_HLEN, 0, 8, 0, true, false);
    private final Field f10_WS_PATH = Field.alphanumeric(s_WS_PATH, 0, 256, false);
    private final Field f11_WS_PLEN = Field.binary(s_WS_PLEN, 0, 8, 0, true, false);
    private final Field f12_WS_QRY = Field.alphanumeric(s_WS_QRY, 0, 256, false);
    private final Field f13_WS_QLEN = Field.binary(s_WS_QLEN, 0, 8, 0, true, false);
    private final Field f14_WS_TAG = Field.alphanumeric(s_WS_TAG, 0, 10, false);
    private final Field f15_WS_TLEN = Field.binary(s_WS_TLEN, 0, 8, 0, true, false);
    private final Field f16_WS_STAT = Field.alphanumeric(s_WS_STAT, 0, 2, false);
    private final Field f17_WS_OUT = Field.group(s_WS_OUT, 0, 107);
    private final Field f19_OUT_RR = Field.zoned(s_WS_OUT, 4, 2, 0, false, false, false);
    private final Field f21_OUT_R2 = Field.zoned(s_WS_OUT, 7, 3, 0, false, false, false);
    private final Field f23_OUT_LEN = Field.zoned(s_WS_OUT, 13, 3, 0, false, false, false);
    private final Field f25_OUT_BODY = Field.alphanumeric(s_WS_OUT, 19, 8, false);
    private final Field f27_OUT_METH = Field.alphanumeric(s_WS_OUT, 30, 6, false);
    private final Field f29_OUT_HOST = Field.alphanumeric(s_WS_OUT, 39, 20, false);
    private final Field f31_OUT_PATH = Field.alphanumeric(s_WS_OUT, 62, 10, false);
    private final Field f33_OUT_QRY = Field.alphanumeric(s_WS_OUT, 75, 10, false);
    private final Field f35_OUT_TR = Field.zoned(s_WS_OUT, 88, 2, 0, false, false, false);
    private final Field f37_OUT_T2 = Field.zoned(s_WS_OUT, 91, 3, 0, false, false, false);
    private final Field f39_OUT_TAG = Field.alphanumeric(s_WS_OUT, 97, 10, false);
    private final Field f41_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f42_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f43_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f44_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f45_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f48_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f69_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f70_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f72_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

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



    public GtwrecvService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_IN, 0, s_WS_IN.bytes, 0, IMAGE_s_WS_IN.length);
        System.arraycopy(IMAGE_s_WS_LEN, 0, s_WS_LEN.bytes, 0, IMAGE_s_WS_LEN.length);
        System.arraycopy(IMAGE_s_WS_MAX, 0, s_WS_MAX.bytes, 0, IMAGE_s_WS_MAX.length);
        System.arraycopy(IMAGE_s_WS_RESP, 0, s_WS_RESP.bytes, 0, IMAGE_s_WS_RESP.length);
        System.arraycopy(IMAGE_s_WS_RESP2, 0, s_WS_RESP2.bytes, 0, IMAGE_s_WS_RESP2.length);
        System.arraycopy(IMAGE_s_WS_METH, 0, s_WS_METH.bytes, 0, IMAGE_s_WS_METH.length);
        System.arraycopy(IMAGE_s_WS_MLEN, 0, s_WS_MLEN.bytes, 0, IMAGE_s_WS_MLEN.length);
        System.arraycopy(IMAGE_s_WS_HOST, 0, s_WS_HOST.bytes, 0, IMAGE_s_WS_HOST.length);
        System.arraycopy(IMAGE_s_WS_HLEN, 0, s_WS_HLEN.bytes, 0, IMAGE_s_WS_HLEN.length);
        System.arraycopy(IMAGE_s_WS_PATH, 0, s_WS_PATH.bytes, 0, IMAGE_s_WS_PATH.length);
        System.arraycopy(IMAGE_s_WS_PLEN, 0, s_WS_PLEN.bytes, 0, IMAGE_s_WS_PLEN.length);
        System.arraycopy(IMAGE_s_WS_QRY, 0, s_WS_QRY.bytes, 0, IMAGE_s_WS_QRY.length);
        System.arraycopy(IMAGE_s_WS_QLEN, 0, s_WS_QLEN.bytes, 0, IMAGE_s_WS_QLEN.length);
        System.arraycopy(IMAGE_s_WS_TAG, 0, s_WS_TAG.bytes, 0, IMAGE_s_WS_TAG.length);
        System.arraycopy(IMAGE_s_WS_TLEN, 0, s_WS_TLEN.bytes, 0, IMAGE_s_WS_TLEN.length);
        System.arraycopy(IMAGE_s_WS_STAT, 0, s_WS_STAT.bytes, 0, IMAGE_s_WS_STAT.length);
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
        return Cobol.num(f72_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f43_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f45_EIBTRMID, CS);
            Cobol.store(f44_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f42_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f41_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            Cobol.store(f48_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
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
        region.run(task, "GTWRECV", this::runTask);
    }

    public void handleTransaction(String transid, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, null, area);
        region.run(task, "GTWRECV", this::runTask);
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
        // EXEC CICS WEB RECEIVE INTO(WS-IN) LENGTH(WS-LEN) MAXLENGTH(WS-MAX) SRVCONVERT CHARACTERSET('iso-8859-1') HOSTCODEPAGE('037') RESP(WS-RESP) RESP2(WS-RE
        CicsTask.WebReceived web1 = task.webReceive(Cobol.num(f3_WS_MAX, CS).intValue(), 8, 1);
        if (web1.body() != null) {
            if (web1.body().getBytes(CS).length > f1_WS_IN.length()) throw new DetCics.PastFrom("WEB RECEIVE INTO beyond its area: not modelled"); DetCics.put(f1_WS_IN, web1.body().getBytes(CS));
            Cobol.store(f2_WS_LEN, BigDecimal.valueOf(web1.body().length()), false, CS);
        }
        Cobol.store(f69_EIBRESP, BigDecimal.valueOf(web1.resp()), false, CS);
        Cobol.store(f70_EIBRESP2, BigDecimal.valueOf(web1.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(web1.resp()), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(web1.resp2()), false, CS);
        // MOVE WS-RESP TO OUT-RR
        Cobol.move(f4_WS_RESP, f19_OUT_RR, CS);
        // MOVE WS-RESP2 TO OUT-R2
        Cobol.move(f5_WS_RESP2, f21_OUT_R2, CS);
        // MOVE WS-LEN TO OUT-LEN
        Cobol.move(f2_WS_LEN, f23_OUT_LEN, CS);
        // MOVE WS-IN TO OUT-BODY
        Cobol.move(f1_WS_IN, f25_OUT_BODY, CS);
        // EXEC CICS WEB EXTRACT HTTPMETHOD(WS-METH) METHODLENGTH(WS-MLEN) HOST(WS-HOST) HOSTLENGTH(WS-HLEN) PATH(WS-PATH) PATHLENGTH(WS-PLEN) QUERYSTRING(WS-QRY
        CicsTask.WebExtracted web2 = task.webExtract(Integer.valueOf(Cobol.num(f9_WS_HLEN, CS).intValue()), 116, Integer.valueOf(Cobol.num(f7_WS_MLEN, CS).intValue()), 8, null, 0, Integer.valueOf(Cobol.num(f11_WS_PLEN, CS).intValue()), 256, Integer.valueOf(Cobol.num(f13_WS_QLEN, CS).intValue()), 256);
        if (web2.resp() == 0) {
            if (web2.host().getBytes(CS).length > f8_WS_HOST.length()) throw new DetCics.PastFrom("WEB EXTRACT HOST beyond its area: not modelled"); DetCics.put(f8_WS_HOST, web2.host().getBytes(CS));
            Cobol.store(f9_WS_HLEN, BigDecimal.valueOf(web2.host().length()), false, CS);
            if (web2.method().getBytes(CS).length > f6_WS_METH.length()) throw new DetCics.PastFrom("WEB EXTRACT HTTPMETHOD beyond its area: not modelled"); DetCics.put(f6_WS_METH, web2.method().getBytes(CS));
            Cobol.store(f7_WS_MLEN, BigDecimal.valueOf(web2.method().length()), false, CS);
            if (web2.path().getBytes(CS).length > f10_WS_PATH.length()) throw new DetCics.PastFrom("WEB EXTRACT PATH beyond its area: not modelled"); DetCics.put(f10_WS_PATH, web2.path().getBytes(CS));
            Cobol.store(f11_WS_PLEN, BigDecimal.valueOf(web2.path().length()), false, CS);
            if (web2.query().getBytes(CS).length > f12_WS_QRY.length()) throw new DetCics.PastFrom("WEB EXTRACT QUERYSTRING beyond its area: not modelled"); DetCics.put(f12_WS_QRY, web2.query().getBytes(CS));
            Cobol.store(f13_WS_QLEN, BigDecimal.valueOf(web2.query().length()), false, CS);
        }
        Cobol.store(f69_EIBRESP, BigDecimal.valueOf(web2.resp()), false, CS);
        Cobol.store(f70_EIBRESP2, BigDecimal.valueOf(web2.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(web2.resp()), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(web2.resp2()), false, CS);
        // MOVE WS-METH(1:6) TO OUT-METH
        Cobol.move(f6_WS_METH.ref(1, Integer.valueOf(6)), f27_OUT_METH, CS);
        // MOVE WS-HOST(1:20) TO OUT-HOST
        Cobol.move(f8_WS_HOST.ref(1, Integer.valueOf(20)), f29_OUT_HOST, CS);
        // IF WS-PATH(1:1) = '/'
        if (Cobol.compare(f10_WS_PATH.ref(1, Integer.valueOf(1)), "/", CS) == 0) {
            // MOVE WS-PATH(2:10) TO OUT-PATH
            Cobol.move(f10_WS_PATH.ref(2, Integer.valueOf(10)), f31_OUT_PATH, CS);
        } else {
            // MOVE WS-PATH(1:10) TO OUT-PATH
            Cobol.move(f10_WS_PATH.ref(1, Integer.valueOf(10)), f31_OUT_PATH, CS);
        }
        // IF WS-QRY(1:1) = '?'
        if (Cobol.compare(f12_WS_QRY.ref(1, Integer.valueOf(1)), "?", CS) == 0) {
            // MOVE WS-QRY(2:10) TO OUT-QRY
            Cobol.move(f12_WS_QRY.ref(2, Integer.valueOf(10)), f33_OUT_QRY, CS);
        } else {
            // MOVE WS-QRY(1:10) TO OUT-QRY
            Cobol.move(f12_WS_QRY.ref(1, Integer.valueOf(10)), f33_OUT_QRY, CS);
        }
        // EXEC CICS WEB READ HTTPHEADER('X-Crucible-Tag') NAMELENGTH(14) VALUE(WS-TAG) VALUELENGTH(WS-TLEN) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        CicsTask.WebHeader web3 = task.webReadHeader("X-Crucible-Tag", 14, Cobol.num(f15_WS_TLEN, CS).intValue(), 10);
        if (web3.resp() == 0) {
            if (web3.value().getBytes(CS).length > f14_WS_TAG.length()) throw new DetCics.PastFrom("WEB READ HTTPHEADER VALUE beyond its area: not modelled"); DetCics.put(f14_WS_TAG, web3.value().getBytes(CS));
            Cobol.store(f15_WS_TLEN, BigDecimal.valueOf(web3.value().length()), false, CS);
        }
        Cobol.store(f69_EIBRESP, BigDecimal.valueOf(web3.resp()), false, CS);
        Cobol.store(f70_EIBRESP2, BigDecimal.valueOf(web3.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(web3.resp()), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(web3.resp2()), false, CS);
        // MOVE WS-RESP TO OUT-TR
        Cobol.move(f4_WS_RESP, f35_OUT_TR, CS);
        // MOVE WS-RESP2 TO OUT-T2
        Cobol.move(f5_WS_RESP2, f37_OUT_T2, CS);
        // IF WS-RESP = 0
        if (Cobol.num(f4_WS_RESP, CS).compareTo(D0) == 0) {
            // MOVE WS-TAG TO OUT-TAG
            Cobol.move(f14_WS_TAG, f39_OUT_TAG, CS);
        }
        // EXEC CICS WEB SEND FROM(WS-OUT) FROMLENGTH(107) MEDIATYPE('text/plain') STATUSCODE(200) STATUSTEXT(WS-STAT) STATUSLEN(2) SRVCONVERT CHARACTERSET('iso-
        int[] web4 = task.webSend(Cobol.text(f17_WS_OUT, CS), 107, "text/plain", 0, 200, Cobol.text(f16_WS_STAT, CS), 2, 1);
        Cobol.store(f69_EIBRESP, BigDecimal.valueOf(web4[0]), false, CS);
        Cobol.store(f70_EIBRESP2, BigDecimal.valueOf(web4[1]), false, CS);
        if (web4[0] != 0) {
            int to = condition(DetCics.condition(web4[0]));
            if (to >= 0) return GOTO | to;
        }
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        return 1;
    }

}
