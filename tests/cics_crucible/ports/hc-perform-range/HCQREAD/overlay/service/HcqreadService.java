package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.exception.*;
import com.gitgalaxy.modernized.messaging.TempStorage;
import java.nio.charset.Charset;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * the RESP of READQ at line 41 (paragraph MAIN-PARA) is never tested: it is only moved to WS-RESP-D
 * and appended to the trail, never branched on (kept as the original does it).
 *
 * Port of HCQREAD (transaction HC01). The CICS temporary storage commands go through the task
 * (CicsTask.readqTs / writeqTs, #4002), which report QIDERR / ITEMERR / LENGERR and the LENGTH set,
 * so that HANDLE CONDITION, IGNORE CONDITION and RESP behave as under CICS. The HANDLE CONDITION
 * labels are GO TOs: the paragraphs fall through into each other and return to the PERFORM ... THRU
 * only when control reaches READ-ITEMS-EXIT while that PERFORM is active.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class HcqreadService {

    private static final Logger log = LoggerFactory.getLogger(HcqreadService.class);

    /** The region's EBCDIC code page: TS items are the bytes the program wrote (#4002). */
    private static final Charset EBCDIC = Charset.forName("IBM037");

    /** The program's working storage and handler table of the task running on this thread. */
    private static final ThreadLocal<Run> CURRENT = new ThreadLocal<>();

    private final TempStorage tempStorage;

    public void executeHcqread(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for HCQREAD");
        // HCQREAD is a CICS program (transaction HC01, group CRUCHC1): it has no batch or COMMAREA
        // interface, so a call from the controller runs one HC01 task with no COMMAREA.
        handleTransaction("HC01");
    }

    /** A CICS transaction entered the program: one task, no COMMAREA (EIBCALEN = 0), ENTER. */
    public void handleTransaction(String transid) {
        log.info("Hcqread: handleTransaction");
        CicsTask task = new CicsTask(transid, "ENTER", null, null);
        runTask(task);
        log.info("Hcqread: task {} ended after {} CICS commands", transid, task.events().size());
    }

    /** One task of this program (#3754): the PROCEDURE DIVISION from MAIN-PARA. */
    public void runTask(CicsTask task) {
        log.info("Hcqread: runTask");
        Run run = new Run(task);
        Run outer = CURRENT.get();
        CURRENT.set(run);
        try {
            mainPara(run);
        } finally {
            if (outer == null) {
                CURRENT.remove();
            } else {
                CURRENT.set(outer);
            }
        }
    }

    /**
     * EXEC CICS HANDLE CONDITION at src/HCQREAD.cbl:25 (paragraph MAIN-PARA) routes QIDERR to NO-QUEUE.
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     */
    public void onConditionQiderrL25(CicsConditionException e) {
        log.info("HANDLE CONDITION QIDERR LABEL NO-QUEUE at line 25", e);
        // GO TO NO-QUEUE: falls through PAST-END to READ-ITEMS-EXIT
        runFrom(current(), Label.NO_QUEUE);
    }

    /**
     * EXEC CICS HANDLE CONDITION at src/HCQREAD.cbl:25 (paragraph MAIN-PARA) routes ITEMERR to PAST-END.
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     */
    public void onConditionItemerrL25(CicsConditionException e) {
        log.info("HANDLE CONDITION ITEMERR LABEL PAST-END at line 25", e);
        // GO TO PAST-END: falls through to READ-ITEMS-EXIT
        runFrom(current(), Label.PAST_END);
    }

    /**
     * EXEC CICS HANDLE CONDITION at src/HCQREAD.cbl:25 (paragraph MAIN-PARA) routes ERROR to ANY-ERROR.
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     */
    public void onConditionErrorL25(CicsConditionException e) {
        log.info("HANDLE CONDITION ERROR LABEL ANY-ERROR at line 25", e);
        // GO TO ANY-ERROR: falls through to SEND-TRAIL, which ends the task
        runFrom(current(), Label.ANY_ERROR);
    }

    /**
     * EXEC CICS HANDLE CONDITION at src/HCQREAD.cbl:56 (paragraph MAIN-PARA) routes ITEMERR to LATE-ITEM.
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     */
    public void onConditionItemerrL56(CicsConditionException e) {
        log.info("HANDLE CONDITION ITEMERR LABEL LATE-ITEM at line 56", e);
        // GO TO LATE-ITEM: then GO TO SEND-TRAIL, which ends the task
        runFrom(current(), Label.LATE_ITEM);
    }

    /** EXEC CICS WRITEQ TS QUEUE('HCWORK') FROM(WS-ONE) at src/HCQREAD.cbl:37 (#3620).
     *  CICS resources field testing: open (5 public / 0 private estates). */
    protected int writeqTsHcworkL37(String record) {
        return tempStorage.writeItem("HCWORK", record);
    }

    /** EXEC CICS READQ TS QUEUE('HCWORK') INTO(WS-ITEM) ITEM(2) at src/HCQREAD.cbl:41 (#3620).
     *  CICS resources field testing: open (5 public / 0 private estates). */
    protected Optional<String> readqTsHcworkL41() {
        return tempStorage.readItem("HCWORK", 2);
    }

    /** EXEC CICS READQ TS QUEUE('HCWORK') INTO(WS-ITEM) ITEM(3) at src/HCQREAD.cbl:49 (#3620).
     *  CICS resources field testing: open (5 public / 0 private estates). */
    protected Optional<String> readqTsHcworkL49() {
        return tempStorage.readItem("HCWORK", 3);
    }

    /** EXEC CICS READQ TS QUEUE('HCWORK') INTO(WS-ITEM) ITEM(4) at src/HCQREAD.cbl:57 (#3620).
     *  CICS resources field testing: open (5 public / 0 private estates). */
    protected Optional<String> readqTsHcworkL57() {
        return tempStorage.readItem("HCWORK", 4);
    }

    /** EXEC CICS READQ TS QUEUE('HCQ1') INTO(WS-ITEM) ITEM(WS-N) at src/HCQREAD.cbl:65 (#3620).
     *  CICS resources field testing: open (5 public / 0 private estates). */
    protected Optional<String> readqTsHcq1L65(int item) {
        return tempStorage.readItem("HCQ1", item);
    }

    // ------------------------------------------------------------------------------------------
    // PROCEDURE DIVISION
    // ------------------------------------------------------------------------------------------

    /** MAIN-PARA (lines 24-62). */
    private void mainPara(Run run) {
        Ws ws = run.ws;
        CicsTask task = run.task;

        // EXEC CICS HANDLE CONDITION QIDERR(NO-QUEUE) ITEMERR(PAST-END) ERROR(ANY-ERROR) (line 25)
        run.handle("QIDERR", Label.NO_QUEUE);
        run.handle("ITEMERR", Label.PAST_END);
        run.handle("ERROR", Label.ANY_ERROR);

        // STRING 'm' DELIMITED BY SIZE INTO WS-TRAIL WITH POINTER WS-PTR (line 29)
        string(ws, "m");

        // MOVE 8 TO WS-ILEN (line 32)
        // DEFECT kept: WS-ILEN is set once, before the loop, and never reset; READQ's LENGTH is
        // input (maximum) and output (the item's length), so a short item shrinks the maximum and a
        // later longer item raises LENGERR (-> ANY-ERROR). Fix: MOVE 8 TO WS-ILEN before each READQ.
        ws.ilen = 8;

        // PERFORM READ-ITEMS THRU READ-ITEMS-EXIT (line 33)
        if (!performReadItemsThruReadItemsExit(run)) {
            return; // control left the range (GO TO ANY-ERROR -> SEND-TRAIL): the task has ended
        }

        // STRING 'b' ... (line 34)
        string(ws, "b");

        // EXEC CICS WRITEQ TS QUEUE('HCWORK') FROM(WS-ONE) LENGTH(1) (line 37)
        CicsTask.TsResult written = task.writeqTs("HCWORK", Arrays.copyOf(ws.one, 1));
        Label to = run.raise(written.resp());
        if (to != null) {
            runFrom(run, to);
            return;
        }

        // EXEC CICS READQ TS QUEUE('HCWORK') INTO(WS-ITEM) LENGTH(WS-ILEN) ITEM(2) RESP(WS-RESP) (line 41)
        // RESP: no handler is taken, whatever the condition; control falls through.
        CicsTask.TsResult r2 = task.readqTs("HCWORK", 2, ws.ilen);
        readInto(ws, r2);
        ws.resp = run.respond(r2.resp());
        // DEFECT kept (unchecked response): WS-RESP is never tested, only shown in the trail.
        // Fix: IF WS-RESP NOT = DFHRESP(NORMAL) ... after the READQ.

        // MOVE WS-RESP TO WS-RESP-D (line 44)
        ws.respD = moveToPic99(ws.resp);
        // STRING 'r' WS-RESP-D ... (line 45)
        string(ws, "r" + pic99(ws.respD));

        // EXEC CICS IGNORE CONDITION ITEMERR (line 48)
        run.ignore("ITEMERR");

        // EXEC CICS READQ TS QUEUE('HCWORK') INTO(WS-ITEM) LENGTH(WS-ILEN) ITEM(3) (line 49)
        CicsTask.TsResult r3 = task.readqTs("HCWORK", 3, ws.ilen);
        readInto(ws, r3);
        to = run.raise(r3.resp());
        if (to != null) {
            runFrom(run, to);
            return;
        }

        // MOVE EIBRESP TO WS-RESP-D (line 52): an ignored ITEMERR still leaves EIBRESP = 26
        ws.respD = moveToPic99(ws.eibresp);
        // STRING 'i' WS-RESP-D ... (line 53)
        string(ws, "i" + pic99(ws.respD));

        // EXEC CICS HANDLE CONDITION ITEMERR(LATE-ITEM) (line 56): overrides the IGNORE
        run.handle("ITEMERR", Label.LATE_ITEM);

        // EXEC CICS READQ TS QUEUE('HCWORK') INTO(WS-ITEM) LENGTH(WS-ILEN) ITEM(4) (line 57)
        CicsTask.TsResult r4 = task.readqTs("HCWORK", 4, ws.ilen);
        readInto(ws, r4);
        to = run.raise(r4.resp());
        if (to != null) {
            runFrom(run, to);
            return;
        }

        // STRING 'x' ... (line 60)
        string(ws, "x");
        // GO TO SEND-TRAIL (line 62)
        sendTrail(run);
    }

    /**
     * PERFORM READ-ITEMS THRU READ-ITEMS-EXIT: true when control reaches the end of READ-ITEMS-EXIT
     * and returns to MAIN-PARA, false when a GO TO took it out of the range and the task ended.
     */
    private boolean performReadItemsThruReadItemsExit(Run run) {
        boolean outer = run.performActive;
        run.performActive = true;
        try {
            return readItems(run);
        } finally {
            run.performActive = outer;
        }
    }

    /** READ-ITEMS (lines 63-72), falling through NO-QUEUE, PAST-END and READ-ITEMS-EXIT. */
    private boolean readItems(Run run) {
        Ws ws = run.ws;
        // PERFORM VARYING WS-N FROM 1 BY 1 UNTIL WS-N > 5 (line 64)
        for (ws.n = 1; ws.n <= 5; ws.n++) {
            // EXEC CICS READQ TS QUEUE('HCQ1') INTO(WS-ITEM) LENGTH(WS-ILEN) ITEM(WS-N) (line 65)
            CicsTask.TsResult r = run.task.readqTs("HCQ1", ws.n, ws.ilen);
            readInto(ws, r);
            Label to = run.raise(r.resp());
            if (to != null) {
                return runFrom(run, to); // GO TO the handler's label, out of the inline PERFORM
            }
            // STRING WS-ITEM(1:1) DELIMITED BY SIZE INTO WS-TRAIL WITH POINTER WS-PTR (line 68)
            string(ws, new String(ws.item, 0, 1, EBCDIC));
        }
        // STRING 'l' ... (line 71)
        string(ws, "l");
        // DEFECT kept: READ-ITEMS falls through into NO-QUEUE and PAST-END, so a clean loop
        // leaves "lqp" in the trail though no condition was raised.
        // Fix: GO TO READ-ITEMS-EXIT after the STRING 'l'.
        return runFrom(run, Label.NO_QUEUE);
    }

    /**
     * Control transferred (GO TO, or fall-through) to a label: runs the paragraphs from there in
     * source order. True when it returns to the active PERFORM at the end of READ-ITEMS-EXIT; false
     * when the task ended (SEND-TRAIL's RETURN, or a default-action abend).
     */
    private boolean runFrom(Run run, Label start) {
        Ws ws = run.ws;
        Label at = start;
        if (at == Label.ABENDED) {
            return false;
        }
        if (at == Label.NO_QUEUE) {
            // NO-QUEUE (lines 73-75)
            // DEFECT kept: falls through into PAST-END, so QIDERR leaves "qp".
            // Fix: GO TO READ-ITEMS-EXIT at the end of NO-QUEUE.
            string(ws, "q");
            at = Label.PAST_END;
        }
        if (at == Label.PAST_END) {
            // PAST-END (lines 76-78)
            string(ws, "p");
            at = Label.READ_ITEMS_EXIT;
        }
        if (at == Label.READ_ITEMS_EXIT) {
            // READ-ITEMS-EXIT. EXIT. (lines 79-80): the end of the PERFORM ... THRU range
            if (run.performActive) {
                return true;
            }
            // No PERFORM active (a handler reached from MAIN-PARA after the PERFORM): control falls
            // through into LATE-ITEM.
            at = Label.LATE_ITEM;
        }
        if (at == Label.LATE_ITEM) {
            // LATE-ITEM (lines 81-84)
            string(ws, "t");
            // GO TO SEND-TRAIL
            sendTrail(run);
            return false;
        }
        if (at == Label.ANY_ERROR) {
            // ANY-ERROR (lines 85-88): outside the PERFORM range
            // DEFECT kept: a condition caught here during READ-ITEMS abandons the PERFORM and the rest
            // of MAIN-PARA (no 'b', no HCWORK write). Fix: GO TO READ-ITEMS-EXIT from a paragraph in the range.
            // MOVE EIBRESP TO WS-RESP-D
            ws.respD = moveToPic99(ws.eibresp);
            // STRING 'e' WS-RESP-D ...
            string(ws, "e" + pic99(ws.respD));
            // falls through into SEND-TRAIL
            sendTrail(run);
            return false;
        }
        throw new IllegalStateException("HCQREAD: no paragraph for label " + at);
    }

    /** SEND-TRAIL (lines 89-92). */
    private void sendTrail(Run run) {
        // EXEC CICS SEND TEXT FROM(WS-TRAIL) LENGTH(40) ERASE
        run.task.sendText(new String(run.ws.trail), 40, "ERASE");
        run.eibresp(0);
        // EXEC CICS RETURN
        run.task.returnTransid(null, null);
    }

    // ------------------------------------------------------------------------------------------
    // Storage semantics
    // ------------------------------------------------------------------------------------------

    /**
     * READQ TS INTO(WS-ITEM) LENGTH(WS-ILEN): the data moved over the first bytes of WS-ITEM (the
     * rest keeps its content); LENGTH is set to the item's own length on NORMAL and LENGERR.
     */
    private static void readInto(Ws ws, CicsTask.TsResult r) {
        if (r.data() != null) {
            // WS-ITEM is PIC X(8): a LENGTH above 8 would overlay the storage after it under CICS;
            // only WS-ITEM's own 8 bytes are kept here.
            int n = Math.min(r.data().length, ws.item.length);
            System.arraycopy(r.data(), 0, ws.item, 0, n);
        }
        if (r.length() >= 0) {
            ws.ilen = r.length(); // PIC S9(4) COMP: an item is at most 32763 bytes
        }
    }

    /** STRING ... DELIMITED BY SIZE INTO WS-TRAIL WITH POINTER WS-PTR (no ON OVERFLOW). */
    private static void string(Ws ws, String source) {
        if (ws.ptr < 1 || ws.ptr > ws.trail.length) {
            return; // overflow before any transfer: nothing moved, WS-PTR unchanged
        }
        for (int i = 0; i < source.length(); i++) {
            if (ws.ptr > ws.trail.length) {
                return; // overflow: the rest is not moved
            }
            ws.trail[ws.ptr - 1] = source.charAt(i);
            ws.ptr++;
        }
    }

    /** MOVE (S9(8) COMP or EIBRESP) TO PIC 99: the sign and the high-order digits are lost. */
    private static int moveToPic99(long value) {
        return (int) (Math.abs(value) % 100);
    }

    /** PIC 99 DISPLAY as its two digit characters. */
    private static String pic99(int value) {
        return String.format(Locale.ROOT, "%02d", value);
    }

    /** DFHRESP value of a condition, as EIBRESP / RESP hold it. */
    private static int dfhresp(String condition) {
        return switch (condition) {
            case "NORMAL" -> 0;
            case "ERROR" -> 1;
            case "NOTFND" -> 13;
            case "INVREQ" -> 16;
            case "NOSPACE" -> 18;
            case "LENGERR" -> 22;
            case "ITEMERR" -> 26;
            case "QIDERR" -> 44;
            default -> throw new IllegalArgumentException("HCQREAD: no DFHRESP value for " + condition);
        };
    }

    private static Run current() {
        Run run = CURRENT.get();
        if (run == null) {
            throw new IllegalStateException("HCQREAD handler label reached outside a HCQREAD task");
        }
        return run;
    }

    // ------------------------------------------------------------------------------------------
    // Working storage and the task's HANDLE / IGNORE CONDITION table
    // ------------------------------------------------------------------------------------------

    /** The paragraphs a HANDLE CONDITION (or fall-through) can transfer control to. */
    private enum Label {
        NO_QUEUE, PAST_END, READ_ITEMS_EXIT, LATE_ITEM, ANY_ERROR,
        /** No handler and no IGNORE: CICS's default action abended the task. */
        ABENDED
    }

    /** WORKING-STORAGE SECTION (lines 15-22), fresh for each task. */
    private static final class Ws {
        final char[] trail = spaces(40);                 // WS-TRAIL PIC X(40) VALUE SPACES
        int ptr = 1;                                     // WS-PTR PIC S9(4) COMP VALUE 1
        final byte[] item = ebcdicSpaces(8);             // WS-ITEM PIC X(8) VALUE SPACES
        int ilen = 0;                                    // WS-ILEN PIC S9(4) COMP VALUE 0
        int n = 0;                                       // WS-N PIC S9(4) COMP VALUE 0
        final byte[] one = "W".getBytes(EBCDIC);         // WS-ONE PIC X VALUE 'W'
        int resp = 0;                                    // WS-RESP PIC S9(8) COMP VALUE 0
        int respD = 0;                                   // WS-RESP-D PIC 99 VALUE 0
        int eibresp = 0;                                 // EIBRESP

        private static char[] spaces(int n) {
            char[] c = new char[n];
            Arrays.fill(c, ' ');
            return c;
        }

        private static byte[] ebcdicSpaces(int n) {
            byte[] b = new byte[n];
            Arrays.fill(b, (byte) 0x40);
            return b;
        }
    }

    /** One task's state: its working storage, its handler table and whether the PERFORM is active. */
    private static final class Run {
        final CicsTask task;
        final Ws ws = new Ws();
        final Map<String, Label> handlers = new HashMap<>();
        final Set<String> ignored = new HashSet<>();
        boolean performActive;

        Run(CicsTask task) {
            this.task = task;
        }

        void eibresp(int value) {
            ws.eibresp = value;
        }

        /** HANDLE CONDITION condition(label): replaces any earlier HANDLE or IGNORE of it. */
        void handle(String condition, Label label) {
            ignored.remove(condition);
            handlers.put(condition, label);
            eibresp(0);
        }

        /** IGNORE CONDITION condition: replaces any earlier HANDLE of it. */
        void ignore(String condition) {
            handlers.remove(condition);
            ignored.add(condition);
            eibresp(0);
        }

        /** A command with RESP: EIBRESP and the RESP value are set, no handler is taken. */
        int respond(String resp) {
            int code = dfhresp(resp);
            eibresp(code);
            return code;
        }

        /**
         * A command without RESP: EIBRESP is set; null to go on, else the label control goes to --
         * the condition's own HANDLE, none when IGNOREd, else the ERROR handler, else CICS's
         * default action (an abend of the task).
         */
        Label raise(String resp) {
            eibresp(dfhresp(resp));
            if ("NORMAL".equals(resp) || ignored.contains(resp)) {
                return null;
            }
            Label label = handlers.get(resp);
            if (label == null) {
                label = handlers.get("ERROR");
            }
            if (label == null) {
                task.abendOnCondition(resp);
                return Label.ABENDED;
            }
            return label;
        }
    }
}
