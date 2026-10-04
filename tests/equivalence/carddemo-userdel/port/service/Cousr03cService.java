package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.Cousr03cCarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Cousr3aScreen;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.SecUserData;
import com.gitgalaxy.modernized.repository.vsam.SecUserDataRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.time.LocalDateTime;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * READ at line 269 tests NORMAL,NOTFND
 * DELETE at line 307 tests NORMAL,NOTFND
 * The RESP of RECEIVE at line 232 (paragraph RECEIVE-USRDEL-SCREEN) is never tested by the program.
 * Screens (#3619): Cousr3aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Cousr03cService {

    private static final Logger log = LoggerFactory.getLogger(Cousr03cService.class);

    private static final String WS_PGMNAME = "COUSR03C";
    private static final String WS_TRANID = "CU03";
    private static final String WS_USRSEC_FILE = "USRSEC";
    private static final int DFHNEUTR = 0xF7;
    private static final int DFHGREEN = 0xF4;
    private static final String CCDA_TITLE01 = "      AWS Mainframe Modernization       ";
    private static final String CCDA_TITLE02 = "              CardDemo                  ";
    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed. Please see below...         ";

    private final ObjectProvider<Coadm01cService> coadm01cService;
    private final ObjectProvider<Cosgn00cService> cosgn00cService;
    private final SecUserDataRepository secUserDataRepository;

    public void executeCousr03c(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for COUSR03C");
        // COUSR03C is a pseudo-conversational CICS program with no parameters mapped from a
        // controller: its whole PROCEDURE DIVISION is ported in runTask(CicsTask).
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public Cousr03cCarddemoCommarea handleTransaction(String transid, Cousr03cCarddemoCommarea request) {
        log.info("Cousr03c: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of this program (#3754): MAIN-PARA and the paragraphs it performs. */
    public void runTask(CicsTask task) {
        log.info("Cousr03c: runTask");
        new Run(task).mainPara();
    }

    /** Another program LINKed / XCTLed to this one. TODO: [AI AGENT] implement from the program's business rules. */
    public Cousr03cCarddemoCommarea handleLink(Cousr03cCarddemoCommarea request) {
        log.info("Cousr03c: handleLink");
        return request;
    }

    /** XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COUSR03C.cbl:205: the target is data-driven. Candidates: COADM01C (moves), COSGN00C (moves).
     *  Also MOVEd from CDEMO-FROM-PROGRAM, whose content is not known statically: those names reach the default branch.
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCdemoToProgramL205(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COADM01C":
                return coadm01cService.getObject().handleLink((CarddemoCommarea) request);
            case "COSGN00C":
                cosgn00cService.getObject().handleLink();
                return null;
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COUSR03C.cbl:205: no known target " + program);
        }
    }

    /** AWS.M2.CARDDEMO.USRSEC.VSAM.KSDS as CICS file USRSEC at app/cbl/COUSR03C.cbl:269, 307; VSAM defines field testing: open (3 public / 0 private estates). */
    public Optional<SecUserData> readUsrsec(String key) {
        return secUserDataRepository.findById(key);
    }

    public void deleteUsrsec(String key) {
        secUserDataRepository.deleteById(key);
    }

    /** SEND MAP(COUSR3A) MAPSET(COUSR03) FROM(COUSR3AO) at app/cbl/COUSR03C.cbl:219 (#3619).
     *  TODO: port the logic that fills COUSR3AO before the SEND.
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public Cousr3aScreen renderCousr3a(Cousr3aScreen screen) {
        return screen;
    }

    /** RECEIVE MAP(COUSR3A) MAPSET(COUSR03) INTO(COUSR3AI) at app/cbl/COUSR03C.cbl:232 (#3619).
     *  `aid` is the key the user pressed (EIBAID): ENTER, PF1-PF24, CLEAR, PA1-PA3.
     *  TODO: port the logic that reads COUSR3AI after the RECEIVE, and return the screen to show next.
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public ScreenModel submitCousr3a(Cousr3aScreen input, String aid) {
        return renderCousr3a(input);
    }

    // ------------------------------------------------------------------------------------------
    // helpers (COBOL MOVE semantics for PIC X)
    // ------------------------------------------------------------------------------------------

    private static String fit(String v, int width) {
        String s = v == null ? "" : v;
        if (s.length() >= width) {
            return s.substring(0, width);
        }
        return s + " ".repeat(width - s.length());
    }

    private static String spaces(int n) {
        return " ".repeat(n);
    }

    /** IF field = SPACES OR LOW-VALUES */
    private static boolean blankOrLow(String v, int width) {
        return CobolCompare.eq(v, "") || CobolCompare.eq(v, CobolCompare.lowValues(width));
    }

    private static String rtrim(String v) {
        int n = v.length();
        while (n > 0 && v.charAt(n - 1) == ' ') {
            n--;
        }
        return v.substring(0, n);
    }

    private static int nz(Integer v) {
        return v == null ? 0 : v;
    }

    private static long nz(Long v) {
        return v == null ? 0L : v;
    }

    /** The program's own copy of CARDDEMO-COMMAREA (194 bytes). */
    private static Cousr03cCarddemoCommarea copyCommarea(Cousr03cCarddemoCommarea s, String nextPageFlgDefault) {
        Cousr03cCarddemoCommarea c = new Cousr03cCarddemoCommarea();
        c.setCdemoFromTranid(fit(s == null ? null : s.getCdemoFromTranid(), 4));
        c.setCdemoFromProgram(fit(s == null ? null : s.getCdemoFromProgram(), 8));
        c.setCdemoToTranid(fit(s == null ? null : s.getCdemoToTranid(), 4));
        c.setCdemoToProgram(fit(s == null ? null : s.getCdemoToProgram(), 8));
        c.setCdemoUserId(fit(s == null ? null : s.getCdemoUserId(), 8));
        c.setCdemoUserType(fit(s == null ? null : s.getCdemoUserType(), 1));
        c.setCdemoPgmContext(s == null ? 0 : nz(s.getCdemoPgmContext()));
        c.setCdemoCustId(s == null ? 0 : nz(s.getCdemoCustId()));
        c.setCdemoCustFname(fit(s == null ? null : s.getCdemoCustFname(), 25));
        c.setCdemoCustMname(fit(s == null ? null : s.getCdemoCustMname(), 25));
        c.setCdemoCustLname(fit(s == null ? null : s.getCdemoCustLname(), 25));
        c.setCdemoAcctId(s == null ? 0L : nz(s.getCdemoAcctId()));
        c.setCdemoAcctStatus(fit(s == null ? null : s.getCdemoAcctStatus(), 1));
        c.setCdemoCardNum(s == null ? 0L : nz(s.getCdemoCardNum()));
        c.setCdemoLastMap(fit(s == null ? null : s.getCdemoLastMap(), 7));
        c.setCdemoLastMapset(fit(s == null ? null : s.getCdemoLastMapset(), 7));
        c.setCdemoCu03UsridFirst(fit(s == null ? null : s.getCdemoCu03UsridFirst(), 8));
        c.setCdemoCu03UsridLast(fit(s == null ? null : s.getCdemoCu03UsridLast(), 8));
        c.setCdemoCu03PageNum(s == null ? 0 : nz(s.getCdemoCu03PageNum()));
        c.setCdemoCu03NextPageFlg(s == null ? nextPageFlgDefault : fit(s.getCdemoCu03NextPageFlg(), 1));
        c.setCdemoCu03UsrSelFlg(fit(s == null ? null : s.getCdemoCu03UsrSelFlg(), 1));
        c.setCdemoCu03UsrSelected(fit(s == null ? null : s.getCdemoCu03UsrSelected(), 8));
        return c;
    }

    /** One task's working storage and paragraphs. */
    private final class Run {
        private final CicsTask task;
        private final Charset cs = CobolRecords.charset();

        private Cousr03cCarddemoCommarea cc = copyCommarea(null, "N");   // CARDDEMO-COMMAREA (NEXT-PAGE-FLG VALUE 'N')
        private String message = spaces(80);                             // WS-MESSAGE
        private boolean errFlg;                                          // WS-ERR-FLG
        private int resp;                                                // WS-RESP-CD
        private int reas;                                                // WS-REAS-CD
        private SecUserData secUser = new SecUserData();                 // SEC-USER-DATA

        // COUSR3AI / COUSR3AO share storage: the four fields the program shows and edits
        private String usridin = spaces(8);                              // USRIDINI / USRIDINO
        private String fname = spaces(20);                               // FNAMEI / FNAMEO
        private String lname = spaces(20);                               // LNAMEI / LNAMEO
        private String usrtype = spaces(1);                              // USRTYPEI / USRTYPEO
        private final Set<String> cursor = new LinkedHashSet<>();        // fields whose length (xxxxL) holds -1
        private Integer errmsgColor;                                     // ERRMSGC, null = never set

        Run(CicsTask task) {
            this.task = task;
        }

        // MAIN-PARA
        void mainPara() {
            errFlg = false;                       // SET ERR-FLG-OFF TO TRUE
            message = spaces(80);                 // MOVE SPACES TO WS-MESSAGE ERRMSGO

            if (!task.hasCommarea()) {            // IF EIBCALEN = 0
                cc.setCdemoToProgram(fit("COSGN00C", 8));
                returnToPrevScreen();
            } else {
                cc = copyCommarea(task.commarea(Cousr03cCarddemoCommarea.class), spaces(1));
                if (nz(cc.getCdemoPgmContext()) != 1) {          // IF NOT CDEMO-PGM-REENTER
                    cc.setCdemoPgmContext(1);                    // SET CDEMO-PGM-REENTER TO TRUE
                    usridin = CobolCompare.lowValues(8);         // MOVE LOW-VALUES TO COUSR3AO
                    fname = CobolCompare.lowValues(20);
                    lname = CobolCompare.lowValues(20);
                    usrtype = CobolCompare.lowValues(1);
                    errmsgColor = null;
                    cursor.clear();
                    cursor.add("USRIDIN");                       // MOVE -1 TO USRIDINL
                    String sel = cc.getCdemoCu03UsrSelected();
                    if (!CobolCompare.eq(sel, "") && !CobolCompare.eq(sel, CobolCompare.lowValues(8))) {
                        usridin = fit(sel, 8);                   // MOVE CDEMO-CU03-USR-SELECTED TO USRIDINI
                        processEnterKey();
                    }
                    sendUsrdelScreen();
                } else {
                    receiveUsrdelScreen();
                    switch (task.aid()) {                        // EVALUATE EIBAID
                        case "ENTER":
                            processEnterKey();
                            break;
                        case "PF3": {
                            String from = cc.getCdemoFromProgram();
                            if (blankOrLow(from, 8)) {
                                cc.setCdemoToProgram(fit("COADM01C", 8));
                            } else {
                                cc.setCdemoToProgram(fit(from, 8));
                            }
                            returnToPrevScreen();
                            break;
                        }
                        case "PF4":
                            clearCurrentScreen();
                            break;
                        case "PF5":
                            deleteUserInfo();
                            break;
                        case "PF12":
                            cc.setCdemoToProgram(fit("COADM01C", 8));
                            returnToPrevScreen();
                            break;
                        default:                                 // WHEN OTHER
                            errFlg = true;
                            message = fit(CCDA_MSG_INVALID_KEY, 80);
                            sendUsrdelScreen();
                            break;
                    }
                }
            }

            if (task.ended()) {
                return;                           // an XCTL took control: nothing after it runs
            }
            task.returnTransid(WS_TRANID, cc);    // EXEC CICS RETURN TRANSID COMMAREA
        }

        // PROCESS-ENTER-KEY
        private void processEnterKey() {
            if (blankOrLow(usridin, 8)) {
                errFlg = true;
                message = fit("User ID can NOT be empty...", 80);
                cursor.add("USRIDIN");
                sendUsrdelScreen();
            } else {
                cursor.add("USRIDIN");
            }

            if (!errFlg) {
                fname = spaces(20);
                lname = spaces(20);
                usrtype = spaces(1);
                secUser.setSecUsrId(usridin);
                readUserSecFile();
            }

            if (!errFlg) {
                fname = fit(secUser.getSecUsrFname(), 20);
                lname = fit(secUser.getSecUsrLname(), 20);
                usrtype = fit(secUser.getSecUsrType(), 1);
                sendUsrdelScreen();
            }
        }

        // DELETE-USER-INFO
        private void deleteUserInfo() {
            if (blankOrLow(usridin, 8)) {
                errFlg = true;
                message = fit("User ID can NOT be empty...", 80);
                cursor.add("USRIDIN");
                sendUsrdelScreen();
            } else {
                cursor.add("USRIDIN");
            }

            if (!errFlg) {
                secUser.setSecUsrId(usridin);
                readUserSecFile();
                // DEFECT (kept): the DELETE runs even when the READ above failed (the error flag is not
                // tested); it then fails with INVREQ (no held record) and shows 'Unable to Update User...'.
                // Fix: wrap deleteUserSecFile() in IF NOT ERR-FLG-ON.
                deleteUserSecFile();
            }
        }

        // RETURN-TO-PREV-SCREEN
        private void returnToPrevScreen() {
            if (blankOrLow(cc.getCdemoToProgram(), 8)) {
                cc.setCdemoToProgram(fit("COSGN00C", 8));
            }
            cc.setCdemoFromTranid(fit(WS_TRANID, 4));
            cc.setCdemoFromProgram(fit(WS_PGMNAME, 8));
            cc.setCdemoPgmContext(0);
            task.xctl(rtrim(cc.getCdemoToProgram()), cc);   // XCTL PROGRAM(CDEMO-TO-PROGRAM) COMMAREA
        }

        // SEND-USRDEL-SCREEN
        private void sendUsrdelScreen() {
            Cousr3aScreen screen = new Cousr3aScreen();
            populateHeaderInfo(screen);
            screen.setUsridin(usridin);
            screen.setFname(fname);
            screen.setLname(lname);
            screen.setUsrtype(usrtype);
            screen.setErrmsg(fit(message, 78));   // MOVE WS-MESSAGE (80) TO ERRMSGO (78): truncated

            CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
            for (String f : cursor) {
                sub.cursor(f);
            }
            if (errmsgColor != null) {
                sub.color("ERRMSG", errmsgColor);
            }
            task.sendMap("COUSR3A", "COUSR03", screen, sub, "CURSOR", "ERASE");
        }

        // RECEIVE-USRDEL-SCREEN
        private void receiveUsrdelScreen() {
            Optional<Cousr3aScreen> in = task.receive("COUSR3A", "COUSR03", Cousr3aScreen.class);
            // The RESP is never tested (kept). On MAPFAIL COUSR3AI stays as it was.
            cursor.clear();   // RECEIVE replaces the length fields
            if (in.isPresent()) {
                Cousr3aScreen s = in.get();
                usridin = fit(s.getUsridin(), 8);
                fname = fit(s.getFname(), 20);
                lname = fit(s.getLname(), 20);
                usrtype = fit(s.getUsrtype(), 1);
            }
        }

        // POPULATE-HEADER-INFO
        private void populateHeaderInfo(Cousr3aScreen screen) {
            LocalDateTime now = task.now();   // FUNCTION CURRENT-DATE
            String year = String.format(Locale.ROOT, "%04d", now.getYear());
            screen.setTitle01(fit(CCDA_TITLE01, 40));
            screen.setTitle02(fit(CCDA_TITLE02, 40));
            screen.setTrnname(fit(WS_TRANID, 4));
            screen.setPgmname(fit(WS_PGMNAME, 8));
            screen.setCurdate(String.format(Locale.ROOT, "%02d/%02d/%s", now.getMonthValue(), now.getDayOfMonth(),
                    year.substring(2, 4)));
            screen.setCurtime(String.format(Locale.ROOT, "%02d:%02d:%02d", now.getHour(), now.getMinute(),
                    now.getSecond()));
        }

        // READ-USER-SEC-FILE
        private void readUserSecFile() {
            String key = secUser.getSecUsrId();
            CicsTask.FileRead<SecUserData> r = task.readForUpdate(WS_USRSEC_FILE, () -> readUsrsec(key));
            resp = r.resp();
            reas = r.resp2();
            if (r.normal() && r.record() != null) {
                // READ INTO: the program's own copy, never the managed entity
                secUser = SecUserData.fromRecord(r.record().toRecord(cs), cs);
            }
            switch (resp) {
                case 0:   // DFHRESP(NORMAL)
                    message = fit("Press PF5 key to delete this user ...", 80);
                    errmsgColor = DFHNEUTR;
                    sendUsrdelScreen();
                    break;
                case 13:  // DFHRESP(NOTFND)
                    errFlg = true;
                    message = fit("User ID NOT found...", 80);
                    cursor.add("USRIDIN");
                    sendUsrdelScreen();
                    break;
                default:
                    displayResp();
                    errFlg = true;
                    message = fit("Unable to lookup User...", 80);
                    cursor.add("FNAME");
                    sendUsrdelScreen();
                    break;
            }
        }

        // DELETE-USER-SEC-FILE
        private void deleteUserSecFile() {
            // DELETE without RIDFLD: the record the READ UPDATE holds. CicsTask gives no RESP2 for it: 0 is shown.
            resp = task.deleteHeld(WS_USRSEC_FILE, () -> deleteUsrsec(secUser.getSecUsrId()));
            reas = 0;
            switch (resp) {
                case 0:   // DFHRESP(NORMAL)
                    initializeAllFields();
                    message = spaces(80);
                    errmsgColor = DFHGREEN;
                    String id = secUser.getSecUsrId() == null ? "" : secUser.getSecUsrId();
                    int sp = id.indexOf(' ');
                    String shown = sp < 0 ? id : id.substring(0, sp);   // DELIMITED BY SPACE
                    message = fit("User " + shown + " has been deleted ...", 80);
                    sendUsrdelScreen();
                    break;
                case 13:  // DFHRESP(NOTFND)
                    errFlg = true;
                    message = fit("User ID NOT found...", 80);
                    cursor.add("USRIDIN");
                    sendUsrdelScreen();
                    break;
                default:
                    displayResp();
                    errFlg = true;
                    message = fit("Unable to Update User...", 80);
                    cursor.add("FNAME");
                    sendUsrdelScreen();
                    break;
            }
        }

        // CLEAR-CURRENT-SCREEN
        private void clearCurrentScreen() {
            initializeAllFields();
            sendUsrdelScreen();
        }

        // INITIALIZE-ALL-FIELDS
        private void initializeAllFields() {
            cursor.add("USRIDIN");
            usridin = spaces(8);
            fname = spaces(20);
            lname = spaces(20);
            usrtype = spaces(1);
            message = spaces(80);
        }

        private void displayResp() {
            Sysout.display("RESP:", Sysout.number(BigDecimal.valueOf(resp), 9, 0, true),
                    "REAS:", Sysout.number(BigDecimal.valueOf(reas), 9, 0, true));
        }
    }
}
