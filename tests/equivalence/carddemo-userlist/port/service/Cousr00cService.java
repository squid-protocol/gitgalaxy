package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.Cousr00cCarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.Cousr02cCarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.Cousr03cCarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Cousr0aScreen;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.SecUserData;
import com.gitgalaxy.modernized.repository.vsam.SecUserDataRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.TreeMap;
import java.util.TreeSet;
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

    private static final String TRANID = "CU00";
    private static final String PGMNAME = "COUSR00C";
    private static final String FILE = "USRSEC";
    private static final String TITLE01 = "      AWS Mainframe Modernization       ";
    private static final String TITLE02 = "              CardDemo                  ";
    private static final String MSG_INVALID_KEY = "Invalid key pressed. Please see below...         ";
    private static final Map<String, Integer> WIDTHS = widths();

    private final ObjectProvider<Coadm01cService> coadm01cService;
    private final ObjectProvider<Cosgn00cService> cosgn00cService;
    private final ObjectProvider<Cousr02cService> cousr02cService;
    private final ObjectProvider<Cousr03cService> cousr03cService;
    private final SecUserDataRepository secUserDataRepository;

    private static Map<String, Integer> widths() {
        Map<String, Integer> w = new LinkedHashMap<>();
        for (var f : Cousr0aScreen.LAYOUT) {
            if (f.name() != null) {
                w.put(f.name(), f.length());
            }
        }
        return w;
    }

    /** The business logic of COUSR00C lives in runTask (a CICS program has no batch entry). */
    public void executeCousr00c(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for COUSR00C");
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public Cousr00cCarddemoCommarea handleTransaction(String transid, Cousr00cCarddemoCommarea request) {
        log.info("Cousr00c: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of this program: MAIN-PARA and the paragraphs it performs. */
    public void runTask(CicsTask task) {
        new Session(task).mainPara();
    }

    /** Another program LINKed / XCTLed to this one. TODO: [AI AGENT] implement from the program's business rules. */
    public Cousr00cCarddemoCommarea handleLink(Cousr00cCarddemoCommarea request) {
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
                return cousr02cService.getObject().handleLink((Cousr02cCarddemoCommarea) request);
            case "COUSR03C":
                return cousr03cService.getObject().handleLink((Cousr03cCarddemoCommarea) request);
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
                return cousr02cService.getObject().handleLink((Cousr02cCarddemoCommarea) request);
            case "COUSR03C":
                return cousr03cService.getObject().handleLink((Cousr03cCarddemoCommarea) request);
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
                return cousr02cService.getObject().handleLink((Cousr02cCarddemoCommarea) request);
            case "COUSR03C":
                return cousr03cService.getObject().handleLink((Cousr03cCarddemoCommarea) request);
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
     *  The screen is filled inside runTask (SEND-USRLST-SCREEN). */
    public Cousr0aScreen renderCousr0a(Cousr0aScreen screen) {
        return screen;
    }

    /** RECEIVE MAP(COUSR0A) MAPSET(COUSR00) INTO(COUSR0AI) at app/cbl/COUSR00C.cbl:551 (#3619).
     *  The screen logic is ported in runTask. */
    public ScreenModel submitCousr0a(Cousr0aScreen input, String aid) {
        return renderCousr0a(input);
    }

    /** The working storage of one task. COUSR0AI and COUSR0AO share storage, so one field map serves both. */
    private final class Session {
        final CicsTask task;
        final Charset cs = CobolRecords.charset();
        final Map<String, String> scr = new LinkedHashMap<>();
        Cousr00cCarddemoCommarea comm;
        String message = CobolRecords.fit("", 80, cs);
        boolean errFlg;
        boolean eof;
        boolean sendErase = true;
        boolean ended;
        int respCd;
        int reasCd;   // RESP2 is not exposed by CicsTask's browse calls: stays 0
        int idx;
        String secUsrId = CobolRecords.fit("", 8, cs);
        SecUserData secUser = SecUserData.fromRecord(CobolRecords.blank(80, cs), cs);

        Session(CicsTask task) {
            this.task = task;
            for (String n : WIDTHS.keySet()) {
                put(n, "");
            }
        }

        // ---- storage helpers ----
        String get(String n) {
            return scr.get(n);
        }

        void put(String n, String v) {
            scr.put(n, CobolRecords.fit(v, WIDTHS.get(n), cs));
        }

        void low(String n) {
            scr.put(n, "\0".repeat(WIDTHS.get(n)));
        }

        String f8(String v) {
            return CobolRecords.fit(v, 8, cs);
        }

        void msg(String s) {
            message = CobolRecords.fit(s, 80, cs);
        }

        /** NOT = SPACES AND LOW-VALUES is the negation of this. */
        boolean blankOrLow(String s, int w) {
            String v = CobolRecords.fit(s, w, cs);
            return CobolCompare.eq(v, "") || CobolCompare.eq(v, CobolCompare.lowValues(w));
        }

        String str(String v, int off, int w, int len) {
            return CobolRecords.fit(off < len ? v : null, w, cs);
        }

        /** MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA: bytes past EIBCALEN are spaces. */
        Cousr00cCarddemoCommarea normalize(Cousr00cCarddemoCommarea s, int len) {
            Cousr00cCarddemoCommarea c = new Cousr00cCarddemoCommarea();
            boolean h = s != null;
            c.setCdemoFromTranid(str(h ? s.getCdemoFromTranid() : null, 0, 4, len));
            c.setCdemoFromProgram(str(h ? s.getCdemoFromProgram() : null, 4, 8, len));
            c.setCdemoToTranid(str(h ? s.getCdemoToTranid() : null, 12, 4, len));
            c.setCdemoToProgram(str(h ? s.getCdemoToProgram() : null, 16, 8, len));
            c.setCdemoUserId(str(h ? s.getCdemoUserId() : null, 24, 8, len));
            c.setCdemoUserType(str(h ? s.getCdemoUserType() : null, 32, 1, len));
            c.setCdemoPgmContext(h && 33 < len && s.getCdemoPgmContext() != null ? s.getCdemoPgmContext() : 0);
            c.setCdemoCustId(h && 34 < len && s.getCdemoCustId() != null ? s.getCdemoCustId() : 0);
            c.setCdemoCustFname(str(h ? s.getCdemoCustFname() : null, 43, 25, len));
            c.setCdemoCustMname(str(h ? s.getCdemoCustMname() : null, 68, 25, len));
            c.setCdemoCustLname(str(h ? s.getCdemoCustLname() : null, 93, 25, len));
            c.setCdemoAcctId(h && 118 < len && s.getCdemoAcctId() != null ? s.getCdemoAcctId() : 0L);
            c.setCdemoAcctStatus(str(h ? s.getCdemoAcctStatus() : null, 129, 1, len));
            c.setCdemoCardNum(h && 130 < len && s.getCdemoCardNum() != null ? s.getCdemoCardNum() : 0L);
            c.setCdemoLastMap(str(h ? s.getCdemoLastMap() : null, 146, 7, len));
            c.setCdemoLastMapset(str(h ? s.getCdemoLastMapset() : null, 153, 7, len));
            c.setCdemoCu00UsridFirst(str(h ? s.getCdemoCu00UsridFirst() : null, 160, 8, len));
            c.setCdemoCu00UsridLast(str(h ? s.getCdemoCu00UsridLast() : null, 168, 8, len));
            c.setCdemoCu00PageNum(h && 176 < len && s.getCdemoCu00PageNum() != null ? s.getCdemoCu00PageNum() : 0);
            c.setCdemoCu00NextPageFlg(str(h ? s.getCdemoCu00NextPageFlg() : null, 184, 1, len));
            c.setCdemoCu00UsrSelFlg(str(h ? s.getCdemoCu00UsrSelFlg() : null, 185, 1, len));
            c.setCdemoCu00UsrSelected(str(h ? s.getCdemoCu00UsrSelected() : null, 186, 8, len));
            return c;
        }

        boolean nextPageYes() {
            return CobolCompare.eq(comm.getCdemoCu00NextPageFlg(), "Y");
        }

        void abendOn(int resp) {
            String cond = switch (resp) {
                case 13 -> "NOTFND";
                case 22 -> "LENGERR";
                case 26 -> "ITEMERR";
                case 27 -> "PGMIDERR";
                case 29 -> "ENDDATA";
                case 36 -> "MAPFAIL";
                case 44 -> "QIDERR";
                default -> "INVREQ";
            };
            task.abendOnCondition(cond);
            ended = true;
        }

        // ---- MAIN-PARA ----
        void mainPara() {
            errFlg = false;
            eof = false;
            sendErase = true;
            msg("");
            put("ERRMSG", "");
            // MOVE -1 TO USRIDINL: the cursor goes to USRIDIN on every SEND (see sendUsrlstScreen)

            boolean noCommarea = !task.hasCommarea() || (task.eibcalen() != null && task.eibcalen() == 0);
            if (noCommarea) {
                comm = normalize(null, 0);
                comm.setCdemoCu00NextPageFlg("N");   // SET NEXT-PAGE-NO (nothing overwrites it)
                comm.setCdemoToProgram(f8("COSGN00C"));
                returnToPrevScreen();
                return;
            }
            Integer calen = task.eibcalen();
            int len = calen == null ? 194 : Math.min(calen, 194);
            comm = normalize(task.commarea(Cousr00cCarddemoCommarea.class), len);
            if (comm.getCdemoPgmContext() != 1) {
                comm.setCdemoPgmContext(1);
                for (String n : WIDTHS.keySet()) {
                    low(n);   // MOVE LOW-VALUES TO COUSR0AO
                }
                processEnterKey();
                if (ended) {
                    return;
                }
                sendUsrlstScreen();
            } else {
                receiveUsrlstScreen();
                String aid = task.aid();
                switch (aid) {
                    case "ENTER" -> processEnterKey();
                    case "PF3" -> {
                        comm.setCdemoToProgram(f8("COADM01C"));
                        returnToPrevScreen();
                    }
                    case "PF7" -> processPf7Key();
                    case "PF8" -> processPf8Key();
                    default -> {
                        errFlg = true;
                        msg(MSG_INVALID_KEY);
                        sendUsrlstScreen();
                    }
                }
                if (ended) {
                    return;
                }
            }
            task.returnTransid(TRANID, comm);
        }

        // ---- PROCESS-ENTER-KEY ----
        void processEnterKey() {
            String selFlg = null;
            String selected = null;
            for (int i = 1; i <= 10; i++) {
                String s = get(String.format(Locale.ROOT, "SEL%04d", i));
                if (!blankOrLow(s, 1)) {
                    selFlg = s;
                    selected = get(String.format(Locale.ROOT, "USRID%02d", i));
                    break;
                }
            }
            if (selFlg == null) {
                selFlg = " ";
                selected = CobolRecords.fit("", 8, cs);
            }
            comm.setCdemoCu00UsrSelFlg(CobolRecords.fit(selFlg, 1, cs));
            comm.setCdemoCu00UsrSelected(f8(selected));

            if (!blankOrLow(comm.getCdemoCu00UsrSelFlg(), 1) && !blankOrLow(comm.getCdemoCu00UsrSelected(), 8)) {
                String flg = comm.getCdemoCu00UsrSelFlg();
                if (CobolCompare.eq(flg, "U") || CobolCompare.eq(flg, "u")) {
                    transferTo("COUSR02C");
                    return;
                } else if (CobolCompare.eq(flg, "D") || CobolCompare.eq(flg, "d")) {
                    transferTo("COUSR03C");
                    return;
                } else {
                    msg("Invalid selection. Valid values are U and D");
                }
            }

            String in = get("USRIDIN");
            if (blankOrLow(in, 8)) {
                secUsrId = CobolCompare.lowValues(8);
            } else {
                secUsrId = f8(in);
            }
            comm.setCdemoCu00PageNum(0);
            processPageForward();
            if (ended) {
                return;
            }
            if (!errFlg) {
                put("USRIDIN", " ");
            }
        }

        /** The XCTL of the 'U' / 'D' selections (lines 192-209). */
        void transferTo(String program) {
            comm.setCdemoToProgram(f8(program));
            comm.setCdemoFromTranid(CobolRecords.fit(TRANID, 4, cs));
            comm.setCdemoFromProgram(f8(PGMNAME));
            comm.setCdemoPgmContext(0);
            xctl();
        }

        void xctl() {
            String resp = task.xctl(comm.getCdemoToProgram().stripTrailing(), comm);
            if (!"NORMAL".equals(resp)) {
                task.abendOnCondition(resp);   // no RESP on the XCTL: CICS default action
            }
            ended = true;
        }

        // ---- PROCESS-PF7-KEY ----
        void processPf7Key() {
            if (blankOrLow(comm.getCdemoCu00UsridFirst(), 8)) {
                secUsrId = CobolCompare.lowValues(8);
            } else {
                secUsrId = f8(comm.getCdemoCu00UsridFirst());
            }
            comm.setCdemoCu00NextPageFlg("Y");
            if (comm.getCdemoCu00PageNum() > 1) {
                processPageBackward();
            } else {
                msg("You are already at the top of the page...");
                sendErase = false;
                sendUsrlstScreen();
            }
        }

        // ---- PROCESS-PF8-KEY ----
        void processPf8Key() {
            if (blankOrLow(comm.getCdemoCu00UsridLast(), 8)) {
                secUsrId = "\u00ff".repeat(8);   // HIGH-VALUES
            } else {
                secUsrId = f8(comm.getCdemoCu00UsridLast());
            }
            if (nextPageYes()) {
                processPageForward();
            } else {
                msg("You are already at the bottom of the page...");
                sendErase = false;
                sendUsrlstScreen();
            }
        }

        // ---- PROCESS-PAGE-FORWARD ----
        void processPageForward() {
            startbrUserSecFile();
            if (ended || errFlg) {
                return;
            }
            String aid = task.aid();
            if (!aid.equals("ENTER") && !aid.equals("PF7") && !aid.equals("PF3")) {
                readnextUserSecFile();
            }
            if (!eof && !errFlg) {
                for (idx = 1; idx <= 10; idx++) {
                    initializeUserData();
                }
            }
            idx = 1;
            while (!(idx >= 11 || eof || errFlg)) {
                readnextUserSecFile();
                if (!eof && !errFlg) {
                    populateUserData();
                    idx = idx + 1;
                }
            }
            if (!eof && !errFlg) {
                comm.setCdemoCu00PageNum((comm.getCdemoCu00PageNum() + 1) % 100_000_000);
                readnextUserSecFile();
                comm.setCdemoCu00NextPageFlg(!eof && !errFlg ? "Y" : "N");
            } else {
                comm.setCdemoCu00NextPageFlg("N");
                if (idx > 1) {
                    comm.setCdemoCu00PageNum((comm.getCdemoCu00PageNum() + 1) % 100_000_000);
                }
            }
            endbrUserSecFile();
            if (ended) {
                return;
            }
            put("PAGENUM", Sysout.number(BigDecimal.valueOf(comm.getCdemoCu00PageNum()), 8, 0, false));
            put("USRIDIN", " ");
            sendUsrlstScreen();
        }

        // ---- PROCESS-PAGE-BACKWARD ----
        void processPageBackward() {
            startbrUserSecFile();
            if (ended || errFlg) {
                return;
            }
            String aid = task.aid();
            if (!aid.equals("ENTER") && !aid.equals("PF8")) {
                readprevUserSecFile();
            }
            if (!eof && !errFlg) {
                for (idx = 1; idx <= 10; idx++) {
                    initializeUserData();
                }
            }
            idx = 10;
            while (!(idx <= 0 || eof || errFlg)) {
                readprevUserSecFile();
                if (!eof && !errFlg) {
                    populateUserData();
                    idx = idx - 1;
                }
            }
            if (!eof && !errFlg) {
                readprevUserSecFile();
                if (nextPageYes()) {
                    if (!eof && !errFlg && comm.getCdemoCu00PageNum() > 1) {
                        comm.setCdemoCu00PageNum(comm.getCdemoCu00PageNum() - 1);
                    } else {
                        comm.setCdemoCu00PageNum(1);
                    }
                }
            }
            endbrUserSecFile();
            if (ended) {
                return;
            }
            put("PAGENUM", Sysout.number(BigDecimal.valueOf(comm.getCdemoCu00PageNum()), 8, 0, false));
            sendUsrlstScreen();
        }

        // ---- POPULATE-USER-DATA ----
        void populateUserData() {
            if (idx < 1 || idx > 10) {
                return;   // WHEN OTHER: CONTINUE
            }
            put(String.format(Locale.ROOT, "USRID%02d", idx), secUser.getSecUsrId());
            if (idx == 1) {
                comm.setCdemoCu00UsridFirst(f8(secUser.getSecUsrId()));
            }
            if (idx == 10) {
                comm.setCdemoCu00UsridLast(f8(secUser.getSecUsrId()));
            }
            put(String.format(Locale.ROOT, "FNAME%02d", idx), secUser.getSecUsrFname());
            put(String.format(Locale.ROOT, "LNAME%02d", idx), secUser.getSecUsrLname());
            put(String.format(Locale.ROOT, "UTYPE%02d", idx), secUser.getSecUsrType());
        }

        // ---- INITIALIZE-USER-DATA ----
        void initializeUserData() {
            if (idx < 1 || idx > 10) {
                return;
            }
            put(String.format(Locale.ROOT, "USRID%02d", idx), "");
            put(String.format(Locale.ROOT, "FNAME%02d", idx), "");
            put(String.format(Locale.ROOT, "LNAME%02d", idx), "");
            put(String.format(Locale.ROOT, "UTYPE%02d", idx), "");
        }

        // ---- RETURN-TO-PREV-SCREEN ----
        void returnToPrevScreen() {
            if (blankOrLow(comm.getCdemoToProgram(), 8)) {
                comm.setCdemoToProgram(f8("COSGN00C"));
            }
            comm.setCdemoFromTranid(CobolRecords.fit(TRANID, 4, cs));
            comm.setCdemoFromProgram(f8(PGMNAME));
            comm.setCdemoPgmContext(0);
            xctl();
        }

        // ---- SEND-USRLST-SCREEN ----
        void sendUsrlstScreen() {
            populateHeaderInfo();
            put("ERRMSG", message);
            // MOVE -1 TO USRIDINL holds at every SEND of this program: cursor on USRIDIN
            CicsTask.MapSubfields sub = new CicsTask.MapSubfields().cursor("USRIDIN");
            Cousr0aScreen screen = Cousr0aScreen.fromValues(new LinkedHashMap<>(scr));
            if (sendErase) {
                task.sendMap(Cousr0aScreen.MAP, Cousr0aScreen.MAPSET, screen, sub, "ERASE", "CURSOR");
            } else {
                task.sendMap(Cousr0aScreen.MAP, Cousr0aScreen.MAPSET, screen, sub, "CURSOR");
            }
        }

        // ---- RECEIVE-USRLST-SCREEN ----
        void receiveUsrlstScreen() {
            // RESP is never tested by the program: MAPFAIL leaves the previous screen storage in place
            Optional<Cousr0aScreen> in = task.receive(Cousr0aScreen.MAP, Cousr0aScreen.MAPSET, Cousr0aScreen.class);
            if (in.isPresent()) {
                for (Map.Entry<String, String> e : in.get().screenValues().entrySet()) {
                    put(e.getKey(), e.getValue() == null ? "" : e.getValue());
                }
            }
            respCd = in.isPresent() ? 0 : 36;
            reasCd = 0;
        }

        // ---- POPULATE-HEADER-INFO ----
        void populateHeaderInfo() {
            LocalDateTime now = task.now();
            put("TITLE01", TITLE01);
            put("TITLE02", TITLE02);
            put("TRNNAME", TRANID);
            put("PGMNAME", PGMNAME);
            put("CURDATE", String.format(Locale.ROOT, "%02d/%02d/%02d", now.getMonthValue(), now.getDayOfMonth(),
                    now.getYear() % 100));
            put("CURTIME", String.format(Locale.ROOT, "%02d:%02d:%02d", now.getHour(), now.getMinute(),
                    now.getSecond()));
        }

        // ---- STARTBR-USER-SEC-FILE ----
        void startbrUserSecFile() {
            respCd = task.startbr(FILE, ridfld(), false, () -> new TreeSet<>(usrsec().keySet()));
            if (respCd == 0) {
                return;
            } else if (respCd == 13) {
                eof = true;
                msg("You are at the top of the page...");
                sendUsrlstScreen();
            } else {
                failedLookup();
            }
        }

        // ---- READNEXT-USER-SEC-FILE ----
        void readnextUserSecFile() {
            CicsTask.Browsed b = task.readnext(FILE, ridfld());
            browsed(b, "You have reached the bottom of the page...");
        }

        // ---- READPREV-USER-SEC-FILE ----
        void readprevUserSecFile() {
            CicsTask.Browsed b = task.readprev(FILE, ridfld());
            browsed(b, "You have reached the top of the page...");
        }

        void browsed(CicsTask.Browsed b, String eofMessage) {
            respCd = b.resp();
            if (b.normal()) {
                SecUserData u = usrsec().get(b.key());
                if (u != null) {
                    // READ ... INTO: the program's own copy, RIDFLD follows the key read
                    secUser = SecUserData.fromRecord(u.toRecord(cs), cs);
                    secUsrId = f8(secUser.getSecUsrId());
                }
            } else if (respCd == 20) {
                eof = true;
                msg(eofMessage);
                sendUsrlstScreen();
            } else {
                failedLookup();
            }
        }

        void failedLookup() {
            Sysout.display("RESP:", Sysout.number(BigDecimal.valueOf(respCd), 9, 0, true),
                    "REAS:", Sysout.number(BigDecimal.valueOf(reasCd), 9, 0, true));
            errFlg = true;
            msg("Unable to lookup User...");
            sendUsrlstScreen();
        }

        // ---- ENDBR-USER-SEC-FILE ----
        void endbrUserSecFile() {
            int r = task.endbr(FILE);
            if (r != 0) {
                abendOn(r);   // no RESP on the ENDBR: CICS default action
            }
        }

        /** RIDFLD(SEC-USR-ID): the key as the task's browse holds it (code-page hex; HIGH-VALUES raw). */
        String ridfld() {
            if (secUsrId.chars().allMatch(c -> c == 0xFF)) {
                return secUsrId;
            }
            return CobolRecords.sortKey(secUsrId, "cp037");
        }

        TreeMap<String, SecUserData> usrsec() {
            TreeMap<String, SecUserData> m = new TreeMap<>();
            for (SecUserData u : secUserDataRepository.findAll()) {
                m.put(CobolRecords.sortKey(CobolRecords.fit(u.getSecUsrId(), 8, cs), "cp037"), u);
            }
            return m;
        }
    }

}
