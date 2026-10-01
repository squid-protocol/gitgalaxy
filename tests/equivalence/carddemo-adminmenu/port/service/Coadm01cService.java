package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea6;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.CotrtlicCommarea;
import com.gitgalaxy.modernized.dto.contract.CotrtupcCommarea;
import com.gitgalaxy.modernized.dto.screen.Coadm1aScreen;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.exception.*;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.time.LocalDateTime;
import java.util.Locale;
import java.util.Optional;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * The RESP of RECEIVE at line 194 (paragraph RECEIVE-MENU-SCREEN) is never tested by the program (kept, see runTask).
 * Screens (#3619): Coadm1aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Coadm01cService {

    private static final Logger log = LoggerFactory.getLogger(Coadm01cService.class);

    private static final String WS_PGMNAME = "COADM01C";
    private static final String WS_TRANID = "CA00";
    private static final int DFHGREEN = 0xF4;
    private static final String MAP = "COADM1A";
    private static final String MAPSET = "COADM01";

    // COADM02Y: CDEMO-ADMIN-OPT-COUNT = 6 and the option table
    private static final int ADMIN_OPT_COUNT = 6;
    private static final String[] OPT_NAME = {
        "User List (Security)", "User Add (Security)", "User Update (Security)",
        "User Delete (Security)", "Transaction Type List/Update (Db2)", "Transaction Type Maintenance (Db2)"};
    private static final String[] OPT_PGM = {
        "COUSR00C", "COUSR01C", "COUSR02C", "COUSR03C", "COTRTLIC", "COTRTUPC"};

    // COTTL01Y / CSMSG01Y
    private static final String CCDA_TITLE01 = "      AWS Mainframe Modernization";
    private static final String CCDA_TITLE02 = "              CardDemo";
    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed. Please see below...";

    private final ObjectProvider<CotrtlicService> cotrtlicService;
    private final ObjectProvider<CotrtupcService> cotrtupcService;
    private final ObjectProvider<Cousr00cService> cousr00cService;
    private final ObjectProvider<Cousr01cService> cousr01cService;
    private final ObjectProvider<Cousr02cService> cousr02cService;
    private final ObjectProvider<Cousr03cService> cousr03cService;
    private final ObjectProvider<Cosgn00cService> cosgn00cService;

    /** The program's working storage for one task (the service is a singleton). */
    private static final class State {
        CarddemoCommarea commarea;      // CARDDEMO-COMMAREA
        Coadm1aScreen screen;           // COADM1AI / COADM1AO (one storage area)
        String message = spaces(80);    // WS-MESSAGE
        boolean err;                    // WS-ERR-FLG
        Integer errColor;               // ERRMSGC OF COADM1AO, null = not set
    }

    public void executeCoadm01c(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for COADM01C");
        // The business logic of COADM01C is a CICS task: see runTask.
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea handleTransaction(String transid, CarddemoCommarea request) {
        log.info("Coadm01c: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of this program (#3754). Ports MAIN-PARA and the paragraphs it performs. */
    public void runTask(CicsTask task) {
        log.info("Coadm01c: runTask");
        State st = new State();

        // MAIN-PARA: HANDLE CONDITION PGMIDERR(PGMIDERR-ERR-PARA) -- ported as control flow (xctlTo).
        // SET ERR-FLG-OFF TO TRUE
        st.err = false;
        // MOVE SPACES TO WS-MESSAGE ERRMSGO OF COADM1AO
        st.message = spaces(80);

        if (!task.hasCommarea()) {
            // EIBCALEN = 0 (working storage not yet set: alphanumerics spaces, numerics zero)
            st.commarea = initialCommarea();
            st.screen = newScreen(' ');
            st.screen.setErrmsg(spaces(78));
            st.commarea.setCdemoFromProgram("COSGN00C");
            returnToSignonScreen(task, st);
            return;
        }

        // MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA
        // (a COMMAREA shorter than 160 bytes would leave the rest initial; the DTO is taken whole)
        st.commarea = copy(task.commarea(CarddemoCommarea.class));
        st.screen = newScreen(' ');
        st.screen.setErrmsg(spaces(78));

        if (!(st.commarea.getCdemoPgmContext() != null && st.commarea.getCdemoPgmContext() == 1)) {
            // NOT CDEMO-PGM-REENTER
            st.commarea.setCdemoPgmContext(1);
            st.screen = newScreen('\u0000');   // MOVE LOW-VALUES TO COADM1AO
            sendMenuScreen(task, st);
        } else {
            receiveMenuScreen(task, st);
            String aid = task.aid();
            if ("ENTER".equals(aid)) {
                if (processEnterKey(task, st)) {
                    return;
                }
            } else if ("PF3".equals(aid)) {
                st.commarea.setCdemoToProgram("COSGN00C");
                returnToSignonScreen(task, st);
                return;
            } else {
                st.err = true;
                st.message = CobolRecords.fit(CCDA_MSG_INVALID_KEY, 80, CobolRecords.charset());
                sendMenuScreen(task, st);
            }
        }

        // EXEC CICS RETURN TRANSID(WS-TRANID) COMMAREA(CARDDEMO-COMMAREA)
        task.returnTransid(WS_TRANID, st.commarea);
    }

    /** PROCESS-ENTER-KEY. Returns true when the task is over (XCTL taken). */
    private boolean processEnterKey(CicsTask task, State st) {
        String optionI = st.screen.getOption();
        // PERFORM VARYING WS-IDX FROM LENGTH OF OPTIONI BY -1 UNTIL OPTIONI(WS-IDX:1) NOT = SPACES OR WS-IDX = 1
        int idx = optionI.charAt(1) != ' ' ? 2 : 1;
        // MOVE OPTIONI(1:WS-IDX) TO WS-OPTION-X  (PIC X(02) JUST RIGHT)
        String optionX = idx == 2 ? optionI.substring(0, 2) : " " + optionI.charAt(0);
        // INSPECT WS-OPTION-X REPLACING ALL ' ' BY '0'
        optionX = optionX.replace(' ', '0');
        // MOVE WS-OPTION-X TO WS-OPTION (alphanumeric to PIC 9(02)): the harness's COBOL keeps only the
        // digit characters, right-aligned ("0A" -> 00), so WS-OPTION is always NUMERIC afterwards.
        StringBuilder digits = new StringBuilder();
        for (int i = 0; i < optionX.length(); i++) {
            char c = optionX.charAt(i);
            if (c >= '0' && c <= '9') {
                digits.append(c);
            }
        }
        int option = digits.length() == 0 ? 0 : Integer.parseInt(digits.toString());
        // MOVE WS-OPTION TO OPTIONO OF COADM1AO
        st.screen.setOption(String.format(Locale.ROOT, "%02d", option));

        // IF WS-OPTION IS NOT NUMERIC OR WS-OPTION > CDEMO-ADMIN-OPT-COUNT OR WS-OPTION = ZEROS
        if (option > ADMIN_OPT_COUNT || option == 0) {
            st.err = true;
            st.message = CobolRecords.fit("Please enter a valid option number...", 80, CobolRecords.charset());
            sendMenuScreen(task, st);
        }

        if (!st.err) {
            String pgm = OPT_PGM[option - 1];
            if (!CobolCompare.eq(pgm.substring(0, 5), "DUMMY")) {
                st.commarea.setCdemoFromTranid(WS_TRANID);
                st.commarea.setCdemoFromProgram(WS_PGMNAME);
                st.commarea.setCdemoPgmContext(0);
                // XCTL PROGRAM(CDEMO-ADMIN-OPT-PGMNAME(WS-OPTION)) COMMAREA(CARDDEMO-COMMAREA)
                if (xctlTo(task, st, pgm, st.commarea)) {
                    return true;
                }
            }
            // Only reached for a 'DUMMY' entry (none in COADM02Y): unreachable with the shipped table, kept.
            st.message = spaces(80);
            st.errColor = DFHGREEN;
            st.message = CobolRecords.fit("This option is not installed ...", 80, CobolRecords.charset());
            sendMenuScreen(task, st);
        }
        return false;
    }

    /** RETURN-TO-SIGNON-SCREEN: the XCTL never returns, so the task is over afterwards. */
    private void returnToSignonScreen(CicsTask task, State st) {
        String to = st.commarea.getCdemoToProgram();
        if (CobolCompare.eq(to, CobolCompare.lowValues(8)) || CobolCompare.eq(to, "")) {
            st.commarea.setCdemoToProgram("COSGN00C");
        }
        xctlTo(task, st, st.commarea.getCdemoToProgram(), null);
    }

    /**
     * EXEC CICS XCTL under HANDLE CONDITION PGMIDERR(PGMIDERR-ERR-PARA). Always true: the XCTL either leaves
     * the program, or the handler paragraph ran and RETURNed, or the task was abended.
     */
    private boolean xctlTo(CicsTask task, State st, String program, CarddemoCommarea commarea) {
        String resp = task.xctl(program.trim(), commarea);
        if ("NORMAL".equals(resp)) {
            return true;
        }
        if ("PGMIDERR".equals(resp)) {
            pgmiderrErrPara(task, st);
            return true;
        }
        task.abendOnCondition(resp);   // no HANDLE ABEND in this program: the task ends
        return true;
    }

    /** SEND-MENU-SCREEN. */
    private void sendMenuScreen(CicsTask task, State st) {
        populateHeaderInfo(task, st);
        buildMenuOptions(st);
        // MOVE WS-MESSAGE TO ERRMSGO OF COADM1AO
        st.screen.setErrmsg(CobolRecords.fit(st.message, 78, CobolRecords.charset()));

        CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
        if (st.errColor != null) {
            sub.color("ERRMSG", st.errColor);
        }
        task.sendMap(MAP, MAPSET, Coadm1aScreen.fromValues(st.screen.screenValues()), sub, "ERASE");
    }

    /** RECEIVE-MENU-SCREEN. */
    private void receiveMenuScreen(CicsTask task, State st) {
        Optional<Coadm1aScreen> in = task.receive(MAP, MAPSET, Coadm1aScreen.class);
        // RESP(WS-RESP-CD) is never tested (defect: a MAPFAIL or other RESP is ignored; fix: EVALUATE WS-RESP-CD).
        // On MAPFAIL COADM1AI keeps its previous content (blank here).
        in.ifPresent(s -> st.screen = normalize(s));
    }

    /** POPULATE-HEADER-INFO. */
    private void populateHeaderInfo(CicsTask task, State st) {
        LocalDateTime now = task.now();   // MOVE FUNCTION CURRENT-DATE TO WS-CURDATE-DATA
        Coadm1aScreen s = st.screen;
        s.setTitle01(CobolRecords.fit(CCDA_TITLE01, 40, CobolRecords.charset()));
        s.setTitle02(CobolRecords.fit(CCDA_TITLE02, 40, CobolRecords.charset()));
        s.setTrnname(WS_TRANID);
        s.setPgmname(WS_PGMNAME);
        s.setCurdate(String.format(Locale.ROOT, "%02d/%02d/%02d",
                now.getMonthValue(), now.getDayOfMonth(), now.getYear() % 100));
        s.setCurtime(String.format(Locale.ROOT, "%02d:%02d:%02d",
                now.getHour(), now.getMinute(), now.getSecond()));
    }

    /** BUILD-MENU-OPTIONS. */
    private void buildMenuOptions(State st) {
        for (int idx = 1; idx <= ADMIN_OPT_COUNT; idx++) {
            // STRING NUM '. ' NAME INTO WS-ADMIN-OPT-TXT (PIC X(40), spaces first)
            String txt = String.format(Locale.ROOT, "%02d", idx) + ". "
                    + CobolRecords.fit(OPT_NAME[idx - 1], 35, CobolRecords.charset());
            txt = CobolRecords.fit(txt, 40, CobolRecords.charset());
            Coadm1aScreen s = st.screen;
            switch (idx) {
                case 1 -> s.setOptn001(txt);
                case 2 -> s.setOptn002(txt);
                case 3 -> s.setOptn003(txt);
                case 4 -> s.setOptn004(txt);
                case 5 -> s.setOptn005(txt);
                case 6 -> s.setOptn006(txt);
                case 7 -> s.setOptn007(txt);
                case 8 -> s.setOptn008(txt);
                case 9 -> s.setOptn009(txt);
                case 10 -> s.setOptn010(txt);
                default -> { }   // WHEN OTHER CONTINUE (OPTN011 / OPTN012 are never filled)
            }
        }
    }

    /** PGMIDERR-ERR-PARA: reached by HANDLE CONDITION PGMIDERR when an XCTL finds no program. */
    private void pgmiderrErrPara(CicsTask task, State st) {
        st.message = spaces(80);
        st.errColor = DFHGREEN;
        st.message = CobolRecords.fit("This option is not installed ...", 80, CobolRecords.charset());
        sendMenuScreen(task, st);
        task.returnTransid(WS_TRANID, st.commarea);
    }

    /** Another program LINKed / XCTLed to this one. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea handleLink(CarddemoCommarea request) {
        log.info("Coadm01c: handleLink");
        return request;
    }

    /** XCTL PROGRAM(CDEMO-ADMIN-OPT-PGMNAME) at app/cbl/COADM01C.cbl:145: the target is data-driven. Candidates: COTRTLIC (table), COTRTUPC (table), COUSR00C (table), COUSR01C (table), COUSR02C (table), COUSR03C (table).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCdemoAdminOptPgmnameL145(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COTRTLIC":
                return cotrtlicService.getObject().handleLink(CotrtlicCommarea.fromPrefix((CarddemoCommarea) request));
            case "COTRTUPC":
                return cotrtupcService.getObject().handleLink(CotrtupcCommarea.fromPrefix((CarddemoCommarea) request));
            case "COUSR00C":
                return cousr00cService.getObject().handleLink((CarddemoCommarea6) request);
            case "COUSR01C":
                return cousr01cService.getObject().handleLink((CarddemoCommarea) request);
            case "COUSR02C":
                return cousr02cService.getObject().handleLink((CarddemoCommarea) request);
            case "COUSR03C":
                return cousr03cService.getObject().handleLink((CarddemoCommarea) request);
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CDEMO-ADMIN-OPT-PGMNAME) at app/cbl/COADM01C.cbl:145: no known target " + program);
        }
    }

    /** XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COADM01C.cbl:168: the target is data-driven. Candidates: COSGN00C (moves).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCdemoToProgramL168(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COSGN00C":
                cosgn00cService.getObject().handleLink();
                return null;
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COADM01C.cbl:168: no known target " + program);
        }
    }

    /**
     * EXEC CICS HANDLE CONDITION at app/cbl/COADM01C.cbl:77 (paragraph MAIN-PARA) routes PGMIDERR to PGMIDERR-ERR-PARA.
     * Per the CICS porting rules the transfer is plain control flow, never an exception: runTask reaches
     * PGMIDERR-ERR-PARA (pgmiderrErrPara) from the RESP of its XCTLs. This entry point has no task to
     * send on, so it only records the condition.
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     */
    public void onConditionPgmiderrL77(CicsConditionException e) {
        log.info("HANDLE CONDITION PGMIDERR LABEL PGMIDERR-ERR-PARA at line 77", e);
        // Logic of PGMIDERR-ERR-PARA: see pgmiderrErrPara(CicsTask, State), run from runTask.
    }

    /** SEND MAP(COADM1A) MAPSET(COADM01) FROM(COADM1AO) at app/cbl/COADM01C.cbl:182 (#3619).
     *  The logic that fills COADM1AO is in sendMenuScreen (runTask).
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public Coadm1aScreen renderCoadm1a(Coadm1aScreen screen) {
        return screen;
    }

    /** RECEIVE MAP(COADM1A) MAPSET(COADM01) INTO(COADM1AI) at app/cbl/COADM01C.cbl:194 (#3619).
     *  `aid` is the key the user pressed (EIBAID): ENTER, PF1-PF24, CLEAR, PA1-PA3.
     *  The logic that reads COADM1AI after the RECEIVE is in processEnterKey (runTask).
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public ScreenModel submitCoadm1a(Coadm1aScreen input, String aid) {
        return renderCoadm1a(input);
    }

    // ---- helpers -------------------------------------------------------------------------------

    private static String spaces(int n) {
        return " ".repeat(n);
    }

    private static Coadm1aScreen newScreen(char fill) {
        Coadm1aScreen s = new Coadm1aScreen();
        String f4 = String.valueOf(fill).repeat(4);
        String f8 = String.valueOf(fill).repeat(8);
        String f40 = String.valueOf(fill).repeat(40);
        s.setTrnname(f4);
        s.setTitle01(f40);
        s.setCurdate(f8);
        s.setPgmname(f8);
        s.setTitle02(f40);
        s.setCurtime(f8);
        s.setOptn001(f40);
        s.setOptn002(f40);
        s.setOptn003(f40);
        s.setOptn004(f40);
        s.setOptn005(f40);
        s.setOptn006(f40);
        s.setOptn007(f40);
        s.setOptn008(f40);
        s.setOptn009(f40);
        s.setOptn010(f40);
        s.setOptn011(f40);
        s.setOptn012(f40);
        s.setOption(String.valueOf(fill).repeat(2));
        s.setErrmsg(String.valueOf(fill).repeat(78));
        return s;
    }

    /** A received map as COADM1AI holds it: each field its declared width; an untransmitted one low-values. */
    private static Coadm1aScreen normalize(Coadm1aScreen in) {
        Coadm1aScreen s = new Coadm1aScreen();
        s.setTrnname(fld(in.getTrnname(), 4));
        s.setTitle01(fld(in.getTitle01(), 40));
        s.setCurdate(fld(in.getCurdate(), 8));
        s.setPgmname(fld(in.getPgmname(), 8));
        s.setTitle02(fld(in.getTitle02(), 40));
        s.setCurtime(fld(in.getCurtime(), 8));
        s.setOptn001(fld(in.getOptn001(), 40));
        s.setOptn002(fld(in.getOptn002(), 40));
        s.setOptn003(fld(in.getOptn003(), 40));
        s.setOptn004(fld(in.getOptn004(), 40));
        s.setOptn005(fld(in.getOptn005(), 40));
        s.setOptn006(fld(in.getOptn006(), 40));
        s.setOptn007(fld(in.getOptn007(), 40));
        s.setOptn008(fld(in.getOptn008(), 40));
        s.setOptn009(fld(in.getOptn009(), 40));
        s.setOptn010(fld(in.getOptn010(), 40));
        s.setOptn011(fld(in.getOptn011(), 40));
        s.setOptn012(fld(in.getOptn012(), 40));
        s.setOption(fld(in.getOption(), 2));
        s.setErrmsg(fld(in.getErrmsg(), 78));
        return s;
    }

    private static String fld(String v, int len) {
        return v == null ? "\u0000".repeat(len) : CobolRecords.fit(v, len, CobolRecords.charset());
    }

    private static CarddemoCommarea initialCommarea() {
        CarddemoCommarea c = new CarddemoCommarea();
        c.setCdemoFromTranid(spaces(4));
        c.setCdemoFromProgram(spaces(8));
        c.setCdemoToTranid(spaces(4));
        c.setCdemoToProgram(spaces(8));
        c.setCdemoUserId(spaces(8));
        c.setCdemoUserType(" ");
        c.setCdemoPgmContext(0);
        c.setCdemoCustId(0);
        c.setCdemoCustFname(spaces(25));
        c.setCdemoCustMname(spaces(25));
        c.setCdemoCustLname(spaces(25));
        c.setCdemoAcctId(0L);
        c.setCdemoAcctStatus(" ");
        c.setCdemoCardNum(0L);
        c.setCdemoLastMap(spaces(7));
        c.setCdemoLastMapset(spaces(7));
        return c;
    }

    private static CarddemoCommarea copy(CarddemoCommarea s) {
        CarddemoCommarea c = new CarddemoCommarea();
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
        return c;
    }

}
