package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.CoactupcCommarea;
import com.gitgalaxy.modernized.dto.contract.CoactvwcCommarea;
import com.gitgalaxy.modernized.dto.contract.Cobil00cCarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.CocrdlicCommarea;
import com.gitgalaxy.modernized.dto.contract.CocrdslcCommarea;
import com.gitgalaxy.modernized.dto.contract.CocrdupcCommarea;
import com.gitgalaxy.modernized.dto.contract.Copaus0cCarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.Cotrn00cCarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.Cotrn01cCarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.Cotrn02cCarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Comen1aScreen;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.time.LocalDateTime;
import java.util.Locale;
import java.util.Optional;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * INQUIRE at line 148 tests NORMAL
 * TODO: the RESP of RECEIVE at line 227 (paragraph RECEIVE-MENU-SCREEN) is never tested
 * Screens (#3619): Comen1aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Comen01cService {

    private static final Logger log = LoggerFactory.getLogger(Comen01cService.class);

    private static final String WS_PGMNAME = "COMEN01C";
    private static final String WS_TRANID = "CM00";
    private static final String MAP = "COMEN1A";
    private static final String MAPSET = "COMEN01";
    private static final int DFHRED = 0xF2;
    private static final int DFHGREEN = 0xF4;

    // COCOM01Y 88 CDEMO-PGM-REENTER VALUE 1
    private static final int PGM_REENTER = 1;

    // COTTL01Y
    private static final String CCDA_TITLE01 = "      AWS Mainframe Modernization       ";
    private static final String CCDA_TITLE02 = "              CardDemo                  ";
    // CSMSG01Y
    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed. Please see below...         ";

    // COMEN02Y: CDEMO-MENU-OPT-COUNT and the table (NAME X(35), PGMNAME X(08), USRTYPE X(01))
    private static final int MENU_OPT_COUNT = 11;
    private static final String[] OPT_NAME = {
        "Account View", "Account Update", "Credit Card List", "Credit Card View", "Credit Card Update",
        "Transaction List", "Transaction View", "Transaction Add", "Transaction Reports", "Bill Payment",
        "Pending Authorization View"};
    private static final String[] OPT_PGM = {
        "COACTVWC", "COACTUPC", "COCRDLIC", "COCRDSLC", "COCRDUPC", "COTRN00C", "COTRN01C", "COTRN02C",
        "CORPT00C", "COBIL00C", "COPAUS0C"};
    private static final String[] OPT_USRTYPE = {"U", "U", "U", "U", "U", "U", "U", "U", "U", "U", "U"};

    private final ObjectProvider<CoactupcService> coactupcService;
    private final ObjectProvider<CoactvwcService> coactvwcService;
    private final ObjectProvider<Cobil00cService> cobil00cService;
    private final ObjectProvider<CocrdlicService> cocrdlicService;
    private final ObjectProvider<CocrdslcService> cocrdslcService;
    private final ObjectProvider<CocrdupcService> cocrdupcService;
    private final ObjectProvider<Copaus0cService> copaus0cService;
    private final ObjectProvider<Corpt00cService> corpt00cService;
    private final ObjectProvider<Cotrn00cService> cotrn00cService;
    private final ObjectProvider<Cotrn01cService> cotrn01cService;
    private final ObjectProvider<Cotrn02cService> cotrn02cService;
    private final ObjectProvider<Cosgn00cService> cosgn00cService;

    /** COMEN01C is a CICS program: its whole PROCEDURE DIVISION is ported in {@link #runTask(CicsTask)}. */
    public void executeComen01c(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for COMEN01C");
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea handleTransaction(String transid, CarddemoCommarea request) {
        log.info("Comen01c: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of this program (#3754): MAIN-PARA and the paragraphs it performs. */
    public void runTask(CicsTask task) {
        new Run(task).mainPara();
    }

    /** Another program LINKed / XCTLed to this one. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea handleLink(CarddemoCommarea request) {
        log.info("Comen01c: handleLink");
        return request;
    }

    /** XCTL PROGRAM(CDEMO-MENU-OPT-PGMNAME) at app/cbl/COMEN01C.cbl:156: the target is data-driven. Candidates: COACTUPC (table), COACTVWC (table), COBIL00C (table), COCRDLIC (table), COCRDSLC (table), COCRDUPC (table), COPAUS0C (table), CORPT00C (table), COTRN00C (table), COTRN01C (table), COTRN02C (table).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCdemoMenuOptPgmnameL156(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COACTUPC":
                return coactupcService.getObject().handleLink(CoactupcCommarea.fromPrefix((CarddemoCommarea) request));
            case "COACTVWC":
                return coactvwcService.getObject().handleLink(CoactvwcCommarea.fromPrefix((CarddemoCommarea) request));
            case "COBIL00C":
                return cobil00cService.getObject().handleLink((Cobil00cCarddemoCommarea) request);
            case "COCRDLIC":
                return cocrdlicService.getObject().handleLink(CocrdlicCommarea.fromPrefix((CarddemoCommarea) request));
            case "COCRDSLC":
                return cocrdslcService.getObject().handleLink(CocrdslcCommarea.fromPrefix((CarddemoCommarea) request));
            case "COCRDUPC":
                return cocrdupcService.getObject().handleLink(CocrdupcCommarea.fromPrefix((CarddemoCommarea) request));
            case "COPAUS0C":
                return copaus0cService.getObject().handleLink((Copaus0cCarddemoCommarea) request);
            case "CORPT00C":
                return corpt00cService.getObject().handleLink((CarddemoCommarea) request);
            case "COTRN00C":
                return cotrn00cService.getObject().handleLink((Cotrn00cCarddemoCommarea) request);
            case "COTRN01C":
                return cotrn01cService.getObject().handleLink((Cotrn01cCarddemoCommarea) request);
            case "COTRN02C":
                return cotrn02cService.getObject().handleLink((Cotrn02cCarddemoCommarea) request);
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CDEMO-MENU-OPT-PGMNAME) at app/cbl/COMEN01C.cbl:156: no known target " + program);
        }
    }

    /** XCTL PROGRAM(CDEMO-MENU-OPT-PGMNAME) at app/cbl/COMEN01C.cbl:184: the target is data-driven. Candidates: COACTUPC (table), COACTVWC (table), COBIL00C (table), COCRDLIC (table), COCRDSLC (table), COCRDUPC (table), COPAUS0C (table), CORPT00C (table), COTRN00C (table), COTRN01C (table), COTRN02C (table).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCdemoMenuOptPgmnameL184(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COACTUPC":
                return coactupcService.getObject().handleLink(CoactupcCommarea.fromPrefix((CarddemoCommarea) request));
            case "COACTVWC":
                return coactvwcService.getObject().handleLink(CoactvwcCommarea.fromPrefix((CarddemoCommarea) request));
            case "COBIL00C":
                return cobil00cService.getObject().handleLink((Cobil00cCarddemoCommarea) request);
            case "COCRDLIC":
                return cocrdlicService.getObject().handleLink(CocrdlicCommarea.fromPrefix((CarddemoCommarea) request));
            case "COCRDSLC":
                return cocrdslcService.getObject().handleLink(CocrdslcCommarea.fromPrefix((CarddemoCommarea) request));
            case "COCRDUPC":
                return cocrdupcService.getObject().handleLink(CocrdupcCommarea.fromPrefix((CarddemoCommarea) request));
            case "COPAUS0C":
                return copaus0cService.getObject().handleLink((Copaus0cCarddemoCommarea) request);
            case "CORPT00C":
                return corpt00cService.getObject().handleLink((CarddemoCommarea) request);
            case "COTRN00C":
                return cotrn00cService.getObject().handleLink((Cotrn00cCarddemoCommarea) request);
            case "COTRN01C":
                return cotrn01cService.getObject().handleLink((Cotrn01cCarddemoCommarea) request);
            case "COTRN02C":
                return cotrn02cService.getObject().handleLink((Cotrn02cCarddemoCommarea) request);
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CDEMO-MENU-OPT-PGMNAME) at app/cbl/COMEN01C.cbl:184: no known target " + program);
        }
    }

    /** XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COMEN01C.cbl:201: the target is data-driven. Candidates: COSGN00C (moves).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCdemoToProgramL201(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COSGN00C":
                cosgn00cService.getObject().handleLink();
                return null;
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COMEN01C.cbl:201: no known target " + program);
        }
    }

    /** SEND MAP(COMEN1A) MAPSET(COMEN01) FROM(COMEN1AO) at app/cbl/COMEN01C.cbl:215 (#3619).
     *  Ported in runTask (SEND-MENU-SCREEN); the web view model is not used by the harness.
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public Comen1aScreen renderComen1a(Comen1aScreen screen) {
        return screen;
    }

    /** RECEIVE MAP(COMEN1A) MAPSET(COMEN01) INTO(COMEN1AI) at app/cbl/COMEN01C.cbl:227 (#3619).
     *  Ported in runTask (RECEIVE-MENU-SCREEN / PROCESS-ENTER-KEY).
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public ScreenModel submitComen1a(Comen1aScreen input, String aid) {
        return renderComen1a(input);
    }

    // ------------------------------------------------------------------------------------------
    // helpers
    // ------------------------------------------------------------------------------------------

    /** Alphanumeric MOVE: pad with spaces or truncate on the right. */
    private static String pad(String s, int n) {
        String v = s == null ? "" : s;
        if (v.length() >= n) {
            return v.substring(0, n);
        }
        return v + " ".repeat(n - v.length());
    }

    private static String lowValues(int n) {
        return "\u0000".repeat(n);
    }

    private static CarddemoCommarea copyOf(CarddemoCommarea c) {
        CarddemoCommarea o = new CarddemoCommarea();
        o.setCdemoFromTranid(c.getCdemoFromTranid());
        o.setCdemoFromProgram(c.getCdemoFromProgram());
        o.setCdemoToTranid(c.getCdemoToTranid());
        o.setCdemoToProgram(c.getCdemoToProgram());
        o.setCdemoUserId(c.getCdemoUserId());
        o.setCdemoUserType(c.getCdemoUserType());
        o.setCdemoPgmContext(c.getCdemoPgmContext());
        o.setCdemoCustId(c.getCdemoCustId());
        o.setCdemoCustFname(c.getCdemoCustFname());
        o.setCdemoCustMname(c.getCdemoCustMname());
        o.setCdemoCustLname(c.getCdemoCustLname());
        o.setCdemoAcctId(c.getCdemoAcctId());
        o.setCdemoAcctStatus(c.getCdemoAcctStatus());
        o.setCdemoCardNum(c.getCdemoCardNum());
        o.setCdemoLastMap(c.getCdemoLastMap());
        o.setCdemoLastMapset(c.getCdemoLastMapset());
        return o;
    }

    /** The working storage of one task (COBOL WORKING-STORAGE is fresh per task). */
    private static final class Run {
        private final CicsTask task;
        private CarddemoCommarea commarea = new CarddemoCommarea();   // CARDDEMO-COMMAREA
        // COMEN1AI / COMEN1AO share storage (REDEFINES): one screen object is both. Initial storage is spaces.
        private final Comen1aScreen scr = blankScreen();
        private final CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
        private String wsMessage = pad("", 80);                        // WS-MESSAGE
        private boolean errFlg = false;                                // WS-ERR-FLG ('Y' = ERR-FLG-ON)

        Run(CicsTask task) {
            this.task = task;
        }

        private static Comen1aScreen blankScreen() {
            Comen1aScreen s = new Comen1aScreen();
            fill(s, ' ');
            return s;
        }

        private static void fill(Comen1aScreen s, char c) {
            String ch = String.valueOf(c);
            s.setTrnname(ch.repeat(4));
            s.setTitle01(ch.repeat(40));
            s.setCurdate(ch.repeat(8));
            s.setPgmname(ch.repeat(8));
            s.setTitle02(ch.repeat(40));
            s.setCurtime(ch.repeat(8));
            for (int i = 1; i <= 12; i++) {
                setOpt(s, i, ch.repeat(40));
            }
            s.setOption(ch.repeat(2));
            s.setErrmsg(ch.repeat(78));
        }

        private static void setOpt(Comen1aScreen s, int i, String v) {
            switch (i) {
                case 1 -> s.setOptn001(v);
                case 2 -> s.setOptn002(v);
                case 3 -> s.setOptn003(v);
                case 4 -> s.setOptn004(v);
                case 5 -> s.setOptn005(v);
                case 6 -> s.setOptn006(v);
                case 7 -> s.setOptn007(v);
                case 8 -> s.setOptn008(v);
                case 9 -> s.setOptn009(v);
                case 10 -> s.setOptn010(v);
                case 11 -> s.setOptn011(v);
                case 12 -> s.setOptn012(v);
                default -> { }
            }
        }

        /** RECEIVE INTO COMEN1AI overwrites the shared storage with what the terminal sent. */
        private void overlay(Comen1aScreen in) {
            if (in.getTrnname() != null) scr.setTrnname(pad(in.getTrnname(), 4));
            if (in.getTitle01() != null) scr.setTitle01(pad(in.getTitle01(), 40));
            if (in.getCurdate() != null) scr.setCurdate(pad(in.getCurdate(), 8));
            if (in.getPgmname() != null) scr.setPgmname(pad(in.getPgmname(), 8));
            if (in.getTitle02() != null) scr.setTitle02(pad(in.getTitle02(), 40));
            if (in.getCurtime() != null) scr.setCurtime(pad(in.getCurtime(), 8));
            String[] o = {in.getOptn001(), in.getOptn002(), in.getOptn003(), in.getOptn004(), in.getOptn005(),
                in.getOptn006(), in.getOptn007(), in.getOptn008(), in.getOptn009(), in.getOptn010(),
                in.getOptn011(), in.getOptn012()};
            for (int i = 0; i < 12; i++) {
                if (o[i] != null) setOpt(scr, i + 1, pad(o[i], 40));
            }
            if (in.getOption() != null) scr.setOption(pad(in.getOption(), 2));
            if (in.getErrmsg() != null) scr.setErrmsg(pad(in.getErrmsg(), 78));
        }

        private boolean xctled = false;

        // ---- MAIN-PARA ----
        void mainPara() {
            errFlg = false;                                            // SET ERR-FLG-OFF TO TRUE
            wsMessage = pad("", 80);                                   // MOVE SPACES TO WS-MESSAGE
            scr.setErrmsg(pad("", 78));                                //   ERRMSGO OF COMEN1AO

            if (!task.hasCommarea()) {                                 // IF EIBCALEN = 0
                commarea.setCdemoFromProgram("COSGN00C");
                returnToSignonScreen();
                return;                                                // XCTL never returns (or the task abended)
            }
            // MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA
            commarea = copyOf(task.commarea(CarddemoCommarea.class));
            int ctx = commarea.getCdemoPgmContext() == null ? 0 : commarea.getCdemoPgmContext();
            if (ctx != PGM_REENTER) {                                  // IF NOT CDEMO-PGM-REENTER
                commarea.setCdemoPgmContext(PGM_REENTER);
                fill(scr, '\u0000');                                   // MOVE LOW-VALUES TO COMEN1AO
                sendMenuScreen();
            } else {
                receiveMenuScreen();
                String aid = task.aid();
                if ("ENTER".equals(aid)) {                             // WHEN DFHENTER
                    processEnterKey();
                    if (xctled) {
                        return;
                    }
                } else if ("PF3".equals(aid)) {                        // WHEN DFHPF3
                    commarea.setCdemoToProgram("COSGN00C");
                    returnToSignonScreen();
                    return;
                } else {                                               // WHEN OTHER
                    errFlg = true;
                    wsMessage = pad(CCDA_MSG_INVALID_KEY, 80);
                    sendMenuScreen();
                }
            }
            // EXEC CICS RETURN TRANSID(WS-TRANID) COMMAREA(CARDDEMO-COMMAREA)
            task.returnTransid(WS_TRANID, commarea);
        }

        // ---- PROCESS-ENTER-KEY ----
        private void processEnterKey() {
            String optionI = pad(scr.getOption(), 2);
            // PERFORM VARYING WS-IDX FROM 2 BY -1 UNTIL OPTIONI(WS-IDX:1) NOT = SPACES OR WS-IDX = 1
            int idx = optionI.charAt(1) != ' ' ? 2 : 1;
            // MOVE OPTIONI(1:WS-IDX) TO WS-OPTION-X (JUST RIGHT)
            String src = optionI.substring(0, idx);
            String optionX = idx == 1 ? " " + src : src;
            optionX = optionX.replace(' ', '0');                       // INSPECT ... REPLACING ALL ' ' BY '0'
            // MOVE WS-OPTION-X TO WS-OPTION (9(02)): bytes are copied as they are
            // MOVE WS-OPTION TO OPTIONO
            scr.setOption(optionX);

            char c0 = optionX.charAt(0);
            char c1 = optionX.charAt(1);
            boolean numeric = c0 >= '0' && c0 <= '9' && c1 >= '0' && c1 <= '9';
            int option = numeric ? (c0 - '0') * 10 + (c1 - '0') : -1;

            if (!numeric || option > MENU_OPT_COUNT || option == 0) {
                errFlg = true;
                wsMessage = pad("Please enter a valid option number...", 80);
                sendMenuScreen();
            }

            // DEFECT (kept): this test runs even after the invalid-option error above, with WS-OPTION out of
            // the table (COBOL reads storage outside it; here: not 'A'). Fix: ELSE-chain the two IFs.
            // DEFECT (kept): every table entry is 'U', so the admin-only branch can never fire.
            boolean inTable = option >= 1 && option <= MENU_OPT_COUNT;
            if (CobolCompare.eq(commarea.getCdemoUserType(), "U") && inTable
                    && "A".equals(OPT_USRTYPE[option - 1])) {
                errFlg = true;
                wsMessage = pad("", 80);
                wsMessage = pad("No access - Admin Only option... ", 80);
                sendMenuScreen();
            }

            if (!errFlg) {                                             // IF NOT ERR-FLG-ON (option is valid here)
                String pgm = OPT_PGM[option - 1];
                String name35 = pad(OPT_NAME[option - 1], 35);
                if (CobolCompare.eq(pgm, "COPAUS0C")) {
                    int resp = task.inquireProgram(pgm);               // EXEC CICS INQUIRE PROGRAM NOHANDLE
                    if (resp == 0) {                                   // EIBRESP = DFHRESP(NORMAL)
                        commarea.setCdemoFromTranid(WS_TRANID);
                        commarea.setCdemoFromProgram(pad(WS_PGMNAME, 8));
                        commarea.setCdemoPgmContext(0);
                        xctl(pgm, commarea);                           // XCTL ... COMMAREA(CARDDEMO-COMMAREA)
                        return;
                    }
                    wsMessage = pad("", 80);
                    sub.color("ERRMSG", DFHRED);
                    int cut = name35.indexOf("  ");                    // DELIMITED BY '  '
                    String nm = cut < 0 ? name35 : name35.substring(0, cut);
                    wsMessage = pad("This option " + nm + " is not installed...", 80);
                } else if (pgm.startsWith("DUMMY")) {
                    wsMessage = pad("", 80);
                    sub.color("ERRMSG", DFHGREEN);
                    int cut = name35.indexOf(' ');                     // DELIMITED BY SPACE
                    String nm = cut < 0 ? name35 : name35.substring(0, cut);
                    wsMessage = pad("This option " + nm + "is coming soon ...", 80);
                } else {
                    commarea.setCdemoFromTranid(WS_TRANID);
                    commarea.setCdemoFromProgram(pad(WS_PGMNAME, 8));
                    // DEFECT (kept): MOVE WS-PGMNAME TO CDEMO-FROM-PROGRAM is coded twice (lines 179-180);
                    // the repeat is harmless. Fix: delete line 180.
                    commarea.setCdemoPgmContext(0);
                    xctl(pgm, commarea);
                    return;
                }
                sendMenuScreen();
            }
        }

        // ---- RETURN-TO-SIGNON-SCREEN ----
        private void returnToSignonScreen() {
            String to = commarea.getCdemoToProgram();
            if (CobolCompare.eq(to, lowValues(8)) || CobolCompare.eq(to, " ")) {
                commarea.setCdemoToProgram("COSGN00C");
            }
            xctl(commarea.getCdemoToProgram(), null);                  // XCTL PROGRAM(CDEMO-TO-PROGRAM)
        }

        /** XCTL: on success the task ends; a failure (PGMIDERR) is unhandled, so CICS abends the task. */
        private void xctl(String program, Object comm) {
            String resp = task.xctl(program.stripTrailing(), comm);
            if (!"NORMAL".equals(resp)) {
                task.abendOnCondition(resp);
            }
            xctled = true;
        }

        // ---- SEND-MENU-SCREEN ----
        private void sendMenuScreen() {
            populateHeaderInfo();
            buildMenuOptions();
            scr.setErrmsg(pad(wsMessage, 78));                         // MOVE WS-MESSAGE TO ERRMSGO
            task.sendMap(MAP, MAPSET, scr, sub, "ERASE");
        }

        // ---- RECEIVE-MENU-SCREEN ----
        private void receiveMenuScreen() {
            // RESP / RESP2 go to WS-RESP-CD / WS-REAS-CD and are never tested (MAPFAIL leaves COMEN1AI as it was).
            Optional<Comen1aScreen> in = task.receive(MAP, MAPSET, Comen1aScreen.class);
            in.ifPresent(this::overlay);
        }

        // ---- POPULATE-HEADER-INFO ----
        private void populateHeaderInfo() {
            LocalDateTime now = task.now();                            // FUNCTION CURRENT-DATE
            scr.setTitle01(pad(CCDA_TITLE01, 40));
            scr.setTitle02(pad(CCDA_TITLE02, 40));
            scr.setTrnname(pad(WS_TRANID, 4));
            scr.setPgmname(pad(WS_PGMNAME, 8));
            scr.setCurdate(String.format(Locale.ROOT, "%02d/%02d/%02d",
                    now.getMonthValue(), now.getDayOfMonth(), now.getYear() % 100));
            scr.setCurtime(String.format(Locale.ROOT, "%02d:%02d:%02d",
                    now.getHour(), now.getMinute(), now.getSecond()));
        }

        // ---- BUILD-MENU-OPTIONS ----
        private void buildMenuOptions() {
            for (int idx = 1; idx <= MENU_OPT_COUNT; idx++) {
                String txt = String.format(Locale.ROOT, "%02d", idx) + ". " + pad(OPT_NAME[idx - 1], 35);
                setOpt(scr, idx, pad(txt, 40));                        // WHEN 1..12 (12 is never reached)
            }
        }
    }
}
