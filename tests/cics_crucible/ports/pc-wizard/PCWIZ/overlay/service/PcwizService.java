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

    /** A CICS transaction entered the program (#4343): one task of it in the region (CicsTask.region()),
     *  ENTER pressed -- `request` its COMMAREA, null when started from a cleared screen -- run through runTask. Returns the COMMAREA its RETURN passes on (null: none).
     *  The COMMAREA crosses programs (#4427): COBOL passes bytes, and each program reads them through its
     *  own record.
     *  It answers PcwizWsState all the same (#4449): the other records a task of it can RETURN
     *  (PcconfWsState) cut their bytes as PcwizWsState does, so task.returned converts
     *  them by layout and loses nothing.
     *  The flows:
     *  out: RETURN TRANSID(PC03) COMMAREA(WS-STATE) at src/PCWIZ.cbl:78 -> src/PCCONF.cbl (PcconfWsState besides PcwizWsState).
     */
    public PcwizWsState handleTransaction(String transid, PcwizWsState request) {
        log.info("Pcwiz: handleTransaction");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "PCWIZ", this::runTask);
        return task.returned(PcwizWsState.class);
    }

    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region
     *  (CicsTask.region()), run through runTask on `request`, passed by reference -- what it changes, the caller sees. */
    public PcwizWsState handleLink(PcwizWsState request) {
        log.info("Pcwiz: handleLink");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("PCWIZ", request);
        region.run(task, "PCWIZ", this::runTask);
        return request;
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
