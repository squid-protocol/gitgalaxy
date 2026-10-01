package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea8;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Cousr2aScreen;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.SecUserData;
import com.gitgalaxy.modernized.repository.vsam.SecUserDataRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
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
 * READ at line 322 tests NORMAL,NOTFND
 * REWRITE at line 360 tests NORMAL,NOTFND
 * TODO: the RESP of RECEIVE at line 285 (paragraph RECEIVE-USRUPD-SCREEN) is never tested
 * Screens (#3619): Cousr2aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Cousr02cService {

    private static final Logger log = LoggerFactory.getLogger(Cousr02cService.class);

    // DFHBMSCA colour attribute bytes (EBCDIC)
    private static final int DFHRED = 0xF2;
    private static final int DFHGREEN = 0xF4;
    private static final int DFHNEUTR = 0xF7;

    private final ObjectProvider<Coadm01cService> coadm01cService;
    private final ObjectProvider<Cosgn00cService> cosgn00cService;
    private final SecUserDataRepository secUserDataRepository;

    public void executeCousr02c(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for COUSR02C");
        // COUSR02C is a pseudo-conversational CICS program: its whole PROCEDURE DIVISION is ported in runTask.
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea8 handleTransaction(String transid, CarddemoCommarea8 request) {
        log.info("Cousr02c: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of this program (#3754): MAIN-PARA and the paragraphs it performs. */
    public void runTask(CicsTask task) {
        log.info("Cousr02c: runTask");
        new Run(task).mainPara();
    }

    /** Another program LINKed / XCTLed to this one. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea8 handleLink(CarddemoCommarea8 request) {
        log.info("Cousr02c: handleLink");
        return request;
    }

    /** XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COUSR02C.cbl:258: the target is data-driven. Candidates: COADM01C (moves), COSGN00C (moves).
     *  Also MOVEd from CDEMO-FROM-PROGRAM, whose content is not known statically: those names reach the default branch.
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCdemoToProgramL258(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COADM01C":
                return coadm01cService.getObject().handleLink((CarddemoCommarea) request);
            case "COSGN00C":
                cosgn00cService.getObject().handleLink();
                return null;
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COUSR02C.cbl:258: no known target " + program);
        }
    }

    /** AWS.M2.CARDDEMO.USRSEC.VSAM.KSDS as CICS file USRSEC at app/cbl/COUSR02C.cbl:322, 360; VSAM defines field testing: open (3 public / 0 private estates). */
    public Optional<SecUserData> readUsrsec(String key) {
        return secUserDataRepository.findById(key);
    }

    public SecUserData rewriteUsrsec(SecUserData record) {
        return secUserDataRepository.save(record);
    }

    /** SEND MAP(COUSR2A) MAPSET(COUSR02) FROM(COUSR2AO) at app/cbl/COUSR02C.cbl:272 (#3619).
     *  TODO: port the logic that fills COUSR2AO before the SEND.
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public Cousr2aScreen renderCousr2a(Cousr2aScreen screen) {
        return screen;
    }

    /** RECEIVE MAP(COUSR2A) MAPSET(COUSR02) INTO(COUSR2AI) at app/cbl/COUSR02C.cbl:285 (#3619).
     *  `aid` is the key the user pressed (EIBAID): ENTER, PF1-PF24, CLEAR, PA1-PA3.
     *  TODO: port the logic that reads COUSR2AI after the RECEIVE, and return the screen to show next.
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public ScreenModel submitCousr2a(Cousr2aScreen input, String aid) {
        return renderCousr2a(input);
    }

    // ------------------------------------------------------------------------------------------
    // helpers
    // ------------------------------------------------------------------------------------------

    private static String spaces(int n) {
        return " ".repeat(n);
    }

    /** MOVE to PIC X(n): pad with spaces or truncate on the right. */
    private static String pic(String s, int n) {
        String v = s == null ? "" : s;
        return v.length() >= n ? v.substring(0, n) : v + spaces(n - v.length());
    }

    /** IF field = SPACES OR LOW-VALUES */
    private static boolean spacesOrLow(String s, int n) {
        return CobolCompare.eq(s, spaces(n)) || CobolCompare.eq(s, CobolCompare.lowValues(n));
    }

    private static SecUserData copySec(SecUserData s) {
        var cs = CobolRecords.charset();
        return SecUserData.fromRecord(s.toRecord(cs), cs);
    }

    private static SecUserData blankSec() {
        SecUserData s = new SecUserData();
        s.setSecUsrId(spaces(8));
        s.setSecUsrFname(spaces(20));
        s.setSecUsrLname(spaces(20));
        s.setSecUsrPwd(spaces(8));
        s.setSecUsrType(spaces(1));
        s.setSecUsrFiller(spaces(23));
        return s;
    }

    private static CarddemoCommarea8 blankCommarea() {
        CarddemoCommarea8 c = new CarddemoCommarea8();
        c.setCdemoFromTranid(spaces(4));
        c.setCdemoFromProgram(spaces(8));
        c.setCdemoToTranid(spaces(4));
        c.setCdemoToProgram(spaces(8));
        c.setCdemoUserId(spaces(8));
        c.setCdemoUserType(spaces(1));
        c.setCdemoPgmContext(0);
        c.setCdemoCustId(0);
        c.setCdemoCustFname(spaces(25));
        c.setCdemoCustMname(spaces(25));
        c.setCdemoCustLname(spaces(25));
        c.setCdemoAcctId(0L);
        c.setCdemoAcctStatus(spaces(1));
        c.setCdemoCardNum(0L);
        c.setCdemoLastMap(spaces(7));
        c.setCdemoLastMapset(spaces(7));
        c.setCdemoCu02UsridFirst(spaces(8));
        c.setCdemoCu02UsridLast(spaces(8));
        c.setCdemoCu02PageNum(0);
        c.setCdemoCu02NextPageFlg("N");
        c.setCdemoCu02UsrSelFlg(spaces(1));
        c.setCdemoCu02UsrSelected(spaces(8));
        return c;
    }

    /** MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA, as the program's own copy. */
    private static CarddemoCommarea8 normalize(CarddemoCommarea8 s) {
        CarddemoCommarea8 c = blankCommarea();
        c.setCdemoFromTranid(pic(s.getCdemoFromTranid(), 4));
        c.setCdemoFromProgram(pic(s.getCdemoFromProgram(), 8));
        c.setCdemoToTranid(pic(s.getCdemoToTranid(), 4));
        c.setCdemoToProgram(pic(s.getCdemoToProgram(), 8));
        c.setCdemoUserId(pic(s.getCdemoUserId(), 8));
        c.setCdemoUserType(pic(s.getCdemoUserType(), 1));
        if (s.getCdemoPgmContext() != null) c.setCdemoPgmContext(s.getCdemoPgmContext());
        if (s.getCdemoCustId() != null) c.setCdemoCustId(s.getCdemoCustId());
        c.setCdemoCustFname(pic(s.getCdemoCustFname(), 25));
        c.setCdemoCustMname(pic(s.getCdemoCustMname(), 25));
        c.setCdemoCustLname(pic(s.getCdemoCustLname(), 25));
        if (s.getCdemoAcctId() != null) c.setCdemoAcctId(s.getCdemoAcctId());
        c.setCdemoAcctStatus(pic(s.getCdemoAcctStatus(), 1));
        if (s.getCdemoCardNum() != null) c.setCdemoCardNum(s.getCdemoCardNum());
        c.setCdemoLastMap(pic(s.getCdemoLastMap(), 7));
        c.setCdemoLastMapset(pic(s.getCdemoLastMapset(), 7));
        c.setCdemoCu02UsridFirst(pic(s.getCdemoCu02UsridFirst(), 8));
        c.setCdemoCu02UsridLast(pic(s.getCdemoCu02UsridLast(), 8));
        if (s.getCdemoCu02PageNum() != null) c.setCdemoCu02PageNum(s.getCdemoCu02PageNum());
        c.setCdemoCu02NextPageFlg(pic(s.getCdemoCu02NextPageFlg(), 1));
        c.setCdemoCu02UsrSelFlg(pic(s.getCdemoCu02UsrSelFlg(), 1));
        c.setCdemoCu02UsrSelected(pic(s.getCdemoCu02UsrSelected(), 8));
        return c;
    }

    /** The program's working storage for one task. COUSR2AI and COUSR2AO share storage, so one screen holds both. */
    private final class Run {
        private final CicsTask task;
        private CarddemoCommarea8 ca;
        private final Cousr2aScreen scr = new Cousr2aScreen();
        private SecUserData sec = blankSec();
        private String wsMessage = spaces(80);
        private boolean errFlg;
        private boolean usrModified;
        private Integer errmsgColor;                       // ERRMSGC, when the program has moved a colour to it
        private final Set<String> cursor = new LinkedHashSet<>();  // fields whose <f>L holds -1

        Run(CicsTask task) {
            this.task = task;
            scr.setTrnname(spaces(4));
            scr.setTitle01(spaces(40));
            scr.setCurdate(spaces(8));
            scr.setPgmname(spaces(8));
            scr.setTitle02(spaces(40));
            scr.setCurtime(spaces(8));
            scr.setUsridin(spaces(8));
            scr.setFname(spaces(20));
            scr.setLname(spaces(20));
            scr.setPasswd(spaces(8));
            scr.setUsrtype(spaces(1));
            scr.setErrmsg(spaces(78));
        }

        /** MAIN-PARA */
        void mainPara() {
            errFlg = false;                       // SET ERR-FLG-OFF
            usrModified = false;                  // SET USR-MODIFIED-NO
            wsMessage = spaces(80);
            scr.setErrmsg(spaces(78));

            if (!task.hasCommarea()) {            // IF EIBCALEN = 0
                ca = blankCommarea();
                ca.setCdemoToProgram(pic("COSGN00C", 8));
                returnToPrevScreen();
            } else {
                ca = normalize(task.commarea(CarddemoCommarea8.class));
                if (ca.getCdemoPgmContext() == null || ca.getCdemoPgmContext() != 1) {  // NOT CDEMO-PGM-REENTER
                    ca.setCdemoPgmContext(1);
                    lowValuesToScreen();          // MOVE LOW-VALUES TO COUSR2AO
                    cursor.clear();
                    errmsgColor = null;
                    cursor.add("USRIDIN");        // MOVE -1 TO USRIDINL
                    if (!spacesOrLow(ca.getCdemoCu02UsrSelected(), 8)) {
                        scr.setUsridin(pic(ca.getCdemoCu02UsrSelected(), 8));
                        processEnterKey();
                    }
                    sendUsrupdScreen();
                } else {
                    receiveUsrupdScreen();
                    String aid = task.aid();
                    if ("ENTER".equals(aid)) {
                        processEnterKey();
                    } else if ("PF3".equals(aid)) {
                        updateUserInfo();
                        if (spacesOrLow(ca.getCdemoFromProgram(), 8)) {
                            ca.setCdemoToProgram(pic("COADM01C", 8));
                        } else {
                            ca.setCdemoToProgram(ca.getCdemoFromProgram());
                        }
                        returnToPrevScreen();
                    } else if ("PF4".equals(aid)) {
                        clearCurrentScreen();
                    } else if ("PF5".equals(aid)) {
                        updateUserInfo();
                    } else if ("PF12".equals(aid)) {
                        ca.setCdemoToProgram(pic("COADM01C", 8));
                        returnToPrevScreen();
                    } else {
                        errFlg = true;
                        wsMessage = pic("Invalid key pressed. Please see below...", 80);  // CCDA-MSG-INVALID-KEY
                        sendUsrupdScreen();
                    }
                }
            }

            if (task.ended()) {                   // XCTL took the task, or an unhandled condition abended it
                return;
            }
            task.returnTransid("CU02", ca);       // EXEC CICS RETURN TRANSID(WS-TRANID) COMMAREA(...)
        }

        /** PROCESS-ENTER-KEY */
        void processEnterKey() {
            if (spacesOrLow(scr.getUsridin(), 8)) {
                errFlg = true;
                wsMessage = pic("User ID can NOT be empty...", 80);
                cursor.add("USRIDIN");
                sendUsrupdScreen();
            } else {
                cursor.add("USRIDIN");
            }

            if (!errFlg) {
                scr.setFname(spaces(20));
                scr.setLname(spaces(20));
                scr.setPasswd(spaces(8));
                scr.setUsrtype(spaces(1));
                sec.setSecUsrId(pic(scr.getUsridin(), 8));
                readUserSecFile();
            }

            if (!errFlg) {
                scr.setFname(pic(sec.getSecUsrFname(), 20));
                scr.setLname(pic(sec.getSecUsrLname(), 20));
                scr.setPasswd(pic(sec.getSecUsrPwd(), 8));
                scr.setUsrtype(pic(sec.getSecUsrType(), 1));
                sendUsrupdScreen();
            }
        }

        /** UPDATE-USER-INFO */
        void updateUserInfo() {
            if (spacesOrLow(scr.getUsridin(), 8)) {
                errFlg = true;
                wsMessage = pic("User ID can NOT be empty...", 80);
                cursor.add("USRIDIN");
                sendUsrupdScreen();
            } else if (spacesOrLow(scr.getFname(), 20)) {
                errFlg = true;
                wsMessage = pic("First Name can NOT be empty...", 80);
                cursor.add("FNAME");
                sendUsrupdScreen();
            } else if (spacesOrLow(scr.getLname(), 20)) {
                errFlg = true;
                wsMessage = pic("Last Name can NOT be empty...", 80);
                cursor.add("LNAME");
                sendUsrupdScreen();
            } else if (spacesOrLow(scr.getPasswd(), 8)) {
                errFlg = true;
                wsMessage = pic("Password can NOT be empty...", 80);
                cursor.add("PASSWD");
                sendUsrupdScreen();
            } else if (spacesOrLow(scr.getUsrtype(), 1)) {
                errFlg = true;
                wsMessage = pic("User Type can NOT be empty...", 80);
                cursor.add("USRTYPE");
                sendUsrupdScreen();
            } else {
                cursor.add("FNAME");
            }

            if (!errFlg) {
                sec.setSecUsrId(pic(scr.getUsridin(), 8));
                readUserSecFile();

                // DEFECT KEPT: the program goes on comparing and rewriting after a failed READ (it tests no
                // error flag here); on NOTFND it compares against stale SEC-USER-DATA and the REWRITE then
                // fails INVREQ. One-line fix: wrap the block below in IF NOT ERR-FLG-ON.
                if (!CobolCompare.eq(scr.getFname(), sec.getSecUsrFname())) {
                    sec.setSecUsrFname(pic(scr.getFname(), 20));
                    usrModified = true;
                }
                if (!CobolCompare.eq(scr.getLname(), sec.getSecUsrLname())) {
                    sec.setSecUsrLname(pic(scr.getLname(), 20));
                    usrModified = true;
                }
                if (!CobolCompare.eq(scr.getPasswd(), sec.getSecUsrPwd())) {
                    sec.setSecUsrPwd(pic(scr.getPasswd(), 8));
                    usrModified = true;
                }
                if (!CobolCompare.eq(scr.getUsrtype(), sec.getSecUsrType())) {
                    sec.setSecUsrType(pic(scr.getUsrtype(), 1));
                    usrModified = true;
                }

                if (usrModified) {
                    updateUserSecFile();
                } else {
                    wsMessage = pic("Please modify to update ...", 80);
                    errmsgColor = DFHRED;
                    sendUsrupdScreen();
                }
            }
        }

        /** RETURN-TO-PREV-SCREEN */
        void returnToPrevScreen() {
            if (spacesOrLow(ca.getCdemoToProgram(), 8)) {
                ca.setCdemoToProgram(pic("COSGN00C", 8));
            }
            ca.setCdemoFromTranid("CU02");
            ca.setCdemoFromProgram(pic("COUSR02C", 8));
            ca.setCdemoPgmContext(0);
            String resp = task.xctl(ca.getCdemoToProgram().trim(), ca);
            if (!"NORMAL".equals(resp)) {
                task.abendOnCondition(resp);      // no RESP on the XCTL: CICS's default action
            }
        }

        /** SEND-USRUPD-SCREEN */
        void sendUsrupdScreen() {
            populateHeaderInfo();
            scr.setErrmsg(pic(wsMessage, 78));
            CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
            if (errmsgColor != null) {
                sub.color("ERRMSG", errmsgColor);
            }
            for (String f : cursor) {
                sub.cursor(f);
            }
            task.sendMap(Cousr2aScreen.MAP, Cousr2aScreen.MAPSET, Cousr2aScreen.fromValues(scr.screenValues()),
                    sub, "ERASE", "CURSOR");
        }

        /** RECEIVE-USRUPD-SCREEN */
        void receiveUsrupdScreen() {
            // TODO (from the facts): the RESP of this RECEIVE is never tested; on MAPFAIL the program goes on
            // with COUSR2AI as it was.
            Optional<Cousr2aScreen> in = task.receive(Cousr2aScreen.MAP, Cousr2aScreen.MAPSET, Cousr2aScreen.class);
            if (in.isPresent()) {
                Cousr2aScreen r = in.get();
                if (r.getTrnname() != null) scr.setTrnname(pic(r.getTrnname(), 4));
                if (r.getTitle01() != null) scr.setTitle01(pic(r.getTitle01(), 40));
                if (r.getCurdate() != null) scr.setCurdate(pic(r.getCurdate(), 8));
                if (r.getPgmname() != null) scr.setPgmname(pic(r.getPgmname(), 8));
                if (r.getTitle02() != null) scr.setTitle02(pic(r.getTitle02(), 40));
                if (r.getCurtime() != null) scr.setCurtime(pic(r.getCurtime(), 8));
                if (r.getUsridin() != null) scr.setUsridin(pic(r.getUsridin(), 8));
                if (r.getFname() != null) scr.setFname(pic(r.getFname(), 20));
                if (r.getLname() != null) scr.setLname(pic(r.getLname(), 20));
                if (r.getPasswd() != null) scr.setPasswd(pic(r.getPasswd(), 8));
                if (r.getUsrtype() != null) scr.setUsrtype(pic(r.getUsrtype(), 1));
                if (r.getErrmsg() != null) scr.setErrmsg(pic(r.getErrmsg(), 78));
                cursor.clear();                   // the <f>L fields now hold the received lengths
            }
        }

        /** POPULATE-HEADER-INFO */
        void populateHeaderInfo() {
            LocalDateTime now = task.now();       // FUNCTION CURRENT-DATE
            scr.setTitle01(pic(spaces(6) + "AWS Mainframe Modernization", 40));   // CCDA-TITLE01
            scr.setTitle02(pic(spaces(14) + "CardDemo", 40));                     // CCDA-TITLE02
            scr.setTrnname("CU02");
            scr.setPgmname(pic("COUSR02C", 8));
            scr.setCurdate(String.format(Locale.ROOT, "%02d/%02d/%02d", now.getMonthValue(), now.getDayOfMonth(),
                    now.getYear() % 100));
            scr.setCurtime(String.format(Locale.ROOT, "%02d:%02d:%02d", now.getHour(), now.getMinute(),
                    now.getSecond()));
        }

        /** READ-USER-SEC-FILE */
        void readUserSecFile() {
            String key = sec.getSecUsrId();
            CicsTask.FileRead<SecUserData> r = task.readForUpdate("USRSEC", () -> readUsrsec(key));
            if (r.normal() && r.record() != null) {
                sec = copySec(r.record());        // READ INTO: the program's own copy
            }
            switch (r.resp()) {
                case 0:                           // DFHRESP(NORMAL)
                    wsMessage = pic("Press PF5 key to save your updates ...", 80);
                    errmsgColor = DFHNEUTR;
                    sendUsrupdScreen();
                    break;
                case 13:                          // DFHRESP(NOTFND)
                    errFlg = true;
                    wsMessage = pic("User ID NOT found...", 80);
                    cursor.add("USRIDIN");
                    sendUsrupdScreen();
                    break;
                default:
                    Sysout.display("RESP:", Sysout.number(BigDecimal.valueOf(r.resp()), 9, 0, true),
                            "REAS:", Sysout.number(BigDecimal.valueOf(r.resp2()), 9, 0, true));
                    errFlg = true;
                    wsMessage = pic("Unable to lookup User...", 80);
                    cursor.add("FNAME");
                    sendUsrupdScreen();
                    break;
            }
        }

        /** UPDATE-USER-SEC-FILE */
        void updateUserSecFile() {
            SecUserData rec = copySec(sec);
            int resp = task.rewrite("USRSEC", () -> rewriteUsrsec(rec));
            int resp2 = resp == 16 ? 2 : 0;       // REWRITE without a held READ UPDATE: INVREQ, RESP2 2
            switch (resp) {
                case 0:
                    wsMessage = spaces(80);
                    errmsgColor = DFHGREEN;
                    String id = sec.getSecUsrId();
                    int sp = id.indexOf(' ');     // DELIMITED BY SPACE
                    wsMessage = pic("User " + (sp < 0 ? id : id.substring(0, sp)) + " has been updated ...", 80);
                    sendUsrupdScreen();
                    break;
                case 13:
                    errFlg = true;
                    wsMessage = pic("User ID NOT found...", 80);
                    cursor.add("USRIDIN");
                    sendUsrupdScreen();
                    break;
                default:
                    Sysout.display("RESP:", Sysout.number(BigDecimal.valueOf(resp), 9, 0, true),
                            "REAS:", Sysout.number(BigDecimal.valueOf(resp2), 9, 0, true));
                    errFlg = true;
                    wsMessage = pic("Unable to Update User...", 80);
                    cursor.add("FNAME");
                    sendUsrupdScreen();
                    break;
            }
        }

        /** CLEAR-CURRENT-SCREEN */
        void clearCurrentScreen() {
            initializeAllFields();
            sendUsrupdScreen();
        }

        /** INITIALIZE-ALL-FIELDS */
        void initializeAllFields() {
            cursor.add("USRIDIN");
            scr.setUsridin(spaces(8));
            scr.setFname(spaces(20));
            scr.setLname(spaces(20));
            scr.setPasswd(spaces(8));
            scr.setUsrtype(spaces(1));
            wsMessage = spaces(80);
        }

        /** MOVE LOW-VALUES TO COUSR2AO (MAIN-PARA): data fields hold X'00'; BMS then keeps the map's INITIAL. */
        void lowValuesToScreen() {
            scr.setTrnname("\u0000".repeat(4));
            scr.setTitle01("\u0000".repeat(40));
            scr.setCurdate("\u0000".repeat(8));
            scr.setPgmname("\u0000".repeat(8));
            scr.setTitle02("\u0000".repeat(40));
            scr.setCurtime("\u0000".repeat(8));
            scr.setUsridin("\u0000".repeat(8));
            scr.setFname("\u0000".repeat(20));
            scr.setLname("\u0000".repeat(20));
            scr.setPasswd("\u0000".repeat(8));
            scr.setUsrtype("\u0000".repeat(1));
            scr.setErrmsg("\u0000".repeat(78));
        }
    }
}
