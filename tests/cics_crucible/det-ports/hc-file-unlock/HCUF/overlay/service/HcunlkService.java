// gitgalaxy-det-port: COBOL HCUNLK (HCUNLK.cbl), translated by rule, statement for statement
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
import com.gitgalaxy.modernized.repository.vsam.*;
import com.gitgalaxy.modernized.repository.vsam.WsRecRepository;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * HCUNLK: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 70, translated 70, holes 0.
 */
@Service
public class HcunlkService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D8 = new BigDecimal("8");
    private static final BigDecimal D0 = new BigDecimal("0");
    private static final BigDecimal D16 = new BigDecimal("16");

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
    private static final byte[] IMAGE_s_WS_LEN = Base64.getDecoder().decode(String.join("",
            "ABA="));
    private static final byte[] IMAGE_s_WS_KEY = Base64.getDecoder().decode(String.join("",
            "ICAgIA=="));
    private static final byte[] IMAGE_s_WS_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_DONE = Base64.getDecoder().decode(String.join("",
            "RE9ORSBPSyA="));
    private static final byte[] IMAGE_s_WS_CLOG = Base64.getDecoder().decode(String.join("",
            "ICAgIFI9MDAgUz0wMDAgRD0gICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_INPUT = new Storage(IMAGE_s_WS_INPUT.length);
    private final Storage s_WS_INLEN = new Storage(IMAGE_s_WS_INLEN.length);
    private final Storage s_WS_MODE = new Storage(IMAGE_s_WS_MODE.length);
    private final Storage s_WS_RESP = new Storage(IMAGE_s_WS_RESP.length);
    private final Storage s_WS_RESP2 = new Storage(IMAGE_s_WS_RESP2.length);
    private final Storage s_WS_LEN = new Storage(IMAGE_s_WS_LEN.length);
    private final Storage s_WS_KEY = new Storage(IMAGE_s_WS_KEY.length);
    private final Storage s_WS_REC = new Storage(IMAGE_s_WS_REC.length);
    private final Storage s_WS_DONE = new Storage(IMAGE_s_WS_DONE.length);
    private final Storage s_WS_CLOG = new Storage(IMAGE_s_WS_CLOG.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_INPUT = Field.alphanumeric(s_WS_INPUT, 0, 8, false);
    private final Field f2_WS_INLEN = Field.binary(s_WS_INLEN, 0, 4, 0, true, false);
    private final Field f3_WS_MODE = Field.alphanumeric(s_WS_MODE, 0, 1, false);
    private final Field f4_WS_RESP = Field.binary(s_WS_RESP, 0, 8, 0, true, false);
    private final Field f5_WS_RESP2 = Field.binary(s_WS_RESP2, 0, 8, 0, true, false);
    private final Field f6_WS_LEN = Field.binary(s_WS_LEN, 0, 4, 0, true, false);
    private final Field f7_WS_KEY = Field.alphanumeric(s_WS_KEY, 0, 4, false);
    private final Field f8_WS_REC = Field.alphanumeric(s_WS_REC, 0, 16, false);
    private final Field f9_WS_DONE = Field.alphanumeric(s_WS_DONE, 0, 8, false);
    private final Field f10_WS_CLOG = Field.group(s_WS_CLOG, 0, 33);
    private final Field f11_CLOG_TAG = Field.alphanumeric(s_WS_CLOG, 0, 3, false);
    private final Field f13_CLOG_RESP = Field.zoned(s_WS_CLOG, 6, 2, 0, false, false, false);
    private final Field f15_CLOG_RESP2 = Field.zoned(s_WS_CLOG, 11, 3, 0, false, false, false);
    private final Field f17_CLOG_DATA = Field.alphanumeric(s_WS_CLOG, 17, 16, false);
    private final Field f19_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f20_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f21_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f22_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f23_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f26_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f47_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f48_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f50_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

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
        return (DetCics.Store<E>) stores.computeIfAbsent(name, n -> switch (n) {
            case "HCUF" -> new DetCics.Store<WsRec>(wsRecRepository::findAll, e -> e.toRecord(CS), b -> WsRec.fromRecord(b, CS), e -> task.write("HCUF", () -> wsRecRepository.save(e)), e -> task.write("HCUF", () -> wsRecRepository.delete(e)), 0, 4, CS).withLengths(CicsTask.recordLengths("WsRec"));
            default -> throw new Hole("CICS file " + n + ": no store in the generated project");
        });
    }

    private static final java.util.Map<String, Integer> PARAGRAPHS = java.util.Map.ofEntries(
            java.util.Map.entry("LOG-W", 8),
            java.util.Map.entry("LOG-R", 7),
            java.util.Map.entry("LOG-D", 6),
            java.util.Map.entry("READ-PARA", 5),
            java.util.Map.entry("SHORT-PARA", 4),
            java.util.Map.entry("NOTHING-PARA", 3),
            java.util.Map.entry("UNLOCK-PARA", 2),
            java.util.Map.entry("REWRITE-PARA", 1),
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


    private final WsRecRepository wsRecRepository;

    public HcunlkService(WsRecRepository wsRecRepository) {
        this.wsRecRepository = wsRecRepository;
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_INPUT, 0, s_WS_INPUT.bytes, 0, IMAGE_s_WS_INPUT.length);
        System.arraycopy(IMAGE_s_WS_INLEN, 0, s_WS_INLEN.bytes, 0, IMAGE_s_WS_INLEN.length);
        System.arraycopy(IMAGE_s_WS_MODE, 0, s_WS_MODE.bytes, 0, IMAGE_s_WS_MODE.length);
        System.arraycopy(IMAGE_s_WS_RESP, 0, s_WS_RESP.bytes, 0, IMAGE_s_WS_RESP.length);
        System.arraycopy(IMAGE_s_WS_RESP2, 0, s_WS_RESP2.bytes, 0, IMAGE_s_WS_RESP2.length);
        System.arraycopy(IMAGE_s_WS_LEN, 0, s_WS_LEN.bytes, 0, IMAGE_s_WS_LEN.length);
        System.arraycopy(IMAGE_s_WS_KEY, 0, s_WS_KEY.bytes, 0, IMAGE_s_WS_KEY.length);
        System.arraycopy(IMAGE_s_WS_REC, 0, s_WS_REC.bytes, 0, IMAGE_s_WS_REC.length);
        System.arraycopy(IMAGE_s_WS_DONE, 0, s_WS_DONE.bytes, 0, IMAGE_s_WS_DONE.length);
        System.arraycopy(IMAGE_s_WS_CLOG, 0, s_WS_CLOG.bytes, 0, IMAGE_s_WS_CLOG.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 8);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f50_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f21_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f23_EIBTRMID, CS);
            Cobol.store(f22_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f20_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f19_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            Cobol.store(f26_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                perform(0, 8);
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
        region.run(task, "HCUNLK", this::runTask);
    }

    public void handleTransaction(String transid, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, null, area);
        region.run(task, "HCUNLK", this::runTask);
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
                if (next >= 9) {
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
            case 8: return p8();
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** MAIN-PARA. */
    private int p0() {
        // EXEC CICS RECEIVE INTO(WS-INPUT) LENGTH(WS-INLEN) END-EXEC
        CicsTask.Received received1 = task.receive(Cobol.num(f2_WS_INLEN, CS).intValue(), false);
        DetCics.received(f1_WS_INPUT, received1.data(), CS);
        Cobol.store(f2_WS_INLEN, BigDecimal.valueOf(received1.length()), false, CS);
        Cobol.store(f47_EIBRESP, BigDecimal.valueOf(DetCics.resp(received1.resp())), false, CS);
        Cobol.store(f48_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(received1.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(received1.resp())));
            if (to >= 0) return GOTO | to;
        }
        // MOVE WS-INPUT(6:1) TO WS-MODE
        Cobol.move(f1_WS_INPUT.ref(6, Integer.valueOf(1)), f3_WS_MODE, CS);
        // EVALUATE WS-MODE
        if ((Cobol.compare(f3_WS_MODE, "R", CS) == 0)) {
            // PERFORM REWRITE-PARA
            perform(1, 1);
        } else if ((Cobol.compare(f3_WS_MODE, "U", CS) == 0)) {
            // PERFORM UNLOCK-PARA
            perform(2, 2);
        } else if ((Cobol.compare(f3_WS_MODE, "N", CS) == 0)) {
            // PERFORM NOTHING-PARA
            perform(3, 3);
        } else if ((Cobol.compare(f3_WS_MODE, "S", CS) == 0)) {
            // PERFORM SHORT-PARA
            perform(4, 4);
        }
        // EXEC CICS SEND TEXT FROM(WS-DONE) LENGTH(8) ERASE END-EXEC
        String text2 = Cobol.text(f9_WS_DONE, CS);
        int[] planned3 = task.planned("SEND-TEXT", "-");
        if (planned3[0] == 0) task.sendText(text2.substring(0, Math.min(text2.length(), 8)), 8, "ERASE");
        Cobol.store(f47_EIBRESP, BigDecimal.valueOf(planned3[0]), false, CS);
        Cobol.store(f48_EIBRESP2, BigDecimal.valueOf(planned3[1]), false, CS);
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

    /** REWRITE-PARA. */
    private int p1() {
        // MOVE 'K002' TO WS-KEY
        Cobol.move("K002", f7_WS_KEY, CS);
        // EXEC CICS READ FILE('HCUF') INTO(WS-REC) LENGTH(WS-LEN) RIDFLD(WS-KEY) UPDATE RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        byte[] rec5 = DetCics.bytes(f7_WS_KEY);
        CicsTask.FileRead<byte[]> read4 = task.readForUpdate("HCUF".stripTrailing(), () -> store("HCUF".stripTrailing()).find(rec5));
        int resp6 = read4.resp();
        int resp27 = read4.resp2();
        if (read4.record() != null) {
            resp6 = DetCics.readInto(f8_WS_REC, read4.record(), Cobol.num(f6_WS_LEN, CS).intValue(), true);
            resp27 = resp6 == 22 ? 11 : 0;
            heldKey.put("HCUF".stripTrailing(), rec5);
            Cobol.store(f6_WS_LEN, BigDecimal.valueOf(read4.record().length), false, CS);
        }
        Cobol.store(f47_EIBRESP, BigDecimal.valueOf(resp6), false, CS);
        Cobol.store(f48_EIBRESP2, BigDecimal.valueOf(resp27), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp6), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(resp27), false, CS);
        // MOVE 'R1 ' TO CLOG-TAG
        Cobol.move("R1 ", f11_CLOG_TAG, CS);
        // PERFORM LOG-D
        perform(6, 6);
        // MOVE '0099' TO WS-REC(13:4)
        Cobol.move("0099", f8_WS_REC.ref(13, Integer.valueOf(4)), CS);
        // EXEC CICS REWRITE FILE('HCUF') FROM(WS-REC) LENGTH(WS-LEN) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int resp8 = task.rewrite("HCUF".stripTrailing(), () -> store("HCUF".stripTrailing()).store(DetCics.bytes(f8_WS_REC, Cobol.num(f6_WS_LEN, CS).intValue())));
        Cobol.store(f47_EIBRESP, BigDecimal.valueOf(resp8), false, CS);
        Cobol.store(f48_EIBRESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp8), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        // MOVE 'R2 ' TO CLOG-TAG
        Cobol.move("R2 ", f11_CLOG_TAG, CS);
        // PERFORM LOG-R
        perform(7, 7);
        // PERFORM READ-PARA
        perform(5, 5);
        // MOVE 'R3 ' TO CLOG-TAG
        Cobol.move("R3 ", f11_CLOG_TAG, CS);
        // PERFORM LOG-D
        perform(6, 6);
        return 2;
    }

    /** UNLOCK-PARA. */
    private int p2() {
        // MOVE 'K002' TO WS-KEY
        Cobol.move("K002", f7_WS_KEY, CS);
        // EXEC CICS READ FILE('HCUF') INTO(WS-REC) LENGTH(WS-LEN) RIDFLD(WS-KEY) UPDATE RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        byte[] rec10 = DetCics.bytes(f7_WS_KEY);
        CicsTask.FileRead<byte[]> read9 = task.readForUpdate("HCUF".stripTrailing(), () -> store("HCUF".stripTrailing()).find(rec10));
        int resp11 = read9.resp();
        int resp212 = read9.resp2();
        if (read9.record() != null) {
            resp11 = DetCics.readInto(f8_WS_REC, read9.record(), Cobol.num(f6_WS_LEN, CS).intValue(), true);
            resp212 = resp11 == 22 ? 11 : 0;
            heldKey.put("HCUF".stripTrailing(), rec10);
            Cobol.store(f6_WS_LEN, BigDecimal.valueOf(read9.record().length), false, CS);
        }
        Cobol.store(f47_EIBRESP, BigDecimal.valueOf(resp11), false, CS);
        Cobol.store(f48_EIBRESP2, BigDecimal.valueOf(resp212), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp11), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(resp212), false, CS);
        // MOVE 'U1 ' TO CLOG-TAG
        Cobol.move("U1 ", f11_CLOG_TAG, CS);
        // PERFORM LOG-D
        perform(6, 6);
        // EXEC CICS UNLOCK FILE('HCUF') RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int resp13 = task.unlock("HCUF".stripTrailing());
        Cobol.store(f47_EIBRESP, BigDecimal.valueOf(resp13), false, CS);
        Cobol.store(f48_EIBRESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp13), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        // MOVE 'U2 ' TO CLOG-TAG
        Cobol.move("U2 ", f11_CLOG_TAG, CS);
        // PERFORM LOG-R
        perform(7, 7);
        // MOVE '0099' TO WS-REC(13:4)
        Cobol.move("0099", f8_WS_REC.ref(13, Integer.valueOf(4)), CS);
        // EXEC CICS REWRITE FILE('HCUF') FROM(WS-REC) LENGTH(WS-LEN) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int resp14 = task.rewrite("HCUF".stripTrailing(), () -> store("HCUF".stripTrailing()).store(DetCics.bytes(f8_WS_REC, Cobol.num(f6_WS_LEN, CS).intValue())));
        Cobol.store(f47_EIBRESP, BigDecimal.valueOf(resp14), false, CS);
        Cobol.store(f48_EIBRESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp14), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        // MOVE 'U3 ' TO CLOG-TAG
        Cobol.move("U3 ", f11_CLOG_TAG, CS);
        // PERFORM LOG-R
        perform(7, 7);
        // PERFORM READ-PARA
        perform(5, 5);
        // MOVE 'U4 ' TO CLOG-TAG
        Cobol.move("U4 ", f11_CLOG_TAG, CS);
        // PERFORM LOG-D
        perform(6, 6);
        return 3;
    }

    /** NOTHING-PARA. */
    private int p3() {
        // EXEC CICS UNLOCK FILE('HCUF') RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int resp15 = task.unlock("HCUF".stripTrailing());
        Cobol.store(f47_EIBRESP, BigDecimal.valueOf(resp15), false, CS);
        Cobol.store(f48_EIBRESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp15), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        // MOVE 'N1 ' TO CLOG-TAG
        Cobol.move("N1 ", f11_CLOG_TAG, CS);
        // PERFORM LOG-R
        perform(7, 7);
        // MOVE 'K001ALPHA 0099' TO WS-REC
        Cobol.move("K001ALPHA   0099", f8_WS_REC, CS);
        // EXEC CICS REWRITE FILE('HCUF') FROM(WS-REC) LENGTH(WS-LEN) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        int resp16 = task.rewrite("HCUF".stripTrailing(), () -> store("HCUF".stripTrailing()).store(DetCics.bytes(f8_WS_REC, Cobol.num(f6_WS_LEN, CS).intValue())));
        Cobol.store(f47_EIBRESP, BigDecimal.valueOf(resp16), false, CS);
        Cobol.store(f48_EIBRESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp16), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(task.resp2()), false, CS);
        // MOVE 'N2 ' TO CLOG-TAG
        Cobol.move("N2 ", f11_CLOG_TAG, CS);
        // PERFORM LOG-R
        perform(7, 7);
        // MOVE 'K001' TO WS-KEY
        Cobol.move("K001", f7_WS_KEY, CS);
        // PERFORM READ-PARA
        perform(5, 5);
        // MOVE 'N3 ' TO CLOG-TAG
        Cobol.move("N3 ", f11_CLOG_TAG, CS);
        // PERFORM LOG-D
        perform(6, 6);
        return 4;
    }

    /** SHORT-PARA. */
    private int p4() {
        // MOVE 'K002' TO WS-KEY
        Cobol.move("K002", f7_WS_KEY, CS);
        // MOVE 8 TO WS-LEN
        Cobol.move(D8, f6_WS_LEN, CS);
        // EXEC CICS READ FILE('HCUF') INTO(WS-REC) LENGTH(WS-LEN) RIDFLD(WS-KEY) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        byte[] rec18 = DetCics.bytes(f7_WS_KEY);
        CicsTask.FileRead<byte[]> read17 = task.read("HCUF".stripTrailing(), () -> store("HCUF".stripTrailing()).find(rec18));
        int resp19 = read17.resp();
        int resp220 = read17.resp2();
        if (read17.record() != null) {
            resp19 = DetCics.readInto(f8_WS_REC, read17.record(), Cobol.num(f6_WS_LEN, CS).intValue(), false);
            resp220 = resp19 == 22 ? 11 : 0;
            Cobol.store(f6_WS_LEN, BigDecimal.valueOf(read17.record().length), false, CS);
        }
        Cobol.store(f47_EIBRESP, BigDecimal.valueOf(resp19), false, CS);
        Cobol.store(f48_EIBRESP2, BigDecimal.valueOf(resp220), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp19), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(resp220), false, CS);
        // MOVE 'S1 ' TO CLOG-TAG
        Cobol.move("S1 ", f11_CLOG_TAG, CS);
        // MOVE SPACES TO CLOG-DATA
        Cobol.moveFigurative(Figurative.SPACES, f17_CLOG_DATA, CS);
        // MOVE WS-RESP TO CLOG-RESP
        Cobol.move(f4_WS_RESP, f13_CLOG_RESP, CS);
        // MOVE 0 TO CLOG-RESP2
        Cobol.move(D0, f15_CLOG_RESP2, CS);
        // EXEC CICS WRITEQ TS QUEUE('HCLOG') FROM(WS-CLOG) LENGTH(33) END-EXEC
        CicsTask.TsResult ts21 = task.writeqTs("HCLOG".strip(), DetCics.toRegion(DetCics.padded(f10_WS_CLOG, 33, "WRITEQ TS", CS), CS, REGION));
        Cobol.store(f47_EIBRESP, BigDecimal.valueOf(DetCics.resp(ts21.resp())), false, CS);
        Cobol.store(f48_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(ts21.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(ts21.resp())));
            if (to >= 0) return GOTO | to;
        }
        // MOVE 16 TO WS-LEN
        Cobol.move(D16, f6_WS_LEN, CS);
        // MOVE SPACES TO WS-REC
        Cobol.moveFigurative(Figurative.SPACES, f8_WS_REC, CS);
        // PERFORM READ-PARA
        perform(5, 5);
        // MOVE 'S2 ' TO CLOG-TAG
        Cobol.move("S2 ", f11_CLOG_TAG, CS);
        // PERFORM LOG-D
        perform(6, 6);
        return 5;
    }

    /** READ-PARA. */
    private int p5() {
        // EXEC CICS READ FILE('HCUF') INTO(WS-REC) LENGTH(WS-LEN) RIDFLD(WS-KEY) RESP(WS-RESP) RESP2(WS-RESP2) END-EXEC
        byte[] rec23 = DetCics.bytes(f7_WS_KEY);
        CicsTask.FileRead<byte[]> read22 = task.read("HCUF".stripTrailing(), () -> store("HCUF".stripTrailing()).find(rec23));
        int resp24 = read22.resp();
        int resp225 = read22.resp2();
        if (read22.record() != null) {
            resp24 = DetCics.readInto(f8_WS_REC, read22.record(), Cobol.num(f6_WS_LEN, CS).intValue(), false);
            resp225 = resp24 == 22 ? 11 : 0;
            Cobol.store(f6_WS_LEN, BigDecimal.valueOf(read22.record().length), false, CS);
        }
        Cobol.store(f47_EIBRESP, BigDecimal.valueOf(resp24), false, CS);
        Cobol.store(f48_EIBRESP2, BigDecimal.valueOf(resp225), false, CS);
        Cobol.store(f4_WS_RESP, BigDecimal.valueOf(resp24), false, CS);
        Cobol.store(f5_WS_RESP2, BigDecimal.valueOf(resp225), false, CS);
        return 6;
    }

    /** LOG-D. */
    private int p6() {
        // MOVE SPACES TO CLOG-DATA
        Cobol.moveFigurative(Figurative.SPACES, f17_CLOG_DATA, CS);
        // IF WS-RESP = 0
        if (Cobol.num(f4_WS_RESP, CS).compareTo(D0) == 0) {
            // MOVE WS-REC TO CLOG-DATA
            Cobol.move(f8_WS_REC, f17_CLOG_DATA, CS);
        }
        // PERFORM LOG-W
        perform(8, 8);
        return 7;
    }

    /** LOG-R. */
    private int p7() {
        // MOVE SPACES TO CLOG-DATA
        Cobol.moveFigurative(Figurative.SPACES, f17_CLOG_DATA, CS);
        // PERFORM LOG-W
        perform(8, 8);
        return 8;
    }

    /** LOG-W. */
    private int p8() {
        // MOVE WS-RESP TO CLOG-RESP
        Cobol.move(f4_WS_RESP, f13_CLOG_RESP, CS);
        // MOVE 0 TO CLOG-RESP2
        Cobol.move(D0, f15_CLOG_RESP2, CS);
        // IF WS-RESP NOT = 0
        if (!(Cobol.num(f4_WS_RESP, CS).compareTo(D0) == 0)) {
            // MOVE WS-RESP2 TO CLOG-RESP2
            Cobol.move(f5_WS_RESP2, f15_CLOG_RESP2, CS);
        }
        // EXEC CICS WRITEQ TS QUEUE('HCLOG') FROM(WS-CLOG) LENGTH(33) END-EXEC
        CicsTask.TsResult ts26 = task.writeqTs("HCLOG".strip(), DetCics.toRegion(DetCics.padded(f10_WS_CLOG, 33, "WRITEQ TS", CS), CS, REGION));
        Cobol.store(f47_EIBRESP, BigDecimal.valueOf(DetCics.resp(ts26.resp())), false, CS);
        Cobol.store(f48_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (DetCics.resp(ts26.resp()) != 0) {
            int to = condition(DetCics.condition(DetCics.resp(ts26.resp())));
            if (to >= 0) return GOTO | to;
        }
        return 9;
    }

}
