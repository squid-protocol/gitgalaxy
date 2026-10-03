package com.gitgalaxy.modernized.service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.UpdaccDfhcommarea;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.repository.db2.AccountRepository;
import com.gitgalaxy.modernized.repository.db2.Db2Dates;
import com.gitgalaxy.modernized.util.CobolCompare;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
@RequiredArgsConstructor
public class UpdaccService {

    private static final Logger log = LoggerFactory.getLogger(UpdaccService.class);

    /** COPY SORTCODE: 77 SORTCODE PIC 9(6) VALUE 987654. */
    private static final int SORTCODE = 987654;

    private final AccountRepository accountRepository;

    public void executeUpdacc(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for UPDACC");
        // UPDACC has no entry other than the CICS task (runTask) and LINK (handleLink); nothing to do here.
    }

    /** PROCEDURE DIVISION run as a CICS task: PREMIERE / A010, then GET-ME-OUT-OF-HERE (EXEC CICS RETURN). */
    public void runTask(CicsTask task) {
        log.info("Updacc: runTask");
        if (!task.hasCommarea()) {
            // The original addresses DFHCOMMAREA without checking EIBCALEN (storage violation, ASRA). Kept: no guard.
            task.abend("ASRA");
            return;
        }
        UpdaccDfhcommarea comm = task.commarea(UpdaccDfhcommarea.class);
        updateAccount(comm);      // A010: PERFORM UPDATE-ACCOUNT-DB2
        task.returnTransid(null, null);   // GET-ME-OUT-OF-HERE: EXEC CICS RETURN
    }

    /** Another program LINKed / XCTLed to this one: the same logic on the caller's COMMAREA. */
    public UpdaccDfhcommarea handleLink(UpdaccDfhcommarea request) {
        log.info("Updacc: handleLink");
        updateAccount(request);
        return request;
    }

    /** A010 + UPDATE-ACCOUNT-DB2 (UAD010..UAD999). */
    private void updateAccount(UpdaccDfhcommarea comm) {
        // A010
        comm.setCommScode(String.format(Locale.ROOT, "%06d", SORTCODE));   // MOVE SORTCODE TO COMM-SCODE
        int desiredSortCode = SORTCODE;                                     // MOVE SORTCODE TO DESIRED-SORT-CODE

        // UAD010
        int commAccno = comm.getCommAccno() == null ? 0 : comm.getCommAccno();
        int desiredAccNo = Math.floorMod(commAccno, 100000000);             // MOVE COMM-ACCNO TO DESIRED-ACC-NO
        String hvSortcode = String.format(Locale.ROOT, "%06d", desiredSortCode);
        String hvAccNo = String.format(Locale.ROOT, "%08d", desiredAccNo);

        Map<String, Object> key = new HashMap<>();
        key.put("hvAccountSortcode", hvSortcode);
        key.put("hvAccountAccNo", hvAccNo);

        // EXEC SQL SELECT ... (UPDACC.cbl:191)
        int sqlcode = 0;
        Map<String, Object> row = null;
        try {
            row = accountRepository.selectL191Updacc(key);
        } catch (EmptyResultDataAccessException e) {
            sqlcode = 100;
        } catch (DataAccessException e) {
            sqlcode = -904;
        }
        String hvEyecatcher = null;
        String hvCustNo = null;
        String hvOpened = null;
        String hvLastStmt = null;
        String hvNextStmt = null;
        BigDecimal hvAvailBal = null;
        BigDecimal hvActualBal = null;
        if (row != null) {
            // No indicator variables in the original: a NULL column is SQLCODE -305.
            Object eye = col(row, "ACCOUNT_EYECATCHER");
            Object cust = col(row, "ACCOUNT_CUSTOMER_NUMBER");
            Object opened = col(row, "ACCOUNT_OPENED");
            Object last = col(row, "ACCOUNT_LAST_STATEMENT");
            Object next = col(row, "ACCOUNT_NEXT_STATEMENT");
            Object avail = col(row, "ACCOUNT_AVAILABLE_BALANCE");
            Object actual = col(row, "ACCOUNT_ACTUAL_BALANCE");
            if (eye == null || cust == null || opened == null || last == null || next == null
                    || avail == null || actual == null
                    || col(row, "ACCOUNT_TYPE") == null || col(row, "ACCOUNT_INTEREST_RATE") == null
                    || col(row, "ACCOUNT_OVERDRAFT_LIMIT") == null) {
                sqlcode = -305;
            } else {
                hvEyecatcher = CobolRecords.fit(eye.toString(), 4, CobolRecords.charset());
                hvCustNo = CobolRecords.fit(cust.toString(), 10, CobolRecords.charset());
                hvOpened = Db2Dates.date(opened);
                hvLastStmt = Db2Dates.date(last);
                hvNextStmt = Db2Dates.date(next);
                hvAvailBal = CobolRecords.decimal(avail);
                hvActualBal = CobolRecords.decimal(actual);
            }
        }

        // IF SQLCODE NOT = 0
        if (sqlcode != 0) {
            comm.setCommSuccess("N");
            Sysout.display("ERROR: UPDACC returned ", sqlcodeDisplay(sqlcode), " on SELECT");
            return;   // GO TO UAD999
        }

        // IF (COMM-ACC-TYPE = SPACES OR COMM-ACC-TYPE(1:1) = ' ')
        String accType = comm.getCommAccType() == null ? "" : comm.getCommAccType();
        if (CobolCompare.eq(accType, "") || accType.charAt(0) == ' ') {
            comm.setCommSuccess("N");
            Sysout.display("ERROR: UPDACC has invalid account-type");
            return;   // GO TO UAD999
        }

        // MOVE COMM-ACC-TYPE / COMM-OVERDRAFT / COMM-INT-RATE TO the host variables
        String hvAccType = CobolRecords.fit(accType, 8, CobolRecords.charset());
        int commOverdraft = comm.getCommOverdraft() == null ? 0 : comm.getCommOverdraft();
        int hvOverdraft = Math.floorMod(commOverdraft, 1000000000);    // S9(9) COMP
        BigDecimal commRate = comm.getCommIntRate() == null ? BigDecimal.ZERO : comm.getCommIntRate();
        BigDecimal hvIntRate = commRate.setScale(2, RoundingMode.DOWN);

        // EXEC SQL UPDATE ... (UPDACC.cbl:278)
        Map<String, Object> upd = new HashMap<>(key);
        upd.put("hvAccountAccType", hvAccType);
        upd.put("hvAccountIntRate", hvIntRate);
        upd.put("hvAccountOverdraftLim", hvOverdraft);
        sqlcode = 0;
        try {
            int n = accountRepository.updateL278Updacc(upd);
            if (n == 0) {
                sqlcode = 100;
            }
        } catch (DataAccessException e) {
            sqlcode = -904;
        }
        if (sqlcode != 0) {
            comm.setCommSuccess("N");
            Sysout.display("ERROR: UPDACC returned ", sqlcodeDisplay(sqlcode), " on UPDATE");
            return;   // GO TO UAD999
        }

        // Success: refresh the COMMAREA from the host variables
        comm.setCommEye(hvEyecatcher);
        comm.setCommCustno(hvCustNo);
        comm.setCommScode(hvSortcode);
        comm.setCommAccno(CobolRecords.numval(hvAccNo.strip()).intValue());
        comm.setCommAccType(hvAccType);
        comm.setCommIntRate(hvIntRate);
        comm.setCommOpened(ddmmyyyy(hvOpened));
        comm.setCommOverdraft(hvOverdraft);
        comm.setCommLastStmtDt(ddmmyyyy(hvLastStmt));
        comm.setCommNextStmtDt(ddmmyyyy(hvNextStmt));
        comm.setCommAvailBal(hvAvailBal.setScale(2, RoundingMode.DOWN));
        comm.setCommActualBal(hvActualBal.setScale(2, RoundingMode.DOWN));
        comm.setCommSuccess("Y");
    }

    /** MOVE X(10) 'yyyy-mm-dd' TO DB2-DATE-REFORMAT, then YR / MNTH / DAY into the DDMMYYYY redefined group. */
    private static int ddmmyyyy(String iso) {
        int yr = CobolRecords.numval(iso.substring(0, 4)).intValue();
        int mnth = CobolRecords.numval(iso.substring(5, 7)).intValue();
        int day = CobolRecords.numval(iso.substring(8, 10)).intValue();
        return day * 1000000 + mnth * 10000 + yr;
    }

    /** SQLCODE-DISPLAY: PIC S9(8) SIGN LEADING SEPARATE. */
    private static String sqlcodeDisplay(int sqlcode) {
        return String.format(Locale.ROOT, "%+09d", sqlcode);
    }

    private static Object col(Map<String, Object> row, String name) {
        for (Map.Entry<String, Object> e : row.entrySet()) {
            if (e.getKey().equalsIgnoreCase(name)) {
                return e.getValue();
            }
        }
        return null;
    }

}
