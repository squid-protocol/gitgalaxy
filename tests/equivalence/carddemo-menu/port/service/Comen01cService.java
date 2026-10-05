package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Comen1aScreen;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.time.LocalDateTime;
import java.util.Locale;
import java.util.Optional;
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


    /** A CICS transaction entered the program (#4343): one task of it in the region (CicsTask.region()),
     *  ENTER pressed -- `request` its COMMAREA, null when started from a cleared screen -- run through runTask. Returns the COMMAREA its RETURN passes on (null: none).
     *  The COMMAREA crosses programs (#4427): COBOL passes bytes, and each program reads them through its
     *  own record, so a port may pass either record -- the facade carries it as Object where a flow
     *  presents another class, and runTask reads it (task.commarea(..)). The flows:
     *  out: RETURN TRANSID(CPVS) COMMAREA(CARDDEMO-COMMAREA) at app/app-authorization-ims-db2-mq/cbl/COPAUS0C.cbl:254 -> app/app-authorization-ims-db2-mq/cbl/COPAUS0C.cbl, after an XCTL from app/cbl/COMEN01C.cbl (Copaus0cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CPVD) COMMAREA(CARDDEMO-COMMAREA) at app/app-authorization-ims-db2-mq/cbl/COPAUS1C.cbl:202 -> a program the estate does not resolve, after an XCTL from app/cbl/COMEN01C.cbl (Copaus1cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CTLI) COMMAREA(WS-COMMAREA) at app/app-transaction-type-db2/cbl/COTRTLIC.cbl:910 -> app/app-transaction-type-db2/cbl/COTRTLIC.cbl, after an XCTL from app/cbl/COMEN01C.cbl (CotrtlicCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CTTU) COMMAREA(WS-COMMAREA) at app/app-transaction-type-db2/cbl/COTRTUPC.cbl:567 -> app/app-transaction-type-db2/cbl/COTRTUPC.cbl, after an XCTL from app/cbl/COMEN01C.cbl (CotrtupcCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CAUP) COMMAREA(WS-COMMAREA) at app/cbl/COACTUPC.cbl:1015 -> app/cbl/COACTUPC.cbl, after an XCTL from app/cbl/COMEN01C.cbl (CoactupcCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CAVW) COMMAREA(WS-COMMAREA) at app/cbl/COACTVWC.cbl:402 -> app/cbl/COACTVWC.cbl, after an XCTL from app/cbl/COMEN01C.cbl (CoactvwcCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CB00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COBIL00C.cbl:146 -> app/cbl/COBIL00C.cbl, after an XCTL from app/cbl/COMEN01C.cbl (Cobil00cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CCLI) COMMAREA(WS-COMMAREA) at app/cbl/COCRDLIC.cbl:615 -> app/cbl/COCRDLIC.cbl, after an XCTL from app/cbl/COMEN01C.cbl (CocrdlicCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CCDL) COMMAREA(WS-COMMAREA) at app/cbl/COCRDSLC.cbl:402 -> app/cbl/COCRDSLC.cbl, after an XCTL from app/cbl/COMEN01C.cbl (CocrdslcCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CCUP) COMMAREA(WS-COMMAREA) at app/cbl/COCRDUPC.cbl:554 -> app/cbl/COCRDUPC.cbl, after an XCTL from app/cbl/COMEN01C.cbl (CocrdupcCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CC00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COSGN00C.cbl:98 -> a program the estate does not resolve, after an XCTL from app/cbl/COMEN01C.cbl (no DTO besides CarddemoCommarea).
     *  out: RETURN TRANSID(CT00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COTRN00C.cbl:138 -> app/cbl/COTRN00C.cbl, after an XCTL from app/cbl/COMEN01C.cbl (Cotrn00cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CT01) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COTRN01C.cbl:136 -> app/cbl/COTRN01C.cbl, after an XCTL from app/cbl/COMEN01C.cbl (Cotrn01cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CT02) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COTRN02C.cbl:156 -> app/cbl/COTRN02C.cbl, after an XCTL from app/cbl/COMEN01C.cbl (Cotrn02cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CT02) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COTRN02C.cbl:530 -> app/cbl/COTRN02C.cbl, after an XCTL from app/cbl/COMEN01C.cbl (Cotrn02cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CU00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COUSR00C.cbl:141 -> app/cbl/COUSR00C.cbl, after an XCTL from app/cbl/COMEN01C.cbl (Cousr00cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CU02) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COUSR02C.cbl:135 -> app/cbl/COUSR02C.cbl, after an XCTL from app/cbl/COMEN01C.cbl (Cousr02cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CU03) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COUSR03C.cbl:134 -> app/cbl/COUSR03C.cbl, after an XCTL from app/cbl/COMEN01C.cbl (Cousr03cCarddemoCommarea besides CarddemoCommarea).
     */
    public Object handleTransaction(String transid, CarddemoCommarea request) {
        log.info("Comen01c: handleTransaction");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "COMEN01C", this::runTask);
        return task.returned(Object.class);
    }

    /** One pseudo-conversational task of this program (#3754): MAIN-PARA and the paragraphs it performs. */
    public void runTask(CicsTask task) {
        new Run(task).mainPara();
    }

    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region
     *  (CicsTask.region()), run through runTask on `request`, passed by reference -- what it changes, the caller sees. */
    public CarddemoCommarea handleLink(CarddemoCommarea request) {
        log.info("Comen01c: handleLink");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("COMEN01C", request);
        region.run(task, "COMEN01C", this::runTask);
        return request;
    }

    /** EXEC CICS XCTL PROGRAM(CDEMO-MENU-OPT-PGMNAME) at app/cbl/COMEN01C.cbl:156, COMMAREA(CARDDEMO-COMMAREA): the target is data-driven (candidates the engine found: COACTUPC (table), COACTVWC (table), COBIL00C (table), COCRDLIC (table), COCRDSLC (table), COCRDUPC (table), COPAUS0C (table), CORPT00C (table), COTRN00C (table), COTRN01C (table), COTRN02C (table)).
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchCdemoMenuOptPgmnameL156(CicsTask task, String program, Object commarea) {
        return task.xctl(program.stripTrailing(), commarea);
    }

    /** EXEC CICS XCTL PROGRAM(CDEMO-MENU-OPT-PGMNAME) at app/cbl/COMEN01C.cbl:184, COMMAREA(CARDDEMO-COMMAREA): the target is data-driven (candidates the engine found: COACTUPC (table), COACTVWC (table), COBIL00C (table), COCRDLIC (table), COCRDSLC (table), COCRDUPC (table), COPAUS0C (table), CORPT00C (table), COTRN00C (table), COTRN01C (table), COTRN02C (table)).
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchCdemoMenuOptPgmnameL184(CicsTask task, String program, Object commarea) {
        return task.xctl(program.stripTrailing(), commarea);
    }

    /** EXEC CICS XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COMEN01C.cbl:201, no COMMAREA: the target is data-driven (candidates the engine found: COSGN00C (moves)).
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchCdemoToProgramL201(CicsTask task, String program) {
        return task.xctl(program.stripTrailing(), null);
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
    private final class Run {
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
                        xctl(dispatchCdemoMenuOptPgmnameL156(task, pgm, commarea));   // XCTL ... COMMAREA, line 156
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
                    xctl(dispatchCdemoMenuOptPgmnameL184(task, pgm, commarea));   // line 184
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
            xctl(dispatchCdemoToProgramL201(task, commarea.getCdemoToProgram()));   // XCTL PROGRAM(CDEMO-TO-PROGRAM), line 201
        }

        /** After an XCTL (its condition): on success the task ends; a failure (PGMIDERR) is unhandled, so CICS abends
         *  the task. */
        private void xctl(String resp) {
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
