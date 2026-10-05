package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.exception.*;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.Charset;
import java.util.Arrays;

@Service
@Transactional
@RequiredArgsConstructor
public class GtstartService {

    private static final Logger log = LoggerFactory.getLogger(GtstartService.class);

    /** The region's code page: a START's FROM data is the bytes of the working-storage field, in EBCDIC. */
    private static final Charset EBCDIC = Charset.forName("IBM037");

    // ----------------------------------------------------------------------------------------------
    // WORKING-STORAGE SECTION (initial VALUEs; a CICS task gets a fresh copy each time)
    // ----------------------------------------------------------------------------------------------
    /** 01 WS-INPUT PIC X(20) VALUE SPACES. */
    private static final int WS_INPUT_LEN = 20;
    /** 01 WS-INLEN PIC S9(4) COMP VALUE 20. */
    private static final int WS_INLEN_INITIAL = 20;
    /** 01 WS-MSG PIC X(20) VALUE 'ORDER 0001 READY'. */
    private static final String WS_MSG = pic("ORDER 0001 READY", 20);
    /** 01 WS-MSG2 PIC X(20) VALUE 'ORDER 0002 LATE'. */
    private static final String WS_MSG2 = pic("ORDER 0002 LATE", 20);
    /** 01 WS-LONG PIC X(30) VALUE 'THIRTY BYTE PAYLOAD 0123456789'. */
    private static final String WS_LONG = pic("THIRTY BYTE PAYLOAD 0123456789", 30);
    /** 01 WS-UNPROT PIC X(20) VALUE 'UNPROTECTED START'. */
    private static final String WS_UNPROT = pic("UNPROTECTED START", 20);
    /** 01 WS-PROT PIC X(20) VALUE 'PROTECTED START'. */
    private static final String WS_PROT = pic("PROTECTED START", 20);
    /** 01 WS-TEXT PIC X(20) VALUE 'STARTS ISSUED'. */
    private static final String WS_TEXT = pic("STARTS ISSUED", 20);

    /** The transaction GTSTART starts (START TRANSID('GT02'), CSD: GT02 -> GTWORK). */
    private static final String GT02 = "GT02";

    /** A CICS transaction entered the program (#4343): one task of it in the region (CicsTask.region()),
     *  ENTER pressed, started from a cleared screen, run through runTask. */
    public void handleTransaction(String transid) {
        log.info("Gtstart: handleTransaction");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, null);
        region.run(task, "GTSTART", this::runTask);
    }

    /** One pseudo-conversational task of this program (#3754): the PROCEDURE DIVISION of GTSTART. */
    public void runTask(CicsTask task) {
        log.info("Gtstart: runTask");
        mainPara(task);
    }

    // ----------------------------------------------------------------------------------------------
    // MAIN-PARA (src/GTSTART.cbl:28-62)
    // ----------------------------------------------------------------------------------------------
    private void mainPara(CicsTask task) {
        // WORKING-STORAGE for this task
        char[] wsInput = new char[WS_INPUT_LEN];
        Arrays.fill(wsInput, ' ');
        int wsInlen = WS_INLEN_INITIAL;

        // EXEC CICS RECEIVE INTO(WS-INPUT) LENGTH(WS-INLEN) END-EXEC            (lines 29-30)
        // No RESP / NOHANDLE / HANDLE CONDITION: an input longer than 20 bytes raises LENGERR, whose
        // default action abends the task (AEIV).
        CicsTask.Received rcv = task.receiveText(wsInlen);
        String data = rcv.data() == null ? "" : rcv.data();
        // RECEIVE INTO moves only the bytes received: the rest of WS-INPUT keeps its VALUE SPACES.
        for (int i = 0; i < data.length() && i < WS_INPUT_LEN; i++) {
            wsInput[i] = data.charAt(i);
        }
        wsInlen = rcv.length();
        if (!"NORMAL".equals(rcv.resp())) {
            task.abendOnCondition(rcv.resp());
            return;
        }

        // MOVE WS-INPUT(6:1) TO WS-MODE                                          (line 31)
        char wsMode = wsInput[5];

        // EVALUATE WS-MODE                                                        (lines 32-59)
        switch (wsMode) {
            case 'A' -> {
                // EXEC CICS START TRANSID('GT02') INTERVAL(0) FROM(WS-MSG) LENGTH(20)   (line 34)
                if (!started(task, task.start(GT02, null, 0, from(WS_MSG, 20), null, false))) {
                    return;
                }
            }
            case 'N' -> {
                // EXEC CICS START TRANSID('GT02') INTERVAL(0)                          (line 38)
                if (!started(task, task.start(GT02, null, 0, null, null, false))) {
                    return;
                }
            }
            case 'T' -> {
                // EXEC CICS START TRANSID('GT02') TIME(103000) FROM(WS-MSG) LENGTH(20) (line 41)
                if (!started(task, task.startAt(GT02, null, 103000, from(WS_MSG, 20), null, false))) {
                    return;
                }
                // EXEC CICS START TRANSID('GT02') TIME(093000) FROM(WS-MSG2) LENGTH(20) (line 44)
                if (!started(task, task.startAt(GT02, null, 93000, from(WS_MSG2, 20), null, false))) {
                    return;
                }
            }
            case 'L' -> {
                // EXEC CICS START TRANSID('GT02') INTERVAL(0) FROM(WS-LONG) LENGTH(30) (line 48)
                if (!started(task, task.start(GT02, null, 0, from(WS_LONG, 30), null, false))) {
                    return;
                }
            }
            case 'X' -> {
                // EXEC CICS START TRANSID('GT02') INTERVAL(0) FROM(WS-UNPROT) LENGTH(20) (line 52)
                if (!started(task, task.start(GT02, null, 0, from(WS_UNPROT, 20), null, false))) {
                    return;
                }
                // EXEC CICS START TRANSID('GT02') INTERVAL(0) FROM(WS-PROT) LENGTH(20) PROTECT (line 55)
                if (!started(task, task.start(GT02, null, 0, from(WS_PROT, 20), null, true))) {
                    return;
                }
                // EXEC CICS ABEND ABCODE('GTAB') END-EXEC                                (line 58)
                // No HANDLE ABEND is active: the task is terminated here.
                task.abend("GTAB");
                return;
            }
            default -> {
                // No WHEN OTHER: any other mode (including a blank) issues no START.
                // Kept defect: the program still sends 'STARTS ISSUED' below although nothing was started.
                // One-line fix: add WHEN OTHER with a SEND TEXT of an 'INVALID MODE' message.
            }
        }
        // END-EVALUATE

        // EXEC CICS SEND TEXT FROM(WS-TEXT) LENGTH(20) ERASE END-EXEC                (lines 60-61)
        task.sendText(WS_TEXT, 20, "ERASE");

        // EXEC CICS RETURN END-EXEC.                                                  (line 62)
        task.returnTransid(null, null);
    }

    /**
     * A START with no RESP / NOHANDLE / HANDLE CONDITION: any condition other than NORMAL takes CICS's
     * default action, which abends the task (#4003). Returns false when the task has ended.
     */
    private static boolean started(CicsTask task, CicsTask.StartResult result) {
        if (!"NORMAL".equals(result.resp())) {
            task.abendOnCondition(result.resp());
            return false;
        }
        return true;
    }

    /** FROM(field) LENGTH(length): the first `length` bytes of the field's storage, in EBCDIC. */
    private static byte[] from(String field, int length) {
        return pic(field, length).getBytes(EBCDIC);
    }

    /** MOVE to PIC X(len): padded with spaces or truncated on the right. */
    private static String pic(String value, int len) {
        String v = value == null ? "" : value;
        if (v.length() >= len) {
            return v.substring(0, len);
        }
        StringBuilder sb = new StringBuilder(len).append(v);
        while (sb.length() < len) {
            sb.append(' ');
        }
        return sb.toString();
    }

    /**
     * EXEC CICS ABEND ABCODE(GTAB) at src/GTSTART.cbl:58 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendGtabL58() {
        throw new CicsAbendException("GTAB", "GTSTART", "src/GTSTART.cbl:58");
    }

}
