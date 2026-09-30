package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.CobolAbend;
import com.gitgalaxy.modernized.batch.CobolFiles;
import com.gitgalaxy.modernized.batch.DatasetResolver;
import com.gitgalaxy.modernized.batch.Dd;
import com.gitgalaxy.modernized.entity.vsam.CardXrefRecord;
import com.gitgalaxy.modernized.entity.vsam.CobolEdit;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.FdTranCatRecord;
import com.gitgalaxy.modernized.entity.vsam.FdTranCatRecordKey;
import com.gitgalaxy.modernized.entity.vsam.FdTrantypeRec;
import com.gitgalaxy.modernized.repository.vsam.CardXrefRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.FdTranCatRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.FdTrantypeRecRepository;
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
import java.util.Locale;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class Cbtrn03cService {

    private static final Logger log = LoggerFactory.getLogger(Cbtrn03cService.class);

    private static final Charset CS = StandardCharsets.ISO_8859_1;
    private static final int TRAN_LEN = 350;      // FD-TRANFILE-REC: 304 + 26 + 20
    private static final int DATEPARM_LEN = 80;   // FD-DATEPARM-REC
    private static final int REPT_LEN = 133;      // FD-REPTFILE-REC
    private static final long LINE_MOD = 1_000_000_000L;   // WS-LINE-COUNTER PIC 9(09)
    private static final int PAGE_SIZE = 20;                // WS-PAGE-SIZE

    private final CardXrefRecordRepository cardXrefRecordRepository;
    private final FdTranCatRecordRepository fdTranCatRecordRepository;
    private final FdTrantypeRecRepository fdTrantypeRecRepository;
    private final CobolFiles cobolFiles;
    private final DatasetResolver datasetResolver;

    /** The business logic of CBTRN03C is a batch program: it runs in {@link #runBatch}. */
    public void executeCbtrn03c(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for CBTRN03C");
    }

    /** AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS as BATCH SELECT XREF-FILE at app/cbl/CBTRN03C.cbl (SELECT XREF-FILE); VSAM defines field testing: open (3 public / 0 private estates). */
    // FD-CARDXREF-REC (16-byte key + 34 data) is read INTO CARD-XREF-RECORD: the entity is that record.
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
     *  DD CARDXREF, DATEPARM, TRANCATG, TRANFILE, TRANTYPE (INPUT), TRANREPT (OUTPUT).
     *  The program never sets RETURN-CODE: it ends with 0 (or abends). */
    public int runBatch(List<Dd> dds, String parm) {
        new Run(dds).main();
        return 0;
    }

    // ------------------------------------------------------------------ helpers

    private static String fit(String s, int n) {
        String v = s == null ? "" : s;
        if (v.length() >= n) {
            return v.substring(0, n);
        }
        return v + " ".repeat(n - v.length());
    }

    /** ADD into a PIC S9(09)V99 field without SIZE ERROR: decimals truncated, high-order digits lost. */
    private static BigDecimal add(BigDecimal a, BigDecimal b) {
        BigInteger u = a.add(b).setScale(2, RoundingMode.DOWN).unscaledValue();
        BigInteger m = u.abs().mod(BigInteger.TEN.pow(11));
        return new BigDecimal(u.signum() < 0 ? m.negate() : m, 2);
    }

    private static Iterator<byte[]> records(Path file, int len) {
        List<byte[]> out = new ArrayList<>();
        if (file != null && Files.exists(file)) {
            try {
                byte[] all = Files.readAllBytes(file);
                for (int off = 0; off < all.length; off += len) {
                    byte[] rec = new byte[len];
                    Arrays.fill(rec, (byte) ' ');
                    System.arraycopy(all, off, rec, 0, Math.min(len, all.length - off));
                    out.add(rec);
                }
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        }
        return out.iterator();
    }

    private static Path pathOf(DatasetResolver resolver, List<Dd> dds, String name) {
        for (Dd d : dds) {
            if (name.equals(d.name())) {
                return resolver.path(d);
            }
        }
        return null;
    }

    private static boolean isDigit(char c) {
        return c >= '0' && c <= '9';
    }

    /** One run of the program: its WORKING-STORAGE and paragraphs. */
    private final class Run {
        private final Path tranPath;
        private final Path reptPath;
        private final Path datePath;
        private Iterator<byte[]> tranIt;
        private Iterator<byte[]> dateIt;

        // TRAN-RECORD (CVTRA05Y), initial: alphanumerics spaces, numerics zero
        private String tranId = fit("", 16);
        private String tranTypeCd = fit("", 2);
        private String tranCatCdText = "0000";
        private String tranSource = fit("", 10);
        private BigDecimal tranAmt = new BigDecimal("0.00");
        private String tranCardNum = fit("", 16);
        private String tranProcTs = fit("", 26);

        // CARD-XREF-RECORD / TRAN-TYPE-RECORD / TRAN-CAT-RECORD
        private long xrefAcctId = 0;
        private String tranTypeDesc = fit("", 50);
        private String tranCatTypeDesc = fit("", 50);

        // WS-DATEPARM-RECORD
        private String wsStartDate = fit("", 10);
        private String wsEndDate = fit("", 10);
        private String reptStartDate = fit("", 10);
        private String reptEndDate = fit("", 10);

        // WS-REPORT-VARS
        private char wsFirstTime = 'Y';
        private long wsLineCounter = 0;
        private BigDecimal wsPageTotal = new BigDecimal("0.00");
        private BigDecimal wsAccountTotal = new BigDecimal("0.00");
        private BigDecimal wsGrandTotal = new BigDecimal("0.00");
        private String wsCurrCardNum = fit("", 16);

        private char endOfFile = 'N';

        Run(List<Dd> dds) {
            // resolved once: a (+1) generation is re-counted on every call
            tranPath = pathOf(datasetResolver, dds, "TRANFILE");
            reptPath = pathOf(datasetResolver, dds, "TRANREPT");
            datePath = pathOf(datasetResolver, dds, "DATEPARM");
        }

        // PROCEDURE DIVISION main line
        void main() {
            log.info("START OF EXECUTION OF PROGRAM CBTRN03C");
            tranfileOpen();
            reptfileOpen();
            cardxrefOpen();
            trantypeOpen();
            trancatgOpen();
            dateparmOpen();

            dateparmRead();

            while (endOfFile != 'Y') {
                if (endOfFile == 'N') {
                    tranfileGetNext();
                    if (tranProcTs.substring(0, 10).compareTo(wsStartDate) >= 0
                            && tranProcTs.substring(0, 10).compareTo(wsEndDate) <= 0) {
                        // CONTINUE
                    } else {
                        // NEXT SENTENCE: jumps past the period after END-PERFORM, ending the loop
                        // (DEFECT kept, see notes)
                        break;
                    }
                    if (endOfFile == 'N') {
                        log.info("{}", tranRecordText());
                        if (!wsCurrCardNum.equals(tranCardNum)) {
                            if (wsFirstTime == 'N') {
                                writeAccountTotals();   // 1120-WRITE-ACCOUNT-TOTALS
                            }
                            wsCurrCardNum = tranCardNum;
                            lookupXref(tranCardNum);    // MOVE TRAN-CARD-NUM TO FD-XREF-CARD-NUM
                        }
                        lookupTrantype(tranTypeCd);
                        lookupTrancatg(tranTypeCd, catCd());
                        writeTransactionReport();
                    } else {
                        // end of file, TRAN-RECORD still holds the last record read
                        log.info("TRAN-AMT {}", tranAmt.toPlainString());
                        log.info("WS-PAGE-TOTAL{}", wsPageTotal.toPlainString());
                        wsPageTotal = add(wsPageTotal, tranAmt);
                        wsAccountTotal = add(wsAccountTotal, tranAmt);
                        writePageTotals();      // 1110-WRITE-PAGE-TOTALS
                        writeGrandTotals();     // 1110-WRITE-GRAND-TOTALS
                    }
                }
            }

            tranfileClose();
            reptfileClose();
            cardxrefClose();
            trantypeClose();
            trancatgClose();
            dateparmClose();

            log.info("END OF EXECUTION OF PROGRAM CBTRN03C");
        }

        private int catCd() {
            BigDecimal v = CobolRecords.zoned(tranCatCdText.getBytes(CS), 0, 4, 0, CS);
            return v == null ? 0 : v.intValue();
        }

        private String tranRecordText() {
            return tranId + tranTypeCd + tranCatCdText + tranSource + fit("", 100)
                    + tranAmt.toPlainString() + tranCardNum + tranProcTs;
        }

        // 0550-DATEPARM-READ
        private void dateparmRead() {
            CobolFiles.Read<byte[]> r = cobolFiles.readNext("DATEPARM", dateIt);
            String st = r.status();
            int applResult;
            if ("00".equals(st)) {
                if (r.record() != null) {
                    String s = new String(r.record(), CS);   // READ ... INTO WS-DATEPARM-RECORD
                    wsStartDate = fit(s.substring(0, 10), 10);
                    wsEndDate = fit(s.substring(11, 21), 10);
                }
                applResult = 0;
            } else if ("10".equals(st)) {
                applResult = 16;
            } else {
                applResult = 12;
            }
            if (applResult == 0) {
                log.info("Reporting from {} to {}", wsStartDate, wsEndDate);
            } else if (applResult == 16) {
                endOfFile = 'Y';
            } else {
                log.info("ERROR READING DATEPARM FILE");
                displayIoStatus(st);
                throw abend();
            }
        }

        // 1000-TRANFILE-GET-NEXT
        private void tranfileGetNext() {
            CobolFiles.Read<byte[]> r = cobolFiles.readNext("TRANFILE", tranIt);
            String st = r.status();
            int applResult;
            if ("00".equals(st)) {
                if (r.record() != null) {
                    moveTranRecord(r.record());   // READ ... INTO TRAN-RECORD
                }
                applResult = 0;
            } else if ("10".equals(st)) {
                applResult = 16;
            } else {
                applResult = 12;
            }
            if (applResult == 0) {
                // CONTINUE
            } else if (applResult == 16) {
                endOfFile = 'Y';
            } else {
                log.info("ERROR READING TRANSACTION FILE");
                displayIoStatus(st);
                throw abend();
            }
        }

        private void moveTranRecord(byte[] rec) {
            tranId = CobolRecords.text(rec, 0, 16, CS);
            tranTypeCd = CobolRecords.text(rec, 16, 2, CS);
            tranCatCdText = CobolRecords.text(rec, 18, 4, CS);
            tranSource = CobolRecords.text(rec, 22, 10, CS);
            BigDecimal amt = CobolRecords.zoned(rec, 132, 11, 2, CS);
            tranAmt = amt == null ? new BigDecimal("0.00") : amt;
            tranCardNum = CobolRecords.text(rec, 262, 16, CS);
            tranProcTs = CobolRecords.text(rec, 304, 26, CS);
        }

        // 1100-WRITE-TRANSACTION-REPORT
        private void writeTransactionReport() {
            if (wsFirstTime == 'Y') {
                wsFirstTime = 'N';
                reptStartDate = wsStartDate;
                reptEndDate = wsEndDate;
                writeHeaders();
            }
            if (wsLineCounter % PAGE_SIZE == 0) {
                writePageTotals();
                writeHeaders();
            }
            wsPageTotal = add(wsPageTotal, tranAmt);
            wsAccountTotal = add(wsAccountTotal, tranAmt);
            writeDetail();
        }

        private void nextLine() {
            wsLineCounter = (wsLineCounter + 1) % LINE_MOD;
        }

        private String edited(BigDecimal v) {
            return CobolEdit.format("+ZZZ,ZZZ,ZZZ.ZZ", v, false, null);
        }

        // 1110-WRITE-PAGE-TOTALS
        private void writePageTotals() {
            writeReportRec(fit("Page Total", 11) + ".".repeat(86) + edited(wsPageTotal));
            wsGrandTotal = add(wsGrandTotal, wsPageTotal);
            wsPageTotal = new BigDecimal("0.00");
            nextLine();
            writeReportRec("-".repeat(REPT_LEN));   // TRANSACTION-HEADER-2
            nextLine();
        }

        // 1120-WRITE-ACCOUNT-TOTALS
        private void writeAccountTotals() {
            writeReportRec(fit("Account Total", 13) + ".".repeat(84) + edited(wsAccountTotal));
            wsAccountTotal = new BigDecimal("0.00");
            nextLine();
            writeReportRec("-".repeat(REPT_LEN));
            nextLine();
        }

        // 1110-WRITE-GRAND-TOTALS
        private void writeGrandTotals() {
            writeReportRec(fit("Grand Total", 11) + ".".repeat(86) + edited(wsGrandTotal));
        }

        // 1120-WRITE-HEADERS
        private void writeHeaders() {
            writeReportRec(fit("DALYREPT", 38) + fit("Daily Transaction Report", 41) + "Date Range: "
                    + reptStartDate + " to " + reptEndDate);   // REPORT-NAME-HEADER
            nextLine();
            writeReportRec(fit("", REPT_LEN));                 // WS-BLANK-LINE
            nextLine();
            writeReportRec(fit("Transaction ID", 17) + fit("Account ID", 12) + fit("Transaction Type", 19)
                    + fit("Tran Category", 35) + fit("Tran Source", 14) + " " + "        Amount"); // TRANSACTION-HEADER-1
            nextLine();
            writeReportRec("-".repeat(REPT_LEN));
            nextLine();
        }

        // 1111-WRITE-REPORT-REC
        private void writeReportRec(String line) {
            byte[] rec = fit(line, REPT_LEN).getBytes(CS);
            String st = cobolFiles.write("TRANREPT", () -> Files.write(reptPath, rec,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND));
            if (!"00".equals(st)) {
                log.info("ERROR WRITING REPTFILE");
                displayIoStatus(st);
                throw abend();
            }
        }

        // 1120-WRITE-DETAIL
        private void writeDetail() {
            String acct = String.format(Locale.ROOT, "%011d", xrefAcctId);
            String line = fit(tranId, 16) + " " + acct + " " + fit(tranTypeCd, 2) + "-"
                    + fit(tranTypeDesc, 15) + " " + tranCatCdText + "-" + fit(tranCatTypeDesc, 29) + " "
                    + fit(tranSource, 10) + "    "
                    + CobolEdit.format("-ZZZ,ZZZ,ZZZ.ZZ", tranAmt, false, null) + "  ";
            writeReportRec(line);
            nextLine();
        }

        // 0000-TRANFILE-OPEN
        private void tranfileOpen() {
            String st = cobolFiles.open("TRANFILE", tranPath, true);
            if (!"00".equals(st)) {
                log.info("ERROR OPENING TRANFILE");
                displayIoStatus(st);
                throw abend();
            }
            tranIt = records(tranPath, TRAN_LEN);
        }

        // 0100-REPTFILE-OPEN
        private void reptfileOpen() {
            String st = cobolFiles.open("TRANREPT", reptPath, false);
            if ("00".equals(st) && reptPath == null) {
                st = "35";
            }
            if ("00".equals(st)) {
                try {
                    if (reptPath.getParent() != null) {
                        Files.createDirectories(reptPath.getParent());
                    }
                    Files.write(reptPath, new byte[0]);   // OPEN OUTPUT: empty dataset
                } catch (IOException e) {
                    throw new UncheckedIOException(e);
                }
            }
            if (!"00".equals(st)) {
                log.info("ERROR OPENING REPTFILE");
                displayIoStatus(st);
                throw abend();
            }
        }

        // 0200-CARDXREF-OPEN
        private void cardxrefOpen() {
            String st = cobolFiles.open("CARDXREF");
            if (!"00".equals(st)) {
                log.info("ERROR OPENING CROSS REF FILE");
                displayIoStatus(st);
                throw abend();
            }
        }

        // 0300-TRANTYPE-OPEN
        private void trantypeOpen() {
            String st = cobolFiles.open("TRANTYPE");
            if (!"00".equals(st)) {
                log.info("ERROR OPENING TRANSACTION TYPE FILE");
                displayIoStatus(st);
                throw abend();
            }
        }

        // 0400-TRANCATG-OPEN
        private void trancatgOpen() {
            String st = cobolFiles.open("TRANCATG");
            if (!"00".equals(st)) {
                log.info("ERROR OPENING TRANSACTION CATG FILE");
                displayIoStatus(st);
                throw abend();
            }
        }

        // 0500-DATEPARM-OPEN
        private void dateparmOpen() {
            String st = cobolFiles.open("DATEPARM", datePath, true);
            if (!"00".equals(st)) {
                log.info("ERROR OPENING DATE PARM FILE");
                displayIoStatus(st);
                throw abend();
            }
            dateIt = records(datePath, DATEPARM_LEN);
        }

        // 1500-A-LOOKUP-XREF
        private void lookupXref(String cardNum) {
            CobolFiles.Read<CardXrefRecord> r = cobolFiles.read("CARDXREF", () -> readXrefFile(cardNum));
            if (r.status().startsWith("2")) {   // INVALID KEY
                log.info("INVALID CARD NUMBER : {}", cardNum);
                displayIoStatus("23");
                throw abend();
            }
            if ("00".equals(r.status()) && r.record() != null) {
                Long acct = r.record().getXrefAcctId();   // READ ... INTO CARD-XREF-RECORD
                xrefAcctId = acct == null ? 0 : acct;
            }
        }

        // 1500-B-LOOKUP-TRANTYPE
        private void lookupTrantype(String type) {
            CobolFiles.Read<FdTrantypeRec> r = cobolFiles.read("TRANTYPE", () -> readTrantypeFile(type));
            if (r.status().startsWith("2")) {
                log.info("INVALID TRANSACTION TYPE : {}", type);
                displayIoStatus("23");
                throw abend();
            }
            if ("00".equals(r.status()) && r.record() != null) {
                tranTypeDesc = fit(r.record().getFdTranData(), 50);   // TRAN-TYPE-DESC = first 50 of FD-TRAN-DATA
            }
        }

        // 1500-C-LOOKUP-TRANCATG
        private void lookupTrancatg(String type, int cat) {
            FdTranCatRecordKey key = new FdTranCatRecordKey();
            key.setFdTranTypeCd(type);
            key.setFdTranCatCd(cat);
            CobolFiles.Read<FdTranCatRecord> r = cobolFiles.read("TRANCATG", () -> readTrancatgFile(key));
            if (r.status().startsWith("2")) {
                log.info("INVALID TRAN CATG KEY : {}{}", type, String.format(Locale.ROOT, "%04d", cat));
                displayIoStatus("23");
                throw abend();
            }
            if ("00".equals(r.status()) && r.record() != null) {
                tranCatTypeDesc = fit(r.record().getFdTranCatData(), 50);
            }
        }

        // 9000-TRANFILE-CLOSE
        private void tranfileClose() {
            String st = cobolFiles.close("TRANFILE");
            if (!"00".equals(st)) {
                log.info("ERROR CLOSING POSTED TRANSACTION FILE");
                displayIoStatus(st);
                throw abend();
            }
        }

        // 9100-REPTFILE-CLOSE
        private void reptfileClose() {
            String st = cobolFiles.close("TRANREPT");
            if (!"00".equals(st)) {
                log.info("ERROR CLOSING REPORT FILE");
                displayIoStatus(st);
                throw abend();
            }
        }

        // 9200-CARDXREF-CLOSE
        private void cardxrefClose() {
            String st = cobolFiles.close("CARDXREF");
            if (!"00".equals(st)) {
                log.info("ERROR CLOSING CROSS REF FILE");
                displayIoStatus(st);
                throw abend();
            }
        }

        // 9300-TRANTYPE-CLOSE
        private void trantypeClose() {
            String st = cobolFiles.close("TRANTYPE");
            if (!"00".equals(st)) {
                log.info("ERROR CLOSING TRANSACTION TYPE FILE");
                displayIoStatus(st);
                throw abend();
            }
        }

        // 9400-TRANCATG-CLOSE
        private void trancatgClose() {
            String st = cobolFiles.close("TRANCATG");
            if (!"00".equals(st)) {
                log.info("ERROR CLOSING TRANSACTION CATG FILE");
                displayIoStatus(st);
                throw abend();
            }
        }

        // 9500-DATEPARM-CLOSE
        private void dateparmClose() {
            String st = cobolFiles.close("DATEPARM");
            if (!"00".equals(st)) {
                log.info("ERROR CLOSING DATE PARM FILE");
                displayIoStatus(st);
                throw abend();
            }
        }

        // 9999-ABEND-PROGRAM: callers `throw abend()`
        private CobolAbend abend() {
            log.info("ABENDING PROGRAM");
            return CobolAbend.user(999, "CBTRN03C abend (9999-ABEND-PROGRAM)");
        }

        // 9910-DISPLAY-IO-STATUS
        private void displayIoStatus(String ioStatus) {
            String s = fit(ioStatus, 2);
            char s1 = s.charAt(0);
            char s2 = s.charAt(1);
            if (!(isDigit(s1) && isDigit(s2)) || s1 == '9') {
                log.info("FILE STATUS IS: NNNN{}{}", s1, String.format(Locale.ROOT, "%03d", s2 & 0xFF));
            } else {
                log.info("FILE STATUS IS: NNNN00{}", s);
            }
        }
    }
}
