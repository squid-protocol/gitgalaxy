// gitgalaxy-det-port: COBOL CBSTM03B (CBSTM03B.CBL), translated by rule, statement for statement
package com.gitgalaxy.modernized.service;

import com.gitgalaxy.modernized.batch.CobolAbend;
import com.gitgalaxy.modernized.batch.CobolFiles;
import com.gitgalaxy.modernized.batch.DatasetResolver;
import com.gitgalaxy.modernized.batch.Dd;
import com.gitgalaxy.modernized.batch.MainframeClock;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.cobolrt.batch.DetFiles;
import com.gitgalaxy.modernized.cobolrt.Cobol;
import com.gitgalaxy.modernized.cobolrt.Field;
import com.gitgalaxy.modernized.cobolrt.Figurative;
import com.gitgalaxy.modernized.cobolrt.Funcs;
import com.gitgalaxy.modernized.cobolrt.Hole;
import com.gitgalaxy.modernized.cobolrt.Storage;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.dto.contract.*;
import com.gitgalaxy.modernized.entity.vsam.*;
import com.gitgalaxy.modernized.entity.vsam.AccountRecord;
import com.gitgalaxy.modernized.entity.vsam.CardXrefRecord;
import com.gitgalaxy.modernized.entity.vsam.CustomerRecord;
import com.gitgalaxy.modernized.entity.vsam.FdTrnxfileRec;
import com.gitgalaxy.modernized.repository.vsam.AccountRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.CardXrefRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.CustomerRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.FdTrnxfileRecRepository;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * CBSTM03B: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 53, translated 53, holes 0.
 */
@Service
public class Cbstm03bService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;

    private static final byte[] IMAGE_s_FD_TRNXFILE_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_FD_XREFFILE_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_FD_CUSTFILE_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_FD_ACCTFILE_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_TRNXFILE_STATUS = Base64.getDecoder().decode(String.join("",
            "ICA="));
    private static final byte[] IMAGE_s_XREFFILE_STATUS = Base64.getDecoder().decode(String.join("",
            "ICA="));
    private static final byte[] IMAGE_s_CUSTFILE_STATUS = Base64.getDecoder().decode(String.join("",
            "ICA="));
    private static final byte[] IMAGE_s_ACCTFILE_STATUS = Base64.getDecoder().decode(String.join("",
            "ICA="));
    private static final byte[] IMAGE_s_LK_M03B_AREA = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgMDAwMCAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_FD_TRNXFILE_REC = new Storage(IMAGE_s_FD_TRNXFILE_REC.length);
    private final Storage s_FD_XREFFILE_REC = new Storage(IMAGE_s_FD_XREFFILE_REC.length);
    private final Storage s_FD_CUSTFILE_REC = new Storage(IMAGE_s_FD_CUSTFILE_REC.length);
    private final Storage s_FD_ACCTFILE_REC = new Storage(IMAGE_s_FD_ACCTFILE_REC.length);
    private final Storage s_TRNXFILE_STATUS = new Storage(IMAGE_s_TRNXFILE_STATUS.length);
    private final Storage s_XREFFILE_STATUS = new Storage(IMAGE_s_XREFFILE_STATUS.length);
    private final Storage s_CUSTFILE_STATUS = new Storage(IMAGE_s_CUSTFILE_STATUS.length);
    private final Storage s_ACCTFILE_STATUS = new Storage(IMAGE_s_ACCTFILE_STATUS.length);
    private final Storage s_LK_M03B_AREA = new Storage(IMAGE_s_LK_M03B_AREA.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_FD_TRNXFILE_REC = Field.group(s_FD_TRNXFILE_REC, 0, 350);
    private final Field f6_FD_XREFFILE_REC = Field.group(s_FD_XREFFILE_REC, 0, 50);
    private final Field f9_FD_CUSTFILE_REC = Field.group(s_FD_CUSTFILE_REC, 0, 500);
    private final Field f10_FD_CUST_ID = Field.alphanumeric(s_FD_CUSTFILE_REC, 0, 9, false);
    private final Field f12_FD_ACCTFILE_REC = Field.group(s_FD_ACCTFILE_REC, 0, 300);
    private final Field f13_FD_ACCT_ID = Field.zoned(s_FD_ACCTFILE_REC, 0, 11, 0, false, false, false);
    private final Field f15_TRNXFILE_STATUS = Field.group(s_TRNXFILE_STATUS, 0, 2);
    private final Field f18_XREFFILE_STATUS = Field.group(s_XREFFILE_STATUS, 0, 2);
    private final Field f21_CUSTFILE_STATUS = Field.group(s_CUSTFILE_STATUS, 0, 2);
    private final Field f24_ACCTFILE_STATUS = Field.group(s_ACCTFILE_STATUS, 0, 2);
    private final Field f27_LK_M03B_AREA = Field.group(s_LK_M03B_AREA, 0, 1040);
    private final Field f28_LK_M03B_DD = Field.alphanumeric(s_LK_M03B_AREA, 0, 8, false);
    private final Field f29_LK_M03B_OPER = Field.alphanumeric(s_LK_M03B_AREA, 8, 1, false);
    private final Field f30_LK_M03B_RC = Field.alphanumeric(s_LK_M03B_AREA, 9, 2, false);
    private final Field f31_LK_M03B_KEY = Field.alphanumeric(s_LK_M03B_AREA, 11, 25, false);
    private final Field f32_LK_M03B_KEY_LN = Field.zoned(s_LK_M03B_AREA, 36, 4, 0, true, false, false);
    private final Field f33_LK_M03B_FLDT = Field.alphanumeric(s_LK_M03B_AREA, 40, 1000, false);
    private final Field f34_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

    private static FdTrnxfileRecKey id_FdTrnxfileRec(byte[] rec) {
        Storage s = Storage.of(rec);
        FdTrnxfileRecKey k = new FdTrnxfileRecKey();
        k.setFdTrnxCard(Cobol.text(Field.alphanumeric(s, 0, 16, false), CS));
        k.setFdTrnxId(Cobol.text(Field.alphanumeric(s, 16, 16, false), CS));
        return k;
    }

    private static String id_CardXrefRecord(byte[] rec) {
        Storage s = Storage.of(rec);
        return Cobol.text(Field.alphanumeric(s, 0, 16, false), CS);
    }

    private static Integer id_CustomerRecord(byte[] rec) {
        Storage s = Storage.of(rec);
        return Cobol.num(Field.zoned(s, 0, 9, 0, false, false, false), CS).intValue();
    }

    private static Long id_AccountRecord(byte[] rec) {
        Storage s = Storage.of(rec);
        return Cobol.num(Field.zoned(s, 0, 11, 0, false, false, false), CS).longValue();
    }

    private void in_Cbstm03bLkM03bArea(Cbstm03bLkM03bArea d, Storage s, int base) {
        if (d == null) {
            return;
        }
        Cobol.move(d.getLkM03BDd() == null ? "" : d.getLkM03BDd(), Field.alphanumeric(s, base + 0, 8, false), CS);
        Cobol.move(d.getLkM03BOper() == null ? "" : d.getLkM03BOper(), Field.alphanumeric(s, base + 8, 1, false), CS);
        Cobol.move(d.getLkM03BRc() == null ? "" : d.getLkM03BRc(), Field.alphanumeric(s, base + 9, 2, false), CS);
        Cobol.move(d.getLkM03BKey() == null ? "" : d.getLkM03BKey(), Field.alphanumeric(s, base + 11, 25, false), CS);
        Cobol.move(d.getLkM03BKeyLn() == null ? BigDecimal.ZERO : new BigDecimal(d.getLkM03BKeyLn().toString()), Field.zoned(s, base + 36, 4, 0, true, false, false), CS);
        Cobol.move(d.getLkM03BFldt() == null ? "" : d.getLkM03BFldt(), Field.alphanumeric(s, base + 40, 1000, false), CS);
    }

    private void fill_Cbstm03bLkM03bArea(Cbstm03bLkM03bArea d, Storage s, int base) {
        d.setLkM03BDd(Cobol.text(Field.alphanumeric(s, base + 0, 8, false), CS));
        d.setLkM03BOper(Cobol.text(Field.alphanumeric(s, base + 8, 1, false), CS));
        d.setLkM03BRc(Cobol.text(Field.alphanumeric(s, base + 9, 2, false), CS));
        d.setLkM03BKey(Cobol.text(Field.alphanumeric(s, base + 11, 25, false), CS));
        d.setLkM03BKeyLn(Cobol.num(Field.zoned(s, base + 36, 4, 0, true, false, false), CS).intValue());
        d.setLkM03BFldt(Cobol.text(Field.alphanumeric(s, base + 40, 1000, false), CS));
    }

    private Cbstm03bLkM03bArea out_Cbstm03bLkM03bArea(Storage s, int base) {
        Cbstm03bLkM03bArea d = new Cbstm03bLkM03bArea();
        fill_Cbstm03bLkM03bArea(d, s, base);
        return d;
    }

    private DetFiles.DetFile TRNX_FILE;
    private DetFiles.DetFile XREF_FILE;
    private DetFiles.DetFile CUST_FILE;
    private DetFiles.DetFile ACCT_FILE;

    private final FdTrnxfileRecRepository fdTrnxfileRecRepository;
    private final CardXrefRecordRepository cardXrefRecordRepository;
    private final CustomerRecordRepository customerRecordRepository;
    private final AccountRecordRepository accountRecordRepository;
    private final DatasetResolver datasets;
    private final CobolFiles files;
    private final MainframeClock clock;

    public Cbstm03bService(FdTrnxfileRecRepository fdTrnxfileRecRepository, CardXrefRecordRepository cardXrefRecordRepository, CustomerRecordRepository customerRecordRepository, AccountRecordRepository accountRecordRepository, DatasetResolver datasets, CobolFiles files, MainframeClock clock) {
        this.fdTrnxfileRecRepository = fdTrnxfileRecRepository;
        this.cardXrefRecordRepository = cardXrefRecordRepository;
        this.customerRecordRepository = customerRecordRepository;
        this.accountRecordRepository = accountRecordRepository;
        this.datasets = datasets;
        this.files = files;
        this.clock = clock;
        initialState();
        List<Dd> dds = List.of();
        TRNX_FILE = new DetFiles.Indexed<FdTrnxfileRec>(files, "TRNXFILE", s_FD_TRNXFILE_REC, 0, 350, 0, 32, fdTrnxfileRecRepository::findAll, e -> e.toRecord(CS), b -> FdTrnxfileRec.fromRecord(b, CS), fdTrnxfileRecRepository::save, CS).withFindById(rec -> fdTrnxfileRecRepository.findById(id_FdTrnxfileRec(rec)));
        XREF_FILE = new DetFiles.Indexed<CardXrefRecord>(files, "XREFFILE", s_FD_XREFFILE_REC, 0, 50, 0, 16, cardXrefRecordRepository::findAll, e -> e.toRecord(CS), b -> CardXrefRecord.fromRecord(b, CS), cardXrefRecordRepository::save, CS).withFindById(rec -> cardXrefRecordRepository.findById(id_CardXrefRecord(rec)));
        CUST_FILE = new DetFiles.Indexed<CustomerRecord>(files, "CUSTFILE", s_FD_CUSTFILE_REC, 0, 500, 0, 9, customerRecordRepository::findAll, e -> e.toRecord(CS), b -> CustomerRecord.fromRecord(b, CS), customerRecordRepository::save, CS).withFindById(rec -> customerRecordRepository.findById(id_CustomerRecord(rec)));
        ACCT_FILE = new DetFiles.Indexed<AccountRecord>(files, "ACCTFILE", s_FD_ACCTFILE_REC, 0, 300, 0, 11, accountRecordRepository::findAll, e -> e.toRecord(CS), b -> AccountRecord.fromRecord(b, CS), accountRecordRepository::save, CS).withFindById(rec -> accountRecordRepository.findById(id_AccountRecord(rec)));
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_FD_TRNXFILE_REC, 0, s_FD_TRNXFILE_REC.bytes, 0, IMAGE_s_FD_TRNXFILE_REC.length);
        System.arraycopy(IMAGE_s_FD_XREFFILE_REC, 0, s_FD_XREFFILE_REC.bytes, 0, IMAGE_s_FD_XREFFILE_REC.length);
        System.arraycopy(IMAGE_s_FD_CUSTFILE_REC, 0, s_FD_CUSTFILE_REC.bytes, 0, IMAGE_s_FD_CUSTFILE_REC.length);
        System.arraycopy(IMAGE_s_FD_ACCTFILE_REC, 0, s_FD_ACCTFILE_REC.bytes, 0, IMAGE_s_FD_ACCTFILE_REC.length);
        System.arraycopy(IMAGE_s_TRNXFILE_STATUS, 0, s_TRNXFILE_STATUS.bytes, 0, IMAGE_s_TRNXFILE_STATUS.length);
        System.arraycopy(IMAGE_s_XREFFILE_STATUS, 0, s_XREFFILE_STATUS.bytes, 0, IMAGE_s_XREFFILE_STATUS.length);
        System.arraycopy(IMAGE_s_CUSTFILE_STATUS, 0, s_CUSTFILE_STATUS.bytes, 0, IMAGE_s_CUSTFILE_STATUS.length);
        System.arraycopy(IMAGE_s_ACCTFILE_STATUS, 0, s_ACCTFILE_STATUS.bytes, 0, IMAGE_s_ACCTFILE_STATUS.length);
        System.arraycopy(IMAGE_s_LK_M03B_AREA, 0, s_LK_M03B_AREA.bytes, 0, IMAGE_s_LK_M03B_AREA.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 13);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f34_GG_RETURN_CODE, CS).intValue();
    }

    private byte[][] callAreas;  // #4778: the next handleCall's items as bytes (withCallAreas)

    /** #4778: the next handleCall's USING items as their caller's bytes too, one array per item, BY
     *  REFERENCE: the program runs over them -- every byte, those no DTO property names too -- and leaves
     *  its result there as well as in the objects. */
    public void withCallAreas(byte[]... areas) {
        this.callAreas = areas;
    }

    public int handleCall(Cbstm03bLkM03bArea arg1) {
        boolean truncBefore = Cobol.swapTruncBinary(true);  // TRUNC(STD)
        boolean pfdBefore = Cobol.swapNumprocPfd(false);  // NUMPROC(NOPFD)
        try {
            byte[][] areas = callAreas;
            callAreas = null;
            if (areas != null) {
                System.arraycopy(areas[0], 0, f27_LK_M03B_AREA.storage().bytes, f27_LK_M03B_AREA.offset(), Math.min(areas[0].length, f27_LK_M03B_AREA.length()));
            } else {
                in_Cbstm03bLkM03bArea(arg1, f27_LK_M03B_AREA.storage(), f27_LK_M03B_AREA.offset());
            }
            try {
                perform(0, 13);
            } catch (Goback g) {
                // GOBACK
            }
            fill_Cbstm03bLkM03bArea(arg1, f27_LK_M03B_AREA.storage(), f27_LK_M03B_AREA.offset());
            if (areas != null) {
                System.arraycopy(f27_LK_M03B_AREA.storage().bytes, f27_LK_M03B_AREA.offset(), areas[0], 0, Math.min(areas[0].length, f27_LK_M03B_AREA.length()));
            }
            return Cobol.num(f34_GG_RETURN_CODE, CS).intValue();
        } finally {
            Cobol.swapTruncBinary(truncBefore);
            Cobol.swapNumprocPfd(pfdBefore);
        }
    }


    /** GOBACK / STOP RUN. */
    private static final class Goback extends RuntimeException {
        private static final long serialVersionUID = 1L;

        Goback() {
            super(null, null, false, false);
        }
    }

    private static Dd dd(List<Dd> dds, String name) {
        return dds.stream().filter(d -> name.equals(d.name())).findFirst().orElse(null);
    }

    /** The batch entry. */
    public int runBatch(List<Dd> dds, String parm) {
        boolean truncBefore = Cobol.swapTruncBinary(true);  // TRUNC(STD)
        boolean pfdBefore = Cobol.swapNumprocPfd(false);  // NUMPROC(NOPFD)
        try {
            initialState();
            byte[] parmText = (parm == null ? "" : parm).getBytes(CS);
            s_LK_M03B_AREA.bytes[0] = (byte) (parmText.length >> 8);
            s_LK_M03B_AREA.bytes[1] = (byte) parmText.length;
            System.arraycopy(parmText, 0, s_LK_M03B_AREA.bytes, 2, Math.min(parmText.length, s_LK_M03B_AREA.bytes.length - 2));
            TRNX_FILE = new DetFiles.Indexed<FdTrnxfileRec>(files, "TRNXFILE", s_FD_TRNXFILE_REC, 0, 350, 0, 32, fdTrnxfileRecRepository::findAll, e -> e.toRecord(CS), b -> FdTrnxfileRec.fromRecord(b, CS), fdTrnxfileRecRepository::save, CS).withFindById(rec -> fdTrnxfileRecRepository.findById(id_FdTrnxfileRec(rec)));
            XREF_FILE = new DetFiles.Indexed<CardXrefRecord>(files, "XREFFILE", s_FD_XREFFILE_REC, 0, 50, 0, 16, cardXrefRecordRepository::findAll, e -> e.toRecord(CS), b -> CardXrefRecord.fromRecord(b, CS), cardXrefRecordRepository::save, CS).withFindById(rec -> cardXrefRecordRepository.findById(id_CardXrefRecord(rec)));
            CUST_FILE = new DetFiles.Indexed<CustomerRecord>(files, "CUSTFILE", s_FD_CUSTFILE_REC, 0, 500, 0, 9, customerRecordRepository::findAll, e -> e.toRecord(CS), b -> CustomerRecord.fromRecord(b, CS), customerRecordRepository::save, CS).withFindById(rec -> customerRecordRepository.findById(id_CustomerRecord(rec)));
            ACCT_FILE = new DetFiles.Indexed<AccountRecord>(files, "ACCTFILE", s_FD_ACCTFILE_REC, 0, 300, 0, 11, accountRecordRepository::findAll, e -> e.toRecord(CS), b -> AccountRecord.fromRecord(b, CS), accountRecordRepository::save, CS).withFindById(rec -> accountRecordRepository.findById(id_AccountRecord(rec)));
            try {
                perform(0, 13);
            } catch (Goback g) {
                // the program ended
            }
            return Cobol.num(f34_GG_RETURN_CODE, CS).intValue();
        } finally {
            Cobol.swapTruncBinary(truncBefore);
            Cobol.swapNumprocPfd(pfdBefore);
        }
    }

    /** The active PERFORMs' last paragraphs, outermost first. */
    private int[] performThru = new int[64];
    private int performDepth = 0;

    /** Control reached the end of an outer active PERFORM's range: that PERFORM returns (`depth`). */
    private static final class PerformExit extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final int depth;

        PerformExit(int depth) {
            super(null, null, false, false);
            this.depth = depth;
        }
    }

    /** PERFORM from THRU thru. When control falls off the end of a paragraph, the innermost active PERFORM
     *  whose range ends there returns -- this one, or an outer one a GO TO reached the end of, abandoning
     *  the PERFORMs inside it (GnuCOBOL, as IBM: test_det_programs.py, GOTOOUT). */
    private void perform(int from, int thru) {
        int mine = performDepth;
        if (mine == performThru.length) {
            performThru = java.util.Arrays.copyOf(performThru, mine * 2);
        }
        performThru[performDepth++] = thru;
        try {
            int i = from;
            while (true) {
                int next = run(i);
                boolean jumped = (next & GOTO) != 0;
                next &= ~GOTO;
                if (!jumped) {
                    if (i == thru) {
                        return;
                    }
                    for (int d = mine - 1; d >= 0; d--) {
                        if (performThru[d] == i) {
                            throw new PerformExit(d);
                        }
                    }
                }
                if (next >= 14) {
                    throw new Goback();
                }
                i = next;
            }
        } catch (PerformExit e) {
            if (e.depth != mine) {
                throw e;
            }
        } finally {
            performDepth = mine;
        }
    }

    private int run(int i) {
        switch (i) {
            case 0: return p0();
            case 1: return p1();
            case 2: return p2();
            case 3: return p3();
            case 4: return p4();
            case 5: return p5();
            case 6: return p6();
            case 7: return p7();
            case 8: return p8();
            case 9: return p9();
            case 10: return p10();
            case 11: return p11();
            case 12: return p12();
            case 13: return p13();
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** 0000-START. */
    private int p0() {
        // EVALUATE LK-M03B-DD
        if ((Cobol.compare(f28_LK_M03B_DD, "TRNXFILE", CS) == 0)) {
            // PERFORM 1000-TRNXFILE-PROC THRU 1999-EXIT
            perform(2, 4);
        } else if ((Cobol.compare(f28_LK_M03B_DD, "XREFFILE", CS) == 0)) {
            // PERFORM 2000-XREFFILE-PROC THRU 2999-EXIT
            perform(5, 7);
        } else if ((Cobol.compare(f28_LK_M03B_DD, "CUSTFILE", CS) == 0)) {
            // PERFORM 3000-CUSTFILE-PROC THRU 3999-EXIT
            perform(8, 10);
        } else if ((Cobol.compare(f28_LK_M03B_DD, "ACCTFILE", CS) == 0)) {
            // PERFORM 4000-ACCTFILE-PROC THRU 4999-EXIT
            perform(11, 13);
        } else if (true) {
            // GO TO 9999-GOBACK
            if (true) return GOTO | 1;
        }
        return 1;
    }

    /** 9999-GOBACK. */
    private int p1() {
        // GOBACK
        if (true) throw new Goback();
        return 2;
    }

    /** 1000-TRNXFILE-PROC. */
    private int p2() {
        // IF M03B-OPEN
        if (isM03bOpen()) {
            // OPEN INPUT TRNX-FILE
            String st1 = TRNX_FILE.open("INPUT");
            Cobol.move(st1, f15_TRNXFILE_STATUS, CS);
            // GO TO 1900-EXIT
            if (true) return GOTO | 3;
        }
        // IF M03B-READ
        if (isM03bRead()) {
            // READ TRNX-FILE INTO LK-M03B-FLDT
            String st2 = TRNX_FILE.readNext();
            Cobol.move(st2, f15_TRNXFILE_STATUS, CS);
            if (st2.startsWith("0")) {
                Cobol.move(f1_FD_TRNXFILE_REC, f33_LK_M03B_FLDT, CS);
            }
            // GO TO 1900-EXIT
            if (true) return GOTO | 3;
        }
        // IF M03B-CLOSE
        if (isM03bClose()) {
            // CLOSE TRNX-FILE
            String st3 = TRNX_FILE.close();
            Cobol.move(st3, f15_TRNXFILE_STATUS, CS);
            // GO TO 1900-EXIT
            if (true) return GOTO | 3;
        }
        return 3;
    }

    /** 1900-EXIT. */
    private int p3() {
        // MOVE TRNXFILE-STATUS TO LK-M03B-RC
        Cobol.move(f15_TRNXFILE_STATUS, f30_LK_M03B_RC, CS);
        return 4;
    }

    /** 1999-EXIT. */
    private int p4() {
        // EXIT
        return 5;
    }

    /** 2000-XREFFILE-PROC. */
    private int p5() {
        // IF M03B-OPEN
        if (isM03bOpen()) {
            // OPEN INPUT XREF-FILE
            String st4 = XREF_FILE.open("INPUT");
            Cobol.move(st4, f18_XREFFILE_STATUS, CS);
            // GO TO 2900-EXIT
            if (true) return GOTO | 6;
        }
        // IF M03B-READ
        if (isM03bRead()) {
            // READ XREF-FILE INTO LK-M03B-FLDT
            String st5 = XREF_FILE.readNext();
            Cobol.move(st5, f18_XREFFILE_STATUS, CS);
            if (st5.startsWith("0")) {
                Cobol.move(f6_FD_XREFFILE_REC, f33_LK_M03B_FLDT, CS);
            }
            // GO TO 2900-EXIT
            if (true) return GOTO | 6;
        }
        // IF M03B-CLOSE
        if (isM03bClose()) {
            // CLOSE XREF-FILE
            String st6 = XREF_FILE.close();
            Cobol.move(st6, f18_XREFFILE_STATUS, CS);
            // GO TO 2900-EXIT
            if (true) return GOTO | 6;
        }
        return 6;
    }

    /** 2900-EXIT. */
    private int p6() {
        // MOVE XREFFILE-STATUS TO LK-M03B-RC
        Cobol.move(f18_XREFFILE_STATUS, f30_LK_M03B_RC, CS);
        return 7;
    }

    /** 2999-EXIT. */
    private int p7() {
        // EXIT
        return 8;
    }

    /** 3000-CUSTFILE-PROC. */
    private int p8() {
        // IF M03B-OPEN
        if (isM03bOpen()) {
            // OPEN INPUT CUST-FILE
            String st7 = CUST_FILE.open("INPUT");
            Cobol.move(st7, f21_CUSTFILE_STATUS, CS);
            // GO TO 3900-EXIT
            if (true) return GOTO | 9;
        }
        // IF M03B-READ-K
        if (isM03bReadK()) {
            // MOVE LK-M03B-KEY (1:LK-M03B-KEY-LN) TO FD-CUST-ID
            Cobol.move(f31_LK_M03B_KEY.ref(1, Integer.valueOf(Cobol.num(f32_LK_M03B_KEY_LN, CS).intValue())), f10_FD_CUST_ID, CS);
            // READ CUST-FILE INTO LK-M03B-FLDT
            String st8 = CUST_FILE.readKey(0, 9);
            Cobol.move(st8, f21_CUSTFILE_STATUS, CS);
            if (st8.startsWith("0")) {
                Cobol.move(f9_FD_CUSTFILE_REC, f33_LK_M03B_FLDT, CS);
            }
            // GO TO 3900-EXIT
            if (true) return GOTO | 9;
        }
        // IF M03B-CLOSE
        if (isM03bClose()) {
            // CLOSE CUST-FILE
            String st9 = CUST_FILE.close();
            Cobol.move(st9, f21_CUSTFILE_STATUS, CS);
            // GO TO 3900-EXIT
            if (true) return GOTO | 9;
        }
        return 9;
    }

    /** 3900-EXIT. */
    private int p9() {
        // MOVE CUSTFILE-STATUS TO LK-M03B-RC
        Cobol.move(f21_CUSTFILE_STATUS, f30_LK_M03B_RC, CS);
        return 10;
    }

    /** 3999-EXIT. */
    private int p10() {
        // EXIT
        return 11;
    }

    /** 4000-ACCTFILE-PROC. */
    private int p11() {
        // IF M03B-OPEN
        if (isM03bOpen()) {
            // OPEN INPUT ACCT-FILE
            String st10 = ACCT_FILE.open("INPUT");
            Cobol.move(st10, f24_ACCTFILE_STATUS, CS);
            // GO TO 4900-EXIT
            if (true) return GOTO | 12;
        }
        // IF M03B-READ-K
        if (isM03bReadK()) {
            // MOVE LK-M03B-KEY (1:LK-M03B-KEY-LN) TO FD-ACCT-ID
            Cobol.move(f31_LK_M03B_KEY.ref(1, Integer.valueOf(Cobol.num(f32_LK_M03B_KEY_LN, CS).intValue())), f13_FD_ACCT_ID, CS);
            // READ ACCT-FILE INTO LK-M03B-FLDT
            String st11 = ACCT_FILE.readKey(0, 11);
            Cobol.move(st11, f24_ACCTFILE_STATUS, CS);
            if (st11.startsWith("0")) {
                Cobol.move(f12_FD_ACCTFILE_REC, f33_LK_M03B_FLDT, CS);
            }
            // GO TO 4900-EXIT
            if (true) return GOTO | 12;
        }
        // IF M03B-CLOSE
        if (isM03bClose()) {
            // CLOSE ACCT-FILE
            String st12 = ACCT_FILE.close();
            Cobol.move(st12, f24_ACCTFILE_STATUS, CS);
            // GO TO 4900-EXIT
            if (true) return GOTO | 12;
        }
        return 12;
    }

    /** 4900-EXIT. */
    private int p12() {
        // MOVE ACCTFILE-STATUS TO LK-M03B-RC
        Cobol.move(f24_ACCTFILE_STATUS, f30_LK_M03B_RC, CS);
        return 13;
    }

    /** 4999-EXIT. */
    private int p13() {
        // EXIT
        return 14;
    }

    /** 88 M03B-OPEN of LK-M03B-OPER. */
    private boolean isM03bOpen() { return Cobol.compare(f29_LK_M03B_OPER, "O", CS) == 0; }

    /** 88 M03B-READ of LK-M03B-OPER. */
    private boolean isM03bRead() { return Cobol.compare(f29_LK_M03B_OPER, "R", CS) == 0; }

    /** 88 M03B-CLOSE of LK-M03B-OPER. */
    private boolean isM03bClose() { return Cobol.compare(f29_LK_M03B_OPER, "C", CS) == 0; }

    /** 88 M03B-READ-K of LK-M03B-OPER. */
    private boolean isM03bReadK() { return Cobol.compare(f29_LK_M03B_OPER, "K", CS) == 0; }

}
