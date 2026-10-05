package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.HcsubDfhcommarea;
import com.gitgalaxy.modernized.exception.*;
import com.gitgalaxy.modernized.messaging.TempStorage;
import java.util.Optional;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * READQ at line 37 tests QIDERR
 *
 * HCSUB is LINKed from HCMAIN (src/HCMAIN.cbl:47) with a 20-byte COMMAREA (copy/HCLINKCA.cpy).
 * It sets no HANDLE CONDITION of its own:
 *   mode 'Q'   - READQ TS without RESP: an error condition takes CICS's default action (abend, AEYH for
 *                QIDERR), searched through the active HANDLE ABEND exits from this level upward;
 *   mode 'A'   - HANDLE ABEND LABEL(SUB-ABEND), ABEND ABCODE('HCX1'), recovery in SUB-ABEND by RETURN;
 *   otherwise  - READQ TS with RESP: QIDERR is reported in CA-RESULT.
 * CICS transfers (abends, exits) are ported as control flow through CicsTask, never as exceptions (#3989).
 */
@Service
@Transactional
@RequiredArgsConstructor
public class HcsubService {

    private static final Logger log = LoggerFactory.getLogger(HcsubService.class);

    /** PROGRAM-ID. */
    private static final String PROGRAM = "HCSUB";

    /** The HANDLE ABEND LABEL of line 32. */
    private static final String LABEL_SUB_ABEND = "SUB-ABEND";

    /** The TS queue both READQs name (lines 27 and 37). */
    private static final String QUEUE_HCNONE = "HCNONE";

    /** 01 WS-JLEN PIC S9(4) COMP VALUE 8: WORKING-STORAGE is fresh on every LINK, so it is 8 on entry. */
    private static final int WS_JLEN_INITIAL = 8;

    /** CA-MODE PIC X, CA-TRAIL PIC X(9), CA-RESULT PIC X(4); WS-ABCODE PIC X(4). */
    private static final int CA_MODE_LEN = 1;
    private static final int CA_TRAIL_LEN = 9;
    private static final int CA_RESULT_LEN = 4;
    private static final int WS_ABCODE_LEN = 4;

    /** CA-COUNT PIC S9(4) COMP under TRUNC(STD) (the default): four decimal digits are kept. */
    private static final long CA_COUNT_MODULUS = 10_000L;

    private final TempStorage tempStorage;

    /** The task and COMMAREA a running HCSUB level works on, so that onAbendL32 (paragraph SUB-ABEND)
     *  reaches the same DFHCOMMAREA and task. Saved and restored around each run. */
    private static final ThreadLocal<Frame> CURRENT = new ThreadLocal<>();

    private record Frame(CicsTask task, HcsubDfhcommarea ca) {
    }

    /** This program's run at a LINK / XCTL level (#4004): task.level(), task.eibcalen(). */
    public void runTask(CicsTask task) {
        log.info("Hcsub: runTask");
        if (!task.hasCommarea()) {
            // HCSUB never tests EIBCALEN: with no COMMAREA, DFHCOMMAREA has no addressability and the first
            // MOVE (line 23) fails (ASRA on the mainframe). DEFECT kept; one-line fix (business decision):
            // IF EIBCALEN = 0 EXEC CICS RETURN END-EXEC END-IF before line 23.
            // Modelled as an abend searched through the active exits, never as an exception (#3989).
            log.info("HCSUB: no COMMAREA, DFHCOMMAREA not addressable at src/HCSUB.cbl:23");
            task.abend("ASRA");
            return;
        }
        HcsubDfhcommarea ca = task.commarea(HcsubDfhcommarea.class);
        Frame previous = CURRENT.get();
        CURRENT.set(new Frame(task, ca));
        try {
            subMain(task, ca);
        } finally {
            if (previous == null) {
                CURRENT.remove();
            } else {
                CURRENT.set(previous);
            }
        }
    }

    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region
     *  (CicsTask.region()), run through runTask on `request`, passed by reference -- what it changes, the caller sees. */
    public HcsubDfhcommarea handleLink(HcsubDfhcommarea request) {
        log.info("Hcsub: handleLink");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("HCSUB", request);
        region.run(task, "HCSUB", this::runTask);
        return request;
    }

    /**
     * EXEC CICS HANDLE ABEND at src/HCSUB.cbl:32 (paragraph SUB-MAIN) routes abends to SUB-ABEND.
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     */
    public void onAbendL32(CicsAbendException e) {
        log.info("HANDLE ABEND LABEL SUB-ABEND at line 32", e);
        Frame frame = CURRENT.get();
        if (frame == null) {
            // SUB-ABEND addresses DFHCOMMAREA and issues ASSIGN / RETURN: it only runs inside an HCSUB task.
            log.info("HCSUB: SUB-ABEND taken outside an HCSUB task; nothing to do");
            return;
        }
        subAbend(frame.task(), frame.ca());
    }

    /**
     * EXEC CICS ABEND ABCODE(HCX1) at src/HCSUB.cbl:34 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendHcx1L34() {
        throw new CicsAbendException("HCX1", "HCSUB", "src/HCSUB.cbl:34");
    }

    /** EXEC CICS READQ TS QUEUE('HCNONE') INTO(WS-JUNK) ITEM(1) at src/HCSUB.cbl:27 (#3620).
     *  CICS resources field testing: open (5 public / 0 private estates). */
    protected Optional<String> readqTsHcnoneL27() {
        return tempStorage.readItem("HCNONE", 1);
    }

    /** EXEC CICS READQ TS QUEUE('HCNONE') INTO(WS-JUNK) ITEM(1) at src/HCSUB.cbl:37 (#3620).
     *  CICS resources field testing: open (5 public / 0 private estates). */
    protected Optional<String> readqTsHcnoneL37() {
        return tempStorage.readItem("HCNONE", 1);
    }

    // ------------------------------------------------------------------------------------------------
    // The PROCEDURE DIVISION
    // ------------------------------------------------------------------------------------------------

    // SUB-MAIN (lines 22-45)
    private void subMain(CicsTask task, HcsubDfhcommarea ca) {
        // line 23: MOVE 's' TO CA-TRAIL(1:1)
        ca.setCaTrail(overlay(ca.getCaTrail(), CA_TRAIL_LEN, 1, 's'));

        // line 24: ADD 1 TO CA-COUNT (PIC S9(4) COMP, no SIZE ERROR: high-order digits lost past 9999)
        ca.setCaCount(addToCount(ca.getCaCount(), 1));

        // line 25: EVALUATE CA-MODE
        String caMode = pad(ca.getCaMode(), CA_MODE_LEN);
        if ("Q".equals(caMode)) {
            // WHEN 'Q'
            // lines 27-29: EXEC CICS READQ TS QUEUE('HCNONE') INTO(WS-JUNK) LENGTH(WS-JLEN) ITEM(1) -- no RESP,
            // no HANDLE CONDITION in HCSUB (the linking program's are not inherited): an error condition
            // takes CICS's default action, an abend searched through the exits from this level upward.
            CicsTask.TsResult read = task.readqTs(QUEUE_HCNONE, 1, WS_JLEN_INITIAL);
            if (!"NORMAL".equals(read.resp())) {
                String label = task.abendOnCondition(read.resp());
                if (LABEL_SUB_ABEND.equals(label)) {
                    // this program's own exit took it (not reachable in mode 'Q': HANDLE ABEND is only
                    // issued in mode 'A', and WORKING-STORAGE / handlers are fresh on every LINK)
                    subAbend(task, ca);
                }
                // null: a linking program's exit took the abend, or the task was terminated -- stop now
                return;
            }
            // WS-JUNK receives read.data(), WS-JLEN read.length(); neither is used afterwards.
            // line 30: MOVE 'x' TO CA-TRAIL(2:1)
            ca.setCaTrail(overlay(ca.getCaTrail(), CA_TRAIL_LEN, 2, 'x'));
        } else if ("A".equals(caMode)) {
            // WHEN 'A'
            // line 32: EXEC CICS HANDLE ABEND LABEL(SUB-ABEND)
            task.handleAbend(LABEL_SUB_ABEND);
            // line 33: MOVE 'h' TO CA-TRAIL(2:1)
            ca.setCaTrail(overlay(ca.getCaTrail(), CA_TRAIL_LEN, 2, 'h'));
            // line 34: EXEC CICS ABEND ABCODE('HCX1')
            String label = task.abend("HCX1");
            if (LABEL_SUB_ABEND.equals(label)) {
                // this program's exit (HANDLE ABEND, line 32) took the abend: control goes to SUB-ABEND,
                // which ends with RETURN
                onAbendL32(new CicsAbendException("HCX1", PROGRAM, "src/HCSUB.cbl:34"));
                return;
            }
            if (label == null) {
                // an exit above took it, or the task was terminated
                return;
            }
            // line 35: MOVE 'x' TO CA-TRAIL(3:1)
            // DEFECT kept: unreachable -- ABEND never returns to the next statement, and SUB-ABEND ends in
            // RETURN. One-line fix (business decision): delete line 35.
            ca.setCaTrail(overlay(ca.getCaTrail(), CA_TRAIL_LEN, 3, 'x'));
        } else {
            // WHEN OTHER
            // lines 37-39: EXEC CICS READQ TS QUEUE('HCNONE') INTO(WS-JUNK) LENGTH(WS-JLEN) ITEM(1) RESP(WS-RESP)
            CicsTask.TsResult read = task.readqTs(QUEUE_HCNONE, 1, WS_JLEN_INITIAL);
            String wsResp = read.resp();
            // line 40: IF WS-RESP = DFHRESP(QIDERR)
            if ("QIDERR".equals(wsResp)) {
                // line 41: MOVE 'QIDR' TO CA-RESULT
                ca.setCaResult(pad("QIDR", CA_RESULT_LEN));
            }
            // line 43: MOVE 'n' TO CA-TRAIL(2:1)
            ca.setCaTrail(overlay(ca.getCaTrail(), CA_TRAIL_LEN, 2, 'n'));
        }
        // line 44: END-EVALUATE
        // line 45: EXEC CICS RETURN -- back to the linking program (a plain RETURN at level 1)
        task.returnTransid(null, null);
    }

    // SUB-ABEND (lines 46-50)
    private void subAbend(CicsTask task, HcsubDfhcommarea ca) {
        // line 47: EXEC CICS ASSIGN ABCODE(WS-ABCODE)
        String wsAbcode = pad(task.abcode(), WS_ABCODE_LEN);
        // line 48: MOVE WS-ABCODE TO CA-RESULT
        ca.setCaResult(pad(wsAbcode, CA_RESULT_LEN));
        // line 49: MOVE 'a' TO CA-TRAIL(3:1)
        ca.setCaTrail(overlay(ca.getCaTrail(), CA_TRAIL_LEN, 3, 'a'));
        // line 50: EXEC CICS RETURN
        task.returnTransid(null, null);
    }

    // ------------------------------------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------------------------------------

    /** ADD n TO CA-COUNT, PIC S9(4) COMP under TRUNC(STD): the result keeps its sign and low four digits. */
    private static Integer addToCount(Integer count, int n) {
        long sum = (count == null ? 0L : count.longValue()) + n;
        long magnitude = Math.abs(sum) % CA_COUNT_MODULUS;
        return (int) (sum < 0 ? -magnitude : magnitude);
    }

    /** MOVE c TO field(pos:1): the field as its PIC X(len) storage (space-padded), one byte replaced. */
    private static String overlay(String field, int len, int pos, char c) {
        StringBuilder b = new StringBuilder(pad(field, len));
        b.setCharAt(pos - 1, c);
        return b.toString();
    }

    /** An alphanumeric field as its PIC X(len) storage: padded with spaces or truncated on the right. */
    private static String pad(String s, int len) {
        StringBuilder b = new StringBuilder(s == null ? "" : s);
        while (b.length() < len) {
            b.append(' ');
        }
        b.setLength(len);
        return b.toString();
    }
}
