package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea5;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea6;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Cotrn1aScreen;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import com.gitgalaxy.modernized.entity.vsam.CobolEdit;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.TranRecord;
import com.gitgalaxy.modernized.repository.vsam.TranRecordRepository;
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
 * READ at line 269 tests NORMAL,NOTFND
 * The RESP of RECEIVE at line 232 (paragraph RECEIVE-TRNVIEW-SCREEN) is never tested by the program; kept so.
 * Screens (#3619): Cotrn1aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Cotrn01cService {

    private static final Logger log = LoggerFactory.getLogger(Cotrn01cService.class);

    private static final String WS_PGMNAME = "COTRN01C";
    private static final String WS_TRANID = "CT01";
    private static final String CCDA_TITLE01 = "      AWS Mainframe Modernization       ";
    private static final String CCDA_TITLE02 = "              CardDemo                  ";
    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed. Please see below...         ";

    private final ObjectProvider<Comen01cService> comen01cService;
    private final ObjectProvider<Cosgn00cService> cosgn00cService;
    private final ObjectProvider<Cotrn00cService> cotrn00cService;
    private final TranRecordRepository tranRecordRepository;

    /** The program's working storage for one task. */
    private static final class State {
        Cotrn1aScreen scr = lowScreen();     // COTRN1AI / COTRN1AO (one storage, REDEFINES)
        String message = spaces(80);         // WS-MESSAGE
        boolean err;                         // WS-ERR-FLG
        boolean cursor;                      // TRNIDINL = -1
        CarddemoCommarea6 ca = newCommarea(); // CARDDEMO-COMMAREA
        TranRecord tran;                     // TRAN-RECORD (the program's own copy)
    }

    public void executeCotrn01c(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for COTRN01C");
        // The program's business logic is pseudo-conversational and lives in runTask(CicsTask).
    }

    /** A CICS transaction entered the program: the logic is in runTask. */
    public CarddemoCommarea6 handleTransaction(String transid, CarddemoCommarea6 request) {
        log.info("Cotrn01c: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of this program (#3754). */
    public void runTask(CicsTask task) {
        log.info("Cotrn01c: runTask");
        State st = new State();

        // MAIN-PARA
        st.err = false;                       // SET ERR-FLG-OFF
        st.message = spaces(80);              // MOVE SPACES TO WS-MESSAGE
        st.scr.setErrmsg(spaces(78));         //                ERRMSGO

        if (!task.hasCommarea()) {            // IF EIBCALEN = 0
            st.ca.setCdemoToProgram("COSGN00C");
            returnToPrevScreen(task, st);     // PERFORM RETURN-TO-PREV-SCREEN (XCTL never returns)
            return;
        }
        st.ca = copyCommarea(task.commarea(CarddemoCommarea6.class));   // MOVE DFHCOMMAREA(1:EIBCALEN)
        if (!(st.ca.getCdemoPgmContext() != null && st.ca.getCdemoPgmContext() == 1)) {  // NOT CDEMO-PGM-REENTER
            st.ca.setCdemoPgmContext(1);      // SET CDEMO-PGM-REENTER TO TRUE
            st.scr = lowScreen();             // MOVE LOW-VALUES TO COTRN1AO
            st.cursor = true;                 // MOVE -1 TO TRNIDINL
            String sel = st.ca.getCdemoCt01TrnSelected();
            if (!blankOrLow(sel, 16)) {       // NOT = SPACES AND LOW-VALUES
                st.scr.setTrnidin(x(sel, 16));
                processEnterKey(task, st);
            }
            // DEFECT kept: when PROCESS-ENTER-KEY already sent the screen (error), this sends it a second time.
            // Fix: send here only if NOT ERR-FLG-ON.
            sendTrnviewScreen(task, st);
        } else {
            receiveTrnviewScreen(task, st);
            String aid = task.aid();
            if ("ENTER".equals(aid)) {                       // WHEN DFHENTER
                processEnterKey(task, st);
            } else if ("PF3".equals(aid)) {                  // WHEN DFHPF3
                String from = st.ca.getCdemoFromProgram();
                if (blankOrLow(from, 8)) {
                    st.ca.setCdemoToProgram("COMEN01C");
                } else {
                    st.ca.setCdemoToProgram(x(from, 8));
                }
                returnToPrevScreen(task, st);
                return;
            } else if ("PF4".equals(aid)) {                  // WHEN DFHPF4
                clearCurrentScreen(task, st);
            } else if ("PF5".equals(aid)) {                  // WHEN DFHPF5
                st.ca.setCdemoToProgram("COTRN00C");
                returnToPrevScreen(task, st);
                return;
            } else {                                         // WHEN OTHER
                st.err = true;
                st.message = x(CCDA_MSG_INVALID_KEY, 80);
                sendTrnviewScreen(task, st);
            }
        }

        // EXEC CICS RETURN TRANSID(WS-TRANID) COMMAREA(CARDDEMO-COMMAREA)
        task.returnTransid(WS_TRANID, st.ca);
    }

    /** PROCESS-ENTER-KEY */
    private void processEnterKey(CicsTask task, State st) {
        if (blankOrLow(st.scr.getTrnidin(), 16)) {           // WHEN TRNIDINI = SPACES OR LOW-VALUES
            st.err = true;
            st.message = x("Tran ID can NOT be empty...", 80);
            st.cursor = true;
            sendTrnviewScreen(task, st);
        } else {                                             // WHEN OTHER
            st.cursor = true;
        }

        if (!st.err) {
            clearDetailFields(st.scr);
            String tranId = x(st.scr.getTrnidin(), 16);      // MOVE TRNIDINI TO TRAN-ID
            readTransactFile(task, st, tranId);
        }

        if (!st.err) {
            TranRecord t = st.tran;
            Cotrn1aScreen s = st.scr;
            String wsTranAmt = CobolEdit.format("+99999999.99",
                    t.getTranAmt() == null ? BigDecimal.ZERO : t.getTranAmt(), false, null);   // MOVE TRAN-AMT TO WS-TRAN-AMT
            s.setTrnid(x(t.getTranId(), 16));
            s.setCardnum(x(t.getTranCardNum(), 16));
            s.setTtypcd(x(t.getTranTypeCd(), 2));
            s.setTcatcd(Sysout.number(CobolRecords.decimal(t.getTranCatCd()), 4, 0, false));
            s.setTrnsrc(x(t.getTranSource(), 10));
            s.setTrnamt(x(wsTranAmt, 12));
            s.setTdesc(x(t.getTranDesc(), 60));
            s.setTorigdt(x(t.getTranOrigTs(), 10));
            s.setTprocdt(x(t.getTranProcTs(), 10));
            s.setMid(Sysout.number(CobolRecords.decimal(t.getTranMerchantId()), 9, 0, false));
            s.setMname(x(t.getTranMerchantName(), 30));
            s.setMcity(x(t.getTranMerchantCity(), 25));
            s.setMzip(x(t.getTranMerchantZip(), 10));
            sendTrnviewScreen(task, st);
        }
    }

    /** RETURN-TO-PREV-SCREEN */
    private void returnToPrevScreen(CicsTask task, State st) {
        if (blankOrLow(st.ca.getCdemoToProgram(), 8)) {
            st.ca.setCdemoToProgram("COSGN00C");
        }
        st.ca.setCdemoFromTranid(WS_TRANID);
        st.ca.setCdemoFromProgram(WS_PGMNAME);
        st.ca.setCdemoPgmContext(0);
        String program = x(st.ca.getCdemoToProgram(), 8).stripTrailing();
        String resp = task.xctl(program, st.ca);             // XCTL PROGRAM(CDEMO-TO-PROGRAM)
        if (!"NORMAL".equals(resp)) {
            task.abendOnCondition(resp);                     // no RESP coded: CICS default action
        }
    }

    /** SEND-TRNVIEW-SCREEN */
    private void sendTrnviewScreen(CicsTask task, State st) {
        populateHeaderInfo(task, st);
        st.scr.setErrmsg(x(st.message, 78));                 // MOVE WS-MESSAGE TO ERRMSGO
        CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
        if (st.cursor) {
            sub.cursor("TRNIDIN");                           // TRNIDINL = -1
        }
        task.sendMap(Cotrn1aScreen.MAP, Cotrn1aScreen.MAPSET, Cotrn1aScreen.fromValues(st.scr.screenValues()),
                sub, "ERASE", "CURSOR");
    }

    /** RECEIVE-TRNVIEW-SCREEN: RESP / RESP2 are stored by the program and never tested. */
    private void receiveTrnviewScreen(CicsTask task, State st) {
        Optional<Cotrn1aScreen> in = task.receive(Cotrn1aScreen.MAP, Cotrn1aScreen.MAPSET, Cotrn1aScreen.class);
        if (in.isPresent()) {
            st.scr = loadScreen(in.get());
        }
        // MAPFAIL: COTRN1AI keeps its storage.
        // DEFECT kept: the RESP is not tested. Fix: EVALUATE WS-RESP-CD after the RECEIVE.
    }

    /** POPULATE-HEADER-INFO */
    private void populateHeaderInfo(CicsTask task, State st) {
        LocalDateTime now = task.now();                      // FUNCTION CURRENT-DATE
        Cotrn1aScreen s = st.scr;
        s.setTitle01(x(CCDA_TITLE01, 40));
        s.setTitle02(x(CCDA_TITLE02, 40));
        s.setTrnname(x(WS_TRANID, 4));
        s.setPgmname(x(WS_PGMNAME, 8));
        s.setCurdate(String.format(Locale.ROOT, "%02d/%02d/%02d", now.getMonthValue(), now.getDayOfMonth(),
                now.getYear() % 100));
        s.setCurtime(String.format(Locale.ROOT, "%02d:%02d:%02d", now.getHour(), now.getMinute(), now.getSecond()));
    }

    /** READ-TRANSACT-FILE */
    private void readTransactFile(CicsTask task, State st, String tranId) {
        CicsTask.FileRead<TranRecord> read = task.readForUpdate("TRANSACT", () -> readTransact(tranId));
        switch (read.resp()) {
            case 0:                                          // DFHRESP(NORMAL)
                st.tran = TranRecord.fromRecord(read.record().toRecord(CobolRecords.charset()), CobolRecords.charset());
                break;
            case 13:                                         // DFHRESP(NOTFND)
                st.err = true;
                st.message = x("Transaction ID NOT found...", 80);
                st.cursor = true;
                sendTrnviewScreen(task, st);
                break;
            default:                                         // WHEN OTHER
                Sysout.display("RESP:", Sysout.number(BigDecimal.valueOf(read.resp()), 9, 0, true),
                        "REAS:", Sysout.number(BigDecimal.valueOf(read.resp2()), 9, 0, true));
                st.err = true;
                st.message = x("Unable to lookup Transaction...", 80);
                st.cursor = true;
                sendTrnviewScreen(task, st);
                break;
        }
        // DEFECT kept: READ ... UPDATE with no REWRITE / UNLOCK holds the record needlessly. Fix: drop UPDATE.
    }

    /** CLEAR-CURRENT-SCREEN + INITIALIZE-ALL-FIELDS */
    private void clearCurrentScreen(CicsTask task, State st) {
        st.cursor = true;                                    // MOVE -1 TO TRNIDINL
        st.scr.setTrnidin(spaces(16));
        clearDetailFields(st.scr);
        st.scr.setTrnid(spaces(16));
        st.message = spaces(80);
        sendTrnviewScreen(task, st);
    }

    private static void clearDetailFields(Cotrn1aScreen s) {
        s.setTrnid(spaces(16));
        s.setCardnum(spaces(16));
        s.setTtypcd(spaces(2));
        s.setTcatcd(spaces(4));
        s.setTrnsrc(spaces(10));
        s.setTrnamt(spaces(12));
        s.setTdesc(spaces(60));
        s.setTorigdt(spaces(10));
        s.setTprocdt(spaces(10));
        s.setMid(spaces(9));
        s.setMname(spaces(30));
        s.setMcity(spaces(25));
        s.setMzip(spaces(10));
    }

    private static Cotrn1aScreen lowScreen() {
        Cotrn1aScreen s = new Cotrn1aScreen();
        s.setTrnname(low(4));
        s.setTitle01(low(40));
        s.setCurdate(low(8));
        s.setPgmname(low(8));
        s.setTitle02(low(40));
        s.setCurtime(low(8));
        s.setTrnidin(low(16));
        s.setTrnid(low(16));
        s.setCardnum(low(16));
        s.setTtypcd(low(2));
        s.setTcatcd(low(4));
        s.setTrnsrc(low(10));
        s.setTdesc(low(60));
        s.setTrnamt(low(12));
        s.setTorigdt(low(10));
        s.setTprocdt(low(10));
        s.setMid(low(9));
        s.setMname(low(30));
        s.setMcity(low(25));
        s.setMzip(low(10));
        s.setErrmsg(low(78));
        return s;
    }

    /** The received map as the program's storage: each field its width, a field not sent stays low-values. */
    private static Cotrn1aScreen loadScreen(Cotrn1aScreen in) {
        Cotrn1aScreen s = new Cotrn1aScreen();
        s.setTrnname(norm(in.getTrnname(), 4));
        s.setTitle01(norm(in.getTitle01(), 40));
        s.setCurdate(norm(in.getCurdate(), 8));
        s.setPgmname(norm(in.getPgmname(), 8));
        s.setTitle02(norm(in.getTitle02(), 40));
        s.setCurtime(norm(in.getCurtime(), 8));
        s.setTrnidin(norm(in.getTrnidin(), 16));
        s.setTrnid(norm(in.getTrnid(), 16));
        s.setCardnum(norm(in.getCardnum(), 16));
        s.setTtypcd(norm(in.getTtypcd(), 2));
        s.setTcatcd(norm(in.getTcatcd(), 4));
        s.setTrnsrc(norm(in.getTrnsrc(), 10));
        s.setTdesc(norm(in.getTdesc(), 60));
        s.setTrnamt(norm(in.getTrnamt(), 12));
        s.setTorigdt(norm(in.getTorigdt(), 10));
        s.setTprocdt(norm(in.getTprocdt(), 10));
        s.setMid(norm(in.getMid(), 9));
        s.setMname(norm(in.getMname(), 30));
        s.setMcity(norm(in.getMcity(), 25));
        s.setMzip(norm(in.getMzip(), 10));
        s.setErrmsg(norm(in.getErrmsg(), 78));
        return s;
    }

    /** Fresh CARDDEMO-COMMAREA: numeric items start at zero (the first-entry XCTL passes them), CT01-NEXT-PAGE-FLG VALUE 'N'. */
    private static CarddemoCommarea6 newCommarea() {
        CarddemoCommarea6 c = new CarddemoCommarea6();
        c.setCdemoPgmContext(0);
        c.setCdemoCustId(0);
        c.setCdemoAcctId(0L);
        c.setCdemoCardNum(0L);
        c.setCdemoCt01PageNum(0);
        c.setCdemoCt01NextPageFlg("N");                      // VALUE 'N'
        return c;
    }

    private static CarddemoCommarea6 copyCommarea(CarddemoCommarea6 in) {
        CarddemoCommarea6 c = new CarddemoCommarea6();
        c.setCdemoFromTranid(in.getCdemoFromTranid());
        c.setCdemoFromProgram(in.getCdemoFromProgram());
        c.setCdemoToTranid(in.getCdemoToTranid());
        c.setCdemoToProgram(in.getCdemoToProgram());
        c.setCdemoUserId(in.getCdemoUserId());
        c.setCdemoUserType(in.getCdemoUserType());
        c.setCdemoPgmContext(in.getCdemoPgmContext());
        c.setCdemoCustId(in.getCdemoCustId());
        c.setCdemoCustFname(in.getCdemoCustFname());
        c.setCdemoCustMname(in.getCdemoCustMname());
        c.setCdemoCustLname(in.getCdemoCustLname());
        c.setCdemoAcctId(in.getCdemoAcctId());
        c.setCdemoAcctStatus(in.getCdemoAcctStatus());
        c.setCdemoCardNum(in.getCdemoCardNum());
        c.setCdemoLastMap(in.getCdemoLastMap());
        c.setCdemoLastMapset(in.getCdemoLastMapset());
        c.setCdemoCt01TrnidFirst(in.getCdemoCt01TrnidFirst());
        c.setCdemoCt01TrnidLast(in.getCdemoCt01TrnidLast());
        c.setCdemoCt01PageNum(in.getCdemoCt01PageNum());
        c.setCdemoCt01NextPageFlg(in.getCdemoCt01NextPageFlg());
        c.setCdemoCt01TrnSelFlg(in.getCdemoCt01TrnSelFlg());
        c.setCdemoCt01TrnSelected(in.getCdemoCt01TrnSelected());
        return c;
    }

    /** IF x = SPACES OR LOW-VALUES */
    private static boolean blankOrLow(String v, int width) {
        return CobolCompare.eq(v, "") || CobolCompare.eq(v, low(width));
    }

    private static String x(String v, int width) {
        return CobolRecords.fit(v, width, CobolRecords.charset());
    }

    private static String norm(String v, int width) {
        return v == null ? low(width) : x(v, width);
    }

    private static String spaces(int n) {
        return " ".repeat(n);
    }

    private static String low(int n) {
        return "\u0000".repeat(n);
    }

    /** Another program LINKed / XCTLed to this one: the logic is in runTask. */
    public CarddemoCommarea6 handleLink(CarddemoCommarea6 request) {
        log.info("Cotrn01c: handleLink");
        return request;
    }

    /** XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COTRN01C.cbl:205: the target is data-driven. Candidates: COMEN01C (moves), COSGN00C (moves), COTRN00C (moves).
     *  Also MOVEd from CDEMO-FROM-PROGRAM, whose content is not known statically: those names reach the default branch.
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCdemoToProgramL205(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COMEN01C":
                return comen01cService.getObject().handleLink((CarddemoCommarea) request);
            case "COSGN00C":
                cosgn00cService.getObject().handleLink();
                return null;
            case "COTRN00C":
                return cotrn00cService.getObject().handleLink((CarddemoCommarea5) request);
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COTRN01C.cbl:205: no known target " + program);
        }
    }

    /** AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS as CICS file TRANSACT at app/cbl/COTRN01C.cbl:269; VSAM defines field testing: open (3 public / 0 private estates). */
    public Optional<TranRecord> readTransact(String key) {
        return tranRecordRepository.findById(key);
    }

    /** SEND MAP(COTRN1A) MAPSET(COTRN01) FROM(COTRN1AO) at app/cbl/COTRN01C.cbl:219 (#3619); the logic is in runTask. */
    public Cotrn1aScreen renderCotrn1a(Cotrn1aScreen screen) {
        return screen;
    }

    /** RECEIVE MAP(COTRN1A) MAPSET(COTRN01) INTO(COTRN1AI) at app/cbl/COTRN01C.cbl:232 (#3619); the logic is in runTask. */
    public ScreenModel submitCotrn1a(Cotrn1aScreen input, String aid) {
        return renderCotrn1a(input);
    }

}
