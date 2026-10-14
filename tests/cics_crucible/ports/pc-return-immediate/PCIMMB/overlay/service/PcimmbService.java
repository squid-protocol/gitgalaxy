// gitgalaxy-det-port: COBOL PCIMMB (PCIMMB.cbl), translated by rule, statement for statement
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
 * PCIMMB: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 12, translated 12, holes 0.
 */
@Service
public class PcimmbService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;

    private static final byte[] IMAGE_s_WS_CALEN = Base64.getDecoder().decode(String.join("",
            "MDA="));
    private static final byte[] IMAGE_s_WS_BLOG = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICBDPTAw"));
    private static final byte[] IMAGE_s_DFHCOMMAREA = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICA="));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_CALEN = new Storage(IMAGE_s_WS_CALEN.length);
    private final Storage s_WS_BLOG = new Storage(IMAGE_s_WS_BLOG.length);
    private final Storage s_DFHCOMMAREA = new Storage(IMAGE_s_DFHCOMMAREA.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_CALEN = Field.zoned(s_WS_CALEN, 0, 2, 0, false, false, false);
    private final Field f2_WS_BLOG = Field.group(s_WS_BLOG, 0, 15);
    private final Field f3_BLOG_TAG = Field.alphanumeric(s_WS_BLOG, 0, 3, false);
    private final Field f4_BLOG_TEXT = Field.alphanumeric(s_WS_BLOG, 3, 7, false);
    private final Field f6_BLOG_CALEN = Field.zoned(s_WS_BLOG, 13, 2, 0, false, false, false);
    private final Field f7_DFHCOMMAREA = Field.group(s_DFHCOMMAREA, 0, 8);
    private final Field f8_CA_STAGE = Field.alphanumeric(s_DFHCOMMAREA, 0, 1, false);
    private final Field f9_CA_TEXT = Field.alphanumeric(s_DFHCOMMAREA, 1, 7, false);
    private final Field f11_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f12_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f13_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f14_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f15_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f18_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f39_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f40_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f42_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

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
            java.util.Map.entry("LOG-B", 1),
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

    /** #4270 (X23): DFHCOMMAREA's whole record again, with what the task left in its EIBCALEN bytes. */
    private void caWhole(byte[] whole) {
        if (s_DFHCOMMAREA.bytes != whole) {
            System.arraycopy(s_DFHCOMMAREA.bytes, 0, whole, 0, s_DFHCOMMAREA.bytes.length);
            s_DFHCOMMAREA.bytes = whole;
        }
    }



    public PcimmbService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_CALEN, 0, s_WS_CALEN.bytes, 0, IMAGE_s_WS_CALEN.length);
        System.arraycopy(IMAGE_s_WS_BLOG, 0, s_WS_BLOG.bytes, 0, IMAGE_s_WS_BLOG.length);
        System.arraycopy(IMAGE_s_DFHCOMMAREA, 0, s_DFHCOMMAREA.bytes, 0, IMAGE_s_DFHCOMMAREA.length);
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
        return Cobol.num(f42_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f13_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f15_EIBTRMID, CS);
            Cobol.store(f14_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f12_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f11_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (ca instanceof PcimmaWsCa x) {
                in_PcimmaWsCa(x, s_DFHCOMMAREA, 0);
                caBack = () -> fill_PcimmaWsCa(x, s_DFHCOMMAREA, 0);
                calen = cx(task, 8);
            }
            s_DFHCOMMAREA.beyond = null;
            if (ca instanceof byte[] cb0) {
                byte[] cb = DetCics.commareaIn(cb0, CS);
                System.arraycopy(cb, 0, s_DFHCOMMAREA.bytes, 0, Math.min(cb.length, s_DFHCOMMAREA.bytes.length));
                if (cb.length > s_DFHCOMMAREA.bytes.length) {
                    s_DFHCOMMAREA.beyond = java.util.Arrays.copyOfRange(cb, s_DFHCOMMAREA.bytes.length, cb.length);
                }
                calen = cx(task, cb.length);
            }
            byte[] raw = task.linkArea();
            if (raw != null) {
                System.arraycopy(raw, 0, s_DFHCOMMAREA.bytes, 0, Math.min(raw.length, s_DFHCOMMAREA.bytes.length));
                int keep = s_DFHCOMMAREA.bytes.length;
                s_DFHCOMMAREA.beyond = raw.length > keep ? java.util.Arrays.copyOfRange(raw, keep, raw.length) : null;
                Runnable typed = caBack;
                caBack = () -> { typed.run(); System.arraycopy(s_DFHCOMMAREA.bytes, 0, raw, 0, Math.min(raw.length, keep)); if (s_DFHCOMMAREA.beyond != null) { System.arraycopy(s_DFHCOMMAREA.beyond, 0, raw, keep, raw.length - keep); } };
            }
            byte[] caWhole = null;
            if (task.exactCommarea() && calen < s_DFHCOMMAREA.bytes.length) {
                caWhole = s_DFHCOMMAREA.bytes;
                s_DFHCOMMAREA.bytes = java.util.Arrays.copyOf(caWhole, calen);
                Runnable typed = caBack;
                byte[] whole = caWhole;
                caBack = () -> { caWhole(whole); typed.run(); };
            }
            Cobol.store(f18_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                try {
                    perform(0, 1);
                } catch (Goback g) {
                    // RETURN / XCTL / an abend ended the program
                }
            } catch (IndexOutOfBoundsException e) {
                if (caWhole == null) {
                    throw e;
                }
                throw new DetCics.PastFrom("COMMAREA past EIBCALEN (" + calen + " bytes): not modelled");
            } finally {
                if (caWhole != null) {
                    caWhole(caWhole);
                }
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

    public PcimmaWsCa handleTransaction(String transid, PcimmaWsCa request) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "PCIMMB", this::runTask);
        return task.returned(PcimmaWsCa.class);
    }

    public PcimmaWsCa handleTransaction(String transid, PcimmaWsCa request, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request, area);
        region.run(task, "PCIMMB", this::runTask);
        lastAnswerBytes = task.returnedBytes();
        return task.returned(PcimmaWsCa.class);
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
        // MOVE EIBCALEN TO WS-CALEN
        Cobol.move(f18_EIBCALEN, f1_WS_CALEN, CS);
        // MOVE WS-CALEN TO BLOG-CALEN
        Cobol.move(f1_WS_CALEN, f6_BLOG_CALEN, CS);
        // MOVE CA-TEXT TO BLOG-TEXT
        Cobol.move(f9_CA_TEXT, f4_BLOG_TEXT, CS);
        // IF CA-STAGE = '1'
        if (Cobol.compare(f8_CA_STAGE, "1", CS) == 0) {
            // MOVE 'B1 ' TO BLOG-TAG
            Cobol.move("B1 ", f3_BLOG_TAG, CS);
            // PERFORM LOG-B
            perform(1, 1);
            // MOVE '2' TO CA-STAGE
            Cobol.move("2", f8_CA_STAGE, CS);
            // EXEC CICS RETURN TRANSID('PC52') COMMAREA(DFHCOMMAREA) LENGTH(8) END-EXEC
            caBack.run();
            task.returnTransid("PC52".strip(), out_PcimmaWsCa(f7_DFHCOMMAREA.storage(), f7_DFHCOMMAREA.offset()), 8, Cobol.commarea(f7_DFHCOMMAREA, 8).bytes);
            if (true) throw new Goback();
        } else {
            // MOVE 'B2 ' TO BLOG-TAG
            Cobol.move("B2 ", f3_BLOG_TAG, CS);
            // PERFORM LOG-B
            perform(1, 1);
            // EXEC CICS RETURN END-EXEC
            caBack.run();
            task.returnTransid(null, null);
            if (true) throw new Goback();
        }
        return 1;
    }

    /** LOG-B. */
    private int p1() {
        // EXEC CICS WRITEQ TS QUEUE('PCLOG') FROM(WS-BLOG) LENGTH(15) END-EXEC
        CicsTask.TsResult ts1 = task.writeqTs("PCLOG".strip(), DetCics.toRegion(DetCics.bytes(f2_WS_BLOG, DetCics.within(f2_WS_BLOG, 15, "WRITEQ TS")), CS, REGION));
        Cobol.store(f39_EIBRESP, BigDecimal.valueOf(DetCics.resp(ts1.resp())), false, CS);
        Cobol.store(f40_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(ts1.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(ts1.resp())));
            if (to >= 0) return GOTO | to;
        }
        return 2;
    }

}
