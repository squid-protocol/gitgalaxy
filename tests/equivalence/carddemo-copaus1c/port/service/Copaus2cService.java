// gitgalaxy-det-port: COBOL COPAUS2C (COPAUS2C.cbl), translated by rule, statement for statement
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
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.cobolrt.cics.DetCics;
import com.gitgalaxy.modernized.dto.screen.*;
import com.gitgalaxy.modernized.dto.contract.*;
import com.gitgalaxy.modernized.entity.vsam.*;
import com.gitgalaxy.modernized.repository.vsam.*;
import com.gitgalaxy.modernized.cobolrt.sql.DetSql;
import com.gitgalaxy.modernized.repository.db2.AuthfrdsRepository;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * COPAUS2C: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 56, translated 56, holes 0.
 */
@Service
public class Copaus2cService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D999999999 = new BigDecimal("999999999");
    private static final BigDecimal DM803 = new BigDecimal("-803");

    private static final byte[] IMAGE_s_WS_VARIABLES = Base64.getDecoder().decode(String.join("",
            "Q09QQVVTMkMAADAwMDAwMDAwMCAgLSAgLSAgICAgLiAgLiAgICAgMDAwTiAgICAgICAgICAgICAgICAgAAAAAAAAAAwgICAgICAgIA=="));
    private static final byte[] IMAGE_s_SQLCA = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAAAAAAAAAAAAAAICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_DCLAUTHFRDS = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAAAAAAAAAMAAAAAAAADCAgICAgICAAACAgICAgICAgICAgICAgIAAAICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAADAAAAAAM"));
    private static final byte[] IMAGE_s_DFHCOMMAREA = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwMDAwMDAwMDAwMDAAAAwAAAAADCAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDAwMDAwMAAAAAAAAAwAAAAAAAAMICAgICAgIDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_VARIABLES = new Storage(IMAGE_s_WS_VARIABLES.length);
    private final Storage s_SQLCA = new Storage(IMAGE_s_SQLCA.length);
    private final Storage s_DCLAUTHFRDS = new Storage(IMAGE_s_DCLAUTHFRDS.length);
    private final Storage s_DFHCOMMAREA = new Storage(IMAGE_s_DFHCOMMAREA.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f4_WS_AUTH_TIME = Field.zoned(s_WS_VARIABLES, 10, 9, 0, false, false, false);
    private final Field f5_WS_AUTH_TIME_AN = Field.alphanumeric(s_WS_VARIABLES, 10, 9, false);
    private final Field f6_WS_AUTH_TS = Field.group(s_WS_VARIABLES, 19, 23);
    private final Field f7_WS_AUTH_YY = Field.alphanumeric(s_WS_VARIABLES, 19, 2, false);
    private final Field f9_WS_AUTH_MM = Field.alphanumeric(s_WS_VARIABLES, 22, 2, false);
    private final Field f11_WS_AUTH_DD = Field.alphanumeric(s_WS_VARIABLES, 25, 2, false);
    private final Field f13_WS_AUTH_HH = Field.alphanumeric(s_WS_VARIABLES, 28, 2, false);
    private final Field f15_WS_AUTH_MI = Field.alphanumeric(s_WS_VARIABLES, 31, 2, false);
    private final Field f17_WS_AUTH_SS = Field.alphanumeric(s_WS_VARIABLES, 34, 2, false);
    private final Field f18_WS_AUTH_SSS = Field.alphanumeric(s_WS_VARIABLES, 36, 3, false);
    private final Field f21_WS_SQLCODE = Field.numericEdited(s_WS_VARIABLES, 43, 7, "+999999", false);
    private final Field f22_WS_SQLSTATE = Field.numericEdited(s_WS_VARIABLES, 50, 10, "+999999999", false);
    private final Field f23_WS_ABS_TIME = Field.packed(s_WS_VARIABLES, 60, 15, 0, true);
    private final Field f24_WS_CUR_DATE = Field.alphanumeric(s_WS_VARIABLES, 68, 8, false);
    private final Field f25_SQLCA = Field.group(s_SQLCA, 0, 136);
    private final Field f28_SQLCODE = Field.binary(s_SQLCA, 12, 9, 0, true, true);
    private final Field f46_SQLSTATE = Field.alphanumeric(s_SQLCA, 131, 5, false);
    private final Field f48_CARD_NUM = Field.alphanumeric(s_DCLAUTHFRDS, 0, 16, false);
    private final Field f49_AUTH_TS = Field.alphanumeric(s_DCLAUTHFRDS, 16, 26, false);
    private final Field f50_AUTH_TYPE = Field.alphanumeric(s_DCLAUTHFRDS, 42, 4, false);
    private final Field f51_CARD_EXPIRY_DATE = Field.alphanumeric(s_DCLAUTHFRDS, 46, 4, false);
    private final Field f52_MESSAGE_TYPE = Field.alphanumeric(s_DCLAUTHFRDS, 50, 6, false);
    private final Field f53_MESSAGE_SOURCE = Field.alphanumeric(s_DCLAUTHFRDS, 56, 6, false);
    private final Field f54_AUTH_ID_CODE = Field.alphanumeric(s_DCLAUTHFRDS, 62, 6, false);
    private final Field f55_AUTH_RESP_CODE = Field.alphanumeric(s_DCLAUTHFRDS, 68, 2, false);
    private final Field f56_AUTH_RESP_REASON = Field.alphanumeric(s_DCLAUTHFRDS, 70, 4, false);
    private final Field f57_PROCESSING_CODE = Field.alphanumeric(s_DCLAUTHFRDS, 74, 6, false);
    private final Field f58_TRANSACTION_AMT = Field.packed(s_DCLAUTHFRDS, 80, 12, 2, true);
    private final Field f59_APPROVED_AMT = Field.packed(s_DCLAUTHFRDS, 87, 12, 2, true);
    private final Field f60_MERCHANT_CATAGORY_CODE = Field.alphanumeric(s_DCLAUTHFRDS, 94, 4, false);
    private final Field f61_ACQR_COUNTRY_CODE = Field.alphanumeric(s_DCLAUTHFRDS, 98, 3, false);
    private final Field f62_POS_ENTRY_MODE = Field.binary(s_DCLAUTHFRDS, 101, 4, 0, true, false);
    private final Field f63_MERCHANT_ID = Field.alphanumeric(s_DCLAUTHFRDS, 103, 15, false);
    private final Field f65_MERCHANT_NAME_LEN = Field.binary(s_DCLAUTHFRDS, 118, 4, 0, true, false);
    private final Field f66_MERCHANT_NAME_TEXT = Field.alphanumeric(s_DCLAUTHFRDS, 120, 22, false);
    private final Field f67_MERCHANT_CITY = Field.alphanumeric(s_DCLAUTHFRDS, 142, 13, false);
    private final Field f68_MERCHANT_STATE = Field.alphanumeric(s_DCLAUTHFRDS, 155, 2, false);
    private final Field f69_MERCHANT_ZIP = Field.alphanumeric(s_DCLAUTHFRDS, 157, 9, false);
    private final Field f70_TRANSACTION_ID = Field.alphanumeric(s_DCLAUTHFRDS, 166, 15, false);
    private final Field f71_MATCH_STATUS = Field.alphanumeric(s_DCLAUTHFRDS, 181, 1, false);
    private final Field f72_AUTH_FRAUD = Field.alphanumeric(s_DCLAUTHFRDS, 182, 1, false);
    private final Field f74_ACCT_ID = Field.packed(s_DCLAUTHFRDS, 193, 11, 0, true);
    private final Field f75_CUST_ID = Field.packed(s_DCLAUTHFRDS, 199, 9, 0, true);
    private final Field f77_WS_ACCT_ID = Field.zoned(s_DFHCOMMAREA, 0, 11, 0, false, false, false);
    private final Field f78_WS_CUST_ID = Field.zoned(s_DFHCOMMAREA, 11, 9, 0, false, false, false);
    private final Field f82_PA_AUTH_TIME_9C = Field.packed(s_DFHCOMMAREA, 23, 9, 0, true);
    private final Field f83_PA_AUTH_ORIG_DATE = Field.alphanumeric(s_DFHCOMMAREA, 28, 6, false);
    private final Field f85_PA_CARD_NUM = Field.alphanumeric(s_DFHCOMMAREA, 40, 16, false);
    private final Field f86_PA_AUTH_TYPE = Field.alphanumeric(s_DFHCOMMAREA, 56, 4, false);
    private final Field f87_PA_CARD_EXPIRY_DATE = Field.alphanumeric(s_DFHCOMMAREA, 60, 4, false);
    private final Field f88_PA_MESSAGE_TYPE = Field.alphanumeric(s_DFHCOMMAREA, 64, 6, false);
    private final Field f89_PA_MESSAGE_SOURCE = Field.alphanumeric(s_DFHCOMMAREA, 70, 6, false);
    private final Field f90_PA_AUTH_ID_CODE = Field.alphanumeric(s_DFHCOMMAREA, 76, 6, false);
    private final Field f91_PA_AUTH_RESP_CODE = Field.alphanumeric(s_DFHCOMMAREA, 82, 2, false);
    private final Field f92_PA_AUTH_RESP_REASON = Field.alphanumeric(s_DFHCOMMAREA, 84, 4, false);
    private final Field f93_PA_PROCESSING_CODE = Field.zoned(s_DFHCOMMAREA, 88, 6, 0, false, false, false);
    private final Field f94_PA_TRANSACTION_AMT = Field.packed(s_DFHCOMMAREA, 94, 12, 2, true);
    private final Field f95_PA_APPROVED_AMT = Field.packed(s_DFHCOMMAREA, 101, 12, 2, true);
    private final Field f96_PA_MERCHANT_CATAGORY_CODE = Field.alphanumeric(s_DFHCOMMAREA, 108, 4, false);
    private final Field f97_PA_ACQR_COUNTRY_CODE = Field.alphanumeric(s_DFHCOMMAREA, 112, 3, false);
    private final Field f98_PA_POS_ENTRY_MODE = Field.zoned(s_DFHCOMMAREA, 115, 2, 0, false, false, false);
    private final Field f99_PA_MERCHANT_ID = Field.alphanumeric(s_DFHCOMMAREA, 117, 15, false);
    private final Field f100_PA_MERCHANT_NAME = Field.alphanumeric(s_DFHCOMMAREA, 132, 22, false);
    private final Field f101_PA_MERCHANT_CITY = Field.alphanumeric(s_DFHCOMMAREA, 154, 13, false);
    private final Field f102_PA_MERCHANT_STATE = Field.alphanumeric(s_DFHCOMMAREA, 167, 2, false);
    private final Field f103_PA_MERCHANT_ZIP = Field.alphanumeric(s_DFHCOMMAREA, 169, 9, false);
    private final Field f104_PA_TRANSACTION_ID = Field.alphanumeric(s_DFHCOMMAREA, 178, 15, false);
    private final Field f105_PA_MATCH_STATUS = Field.alphanumeric(s_DFHCOMMAREA, 193, 1, false);
    private final Field f107_PA_FRAUD_RPT_DATE = Field.alphanumeric(s_DFHCOMMAREA, 195, 8, false);
    private final Field f110_WS_FRD_ACTION = Field.alphanumeric(s_DFHCOMMAREA, 220, 1, false);
    private final Field f111_WS_FRD_UPDATE_STATUS = Field.alphanumeric(s_DFHCOMMAREA, 221, 1, false);
    private final Field f112_WS_FRD_ACT_MSG = Field.alphanumeric(s_DFHCOMMAREA, 222, 50, false);
    private final Field f114_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f115_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f116_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f117_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f118_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f121_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f145_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);
    private String f2_WS_PGMNAME;  // WS-PGMNAME PIC X(08)
    private long f3_WS_LENGTH;  // WS-LENGTH PIC S9(4) BINARY
    private String f20_WS_ERR_FLG;  // WS-ERR-FLG PIC X(01)
    private String f73_FRAUD_RPT_DATE;  // FRAUD-RPT-DATE PIC X(10)

    private CicsTask task;
    private final java.util.Map<String, Integer> handlers = new java.util.HashMap<>();
    private final java.util.Map<String, DetCics.Store<?>> stores = new java.util.HashMap<>();
    private final java.util.Map<String, byte[]> heldKey = new java.util.HashMap<>();
    /** Writes the COMMAREA's bytes back into the object the task carries (a LINKed program's is its caller's). */
    private Runnable caBack = () -> { };

    /** The program ends because of an abend: a LINKed program's COMMAREA writes stay its caller's. */
    private Goback abended() {
        if (task.level() > 1) {
            caBack.run();
        }
        return new Goback();
    }

    @SuppressWarnings("unchecked")
    private <E> DetCics.Store<E> store(String name) {
        throw new Hole("CICS file " + name + ": the program names no file the generated project stores");
    }

    private static final java.util.Map<String, Integer> PARAGRAPHS = java.util.Map.ofEntries(
            java.util.Map.entry("FRAUD-UPDATE", 1),
            java.util.Map.entry("MAIN-PARA", 0)
    );

    private static int paragraph(String name) {
        Integer i = PARAGRAPHS.get(name);
        if (i == null) {
            throw new IllegalStateException("no paragraph " + name);
        }
        return i;
    }

    /** A condition the command did not return in RESP: its HANDLE CONDITION label, or -1 (go on) when IGNOREd
     *  (#4414); else CICS's default action -- -1 for one whose default is to ignore it (#4413: EOC); else the
     *  ERROR label (#4502: IBM, HANDLE CONDITION: "if the default action for such a condition terminates the
     *  task abnormally, and the condition ERROR has been specified, the action for ERROR is taken"); else an
     *  abend, to this program's HANDLE ABEND exit or ending the task. */
    private int condition(String cond) {
        Integer h = handlers.get(cond);
        if (h != null) {
            return h;
        }
        if (DetCics.ignoredByDefault(cond)) {
            return -1;
        }
        Integer error = handlers.get("ERROR");
        if (error != null) {
            return error;
        }
        String label = task.abendOnCondition(cond);
        if (label == null) {
            throw abended();
        }
        return paragraph(label);
    }

    private static int cx(CicsTask task, int whole) {
        return task.eibcalen() == null ? whole : task.eibcalen();
    }

    private void in_Copaus2cDfhcommarea(Copaus2cDfhcommarea d, Storage s, int base) {
        if (d == null) {
            return;
        }
        Cobol.move(d.getWsAcctId() == null ? BigDecimal.ZERO : new BigDecimal(d.getWsAcctId().toString()), Field.zoned(s, base + 0, 11, 0, false, false, false), CS);
        Cobol.move(d.getWsCustId() == null ? BigDecimal.ZERO : new BigDecimal(d.getWsCustId().toString()), Field.zoned(s, base + 11, 9, 0, false, false, false), CS);
        Cobol.move(d.getPaAuthDate9C() == null ? BigDecimal.ZERO : new BigDecimal(d.getPaAuthDate9C().toString()), Field.packed(s, base + 20, 5, 0, true), CS);
        Cobol.move(d.getPaAuthTime9C() == null ? BigDecimal.ZERO : new BigDecimal(d.getPaAuthTime9C().toString()), Field.packed(s, base + 23, 9, 0, true), CS);
        Cobol.move(d.getPaAuthOrigDate() == null ? "" : d.getPaAuthOrigDate(), Field.alphanumeric(s, base + 28, 6, false), CS);
        Cobol.move(d.getPaAuthOrigTime() == null ? "" : d.getPaAuthOrigTime(), Field.alphanumeric(s, base + 34, 6, false), CS);
        Cobol.move(d.getPaCardNum() == null ? "" : d.getPaCardNum(), Field.alphanumeric(s, base + 40, 16, false), CS);
        Cobol.move(d.getPaAuthType() == null ? "" : d.getPaAuthType(), Field.alphanumeric(s, base + 56, 4, false), CS);
        Cobol.move(d.getPaCardExpiryDate() == null ? "" : d.getPaCardExpiryDate(), Field.alphanumeric(s, base + 60, 4, false), CS);
        Cobol.move(d.getPaMessageType() == null ? "" : d.getPaMessageType(), Field.alphanumeric(s, base + 64, 6, false), CS);
        Cobol.move(d.getPaMessageSource() == null ? "" : d.getPaMessageSource(), Field.alphanumeric(s, base + 70, 6, false), CS);
        Cobol.move(d.getPaAuthIdCode() == null ? "" : d.getPaAuthIdCode(), Field.alphanumeric(s, base + 76, 6, false), CS);
        Cobol.move(d.getPaAuthRespCode() == null ? "" : d.getPaAuthRespCode(), Field.alphanumeric(s, base + 82, 2, false), CS);
        Cobol.move(d.getPaAuthRespReason() == null ? "" : d.getPaAuthRespReason(), Field.alphanumeric(s, base + 84, 4, false), CS);
        Cobol.move(d.getPaProcessingCode() == null ? BigDecimal.ZERO : new BigDecimal(d.getPaProcessingCode().toString()), Field.zoned(s, base + 88, 6, 0, false, false, false), CS);
        Cobol.move(d.getPaTransactionAmt() == null ? BigDecimal.ZERO : new BigDecimal(d.getPaTransactionAmt().toString()), Field.packed(s, base + 94, 12, 2, true), CS);
        Cobol.move(d.getPaApprovedAmt() == null ? BigDecimal.ZERO : new BigDecimal(d.getPaApprovedAmt().toString()), Field.packed(s, base + 101, 12, 2, true), CS);
        Cobol.move(d.getPaMerchantCatagoryCode() == null ? "" : d.getPaMerchantCatagoryCode(), Field.alphanumeric(s, base + 108, 4, false), CS);
        Cobol.move(d.getPaAcqrCountryCode() == null ? "" : d.getPaAcqrCountryCode(), Field.alphanumeric(s, base + 112, 3, false), CS);
        Cobol.move(d.getPaPosEntryMode() == null ? BigDecimal.ZERO : new BigDecimal(d.getPaPosEntryMode().toString()), Field.zoned(s, base + 115, 2, 0, false, false, false), CS);
        Cobol.move(d.getPaMerchantId() == null ? "" : d.getPaMerchantId(), Field.alphanumeric(s, base + 117, 15, false), CS);
        Cobol.move(d.getPaMerchantName() == null ? "" : d.getPaMerchantName(), Field.alphanumeric(s, base + 132, 22, false), CS);
        Cobol.move(d.getPaMerchantCity() == null ? "" : d.getPaMerchantCity(), Field.alphanumeric(s, base + 154, 13, false), CS);
        Cobol.move(d.getPaMerchantState() == null ? "" : d.getPaMerchantState(), Field.alphanumeric(s, base + 167, 2, false), CS);
        Cobol.move(d.getPaMerchantZip() == null ? "" : d.getPaMerchantZip(), Field.alphanumeric(s, base + 169, 9, false), CS);
        Cobol.move(d.getPaTransactionId() == null ? "" : d.getPaTransactionId(), Field.alphanumeric(s, base + 178, 15, false), CS);
        Cobol.move(d.getPaMatchStatus() == null ? "" : d.getPaMatchStatus(), Field.alphanumeric(s, base + 193, 1, false), CS);
        Cobol.move(d.getPaAuthFraud() == null ? "" : d.getPaAuthFraud(), Field.alphanumeric(s, base + 194, 1, false), CS);
        Cobol.move(d.getPaFraudRptDate() == null ? "" : d.getPaFraudRptDate(), Field.alphanumeric(s, base + 195, 8, false), CS);
        Cobol.move(d.getWsFrdAction() == null ? "" : d.getWsFrdAction(), Field.alphanumeric(s, base + 220, 1, false), CS);
        Cobol.move(d.getWsFrdUpdateStatus() == null ? "" : d.getWsFrdUpdateStatus(), Field.alphanumeric(s, base + 221, 1, false), CS);
        Cobol.move(d.getWsFrdActMsg() == null ? "" : d.getWsFrdActMsg(), Field.alphanumeric(s, base + 222, 50, false), CS);
    }

    private void fill_Copaus2cDfhcommarea(Copaus2cDfhcommarea d, Storage s, int base) {
        d.setWsAcctId(Cobol.num(Field.zoned(s, base + 0, 11, 0, false, false, false), CS).longValue());
        d.setWsCustId(Cobol.num(Field.zoned(s, base + 11, 9, 0, false, false, false), CS).intValue());
        d.setPaAuthDate9C(Cobol.num(Field.packed(s, base + 20, 5, 0, true), CS).intValue());
        d.setPaAuthTime9C(Cobol.num(Field.packed(s, base + 23, 9, 0, true), CS).intValue());
        d.setPaAuthOrigDate(Cobol.text(Field.alphanumeric(s, base + 28, 6, false), CS));
        d.setPaAuthOrigTime(Cobol.text(Field.alphanumeric(s, base + 34, 6, false), CS));
        d.setPaCardNum(Cobol.text(Field.alphanumeric(s, base + 40, 16, false), CS));
        d.setPaAuthType(Cobol.text(Field.alphanumeric(s, base + 56, 4, false), CS));
        d.setPaCardExpiryDate(Cobol.text(Field.alphanumeric(s, base + 60, 4, false), CS));
        d.setPaMessageType(Cobol.text(Field.alphanumeric(s, base + 64, 6, false), CS));
        d.setPaMessageSource(Cobol.text(Field.alphanumeric(s, base + 70, 6, false), CS));
        d.setPaAuthIdCode(Cobol.text(Field.alphanumeric(s, base + 76, 6, false), CS));
        d.setPaAuthRespCode(Cobol.text(Field.alphanumeric(s, base + 82, 2, false), CS));
        d.setPaAuthRespReason(Cobol.text(Field.alphanumeric(s, base + 84, 4, false), CS));
        d.setPaProcessingCode(Cobol.num(Field.zoned(s, base + 88, 6, 0, false, false, false), CS).intValue());
        d.setPaTransactionAmt(Cobol.num(Field.packed(s, base + 94, 12, 2, true), CS));
        d.setPaApprovedAmt(Cobol.num(Field.packed(s, base + 101, 12, 2, true), CS));
        d.setPaMerchantCatagoryCode(Cobol.text(Field.alphanumeric(s, base + 108, 4, false), CS));
        d.setPaAcqrCountryCode(Cobol.text(Field.alphanumeric(s, base + 112, 3, false), CS));
        d.setPaPosEntryMode(Cobol.num(Field.zoned(s, base + 115, 2, 0, false, false, false), CS).intValue());
        d.setPaMerchantId(Cobol.text(Field.alphanumeric(s, base + 117, 15, false), CS));
        d.setPaMerchantName(Cobol.text(Field.alphanumeric(s, base + 132, 22, false), CS));
        d.setPaMerchantCity(Cobol.text(Field.alphanumeric(s, base + 154, 13, false), CS));
        d.setPaMerchantState(Cobol.text(Field.alphanumeric(s, base + 167, 2, false), CS));
        d.setPaMerchantZip(Cobol.text(Field.alphanumeric(s, base + 169, 9, false), CS));
        d.setPaTransactionId(Cobol.text(Field.alphanumeric(s, base + 178, 15, false), CS));
        d.setPaMatchStatus(Cobol.text(Field.alphanumeric(s, base + 193, 1, false), CS));
        d.setPaAuthFraud(Cobol.text(Field.alphanumeric(s, base + 194, 1, false), CS));
        d.setPaFraudRptDate(Cobol.text(Field.alphanumeric(s, base + 195, 8, false), CS));
        d.setWsFrdAction(Cobol.text(Field.alphanumeric(s, base + 220, 1, false), CS));
        d.setWsFrdUpdateStatus(Cobol.text(Field.alphanumeric(s, base + 221, 1, false), CS));
        d.setWsFrdActMsg(Cobol.text(Field.alphanumeric(s, base + 222, 50, false), CS));
    }

    private Copaus2cDfhcommarea out_Copaus2cDfhcommarea(Storage s, int base) {
        Copaus2cDfhcommarea d = new Copaus2cDfhcommarea();
        fill_Copaus2cDfhcommarea(d, s, base);
        return d;
    }

    /** #4270 (X23): DFHCOMMAREA's whole record again, with what the task left in its EIBCALEN bytes. */
    private void caWhole(byte[] whole) {
        if (s_DFHCOMMAREA.bytes != whole) {
            System.arraycopy(s_DFHCOMMAREA.bytes, 0, whole, 0, s_DFHCOMMAREA.bytes.length);
            s_DFHCOMMAREA.bytes = whole;
        }
    }


    private final AuthfrdsRepository authfrdsRepository;
    private final DatasetResolver datasets;
    private final CobolFiles files;
    private final MainframeClock clock;

    public Copaus2cService(AuthfrdsRepository authfrdsRepository, DatasetResolver datasets, CobolFiles files, MainframeClock clock) {
        this.authfrdsRepository = authfrdsRepository;
        this.datasets = datasets;
        this.files = files;
        this.clock = clock;
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_VARIABLES, 0, s_WS_VARIABLES.bytes, 0, IMAGE_s_WS_VARIABLES.length);
        System.arraycopy(IMAGE_s_SQLCA, 0, s_SQLCA.bytes, 0, IMAGE_s_SQLCA.length);
        System.arraycopy(IMAGE_s_DCLAUTHFRDS, 0, s_DCLAUTHFRDS.bytes, 0, IMAGE_s_DCLAUTHFRDS.length);
        System.arraycopy(IMAGE_s_DFHCOMMAREA, 0, s_DFHCOMMAREA.bytes, 0, IMAGE_s_DFHCOMMAREA.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
        f2_WS_PGMNAME = "COPAUS2C";
        f3_WS_LENGTH = 0L;
        f20_WS_ERR_FLG = "N";
        f73_FRAUD_RPT_DATE = "          ";
        Cobol.moveFigurative(Figurative.ZEROS, f21_WS_SQLCODE, CS);
        Cobol.moveFigurative(Figurative.ZEROS, f22_WS_SQLSTATE, CS);
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 1);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f145_GG_RETURN_CODE, CS).intValue();
    }

    /** One task of the program: the EIB and COMMAREA from the task, then the PROCEDURE DIVISION. */
    public void runTask(CicsTask task) {
        boolean truncBefore = Cobol.swapTruncBinary(true);  // TRUNC(STD)
        boolean pfdBefore = Cobol.swapNumprocPfd(false);  // NUMPROC(NOPFD)
        try {
            this.task = task;
            DetSql.closeAll();  // a task's cursors are its own
            caBack = () -> { };
            handlers.clear();
            heldKey.clear();
            initialState();
            Cobol.move(task.transid(), f116_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f118_EIBTRMID, CS);
            Cobol.store(f117_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f115_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f114_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (ca instanceof Copaus2cDfhcommarea x) {
                in_Copaus2cDfhcommarea(x, s_DFHCOMMAREA, 0);
                caBack = () -> fill_Copaus2cDfhcommarea(x, s_DFHCOMMAREA, 0);
                calen = cx(task, 272);
            }
            s_DFHCOMMAREA.beyond = null;
            if (ca instanceof byte[] cb0) {
                byte[] cb = DetCics.commareaIn(cb0, CS);
                System.arraycopy(cb, 0, s_DFHCOMMAREA.bytes, 0, Math.min(cb.length, s_DFHCOMMAREA.bytes.length));
                if (cb.length > s_DFHCOMMAREA.bytes.length) {
                    s_DFHCOMMAREA.beyond = java.util.Arrays.copyOfRange(cb, s_DFHCOMMAREA.bytes.length, cb.length);
                }
                calen = cx(task, cb.length);
            }
            byte[] raw = task.linkArea();
            if (raw != null) {
                System.arraycopy(raw, 0, s_DFHCOMMAREA.bytes, 0, Math.min(raw.length, s_DFHCOMMAREA.bytes.length));
                int keep = s_DFHCOMMAREA.bytes.length;
                s_DFHCOMMAREA.beyond = raw.length > keep ? java.util.Arrays.copyOfRange(raw, keep, raw.length) : null;
                Runnable typed = caBack;
                caBack = () -> { typed.run(); System.arraycopy(s_DFHCOMMAREA.bytes, 0, raw, 0, Math.min(raw.length, keep)); if (s_DFHCOMMAREA.beyond != null) { System.arraycopy(s_DFHCOMMAREA.beyond, 0, raw, keep, raw.length - keep); } };
            }
            byte[] caWhole = null;
            if (task.exactCommarea() && calen < s_DFHCOMMAREA.bytes.length) {
                caWhole = s_DFHCOMMAREA.bytes;
                s_DFHCOMMAREA.bytes = java.util.Arrays.copyOf(caWhole, calen);
                Runnable typed = caBack;
                byte[] whole = caWhole;
                caBack = () -> { caWhole(whole); typed.run(); };
            }
            Cobol.store(f121_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                try {
                    perform(0, 1);
                } catch (Goback g) {
                    // RETURN / XCTL / an abend ended the program
                }
            } catch (IndexOutOfBoundsException e) {
                if (caWhole == null) {
                    throw e;
                }
                throw new DetCics.PastFrom("COMMAREA past EIBCALEN (" + calen + " bytes): not modelled");
            } finally {
                if (caWhole != null) {
                    caWhole(caWhole);
                }
            }
            if (!task.ended()) {
                caBack.run();
                task.returnTransid(null, null);  // a GOBACK is a RETURN
            }
        } finally {
            Cobol.swapTruncBinary(truncBefore);
            Cobol.swapNumprocPfd(pfdBefore);
        }
    }

    public Copaus2cDfhcommarea handleLink(Copaus2cDfhcommarea request) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("COPAUS2C", request);
        region.run(task, "COPAUS2C", this::runTask);
        return request;
    }

    public Copaus2cDfhcommarea handleLink(Copaus2cDfhcommarea request, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("COPAUS2C", request, area);
        region.run(task, "COPAUS2C", this::runTask);
        byte[] left = task.linkAreaView();
        lastLinkBytes = task.linkAreaTaken() && left != null ? java.util.Arrays.copyOf(left, left.length) : null;
        return request;
    }

    // @facade-helper: the bytes the last byte-carrying handleLink's program left in the COMMAREA
    private byte[] lastLinkBytes;

    /** The bytes the last byte-carrying handleLink's program left in the LINK COMMAREA (a copy; null: it
     *  took none -- its DTO is the COMMAREA). @facade-helper */
    public byte[] lastLinkBytes() {
        return lastLinkBytes == null ? null : java.util.Arrays.copyOf(lastLinkBytes, lastLinkBytes.length);
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
            DetSql.closeAll();  // a step's cursors are its own
            initialState();
            try {
                perform(0, 1);
            } catch (Goback g) {
                // the program ended
            }
            return Cobol.num(f145_GG_RETURN_CODE, CS).intValue();
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
                if (next >= 2) {
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
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** MAIN-PARA. */
    private int p0() {
        // EXEC CICS ASKTIME NOHANDLE ABSTIME(WS-ABS-TIME) NOHANDLE END-EXEC
        Cobol.store(f23_WS_ABS_TIME, BigDecimal.valueOf(task.asktime()), false, CS);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS-TIME) MMDDYY(WS-CUR-DATE) DATESEP NOHANDLE END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f23_WS_ABS_TIME, CS).longValue(), "MMDDYY", "/"), f24_WS_CUR_DATE, CS);
        // MOVE WS-CUR-DATE TO PA-FRAUD-RPT-DATE
        Cobol.move(f24_WS_CUR_DATE, f107_PA_FRAUD_RPT_DATE, CS);
        // MOVE PA-AUTH-ORIG-DATE(1:2) TO WS-AUTH-YY
        Cobol.move(f83_PA_AUTH_ORIG_DATE.ref(1, Integer.valueOf(2)), f7_WS_AUTH_YY, CS);
        // MOVE PA-AUTH-ORIG-DATE(3:2) TO WS-AUTH-MM
        Cobol.move(f83_PA_AUTH_ORIG_DATE.ref(3, Integer.valueOf(2)), f9_WS_AUTH_MM, CS);
        // MOVE PA-AUTH-ORIG-DATE(5:2) TO WS-AUTH-DD
        Cobol.move(f83_PA_AUTH_ORIG_DATE.ref(5, Integer.valueOf(2)), f11_WS_AUTH_DD, CS);
        // COMPUTE WS-AUTH-TIME = 999999999 - PA-AUTH-TIME-9C
        BigDecimal v1 = D999999999.subtract(Cobol.num(f82_PA_AUTH_TIME_9C, CS));
        Cobol.store(f4_WS_AUTH_TIME, v1, false, CS);
        // MOVE WS-AUTH-TIME-AN(1:2) TO WS-AUTH-HH
        Cobol.move(f5_WS_AUTH_TIME_AN.ref(1, Integer.valueOf(2)), f13_WS_AUTH_HH, CS);
        // MOVE WS-AUTH-TIME-AN(3:2) TO WS-AUTH-MI
        Cobol.move(f5_WS_AUTH_TIME_AN.ref(3, Integer.valueOf(2)), f15_WS_AUTH_MI, CS);
        // MOVE WS-AUTH-TIME-AN(5:2) TO WS-AUTH-SS
        Cobol.move(f5_WS_AUTH_TIME_AN.ref(5, Integer.valueOf(2)), f17_WS_AUTH_SS, CS);
        // MOVE WS-AUTH-TIME-AN(7:3) TO WS-AUTH-SSS
        Cobol.move(f5_WS_AUTH_TIME_AN.ref(7, Integer.valueOf(3)), f18_WS_AUTH_SSS, CS);
        // MOVE PA-CARD-NUM TO CARD-NUM
        Cobol.move(f85_PA_CARD_NUM, f48_CARD_NUM, CS);
        // MOVE WS-AUTH-TS TO AUTH-TS
        Cobol.move(f6_WS_AUTH_TS, f49_AUTH_TS, CS);
        // MOVE PA-AUTH-TYPE TO AUTH-TYPE
        Cobol.move(f86_PA_AUTH_TYPE, f50_AUTH_TYPE, CS);
        // MOVE PA-CARD-EXPIRY-DATE TO CARD-EXPIRY-DATE
        Cobol.move(f87_PA_CARD_EXPIRY_DATE, f51_CARD_EXPIRY_DATE, CS);
        // MOVE PA-MESSAGE-TYPE TO MESSAGE-TYPE
        Cobol.move(f88_PA_MESSAGE_TYPE, f52_MESSAGE_TYPE, CS);
        // MOVE PA-MESSAGE-SOURCE TO MESSAGE-SOURCE
        Cobol.move(f89_PA_MESSAGE_SOURCE, f53_MESSAGE_SOURCE, CS);
        // MOVE PA-AUTH-ID-CODE TO AUTH-ID-CODE
        Cobol.move(f90_PA_AUTH_ID_CODE, f54_AUTH_ID_CODE, CS);
        // MOVE PA-AUTH-RESP-CODE TO AUTH-RESP-CODE
        Cobol.move(f91_PA_AUTH_RESP_CODE, f55_AUTH_RESP_CODE, CS);
        // MOVE PA-AUTH-RESP-REASON TO AUTH-RESP-REASON
        Cobol.move(f92_PA_AUTH_RESP_REASON, f56_AUTH_RESP_REASON, CS);
        // MOVE PA-PROCESSING-CODE TO PROCESSING-CODE
        Cobol.move(f93_PA_PROCESSING_CODE, f57_PROCESSING_CODE, CS);
        // MOVE PA-TRANSACTION-AMT TO TRANSACTION-AMT
        Cobol.move(f94_PA_TRANSACTION_AMT, f58_TRANSACTION_AMT, CS);
        // MOVE PA-APPROVED-AMT TO APPROVED-AMT
        Cobol.move(f95_PA_APPROVED_AMT, f59_APPROVED_AMT, CS);
        // MOVE PA-MERCHANT-CATAGORY-CODE TO MERCHANT-CATAGORY-CODE
        Cobol.move(f96_PA_MERCHANT_CATAGORY_CODE, f60_MERCHANT_CATAGORY_CODE, CS);
        // MOVE PA-ACQR-COUNTRY-CODE TO ACQR-COUNTRY-CODE
        Cobol.move(f97_PA_ACQR_COUNTRY_CODE, f61_ACQR_COUNTRY_CODE, CS);
        // MOVE PA-POS-ENTRY-MODE TO POS-ENTRY-MODE
        Cobol.move(f98_PA_POS_ENTRY_MODE, f62_POS_ENTRY_MODE, CS);
        // MOVE PA-MERCHANT-ID TO MERCHANT-ID
        Cobol.move(f99_PA_MERCHANT_ID, f63_MERCHANT_ID, CS);
        // MOVE LENGTH OF PA-MERCHANT-NAME TO MERCHANT-NAME-LEN
        Cobol.move(BigDecimal.valueOf(22), f65_MERCHANT_NAME_LEN, CS);
        // MOVE PA-MERCHANT-NAME TO MERCHANT-NAME-TEXT
        Cobol.move(f100_PA_MERCHANT_NAME, f66_MERCHANT_NAME_TEXT, CS);
        // MOVE PA-MERCHANT-CITY TO MERCHANT-CITY
        Cobol.move(f101_PA_MERCHANT_CITY, f67_MERCHANT_CITY, CS);
        // MOVE PA-MERCHANT-STATE TO MERCHANT-STATE
        Cobol.move(f102_PA_MERCHANT_STATE, f68_MERCHANT_STATE, CS);
        // MOVE PA-MERCHANT-ZIP TO MERCHANT-ZIP
        Cobol.move(f103_PA_MERCHANT_ZIP, f69_MERCHANT_ZIP, CS);
        // MOVE PA-TRANSACTION-ID TO TRANSACTION-ID
        Cobol.move(f104_PA_TRANSACTION_ID, f70_TRANSACTION_ID, CS);
        // MOVE PA-MATCH-STATUS TO MATCH-STATUS
        Cobol.move(f105_PA_MATCH_STATUS, f71_MATCH_STATUS, CS);
        // MOVE WS-FRD-ACTION TO AUTH-FRAUD
        Cobol.move(f110_WS_FRD_ACTION, f72_AUTH_FRAUD, CS);
        // MOVE WS-ACCT-ID TO ACCT-ID
        Cobol.move(f77_WS_ACCT_ID, f74_ACCT_ID, CS);
        // MOVE WS-CUST-ID TO CUST-ID
        Cobol.move(f78_WS_CUST_ID, f75_CUST_ID, CS);
        // EXEC SQL INSERT INTO CARDDEMO.AUTHFRDS (CARD_NUM ,AUTH_TS ,AUTH_TYPE ,CARD_EXPIRY_DATE ,MESSAGE_TYPE ,MESSAGE_SOURCE ,AUTH_ID_CODE ,AUTH_RESP_CODE ,AU
        java.util.Map<String, Object> sqlParams2 = new java.util.HashMap<>();
        sqlParams2.put("cardNum", DetSql.charIn(f48_CARD_NUM, CS));
        sqlParams2.put("authTs", DetSql.charIn(f49_AUTH_TS, CS));
        sqlParams2.put("authType", DetSql.charIn(f50_AUTH_TYPE, CS));
        sqlParams2.put("cardExpiryDate", DetSql.charIn(f51_CARD_EXPIRY_DATE, CS));
        sqlParams2.put("messageType", DetSql.charIn(f52_MESSAGE_TYPE, CS));
        sqlParams2.put("messageSource", DetSql.charIn(f53_MESSAGE_SOURCE, CS));
        sqlParams2.put("authIdCode", DetSql.charIn(f54_AUTH_ID_CODE, CS));
        sqlParams2.put("authRespCode", DetSql.charIn(f55_AUTH_RESP_CODE, CS));
        sqlParams2.put("authRespReason", DetSql.charIn(f56_AUTH_RESP_REASON, CS));
        sqlParams2.put("processingCode", DetSql.charIn(f57_PROCESSING_CODE, CS));
        sqlParams2.put("transactionAmt", DetSql.numIn(f58_TRANSACTION_AMT, CS));
        sqlParams2.put("approvedAmt", DetSql.numIn(f59_APPROVED_AMT, CS));
        sqlParams2.put("merchantCatagoryCode", DetSql.charIn(f60_MERCHANT_CATAGORY_CODE, CS));
        sqlParams2.put("acqrCountryCode", DetSql.charIn(f61_ACQR_COUNTRY_CODE, CS));
        sqlParams2.put("posEntryMode", DetSql.numIn(f62_POS_ENTRY_MODE, CS));
        sqlParams2.put("merchantId", DetSql.charIn(f63_MERCHANT_ID, CS));
        sqlParams2.put("merchantName", DetSql.varcharIn(f65_MERCHANT_NAME_LEN, f66_MERCHANT_NAME_TEXT, CS));
        sqlParams2.put("merchantCity", DetSql.charIn(f67_MERCHANT_CITY, CS));
        sqlParams2.put("merchantState", DetSql.charIn(f68_MERCHANT_STATE, CS));
        sqlParams2.put("merchantZip", DetSql.charIn(f69_MERCHANT_ZIP, CS));
        sqlParams2.put("transactionId", DetSql.charIn(f70_TRANSACTION_ID, CS));
        sqlParams2.put("matchStatus", DetSql.charIn(f71_MATCH_STATUS, CS));
        sqlParams2.put("authFraud", DetSql.charIn(f72_AUTH_FRAUD, CS));
        sqlParams2.put("acctId", DetSql.numIn(f74_ACCT_ID, CS));
        sqlParams2.put("custId", DetSql.numIn(f75_CUST_ID, CS));
        DetSql.update(f25_SQLCA, "COPAUS2C:141", () -> authfrdsRepository.insertL141Copaus2c(sqlParams2), false, CS);
        // IF SQLCODE = ZERO
        if (Cobol.num(f28_SQLCODE, CS).compareTo(BigDecimal.ZERO) == 0) {
            // SET WS-FRD-UPDT-SUCCESS TO TRUE
            Cobol.move("S", f111_WS_FRD_UPDATE_STATUS, CS);
            // MOVE 'ADD SUCCESS' TO WS-FRD-ACT-MSG
            Cobol.move("ADD SUCCESS", f112_WS_FRD_ACT_MSG, CS);
        } else {
            // ELSE IF SQLCODE = -803
            if (Cobol.num(f28_SQLCODE, CS).compareTo(DM803) == 0) {
                // PERFORM FRAUD-UPDATE
                perform(1, 1);
            } else {
                // SET WS-FRD-UPDT-FAILED TO TRUE
                Cobol.move("F", f111_WS_FRD_UPDATE_STATUS, CS);
                // MOVE SQLCODE TO WS-SQLCODE
                Cobol.move(f28_SQLCODE, f21_WS_SQLCODE, CS);
                // MOVE SQLSTATE TO WS-SQLSTATE
                Cobol.move(f46_SQLSTATE, f22_WS_SQLSTATE, CS);
                // STRING ' SYSTEM ERROR DB2: CODE:' WS-SQLCODE ', STATE: ' WS-SQLSTATE DELIMITED BY SIZE INTO WS-FRD-ACT-MSG
                Cobol.string(f112_WS_FRD_ACT_MSG, null, CS, Cobol.StringPart.size(" SYSTEM ERROR DB2: CODE:", CS), Cobol.StringPart.size(f21_WS_SQLCODE), Cobol.StringPart.size(", STATE: ", CS), Cobol.StringPart.size(f22_WS_SQLSTATE));
            }
        }
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        return 1;
    }

    /** FRAUD-UPDATE. */
    private int p1() {
        // EXEC SQL UPDATE CARDDEMO.AUTHFRDS SET AUTH_FRAUD = :AUTH-FRAUD, FRAUD_RPT_DATE = CURRENT DATE WHERE CARD_NUM = :CARD-NUM AND AUTH_TS = TIMESTAMP_FORMA
        java.util.Map<String, Object> sqlParams3 = new java.util.HashMap<>();
        sqlParams3.put("authFraud", DetSql.charIn(f72_AUTH_FRAUD, CS));
        sqlParams3.put("cardNum", DetSql.charIn(f48_CARD_NUM, CS));
        sqlParams3.put("authTs", DetSql.charIn(f49_AUTH_TS, CS));
        DetSql.update(f25_SQLCA, "COPAUS2C:222", () -> authfrdsRepository.updateL222Copaus2c(sqlParams3), true, CS);
        // IF SQLCODE = ZERO
        if (Cobol.num(f28_SQLCODE, CS).compareTo(BigDecimal.ZERO) == 0) {
            // SET WS-FRD-UPDT-SUCCESS TO TRUE
            Cobol.move("S", f111_WS_FRD_UPDATE_STATUS, CS);
            // MOVE 'UPDT SUCCESS' TO WS-FRD-ACT-MSG
            Cobol.move("UPDT SUCCESS", f112_WS_FRD_ACT_MSG, CS);
        } else {
            // SET WS-FRD-UPDT-FAILED TO TRUE
            Cobol.move("F", f111_WS_FRD_UPDATE_STATUS, CS);
            // MOVE SQLCODE TO WS-SQLCODE
            Cobol.move(f28_SQLCODE, f21_WS_SQLCODE, CS);
            // MOVE SQLSTATE TO WS-SQLSTATE
            Cobol.move(f46_SQLSTATE, f22_WS_SQLSTATE, CS);
            // STRING ' UPDT ERROR DB2: CODE:' WS-SQLCODE ', STATE: ' WS-SQLSTATE DELIMITED BY SIZE INTO WS-FRD-ACT-MSG
            Cobol.string(f112_WS_FRD_ACT_MSG, null, CS, Cobol.StringPart.size(" UPDT ERROR DB2: CODE:", CS), Cobol.StringPart.size(f21_WS_SQLCODE), Cobol.StringPart.size(", STATE: ", CS), Cobol.StringPart.size(f22_WS_SQLSTATE));
        }
        return 2;
    }

}
