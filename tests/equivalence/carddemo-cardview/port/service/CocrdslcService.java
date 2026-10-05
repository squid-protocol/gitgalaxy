package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.CocrdslcCommarea;
import com.gitgalaxy.modernized.dto.screen.CcrdslaScreen;
import com.gitgalaxy.modernized.entity.vsam.CardRecord;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.exception.*;
import com.gitgalaxy.modernized.repository.vsam.CardRecordRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * READ at line 742 tests NORMAL,NOTFND
 * READ at line 783 tests NORMAL,NOTFND
 * The RESP of SEND at line 569 (paragraph 1400-SEND-SCREEN) is never tested by the program.
 * The RESP of RECEIVE at line 597 (paragraph 2100-RECEIVE-MAP) is never tested by the program.
 * The RESP of SEND at line 865 (paragraph ABEND-ROUTINE) is never tested (NOHANDLE).
 * Screens (#3619): CcrdslaScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class CocrdslcService {

    private static final Logger log = LoggerFactory.getLogger(CocrdslcService.class);

    private static final String LIT_THISPGM = "COCRDSLC";
    private static final String LIT_THISTRANID = "CCDL";
    private static final String LIT_THISMAPSET = "COCRDSL";   // X(8) 'COCRDSL ' moved to X(7)
    private static final String LIT_THISMAP = "CCRDSLA";
    private static final String LIT_CCLISTPGM = "COCRDLIC";
    private static final String LIT_CCLISTMAPSET = "COCRDLI";
    private static final String LIT_MENUPGM = "COMEN01C";
    private static final String LIT_MENUTRANID = "CM00";
    private static final String LIT_CARDFILENAME = "CARDDAT";

    private static final String TITLE01 = "      AWS Mainframe Modernization       ";
    private static final String TITLE02 = "              CardDemo                  ";
    private static final String MSG_FOUND = "   Displaying requested details";
    private static final String MSG_PROMPT_INPUT = "Please enter Account and Card Number";

    // DFHBMSCA attribute / colour bytes
    private static final int DFHBMPRF = 0x61;
    private static final int DFHBMFSE = 0xC1;
    private static final int DFHBMDAR = 0x4C;
    private static final int DFHDFCOL = 0x00;
    private static final int DFHRED = 0xF2;
    private static final int DFHNEUTR = 0xF7;

    private final CardRecordRepository cardRecordRepository;

    private final ThreadLocal<Active> activeTask = new ThreadLocal<>();

    private record Active(CicsTask task, Ws ws) {
    }

    /** The program's WORKING-STORAGE as INITIALIZE leaves it (0000-MAIN: INITIALIZE WS-MISC-STORAGE, CC-WORK-AREA). */
    private static final class Ws {
        char inputFlag = ' ';     // WS-INPUT-FLAG ('0' OK, '1' ERROR)
        char acctFlag = ' ';      // WS-EDIT-ACCT-FLAG ('0' not ok, '1' valid, ' ' blank)
        char cardFlag = ' ';      // WS-EDIT-CARD-FLAG
        String returnMsg = x("", 75);
        String infoMsg = x("", 40);
        String ccAcctId = x("", 11);
        String ccCardNum = x("", 16);
        String ccAid = x("", 5);
        CardRecord card = null;
        boolean firstEntry;       // EIBCALEN = 0
        String abendCode = x("", 4);
        String abendCulprit = x("", 8);
        String abendReason = x("", 50);
        String abendMsg = x("", 72);
        int respCd;
        int reasCd;
    }

    /** A CICS transaction entered the program (#4343): one task of it in the region (CicsTask.region()),
     *  ENTER pressed -- `request` its COMMAREA, null when started from a cleared screen -- run through runTask. Returns the COMMAREA its RETURN passes on (null: none). */
    public CocrdslcCommarea handleTransaction(String transid, CocrdslcCommarea request) {
        log.info("Cocrdslc: handleTransaction");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "COCRDSLC", this::runTask);
        return task.returned(CocrdslcCommarea.class);
    }

    /** One pseudo-conversational task of this program (#3754): paragraph 0000-MAIN. */
    public void runTask(CicsTask task) {
        log.info("Cocrdslc: runTask");
        Ws w = new Ws();
        activeTask.set(new Active(task, w));
        try {
            main(task, w);
        } finally {
            activeTask.remove();
        }
    }

    // ---------------------------------------------------------------- 0000-MAIN
    private void main(CicsTask task, Ws w) {
        // 0000-MAIN: EXEC CICS HANDLE ABEND LABEL(ABEND-ROUTINE)
        task.handleAbend("ABEND-ROUTINE");
        // 0000-MAIN: INITIALIZE CC-WORK-AREA WS-MISC-STORAGE WS-COMMAREA (done by new Ws())
        // 0000-MAIN: MOVE LIT-THISTRANID TO WS-TRANID; SET WS-RETURN-MSG-OFF (done by new Ws())

        w.firstEntry = !task.hasCommarea();
        CarddemoCommarea ca;
        CocrdslcCommarea progCa = null;
        // DEFECT (kept): the test "CDEMO-FROM-PROGRAM = LIT-MENUPGM AND NOT CDEMO-PGM-REENTER" reads CARDDEMO-COMMAREA
        // in WORKING-STORAGE before DFHCOMMAREA is moved into it, so it is never true when EIBCALEN > 0.
        // One-line fix: test the fields of DFHCOMMAREA, or move the commarea before the IF.
        if (w.firstEntry) {
            ca = initCommarea();
        } else {
            CocrdslcCommarea in = task.commarea(CocrdslcCommarea.class);
            ca = in == null || in.getCarddemoCommarea() == null ? initCommarea() : copyCommarea(in.getCarddemoCommarea());
            progCa = in;
        }

        // YYYY-STORE-PFKEY
        storePfkey(w, task.aid());

        // 0000-MAIN: check the AID
        boolean pfkValid = false;
        if (eq(w.ccAid, "ENTER") || eq(w.ccAid, "PFK03")) {
            pfkValid = true;
        }
        if (!pfkValid) {
            w.ccAid = x("ENTER", 5);
        }

        // 0000-MAIN: EVALUATE TRUE
        int ctx = ca.getCdemoPgmContext() == null ? 0 : ca.getCdemoPgmContext();
        if (eq(w.ccAid, "PFK03")) {
            if (CobolCompare.eq(ca.getCdemoFromTranid(), CobolCompare.lowValues(4)) || CobolCompare.eq(ca.getCdemoFromTranid(), "")) {
                ca.setCdemoToTranid(x(LIT_MENUTRANID, 4));
            } else {
                ca.setCdemoToTranid(ca.getCdemoFromTranid());
            }
            if (CobolCompare.eq(ca.getCdemoFromProgram(), CobolCompare.lowValues(8)) || CobolCompare.eq(ca.getCdemoFromProgram(), "")) {
                ca.setCdemoToProgram(x(LIT_MENUPGM, 8));
            } else {
                ca.setCdemoToProgram(ca.getCdemoFromProgram());
            }
            ca.setCdemoFromTranid(x(LIT_THISTRANID, 4));
            ca.setCdemoFromProgram(x(LIT_THISPGM, 8));
            ca.setCdemoUserType("U");
            ca.setCdemoPgmContext(0);
            ca.setCdemoLastMapset(x(LIT_THISMAPSET, 7));
            ca.setCdemoLastMap(x(LIT_THISMAP, 7));
            // EXEC CICS XCTL PROGRAM(CDEMO-TO-PROGRAM) COMMAREA(CARDDEMO-COMMAREA)
            String resp = dispatchCdemoToProgramL331(task, ca.getCdemoToProgram(), ca);   // line 331
            if (!"NORMAL".equals(resp)) {
                // no RESP / HANDLE CONDITION: CICS default action abends the task
                String label = task.abendOnCondition(resp);
                if (label != null) {
                    // the HANDLE ABEND exit of line 250 takes the abend: ABEND-ROUTINE
                    onAbendL250(new CicsAbendException(CicsTask.abcodeFor(resp), "COCRDSLC",
                            "app/cbl/COCRDSLC.cbl:331"));
                }
            }
            return;
        } else if (ctx == 0 && CobolCompare.eq(ca.getCdemoFromProgram(), LIT_CCLISTPGM)) {
            // coming from credit card list screen, criteria already validated
            w.inputFlag = '0';
            w.ccAcctId = zeroFmt(ca.getCdemoAcctId(), 11);
            w.ccCardNum = zeroFmt(ca.getCdemoCardNum(), 16);
            readData(task, w);
            sendMap(task, w, ca);
            commonReturn(task, ca, progCa);
            return;
        } else if (ctx == 0) {
            // coming from some other context, criteria to be gathered
            sendMap(task, w, ca);
            commonReturn(task, ca, progCa);
            return;
        } else if (ctx == 1) {
            processInputs(task, w, ca);
            if (w.inputFlag == '1') {
                sendMap(task, w, ca);
                commonReturn(task, ca, progCa);
                return;
            } else {
                readData(task, w);
                sendMap(task, w, ca);
                commonReturn(task, ca, progCa);
                return;
            }
        } else {
            // WHEN OTHER
            w.abendCulprit = x(LIT_THISPGM, 8);
            w.abendCode = x("0001", 4);
            w.abendReason = x("", 50);
            w.returnMsg = x("UNEXPECTED DATA SCENARIO", 75);
            // SEND-PLAIN-TEXT
            task.sendText(w.returnMsg, 75, "ERASE", "FREEKB");
            task.returnTransid(null, null);
            return;
        }
        // The "IF INPUT-ERROR" block after the EVALUATE at the end of 0000-MAIN is unreachable: every WHEN ends the
        // task (RETURN, XCTL or GO TO COMMON-RETURN).
    }

    // ---------------------------------------------------------------- COMMON-RETURN
    private void commonReturn(CicsTask task, CarddemoCommarea ca, CocrdslcCommarea in) {
        // COMMON-RETURN: MOVE WS-RETURN-MSG TO CCARD-ERROR-MSG (working storage only, never output)
        // MOVE CARDDEMO-COMMAREA TO WS-COMMAREA; MOVE WS-THIS-PROGCOMMAREA TO WS-COMMAREA(161:12)
        CocrdslcCommarea out = CocrdslcCommarea.fromPrefix(ca);
        if (in != null) {
            out.setWsThisProgcommarea(in.getWsThisProgcommarea());   // never changed by this program
        }
        task.returnTransid(LIT_THISTRANID, out, 2000);
    }

    // ---------------------------------------------------------------- YYYY-STORE-PFKEY
    private void storePfkey(Ws w, String aid) {
        String a = aid == null ? "" : aid;
        switch (a) {
            case "ENTER" -> w.ccAid = x("ENTER", 5);
            case "CLEAR" -> w.ccAid = x("CLEAR", 5);
            case "PA1" -> w.ccAid = x("PA1", 5);
            case "PA2" -> w.ccAid = x("PA2", 5);
            default -> {
                if (a.startsWith("PF")) {
                    int n = Integer.parseInt(a.substring(2));
                    int k = n > 12 ? n - 12 : n;
                    w.ccAid = x(String.format(Locale.ROOT, "PFK%02d", k), 5);
                }
                // PA3 and anything else: CCARD-AID keeps its INITIALIZEd spaces
            }
        }
    }

    // ---------------------------------------------------------------- 1000-SEND-MAP
    private void sendMap(CicsTask task, Ws w, CarddemoCommarea ca) {
        CcrdslaScreen s = new CcrdslaScreen();
        CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
        screenInit(task, s);                 // 1100-SCREEN-INIT
        setupScreenVars(w, ca, s);           // 1200-SETUP-SCREEN-VARS
        setupScreenAttrs(w, ca, s, sub);     // 1300-SETUP-SCREEN-ATTRS
        // 1400-SEND-SCREEN
        ca.setCdemoPgmContext(1);            // SET CDEMO-PGM-REENTER TO TRUE
        task.sendMap(LIT_THISMAP, LIT_THISMAPSET, s, sub, "CURSOR", "ERASE", "FREEKB");
    }

    /** 1100-SCREEN-INIT */
    private void screenInit(CicsTask task, CcrdslaScreen s) {
        // MOVE LOW-VALUES TO CCRDSLAO
        s.setTrnname(lv(4));
        s.setTitle01(lv(40));
        s.setCurdate(lv(8));
        s.setPgmname(lv(8));
        s.setTitle02(lv(40));
        s.setCurtime(lv(8));
        s.setAcctsid(lv(11));
        s.setCardsid(lv(16));
        s.setCrdname(lv(50));
        s.setCrdstcd(lv(1));
        s.setExpmon(lv(2));
        s.setExpyear(lv(4));
        s.setInfomsg(lv(40));
        s.setErrmsg(lv(80));
        s.setFkeys(lv(75));

        LocalDateTime now = task.now();   // FUNCTION CURRENT-DATE
        s.setTitle01(x(TITLE01, 40));
        s.setTitle02(x(TITLE02, 40));
        s.setTrnname(x(LIT_THISTRANID, 4));
        s.setPgmname(x(LIT_THISPGM, 8));
        s.setCurdate(now.format(DateTimeFormatter.ofPattern("MM/dd/yy", Locale.ROOT)));
        s.setCurtime(now.format(DateTimeFormatter.ofPattern("HH:mm:ss", Locale.ROOT)));
    }

    /** 1200-SETUP-SCREEN-VARS */
    private void setupScreenVars(Ws w, CarddemoCommarea ca, CcrdslaScreen s) {
        if (w.firstEntry) {
            w.infoMsg = x(MSG_PROMPT_INPUT, 40);          // SET WS-PROMPT-FOR-INPUT
        } else {
            if (ca.getCdemoAcctId() == null || ca.getCdemoAcctId() == 0L) {
                s.setAcctsid(lv(11));
            } else {
                s.setAcctsid(x(w.ccAcctId, 11));
            }
            if (ca.getCdemoCardNum() == null || ca.getCdemoCardNum() == 0L) {
                s.setCardsid(lv(16));
            } else {
                s.setCardsid(x(w.ccCardNum, 16));
            }
            if (CobolCompare.eq(w.infoMsg, MSG_FOUND)) {
                CardRecord c = w.card;
                s.setCrdname(x(c == null ? null : c.getCardEmbossedName(), 50));
                String exp = x(c == null ? null : c.getCardExpiraionDate(), 10);   // CARD-EXPIRAION-DATE-X
                s.setExpmon(exp.substring(5, 7));    // CARD-EXPIRY-MONTH
                s.setExpyear(exp.substring(0, 4));   // CARD-EXPIRY-YEAR
                s.setCrdstcd(x(c == null ? null : c.getCardActiveStatus(), 1));
            }
        }
        if (noInfo(w)) {
            w.infoMsg = x(MSG_PROMPT_INPUT, 40);
        }
        s.setErrmsg(x(w.returnMsg, 80));
        s.setInfomsg(x(w.infoMsg, 40));
    }

    /** 1300-SETUP-SCREEN-ATTRS */
    private void setupScreenAttrs(Ws w, CarddemoCommarea ca, CcrdslaScreen s, CicsTask.MapSubfields sub) {
        boolean fromList = CobolCompare.eq(ca.getCdemoLastMapset(), LIT_CCLISTMAPSET)
                && CobolCompare.eq(ca.getCdemoFromProgram(), LIT_CCLISTPGM);
        if (fromList) {
            sub.attr("ACCTSID", DFHBMPRF);
            sub.attr("CARDSID", DFHBMPRF);
        } else {
            sub.attr("ACCTSID", DFHBMFSE);
            sub.attr("CARDSID", DFHBMFSE);
        }

        // position cursor
        if (w.acctFlag == '0' || w.acctFlag == ' ') {
            sub.cursor("ACCTSID");
        } else if (w.cardFlag == '0' || w.cardFlag == ' ') {
            sub.cursor("CARDSID");
        } else {
            sub.cursor("ACCTSID");
        }

        // colours
        if (fromList) {
            sub.color("ACCTSID", DFHDFCOL);
            sub.color("CARDSID", DFHDFCOL);
        }
        if (w.acctFlag == '0') {
            sub.color("ACCTSID", DFHRED);
        }
        if (w.cardFlag == '0') {
            sub.color("CARDSID", DFHRED);
        }
        boolean reenter = ca.getCdemoPgmContext() != null && ca.getCdemoPgmContext() == 1;
        if (w.acctFlag == ' ' && reenter) {
            s.setAcctsid(x("*", 11));
            sub.color("ACCTSID", DFHRED);
        }
        if (w.cardFlag == ' ' && reenter) {
            s.setCardsid(x("*", 16));
            sub.color("CARDSID", DFHRED);
        }
        if (noInfo(w)) {
            sub.color("INFOMSG", DFHBMDAR);
        } else {
            sub.color("INFOMSG", DFHNEUTR);
        }
    }

    // ---------------------------------------------------------------- 2000-PROCESS-INPUTS
    private void processInputs(CicsTask task, Ws w, CarddemoCommarea ca) {
        // 2100-RECEIVE-MAP (RESP never tested; on MAPFAIL the input area keeps its initial blanks)
        CcrdslaScreen in = task.receive(LIT_THISMAP, LIT_THISMAPSET, CcrdslaScreen.class).orElse(new CcrdslaScreen());
        // 2200-EDIT-MAP-INPUTS
        w.inputFlag = '0';
        w.cardFlag = '1';
        w.acctFlag = '1';

        String acctIn = x(in.getAcctsid(), 11);
        if (CobolCompare.eq(acctIn, "*") || CobolCompare.eq(acctIn, "")) {
            w.ccAcctId = CobolCompare.lowValues(11);
        } else {
            w.ccAcctId = acctIn;
        }
        String cardIn = x(in.getCardsid(), 16);
        if (CobolCompare.eq(cardIn, "*") || CobolCompare.eq(cardIn, "")) {
            w.ccCardNum = CobolCompare.lowValues(16);
        } else {
            w.ccCardNum = cardIn;
        }

        editAccount(w, ca);   // 2210-EDIT-ACCOUNT
        editCard(w, ca);      // 2220-EDIT-CARD

        if (w.acctFlag == ' ' && w.cardFlag == ' ') {
            w.returnMsg = x("No input received", 75);   // SET NO-SEARCH-CRITERIA-RECEIVED
        }
        // 2000-PROCESS-INPUTS: MOVE WS-RETURN-MSG TO CCARD-ERROR-MSG; CCARD-NEXT-PROG/MAPSET/MAP (working storage only)
    }

    /** 2210-EDIT-ACCOUNT */
    private void editAccount(Ws w, CarddemoCommarea ca) {
        w.acctFlag = '0';
        if (CobolCompare.eq(w.ccAcctId, CobolCompare.lowValues(11)) || CobolCompare.eq(w.ccAcctId, "")
                || allZeroDigits(w.ccAcctId)) {
            w.inputFlag = '1';
            w.acctFlag = ' ';
            if (msgOff(w)) {
                w.returnMsg = x("Account number not provided", 75);
            }
            ca.setCdemoAcctId(0L);
            return;
        }
        if (!isNumeric(w.ccAcctId)) {
            w.inputFlag = '1';
            w.acctFlag = '0';
            if (msgOff(w)) {
                w.returnMsg = x("ACCOUNT FILTER,IF SUPPLIED MUST BE A 11 DIGIT NUMBER", 75);
            }
            ca.setCdemoAcctId(0L);
            return;
        }
        ca.setCdemoAcctId(CobolRecords.numval(w.ccAcctId, '.').longValue());
        w.acctFlag = '1';
    }

    /** 2220-EDIT-CARD */
    private void editCard(Ws w, CarddemoCommarea ca) {
        w.cardFlag = '0';
        if (CobolCompare.eq(w.ccCardNum, CobolCompare.lowValues(16)) || CobolCompare.eq(w.ccCardNum, "")
                || allZeroDigits(w.ccCardNum)) {
            w.inputFlag = '1';
            w.cardFlag = ' ';
            if (msgOff(w)) {
                w.returnMsg = x("Card number not provided", 75);
            }
            ca.setCdemoCardNum(0L);
            return;
        }
        if (!isNumeric(w.ccCardNum)) {
            w.inputFlag = '1';
            w.cardFlag = '0';
            if (msgOff(w)) {
                w.returnMsg = x("CARD ID FILTER,IF SUPPLIED MUST BE A 16 DIGIT NUMBER", 75);
            }
            ca.setCdemoCardNum(0L);
            return;
        }
        ca.setCdemoCardNum(CobolRecords.numval(w.ccCardNum, '.').longValue());
        w.cardFlag = '1';
    }

    // ---------------------------------------------------------------- 9000-READ-DATA
    private void readData(CicsTask task, Ws w) {
        getCardByAcctCard(task, w);   // 9100-GETCARD-BYACCTCARD
    }

    /** 9100-GETCARD-BYACCTCARD */
    private void getCardByAcctCard(CicsTask task, Ws w) {
        String key = x(w.ccCardNum, 16);   // MOVE CC-CARD-NUM TO WS-CARD-RID-CARDNUM
        CicsTask.FileRead<CardRecord> r = task.read(LIT_CARDFILENAME, () -> readCarddat(key));
        w.respCd = r.resp();
        w.reasCd = r.resp2();
        if (r.resp() == 0) {
            // INTO(CARD-RECORD): the program's own copy of the record
            java.nio.charset.Charset cs = CobolRecords.charset();
            w.card = CardRecord.fromRecord(r.record().toRecord(cs), cs);
            w.infoMsg = x(MSG_FOUND, 40);                  // SET FOUND-CARDS-FOR-ACCOUNT
        } else if (r.resp() == 13) {
            w.inputFlag = '1';
            w.acctFlag = '0';
            w.cardFlag = '0';
            if (msgOff(w)) {
                w.returnMsg = x("Did not find cards for this search condition", 75);
            }
        } else {
            w.inputFlag = '1';
            if (msgOff(w)) {
                w.acctFlag = '0';
            }
            String msg = x("File Error: ", 12) + x("READ", 8) + x(" on ", 4) + x(LIT_CARDFILENAME, 9)
                    + x(" returned RESP ", 15) + x(String.format(Locale.ROOT, "%09d", w.respCd), 10)
                    + x(",RESP2 ", 7) + x(String.format(Locale.ROOT, "%09d", w.reasCd), 10) + x("", 5);
            w.returnMsg = x(msg, 75);
        }
    }

    // 9150-GETCARD-BYACCT (READ of CARDAIX) is never PERFORMed by the program: not ported.

    // ---------------------------------------------------------------- ABEND-ROUTINE
    private void abendRoutine(CicsTask task, Ws w) {
        // DEFECT (kept): ABEND-MSG is initialised to SPACES, never LOW-VALUES, so this test is never true and the
        // 'UNEXPECTED ABEND OCCURRED.' text is never shown. One-line fix: test ABEND-MSG EQUAL SPACES.
        if (CobolCompare.eq(w.abendMsg, CobolCompare.lowValues(72))) {
            w.abendMsg = x("UNEXPECTED ABEND OCCURRED.", 72);
        }
        w.abendCulprit = x(LIT_THISPGM, 8);
        // EXEC CICS SEND FROM(ABEND-DATA) LENGTH(LENGTH OF ABEND-DATA) NOHANDLE
        String data = w.abendCode + w.abendCulprit + w.abendReason + w.abendMsg;
        task.sendText(data, 134);
        task.handleAbendCancel();       // EXEC CICS HANDLE ABEND CANCEL
        task.abend("9999");             // EXEC CICS ABEND ABCODE('9999')
    }

    // ---------------------------------------------------------------- helpers
    private static CarddemoCommarea initCommarea() {
        return copyCommarea(new CarddemoCommarea());
    }

    private static CarddemoCommarea copyCommarea(CarddemoCommarea s) {
        CarddemoCommarea c = new CarddemoCommarea();
        c.setCdemoFromTranid(x(s.getCdemoFromTranid(), 4));
        c.setCdemoFromProgram(x(s.getCdemoFromProgram(), 8));
        c.setCdemoToTranid(x(s.getCdemoToTranid(), 4));
        c.setCdemoToProgram(x(s.getCdemoToProgram(), 8));
        c.setCdemoUserId(x(s.getCdemoUserId(), 8));
        c.setCdemoUserType(x(s.getCdemoUserType(), 1));
        c.setCdemoPgmContext(s.getCdemoPgmContext() == null ? 0 : s.getCdemoPgmContext());
        c.setCdemoCustId(s.getCdemoCustId() == null ? 0 : s.getCdemoCustId());
        c.setCdemoCustFname(x(s.getCdemoCustFname(), 25));
        c.setCdemoCustMname(x(s.getCdemoCustMname(), 25));
        c.setCdemoCustLname(x(s.getCdemoCustLname(), 25));
        c.setCdemoAcctId(s.getCdemoAcctId() == null ? 0L : s.getCdemoAcctId());
        c.setCdemoAcctStatus(x(s.getCdemoAcctStatus(), 1));
        c.setCdemoCardNum(s.getCdemoCardNum() == null ? 0L : s.getCdemoCardNum());
        c.setCdemoLastMap(x(s.getCdemoLastMap(), 7));
        c.setCdemoLastMapset(x(s.getCdemoLastMapset(), 7));
        return c;
    }

    /** MOVE to alphanumeric: pad with spaces / truncate on the right. */
    private static String x(String v, int n) {
        return CobolRecords.fit(v, n, CobolRecords.charset());
    }

    private static String lv(int n) {
        return "\u0000".repeat(n);
    }

    private static boolean eq(String a, String b) {
        return CobolCompare.eq(a, b);
    }

    private static boolean msgOff(Ws w) {
        return CobolCompare.eq(w.returnMsg, "");
    }

    private static boolean noInfo(Ws w) {
        return CobolCompare.eq(w.infoMsg, "") || CobolCompare.eq(w.infoMsg, CobolCompare.lowValues(40));
    }

    /** MOVE of an unsigned 9(n) number to an X(n) redefined item: its digits, zero-padded. */
    private static String zeroFmt(Long v, int width) {
        String d = Long.toString(Math.abs(v == null ? 0L : v));
        d = d.length() >= width ? d.substring(d.length() - width) : "0".repeat(width - d.length()) + d;
        return d;
    }

    /** IF item IS NOT NUMERIC (alphanumeric class test): every character a digit. */
    private static boolean isNumeric(String s) {
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < '0' || c > '9') {
                return false;
            }
        }
        return !s.isEmpty();
    }

    /** CC-xxx-N EQUAL ZEROS on the numeric redefinition (taken as: every character the digit 0). */
    private static boolean allZeroDigits(String s) {
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) != '0') {
                return false;
            }
        }
        return !s.isEmpty();
    }

    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region
     *  (CicsTask.region()), run through runTask on `request`, passed by reference -- what it changes, the caller sees. */
    public CocrdslcCommarea handleLink(CocrdslcCommarea request) {
        log.info("Cocrdslc: handleLink");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("COCRDSLC", request);
        region.run(task, "COCRDSLC", this::runTask);
        return request;
    }

    /** EXEC CICS XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COCRDSLC.cbl:331, COMMAREA(CARDDEMO-COMMAREA): the target is data-driven (candidates the engine found: COMEN01C (moves)).
     *  Also MOVEd from CDEMO-FROM-PROGRAM, whose content is not known statically.
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchCdemoToProgramL331(CicsTask task, String program, Object commarea) {
        return task.xctl(program.stripTrailing(), commarea);
    }

    /** AWS.M2.CARDDEMO.CARDDATA.VSAM.KSDS as CICS file CARDAIX at app/cbl/COCRDSLC.cbl:783; VSAM defines field testing: open (3 public / 0 private estates). */
    public List<CardRecord> readCardaix(Long cardAcctId) {
        return cardRecordRepository.findByCardAcctId(cardAcctId);
    }

    /** AWS.M2.CARDDEMO.CARDDATA.VSAM.KSDS as CICS file CARDDAT at app/cbl/COCRDSLC.cbl:742; VSAM defines field testing: open (3 public / 0 private estates). */
    public Optional<CardRecord> readCarddat(String key) {
        return cardRecordRepository.findById(key);
    }

    /**
     * EXEC CICS HANDLE ABEND at app/cbl/COCRDSLC.cbl:250 (paragraph 0000-MAIN) routes abends to ABEND-ROUTINE.
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     */
    public void onAbendL250(CicsAbendException e) {
        log.info("HANDLE ABEND LABEL ABEND-ROUTINE at line 250", e);
        // ABEND-ROUTINE, on the task that is running
        Active a = activeTask.get();
        if (a != null) {
            abendRoutine(a.task(), a.ws());
        }
    }

    /**
     * EXEC CICS ABEND ABCODE(9999) at app/cbl/COCRDSLC.cbl:875 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendLegacy9999L875() {
        throw new CicsAbendException("9999", "COCRDSLC", "app/cbl/COCRDSLC.cbl:875");
    }
}
