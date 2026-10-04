package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.PcconfWsState;
import com.gitgalaxy.modernized.dto.contract.PcwizWsState;
import com.gitgalaxy.modernized.dto.screen.Pcm2Screen;
import com.gitgalaxy.modernized.dto.screen.Pcm3Screen;
import com.gitgalaxy.modernized.messaging.TempStorage;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.Charset;
import java.util.Locale;
import java.util.Optional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * RECEIVE at line 61 tests NORMAL
 * Screens (#3619): Pcm2Screen, Pcm3Screen.
 *
 * Port of PCCONF (src/PCCONF.cbl), transaction PC03: takes the amount (step 2), shows the
 * confirmation (step 3), posts on ENTER, goes back to PCWIZ on PF7 (XCTL), cancels on PF3,
 * redraws on CLEAR.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class PcconfService {

    private static final Logger log = LoggerFactory.getLogger(PcconfService.class);

    private static final String TRANSID = "PC03";
    private static final String MAPSET = "PCSET";
    private static final int COMMAREA_LENGTH = 30;

    /** WS-BYE PIC X(16) VALUE 'WIZARD CANCELLED'. */
    private static final String WS_BYE = "WIZARD CANCELLED";
    /** LG-SEP PIC X(3) VALUE ' E='. */
    private static final String LG_SEP = " E=";
    /** WS-POSTED's FILLER PIC X(8) VALUE 'POSTED: '. */
    private static final String POSTED_PREFIX = "POSTED: ";

    /** The region's code page for the TS item bytes (#4002: an item is the bytes the program wrote, in EBCDIC). */
    private static final Charset EBCDIC = Charset.forName("IBM037");

    private final ObjectProvider<PcwizService> pcwizService;
    private final TempStorage tempStorage;

    /** WORKING-STORAGE of one task: WS-STATE and WS-MSG (fresh per task, VALUE SPACES). */
    private static final class WorkingStorage {
        PcconfWsState state;
        String wsMsg = spaces(40);
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public PcconfWsState handleTransaction(String transid, PcconfWsState request) {
        log.info("Pcconf: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of this program (#3754). */
    public void runTask(CicsTask task) {
        log.info("Pcconf: runTask");

        // ---- MAIN-PARA ------------------------------------------------------------------------
        // MOVE DFHCOMMAREA TO WS-STATE
        // DEFECT (kept): the program never tests EIBCALEN before moving DFHCOMMAREA; with no COMMAREA
        // DFHCOMMAREA has no addressability and the MOVE fails with a protection exception (ASRA).
        // Fix: IF EIBCALEN = 0 ... (send step 2 / return) END-IF before the MOVE.
        if (!task.hasCommarea()) {
            task.abend("ASRA");
            return;
        }
        WorkingStorage ws = new WorkingStorage();
        ws.state = copyState(task.commarea(Object.class));

        String aid = task.aid();
        // EVALUATE TRUE
        if ("PF3".equals(aid)) {
            // WHEN EIBAID = DFHPF3
            task.sendText(WS_BYE, 16, "ERASE");
            task.returnTransid(null, null);
        } else if ("CLEAR".equals(aid)) {
            // WHEN EIBAID = DFHCLEAR
            ws.wsMsg = pad("SCREEN RESTORED", 40);
            if (pcStep(ws.state) == 3) {
                sendStep3(task, ws);
            } else {
                sendStep2(task, ws);
            }
        } else if (pcStep(ws.state) == 2) {
            // WHEN PC-STEP = 2 (before PF7 / ENTER: on step 2 any other key takes the amount)
            takeAmount(task, ws);
        } else if ("PF7".equals(aid)) {
            // WHEN EIBAID = DFHPF7
            ws.state.setPcBack("Y");
            String resp = task.xctl("PCWIZ", toPcwiz(ws.state), COMMAREA_LENGTH);
            if (!"NORMAL".equals(resp)) {
                // no RESP / HANDLE CONDITION: CICS's default action abends the task
                task.abendOnCondition(resp);
            }
        } else if ("ENTER".equals(aid)) {
            // WHEN EIBAID = DFHENTER
            postIt(task, ws);
        } else {
            // WHEN OTHER
            ws.wsMsg = pad("USE ENTER, PF7 OR PF3", 40);
            sendStep3(task, ws);
        }
        // END-EVALUATE.
        // DEFECT (kept): MAIN-PARA has no GOBACK, so control would fall through into TAKE-AMOUNT.
        // Every branch ends the task (RETURN / XCTL / abend), so this is reached only if one did not.
        // Fix: add EXEC CICS RETURN END-EXEC (or GOBACK) after END-EVALUATE.
        if (!task.ended()) {
            takeAmount(task, ws);
        }
    }

    // ---- TAKE-AMOUNT --------------------------------------------------------------------------
    private void takeAmount(CicsTask task, WorkingStorage ws) {
        // MOVE LOW-VALUES TO PCM2I
        int amtl = 0;
        String amti = lowValues(7);
        // EXEC CICS RECEIVE MAP('PCM2') MAPSET('PCSET') INTO(PCM2I) RESP(WS-RESP)
        Optional<Pcm2Screen> received = task.receive(Pcm2Screen.MAP, MAPSET, Pcm2Screen.class);
        boolean normal = received.isPresent();
        if (normal) {
            // 3270 input suppresses nulls; AMT is JUSTIFY=(RIGHT,ZERO): right-justified, zero-filled
            String typed = received.get().getAmt();
            String data = typed == null ? "" : typed.replace("\0", "");
            if (data.length() > 7) {
                data = data.substring(0, 7);
            }
            if (!data.isEmpty()) {
                amtl = data.length();
                amti = "0".repeat(7 - data.length()) + data;
            }
        }
        // IF WS-RESP NOT = DFHRESP(NORMAL) OR AMTL = 0 OR AMTI IS NOT NUMERIC
        if (!normal || amtl == 0 || !isNumeric(amti)) {
            // ADD 1 TO PC-ERRORS (S9(4) COMP, TRUNC(STD): high-order digits lost past 9999)
            ws.state.setPcErrors(addOneS9_4(ws.state.getPcErrors()));
            ws.wsMsg = pad("AMOUNT MUST BE DIGITS", 40);
            sendStep2(task, ws);
            if (task.ended()) {
                return;
            }
        }
        // MOVE AMTI TO WS-AMT-DIGITS (PIC 9(7); AMTI verified NUMERIC, digit by digit)
        long wsAmtDigits = 0;
        for (int i = 0; i < 7; i++) {
            wsAmtDigits = wsAmtDigits * 10 + (amti.charAt(i) - '0');
        }
        // COMPUTE PC-AMOUNT = WS-AMT-DIGITS / 100 (no ROUNDED: truncated into S9(5)V99)
        BigDecimal amount = BigDecimal.valueOf(wsAmtDigits)
                .divide(BigDecimal.valueOf(100), 2, RoundingMode.DOWN);
        ws.state.setPcAmount(fitS9_5V99(amount));
        // MOVE 3 TO PC-STEP
        ws.state.setPcStep(3);
        // PERFORM SEND-STEP3
        sendStep3(task, ws);
    }

    // ---- SEND-STEP2 ---------------------------------------------------------------------------
    private void sendStep2(CicsTask task, WorkingStorage ws) {
        Pcm2Screen screen = fillPcm2(ws);
        task.sendMap(Pcm2Screen.MAP, MAPSET, screen, "ERASE");
        task.returnTransid(TRANSID, copyState(ws.state), COMMAREA_LENGTH);
    }

    /** SEND-STEP2: the logic that fills PCM2O before SEND MAP('PCM2'). */
    private Pcm2Screen fillPcm2(WorkingStorage ws) {
        // MOVE LOW-VALUES TO PCM2O
        Pcm2Screen screen = new Pcm2Screen();
        screen.setNameout(lowValues(15));
        screen.setAmt(lowValues(7));
        screen.setMsg2(lowValues(40));
        // MOVE PC-NAME TO NAMEOUTO
        screen.setNameout(pad(ws.state.getPcName(), 15));
        // IF PC-AMOUNT > 0
        BigDecimal amount = pcAmount(ws.state);
        if (amount.signum() > 0) {
            // COMPUTE WS-AMT-DIGITS = PC-AMOUNT * 100 (PIC 9(7), unsigned, truncated)
            long wsAmtDigits = amount.movePointRight(2).setScale(0, RoundingMode.DOWN)
                    .abs().longValue() % 10_000_000L;
            // MOVE WS-AMT-DIGITS TO AMTO
            screen.setAmt(String.format(Locale.ROOT, "%07d", wsAmtDigits));
        }
        // MOVE WS-MSG TO MSG2O
        screen.setMsg2(pad(ws.wsMsg, 40));
        return screen;
    }

    // ---- SEND-STEP3 ---------------------------------------------------------------------------
    private void sendStep3(CicsTask task, WorkingStorage ws) {
        Pcm3Screen screen = fillPcm3(ws);
        task.sendMap(Pcm3Screen.MAP, MAPSET, screen, "ERASE");
        task.returnTransid(TRANSID, copyState(ws.state), COMMAREA_LENGTH);
    }

    /** SEND-STEP3: the logic that fills PCM3O before SEND MAP('PCM3'). */
    private Pcm3Screen fillPcm3(WorkingStorage ws) {
        // MOVE LOW-VALUES TO PCM3O
        Pcm3Screen screen = new Pcm3Screen();
        screen.setSumname(lowValues(15));
        screen.setSumamt(lowValues(10));
        screen.setMsg3(lowValues(40));   // low-values: the map's INITIAL (ENTER=POST ...) shows
        // MOVE PC-NAME TO SUMNAMEO
        screen.setSumname(pad(ws.state.getPcName(), 15));
        // MOVE PC-AMOUNT TO WS-AMT-ED ; MOVE WS-AMT-ED TO SUMAMTO
        screen.setSumamt(editZzzZz9V99(pcAmount(ws.state)));
        // IF WS-MSG NOT = SPACES MOVE WS-MSG TO MSG3O
        if (!ws.wsMsg.isBlank() || ws.wsMsg.chars().anyMatch(c -> c != ' ')) {
            screen.setMsg3(pad(ws.wsMsg, 40));
        }
        return screen;
    }

    // ---- POST-IT ------------------------------------------------------------------------------
    private void postIt(CicsTask task, WorkingStorage ws) {
        // MOVE PC-NAME TO LG-NAME
        String lgName = pad(ws.state.getPcName(), 15);
        // MOVE PC-AMOUNT TO LG-AMT (ZZZ,ZZ9.99)
        String lgAmt = editZzzZz9V99(pcAmount(ws.state));
        // MOVE PC-ERRORS TO LG-ERR (PIC 9(2): unsigned, high-order digits lost)
        int errors = ws.state.getPcErrors() == null ? 0 : ws.state.getPcErrors();
        String lgErr = String.format(Locale.ROOT, "%02d", Math.abs(errors) % 100);
        String wsLedger = lgName + lgAmt + LG_SEP + lgErr;   // 15 + 10 + 3 + 2 = 30
        // EXEC CICS WRITEQ TS QUEUE('PCLEDGER') FROM(WS-LEDGER) LENGTH(30)
        CicsTask.TsResult ts = task.writeqTs("PCLEDGER", wsLedger.getBytes(EBCDIC));
        if (!"NORMAL".equals(ts.resp())) {
            // no RESP / HANDLE CONDITION: CICS's default action abends the task
            task.abendOnCondition(ts.resp());
            return;
        }
        // MOVE WS-LEDGER TO WS-POST-DATA
        String wsPostData = pad(wsLedger, 30);
        // EXEC CICS SEND TEXT FROM(WS-POSTED) LENGTH(38) ERASE
        task.sendText(POSTED_PREFIX + wsPostData, 38, "ERASE");
        // EXEC CICS RETURN
        task.returnTransid(null, null);
    }

    /** EXEC CICS XCTL PROGRAM(PCWIZ) at src/PCCONF.cbl:50. XCTL transfers control: nothing after it runs in the caller.
     *  Call targets field testing: open (6 public / 0 private estates). */
    public PcwizWsState xctlPcwiz(PcwizWsState request) {
        return pcwizService.getObject().handleLink(request);
    }

    /** EXEC CICS WRITEQ TS QUEUE('PCLEDGER') FROM(WS-LEDGER) at src/PCCONF.cbl:104 (#3620).
     *  CICS resources field testing: open (5 public / 0 private estates). */
    protected int writeqTsPcledgerL104(String record) {
        return tempStorage.writeItem("PCLEDGER", record);
    }

    // ---- helpers ------------------------------------------------------------------------------

    /** MOVE DFHCOMMAREA TO WS-STATE: a copy of the 30-byte state (either program's DTO of PCSTATE). */
    private static PcconfWsState copyState(Object commarea) {
        PcconfWsState s = new PcconfWsState();
        if (commarea instanceof PcconfWsState c) {
            s.setPcStep(c.getPcStep());
            s.setPcName(c.getPcName());
            s.setPcAmount(c.getPcAmount());
            s.setPcErrors(c.getPcErrors());
            s.setPcBack(c.getPcBack());
            s.setPcSpare(c.getPcSpare());
        } else if (commarea instanceof PcwizWsState c) {
            s.setPcStep(c.getPcStep());
            s.setPcName(c.getPcName());
            s.setPcAmount(c.getPcAmount());
            s.setPcErrors(c.getPcErrors());
            s.setPcBack(c.getPcBack());
            s.setPcSpare(c.getPcSpare());
        }
        return s;
    }

    /** WS-STATE as the COMMAREA PCWIZ reads (same PCSTATE layout, 30 bytes). */
    private static PcwizWsState toPcwiz(PcconfWsState s) {
        PcwizWsState w = new PcwizWsState();
        w.setPcStep(s.getPcStep());
        w.setPcName(s.getPcName());
        w.setPcAmount(s.getPcAmount());
        w.setPcErrors(s.getPcErrors());
        w.setPcBack(s.getPcBack());
        w.setPcSpare(s.getPcSpare());
        return w;
    }

    private static int pcStep(PcconfWsState s) {
        return s.getPcStep() == null ? -1 : s.getPcStep();
    }

    private static BigDecimal pcAmount(PcconfWsState s) {
        return s.getPcAmount() == null ? BigDecimal.ZERO.setScale(2)
                : fitS9_5V99(s.getPcAmount().setScale(2, RoundingMode.DOWN));
    }

    /** A value stored into PIC S9(5)V99: decimals truncated, high-order digits past 5 lost. */
    private static BigDecimal fitS9_5V99(BigDecimal v) {
        BigDecimal t = v.setScale(2, RoundingMode.DOWN);
        return t.remainder(BigDecimal.valueOf(100000)).setScale(2, RoundingMode.DOWN);
    }

    /** ADD 1 TO a PIC S9(4) COMP field (TRUNC(STD): the result keeps its 4 low-order digits). */
    private static Integer addOneS9_4(Integer value) {
        int r = (value == null ? 0 : value) + 1;
        int t = Math.abs(r) % 10000;
        return r < 0 ? -t : t;
    }

    /** IS NUMERIC for PIC X: every character an (EBCDIC) digit 0-9. */
    private static boolean isNumeric(String s) {
        if (s == null || s.isEmpty()) {
            return false;
        }
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < '0' || c > '9') {
                return false;
            }
        }
        return true;
    }

    /** MOVE S9(5)V99 TO PIC ZZZ,ZZ9.99 (unsigned edit: the sign is dropped). */
    private static String editZzzZz9V99(BigDecimal value) {
        long cents = value.abs().movePointRight(2).setScale(0, RoundingMode.DOWN).longValue() % 100_000_000L;
        String digits = String.format(Locale.ROOT, "%08d", cents);   // 6 integer + 2 decimal positions
        StringBuilder sb = new StringBuilder(10);
        boolean significant = false;
        for (int i = 0; i < 6; i++) {
            if (i == 3) {
                sb.append(significant ? ',' : ' ');   // insertion comma blanked while suppressing
            }
            char c = digits.charAt(i);
            if (!significant && c == '0' && i < 5) {
                sb.append(' ');                        // Z positions
            } else {
                significant = true;
                sb.append(c);                          // the 9 position and every digit after a significant one
            }
        }
        sb.append('.').append(digits, 6, 8);
        return sb.toString();
    }

    /** MOVE to PIC X(n): padded with spaces or truncated on the right. */
    private static String pad(String s, int n) {
        String v = s == null ? "" : s;
        if (v.length() >= n) {
            return v.substring(0, n);
        }
        return v + " ".repeat(n - v.length());
    }

    private static String spaces(int n) {
        return " ".repeat(n);
    }

    private static String lowValues(int n) {
        return "\0".repeat(n);
    }
}
