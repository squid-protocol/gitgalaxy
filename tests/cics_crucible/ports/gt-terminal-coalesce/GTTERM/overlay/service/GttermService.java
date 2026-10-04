package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.Charset;
import java.util.Locale;

/**
 * Port of GTTERM (src/GTTERM.cbl), started by transaction GT11 (CSD group CRUCGT2).
 * It starts GT12 on its own terminal. The mode is the character typed after the transid:
 *   3  three STARTs, INTERVAL(0)
 *   S  INTERVAL(0) and INTERVAL(10)
 *   C  INTERVAL(30) with REQID('GTREQ001')
 *   anything else (the documented K)  CANCEL REQID('GTREQ001')
 *
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * the RESP of CANCEL at line 58 (paragraph MAIN-PARA) is never tested. The original only shows it
 * on the screen, and so does this port (see the note in MAIN-PARA).
 */
@Service
@Transactional
@RequiredArgsConstructor
public class GttermService {

    private static final Logger log = LoggerFactory.getLogger(GttermService.class);

    /** The region's code page. The FROM data of a START is the program's storage bytes. For the
     *  characters this program sends (A-Z, space), IBM-037 and IBM-1047 produce the same bytes. */
    private static final Charset EBCDIC = Charset.forName("IBM1047");

    private static final String GT12 = "GT12";
    private static final String REQID = "GTREQ001";

    /** GTTERM is a CICS-only program. It has no batch entry and no COMMAREA, and its logic is in runTask. */
    public void executeGtterm(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for GTTERM");
        // GTTERM has no batch PROCEDURE entry. Its PROCEDURE DIVISION runs only as CICS transaction GT11,
        // which is ported in runTask(CicsTask). There is nothing to run here.
    }

    /** A CICS transaction entered the program. GT11 is ported in runTask(CicsTask). */
    public void handleTransaction(String transid) {
        log.info("Gtterm: handleTransaction {}", transid);
    }

    /** One task of GTTERM (#3754). */
    public void runTask(CicsTask task) {
        log.info("Gtterm: runTask");

        // ---- MAIN-PARA ---------------------------------------------------------------------------
        // 01 WS-INPUT PIC X(20) VALUE SPACES.   01 WS-INLEN PIC S9(4) COMP VALUE 20.
        int wsInlen = 20;
        String wsText = spaces(20);                 // 01 WS-TEXT PIC X(20) VALUE SPACES.

        // EXEC CICS RECEIVE INTO(WS-INPUT) LENGTH(WS-INLEN) END-EXEC
        // This command has no RESP and no HANDLE CONDITION. If the operator types more than 20 bytes,
        // LENGERR takes CICS's default action and the task abends with AEIV.
        CicsTask.Received rcv = task.receiveText(wsInlen);
        if (!"NORMAL".equals(rcv.resp())) {
            task.abendOnCondition(rcv.resp());
            return;
        }
        // INTO overwrites only the bytes received. The rest of WS-INPUT keeps its VALUE SPACES.
        String wsInput = overlay(spaces(20), rcv.data());

        // MOVE WS-INPUT(6:1) TO WS-MODE
        char wsMode = wsInput.charAt(5);
        // MOVE EIBTRMID TO WS-TERM  (PIC X(4))
        String eibtrmid = task.termid();
        String wsTerm = eibtrmid == null ? null : pic(eibtrmid, 4);

        // WS-A / WS-B / WS-C PIC X(10) VALUE 'ALPHA' / 'BRAVO' / 'CHARLIE'; FROM(..) LENGTH(10)
        byte[] wsA = pic("ALPHA", 10).getBytes(EBCDIC);
        byte[] wsB = pic("BRAVO", 10).getBytes(EBCDIC);
        byte[] wsC = pic("CHARLIE", 10).getBytes(EBCDIC);

        // EVALUATE WS-MODE
        switch (wsMode) {
            case '3' -> {
                // WHEN '3': three STARTs, INTERVAL(0), on the same terminal
                if (!start(task, wsTerm, 0, wsA, null)) {
                    return;
                }
                if (!start(task, wsTerm, 0, wsB, null)) {
                    return;
                }
                if (!start(task, wsTerm, 0, wsC, null)) {
                    return;
                }
                wsText = pic("QUEUED 3", 20);                    // MOVE 'QUEUED 3' TO WS-TEXT
            }
            case 'S' -> {
                // WHEN 'S': INTERVAL(0), then INTERVAL(10)
                if (!start(task, wsTerm, 0, wsA, null)) {
                    return;
                }
                if (!start(task, wsTerm, 10, wsB, null)) {
                    return;
                }
                wsText = pic("QUEUED STAGGERED", 20);            // MOVE 'QUEUED STAGGERED' TO WS-TEXT
            }
            case 'C' -> {
                // WHEN 'C': INTERVAL(30) REQID('GTREQ001')
                if (!start(task, wsTerm, 30, wsA, REQID)) {
                    return;
                }
                wsText = pic("QUEUED GTREQ001", 20);             // MOVE 'QUEUED GTREQ001' TO WS-TEXT
            }
            default -> {
                // WHEN OTHER
                // DEFECT (kept): the header documents only mode K for CANCEL, but WHEN OTHER cancels for
                // every other mode too (blank, lower case, typos). Fix: WHEN 'K' for the CANCEL, and a
                // WHEN OTHER that rejects the mode.
                // EXEC CICS CANCEL REQID('GTREQ001') RESP(WS-RESP) END-EXEC
                // UNCHECKED RESPONSE (kept): WS-RESP is never tested, only shown on the screen. A NOTFND
                // reports "CANCEL RESP=13" and the task carries on.
                // Fix: IF WS-RESP NOT = DFHRESP(NORMAL) ... handle it.
                String resp = task.cancel(REQID);
                int wsResp = dfhresp(resp);                        // WS-RESP PIC S9(8) COMP
                // MOVE WS-RESP TO WS-RESP-D (PIC 99): unsigned, and the high-order digits are truncated
                String wsRespD = String.format(Locale.ROOT, "%02d", Math.abs(wsResp) % 100);
                // STRING 'CANCEL RESP=' WS-RESP-D DELIMITED BY SIZE INTO WS-TEXT
                // STRING does not pad: the 6 bytes after the 14 written keep their spaces.
                wsText = overlay(wsText, "CANCEL RESP=" + wsRespD);
            }
        }
        // END-EVALUATE

        // EXEC CICS SEND TEXT FROM(WS-TEXT) LENGTH(20) ERASE END-EXEC
        task.sendText(wsText, 20, "ERASE");
        // EXEC CICS RETURN END-EXEC.
        task.returnTransid(null, null);
    }

    /** EXEC CICS START TRANSID('GT12') TERMID(WS-TERM) INTERVAL(n) FROM(..) LENGTH(10) [REQID].
     *  The command has no RESP, so any condition (INVREQ, LENGERR, TRANSIDERR, TERMIDERR) takes CICS's
     *  default action and abends the task. Returns false when the task was abended. */
    private boolean start(CicsTask task, String term, int interval, byte[] from, String reqid) {
        CicsTask.StartResult r = task.start(GT12, term, interval, from, reqid, false);
        if (!"NORMAL".equals(r.resp())) {
            task.abendOnCondition(r.resp());
            return false;
        }
        return true;
    }

    /** The DFHRESP value of each condition CANCEL can return. */
    private static int dfhresp(String resp) {
        return switch (resp) {
            case "NORMAL" -> 0;
            case "NOTFND" -> 13;
            case "INVREQ" -> 16;
            case "SYSIDERR" -> 53;
            case "NOTAUTH" -> 70;
            default -> throw new IllegalStateException("unexpected CANCEL response " + resp);
        };
    }

    private static String spaces(int n) {
        return " ".repeat(n);
    }

    /** MOVE to PIC X(n): pad with spaces or truncate on the right. */
    private static String pic(String s, int n) {
        String v = s == null ? "" : s;
        return v.length() >= n ? v.substring(0, n) : v + spaces(n - v.length());
    }

    /** Writes data over the start of a field and keeps the field's remaining bytes (RECEIVE INTO, STRING). */
    private static String overlay(String field, String data) {
        String d = data == null ? "" : data;
        if (d.length() >= field.length()) {
            return d.substring(0, field.length());
        }
        return d + field.substring(d.length());
    }
}
