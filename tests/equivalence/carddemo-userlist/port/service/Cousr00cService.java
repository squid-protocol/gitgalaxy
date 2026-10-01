package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea7;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea8;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea9;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Cousr0aScreen;
import com.gitgalaxy.modernized.dto.screen.ScreenField;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.SecUserData;
import com.gitgalaxy.modernized.repository.vsam.SecUserDataRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.NavigableSet;
import java.util.Optional;
import java.util.TreeSet;
import java.util.function.Supplier;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * STARTBR at line 588 tests NORMAL,NOTFND
 * READNEXT at line 621 tests ENDFILE,NORMAL
 * READPREV at line 655 tests ENDFILE,NORMAL
 * TODO: the RESP of RECEIVE at line 551 (paragraph RECEIVE-USRLST-SCREEN) is never tested
 * Screens (#3619): Cousr0aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Cousr00cService {

    private static final Logger log = LoggerFactory.getLogger(Cousr00cService.class);

    private static final String WS_PGMNAME = "COUSR00C";
    private static final String WS_TRANID = "CU00";
    private static final String FILE = "USRSEC";
    private static final String MAP = "COUSR0A";
    private static final String MAPSET = "COUSR00";
    private static final String TITLE01 = "      AWS Mainframe Modernization       ";
    private static final String TITLE02 = "              CardDemo                  ";
    private static final String MSG_INVALID_KEY = "Invalid key pressed. Please see below...         ";

    /** Width of each named screen field (the PIC X(n) of its symbolic-map I/O item). */
    private static final Map<String, Integer> WIDTH = new LinkedHashMap<>();

    static {
        for (ScreenField f : Cousr0aScreen.LAYOUT) {
            if (f.name() != null) {
                WIDTH.put(f.name(), f.length());
            }
        }
    }

    private final ObjectProvider<Coadm01cService> coadm01cService;
    private final ObjectProvider<Cosgn00cService> cosgn00cService;
    private final ObjectProvider<Cousr02cService> cousr02cService;
    private final ObjectProvider<Cousr03cService> cousr03cService;
    private final SecUserDataRepository secUserDataRepository;

    public void executeCousr00c(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for COUSR00C");
        // COUSR00C is a pseudo-conversational CICS program: its PROCEDURE DIVISION is ported in runTask(CicsTask).
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea7 handleTransaction(String transid, CarddemoCommarea7 request) {
        log.info("Cousr00c: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of this program (#3754): MAIN-PARA and the paragraphs it performs. */
    public void runTask(CicsTask task) {
        log.info("Cousr00c: runTask");
        new Run(task).mainPara();
    }

    /** Another program LINKed / XCTLed to this one. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea7 handleLink(CarddemoCommarea7 request) {
        log.info("Cousr00c: handleLink");
        return request;
    }

    /** XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COUSR00C.cbl:196: the target is data-driven. Candidates: COADM01C (moves), COSGN00C (moves), COUSR02C (moves), COUSR03C (moves).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCdemoToProgramL196(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COADM01C":
                return coadm01cService.getObject().handleLink((CarddemoCommarea) request);
            case "COSGN00C":
                cosgn00cService.getObject().handleLink();
                return null;
            case "COUSR02C":
                return cousr02cService.getObject().handleLink((CarddemoCommarea8) request);
            case "COUSR03C":
                return cousr03cService.getObject().handleLink((CarddemoCommarea9) request);
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COUSR00C.cbl:196: no known target " + program);
        }
    }

    /** XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COUSR00C.cbl:206: the target is data-driven. Candidates: COADM01C (moves), COSGN00C (moves), COUSR02C (moves), COUSR03C (moves).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCdemoToProgramL206(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COADM01C":
                return coadm01cService.getObject().handleLink((CarddemoCommarea) request);
            case "COSGN00C":
                cosgn00cService.getObject().handleLink();
                return null;
            case "COUSR02C":
                return cousr02cService.getObject().handleLink((CarddemoCommarea8) request);
            case "COUSR03C":
                return cousr03cService.getObject().handleLink((CarddemoCommarea9) request);
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COUSR00C.cbl:206: no known target " + program);
        }
    }

    /** XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COUSR00C.cbl:514: the target is data-driven. Candidates: COADM01C (moves), COSGN00C (moves), COUSR02C (moves), COUSR03C (moves).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCdemoToProgramL514(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COADM01C":
                return coadm01cService.getObject().handleLink((CarddemoCommarea) request);
            case "COSGN00C":
                cosgn00cService.getObject().handleLink();
                return null;
            case "COUSR02C":
                return cousr02cService.getObject().handleLink((CarddemoCommarea8) request);
            case "COUSR03C":
                return cousr03cService.getObject().handleLink((CarddemoCommarea9) request);
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COUSR00C.cbl:514: no known target " + program);
        }
    }

    /** AWS.M2.CARDDEMO.USRSEC.VSAM.KSDS as CICS file USRSEC at app/cbl/COUSR00C.cbl:588, 621, 655, 689; VSAM defines field testing: open (3 public / 0 private estates). */
    public List<SecUserData> browseUsrsec(String from, int count) {
        return secUserDataRepository.findBySecUsrIdSortGreaterThanEqualOrderBySecUsrIdSortAsc(CobolRecords.sortKey(from, "cp037"), org.springframework.data.domain.PageRequest.of(0, count));
    }

    public List<SecUserData> browseBackUsrsec(String from, int count) {
        return secUserDataRepository.findBySecUsrIdSortLessThanEqualOrderBySecUsrIdSortDesc(CobolRecords.sortKey(from, "cp037"), org.springframework.data.domain.PageRequest.of(0, count));
    }

    /** SEND MAP(COUSR0A) MAPSET(COUSR00) FROM(COUSR0AO) at app/cbl/COUSR00C.cbl:529, app/cbl/COUSR00C.cbl:537 (#3619).
     *  The screen is filled and sent by runTask (SEND-USRLST-SCREEN).
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public Cousr0aScreen renderCousr0a(Cousr0aScreen screen) {
        return screen;
    }

    /** RECEIVE MAP(COUSR0A) MAPSET(COUSR00) INTO(COUSR0AI) at app/cbl/COUSR00C.cbl:551 (#3619).
     *  The receive and what follows it are ported in runTask (MAIN-PARA / RECEIVE-USRLST-SCREEN).
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public ScreenModel submitCousr0a(Cousr0aScreen input, String aid) {
        return renderCousr0a(input);
    }

    // ------------------------------------------------------------------------------------------------
    // helpers (COBOL MOVE / comparison semantics for PIC X items)
    // ------------------------------------------------------------------------------------------------

    private static String spaces(int w) {
        return " ".repeat(w);
    }

    /** MOVE to PIC X(w): pad with spaces or truncate on the right. */
    private static String fit(String s, int w) {
        String v = s == null ? "" : s;
        return v.length() >= w ? v.substring(0, w) : v + " ".repeat(w - v.length());
    }

    private static boolean isSpaces(String s) {
        return CobolCompare.eq(s, "");
    }

    private static boolean isLow(String s) {
        return s != null && !s.isEmpty() && CobolCompare.eq(s, CobolCompare.lowValues(s.length()));
    }

    /** x = SPACES OR LOW-VALUES */
    private static boolean spacesOrLow(String s) {
        return isSpaces(s) || isLow(s);
    }

    /** x NOT = SPACES AND LOW-VALUES */
    private static boolean notSpacesNorLow(String s) {
        return !spacesOrLow(s);
    }

    /** The part of the DFHCOMMAREA field (start, width) that EIBCALEN `n` covers; the rest is spaces. */
    private static String part(String v, int w, int start, int n) {
        if (n >= start + w) {
            return fit(v, w);
        }
        if (n <= start) {
            return spaces(w);
        }
        return fit(v, w).substring(0, n - start) + spaces(start + w - n);
    }

    private static CarddemoCommarea7 widen(Object raw) {
        if (raw instanceof CarddemoCommarea7 c7) {
            return c7;
        }
        CarddemoCommarea7 d = new CarddemoCommarea7();
        if (raw instanceof CarddemoCommarea c) {
            d.setCdemoFromTranid(c.getCdemoFromTranid());
            d.setCdemoFromProgram(c.getCdemoFromProgram());
            d.setCdemoToTranid(c.getCdemoToTranid());
            d.setCdemoToProgram(c.getCdemoToProgram());
            d.setCdemoUserId(c.getCdemoUserId());
            d.setCdemoUserType(c.getCdemoUserType());
            d.setCdemoPgmContext(c.getCdemoPgmContext());
            d.setCdemoCustId(c.getCdemoCustId());
            d.setCdemoCustFname(c.getCdemoCustFname());
            d.setCdemoCustMname(c.getCdemoCustMname());
            d.setCdemoCustLname(c.getCdemoCustLname());
            d.setCdemoAcctId(c.getCdemoAcctId());
            d.setCdemoAcctStatus(c.getCdemoAcctStatus());
            d.setCdemoCardNum(c.getCdemoCardNum());
            d.setCdemoLastMap(c.getCdemoLastMap());
            d.setCdemoLastMapset(c.getCdemoLastMapset());
        }
        return d;
    }

    /** One task of COUSR00C: its WORKING-STORAGE (a fresh copy per task, as CICS gives one) and paragraphs. */
    private final class Run {
        private final CicsTask task;
        private final CarddemoCommarea7 ca = new CarddemoCommarea7();     // CARDDEMO-COMMAREA
        private final Map<String, String> scr = new LinkedHashMap<>();   // COUSR0AI / COUSR0AO (one storage)
        private SecUserData sec = new SecUserData();                     // SEC-USER-DATA (SEC-USR-ID = RIDFLD)
        private String msg = spaces(80);                                 // WS-MESSAGE
        private boolean errOn;                                           // ERR-FLG-ON
        private boolean eof;                                             // USER-SEC-EOF
        private boolean sendErase = true;                                // SEND-ERASE-YES
        private int respCd;                                              // WS-RESP-CD
        private int reasCd;                                              // WS-REAS-CD (see notes)
        private int idx;                                                 // WS-IDX
        private boolean ended;                                           // the task ended (XCTL / ABEND)

        Run(CicsTask task) {
            this.task = task;
            for (Map.Entry<String, Integer> e : WIDTH.entrySet()) {
                scr.put(e.getKey(), spaces(e.getValue()));
            }
            ca.setCdemoFromTranid(spaces(4));
            ca.setCdemoFromProgram(spaces(8));
            ca.setCdemoToTranid(spaces(4));
            ca.setCdemoToProgram(spaces(8));
            ca.setCdemoUserId(spaces(8));
            ca.setCdemoUserType(spaces(1));
            ca.setCdemoPgmContext(0);
            ca.setCdemoCustId(0);
            ca.setCdemoCustFname(spaces(25));
            ca.setCdemoCustMname(spaces(25));
            ca.setCdemoCustLname(spaces(25));
            ca.setCdemoAcctId(0L);
            ca.setCdemoAcctStatus(spaces(1));
            ca.setCdemoCardNum(0L);
            ca.setCdemoLastMap(spaces(7));
            ca.setCdemoLastMapset(spaces(7));
            ca.setCdemoCu00UsridFirst(spaces(8));
            ca.setCdemoCu00UsridLast(spaces(8));
            ca.setCdemoCu00PageNum(0);
            ca.setCdemoCu00NextPageFlg("N");
            ca.setCdemoCu00UsrSelFlg(spaces(1));
            ca.setCdemoCu00UsrSelected(spaces(8));
            sec.setSecUsrId(spaces(8));
            sec.setSecUsrFname(spaces(20));
            sec.setSecUsrLname(spaces(20));
            sec.setSecUsrPwd(spaces(8));
            sec.setSecUsrType(spaces(1));
            sec.setSecUsrFiller(spaces(23));
        }

        private void put(String field, String value) {
            scr.put(field, fit(value, WIDTH.get(field)));
        }

        private int page() {
            return ca.getCdemoCu00PageNum() == null ? 0 : ca.getCdemoCu00PageNum();
        }

        /** COMPUTE / ADD into PIC 9(08): without SIZE ERROR the high-order digits are lost. */
        private void setPage(long v) {
            ca.setCdemoCu00PageNum((int) Math.floorMod(v, 100_000_000L));
        }

        private boolean nextPageYes() {
            return "Y".equals(ca.getCdemoCu00NextPageFlg());
        }

        private boolean aidIs(String a) {
            return a.equals(task.aid());
        }

        // ---------------------------------------------------------------- MAIN-PARA
        void mainPara() {
            errOn = false;                       // SET ERR-FLG-OFF
            eof = false;                         // SET USER-SEC-NOT-EOF
            ca.setCdemoCu00NextPageFlg("N");     // SET NEXT-PAGE-NO
            sendErase = true;                    // SET SEND-ERASE-YES
            msg = spaces(80);                    // MOVE SPACES TO WS-MESSAGE ERRMSGO
            put("ERRMSG", spaces(78));
            // MOVE -1 TO USRIDINL: every SEND below is preceded by this move, see sendUsrlstScreen

            boolean noCommarea = !task.hasCommarea() || (task.eibcalen() != null && task.eibcalen() == 0);
            if (noCommarea) {                                       // IF EIBCALEN = 0
                ca.setCdemoToProgram(fit("COSGN00C", 8));
                returnToPrevScreen();
            } else {
                moveCommarea();                                     // MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA
                if (page0Context() != 1) {                          // IF NOT CDEMO-PGM-REENTER
                    ca.setCdemoPgmContext(1);
                    for (Map.Entry<String, Integer> e : WIDTH.entrySet()) {   // MOVE LOW-VALUES TO COUSR0AO
                        scr.put(e.getKey(), "\u0000".repeat(e.getValue()));
                    }
                    processEnterKey();
                    if (!ended) {
                        sendUsrlstScreen();
                    }
                } else {
                    receiveUsrlstScreen();
                    String aid = task.aid() == null ? "" : task.aid();
                    switch (aid) {                                  // EVALUATE EIBAID
                        case "ENTER":
                            processEnterKey();
                            break;
                        case "PF3":
                            ca.setCdemoToProgram(fit("COADM01C", 8));
                            returnToPrevScreen();
                            break;
                        case "PF7":
                            processPf7Key();
                            break;
                        case "PF8":
                            processPf8Key();
                            break;
                        default:
                            errOn = true;                           // MOVE 'Y' TO WS-ERR-FLG
                            msg = fit(MSG_INVALID_KEY, 80);
                            sendUsrlstScreen();
                    }
                }
            }
            if (!ended) {
                task.returnTransid(WS_TRANID, ca);                  // EXEC CICS RETURN TRANSID COMMAREA
            }
        }

        private int page0Context() {
            return ca.getCdemoPgmContext() == null ? 0 : ca.getCdemoPgmContext();
        }

        /** MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA: a short source pads the rest with spaces. */
        private void moveCommarea() {
            Object raw = task.commarea(Object.class);
            CarddemoCommarea7 s = widen(raw);
            Integer len = task.eibcalen();
            int n = len != null ? len : (raw instanceof CarddemoCommarea ? 160 : 194);
            ca.setCdemoFromTranid(part(s.getCdemoFromTranid(), 4, 0, n));
            ca.setCdemoFromProgram(part(s.getCdemoFromProgram(), 8, 4, n));
            ca.setCdemoToTranid(part(s.getCdemoToTranid(), 4, 12, n));
            ca.setCdemoToProgram(part(s.getCdemoToProgram(), 8, 16, n));
            ca.setCdemoUserId(part(s.getCdemoUserId(), 8, 24, n));
            ca.setCdemoUserType(part(s.getCdemoUserType(), 1, 32, n));
            ca.setCdemoPgmContext(n >= 34 && s.getCdemoPgmContext() != null ? s.getCdemoPgmContext() : 0);
            ca.setCdemoCustId(n >= 43 && s.getCdemoCustId() != null ? s.getCdemoCustId() : 0);
            ca.setCdemoCustFname(part(s.getCdemoCustFname(), 25, 43, n));
            ca.setCdemoCustMname(part(s.getCdemoCustMname(), 25, 68, n));
            ca.setCdemoCustLname(part(s.getCdemoCustLname(), 25, 93, n));
            ca.setCdemoAcctId(n >= 129 && s.getCdemoAcctId() != null ? s.getCdemoAcctId() : 0L);
            ca.setCdemoAcctStatus(part(s.getCdemoAcctStatus(), 1, 129, n));
            ca.setCdemoCardNum(n >= 146 && s.getCdemoCardNum() != null ? s.getCdemoCardNum() : 0L);
            ca.setCdemoLastMap(part(s.getCdemoLastMap(), 7, 146, n));
            ca.setCdemoLastMapset(part(s.getCdemoLastMapset(), 7, 153, n));
            ca.setCdemoCu00UsridFirst(part(s.getCdemoCu00UsridFirst(), 8, 160, n));
            ca.setCdemoCu00UsridLast(part(s.getCdemoCu00UsridLast(), 8, 168, n));
            ca.setCdemoCu00PageNum(n >= 184 && s.getCdemoCu00PageNum() != null ? s.getCdemoCu00PageNum() : 0);
            ca.setCdemoCu00NextPageFlg(part(s.getCdemoCu00NextPageFlg(), 1, 184, n));
            ca.setCdemoCu00UsrSelFlg(part(s.getCdemoCu00UsrSelFlg(), 1, 185, n));
            ca.setCdemoCu00UsrSelected(part(s.getCdemoCu00UsrSelected(), 8, 186, n));
        }

        // ---------------------------------------------------------------- PROCESS-ENTER-KEY
        void processEnterKey() {
            boolean picked = false;
            for (int i = 1; i <= 10; i++) {                         // EVALUATE TRUE, WHEN SEL000nI ...
                String nn = String.format(Locale.ROOT, "%02d", i);
                String sel = scr.get("SEL00" + nn);
                if (notSpacesNorLow(sel)) {
                    ca.setCdemoCu00UsrSelFlg(fit(sel, 1));
                    ca.setCdemoCu00UsrSelected(fit(scr.get("USRID" + nn), 8));
                    picked = true;
                    break;
                }
            }
            if (!picked) {                                          // WHEN OTHER
                ca.setCdemoCu00UsrSelFlg(spaces(1));
                ca.setCdemoCu00UsrSelected(spaces(8));
            }

            if (notSpacesNorLow(ca.getCdemoCu00UsrSelFlg()) && notSpacesNorLow(ca.getCdemoCu00UsrSelected())) {
                switch (ca.getCdemoCu00UsrSelFlg()) {
                    case "U":
                    case "u":
                        ca.setCdemoToProgram(fit("COUSR02C", 8));
                        ca.setCdemoFromTranid(fit(WS_TRANID, 4));
                        ca.setCdemoFromProgram(fit(WS_PGMNAME, 8));
                        ca.setCdemoPgmContext(0);
                        xctl();                                     // XCTL at line 196
                        if (ended) {
                            return;
                        }
                        break;
                    case "D":
                    case "d":
                        ca.setCdemoToProgram(fit("COUSR03C", 8));
                        ca.setCdemoFromTranid(fit(WS_TRANID, 4));
                        ca.setCdemoFromProgram(fit(WS_PGMNAME, 8));
                        ca.setCdemoPgmContext(0);
                        xctl();                                     // XCTL at line 206
                        if (ended) {
                            return;
                        }
                        break;
                    default:
                        msg = fit("Invalid selection. Valid values are U and D", 80);
                }
            }

            String in = scr.get("USRIDIN");
            if (spacesOrLow(in)) {                                  // IF USRIDINI = SPACES OR LOW-VALUES
                sec.setSecUsrId("\u0000".repeat(8));
            } else {
                sec.setSecUsrId(fit(in, 8));
            }
            setPage(0);                                             // MOVE 0 TO CDEMO-CU00-PAGE-NUM
            processPageForward();
            if (ended) {
                return;
            }
            if (!errOn) {
                put("USRIDIN", spaces(8));                          // MOVE SPACE TO USRIDINO
            }
        }

        // ---------------------------------------------------------------- PROCESS-PF7-KEY
        void processPf7Key() {
            if (spacesOrLow(ca.getCdemoCu00UsridFirst())) {
                sec.setSecUsrId("\u0000".repeat(8));
            } else {
                sec.setSecUsrId(fit(ca.getCdemoCu00UsridFirst(), 8));
            }
            ca.setCdemoCu00NextPageFlg("Y");                        // SET NEXT-PAGE-YES
            if (page() > 1) {
                processPageBackward();
            } else {
                msg = fit("You are already at the top of the page...", 80);
                sendErase = false;                                  // SET SEND-ERASE-NO
                sendUsrlstScreen();
            }
        }

        // ---------------------------------------------------------------- PROCESS-PF8-KEY
        void processPf8Key() {
            if (spacesOrLow(ca.getCdemoCu00UsridLast())) {
                // HIGH-VALUES: X'FF' bytes, which is how CicsTask recognises a browse at the end
                sec.setSecUsrId("\u00ff".repeat(8));
            } else {
                sec.setSecUsrId(fit(ca.getCdemoCu00UsridLast(), 8));
            }
            if (nextPageYes()) {
                processPageForward();
            } else {
                msg = fit("You are already at the bottom of the page...", 80);
                sendErase = false;
                sendUsrlstScreen();
            }
        }

        // ---------------------------------------------------------------- PROCESS-PAGE-FORWARD
        void processPageForward() {
            startbrUserSecFile();
            if (ended) {
                return;
            }
            if (!errOn) {
                if (!aidIs("ENTER") && !aidIs("PF7") && !aidIs("PF3")) {
                    readnextUserSecFile();
                }
                if (!eof && !errOn) {
                    for (idx = 1; idx <= 10; idx++) {
                        initializeUserData();
                    }
                }
                idx = 1;
                while (!(idx >= 11 || eof || errOn)) {
                    readnextUserSecFile();
                    if (!eof && !errOn) {
                        populateUserData();
                        idx = idx + 1;
                    }
                }
                if (!eof && !errOn) {
                    setPage(page() + 1);
                    readnextUserSecFile();
                    ca.setCdemoCu00NextPageFlg(!eof && !errOn ? "Y" : "N");
                } else {
                    ca.setCdemoCu00NextPageFlg("N");
                    if (idx > 1) {
                        setPage(page() + 1);
                    }
                }
                endbrUserSecFile();
                if (ended) {
                    return;
                }
                put("PAGENUM", String.format(Locale.ROOT, "%08d", page()));   // MOVE 9(08) TO X(08)
                put("USRIDIN", spaces(8));
                sendUsrlstScreen();
            }
        }

        // ---------------------------------------------------------------- PROCESS-PAGE-BACKWARD
        void processPageBackward() {
            startbrUserSecFile();
            if (ended) {
                return;
            }
            if (!errOn) {
                if (!aidIs("ENTER") && !aidIs("PF8")) {
                    readprevUserSecFile();
                }
                if (!eof && !errOn) {
                    for (idx = 1; idx <= 10; idx++) {
                        initializeUserData();
                    }
                }
                idx = 10;
                while (!(idx <= 0 || eof || errOn)) {
                    readprevUserSecFile();
                    if (!eof && !errOn) {
                        populateUserData();
                        idx = idx - 1;
                    }
                }
                if (!eof && !errOn) {
                    readprevUserSecFile();
                    if (nextPageYes()) {
                        if (!eof && !errOn && page() > 1) {
                            setPage(page() - 1);
                        } else {
                            setPage(1);
                        }
                    }
                }
                endbrUserSecFile();
                if (ended) {
                    return;
                }
                put("PAGENUM", String.format(Locale.ROOT, "%08d", page()));
                sendUsrlstScreen();
            }
        }

        // ---------------------------------------------------------------- POPULATE-USER-DATA
        void populateUserData() {
            if (idx < 1 || idx > 10) {
                return;                                             // WHEN OTHER CONTINUE
            }
            String nn = String.format(Locale.ROOT, "%02d", idx);
            put("USRID" + nn, sec.getSecUsrId());
            if (idx == 1) {
                ca.setCdemoCu00UsridFirst(fit(sec.getSecUsrId(), 8));
            }
            if (idx == 10) {
                ca.setCdemoCu00UsridLast(fit(sec.getSecUsrId(), 8));
            }
            put("FNAME" + nn, sec.getSecUsrFname());
            put("LNAME" + nn, sec.getSecUsrLname());
            put("UTYPE" + nn, sec.getSecUsrType());
        }

        // ---------------------------------------------------------------- INITIALIZE-USER-DATA
        void initializeUserData() {
            if (idx < 1 || idx > 10) {
                return;
            }
            String nn = String.format(Locale.ROOT, "%02d", idx);
            put("USRID" + nn, spaces(8));
            put("FNAME" + nn, spaces(20));
            put("LNAME" + nn, spaces(20));
            put("UTYPE" + nn, spaces(1));
        }

        // ---------------------------------------------------------------- RETURN-TO-PREV-SCREEN
        void returnToPrevScreen() {
            if (spacesOrLow(ca.getCdemoToProgram())) {
                ca.setCdemoToProgram(fit("COSGN00C", 8));
            }
            ca.setCdemoFromTranid(fit(WS_TRANID, 4));
            ca.setCdemoFromProgram(fit(WS_PGMNAME, 8));
            ca.setCdemoPgmContext(0);
            xctl();                                                 // XCTL at line 514
        }

        /** EXEC CICS XCTL PROGRAM(CDEMO-TO-PROGRAM) COMMAREA(CARDDEMO-COMMAREA): no RESP, so a failure abends. */
        private void xctl() {
            String resp = task.xctl(ca.getCdemoToProgram().stripTrailing(), ca);
            if (!"NORMAL".equals(resp)) {
                task.abendOnCondition(resp);                        // PGMIDERR / LENGERR: default action
            }
            ended = true;                                           // XCTL never returns to the program
        }

        // ---------------------------------------------------------------- SEND-USRLST-SCREEN
        void sendUsrlstScreen() {
            populateHeaderInfo();
            put("ERRMSG", msg);                                     // MOVE WS-MESSAGE TO ERRMSGO (80 -> 78)
            CicsTask.MapSubfields sub = new CicsTask.MapSubfields().cursor("USRIDIN");   // MOVE -1 TO USRIDINL
            Cousr0aScreen screen = Cousr0aScreen.fromValues(scr);
            if (sendErase) {
                task.sendMap(MAP, MAPSET, screen, sub, "ERASE", "CURSOR");
            } else {
                task.sendMap(MAP, MAPSET, screen, sub, "CURSOR");
            }
        }

        // ---------------------------------------------------------------- RECEIVE-USRLST-SCREEN
        void receiveUsrlstScreen() {
            Optional<Cousr0aScreen> in = task.receive(MAP, MAPSET, Cousr0aScreen.class);
            respCd = in.isPresent() ? 0 : 36;                       // NORMAL / MAPFAIL; RESP is never tested
            reasCd = 0;
            if (in.isPresent()) {
                for (Map.Entry<String, String> e : in.get().screenValues().entrySet()) {
                    if (e.getValue() != null && WIDTH.containsKey(e.getKey())) {
                        put(e.getKey(), e.getValue());
                    }
                }
            }
        }

        // ---------------------------------------------------------------- POPULATE-HEADER-INFO
        void populateHeaderInfo() {
            LocalDateTime now = task.now();                         // FUNCTION CURRENT-DATE
            put("TITLE01", TITLE01);
            put("TITLE02", TITLE02);
            put("TRNNAME", WS_TRANID);
            put("PGMNAME", WS_PGMNAME);
            put("CURDATE", String.format(Locale.ROOT, "%02d/%02d/%02d",
                    now.getMonthValue(), now.getDayOfMonth(), now.getYear() % 100));
            put("CURTIME", String.format(Locale.ROOT, "%02d:%02d:%02d",
                    now.getHour(), now.getMinute(), now.getSecond()));
        }

        // ---------------------------------------------------------------- STARTBR-USER-SEC-FILE
        void startbrUserSecFile() {
            respCd = task.startbr(FILE, sec.getSecUsrId(), false, keys());   // GTEQ (default)
            switch (respCd) {
                case 0:
                    break;
                case 13:                                            // NOTFND
                    eof = true;
                    msg = fit("You are at the top of the page...", 80);
                    sendUsrlstScreen();
                    break;
                default:
                    lookupError();
            }
        }

        // ---------------------------------------------------------------- READNEXT-USER-SEC-FILE
        void readnextUserSecFile() {
            CicsTask.Browsed b = task.readnext(FILE, sec.getSecUsrId());
            respCd = b.resp();
            intoRecord(b);
            switch (respCd) {
                case 0:
                    break;
                case 20:                                            // ENDFILE
                    eof = true;
                    msg = fit("You have reached the bottom of the page...", 80);
                    sendUsrlstScreen();
                    break;
                default:
                    lookupError();
            }
        }

        // ---------------------------------------------------------------- READPREV-USER-SEC-FILE
        void readprevUserSecFile() {
            CicsTask.Browsed b = task.readprev(FILE, sec.getSecUsrId());
            respCd = b.resp();
            intoRecord(b);
            switch (respCd) {
                case 0:
                    break;
                case 20:
                    eof = true;
                    msg = fit("You have reached the top of the page...", 80);
                    sendUsrlstScreen();
                    break;
                default:
                    lookupError();
            }
        }

        // ---------------------------------------------------------------- ENDBR-USER-SEC-FILE
        void endbrUserSecFile() {
            int r = task.endbr(FILE);                               // no RESP: a failure takes the default action
            if (r != 0) {
                task.abendOnCondition("INVREQ");
                ended = true;
            }
        }

        /** INTO(SEC-USER-DATA) RIDFLD(SEC-USR-ID): the program's own copy of the record read. */
        private void intoRecord(CicsTask.Browsed b) {
            if (!b.normal()) {
                return;                                             // a failed read leaves the previous record
            }
            Optional<SecUserData> rec = secUserDataRepository.findById(b.key());
            if (rec.isPresent()) {
                sec = SecUserData.fromRecord(rec.get().toRecord(CobolRecords.charset()), CobolRecords.charset());
            } else {
                respCd = 13;                                        // key vanished between browse and read
            }
        }

        /** WHEN OTHER of the STARTBR / READNEXT / READPREV EVALUATEs. */
        private void lookupError() {
            Sysout.display("RESP:", Sysout.number(BigDecimal.valueOf(respCd), 9, 0, true),
                    "REAS:", Sysout.number(BigDecimal.valueOf(reasCd), 9, 0, true));
            errOn = true;
            msg = fit("Unable to lookup User...", 80);
            sendUsrlstScreen();
        }

        /** The keys of USRSEC in the EBCDIC order VSAM keeps them. */
        private Supplier<NavigableSet<String>> keys() {
            return () -> {
                TreeSet<String> t = new TreeSet<>((a, b) ->
                        CobolRecords.sortKey(a, "cp037").compareTo(CobolRecords.sortKey(b, "cp037")));
                for (SecUserData u : secUserDataRepository.findAll()) {
                    t.add(u.getSecUsrId());
                }
                return t;
            };
        }
    }
}
