package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.CocrdlicCommarea;
import com.gitgalaxy.modernized.dto.contract.CocrdlicWsThisProgcommarea;
import com.gitgalaxy.modernized.dto.contract.CocrdslcCommarea;
import com.gitgalaxy.modernized.dto.contract.CocrdupcCommarea;
import com.gitgalaxy.modernized.dto.screen.CcrdliaScreen;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import com.gitgalaxy.modernized.entity.vsam.CardRecord;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.repository.vsam.CardRecordRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.NavigableSet;
import java.util.Optional;
import java.util.TreeSet;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * READNEXT at line 1146 tests DUPREC,NORMAL
 * READNEXT at line 1197 tests DUPREC,ENDFILE,NORMAL
 * READPREV at line 1294 tests DUPREC,NORMAL
 * READPREV at line 1322 tests DUPREC,NORMAL
 * TODO: the RESP of SEND at line 939 (paragraph 1500-SEND-SCREEN) is never tested
 * TODO: the RESP of RECEIVE at line 963 (paragraph 2100-RECEIVE-SCREEN) is never tested
 * TODO: the RESP of STARTBR at line 1129 (paragraph 9000-READ-FORWARD) is never tested
 * TODO: the RESP of STARTBR at line 1273 (paragraph 9100-READ-BACKWARDS) is never tested
 * Screens (#3619): CcrdliaScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class CocrdlicService {

    private static final Logger log = LoggerFactory.getLogger(CocrdlicService.class);

    private static final String PGM = "COCRDLIC";
    private static final String TRAN = "CCLI";
    private static final String MAPSET = "COCRDLI";
    private static final String MAP = "CCRDLIA";
    private static final String MENUPGM = "COMEN01C";
    private static final String CARDFILE = "CARDDAT";
    private static final String LOW = "\u0000";
    private static final String SORT_PAGE = "cp037";

    private static final String MSG_EXIT = "PF03 PRESSED.EXITING";
    private static final String MSG_NO_RECORDS = "NO RECORDS FOUND FOR THIS SEARCH CONDITION.";
    private static final String MSG_MORE_THAN_1 = "PLEASE SELECT ONLY ONE RECORD TO VIEW OR UPDATE";
    private static final String MSG_INVALID_ACTION = "INVALID ACTION CODE";
    private static final String INFORM_REC_ACTIONS = "TYPE S FOR DETAIL, U TO UPDATE ANY RECORD";

    // BMS attribute / colour bytes (DFHBMSCA, EBCDIC values)
    private static final int DFHBMPRO = 0x60;
    private static final int DFHBMPRF = 0x61;
    private static final int DFHBMFSE = 0xC1;
    private static final int DFHBMDAR = 0x4C;
    private static final int DFHRED = 0xF2;
    private static final int DFHNEUTR = 0xF7;

    private static final Map<String, Integer> FIELD_LEN = new HashMap<>();

    static {
        for (var f : CcrdliaScreen.LAYOUT) {
            if (f.name() != null) {
                FIELD_LEN.put(f.name(), f.length());
            }
        }
    }

    private final ObjectProvider<Comen01cService> comen01cService;
    private final ObjectProvider<CocrdslcService> cocrdslcService;
    private final ObjectProvider<CocrdupcService> cocrdupcService;
    private final CardRecordRepository cardRecordRepository;

    /** The program's working storage for one task (WS-MISC-STORAGE, CC-WORK-AREA, WS-THIS-PROGCOMMAREA, CARD-RECORD). */
    private static final class Ws {
        CarddemoCommarea cc = blankCommarea();

        // WS-THIS-PROGCOMMAREA
        String lastCardNum = x("", 16);
        long lastCardAcctId;
        String firstCardNum = x("", 16);
        long firstCardAcctId;
        int screenNum;
        int lastPageDisp;
        String nextPageInd = " ";
        String returnFlag = " ";
        String allRows = x("", 196);

        // WS-MISC-STORAGE (INITIALIZE: alphanumerics spaces, numerics zero)
        String inputFlag = " ";
        String acctFlag = " ";
        String cardFlag = " ";
        String selectFlags = x("", 7);
        String selectErrFlags = x("", 7);
        int i;
        int iSelected;
        String protectRows = " ";
        String infoMsg = x("", 45);
        String errorMsg = x("", 75);
        String ridCardNum = x("", 16);
        int scrnCounter;
        boolean moreRecords;
        boolean doNotExclude;

        // CC-WORK-AREA
        String ccAid = x("", 5);
        String ccAcctId = x("", 11);
        String ccCardNum = x("", 16);
        String nextProg = x("", 8);

        // CARD-RECORD (keeps its last content when a READ fails)
        String cardNum = x("", 16);
        long cardAcctId;
        String cardStatus = " ";

        void resetThis() {
            lastCardNum = x("", 16);
            lastCardAcctId = 0;
            firstCardNum = x("", 16);
            firstCardAcctId = 0;
            screenNum = 0;
            lastPageDisp = 0;
            nextPageInd = " ";
            returnFlag = " ";
            allRows = x("", 196);
        }

        boolean errorMsgOff() {
            return CobolCompare.eq(errorMsg, " ");
        }

        boolean inputOk() {
            char c = inputFlag.charAt(0);
            return c == '0' || c == ' ' || c == '\u0000';
        }

        boolean inputError() {
            return inputFlag.charAt(0) == '1';
        }
    }

    public void executeCocrdlic(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for COCRDLIC");
        // COCRDLIC is a pseudo-conversational CICS transaction: its whole PROCEDURE DIVISION is ported in runTask(CicsTask).
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public CocrdlicCommarea handleTransaction(String transid, CocrdlicCommarea request) {
        log.info("Cocrdlic: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of this program (#3754): paragraph 0000-MAIN through COMMON-RETURN. */
    public void runTask(CicsTask task) {
        log.info("Cocrdlic: runTask");
        // 0000-MAIN: INITIALIZE CC-WORK-AREA WS-MISC-STORAGE WS-COMMAREA
        Ws w = new Ws();
        // MOVE LIT-THISTRANID TO WS-TRANID (never read again); SET WS-ERROR-MSG-OFF
        w.errorMsg = x("", 75);

        int calen = !task.hasCommarea() ? 0 : (task.eibcalen() == null ? 414 : task.eibcalen());
        if (calen == 0) {
            w.cc = blankCommarea();
            w.resetThis();
            w.cc.setCdemoFromTranid(x(TRAN, 4));
            w.cc.setCdemoFromProgram(x(PGM, 8));
            w.cc.setCdemoUserType("U");
            w.cc.setCdemoPgmContext(0);
            w.cc.setCdemoLastMap(x(MAP, 7));
            w.cc.setCdemoLastMapset(x(MAPSET, 7));
            w.screenNum = 1;
            w.lastPageDisp = 9;
        } else {
            loadCommarea(task, w);
        }

        // coming in from the menu: forget the past
        if (w.cc.getCdemoPgmContext() == 0 && !fromThisProgram(w)) {
            w.resetThis();
            w.cc.setCdemoPgmContext(0);
            w.cc.setCdemoLastMap(x(MAP, 7));
            w.screenNum = 1;
            w.lastPageDisp = 9;
        }

        // YYYY-STORE-PFKEY
        storePfKey(task, w);

        // receive and edit what the user typed
        if (calen > 0 && fromThisProgram(w)) {
            receiveMap(task, w);
        }

        // validity of the mapped key
        boolean pfkValid = aid(w, "ENTER") || aid(w, "PFK03") || aid(w, "PFK07") || aid(w, "PFK08");
        if (!pfkValid) {
            w.ccAid = "ENTER";
        }

        // PF3 from this program: back to the menu
        if (aid(w, "PFK03") && fromThisProgram(w)) {
            w.cc.setCdemoFromTranid(x(TRAN, 4));
            w.cc.setCdemoFromProgram(x(PGM, 8));
            w.cc.setCdemoUserType("U");
            w.cc.setCdemoPgmContext(0);
            w.cc.setCdemoLastMapset(x(MAPSET, 7));
            w.cc.setCdemoLastMap(x(MAP, 7));
            w.cc.setCdemoToProgram(x(MENUPGM, 8));
            // CCARD-NEXT-MAPSET / CCARD-NEXT-MAP are never used by the program afterwards
            w.errorMsg = x(MSG_EXIT, 75);
            w.cc.setCdemoPgmContext(0);
            xctl(task, MENUPGM, w);
            return;
        }

        // not PF8: reset the last page flag
        if (!aid(w, "PFK08")) {
            w.lastPageDisp = 9;
        }

        // EVALUATE TRUE
        boolean firstPage = w.screenNum == 1;
        if (w.inputError()) {
            // WHEN INPUT-ERROR
            w.cc.setCdemoFromProgram(x(PGM, 8));
            w.cc.setCdemoLastMapset(x(MAPSET, 7));
            w.cc.setCdemoLastMap(x(MAP, 7));
            w.nextProg = x(PGM, 8);
            if (w.acctFlag.charAt(0) != '0' && w.cardFlag.charAt(0) != '0') {
                if (readForward(task, w)) {
                    return;
                }
            }
            sendMap(task, w);
            commonReturn(task, w);
        } else if (aid(w, "PFK07") && firstPage) {
            // WHEN PFK07 AND CA-FIRST-PAGE (the source repeats this WHEN; same condition)
            w.ridCardNum = w.firstCardNum;
            if (readForward(task, w)) {
                return;
            }
            sendMap(task, w);
            commonReturn(task, w);
        } else if (aid(w, "PFK03") || (w.cc.getCdemoPgmContext() == 1 && !fromThisProgram(w))) {
            // WHEN CCARD-AID-PFK03 WHEN CDEMO-PGM-REENTER AND FROM-PROGRAM NOT = THIS
            w.cc = blankCommarea();
            w.resetThis();
            w.cc.setCdemoFromTranid(x(TRAN, 4));
            w.cc.setCdemoFromProgram(x(PGM, 8));
            w.cc.setCdemoUserType("U");
            w.cc.setCdemoPgmContext(0);
            w.cc.setCdemoLastMap(x(MAP, 7));
            w.cc.setCdemoLastMapset(x(MAPSET, 7));
            w.screenNum = 1;
            w.lastPageDisp = 9;
            w.ridCardNum = w.firstCardNum;
            if (readForward(task, w)) {
                return;
            }
            sendMap(task, w);
            commonReturn(task, w);
        } else if (aid(w, "PFK08") && w.nextPageInd.charAt(0) == 'Y') {
            // WHEN PAGE DOWN
            w.ridCardNum = w.lastCardNum;
            w.screenNum = (w.screenNum + 1) % 10;
            if (readForward(task, w)) {
                return;
            }
            sendMap(task, w);
            commonReturn(task, w);
        } else if (aid(w, "PFK07") && !firstPage) {
            // WHEN PAGE UP
            w.ridCardNum = w.firstCardNum;
            w.screenNum = Math.abs(w.screenNum - 1) % 10;
            if (readBackwards(task, w)) {
                return;
            }
            sendMap(task, w);
            commonReturn(task, w);
        } else if (aid(w, "ENTER") && selectedIs(w, 'S') && fromThisProgram(w)) {
            // WHEN TRANSFER TO CARD DETAIL VIEW
            transferTo(task, w, "COCRDSLC");
        } else if (aid(w, "ENTER") && selectedIs(w, 'U') && fromThisProgram(w)) {
            // WHEN TRANSFER TO CARD UPDATE
            transferTo(task, w, "COCRDUPC");
        } else {
            // WHEN OTHER
            w.ridCardNum = w.firstCardNum;
            if (readForward(task, w)) {
                return;
            }
            sendMap(task, w);
            commonReturn(task, w);
        }
        // Source lines 586-601 (IF INPUT-ERROR ... GO TO COMMON-RETURN; MOVE LIT-THISPGM TO CCARD-NEXT-PROG)
        // are unreachable: every WHEN above ends in COMMON-RETURN or XCTL, and INPUT-ERROR is the first WHEN.
    }

    /** WHEN CCARD-AID-ENTER AND VIEW/UPDATE-REQUESTED-ON: sets the commarea and XCTLs to the next program. */
    private void transferTo(CicsTask task, Ws w, String program) {
        w.cc.setCdemoFromTranid(x(TRAN, 4));
        w.cc.setCdemoFromProgram(x(PGM, 8));
        w.cc.setCdemoUserType("U");
        w.cc.setCdemoPgmContext(0);
        w.cc.setCdemoLastMapset(x(MAPSET, 7));
        w.cc.setCdemoLastMap(x(MAP, 7));
        w.nextProg = x(program, 8);
        int start = (w.iSelected - 1) * 28;
        String rowAcct = w.allRows.substring(start, start + 11);
        String rowCard = w.allRows.substring(start + 11, start + 27);
        w.cc.setCdemoAcctId(numberFromAlnum(rowAcct));
        w.cc.setCdemoCardNum(numberFromAlnum(rowCard));
        xctl(task, w.nextProg.trim(), w);
    }

    /** EXEC CICS XCTL PROGRAM(..) COMMAREA(CARDDEMO-COMMAREA) with no RESP: a failure takes the default abend. */
    private void xctl(CicsTask task, String program, Ws w) {
        String resp = task.xctl(program, copyCommarea(w.cc));
        if (!"NORMAL".equals(resp)) {
            task.abendOnCondition(resp);
        }
    }

    /** COMMON-RETURN. */
    private void commonReturn(CicsTask task, Ws w) {
        w.cc.setCdemoFromTranid(x(TRAN, 4));
        w.cc.setCdemoFromProgram(x(PGM, 8));
        w.cc.setCdemoLastMapset(x(MAPSET, 7));
        w.cc.setCdemoLastMap(x(MAP, 7));
        // MOVE CARDDEMO-COMMAREA / WS-THIS-PROGCOMMAREA TO WS-COMMAREA (X(2000)): the DTO carries the 414 bytes
        CocrdlicCommarea ca = new CocrdlicCommarea();
        ca.setCarddemoCommarea(copyCommarea(w.cc));
        CocrdlicWsThisProgcommarea t = new CocrdlicWsThisProgcommarea();
        t.setWsCaLastCardNum(w.lastCardNum);
        t.setWsCaLastCardAcctId(w.lastCardAcctId);
        t.setWsCaFirstCardNum(w.firstCardNum);
        t.setWsCaFirstCardAcctId(w.firstCardAcctId);
        t.setWsCaScreenNum(w.screenNum);
        t.setWsCaLastPageDisplayed(w.lastPageDisp);
        t.setWsCaNextPageInd(w.nextPageInd);
        t.setWsReturnFlag(w.returnFlag);
        t.setWsAllRows(w.allRows);
        ca.setWsThisProgcommarea(t);
        task.returnTransid(TRAN, ca, 2000);
    }

    // ------------------------------------------------------------------ YYYY-STORE-PFKEY

    private void storePfKey(CicsTask task, Ws w) {
        String a = task.aid() == null ? "" : task.aid();
        switch (a) {
            case "ENTER" -> w.ccAid = "ENTER";
            case "CLEAR" -> w.ccAid = "CLEAR";
            case "PA1" -> w.ccAid = "PA1  ";
            case "PA2" -> w.ccAid = "PA2  ";
            default -> {
                if (a.startsWith("PF")) {
                    int n = CobolRecords.numval(a.substring(2), '.').intValue();
                    if (n >= 1 && n <= 24) {
                        w.ccAid = String.format(Locale.ROOT, "PFK%02d", n > 12 ? n - 12 : n);
                    }
                }
                // PA3 and anything else: CCARD-AID keeps its initial spaces
            }
        }
    }

    private static boolean aid(Ws w, String code) {
        return CobolCompare.eq(w.ccAid, code);
    }

    // ------------------------------------------------------------------ 2000-RECEIVE-MAP

    private void receiveMap(CicsTask task, Ws w) {
        receiveScreen(task, w);   // 2100-RECEIVE-SCREEN
        editInputs(w);            // 2200-EDIT-INPUTS
    }

    /** 2100-RECEIVE-SCREEN (the RESP is never tested: a MAPFAIL leaves the input area as it was, spaces). */
    private void receiveScreen(CicsTask task, Ws w) {
        Optional<CcrdliaScreen> r = task.receive(MAP, MAPSET, CcrdliaScreen.class);
        Map<String, String> in = r.isPresent() ? r.get().screenValues() : null;
        w.ccAcctId = inField(in, "ACCTSID", 11);
        w.ccCardNum = inField(in, "CARDSID", 16);
        StringBuilder sel = new StringBuilder();
        for (int i = 1; i <= 7; i++) {
            sel.append(inField(in, "CRDSEL" + i, 1));
        }
        w.selectFlags = sel.toString();
    }

    private static String inField(Map<String, String> in, String name, int len) {
        if (in == null) {
            return x("", len);
        }
        String v = in.get(name);
        if (v == null || v.isEmpty()) {
            return LOW.repeat(len);
        }
        return x(v, len);
    }

    /** 2200-EDIT-INPUTS. */
    private void editInputs(Ws w) {
        w.inputFlag = "0";       // SET INPUT-OK
        w.protectRows = "0";     // SET FLG-PROTECT-SELECT-ROWS-NO
        editAccount(w);
        editCard(w);
        editArray(w);
    }

    /** 2210-EDIT-ACCOUNT. */
    private void editAccount(Ws w) {
        w.acctFlag = " ";
        if (CobolCompare.eq(w.ccAcctId, CobolCompare.lowValues(11)) || CobolCompare.eq(w.ccAcctId, " ")
                || numericZero(w.ccAcctId)) {
            w.acctFlag = " ";
            w.cc.setCdemoAcctId(0L);
            return;
        }
        if (!isNumeric(w.ccAcctId)) {
            w.inputFlag = "1";
            w.acctFlag = "0";
            w.protectRows = "1";
            w.errorMsg = x("ACCOUNT FILTER,IF SUPPLIED MUST BE A 11 DIGIT NUMBER", 75);
            w.cc.setCdemoAcctId(0L);
        } else {
            w.cc.setCdemoAcctId(CobolRecords.numval(w.ccAcctId, '.').longValue());
            w.acctFlag = "1";
        }
    }

    /** 2220-EDIT-CARD. */
    private void editCard(Ws w) {
        w.cardFlag = " ";
        if (CobolCompare.eq(w.ccCardNum, CobolCompare.lowValues(16)) || CobolCompare.eq(w.ccCardNum, " ")
                || numericZero(w.ccCardNum)) {
            w.cardFlag = " ";
            w.cc.setCdemoCardNum(0L);
            return;
        }
        if (!isNumeric(w.ccCardNum)) {
            w.inputFlag = "1";
            w.cardFlag = "0";
            w.protectRows = "1";
            if (w.errorMsgOff()) {
                w.errorMsg = x("CARD ID FILTER,IF SUPPLIED MUST BE A 16 DIGIT NUMBER", 75);
            }
            w.cc.setCdemoCardNum(0L);
        } else {
            w.cc.setCdemoCardNum(CobolRecords.numval(w.ccCardNum, '.').longValue());
            w.cardFlag = "1";
        }
    }

    /** 2250-EDIT-ARRAY. */
    private void editArray(Ws w) {
        if (w.inputError()) {
            return;
        }
        // INSPECT WS-EDIT-SELECT-FLAGS TALLYING I FOR ALL 'S' ALL 'U'
        for (int k = 0; k < 7; k++) {
            char c = w.selectFlags.charAt(k);
            if (c == 'S' || c == 'U') {
                w.i++;
            }
        }
        if (w.i > 1) {
            w.inputFlag = "1";
            w.errorMsg = x(MSG_MORE_THAN_1, 75);
            StringBuilder e = new StringBuilder();
            for (int k = 0; k < 7; k++) {
                char c = w.selectFlags.charAt(k);
                e.append(c == 'S' || c == 'U' ? '1' : '0');
            }
            w.selectErrFlags = e.toString();
        }
        w.iSelected = 0;
        for (w.i = 1; w.i <= 7; w.i++) {
            char c = w.selectFlags.charAt(w.i - 1);
            if (c == 'S' || c == 'U') {
                w.iSelected = w.i;
                if (CobolCompare.eq(w.errorMsg, MSG_MORE_THAN_1)) {
                    setErrFlag(w, w.i);
                }
            } else if (c == ' ' || c == '\u0000') {
                // SELECT-BLANK: CONTINUE
            } else {
                w.inputFlag = "1";
                setErrFlag(w, w.i);
                if (w.errorMsgOff()) {
                    w.errorMsg = x(MSG_INVALID_ACTION, 75);
                }
            }
        }
    }

    private static void setErrFlag(Ws w, int i) {
        StringBuilder b = new StringBuilder(w.selectErrFlags);
        b.setCharAt(i - 1, '1');
        w.selectErrFlags = b.toString();
    }

    // ------------------------------------------------------------------ 1000-SEND-MAP

    private void sendMap(CicsTask task, Ws w) {
        Map<String, String> o = new LinkedHashMap<>();
        CicsTask.MapSubfields sub = new CicsTask.MapSubfields();

        // 1100-SCREEN-INIT
        for (var f : CcrdliaScreen.LAYOUT) {
            if (f.name() != null) {
                o.put(f.name(), LOW.repeat(f.length()));   // MOVE LOW-VALUES TO CCRDLIAO
            }
        }
        LocalDateTime now = task.now();
        o.put("TITLE01", x(" ".repeat(6) + "AWS Mainframe Modernization", 40));
        o.put("TITLE02", x(" ".repeat(14) + "CardDemo", 40));
        o.put("TRNNAME", x(TRAN, 4));
        o.put("PGMNAME", x(PGM, 8));
        String year = String.format(Locale.ROOT, "%04d", now.getYear());
        o.put("CURDATE", String.format(Locale.ROOT, "%02d/%02d/%s", now.getMonthValue(), now.getDayOfMonth(),
                year.substring(2)));
        o.put("CURTIME", String.format(Locale.ROOT, "%02d:%02d:%02d", now.getHour(), now.getMinute(),
                now.getSecond()));
        o.put("PAGENO", x(Integer.toString(w.screenNum), 3));
        w.infoMsg = x("", 45);   // SET WS-NO-INFO-MESSAGE
        o.put("INFOMSG", w.infoMsg);
        sub.color("INFOMSG", DFHBMDAR);

        // 1200-SCREEN-ARRAY-INIT
        for (int i = 1; i <= 7; i++) {
            if (!rowIsLow(w, i)) {
                int s = (i - 1) * 28;
                o.put("CRDSEL" + i, String.valueOf(w.selectFlags.charAt(i - 1)));
                o.put("ACCTNO" + i, w.allRows.substring(s, s + 11));
                o.put("CRDNUM" + i, w.allRows.substring(s + 11, s + 27));
                o.put("CRDSTS" + i, w.allRows.substring(s + 27, s + 28));
            }
        }

        // 1250-SETUP-ARRAY-ATTRIBS
        for (int i = 1; i <= 7; i++) {
            String sel = "CRDSEL" + i;
            boolean protect = rowIsLow(w, i) || w.protectRows.charAt(0) == '1';
            if (protect) {
                sub.attr(sel, i == 1 ? DFHBMPRF : DFHBMPRO);
            } else {
                if (w.selectErrFlags.charAt(i - 1) == '1') {
                    sub.color(sel, DFHRED);
                    if (i == 1) {
                        // Row 1 differs from rows 2-7: it shows '*' and does not ask for the cursor
                        char c = w.selectFlags.charAt(0);
                        if (c == ' ' || c == '\u0000') {
                            o.put(sel, "*");
                        }
                    } else {
                        sub.cursor(sel);
                    }
                }
                sub.attr(sel, DFHBMFSE);
            }
            // Source line 790 has a stray 'I' after MOVE DFHBMPRO TO CRDSEL4A OF CCRDLIAI: it is a second
            // receiving item (MOVE ... TO I). I is not read again after this paragraph, so it is not modelled.
        }

        // 1300-SETUP-SCREEN-ATTRS
        boolean skip = w.cc.getCdemoPgmContext() == 0 && CobolCompare.eq(w.cc.getCdemoFromProgram(), MENUPGM);
        // (EIBCALEN = 0 case is folded in below through hasCommarea at the caller's state)
        if (!(task.hasCommarea() ? (task.eibcalen() != null && task.eibcalen() == 0) : true) && !skip) {
            char af = w.acctFlag.charAt(0);
            if (af == '1' || af == '0') {
                o.put("ACCTSID", x(w.ccAcctId, 11));
                sub.attr("ACCTSID", DFHBMFSE);
            } else if (w.cc.getCdemoAcctId() == 0) {
                o.put("ACCTSID", LOW.repeat(11));
            } else {
                o.put("ACCTSID", digits(w.cc.getCdemoAcctId(), 11));
                sub.attr("ACCTSID", DFHBMFSE);
            }
            char cf = w.cardFlag.charAt(0);
            if (cf == '1' || cf == '0') {
                o.put("CARDSID", x(w.ccCardNum, 16));
                sub.attr("CARDSID", DFHBMFSE);
            } else if (w.cc.getCdemoCardNum() == 0) {
                o.put("CARDSID", LOW.repeat(16));
            } else {
                o.put("CARDSID", digits(w.cc.getCdemoCardNum(), 16));
                sub.attr("CARDSID", DFHBMFSE);
            }
        }
        if (w.acctFlag.charAt(0) == '0') {
            sub.color("ACCTSID", DFHRED);
            sub.cursor("ACCTSID");
        }
        if (w.cardFlag.charAt(0) == '0') {
            sub.color("CARDSID", DFHRED);
            sub.cursor("CARDSID");
        }
        if (w.inputOk()) {
            sub.cursor("ACCTSID");
        }

        // 1400-SETUP-MESSAGE
        boolean noInfo = CobolCompare.eq(w.infoMsg, " ") || CobolCompare.eq(w.infoMsg, CobolCompare.lowValues(45));
        boolean nextNotExists = w.nextPageInd.charAt(0) == '\u0000';
        boolean nextExists = w.nextPageInd.charAt(0) == 'Y';
        if (w.acctFlag.charAt(0) == '0' || w.cardFlag.charAt(0) == '0') {
            // CONTINUE
        } else if (aid(w, "PFK07") && w.screenNum == 1) {
            w.errorMsg = x("NO PREVIOUS PAGES TO DISPLAY", 75);
        } else if (aid(w, "PFK08") && nextNotExists && w.lastPageDisp == 0) {
            w.errorMsg = x("NO MORE PAGES TO DISPLAY", 75);
        } else if (aid(w, "PFK08") && nextNotExists) {
            w.infoMsg = x(INFORM_REC_ACTIONS, 45);
            if (w.lastPageDisp == 9 && nextNotExists) {
                w.lastPageDisp = 0;
            }
        } else if (noInfo || nextExists) {
            w.infoMsg = x(INFORM_REC_ACTIONS, 45);
        } else {
            // WHEN OTHER is unreachable: WS-INFO-MSG is spaces here, so the WS-NO-INFO-MESSAGE arm always matches
            w.infoMsg = x("", 45);
        }
        o.put("ERRMSG", x(w.errorMsg, 78));
        boolean noInfoNow = CobolCompare.eq(w.infoMsg, " ") || CobolCompare.eq(w.infoMsg, CobolCompare.lowValues(45));
        if (!noInfoNow && !CobolCompare.eq(w.errorMsg, MSG_NO_RECORDS)) {
            o.put("INFOMSG", x(w.infoMsg, 45));
            sub.color("INFOMSG", DFHNEUTR);
        }

        // 1500-SEND-SCREEN (RESP never tested)
        task.sendMap(MAP, MAPSET, CcrdliaScreen.fromValues(o), sub, "CURSOR", "ERASE", "FREEKB");
    }

    private static boolean rowIsLow(Ws w, int i) {
        int s = (i - 1) * 28;
        for (int k = s; k < s + 28; k++) {
            if (w.allRows.charAt(k) != '\u0000') {
                return false;
            }
        }
        return true;
    }

    private static boolean selectedIs(Ws w, char flag) {
        return w.iSelected >= 1 && w.iSelected <= 7 && w.selectFlags.charAt(w.iSelected - 1) == flag;
    }

    /** EXEC CICS ENDBR FILE(LIT-CARD-FILE) with no RESP: a failure (INVREQ when no browse is active, e.g. after
     *  a STARTBR that failed unnoticed) takes CICS's default action. Returns true when the task was abended
     *  and runTask must return at once. */
    private boolean endBr(CicsTask task) {
        int resp = task.endbr(CARDFILE);
        if (resp == 0) {
            return false;
        }
        String cond = resp == 13 ? "NOTFND" : "INVREQ";
        task.abendOnCondition(cond);
        return true;
    }

    // ------------------------------------------------------------------ 9000-READ-FORWARD

    /** Returns true when the closing ENDBR abended the task. */
    private boolean readForward(CicsTask task, Ws w) {
        w.allRows = LOW.repeat(196);
        task.startbr(CARDFILE, w.ridCardNum, false, this::cardKeys);   // RESP never tested
        w.scrnCounter = 0;
        w.nextPageInd = "Y";
        w.moreRecords = true;

        while (w.moreRecords) {
            int resp = readNext(task, w);
            if (resp == 0 || resp == 14) {
                filterRecords(w);   // 9500-FILTER-RECORDS
                if (w.doNotExclude) {
                    w.scrnCounter++;
                    setRow(w, w.scrnCounter);
                    if (w.scrnCounter == 1) {
                        w.firstCardAcctId = w.cardAcctId;
                        w.firstCardNum = w.cardNum;
                        if (w.screenNum == 0) {
                            w.screenNum = 1;
                        }
                    }
                }
                if (w.scrnCounter == 7) {
                    w.moreRecords = false;
                    w.lastCardAcctId = w.cardAcctId;
                    w.lastCardNum = w.cardNum;
                    int resp2 = readNext(task, w);
                    if (resp2 == 0 || resp2 == 14) {
                        w.nextPageInd = "Y";
                        w.lastCardAcctId = w.cardAcctId;
                        w.lastCardNum = w.cardNum;
                    } else if (resp2 == 20) {
                        w.nextPageInd = LOW;
                        if (w.errorMsgOff()) {
                            w.errorMsg = x("NO MORE RECORDS TO SHOW", 75);
                        }
                    } else {
                        w.moreRecords = false;
                        fileError(w, resp2);
                    }
                }
            } else if (resp == 20) {
                w.moreRecords = false;
                w.nextPageInd = LOW;
                // CARD-RECORD still holds the last record read (or its initial content)
                w.lastCardAcctId = w.cardAcctId;
                w.lastCardNum = w.cardNum;
                if (w.errorMsgOff()) {
                    w.errorMsg = x("NO MORE RECORDS TO SHOW", 75);
                }
                if (w.screenNum == 1 && w.scrnCounter == 0) {
                    w.errorMsg = x(MSG_NO_RECORDS, 75);
                }
            } else {
                w.moreRecords = false;
                fileError(w, resp);
            }
        }
        return endBr(task);   // line 1258
    }

    // ------------------------------------------------------------------ 9100-READ-BACKWARDS

    /** Returns true when the closing ENDBR abended the task. */
    private boolean readBackwards(CicsTask task, Ws w) {
        w.allRows = LOW.repeat(196);
        w.lastCardNum = w.firstCardNum;
        w.lastCardAcctId = w.firstCardAcctId;
        task.startbr(CARDFILE, w.ridCardNum, false, this::cardKeys);   // RESP never tested
        w.scrnCounter = 7 + 1;
        w.nextPageInd = "Y";
        w.moreRecords = true;

        int resp = readPrev(task, w);
        if (resp == 0 || resp == 14) {
            w.scrnCounter--;
        } else {
            w.moreRecords = false;
            fileError(w, resp);
            return endBr(task);   // GO TO 9100-READ-BACKWARDS-EXIT (line 1375)
        }

        while (w.moreRecords) {
            resp = readPrev(task, w);
            if (resp == 0 || resp == 14) {
                filterRecords(w);
                if (w.doNotExclude) {
                    setRow(w, w.scrnCounter);
                    w.scrnCounter--;
                    if (w.scrnCounter == 0) {
                        w.moreRecords = false;
                        w.firstCardAcctId = w.cardAcctId;
                        w.firstCardNum = w.cardNum;
                    }
                }
            } else {
                // includes ENDFILE: a short previous page ends in a File Error message
                w.moreRecords = false;
                fileError(w, resp);
            }
        }
        return endBr(task);   // 9100-READ-BACKWARDS-EXIT
    }

    // ------------------------------------------------------------------ 9500-FILTER-RECORDS

    private void filterRecords(Ws w) {
        w.doNotExclude = true;
        if (w.acctFlag.charAt(0) == '1') {
            if (!CobolCompare.eq(digits(w.cardAcctId, 11), w.ccAcctId)) {
                w.doNotExclude = false;
                return;
            }
        }
        if (w.cardFlag.charAt(0) == '1') {
            if (!CobolCompare.eq(w.cardNum, w.ccCardNum)) {
                w.doNotExclude = false;
            }
        }
    }

    // ------------------------------------------------------------------ browse helpers

    /** EXEC CICS READNEXT INTO(CARD-RECORD) RIDFLD(WS-CARD-RID-CARDNUM): the RESP; CARD-RECORD and RIDFLD change only on NORMAL. */
    private int readNext(CicsTask task, Ws w) {
        CicsTask.Browsed b = task.readnext(CARDFILE, w.ridCardNum);
        if (b.normal()) {
            w.ridCardNum = x(b.key(), 16);
            cardRecordRepository.findById(b.key()).ifPresent(r -> takeCard(w, r));
        }
        return b.resp();
    }

    /** EXEC CICS READPREV INTO(CARD-RECORD) RIDFLD(WS-CARD-RID-CARDNUM). */
    private int readPrev(CicsTask task, Ws w) {
        CicsTask.Browsed b = task.readprev(CARDFILE, w.ridCardNum);
        if (b.normal()) {
            w.ridCardNum = x(b.key(), 16);
            cardRecordRepository.findById(b.key()).ifPresent(r -> takeCard(w, r));
        }
        return b.resp();
    }

    private static void takeCard(Ws w, CardRecord r) {
        w.cardNum = x(r.getCardNum(), 16);
        w.cardAcctId = r.getCardAcctId() == null ? 0L : r.getCardAcctId();
        w.cardStatus = x(r.getCardActiveStatus(), 1);
    }

    private NavigableSet<String> cardKeys() {
        TreeSet<String> keys = new TreeSet<>(Comparator.comparing((String s) -> CobolRecords.sortKey(s, SORT_PAGE)));
        for (CardRecord r : cardRecordRepository.findAll()) {
            keys.add(r.getCardNum());
        }
        return keys;
    }

    /** MOVE CARD-NUM / CARD-ACCT-ID / CARD-ACTIVE-STATUS TO WS-ROW-...(n). */
    private static void setRow(Ws w, int n) {
        int s = (n - 1) * 28;
        w.allRows = w.allRows.substring(0, s) + digits(w.cardAcctId, 11) + w.cardNum + w.cardStatus
                + w.allRows.substring(s + 28);
    }

    /** The WHEN OTHER file-error text: WS-FILE-ERROR-MESSAGE moved to WS-ERROR-MSG (X(75), so the last 5 bytes are cut).
     *  RESP2 is not available from the task's browse calls: 0 is shown. */
    private static void fileError(Ws w, int resp) {
        String msg = "File Error: " + x("READ", 8) + " on " + x("CARDDAT ", 9) + " returned RESP "
                + x(digits(resp, 9), 10) + ",RESP2 " + x(digits(0, 9), 10) + x("", 5);
        w.errorMsg = x(msg, 75);
    }

    // ------------------------------------------------------------------ commarea helpers

    private static void loadCommarea(CicsTask task, Ws w) {
        Object ca = task.commarea(Object.class);
        if (ca instanceof CocrdlicCommarea c) {
            w.cc = copyCommarea(c.getCarddemoCommarea());
            CocrdlicWsThisProgcommarea t = c.getWsThisProgcommarea();
            if (t == null) {
                w.resetThis();
            } else {
                w.lastCardNum = x(t.getWsCaLastCardNum(), 16);
                w.lastCardAcctId = nz(t.getWsCaLastCardAcctId());
                w.firstCardNum = x(t.getWsCaFirstCardNum(), 16);
                w.firstCardAcctId = nz(t.getWsCaFirstCardAcctId());
                w.screenNum = (int) (nz(t.getWsCaScreenNum()) % 10);
                w.lastPageDisp = (int) (nz(t.getWsCaLastPageDisplayed()) % 10);
                w.nextPageInd = x(t.getWsCaNextPageInd(), 1);
                w.returnFlag = x(t.getWsReturnFlag(), 1);
                w.allRows = x(t.getWsAllRows(), 196);
            }
        } else if (ca instanceof CarddemoCommarea c) {
            w.cc = copyCommarea(c);
            w.resetThis();
        } else {
            w.cc = blankCommarea();
            w.resetThis();
        }
    }

    private static boolean fromThisProgram(Ws w) {
        return CobolCompare.eq(w.cc.getCdemoFromProgram(), PGM);
    }

    /** INITIALIZE CARDDEMO-COMMAREA: alphanumerics spaces, numerics zero. */
    private static CarddemoCommarea blankCommarea() {
        return copyCommarea(null);
    }

    private static CarddemoCommarea copyCommarea(CarddemoCommarea s) {
        CarddemoCommarea c = new CarddemoCommarea();
        c.setCdemoFromTranid(x(s == null ? null : s.getCdemoFromTranid(), 4));
        c.setCdemoFromProgram(x(s == null ? null : s.getCdemoFromProgram(), 8));
        c.setCdemoToTranid(x(s == null ? null : s.getCdemoToTranid(), 4));
        c.setCdemoToProgram(x(s == null ? null : s.getCdemoToProgram(), 8));
        c.setCdemoUserId(x(s == null ? null : s.getCdemoUserId(), 8));
        c.setCdemoUserType(x(s == null ? null : s.getCdemoUserType(), 1));
        c.setCdemoPgmContext(s == null || s.getCdemoPgmContext() == null ? 0 : s.getCdemoPgmContext());
        c.setCdemoCustId(s == null || s.getCdemoCustId() == null ? 0 : s.getCdemoCustId());
        c.setCdemoCustFname(x(s == null ? null : s.getCdemoCustFname(), 25));
        c.setCdemoCustMname(x(s == null ? null : s.getCdemoCustMname(), 25));
        c.setCdemoCustLname(x(s == null ? null : s.getCdemoCustLname(), 25));
        c.setCdemoAcctId(s == null || s.getCdemoAcctId() == null ? 0L : s.getCdemoAcctId());
        c.setCdemoAcctStatus(x(s == null ? null : s.getCdemoAcctStatus(), 1));
        c.setCdemoCardNum(s == null || s.getCdemoCardNum() == null ? 0L : s.getCdemoCardNum());
        c.setCdemoLastMap(x(s == null ? null : s.getCdemoLastMap(), 7));
        c.setCdemoLastMapset(x(s == null ? null : s.getCdemoLastMapset(), 7));
        return c;
    }

    // ------------------------------------------------------------------ storage helpers

    /** MOVE to PIC X(n): pad with spaces or truncate on the right. */
    private static String x(String v, int n) {
        String s = v == null ? "" : v;
        return s.length() >= n ? s.substring(0, n) : s + " ".repeat(n - s.length());
    }

    /** MOVE of an unsigned integer to PIC 9(n) shown as characters: zero-padded, high-order digits lost. */
    private static String digits(long v, int n) {
        String s = Long.toString(Math.abs(v));
        return s.length() >= n ? s.substring(s.length() - n) : "0".repeat(n - s.length()) + s;
    }

    private static long nz(Number n) {
        return n == null ? 0L : n.longValue();
    }

    /** IS NUMERIC on an alphanumeric item: only the digits 0-9. */
    private static boolean isNumeric(String s) {
        if (s.isEmpty()) {
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

    /** A numeric-display redefinition compared with ZEROS: every digit position (low nibble) is zero. */
    private static boolean numericZero(String s) {
        for (int i = 0; i < s.length(); i++) {
            if ((s.charAt(i) & 0x0F) != 0) {
                return false;
            }
        }
        return true;
    }

    /** MOVE alphanumeric TO PIC 9(n): each position contributes its digit nibble. */
    private static long numberFromAlnum(String s) {
        long v = 0;
        for (int i = 0; i < s.length(); i++) {
            v = v * 10 + ((s.charAt(i) & 0x0F) % 10);
        }
        return v;
    }

    /** Another program LINKed / XCTLed to this one. TODO: [AI AGENT] implement from the program's business rules. */
    public CocrdlicCommarea handleLink(CocrdlicCommarea request) {
        log.info("Cocrdlic: handleLink");
        return request;
    }

    /** XCTL PROGRAM(LIT-MENUPGM) at app/cbl/COCRDLIC.cbl:402: the target is data-driven. Candidates: COMEN01C (value).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchLitMenupgmL402(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COMEN01C":
                return comen01cService.getObject().handleLink((CarddemoCommarea) request);
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(LIT-MENUPGM) at app/cbl/COCRDLIC.cbl:402: no known target " + program);
        }
    }

    /** XCTL PROGRAM(CCARD-NEXT-PROG) at app/cbl/COCRDLIC.cbl:538: the target is data-driven. Candidates: COCRDLIC (moves), COCRDSLC (moves), COCRDUPC (moves).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCcardNextProgL538(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COCRDLIC":
                return this.handleLink(CocrdlicCommarea.fromPrefix((CarddemoCommarea) request));
            case "COCRDSLC":
                return cocrdslcService.getObject().handleLink(CocrdslcCommarea.fromPrefix((CarddemoCommarea) request));
            case "COCRDUPC":
                return cocrdupcService.getObject().handleLink(CocrdupcCommarea.fromPrefix((CarddemoCommarea) request));
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CCARD-NEXT-PROG) at app/cbl/COCRDLIC.cbl:538: no known target " + program);
        }
    }

    /** XCTL PROGRAM(CCARD-NEXT-PROG) at app/cbl/COCRDLIC.cbl:566: the target is data-driven. Candidates: COCRDLIC (moves), COCRDSLC (moves), COCRDUPC (moves).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCcardNextProgL566(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COCRDLIC":
                return this.handleLink(CocrdlicCommarea.fromPrefix((CarddemoCommarea) request));
            case "COCRDSLC":
                return cocrdslcService.getObject().handleLink(CocrdslcCommarea.fromPrefix((CarddemoCommarea) request));
            case "COCRDUPC":
                return cocrdupcService.getObject().handleLink(CocrdupcCommarea.fromPrefix((CarddemoCommarea) request));
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CCARD-NEXT-PROG) at app/cbl/COCRDLIC.cbl:566: no known target " + program);
        }
    }

    /** AWS.M2.CARDDEMO.CARDDATA.VSAM.KSDS as CICS file CARDDAT at app/cbl/COCRDLIC.cbl:1129, 1146, 1197, 1258, 1273, 1294, 1322, 1375; VSAM defines field testing: open (3 public / 0 private estates). */
    public List<CardRecord> browseCarddat(String from, int count) {
        return cardRecordRepository.findByCardNumSortGreaterThanEqualOrderByCardNumSortAsc(CobolRecords.sortKey(from, "cp037"), org.springframework.data.domain.PageRequest.of(0, count));
    }

    public List<CardRecord> browseBackCarddat(String from, int count) {
        return cardRecordRepository.findByCardNumSortLessThanEqualOrderByCardNumSortDesc(CobolRecords.sortKey(from, "cp037"), org.springframework.data.domain.PageRequest.of(0, count));
    }

    /** SEND MAP(CCRDLIA) MAPSET(COCRDLI) FROM(CCRDLIAO) at app/cbl/COCRDLIC.cbl:939 (#3619).
     *  TODO: port the logic that fills CCRDLIAO before the SEND.
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public CcrdliaScreen renderCcrdlia(CcrdliaScreen screen) {
        return screen;
    }

    /** RECEIVE MAP(CCRDLIA) MAPSET(COCRDLI) INTO(CCRDLIAI) at app/cbl/COCRDLIC.cbl:963 (#3619).
     *  `aid` is the key the user pressed (EIBAID): ENTER, PF1-PF24, CLEAR, PA1-PA3.
     *  TODO: port the logic that reads CCRDLIAI after the RECEIVE, and return the screen to show next.
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public ScreenModel submitCcrdlia(CcrdliaScreen input, String aid) {
        return renderCcrdlia(input);
    }

}
