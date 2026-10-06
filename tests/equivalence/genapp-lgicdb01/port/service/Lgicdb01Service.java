package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.LgstsqDfhcommarea;
import com.gitgalaxy.modernized.dto.contract.Lgicdb01Dfhcommarea;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.exception.*;
import com.gitgalaxy.modernized.repository.db2.CustomerRepository;
import com.gitgalaxy.modernized.repository.db2.Db2Dates;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.dao.IncorrectResultSizeDataAccessException;
import org.springframework.dao.PessimisticLockingFailureException;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.Charset;
import java.sql.SQLException;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

@Service
@Transactional
@RequiredArgsConstructor
public class Lgicdb01Service {

    private static final Logger log = LoggerFactory.getLogger(Lgicdb01Service.class);

    private static final int DFHCOMMAREA_LEN = 32500;
    private static final int SPECIFIC_LEN = 32482;
    private static final int WS_CUSTOMER_LEN = 72;          // WS-CUSTOMER-LEN (lgpolicy.cpy)
    private static final int WS_CA_HEADERTRAILER_LEN = 18;  // WS-CA-HEADERTRAILER-LEN

    private final ObjectProvider<LgstsqService> lgstsqService;
    private final CustomerRepository customerRepository;

    /** One task of LGICDB01: MAINLINE SECTION, GET-CUSTOMER-INFO, WRITE-ERROR-MESSAGE. */
    public void runTask(CicsTask task) {
        log.info("Lgicdb01: runTask");
        Charset cs = CobolRecords.charset();

        // MAINLINE: INITIALIZE WS-HEADER / MOVE EIBTRNID, EIBTRMID, EIBTASKN -- debug fields, never output.

        // MAINLINE: IF EIBCALEN IS EQUAL TO ZERO
        if (!task.hasCommarea() || (task.eibcalen() != null && task.eibcalen() == 0)) {
            // MOVE ' NO COMMAREA RECEIVED' TO EM-VARIABLE (47 bytes, group move: pads with spaces)
            String emVariable = CobolRecords.fit(" NO COMMAREA RECEIVED", 47, cs);
            if (!writeErrorMessage(task, null, 0, emVariable, 0, cs)) {
                return;
            }
            task.abend("LGCA");   // ABEND ABCODE('LGCA') NODUMP; no HANDLE ABEND, so the task ends
            return;
        }

        Lgicdb01Dfhcommarea ca = task.commarea(Lgicdb01Dfhcommarea.class);
        Integer eibcalen = task.eibcalen();
        int calen = eibcalen == null ? DFHCOMMAREA_LEN : eibcalen;

        // MAINLINE: MOVE '00' TO CA-RETURN-CODE
        ca.setCaReturnCode(0);
        // MOVE EIBCALEN TO WS-CALEN / SET WS-ADDR-DFHCOMMAREA / INITIALIZE DB2-IN-INTEGERS: no output.

        // MAINLINE: MOVE WS-CUSTOMER-LEN TO WS-REQUIRED-CA-LEN; ADD WS-CA-HEADERTRAILER-LEN
        int requiredCaLen = WS_CUSTOMER_LEN + WS_CA_HEADERTRAILER_LEN;
        if (calen < requiredCaLen) {
            ca.setCaReturnCode(98);
            task.returnTransid(null, null);   // EXEC CICS RETURN
            return;
        }

        // MOVE CA-CUSTOMER-NUM TO DB2-CUSTOMERNUMBER-INT (S9(9) COMP: high-order digit lost)
        long custNum = ca.getCaCustomerNum() == null ? 0L : ca.getCaCustomerNum();
        long db2CustomerNumber = custNum % 1_000_000_000L;
        // MOVE CA-CUSTOMER-NUM TO EM-CUSNUM (X(10), the 10 digits as stored)
        String emCusnum = String.format(Locale.ROOT, "%010d", custNum);

        // MAINLINE: PERFORM GET-CUSTOMER-INFO
        if (!getCustomerInfo(task, ca, db2CustomerNumber, emCusnum, calen, cs)) {
            return;
        }

        // MAINLINE-END: EXEC CICS RETURN
        task.returnTransid(null, null);
    }

    /** GET-CUSTOMER-INFO; false when the task has ended (RETURN or an abend inside). */
    private boolean getCustomerInfo(CicsTask task, Lgicdb01Dfhcommarea ca, long db2CustomerNumber,
                                    String emCusnum, int calen, Charset cs) {
        int sqlcode;
        Map<String, Object> row = null;
        try {
            Map<String, Object> params = new HashMap<>();
            params.put("db2CustomernumberInt", db2CustomerNumber);
            row = customerRepository.selectL169Lgicdb01(params);
            sqlcode = 0;
            // a NULL column with no indicator variable is SQLCODE -305 in DB2
            for (String col : COLUMNS) {
                if (row.get(col) == null) {
                    sqlcode = -305;
                    break;
                }
            }
        } catch (EmptyResultDataAccessException e) {
            sqlcode = 100;
        } catch (IncorrectResultSizeDataAccessException e) {
            sqlcode = -811;
        } catch (PessimisticLockingFailureException e) {
            sqlcode = -913;
        } catch (DataAccessException e) {
            sqlcode = otherSqlcode(e);
        }

        // SELECT ... INTO: host variables are set only on SQLCODE 0 (the row's columns overlay CA-REQUEST-SPECIFIC)
        if (sqlcode == 0) {
            StringBuilder sb = new StringBuilder(
                    CobolRecords.fit(ca.getCaRequestSpecific(), SPECIFIC_LEN, cs));
            put(sb, 0, 10, row.get("FIRSTNAME"), cs);       // CA-FIRST-NAME
            put(sb, 10, 20, row.get("LASTNAME"), cs);       // CA-LAST-NAME
            put(sb, 30, 10, row.get("DATEOFBIRTH"), cs);    // CA-DOB
            put(sb, 40, 20, row.get("HOUSENAME"), cs);      // CA-HOUSE-NAME
            put(sb, 60, 4, row.get("HOUSENUMBER"), cs);     // CA-HOUSE-NUM
            put(sb, 64, 8, row.get("POSTCODE"), cs);        // CA-POSTCODE
            put(sb, 75, 20, row.get("PHONEMOBILE"), cs);    // CA-PHONE-MOBILE
            put(sb, 95, 20, row.get("PHONEHOME"), cs);      // CA-PHONE-HOME
            put(sb, 115, 100, row.get("EMAILADDRESS"), cs); // CA-EMAIL-ADDRESS
            ca.setCaRequestSpecific(sb.toString());
        }

        // Evaluate SQLCODE
        if (sqlcode == 0) {
            ca.setCaReturnCode(0);
        } else if (sqlcode == 100) {
            ca.setCaReturnCode(1);
        } else if (sqlcode == -913) {
            ca.setCaReturnCode(1);
        } else {
            ca.setCaReturnCode(90);
            // EM-VARIABLE: ' CNUM=' EM-CUSNUM EM-SQLREQ(spaces) ' SQLCODE=' EM-SQLRC (set in WRITE-ERROR-MESSAGE)
            String emVariable = " CNUM=" + emCusnum + " ".repeat(16) + " SQLCODE=";
            if (!writeErrorMessage(task, ca, calen, emVariable, sqlcode, cs)) {
                return false;
            }
            task.returnTransid(null, null);   // EXEC CICS RETURN
            return false;
        }
        return true;
    }

    private static final String[] COLUMNS = {"FIRSTNAME", "LASTNAME", "DATEOFBIRTH", "HOUSENAME",
            "HOUSENUMBER", "POSTCODE", "PHONEMOBILE", "PHONEHOME", "EMAILADDRESS"};

    /**
     * WRITE-ERROR-MESSAGE. `emVariable` is EM-VARIABLE as the caller left it (47 bytes, or its first 41
     * when EM-SQLRC is still to be set). Returns false when the task ended (a failed LINK abended it).
     */
    private boolean writeErrorMessage(CicsTask task, Lgicdb01Dfhcommarea ca, int calen, String emVariable,
                                      int sqlcode, Charset cs) {
        // MOVE SQLCODE TO EM-SQLRC (PIC +9(5)): last 6 bytes of EM-VARIABLE
        String emSqlrc = (sqlcode < 0 ? "-" : "+")
                + String.format(Locale.ROOT, "%05d", Math.abs((long) sqlcode) % 100000L);
        String variable = CobolRecords.fit(emVariable, 47, cs).substring(0, 41) + emSqlrc;

        // EXEC CICS ASKTIME / FORMATTIME MMDDYYYY(WS-DATE) TIME(WS-TIME)
        long abstime = task.asktime();
        String wsDate = CobolRecords.fit(CicsTask.formatDate(abstime, "MMDDYYYY", ""), 10, cs);
        String wsTime = CobolRecords.fit(CicsTask.formatTime(abstime, ""), 8, cs);
        String emDate = wsDate.substring(0, 8);     // MOVE WS-DATE TO EM-DATE
        String emTime = wsTime.substring(0, 6);     // MOVE WS-TIME TO EM-TIME

        // ERROR-MSG: EM-DATE, FILLER, EM-TIME, ' LGICUS01', EM-VARIABLE (71 bytes)
        String errorMsg = emDate + " " + emTime + " LGICUS01" + variable;

        // EXEC CICS LINK PROGRAM('LGSTSQ') COMMAREA(ERROR-MSG) LENGTH(71)
        LgstsqDfhcommarea msg = new LgstsqDfhcommarea();
        msg.setCaData(errorMsg);
        if (!linked(task, task.link("LGSTSQ", msg, errorMsg.length()))) {
            return false;
        }

        // IF EIBCALEN > 0 (EIBCALEN is 0 on the no-commarea path)
        if (ca != null && calen > 0) {
            int n = Math.min(calen, 90);   // < 91: DFHCOMMAREA(1:EIBCALEN); else DFHCOMMAREA(1:90)
            LgstsqDfhcommarea caMsg = new LgstsqDfhcommarea();
            caMsg.setCaData(CobolRecords.fit(commareaText(ca, cs).substring(0, n), 90, cs));
            // EXEC CICS LINK PROGRAM('LGSTSQ') COMMAREA(CA-ERROR-MSG) LENGTH(99)
            if (!linked(task, task.link("LGSTSQ", caMsg, 99))) {
                return false;
            }
        }
        return true;
    }

    /** After a LINK with no RESP clause: an unhandled condition abends the task (default action). */
    private boolean linked(CicsTask task, String resp) {
        if (!"NORMAL".equals(resp)) {
            task.abendOnCondition(resp);
            return false;
        }
        return !task.ended();
    }

    /** The first 90 bytes of DFHCOMMAREA as text: request id, return code, customer number, specific data. */
    private static String commareaText(Lgicdb01Dfhcommarea ca, Charset cs) {
        int rc = ca.getCaReturnCode() == null ? 0 : ca.getCaReturnCode();
        long num = ca.getCaCustomerNum() == null ? 0L : ca.getCaCustomerNum();
        return CobolRecords.fit(ca.getCaRequestId(), 6, cs)
                + String.format(Locale.ROOT, "%02d", rc % 100)
                + String.format(Locale.ROOT, "%010d", num)
                + CobolRecords.fit(ca.getCaRequestSpecific(), 72, cs);
    }

    /** MOVE a fetched column to a PIC X host variable at `offset` of CA-REQUEST-SPECIFIC. */
    private static void put(StringBuilder sb, int offset, int width, Object value, Charset cs) {
        sb.replace(offset, offset + width, CobolRecords.fit(text(value), width, cs));
    }

    private static String text(Object v) {
        if (v == null) {
            return "";
        }
        if (v instanceof java.sql.Date || v instanceof java.time.LocalDate) {
            return Db2Dates.date(v);   // DB2 DATE in a character host variable (iso)
        }
        return v.toString();
    }

    /** SQLCODE for a failure the program treats as WHEN OTHER: the negated vendor code, else -1. */
    private static int otherSqlcode(DataAccessException e) {
        Throwable t = e.getRootCause();
        if (t instanceof SQLException se && se.getErrorCode() != 0) {
            return -Math.abs(se.getErrorCode());
        }
        return -1;
    }

    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region
     *  (CicsTask.region()), run through runTask on `request`, passed by reference -- what it changes, the caller sees. */
    public Lgicdb01Dfhcommarea handleLink(Lgicdb01Dfhcommarea request) {
        log.info("Lgicdb01: handleLink");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("LGICDB01", request);
        region.run(task, "LGICDB01", this::runTask);
        return request;
    }

    /** EXEC CICS LINK PROGRAM(LGSTSQ) at base/src/lgicdb01.cbl:225, :233, :239 (runTask links through the task). */
    public LgstsqDfhcommarea linkLgstsq(LgstsqDfhcommarea request) {
        return lgstsqService.getObject().handleLink(request);
    }

    /**
     * EXEC CICS ABEND ABCODE(LGCA) at base/src/lgicdb01.cbl:122. runTask does not use this: it ends the
     * task through task.abend("LGCA") instead of throwing.
     */
    public void abendLgcaL122() {
        throw new CicsAbendException("LGCA", "LGICDB01", "base/src/lgicdb01.cbl:122");
    }

}
