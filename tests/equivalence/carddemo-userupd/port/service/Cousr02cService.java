package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.Cousr02cCarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Cousr2aScreen;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.SecUserData;
import com.gitgalaxy.modernized.repository.vsam.SecUserDataRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.HashSet;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * READ at line 322 tests NORMAL,NOTFND
 * REWRITE at line 360 tests NORMAL,NOTFND
 * The RESP of RECEIVE at line 285 (paragraph RECEIVE-USRUPD-SCREEN) is never tested by the program.
 * Screens (#3619): Cousr2aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Cousr02cService {

    private static final Logger log = LoggerFactory.getLogger(Cousr02cService.class);

    private static final String WS_PGMNAME = "COUSR02C";
    private static final String WS_TRANID = "CU02";
    private static final String USRSEC = "USRSEC";
    private static final String TITLE01 = "      AWS Mainframe Modernization       ";
    private static final String TITLE02 = "              CardDemo                  ";
    private static final String MSG_INVALID_KEY = "Invalid key pressed. Please see below...";

    private static final int DFHRED = 0xF2;
    private static final int DFHGREEN = 0xF4;
    private static final int DFHNEUTR = 0xF7;

    /** Screen order of the fields whose length can hold -1 (cursor request). */
    private static final String[] CURSOR_ORDER = {"USRIDIN", "FNAME", "LNAME", "PASSWD", "USRTYPE"};

    private final SecUserDataRepository secUserDataRepository;

    /** A CICS transaction entered the program (#4343): one task of it in the region (CicsTask.region()),
     *  ENTER pressed -- `request` its COMMAREA, null when started from a cleared screen -- run through runTask. Returns the COMMAREA its RETURN passes on (null: none). */
    public Cousr02cCarddemoCommarea handleTransaction(String transid, Cousr02cCarddemoCommarea request) {
        log.info("Cousr02c: handleTransaction");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "COUSR02C", this::runTask);
        return task.returned(Cousr02cCarddemoCommarea.class);
    }

    /** Working storage of one task (a task starts with fresh storage). */
    private static final class Ws {
        boolean err;                 // WS-ERR-FLG
        boolean modified;            // WS-USR-MODIFIED
        String message = spaces(80); // WS-MESSAGE
        int respCd;                  // WS-RESP-CD
        int reasCd;                  // WS-REAS-CD
        Cousr02cCarddemoCommarea ca; // CARDDEMO-COMMAREA
        // COUSR2AI / COUSR2AO share storage: one value per field
        String usridin = spaces(8);
        String fname = spaces(20);
        String lname = spaces(20);
        String passwd = spaces(8);
        String usrtype = spaces(1);
        String trnname = spaces(4);
        String pgmname = spaces(8);
        String title01 = spaces(40);
        String title02 = spaces(40);
        String curdate = spaces(8);
        String curtime = spaces(8);
        String errmsg = spaces(78);
        Integer errmsgColor;         // ERRMSGC, null while never set
        final Set<String> cursor = new HashSet<>(); // fields whose L holds -1
        SecUserData sec = blankSec(); // SEC-USER-DATA
    }

    /** One pseudo-conversational task of this program (#3754). */
    public void runTask(CicsTask task) {
        Ws w = new Ws();

        // MAIN-PARA
        w.err = false;
        w.modified = false;
        w.message = spaces(80);
        w.errmsg = spaces(78);

        if (!task.hasCommarea() || (task.eibcalen() != null && task.eibcalen() == 0)) {
            w.ca = blankCommarea();
            w.ca.setCdemoToProgram("COSGN00C");
            returnToPrevScreen(w, task);
            return;
        }
        w.ca = loadCommarea(task);
        if (!(w.ca.getCdemoPgmContext() != null && w.ca.getCdemoPgmContext() == 1)) {
            w.ca.setCdemoPgmContext(1);
            w.usridin = low(8);
            w.fname = low(20);
            w.lname = low(20);
            w.passwd = low(8);
            w.usrtype = low(1);
            w.trnname = low(4);
            w.pgmname = low(8);
            w.title01 = low(40);
            w.title02 = low(40);
            w.curdate = low(8);
            w.curtime = low(8);
            w.errmsg = low(78);
            w.errmsgColor = null;
            w.cursor.clear();
            w.cursor.add("USRIDIN");
            String selected = fit(w.ca.getCdemoCu02UsrSelected(), 8);
            if (!blankOrLow(selected, 8)) {
                w.usridin = selected;
                processEnterKey(w, task);
            }
            sendUsrupdScreen(w, task);
        } else {
            receiveUsrupdScreen(w, task);
            String aid = task.aid() == null ? "" : task.aid();
            switch (aid) {
                case "ENTER":
                    processEnterKey(w, task);
                    break;
                case "PF3":
                    updateUserInfo(w, task);
                    if (blankOrLow(fit(w.ca.getCdemoFromProgram(), 8), 8)) {
                        w.ca.setCdemoToProgram("COADM01C");
                    } else {
                        w.ca.setCdemoToProgram(w.ca.getCdemoFromProgram());
                    }
                    returnToPrevScreen(w, task);
                    return;
                case "PF4":
                    clearCurrentScreen(w, task);
                    break;
                case "PF5":
                    updateUserInfo(w, task);
                    break;
                case "PF12":
                    w.ca.setCdemoToProgram("COADM01C");
                    returnToPrevScreen(w, task);
                    return;
                default:
                    w.err = true;
                    w.message = fit(MSG_INVALID_KEY, 80);
                    sendUsrupdScreen(w, task);
                    break;
            }
        }

        // EXEC CICS RETURN TRANSID(WS-TRANID) COMMAREA(CARDDEMO-COMMAREA)
        task.returnTransid(WS_TRANID, w.ca);
    }

    /** PROCESS-ENTER-KEY */
    private void processEnterKey(Ws w, CicsTask task) {
        if (blankOrLow(w.usridin, 8)) {
            w.err = true;
            w.message = fit("User ID can NOT be empty...", 80);
            w.cursor.add("USRIDIN");
            sendUsrupdScreen(w, task);
        } else {
            w.cursor.add("USRIDIN");
        }

        if (!w.err) {
            w.fname = spaces(20);
            w.lname = spaces(20);
            w.passwd = spaces(8);
            w.usrtype = spaces(1);
            w.sec.setSecUsrId(fit(w.usridin, 8));
            readUserSecFile(w, task);
        }

        if (!w.err) {
            w.fname = fit(w.sec.getSecUsrFname(), 20);
            w.lname = fit(w.sec.getSecUsrLname(), 20);
            w.passwd = fit(w.sec.getSecUsrPwd(), 8);
            w.usrtype = fit(w.sec.getSecUsrType(), 1);
            sendUsrupdScreen(w, task);
        }
    }

    /** UPDATE-USER-INFO */
    private void updateUserInfo(Ws w, CicsTask task) {
        if (blankOrLow(w.usridin, 8)) {
            w.err = true;
            w.message = fit("User ID can NOT be empty...", 80);
            w.cursor.add("USRIDIN");
            sendUsrupdScreen(w, task);
        } else if (blankOrLow(w.fname, 20)) {
            w.err = true;
            w.message = fit("First Name can NOT be empty...", 80);
            w.cursor.add("FNAME");
            sendUsrupdScreen(w, task);
        } else if (blankOrLow(w.lname, 20)) {
            w.err = true;
            w.message = fit("Last Name can NOT be empty...", 80);
            w.cursor.add("LNAME");
            sendUsrupdScreen(w, task);
        } else if (blankOrLow(w.passwd, 8)) {
            w.err = true;
            w.message = fit("Password can NOT be empty...", 80);
            w.cursor.add("PASSWD");
            sendUsrupdScreen(w, task);
        } else if (blankOrLow(w.usrtype, 1)) {
            w.err = true;
            w.message = fit("User Type can NOT be empty...", 80);
            w.cursor.add("USRTYPE");
            sendUsrupdScreen(w, task);
        } else {
            w.cursor.add("FNAME");
        }

        if (!w.err) {
            w.sec.setSecUsrId(fit(w.usridin, 8));
            // Defect kept: the program does not test WS-ERR-FLG after this READ, so the compare / REWRITE
            // below run even after NOTFND (the REWRITE then fails INVREQ). Fix: IF NOT ERR-FLG-ON around them.
            readUserSecFile(w, task);

            if (!CobolCompare.eq(w.fname, w.sec.getSecUsrFname())) {
                w.sec.setSecUsrFname(w.fname);
                w.modified = true;
            }
            if (!CobolCompare.eq(w.lname, w.sec.getSecUsrLname())) {
                w.sec.setSecUsrLname(w.lname);
                w.modified = true;
            }
            if (!CobolCompare.eq(w.passwd, w.sec.getSecUsrPwd())) {
                w.sec.setSecUsrPwd(w.passwd);
                w.modified = true;
            }
            if (!CobolCompare.eq(w.usrtype, w.sec.getSecUsrType())) {
                w.sec.setSecUsrType(w.usrtype);
                w.modified = true;
            }

            if (w.modified) {
                updateUserSecFile(w, task);
            } else {
                w.message = fit("Please modify to update ...", 80);
                w.errmsgColor = DFHRED;
                sendUsrupdScreen(w, task);
            }
        }
    }

    /** RETURN-TO-PREV-SCREEN: the XCTL ends the task. */
    private void returnToPrevScreen(Ws w, CicsTask task) {
        if (blankOrLow(fit(w.ca.getCdemoToProgram(), 8), 8)) {
            w.ca.setCdemoToProgram("COSGN00C");
        }
        w.ca.setCdemoFromTranid(WS_TRANID);
        w.ca.setCdemoFromProgram(WS_PGMNAME);
        w.ca.setCdemoPgmContext(0);
        String resp = dispatchCdemoToProgramL258(task, fit(w.ca.getCdemoToProgram(), 8), w.ca);   // line 258
        if (!"NORMAL".equals(resp)) {
            // no RESP clause: the unhandled condition takes CICS's default action
            task.abendOnCondition(resp);
        }
    }

    /** SEND-USRUPD-SCREEN */
    private void sendUsrupdScreen(Ws w, CicsTask task) {
        populateHeaderInfo(w, task);
        w.errmsg = fit(w.message, 78);

        Cousr2aScreen s = new Cousr2aScreen();
        s.setTrnname(w.trnname);
        s.setTitle01(w.title01);
        s.setCurdate(w.curdate);
        s.setPgmname(w.pgmname);
        s.setTitle02(w.title02);
        s.setCurtime(w.curtime);
        s.setUsridin(w.usridin);
        s.setFname(w.fname);
        s.setLname(w.lname);
        s.setPasswd(w.passwd);
        s.setUsrtype(w.usrtype);
        s.setErrmsg(w.errmsg);

        CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
        if (w.errmsgColor != null) {
            sub.color("ERRMSG", w.errmsgColor);
        }
        for (String f : CURSOR_ORDER) {
            if (w.cursor.contains(f)) {
                sub.cursor(f);
            }
        }
        task.sendMap(Cousr2aScreen.MAP, Cousr2aScreen.MAPSET, s, sub, "ERASE", "CURSOR");
    }

    /** RECEIVE-USRUPD-SCREEN */
    private void receiveUsrupdScreen(Ws w, CicsTask task) {
        Optional<Cousr2aScreen> in = task.receive(Cousr2aScreen.MAP, Cousr2aScreen.MAPSET, Cousr2aScreen.class);
        // RESP is stored but never tested by the program (kept: MAPFAIL leaves the input area as it was).
        w.respCd = in.isPresent() ? 0 : 36;
        w.reasCd = 0;
        w.cursor.clear(); // the length fields now hold what was received
        if (in.isPresent()) {
            Cousr2aScreen s = in.get();
            w.usridin = fit(s.getUsridin(), 8);
            w.fname = fit(s.getFname(), 20);
            w.lname = fit(s.getLname(), 20);
            w.passwd = fit(s.getPasswd(), 8);
            w.usrtype = fit(s.getUsrtype(), 1);
        }
    }

    /** POPULATE-HEADER-INFO */
    private void populateHeaderInfo(Ws w, CicsTask task) {
        LocalDateTime now = task.now();
        w.title01 = fit(TITLE01, 40);
        w.title02 = fit(TITLE02, 40);
        w.trnname = fit(WS_TRANID, 4);
        w.pgmname = fit(WS_PGMNAME, 8);
        w.curdate = String.format(Locale.ROOT, "%02d/%02d/%02d", now.getMonthValue(), now.getDayOfMonth(),
                now.getYear() % 100);
        w.curtime = String.format(Locale.ROOT, "%02d:%02d:%02d", now.getHour(), now.getMinute(), now.getSecond());
    }

    /** READ-USER-SEC-FILE */
    private void readUserSecFile(Ws w, CicsTask task) {
        String key = fit(w.sec.getSecUsrId(), 8);
        CicsTask.FileRead<SecUserData> r = task.readForUpdate(USRSEC, () -> readUsrsec(key));
        w.respCd = r.resp();
        w.reasCd = r.resp2();
        if (r.normal()) {
            // INTO SEC-USER-DATA: the program's own copy, never the managed entity
            java.nio.charset.Charset cs = CobolRecords.charset();
            w.sec = SecUserData.fromRecord(r.record().toRecord(cs), cs);
        }
        if (w.respCd == 0) {
            w.message = fit("Press PF5 key to save your updates ...", 80);
            w.errmsgColor = DFHNEUTR;
            sendUsrupdScreen(w, task);
        } else if (w.respCd == 13) {
            w.err = true;
            w.message = fit("User ID NOT found...", 80);
            w.cursor.add("USRIDIN");
            sendUsrupdScreen(w, task);
        } else {
            displayResp(w);
            w.err = true;
            w.message = fit("Unable to lookup User...", 80);
            w.cursor.add("FNAME");
            sendUsrupdScreen(w, task);
        }
    }

    /** UPDATE-USER-SEC-FILE */
    private void updateUserSecFile(Ws w, CicsTask task) {
        SecUserData toSave = w.sec;
        w.respCd = task.rewrite(USRSEC, () -> rewriteUsrsec(toSave));
        // TODO: CicsTask.rewrite does not expose RESP2; WS-REAS-CD is taken as 0.
        w.reasCd = 0;
        if (w.respCd == 0) {
            w.message = spaces(80);
            w.errmsgColor = DFHGREEN;
            String id = fit(w.sec.getSecUsrId(), 8);
            int sp = id.indexOf(' ');
            String shown = sp < 0 ? id : id.substring(0, sp); // DELIMITED BY SPACE
            w.message = fit("User " + shown + " has been updated ...", 80);
            sendUsrupdScreen(w, task);
        } else if (w.respCd == 13) {
            w.err = true;
            w.message = fit("User ID NOT found...", 80);
            w.cursor.add("USRIDIN");
            sendUsrupdScreen(w, task);
        } else {
            displayResp(w);
            w.err = true;
            w.message = fit("Unable to Update User...", 80);
            w.cursor.add("FNAME");
            sendUsrupdScreen(w, task);
        }
    }

    /** CLEAR-CURRENT-SCREEN */
    private void clearCurrentScreen(Ws w, CicsTask task) {
        initializeAllFields(w);
        sendUsrupdScreen(w, task);
    }

    /** INITIALIZE-ALL-FIELDS */
    private void initializeAllFields(Ws w) {
        w.cursor.add("USRIDIN");
        w.usridin = spaces(8);
        w.fname = spaces(20);
        w.lname = spaces(20);
        w.passwd = spaces(8);
        w.usrtype = spaces(1);
        w.message = spaces(80);
    }

    private static void displayResp(Ws w) {
        Sysout.display("RESP:", Sysout.number(BigDecimal.valueOf(w.respCd), 9, 0, true),
                "REAS:", Sysout.number(BigDecimal.valueOf(w.reasCd), 9, 0, true));
    }

    // ---- helpers: COBOL storage ------------------------------------------------------------

    private static String spaces(int n) {
        return " ".repeat(n);
    }

    private static String low(int n) {
        return "\u0000".repeat(n);
    }

    /** MOVE to PIC X(n): pad with spaces or truncate on the right. */
    private static String fit(String v, int n) {
        return CobolRecords.fit(v, n, CobolRecords.charset());
    }

    /** `x = SPACES OR LOW-VALUES` for a PIC X(n) item. */
    private static boolean blankOrLow(String v, int n) {
        String f = fit(v, n);
        return CobolCompare.eq(f, "") || CobolCompare.eq(f, CobolCompare.lowValues(n));
    }

    private static SecUserData blankSec() {
        java.nio.charset.Charset cs = CobolRecords.charset();
        return SecUserData.fromRecord(CobolRecords.blank(80, cs), cs);
    }

    /** CARDDEMO-COMMAREA in a fresh working storage: spaces, zeros, NEXT-PAGE-FLG 'N'. */
    private static Cousr02cCarddemoCommarea blankCommarea() {
        Cousr02cCarddemoCommarea c = new Cousr02cCarddemoCommarea();
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

    /** MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA: a copy; bytes past EIBCALEN keep their initial value. */
    private static Cousr02cCarddemoCommarea loadCommarea(CicsTask task) {
        Object in = task.commarea(Object.class);
        Cousr02cCarddemoCommarea c = blankCommarea();
        int len = task.eibcalen() == null ? Integer.MAX_VALUE : task.eibcalen();
        if (in instanceof Cousr02cCarddemoCommarea s) {
            c.setCdemoFromTranid(s.getCdemoFromTranid());
            c.setCdemoFromProgram(s.getCdemoFromProgram());
            c.setCdemoToTranid(s.getCdemoToTranid());
            c.setCdemoToProgram(s.getCdemoToProgram());
            c.setCdemoUserId(s.getCdemoUserId());
            c.setCdemoUserType(s.getCdemoUserType());
            c.setCdemoPgmContext(s.getCdemoPgmContext());
            c.setCdemoCustId(s.getCdemoCustId());
            c.setCdemoCustFname(s.getCdemoCustFname());
            c.setCdemoCustMname(s.getCdemoCustMname());
            c.setCdemoCustLname(s.getCdemoCustLname());
            c.setCdemoAcctId(s.getCdemoAcctId());
            c.setCdemoAcctStatus(s.getCdemoAcctStatus());
            c.setCdemoCardNum(s.getCdemoCardNum());
            c.setCdemoLastMap(s.getCdemoLastMap());
            c.setCdemoLastMapset(s.getCdemoLastMapset());
            if (len > 160) {
                c.setCdemoCu02UsridFirst(s.getCdemoCu02UsridFirst());
            }
            if (len > 168) {
                c.setCdemoCu02UsridLast(s.getCdemoCu02UsridLast());
            }
            if (len > 176) {
                c.setCdemoCu02PageNum(s.getCdemoCu02PageNum());
            }
            if (len > 184) {
                c.setCdemoCu02NextPageFlg(s.getCdemoCu02NextPageFlg());
            }
            if (len > 185) {
                c.setCdemoCu02UsrSelFlg(s.getCdemoCu02UsrSelFlg());
            }
            if (len > 186) {
                c.setCdemoCu02UsrSelected(s.getCdemoCu02UsrSelected());
            }
        } else if (in instanceof CarddemoCommarea s) {
            c.setCdemoFromTranid(s.getCdemoFromTranid());
            c.setCdemoFromProgram(s.getCdemoFromProgram());
            c.setCdemoToTranid(s.getCdemoToTranid());
            c.setCdemoToProgram(s.getCdemoToProgram());
            c.setCdemoUserId(s.getCdemoUserId());
            c.setCdemoUserType(s.getCdemoUserType());
            c.setCdemoPgmContext(s.getCdemoPgmContext());
            c.setCdemoCustId(s.getCdemoCustId());
            c.setCdemoCustFname(s.getCdemoCustFname());
            c.setCdemoCustMname(s.getCdemoCustMname());
            c.setCdemoCustLname(s.getCdemoCustLname());
            c.setCdemoAcctId(s.getCdemoAcctId());
            c.setCdemoAcctStatus(s.getCdemoAcctStatus());
            c.setCdemoCardNum(s.getCdemoCardNum());
            c.setCdemoLastMap(s.getCdemoLastMap());
            c.setCdemoLastMapset(s.getCdemoLastMapset());
        }
        return c;
    }

    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region
     *  (CicsTask.region()), run through runTask on `request`, passed by reference -- what it changes, the caller sees. */
    public Cousr02cCarddemoCommarea handleLink(Cousr02cCarddemoCommarea request) {
        log.info("Cousr02c: handleLink");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("COUSR02C", request);
        region.run(task, "COUSR02C", this::runTask);
        return request;
    }

    /** EXEC CICS XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COUSR02C.cbl:258, COMMAREA(CARDDEMO-COMMAREA): the target is data-driven (candidates the engine found: COADM01C (moves), COSGN00C (moves)).
     *  Also MOVEd from CDEMO-FROM-PROGRAM, whose content is not known statically.
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchCdemoToProgramL258(CicsTask task, String program, Object commarea) {
        return task.xctl(program.stripTrailing(), commarea);
    }

    /** AWS.M2.CARDDEMO.USRSEC.VSAM.KSDS as CICS file USRSEC at app/cbl/COUSR02C.cbl:322, 360; VSAM defines field testing: open (3 public / 0 private estates). */
    public Optional<SecUserData> readUsrsec(String key) {
        return secUserDataRepository.findById(key);
    }

    public SecUserData rewriteUsrsec(SecUserData record) {
        return secUserDataRepository.save(record);
    }
}
