package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Cosgn0aScreen;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.SecUserData;
import com.gitgalaxy.modernized.repository.vsam.SecUserDataRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Locale;
import java.util.Optional;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * READ at line 211 tests NORMAL,NOTFND
 * The RESP of RECEIVE at line 110 (paragraph PROCESS-ENTER-KEY) is never tested by the program; kept so.
 * Screens (#3619): Cosgn0aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Cosgn00cService {

    private static final Logger log = LoggerFactory.getLogger(Cosgn00cService.class);

    private static final String WS_PGMNAME = "COSGN00C";
    private static final String WS_TRANID = "CC00";
    private static final String WS_USRSEC_FILE = "USRSEC";
    private static final int COMMAREA_LENGTH = 160;

    // COTTL01Y
    private static final String CCDA_TITLE01 = "      AWS Mainframe Modernization       ";
    private static final String CCDA_TITLE02 = "              CardDemo                  ";
    // CSMSG01Y
    private static final String CCDA_MSG_THANK_YOU = "Thank you for using CardDemo application...      ";
    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed. Please see below...         ";

    private static final DateTimeFormatter MM_DD_YY = DateTimeFormatter.ofPattern("MM/dd/yy", Locale.ROOT);
    private static final DateTimeFormatter HH_MM_SS = DateTimeFormatter.ofPattern("HH:mm:ss", Locale.ROOT);

    private final ObjectProvider<Coadm01cService> coadm01cService;
    private final ObjectProvider<Comen01cService> comen01cService;
    private final SecUserDataRepository secUserDataRepository;

    /** A CICS transaction entered the program (#4343): one task of it in the region (CicsTask.region()),
     *  ENTER pressed -- `request` its COMMAREA, null when started from a cleared screen -- run through runTask. Returns the COMMAREA its RETURN passes on (null: none).
     *  The COMMAREA crosses programs (#4427): COBOL passes bytes, and each program reads them through its
     *  own record, so a port may pass either record -- the facade carries it as Object where a flow
     *  presents another class, and runTask reads it (task.commarea(..)). The flows:
     *  out: RETURN TRANSID(CPVS) COMMAREA(CARDDEMO-COMMAREA) at app/app-authorization-ims-db2-mq/cbl/COPAUS0C.cbl:254 -> app/app-authorization-ims-db2-mq/cbl/COPAUS0C.cbl, after an XCTL from app/cbl/COSGN00C.cbl (Copaus0cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CPVD) COMMAREA(CARDDEMO-COMMAREA) at app/app-authorization-ims-db2-mq/cbl/COPAUS1C.cbl:202 -> app/app-authorization-ims-db2-mq/cbl/COPAUS1C.cbl, after an XCTL from app/cbl/COSGN00C.cbl (Copaus1cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CTLI) COMMAREA(WS-COMMAREA) at app/app-transaction-type-db2/cbl/COTRTLIC.cbl:910 -> app/app-transaction-type-db2/cbl/COTRTLIC.cbl, after an XCTL from app/cbl/COSGN00C.cbl (CotrtlicCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CTTU) COMMAREA(WS-COMMAREA) at app/app-transaction-type-db2/cbl/COTRTUPC.cbl:567 -> app/app-transaction-type-db2/cbl/COTRTUPC.cbl, after an XCTL from app/cbl/COSGN00C.cbl (CotrtupcCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CAUP) COMMAREA(WS-COMMAREA) at app/cbl/COACTUPC.cbl:1015 -> app/cbl/COACTUPC.cbl, after an XCTL from app/cbl/COSGN00C.cbl (CoactupcCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CAVW) COMMAREA(WS-COMMAREA) at app/cbl/COACTVWC.cbl:402 -> app/cbl/COACTVWC.cbl, after an XCTL from app/cbl/COSGN00C.cbl (CoactvwcCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CB00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COBIL00C.cbl:146 -> app/cbl/COBIL00C.cbl, after an XCTL from app/cbl/COSGN00C.cbl (Cobil00cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CCLI) COMMAREA(WS-COMMAREA) at app/cbl/COCRDLIC.cbl:615 -> app/cbl/COCRDLIC.cbl, after an XCTL from app/cbl/COSGN00C.cbl (CocrdlicCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CCDL) COMMAREA(WS-COMMAREA) at app/cbl/COCRDSLC.cbl:402 -> app/cbl/COCRDSLC.cbl, after an XCTL from app/cbl/COSGN00C.cbl (CocrdslcCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CCUP) COMMAREA(WS-COMMAREA) at app/cbl/COCRDUPC.cbl:554 -> app/cbl/COCRDUPC.cbl, after an XCTL from app/cbl/COSGN00C.cbl (CocrdupcCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CT00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COTRN00C.cbl:138 -> app/cbl/COTRN00C.cbl, after an XCTL from app/cbl/COSGN00C.cbl (Cotrn00cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CT01) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COTRN01C.cbl:136 -> app/cbl/COTRN01C.cbl, after an XCTL from app/cbl/COSGN00C.cbl (Cotrn01cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CT02) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COTRN02C.cbl:156 -> app/cbl/COTRN02C.cbl, after an XCTL from app/cbl/COSGN00C.cbl (Cotrn02cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CT02) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COTRN02C.cbl:530 -> app/cbl/COTRN02C.cbl, after an XCTL from app/cbl/COSGN00C.cbl (Cotrn02cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CU00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COUSR00C.cbl:141 -> app/cbl/COUSR00C.cbl, after an XCTL from app/cbl/COSGN00C.cbl (Cousr00cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CU02) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COUSR02C.cbl:135 -> app/cbl/COUSR02C.cbl, after an XCTL from app/cbl/COSGN00C.cbl (Cousr02cCarddemoCommarea besides CarddemoCommarea).
     *  out: RETURN TRANSID(CU03) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COUSR03C.cbl:134 -> app/cbl/COUSR03C.cbl, after an XCTL from app/cbl/COSGN00C.cbl (Cousr03cCarddemoCommarea besides CarddemoCommarea).
     */
    public Object handleTransaction(String transid, CarddemoCommarea request) {
        log.info("Cosgn00c: handleTransaction");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "COSGN00C", this::runTask);
        return task.returned(Object.class);
    }

    /** The program's working storage for one task. */
    private static final class Ws {
        final CicsTask task;
        boolean errFlag;                      // WS-ERR-FLG
        String message = spaces(80);          // WS-MESSAGE
        String userId = spaces(8);            // WS-USER-ID
        String userPwd = spaces(8);           // WS-USER-PWD
        String userIdI = spaces(8);           // USERIDI / USERIDO (same storage)
        String passwdI = spaces(8);           // PASSWDI / PASSWDO
        String sysidArea = spaces(8);         // SYSIDI / SYSIDO
        String cursor;                        // field whose L holds -1 at the SEND
        boolean done;                         // the task has ended (XCTL / RETURN issued)
        final CarddemoCommarea commarea = newCommarea();

        Ws(CicsTask task) {
            this.task = task;
        }
    }

    /** One pseudo-conversational task of COSGN00C (#3754). */
    public void runTask(CicsTask task) {
        Ws ws = new Ws(task);

        // MAIN-PARA
        ws.errFlag = false;                                   // SET ERR-FLG-OFF TO TRUE
        ws.message = spaces(80);                              // MOVE SPACES TO WS-MESSAGE ERRMSGO

        if (!task.hasCommarea() || (task.eibcalen() != null && task.eibcalen() == 0)) {
            // MOVE LOW-VALUES TO COSGN0AO / MOVE -1 TO USERIDL
            ws.userIdI = nulls(8);
            ws.passwdI = nulls(8);
            ws.sysidArea = nulls(8);
            ws.cursor = "USERID";
            sendSignonScreen(ws);
        } else {
            String aid = task.aid();
            if ("ENTER".equals(aid)) {
                processEnterKey(ws);
            } else if ("PF3".equals(aid)) {
                ws.message = CobolRecords.fit(CCDA_MSG_THANK_YOU, 80, CobolRecords.charset());
                sendPlainText(ws);
            } else {
                ws.errFlag = true;
                ws.message = CobolRecords.fit(CCDA_MSG_INVALID_KEY, 80, CobolRecords.charset());
                sendSignonScreen(ws);
            }
        }

        if (!ws.done) {
            // EXEC CICS RETURN TRANSID(WS-TRANID) COMMAREA(CARDDEMO-COMMAREA) LENGTH(160)
            task.returnTransid(WS_TRANID, ws.commarea, COMMAREA_LENGTH);
        }
    }

    // PROCESS-ENTER-KEY
    private void processEnterKey(Ws ws) {
        // EXEC CICS RECEIVE MAP('COSGN0A') MAPSET('COSGN00') RESP(WS-RESP-CD) -- RESP never tested;
        // on MAPFAIL the input storage is left as it was (spaces).
        Optional<Cosgn0aScreen> received = ws.task.receive(Cosgn0aScreen.MAP, Cosgn0aScreen.MAPSET,
                Cosgn0aScreen.class);
        if (received.isPresent()) {
            Cosgn0aScreen in = received.get();
            if (in.getUserid() != null) {
                ws.userIdI = fit(in.getUserid(), 8);
            }
            if (in.getPasswd() != null) {
                ws.passwdI = fit(in.getPasswd(), 8);
            }
            if (in.getSysid() != null) {
                ws.sysidArea = fit(in.getSysid(), 8);
            }
        }

        // EVALUATE TRUE
        if (blankOrLowValues(ws.userIdI)) {
            ws.errFlag = true;
            ws.message = fit("Please enter User ID ...", 80);
            ws.cursor = "USERID";
            sendSignonScreen(ws);
        } else if (blankOrLowValues(ws.passwdI)) {
            ws.errFlag = true;
            ws.message = fit("Please enter Password ...", 80);
            ws.cursor = "PASSWD";
            sendSignonScreen(ws);
        }

        // FUNCTION UPPER-CASE moves (run even after the error sends above, as in the source)
        ws.userId = fit(upper(ws.userIdI), 8);
        ws.commarea.setCdemoUserId(ws.userId);
        ws.userPwd = fit(upper(ws.passwdI), 8);

        if (!ws.errFlag) {
            readUserSecFile(ws);
        }
    }

    // SEND-SIGNON-SCREEN
    private void sendSignonScreen(Ws ws) {
        Cosgn0aScreen screen = new Cosgn0aScreen();

        // POPULATE-HEADER-INFO
        LocalDateTime now = ws.task.now();                    // MOVE FUNCTION CURRENT-DATE
        screen.setTitle01(fit(CCDA_TITLE01, 40));
        screen.setTitle02(fit(CCDA_TITLE02, 40));
        screen.setTrnname(WS_TRANID);
        screen.setPgmname(WS_PGMNAME);
        screen.setCurdate(MM_DD_YY.format(now));              // WS-CURDATE-MM-DD-YY
        screen.setCurtime(HH_MM_SS.format(now));              // WS-CURTIME-HH-MM-SS
        screen.setApplid(ws.task.assignApplid());             // ASSIGN APPLID
        // ASSIGN SYSID writes 4 bytes into the 8-byte SYSIDO; the other 4 keep their previous contents.
        screen.setSysid(ws.task.assignSysid() + ws.sysidArea.substring(4));
        // USERIDO / PASSWDO share storage with USERIDI / PASSWDI
        screen.setUserid(ws.userIdI);
        screen.setPasswd(ws.passwdI);

        screen.setErrmsg(fit(ws.message, 78));                // MOVE WS-MESSAGE TO ERRMSGO

        CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
        if (ws.cursor != null) {
            sub.cursor(ws.cursor);                            // MOVE -1 TO USERIDL / PASSWDL
        }
        ws.task.sendMap(Cosgn0aScreen.MAP, Cosgn0aScreen.MAPSET, screen, sub, "ERASE", "CURSOR");
    }

    // SEND-PLAIN-TEXT
    private void sendPlainText(Ws ws) {
        ws.task.sendText(ws.message, 80, "ERASE", "FREEKB");
        ws.task.returnTransid(null, null);                    // EXEC CICS RETURN
        ws.done = true;
    }

    // READ-USER-SEC-FILE
    private void readUserSecFile(Ws ws) {
        String key = ws.userId;
        CicsTask.FileRead<SecUserData> read = ws.task.read(WS_USRSEC_FILE, () -> readUsrsec(key));

        int resp = read.resp();
        if (resp == 0) {
            SecUserData sec = read.record();
            if (CobolCompare.eq(sec.getSecUsrPwd(), ws.userPwd)) {
                CarddemoCommarea ca = ws.commarea;
                ca.setCdemoFromTranid(fit(WS_TRANID, 4));
                ca.setCdemoFromProgram(fit(WS_PGMNAME, 8));
                ca.setCdemoUserId(ws.userId);
                ca.setCdemoUserType(fit(sec.getSecUsrType(), 1));
                ca.setCdemoPgmContext(0);

                // IF CDEMO-USRTYP-ADMIN (VALUE 'A')
                String target = CobolCompare.eq(ca.getCdemoUserType(), "A") ? "COADM01C" : "COMEN01C";
                String xr = ws.task.xctl(target, ca);
                if (!"NORMAL".equals(xr)) {
                    // no RESP on the XCTL: the condition takes CICS's default action
                    ws.task.abendOnCondition(xr);
                }
                ws.done = true;                               // XCTL does not return here
            } else {
                ws.message = fit("Wrong Password. Try again ...", 80);
                ws.cursor = "PASSWD";
                sendSignonScreen(ws);
            }
        } else if (resp == 13) {
            ws.errFlag = true;
            ws.message = fit("User not found. Try again ...", 80);
            ws.cursor = "USERID";
            sendSignonScreen(ws);
        } else {
            ws.errFlag = true;
            ws.message = fit("Unable to verify the User ...", 80);
            ws.cursor = "USERID";
            sendSignonScreen(ws);
        }
    }

    // ---- helpers -------------------------------------------------------------------------

    private static CarddemoCommarea newCommarea() {
        // WORKING-STORAGE without VALUE: alphanumeric spaces, numeric zeros
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

    private static String spaces(int n) {
        return " ".repeat(n);
    }

    private static String nulls(int n) {
        return "\u0000".repeat(n);
    }

    /** MOVE to PIC X(width): pad with spaces or truncate on the right. */
    private static String fit(String value, int width) {
        return CobolRecords.fit(value, width, CobolRecords.charset());
    }

    /** X = SPACES OR LOW-VALUES for a whole field. */
    private static boolean blankOrLowValues(String s) {
        return s.chars().allMatch(ch -> ch == ' ') || s.chars().allMatch(ch -> ch == 0);
    }

    /** FUNCTION UPPER-CASE: a-z only, byte for byte (never changes the length). */
    private static String upper(String s) {
        StringBuilder b = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            b.append(c >= 'a' && c <= 'z' ? (char) (c - 32) : c);
        }
        return b.toString();
    }

    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region
     *  (CicsTask.region()), run through runTask on `request`, passed by reference -- what it changes, the caller sees. */
    public CarddemoCommarea handleLink(CarddemoCommarea request) {
        log.info("Cosgn00c: handleLink");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("COSGN00C", request);
        region.run(task, "COSGN00C", this::runTask);
        return request;
    }

    /** EXEC CICS XCTL PROGRAM(COADM01C) at app/cbl/COSGN00C.cbl:231. XCTL transfers control: nothing after it runs in the caller.
     *  Call targets field testing: open (6 public / 0 private estates). */
    public CarddemoCommarea xctlCoadm01c(CarddemoCommarea request) {
        return coadm01cService.getObject().handleLink(request);
    }

    /** EXEC CICS XCTL PROGRAM(COMEN01C) at app/cbl/COSGN00C.cbl:236. XCTL transfers control: nothing after it runs in the caller.
     *  Call targets field testing: open (6 public / 0 private estates). */
    public CarddemoCommarea xctlComen01c(CarddemoCommarea request) {
        return comen01cService.getObject().handleLink(request);
    }

    /** AWS.M2.CARDDEMO.USRSEC.VSAM.KSDS as CICS file USRSEC at app/cbl/COSGN00C.cbl:211; VSAM defines field testing: open (3 public / 0 private estates). */
    public Optional<SecUserData> readUsrsec(String key) {
        return secUserDataRepository.findById(key);
    }
}
