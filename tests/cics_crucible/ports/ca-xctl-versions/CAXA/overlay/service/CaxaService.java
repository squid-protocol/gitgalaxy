package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CaxbDfhcommarea;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.Locale;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * no IF tests the RESP of the XCTL at line 52 (paragraph MAIN-PARA). The program falls through to the
 * failure report whatever WS-RESP holds. This is correct only because a successful XCTL never returns.
 * DEFECT kept: the RESP is never tested.
 *   One-line fix: IF WS-RESP NOT = DFHRESP(NORMAL) around the report.
 *
 * CAXA is an old version-1 front end (transaction CA02, csd/ca-xctl-versions.csd group CRUCCA2).
 * It XCTLs to CAXB, which declares a version-2, 80-byte DFHCOMMAREA. The sixth byte of the terminal
 * input selects the mode:
 * <ul>
 *   <li>S: XCTL LENGTH(10).</li>
 *   <li>L: XCTL LENGTH(80), which passes WS-V1 plus 70 bytes of neighbouring storage.</li>
 *   <li>Anything else: XCTL LENGTH(32767), which always fails with LENGERR.</li>
 * </ul>
 */
@Service
@Transactional
@RequiredArgsConstructor
public class CaxaService {

    private static final Logger log = LoggerFactory.getLogger(CaxaService.class);

    /** WS-INLEN PIC S9(4) COMP VALUE 20: the RECEIVE length, and the size of WS-INPUT PIC X(20). */
    private static final int WS_INLEN = 20;
    /** WS-BIGLEN PIC S9(4) COMP-5 VALUE 32767. COMP-5 holds the full halfword, so 32767 is stored as is. */
    private static final int WS_BIGLEN = 32767;
    /** WS-BIG PIC X(32767). */
    private static final int WS_BIG_LEN = 32767;
    /** WS-REPORT PIC X(40). */
    private static final int WS_REPORT_LEN = 40;

    private final ObjectProvider<CaxbService> caxbService;

    public void executeCaxa(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for CAXA");
        // CAXA is a CICS-only program (transaction CA02). It has no batch or controller behaviour.
        // Its whole PROCEDURE DIVISION (MAIN-PARA) is ported into runTask(CicsTask).
    }

    /** A CICS transaction entered the program. */
    public void handleTransaction(String transid) {
        // Transaction CA02 enters CAXA. The task itself (terminal RECEIVE, XCTL, SEND TEXT, RETURN)
        // is ported in runTask(CicsTask). The CICS runtime drives it with the task it builds.
        log.info("Caxa: handleTransaction {}", transid);
    }

    /** One pseudo-conversational task of this program (#3754). */
    public void runTask(CicsTask task) {
        log.info("Caxa: runTask");

        // ---- MAIN-PARA ------------------------------------------------------------------
        // EXEC CICS RECEIVE INTO(WS-INPUT) LENGTH(WS-INLEN) END-EXEC   (line 39)
        // There is no RESP and no HANDLE CONDITION. A LENGERR (input longer than 20 bytes) therefore
        // takes CICS's default action and abends the task with AEIV.
        // DEFECT kept: typing more than 20 characters abends the task (AEIV).
        //   One-line fix: code RESP(WS-RESP) on the RECEIVE.
        CicsTask.Received received = task.receiveText(WS_INLEN);
        if (!"NORMAL".equals(received.resp())) {
            task.abendOnCondition(received.resp());  // no HANDLE ABEND here: always null, so stop
            return;
        }
        // RECEIVE INTO moves only the bytes received. The rest of WS-INPUT keeps its VALUE SPACES.
        String wsInput = padRight(received.data(), WS_INLEN);
        // RECEIVE sets WS-INLEN to received.length(). The program never reads it again.

        // MOVE WS-INPUT(6:1) TO WS-MODE   (line 41)
        String wsMode = wsInput.substring(5, 6);

        int wsResp = 0;   // WS-RESP  PIC S9(8) COMP VALUE 0
        int wsResp2 = 0;  // WS-RESP2 PIC S9(8) COMP VALUE 0

        // EVALUATE WS-MODE   (lines 42-56)
        switch (wsMode) {
            case "S" -> {
                // WHEN 'S': EXEC CICS XCTL PROGRAM('CAXB') COMMAREA(WS-V1) LENGTH(10)   (line 44)
                // There is no RESP. A failure (PGMIDERR) is an unhandled condition, so the task abends.
                String resp = task.xctl("CAXB", wsV1Commarea(false), 10);
                if (!"NORMAL".equals(resp)) {
                    task.abendOnCondition(resp);
                }
                return;  // either XCTL transferred control, or the task has abended
            }
            case "L" -> {
                // WHEN 'L': EXEC CICS XCTL PROGRAM('CAXB') COMMAREA(WS-V1) LENGTH(80)   (line 48)
                // DEFECT kept: LENGTH(80) is longer than WS-V1 (10 bytes). CICS copies the 70 bytes
                // that follow WS-V1 in WORKING-STORAGE (WS-NEIGHBOUR). CAXB then reads them as
                // V2-TIER, V2-BALANCE and V2-NOTE.
                //   One-line fix: build an 80-byte version-2 COMMAREA (copy/CAV2.cpy) and XCTL that.
                String resp = task.xctl("CAXB", wsV1Commarea(true), 80);
                if (!"NORMAL".equals(resp)) {
                    task.abendOnCondition(resp);
                }
                return;
            }
            default -> {
                // WHEN OTHER: EXEC CICS XCTL PROGRAM('CAXB') COMMAREA(WS-BIG) LENGTH(WS-BIGLEN)
                //             RESP(WS-RESP) RESP2(WS-RESP2)   (line 52)
                // WS-BIG is a plain PIC X(32767) item that no generated DTO describes, so it is passed
                // as a String of its 32767 characters (#3989): VALUE SPACES, never changed.
                // DEFECT kept: WS-BIGLEN = 32767 is outside 0..32763. This XCTL therefore always fails
                // with LENGERR (RESP2 11), including for a blank mode (a bare "CA02").
                //   One-line fix: pass LENGTH(80) with a version-2 COMMAREA.
                String resp = task.xctl("CAXB", wsBig(), WS_BIGLEN);
                wsResp = dfhresp(resp);
                wsResp2 = resp2(resp);
                if ("NORMAL".equals(resp)) {
                    return;  // XCTL transferred control: nothing after it runs in CAXA
                }
            }
        }

        // Only reached when the XCTL at line 52 failed   (line 57)
        // MOVE WS-RESP TO WS-RESP-D; MOVE WS-RESP2 TO WS-RESP2-D   (lines 58-59)
        // Each target is an unsigned PIC 99: the sign is dropped and high-order digits are truncated.
        String wsRespD = pic99(wsResp);
        String wsResp2D = pic99(wsResp2);

        // STRING 'XCTL FAILED RESP=' WS-RESP-D ' RESP2=' WS-RESP2-D DELIMITED BY SIZE INTO WS-REPORT
        //   (line 60). STRING does not pad. WS-REPORT starts as VALUE SPACES, so the tail stays blank.
        String wsReport = padRight("XCTL FAILED RESP=" + wsRespD + " RESP2=" + wsResp2D, WS_REPORT_LEN);

        // EXEC CICS SEND TEXT FROM(WS-REPORT) LENGTH(40) ERASE END-EXEC   (line 62)
        task.sendText(wsReport, WS_REPORT_LEN, "ERASE");

        // EXEC CICS RETURN END-EXEC   (line 64)
        task.returnTransid(null, null);
    }

    /**
     * WS-V1 as CAXB's DFHCOMMAREA sees it, byte for byte:
     * V1-VERSION '1', V1-CUSTID 'C0042' and V1-VISITS 7 overlay V2-VERSION, V2-CUSTID and V2-VISITS.
     * <p>
     * With {@code withNeighbour} (LENGTH(80)), the next 70 bytes are WS-NEIGHBOUR: NB-TIER 'GOLD',
     * NB-BALANCE +12345.67 COMP-3 and NB-NOTE. They occupy exactly V2-TIER, V2-BALANCE (same PICTURE)
     * and V2-NOTE.
     * <p>
     * With LENGTH(10), no bytes past offset 10 are passed.
     */
    private static CaxbDfhcommarea wsV1Commarea(boolean withNeighbour) {
        CaxbDfhcommarea c = new CaxbDfhcommarea();
        c.setV2Version("1");                                        // V1-VERSION PIC X VALUE '1'
        c.setV2Custid("C0042");                                     // V1-CUSTID PIC X(5) VALUE 'C0042'
        c.setV2Visits(7);                                           // V1-VISITS PIC 9(4) VALUE 7
        if (withNeighbour) {
            c.setV2Tier(padRight("GOLD", 10));                      // NB-TIER PIC X(10) VALUE 'GOLD'
            c.setV2Balance(BigDecimal.valueOf(1234567L, 2));        // NB-BALANCE S9(7)V99 COMP-3 +12345.67
            c.setV2Note(padRight("NEIGHBOUR STORAGE, NOT V1", 55)); // NB-NOTE PIC X(55)
        }
        return c;
    }

    /** WS-BIG PIC X(32767) VALUE SPACES: a plain item, passed as a String of its 32767 characters (#3989). */
    private static String wsBig() {
        return " ".repeat(WS_BIG_LEN);
    }

    /** The DFHRESP value RESP() stores for an XCTL condition. */
    private static int dfhresp(String condition) {
        return switch (condition) {
            case "NORMAL" -> 0;
            case "INVREQ" -> 16;
            case "LENGERR" -> 22;
            case "PGMIDERR" -> 27;
            case "NOTAUTH" -> 70;
            default -> 0;
        };
    }

    /** The RESP2 of an XCTL condition, as CicsTask.xctl records it. */
    private static int resp2(String condition) {
        return switch (condition) {
            case "LENGERR" -> 11;
            case "PGMIDERR" -> 1;
            default -> 0;
        };
    }

    /** MOVE of a binary field to an unsigned PIC 99: the absolute value, high-order digits truncated. */
    private static String pic99(int value) {
        long v = Math.abs((long) value) % 100;
        return String.format(Locale.ROOT, "%02d", v);
    }

    /** Alphanumeric MOVE: pad with spaces, or truncate on the right. */
    private static String padRight(String s, int len) {
        String v = s == null ? "" : s;
        if (v.length() >= len) {
            return v.substring(0, len);
        }
        StringBuilder sb = new StringBuilder(len).append(v);
        while (sb.length() < len) {
            sb.append(' ');
        }
        return sb.toString();
    }

    /** EXEC CICS XCTL PROGRAM(CAXB) at src/CAXA.cbl:44, src/CAXA.cbl:48, src/CAXA.cbl:52. XCTL transfers control: nothing after it runs in the caller.
     *  Call targets field testing: open (6 public / 0 private estates). */
    // How each site's COMMAREA is mapped onto CAXB's 80-byte layout:
    //   - line 52 passes WS-BIG (32767 bytes) as a plain String of its characters (wsBig()); the XCTL
    //     fails with LENGERR before CAXB could see it;
    //   - lines 44 and 48 pass WS-V1 (10 bytes, plus 70 neighbour bytes at line 48), mapped by wsV1Commarea().
    // runTask issues all three through task.xctl, so the CICS runtime runs CAXB at the same level.
    public CaxbDfhcommarea xctlCaxb(CaxbDfhcommarea request) {
        return caxbService.getObject().handleLink(request);
    }

}
