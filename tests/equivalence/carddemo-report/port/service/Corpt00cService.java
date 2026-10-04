package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.call.CobolRef;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Corpt0aScreen;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.messaging.TransientData;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Optional;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * WRITEQ at line 517 tests NORMAL
 * The RESP of RECEIVE at line 598 (paragraph RECEIVE-TRNRPT-SCREEN) is never tested (kept: see runTask).
 * Screens (#3619): Corpt0aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Corpt00cService {

    private static final Logger log = LoggerFactory.getLogger(Corpt00cService.class);

    private static final String TRANID = "CR00";          // WS-TRANID
    private static final String PGMNAME = "CORPT00C";     // WS-PGMNAME
    private static final String DATE_FORMAT = "YYYY-MM-DD"; // WS-DATE-FORMAT
    private static final int DFHGREEN = 0xF4;             // DFHBMSCA DFHGREEN
    private static final String TITLE01 = "      AWS Mainframe Modernization       "; // CCDA-TITLE01
    private static final String TITLE02 = "              CardDemo                  "; // CCDA-TITLE02
    private static final String MSG_INVALID_KEY = "Invalid key pressed. Please see below..."; // CCDA-MSG-INVALID-KEY

    private final ObjectProvider<CsutldtcService> csutldtcService;
    private final TransientData transientData;

    /** The program's working storage for one task. */
    private static final class Work {
        String message = spaces(80);                // WS-MESSAGE
        boolean errFlg;                             // WS-ERR-FLG
        boolean sendErase = true;                   // WS-SEND-ERASE-FLG
        boolean endLoop;                            // WS-END-LOOP
        String reportName = spaces(10);             // WS-REPORT-NAME
        String sY = spaces(4), sM = spaces(2), sD = spaces(2);   // WS-START-DATE parts
        String eY = spaces(4), eM = spaces(2), eD = spaces(2);   // WS-END-DATE parts
        String pStart = spaces(10);                 // PARM-START-DATE-1 / -2 (always set together)
        String pEnd = spaces(10);                   // PARM-END-DATE-1 / -2
        Corpt0aScreen scr;                          // CORPT0AI / CORPT0AO share one storage
        CarddemoCommarea ca;                        // CARDDEMO-COMMAREA
        CicsTask.MapSubfields sub = new CicsTask.MapSubfields();

        String startDate() {
            return sY + "-" + sM + "-" + sD;
        }

        String endDate() {
            return eY + "-" + eM + "-" + eD;
        }
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea handleTransaction(String transid, CarddemoCommarea request) {
        log.info("Corpt00c: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of this program (#3754): PROCEDURE DIVISION, MAIN-PARA. */
    public void runTask(CicsTask task) {
        log.info("Corpt00c: runTask");
        Work w = new Work();
        w.scr = loadScreen(null, ' ');      // initial storage of CORPT0AI / CORPT0AO
        w.ca = initialCommarea();

        // MAIN-PARA
        // SET ERR-FLG-OFF / TRANSACT-NOT-EOF / SEND-ERASE-YES are the initial values of Work.
        w.message = spaces(80);
        w.scr.setErrmsg(spaces(78));        // MOVE SPACES TO ERRMSGO OF CORPT0AO

        if (!task.hasCommarea() || Integer.valueOf(0).equals(task.eibcalen())) {   // IF EIBCALEN = 0
            w.ca.setCdemoToProgram("COSGN00C");
            returnToPrevScreen(task, w);
            return;
        }
        copyCommarea(task.commarea(CarddemoCommarea.class), task.eibcalen(), w.ca); // MOVE DFHCOMMAREA(1:EIBCALEN)
        Integer ctx = w.ca.getCdemoPgmContext();
        if (ctx == null || ctx != 1) {                          // IF NOT CDEMO-PGM-REENTER
            w.ca.setCdemoPgmContext(1);
            w.scr = loadScreen(null, '\0');                     // MOVE LOW-VALUES TO CORPT0AO
            w.sub.cursor("MONTHLY");                            // MOVE -1 TO MONTHLYL
            sendTrnrptScreen(task, w);
            return;
        }
        receiveTrnrptScreen(task, w);
        String aid = task.aid();
        if ("ENTER".equals(aid)) {                              // WHEN DFHENTER
            processEnterKey(task, w);
            if (task.ended()) {
                return;
            }
        } else if ("PF3".equals(aid)) {                         // WHEN DFHPF3
            w.ca.setCdemoToProgram("COMEN01C");
            returnToPrevScreen(task, w);
            return;
        } else {                                                // WHEN OTHER
            w.errFlg = true;
            w.sub.cursor("MONTHLY");
            w.message = fit(MSG_INVALID_KEY, 80);
            sendTrnrptScreen(task, w);
            return;
        }
        // DEFECT (kept): unreachable -- every path above ends in SEND-TRNRPT-SCREEN (GO TO RETURN-TO-CICS) or XCTL.
        task.returnTransid(TRANID, w.ca);
    }

    /** Another program LINKed / XCTLed to this one. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea handleLink(CarddemoCommarea request) {
        log.info("Corpt00c: handleLink");
        return request;
    }

    // ---------------------------------------------------------------- PROCESS-ENTER-KEY
    private void processEnterKey(CicsTask task, Work w) {
        Sysout.display("PROCESS ENTER KEY");
        Corpt0aScreen s = w.scr;
        if (!blankOrLow(s.getMonthly())) {                      // WHEN MONTHLYI NOT = SPACES AND LOW-VALUES
            w.reportName = fit("Monthly", 10);
            LocalDateTime now = task.now();                     // MOVE FUNCTION CURRENT-DATE TO WS-CURDATE-DATA
            int year = now.getYear();
            int month = now.getMonthValue();
            w.sY = digits(year, 4);
            w.sM = digits(month, 2);
            w.sD = "01";
            w.pStart = w.startDate();
            month += 1;                                         // MOVE 1 TO DAY; ADD 1 TO MONTH
            if (month > 12) {
                year += 1;
                month = 1;
            }
            // COMPUTE WS-CURDATE-N = DATE-OF-INTEGER(INTEGER-OF-DATE(WS-CURDATE-N) - 1): last day of the month
            LocalDate last = LocalDate.of(year, month, 1).minusDays(1);
            w.eY = digits(last.getYear(), 4);
            w.eM = digits(last.getMonthValue(), 2);
            w.eD = digits(last.getDayOfMonth(), 2);
            w.pEnd = w.endDate();
            submitJobToIntrdr(task, w);
            if (task.ended()) {
                return;
            }
        } else if (!blankOrLow(s.getYearly())) {                // WHEN YEARLYI NOT = SPACES AND LOW-VALUES
            w.reportName = fit("Yearly", 10);
            String y = digits(task.now().getYear(), 4);
            w.sY = y;
            w.eY = y;
            w.sM = "01";
            w.sD = "01";
            w.pStart = w.startDate();
            w.eM = "12";
            w.eD = "31";
            w.pEnd = w.endDate();
            submitJobToIntrdr(task, w);
            if (task.ended()) {
                return;
            }
        } else if (!blankOrLow(s.getCustom())) {               // WHEN CUSTOMI NOT = SPACES AND LOW-VALUES
            if (blankOrLow(s.getSdtmm())) {
                reject(task, w, "Start Date - Month can NOT be empty...", "SDTMM");
                return;
            }
            if (blankOrLow(s.getSdtdd())) {
                reject(task, w, "Start Date - Day can NOT be empty...", "SDTDD");
                return;
            }
            if (blankOrLow(s.getSdtyyyy())) {
                reject(task, w, "Start Date - Year can NOT be empty...", "SDTYYYY");
                return;
            }
            if (blankOrLow(s.getEdtmm())) {
                reject(task, w, "End Date - Month can NOT be empty...", "EDTMM");
                return;
            }
            if (blankOrLow(s.getEdtdd())) {
                reject(task, w, "End Date - Day can NOT be empty...", "EDTDD");
                return;
            }
            if (blankOrLow(s.getEdtyyyy())) {
                reject(task, w, "End Date - Year can NOT be empty...", "EDTYYYY");
                return;
            }
            // COMPUTE WS-NUM-99 / WS-NUM-9999 = FUNCTION NUMVAL-C(...); MOVE it back to the X field
            s.setSdtmm(numvalDigits(s.getSdtmm(), 2));
            s.setSdtdd(numvalDigits(s.getSdtdd(), 2));
            s.setSdtyyyy(numvalDigits(s.getSdtyyyy(), 4));
            s.setEdtmm(numvalDigits(s.getEdtmm(), 2));
            s.setEdtdd(numvalDigits(s.getEdtdd(), 2));
            s.setEdtyyyy(numvalDigits(s.getEdtyyyy(), 4));
            // DEFECT (kept): the values were just rebuilt as digits, so the NOT NUMERIC tests below (and the
            // year ones) can never fire, and month/day '00' pass. Fix: test the field before the NUMVAL-C.
            if (!isNumeric(s.getSdtmm()) || CobolCompare.gt(s.getSdtmm(), "12")) {
                reject(task, w, "Start Date - Not a valid Month...", "SDTMM");
                return;
            }
            if (!isNumeric(s.getSdtdd()) || CobolCompare.gt(s.getSdtdd(), "31")) {
                reject(task, w, "Start Date - Not a valid Day...", "SDTDD");
                return;
            }
            if (!isNumeric(s.getSdtyyyy())) {
                reject(task, w, "Start Date - Not a valid Year...", "SDTYYYY");
                return;
            }
            if (!isNumeric(s.getEdtmm()) || CobolCompare.gt(s.getEdtmm(), "12")) {
                reject(task, w, "End Date - Not a valid Month...", "EDTMM");
                return;
            }
            if (!isNumeric(s.getEdtdd()) || CobolCompare.gt(s.getEdtdd(), "31")) {
                reject(task, w, "End Date - Not a valid Day...", "EDTDD");
                return;
            }
            if (!isNumeric(s.getEdtyyyy())) {
                reject(task, w, "End Date - Not a valid Year...", "EDTYYYY");
                return;
            }
            w.sY = fit(s.getSdtyyyy(), 4);
            w.sM = fit(s.getSdtmm(), 2);
            w.sD = fit(s.getSdtdd(), 2);
            w.eY = fit(s.getEdtyyyy(), 4);
            w.eM = fit(s.getEdtmm(), 2);
            w.eD = fit(s.getEdtdd(), 2);

            if (invalidDate(w.startDate())) {                   // CALL 'CSUTLDTC' (line 392)
                reject(task, w, "Start Date - Not a valid date...", "SDTMM");
                return;
            }
            if (invalidDate(w.endDate())) {                     // CALL 'CSUTLDTC' (line 412)
                reject(task, w, "End Date - Not a valid date...", "EDTMM");
                return;
            }
            w.pStart = w.startDate();
            w.pEnd = w.endDate();
            w.reportName = fit("Custom", 10);
            if (!w.errFlg) {
                submitJobToIntrdr(task, w);
                if (task.ended()) {
                    return;
                }
            }
        } else {                                                // WHEN OTHER
            reject(task, w, "Select a report type to print report...", "MONTHLY");
            return;
        }

        // DEFECT (kept): ERR-FLG-ON is always off here (every error path sends and RETURNs). Fix: none needed.
        if (!w.errFlg) {
            initializeAllFields(w);
            w.sub.color("ERRMSG", DFHGREEN);                    // MOVE DFHGREEN TO ERRMSGC
            stringInto(w, delimBySpace(w.reportName), " report submitted for printing ...");
            w.sub.cursor("MONTHLY");
            sendTrnrptScreen(task, w);
        }
    }

    /** The common error arm: message, WS-ERR-FLG, cursor field, SEND-TRNRPT-SCREEN (which RETURNs). */
    private void reject(CicsTask task, Work w, String text, String cursorField) {
        w.message = fit(text, 80);
        w.errFlg = true;
        w.sub.cursor(cursorField);
        sendTrnrptScreen(task, w);
    }

    /** CALL 'CSUTLDTC': true when the result is neither severity '0000' nor message number '2513'. */
    private boolean invalidDate(String date) {
        CobolRef<String> d = CobolRef.of(fit(date, 10));
        CobolRef<String> f = CobolRef.of(fit(DATE_FORMAT, 10));
        CobolRef<String> r = CobolRef.of(spaces(80));           // MOVE SPACES TO CSUTLDTC-RESULT
        callCsutldtc(d, f, r);
        String res = fit(r.get(), 80);
        String sev = res.substring(0, 4);                       // CSUTLDTC-RESULT-SEV-CD
        String msgNum = res.substring(15, 19);                  // CSUTLDTC-RESULT-MSG-NUM
        if (CobolCompare.eq(sev, "0000")) {
            return false;
        }
        return !CobolCompare.eq(msgNum, "2513");
    }

    // ---------------------------------------------------------------- SUBMIT-JOB-TO-INTRDR
    private void submitJobToIntrdr(CicsTask task, Work w) {
        String confirm = w.scr.getConfirm();
        if (blankOrLow(confirm)) {
            stringInto(w, "Please confirm to print the ", delimBySpace(w.reportName), " report...");
            w.errFlg = true;
            w.sub.cursor("CONFIRM");
            sendTrnrptScreen(task, w);
            return;
        }
        if (!w.errFlg) {
            if (CobolCompare.eq(confirm, "Y") || CobolCompare.eq(confirm, "y")) {
                // CONTINUE
            } else if (CobolCompare.eq(confirm, "N") || CobolCompare.eq(confirm, "n")) {
                initializeAllFields(w);
                w.errFlg = true;
                sendTrnrptScreen(task, w);
                return;
            } else {
                stringInto(w, "\"", delimBySpace(confirm), "\" is not a valid value to confirm...");
                w.errFlg = true;
                w.sub.cursor("CONFIRM");
                sendTrnrptScreen(task, w);
                return;
            }

            w.endLoop = false;
            for (int idx = 1; !(idx > 1000 || w.endLoop || w.errFlg); idx++) {
                String rec = jobLine(w, idx);                   // MOVE JOB-LINES(WS-IDX) TO JCL-RECORD
                if (CobolCompare.eq(rec, "/*EOF") || CobolCompare.eq(rec, "")
                        || CobolCompare.eq(rec, CobolCompare.lowValues(80))) {
                    w.endLoop = true;
                }
                writeJobsubTdq(task, w, rec);
                if (task.ended()) {
                    return;
                }
            }
        }
    }

    /** JOB-LINES(idx): the 80-byte records of JOB-DATA-1 (17 of them; /*EOF is the last). */
    private static String jobLine(Work w, int idx) {
        String line;
        switch (idx) {
            case 1: line = "//TRNRPT00 JOB 'TRAN REPORT',CLASS=A,MSGCLASS=0,"; break;
            case 2: line = "// NOTIFY=&SYSUID"; break;
            case 3: line = "//*"; break;
            case 4: line = "//JOBLIB JCLLIB ORDER=('AWS.M2.CARDDEMO.PROC')"; break;
            case 5: line = "//*"; break;
            case 6: line = "//STEP10 EXEC PROC=TRANREPT"; break;
            case 7: line = "//*"; break;
            case 8: line = "//STEP05R.SYMNAMES DD *"; break;
            case 9: line = "TRAN-CARD-NUM,263,16,ZD"; break;
            case 10: line = "TRAN-PROC-DT,305,10,CH"; break;
            case 11: line = fit("PARM-START-DATE,C'", 18) + fit(w.pStart, 10) + fit("'", 52); break;
            case 12: line = fit("PARM-END-DATE,C'", 16) + fit(w.pEnd, 10) + fit("'", 54); break;
            case 13: line = "/*"; break;
            case 14: line = "//STEP10R.DATEPARM DD *"; break;
            case 15: line = fit(w.pStart, 10) + " " + fit(w.pEnd, 10) + spaces(59); break;
            case 16: line = "/*"; break;
            case 17: line = "/*EOF"; break;
            default: line = spaces(80);   // beyond JOB-DATA-1: never reached, the loop ends at /*EOF
        }
        return fit(line, 80);
    }

    // ---------------------------------------------------------------- WIRTE-JOBSUB-TDQ
    private void writeJobsubTdq(CicsTask task, Work w, String jclRecord) {
        int resp = task.writeqTd("JOBS", jclRecord);
        if (resp != 0) {                                        // WHEN OTHER (not DFHRESP(NORMAL))
            // RESP2 is not exposed by CicsTask.writeqTd: REAS shows zeros.
            Sysout.display("RESP:", Sysout.number(BigDecimal.valueOf(resp), 9, 0, true),
                    "REAS:", Sysout.number(BigDecimal.ZERO, 9, 0, true));
            w.errFlg = true;
            w.message = fit("Unable to Write TDQ (JOBS)...", 80);
            w.sub.cursor("MONTHLY");
            sendTrnrptScreen(task, w);
        }
    }

    // ---------------------------------------------------------------- RETURN-TO-PREV-SCREEN
    private void returnToPrevScreen(CicsTask task, Work w) {
        CarddemoCommarea ca = w.ca;
        String to = ca.getCdemoToProgram();
        if (to == null || blankOrLow(fit(to, 8))) {
            ca.setCdemoToProgram("COSGN00C");
        }
        ca.setCdemoFromTranid(TRANID);
        ca.setCdemoFromProgram(PGMNAME);
        ca.setCdemoPgmContext(0);
        String resp = dispatchCdemoToProgramL548(task, ca.getCdemoToProgram(), ca);   // line 548
        if (!"NORMAL".equals(resp)) {
            task.abendOnCondition(resp);                        // no RESP on the XCTL: default action abends
        }
    }

    // ---------------------------------------------------------------- SEND-TRNRPT-SCREEN / RETURN-TO-CICS
    private void sendTrnrptScreen(CicsTask task, Work w) {
        populateHeaderInfo(task, w);
        w.scr.setErrmsg(fit(w.message, 78));                    // MOVE WS-MESSAGE TO ERRMSGO
        if (w.sendErase) {
            task.sendMap(Corpt0aScreen.MAP, Corpt0aScreen.MAPSET, w.scr, w.sub, "ERASE", "CURSOR");
        } else {
            // DEFECT (kept): unreachable, WS-SEND-ERASE-FLG is only ever set to YES. Fix: none needed.
            task.sendMap(Corpt0aScreen.MAP, Corpt0aScreen.MAPSET, w.scr, w.sub, "CURSOR");
        }
        // GO TO RETURN-TO-CICS
        task.returnTransid(TRANID, w.ca);
    }

    // ---------------------------------------------------------------- RECEIVE-TRNRPT-SCREEN
    private void receiveTrnrptScreen(CicsTask task, Work w) {
        // RESP(WS-RESP-CD) is never tested (kept): on MAPFAIL the program goes on with CORPT0AI as it was.
        Optional<Corpt0aScreen> in = task.receive(Corpt0aScreen.MAP, Corpt0aScreen.MAPSET, Corpt0aScreen.class);
        if (in.isPresent()) {
            w.scr = loadScreen(in.get(), '\0');
        }
    }

    // ---------------------------------------------------------------- POPULATE-HEADER-INFO
    private void populateHeaderInfo(CicsTask task, Work w) {
        LocalDateTime now = task.now();                         // MOVE FUNCTION CURRENT-DATE TO WS-CURDATE-DATA
        Corpt0aScreen s = w.scr;
        s.setTitle01(fit(TITLE01, 40));
        s.setTitle02(fit(TITLE02, 40));
        s.setTrnname(fit(TRANID, 4));
        s.setPgmname(fit(PGMNAME, 8));
        String yyyy = digits(now.getYear(), 4);
        s.setCurdate(digits(now.getMonthValue(), 2) + "/" + digits(now.getDayOfMonth(), 2) + "/" + yyyy.substring(2));
        s.setCurtime(digits(now.getHour(), 2) + ":" + digits(now.getMinute(), 2) + ":" + digits(now.getSecond(), 2));
    }

    // ---------------------------------------------------------------- INITIALIZE-ALL-FIELDS
    private void initializeAllFields(Work w) {
        w.sub.cursor("MONTHLY");                                // MOVE -1 TO MONTHLYL
        Corpt0aScreen s = w.scr;
        s.setMonthly(spaces(1));
        s.setYearly(spaces(1));
        s.setCustom(spaces(1));
        s.setSdtmm(spaces(2));
        s.setSdtdd(spaces(2));
        s.setSdtyyyy(spaces(4));
        s.setEdtmm(spaces(2));
        s.setEdtdd(spaces(2));
        s.setEdtyyyy(spaces(4));
        s.setConfirm(spaces(1));
        w.message = spaces(80);
    }

    // ---------------------------------------------------------------- helpers
    private static CarddemoCommarea initialCommarea() {
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

    /** MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA: only the fields wholly inside EIBCALEN are moved. */
    private static void copyCommarea(CarddemoCommarea src, Integer eibcalen, CarddemoCommarea dst) {
        int len = eibcalen == null ? 160 : Math.min(eibcalen, 160);
        if (len >= 4) dst.setCdemoFromTranid(src.getCdemoFromTranid());
        if (len >= 12) dst.setCdemoFromProgram(src.getCdemoFromProgram());
        if (len >= 16) dst.setCdemoToTranid(src.getCdemoToTranid());
        if (len >= 24) dst.setCdemoToProgram(src.getCdemoToProgram());
        if (len >= 32) dst.setCdemoUserId(src.getCdemoUserId());
        if (len >= 33) dst.setCdemoUserType(src.getCdemoUserType());
        if (len >= 34) dst.setCdemoPgmContext(src.getCdemoPgmContext());
        if (len >= 43) dst.setCdemoCustId(src.getCdemoCustId());
        if (len >= 68) dst.setCdemoCustFname(src.getCdemoCustFname());
        if (len >= 93) dst.setCdemoCustMname(src.getCdemoCustMname());
        if (len >= 118) dst.setCdemoCustLname(src.getCdemoCustLname());
        if (len >= 129) dst.setCdemoAcctId(src.getCdemoAcctId());
        if (len >= 130) dst.setCdemoAcctStatus(src.getCdemoAcctStatus());
        if (len >= 146) dst.setCdemoCardNum(src.getCdemoCardNum());
        if (len >= 153) dst.setCdemoLastMap(src.getCdemoLastMap());
        if (len >= 160) dst.setCdemoLastMapset(src.getCdemoLastMapset());
    }

    /** The shared CORPT0AI / CORPT0AO storage: `src` fields (an absent or empty one holds `absent` bytes). */
    private static Corpt0aScreen loadScreen(Corpt0aScreen src, char absent) {
        Corpt0aScreen s = new Corpt0aScreen();
        s.setTrnname(field(src == null ? null : src.getTrnname(), 4, absent));
        s.setTitle01(field(src == null ? null : src.getTitle01(), 40, absent));
        s.setCurdate(field(src == null ? null : src.getCurdate(), 8, absent));
        s.setPgmname(field(src == null ? null : src.getPgmname(), 8, absent));
        s.setTitle02(field(src == null ? null : src.getTitle02(), 40, absent));
        s.setCurtime(field(src == null ? null : src.getCurtime(), 8, absent));
        s.setMonthly(field(src == null ? null : src.getMonthly(), 1, absent));
        s.setYearly(field(src == null ? null : src.getYearly(), 1, absent));
        s.setCustom(field(src == null ? null : src.getCustom(), 1, absent));
        s.setSdtmm(field(src == null ? null : src.getSdtmm(), 2, absent));
        s.setSdtdd(field(src == null ? null : src.getSdtdd(), 2, absent));
        s.setSdtyyyy(field(src == null ? null : src.getSdtyyyy(), 4, absent));
        s.setEdtmm(field(src == null ? null : src.getEdtmm(), 2, absent));
        s.setEdtdd(field(src == null ? null : src.getEdtdd(), 2, absent));
        s.setEdtyyyy(field(src == null ? null : src.getEdtyyyy(), 4, absent));
        s.setConfirm(field(src == null ? null : src.getConfirm(), 1, absent));
        s.setErrmsg(field(src == null ? null : src.getErrmsg(), 78, absent));
        return s;
    }

    private static String field(String v, int n, char absent) {
        if (v == null || v.isEmpty()) {
            return String.valueOf(absent).repeat(n);
        }
        return fit(v, n);
    }

    /** MOVE to PIC X(n): space padded, truncated on the right. */
    private static String fit(String v, int n) {
        return CobolRecords.fit(v, n, CobolRecords.charset());
    }

    private static String spaces(int n) {
        return " ".repeat(n);
    }

    /** `x = SPACES OR LOW-VALUES` */
    private static boolean blankOrLow(String s) {
        return allOf(s, ' ') || allOf(s, '\0');
    }

    private static boolean allOf(String s, char c) {
        if (s == null || s.isEmpty()) {
            return true;
        }
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) != c) {
                return false;
            }
        }
        return true;
    }

    /** `x IS NUMERIC` for an unsigned alphanumeric item. */
    private static boolean isNumeric(String s) {
        if (s == null || s.isEmpty()) {
            return false;
        }
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < '0' || c > '9') {
                return false;
            }
        }
        return true;
    }

    /** `DELIMITED BY SPACE`: the text up to the first space. */
    private static String delimBySpace(String s) {
        int i = s.indexOf(' ');
        return i < 0 ? s : s.substring(0, i);
    }

    /** STRING ... INTO WS-MESSAGE: overlays the front of the target, the rest is left as it was. */
    private static void stringInto(Work w, String... parts) {
        StringBuilder b = new StringBuilder();
        for (String p : parts) {
            b.append(p);
        }
        String s = b.length() > 80 ? b.substring(0, 80) : b.toString();
        w.message = s + w.message.substring(s.length());
    }

    /** An unsigned PIC 9(n) result: decimals truncated, high-order digits lost, sign dropped; as display digits. */
    private static String digits(long v, int n) {
        return unsignedDigits(BigDecimal.valueOf(v), n);
    }

    private static String unsignedDigits(BigDecimal v, int n) {
        BigInteger x = v.abs().setScale(0, RoundingMode.DOWN).toBigInteger().mod(BigInteger.TEN.pow(n));
        String s = x.toString();
        return "0".repeat(n - s.length()) + s;
    }

    /** COMPUTE WS-NUM-nn = FUNCTION NUMVAL-C(text), then MOVE WS-NUM-nn TO the X field. Invalid text gives 0. */
    private static String numvalDigits(String text, int n) {
        BigDecimal v;
        try {
            v = CobolRecords.numval(text.replace(",", ""), '.');
        } catch (NumberFormatException e) {
            v = BigDecimal.ZERO;
        }
        return unsignedDigits(v, n);
    }

    /** CALL 'CSUTLDTC' at app/cbl/CORPT00C.cbl:392, app/cbl/CORPT00C.cbl:412; the parameters are Csutldtc's USING items.
     *  Call targets open (6 public / 0 private estates); CALL USING open (5 public / 0 private estates). */
    public int callCsutldtc(CobolRef<String> lsDate, CobolRef<String> lsDateFormat, CobolRef<String> lsResult) {
        return csutldtcService.getObject().handleCall(lsDate, lsDateFormat, lsResult);
    }

    /** EXEC CICS XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/CORPT00C.cbl:548, COMMAREA(CARDDEMO-COMMAREA): the target is data-driven (candidates the engine found: COMEN01C (moves), COSGN00C (moves)).
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchCdemoToProgramL548(CicsTask task, String program, Object commarea) {
        return task.xctl(program.stripTrailing(), commarea);
    }

    /** EXEC CICS WRITEQ TD QUEUE('JOBS') FROM(JCL-RECORD) at app/cbl/CORPT00C.cbl:517 (#3620).
     *  Route: reader -- the internal reader (DD INREADER): its records are JCL.
     *  The job submission itself is this service's submit helper (#3622).
     *  CICS resources field testing: open (5 public / 0 private estates). */
    protected void writeqTdJobsL517(String record) {
        transientData.write("JOBS", record);
    }

    /** Job submission at line 517 (#3622). TODO: this program submits job TRNRPT00 through the internal reader, which runs PROC TRANREPT (app/proc/TRANREPT.prc): no generated job matches -- launch its steps. */
    protected void submitTrnrpt00L517() {
    }
}
