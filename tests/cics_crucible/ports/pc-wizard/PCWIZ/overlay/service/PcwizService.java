package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.PcwizWsState;
import com.gitgalaxy.modernized.dto.screen.Pcm1Screen;
import com.gitgalaxy.modernized.dto.screen.Pcm2Screen;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * RECEIVE at line 48 tests NORMAL
 * Screens (#3619): Pcm1Screen, Pcm2Screen.
 *
 * PCWIZ (src/PCWIZ.cbl): steps 1-2 of the pc-wizard. Runs as PC01 (first entry, EIBCALEN = 0), PC02
 * (name screen answered), and is XCTLed to from PCCONF (PF7 = back) under PC03. Every task ends in
 * RETURN TRANSID(next) COMMAREA(WS-STATE) LENGTH(30), or a plain RETURN after PF3.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class PcwizService {

    private static final Logger log = LoggerFactory.getLogger(PcwizService.class);

    private static final String MAPSET = "PCSET";
    private static final String MAP1 = "PCM1";
    private static final String MAP2 = "PCM2";

    /** DFHAID values as CicsTask.aid() reports them. */
    private static final String DFHPF3 = "PF3";
    private static final String DFHCLEAR = "CLEAR";

    /** 01 WS-BYE PIC X(16) VALUE 'WIZARD CANCELLED'. */
    private static final String WS_BYE = "WIZARD CANCELLED";

    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);
    /** WS-AMT-DIGITS PIC 9(7): 7 integer digits kept. */
    private static final BigDecimal TEN_POWER_7 = BigDecimal.TEN.pow(7);

    /** WORKING-STORAGE of one task: a fresh copy per task, as CICS gives each task its own. */
    private static final class Work {
        /** 01 WS-STATE (COPY PCSTATE), 30 bytes. */
        PcwizWsState state = new PcwizWsState();
        /** 01 WS-RESP PIC S9(8) COMP VALUE 0. */
        String resp = "NORMAL";
        /** 01 WS-MSG PIC X(40) VALUE SPACES. */
        String msg = spaces(40);
        /** 01 WS-AMT-DIGITS PIC 9(7) VALUE 0. */
        BigDecimal amtDigits = BigDecimal.ZERO;
    }

    public void executePcwiz(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for PCWIZ");
        // PCWIZ is a CICS program with no batch entry: its PROCEDURE DIVISION is ported in runTask(CicsTask).
        log.info("PCWIZ runs only as a CICS transaction (PC01 / PC02 / XCTL from PCCONF); see runTask");
    }

    /** A CICS transaction entered the program: runs one task with no screen input (a RECEIVE MAP is MAPFAIL)
     *  and returns the COMMAREA the task's RETURN passes on (the request itself when it ended with a plain
     *  RETURN). */
    public PcwizWsState handleTransaction(String transid, PcwizWsState request) {
        log.info("Pcwiz: handleTransaction");
        CicsTask task = new CicsTask(transid, "ENTER", request, Map.of());
        runTask(task);
        return returnedCommarea(task, request);
    }

    /** Another program XCTLed to this one (PCCONF's PF7, still under PC03): the same PROCEDURE DIVISION. */
    public PcwizWsState handleLink(PcwizWsState request) {
        log.info("Pcwiz: handleLink");
        CicsTask task = new CicsTask("PC03", "PF7", request, Map.of());
        runTask(task);
        return returnedCommarea(task, request);
    }

    /** One pseudo-conversational task of this program (#3754). */
    public void runTask(CicsTask task) {
        log.info("Pcwiz: runTask");
        Work w = new Work();

        // ---- MAIN-PARA ----
        if (!task.hasCommarea()) {                       // IF EIBCALEN = 0
            initializeWsState(w);                        // INITIALIZE WS-STATE
            w.state.setPcStep(1);                        // MOVE 1 TO PC-STEP
            w.msg = alnum("TYPE YOUR NAME", 40);         // MOVE 'TYPE YOUR NAME' TO WS-MSG
            sendStep1(task, w);                          // PERFORM SEND-STEP1 (ends in RETURN)
            return;
        }
        // MOVE DFHCOMMAREA TO WS-STATE (30-byte group move)
        w.state = copyOf(task.commarea(PcwizWsState.class));

        String aid = task.aid();
        // EVALUATE TRUE
        if (DFHPF3.equals(aid)) {                                     // WHEN EIBAID = DFHPF3
            cancelWizard(task);                                       // PERFORM CANCEL-WIZARD
            return;
        } else if ("Y".equals(alnum(w.state.getPcBack(), 1))) {       // WHEN PC-BACK = 'Y'
            // Kept: PC-BACK is tested before CLEAR, so CLEAR on a back-navigated state shows step 2.
            w.state.setPcBack("N");                                   // MOVE 'N' TO PC-BACK
            w.state.setPcStep(2);                                     // MOVE 2 TO PC-STEP
            w.msg = alnum("CHANGE THE AMOUNT", 40);                   // MOVE 'CHANGE THE AMOUNT' TO WS-MSG
            sendStep2(task, w);                                       // PERFORM SEND-STEP2
            return;
        } else if (DFHCLEAR.equals(aid)) {                            // WHEN EIBAID = DFHCLEAR
            w.msg = alnum("SCREEN RESTORED", 40);                     // MOVE 'SCREEN RESTORED' TO WS-MSG
            sendStep1(task, w);                                       // PERFORM SEND-STEP1
            return;
        } else {                                                      // WHEN OTHER
            takeName(task, w);                                        // PERFORM TAKE-NAME
            return;
        }
        // END-EVALUATE. Every branch ends the task in RETURN, so MAIN-PARA never falls through into TAKE-NAME.
    }

    // ---- TAKE-NAME ----
    private void takeName(CicsTask task, Work w) {
        // MOVE LOW-VALUES TO PCM1I: NAMEL = 0, NAMEI = low-values
        int namel = 0;
        String namei = lowValues(15);
        // EXEC CICS RECEIVE MAP('PCM1') MAPSET('PCSET') INTO(PCM1I) RESP(WS-RESP)
        Optional<Pcm1Screen> received = task.receive(MAP1, MAPSET, Pcm1Screen.class);
        w.resp = received.isPresent() ? "NORMAL" : "MAPFAIL";
        if (received.isPresent()) {
            String typed = received.get().getName();
            if (typed != null) {
                String data = stripTrailingNulls(typed);
                namel = Math.min(data.length(), 15);
                if (namel > 0) {
                    // NAME is JUSTIFY=(LEFT,BLANK): the input is left-justified and padded with blanks
                    namei = alnum(data, 15);
                }
            }
        }
        // IF WS-RESP NOT = DFHRESP(NORMAL) OR NAMEL = 0
        if (!"NORMAL".equals(w.resp) || namel == 0) {
            // ADD 1 TO PC-ERRORS (S9(4) COMP, no SIZE ERROR: the low-order 4 digits are kept, TRUNC(STD))
            // Kept defect: PC-ERRORS is counted but never reset nor read by PCWIZ.
            // Fix: MOVE 0 TO PC-ERRORS once a name is accepted (or drop the counter).
            w.state.setPcErrors((nz(w.state.getPcErrors()) + 1) % 10000);
            w.msg = alnum("NAME IS REQUIRED", 40);     // MOVE 'NAME IS REQUIRED' TO WS-MSG
            sendStep1(task, w);                        // PERFORM SEND-STEP1 (ends in RETURN)
            return;
        }
        // Kept defect: a name typed as spaces only has NAMEL > 0 and is accepted as blank.
        // Fix: IF WS-RESP NOT = DFHRESP(NORMAL) OR NAMEL = 0 OR NAMEI = SPACES.
        w.state.setPcName(namei);                              // MOVE NAMEI TO PC-NAME
        w.state.setPcStep(2);                                  // MOVE 2 TO PC-STEP
        w.msg = alnum("TYPE THE AMOUNT IN CENTS", 40);         // MOVE 'TYPE THE AMOUNT IN CENTS' TO WS-MSG
        sendStep2(task, w);                                    // PERFORM SEND-STEP2
    }

    // ---- SEND-STEP1 ----
    private void sendStep1(CicsTask task, Work w) {
        Pcm1Screen screen = buildPcm1(w.msg);
        // EXEC CICS SEND MAP('PCM1') MAPSET('PCSET') FROM(PCM1O) ERASE
        task.sendMap(MAP1, MAPSET, screen, new CicsTask.MapSubfields(), "ERASE");
        // EXEC CICS RETURN TRANSID('PC02') COMMAREA(WS-STATE) LENGTH(30)
        task.returnTransid("PC02", w.state, 30);
    }

    /** SEND-STEP1's MOVE LOW-VALUES TO PCM1O / MOVE WS-MSG TO MSG1O. */
    private static Pcm1Screen buildPcm1(String wsMsg) {
        Pcm1Screen screen = new Pcm1Screen();
        screen.setName(lowValues(15));        // MOVE LOW-VALUES TO PCM1O
        screen.setMsg1(lowValues(40));
        screen.setMsg1(alnum(wsMsg, 40));     // MOVE WS-MSG TO MSG1O
        return screen;
    }

    // ---- SEND-STEP2 ----
    private void sendStep2(CicsTask task, Work w) {
        Pcm2Screen screen = buildPcm2(w);
        // EXEC CICS SEND MAP('PCM2') MAPSET('PCSET') FROM(PCM2O) ERASE
        task.sendMap(MAP2, MAPSET, screen, new CicsTask.MapSubfields(), "ERASE");
        // EXEC CICS RETURN TRANSID('PC03') COMMAREA(WS-STATE) LENGTH(30)
        task.returnTransid("PC03", w.state, 30);
    }

    /** SEND-STEP2's moves into PCM2O. */
    private static Pcm2Screen buildPcm2(Work w) {
        Pcm2Screen screen = new Pcm2Screen();
        // MOVE LOW-VALUES TO PCM2O
        screen.setNameout(lowValues(15));
        screen.setAmt(lowValues(7));
        screen.setMsg2(lowValues(40));
        // MOVE PC-NAME TO NAMEOUTO
        screen.setNameout(alnum(w.state.getPcName(), 15));
        // IF PC-AMOUNT > 0
        BigDecimal amount = w.state.getPcAmount() == null ? BigDecimal.ZERO : w.state.getPcAmount();
        if (amount.signum() > 0) {
            // COMPUTE WS-AMT-DIGITS = PC-AMOUNT * 100 (no ROUNDED: truncated; 9(7) unsigned keeps 7 digits)
            w.amtDigits = amount.multiply(HUNDRED).setScale(0, RoundingMode.DOWN).abs().remainder(TEN_POWER_7);
            // MOVE WS-AMT-DIGITS TO AMTO: the 7 display digits
            screen.setAmt(String.format(Locale.ROOT, "%07d", w.amtDigits.longValueExact()));
        }
        // Kept: an amount of zero or below leaves AMTO as LOW-VALUES (the field goes out empty).
        // MOVE WS-MSG TO MSG2O
        screen.setMsg2(alnum(w.msg, 40));
        return screen;
    }

    // ---- CANCEL-WIZARD ----
    private void cancelWizard(CicsTask task) {
        // EXEC CICS SEND TEXT FROM(WS-BYE) LENGTH(16) ERASE
        task.sendText(WS_BYE, 16, "ERASE");
        // EXEC CICS RETURN
        task.returnTransid(null, null);
    }

    /** SEND MAP(PCM1) MAPSET(PCSET) FROM(PCM1O) at src/PCWIZ.cbl:63 (#3619): SEND-STEP1's moves, with the
     *  screen's msg1 as WS-MSG. */
    public Pcm1Screen renderPcm1(Pcm1Screen screen) {
        return buildPcm1(screen == null ? spaces(40) : screen.getMsg1());
    }

    /** RECEIVE MAP(PCM1) MAPSET(PCSET) INTO(PCM1I) at src/PCWIZ.cbl:48 (#3619): runs the PC02 task on a
     *  step-1 state with this input and key, and returns the screen it sends next -- null when the task
     *  sent text instead (PF3: WIZARD CANCELLED). */
    public ScreenModel submitPcm1(Pcm1Screen input, String aid) {
        Work w = new Work();
        initializeWsState(w);
        w.state.setPcStep(1);
        Map<String, Object> received = input == null ? Map.of() : Map.of(MAP1, input);
        CicsTask task = new CicsTask("PC02", aid, w.state, received);
        runTask(task);
        ScreenModel next = null;
        List<Map<String, Object>> events = task.events();
        for (Map<String, Object> e : events) {
            if ("SEND-MAP".equals(e.get("event")) && e.get("screen") instanceof ScreenModel s) {
                next = s;
            }
        }
        return next;
    }

    /** SEND MAP(PCM2) MAPSET(PCSET) FROM(PCM2O) at src/PCWIZ.cbl:76 (#3619): the moves SEND-STEP2 makes,
     *  taking PC-NAME from nameout, the amount digits from amt and WS-MSG from msg2. */
    public Pcm2Screen renderPcm2(Pcm2Screen screen) {
        Pcm2Screen out = new Pcm2Screen();
        out.setNameout(alnum(screen == null ? null : screen.getNameout(), 15));
        out.setAmt(screen == null || screen.getAmt() == null ? lowValues(7) : alnum(screen.getAmt(), 7));
        out.setMsg2(alnum(screen == null ? null : screen.getMsg2(), 40));
        return out;
    }

    // ---- helpers ----

    /** INITIALIZE WS-STATE: numeric fields to zero, alphanumeric fields to spaces. */
    private static void initializeWsState(Work w) {
        PcwizWsState s = new PcwizWsState();
        s.setPcStep(0);
        s.setPcName(spaces(15));
        s.setPcAmount(BigDecimal.ZERO.setScale(2));
        s.setPcErrors(0);
        s.setPcBack(spaces(1));
        s.setPcSpare(spaces(7));
        w.state = s;
    }

    /** MOVE DFHCOMMAREA TO WS-STATE: WS-STATE is the program's own storage, not the COMMAREA itself. */
    private static PcwizWsState copyOf(PcwizWsState from) {
        PcwizWsState s = new PcwizWsState();
        if (from != null) {
            s.setPcStep(from.getPcStep());
            s.setPcName(from.getPcName());
            s.setPcAmount(from.getPcAmount());
            s.setPcErrors(from.getPcErrors());
            s.setPcBack(from.getPcBack());
            s.setPcSpare(from.getPcSpare());
        }
        return s;
    }

    private static PcwizWsState returnedCommarea(CicsTask task, PcwizWsState fallback) {
        PcwizWsState out = fallback;
        for (Map<String, Object> e : task.events()) {
            if ("RETURN".equals(e.get("event")) && e.get("commarea") instanceof PcwizWsState s) {
                out = s;
            }
        }
        return out;
    }

    /** MOVE to PIC X(n): padded with spaces or truncated on the right. */
    private static String alnum(String value, int length) {
        String v = value == null ? "" : value;
        if (v.length() >= length) {
            return v.substring(0, length);
        }
        return v + " ".repeat(length - v.length());
    }

    private static String spaces(int length) {
        return " ".repeat(length);
    }

    private static String lowValues(int length) {
        return "\u0000".repeat(length);
    }

    private static String stripTrailingNulls(String s) {
        int end = s.length();
        while (end > 0 && s.charAt(end - 1) == '\u0000') {
            end--;
        }
        return s.substring(0, end);
    }

    private static int nz(Integer value) {
        return value == null ? 0 : value;
    }
}
