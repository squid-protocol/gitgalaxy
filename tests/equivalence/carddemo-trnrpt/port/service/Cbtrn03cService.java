package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.CobolAbend;
import com.gitgalaxy.modernized.batch.CobolFiles;
import com.gitgalaxy.modernized.batch.DatasetResolver;
import com.gitgalaxy.modernized.batch.Dd;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.entity.vsam.CardXrefRecord;
import com.gitgalaxy.modernized.entity.vsam.CobolEdit;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.FdTranCatRecord;
import com.gitgalaxy.modernized.entity.vsam.FdTranCatRecordKey;
import com.gitgalaxy.modernized.entity.vsam.FdTrantypeRec;
import com.gitgalaxy.modernized.repository.vsam.CardXrefRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.FdTranCatRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.FdTrantypeRecRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Iterator;
import java.util.List;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class Cbtrn03cService {

    private static final Logger log = LoggerFactory.getLogger(Cbtrn03cService.class);

    // The datasets are ASCII transfers (the original's SYSOUT shows readable text, status byte 'A' = 65):
    // records are read and written as ISO-8859-1, not IBM037.
    private static final Charset CS = StandardCharsets.ISO_8859_1;

    // TRAN-RECORD (CVTRA05Y, 350 bytes) offsets
    private static final int REC_LEN = 350;
    private static final int O_TYPE_CD = 16;
    private static final int O_CAT_CD = 18;
    private static final int O_SOURCE = 22;
    private static final int O_AMT = 132;
    private static final int O_CARD = 262;
    private static final int O_PROC_TS = 304;

    private final CardXrefRecordRepository cardXrefRecordRepository;
    private final FdTranCatRecordRepository fdTranCatRecordRepository;
    private final FdTrantypeRecRepository fdTrantypeRecRepository;
    private final CobolFiles files;
    private final DatasetResolver datasetResolver;

    public void executeCbtrn03c(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for CBTRN03C");
        // The program is a batch main line only: its whole PROCEDURE DIVISION is ported in runBatch.
    }

    /** AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS as BATCH SELECT XREF-FILE at app/cbl/CBTRN03C.cbl (SELECT XREF-FILE); VSAM defines field testing: open (3 public / 0 private estates). */
    // FD-CARDXREF-REC (key 16 + data 34) is read INTO CARD-XREF-RECORD: the entity follows CARD-XREF-RECORD.
    public Optional<CardXrefRecord> readXrefFile(String key) {
        return cardXrefRecordRepository.findById(key);
    }

    /** AWS.M2.CARDDEMO.TRANCATG.VSAM.KSDS as BATCH SELECT TRANCATG-FILE at app/cbl/CBTRN03C.cbl (SELECT TRANCATG-FILE); VSAM defines field testing: open (3 public / 0 private estates). */
    public Optional<FdTranCatRecord> readTrancatgFile(FdTranCatRecordKey key) {
        return fdTranCatRecordRepository.findById(key);
    }

    /** AWS.M2.CARDDEMO.TRANTYPE.VSAM.KSDS as BATCH SELECT TRANTYPE-FILE at app/cbl/CBTRN03C.cbl (SELECT TRANTYPE-FILE); VSAM defines field testing: open (3 public / 0 private estates). */
    public Optional<FdTrantypeRec> readTrantypeFile(String key) {
        return fdTrantypeRecRepository.findById(key);
    }

    /** The batch entry (#3622): run by job TRANREPT step STEP10R (app/jcl/TRANREPT.jcl:59).
     *  DD CARDXREF, DATEPARM, TRANCATG, TRANFILE (INPUT), TRANREPT (OUTPUT), TRANTYPE (INPUT).
     *  JCL job flow field testing: open (5 public / 0 private estates). */
    public int runBatch(List<Dd> dds, String parm) {
        return new Run(dds).main();
    }

    private static Dd find(List<Dd> dds, String name) {
        for (Dd d : dds) {
            if (name.equals(d.name())) {
                return d;
            }
        }
        return null;
    }

    private static String spaces(int n) {
        return " ".repeat(n);
    }

    private static Iterator<byte[]> chunks(Path p, int len) {
        List<byte[]> out = new ArrayList<>();
        if (p != null && Files.exists(p)) {
            try {
                byte[] all = Files.readAllBytes(p);
                byte sp = " ".getBytes(CS)[0];
                for (int i = 0; i < all.length; i += len) {
                    byte[] r = new byte[len];
                    Arrays.fill(r, sp);
                    System.arraycopy(all, i, r, 0, Math.min(len, all.length - i));
                    out.add(r);
                }
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        }
        return out.iterator();
    }

    /** ADD into a PIC S9(09)V99 field without SIZE ERROR: high-order digits are lost. */
    private static BigDecimal fit(BigDecimal v) {
        BigInteger u = v.setScale(2, RoundingMode.DOWN).unscaledValue();
        BigInteger m = u.abs().mod(BigInteger.TEN.pow(11));
        return new BigDecimal(u.signum() < 0 ? m.negate() : m, 2);
    }

    /** One execution of the program: its WORKING-STORAGE. */
    private final class Run {
        private final Path tranPath;
        private final Path reptPath;
        private final Path dateParmPath;
        private Iterator<byte[]> tranIt;
        private Iterator<byte[]> dateIt;

        private String endOfFile = "N";
        private String firstTime = "Y";
        private long lineCounter = 0;
        private final long pageSize = 20;
        private BigDecimal pageTotal = BigDecimal.ZERO.setScale(2);
        private BigDecimal accountTotal = BigDecimal.ZERO.setScale(2);
        private BigDecimal grandTotal = BigDecimal.ZERO.setScale(2);
        private String currCardNum = spaces(16);
        private String startDate = spaces(10);
        private String endDate = spaces(10);
        private String reptStartDate = spaces(10);
        private String reptEndDate = spaces(10);

        private byte[] tran;
        private CardXrefRecord xref;
        private String tranTypeDesc = spaces(50);
        private String tranCatTypeDesc = spaces(50);

        Run(List<Dd> dds) {
            // GDG (+1) names are resolved once: a second call after the file exists would name the next generation
            tranPath = path(dds, "TRANFILE");
            reptPath = path(dds, "TRANREPT");
            dateParmPath = path(dds, "DATEPARM");
            tran = CobolRecords.blank(REC_LEN, CS);
            CobolRecords.putZoned(tran, O_AMT, 11, 2, true, BigDecimal.ZERO, CS);
        }

        private Path path(List<Dd> dds, String name) {
            Dd d = find(dds, name);
            return d == null ? null : datasetResolver.path(d);
        }

        private String t(int off, int len) {
            return CobolRecords.text(tran, off, len, CS);
        }

        private BigDecimal tranAmt() {
            BigDecimal v = CobolRecords.zoned(tran, O_AMT, 11, 2, CS);
            return v == null ? BigDecimal.ZERO.setScale(2) : v;
        }

        int main() {
            Sysout.display("START OF EXECUTION OF PROGRAM CBTRN03C");
            tranFileOpen();
            reptFileOpen();
            cardXrefOpen();
            tranTypeOpen();
            tranCatgOpen();
            dateParmOpen();

            dateParmRead();

            // PROCEDURE DIVISION main loop (PERFORM UNTIL END-OF-FILE = 'Y')
            while (!"Y".equals(endOfFile)) {
                if ("N".equals(endOfFile)) {
                    tranFileGetNext();
                    if (CobolCompare.ge(t(O_PROC_TS, 10), startDate) && CobolCompare.le(t(O_PROC_TS, 10), endDate)) {
                        // CONTINUE
                    } else {
                        // DEFECT: NEXT SENTENCE jumps past the period that closes END-PERFORM, so the first
                        // record outside the date range ends the whole loop (no totals). Fix: CONTINUE-style
                        // skip (e.g. a nested IF / GO TO loop end) instead of NEXT SENTENCE.
                        break;
                    }
                    if ("N".equals(endOfFile)) {
                        Sysout.display(CobolRecords.text(tran, 0, REC_LEN, CS));
                        String cardNum = t(O_CARD, 16);
                        if (!CobolCompare.eq(currCardNum, cardNum)) {
                            if ("N".equals(firstTime)) {
                                writeAccountTotals();
                            }
                            currCardNum = cardNum;
                            lookupXref(cardNum);
                        }
                        String typeCd = t(O_TYPE_CD, 2);
                        lookupTranType(typeCd);
                        lookupTranCatg(typeCd, t(O_CAT_CD, 4));
                        writeTransactionReport();
                    } else {
                        // DEFECT: at end of file TRAN-RECORD still holds the last record, so its amount is added
                        // a second time to the page / account totals; the last account's total is never written.
                        // Fix: do not ADD TRAN-AMT here and PERFORM 1120-WRITE-ACCOUNT-TOTALS first.
                        Sysout.display("TRAN-AMT ", Sysout.number(tranAmt(), 11, 2, true));
                        Sysout.display("WS-PAGE-TOTAL", Sysout.number(pageTotal, 11, 2, true));
                        pageTotal = fit(pageTotal.add(tranAmt()));
                        accountTotal = fit(accountTotal.add(tranAmt()));
                        writePageTotals();
                        writeGrandTotals();
                    }
                }
            }

            tranFileClose();
            reptFileClose();
            cardXrefClose();
            tranTypeClose();
            tranCatgClose();
            dateParmClose();

            Sysout.display("END OF EXECUTION OF PROGRAM CBTRN03C");
            return 0;
        }

        // 0550-DATEPARM-READ
        private void dateParmRead() {
            CobolFiles.Read<byte[]> r = files.readNext("DATEPARM", dateIt);
            int applResult;
            switch (r.status()) {
                case "00" -> applResult = 0;
                case "10" -> applResult = 16;
                default -> applResult = 12;
            }
            if (applResult == 0) {
                // READ ... INTO WS-DATEPARM-RECORD (21 bytes of the 80)
                startDate = CobolRecords.text(r.record(), 0, 10, CS);
                endDate = CobolRecords.text(r.record(), 11, 10, CS);
                Sysout.display("Reporting from ", startDate, " to ", endDate);
            } else if (applResult == 16) {
                endOfFile = "Y";
            } else {
                Sysout.display("ERROR READING DATEPARM FILE");
                displayIoStatus(r.status());
                abend();
            }
        }

        // 1000-TRANFILE-GET-NEXT
        private void tranFileGetNext() {
            CobolFiles.Read<byte[]> r = files.readNext("TRANFILE", tranIt);
            int applResult;
            switch (r.status()) {
                case "00" -> applResult = 0;
                case "10" -> applResult = 16;
                default -> applResult = 12;
            }
            if (applResult == 0) {
                tran = r.record();
            } else if (applResult == 16) {
                endOfFile = "Y";
            } else {
                Sysout.display("ERROR READING TRANSACTION FILE");
                displayIoStatus(r.status());
                abend();
            }
        }

        // 1100-WRITE-TRANSACTION-REPORT
        private void writeTransactionReport() {
            if ("Y".equals(firstTime)) {
                firstTime = "N";
                reptStartDate = startDate;
                reptEndDate = endDate;
                writeHeaders();
            }
            if (lineCounter % pageSize == 0) {
                writePageTotals();
                writeHeaders();
            }
            pageTotal = fit(pageTotal.add(tranAmt()));
            accountTotal = fit(accountTotal.add(tranAmt()));
            writeDetail();
        }

        // 1110-WRITE-PAGE-TOTALS
        private void writePageTotals() {
            String line = CobolRecords.fit("Page Total", 11, CS) + ".".repeat(86)
                    + CobolEdit.format("+ZZZ,ZZZ,ZZZ.ZZ", pageTotal, false, null);
            writeReportRec(line);
            grandTotal = fit(grandTotal.add(pageTotal));
            pageTotal = BigDecimal.ZERO.setScale(2);
            addLine();
            writeReportRec("-".repeat(133));
            addLine();
        }

        // 1120-WRITE-ACCOUNT-TOTALS
        private void writeAccountTotals() {
            String line = CobolRecords.fit("Account Total", 13, CS) + ".".repeat(84)
                    + CobolEdit.format("+ZZZ,ZZZ,ZZZ.ZZ", accountTotal, false, null);
            writeReportRec(line);
            accountTotal = BigDecimal.ZERO.setScale(2);
            addLine();
            writeReportRec("-".repeat(133));
            addLine();
        }

        // 1110-WRITE-GRAND-TOTALS
        private void writeGrandTotals() {
            String line = CobolRecords.fit("Grand Total", 11, CS) + ".".repeat(86)
                    + CobolEdit.format("+ZZZ,ZZZ,ZZZ.ZZ", grandTotal, false, null);
            writeReportRec(line);
        }

        // 1120-WRITE-HEADERS
        private void writeHeaders() {
            String name = CobolRecords.fit("DALYREPT", 38, CS) + CobolRecords.fit("Daily Transaction Report", 41, CS)
                    + "Date Range: " + reptStartDate + " to " + reptEndDate;
            writeReportRec(name);
            addLine();
            writeReportRec(spaces(133));
            addLine();
            String h1 = CobolRecords.fit("Transaction ID", 17, CS) + CobolRecords.fit("Account ID", 12, CS)
                    + CobolRecords.fit("Transaction Type", 19, CS) + CobolRecords.fit("Tran Category", 35, CS)
                    + CobolRecords.fit("Tran Source", 14, CS) + " " + CobolRecords.fit("        Amount", 16, CS);
            writeReportRec(h1);
            addLine();
            writeReportRec("-".repeat(133));
            addLine();
        }

        private void addLine() {
            lineCounter = (lineCounter + 1) % 1_000_000_000L;
        }

        // 1111-WRITE-REPORT-REC
        private void writeReportRec(String line) {
            byte[] b = CobolRecords.fit(line, 133, CS).getBytes(CS);
            String st = files.write("TRANREPT",
                    () -> Files.write(reptPath, b, StandardOpenOption.CREATE, StandardOpenOption.APPEND));
            if (!"00".equals(st)) {
                Sysout.display("ERROR WRITING REPTFILE");
                displayIoStatus(st);
                abend();
            }
        }

        // 1120-WRITE-DETAIL
        private void writeDetail() {
            BigDecimal acct = xref == null ? BigDecimal.ZERO : CobolRecords.decimal(xref.getXrefAcctId());
            BigDecimal cat = CobolRecords.zoned(tran, O_CAT_CD, 4, 0, CS);
            String line = t(0, 16) + " "
                    + Sysout.number(acct, 11, 0, false) + " "
                    + t(O_TYPE_CD, 2) + "-"
                    + CobolRecords.fit(tranTypeDesc, 15, CS) + " "
                    + Sysout.number(cat == null ? BigDecimal.ZERO : cat, 4, 0, false) + "-"
                    + CobolRecords.fit(tranCatTypeDesc, 29, CS) + " "
                    + t(O_SOURCE, 10) + spaces(4)
                    + CobolEdit.format("-ZZZ,ZZZ,ZZZ.ZZ", tranAmt(), false, null)
                    + spaces(2);
            writeReportRec(line);
            addLine();
        }

        // 1500-A-LOOKUP-XREF
        private void lookupXref(String key) {
            CobolFiles.Read<CardXrefRecord> r = files.read("CARDXREF", () -> readXrefFile(key));
            if ("00".equals(r.status())) {
                xref = CardXrefRecord.fromRecord(r.record().toRecord(CS), CS);
            } else if (r.status().startsWith("2")) {
                Sysout.display("INVALID CARD NUMBER : ", key);
                displayIoStatus("23");
                abend();
            }
            // any other status: no INVALID KEY, the previous record stays
        }

        // 1500-B-LOOKUP-TRANTYPE
        private void lookupTranType(String key) {
            CobolFiles.Read<FdTrantypeRec> r = files.read("TRANTYPE", () -> readTrantypeFile(key));
            if ("00".equals(r.status())) {
                FdTrantypeRec own = FdTrantypeRec.fromRecord(r.record().toRecord(CS), CS);
                tranTypeDesc = CobolRecords.fit(own.getFdTranData(), 50, CS);
            } else if (r.status().startsWith("2")) {
                Sysout.display("INVALID TRANSACTION TYPE : ", key);
                displayIoStatus("23");
                abend();
            }
        }

        // 1500-C-LOOKUP-TRANCATG
        private void lookupTranCatg(String typeCd, String catRaw) {
            BigDecimal cat = CobolRecords.zoned(tran, O_CAT_CD, 4, 0, CS);
            FdTranCatRecordKey key = new FdTranCatRecordKey();
            key.setFdTranTypeCd(typeCd);
            key.setFdTranCatCd(cat == null ? 0 : cat.intValue());
            CobolFiles.Read<FdTranCatRecord> r = files.read("TRANCATG", () -> readTrancatgFile(key));
            if ("00".equals(r.status())) {
                FdTranCatRecord own = FdTranCatRecord.fromRecord(r.record().toRecord(CS), CS);
                tranCatTypeDesc = CobolRecords.fit(own.getFdTranCatData(), 50, CS);
            } else if (r.status().startsWith("2")) {
                Sysout.display("INVALID TRAN CATG KEY : ", typeCd, catRaw);
                displayIoStatus("23");
                abend();
            }
        }

        // 0000-TRANFILE-OPEN
        private void tranFileOpen() {
            String st = files.open("TRANFILE", tranPath, true);
            tranIt = chunks(tranPath, REC_LEN);
            check(st, "ERROR OPENING TRANFILE");
        }

        // 0100-REPTFILE-OPEN
        private void reptFileOpen() {
            String st = files.open("TRANREPT", reptPath, false);
            if ("00".equals(st) && reptPath != null) {
                try {
                    if (reptPath.getParent() != null) {
                        Files.createDirectories(reptPath.getParent());
                    }
                    Files.write(reptPath, new byte[0]);
                } catch (IOException e) {
                    throw new UncheckedIOException(e);
                }
            }
            check(st, "ERROR OPENING REPTFILE");
        }

        // 0200-CARDXREF-OPEN
        private void cardXrefOpen() {
            check(files.open("CARDXREF"), "ERROR OPENING CROSS REF FILE");
        }

        // 0300-TRANTYPE-OPEN
        private void tranTypeOpen() {
            check(files.open("TRANTYPE"), "ERROR OPENING TRANSACTION TYPE FILE");
        }

        // 0400-TRANCATG-OPEN
        private void tranCatgOpen() {
            check(files.open("TRANCATG"), "ERROR OPENING TRANSACTION CATG FILE");
        }

        // 0500-DATEPARM-OPEN
        private void dateParmOpen() {
            String st = files.open("DATEPARM", dateParmPath, true);
            dateIt = chunks(dateParmPath, 80);
            check(st, "ERROR OPENING DATE PARM FILE");
        }

        // 9000-TRANFILE-CLOSE
        private void tranFileClose() {
            check(files.close("TRANFILE"), "ERROR CLOSING POSTED TRANSACTION FILE");
        }

        // 9100-REPTFILE-CLOSE
        private void reptFileClose() {
            check(files.close("TRANREPT"), "ERROR CLOSING REPORT FILE");
        }

        // 9200-CARDXREF-CLOSE
        private void cardXrefClose() {
            check(files.close("CARDXREF"), "ERROR CLOSING CROSS REF FILE");
        }

        // 9300-TRANTYPE-CLOSE
        private void tranTypeClose() {
            check(files.close("TRANTYPE"), "ERROR CLOSING TRANSACTION TYPE FILE");
        }

        // 9400-TRANCATG-CLOSE
        private void tranCatgClose() {
            check(files.close("TRANCATG"), "ERROR CLOSING TRANSACTION CATG FILE");
        }

        // 9500-DATEPARM-CLOSE
        private void dateParmClose() {
            check(files.close("DATEPARM"), "ERROR CLOSING DATE PARM FILE");
        }

        /** The shared OPEN / CLOSE tail: IF status = '00' ... ELSE DISPLAY msg, 9910, 9999. */
        private void check(String status, String msg) {
            if (!"00".equals(status)) {
                Sysout.display(msg);
                displayIoStatus(status);
                abend();
            }
        }

        // 9999-ABEND-PROGRAM
        private void abend() {
            Sysout.display("ABENDING PROGRAM");
            throw CobolAbend.user(999, "CEE3ABD called by CBTRN03C");
        }

        // 9910-DISPLAY-IO-STATUS
        private void displayIoStatus(String status) {
            char s1 = status.charAt(0);
            char s2 = status.charAt(1);
            boolean numeric = s1 >= '0' && s1 <= '9' && s2 >= '0' && s2 <= '9';
            if (!numeric || s1 == '9') {
                int two = String.valueOf(s2).getBytes(CS)[0] & 0xFF;  // TWO-BYTES-RIGHT of the binary
                Sysout.display("FILE STATUS IS: NNNN", String.valueOf(s1),
                        Sysout.number(BigDecimal.valueOf(two), 3, 0, false));
            } else {
                Sysout.display("FILE STATUS IS: NNNN", "00" + status);
            }
        }
    }

}
