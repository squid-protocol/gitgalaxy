package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.HxextWsCa;
import com.gitgalaxy.modernized.dto.screen.Hxm2Screen;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import org.springframework.transaction.annotation.Transactional;

/**
 * Port of HXEXT (src/HXEXT.cbl), transaction HX02, mapset HXSET2 / map HXM2.
 *
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * the RESP of RECEIVE at line 40 (paragraph CHECK-INPUT) is stored in WS-RESP and never tested.
 * The original's behaviour is kept: on MAPFAIL, HXM2I keeps the LOW-VALUES moved at line 39, so
 * ACCTL = 0 and the program takes the "ACCOUNT MUST BE 6 DIGITS" branch.
 * Screens (#3619): Hxm2Screen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class HxextService {

    private static final Logger log = LoggerFactory.getLogger(HxextService.class);

    private static final String MAP = "HXM2";
    private static final String MAPSET = "HXSET2";
    private static final String TRANSID = "HX02";
    private static final String PF5 = "PF5";

    /** Field lengths in the symbolic map (copy/HXSET2.cpy). */
    private static final int ACCT_LEN = 6;
    private static final int AMOUNT_LEN = 7;
    private static final int MSG_LEN = 30;

    /** DFHBMSCA values, as the EBCDIC bytes they hold. */
    private static final int DFHUNIMD = 0xC9;   // unprotected, bright, MDT
    private static final int DFHBMUNP = 0x40;   // unprotected
    private static final int DFHRED = 0xF2;     // extended colour red
    private static final int DFHBLINK = 0xF1;   // extended highlight blink
    private static final int X_F1 = 0xF1;       // X'F1' moved to MSGA (BLINK-MISTAKE)

    private static final char LOW_VALUE = '\u0000';

    /** One SEND MAP: the HXM2O data, the other subfields the program set, the options. */
    private record Send(Hxm2Screen screen, CicsTask.MapSubfields subfields, String[] options) {
    }

    /** A CICS transaction entered the program (#4343): one task of it in the region (CicsTask.region()),
     *  ENTER pressed -- `request` its COMMAREA, null when started from a cleared screen -- run through runTask. Returns the COMMAREA its RETURN passes on (null: none). */
    public HxextWsCa handleTransaction(String transid, HxextWsCa request) {
        log.info("Hxext: handleTransaction");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "HXEXT", this::runTask);
        return task.returned(HxextWsCa.class);
    }

    /** One pseudo-conversational task of this program (#3754). */
    public void runTask(CicsTask task) {
        log.info("Hxext: runTask");

        // MAIN-PARA
        // IF EIBCALEN = 0
        Integer eibcalen = task.eibcalen();
        boolean firstEntry = !task.hasCommarea() || (eibcalen != null && eibcalen == 0);
        if (firstEntry) {
            // MOVE LOW-VALUES TO HXM2O / MOVE 'ENTER ACCOUNT AND AMOUNT' TO MSGO
            // EXEC CICS SEND MAP('HXM2') MAPSET('HXSET2') FROM(HXM2O) ERASE
            send(task, firstEntryScreen());
        } else if (PF5.equals(task.aid())) {
            // IF EIBAID = DFHPF5 PERFORM BLINK-MISTAKE
            send(task, blinkMistake());
        } else {
            // ELSE PERFORM CHECK-INPUT
            checkInput(task);
        }

        // EXEC CICS RETURN TRANSID('HX02') COMMAREA(WS-CA) LENGTH(1)
        // WS-CA is WORKING-STORAGE with VALUE 'E', fresh in every task.
        task.returnTransid(TRANSID, newWsCa(), 1);
    }

    /** SEND MAP(HXM2) MAPSET(HXSET2) FROM(HXM2O): the first-entry HXM2O when none is given, else the
     *  screen as the program filled it. */
    public Hxm2Screen renderHxm2(Hxm2Screen screen) {
        return screen == null ? firstEntryScreen().screen() : screen;
    }

    // ------------------------------------------------------------------------------------------
    // Paragraphs
    // ------------------------------------------------------------------------------------------

    /** MAIN-PARA, EIBCALEN = 0 branch (lines 24-28). */
    private Send firstEntryScreen() {
        // MOVE LOW-VALUES TO HXM2O
        Hxm2Screen out = lowValueScreen();
        // MOVE 'ENTER ACCOUNT AND AMOUNT' TO MSGO
        out.setMsg(moveAlpha("ENTER ACCOUNT AND AMOUNT", MSG_LEN));
        // SEND MAP ... ERASE; every attribute / colour / highlight byte is LOW-VALUES (map defaults)
        return new Send(out, null, new String[] {"ERASE"});
    }

    /** CHECK-INPUT (lines 38-59): RECEIVE MAP then SEND MAP, through the task. */
    private void checkInput(CicsTask task) {
        // MOVE LOW-VALUES TO HXM2I
        // EXEC CICS RECEIVE MAP('HXM2') MAPSET('HXSET2') INTO(HXM2I) RESP(WS-RESP)
        // WS-RESP is never tested (MAPFAIL leaves HXM2I at LOW-VALUES).
        Hxm2Screen received = task.receive(MAP, MAPSET, Hxm2Screen.class).orElse(null);
        send(task, checkInput(received));
    }

    /** CHECK-INPUT (lines 39-59) on the received HXM2I (null: MAPFAIL). */
    private Send checkInput(Hxm2Screen received) {
        // MOVE LOW-VALUES TO HXM2I
        int acctL = 0;
        String acctI = lowValues(ACCT_LEN);
        String amountI = lowValues(AMOUNT_LEN);

        // RECEIVE MAP INTO(HXM2I): ACCT is JUSTIFY=(LEFT,BLANK), AMOUNT is JUSTIFY=(RIGHT,ZERO);
        // a field not received keeps its LOW-VALUES and a length of 0.
        if (received != null) {
            String acct = received.getAcct();
            if (acct != null && !acct.isEmpty()) {
                acctL = Math.min(acct.length(), ACCT_LEN);
                acctI = moveAlpha(acct, ACCT_LEN);
            }
            String amount = received.getAmount();
            if (amount != null && !amount.isEmpty()) {
                amountI = rightJustifyZero(amount, AMOUNT_LEN);
            }
        }

        // HXM2O REDEFINES HXM2I: ACCTO is ACCTI, AMOUNTO is AMOUNTI, MSGO is MSGI.
        Hxm2Screen out = new Hxm2Screen();
        out.setAcct(acctI);
        out.setAmount(amountI);

        // IF ACCTL NOT = 6 OR ACCTI IS NOT NUMERIC
        if (acctL != 6 || !isNumeric(acctI)) {
            CicsTask.MapSubfields sub = new CicsTask.MapSubfields()
                    .cursor("ACCT")                 // MOVE -1 TO ACCTL
                    .attr("ACCT", DFHUNIMD)         // MOVE DFHUNIMD TO ACCTA
                    .color("ACCT", DFHRED)          // MOVE DFHRED TO ACCTC
                    .hilight("ACCT", DFHBLINK);     // MOVE DFHBLINK TO ACCTH
            // MOVE 'ACCOUNT MUST BE 6 DIGITS' TO MSGO
            out.setMsg(moveAlpha("ACCOUNT MUST BE 6 DIGITS", MSG_LEN));
            // EXEC CICS SEND MAP('HXM2') MAPSET('HXSET2') FROM(HXM2O) DATAONLY CURSOR ALARM
            return new Send(out, sub, new String[] {"DATAONLY", "CURSOR", "ALARM"});
        }

        // MOVE SPACES TO MSGO
        // STRING 'OK ' ACCTI ' AMOUNT ' AMOUNTI DELIMITED BY SIZE INTO MSGO
        // (24 characters; the other 6 keep the spaces). AMOUNTI is taken as it is: LOW-VALUES when
        // AMOUNT was not entered, and never validated as numeric (kept as in the original).
        String strung = "OK " + acctI + " AMOUNT " + amountI;
        out.setMsg(moveAlpha(strung, MSG_LEN));
        // EXEC CICS SEND MAP('HXM2') MAPSET('HXSET2') FROM(HXM2O) DATAONLY
        return new Send(out, null, new String[] {"DATAONLY"});
    }

    /** BLINK-MISTAKE (lines 60-70). */
    private Send blinkMistake() {
        // MOVE LOW-VALUES TO HXM2O
        Hxm2Screen out = lowValueScreen();
        CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
        // DEFECT (kept, the program's own demonstration): X'F1' in the attribute byte is autoskip + MDT,
        // not blink. Fix: MOVE DFHBLINK TO MSGH instead of MOVE X'F1' TO MSGA.
        sub.attr("MSG", X_F1);                      // MOVE X'F1' TO MSGA
        // MOVE 'BLINK REQUESTED' TO MSGO
        out.setMsg(moveAlpha("BLINK REQUESTED", MSG_LEN));
        sub.attr("ACCT", DFHBMUNP);                 // MOVE DFHBMUNP TO ACCTA
        sub.hilight("ACCT", DFHBLINK);              // MOVE DFHBLINK TO ACCTH
        // EXEC CICS SEND MAP('HXM2') MAPSET('HXSET2') FROM(HXM2O) DATAONLY
        return new Send(out, sub, new String[] {"DATAONLY"});
    }

    // ------------------------------------------------------------------------------------------
    // Storage helpers
    // ------------------------------------------------------------------------------------------

    private void send(CicsTask task, Send s) {
        task.sendMap(MAP, MAPSET, renderHxm2(s.screen()), s.subfields(), s.options());
    }

    private static HxextWsCa newWsCa() {
        // 01 WS-CA PIC X VALUE 'E'.
        HxextWsCa ca = new HxextWsCa();
        ca.setWsCa("E");
        return ca;
    }

    /** HXM2O after MOVE LOW-VALUES TO HXM2O: every O field is X'00'. */
    private static Hxm2Screen lowValueScreen() {
        Hxm2Screen out = new Hxm2Screen();
        out.setAcct(lowValues(ACCT_LEN));
        out.setAmount(lowValues(AMOUNT_LEN));
        out.setMsg(lowValues(MSG_LEN));
        return out;
    }

    private static String lowValues(int length) {
        return String.valueOf(LOW_VALUE).repeat(length);
    }

    /** MOVE to PIC X(n): pad with spaces or truncate on the right. */
    private static String moveAlpha(String value, int length) {
        String v = value == null ? "" : value;
        if (v.length() >= length) {
            return v.substring(0, length);
        }
        return v + " ".repeat(length - v.length());
    }

    /** BMS input JUSTIFY=(RIGHT,ZERO): right-justified, zero-filled on the left. */
    private static String rightJustifyZero(String value, int length) {
        String v = value.length() > length ? value.substring(0, length) : value;
        return "0".repeat(length - v.length()) + v;
    }

    /** IS NUMERIC on PIC X: every character a digit 0-9 (only the code page's digits, #3831). */
    private static boolean isNumeric(String value) {
        if (value == null || value.isEmpty()) {
            return false;
        }
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (c < '0' || c > '9') {
                return false;
            }
        }
        return true;
    }
}
