package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.client.Dor1RemoteClient;
import com.gitgalaxy.modernized.dto.contract.Lgapdb01Dfhcommarea;
import com.gitgalaxy.modernized.dto.contract.Lgapvs01Dfhcommarea;
import com.gitgalaxy.modernized.dto.contract.LgstsqDfhcommarea;
import com.gitgalaxy.modernized.exception.*;
import com.gitgalaxy.modernized.repository.db2.CommercialRepository;
import com.gitgalaxy.modernized.repository.db2.Db2ValuesRepository;
import com.gitgalaxy.modernized.repository.db2.Db2Dates;
import com.gitgalaxy.modernized.repository.db2.EndowmentRepository;
import com.gitgalaxy.modernized.repository.db2.HouseRepository;
import com.gitgalaxy.modernized.repository.db2.MotorRepository;
import com.gitgalaxy.modernized.repository.db2.PolicyRepository;
import com.gitgalaxy.modernized.entity.vsam.CobolEdit;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.util.CobolCompare;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.LinkedHashMap;
import java.util.Map;

@Service
@Transactional
@RequiredArgsConstructor
public class Lgapdb01Service {

    private static final Logger log = LoggerFactory.getLogger(Lgapdb01Service.class);

    private final Dor1RemoteClient dor1RemoteClient;
    private final ObjectProvider<LgstsqService> lgstsqService;
    private final CommercialRepository commercialRepository;
    private final Db2ValuesRepository db2ValuesRepository;
    private final EndowmentRepository endowmentRepository;
    private final HouseRepository houseRepository;
    private final MotorRepository motorRepository;
    private final PolicyRepository policyRepository;

    /** This program's run at a LINK / XCTL level (#4004): task.level(), task.eibcalen(). */
    public void runTask(CicsTask task) {
        log.info("Lgapdb01: runTask");
        new Mainline(task).run();
    }

    /** Working storage and paragraphs of one LGAPDB01 run. Each method names the paragraph it ports;
     *  a boolean result is false when the task has ended (RETURN / ABEND) and the caller must stop. */
    private final class Mainline {
        /** CA-REQUEST-SPECIFIC starts at byte 18 of DFHCOMMAREA (CA-POLICY-REQUEST redefines it). */
        private static final int SPEC = 18;

        private final CicsTask task;
        private final Charset cs = CobolRecords.charset();
        private final Lgapdb01Dfhcommarea ca;
        private final int calen;
        private final byte[] rec;
        /** EM-VARIABLE, 63 bytes: ' CNUM=' CUSNUM(10) ' PNUM=' POLNUM(10) SQLREQ(16) ' SQLCODE=' SQLRC(6). */
        private final StringBuilder emVar = new StringBuilder(
                " CNUM=" + " ".repeat(10) + " PNUM=" + " ".repeat(10) + " ".repeat(16) + " SQLCODE=" + " ".repeat(6));
        private int sqlcode;
        private int policyInt;          // DB2-POLICYNUM-INT
        private String policyType = " "; // DB2-POLICYTYPE
        private int requiredLen;        // WS-REQUIRED-CA-LEN

        Mainline(CicsTask task) {
            this.task = task;
            Integer l = task.eibcalen();
            this.ca = task.hasCommarea() ? task.commarea(Lgapdb01Dfhcommarea.class) : null;
            this.calen = ca == null ? 0 : (l == null ? 32500 : l);
            this.rec = ca == null ? CobolRecords.blank(32500, cs) : ca.toCommarea();
        }

        // ---- helpers over the COMMAREA record ------------------------------------------------------------
        private String x(int off, int len) {
            return CobolRecords.text(rec, SPEC + off, len, cs);
        }

        private BigDecimal num(int off, int len) {
            BigDecimal v = CobolRecords.zoned(rec, SPEC + off, len, 0, cs);
            return v == null ? BigDecimal.ZERO : v;
        }

        /** MOVE of an unsigned display number to PIC S9(9) COMP: keeps 9 low-order digits. */
        private int bin9(BigDecimal v) {
            return (int) (v.toBigInteger().abs().longValue() % 1_000_000_000L);
        }

        /** MOVE to PIC S9(4) COMP: keeps 4 low-order digits. */
        private int bin4(BigDecimal v) {
            return (int) (v.toBigInteger().abs().longValue() % 10_000L);
        }

        private void setRc(int v) {
            ca.setCaReturnCode(v);
            CobolRecords.putZoned(rec, 6, 2, 0, false, BigDecimal.valueOf(v), cs);
        }

        private void syncSpec() {
            ca.setCaRequestSpecific(CobolRecords.text(rec, SPEC, 32482, cs));
        }

        private void putEm(int off, int len, String text) {
            emVar.replace(off, off + len, CobolRecords.fit(text, len, cs));
        }

        private void doReturn() {
            // EXEC CICS RETURN END-EXEC
            task.returnTransid(null, null);
        }

        private int exec(Runnable statement) {
            try {
                statement.run();
                return 0;
            } catch (DuplicateKeyException e) {
                return -803;
            } catch (DataIntegrityViolationException e) {
                return -530;
            } catch (DataAccessException e) {
                return -911;
            }
        }

        private Object firstValue(Map<String, Object> row) {
            return row == null || row.isEmpty() ? null : row.values().iterator().next();
        }

        // ---- MAINLINE ------------------------------------------------------------------------------------
        void run() {
            // IF EIBCALEN IS EQUAL TO ZERO
            if (calen == 0) {
                putEm(0, 63, " NO COMMAREA RECEIVED");
                if (!writeErrorMessage()) {
                    return;
                }
                task.abend("LGCA");
                return;
            }

            setRc(0);
            // MOVE CA-CUSTOMER-NUM TO DB2-CUSTOMERNUM-INT / EM-CUSNUM
            putEm(6, 10, CobolRecords.text(rec, 8, 10, cs));
            int customerInt = bin9(CobolRecords.zoned(rec, 8, 10, 0, cs) == null ? BigDecimal.ZERO
                    : CobolRecords.zoned(rec, 8, 10, 0, cs));

            requiredLen += 28; // ADD WS-CA-HEADER-LEN TO WS-REQUIRED-CA-LEN
            String id = CobolRecords.text(rec, 0, 6, cs);
            String kind;
            if (CobolCompare.eq(id, "01AEND")) {
                requiredLen += 124;
                policyType = "E";
                kind = "E";
            } else if (CobolCompare.eq(id, "01AHOU")) {
                requiredLen += 130;
                policyType = "H";
                kind = "H";
            } else if (CobolCompare.eq(id, "01AMOT")) {
                requiredLen += 137;
                policyType = "M";
                kind = "M";
            } else if (CobolCompare.eq(id, "01ACOM")) {
                requiredLen += 1174;
                policyType = "C";
                kind = "C";
            } else {
                setRc(99);
                doReturn();
                return;
            }

            if (calen < requiredLen) {
                setRc(98);
                doReturn();
                return;
            }

            if (!insertPolicy(customerInt)) {
                return;
            }

            boolean ok;
            switch (kind) {
                case "E" -> ok = insertEndow();
                case "H" -> ok = insertHouse();
                case "M" -> ok = insertMotor();
                default -> ok = insertCommercial();
            }
            // DEFECT (kept): the second EVALUATE's WHEN OTHER ('99') is unreachable, the first one already
            // returned for an unknown request. Fix: delete the branch.
            if (!ok) {
                return;
            }

            // EXEC CICS LINK PROGRAM(LGAPVS01) COMMAREA(DFHCOMMAREA) LENGTH(32500)
            Lgapvs01Dfhcommarea vs = new Lgapvs01Dfhcommarea();
            vs.setCaRequestId(ca.getCaRequestId());
            vs.setCaReturnCode(ca.getCaReturnCode());
            vs.setCaCustomerNum(ca.getCaCustomerNum());
            vs.setCaRequestSpecific(ca.getCaRequestSpecific());
            byte[] area = ca.toCommarea();
            String resp = task.link("LGAPVS01", vs, 32500, area);
            if (!"NORMAL".equals(resp)) {
                task.abendOnCondition(resp);
                return;
            }
            if (task.ended()) {
                return;
            }
            if (task.linkAreaBack()) {
                Lgapdb01Dfhcommarea back = Lgapdb01Dfhcommarea.fromCommarea(area);
                ca.setCaRequestId(back.getCaRequestId());
                ca.setCaReturnCode(back.getCaReturnCode());
                ca.setCaCustomerNum(back.getCaCustomerNum());
                ca.setCaRequestSpecific(back.getCaRequestSpecific());
            } else {
                ca.setCaRequestId(vs.getCaRequestId());
                ca.setCaReturnCode(vs.getCaReturnCode());
                ca.setCaCustomerNum(vs.getCaCustomerNum());
                ca.setCaRequestSpecific(vs.getCaRequestSpecific());
            }

            doReturn(); // Return to caller
        }

        // ---- INSERT-POLICY -------------------------------------------------------------------------------
        private boolean insertPolicy(int customerInt) {
            int brokerInt = bin9(num(56, 10));
            int paymentInt = bin9(num(76, 6));
            putEm(32, 16, " INSERT POLICY");

            Map<String, Object> p = new LinkedHashMap<>();
            p.put("db2CustomernumInt", customerInt);
            p.put("caIssueDate", x(10, 10));
            p.put("caExpiryDate", x(20, 10));
            p.put("db2Policytype", policyType);
            p.put("db2BrokeridInt", brokerInt);
            p.put("caBrokersref", x(66, 10));
            p.put("db2PaymentInt", paymentInt);
            sqlcode = exec(() -> policyRepository.insertL268Lgapdb01(p));

            if (sqlcode == 0) {
                setRc(0);
            } else if (sqlcode == -530) {
                setRc(70);
                if (writeErrorMessage()) {
                    doReturn();
                }
                return false;
            } else {
                setRc(90);
                if (writeErrorMessage()) {
                    doReturn();
                }
                return false;
            }

            // SET :DB2-POLICYNUM-INT = IDENTITY_VAL_LOCAL()
            try {
                Object v = firstValue(db2ValuesRepository.setL308Lgapdb01(new LinkedHashMap<>()));
                policyInt = bin9(CobolRecords.decimal(v));
                sqlcode = 0;
            } catch (DataAccessException e) {
                sqlcode = -911;
            }
            CobolRecords.putZoned(rec, SPEC, 10, 0, false, BigDecimal.valueOf(policyInt), cs); // CA-POLICY-NUM
            syncSpec();
            putEm(22, 10, x(0, 10)); // EM-POLNUM

            // SELECT LASTCHANGED INTO :CA-LASTCHANGED
            try {
                Map<String, Object> q = new LinkedHashMap<>();
                q.put("db2PolicynumInt", policyInt);
                Object ts = firstValue(policyRepository.selectL316Lgapdb01(q));
                sqlcode = 0;
                if (ts != null) {
                    CobolRecords.putText(rec, SPEC + 30, 26, Db2Dates.timestamp(ts), cs);
                    syncSpec();
                }
            } catch (DataAccessException e) {
                sqlcode = -911;
            }
            return true;
        }

        // ---- INSERT-ENDOW --------------------------------------------------------------------------------
        private boolean insertEndow() {
            int termInt = bin4(num(95, 2));
            int sumInt = bin9(num(97, 6));
            putEm(32, 16, " INSERT ENDOW ");

            // SUBTRACT WS-REQUIRED-CA-LEN FROM EIBCALEN GIVING WS-VARY-LEN (S9(4) COMP: high-order digits lost)
            int varyLen = (calen - requiredLen) % 10000;

            Map<String, Object> p = new LinkedHashMap<>();
            p.put("db2PolicynumInt", policyInt);
            p.put("caEWithProfits", x(82 - 82, 1).isEmpty() ? "" : x(82, 1));
            p.put("caEEquities", x(83, 1));
            p.put("caEManagedFund", x(84, 1));
            p.put("caEFundName", x(85, 10));
            p.put("db2ETermSint", termInt);
            p.put("db2ESumassuredInt", sumInt);
            p.put("caELifeAssured", x(103, 31));
            if (varyLen > 0) {
                // MOVE CA-E-PADDING-DATA TO WS-VARY-CHAR(1:WS-VARY-LEN); the host variable is WS-VARY-LEN long
                String padding = x(134, 32348);
                p.put("wsVaryField", padding.substring(0, Math.min(varyLen, padding.length())));
                sqlcode = exec(() -> endowmentRepository.insertL346Lgapdb01(p));
            } else {
                sqlcode = exec(() -> endowmentRepository.insertL368Lgapdb01(p));
            }
            return checkInsert();
        }

        // ---- INSERT-HOUSE --------------------------------------------------------------------------------
        private boolean insertHouse() {
            int valueInt = bin9(num(100, 8));
            int bedroomsInt = bin4(num(97, 3));
            putEm(32, 16, " INSERT HOUSE ");

            Map<String, Object> p = new LinkedHashMap<>();
            p.put("db2PolicynumInt", policyInt);
            p.put("caHPropertyType", x(82, 15));
            p.put("db2HBedroomsSint", bedroomsInt);
            p.put("db2HValueInt", valueInt);
            p.put("caHHouseName", x(108, 20));
            p.put("caHHouseNumber", x(128, 4));
            p.put("caHPostcode", x(132, 8));
            sqlcode = exec(() -> houseRepository.insertL409Lgapdb01(p));
            return checkInsert();
        }

        // ---- INSERT-MOTOR --------------------------------------------------------------------------------
        private boolean insertMotor() {
            int valueInt = bin9(num(112, 6));
            int ccInt = bin4(num(133, 4));
            int premiumInt = bin9(num(147, 6));
            int accidentsInt = bin9(num(153, 6));
            putEm(32, 16, " INSERT MOTOR ");

            Map<String, Object> p = new LinkedHashMap<>();
            p.put("db2PolicynumInt", policyInt);
            p.put("caMMake", x(82, 15));
            p.put("caMModel", x(97, 15));
            p.put("db2MValueInt", valueInt);
            p.put("caMRegnumber", x(118, 7));
            p.put("caMColour", x(125, 8));
            p.put("db2MCcSint", ccInt);
            p.put("caMManufactured", x(137, 10));
            p.put("db2MPremiumInt", premiumInt);
            p.put("db2MAccidentsInt", accidentsInt);
            sqlcode = exec(() -> motorRepository.insertL449Lgapdb01(p));
            return checkInsert();
        }

        // ---- INSERT-COMMERCIAL ---------------------------------------------------------------------------
        private boolean insertCommercial() {
            int fireP = bin4(num(877, 4));
            int firePrem = bin9(num(881, 8));
            int crimeP = bin4(num(889, 4));
            int crimePrem = bin9(num(893, 8));
            int floodP = bin4(num(901, 4));
            int floodPrem = bin9(num(905, 8));
            int weatherP = bin4(num(913, 4));
            int weatherPrem = bin9(num(917, 8));
            int status = bin4(num(925, 4));
            putEm(32, 16, " INSERT COMMER");

            Map<String, Object> p = new LinkedHashMap<>();
            p.put("db2PolicynumInt", policyInt);
            p.put("caLastchanged", x(30, 26));
            p.put("caIssueDate", x(10, 10));
            p.put("caExpiryDate", x(20, 10));
            p.put("caBAddress", x(82, 255));
            p.put("caBPostcode", x(337, 8));
            p.put("caBLatitude", x(345, 11));
            p.put("caBLongitude", x(356, 11));
            p.put("caBCustomer", x(367, 255));
            p.put("caBProptype", x(622, 255));
            p.put("db2BFireperilInt", fireP);
            p.put("db2BFirepremiumInt", firePrem);
            p.put("db2BCrimeperilInt", crimeP);
            p.put("db2BCrimepremiumInt", crimePrem);
            p.put("db2BFloodperilInt", floodP);
            p.put("db2BFloodpremiumInt", floodPrem);
            p.put("db2BWeatherperilInt", weatherP);
            p.put("db2BWeatherpremiumInt", weatherPrem);
            p.put("db2BStatusInt", status);
            p.put("caBRejectreason", x(929, 255));
            sqlcode = exec(() -> commercialRepository.insertL499Lgapdb01(p));
            return checkInsert();
        }

        /** IF SQLCODE NOT EQUAL 0: '90', error message, ABEND LGSQ (the RETURN after it is unreachable). */
        private boolean checkInsert() {
            if (sqlcode != 0) {
                setRc(90);
                if (!writeErrorMessage()) {
                    return false;
                }
                // EXEC CICS ABEND ABCODE('LGSQ'); the following RETURN never runs
                task.abend("LGSQ");
                return false;
            }
            return true;
        }

        // ---- WRITE-ERROR-MESSAGE -------------------------------------------------------------------------
        private boolean writeErrorMessage() {
            // MOVE SQLCODE TO EM-SQLRC  (PIC +9(5))
            putEm(57, 6, CobolEdit.format("+9(5)", BigDecimal.valueOf(sqlcode), false, null));
            // EXEC CICS ASKTIME / FORMATTIME MMDDYYYY(DATE1) TIME(TIME1)
            // DEFECT (kept): ABS-TIME is PIC S9(8) COMP, ASKTIME needs a 15-digit packed field.
            // Fix: declare ABS-TIME PIC S9(15) COMP-3.
            long abs = task.asktime();
            String emDate = CicsTask.formatDate(abs, "MMDDYYYY", "");
            String emTime = CicsTask.formatTime(abs, "");
            String msg = CobolRecords.fit(emDate, 8, cs) + " " + CobolRecords.fit(emTime, 6, cs) + " LGAPDB01"
                    + emVar;

            // Write output message to TDQ: LINK LGSTSQ with ERROR-MSG (87 bytes)
            // DEFECT (kept): LGSTSQ's COMMAREA is 90 bytes, ERROR-MSG is 87 (CA-ERROR-MSG is 99).
            if (!linkLgstsq(msg, msg.length())) {
                return false;
            }
            // Write 90 bytes or as much as we have of commarea to TDQ
            if (calen > 0) {
                String data = calen < 91 ? CobolRecords.text(rec, 0, calen, cs) : CobolRecords.text(rec, 0, 90, cs);
                data = CobolRecords.fit(data, 90, cs);
                if (!linkLgstsq("COMMAREA=" + data, 99)) {
                    return false;
                }
            }
            return true;
        }

        private boolean linkLgstsq(String text, int length) {
            LgstsqDfhcommarea dto = new LgstsqDfhcommarea();
            // CA-ERROR-MSG: CA-DATA follows the 9-byte 'COMMAREA=' literal; ERROR-MSG is passed whole
            dto.setCaData(length == 99 ? text.substring(9) : text);
            byte[] area = text.getBytes(cs);
            String resp = task.link("LGSTSQ", dto, length, area);
            if (!"NORMAL".equals(resp)) {
                task.abendOnCondition(resp);
                return false;
            }
            return !task.ended();
        }
    }

    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region
     *  (CicsTask.region()), run through runTask on `request`, passed by reference -- what it changes, the caller sees. */
    public Lgapdb01Dfhcommarea handleLink(Lgapdb01Dfhcommarea request) {
        log.info("Lgapdb01: handleLink");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("LGAPDB01", request);
        region.run(task, "LGAPDB01", this::runTask);
        return request;
    }

    /** #5053: handleLink with the raw bytes of the LINK's COMMAREA (passed by address: what the program
     *  leaves there the caller sees); lastLinkBytes() then answers the bytes it left. */
    public Lgapdb01Dfhcommarea handleLink(Lgapdb01Dfhcommarea request, byte[] area) {
        log.info("Lgapdb01: handleLink (bytes)");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("LGAPDB01", request, area);
        region.run(task, "LGAPDB01", this::runTask);
        byte[] left = task.linkAreaView();
        lastLinkBytes = task.linkAreaTaken() && left != null ? java.util.Arrays.copyOf(left, left.length) : null;
        return request;
    }

    // @facade-helper: the bytes the last byte-carrying handleLink's program left in the COMMAREA
    private byte[] lastLinkBytes;

    /** The bytes the last byte-carrying handleLink's program left in the LINK COMMAREA (a copy; null: it took
     *  none -- its DTO is the COMMAREA). @facade-helper */
    public byte[] lastLinkBytes() {
        return lastLinkBytes == null ? null : java.util.Arrays.copyOf(lastLinkBytes, lastLinkBytes.length);
    }

    /** EXEC CICS LINK PROGRAM(LGAPVS01) at 243: the CSD routes it to region DOR1 (distributed program link).
     *  Remote calls field testing: open (5 public / 0 private estates). */
    public Lgapvs01Dfhcommarea remoteLgapvs01L243(Lgapvs01Dfhcommarea request) {
        return dor1RemoteClient.linkLgapvs01(request);
    }

    /** EXEC CICS LINK PROGRAM(LGSTSQ) at base/src/lgapdb01.cbl:575, base/src/lgapdb01.cbl:583, base/src/lgapdb01.cbl:589.
     *  Call targets field testing: open (8 public / 0 private estates). */
    // TODO: this site passes ERROR-MSG; LGSTSQ receives CA-ERROR-MSG (base/src/lgacdb01.cbl) -- map one layout onto the other
    public LgstsqDfhcommarea linkLgstsq(LgstsqDfhcommarea request) {
        return lgstsqService.getObject().handleLink(request);
    }

    /** EXEC CICS LINK PROGRAM(LGAPVS01) at base/src/lgapdb01.cbl:243, COMMAREA(DFHCOMMAREA) LENGTH(32500): the target is data-driven (candidates the engine found: LGAPVS01 (value)).
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchLgapvs01L243(CicsTask task, String program, Object commarea, int length) {
        return task.link(program.stripTrailing(), commarea, length);
    }

    /**
     * EXEC CICS ABEND ABCODE(LGCA) at base/src/lgapdb01.cbl:168 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendLgcaL168() {
        throw new CicsAbendException("LGCA", "LGAPDB01", "base/src/lgapdb01.cbl:168");
    }

    /**
     * EXEC CICS ABEND ABCODE(LGSQ) at base/src/lgapdb01.cbl:393 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendLgsqL393() {
        throw new CicsAbendException("LGSQ", "LGAPDB01", "base/src/lgapdb01.cbl:393");
    }

    /**
     * EXEC CICS ABEND ABCODE(LGSQ) at base/src/lgapdb01.cbl:431 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendLgsqL431() {
        throw new CicsAbendException("LGSQ", "LGAPDB01", "base/src/lgapdb01.cbl:431");
    }

    /**
     * EXEC CICS ABEND ABCODE(LGSQ) at base/src/lgapdb01.cbl:477 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendLgsqL477() {
        throw new CicsAbendException("LGSQ", "LGAPDB01", "base/src/lgapdb01.cbl:477");
    }

    /**
     * EXEC CICS ABEND ABCODE(LGSQ) at base/src/lgapdb01.cbl:551 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendLgsqL551() {
        throw new CicsAbendException("LGSQ", "LGAPDB01", "base/src/lgapdb01.cbl:551");
    }

}
