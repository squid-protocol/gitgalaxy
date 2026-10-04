package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Coadm1aScreen;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.exception.*;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Locale;
import java.util.Optional;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * The RESP of RECEIVE at line 194 (paragraph RECEIVE-MENU-SCREEN) is never tested by the program.
 * Screens (#3619): Coadm1aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Coadm01cService {

    private static final Logger log = LoggerFactory.getLogger(Coadm01cService.class);

    private static final String PGMNAME = "COADM01C";
    private static final String TRANID = "CA00";
    private static final String MAP = "COADM1A";
    private static final String MAPSET = "COADM01";
    private static final String TITLE01 = "      AWS Mainframe Modernization       ";
    private static final String TITLE02 = "              CardDemo                  ";
    private static final String MSG_INVALID_KEY = "Invalid key pressed. Please see below...         ";
    private static final int DFHGREEN = 0xF4;
    private static final int OPT_COUNT = 6;
    // COADM02Y: CDEMO-ADMIN-OPT-NAME (X(35)) and -PGMNAME of each option; the number is the 1-based index
    private static final String[] OPT_NAME = {
        "User List (Security)", "User Add (Security)", "User Update (Security)",
        "User Delete (Security)", "Transaction Type List/Update (Db2)", "Transaction Type Maintenance (Db2)"};
    private static final String[] OPT_PGM = {
        "COUSR00C", "COUSR01C", "COUSR02C", "COUSR03C", "COTRTLIC", "COTRTUPC"};


    /** The program's working storage for one task. */
    private static final class State {
        CarddemoCommarea ca;
        Coadm1aScreen screen = new Coadm1aScreen();   // COADM1AO (redefines COADM1AI)
        CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
        String message = " ".repeat(80);               // WS-MESSAGE
        boolean err;                                   // WS-ERR-FLG
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea handleTransaction(String transid, CarddemoCommarea request) {
        log.info("Coadm01c: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of this program (#3754). */
    public void runTask(CicsTask task) {
        log.info("Coadm01c: runTask");
        State s = new State();

        // MAIN-PARA: HANDLE CONDITION PGMIDERR(PGMIDERR-ERR-PARA) is ported as control flow:
        // each XCTL that answers PGMIDERR goes to pgmiderrErrPara.
        s.err = false;                                  // SET ERR-FLG-OFF
        s.message = " ".repeat(80);                     // MOVE SPACES TO WS-MESSAGE ERRMSGO
        s.screen.setErrmsg(" ".repeat(78));

        if (!task.hasCommarea()) {                      // IF EIBCALEN = 0
            s.ca = blankCommarea();
            s.ca.setCdemoFromProgram("COSGN00C");
            if (returnToSignonScreen(task, s)) {
                return;
            }
        } else {
            s.ca = copyOf(task.commarea(CarddemoCommarea.class));   // MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA
            if (s.ca.getCdemoPgmContext() == null || s.ca.getCdemoPgmContext() != 1) {   // NOT CDEMO-PGM-REENTER
                s.ca.setCdemoPgmContext(1);
                s.screen = lowValuesScreen();           // MOVE LOW-VALUES TO COADM1AO
                sendMenuScreen(task, s);
            } else {
                receiveMenuScreen(task, s);
                String aid = task.aid();
                if ("ENTER".equals(aid)) {
                    if (processEnterKey(task, s)) {
                        return;
                    }
                } else if ("PF3".equals(aid)) {
                    s.ca.setCdemoToProgram("COSGN00C");
                    if (returnToSignonScreen(task, s)) {
                        return;
                    }
                } else {
                    s.err = true;
                    s.message = CobolRecords.fit(MSG_INVALID_KEY, 80, CobolRecords.charset());
                    sendMenuScreen(task, s);
                }
            }
        }
        task.returnTransid(TRANID, s.ca);               // EXEC CICS RETURN TRANSID(WS-TRANID) COMMAREA(...)
    }

    /** Another program LINKed / XCTLed to this one. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea handleLink(CarddemoCommarea request) {
        log.info("Coadm01c: handleLink");
        return request;
    }

    // PROCESS-ENTER-KEY. Returns true when the task has ended (XCTL taken or PGMIDERR path ran).
    private boolean processEnterKey(CicsTask task, State s) {
        String in = fld(s.screen.getOption(), 2);
        // PERFORM VARYING WS-IDX FROM 2 BY -1 UNTIL OPTIONI(WS-IDX:1) NOT = SPACES OR WS-IDX = 1
        int idx = in.charAt(1) != ' ' ? 2 : 1;
        String moved = in.substring(0, idx);
        // MOVE OPTIONI(1:WS-IDX) TO WS-OPTION-X (PIC X(02) JUST RIGHT)
        String optX = idx == 2 ? moved : " " + moved;
        optX = optX.replace(' ', '0');                  // INSPECT ... REPLACING ALL ' ' BY '0'
        // MOVE WS-OPTION-X TO WS-OPTION (PIC 9(02)): the original run stores a non-digit byte as 0
        // ("0A" -> 00), so WS-OPTION is always numeric afterwards.
        StringBuilder digits = new StringBuilder(2);
        for (int i = 0; i < 2; i++) {
            digits.append(isDigit(optX.charAt(i)) ? optX.charAt(i) : '0');
        }
        String optNum = digits.toString();
        int option = (optNum.charAt(0) - '0') * 10 + (optNum.charAt(1) - '0');
        s.screen.setOption(optNum);                     // MOVE WS-OPTION TO OPTIONO

        // IS NOT NUMERIC can no longer be true here (see above); the other two tests remain.
        if (option > OPT_COUNT || option == 0) {
            s.err = true;
            s.message = fld("Please enter a valid option number...", 80);
            sendMenuScreen(task, s);
        }

        if (!s.err) {
            String pgm = OPT_PGM[option - 1];
            // Defect kept: no option of the table is named DUMMY, so the "not installed" message below is
            // reached only if the XCTL answers something other than success / PGMIDERR. Fix: none needed
            // unless DUMMY entries are added to COADM02Y.
            if (!CobolCompare.eq(pgm.substring(0, 5), "DUMMY")) {
                s.ca.setCdemoFromTranid(TRANID);
                s.ca.setCdemoFromProgram(PGMNAME);
                s.ca.setCdemoPgmContext(0);
                String resp = dispatchCdemoAdminOptPgmnameL145(task, pgm, s.ca);   // line 145
                if ("PGMIDERR".equals(resp)) {
                    pgmiderrErrPara(task, s);
                    return true;
                }
                if (task.ended()) {
                    return true;
                }
            }
            s.message = fld("This option is not installed ...", 80);
            s.sub.color("ERRMSG", DFHGREEN);            // MOVE DFHGREEN TO ERRMSGC
            sendMenuScreen(task, s);
        }
        return false;
    }

    // RETURN-TO-SIGNON-SCREEN. Returns true when the task has ended.
    private boolean returnToSignonScreen(CicsTask task, State s) {
        String to = s.ca.getCdemoToProgram();
        if (to == null || CobolCompare.eq(to, CobolCompare.lowValues(8)) || CobolCompare.eq(to, "")) {
            s.ca.setCdemoToProgram("COSGN00C");
        }
        String resp = dispatchCdemoToProgramL168(task, s.ca.getCdemoToProgram());   // XCTL without COMMAREA, line 168
        if ("PGMIDERR".equals(resp)) {
            pgmiderrErrPara(task, s);
            return true;
        }
        return task.ended();
    }

    // SEND-MENU-SCREEN
    private void sendMenuScreen(CicsTask task, State s) {
        populateHeaderInfo(task, s);
        buildMenuOptions(s);
        s.screen.setErrmsg(fld(s.message, 78));         // MOVE WS-MESSAGE TO ERRMSGO
        normalize(s.screen);
        task.sendMap(MAP, MAPSET, s.screen, s.sub, "ERASE");
    }

    // RECEIVE-MENU-SCREEN: RESP / RESP2 are stored in WS-RESP-CD / WS-REAS-CD and never tested
    // (defect kept; fix: test WS-RESP-CD after the RECEIVE, e.g. for MAPFAIL).
    private void receiveMenuScreen(CicsTask task, State s) {
        Optional<Coadm1aScreen> r = task.receive(MAP, MAPSET, Coadm1aScreen.class);
        // COADM1AO redefines COADM1AI: on MAPFAIL the area keeps what it held
        if (r.isPresent()) {
            s.screen = Coadm1aScreen.fromValues(r.get().screenValues());
        }
    }

    // POPULATE-HEADER-INFO
    private void populateHeaderInfo(CicsTask task, State s) {
        LocalDateTime now = task.now();
        Coadm1aScreen o = s.screen;
        o.setTitle01(fld(TITLE01, 40));
        o.setTitle02(fld(TITLE02, 40));
        o.setTrnname(fld(TRANID, 4));
        o.setPgmname(fld(PGMNAME, 8));
        o.setCurdate(now.format(DateTimeFormatter.ofPattern("MM/dd/yy", Locale.ROOT)));
        o.setCurtime(now.format(DateTimeFormatter.ofPattern("HH:mm:ss", Locale.ROOT)));
    }

    // BUILD-MENU-OPTIONS (OPTN001-OPTN010 are the only targets; the table holds 6 options)
    private void buildMenuOptions(State s) {
        for (int idx = 1; idx <= OPT_COUNT; idx++) {
            String txt = fld(String.format(Locale.ROOT, "%02d", idx) + ". " + fld(OPT_NAME[idx - 1], 35), 40);
            Coadm1aScreen o = s.screen;
            switch (idx) {
                case 1 -> o.setOptn001(txt);
                case 2 -> o.setOptn002(txt);
                case 3 -> o.setOptn003(txt);
                case 4 -> o.setOptn004(txt);
                case 5 -> o.setOptn005(txt);
                case 6 -> o.setOptn006(txt);
                case 7 -> o.setOptn007(txt);
                case 8 -> o.setOptn008(txt);
                case 9 -> o.setOptn009(txt);
                case 10 -> o.setOptn010(txt);
                default -> { }
            }
        }
    }

    /**
     * EXEC CICS HANDLE CONDITION at app/cbl/COADM01C.cbl:77 (paragraph MAIN-PARA) routes PGMIDERR to PGMIDERR-ERR-PARA.
     * The transfer is ported as control flow inside runTask (rule 19: never an exception); this hook has no
     * task to send through, so it only records the condition.
     */
    public void onConditionPgmiderrL77(CicsConditionException e) {
        log.info("HANDLE CONDITION PGMIDERR LABEL PGMIDERR-ERR-PARA at line 77: ported in runTask/pgmiderrErrPara", e);
    }

    // PGMIDERR-ERR-PARA
    private void pgmiderrErrPara(CicsTask task, State s) {
        s.message = " ".repeat(80);
        s.sub.color("ERRMSG", DFHGREEN);
        s.message = fld("This option is not installed ...", 80);
        sendMenuScreen(task, s);
        task.returnTransid(TRANID, s.ca);
    }

    // ---- helpers ----

    private static String fld(String v, int width) {
        return CobolRecords.fit(v, width, CobolRecords.charset());
    }

    private static boolean isDigit(char c) {
        return c >= '0' && c <= '9';
    }

    private static CarddemoCommarea blankCommarea() {
        CarddemoCommarea c = new CarddemoCommarea();
        c.setCdemoFromTranid(fld("", 4));
        c.setCdemoFromProgram(fld("", 8));
        c.setCdemoToTranid(fld("", 4));
        c.setCdemoToProgram(fld("", 8));
        c.setCdemoUserId(fld("", 8));
        c.setCdemoUserType(fld("", 1));
        c.setCdemoPgmContext(0);
        c.setCdemoCustId(0);
        c.setCdemoCustFname(fld("", 25));
        c.setCdemoCustMname(fld("", 25));
        c.setCdemoCustLname(fld("", 25));
        c.setCdemoAcctId(0L);
        c.setCdemoAcctStatus(fld("", 1));
        c.setCdemoCardNum(0L);
        c.setCdemoLastMap(fld("", 7));
        c.setCdemoLastMapset(fld("", 7));
        return c;
    }

    /** MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA: the program's own copy. */
    private static CarddemoCommarea copyOf(CarddemoCommarea in) {
        CarddemoCommarea c = blankCommarea();
        if (in.getCdemoFromTranid() != null) c.setCdemoFromTranid(fld(in.getCdemoFromTranid(), 4));
        if (in.getCdemoFromProgram() != null) c.setCdemoFromProgram(fld(in.getCdemoFromProgram(), 8));
        if (in.getCdemoToTranid() != null) c.setCdemoToTranid(fld(in.getCdemoToTranid(), 4));
        if (in.getCdemoToProgram() != null) c.setCdemoToProgram(fld(in.getCdemoToProgram(), 8));
        if (in.getCdemoUserId() != null) c.setCdemoUserId(fld(in.getCdemoUserId(), 8));
        if (in.getCdemoUserType() != null) c.setCdemoUserType(fld(in.getCdemoUserType(), 1));
        if (in.getCdemoPgmContext() != null) c.setCdemoPgmContext(in.getCdemoPgmContext());
        if (in.getCdemoCustId() != null) c.setCdemoCustId(in.getCdemoCustId());
        if (in.getCdemoCustFname() != null) c.setCdemoCustFname(fld(in.getCdemoCustFname(), 25));
        if (in.getCdemoCustMname() != null) c.setCdemoCustMname(fld(in.getCdemoCustMname(), 25));
        if (in.getCdemoCustLname() != null) c.setCdemoCustLname(fld(in.getCdemoCustLname(), 25));
        if (in.getCdemoAcctId() != null) c.setCdemoAcctId(in.getCdemoAcctId());
        if (in.getCdemoAcctStatus() != null) c.setCdemoAcctStatus(fld(in.getCdemoAcctStatus(), 1));
        if (in.getCdemoCardNum() != null) c.setCdemoCardNum(in.getCdemoCardNum());
        if (in.getCdemoLastMap() != null) c.setCdemoLastMap(fld(in.getCdemoLastMap(), 7));
        if (in.getCdemoLastMapset() != null) c.setCdemoLastMapset(fld(in.getCdemoLastMapset(), 7));
        return c;
    }

    /** MOVE LOW-VALUES TO COADM1AO: every field starts with a null character (the map's INITIAL). */
    private static Coadm1aScreen lowValuesScreen() {
        Coadm1aScreen o = new Coadm1aScreen();
        o.setTrnname("\0".repeat(4));
        o.setTitle01("\0".repeat(40));
        o.setCurdate("\0".repeat(8));
        o.setPgmname("\0".repeat(8));
        o.setTitle02("\0".repeat(40));
        o.setCurtime("\0".repeat(8));
        o.setOptn001("\0".repeat(40));
        o.setOptn002("\0".repeat(40));
        o.setOptn003("\0".repeat(40));
        o.setOptn004("\0".repeat(40));
        o.setOptn005("\0".repeat(40));
        o.setOptn006("\0".repeat(40));
        o.setOptn007("\0".repeat(40));
        o.setOptn008("\0".repeat(40));
        o.setOptn009("\0".repeat(40));
        o.setOptn010("\0".repeat(40));
        o.setOptn011("\0".repeat(40));
        o.setOptn012("\0".repeat(40));
        o.setOption("\0".repeat(2));
        o.setErrmsg("\0".repeat(78));
        return o;
    }

    /** A field never set holds spaces (working storage without VALUE). */
    private static void normalize(Coadm1aScreen o) {
        o.setTrnname(fld(o.getTrnname(), 4));
        o.setTitle01(fld(o.getTitle01(), 40));
        o.setCurdate(fld(o.getCurdate(), 8));
        o.setPgmname(fld(o.getPgmname(), 8));
        o.setTitle02(fld(o.getTitle02(), 40));
        o.setCurtime(fld(o.getCurtime(), 8));
        o.setOptn001(fld(o.getOptn001(), 40));
        o.setOptn002(fld(o.getOptn002(), 40));
        o.setOptn003(fld(o.getOptn003(), 40));
        o.setOptn004(fld(o.getOptn004(), 40));
        o.setOptn005(fld(o.getOptn005(), 40));
        o.setOptn006(fld(o.getOptn006(), 40));
        o.setOptn007(fld(o.getOptn007(), 40));
        o.setOptn008(fld(o.getOptn008(), 40));
        o.setOptn009(fld(o.getOptn009(), 40));
        o.setOptn010(fld(o.getOptn010(), 40));
        o.setOptn011(fld(o.getOptn011(), 40));
        o.setOptn012(fld(o.getOptn012(), 40));
        o.setOption(fld(o.getOption(), 2));
        o.setErrmsg(fld(o.getErrmsg(), 78));
    }

    /** EXEC CICS XCTL PROGRAM(CDEMO-ADMIN-OPT-PGMNAME) at app/cbl/COADM01C.cbl:145, COMMAREA(CARDDEMO-COMMAREA): the target is data-driven (candidates the engine found: COTRTLIC (table), COTRTUPC (table), COUSR00C (table), COUSR01C (table), COUSR02C (table), COUSR03C (table)).
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchCdemoAdminOptPgmnameL145(CicsTask task, String program, Object commarea) {
        return task.xctl(program.stripTrailing(), commarea);
    }

    /** EXEC CICS XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COADM01C.cbl:168, no COMMAREA: the target is data-driven (candidates the engine found: COSGN00C (moves)).
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchCdemoToProgramL168(CicsTask task, String program) {
        return task.xctl(program.stripTrailing(), null);
    }
}
