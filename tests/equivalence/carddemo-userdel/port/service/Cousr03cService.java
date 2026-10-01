package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea9;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Cousr3aScreen;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.SecUserData;
import com.gitgalaxy.modernized.repository.vsam.SecUserDataRepository;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * READ at line 269 tests NORMAL,NOTFND
 * DELETE at line 307 tests NORMAL,NOTFND
 * TODO: the RESP of RECEIVE at line 232 (paragraph RECEIVE-USRDEL-SCREEN) is never tested
 * Screens (#3619): Cousr3aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Cousr03cService {

    private static final Logger log = LoggerFactory.getLogger(Cousr03cService.class);

    private static final String PGMNAME = "COUSR03C";
    private static final String TRANID = "CU03";
    private static final String USRSEC = "USRSEC";
    private static final int COMM_LEN = 194;
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
        // COUSR03C is a pseudo-conversational CICS program: its whole PROCEDURE DIVISION is ported in runTask.
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea9 handleTransaction(String transid, CarddemoCommarea9 request) {
        log.info("Cousr03c: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of this program (#3754): MAIN-PARA and the paragraphs it performs. */
    public void runTask(CicsTask task) {
        log.info("Cousr03c: runTask");
        new Session(task).mainPara();
    }

    /** Another program LINKed / XCTLed to this one. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea9 handleLink(CarddemoCommarea9 request) {
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
     *  The logic that fills COUSR3AO is ported in runTask (SEND-USRDEL-SCREEN / POPULATE-HEADER-INFO).
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public Cousr3aScreen renderCousr3a(Cousr3aScreen screen) {
        return screen;
    }

    /** RECEIVE MAP(COUSR3A) MAPSET(COUSR03) INTO(COUSR3AI) at app/cbl/COUSR03C.cbl:232 (#3619).
     *  `aid` is the key the user pressed (EIBAID): ENTER, PF1-PF24, CLEAR, PA1-PA3.
     *  The logic that reads COUSR3AI after the RECEIVE is ported in runTask.
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public ScreenModel submitCousr3a(Cousr3aScreen input, String aid) {
        return renderCousr3a(input);
    }

    // ------------------------------------------------------------------ helpers

    /** MOVE to PIC X(n): pad with spaces or truncate on the right. */
    private static String fit(String v, int n) {
        String s = v == null ? "" : v;
        return s.length() >= n ? s.substring(0, n) : s + " ".repeat(n - s.length());
    }

    /** IF x = SPACES OR LOW-VALUES. */
    private static boolean isBlankOrLow(String v) {
        if (v == null) {
            return true;
        }
        return v.chars().allMatch(c -> c == ' ') || v.chars().allMatch(c -> c == 0);
    }

    private static String digits(Number n, int w) {
        long v = n == null ? 0 : Math.abs(n.longValue());
        String s = Long.toString(v);
        return s.length() > w ? s.substring(s.length() - w) : "0".repeat(w - s.length()) + s;
    }

    private static BigDecimal num(String s) {
        try {
            return CobolRecords.numval(s, '.');
        } catch (NumberFormatException e) {
            return BigDecimal.ZERO;
        }
    }

    /** CARDDEMO-COMMAREA as its 194 bytes of storage: MOVEs of groups are byte moves. */
    private static final class Comm {
        final StringBuilder b;

        Comm(String image) {
            b = new StringBuilder(fit(image, COMM_LEN));
        }

        String get(int off, int len) {
            return b.substring(off, off + len);
        }

        void put(int off, int len, String v) {
            b.replace(off, off + len, fit(v, len));
        }
    }

    private static Comm imageOf(CarddemoCommarea9 d) {
        Comm c = new Comm("");
        c.put(0, 4, d.getCdemoFromTranid());
        c.put(4, 8, d.getCdemoFromProgram());
        c.put(12, 4, d.getCdemoToTranid());
        c.put(16, 8, d.getCdemoToProgram());
        c.put(24, 8, d.getCdemoUserId());
        c.put(32, 1, d.getCdemoUserType());
        c.put(33, 1, digits(d.getCdemoPgmContext(), 1));
        c.put(34, 9, digits(d.getCdemoCustId(), 9));
        c.put(43, 25, d.getCdemoCustFname());
        c.put(68, 25, d.getCdemoCustMname());
        c.put(93, 25, d.getCdemoCustLname());
        c.put(118, 11, digits(d.getCdemoAcctId(), 11));
        c.put(129, 1, d.getCdemoAcctStatus());
        c.put(130, 16, digits(d.getCdemoCardNum(), 16));
        c.put(146, 7, d.getCdemoLastMap());
        c.put(153, 7, d.getCdemoLastMapset());
        c.put(160, 8, d.getCdemoCu03UsridFirst());
        c.put(168, 8, d.getCdemoCu03UsridLast());
        c.put(176, 8, digits(d.getCdemoCu03PageNum(), 8));
        c.put(184, 1, d.getCdemoCu03NextPageFlg());
        c.put(185, 1, d.getCdemoCu03UsrSelFlg());
        c.put(186, 8, d.getCdemoCu03UsrSelected());
        return c;
    }

    private static CarddemoCommarea9 dtoOf(Comm c) {
        CarddemoCommarea9 d = new CarddemoCommarea9();
        d.setCdemoFromTranid(c.get(0, 4));
        d.setCdemoFromProgram(c.get(4, 8));
        d.setCdemoToTranid(c.get(12, 4));
        d.setCdemoToProgram(c.get(16, 8));
        d.setCdemoUserId(c.get(24, 8));
        d.setCdemoUserType(c.get(32, 1));
        d.setCdemoPgmContext(CobolRecords.toInteger(num(c.get(33, 1))));
        d.setCdemoCustId(CobolRecords.toInteger(num(c.get(34, 9))));
        d.setCdemoCustFname(c.get(43, 25));
        d.setCdemoCustMname(c.get(68, 25));
        d.setCdemoCustLname(c.get(93, 25));
        d.setCdemoAcctId(CobolRecords.toLong(num(c.get(118, 11))));
        d.setCdemoAcctStatus(c.get(129, 1));
        d.setCdemoCardNum(CobolRecords.toLong(num(c.get(130, 16))));
        d.setCdemoLastMap(c.get(146, 7));
        d.setCdemoLastMapset(c.get(153, 7));
        d.setCdemoCu03UsridFirst(c.get(160, 8));
        d.setCdemoCu03UsridLast(c.get(168, 8));
        d.setCdemoCu03PageNum(CobolRecords.toInteger(num(c.get(176, 8))));
        d.setCdemoCu03NextPageFlg(c.get(184, 1));
        d.setCdemoCu03UsrSelFlg(c.get(185, 1));
        d.setCdemoCu03UsrSelected(c.get(186, 8));
        return d;
    }

    /** CARDDEMO-COMMAREA before any MOVE: alphanumerics spaces, numerics zero, NEXT-PAGE-FLG VALUE 'N'. */
    private static Comm initialComm() {
        Comm c = new Comm("");
        c.put(33, 1, "0");
        c.put(34, 9, "0".repeat(9));
        c.put(118, 11, "0".repeat(11));
        c.put(130, 16, "0".repeat(16));
        c.put(176, 8, "0".repeat(8));
        c.put(184, 1, "N");
        return c;
    }

    private static Cousr3aScreen filledScreen(String unit) {
        Cousr3aScreen s = new Cousr3aScreen();
        s.setTrnname(unit.repeat(4));
        s.setTitle01(unit.repeat(40));
        s.setCurdate(unit.repeat(8));
        s.setPgmname(unit.repeat(8));
        s.setTitle02(unit.repeat(40));
        s.setCurtime(unit.repeat(8));
        s.setUsridin(unit.repeat(8));
        s.setFname(unit.repeat(20));
        s.setLname(unit.repeat(20));
        s.setUsrtype(unit);
        s.setErrmsg(unit.repeat(78));
        return s;
    }

    private static Cousr3aScreen copy(Cousr3aScreen o) {
        Cousr3aScreen s = new Cousr3aScreen();
        s.setTrnname(o.getTrnname());
        s.setTitle01(o.getTitle01());
        s.setCurdate(o.getCurdate());
        s.setPgmname(o.getPgmname());
        s.setTitle02(o.getTitle02());
        s.setCurtime(o.getCurtime());
        s.setUsridin(o.getUsridin());
        s.setFname(o.getFname());
        s.setLname(o.getLname());
        s.setUsrtype(o.getUsrtype());
        s.setErrmsg(o.getErrmsg());
        return s;
    }

    private static SecUserData blankUser() {
        SecUserData u = new SecUserData();
        u.setSecUsrId(fit("", 8));
        u.setSecUsrFname(fit("", 20));
        u.setSecUsrLname(fit("", 20));
        u.setSecUsrPwd(fit("", 8));
        u.setSecUsrType(fit("", 1));
        u.setSecUsrFiller(fit("", 23));
        return u;
    }

    // ------------------------------------------------------------------ the task

    /** The working storage of one task: COUSR3AI / COUSR3AO (one storage, REDEFINES), CARDDEMO-COMMAREA,
     *  SEC-USER-DATA and WS-VARIABLES. */
    private final class Session {
        private final CicsTask task;
        private Comm comm = initialComm();
        private Cousr3aScreen scr = filledScreen(" ");
        private SecUserData sec = blankUser();
        private String message = fit("", 80);
        private boolean errFlg;
        private boolean cursorUsrid;   // USRIDINL = -1
        private boolean cursorFname;   // FNAMEL = -1
        private int errmsgC;           // ERRMSGC

        Session(CicsTask task) {
            this.task = task;
        }

        /** MAIN-PARA */
        void mainPara() {
            errFlg = false;                     // SET ERR-FLG-OFF (USR-MODIFIED-NO is never read)
            message = fit("", 80);
            scr.setErrmsg(fit("", 78));

            if (!task.hasCommarea()) {          // IF EIBCALEN = 0
                comm.put(16, 8, "COSGN00C");
                returnToPrevScreen();
                if (task.ended()) {
                    return;
                }
            } else {
                comm = loadCommarea();
                if (!"1".equals(comm.get(33, 1))) {     // IF NOT CDEMO-PGM-REENTER
                    comm.put(33, 1, "1");
                    scr = filledScreen("\0");           // MOVE LOW-VALUES TO COUSR3AO
                    errmsgC = 0;
                    cursorUsrid = false;
                    cursorFname = false;
                    cursorUsrid = true;                 // MOVE -1 TO USRIDINL
                    String selected = comm.get(186, 8);
                    if (!isBlankOrLow(selected)) {
                        scr.setUsridin(fit(selected, 8));
                        processEnterKey();
                    }
                    sendUsrdelScreen();
                } else {
                    receiveUsrdelScreen();
                    switch (task.aid()) {
                        case "ENTER":
                            processEnterKey();
                            break;
                        case "PF3": {
                            String from = comm.get(4, 8);
                            if (isBlankOrLow(from)) {
                                comm.put(16, 8, "COADM01C");
                            } else {
                                comm.put(16, 8, from);
                            }
                            returnToPrevScreen();
                            if (task.ended()) {
                                return;
                            }
                            break;
                        }
                        case "PF4":
                            clearCurrentScreen();
                            break;
                        case "PF5":
                            deleteUserInfo();
                            break;
                        case "PF12":
                            comm.put(16, 8, "COADM01C");
                            returnToPrevScreen();
                            if (task.ended()) {
                                return;
                            }
                            break;
                        default:
                            errFlg = true;
                            message = fit(CCDA_MSG_INVALID_KEY, 80);
                            sendUsrdelScreen();
                            break;
                    }
                }
            }
            // EXEC CICS RETURN TRANSID(WS-TRANID) COMMAREA(CARDDEMO-COMMAREA)
            task.returnTransid(TRANID, dtoOf(comm));
        }

        /** MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA: a byte move, padded with spaces on the right. */
        private Comm loadCommarea() {
            Object raw = task.commarea(Object.class);
            String image;
            if (raw instanceof CarddemoCommarea9 d9) {
                image = imageOf(d9).b.toString();
            } else {
                CarddemoCommarea d = (CarddemoCommarea) raw;
                CarddemoCommarea9 d9 = new CarddemoCommarea9();
                d9.setCdemoFromTranid(d.getCdemoFromTranid());
                d9.setCdemoFromProgram(d.getCdemoFromProgram());
                d9.setCdemoToTranid(d.getCdemoToTranid());
                d9.setCdemoToProgram(d.getCdemoToProgram());
                d9.setCdemoUserId(d.getCdemoUserId());
                d9.setCdemoUserType(d.getCdemoUserType());
                d9.setCdemoPgmContext(d.getCdemoPgmContext());
                d9.setCdemoCustId(d.getCdemoCustId());
                d9.setCdemoCustFname(d.getCdemoCustFname());
                d9.setCdemoCustMname(d.getCdemoCustMname());
                d9.setCdemoCustLname(d.getCdemoCustLname());
                d9.setCdemoAcctId(d.getCdemoAcctId());
                d9.setCdemoAcctStatus(d.getCdemoAcctStatus());
                d9.setCdemoCardNum(d.getCdemoCardNum());
                d9.setCdemoLastMap(d.getCdemoLastMap());
                d9.setCdemoLastMapset(d.getCdemoLastMapset());
                image = imageOf(d9).b.substring(0, 160);
            }
            Integer len = task.eibcalen();
            int n = len == null ? image.length() : Math.min(len, image.length());
            return new Comm(image.substring(0, Math.max(n, 0)));
        }

        /** PROCESS-ENTER-KEY */
        void processEnterKey() {
            if (isBlankOrLow(scr.getUsridin())) {
                errFlg = true;
                message = fit("User ID can NOT be empty...", 80);
                cursorUsrid = true;
                sendUsrdelScreen();
            } else {
                cursorUsrid = true;
            }

            if (!errFlg) {
                scr.setFname(fit("", 20));
                scr.setLname(fit("", 20));
                scr.setUsrtype(fit("", 1));
                sec.setSecUsrId(fit(scr.getUsridin(), 8));
                readUserSecFile();
            }

            if (!errFlg) {
                scr.setFname(fit(sec.getSecUsrFname(), 20));
                scr.setLname(fit(sec.getSecUsrLname(), 20));
                scr.setUsrtype(fit(sec.getSecUsrType(), 1));
                sendUsrdelScreen();
            }
        }

        /** DELETE-USER-INFO */
        void deleteUserInfo() {
            if (isBlankOrLow(scr.getUsridin())) {
                errFlg = true;
                message = fit("User ID can NOT be empty...", 80);
                cursorUsrid = true;
                sendUsrdelScreen();
            } else {
                cursorUsrid = true;
            }

            if (!errFlg) {
                sec.setSecUsrId(fit(scr.getUsridin(), 8));
                readUserSecFile();
                // DEFECT kept: the DELETE runs even when the READ just failed (WS-ERR-FLG on); it then finds no
                // held record (INVREQ) and shows 'Unable to Update User...'. Fix: PERFORM it only IF NOT ERR-FLG-ON.
                deleteUserSecFile();
            }
        }

        /** RETURN-TO-PREV-SCREEN */
        void returnToPrevScreen() {
            if (isBlankOrLow(comm.get(16, 8))) {
                comm.put(16, 8, "COSGN00C");
            }
            comm.put(0, 4, TRANID);
            comm.put(4, 8, PGMNAME);
            comm.put(33, 1, "0");
            String resp = task.xctl(comm.get(16, 8).stripTrailing(), dtoOf(comm));
            if (!"NORMAL".equals(resp)) {
                // no RESP clause: the condition takes CICS's default action
                task.abendOnCondition(resp);
            }
        }

        /** SEND-USRDEL-SCREEN */
        void sendUsrdelScreen() {
            populateHeaderInfo();
            scr.setErrmsg(fit(message, 78));
            CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
            if (cursorUsrid) {
                sub.cursor("USRIDIN");
            }
            if (cursorFname) {
                sub.cursor("FNAME");
            }
            if (errmsgC != 0) {
                sub.color("ERRMSG", errmsgC);
            }
            // a copy: the task keeps the event, and the storage goes on changing
            task.sendMap("COUSR3A", "COUSR03", copy(scr), sub, "ERASE", "CURSOR");
        }

        /** RECEIVE-USRDEL-SCREEN: RESP is stored but never tested (a MAPFAIL leaves the storage as it was). */
        void receiveUsrdelScreen() {
            Optional<Cousr3aScreen> in = task.receive("COUSR3A", "COUSR03", Cousr3aScreen.class);
            in.ifPresent(x -> {
                if (x.getTrnname() != null) scr.setTrnname(fit(x.getTrnname(), 4));
                if (x.getTitle01() != null) scr.setTitle01(fit(x.getTitle01(), 40));
                if (x.getCurdate() != null) scr.setCurdate(fit(x.getCurdate(), 8));
                if (x.getPgmname() != null) scr.setPgmname(fit(x.getPgmname(), 8));
                if (x.getTitle02() != null) scr.setTitle02(fit(x.getTitle02(), 40));
                if (x.getCurtime() != null) scr.setCurtime(fit(x.getCurtime(), 8));
                if (x.getUsridin() != null) scr.setUsridin(fit(x.getUsridin(), 8));
                if (x.getFname() != null) scr.setFname(fit(x.getFname(), 20));
                if (x.getLname() != null) scr.setLname(fit(x.getLname(), 20));
                if (x.getUsrtype() != null) scr.setUsrtype(fit(x.getUsrtype(), 1));
                if (x.getErrmsg() != null) scr.setErrmsg(fit(x.getErrmsg(), 78));
            });
        }

        /** POPULATE-HEADER-INFO */
        void populateHeaderInfo() {
            LocalDateTime now = task.now();     // FUNCTION CURRENT-DATE
            scr.setTitle01(fit(CCDA_TITLE01, 40));
            scr.setTitle02(fit(CCDA_TITLE02, 40));
            scr.setTrnname(fit(TRANID, 4));
            scr.setPgmname(fit(PGMNAME, 8));
            scr.setCurdate(String.format(Locale.ROOT, "%02d/%02d/%02d",
                    now.getMonthValue(), now.getDayOfMonth(), now.getYear() % 100));
            scr.setCurtime(String.format(Locale.ROOT, "%02d:%02d:%02d",
                    now.getHour(), now.getMinute(), now.getSecond()));
        }

        /** READ-USER-SEC-FILE */
        void readUserSecFile() {
            String key = sec.getSecUsrId();
            CicsTask.FileRead<SecUserData> r = task.readForUpdate(USRSEC, () -> readUsrsec(key));
            if (r.normal()) {
                // READ INTO: the program's own copy of the record
                Charset cs = CobolRecords.charset();
                sec = SecUserData.fromRecord(r.record().toRecord(cs), cs);
            }
            switch (r.resp()) {
                case 0:
                    message = fit("Press PF5 key to delete this user ...", 80);
                    errmsgC = DFHNEUTR;
                    sendUsrdelScreen();
                    break;
                case 13:
                    errFlg = true;
                    message = fit("User ID NOT found...", 80);
                    cursorUsrid = true;
                    sendUsrdelScreen();
                    break;
                default:
                    displayResp(r.resp(), r.resp2());
                    errFlg = true;
                    message = fit("Unable to lookup User...", 80);
                    cursorFname = true;
                    sendUsrdelScreen();
                    break;
            }
        }

        /** DELETE-USER-SEC-FILE */
        void deleteUserSecFile() {
            String key = sec.getSecUsrId();
            // DELETE without RIDFLD: the record the READ UPDATE holds (INVREQ when none).
            // RESP2 is not exposed by deleteHeld: REAS in the DISPLAY below is 0.
            int resp = task.deleteHeld(USRSEC, () -> deleteUsrsec(key));
            switch (resp) {
                case 0: {
                    initializeAllFields();
                    message = fit("", 80);
                    errmsgC = DFHGREEN;
                    String id = sec.getSecUsrId();
                    int sp = id.indexOf(' ');
                    String shown = sp < 0 ? id : id.substring(0, sp);   // DELIMITED BY SPACE
                    message = fit("User " + shown + " has been deleted ...", 80);
                    sendUsrdelScreen();
                    break;
                }
                case 13:
                    errFlg = true;
                    message = fit("User ID NOT found...", 80);
                    cursorUsrid = true;
                    sendUsrdelScreen();
                    break;
                default:
                    displayResp(resp, 0);
                    errFlg = true;
                    message = fit("Unable to Update User...", 80);
                    cursorFname = true;
                    sendUsrdelScreen();
                    break;
            }
        }

        /** CLEAR-CURRENT-SCREEN */
        void clearCurrentScreen() {
            initializeAllFields();
            sendUsrdelScreen();
        }

        /** INITIALIZE-ALL-FIELDS */
        void initializeAllFields() {
            cursorUsrid = true;
            scr.setUsridin(fit("", 8));
            scr.setFname(fit("", 20));
            scr.setLname(fit("", 20));
            scr.setUsrtype(fit("", 1));
            message = fit("", 80);
        }

        private void displayResp(int resp, int reas) {
            Sysout.display("RESP:", Sysout.number(BigDecimal.valueOf(resp), 9, 0, true),
                    "REAS:", Sysout.number(BigDecimal.valueOf(reas), 9, 0, true));
        }
    }

}
