package com.gitgalaxy.modernized.service;

import java.nio.charset.Charset;
import java.util.Arrays;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * RETRIEVE at line 23 tests NORMAL
 *
 * GTSHOW is transaction GT12. GTTERM starts it on a terminal with START TERMID. It RETRIEVEs every
 * data record it can get. It strings them into a 40-byte line after 'SHOW:' and sends that line as text.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class GtshowService {

    private static final Logger log = LoggerFactory.getLogger(GtshowService.class);

    /** The region's code page. A RETRIEVE returns the START FROM data as the bytes the starting program
     *  moved, in EBCDIC. This port assumes CCSID 037; see the port notes. */
    private static final Charset REGION_CODE_PAGE = Charset.forName("IBM037");

    /** WS-DATA PIC X(10). */
    private static final int WS_DATA_LEN = 10;
    /** WS-SHOW PIC X(40). */
    private static final int WS_SHOW_LEN = 40;

    /**
     * GTSHOW has no batch entry. It is a CICS program only, reached as transaction GT12 (runTask).
     * No part of the PROCEDURE DIVISION runs outside a CICS task.
     */
    public void executeGtshow(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for GTSHOW");
        log.info("GTSHOW runs only as CICS transaction GT12; its logic is in runTask(CicsTask)");
    }

    /** A CICS transaction entered the program. GT12's logic is in runTask(CicsTask). The CICS runtime
     *  calls it with the task: its RETRIEVE data, terminal and events. */
    public void handleTransaction(String transid) {
        log.info("Gtshow: handleTransaction {} (the task runs through runTask)", transid);
    }

    /** One task of transaction GT12 (#3754): the PROCEDURE DIVISION of GTSHOW. */
    public void runTask(CicsTask task) {
        log.info("Gtshow: runTask");

        // WORKING-STORAGE SECTION: fresh for every task
        char[] wsShow = new char[WS_SHOW_LEN];                    // 01 WS-SHOW PIC X(40) VALUE 'SHOW:'
        Arrays.fill(wsShow, ' ');
        "SHOW:".getChars(0, 5, wsShow, 0);
        int wsPtr = 6;                                            // 01 WS-PTR PIC S9(4) COMP VALUE 6
        int wsCount = 0;                                          // 01 WS-COUNT PIC 9 VALUE 0
        String wsResp;                                            // 01 WS-RESP PIC S9(8) COMP (as a DFHRESP name)
        char[] wsData = new char[WS_DATA_LEN];                    // 01 WS-DATA PIC X(10) VALUE SPACES
        Arrays.fill(wsData, ' ');
        int wsLen;                                                // 01 WS-LEN PIC S9(4) COMP VALUE 0

        // MAIN-PARA
        // PERFORM WITH TEST AFTER UNTIL WS-RESP NOT = DFHRESP(NORMAL)
        do {
            // MOVE SPACES TO WS-DATA
            Arrays.fill(wsData, ' ');
            // MOVE 10 TO WS-LEN
            wsLen = 10;
            // EXEC CICS RETRIEVE INTO(WS-DATA) LENGTH(WS-LEN) RESP(WS-RESP) END-EXEC
            CicsTask.RetrieveResult retrieved = task.retrieve(wsLen);
            wsResp = retrieved.resp();
            if (retrieved.data() != null) {
                // INTO moves the record. On LENGERR the record is truncated to LENGTH.
                // The rest of WS-DATA keeps its spaces.
                String moved = new String(retrieved.data(), REGION_CODE_PAGE);
                int n = Math.min(moved.length(), WS_DATA_LEN);
                moved.getChars(0, n, wsData, 0);
            }
            if (retrieved.length() >= 0) {
                wsLen = retrieved.length();                       // LENGTH is set to the record's own length
            }
            // IF WS-RESP = DFHRESP(NORMAL)
            if ("NORMAL".equals(wsResp)) {
                // IF WS-COUNT > 0: STRING ',' DELIMITED BY SIZE INTO WS-SHOW WITH POINTER WS-PTR
                if (wsCount > 0) {
                    wsPtr = stringInto(wsShow, wsPtr, ",");
                }
                // STRING WS-DATA DELIMITED BY SPACE INTO WS-SHOW WITH POINTER WS-PTR
                wsPtr = stringInto(wsShow, wsPtr, delimitedBySpace(wsData));
                // ADD 1 TO WS-COUNT. The field is PIC 9 with no ON SIZE ERROR, so 9 + 1 = 10 keeps
                // only its low-order digit, 0.
                // DEFECT kept: after the 10th record WS-COUNT wraps to 0, so the 11th record is strung
                // without its ',' separator. Fix: declare WS-COUNT PIC 9(4).
                wsCount = (wsCount + 1) % 10;
            }
            // DEFECT kept: a record longer than 10 bytes gives LENGERR, which ends the loop. That record
            // (truncated in WS-DATA) and every record after it are never shown.
            // Fix: loop UNTIL WS-RESP = DFHRESP(ENDDATA) and show LENGERR records too.
        } while ("NORMAL".equals(wsResp));

        // EXEC CICS SEND TEXT FROM(WS-SHOW) LENGTH(40) ERASE END-EXEC
        String show = new String(wsShow);
        log.info("GTSHOW: {} record(s) retrieved, last RESP {}, WS-LEN {}", wsCount, wsResp, wsLen);
        task.sendText(show, WS_SHOW_LEN, "ERASE");
        // EXEC CICS RETURN END-EXEC.
        task.returnTransid(null, null);
    }

    /**
     * WS-DATA DELIMITED BY SPACE: the characters before the first space. That is all 10 when there is
     * no space, and none when WS-DATA starts with a space.
     */
    private static String delimitedBySpace(char[] data) {
        String s = new String(data);
        int space = s.indexOf(' ');
        return space < 0 ? s : s.substring(0, space);
    }

    /**
     * STRING source INTO receiver WITH POINTER ptr, with no ON OVERFLOW.
     * - A pointer below 1 or past the receiver transfers nothing.
     * - Otherwise characters go in from the pointer on, and the pointer advances by one per character.
     * - Transfer stops when the source ends or the receiver is full; on overflow the rest is dropped.
     * - The receiver's other positions are left as they are.
     * Returns the new pointer.
     * DEFECT kept: there is no ON OVERFLOW, so a line past 40 bytes is cut silently.
     * Fix: add ON OVERFLOW to flag the truncation.
     */
    private static int stringInto(char[] receiver, int ptr, String source) {
        if (ptr < 1 || ptr > receiver.length) {
            return ptr;
        }
        for (int i = 0; i < source.length(); i++) {
            if (ptr > receiver.length) {
                break;
            }
            receiver[ptr - 1] = source.charAt(i);
            ptr++;
        }
        return ptr;
    }

}
