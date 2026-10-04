/*
 * A hand translation of CBTRN02C (app/cbl/CBTRN02C.cbl) from
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
import com.gitgalaxy.modernized.entity.vsam.FdTranCatBalRecord;
import com.gitgalaxy.modernized.entity.vsam.FdTranCatBalRecordKey;
import com.gitgalaxy.modernized.entity.vsam.TranRecord;
import com.gitgalaxy.modernized.repository.vsam.AccountRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.CardXrefRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.FdTranCatBalRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.TranRecordRepository;
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
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * CBTRN02C -- post the daily transactions (job POSTTRAN step STEP15), ported by hand onto the generated
 * skeleton. Each daily transaction is validated (1500: its card in the cross reference, its account on file,
 * within the credit limit, before the account expires) and either posted -- the category balance created or
 * updated (2700), the account's balance and cycle totals updated (2800), the transaction written (2900) -- or
 * written to the rejects with a reason (2500). RETURN-CODE is 4 when any transaction was rejected.
 *
 * Every file I/O statement is one CobolFiles call, in the program's order, and its FILE STATUS drives the
 * program's own checks. Three behaviours of the original are kept as they are:
 * - A READ of XREF-FILE or ACCOUNT-FILE that fails with anything but "not found" runs neither INVALID KEY nor
 *   NOT INVALID KEY, and nothing tests the status: the program goes on with the record the previous READ left
 *   in CARD-XREF-RECORD / ACCOUNT-RECORD (DEFECT: an I/O error posts against the previous transaction's
 *   account. Fix: test the status after each READ and abend, as the other paragraphs do).
 * - 2800-UPDATE-ACCOUNT-REC never tests the REWRITE's status: a failed REWRITE is ignored (its INVALID KEY
 *   only sets reason 109, which nothing reads). DEFECT; fix: abend on any status but "00".
 * - The records are the program's own storage, not the store's: each READ copies the record out (a detached
 *   entity), so a REWRITE that does not happen changes nothing on file -- as a COBOL record area does not.
 */
@Service
public class Cbtrn02cService {

    private static final Logger log = LoggerFactory.getLogger(Cbtrn02cService.class);
    private static final Charset TEXT = StandardCharsets.ISO_8859_1;
    private static final int DALYTRAN_LEN = 350;

    private final AccountRecordRepository accountRecordRepository;
    private final CardXrefRecordRepository cardXrefRecordRepository;
    private final FdTranCatBalRecordRepository fdTranCatBalRecordRepository;
    private final TranRecordRepository tranRecordRepository;
    private final DatasetResolver datasets;
    private final CobolFiles files;

    @Value("${gitgalaxy.clock:}")
    private String clock = "";

    public Cbtrn02cService(AccountRecordRepository accountRecordRepository,
                           CardXrefRecordRepository cardXrefRecordRepository,
                           FdTranCatBalRecordRepository fdTranCatBalRecordRepository,
                           TranRecordRepository tranRecordRepository, DatasetResolver datasets, CobolFiles files) {
        this.accountRecordRepository = accountRecordRepository;
        this.cardXrefRecordRepository = cardXrefRecordRepository;
        this.fdTranCatBalRecordRepository = fdTranCatBalRecordRepository;
        this.tranRecordRepository = tranRecordRepository;
        this.datasets = datasets;
        this.files = files;
    }

    /** The program run as a batch step with no DD overrides and no PARM (#4342): runBatch's DD
     *  names resolved as the program declares them; returns the step's RETURN-CODE. */
    public int executeCbtrn02c() {
        return runBatch(List.of(), null);
    }

    /** The program's working storage between statements (CARD-XREF-RECORD, ACCOUNT-RECORD, the counters). */
    private static final class Work {
        CardXrefRecord xref = new CardXrefRecord();   // WS, never set before the first good READ: ACCT-ID 0
        AccountRecord account = new AccountRecord();
        int failReason;                               // WS-VALIDATION-FAIL-REASON 9(04)
        String failDesc = "";                         // WS-VALIDATION-FAIL-REASON-DESC X(76)
        long transactions;                            // WS-TRANSACTION-COUNT
        long rejects;                                 // WS-REJECT-COUNT

        Work() {
            xref.setXrefAcctId(0L);
        }
    }

    /** The batch entry: job POSTTRAN step STEP15 (app/jcl/POSTTRAN.jcl:23). */
    @Transactional
    public int runBatch(List<Dd> dds, String parm) {
        Sysout.display("START OF EXECUTION OF PROGRAM CBTRN02C");
        Path dalytran = datasets.path(dd(dds, "DALYTRAN"));
        Path rejects = datasets.path(dd(dds, "DALYREJS"));
        check(files.open("DALYTRAN", dalytran, true), "ERROR OPENING DALYTRAN");       // 0000-DALYTRAN-OPEN
        check(files.open("TRANFILE"), "ERROR OPENING TRANSACTION FILE");               // 0100-TRANFILE-OPEN
        check(files.open("XREFFILE"), "ERROR OPENING CROSS REF FILE");                 // 0200-XREFFILE-OPEN
        check(files.open("DALYREJS", rejects, false), "ERROR OPENING DALY REJECTS FILE");  // 0300-DALYREJS-OPEN
        check(files.open("ACCTFILE"), "ERROR OPENING ACCOUNT MASTER FILE");            // 0400-ACCTFILE-OPEN
        check(files.open("TCATBALF"), "ERROR OPENING TRANSACTION BALANCE FILE");       // 0500-TCATBALF-OPEN
        List<byte[]> daily = records(dalytran);
        OutputStream rejs;
        try {
            Files.createDirectories(rejects.getParent());
            rejs = Files.newOutputStream(rejects);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        Work w = new Work();
        try {
            Iterator<byte[]> cursor = daily.iterator();
            while (true) {
                CobolFiles.Read<byte[]> next = files.readNext("DALYTRAN", cursor);    // 1000-DALYTRAN-GET-NEXT
                if ("10".equals(next.status())) {
                    break;                                                           // APPL-EOF
                }
                check(next.status(), "ERROR READING DALYTRAN FILE");
                byte[] tran = next.record();
                w.transactions++;
                w.failReason = 0;
                w.failDesc = "";
                validate(w, tran);                                                   // 1500-VALIDATE-TRAN
                if (w.failReason == 0) {
                    post(w, tran);                                                   // 2000-POST-TRANSACTION
                } else {
                    w.rejects++;
                    writeReject(w, tran, rejs);                                      // 2500-WRITE-REJECT-REC
                }
            }
            check(files.close("DALYTRAN"), "ERROR CLOSING DALYTRAN FILE");          // 9000-DALYTRAN-CLOSE
            check(files.close("TRANFILE"), "ERROR CLOSING TRANSACTION FILE");        // 9100-TRANFILE-CLOSE
            String xrefStatus = files.close("XREFFILE");                              // 9200-XREFFILE-CLOSE
            check(xrefStatus, "ERROR CLOSING CROSS REF FILE");
            // 9300-DALYREJS-CLOSE. DEFECT KEPT (found by the #4056 SYSOUT comparison): on an error it MOVEs
            // XREFFILE-STATUS, not DALYREJS-STATUS, to IO-STATUS, so the job log shows the cross reference file's
            // status. One-line fix in the COBOL: MOVE DALYREJS-STATUS TO IO-STATUS.
            check(files.close("DALYREJS", rejs::close), "ERROR CLOSING DAILY REJECTS FILE", xrefStatus);
            check(files.close("ACCTFILE"), "ERROR CLOSING ACCOUNT FILE");            // 9400-ACCTFILE-CLOSE
            check(files.close("TCATBALF"), "ERROR CLOSING TRANSACTION BALANCE FILE"); // 9500-TCATBALF-CLOSE
        } finally {
            try {
                rejs.close();  // after an abend too: the harness's own file handle, not a CLOSE statement
            } catch (IOException e) {
                log.warn("closing DALYREJS: {}", e.toString());
            }
        }
        Sysout.display("TRANSACTIONS PROCESSED :", String.format(Locale.ROOT, "%09d", w.transactions));  // 9(09)
        Sysout.display("TRANSACTIONS REJECTED  :", String.format(Locale.ROOT, "%09d", w.rejects));
        Sysout.display("END OF EXECUTION OF PROGRAM CBTRN02C");
        return w.rejects > 0 ? 4 : 0;                                                // MOVE 4 TO RETURN-CODE
    }

    // ---- 1500-VALIDATE-TRAN ----------------------------------------------------------------------------
    private void validate(Work w, byte[] tran) {
        String cardNum = CobolRecords.text(tran, 262, 16, TEXT);                     // DALYTRAN-CARD-NUM
        CobolFiles.Read<CardXrefRecord> x = files.read("XREFFILE",                    // 1500-A-LOOKUP-XREF
                () -> cardXrefRecordRepository.findById(cardNum).map(this::copy));
        if ("23".equals(x.status())) {                                               // INVALID KEY
            w.failReason = 100;
            w.failDesc = "INVALID CARD NUMBER FOUND";
        } else if (x.found()) {                                                      // READ ... INTO
            w.xref = x.record();
        }                                                                            // any other status: see DEFECT
        if (w.failReason != 0) {
            return;
        }
        long acctId = w.xref.getXrefAcctId();                                        // 1500-B-LOOKUP-ACCT
        CobolFiles.Read<AccountRecord> a = files.read("ACCTFILE",
                () -> accountRecordRepository.findById(acctId).map(this::copy));
        if ("23".equals(a.status())) {                                               // INVALID KEY
            w.failReason = 101;
            w.failDesc = "ACCOUNT RECORD NOT FOUND";
        } else if (a.found()) {                                                      // NOT INVALID KEY
            w.account = a.record();
            BigDecimal amt = amount(tran);
            // COMPUTE WS-TEMP-BAL = ACCT-CURR-CYC-CREDIT - ACCT-CURR-CYC-DEBIT + DALYTRAN-AMT (S9(09)V99)
            BigDecimal temp = pic(w.account.getAcctCurrCycCredit().subtract(w.account.getAcctCurrCycDebit()).add(amt), 9, 2);
            if (w.account.getAcctCreditLimit().compareTo(temp) < 0) {
                w.failReason = 102;
                w.failDesc = "OVERLIMIT TRANSACTION";
            }
            // ACCT-EXPIRAION-DATE >= DALYTRAN-ORIG-TS (1:10): an alphanumeric comparison, byte by byte
            if (compareText(w.account.getAcctExpiraionDate(), CobolRecords.text(tran, 278, 10, TEXT)) < 0) {
                w.failReason = 103;
                w.failDesc = "TRANSACTION RECEIVED AFTER ACCT EXPIRATION";
            }
        }                                                                            // any other status: see DEFECT
    }

    // ---- 2000-POST-TRANSACTION -------------------------------------------------------------------------
    private void post(Work w, byte[] tran) {
        // TRAN-RECORD: the daily record's fields as they are, TRAN-PROC-TS the current DB2 timestamp
        byte[] rec = CobolRecords.blank(DALYTRAN_LEN, TEXT);
        System.arraycopy(tran, 0, rec, 0, 304);
        CobolRecords.putText(rec, 304, 26, db2Timestamp(), TEXT);
        BigDecimal amt = amount(tran);
        updateTcatbal(w, tran, amt);                                                 // 2700-UPDATE-TCATBAL
        updateAccount(w, amt);                                                       // 2800-UPDATE-ACCOUNT-REC
        TranRecord t = TranRecord.fromRecord(rec, TEXT);                             // 2900-WRITE-TRANSACTION-FILE
        boolean duplicate = tranRecordRepository.existsById(t.getTranId());
        String st = files.write("TRANFILE", () -> {
            if (!duplicate) {
                tranRecordRepository.save(t);
            }
        });
        check("00".equals(st) && duplicate ? "22" : st, "ERROR WRITING TO TRANSACTION FILE");
    }

    /** 2700-UPDATE-TCATBAL: the account / type / category balance, read (23: create it) and updated. */
    private void updateTcatbal(Work w, byte[] tran, BigDecimal amt) {
        FdTranCatBalRecordKey key = new FdTranCatBalRecordKey();
        key.setFdTrancatAcctId(w.xref.getXrefAcctId());                              // XREF-ACCT-ID
        key.setFdTrancatTypeCd(CobolRecords.text(tran, 16, 2, TEXT));               // DALYTRAN-TYPE-CD
        key.setFdTrancatCd(CobolRecords.zoned(tran, 18, 4, 0, TEXT).intValue());    // DALYTRAN-CAT-CD
        CobolFiles.Read<FdTranCatBalRecord> r = files.read("TCATBALF",
                () -> fdTranCatBalRecordRepository.findById(key).map(this::copy));
        boolean create = "23".equals(r.status());                                    // INVALID KEY
        if (create) {
            Sysout.display("TCATBAL record not found for key : ",                    // FD-TRAN-CAT-KEY
                    String.format(Locale.ROOT, "%011d", key.getFdTrancatAcctId()), key.getFdTrancatTypeCd(),
                    String.format(Locale.ROOT, "%04d", key.getFdTrancatCd()), ".. Creating.");
        } else {
            check(r.status(), "ERROR READING TRANSACTION BALANCE FILE");            // '00' OR '23' is APPL-AOK
        }
        if (create) {                                                                // 2700-A-CREATE-TCATBAL-REC
            byte[] rec = CobolRecords.blank(50, TEXT);                               // INITIALIZE, then the key
            CobolRecords.putZoned(rec, 0, 11, 0, false, BigDecimal.valueOf(key.getFdTrancatAcctId()), TEXT);
            CobolRecords.putText(rec, 11, 2, key.getFdTrancatTypeCd(), TEXT);
            CobolRecords.putZoned(rec, 13, 4, 0, false, BigDecimal.valueOf(key.getFdTrancatCd()), TEXT);
            CobolRecords.putZoned(rec, 17, 11, 2, true, pic(amt, 9, 2), TEXT);     // ADD DALYTRAN-AMT TO 0
            FdTranCatBalRecord bal = FdTranCatBalRecord.fromRecord(rec, TEXT);
            boolean duplicate = fdTranCatBalRecordRepository.existsById(key);  // a KSDS WRITE never replaces: 22
            String st = files.write("TCATBALF", () -> {
                if (!duplicate) {
                    fdTranCatBalRecordRepository.save(bal);
                }
            });
            check("00".equals(st) && duplicate ? "22" : st, "ERROR WRITING TRANSACTION BALANCE FILE");
        } else {                                                                     // 2700-B-UPDATE-TCATBAL-REC
            FdTranCatBalRecord bal = r.record();
            byte[] data = data(bal.getFdFdTranCatData(), 33);
            BigDecimal sum = pic(CobolRecords.zoned(data, 0, 11, 2, TEXT).add(amt), 9, 2);  // ADD ... TO TRAN-CAT-BAL
            CobolRecords.putZoned(data, 0, 11, 2, true, sum, TEXT);
            bal.setFdFdTranCatData(new String(data, TEXT));
            check(files.rewrite("TCATBALF", () -> fdTranCatBalRecordRepository.save(bal)),
                    "ERROR REWRITING TRANSACTION BALANCE FILE");
        }
    }

    /** 2800-UPDATE-ACCOUNT-REC: the balance and the cycle credit or debit; the REWRITE's status is not tested. */
    private void updateAccount(Work w, BigDecimal amt) {
        AccountRecord acct = w.account;
        acct.setAcctCurrBal(pic(acct.getAcctCurrBal().add(amt), 10, 2));
        if (amt.signum() >= 0) {
            acct.setAcctCurrCycCredit(pic(acct.getAcctCurrCycCredit().add(amt), 10, 2));
        } else {
            acct.setAcctCurrCycDebit(pic(acct.getAcctCurrCycDebit().add(amt), 10, 2));
        }
        AccountRecord saved = copy(acct);  // the record area as it is now: later changes are not on file
        boolean exists = accountRecordRepository.existsById(saved.getAcctId());
        files.rewrite("ACCTFILE", () -> {
            if (exists) {                                                            // INVALID KEY: reason 109, unread
                accountRecordRepository.save(saved);
            }
        });
    }

    /** 2500-WRITE-REJECT-REC: the daily record (350 bytes) and WS-VALIDATION-TRAILER (reason 9(04), X(76)). */
    private void writeReject(Work w, byte[] tran, OutputStream rejs) {
        byte[] rec = CobolRecords.blank(430, TEXT);
        System.arraycopy(tran, 0, rec, 0, DALYTRAN_LEN);
        CobolRecords.putZoned(rec, 350, 4, 0, false, BigDecimal.valueOf(w.failReason), TEXT);
        CobolRecords.putText(rec, 354, 76, w.failDesc, TEXT);
        check(files.write("DALYREJS", () -> rejs.write(rec)), "ERROR WRITING TO REJECTS FILE");
    }

    // ---- helpers ----------------------------------------------------------------------------------------
    private static Dd dd(List<Dd> dds, String name) {
        return dds.stream().filter(d -> name.equals(d.name())).findFirst().orElseThrow();
    }

    /** DALYTRAN's fixed-length records (RECFM=FB, 350 bytes), or none when the dataset is absent. */
    private static List<byte[]> records(Path file) {
        List<byte[]> out = new ArrayList<>();
        if (file == null || !Files.exists(file)) {
            return out;
        }
        try {
            byte[] all = Files.readAllBytes(file);
            for (int i = 0; i + DALYTRAN_LEN <= all.length; i += DALYTRAN_LEN) {
                out.add(Arrays.copyOfRange(all, i, i + DALYTRAN_LEN));
            }
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        return out;
    }

    private static BigDecimal amount(byte[] tran) {
        return CobolRecords.zoned(tran, 132, 11, 2, TEXT);                           // DALYTRAN-AMT S9(09)V99
    }

    private AccountRecord copy(AccountRecord a) {
        return AccountRecord.fromRecord(a.toRecord(TEXT), TEXT);
    }

    private CardXrefRecord copy(CardXrefRecord x) {
        return CardXrefRecord.fromRecord(x.toRecord(TEXT), TEXT);
    }

    private FdTranCatBalRecord copy(FdTranCatBalRecord b) {
        return FdTranCatBalRecord.fromRecord(b.toRecord(TEXT), TEXT);
    }

    /** An alphanumeric comparison: the shorter operand padded with spaces, then byte by byte. */
    private static int compareText(String a, String b) {
        String x = a == null ? "" : a;
        String y = b == null ? "" : b;
        int n = Math.max(x.length(), y.length());
        byte[] p = String.format(Locale.ROOT, "%-" + n + "s", x).getBytes(TEXT);
        byte[] q = String.format(Locale.ROOT, "%-" + n + "s", y).getBytes(TEXT);
        return Arrays.compareUnsigned(p, q);
    }

    /** FUNCTION CURRENT-DATE as a DB2 timestamp: YYYY-MM-DD-HH.MM.SS.hh0000 (Z-GET-DB2-FORMAT-TIMESTAMP). */
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

    /** A FILE STATUS the program treats as an error: the DISPLAYs, 9910-DISPLAY-IO-STATUS and
     *  9999-ABEND-PROGRAM (CALL 'CEE3ABD' with ABCODE 999). */
    private static void check(String status, String what) {
        check(status, what, status);
    }

    /** As above, with `shown` the status 9910-DISPLAY-IO-STATUS displays (IO-STATUS, as the paragraph moved it). */
    private static void check(String status, String what, String shown) {
        if ("00".equals(status)) {
            return;
        }
        Sysout.display(what);
        Sysout.display("FILE STATUS IS: NNNN", ioStatus04(shown));      // 9910-DISPLAY-IO-STATUS
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
