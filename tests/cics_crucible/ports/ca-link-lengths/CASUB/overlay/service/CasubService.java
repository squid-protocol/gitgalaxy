package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CasubDfhcommarea;
import com.gitgalaxy.modernized.messaging.TempStorage;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.Charset;

@Service
@Transactional
@RequiredArgsConstructor
public class CasubService {

    private static final Logger log = LoggerFactory.getLogger(CasubService.class);

    /** The region's code page (EBCDIC): a TS item is the bytes the program wrote. */
    private static final Charset EBCDIC = Charset.forName("IBM1047");

    /** 01 WS-MSG PIC X(11) VALUE 'NO COMMAREA'. */
    private static final String WS_MSG = "NO COMMAREA";

    /** LENGTH(11) on the WRITEQ TS at line 22-23. */
    private static final int WS_MSG_LENGTH = 11;

    /** LENGTH OF DFHCOMMAREA: CA-HEAD (100) + CA-EXT (400) = 500 bytes. */
    private static final int LENGTH_OF_DFHCOMMAREA = 500;

    private static final int CA_RC_LEN = 2;
    private static final int CA_REPLY_LEN = 20;
    private static final int CA_EXT_FLAG_LEN = 1;
    private static final int CA_EXT_DATA_LEN = 399;

    private final TempStorage tempStorage;

    /** This program's run at a LINK / XCTL level (#4004): task.level(), task.eibcalen(). */
    public void runTask(CicsTask task) {
        log.info("Casub: runTask");

        // ---- SUB-MAIN (line 20) ----
        // IF EIBCALEN = 0 (line 21)
        if (!task.hasCommarea()) {
            // EXEC CICS WRITEQ TS QUEUE('CATRACE') FROM(WS-MSG) LENGTH(11) END-EXEC (lines 22-24)
            // No RESP option: a condition is CICS's default action (abend). With a fixed LENGTH(11) the
            // command cannot raise LENGERR, but the default action is kept for fidelity.
            byte[] item = pad(WS_MSG, WS_MSG_LENGTH).getBytes(EBCDIC);
            CicsTask.TsResult ts = task.writeqTs("CATRACE", item);
            if (!"NORMAL".equals(ts.resp())) {
                task.abendOnCondition(ts.resp());
                return;
            }
            // EXEC CICS RETURN END-EXEC (line 25)
            task.returnTransid(null, null);
            return;
        }

        // EIBCALEN: null means the COMMAREA came as its whole record (#4009).
        Integer len = task.eibcalen();
        int eibcalen = len == null ? LENGTH_OF_DFHCOMMAREA : len;

        CasubDfhcommarea ca = task.commarea(CasubDfhcommarea.class);

        // Lines 27-35
        subMainBody(ca, eibcalen);

        // EXEC CICS RETURN END-EXEC. (line 36)
        task.returnTransid(null, null);
    }

    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region
     *  (CicsTask.region()), run through runTask on `request`, passed by reference -- what it changes, the caller sees. */
    public CasubDfhcommarea handleLink(CasubDfhcommarea request) {
        log.info("Casub: handleLink");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("CASUB", request);
        region.run(task, "CASUB", this::runTask);
        return request;
    }

    /** SUB-MAIN, lines 27-35: the part after the EIBCALEN = 0 test, applied to the caller's COMMAREA. */
    private void subMainBody(CasubDfhcommarea ca, int eibcalen) {
        // MOVE EIBCALEN TO CA-SEEN-LEN (line 27)
        // EIBCALEN (DFHEIBLK) and CA-SEEN-LEN are both PIC S9(4) COMP: a same-PICTURE halfword move,
        // copied as is (EIBCALEN is 0-32763 and always fits the halfword).
        // DEFECT kept: the program writes CA-SEEN-LEN (offset 7-8) and CA-REPLY (offset 29-48) without
        // checking that EIBCALEN covers them -- a caller passing fewer than 49 bytes gets its storage past
        // the COMMAREA overwritten. Fix: IF EIBCALEN >= LENGTH OF CA-HEAD before writing the header.
        ca.setCaSeenLen(eibcalen);

        // MOVE 'PONG' TO CA-REPLY (line 28): alphanumeric MOVE pads with spaces to X(20)
        ca.setCaReply(pad("PONG", CA_REPLY_LEN));

        // IF EIBCALEN >= LENGTH OF DFHCOMMAREA (line 29)
        // DEFECT kept: the test trusts EIBCALEN, not the caller's real area. CALINK line 46 LINKs its
        // 100-byte WS-CA100 with LENGTH(500), so EIBCALEN = 500 and CA-EXT (offsets 100-499) is written over
        // 400 bytes of the caller's storage that follow WS-CA100. Fix (in CALINK): pass LENGTH(LENGTH OF
        // WS-CA100), or LINK a 500-byte area when LENGTH(500) is meant.
        if (eibcalen >= LENGTH_OF_DFHCOMMAREA) {
            // MOVE 'Y' TO CA-EXT-FLAG (line 30)
            ca.setCaExtFlag(pad("Y", CA_EXT_FLAG_LEN));
            // MOVE 'CALLEE-WROTE-HERE' TO CA-EXT-DATA (line 31): padded with spaces to X(399)
            ca.setCaExtData(pad("CALLEE-WROTE-HERE", CA_EXT_DATA_LEN));
            // MOVE '00' TO CA-RC (line 32)
            ca.setCaRc(pad("00", CA_RC_LEN));
        } else {
            // MOVE '04' TO CA-RC (line 34)
            ca.setCaRc(pad("04", CA_RC_LEN));
        }
        // END-IF (line 35)
    }

    /** MOVE to an alphanumeric field: pad with spaces on the right, or truncate on the right. */
    private static String pad(String value, int length) {
        String v = value == null ? "" : value;
        if (v.length() >= length) {
            return v.substring(0, length);
        }
        StringBuilder sb = new StringBuilder(length).append(v);
        while (sb.length() < length) {
            sb.append(' ');
        }
        return sb.toString();
    }

    /** EXEC CICS WRITEQ TS QUEUE('CATRACE') FROM(WS-MSG) at src/CASUB.cbl:22 (#3620).
     *  CICS resources field testing: open (5 public / 0 private estates). */
    protected int writeqTsCatraceL22(String record) {
        return tempStorage.writeItem("CATRACE", record);
    }

}
