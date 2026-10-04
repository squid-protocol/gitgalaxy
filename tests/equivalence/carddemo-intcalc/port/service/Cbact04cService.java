/*
 * A hand translation of CBACT04C (app/cbl/CBACT04C.cbl) from
 * https://github.com/aws-samples/aws-mainframe-modernization-carddemo at commit
 * 59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e, onto the Java GitGalaxy generates from it. That source is
 * Copyright Amazon.com, Inc. or its affiliates and licensed Apache-2.0; this file is derived from it
 * and modified (translated), under the same licence -- see LICENSE and NOTICE in this case's directory.
 */
package com.gitgalaxy.modernized.service;

import com.gitgalaxy.modernized.batch.CobolAbend;
import com.gitgalaxy.modernized.batch.CobolFiles;
import com.gitgalaxy.modernized.batch.DatasetResolver;
import com.gitgalaxy.modernized.batch.Dd;
import com.gitgalaxy.modernized.batch.Sysout;
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
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
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
 * Every file I/O statement is one CobolFiles call, in the program's order, and its FILE STATUS drives the
 * program's own checks: any status the COBOL treats as an error ends in 9999-ABEND-PROGRAM (ABEND U0999).
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
    private final CobolFiles files;

    @Value("${gitgalaxy.clock:}")
    private String clock = "";

    public Cbact04cService(AccountRecordRepository accountRecordRepository,
                           CardXrefRecordRepository cardXrefRecordRepository,
                           FdDiscgrpRecRepository fdDiscgrpRecRepository,
                           FdTranCatBalRecordRepository fdTranCatBalRecordRepository, DatasetResolver datasets,
                           CobolFiles files) {
        this.accountRecordRepository = accountRecordRepository;
        this.cardXrefRecordRepository = cardXrefRecordRepository;
        this.fdDiscgrpRecRepository = fdDiscgrpRecRepository;
        this.fdTranCatBalRecordRepository = fdTranCatBalRecordRepository;
        this.datasets = datasets;
        this.files = files;
    }

    /** The program run as a batch step with no DD overrides and no PARM (#4342): runBatch's DD
     *  names resolved as the program declares them; returns the step's RETURN-CODE. */
    public int executeCbact04c() {
        return runBatch(List.of(), null);
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

    /** TCATBAL-FILE read sequentially: a KSDS returns its records in key order (TRANCAT-ACCT-ID, TYPE, CD). */
    public List<FdTranCatBalRecord> readAllTcatbalFile() {
        return fdTranCatBalRecordRepository.findAll(
                Sort.by("id.fdTrancatAcctId", "id.fdTrancatTypeCd", "id.fdTrancatCd"));
    }

    /** The batch entry: job INTCALC step STEP15 (app/jcl/INTCALC.jcl:22), PARM='2022071800'. */
    @Transactional
    public int runBatch(List<Dd> dds, String parm) {
        Sysout.display("START OF EXECUTION OF PROGRAM CBACT04C");
        String parmDate = String.format(Locale.ROOT, "%-10s", parm == null ? "" : parm).substring(0, 10);
        Path transact = datasets.path(dds.stream().filter(d -> "TRANSACT".equals(d.name())).findFirst().orElseThrow());
        check(files.open("TCATBALF"), "ERROR OPENING TRANSACTION CATEGORY BALANCE");   // 0000-TCATBALF-OPEN
        String xrefOpen = files.open("XREFFILE");                                       // 0100-XREFFILE-OPEN
        check(xrefOpen, "ERROR OPENING CROSS REF FILE", xrefOpen);  // DISPLAY '...'   XREFFILE-STATUS
        check(files.open("DISCGRP"), "ERROR OPENING DALY REJECTS FILE");                // 0200-DISCGRP-OPEN
        check(files.open("ACCTFILE"), "ERROR OPENING ACCOUNT MASTER FILE");             // 0300-ACCTFILE-OPEN
        check(files.open("TRANSACT", transact, false), "ERROR OPENING TRANSACTION FILE");  // 0400-TRANFILE-OPEN
        List<FdTranCatBalRecord> balances = readAllTcatbalFile();                        // TCATBAL-FILE
        OutputStream tranFile;
        try {
            Files.createDirectories(transact.getParent());
            tranFile = Files.newOutputStream(transact);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        try {
            run(balances.iterator(), parmDate, tranFile);
            check(files.close("TCATBALF"), "ERROR CLOSING TRANSACTION BALANCE FILE");    // 9000-TCATBALF-CLOSE
            check(files.close("XREFFILE"), "ERROR CLOSING CROSS REF FILE");              // 9100-XREFFILE-CLOSE
            check(files.close("DISCGRP"), "ERROR CLOSING DISCLOSURE GROUP FILE");        // 9200-DISCGRP-CLOSE
            check(files.close("ACCTFILE"), "ERROR CLOSING ACCOUNT FILE");                // 9300-ACCTFILE-CLOSE
            check(files.close("TRANSACT", tranFile::close), "ERROR CLOSING TRANSACTION FILE");  // 9400-TRANFILE-CLOSE
        } finally {
            try {
                tranFile.close();  // after an abend too: the harness's own file handle, not a CLOSE statement
            } catch (IOException e) {
                log.warn("closing TRANSACT: {}", e.toString());
            }
        }
        Sysout.display("END OF EXECUTION OF PROGRAM CBACT04C");
        return 0;
    }

    private void run(Iterator<FdTranCatBalRecord> cursor, String parmDate, OutputStream tranFile) {
        Long lastAcctNum = null;                         // WS-LAST-ACCT-NUM
        boolean firstTime = true;                        // WS-FIRST-TIME
        BigDecimal totalInt = BigDecimal.ZERO;           // WS-TOTAL-INT      S9(09)V99
        int tranIdSuffix = 0;                            // WS-TRANID-SUFFIX  9(06)
        AccountRecord account = null;                    // ACCOUNT-RECORD
        CardXrefRecord xref = null;                      // CARD-XREF-RECORD
        while (true) {
            CobolFiles.Read<FdTranCatBalRecord> next = files.readNext("TCATBALF", cursor);  // 1000-TCATBALF-GET-NEXT
            if ("10".equals(next.status())) {
                break;                                   // APPL-EOF: END-OF-FILE = 'Y'
            }
            check(next.status(), "ERROR READING TRANSACTION CATEGORY FILE");
            FdTranCatBalRecord tcat = next.record();
            Sysout.display(new String(tcat.toRecord(TEXT), TEXT));  // DISPLAY TRAN-CAT-BAL-RECORD
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
                CobolFiles.Read<AccountRecord> acct = files.read("ACCTFILE",   // 1100-GET-ACCT-DATA
                        () -> accountRecordRepository.findById(acctId));
                if ("23".equals(acct.status())) {        // INVALID KEY
                    Sysout.display("ACCOUNT NOT FOUND: ", String.format(Locale.ROOT, "%011d", acctId));
                }
                check(acct.status(), "ERROR READING ACCOUNT FILE");
                account = acct.record();
                CobolFiles.Read<CardXrefRecord> x = files.read("XREFFILE",     // 1110-GET-XREF-DATA
                        () -> cardXrefRecordRepository.findByXrefAcctId(acctId).stream()
                                .min(Comparator.comparing(CardXrefRecord::getXrefCardNum)));
                if ("23".equals(x.status())) {           // INVALID KEY
                    Sysout.display("ACCOUNT NOT FOUND: ", String.format(Locale.ROOT, "%011d", acctId));
                }
                check(x.status(), "ERROR READING XREF FILE");
                xref = x.record();
            }
            BigDecimal rate = interestRate(account.getAcctGroupId(), typeCd, catCd);  // 1200-GET-INTEREST-RATE
            if (rate.signum() != 0) {
                // 1300-COMPUTE-INTEREST: COMPUTE WS-MONTHLY-INT = (TRAN-CAT-BAL * DIS-INT-RATE) / 1200
                BigDecimal monthlyInt = pic(tranCatBal.multiply(rate).divide(BigDecimal.valueOf(1200), 2,
                        RoundingMode.DOWN), 9, 2);
                totalInt = pic(totalInt.add(monthlyInt), 9, 2);             // ADD ... TO WS-TOTAL-INT
                tranIdSuffix = (tranIdSuffix + 1) % 1_000_000;              // 1300-B-WRITE-TX
                byte[] tx = interestTransaction(parmDate, tranIdSuffix, account, xref, monthlyInt).toRecord(TEXT);
                check(files.write("TRANSACT", () -> tranFile.write(tx)), "ERROR WRITING TRANSACTION RECORD");
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
        check(files.rewrite("ACCTFILE", () -> accountRecordRepository.save(account)), "ERROR RE-WRITING ACCOUNT FILE");
    }

    /** 1200-GET-INTEREST-RATE: the disclosure group's rate, else the DEFAULT group's (status 23). */
    private BigDecimal interestRate(String groupId, String typeCd, int catCd) {
        CobolFiles.Read<FdDiscgrpRec> group = files.read("DISCGRP",
                () -> fdDiscgrpRecRepository.findById(discKey(groupId, typeCd, catCd)));
        if ("23".equals(group.status())) {               // INVALID KEY
            Sysout.display("DISCLOSURE GROUP RECORD MISSING");
            Sysout.display("TRY WITH DEFAULT GROUP CODE");
        } else {
            check(group.status(), "ERROR READING DISCLOSURE GROUP FILE");  // '00' OR '23' is APPL-AOK
        }
        if ("23".equals(group.status())) {               // 1200-A-GET-DEFAULT-INT-RATE
            group = files.read("DISCGRP", () -> fdDiscgrpRecRepository.findById(discKey("DEFAULT", typeCd, catCd)));
            check(group.status(), "ERROR READING DEFAULT DISCLOSURE GROUP");
        }
        return CobolRecords.zoned(data(group.record().getFdDiscgrpData(), 34), 0, 6, 2, TEXT);  // DIS-INT-RATE S9(04)V99
    }

    private static FdDiscgrpRecKey discKey(String groupId, String typeCd, int catCd) {
        FdDiscgrpRecKey k = new FdDiscgrpRecKey();
        k.setFdDisAcctGroupId(String.format(Locale.ROOT, "%-10s", groupId));   // X(10), as the record holds it
        k.setFdDisTranTypeCd(typeCd);
        k.setFdDisTranCatCd(catCd);
        return k;
    }

    /** 1300-B-WRITE-TX: the interest transaction TRAN-RECORD. */
    private TranRecord interestTransaction(String parmDate, int suffix, AccountRecord account, CardXrefRecord xref,
                                           BigDecimal monthlyInt) {
        TranRecord t = new TranRecord();
        t.setTranId(parmDate + String.format(Locale.ROOT, "%06d", suffix));          // STRING PARM-DATE WS-TRANID-SUFFIX
        t.setTranTypeCd("01");
        t.setTranCatCd(5);
        t.setTranSource("System");
        t.setTranDesc("Int. for a/c " + String.format(Locale.ROOT, "%011d", account.getAcctId()));
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
        return String.format(Locale.ROOT, "%04d-%02d-%02d-%02d.%02d.%02d.%02d0000", now.getYear(), now.getMonthValue(),
                now.getDayOfMonth(), now.getHour(), now.getMinute(), now.getSecond(), now.getNano() / 10_000_000);
    }

    /** A value stored in PIC S9(intDigits)V9(scale): decimals truncated, high-order digits lost. */
    private static BigDecimal pic(BigDecimal v, int intDigits, int scale) {
        BigDecimal t = v.setScale(scale, RoundingMode.DOWN);
        return t.remainder(BigDecimal.TEN.pow(intDigits)).setScale(scale, RoundingMode.DOWN);
    }

    /** An entity's data field back as the record bytes it was cut from (padded to its width). */
    private static byte[] data(String field, int width) {
        return String.format(Locale.ROOT, "%-" + width + "s", field == null ? "" : field).getBytes(TEXT);
    }

    /** A FILE STATUS the program treats as an error ("00" is APPL-AOK): the DISPLAYs, 9910-DISPLAY-IO-STATUS
     *  and 9999-ABEND-PROGRAM (CALL 'CEE3ABD' with ABCODE 999). */
    private static void check(String status, String what) {
        check(status, what, "");
    }

    /** As above, the DISPLAY of `what` followed by `more` (DISPLAY 'ERROR OPENING CROSS REF FILE' XREFFILE-STATUS). */
    private static void check(String status, String what, String more) {
        if ("00".equals(status)) {
            return;
        }
        Sysout.display(what, more);
        Sysout.display("FILE STATUS IS: NNNN", ioStatus04(status));     // 9910-DISPLAY-IO-STATUS
        Sysout.display("ABENDING PROGRAM");                             // 9999-ABEND-PROGRAM
        throw CobolAbend.user(999, what + " (FILE STATUS " + status + ")");
    }

    /** 9910-DISPLAY-IO-STATUS's IO-STATUS-04: '00' and the status when it is numeric and not 9x; else IO-STAT1 and
     *  IO-STAT2's byte as the low byte of TWO-BYTES-BINARY (PIC 9(4) BINARY), moved to IO-STATUS-0403 (3 digits). */
    private static String ioStatus04(String status) {
        boolean numeric = status.chars().allMatch(Character::isDigit);
        if (numeric && status.charAt(0) != '9') {
            return "00" + status;
        }
        int low = status.getBytes(TEXT)[1] & 0xFF;
        return status.charAt(0) + String.format(Locale.ROOT, "%03d", low % 1000);
    }
}
