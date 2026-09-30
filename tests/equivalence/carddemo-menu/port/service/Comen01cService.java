package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea2;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea4;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea5;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.CoactupcCommarea;
import com.gitgalaxy.modernized.dto.contract.CoactvwcCommarea;
import com.gitgalaxy.modernized.dto.contract.CocrdlicCommarea;
import com.gitgalaxy.modernized.dto.contract.CocrdslcCommarea;
import com.gitgalaxy.modernized.dto.contract.CocrdupcCommarea;
import com.gitgalaxy.modernized.dto.screen.Comen1aScreen;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * INQUIRE at line 148 tests NORMAL
 * The RESP of RECEIVE at line 227 (paragraph RECEIVE-MENU-SCREEN) is never tested (kept as in the source).
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
    private static final String CCDA_TITLE01 = "      AWS Mainframe Modernization       ";
    private static final String CCDA_TITLE02 = "              CardDemo                  ";
    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed. Please see below...         ";
    private static final int CDEMO_MENU_OPT_COUNT = 11;

    /** COMEN02Y: name, program, user type of each CDEMO-MENU-OPT (number = position). */
    private static final String[][] MENU = {
        {"Account View", "COACTVWC", "U"},
        {"Account Update", "COACTUPC", "U"},
        {"Credit Card List", "COCRDLIC", "U"},
        {"Credit Card View", "COCRDSLC", "U"},
        {"Credit Card Update", "COCRDUPC", "U"},
        {"Transaction List", "COTRN00C", "U"},
        {"Transaction View", "COTRN01C", "U"},
        {"Transaction Add", "COTRN02C", "U"},
        {"Transaction Reports", "CORPT00C", "U"},
        {"Bill Payment", "COBIL00C", "U"},
        {"Pending Authorization View", "COPAUS0C", "U"},
    };

    private static final Map<String, Integer> FIELD_LENGTHS = new LinkedHashMap<>();

    static {
        FIELD_LENGTHS.put("TRNNAME", 4);
        FIELD_LENGTHS.put("TITLE01", 40);
        FIELD_LENGTHS.put("CURDATE", 8);
        FIELD_LENGTHS.put("PGMNAME", 8);
        FIELD_LENGTHS.put("TITLE02", 40);
        FIELD_LENGTHS.put("CURTIME", 8);
        for (int i = 1; i <= 12; i++) {
            FIELD_LENGTHS.put(String.format(Locale.ROOT, "OPTN%03d", i), 40);
        }
        FIELD_LENGTHS.put("OPTION", 2);
        FIELD_LENGTHS.put("ERRMSG", 78);
    }

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

    /** The program's working storage for one task. */
    private static final class Ws {
        boolean errFlg;                 // WS-ERR-FLG
        String message = spaces(80);    // WS-MESSAGE
        CarddemoCommarea ca = freshCommarea();  // CARDDEMO-COMMAREA
        Comen1aScreen screen = filled(" ");     // COMEN1AI / COMEN1AO (one storage)
        Integer errmsgColor;            // ERRMSGC OF COMEN1AO, when the program set it
    }

    public void executeComen01c(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for COMEN01C");
        // The business logic of COMEN01C is a pseudo-conversational CICS task: see runTask.
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea handleTransaction(String transid, CarddemoCommarea request) {
        log.info("Comen01c: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of this program (#3754). */
    public void runTask(CicsTask task) {
        log.info("Comen01c: runTask");
        Ws ws = new Ws();

        // MAIN-PARA
        ws.errFlg = false;                                   // SET ERR-FLG-OFF TO TRUE
        ws.message = spaces(80);                             // MOVE SPACES TO WS-MESSAGE
        ws.screen.setErrmsg(spaces(78));                     // ... ERRMSGO OF COMEN1AO

        Integer calen = task.eibcalen();
        if (!task.hasCommarea() || (calen != null && calen == 0)) {
            ws.ca.setCdemoFromProgram(fit("COSGN00C", 8));   // MOVE 'COSGN00C' TO CDEMO-FROM-PROGRAM
            returnToSignonScreen(task, ws);
            // XCTL ended the task (or a failed XCTL abended it): nothing follows.
            return;
        }

        // MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA
        ws.ca = loadCommarea(task.commarea(CarddemoCommarea.class), calen);
        Integer ctx = ws.ca.getCdemoPgmContext();
        boolean reenter = ctx != null && ctx == 1;           // CDEMO-PGM-REENTER

        if (!reenter) {
            ws.ca.setCdemoPgmContext(1);                     // SET CDEMO-PGM-REENTER TO TRUE
            ws.screen = filled("\u0000");                    // MOVE LOW-VALUES TO COMEN1AO
            sendMenuScreen(task, ws);
        } else {
            receiveMenuScreen(task, ws);
            String aid = task.aid();
            if ("ENTER".equals(aid)) {                       // WHEN DFHENTER
                processEnterKey(task, ws);
                if (task.ended()) {
                    return;
                }
            } else if ("PF3".equals(aid)) {                  // WHEN DFHPF3
                ws.ca.setCdemoToProgram(fit("COSGN00C", 8));
                returnToSignonScreen(task, ws);
                return;
            } else {                                         // WHEN OTHER
                ws.errFlg = true;                            // MOVE 'Y' TO WS-ERR-FLG
                ws.message = fit(CCDA_MSG_INVALID_KEY, 80);
                sendMenuScreen(task, ws);
            }
        }

        // EXEC CICS RETURN TRANSID(WS-TRANID) COMMAREA(CARDDEMO-COMMAREA)
        task.returnTransid(WS_TRANID, ws.ca, null);
    }

    /** PROCESS-ENTER-KEY. */
    private void processEnterKey(CicsTask task, Ws ws) {
        String optionI = fit(ws.screen.getOption(), 2);      // OPTIONI OF COMEN1AI
        int idx = 2;                                          // PERFORM VARYING WS-IDX FROM LENGTH OF OPTIONI BY -1
        while (optionI.charAt(idx - 1) == ' ' && idx != 1) {
            idx--;
        }
        String src = optionI.substring(0, idx);
        String optionX = src.length() >= 2 ? src : " " + src;   // MOVE ... TO WS-OPTION-X (JUST RIGHT)
        optionX = optionX.replace(' ', '0');                  // INSPECT ... REPLACING ALL ' ' BY '0'
        boolean numeric = isDigit(optionX.charAt(0)) && isDigit(optionX.charAt(1));
        int option = numeric ? Integer.parseInt(optionX) : -1;   // MOVE WS-OPTION-X TO WS-OPTION
        ws.screen.setOption(optionX);                         // MOVE WS-OPTION TO OPTIONO

        if (!numeric || option > CDEMO_MENU_OPT_COUNT || option == 0) {
            ws.errFlg = true;
            ws.message = fit("Please enter a valid option number...", 80);
            sendMenuScreen(task, ws);
        }
        // Defect kept: no ELSE/GO TO after the invalid-option SEND, so the checks below still run
        // (they are inert because WS-ERR-FLG is on; the table lookup for an option outside 1-11
        // reads storage past the table on the mainframe, taken here as not 'A'). Fix: make the
        // remaining checks an ELSE branch.
        if ("U".equals(fit(ws.ca.getCdemoUserType(), 1)) && "A".equals(menuUserType(option))) {
            ws.errFlg = true;                                 // SET ERR-FLG-ON TO TRUE
            ws.message = fit("No access - Admin Only option... ", 80);
            sendMenuScreen(task, ws);
        }

        if (!ws.errFlg) {
            String[] entry = MENU[option - 1];
            String name = fit(entry[0], 35);
            String pgm = entry[1];
            if (pgm.equals("COPAUS0C")) {
                int resp = task.inquireProgram(pgm);          // EXEC CICS INQUIRE PROGRAM NOHANDLE
                if (resp == 0) {                              // EIBRESP = DFHRESP(NORMAL)
                    ws.ca.setCdemoFromTranid(WS_TRANID);
                    ws.ca.setCdemoFromProgram(fit(WS_PGMNAME, 8));
                    ws.ca.setCdemoPgmContext(0);
                    xctlOrAbend(task, pgm, ws.ca);            // XCTL at line 156
                    return;
                }
                ws.message = spaces(80);
                ws.errmsgColor = DFHRED;
                ws.message = fit("This option " + delimitedBy(name, "  ") + " is not installed...", 80);
            } else if (pgm.startsWith("DUMMY")) {
                // Unreachable with the shipped menu table (no DUMMY entry); kept as in the source.
                ws.message = spaces(80);
                ws.errmsgColor = DFHGREEN;
                ws.message = fit("This option " + delimitedBy(name, " ") + "is coming soon ...", 80);
            } else {
                ws.ca.setCdemoFromTranid(WS_TRANID);
                ws.ca.setCdemoFromProgram(fit(WS_PGMNAME, 8));
                ws.ca.setCdemoPgmContext(0);
                xctlOrAbend(task, pgm, ws.ca);                // XCTL at line 184
                return;
            }
            sendMenuScreen(task, ws);
        }
    }

    /** RETURN-TO-SIGNON-SCREEN. */
    private void returnToSignonScreen(CicsTask task, Ws ws) {
        String to = ws.ca.getCdemoToProgram();
        if (to == null || to.chars().allMatch(c -> c == ' ' || c == 0)) {   // LOW-VALUES OR SPACES
            ws.ca.setCdemoToProgram(fit("COSGN00C", 8));
        }
        // EXEC CICS XCTL PROGRAM(CDEMO-TO-PROGRAM) with no COMMAREA
        String resp = task.xctl(ws.ca.getCdemoToProgram().trim(), null);
        if (!"NORMAL".equals(resp)) {
            task.abendOnCondition(resp);                      // no HANDLE/RESP: CICS default action
        }
    }

    /** SEND-MENU-SCREEN. */
    private void sendMenuScreen(CicsTask task, Ws ws) {
        populateHeaderInfo(ws.screen, task.now());
        buildMenuOptions(ws.screen);
        ws.screen.setErrmsg(fit(ws.message, 78));             // MOVE WS-MESSAGE TO ERRMSGO
        CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
        if (ws.errmsgColor != null) {
            sub.color("ERRMSG", ws.errmsgColor);
        }
        Comen1aScreen sent = Comen1aScreen.fromValues(ws.screen.screenValues());
        task.sendMap(MAP, MAPSET, sent, sub, "ERASE");
    }

    /** RECEIVE-MENU-SCREEN. RESP / RESP2 are stored and never tested (MAPFAIL leaves COMEN1AI as it was). */
    private void receiveMenuScreen(CicsTask task, Ws ws) {
        Optional<Comen1aScreen> in = task.receive(MAP, MAPSET, Comen1aScreen.class);
        if (in.isPresent()) {
            Map<String, String> v = new LinkedHashMap<>(ws.screen.screenValues());
            in.get().screenValues().forEach((k, val) -> {
                if (val != null && FIELD_LENGTHS.containsKey(k)) {
                    v.put(k, fit(val, FIELD_LENGTHS.get(k)));
                }
            });
            ws.screen = Comen1aScreen.fromValues(v);
        }
    }

    /** POPULATE-HEADER-INFO. */
    private static void populateHeaderInfo(Comen1aScreen s, LocalDateTime now) {
        s.setTitle01(fit(CCDA_TITLE01, 40));
        s.setTitle02(fit(CCDA_TITLE02, 40));
        s.setTrnname(fit(WS_TRANID, 4));
        s.setPgmname(fit(WS_PGMNAME, 8));
        s.setCurdate(String.format(Locale.ROOT, "%02d/%02d/%02d",
                now.getMonthValue(), now.getDayOfMonth(), now.getYear() % 100));
        s.setCurtime(String.format(Locale.ROOT, "%02d:%02d:%02d",
                now.getHour(), now.getMinute(), now.getSecond()));
    }

    /** BUILD-MENU-OPTIONS. */
    private static void buildMenuOptions(Comen1aScreen s) {
        for (int idx = 1; idx <= CDEMO_MENU_OPT_COUNT; idx++) {
            String[] e = MENU[idx - 1];
            String txt = fit(String.format(Locale.ROOT, "%02d", idx) + ". " + fit(e[0], 35), 40);
            setOptn(s, idx, txt);
        }
    }

    private static void setOptn(Comen1aScreen s, int idx, String t) {
        switch (idx) {
            case 1 -> s.setOptn001(t);
            case 2 -> s.setOptn002(t);
            case 3 -> s.setOptn003(t);
            case 4 -> s.setOptn004(t);
            case 5 -> s.setOptn005(t);
            case 6 -> s.setOptn006(t);
            case 7 -> s.setOptn007(t);
            case 8 -> s.setOptn008(t);
            case 9 -> s.setOptn009(t);
            case 10 -> s.setOptn010(t);
            case 11 -> s.setOptn011(t);
            case 12 -> s.setOptn012(t);
            default -> { }
        }
    }

    private static String menuUserType(int option) {
        return option >= 1 && option <= MENU.length ? MENU[option - 1][2] : " ";
    }

    private void xctlOrAbend(CicsTask task, String program, CarddemoCommarea ca) {
        String resp = task.xctl(program, ca);
        if (!"NORMAL".equals(resp)) {
            task.abendOnCondition(resp);                      // PGMIDERR / LENGERR: default abend
        }
    }

    // ---- storage helpers -------------------------------------------------------------------

    private static boolean isDigit(char c) {
        return c >= '0' && c <= '9';
    }

    private static String spaces(int n) {
        return " ".repeat(n);
    }

    /** MOVE to PIC X(n): pad with spaces or truncate on the right. */
    private static String fit(String s, int n) {
        String v = s == null ? "" : s;
        return v.length() >= n ? v.substring(0, n) : v + spaces(n - v.length());
    }

    /** STRING ... DELIMITED BY delim: the source up to the first occurrence of delim. */
    private static String delimitedBy(String s, String delim) {
        int i = s.indexOf(delim);
        return i < 0 ? s : s.substring(0, i);
    }

    private static Comen1aScreen filled(String ch) {
        Map<String, String> v = new LinkedHashMap<>();
        FIELD_LENGTHS.forEach((k, n) -> v.put(k, ch.repeat(n)));
        return Comen1aScreen.fromValues(v);
    }

    private static CarddemoCommarea freshCommarea() {
        CarddemoCommarea c = new CarddemoCommarea();
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
        return c;
    }

    /** MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA: the program's own copy; a shorter
     *  COMMAREA leaves the rest spaces (a numeric field cut short is left null: not numeric). */
    private static CarddemoCommarea loadCommarea(CarddemoCommarea s, Integer len) {
        int n = len == null ? 160 : len;
        CarddemoCommarea c = new CarddemoCommarea();
        c.setCdemoFromTranid(cut(s.getCdemoFromTranid(), 0, 4, n));
        c.setCdemoFromProgram(cut(s.getCdemoFromProgram(), 4, 8, n));
        c.setCdemoToTranid(cut(s.getCdemoToTranid(), 12, 4, n));
        c.setCdemoToProgram(cut(s.getCdemoToProgram(), 16, 8, n));
        c.setCdemoUserId(cut(s.getCdemoUserId(), 24, 8, n));
        c.setCdemoUserType(cut(s.getCdemoUserType(), 32, 1, n));
        c.setCdemoPgmContext(n >= 34 ? s.getCdemoPgmContext() : null);
        c.setCdemoCustId(n >= 43 ? s.getCdemoCustId() : null);
        c.setCdemoCustFname(cut(s.getCdemoCustFname(), 43, 25, n));
        c.setCdemoCustMname(cut(s.getCdemoCustMname(), 68, 25, n));
        c.setCdemoCustLname(cut(s.getCdemoCustLname(), 93, 25, n));
        c.setCdemoAcctId(n >= 129 ? s.getCdemoAcctId() : null);
        c.setCdemoAcctStatus(cut(s.getCdemoAcctStatus(), 129, 1, n));
        c.setCdemoCardNum(n >= 146 ? s.getCdemoCardNum() : null);
        c.setCdemoLastMap(cut(s.getCdemoLastMap(), 146, 7, n));
        c.setCdemoLastMapset(cut(s.getCdemoLastMapset(), 153, 7, n));
        return c;
    }

    private static String cut(String v, int off, int flen, int len) {
        int keep = Math.max(0, Math.min(len - off, flen));
        return fit(v, flen).substring(0, keep) + spaces(flen - keep);
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
                return cobil00cService.getObject().handleLink((CarddemoCommarea2) request);
            case "COCRDLIC":
                return cocrdlicService.getObject().handleLink(CocrdlicCommarea.fromPrefix((CarddemoCommarea) request));
            case "COCRDSLC":
                return cocrdslcService.getObject().handleLink(CocrdslcCommarea.fromPrefix((CarddemoCommarea) request));
            case "COCRDUPC":
                return cocrdupcService.getObject().handleLink(CocrdupcCommarea.fromPrefix((CarddemoCommarea) request));
            case "COPAUS0C":
                return copaus0cService.getObject().handleLink((CarddemoCommarea) request);
            case "CORPT00C":
                return corpt00cService.getObject().handleLink((CarddemoCommarea) request);
            case "COTRN00C":
                return cotrn00cService.getObject().handleLink((CarddemoCommarea4) request);
            case "COTRN01C":
                return cotrn01cService.getObject().handleLink((CarddemoCommarea5) request);
            case "COTRN02C":
                return cotrn02cService.getObject().handleLink((CarddemoCommarea) request);
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
                return cobil00cService.getObject().handleLink((CarddemoCommarea2) request);
            case "COCRDLIC":
                return cocrdlicService.getObject().handleLink(CocrdlicCommarea.fromPrefix((CarddemoCommarea) request));
            case "COCRDSLC":
                return cocrdslcService.getObject().handleLink(CocrdslcCommarea.fromPrefix((CarddemoCommarea) request));
            case "COCRDUPC":
                return cocrdupcService.getObject().handleLink(CocrdupcCommarea.fromPrefix((CarddemoCommarea) request));
            case "COPAUS0C":
                return copaus0cService.getObject().handleLink((CarddemoCommarea) request);
            case "CORPT00C":
                return corpt00cService.getObject().handleLink((CarddemoCommarea) request);
            case "COTRN00C":
                return cotrn00cService.getObject().handleLink((CarddemoCommarea4) request);
            case "COTRN01C":
                return cotrn01cService.getObject().handleLink((CarddemoCommarea5) request);
            case "COTRN02C":
                return cotrn02cService.getObject().handleLink((CarddemoCommarea) request);
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
     *  The screen is filled inside runTask (SEND-MENU-SCREEN), which has the task's clock.
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public Comen1aScreen renderComen1a(Comen1aScreen screen) {
        return screen;
    }

    /** RECEIVE MAP(COMEN1A) MAPSET(COMEN01) INTO(COMEN1AI) at app/cbl/COMEN01C.cbl:227 (#3619).
     *  `aid` is the key the user pressed (EIBAID): ENTER, PF1-PF24, CLEAR, PA1-PA3.
     *  The screen logic is ported inside runTask (PROCESS-ENTER-KEY).
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public ScreenModel submitComen1a(Comen1aScreen input, String aid) {
        return renderComen1a(input);
    }

}
