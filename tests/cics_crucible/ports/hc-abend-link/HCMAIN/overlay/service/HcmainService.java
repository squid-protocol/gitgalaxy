package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.HcsubDfhcommarea;
import com.gitgalaxy.modernized.exception.*;
import com.gitgalaxy.modernized.messaging.TempStorage;
import java.nio.charset.Charset;
import java.util.ArrayDeque;
import java.util.Arrays;
import java.util.Deque;
import java.util.Optional;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
@RequiredArgsConstructor
public class HcmainService {

    private static final Logger log = LoggerFactory.getLogger(HcmainService.class);

    /** PROGRAM-ID. HCMAIN. */
    private static final String PROGRAM = "HCMAIN";
    /** The transaction the CSD (group CRUCHC2) defines for HCMAIN. */
    private static final String TRANSID = "HC02";
    /** EXEC CICS LINK PROGRAM('HCSUB'). */
    private static final String HCSUB = "HCSUB";
    /** HANDLE ABEND LABEL(MAIN-ABEND). */
    private static final String MAIN_ABEND = "MAIN-ABEND";

    /** The region's EBCDIC code page for TS items (#4002). */
    private static final Charset EBCDIC = Charset.forName("IBM037");

    /** WORKING-STORAGE with no VALUE clause (WS-CA) starts as binary zeros (low-values). */
    private static final char LOW_VALUE = '\u0000';

    /** The HCMAIN task in progress on this thread, so the HANDLE CONDITION / HANDLE ABEND entry points
     *  below can run their paragraph on the task's own WORKING-STORAGE. */
    private static final ThreadLocal<Ws> CURRENT = new ThreadLocal<>();

    private final ObjectProvider<HcsubService> hcsubService;
    private final TempStorage tempStorage;

    // =====================================================================================
    // WORKING-STORAGE SECTION (one copy per task: CICS gives every task its own)
    // =====================================================================================
    private static final class Ws {
        final CicsTask task;
        // 01 WS-TRAIL PIC X(40) VALUE SPACES.
        final char[] trail = filled(40, ' ');
        // 01 WS-PTR PIC S9(4) COMP VALUE 1.
        int ptr = 1;
        // 01 WS-MODE PIC X VALUE SPACE.
        char mode = ' ';
        // 01 WS-MLEN PIC S9(4) COMP VALUE 1.
        int mlen = 1;
        // 01 WS-JUNK PIC X(8) VALUE SPACES.
        final char[] junk = filled(8, ' ');
        // 01 WS-JLEN PIC S9(4) COMP VALUE 8.
        int jlen = 8;
        // 01 WS-ABCODE PIC X(4) VALUE SPACES.
        String abcode = "    ";
        // 01 WS-CA. COPY HCLINKCA. (20 bytes, no VALUE clauses: binary zeros until INITIALIZE)
        final HcsubDfhcommarea ca = new HcsubDfhcommarea();

        // HANDLE CONDITION state of this program (the program's own; HANDLE ABEND is the task's)
        boolean qiderrHandler;                               // HANDLE CONDITION QIDERR(MAIN-QIDERR)
        final Deque<Boolean> pushed = new ArrayDeque<>();    // PUSH HANDLE / POP HANDLE
        boolean ended;                                       // RETURN issued / task terminated

        Ws(CicsTask task) {
            this.task = task;
            ca.setCaMode(String.valueOf(filled(1, LOW_VALUE)));
            ca.setCaTrail(String.valueOf(filled(9, LOW_VALUE)));
            ca.setCaResult(String.valueOf(filled(4, LOW_VALUE)));
            ca.setCaCount(0);
            ca.setCaSpare(String.valueOf(filled(4, LOW_VALUE)));
        }
    }

    /** Where control goes after a CICS command. */
    private enum Flow { CONTINUE, TO_MAIN_QIDERR, TO_MAIN_ABEND, TERMINATED }

    // =====================================================================================
    // Entry points
    // =====================================================================================

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public void handleTransaction(String transid) {
        log.info("Hcmain: handleTransaction");
    }

    /** One task of HC02 (#3754). HCMAIN takes no COMMAREA and reads no map; it reads TS, LINKs, sends
     *  its trail as text and returns. */
    public void runTask(CicsTask task) {
        log.info("Hcmain: runTask");
        Ws ws = new Ws(task);
        Ws outer = CURRENT.get();
        CURRENT.set(ws);
        try {
            switch (mainPara(ws)) {
                case CONTINUE -> sendTrail(ws);                          // GO TO SEND-TRAIL
                // the HANDLE CONDITION of line 25 takes QIDERR: MAIN-QIDERR, GO TO SEND-TRAIL
                case TO_MAIN_QIDERR -> onConditionQiderrL25(
                        new CicsConditionException("QIDERR", PROGRAM, "src/HCMAIN.cbl:25"));
                // the HANDLE ABEND exit of line 26 takes the abend: MAIN-ABEND falls into SEND-TRAIL
                case TO_MAIN_ABEND -> onAbendL26(new CicsAbendException(task.abcode(), PROGRAM, "src/HCMAIN.cbl:26"));
                case TERMINATED -> { /* the task was abended and no exit of this program took it */ }
            }
        } finally {
            if (outer == null) {
                CURRENT.remove();
            } else {
                CURRENT.set(outer);
            }
        }
    }

    /** EXEC CICS LINK PROGRAM(HCSUB) at src/HCMAIN.cbl:47.
     *  Call targets field testing: open (6 public / 0 private estates).
     *  WS-CA is COPY HCLINKCA, the same 20-byte layout HCSUB declares as DFHCOMMAREA (the skeleton's
     *  "4 bytes" for WS-CA does not see the copybook), so the DTO is passed as it is. */
    public HcsubDfhcommarea linkHcsub(HcsubDfhcommarea request) {
        return hcsubService.getObject().handleLink(request);
    }

    /**
     * EXEC CICS HANDLE CONDITION at src/HCMAIN.cbl:25 (paragraph MAIN-PARA) routes QIDERR to MAIN-QIDERR.
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * runTask ports the transfer as control flow; this entry point runs the same paragraphs for a caller
     * that reports the condition on the task in progress.
     */
    public void onConditionQiderrL25(CicsConditionException e) {
        log.info("HANDLE CONDITION QIDERR LABEL MAIN-QIDERR at line 25", e);
        Ws ws = CURRENT.get();
        if (ws == null || ws.ended) {
            log.warn("HCMAIN: QIDERR handler entered with no HCMAIN task in progress");
            return;
        }
        mainQiderr(ws);     // MAIN-QIDERR
        sendTrail(ws);      // GO TO SEND-TRAIL
    }

    /**
     * EXEC CICS HANDLE ABEND at src/HCMAIN.cbl:26 (paragraph MAIN-PARA) routes abends to MAIN-ABEND.
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * runTask ports the transfer as control flow (task.abendOnCondition / task.abendExit); this entry
     * point runs the same paragraphs for the task in progress.
     */
    public void onAbendL26(CicsAbendException e) {
        log.info("HANDLE ABEND LABEL MAIN-ABEND at line 26", e);
        Ws ws = CURRENT.get();
        if (ws == null || ws.ended) {
            log.warn("HCMAIN: abend exit entered with no HCMAIN task in progress");
            return;
        }
        mainAbend(ws);      // MAIN-ABEND
        sendTrail(ws);      // falls into SEND-TRAIL
    }

    /** EXEC CICS READQ TS QUEUE('HCMODE') INTO(WS-MODE) ITEM(1) at src/HCMAIN.cbl:27 (#3620).
     *  CICS resources field testing: open (5 public / 0 private estates). */
    protected Optional<String> readqTsHcmodeL27() {
        return tempStorage.readItem("HCMODE", 1);
    }

    /** EXEC CICS READQ TS QUEUE('HCNONE') INTO(WS-JUNK) ITEM(1) at src/HCMAIN.cbl:37 (#3620).
     *  CICS resources field testing: open (5 public / 0 private estates). */
    protected Optional<String> readqTsHcnoneL37() {
        return tempStorage.readItem("HCNONE", 1);
    }

    /** EXEC CICS READQ TS QUEUE('HCNONE') INTO(WS-JUNK) ITEM(1) at src/HCMAIN.cbl:54 (#3620).
     *  CICS resources field testing: open (5 public / 0 private estates). */
    protected Optional<String> readqTsHcnoneL54() {
        return tempStorage.readItem("HCNONE", 1);
    }

    // =====================================================================================
    // PROCEDURE DIVISION
    // =====================================================================================

    /** MAIN-PARA (lines 24-59). */
    private Flow mainPara(Ws ws) {
        CicsTask task = ws.task;

        // EXEC CICS HANDLE CONDITION QIDERR(MAIN-QIDERR) END-EXEC            (line 25)
        ws.qiderrHandler = true;
        // EXEC CICS HANDLE ABEND LABEL(MAIN-ABEND) END-EXEC                  (line 26)
        // The task holds the exit, so an abend in HCSUB (the level below) finds it (#3989).
        task.handleAbend(MAIN_ABEND);

        // EXEC CICS READQ TS QUEUE('HCMODE') INTO(WS-MODE) LENGTH(WS-MLEN) ITEM(1)   (lines 27-29)
        CicsTask.TsResult mode = task.readqTs("HCMODE", 1, ws.mlen);
        if (mode.length() >= 0) {
            ws.mlen = mode.length();                 // LENGTH is set to the item's own length
        }
        if (mode.data() != null && mode.data().length > 0) {
            ws.mode = decode(mode.data()).charAt(0); // INTO WS-MODE (PIC X): the first byte
        }
        Flow flow = condition(ws, mode.resp());
        if (flow != Flow.CONTINUE) {
            return flow;
        }

        // STRING 'm' DELIMITED BY SIZE INTO WS-TRAIL WITH POINTER WS-PTR    (lines 30-31)
        string(ws, "m");

        // IF WS-MODE = 'P' OR WS-MODE = 'O'                                  (line 32)
        if (ws.mode == 'P' || ws.mode == 'O') {
            // EXEC CICS PUSH HANDLE END-EXEC                                 (line 33)
            pushHandle(ws);
            // STRING 'u' ...                                                 (lines 34-35)
            string(ws, "u");
            // IF WS-MODE = 'P'                                               (line 36)
            if (ws.mode == 'P') {
                // EXEC CICS READQ TS QUEUE('HCNONE') INTO(WS-JUNK) LENGTH(WS-JLEN) ITEM(1)  (lines 37-39)
                // Handlers suspended: a QIDERR here takes CICS's default action (AEYH), and the suspended
                // abend exit does not take it.
                flow = readqHcnone(ws);
                if (flow != Flow.CONTINUE) {
                    return flow;
                }
            }
            // EXEC CICS POP HANDLE END-EXEC                                  (line 41)
            popHandle(ws);
            // STRING 'o' ...                                                 (lines 42-43)
            string(ws, "o");
        } else {
            // INITIALIZE WS-CA                                               (line 45)
            ws.ca.setCaMode(" ");
            ws.ca.setCaTrail("         ");
            ws.ca.setCaResult("    ");
            ws.ca.setCaCount(0);
            ws.ca.setCaSpare("    ");
            // MOVE WS-MODE TO CA-MODE                                        (line 46)
            ws.ca.setCaMode(String.valueOf(ws.mode));
            // EXEC CICS LINK PROGRAM('HCSUB') COMMAREA(WS-CA) LENGTH(20)     (lines 47-49)
            flow = linkHcsubL47(ws);
            if (flow != Flow.CONTINUE) {
                return flow;
            }
            // STRING 'r' CA-TRAIL(1:3) CA-RESULT DELIMITED BY SIZE INTO WS-TRAIL WITH POINTER WS-PTR (50-51)
            string(ws, "r", pic(ws.ca.getCaTrail(), 9).substring(0, 3), pic(ws.ca.getCaResult(), 4));
        }

        // The QIDERR handler is in force again here
        // EXEC CICS READQ TS QUEUE('HCNONE') INTO(WS-JUNK) LENGTH(WS-JLEN) ITEM(1)  (lines 54-56)
        // (WS-JLEN is not reset: after a successful read at line 37 it holds that item's length -- see notes)
        flow = readqHcnone(ws);
        if (flow != Flow.CONTINUE) {
            return flow;
        }
        // STRING 'x' ...                                                     (lines 57-58)
        string(ws, "x");
        // GO TO SEND-TRAIL                                                   (line 59)
        return Flow.CONTINUE;
    }

    /** MAIN-QIDERR (lines 60-63): STRING 'q' ...; the caller then does GO TO SEND-TRAIL. */
    private void mainQiderr(Ws ws) {
        string(ws, "q");
    }

    /** MAIN-ABEND (lines 64-67); it falls through into SEND-TRAIL. */
    private void mainAbend(Ws ws) {
        // EXEC CICS ASSIGN ABCODE(WS-ABCODE) END-EXEC                        (line 65)
        ws.abcode = pic(ws.task.abcode(), 4);
        // STRING 'X' WS-ABCODE 'c' CA-TRAIL(1:3) DELIMITED BY SIZE INTO WS-TRAIL WITH POINTER WS-PTR (66-67)
        // DEFECT kept: when the abend comes before the LINK path (e.g. LENGERR on the HCMODE read), WS-CA was
        // never INITIALIZEd and CA-TRAIL(1:3) is its initial binary zeros.
        // Fix: INITIALIZE WS-CA at the start of MAIN-PARA.
        string(ws, "X", ws.abcode, "c", pic(ws.ca.getCaTrail(), 9).substring(0, 3));
    }

    /** SEND-TRAIL (lines 68-71). */
    private void sendTrail(Ws ws) {
        if (ws.ended) {
            return;
        }
        // EXEC CICS SEND TEXT FROM(WS-TRAIL) LENGTH(40) ERASE END-EXEC       (lines 69-70)
        ws.task.sendText(new String(ws.trail), 40, "ERASE");
        // EXEC CICS RETURN END-EXEC                                          (line 71)
        ws.task.returnTransid(null, null);
        ws.ended = true;
    }

    // =====================================================================================
    // CICS commands and their conditions
    // =====================================================================================

    /** READQ TS QUEUE('HCNONE') INTO(WS-JUNK) LENGTH(WS-JLEN) ITEM(1) (lines 37 and 54). */
    private Flow readqHcnone(Ws ws) {
        CicsTask.TsResult r = ws.task.readqTs("HCNONE", 1, ws.jlen);
        if (r.length() >= 0) {
            ws.jlen = r.length();                    // LENGTH(WS-JLEN) is input and output
        }
        if (r.data() != null) {
            String s = decode(r.data());
            for (int i = 0; i < s.length() && i < ws.junk.length; i++) {
                ws.junk[i] = s.charAt(i);            // bytes past the data keep their value
            }
        }
        return condition(ws, r.resp());
    }

    /** LINK PROGRAM('HCSUB') COMMAREA(WS-CA) LENGTH(20) (line 47). WS-CA is shared with HCSUB by reference:
     *  what HCSUB moves into it HCMAIN sees. HCMAIN's HANDLE CONDITION is not HCSUB's, but its HANDLE ABEND
     *  exit takes an abend raised at the lower level: the task reports it through abendExit() (#3989). */
    private Flow linkHcsubL47(Ws ws) {
        CicsTask task = ws.task;
        String resp = task.link(HCSUB, ws.ca, 20);
        if (!"NORMAL".equals(resp)) {
            return condition(ws, resp);              // PGMIDERR / LENGERR: unhandled -> default action
        }
        String exit = task.abendExit();
        if (exit != null) {
            return Flow.TO_MAIN_ABEND;               // an abend in HCSUB reached MAIN-ABEND
        }
        if (task.ended()) {
            ws.ended = true;                         // the task was terminated below
            return Flow.TERMINATED;
        }
        return Flow.CONTINUE;
    }

    /** A command's RESP under the handlers in force (#4003): NORMAL goes on; QIDERR with its HANDLE
     *  CONDITION goes to MAIN-QIDERR; any other condition takes CICS's default action, an abend with the
     *  condition's code, which the task hands to the first active HANDLE ABEND exit (#3989). */
    private Flow condition(Ws ws, String resp) {
        if ("NORMAL".equals(resp)) {
            return Flow.CONTINUE;
        }
        if ("QIDERR".equals(resp) && ws.qiderrHandler) {
            return Flow.TO_MAIN_QIDERR;
        }
        String label = ws.task.abendOnCondition(resp);
        if (MAIN_ABEND.equals(label)) {
            return Flow.TO_MAIN_ABEND;
        }
        ws.ended = true;                             // terminated: return from runTask at once
        return Flow.TERMINATED;
    }

    /** PUSH HANDLE: suspends HANDLE CONDITION (the program's own) and HANDLE ABEND (the task's). */
    private static void pushHandle(Ws ws) {
        ws.pushed.push(ws.qiderrHandler);
        ws.qiderrHandler = false;
        ws.task.pushHandle();
    }

    /** POP HANDLE: restores the handlers PUSH HANDLE suspended. */
    private static void popHandle(Ws ws) {
        if (!ws.pushed.isEmpty()) {
            ws.qiderrHandler = ws.pushed.pop();
        }
        ws.task.popHandle();
    }

    // =====================================================================================
    // COBOL storage helpers
    // =====================================================================================

    /** STRING ... DELIMITED BY SIZE INTO WS-TRAIL WITH POINTER WS-PTR (no ON OVERFLOW): characters go in
     *  from WS-PTR on; a pointer outside 1-40 is the overflow condition, which stops the transfer. */
    private static void string(Ws ws, String... sources) {
        for (String source : sources) {
            for (int i = 0; i < source.length(); i++) {
                if (ws.ptr < 1 || ws.ptr > ws.trail.length) {
                    return;
                }
                ws.trail[ws.ptr - 1] = source.charAt(i);
                ws.ptr++;
            }
        }
    }

    /** An alphanumeric field of `len` characters: padded with spaces or truncated on the right. */
    private static String pic(String value, int len) {
        String s = value == null ? "" : value;
        return s.length() >= len ? s.substring(0, len) : s + " ".repeat(len - s.length());
    }

    private static char[] filled(int len, char c) {
        char[] a = new char[len];
        Arrays.fill(a, c);
        return a;
    }

    private static String decode(byte[] data) {
        return new String(data, EBCDIC);
    }
}
