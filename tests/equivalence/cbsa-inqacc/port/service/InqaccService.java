package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.AbndprocDfhcommarea;
import com.gitgalaxy.modernized.dto.contract.InqaccDfhcommarea;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.exception.*;
import com.gitgalaxy.modernized.repository.db2.AccountRepository;
import com.gitgalaxy.modernized.repository.db2.Db2Dates;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * SYNCPOINT at line 682 tests NORMAL
 */
@Service
@Transactional
@RequiredArgsConstructor
public class InqaccService {

    private static final Logger log = LoggerFactory.getLogger(InqaccService.class);

    /** SORTCODE copybook: 77 SORTCODE PIC 9(6) VALUE 987654. */
    private static final int SORTCODE = 987654;
    /** WS-ABEND-PGM PIC X(8) VALUE 'ABNDPROC'. */
    private static final String WS_ABEND_PGM = "ABNDPROC";
    /** NCS-ACC-NO-NAME: 'HBNKACCT' + 6 spaces + 2 spaces. */
    private static final String NCS_ACC_NO_NAME = "HBNKACCT      " + "  ";
    private static final String NOT_STORM_DRAIN = "Not Storm Drain     ";
    /** SQLCODE used when the JDBC call fails: DB2's real code is not known to the port. */
    private static final int SQLCODE_FAILED = -904;
    /** SQLCODE DB2 returns when a NULL column is fetched into a host variable without an indicator. */
    private static final int SQLCODE_NULL_NO_INDICATOR = -305;
    /** Nullable ACCOUNT columns fetched without indicator variables (ACCDB2: all but SORTCODE and NUMBER). */
    private static final String[] NULLABLE_COLUMNS = {
        "ACCOUNT_EYECATCHER", "ACCOUNT_CUSTOMER_NUMBER", "ACCOUNT_TYPE", "ACCOUNT_INTEREST_RATE",
        "ACCOUNT_OPENED", "ACCOUNT_OVERDRAFT_LIMIT", "ACCOUNT_LAST_STATEMENT", "ACCOUNT_NEXT_STATEMENT",
        "ACCOUNT_AVAILABLE_BALANCE", "ACCOUNT_ACTUAL_BALANCE"};

    private final ObjectProvider<AbndprocService> abndprocService;
    private final AccountRepository accountRepository;

    /** The program's WORKING-STORAGE for one task. */
    private static final class Work {
        InqaccDfhcommarea ca;
        int sqlcode;
        int eibresp;
        int eibresp2;
        String stormDrain = "N";                 // WS-STORM-DRAIN
        String sqlstate = "00000";               // SQLCA, never set by the port
        List<Map<String, Object>> rows = List.of();
        // HOST-ACCOUNT-ROW
        String hvEye = "    ";
        String hvCust = "          ";
        String hvSortcode = "      ";
        String hvAccNo = "        ";
        String hvType = "        ";
        BigDecimal hvRate = BigDecimal.ZERO;
        String hvOpened = "          ";
        int hvOverdraft;
        String hvLast = "          ";
        String hvNext = "          ";
        BigDecimal hvAvail = BigDecimal.ZERO;
        BigDecimal hvActual = BigDecimal.ZERO;
        // OUTPUT-DATA (copybook ACCOUNT); dates held as {day, month, year}
        String eye;
        long custNo;
        int sortCode;
        int number;
        String type;
        BigDecimal rate;
        int[] opened;
        int overdraft;
        int[] last;
        int[] next;
        BigDecimal avail;
        BigDecimal actual;

        /** INITIALIZE OUTPUT-DATA */
        void initOutput() {
            eye = "    ";
            custNo = 0;
            sortCode = 0;
            number = 0;
            type = "        ";
            rate = new BigDecimal("0.00");
            opened = new int[3];
            overdraft = 0;
            last = new int[3];
            next = new int[3];
            avail = new BigDecimal("0.00");
            actual = new BigDecimal("0.00");
        }
    }

    /** PROCEDURE DIVISION USING DFHCOMMAREA (section PREMIERE, paragraph A010). */
    public void runTask(CicsTask task) {
        log.info("Inqacc: runTask");
        Work w = new Work();
        w.ca = task.commarea(InqaccDfhcommarea.class);
        InqaccDfhcommarea ca = w.ca;

        // A010: INITIALIZE OUTPUT-DATA
        w.initOutput();
        // A010: EXEC CICS HANDLE ABEND LABEL(ABEND-HANDLING)
        task.handleAbend("ABEND-HANDLING");
        // A010: MOVE SORTCODE TO REQUIRED-SORT-CODE OF ACCOUNT-KY (constant 987654, used below)

        int accno = ca.getInqaccAccno() == null ? 0 : ca.getInqaccAccno();
        boolean stop = accno == 99999999 ? readAccountLast(task, w) : readAccountDb2(task, w, accno);
        if (stop) {
            return;
        }

        // A010: return the ACCOUNT data to the COMMAREA
        if (isSpacesOrLowValues(w.type)) {
            ca.setInqaccSuccess("N");
        } else {
            ca.setInqaccEye(w.eye);
            ca.setInqaccCustno(w.custNo);
            ca.setInqaccScode(w.sortCode);
            ca.setInqaccAccno(w.number);
            ca.setInqaccAccType(w.type);
            ca.setInqaccIntRate(w.rate);
            ca.setInqaccOpened(dateNum(w.opened));
            ca.setInqaccOverdraft(w.overdraft);
            ca.setInqaccLastStmtDt(dateNum(w.last));
            ca.setInqaccNextStmtDt(dateNum(w.next));
            ca.setInqaccAvailBal(w.avail);
            ca.setInqaccActualBal(w.actual);
            ca.setInqaccSuccess("Y");
        }

        // A010: PERFORM GET-ME-OUT-OF-HERE -> GMOFH010: EXEC CICS RETURN (GOBACK is not reached)
        task.returnTransid(null, null);
    }

    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region
     *  (CicsTask.region()), run through runTask on `request`, passed by reference -- what it changes, the caller sees. */
    public InqaccDfhcommarea handleLink(InqaccDfhcommarea request) {
        log.info("Inqacc: handleLink");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("INQACC", request);
        region.run(task, "INQACC", this::runTask);
        return request;
    }

    // ------------------------------------------------------------------ READ-ACCOUNT-DB2 (RAD010)

    /** @return true when the task has ended (abend) and runTask must return. */
    private boolean readAccountDb2(CicsTask task, Work w, int accno) {
        // RAD010: MOVE INQACC-ACCNO TO HV-ACCOUNT-ACC-NO; MOVE SORTCODE TO HV-ACCOUNT-SORTCODE
        w.hvAccNo = String.format(Locale.ROOT, "%08d", accno);
        w.hvSortcode = String.format(Locale.ROOT, "%06d", SORTCODE);

        // RAD010: EXEC SQL OPEN ACC-CURSOR (the query runs here; FETCH reads its first row)
        try {
            w.rows = accountRepository.cursorAccCursorL66Inqacc(
                    Map.of("hvAccountSortcode", w.hvSortcode, "hvAccountAccNo", w.hvAccNo));
            w.sqlcode = 0;
        } catch (DataAccessException e) {
            w.rows = List.of();
            w.sqlcode = SQLCODE_FAILED;
        }
        if (w.sqlcode != 0) {
            String sd = signSeparate(w.sqlcode);
            return abendSequence(task, w, this::dispatchWsAbendPgmL321, "HRAC",
                    "RAD010 -Failure when attempting to OPEN DB2 " + "CURSOR. Check SQLCODE. " + "SQLCODE=" + sd,
                    "Failure when attempting to open DB2 CURSOR " + "ACC-CURSOR. With SQL code=" + sd,
                    true);
        }

        // RAD010: PERFORM FETCH-DATA
        if (fetchData(task, w)) {
            return true;
        }

        // RAD010: EXEC SQL CLOSE ACC-CURSOR
        w.sqlcode = 0;
        if (w.sqlcode != 0) {   // a CLOSE of an open cursor cannot fail here; port kept for review
            String sd = signSeparate(w.sqlcode);
            return abendSequence(task, w, this::dispatchWsAbendPgmL401, "HRAC",
                    "RAD010 -Failure when attempting to CLOSE DB2 " + "CURSOR (ACC-CUSOR). Check SQLCODE" + "SQLCODE=" + sd,
                    "Failure when attempting to close the DB2 CURSOR" + " ACC-CURSOR. With SQL code=" + sd,
                    true);
        }
        return false;
    }

    // ------------------------------------------------------------------ FETCH-DATA (FD010)

    private boolean fetchData(CicsTask task, Work w) {
        // FD010: EXEC SQL FETCH FROM ACC-CURSOR INTO :HV-...
        if (w.rows.isEmpty()) {
            w.sqlcode = 100;
        } else if (hasNullColumn(w.rows.get(0))) {
            // A NULL column fetched into a host variable with no indicator: SQLCODE -305, host variables untouched.
            w.sqlcode = SQLCODE_NULL_NO_INDICATOR;
        } else {
            w.sqlcode = 0;
            loadHostRow(w, w.rows.get(0));
        }

        // FD010: IF SQLCODE = +100 (no data: return a low-value record)
        if (w.sqlcode == 100) {
            w.initOutput();
            w.sortCode = SORTCODE;
            w.number = w.ca.getInqaccAccno() == null ? 0 : w.ca.getInqaccAccno();
            return false;   // GO TO FD999
        }

        // FD010: IF SQLCODE NOT = 0
        if (w.sqlcode != 0) {
            checkForStormDrain(w);
            String sd = signSeparate(w.sqlcode);
            return abendSequence(task, w, this::dispatchWsAbendPgmL516, "HRAC",
                    "FD010 -Failure when attempting to FETCH from " + "DB2 CURSOR (ACC-CURSOR). Check SQLCODE" + "SQLCODE=" + sd,
                    "Failure when attempting to FETCH from the DB2 " + "CURSOR ACC-CURSOR. With SQL code=" + sd,
                    false);
        }

        // FD010: if we found a matching account record
        moveHostToOutput(w);
        return false;
    }

    // ------------------------------------------------------------------ READ-ACCOUNT-LAST / GET-LAST-ACCOUNT-DB2

    private boolean readAccountLast(CicsTask task, Work w) {
        // RAN010: PERFORM GET-LAST-ACCOUNT-DB2
        // GLAD010
        w.initOutput();
        w.hvAccNo = String.format(Locale.ROOT, "%08d", 0);          // MOVE REQUIRED-ACC-NUMBER2 (0)
        w.hvSortcode = String.format(Locale.ROOT, "%06d", SORTCODE); // REQUIRED-SORT-CODE, then SORTCODE
        Map<String, Object> row = null;
        try {
            row = accountRepository.selectL843Inqacc(Map.of("hvAccountSortcode", w.hvSortcode));
            w.sqlcode = hasNullColumn(row) ? SQLCODE_NULL_NO_INDICATOR : 0;
        } catch (EmptyResultDataAccessException e) {
            w.sqlcode = 100;
        } catch (DataAccessException e) {
            w.sqlcode = SQLCODE_FAILED;
        }

        if (w.sqlcode != 0) {   // IF SQLCODE IS NOT EQUAL TO ZERO (+100 included)
            String sd = signSeparate(w.sqlcode);
            return abendSequence(task, w, this::dispatchWsAbendPgmL924, "HNCS",
                    "GLAD010 -ACCOUNT NCS " + NCS_ACC_NO_NAME + " CANNOT be accessed and DB2 " + " SELECT failed. SQLCODE=" + sd,
                    "INQACC - ACCOUNT NCS " + NCS_ACC_NO_NAME + " CANNOT BE ACCESSED AND DB2 SELECT FAILED. SQLCODE=" + sd,
                    false);
        }
        loadHostRow(w, row);
        moveHostToOutput(w);
        // RAN010: MOVE REQUIRED-ACC-NUMBER2 TO NCS-ACC-NO-VALUE: never read afterwards, no output effect.
        return false;
    }

    // ------------------------------------------------------------------ CHECK-FOR-STORM-DRAIN-DB2 (CFSDCD010)

    private void checkForStormDrain(Work w) {
        String condition = w.sqlcode == 923 ? "DB2 Connection lost " : NOT_STORM_DRAIN;
        String sd = signSeparate(w.sqlcode);
        if (!CobolCompare.eq(condition, NOT_STORM_DRAIN)) {
            Sysout.display("INQACC: Check-For-Storm-Drain-DB2: Storm " + "Drain condition (" + condition + ") "
                    + "has been met (" + sd + ").");
        }
    }

    // ------------------------------------------------------------------ ABEND-HANDLING (AH010)

    /** HANDLE ABEND LABEL(ABEND-HANDLING) at line 210: the logic runs in abendHandling(task, work), reached from
     *  runTask when a program LINKed to reports an abend into this program's exit (CicsTask.abendExit()). */
    public void onAbendL210(CicsAbendException e) {
        log.info("HANDLE ABEND LABEL ABEND-HANDLING at line 210", e);
    }

    /** ABEND-HANDLING section. Always ends the task (see the note on the fall-through below). */
    private boolean abendHandling(CicsTask task, Work w) {
        // AH010: EXEC CICS ASSIGN ABCODE(MY-ABEND-CODE)
        String myAbendCode = CobolRecords.fit(task.abcode(), 4, CobolRecords.charset());

        if (CobolCompare.eq(myAbendCode, "AD2Z")) {
            // WHEN 'AD2Z'
            String sd = signSeparate(w.sqlcode);
            Sysout.display("DB2 DEADLOCK DETECTED IN INQACC, SQLCODE=" + sd);
            Sysout.display("DB2 DEADLOCK FOR ACCOUNT " + w.hvAccNo);
            // The SQLCA is not modelled by the port: SQLSTATE 00000, SQLERRML 0 (empty SQLERRMC), SQLERRD all 0.
            String zero = Sysout.number(BigDecimal.ZERO, 9, 0, true);
            Sysout.display("SQLSTATE=" + w.sqlstate + ",SQLERRMC=" + ""
                    + ",SQLERRD(1)=" + zero + ",SQLERRD(2)=" + zero + ",SQLERRD(3)=" + zero
                    + ",SQLERRD(4)=" + zero + ",SQLERRD(5)=" + zero + ",SQLERRD(6)=" + zero);
        } else if (CobolCompare.eq(myAbendCode, "AFCR") || CobolCompare.eq(myAbendCode, "AFCS")
                || CobolCompare.eq(myAbendCode, "AFCT")) {
            // WHEN 'AFCR' / 'AFCS' fall through to the body of WHEN 'AFCT'
            w.stormDrain = "Y";
            Sysout.display("INQACC: Check-For-Storm-Drain-VSAM: Storm " + "Drain condition (Abend " + myAbendCode + ") "
                    + "has been met.");

            // EXEC CICS SYNCPOINT ROLLBACK RESP(WS-CICS-RESP) RESP2(WS-CICS-RESP2)
            task.rollback();
            int resp = 0;
            int resp2 = 0;
            w.eibresp = resp;
            w.eibresp2 = resp2;

            if (resp != 0) {   // IF WS-CICS-RESP NOT = DFHRESP(NORMAL); rollback always answers NORMAL here
                String freeform = "AH010 -Unable to perform SYNCPOINT ROLLBACK." + " Possible integrity issue following VSAM RLS "
                        + " abend." + " EIBRESP=" + signSeparate(w.eibresp) + " RESP2=" + signSeparate(w.eibresp2);
                AbndprocDfhcommarea rec = buildAbndRec(task, w, "HROL", 0, freeform);
                if (linkAbndproc(task, w, rec, this::dispatchWsAbendPgmL738)) {
                    return true;
                }
                Sysout.display("INQACC: Unable to perform Syncpoint " + "Rollback. Possible Integrity issue "
                        + " following VSAM RLS abend. " + " RESP CODE=" + Sysout.number(BigDecimal.valueOf(resp), 8, 0, true)
                        + " RESP2 CODE=" + Sysout.number(BigDecimal.valueOf(resp2), 8, 0, true));
                task.abendCancel("HROL");
                return true;
            }

            // MOVE 'N' TO INQACC-SUCCESS; EXEC CICS RETURN
            w.ca.setInqaccSuccess("N");
            task.returnTransid(null, null);
            return true;
        }

        // AH010: IF WS-STORM-DRAIN = 'N'
        if ("N".equals(w.stormDrain)) {
            String freeform = "AH010 -WVS-STORM-DRAIN=N" + " EIBRESP=" + signSeparate(w.eibresp) + " RESP2=" + signSeparate(w.eibresp2);
            AbndprocDfhcommarea rec = buildAbndRec(task, w, myAbendCode, 0, freeform);
            if (linkAbndproc(task, w, rec, this::dispatchWsAbendPgmL810)) {
                return true;
            }
            task.abendCancel(myAbendCode);
            return true;
        }
        // DEFECT (kept): had WS-STORM-DRAIN been 'Y' without the AFC* branch (impossible: that branch sets it and
        // RETURNs), control would fall off AH999 into READ-ACCOUNT-LAST. Unreachable; fix: end the section with a GOBACK.
        return true;
    }

    // ------------------------------------------------------------------ shared pieces

    /**
     * The ABEND block common to the failing SQL paragraphs: build ABNDINFO-REC, LINK to the abend program, DISPLAY,
     * optionally CHECK-FOR-STORM-DRAIN-DB2, EXEC CICS ABEND ... CANCEL.
     * @return always true: the task has ended or an abend exit took over.
     */
    private boolean abendSequence(CicsTask task, Work w, AbendLink site, String abcode, String freeform, String display, boolean stormAfterDisplay) {
        AbndprocDfhcommarea rec = buildAbndRec(task, w, abcode, w.sqlcode, freeform);
        if (linkAbndproc(task, w, rec, site)) {
            return true;
        }
        Sysout.display(display);
        if (stormAfterDisplay) {
            checkForStormDrain(w);
        }
        task.abendCancel(abcode);
        return true;
    }

    /** The LINK PROGRAM(WS-ABEND-PGM) of one COBOL site: its dispatcher (#4342). */
    private interface AbendLink {
        String link(CicsTask task, String program, Object commarea, int length);
    }

    /** EXEC CICS LINK PROGRAM(WS-ABEND-PGM) COMMAREA(ABNDINFO-REC), through the site's dispatcher `site` (#4342).
     *  @return true when runTask must stop. */
    private boolean linkAbndproc(CicsTask task, Work w, AbndprocDfhcommarea rec, AbendLink site) {
        site.link(task, WS_ABEND_PGM, rec, 681);
        String exit = task.abendExit();
        if (exit != null) {
            // an abend in the abend program reached this program's HANDLE ABEND exit: GO TO ABEND-HANDLING
            abendHandling(task, w);
            return true;
        }
        return task.ended();
    }

    /** INITIALIZE ABNDINFO-REC and the MOVEs / STRING that fill it, with POPULATE-TIME-DATE (PTD010). */
    private AbndprocDfhcommarea buildAbndRec(CicsTask task, Work w, String abcode, int sqlcode, String freeform) {
        java.nio.charset.Charset cs = CobolRecords.charset();
        AbndprocDfhcommarea r = new AbndprocDfhcommarea();
        r.setAbndUtimeKey(0L);
        r.setAbndTasknoKey(0);
        r.setAbndApplid(CobolRecords.fit("", 8, cs));
        r.setAbndTranid(CobolRecords.fit("", 4, cs));
        r.setAbndDate(CobolRecords.fit("", 10, cs));
        r.setAbndTime(CobolRecords.fit("", 8, cs));
        r.setAbndCode(CobolRecords.fit("", 4, cs));
        r.setAbndProgram(CobolRecords.fit("", 8, cs));
        r.setAbndRespcode(0);
        r.setAbndResp2Code(0);
        r.setAbndSqlcode(0);
        r.setAbndFreeform(CobolRecords.fit("", 600, cs));

        r.setAbndRespcode(w.eibresp);                       // MOVE EIBRESP
        r.setAbndResp2Code(w.eibresp2);                     // MOVE EIBRESP2
        r.setAbndApplid(task.assignApplid());               // ASSIGN APPLID
        r.setAbndTasknoKey(0);                              // MOVE EIBTASKN: not exposed by CicsTask, 0
        r.setAbndTranid(CobolRecords.fit(task.transid(), 4, cs)); // MOVE EIBTRNID

        // PERFORM POPULATE-TIME-DATE: ASKTIME, FORMATTIME DDMMYYYY(WS-ORIG-DATE) TIME(WS-TIME-NOW) DATESEP
        long abstime = task.asktime();
        String date = CicsTask.formatDate(abstime, "DDMMYYYY", "/");
        String time = CicsTask.formatTime(abstime, "");
        r.setAbndDate(CobolRecords.fit(date, 10, cs));
        // DEFECT (kept): the STRING uses WS-TIME-NOW-GRP-MM twice, so ABND-TIME is hh:mm:mm and the seconds are lost.
        // Fix: use WS-TIME-NOW-GRP-SS for the last part.
        String hh = time.substring(0, 2);
        String mm = time.substring(2, 4);
        r.setAbndTime(CobolRecords.fit(hh + ":" + mm + ":" + mm, 8, cs));
        r.setAbndUtimeKey(abstime);
        r.setAbndCode(CobolRecords.fit(abcode, 4, cs));
        r.setAbndProgram(CobolRecords.fit("INQACC", 8, cs));   // ASSIGN PROGRAM
        r.setAbndSqlcode(sqlcode);
        r.setAbndFreeform(CobolRecords.fit(freeform, 600, cs)); // STRING ... INTO ABND-FREEFORM
        return r;
    }

    /** True when a column fetched without an indicator variable is NULL (DB2 answers SQLCODE -305). */
    private static boolean hasNullColumn(Map<String, Object> row) {
        for (String c : NULLABLE_COLUMNS) {
            if (row.get(c) == null) {
                return true;
            }
        }
        return false;
    }

    /** FETCH / SELECT INTO the host variables (HOST-ACCOUNT-ROW). */
    private void loadHostRow(Work w, Map<String, Object> row) {
        java.nio.charset.Charset cs = CobolRecords.charset();
        w.hvEye = CobolRecords.fit(str(row.get("ACCOUNT_EYECATCHER")), 4, cs);
        w.hvCust = CobolRecords.fit(str(row.get("ACCOUNT_CUSTOMER_NUMBER")), 10, cs);
        w.hvSortcode = CobolRecords.fit(str(row.get("ACCOUNT_SORTCODE")), 6, cs);
        w.hvAccNo = CobolRecords.fit(str(row.get("ACCOUNT_NUMBER")), 8, cs);
        w.hvType = CobolRecords.fit(str(row.get("ACCOUNT_TYPE")), 8, cs);
        w.hvRate = fixed(CobolRecords.decimal(row.get("ACCOUNT_INTEREST_RATE")), 4, 2, true);
        w.hvOpened = CobolRecords.fit(str(Db2Dates.date(row.get("ACCOUNT_OPENED"))), 10, cs);
        w.hvOverdraft = fixed(CobolRecords.decimal(row.get("ACCOUNT_OVERDRAFT_LIMIT")), 9, 0, true).intValue();
        w.hvLast = CobolRecords.fit(str(Db2Dates.date(row.get("ACCOUNT_LAST_STATEMENT"))), 10, cs);
        w.hvNext = CobolRecords.fit(str(Db2Dates.date(row.get("ACCOUNT_NEXT_STATEMENT"))), 10, cs);
        w.hvAvail = fixed(CobolRecords.decimal(row.get("ACCOUNT_AVAILABLE_BALANCE")), 10, 2, true);
        w.hvActual = fixed(CobolRecords.decimal(row.get("ACCOUNT_ACTUAL_BALANCE")), 10, 2, true);
    }

    /** The MOVE HV-... TO ... OF OUTPUT-DATA block of FD010 / GLAD010. */
    private void moveHostToOutput(Work w) {
        w.eye = w.hvEye;
        w.custNo = toDigits(w.hvCust, 10);
        w.sortCode = (int) toDigits(w.hvSortcode, 6);
        w.number = (int) toDigits(w.hvAccNo, 8);
        w.type = w.hvType;
        w.rate = fixed(w.hvRate, 4, 2, false);
        w.opened = reformat(w.hvOpened);
        w.overdraft = fixed(BigDecimal.valueOf(w.hvOverdraft), 8, 0, false).intValue();
        w.last = reformat(w.hvLast);
        w.next = reformat(w.hvNext);
        w.avail = w.hvAvail;
        w.actual = w.hvActual;
    }

    /** MOVE host date TO DB2-DATE-REFORMAT: yyyy-mm-dd (ISO) -> {day, month, year}. */
    private static int[] reformat(String hv) {
        return new int[] {(int) toDigits(hv.substring(8, 10), 2), (int) toDigits(hv.substring(5, 7), 2),
                (int) toDigits(hv.substring(0, 4), 4)};
    }

    /** ACCOUNT-OPENED / -LAST-STMT-DATE / -NEXT-STMT-DATE as PIC 9(8) ddmmyyyy. */
    private static int dateNum(int[] dmy) {
        return dmy[0] * 1_000_000 + dmy[1] * 10_000 + dmy[2];
    }

    /** MOVE of an alphanumeric item to PIC 9(n): digits, high-order truncation; non-numeric data reads as 0. */
    private static long toDigits(String s, int digits) {
        try {
            return CobolRecords.numval(s).abs().toBigInteger().mod(BigInteger.TEN.pow(digits)).longValue();
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    /** MOVE to PIC [S]9(digits)V9(scale): truncates both ends; an unsigned target keeps the magnitude. */
    private static BigDecimal fixed(BigDecimal v, int digits, int scale, boolean signed) {
        BigInteger u = v.setScale(scale, RoundingMode.DOWN).unscaledValue();
        BigInteger m = u.abs().mod(BigInteger.TEN.pow(digits + scale));
        if (signed && u.signum() < 0) {
            m = m.negate();
        }
        return new BigDecimal(m, scale);
    }

    /** PIC S9(8) DISPLAY SIGN LEADING SEPARATE as text: '+' / '-' then 8 digits. */
    private static String signSeparate(int v) {
        long a = Math.abs((long) v) % 100_000_000L;
        return (v < 0 ? "-" : "+") + String.format(Locale.ROOT, "%08d", a);
    }

    private static boolean isSpacesOrLowValues(String s) {
        return s.chars().allMatch(c -> c == ' ') || s.chars().allMatch(c -> c == 0);
    }

    private static String str(Object o) {
        return o == null ? "" : o.toString();
    }

    /** EXEC CICS LINK PROGRAM(WS-ABEND-PGM) at src/base/cobol_src/INQACC.cbl:321, COMMAREA(ABNDINFO-REC): the target is data-driven (candidates the engine found: ABNDPROC (value)).
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchWsAbendPgmL321(CicsTask task, String program, Object commarea, int length) {
        return task.link(program.stripTrailing(), commarea, length);
    }

    /** EXEC CICS LINK PROGRAM(WS-ABEND-PGM) at src/base/cobol_src/INQACC.cbl:401, COMMAREA(ABNDINFO-REC): the target is data-driven (candidates the engine found: ABNDPROC (value)).
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchWsAbendPgmL401(CicsTask task, String program, Object commarea, int length) {
        return task.link(program.stripTrailing(), commarea, length);
    }

    /** EXEC CICS LINK PROGRAM(WS-ABEND-PGM) at src/base/cobol_src/INQACC.cbl:516, COMMAREA(ABNDINFO-REC): the target is data-driven (candidates the engine found: ABNDPROC (value)).
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchWsAbendPgmL516(CicsTask task, String program, Object commarea, int length) {
        return task.link(program.stripTrailing(), commarea, length);
    }

    /** EXEC CICS LINK PROGRAM(WS-ABEND-PGM) at src/base/cobol_src/INQACC.cbl:738, COMMAREA(ABNDINFO-REC): the target is data-driven (candidates the engine found: ABNDPROC (value)).
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchWsAbendPgmL738(CicsTask task, String program, Object commarea, int length) {
        return task.link(program.stripTrailing(), commarea, length);
    }

    /** EXEC CICS LINK PROGRAM(WS-ABEND-PGM) at src/base/cobol_src/INQACC.cbl:810, COMMAREA(ABNDINFO-REC): the target is data-driven (candidates the engine found: ABNDPROC (value)).
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchWsAbendPgmL810(CicsTask task, String program, Object commarea, int length) {
        return task.link(program.stripTrailing(), commarea, length);
    }

    /** EXEC CICS LINK PROGRAM(WS-ABEND-PGM) at src/base/cobol_src/INQACC.cbl:924, COMMAREA(ABNDINFO-REC): the target is data-driven (candidates the engine found: ABNDPROC (value)).
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchWsAbendPgmL924(CicsTask task, String program, Object commarea, int length) {
        return task.link(program.stripTrailing(), commarea, length);
    }

    /**
     * EXEC CICS SYNCPOINT ROLLBACK at src/base/cobol_src/INQACC.cbl:682 (paragraph AH010): rolls the unit of work back.
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     */
    public void rollbackL682() {
        throw new UnitOfWorkRollbackException("INQACC", "src/base/cobol_src/INQACC.cbl:682");
    }

    /**
     * EXEC CICS ABEND ABCODE(HRAC) at src/base/cobol_src/INQACC.cbl:335 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendHracL335() {
        throw new CicsAbendException("HRAC", "INQACC", "src/base/cobol_src/INQACC.cbl:335");
    }

    /**
     * EXEC CICS ABEND ABCODE(HRAC) at src/base/cobol_src/INQACC.cbl:415 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendHracL415() {
        throw new CicsAbendException("HRAC", "INQACC", "src/base/cobol_src/INQACC.cbl:415");
    }

    /**
     * EXEC CICS ABEND ABCODE(HRAC) at src/base/cobol_src/INQACC.cbl:524 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendHracL524() {
        throw new CicsAbendException("HRAC", "INQACC", "src/base/cobol_src/INQACC.cbl:524");
    }

    /**
     * EXEC CICS ABEND ABCODE(HROL) at src/base/cobol_src/INQACC.cbl:748 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendHrolL748() {
        throw new CicsAbendException("HROL", "INQACC", "src/base/cobol_src/INQACC.cbl:748");
    }

    /**
     * EXEC CICS ABEND ABCODE(MY-ABEND-CODE) at src/base/cobol_src/INQACC.cbl:814 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendMyabendcodeL814() {
        throw new CicsAbendException("MY-ABEND-CODE", "INQACC", "src/base/cobol_src/INQACC.cbl:814");
    }

    /**
     * EXEC CICS ABEND ABCODE(HNCS) at src/base/cobol_src/INQACC.cbl:932 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendHncsL932() {
        throw new CicsAbendException("HNCS", "INQACC", "src/base/cobol_src/INQACC.cbl:932");
    }

}
