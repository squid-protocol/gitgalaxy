package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.messaging.TempStorage;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.Charset;
import java.util.Arrays;
import java.util.Locale;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * RETRIEVE at line 28 tests LENGERR,NORMAL
 */
@Service
@Transactional
@RequiredArgsConstructor
public class GtworkService {

    private static final Logger log = LoggerFactory.getLogger(GtworkService.class);

    private final TempStorage tempStorage;

    /** The region's code page: WS-LOG's literal and PIC 9 DISPLAY bytes are EBCDIC (0x40 space, 0xF0-0xF9 digits). */
    private static final Charset EBCDIC = Charset.forName("IBM037");
    private static final byte EBCDIC_SPACE = (byte) 0x40;

    /** 01 WS-DATA PIC X(20). */
    private static final int WS_DATA_LEN = 20;
    /** WRITEQ TS ... LENGTH(34): the whole of WS-LOG (2 + 2 + 3 + 4 + 3 + 20). */
    private static final int WS_LOG_LEN = 34;

    /** DFHRESP(NORMAL) and DFHRESP(LENGERR), as the translator resolves them. */
    private static final int DFHRESP_NORMAL = 0;
    private static final int DFHRESP_LENGERR = 22;

    public void executeGtwork(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for GTWORK");
        // GTWORK is the GT02 background task, started only by START (GTSTART). A call from the controller is
        // not a START-initiated task, so it has no START data: its first RETRIEVE answers ENDDATA (as
        // CicsTask.retrieve does for a task no START started). The one WS-LOG record the program then
        // writes goes to the region's TS queue GTLOG through the generated WRITEQ TS (line 41) helper.
        mainPara(maxLength -> new CicsTask.RetrieveResult("ENDDATA", -1, null),
                wsLog -> {
                    writeqTsGtlogL41(new String(wsLog, EBCDIC));
                    return true;
                });
        // EXEC CICS RETURN END-EXEC (line 45): the program ends.
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public void handleTransaction(String transid) {
        log.info("Gtwork: handleTransaction");
    }

    /** One task of GTWORK (transaction GT02, no terminal): RETRIEVEs the START data it was started for and
     *  logs each response to TS queue GTLOG, then RETURNs. */
    public void runTask(CicsTask task) {
        log.info("Gtwork: runTask");
        boolean completed = mainPara(task::retrieve, wsLog -> {
            // EXEC CICS WRITEQ TS QUEUE('GTLOG') FROM(WS-LOG) LENGTH(34) (lines 41-43): no RESP / NOHANDLE,
            // so a condition takes CICS's default action (an abend of the task).
            CicsTask.TsResult written = task.writeqTs("GTLOG", wsLog);
            if (!"NORMAL".equals(written.resp())) {
                task.abendOnCondition(written.resp());
                return false;
            }
            return true;
        });
        if (completed) {
            // EXEC CICS RETURN END-EXEC (line 45)
            task.returnTransid(null, null);
        }
    }

    /** EXEC CICS WRITEQ TS QUEUE('GTLOG') FROM(WS-LOG) at src/GTWORK.cbl:41 (#3620).
     *  CICS resources field testing: open (5 public / 0 private estates). */
    protected int writeqTsGtlogL41(String record) {
        return tempStorage.writeItem("GTLOG", record);
    }

    // ------------------------------------------------------------------------------------------------
    // PROCEDURE DIVISION
    // ------------------------------------------------------------------------------------------------

    /** EXEC CICS RETRIEVE INTO LENGTH, as the task (or the controller's stand-in) answers it. */
    @FunctionalInterface
    private interface Retriever {
        CicsTask.RetrieveResult retrieve(int maxLength);
    }

    /** EXEC CICS WRITEQ TS QUEUE('GTLOG') FROM(WS-LOG) LENGTH(34); false when the task abended. */
    @FunctionalInterface
    private interface GtlogWriter {
        boolean write(byte[] wsLog);
    }

    /**
     * MAIN-PARA (lines 24-44): PERFORM UNTIL WS-MORE = 'N' ... END-PERFORM.
     * Returns false when the task abended inside the loop (it then never reaches the RETURN).
     */
    private boolean mainPara(Retriever retriever, GtlogWriter writer) {
        // WORKING-STORAGE initial values (lines 12-22)
        byte[] wsData = spaces(WS_DATA_LEN);   // WS-DATA  PIC X(20) VALUE SPACES
        int wsLen = 0;                          // WS-LEN   PIC S9(4) COMP VALUE 0
        int wsResp = 0;                         // WS-RESP  PIC S9(8) COMP VALUE 0
        char wsMore = 'Y';                      // WS-MORE  PIC X VALUE 'Y'
        int logResp = 0;                        // LOG-RESP PIC 99 VALUE 0
        int logLen = 0;                         // LOG-LEN  PIC 9(4) VALUE 0
        byte[] logData = spaces(WS_DATA_LEN);   // LOG-DATA PIC X(20) VALUE SPACES

        // PERFORM UNTIL WS-MORE = 'N' (line 25): the test comes before each iteration
        while (wsMore != 'N') {
            // MOVE SPACES TO WS-DATA (line 26)
            Arrays.fill(wsData, EBCDIC_SPACE);
            // MOVE 20 TO WS-LEN (line 27)
            wsLen = 20;

            // EXEC CICS RETRIEVE INTO(WS-DATA) LENGTH(WS-LEN) RESP(WS-RESP) (lines 28-30)
            CicsTask.RetrieveResult retrieved = retriever.retrieve(wsLen);
            wsResp = dfhresp(retrieved.resp());
            if (retrieved.data() != null) {
                // INTO moves the record's bytes (at most LENGTH of them, truncated on LENGERR); the rest of
                // WS-DATA keeps the spaces moved at line 26.
                byte[] data = retrieved.data();
                System.arraycopy(data, 0, wsData, 0, Math.min(data.length, WS_DATA_LEN));
            }
            if (retrieved.length() >= 0) {
                // LENGTH is set to the record's own length -- on LENGERR the original, untruncated length.
                wsLen = retrieved.length();
            }

            // MOVE WS-RESP TO LOG-RESP (line 31): PIC 99 unsigned keeps the absolute value's low two digits
            logResp = Math.abs(wsResp) % 100;

            // IF WS-RESP = DFHRESP(NORMAL) OR WS-RESP = DFHRESP(LENGERR) (lines 32-33)
            if (wsResp == DFHRESP_NORMAL || wsResp == DFHRESP_LENGERR) {
                // MOVE WS-LEN TO LOG-LEN (line 34): PIC 9(4) unsigned keeps the low four digits.
                // KEPT DEFECT: on LENGERR this logs the record's full length, not the 20 bytes moved.
                logLen = Math.abs(wsLen) % 10000;
                // MOVE WS-DATA TO LOG-DATA (line 35): X(20) to X(20)
                logData = wsData.clone();
            } else {
                // MOVE 0 TO LOG-LEN (line 37)
                logLen = 0;
                // MOVE SPACES TO LOG-DATA (line 38)
                logData = spaces(WS_DATA_LEN);
                // MOVE 'N' TO WS-MORE (line 39)
                // KEPT DEFECT: any response other than NORMAL / LENGERR (ENDDATA, but also INVREQ, IOERR,
                // NOTFND...) ends the loop as a normal end of data, with no error raised.
                // Fix: MOVE 'N' TO WS-MORE only when WS-RESP = DFHRESP(ENDDATA), else abend.
                wsMore = 'N';
            } // END-IF (line 40)

            // EXEC CICS WRITEQ TS QUEUE('GTLOG') FROM(WS-LOG) LENGTH(34) (lines 41-43)
            if (!writer.write(wsLog(logResp, logLen, logData))) {
                return false;
            }
        } // END-PERFORM (line 44)
        return true;
    }

    /** 01 WS-LOG (lines 16-22) as its 34 record bytes in the region's code page. */
    private static byte[] wsLog(int logResp, int logLen, byte[] logData) {
        // PIC 99 / PIC 9(4) unsigned DISPLAY: plain zoned digits (zone F, no sign nibble to overpunch).
        String head = "R="                                                   // FILLER X(2) VALUE 'R='
                + String.format(Locale.ROOT, "%02d", logResp)                // LOG-RESP PIC 99
                + " L="                                                      // FILLER X(3) VALUE ' L='
                + String.format(Locale.ROOT, "%04d", logLen)                 // LOG-LEN PIC 9(4)
                + " D=";                                                     // FILLER X(3) VALUE ' D='
        byte[] headBytes = head.getBytes(EBCDIC);
        byte[] record = new byte[WS_LOG_LEN];
        System.arraycopy(headBytes, 0, record, 0, headBytes.length);
        System.arraycopy(logData, 0, record, headBytes.length, WS_DATA_LEN);   // LOG-DATA X(20)
        return record;
    }

    /** DFHRESP(condition): the EIBRESP value the RESP option stores in WS-RESP. */
    private static int dfhresp(String condition) {
        return switch (condition) {
            case "NORMAL" -> 0;
            case "NOTFND" -> 13;
            case "INVREQ" -> 16;
            case "IOERR" -> 17;
            case "LENGERR" -> 22;
            case "ENDDATA" -> 29;
            default -> throw new IllegalStateException("RETRIEVE answered an unexpected condition " + condition);
        };
    }

    private static byte[] spaces(int length) {
        byte[] b = new byte[length];
        Arrays.fill(b, EBCDIC_SPACE);
        return b;
    }
}
