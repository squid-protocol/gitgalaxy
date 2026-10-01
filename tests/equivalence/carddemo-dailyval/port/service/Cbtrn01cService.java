package com.gitgalaxy.modernized.service;

import com.gitgalaxy.modernized.batch.CobolAbend;
import com.gitgalaxy.modernized.batch.CobolFiles;
import com.gitgalaxy.modernized.batch.DatasetResolver;
import com.gitgalaxy.modernized.batch.Dd;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.nio.charset.Charset;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.ApplicationContext;
import org.springframework.core.ResolvableType;
import org.springframework.data.repository.CrudRepository;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class Cbtrn01cService {

    private static final Logger log = LoggerFactory.getLogger(Cbtrn01cService.class);

    private static final String DALYTRAN = "DALYTRAN";
    private static final String CUSTFILE = "CUSTFILE";
    private static final String XREFFILE = "XREFFILE";
    private static final String CARDFILE = "CARDFILE";
    private static final String ACCTFILE = "ACCTFILE";
    private static final String TRANFILE = "TRANFILE";

    // record layouts (CVTRA06Y / CVACT03Y / CVACT01Y)
    private static final int DALYTRAN_LEN = 350;
    private static final int XREF_LEN = 50;
    private static final int ACCT_LEN = 300;

    private final DatasetResolver datasets;
    private final CobolFiles files;
    private final ApplicationContext ctx;

    public void executeCbtrn01c(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for CBTRN01C");
        // The business logic of CBTRN01C is the batch main line: see runBatch.
    }

    /** Working storage of one run. */
    private static final class Run {
        final Charset cs = CobolRecords.charset();
        final List<Dd> dds;
        final Map<String, String> status = new HashMap<>();   // the FILE STATUS of each file
        final Map<String, byte[]> contents = new HashMap<>(); // dataset bytes of a keyed file, when it is one
        final Map<String, Object[]> repos = new HashMap<>();  // the repository serving a keyed file
        java.util.Iterator<byte[]> dalyCursor;
        byte[] dalytran = new byte[DALYTRAN_LEN];              // DALYTRAN-RECORD
        String endOfDailyTrans = "N";                          // END-OF-DAILY-TRANS-FILE
        String xrefCardNum = "";                               // XREF-CARD-NUM
        String xrefCustId = "000000000";                       // XREF-CUST-ID
        String xrefAcctId = "00000000000";                     // XREF-ACCT-ID
        String acctId = "00000000000";                         // ACCT-ID
        int xrefReadStatus;                                    // WS-XREF-READ-STATUS
        int acctReadStatus;                                    // WS-ACCT-READ-STATUS

        Run(List<Dd> dds) {
            this.dds = dds;
            java.util.Arrays.fill(dalytran, CobolRecords.blank(1, cs)[0]);
            for (String n : new String[] {DALYTRAN, CUSTFILE, XREFFILE, CARDFILE, ACCTFILE, TRANFILE}) {
                status.put(n, "  ");
            }
        }

        String dalyId() {
            return CobolRecords.text(dalytran, 0, 16, cs);
        }

        String dalyCardNum() {
            return CobolRecords.text(dalytran, 262, 16, cs);
        }
    }

    /** The batch entry (#3622). */
    public int runBatch(List<Dd> dds, String parm) {
        Run r = new Run(dds);
        // MAIN-PARA
        Sysout.display("START OF EXECUTION OF PROGRAM CBTRN01C");
        openDalytran(r);                                                    // 0000-DALYTRAN-OPEN
        openKeyed(r, CUSTFILE, "ERROR OPENING CUSTOMER FILE");              // 0100-CUSTFILE-OPEN
        openKeyed(r, XREFFILE, "ERROR OPENING CROSS REF FILE");             // 0200-XREFFILE-OPEN
        openKeyed(r, CARDFILE, "ERROR OPENING CARD FILE");                  // 0300-CARDFILE-OPEN
        openKeyed(r, ACCTFILE, "ERROR OPENING ACCOUNT FILE");               // 0400-ACCTFILE-OPEN
        openKeyed(r, TRANFILE, "ERROR OPENING TRANSACTION FILE");           // 0500-TRANFILE-OPEN

        while (!r.endOfDailyTrans.equals("Y")) {
            if (r.endOfDailyTrans.equals("N")) {
                dalytranGetNext(r);                                         // 1000-DALYTRAN-GET-NEXT
                if (r.endOfDailyTrans.equals("N")) {
                    Sysout.display(CobolRecords.text(r.dalytran, 0, DALYTRAN_LEN, r.cs));
                }
                // Defect kept: after end of file the loop still looks up the card of the last record read
                // (DALYTRAN-RECORD is not cleared). Fix: skip the lookup when END-OF-DAILY-TRANS-FILE = 'Y'.
                r.xrefReadStatus = 0;
                r.xrefCardNum = r.dalyCardNum();
                lookupXref(r);                                              // 2000-LOOKUP-XREF
                if (r.xrefReadStatus == 0) {
                    r.acctReadStatus = 0;
                    r.acctId = r.xrefAcctId;
                    readAccount(r);                                         // 3000-READ-ACCOUNT
                    if (r.acctReadStatus != 0) {
                        Sysout.display("ACCOUNT ", r.acctId, " NOT FOUND");
                    }
                } else {
                    Sysout.display("CARD NUMBER ", r.dalyCardNum(),
                            " COULD NOT BE VERIFIED. SKIPPING TRANSACTION ID-", r.dalyId());
                }
            }
        }

        // 9000-DALYTRAN-CLOSE
        // Defect kept: the DALYTRAN close error says CUSTOMER FILE and reports CUSTFILE-STATUS.
        // Fix: DISPLAY 'ERROR CLOSING DAILY TRANSACTION FILE' and MOVE DALYTRAN-STATUS TO IO-STATUS.
        close(r, DALYTRAN, "ERROR CLOSING CUSTOMER FILE", CUSTFILE);
        close(r, CUSTFILE, "ERROR CLOSING CUSTOMER FILE", CUSTFILE);        // 9100-CUSTFILE-CLOSE
        close(r, XREFFILE, "ERROR CLOSING CROSS REF FILE", XREFFILE);       // 9200-XREFFILE-CLOSE
        close(r, CARDFILE, "ERROR CLOSING CARD FILE", CARDFILE);            // 9300-CARDFILE-CLOSE
        close(r, ACCTFILE, "ERROR CLOSING ACCOUNT FILE", ACCTFILE);         // 9400-ACCTFILE-CLOSE
        close(r, TRANFILE, "ERROR CLOSING TRANSACTION FILE", TRANFILE);     // 9500-TRANFILE-CLOSE

        Sysout.display("END OF EXECUTION OF PROGRAM CBTRN01C");
        return 0; // GOBACK, RETURN-CODE never set
    }

    // 0000-DALYTRAN-OPEN
    private void openDalytran(Run r) {
        Path p = path(r, DALYTRAN);
        String st = files.open(DALYTRAN, p, true);
        r.status.put(DALYTRAN, st);
        if (st.equals("00")) {
            List<byte[]> recs = new ArrayList<>();
            byte[] all = readAll(p);
            for (int i = 0; i + DALYTRAN_LEN <= all.length; i += DALYTRAN_LEN) {
                recs.add(java.util.Arrays.copyOfRange(all, i, i + DALYTRAN_LEN));
            }
            r.dalyCursor = recs.iterator();
        } else {
            fail(r, "ERROR OPENING DAILY TRANSACTION FILE", st);
        }
    }

    // 0100 / 0200 / 0300 / 0400 / 0500 -OPEN
    // A keyed (VSAM) file lives in its repository: its OPEN is files.open(dd).
    private void openKeyed(Run r, String dd, String message) {
        String st = files.open(dd);
        r.status.put(dd, st);
        if (st.equals("00")) {
            if (dd.equals(XREFFILE) || dd.equals(ACCTFILE)) {
                r.repos.put(dd, discover(dd.equals(XREFFILE)));
                if (r.repos.get(dd).length == 0) {
                    // no repository found: fall back on a dataset file of the DD, when there is one
                    Path p = path(r, dd);
                    if (p != null && Files.exists(p)) {
                        r.contents.put(dd, readAll(p));
                    }
                }
            }
        } else {
            fail(r, message, st);
        }
    }

    // 9000 .. 9500 -CLOSE: `ioFile` is the file whose status the paragraph reports
    private void close(Run r, String dd, String message, String ioFile) {
        String st = files.close(dd);
        r.status.put(dd, st);
        if (!st.equals("00")) {
            fail(r, message, r.status.get(ioFile));
        }
    }

    // 1000-DALYTRAN-GET-NEXT
    private void dalytranGetNext(Run r) {
        CobolFiles.Read<byte[]> rd = files.readNext(DALYTRAN, r.dalyCursor);
        r.status.put(DALYTRAN, rd.status());
        if (rd.found()) {
            r.dalytran = rd.record().clone(); // READ INTO
        }
        int applResult = rd.status().equals("00") ? 0 : rd.status().equals("10") ? 16 : 12;
        if (applResult == 0) {
            return; // APPL-AOK: CONTINUE
        }
        if (applResult == 16) {
            r.endOfDailyTrans = "Y"; // APPL-EOF
        } else {
            fail(r, "ERROR READING DAILY TRANSACTION FILE", rd.status());
        }
    }

    // 2000-LOOKUP-XREF
    private void lookupXref(Run r) {
        String key = r.xrefCardNum; // MOVE XREF-CARD-NUM TO FD-XREF-CARD-NUM
        CobolFiles.Read<byte[]> rd = files.read(XREFFILE, () -> find(r, XREFFILE, XREF_LEN, 16, key));
        r.status.put(XREFFILE, rd.status());
        if (rd.status().startsWith("2")) { // INVALID KEY
            Sysout.display("INVALID CARD NUMBER FOR XREF");
            r.xrefReadStatus = 4;
        } else if (rd.found()) {           // NOT INVALID KEY (READ INTO CARD-XREF-RECORD)
            r.xrefCardNum = CobolRecords.text(rd.record(), 0, 16, r.cs);
            r.xrefCustId = CobolRecords.text(rd.record(), 16, 9, r.cs);
            r.xrefAcctId = CobolRecords.text(rd.record(), 25, 11, r.cs);
            Sysout.display("SUCCESSFUL READ OF XREF");
            Sysout.display("CARD NUMBER: ", r.xrefCardNum);
            Sysout.display("ACCOUNT ID : ", r.xrefAcctId);
            Sysout.display("CUSTOMER ID: ", r.xrefCustId);
        }
        // Defect kept: any other status (e.g. 30) runs neither branch and nothing tests it, so the previous
        // XREF record (and its XREF-ACCT-ID) stays. Fix: test XREFFILE-STATUS after the READ.
    }

    // 3000-READ-ACCOUNT
    private void readAccount(Run r) {
        String key = r.acctId; // MOVE ACCT-ID TO FD-ACCT-ID
        CobolFiles.Read<byte[]> rd = files.read(ACCTFILE, () -> find(r, ACCTFILE, ACCT_LEN, 11, key));
        r.status.put(ACCTFILE, rd.status());
        if (rd.status().startsWith("2")) { // INVALID KEY
            Sysout.display("INVALID ACCOUNT NUMBER FOUND");
            r.acctReadStatus = 4;
        } else if (rd.found()) {           // NOT INVALID KEY (READ INTO ACCOUNT-RECORD: ACCT-ID is its first field)
            r.acctId = CobolRecords.text(rd.record(), 0, 11, r.cs);
            Sysout.display("SUCCESSFUL READ OF ACCOUNT FILE");
        }
        // Defect kept: a failed read without INVALID KEY goes unreported. Fix: test ACCTFILE-STATUS.
    }

    // Z-DISPLAY-IO-STATUS then Z-ABEND-PROGRAM, after the paragraph's own message
    private void fail(Run r, String message, String ioStatus) {
        Sysout.display(message);
        displayIoStatus(r, ioStatus);
        Sysout.display("ABENDING PROGRAM"); // Z-ABEND-PROGRAM
        throw CobolAbend.user(999, message);
    }

    // Z-DISPLAY-IO-STATUS
    private void displayIoStatus(Run r, String ioStatus) {
        String s = (ioStatus + "  ").substring(0, 2);
        char s1 = s.charAt(0);
        char s2 = s.charAt(1);
        boolean numeric = s1 >= '0' && s1 <= '9' && s2 >= '0' && s2 <= '9';
        if (!numeric || s1 == '9') {
            int binary = String.valueOf(s2).getBytes(r.cs)[0] & 0xFF; // TWO-BYTES-RIGHT of TWO-BYTES-BINARY
            Sysout.display("FILE STATUS IS: NNNN", String.valueOf(s1), Sysout.number(
                    BigDecimal.valueOf(binary), 3, 0, false));
        } else {
            Sysout.display("FILE STATUS IS: NNNN", "00" + s);
        }
    }

    // A keyed READ: from the file's repository, else from a dataset file
    private Optional<byte[]> find(Run r, String dd, int recLen, int keyLen, String key) {
        Object[] repo = r.repos.get(dd);
        if (repo != null && repo.length == 2) {
            return findInRepo(r, repo, key);
        }
        byte[] all = r.contents.get(dd);
        if (all == null) {
            return Optional.empty();
        }
        for (int i = 0; i + recLen <= all.length; i += recLen) {
            if (CobolRecords.text(all, i, keyLen, r.cs).equals(CobolRecords.fit(key, keyLen, r.cs))) {
                return Optional.of(java.util.Arrays.copyOfRange(all, i, i + recLen));
            }
        }
        return Optional.empty();
    }

    /** The generated repository of the xref (or account) entity: {repository, id class}, empty when none. */
    @SuppressWarnings({"rawtypes"})
    private Object[] discover(boolean xref) {
        Object[] best = new Object[0];
        int bestLen = Integer.MAX_VALUE;
        for (Object repo : ctx.getBeansOfType(CrudRepository.class).values()) {
            for (Class<?> i : repo.getClass().getInterfaces()) {
                if (i == CrudRepository.class || !CrudRepository.class.isAssignableFrom(i)) {
                    continue;
                }
                Class<?>[] g = ResolvableType.forClass(i).as(CrudRepository.class).resolveGenerics();
                if (g.length < 2 || g[0] == null || g[1] == null) {
                    continue;
                }
                String n = g[0].getSimpleName().toLowerCase(Locale.ROOT);
                boolean match = xref ? n.contains("xref") : n.contains("acc") && !n.contains("xref");
                if (match && n.length() < bestLen) {
                    bestLen = n.length();
                    best = new Object[] {repo, g[1]};
                }
            }
        }
        return best;
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private Optional<byte[]> findInRepo(Run r, Object[] repo, String key) {
        Class<?> idClass = (Class<?>) repo[1];
        Object id = key;
        if (idClass != String.class) {
            try {
                BigDecimal n = CobolRecords.numval(key);
                if (idClass == Long.class) {
                    id = n.longValue();
                } else if (idClass == Integer.class) {
                    id = n.intValue();
                } else if (idClass == BigDecimal.class) {
                    id = n;
                } else if (idClass == BigInteger.class) {
                    id = n.toBigInteger();
                }
            } catch (NumberFormatException e) {
                return Optional.empty();
            }
        }
        Optional<Object> found = ((CrudRepository) repo[0]).findById(id);
        if (found.isEmpty()) {
            return Optional.empty();
        }
        try {
            Object e = found.get();
            return Optional.of((byte[]) e.getClass().getMethod("toRecord", Charset.class).invoke(e, r.cs));
        } catch (ReflectiveOperationException ex) {
            throw new IllegalStateException("entity has no toRecord(Charset)", ex);
        }
    }

    private Path path(Run r, String name) {
        for (Dd d : r.dds) {
            if (name.equals(d.name())) {
                return datasets.path(d);
            }
        }
        return null;
    }

    private static byte[] readAll(Path p) {
        try {
            return Files.readAllBytes(p);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }
}
