/*
 * A hand translation of CBACT04C (app/cbl/CBACT04C.cbl) from
 * https://github.com/aws-samples/aws-mainframe-modernization-carddemo at commit
 * 59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e, onto the Java GitGalaxy generates from it. That source is
 * Copyright Amazon.com, Inc. or its affiliates and licensed Apache-2.0; this file is derived from it
 * and modified (translated), under the same licence -- see LICENSE and NOTICE in this case's directory.
 */
package com.gitgalaxy.modernized.service;

import com.gitgalaxy.modernized.batch.DatasetResolver;
import com.gitgalaxy.modernized.batch.Dd;
import com.gitgalaxy.modernized.entity.vsam.AccountRecord;
import com.gitgalaxy.modernized.entity.vsam.CardXrefRecord;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.FdDiscgrpRec;
import com.gitgalaxy.modernized.entity.vsam.FdDiscgrpRecKey;
import com.gitgalaxy.modernized.entity.vsam.FdTranCatBalRecord;
import com.gitgalaxy.modernized.entity.vsam.TranRecord;
import com.gitgalaxy.modernized.repository.vsam.AccountRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.CardXrefRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.FdDiscgrpRecRepository;
import com.gitgalaxy.modernized.repository.vsam.FdTranCatBalRecordRepository;
import java.io.IOException;
import java.io.OutputStream;
import java.io.UncheckedIOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * CBACT04C -- the interest calculator (job INTCALC step STEP15), ported by hand onto the generated
 * skeleton (#3624's vertical slice): each block below is the COBOL paragraph it ports, keeping its
 * semantics -- COMPUTE / ADD without ROUNDED truncate, and a result too long for its PICTURE loses its
 * high-order digits; a missing account or cross reference abends; and, as in the COBOL, the last account
 * is never rewritten (see the end of run()). The step's PARM (PARM-DATE) prefixes each transaction id. The clock is
 * `gitgalaxy.clock` (an ISO local date-time) when set -- the harness pins it -- else the system clock.
 */
@Service
public class Cbact04cService {

    private static final Logger log = LoggerFactory.getLogger(Cbact04cService.class);
    private static final Charset TEXT = StandardCharsets.ISO_8859_1;

    private final AccountRecordRepository accountRecordRepository;
    private final CardXrefRecordRepository cardXrefRecordRepository;
    private final FdDiscgrpRecRepository fdDiscgrpRecRepository;
    private final FdTranCatBalRecordRepository fdTranCatBalRecordRepository;
    private final DatasetResolver datasets;

    @Value("${gitgalaxy.clock:}")
    private String clock = "";

    public Cbact04cService(AccountRecordRepository accountRecordRepository,
                           CardXrefRecordRepository cardXrefRecordRepository,
                           FdDiscgrpRecRepository fdDiscgrpRecRepository,
                           FdTranCatBalRecordRepository fdTranCatBalRecordRepository, DatasetResolver datasets) {
        this.accountRecordRepository = accountRecordRepository;
        this.cardXrefRecordRepository = cardXrefRecordRepository;
        this.fdDiscgrpRecRepository = fdDiscgrpRecRepository;
        this.fdTranCatBalRecordRepository = fdTranCatBalRecordRepository;
        this.datasets = datasets;
    }

    public void executeCbact04c() {
        log.info("CBACT04C runs as a batch step: see runBatch");
    }

    public Optional<AccountRecord> readAccountFile(Long key) {
        return accountRecordRepository.findById(key);
    }

    public AccountRecord rewriteAccountFile(AccountRecord record) {
        return accountRecordRepository.save(record);
    }

    public Optional<CardXrefRecord> readXrefFile(String key) {
        return cardXrefRecordRepository.findById(key);
    }

    public Optional<FdDiscgrpRec> readDiscgrpFile(FdDiscgrpRecKey key) {
        return fdDiscgrpRecRepository.findById(key);
    }

    public List<FdTranCatBalRecord> readAllTcatbalFile() {
        return fdTranCatBalRecordRepository.findAll();
    }

    /** The batch entry: job INTCALC step STEP15 (app/jcl/INTCALC.jcl:22), PARM='2022071800'. */
    @Transactional
    public int runBatch(List<Dd> dds, String parm) {
        log.info("START OF EXECUTION OF PROGRAM CBACT04C");
        String parmDate = String.format("%-10s", parm == null ? "" : parm).substring(0, 10);
        Path transact = datasets.path(dds.stream().filter(d -> "TRANSACT".equals(d.name())).findFirst().orElseThrow());
        List<FdTranCatBalRecord> balances = fdTranCatBalRecordRepository.findAll(
                Sort.by("id.fdTrancatAcctId", "id.fdTrancatTypeCd", "id.fdTrancatCd"));  // TCATBAL-FILE, key order
        try {
            Files.createDirectories(transact.getParent());
            try (OutputStream tranFile = Files.newOutputStream(transact)) {
                run(balances, parmDate, tranFile);
            }
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        log.info("END OF EXECUTION OF PROGRAM CBACT04C");
        return 0;
    }

    private void run(List<FdTranCatBalRecord> balances, String parmDate, OutputStream tranFile) throws IOException {
        Long lastAcctNum = null;                         // WS-LAST-ACCT-NUM
        boolean firstTime = true;                        // WS-FIRST-TIME
        BigDecimal totalInt = BigDecimal.ZERO;           // WS-TOTAL-INT      S9(09)V99
        int tranIdSuffix = 0;                            // WS-TRANID-SUFFIX  9(06)
        AccountRecord account = null;                    // ACCOUNT-RECORD
        CardXrefRecord xref = null;                      // CARD-XREF-RECORD
        for (FdTranCatBalRecord tcat : balances) {       // 1000-TCATBALF-GET-NEXT
            long acctId = tcat.getId().getFdTrancatAcctId();
            String typeCd = tcat.getId().getFdTrancatTypeCd();
            int catCd = tcat.getId().getFdTrancatCd();
            BigDecimal tranCatBal = CobolRecords.zoned(data(tcat.getFdFdTranCatData(), 33), 0, 11, 2, TEXT);
            if (lastAcctNum == null || acctId != lastAcctNum) {
                if (!firstTime) {
                    updateAccount(account, totalInt);    // 1050-UPDATE-ACCOUNT
                } else {
                    firstTime = false;
                }
                totalInt = BigDecimal.ZERO;
                lastAcctNum = acctId;
                account = accountRecordRepository.findById(acctId)       // 1100-GET-ACCT-DATA
                        .orElseThrow(() -> abend("ACCOUNT NOT FOUND: " + acctId));
                xref = cardXrefRecordRepository.findByXrefAcctId(acctId).stream()  // 1110-GET-XREF-DATA
                        .min(Comparator.comparing(CardXrefRecord::getXrefCardNum))
                        .orElseThrow(() -> abend("ACCOUNT NOT FOUND: " + acctId));
            }
            BigDecimal rate = interestRate(account.getAcctGroupId(), typeCd, catCd);  // 1200-GET-INTEREST-RATE
            if (rate.signum() != 0) {
                // 1300-COMPUTE-INTEREST: COMPUTE WS-MONTHLY-INT = (TRAN-CAT-BAL * DIS-INT-RATE) / 1200
                BigDecimal monthlyInt = pic(tranCatBal.multiply(rate).divide(BigDecimal.valueOf(1200), 2,
                        RoundingMode.DOWN), 9, 2);
                totalInt = pic(totalInt.add(monthlyInt), 9, 2);             // ADD ... TO WS-TOTAL-INT
                tranIdSuffix = (tranIdSuffix + 1) % 1_000_000;              // 1300-B-WRITE-TX
                tranFile.write(interestTransaction(parmDate, tranIdSuffix, account, xref, monthlyInt).toRecord(TEXT));
                // 1400-COMPUTE-FEES: not implemented in the COBOL either (EXIT)
            }
        }
        // END-OF-FILE: the COBOL's `ELSE PERFORM 1050-UPDATE-ACCOUNT` never runs -- PERFORM UNTIL tests
        // END-OF-FILE before each pass, so the pass that reads end of file is the last, and the branch for
        // END-OF-FILE = 'Y' inside the loop is unreachable. The LAST account's interest is therefore never
        // added to its balance (its transactions are still written): a defect of the original, found by the
        // #3624 equivalence harness, kept here so the port behaves as the program does. The fix is one
        // line -- updateAccount(account, totalInt) -- and a business decision.
    }

    /** 1050-UPDATE-ACCOUNT: ADD WS-TOTAL-INT TO ACCT-CURR-BAL, zero the cycle, REWRITE. */
    private void updateAccount(AccountRecord account, BigDecimal totalInt) {
        account.setAcctCurrBal(pic(account.getAcctCurrBal().add(totalInt), 10, 2));
        account.setAcctCurrCycCredit(BigDecimal.ZERO.setScale(2));
        account.setAcctCurrCycDebit(BigDecimal.ZERO.setScale(2));
        accountRecordRepository.save(account);
    }

    /** 1200-GET-INTEREST-RATE: the disclosure group's rate, else the DEFAULT group's (status 23). */
    private BigDecimal interestRate(String groupId, String typeCd, int catCd) {
        Optional<FdDiscgrpRec> group = fdDiscgrpRecRepository.findById(discKey(groupId, typeCd, catCd));
        if (group.isEmpty()) {
            log.info("DISCLOSURE GROUP RECORD MISSING");
            log.info("TRY WITH DEFAULT GROUP CODE");
            group = fdDiscgrpRecRepository.findById(discKey("DEFAULT", typeCd, catCd));  // 1200-A
        }
        FdDiscgrpRec rec = group.orElseThrow(() -> abend("ERROR READING DEFAULT DISCLOSURE GROUP"));
        return CobolRecords.zoned(data(rec.getFdDiscgrpData(), 34), 0, 6, 2, TEXT);  // DIS-INT-RATE S9(04)V99
    }

    private static FdDiscgrpRecKey discKey(String groupId, String typeCd, int catCd) {
        FdDiscgrpRecKey k = new FdDiscgrpRecKey();
        k.setFdDisAcctGroupId(String.format("%-10s", groupId));   // X(10), as the record holds it
        k.setFdDisTranTypeCd(typeCd);
        k.setFdDisTranCatCd(catCd);
        return k;
    }

    /** 1300-B-WRITE-TX: the interest transaction TRAN-RECORD. */
    private TranRecord interestTransaction(String parmDate, int suffix, AccountRecord account, CardXrefRecord xref,
                                           BigDecimal monthlyInt) {
        TranRecord t = new TranRecord();
        t.setTranId(parmDate + String.format("%06d", suffix));          // STRING PARM-DATE WS-TRANID-SUFFIX
        t.setTranTypeCd("01");
        t.setTranCatCd(5);
        t.setTranSource("System");
        t.setTranDesc("Int. for a/c " + String.format("%011d", account.getAcctId()));
        t.setTranAmt(monthlyInt);
        t.setTranMerchantId(0);
        t.setTranMerchantName("");
        t.setTranMerchantCity("");
        t.setTranMerchantZip("");
        t.setTranCardNum(xref.getXrefCardNum());
        String ts = db2Timestamp();                                       // Z-GET-DB2-FORMAT-TIMESTAMP
        t.setTranOrigTs(ts);
        t.setTranProcTs(ts);
        return t;
    }

    /** FUNCTION CURRENT-DATE as a DB2 timestamp: YYYY-MM-DD-HH.MM.SS.hh0000. */
    private String db2Timestamp() {
        LocalDateTime now = clock.isBlank() ? LocalDateTime.now() : LocalDateTime.parse(clock);
        return String.format("%04d-%02d-%02d-%02d.%02d.%02d.%02d0000", now.getYear(), now.getMonthValue(),
                now.getDayOfMonth(), now.getHour(), now.getMinute(), now.getSecond(), now.getNano() / 10_000_000);
    }

    /** A value stored in PIC S9(intDigits)V9(scale): decimals truncated, high-order digits lost. */
    private static BigDecimal pic(BigDecimal v, int intDigits, int scale) {
        BigDecimal t = v.setScale(scale, RoundingMode.DOWN);
        return t.remainder(BigDecimal.TEN.pow(intDigits)).setScale(scale, RoundingMode.DOWN);
    }

    /** An entity's data field back as the record bytes it was cut from (padded to its width). */
    private static byte[] data(String field, int width) {
        return String.format("%-" + width + "s", field == null ? "" : field).getBytes(TEXT);
    }

    private static IllegalStateException abend(String why) {
        log.error(why);
        log.error("ABENDING PROGRAM");
        return new IllegalStateException("CBACT04C ABEND 999: " + why);
    }
}
