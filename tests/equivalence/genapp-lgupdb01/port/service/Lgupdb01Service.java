package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.client.Dor1RemoteClient;
import com.gitgalaxy.modernized.dto.contract.Lgacdb01CaErrorMsg;
import com.gitgalaxy.modernized.dto.contract.Lgupdb01Dfhcommarea;
import com.gitgalaxy.modernized.dto.contract.Lgupvs01Dfhcommarea;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.exception.*;
import com.gitgalaxy.modernized.repository.db2.Db2Dates;
import com.gitgalaxy.modernized.repository.db2.EndowmentRepository;
import com.gitgalaxy.modernized.repository.db2.HouseRepository;
import com.gitgalaxy.modernized.repository.db2.MotorRepository;
import com.gitgalaxy.modernized.repository.db2.PolicyRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.dao.CannotAcquireLockException;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.dao.IncorrectResultSizeDataAccessException;
import org.springframework.dao.PessimisticLockingFailureException;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
@RequiredArgsConstructor
public class Lgupdb01Service {

    private static final Logger log = LoggerFactory.getLogger(Lgupdb01Service.class);

    private static final int SPEC_LEN = 32482;
    private static final int POLICY_NUM = 0;
    private static final int ISSUE_DATE = 10;
    private static final int EXPIRY_DATE = 20;
    private static final int LASTCHANGED = 30;
    private static final int BROKERID = 56;
    private static final int BROKERSREF = 66;
    private static final int PAYMENT = 76;
    // CA-POLICY-SPECIFIC starts after CA-POLICY-COMMON
    private static final int PSPEC = 82;

    private final Dor1RemoteClient dor1RemoteClient;
    private final ObjectProvider<LgstsqService> lgstsqService;
    private final ObjectProvider<Lgupvs01Service> lgupvs01Service;
    private final EndowmentRepository endowmentRepository;
    private final HouseRepository houseRepository;
    private final MotorRepository motorRepository;
    private final PolicyRepository policyRepository;

    /** Working storage of one task (the program's WORKING-STORAGE). */
    private static final class Ctx {
        String cusnum = "";          // EM-CUSNUM
        String polnum = "";          // EM-POLNUM
        String sqlreq = "";          // EM-SQLREQ
        String variableOverride;     // EM-VARIABLE moved as a whole
        int sqlcode = 0;             // SQLCODE
        int customerInt;             // DB2-CUSTOMERNUM-INT
        int policyInt;               // DB2-POLICYNUM-INT
        int brokerInt;               // DB2-BROKERID-INT
        String db2Lastchanged = "";  // DB2-LASTCHANGED
        boolean cursorOpen;
        List<Map<String, Object>> rows = List.of();
        Object rid;
    }

    /** The logic of LGUPDB01 runs in runTask(CicsTask); there is no batch entry. */
    public void executeLgupdb01(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for lgupdb01");
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public Lgupdb01Dfhcommarea handleTransaction(String transid, Lgupdb01Dfhcommarea request) {
        log.info("Lgupdb01: handleTransaction");
        return request;
    }

    /** MAINLINE SECTION, one task. */
    public void runTask(CicsTask task) {
        Charset cs = CobolRecords.charset();
        Ctx ctx = new Ctx();
        ctx.sqlreq = "";
        int calen = !task.hasCommarea() ? 0 : task.eibcalen() == null ? 32500 : task.eibcalen();
        Lgupdb01Dfhcommarea ca = task.hasCommarea() ? task.commarea(Lgupdb01Dfhcommarea.class) : null;

        // MAINLINE: IF EIBCALEN IS EQUAL TO ZERO
        if (calen == 0) {
            ctx.variableOverride = CobolRecords.fit(" NO COMMAREA RECEIVED", 63, cs);
            if (writeErrorMessage(task, ca, ctx, calen)) {
                return;
            }
            task.abend("LGCA");
            return;
        }

        ca.setCaReturnCode(0);
        long cust = ca.getCaCustomerNum() == null ? 0L : ca.getCaCustomerNum();
        String polRaw = field(ca, POLICY_NUM, 10);
        ctx.customerInt = (int) (cust % 1_000_000_000L);
        ctx.policyInt = (int) (num(polRaw) % 1_000_000_000L);
        ctx.cusnum = String.format(Locale.ROOT, "%010d", cust);
        ctx.polnum = polRaw;

        if (updatePolicyDb2Info(task, ca, ctx, calen)) {
            return;
        }

        // MAINLINE: EXEC CICS LINK PROGRAM(LGUPVS01) COMMAREA(DFHCOMMAREA) LENGTH(225)
        Lgupvs01Dfhcommarea vs = new Lgupvs01Dfhcommarea();
        vs.setCaRequestId(ca.getCaRequestId());
        vs.setCaReturnCode(ca.getCaReturnCode());
        vs.setCaCustomerNum(ca.getCaCustomerNum());
        vs.setCaRequestSpecific(ca.getCaRequestSpecific());
        String resp = task.link("LGUPVS01", vs, 225);
        if (!"NORMAL".equals(resp)) {
            task.abendOnCondition(resp);
            return;
        }
        if (task.ended()) {
            return;
        }
        // LENGTH(225): only the first 225 bytes are shared with the callee
        ca.setCaRequestId(vs.getCaRequestId());
        ca.setCaReturnCode(vs.getCaReturnCode());
        ca.setCaCustomerNum(vs.getCaCustomerNum());
        String back = CobolRecords.fit(vs.getCaRequestSpecific(), SPEC_LEN, cs).substring(0, 207);
        ca.setCaRequestSpecific(back + spec(ca).substring(207));

        // END-PROGRAM
        task.returnTransid(null, null);
    }

    /** UPDATE-POLICY-DB2-INFO. Returns true when the task has ended (RETURN / abend). */
    private boolean updatePolicyDb2Info(CicsTask task, Lgupdb01Dfhcommarea ca, Ctx ctx, int calen) {
        Charset cs = CobolRecords.charset();
        ctx.sqlreq = " OPEN   PCURSOR ";
        // EXEC SQL OPEN POLICY_CURSOR
        try {
            Map<String, Object> p = new HashMap<>();
            p.put("db2CustomernumInt", ctx.customerInt);
            p.put("db2PolicynumInt", ctx.policyInt);
            ctx.rows = policyRepository.cursorPolicyCursorL128Lgupdb01(p);
            ctx.cursorOpen = true;
            ctx.sqlcode = 0;
        } catch (DataAccessException e) {
            ctx.sqlcode = sqlcodeOf(e);
        }
        if (ctx.sqlcode == 0) {
            ca.setCaReturnCode(0);
        } else {
            // WHEN -913 and WHEN OTHER are identical in the source
            ca.setCaReturnCode(90);
            if (writeErrorMessage(task, ca, ctx, calen)) {
                return true;
            }
            task.returnTransid(null, null);
            return true;
        }

        // PERFORM FETCH-DB2-POLICY-ROW
        fetchDb2PolicyRow(ctx);

        if (ctx.sqlcode == 0) {
            if (CobolCompare.eq(field(ca, LASTCHANGED, 26), ctx.db2Lastchanged)) {
                String reqId = CobolRecords.fit(ca.getCaRequestId(), 6, cs);
                if (CobolCompare.eq(reqId, "01UEND")) {
                    if (updateEndowDb2Info(task, ca, ctx, calen)) {
                        return true;
                    }
                } else if (CobolCompare.eq(reqId, "01UHOU")) {
                    if (updateHouseDb2Info(task, ca, ctx, calen)) {
                        return true;
                    }
                } else if (CobolCompare.eq(reqId, "01UMOT")) {
                    if (updateMotorDb2Info(task, ca, ctx, calen)) {
                        return true;
                    }
                }

                if (rc(ca) != 0) {
                    if (closePcursor(task, ca, ctx, calen)) {
                        return true;
                    }
                    task.returnTransid(null, null);
                    return true;
                }

                ctx.brokerInt = (int) (num(field(ca, BROKERID, 10)) % 1_000_000_000L);
                // MOVE CA-PAYMENT TO DB2-PAYMENT-INT: host variable never used afterwards

                ctx.sqlreq = " UPDATE POLICY  ";
                try {
                    Map<String, Object> p = new HashMap<>();
                    p.put("caIssueDate", field(ca, ISSUE_DATE, 10));
                    p.put("caExpiryDate", field(ca, EXPIRY_DATE, 10));
                    p.put("db2BrokeridInt", ctx.brokerInt);
                    p.put("caBrokersref", field(ca, BROKERSREF, 10));
                    p.put("ggRid", ctx.rid);
                    policyRepository.updateL318Lgupdb01(p);
                    ctx.sqlcode = 0;
                } catch (DataAccessException e) {
                    // the program does not test this SQLCODE; the SELECT below overwrites it
                    ctx.sqlcode = sqlcodeOf(e);
                }

                try {
                    Map<String, Object> p = new HashMap<>();
                    p.put("db2PolicynumInt", ctx.policyInt);
                    Map<String, Object> row = policyRepository.selectL329Lgupdb01(p);
                    setSpec(ca, LASTCHANGED, 26, Db2Dates.timestamp(row.get("LASTCHANGED")));
                    ctx.sqlcode = 0;
                } catch (EmptyResultDataAccessException e) {
                    ctx.sqlcode = 100;
                } catch (IncorrectResultSizeDataAccessException e) {
                    ctx.sqlcode = -811;
                } catch (DataAccessException e) {
                    ctx.sqlcode = sqlcodeOf(e);
                }

                if (ctx.sqlcode != 0) {
                    task.rollback();
                    ctx.cursorOpen = false;  // ROLLBACK closes even a WITH HOLD cursor
                    ca.setCaReturnCode(90);
                    if (writeErrorMessage(task, ca, ctx, calen)) {
                        return true;
                    }
                }
            } else {
                ca.setCaReturnCode(2);
            }
        } else {
            if (ctx.sqlcode == 100) {
                ca.setCaReturnCode(1);
            } else {
                ca.setCaReturnCode(90);
                if (writeErrorMessage(task, ca, ctx, calen)) {
                    return true;
                }
            }
        }
        // DEFECT (kept): CLOSE-PCURSOR sets CA-RETURN-CODE '00' on SQLCODE 0, wiping the '01' / '02' / '90'
        // set above, so the caller never sees them. Fix: close without touching CA-RETURN-CODE.
        return closePcursor(task, ca, ctx, calen);
    }

    /** FETCH-DB2-POLICY-ROW (one row expected). */
    private void fetchDb2PolicyRow(Ctx ctx) {
        ctx.sqlreq = " FETCH  ROW   ";
        if (!ctx.cursorOpen) {
            ctx.sqlcode = -501;
            return;
        }
        if (ctx.rows.isEmpty()) {
            ctx.sqlcode = 100;
            return;
        }
        Map<String, Object> row = ctx.rows.get(0);
        ctx.db2Lastchanged = CobolRecords.fit(Db2Dates.timestamp(row.get("LASTCHANGED")), 26,
                CobolRecords.charset());
        ctx.rid = row.get("GG_RID");
        ctx.sqlcode = 0;
    }

    /** CLOSE-PCURSOR. Returns true when the task has ended (RETURN). */
    private boolean closePcursor(CicsTask task, Lgupdb01Dfhcommarea ca, Ctx ctx, int calen) {
        ctx.sqlreq = " CLOSE  PCURSOR";
        if (ctx.cursorOpen) {
            ctx.cursorOpen = false;
            ctx.sqlcode = 0;
        } else {
            ctx.sqlcode = -501;
        }
        if (ctx.sqlcode == 0) {
            ca.setCaReturnCode(0);
        } else if (ctx.sqlcode == -501) {
            ca.setCaReturnCode(0);
            ctx.sqlreq = "-501 detected c";
            task.returnTransid(null, null);
            return true;
        } else {
            ca.setCaReturnCode(90);
            if (writeErrorMessage(task, ca, ctx, calen)) {
                return true;
            }
            task.returnTransid(null, null);
            return true;
        }
        return false;
    }

    /** UPDATE-ENDOW-DB2-INFO. Returns true when the task has ended. */
    private boolean updateEndowDb2Info(CicsTask task, Lgupdb01Dfhcommarea ca, Ctx ctx, int calen) {
        int term = (int) num(field(ca, PSPEC + 13, 2));
        int sum = (int) num(field(ca, PSPEC + 15, 6));
        ctx.sqlreq = " UPDATE ENDOW ";
        try {
            Map<String, Object> p = new HashMap<>();
            p.put("caEWithProfits", field(ca, PSPEC, 1));
            p.put("caEEquities", field(ca, PSPEC + 1, 1));
            p.put("caEManagedFund", field(ca, PSPEC + 2, 1));
            p.put("caEFundName", field(ca, PSPEC + 3, 10));
            p.put("db2ETermSint", term);
            p.put("db2ESumassuredInt", sum);
            p.put("caELifeAssured", field(ca, PSPEC + 21, 31));
            p.put("db2PolicynumInt", ctx.policyInt);
            ctx.sqlcode = endowmentRepository.updateL394Lgupdb01(p) == 0 ? 100 : 0;
        } catch (DataAccessException e) {
            ctx.sqlcode = sqlcodeOf(e);
        }
        return sqlFailure(task, ca, ctx, calen);
    }

    /** UPDATE-HOUSE-DB2-INFO. Returns true when the task has ended. */
    private boolean updateHouseDb2Info(CicsTask task, Lgupdb01Dfhcommarea ca, Ctx ctx, int calen) {
        int bedrooms = (int) num(field(ca, PSPEC + 15, 3));
        int value = (int) num(field(ca, PSPEC + 18, 8));
        ctx.sqlreq = " UPDATE HOUSE ";
        try {
            Map<String, Object> p = new HashMap<>();
            p.put("caHPropertyType", field(ca, PSPEC, 15));
            p.put("db2HBedroomsSint", bedrooms);
            p.put("db2HValueInt", value);
            p.put("caHHouseName", field(ca, PSPEC + 26, 20));
            p.put("caHHouseNumber", field(ca, PSPEC + 46, 4));
            p.put("caHPostcode", field(ca, PSPEC + 50, 8));
            p.put("db2PolicynumInt", ctx.policyInt);
            ctx.sqlcode = houseRepository.updateL431Lgupdb01(p) == 0 ? 100 : 0;
        } catch (DataAccessException e) {
            ctx.sqlcode = sqlcodeOf(e);
        }
        return sqlFailure(task, ca, ctx, calen);
    }

    /** UPDATE-MOTOR-DB2-INFO. Returns true when the task has ended. */
    private boolean updateMotorDb2Info(CicsTask task, Lgupdb01Dfhcommarea ca, Ctx ctx, int calen) {
        int cc = (int) num(field(ca, PSPEC + 51, 4));
        int value = (int) num(field(ca, PSPEC + 30, 6));
        int premium = (int) num(field(ca, PSPEC + 65, 6));
        int accidents = (int) num(field(ca, PSPEC + 71, 6));
        ctx.sqlreq = " UPDATE MOTOR ";
        try {
            Map<String, Object> p = new HashMap<>();
            p.put("caMMake", field(ca, PSPEC, 15));
            p.put("caMModel", field(ca, PSPEC + 15, 15));
            p.put("db2MValueInt", value);
            p.put("caMRegnumber", field(ca, PSPEC + 36, 7));
            p.put("caMColour", field(ca, PSPEC + 43, 8));
            p.put("db2MCcSint", cc);
            p.put("caMManufactured", field(ca, PSPEC + 55, 10));
            p.put("db2MPremiumInt", premium);
            p.put("db2MAccidentsInt", accidents);
            p.put("db2PolicynumInt", ctx.policyInt);
            ctx.sqlcode = motorRepository.updateL469Lgupdb01(p) == 0 ? 100 : 0;
        } catch (DataAccessException e) {
            ctx.sqlcode = sqlcodeOf(e);
        }
        return sqlFailure(task, ca, ctx, calen);
    }

    /** The shared IF SQLCODE NOT EQUAL 0 block of the three type-specific updates. */
    private boolean sqlFailure(CicsTask task, Lgupdb01Dfhcommarea ca, Ctx ctx, int calen) {
        if (ctx.sqlcode != 0) {
            if (ctx.sqlcode == 100) {
                ca.setCaReturnCode(1);
            } else {
                ca.setCaReturnCode(90);
                return writeErrorMessage(task, ca, ctx, calen);
            }
        }
        return false;
    }

    /** WRITE-ERROR-MESSAGE. Returns true when the task has ended (abend in or below a LINK). */
    private boolean writeErrorMessage(CicsTask task, Lgupdb01Dfhcommarea ca, Ctx ctx, int calen) {
        Charset cs = CobolRecords.charset();
        String sqlrc = (ctx.sqlcode < 0 ? "-" : "+")
                + String.format(Locale.ROOT, "%05d", Math.abs((long) ctx.sqlcode) % 100000L);
        long abstime = task.asktime();
        String wsDate = CobolRecords.fit(CicsTask.formatDate(abstime, "MMDDYYYY", ""), 10, cs);
        String wsTime = CobolRecords.fit(CicsTask.formatTime(abstime, ""), 8, cs);
        String variable;
        if (ctx.variableOverride != null) {
            variable = ctx.variableOverride.substring(0, 57) + sqlrc;
        } else {
            variable = " CNUM=" + CobolRecords.fit(ctx.cusnum, 10, cs)
                    + " PNUM=" + CobolRecords.fit(ctx.polnum, 10, cs)
                    + CobolRecords.fit(ctx.sqlreq, 16, cs)
                    + " SQLCODE=" + sqlrc;
        }
        String errorMsg = wsDate.substring(0, 8) + " " + wsTime.substring(0, 6) + " LGUPDB01" + variable;
        Lgacdb01CaErrorMsg em = new Lgacdb01CaErrorMsg();
        em.setCaData(errorMsg);  // 87 bytes: ERROR-MSG, laid over the LGSTSQ commarea
        if (linkLgstsqTask(task, em, 87)) {
            return true;
        }
        if (calen > 0) {
            String dfh = commareaImage(ca, cs);
            Lgacdb01CaErrorMsg c = new Lgacdb01CaErrorMsg();
            if (calen < 91) {
                c.setCaData(CobolRecords.fit(dfh.substring(0, Math.min(calen, dfh.length())), 90, cs));
            } else {
                c.setCaData(dfh.substring(0, 90));
            }
            return linkLgstsqTask(task, c, 99);
        }
        return false;
    }

    private boolean linkLgstsqTask(CicsTask task, Lgacdb01CaErrorMsg msg, int length) {
        String resp = task.link("LGSTSQ", msg, length);
        if (!"NORMAL".equals(resp)) {
            task.abendOnCondition(resp);
            return true;
        }
        return task.ended();
    }

    /** DFHCOMMAREA as bytes: the first 90 are enough for the error message. */
    private String commareaImage(Lgupdb01Dfhcommarea ca, Charset cs) {
        long cust = ca.getCaCustomerNum() == null ? 0L : ca.getCaCustomerNum();
        return CobolRecords.fit(ca.getCaRequestId(), 6, cs)
                + String.format(Locale.ROOT, "%02d", rc(ca))
                + String.format(Locale.ROOT, "%010d", cust)
                + spec(ca).substring(0, 72);
    }

    private int rc(Lgupdb01Dfhcommarea ca) {
        return ca.getCaReturnCode() == null ? 0 : ca.getCaReturnCode();
    }

    private String spec(Lgupdb01Dfhcommarea ca) {
        return CobolRecords.fit(ca.getCaRequestSpecific(), SPEC_LEN, CobolRecords.charset());
    }

    /** A field of CA-REQUEST-SPECIFIC at a 0-based offset. */
    private String field(Lgupdb01Dfhcommarea ca, int off, int len) {
        return spec(ca).substring(off, off + len);
    }

    private void setSpec(Lgupdb01Dfhcommarea ca, int off, int len, String value) {
        String s = spec(ca);
        String v = CobolRecords.fit(value, len, CobolRecords.charset());
        ca.setCaRequestSpecific(s.substring(0, off) + v + s.substring(off + len));
    }

    /** A PIC 9 DISPLAY field moved to a binary host variable; non-digits count as zero. */
    private long num(String text) {
        try {
            return CobolRecords.numval(text, '.').longValue();
        } catch (NumberFormatException e) {
            return 0L;
        }
    }

    private int sqlcodeOf(DataAccessException e) {
        if (e instanceof CannotAcquireLockException || e instanceof PessimisticLockingFailureException) {
            return -913;
        }
        return -904;
    }

    /** Another program LINKed / XCTLed to this one. TODO: [AI AGENT] implement from the program's business rules. */
    public Lgupdb01Dfhcommarea handleLink(Lgupdb01Dfhcommarea request) {
        log.info("Lgupdb01: handleLink");
        return request;
    }

    /** EXEC CICS LINK PROGRAM(LGUPVS01) at 209: the CSD routes it to region DOR1 (distributed program link).
     *  Remote calls field testing: open (5 public / 0 private estates). */
    public Lgupvs01Dfhcommarea remoteLgupvs01L209(Lgupvs01Dfhcommarea request) {
        return dor1RemoteClient.linkLgupvs01(request);
    }

    /** EXEC CICS LINK PROGRAM(LGSTSQ) at base/src/lgupdb01.cbl:515, base/src/lgupdb01.cbl:523, base/src/lgupdb01.cbl:529.
     *  Call targets field testing: open (6 public / 0 private estates). */
    // TODO: this site passes ERROR-MSG; LGSTSQ receives CA-ERROR-MSG (base/src/lgacdb01.cbl) -- map one layout onto the other
    public Lgacdb01CaErrorMsg linkLgstsq(Lgacdb01CaErrorMsg request) {
        return lgstsqService.getObject().handleLink(request);
    }

    /** LINK PROGRAM(LGUPVS01) at base/src/lgupdb01.cbl:209: the target is data-driven. Candidates: LGUPVS01 (value).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchLgupvs01L209(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "LGUPVS01":
                return lgupvs01Service.getObject().handleLink((Lgupvs01Dfhcommarea) request);
            default:
                throw new IllegalArgumentException("LINK PROGRAM(LGUPVS01) at base/src/lgupdb01.cbl:209: no known target " + program);
        }
    }

    /**
     * EXEC CICS SYNCPOINT ROLLBACK at base/src/lgupdb01.cbl:338 (paragraph UPDATE-POLICY-DB2-INFO): rolls the unit of work back.
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     */
    public void rollbackL338() {
        throw new UnitOfWorkRollbackException("LGUPDB01", "base/src/lgupdb01.cbl:338");
    }

    /**
     * EXEC CICS ABEND ABCODE(LGCA) at base/src/lgupdb01.cbl:186 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendLgcaL186() {
        throw new CicsAbendException("LGCA", "LGUPDB01", "base/src/lgupdb01.cbl:186");
    }

}
