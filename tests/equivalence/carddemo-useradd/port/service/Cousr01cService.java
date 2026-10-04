package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Cousr1aScreen;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.SecUserData;
import com.gitgalaxy.modernized.repository.vsam.SecUserDataRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * WRITE at line 240 tests DUPKEY,DUPREC,NORMAL
 * TODO: the RESP of RECEIVE at line 203 (paragraph RECEIVE-USRADD-SCREEN) is never tested
 * Screens (#3619): Cousr1aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Cousr01cService {

    private static final Logger log = LoggerFactory.getLogger(Cousr01cService.class);

    private static final String WS_PGMNAME = "COUSR01C";
    private static final String WS_TRANID = "CU01";
    private static final String WS_USRSEC_FILE = "USRSEC";
    private static final int DFHGREEN = 0xF4;

    private static final String CCDA_TITLE01 = "      AWS Mainframe Modernization";
    private static final String CCDA_TITLE02 = "              CardDemo";
    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed. Please see below...";

    private final ObjectProvider<Coadm01cService> coadm01cService;
    private final ObjectProvider<Cosgn00cService> cosgn00cService;
    private final SecUserDataRepository secUserDataRepository;

    /** Working storage of one task: WS-MESSAGE, WS-ERR-FLG, CARDDEMO-COMMAREA, SEC-USER-DATA and the
     *  symbolic map. COUSR1AO REDEFINES COUSR1AI, so one screen object serves as both (the input
     *  fields and the output fields are the same storage); the L subfields set to -1 are kept in sub. */
    private static final class Work {
        String message = pad("", 80);
        boolean errFlg;
        CarddemoCommarea commarea;
        Cousr1aScreen screen = new Cousr1aScreen();
        final CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
        final SecUserData secUser = new SecUserData();
    }

    public void executeCousr01c(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for COUSR01C");
        // The business logic of COUSR01C is a CICS task: see runTask.
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea handleTransaction(String transid, CarddemoCommarea request) {
        log.info("Cousr01c: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of this program (#3754): MAIN-PARA. */
    public void runTask(CicsTask task) {
        Work w = new Work();

        // MAIN-PARA: SET ERR-FLG-OFF TO TRUE; MOVE SPACES TO WS-MESSAGE ERRMSGO
        w.errFlg = false;
        w.message = pad("", 80);
        w.screen.setErrmsg(pad("", 78));

        if (!task.hasCommarea() || (task.eibcalen() != null && task.eibcalen() == 0)) {
            // IF EIBCALEN = 0
            w.commarea = blankCommarea();
            w.commarea.setCdemoToProgram(pad("COSGN00C", 8));
            returnToPrevScreen(task, w);
            return;
        }

        // MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA
        // (copied whole; a COMMAREA shorter than 160 bytes would leave the tail at its initial value)
        w.commarea = copyOf(task.commarea(CarddemoCommarea.class));

        if (w.commarea.getCdemoPgmContext() == null || w.commarea.getCdemoPgmContext() != 1) {
            // IF NOT CDEMO-PGM-REENTER
            w.commarea.setCdemoPgmContext(1);
            lowValuesToScreen(w.screen);
            w.sub.cursor("FNAME");
            sendUsraddScreen(task, w);
        } else {
            receiveUsraddScreen(task, w);
            switch (task.aid() == null ? "" : task.aid()) {
                case "ENTER":
                    processEnterKey(task, w);
                    break;
                case "PF3":
                    w.commarea.setCdemoToProgram(pad("COADM01C", 8));
                    returnToPrevScreen(task, w);
                    return;
                case "PF4":
                    clearCurrentScreen(task, w);
                    break;
                default:
                    w.errFlg = true;
                    w.sub.cursor("FNAME");
                    w.message = pad(CCDA_MSG_INVALID_KEY, 80);
                    sendUsraddScreen(task, w);
                    break;
            }
        }

        // EXEC CICS RETURN TRANSID(WS-TRANID) COMMAREA(CARDDEMO-COMMAREA)
        task.returnTransid(WS_TRANID, w.commarea, null);
    }

    /** PROCESS-ENTER-KEY */
    private void processEnterKey(CicsTask task, Work w) {
        Cousr1aScreen s = w.screen;
        if (blankOrLow(s.getFname(), 20)) {
            w.errFlg = true;
            w.message = pad("First Name can NOT be empty...", 80);
            w.sub.cursor("FNAME");
            sendUsraddScreen(task, w);
        } else if (blankOrLow(s.getLname(), 20)) {
            w.errFlg = true;
            w.message = pad("Last Name can NOT be empty...", 80);
            w.sub.cursor("LNAME");
            sendUsraddScreen(task, w);
        } else if (blankOrLow(s.getUserid(), 8)) {
            w.errFlg = true;
            w.message = pad("User ID can NOT be empty...", 80);
            w.sub.cursor("USERID");
            sendUsraddScreen(task, w);
        } else if (blankOrLow(s.getPasswd(), 8)) {
            w.errFlg = true;
            w.message = pad("Password can NOT be empty...", 80);
            w.sub.cursor("PASSWD");
            sendUsraddScreen(task, w);
        } else if (blankOrLow(s.getUsrtype(), 1)) {
            w.errFlg = true;
            w.message = pad("User Type can NOT be empty...", 80);
            w.sub.cursor("USRTYPE");
            sendUsraddScreen(task, w);
        } else {
            // WHEN OTHER: MOVE -1 TO FNAMEL (the cursor flag stays set on a later error send)
            w.sub.cursor("FNAME");
        }

        if (!w.errFlg) {
            w.secUser.setSecUsrId(pad(s.getUserid(), 8));
            w.secUser.setSecUsrFname(pad(s.getFname(), 20));
            w.secUser.setSecUsrLname(pad(s.getLname(), 20));
            w.secUser.setSecUsrPwd(pad(s.getPasswd(), 8));
            w.secUser.setSecUsrType(pad(s.getUsrtype(), 1));
            w.secUser.setSecUsrFiller(pad("", 23));
            writeUserSecFile(task, w);
        }
    }

    /** RETURN-TO-PREV-SCREEN: the program ends here (XCTL, or the abend of an XCTL that failed). */
    private void returnToPrevScreen(CicsTask task, Work w) {
        CarddemoCommarea c = w.commarea;
        if (CobolCompare.eq(c.getCdemoToProgram(), CobolCompare.lowValues(8))
                || CobolCompare.eq(c.getCdemoToProgram(), " ".repeat(8))) {
            c.setCdemoToProgram(pad("COSGN00C", 8));
        }
        c.setCdemoFromTranid(pad(WS_TRANID, 4));
        c.setCdemoFromProgram(pad(WS_PGMNAME, 8));
        c.setCdemoPgmContext(0);
        String resp = task.xctl(c.getCdemoToProgram().stripTrailing(), c);
        if (!"NORMAL".equals(resp)) {
            // no RESP / HANDLE CONDITION: CICS's default action abends the task
            task.abendOnCondition(resp);
        }
    }

    /** SEND-USRADD-SCREEN */
    private void sendUsraddScreen(CicsTask task, Work w) {
        populateHeaderInfo(task, w);
        w.screen.setErrmsg(pad(w.message, 78));
        task.sendMap("COUSR1A", "COUSR01", w.screen, w.sub, "ERASE", "CURSOR");
    }

    /** RECEIVE-USRADD-SCREEN (RESP / RESP2 are stored but never tested). */
    private void receiveUsraddScreen(CicsTask task, Work w) {
        Optional<Cousr1aScreen> in = task.receive("COUSR1A", "COUSR01", Cousr1aScreen.class);
        Cousr1aScreen s = new Cousr1aScreen();
        Cousr1aScreen r = in.orElse(null);
        // on MAPFAIL the input area keeps its initial content (spaces)
        s.setFname(pad(r == null ? null : r.getFname(), 20));
        s.setLname(pad(r == null ? null : r.getLname(), 20));
        s.setUserid(pad(r == null ? null : r.getUserid(), 8));
        s.setPasswd(pad(r == null ? null : r.getPasswd(), 8));
        s.setUsrtype(pad(r == null ? null : r.getUsrtype(), 1));
        s.setErrmsg(pad(r == null ? null : r.getErrmsg(), 78));
        w.screen = s;
    }

    /** POPULATE-HEADER-INFO */
    private void populateHeaderInfo(CicsTask task, Work w) {
        LocalDateTime now = task.now();   // MOVE FUNCTION CURRENT-DATE TO WS-CURDATE-DATA
        Cousr1aScreen s = w.screen;
        s.setTitle01(pad(CCDA_TITLE01, 40));
        s.setTitle02(pad(CCDA_TITLE02, 40));
        s.setTrnname(pad(WS_TRANID, 4));
        s.setPgmname(pad(WS_PGMNAME, 8));
        s.setCurdate(String.format(Locale.ROOT, "%02d/%02d/%02d", now.getMonthValue(), now.getDayOfMonth(),
                now.getYear() % 100));
        s.setCurtime(String.format(Locale.ROOT, "%02d:%02d:%02d", now.getHour(), now.getMinute(),
                now.getSecond()));
    }

    /** WRITE-USER-SEC-FILE */
    private void writeUserSecFile(CicsTask task, Work w) {
        SecUserData rec = w.secUser;
        String key = rec.getSecUsrId();
        int resp = task.write(WS_USRSEC_FILE, secUserDataRepository.existsById(key),
                () -> writeUsrsec(rec));   // the record is added through the file's WRITE
        switch (resp) {
            case 0: // DFHRESP(NORMAL)
                initializeAllFields(w);
                w.message = pad("", 80);
                w.sub.color("ERRMSG", DFHGREEN);
                int sp = key.indexOf(' ');
                String id = sp < 0 ? key : key.substring(0, sp);   // DELIMITED BY SPACE
                w.message = pad("User " + id + " has been added ...", 80);
                sendUsraddScreen(task, w);
                break;
            case 15: // DFHRESP(DUPKEY)
            case 14: // DFHRESP(DUPREC)
                w.errFlg = true;
                w.message = pad("User ID already exist...", 80);
                w.sub.cursor("USERID");
                sendUsraddScreen(task, w);
                break;
            default:
                w.errFlg = true;
                w.message = pad("Unable to Add User...", 80);
                w.sub.cursor("FNAME");
                sendUsraddScreen(task, w);
                break;
        }
    }

    /** CLEAR-CURRENT-SCREEN */
    private void clearCurrentScreen(CicsTask task, Work w) {
        initializeAllFields(w);
        sendUsraddScreen(task, w);
    }

    /** INITIALIZE-ALL-FIELDS */
    private void initializeAllFields(Work w) {
        w.sub.cursor("FNAME");
        w.screen.setUserid(pad("", 8));
        w.screen.setFname(pad("", 20));
        w.screen.setLname(pad("", 20));
        w.screen.setPasswd(pad("", 8));
        w.screen.setUsrtype(pad("", 1));
        w.message = pad("", 80);
    }

    /** MOVE LOW-VALUES TO COUSR1AO */
    private static void lowValuesToScreen(Cousr1aScreen s) {
        s.setTrnname(low(4));
        s.setTitle01(low(40));
        s.setCurdate(low(8));
        s.setPgmname(low(8));
        s.setTitle02(low(40));
        s.setCurtime(low(8));
        s.setFname(low(20));
        s.setLname(low(20));
        s.setUserid(low(8));
        s.setPasswd(low(8));
        s.setUsrtype(low(1));
        s.setErrmsg(low(78));
    }

    private static boolean blankOrLow(String value, int length) {
        String v = pad(value, length);
        return CobolCompare.eq(v, " ".repeat(length)) || CobolCompare.eq(v, CobolCompare.lowValues(length));
    }

    private static String low(int n) {
        return "\u0000".repeat(n);
    }

    /** MOVE to PIC X(n): space-padded or truncated on the right. */
    private static String pad(String value, int n) {
        return CobolRecords.fit(value, n, CobolRecords.charset());
    }

    private static CarddemoCommarea blankCommarea() {
        return copyOf(new CarddemoCommarea());
    }

    private static CarddemoCommarea copyOf(CarddemoCommarea c) {
        CarddemoCommarea n = new CarddemoCommarea();
        n.setCdemoFromTranid(pad(c.getCdemoFromTranid(), 4));
        n.setCdemoFromProgram(pad(c.getCdemoFromProgram(), 8));
        n.setCdemoToTranid(pad(c.getCdemoToTranid(), 4));
        n.setCdemoToProgram(pad(c.getCdemoToProgram(), 8));
        n.setCdemoUserId(pad(c.getCdemoUserId(), 8));
        n.setCdemoUserType(pad(c.getCdemoUserType(), 1));
        n.setCdemoPgmContext(c.getCdemoPgmContext() == null ? 0 : c.getCdemoPgmContext());
        n.setCdemoCustId(c.getCdemoCustId() == null ? 0 : c.getCdemoCustId());
        n.setCdemoCustFname(pad(c.getCdemoCustFname(), 25));
        n.setCdemoCustMname(pad(c.getCdemoCustMname(), 25));
        n.setCdemoCustLname(pad(c.getCdemoCustLname(), 25));
        n.setCdemoAcctId(c.getCdemoAcctId() == null ? 0L : c.getCdemoAcctId());
        n.setCdemoAcctStatus(pad(c.getCdemoAcctStatus(), 1));
        n.setCdemoCardNum(c.getCdemoCardNum() == null ? 0L : c.getCdemoCardNum());
        n.setCdemoLastMap(pad(c.getCdemoLastMap(), 7));
        n.setCdemoLastMapset(pad(c.getCdemoLastMapset(), 7));
        return n;
    }

    /** Another program LINKed / XCTLed to this one. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea handleLink(CarddemoCommarea request) {
        log.info("Cousr01c: handleLink");
        return request;
    }

    /** XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COUSR01C.cbl:175: the target is data-driven. Candidates: COADM01C (moves), COSGN00C (moves).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCdemoToProgramL175(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COADM01C":
                return coadm01cService.getObject().handleLink((CarddemoCommarea) request);
            case "COSGN00C":
                cosgn00cService.getObject().handleLink();
                return null;
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COUSR01C.cbl:175: no known target " + program);
        }
    }

    /** AWS.M2.CARDDEMO.USRSEC.VSAM.KSDS as CICS file USRSEC at app/cbl/COUSR01C.cbl:240; VSAM defines field testing: open (3 public / 0 private estates). */
    public SecUserData writeUsrsec(SecUserData record) {
        return secUserDataRepository.save(record);
    }

    /** SEND MAP(COUSR1A) MAPSET(COUSR01) FROM(COUSR1AO) at app/cbl/COUSR01C.cbl:190 (#3619).
     *  The screen is filled by runTask (SEND-USRADD-SCREEN / POPULATE-HEADER-INFO).
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public Cousr1aScreen renderCousr1a(Cousr1aScreen screen) {
        return screen;
    }

    /** RECEIVE MAP(COUSR1A) MAPSET(COUSR01) INTO(COUSR1AI) at app/cbl/COUSR01C.cbl:203 (#3619).
     *  The input is processed by runTask (PROCESS-ENTER-KEY).
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public ScreenModel submitCousr1a(Cousr1aScreen input, String aid) {
        return renderCousr1a(input);
    }

}
