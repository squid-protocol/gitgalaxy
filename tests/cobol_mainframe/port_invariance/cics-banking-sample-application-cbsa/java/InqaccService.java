// gitgalaxy-det-port: COBOL INQACC (INQACC.cbl), translated by rule, statement for statement
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
import com.gitgalaxy.modernized.repository.db2.AccountRepository;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * INQACC: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 227, translated 227, holes 0.
 */
@Service
public class InqaccService {

    private static final Charset CS = CobolRecords.charset();
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D99999999 = new BigDecimal("99999999");
    private static final BigDecimal D0 = new BigDecimal("0");
    private static final BigDecimal D100 = new BigDecimal("100");
    private static final BigDecimal D923 = new BigDecimal("923");

    private static final byte[] IMAGE_s_SORTCODE = Base64.getDecoder().decode(String.join("",
            "OTg3NjU0"));
    private static final byte[] IMAGE_s_HOST_ACCOUNT_ROW = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgAAAADCAgICAgICAgICAAAAAAICAgICAgICAgICAgICAgICAgICAAAAAAAAAMAAAAAAAADA=="));
    private static final byte[] IMAGE_s_SQLCA = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAAAAAAAAAAAAAAICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_CICS_WORK_AREA = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAA="));
    private static final byte[] IMAGE_s_OUTPUT_DATA = Base64.getDecoder().decode(String.join("",
            "ICAgIDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMCAgICAgICAgMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="));
    private static final byte[] IMAGE_s_RETURNED_DATA = Base64.getDecoder().decode(String.join("",
            "ICAgIDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMCAgICAgICAgMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="));
    private static final byte[] IMAGE_s_DB2_DATE_REFORMAT = Base64.getDecoder().decode(String.join("",
            "MDAwMCAwMCAwMA=="));
    private static final byte[] IMAGE_s_ACCOUNT_KY = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwMDAwMDA="));
    private static final byte[] IMAGE_s_MY_ABEND_CODE = Base64.getDecoder().decode(String.join("",
            "ICAgIA=="));
    private static final byte[] IMAGE_s_SQLCODE_DISPLAY = Base64.getDecoder().decode(String.join("",
            "KzAwMDAwMDAw"));
    private static final byte[] IMAGE_s_NCS_ACC_NO_STUFF = Base64.getDecoder().decode(String.join("",
            "SEJOS0FDQ1QgICAgICAgIAAAAAAAAAAAAAAAAAAAAAAwMA=="));
    private static final byte[] IMAGE_s_ACCOUNT_KY2 = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwMDAwMDA="));
    private static final byte[] IMAGE_s_WS_POINTER = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAA="));
    private static final byte[] IMAGE_s_WS_U_TIME = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAw="));
    private static final byte[] IMAGE_s_WS_ORIG_DATE = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_ORIG_DATE_GRP_X = Base64.getDecoder().decode(String.join("",
            "ICAuICAuICAgIA=="));
    private static final byte[] IMAGE_s_WS_TIME_DATA = Base64.getDecoder().decode(String.join("",
            "MDAwMDAw"));
    private static final byte[] IMAGE_s_ABNDINFO_REC = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAwwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgKzAwMDAwMDAwKzAwMDAwMDAwKzAwMDAwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_DFHCOMMAREA = Base64.getDecoder().decode(String.join("",
            "ICAgIDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMCAgICAgICAgMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_SORTCODE = new Storage(IMAGE_s_SORTCODE.length);
    private final Storage s_HOST_ACCOUNT_ROW = new Storage(IMAGE_s_HOST_ACCOUNT_ROW.length);
    private final Storage s_SQLCA = new Storage(IMAGE_s_SQLCA.length);
    private final Storage s_WS_CICS_WORK_AREA = new Storage(IMAGE_s_WS_CICS_WORK_AREA.length);
    private final Storage s_OUTPUT_DATA = new Storage(IMAGE_s_OUTPUT_DATA.length);
    private final Storage s_RETURNED_DATA = new Storage(IMAGE_s_RETURNED_DATA.length);
    private final Storage s_DB2_DATE_REFORMAT = new Storage(IMAGE_s_DB2_DATE_REFORMAT.length);
    private final Storage s_ACCOUNT_KY = new Storage(IMAGE_s_ACCOUNT_KY.length);
    private final Storage s_MY_ABEND_CODE = new Storage(IMAGE_s_MY_ABEND_CODE.length);
    private final Storage s_SQLCODE_DISPLAY = new Storage(IMAGE_s_SQLCODE_DISPLAY.length);
    private final Storage s_NCS_ACC_NO_STUFF = new Storage(IMAGE_s_NCS_ACC_NO_STUFF.length);
    private final Storage s_ACCOUNT_KY2 = new Storage(IMAGE_s_ACCOUNT_KY2.length);
    private final Storage s_WS_POINTER = new Storage(IMAGE_s_WS_POINTER.length);
    private final Storage s_WS_U_TIME = new Storage(IMAGE_s_WS_U_TIME.length);
    private final Storage s_WS_ORIG_DATE = new Storage(IMAGE_s_WS_ORIG_DATE.length);
    private final Storage s_WS_ORIG_DATE_GRP_X = new Storage(IMAGE_s_WS_ORIG_DATE_GRP_X.length);
    private final Storage s_WS_TIME_DATA = new Storage(IMAGE_s_WS_TIME_DATA.length);
    private final Storage s_ABNDINFO_REC = new Storage(IMAGE_s_ABNDINFO_REC.length);
    private final Storage s_DFHCOMMAREA = new Storage(IMAGE_s_DFHCOMMAREA.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_SORTCODE = Field.zoned(s_SORTCODE, 0, 6, 0, false, false, false);
    private final Field f3_HV_ACCOUNT_EYECATCHER = Field.alphanumeric(s_HOST_ACCOUNT_ROW, 0, 4, false);
    private final Field f4_HV_ACCOUNT_CUST_NO = Field.alphanumeric(s_HOST_ACCOUNT_ROW, 4, 10, false);
    private final Field f5_HV_ACCOUNT_SORTCODE = Field.alphanumeric(s_HOST_ACCOUNT_ROW, 14, 6, false);
    private final Field f6_HV_ACCOUNT_ACC_NO = Field.alphanumeric(s_HOST_ACCOUNT_ROW, 20, 8, false);
    private final Field f7_HV_ACCOUNT_ACC_TYPE = Field.alphanumeric(s_HOST_ACCOUNT_ROW, 28, 8, false);
    private final Field f8_HV_ACCOUNT_INT_RATE = Field.packed(s_HOST_ACCOUNT_ROW, 36, 6, 2, true);
    private final Field f9_HV_ACCOUNT_OPENED = Field.alphanumeric(s_HOST_ACCOUNT_ROW, 40, 10, false);
    private final Field f10_HV_ACCOUNT_OVERDRAFT_LIM = Field.binary(s_HOST_ACCOUNT_ROW, 50, 9, 0, true, false);
    private final Field f11_HV_ACCOUNT_LAST_STMT = Field.alphanumeric(s_HOST_ACCOUNT_ROW, 54, 10, false);
    private final Field f12_HV_ACCOUNT_NEXT_STMT = Field.alphanumeric(s_HOST_ACCOUNT_ROW, 64, 10, false);
    private final Field f13_HV_ACCOUNT_AVAIL_BAL = Field.packed(s_HOST_ACCOUNT_ROW, 74, 12, 2, true);
    private final Field f14_HV_ACCOUNT_ACTUAL_BAL = Field.packed(s_HOST_ACCOUNT_ROW, 81, 12, 2, true);
    private final Field f15_SQLCA = Field.group(s_SQLCA, 0, 136);
    private final Field f18_SQLCODE = Field.binary(s_SQLCA, 12, 9, 0, true, true);
    private final Field f20_SQLERRML = Field.binary(s_SQLCA, 16, 4, 0, true, true);
    private final Field f21_SQLERRMC = Field.alphanumeric(s_SQLCA, 18, 70, false);
    private final Field f23_SQLERRD = Field.binary(s_SQLCA, 96, 9, 0, true, true);
    private final Field f36_SQLSTATE = Field.alphanumeric(s_SQLCA, 131, 5, false);
    private final Field f38_WS_CICS_RESP = Field.binary(s_WS_CICS_WORK_AREA, 0, 8, 0, true, false);
    private final Field f39_WS_CICS_RESP2 = Field.binary(s_WS_CICS_WORK_AREA, 4, 8, 0, true, false);
    private final Field f41_OUTPUT_DATA = Field.group(s_OUTPUT_DATA, 0, 98);
    private final Field f43_ACCOUNT_EYE_CATCHER = Field.alphanumeric(s_OUTPUT_DATA, 0, 4, false);
    private final Field f44_ACCOUNT_CUST_NO = Field.zoned(s_OUTPUT_DATA, 4, 10, 0, false, false, false);
    private final Field f46_ACCOUNT_SORT_CODE = Field.zoned(s_OUTPUT_DATA, 14, 6, 0, false, false, false);
    private final Field f47_ACCOUNT_NUMBER = Field.zoned(s_OUTPUT_DATA, 20, 8, 0, false, false, false);
    private final Field f48_ACCOUNT_TYPE = Field.alphanumeric(s_OUTPUT_DATA, 28, 8, false);
    private final Field f49_ACCOUNT_INTEREST_RATE = Field.zoned(s_OUTPUT_DATA, 36, 6, 2, false, false, false);
    private final Field f50_ACCOUNT_OPENED = Field.zoned(s_OUTPUT_DATA, 42, 8, 0, false, false, false);
    private final Field f52_ACCOUNT_OPENED_DAY = Field.zoned(s_OUTPUT_DATA, 42, 2, 0, false, false, false);
    private final Field f53_ACCOUNT_OPENED_MONTH = Field.zoned(s_OUTPUT_DATA, 44, 2, 0, false, false, false);
    private final Field f54_ACCOUNT_OPENED_YEAR = Field.zoned(s_OUTPUT_DATA, 46, 4, 0, false, false, false);
    private final Field f55_ACCOUNT_OVERDRAFT_LIMIT = Field.zoned(s_OUTPUT_DATA, 50, 8, 0, false, false, false);
    private final Field f56_ACCOUNT_LAST_STMT_DATE = Field.zoned(s_OUTPUT_DATA, 58, 8, 0, false, false, false);
    private final Field f58_ACCOUNT_LAST_STMT_DAY = Field.zoned(s_OUTPUT_DATA, 58, 2, 0, false, false, false);
    private final Field f59_ACCOUNT_LAST_STMT_MONTH = Field.zoned(s_OUTPUT_DATA, 60, 2, 0, false, false, false);
    private final Field f60_ACCOUNT_LAST_STMT_YEAR = Field.zoned(s_OUTPUT_DATA, 62, 4, 0, false, false, false);
    private final Field f61_ACCOUNT_NEXT_STMT_DATE = Field.zoned(s_OUTPUT_DATA, 66, 8, 0, false, false, false);
    private final Field f63_ACCOUNT_NEXT_STMT_DAY = Field.zoned(s_OUTPUT_DATA, 66, 2, 0, false, false, false);
    private final Field f64_ACCOUNT_NEXT_STMT_MONTH = Field.zoned(s_OUTPUT_DATA, 68, 2, 0, false, false, false);
    private final Field f65_ACCOUNT_NEXT_STMT_YEAR = Field.zoned(s_OUTPUT_DATA, 70, 4, 0, false, false, false);
    private final Field f66_ACCOUNT_AVAILABLE_BALANCE = Field.zoned(s_OUTPUT_DATA, 74, 12, 2, true, false, false);
    private final Field f67_ACCOUNT_ACTUAL_BALANCE = Field.zoned(s_OUTPUT_DATA, 86, 12, 2, true, false, false);
    private final Field f83_DB2_DATE_REFORMAT = Field.group(s_DB2_DATE_REFORMAT, 0, 10);
    private final Field f84_DB2_DATE_REF_YR = Field.zoned(s_DB2_DATE_REFORMAT, 0, 4, 0, false, false, false);
    private final Field f86_DB2_DATE_REF_MNTH = Field.zoned(s_DB2_DATE_REFORMAT, 5, 2, 0, false, false, false);
    private final Field f88_DB2_DATE_REF_DAY = Field.zoned(s_DB2_DATE_REFORMAT, 8, 2, 0, false, false, false);
    private final Field f94_REQUIRED_SORT_CODE = Field.zoned(s_ACCOUNT_KY, 0, 6, 0, false, false, false);
    private final Field f96_MY_ABEND_CODE = Field.alphanumeric(s_MY_ABEND_CODE, 0, 4, false);
    private final Field f99_SQLCODE_DISPLAY = Field.zoned(s_SQLCODE_DISPLAY, 0, 8, 0, true, true, true);
    private final Field f101_NCS_ACC_NO_NAME = Field.group(s_NCS_ACC_NO_STUFF, 0, 16);
    private final Field f106_NCS_ACC_NO_VALUE = Field.binary(s_NCS_ACC_NO_STUFF, 24, 16, 0, false, false);
    private final Field f111_REQUIRED_ACC_NUMBER2 = Field.zoned(s_ACCOUNT_KY2, 6, 8, 0, false, false, false);
    private final Field f116_WS_U_TIME = Field.packed(s_WS_U_TIME, 0, 15, 0, true);
    private final Field f117_WS_ORIG_DATE = Field.alphanumeric(s_WS_ORIG_DATE, 0, 10, false);
    private final Field f131_WS_TIME_NOW = Field.zoned(s_WS_TIME_DATA, 0, 6, 0, false, false, false);
    private final Field f133_WS_TIME_NOW_GRP_HH = Field.zoned(s_WS_TIME_DATA, 0, 2, 0, false, false, false);
    private final Field f134_WS_TIME_NOW_GRP_MM = Field.zoned(s_WS_TIME_DATA, 2, 2, 0, false, false, false);
    private final Field f137_ABNDINFO_REC = Field.group(s_ABNDINFO_REC, 0, 681);
    private final Field f139_ABND_UTIME_KEY = Field.packed(s_ABNDINFO_REC, 0, 15, 0, true);
    private final Field f140_ABND_TASKNO_KEY = Field.zoned(s_ABNDINFO_REC, 8, 4, 0, false, false, false);
    private final Field f141_ABND_APPLID = Field.alphanumeric(s_ABNDINFO_REC, 12, 8, false);
    private final Field f142_ABND_TRANID = Field.alphanumeric(s_ABNDINFO_REC, 20, 4, false);
    private final Field f143_ABND_DATE = Field.alphanumeric(s_ABNDINFO_REC, 24, 10, false);
    private final Field f144_ABND_TIME = Field.alphanumeric(s_ABNDINFO_REC, 34, 8, false);
    private final Field f145_ABND_CODE = Field.alphanumeric(s_ABNDINFO_REC, 42, 4, false);
    private final Field f146_ABND_PROGRAM = Field.alphanumeric(s_ABNDINFO_REC, 46, 8, false);
    private final Field f147_ABND_RESPCODE = Field.zoned(s_ABNDINFO_REC, 54, 8, 0, true, true, true);
    private final Field f148_ABND_RESP2CODE = Field.zoned(s_ABNDINFO_REC, 63, 8, 0, true, true, true);
    private final Field f149_ABND_SQLCODE = Field.zoned(s_ABNDINFO_REC, 72, 8, 0, true, true, true);
    private final Field f150_ABND_FREEFORM = Field.alphanumeric(s_ABNDINFO_REC, 81, 600, false);
    private final Field f152_INQACC_EYE = Field.alphanumeric(s_DFHCOMMAREA, 0, 4, false);
    private final Field f153_INQACC_CUSTNO = Field.zoned(s_DFHCOMMAREA, 4, 10, 0, false, false, false);
    private final Field f154_INQACC_SCODE = Field.zoned(s_DFHCOMMAREA, 14, 6, 0, false, false, false);
    private final Field f155_INQACC_ACCNO = Field.zoned(s_DFHCOMMAREA, 20, 8, 0, false, false, false);
    private final Field f156_INQACC_ACC_TYPE = Field.alphanumeric(s_DFHCOMMAREA, 28, 8, false);
    private final Field f157_INQACC_INT_RATE = Field.zoned(s_DFHCOMMAREA, 36, 6, 2, false, false, false);
    private final Field f158_INQACC_OPENED = Field.zoned(s_DFHCOMMAREA, 42, 8, 0, false, false, false);
    private final Field f163_INQACC_OVERDRAFT = Field.zoned(s_DFHCOMMAREA, 50, 8, 0, false, false, false);
    private final Field f164_INQACC_LAST_STMT_DT = Field.zoned(s_DFHCOMMAREA, 58, 8, 0, false, false, false);
    private final Field f169_INQACC_NEXT_STMT_DT = Field.zoned(s_DFHCOMMAREA, 66, 8, 0, false, false, false);
    private final Field f174_INQACC_AVAIL_BAL = Field.zoned(s_DFHCOMMAREA, 74, 12, 2, true, false, false);
    private final Field f175_INQACC_ACTUAL_BAL = Field.zoned(s_DFHCOMMAREA, 86, 12, 2, true, false, false);
    private final Field f176_INQACC_SUCCESS = Field.alphanumeric(s_DFHCOMMAREA, 98, 1, false);
    private final Field f179_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f180_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f181_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f182_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f183_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f186_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f207_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f208_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f210_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);
    private String f40_EXIT_BROWSE_LOOP;  // EXIT-BROWSE-LOOP PIC X
    private String f69_RETURNED_EYE_CATCHER;  // RETURNED-EYE-CATCHER PIC X(4)
    private BigDecimal f70_RETURNED_CUST_NO;  // RETURNED-CUST-NO PIC 9(10) DISPLAY
    private BigDecimal f72_RETURNED_SORT_CODE;  // RETURNED-SORT-CODE PIC 9(6) DISPLAY
    private BigDecimal f73_RETURNED_NUMBER;  // RETURNED-NUMBER PIC 9(8) DISPLAY
    private String f74_RETURNED_TYPE;  // RETURNED-TYPE PIC X(8)
    private BigDecimal f75_RETURNED_INTEREST_RATE;  // RETURNED-INTEREST-RATE PIC 9(4)V99 DISPLAY
    private BigDecimal f76_RETURNED_OPENED;  // RETURNED-OPENED PIC 9(8) DISPLAY
    private BigDecimal f77_RETURNED_OVERDRAFT_LIMIT;  // RETURNED-OVERDRAFT-LIMIT PIC 9(8) DISPLAY
    private BigDecimal f78_RETURNED_LAST_STMT_DATE;  // RETURNED-LAST-STMT-DATE PIC 9(8) DISPLAY
    private BigDecimal f79_RETURNED_NEXT_STMT_DATE;  // RETURNED-NEXT-STMT-DATE PIC 9(8) DISPLAY
    private BigDecimal f80_RETURNED_AVAILABLE_BALANCE;  // RETURNED-AVAILABLE-BALANCE PIC S9(10)V99 DISPLAY
    private BigDecimal f81_RETURNED_ACTUAL_BALANCE;  // RETURNED-ACTUAL-BALANCE PIC S9(10)V99 DISPLAY
    private long f82_DESIRED_KEY;  // DESIRED-KEY PIC 9(10) BINARY
    private String f89_DATA_STORE_TYPE;  // DATA-STORE-TYPE PIC X
    private String f90_DB2_EXIT_LOOP;  // DB2-EXIT-LOOP PIC X
    private long f91_FETCH_DATA_CNT;  // FETCH-DATA-CNT PIC 9(4) BINARY
    private long f92_WS_CUST_ALT_KEY_LEN;  // WS-CUST-ALT-KEY-LEN PIC S9(4) BINARY
    private BigDecimal f95_REQUIRED_ACC_NUM;  // REQUIRED-ACC-NUM PIC 9(8) DISPLAY
    private String f97_WS_STORM_DRAIN;  // WS-STORM-DRAIN PIC X
    private String f98_STORM_DRAIN_CONDITION;  // STORM-DRAIN-CONDITION PIC X(20)
    private long f105_NCS_ACC_NO_INC;  // NCS-ACC-NO-INC PIC 9(16) BINARY
    private String f107_NCS_ACC_NO_RESP;  // NCS-ACC-NO-RESP PIC XX
    private BigDecimal f108_WS_DISP_ACC_NO_VAL;  // WS-DISP-ACC-NO-VAL PIC S9(18) DISPLAY
    private BigDecimal f110_REQUIRED_SORT_CODE2;  // REQUIRED-SORT-CODE2 PIC 9(6) DISPLAY
    private BigDecimal f115_WS_POINTER_NUMBER_DISPLAY;  // WS-POINTER-NUMBER-DISPLAY PIC 9(8) DISPLAY
    private String f125_WS_ORIG_DATE_DD_X;  // WS-ORIG-DATE-DD-X PIC XX
    private String f127_WS_ORIG_DATE_MM_X;  // WS-ORIG-DATE-MM-X PIC XX
    private String f129_WS_ORIG_DATE_YYYY_X;  // WS-ORIG-DATE-YYYY-X PIC X(4)
    private String f136_WS_ABEND_PGM;  // WS-ABEND-PGM PIC X(8)

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
            java.util.Map.entry("PTD999", 26),
            java.util.Map.entry("PTD010", 25),
            java.util.Map.entry("POPULATE-TIME-DATE", 24),
            java.util.Map.entry("GLAD999", 23),
            java.util.Map.entry("GLAD010", 22),
            java.util.Map.entry("GET-LAST-ACCOUNT-DB2", 21),
            java.util.Map.entry("RAN999", 20),
            java.util.Map.entry("RAN010", 19),
            java.util.Map.entry("READ-ACCOUNT-LAST", 18),
            java.util.Map.entry("AH999", 17),
            java.util.Map.entry("AH010", 16),
            java.util.Map.entry("ABEND-HANDLING", 15),
            java.util.Map.entry("CFSDCD999", 14),
            java.util.Map.entry("CFSDCD010", 13),
            java.util.Map.entry("CHECK-FOR-STORM-DRAIN-DB2", 12),
            java.util.Map.entry("GMOFH999", 11),
            java.util.Map.entry("GMOFH010", 10),
            java.util.Map.entry("GET-ME-OUT-OF-HERE", 9),
            java.util.Map.entry("FD999", 8),
            java.util.Map.entry("FD010", 7),
            java.util.Map.entry("FETCH-DATA", 6),
            java.util.Map.entry("RAD999", 5),
            java.util.Map.entry("RAD010", 4),
            java.util.Map.entry("READ-ACCOUNT-DB2", 3),
            java.util.Map.entry("A999", 2),
            java.util.Map.entry("A010", 1),
            java.util.Map.entry("PREMIERE", 0)
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

    private void in_AbndprocDfhcommarea(AbndprocDfhcommarea d, Storage s, int base) {
        if (d == null) {
            return;
        }
        Cobol.move(d.getAbndUtimeKey() == null ? BigDecimal.ZERO : new BigDecimal(d.getAbndUtimeKey().toString()), Field.packed(s, base + 0, 15, 0, true), CS);
        Cobol.move(d.getAbndTasknoKey() == null ? BigDecimal.ZERO : new BigDecimal(d.getAbndTasknoKey().toString()), Field.zoned(s, base + 8, 4, 0, false, false, false), CS);
        Cobol.move(d.getAbndApplid() == null ? "" : d.getAbndApplid(), Field.alphanumeric(s, base + 12, 8, false), CS);
        Cobol.move(d.getAbndTranid() == null ? "" : d.getAbndTranid(), Field.alphanumeric(s, base + 20, 4, false), CS);
        Cobol.move(d.getAbndDate() == null ? "" : d.getAbndDate(), Field.alphanumeric(s, base + 24, 10, false), CS);
        Cobol.move(d.getAbndTime() == null ? "" : d.getAbndTime(), Field.alphanumeric(s, base + 34, 8, false), CS);
        Cobol.move(d.getAbndCode() == null ? "" : d.getAbndCode(), Field.alphanumeric(s, base + 42, 4, false), CS);
        Cobol.move(d.getAbndProgram() == null ? "" : d.getAbndProgram(), Field.alphanumeric(s, base + 46, 8, false), CS);
        Cobol.move(d.getAbndRespcode() == null ? BigDecimal.ZERO : new BigDecimal(d.getAbndRespcode().toString()), Field.zoned(s, base + 54, 8, 0, true, true, true), CS);
        Cobol.move(d.getAbndResp2Code() == null ? BigDecimal.ZERO : new BigDecimal(d.getAbndResp2Code().toString()), Field.zoned(s, base + 63, 8, 0, true, true, true), CS);
        Cobol.move(d.getAbndSqlcode() == null ? BigDecimal.ZERO : new BigDecimal(d.getAbndSqlcode().toString()), Field.zoned(s, base + 72, 8, 0, true, true, true), CS);
        Cobol.move(d.getAbndFreeform() == null ? "" : d.getAbndFreeform(), Field.alphanumeric(s, base + 81, 600, false), CS);
    }

    private void fill_AbndprocDfhcommarea(AbndprocDfhcommarea d, Storage s, int base) {
        d.setAbndUtimeKey(Cobol.num(Field.packed(s, base + 0, 15, 0, true), CS).longValue());
        d.setAbndTasknoKey(Cobol.num(Field.zoned(s, base + 8, 4, 0, false, false, false), CS).intValue());
        d.setAbndApplid(Cobol.text(Field.alphanumeric(s, base + 12, 8, false), CS));
        d.setAbndTranid(Cobol.text(Field.alphanumeric(s, base + 20, 4, false), CS));
        d.setAbndDate(Cobol.text(Field.alphanumeric(s, base + 24, 10, false), CS));
        d.setAbndTime(Cobol.text(Field.alphanumeric(s, base + 34, 8, false), CS));
        d.setAbndCode(Cobol.text(Field.alphanumeric(s, base + 42, 4, false), CS));
        d.setAbndProgram(Cobol.text(Field.alphanumeric(s, base + 46, 8, false), CS));
        d.setAbndRespcode(Cobol.num(Field.zoned(s, base + 54, 8, 0, true, true, true), CS).intValue());
        d.setAbndResp2Code(Cobol.num(Field.zoned(s, base + 63, 8, 0, true, true, true), CS).intValue());
        d.setAbndSqlcode(Cobol.num(Field.zoned(s, base + 72, 8, 0, true, true, true), CS).intValue());
        d.setAbndFreeform(Cobol.text(Field.alphanumeric(s, base + 81, 600, false), CS));
    }

    private AbndprocDfhcommarea out_AbndprocDfhcommarea(Storage s, int base) {
        AbndprocDfhcommarea d = new AbndprocDfhcommarea();
        fill_AbndprocDfhcommarea(d, s, base);
        return d;
    }

    private void in_InqaccDfhcommarea(InqaccDfhcommarea d, Storage s, int base) {
        if (d == null) {
            return;
        }
        Cobol.move(d.getInqaccEye() == null ? "" : d.getInqaccEye(), Field.alphanumeric(s, base + 0, 4, false), CS);
        Cobol.move(d.getInqaccCustno() == null ? BigDecimal.ZERO : new BigDecimal(d.getInqaccCustno().toString()), Field.zoned(s, base + 4, 10, 0, false, false, false), CS);
        Cobol.move(d.getInqaccScode() == null ? BigDecimal.ZERO : new BigDecimal(d.getInqaccScode().toString()), Field.zoned(s, base + 14, 6, 0, false, false, false), CS);
        Cobol.move(d.getInqaccAccno() == null ? BigDecimal.ZERO : new BigDecimal(d.getInqaccAccno().toString()), Field.zoned(s, base + 20, 8, 0, false, false, false), CS);
        Cobol.move(d.getInqaccAccType() == null ? "" : d.getInqaccAccType(), Field.alphanumeric(s, base + 28, 8, false), CS);
        Cobol.move(d.getInqaccIntRate() == null ? BigDecimal.ZERO : new BigDecimal(d.getInqaccIntRate().toString()), Field.zoned(s, base + 36, 6, 2, false, false, false), CS);
        Cobol.move(d.getInqaccOpened() == null ? BigDecimal.ZERO : new BigDecimal(d.getInqaccOpened().toString()), Field.zoned(s, base + 42, 8, 0, false, false, false), CS);
        Cobol.move(d.getInqaccOverdraft() == null ? BigDecimal.ZERO : new BigDecimal(d.getInqaccOverdraft().toString()), Field.zoned(s, base + 50, 8, 0, false, false, false), CS);
        Cobol.move(d.getInqaccLastStmtDt() == null ? BigDecimal.ZERO : new BigDecimal(d.getInqaccLastStmtDt().toString()), Field.zoned(s, base + 58, 8, 0, false, false, false), CS);
        Cobol.move(d.getInqaccNextStmtDt() == null ? BigDecimal.ZERO : new BigDecimal(d.getInqaccNextStmtDt().toString()), Field.zoned(s, base + 66, 8, 0, false, false, false), CS);
        Cobol.move(d.getInqaccAvailBal() == null ? BigDecimal.ZERO : new BigDecimal(d.getInqaccAvailBal().toString()), Field.zoned(s, base + 74, 12, 2, true, false, false), CS);
        Cobol.move(d.getInqaccActualBal() == null ? BigDecimal.ZERO : new BigDecimal(d.getInqaccActualBal().toString()), Field.zoned(s, base + 86, 12, 2, true, false, false), CS);
        Cobol.move(d.getInqaccSuccess() == null ? "" : d.getInqaccSuccess(), Field.alphanumeric(s, base + 98, 1, false), CS);
        DetCics.pointerIn(d.getInqaccPcb1Pointer(), s, base + 99, 8);
    }

    private void fill_InqaccDfhcommarea(InqaccDfhcommarea d, Storage s, int base) {
        d.setInqaccEye(Cobol.text(Field.alphanumeric(s, base + 0, 4, false), CS));
        d.setInqaccCustno(Cobol.num(Field.zoned(s, base + 4, 10, 0, false, false, false), CS).longValue());
        d.setInqaccScode(Cobol.num(Field.zoned(s, base + 14, 6, 0, false, false, false), CS).intValue());
        d.setInqaccAccno(Cobol.num(Field.zoned(s, base + 20, 8, 0, false, false, false), CS).intValue());
        d.setInqaccAccType(Cobol.text(Field.alphanumeric(s, base + 28, 8, false), CS));
        d.setInqaccIntRate(Cobol.num(Field.zoned(s, base + 36, 6, 2, false, false, false), CS));
        d.setInqaccOpened(Cobol.num(Field.zoned(s, base + 42, 8, 0, false, false, false), CS).intValue());
        d.setInqaccOverdraft(Cobol.num(Field.zoned(s, base + 50, 8, 0, false, false, false), CS).intValue());
        d.setInqaccLastStmtDt(Cobol.num(Field.zoned(s, base + 58, 8, 0, false, false, false), CS).intValue());
        d.setInqaccNextStmtDt(Cobol.num(Field.zoned(s, base + 66, 8, 0, false, false, false), CS).intValue());
        d.setInqaccAvailBal(Cobol.num(Field.zoned(s, base + 74, 12, 2, true, false, false), CS));
        d.setInqaccActualBal(Cobol.num(Field.zoned(s, base + 86, 12, 2, true, false, false), CS));
        d.setInqaccSuccess(Cobol.text(Field.alphanumeric(s, base + 98, 1, false), CS));
        d.setInqaccPcb1Pointer(DetCics.pointerOut(s, base + 99, 8));
    }

    private InqaccDfhcommarea out_InqaccDfhcommarea(Storage s, int base) {
        InqaccDfhcommarea d = new InqaccDfhcommarea();
        fill_InqaccDfhcommarea(d, s, base);
        return d;
    }

    /** #4270 (X23): DFHCOMMAREA's whole record again, with what the task left in its EIBCALEN bytes. */
    private void caWhole(byte[] whole) {
        if (s_DFHCOMMAREA.bytes != whole) {
            System.arraycopy(s_DFHCOMMAREA.bytes, 0, whole, 0, s_DFHCOMMAREA.bytes.length);
            s_DFHCOMMAREA.bytes = whole;
        }
    }


    private final AccountRepository accountRepository;
    private final DatasetResolver datasets;
    private final CobolFiles files;
    private final MainframeClock clock;

    public InqaccService(AccountRepository accountRepository, DatasetResolver datasets, CobolFiles files, MainframeClock clock) {
        this.accountRepository = accountRepository;
        this.datasets = datasets;
        this.files = files;
        this.clock = clock;
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_SORTCODE, 0, s_SORTCODE.bytes, 0, IMAGE_s_SORTCODE.length);
        System.arraycopy(IMAGE_s_HOST_ACCOUNT_ROW, 0, s_HOST_ACCOUNT_ROW.bytes, 0, IMAGE_s_HOST_ACCOUNT_ROW.length);
        System.arraycopy(IMAGE_s_SQLCA, 0, s_SQLCA.bytes, 0, IMAGE_s_SQLCA.length);
        System.arraycopy(IMAGE_s_WS_CICS_WORK_AREA, 0, s_WS_CICS_WORK_AREA.bytes, 0, IMAGE_s_WS_CICS_WORK_AREA.length);
        System.arraycopy(IMAGE_s_OUTPUT_DATA, 0, s_OUTPUT_DATA.bytes, 0, IMAGE_s_OUTPUT_DATA.length);
        System.arraycopy(IMAGE_s_RETURNED_DATA, 0, s_RETURNED_DATA.bytes, 0, IMAGE_s_RETURNED_DATA.length);
        System.arraycopy(IMAGE_s_DB2_DATE_REFORMAT, 0, s_DB2_DATE_REFORMAT.bytes, 0, IMAGE_s_DB2_DATE_REFORMAT.length);
        System.arraycopy(IMAGE_s_ACCOUNT_KY, 0, s_ACCOUNT_KY.bytes, 0, IMAGE_s_ACCOUNT_KY.length);
        System.arraycopy(IMAGE_s_MY_ABEND_CODE, 0, s_MY_ABEND_CODE.bytes, 0, IMAGE_s_MY_ABEND_CODE.length);
        System.arraycopy(IMAGE_s_SQLCODE_DISPLAY, 0, s_SQLCODE_DISPLAY.bytes, 0, IMAGE_s_SQLCODE_DISPLAY.length);
        System.arraycopy(IMAGE_s_NCS_ACC_NO_STUFF, 0, s_NCS_ACC_NO_STUFF.bytes, 0, IMAGE_s_NCS_ACC_NO_STUFF.length);
        System.arraycopy(IMAGE_s_ACCOUNT_KY2, 0, s_ACCOUNT_KY2.bytes, 0, IMAGE_s_ACCOUNT_KY2.length);
        System.arraycopy(IMAGE_s_WS_POINTER, 0, s_WS_POINTER.bytes, 0, IMAGE_s_WS_POINTER.length);
        System.arraycopy(IMAGE_s_WS_U_TIME, 0, s_WS_U_TIME.bytes, 0, IMAGE_s_WS_U_TIME.length);
        System.arraycopy(IMAGE_s_WS_ORIG_DATE, 0, s_WS_ORIG_DATE.bytes, 0, IMAGE_s_WS_ORIG_DATE.length);
        System.arraycopy(IMAGE_s_WS_ORIG_DATE_GRP_X, 0, s_WS_ORIG_DATE_GRP_X.bytes, 0, IMAGE_s_WS_ORIG_DATE_GRP_X.length);
        System.arraycopy(IMAGE_s_WS_TIME_DATA, 0, s_WS_TIME_DATA.bytes, 0, IMAGE_s_WS_TIME_DATA.length);
        System.arraycopy(IMAGE_s_ABNDINFO_REC, 0, s_ABNDINFO_REC.bytes, 0, IMAGE_s_ABNDINFO_REC.length);
        System.arraycopy(IMAGE_s_DFHCOMMAREA, 0, s_DFHCOMMAREA.bytes, 0, IMAGE_s_DFHCOMMAREA.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
        f40_EXIT_BROWSE_LOOP = "N";
        f69_RETURNED_EYE_CATCHER = "    ";
        f70_RETURNED_CUST_NO = new BigDecimal("0");
        f72_RETURNED_SORT_CODE = new BigDecimal("0");
        f73_RETURNED_NUMBER = new BigDecimal("0");
        f74_RETURNED_TYPE = "        ";
        f75_RETURNED_INTEREST_RATE = new BigDecimal("0");
        f76_RETURNED_OPENED = new BigDecimal("0");
        f77_RETURNED_OVERDRAFT_LIMIT = new BigDecimal("0");
        f78_RETURNED_LAST_STMT_DATE = new BigDecimal("0");
        f79_RETURNED_NEXT_STMT_DATE = new BigDecimal("0");
        f80_RETURNED_AVAILABLE_BALANCE = new BigDecimal("0");
        f81_RETURNED_ACTUAL_BALANCE = new BigDecimal("0");
        f82_DESIRED_KEY = 0L;
        f89_DATA_STORE_TYPE = " ";
        f90_DB2_EXIT_LOOP = " ";
        f91_FETCH_DATA_CNT = 0L;
        f92_WS_CUST_ALT_KEY_LEN = 10L;
        f95_REQUIRED_ACC_NUM = new BigDecimal("0");
        f97_WS_STORM_DRAIN = "N";
        f98_STORM_DRAIN_CONDITION = "                    ";
        f105_NCS_ACC_NO_INC = 0L;
        f107_NCS_ACC_NO_RESP = "00";
        f108_WS_DISP_ACC_NO_VAL = new BigDecimal("0");
        f110_REQUIRED_SORT_CODE2 = new BigDecimal("0");
        f115_WS_POINTER_NUMBER_DISPLAY = new BigDecimal("0");
        f125_WS_ORIG_DATE_DD_X = "  ";
        f127_WS_ORIG_DATE_MM_X = "  ";
        f129_WS_ORIG_DATE_YYYY_X = "    ";
        f136_WS_ABEND_PGM = "ABNDPROC";
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 26);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f210_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f181_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f183_EIBTRMID, CS);
            Cobol.store(f182_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f180_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f179_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (ca instanceof InqaccDfhcommarea x) {
                in_InqaccDfhcommarea(x, s_DFHCOMMAREA, 0);
                caBack = () -> fill_InqaccDfhcommarea(x, s_DFHCOMMAREA, 0);
                calen = cx(task, 103);
            } else if (ca instanceof AbndprocDfhcommarea x) {
                in_AbndprocDfhcommarea(x, s_DFHCOMMAREA, 0);
                caBack = () -> fill_AbndprocDfhcommarea(x, s_DFHCOMMAREA, 0);
                calen = cx(task, 681);
            }
            byte[] raw = task.linkArea();
            if (raw != null) {
                System.arraycopy(raw, 0, s_DFHCOMMAREA.bytes, 0, Math.min(raw.length, s_DFHCOMMAREA.bytes.length));
                Runnable typed = caBack;
                caBack = () -> { typed.run(); System.arraycopy(s_DFHCOMMAREA.bytes, 0, raw, 0, Math.min(raw.length, s_DFHCOMMAREA.bytes.length)); };
            }
            byte[] caWhole = null;
            if (task.exactCommarea() && calen < s_DFHCOMMAREA.bytes.length) {
                caWhole = s_DFHCOMMAREA.bytes;
                s_DFHCOMMAREA.bytes = java.util.Arrays.copyOf(caWhole, calen);
                Runnable typed = caBack;
                byte[] whole = caWhole;
                caBack = () -> { caWhole(whole); typed.run(); };
            }
            Cobol.store(f186_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                try {
                    perform(0, 26);
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

    public InqaccDfhcommarea handleLink(InqaccDfhcommarea request) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("INQACC", request);
        region.run(task, "INQACC", this::runTask);
        return request;
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
            byte[] parmText = (parm == null ? "" : parm).getBytes(CS);
            s_DFHCOMMAREA.bytes[0] = (byte) (parmText.length >> 8);
            s_DFHCOMMAREA.bytes[1] = (byte) parmText.length;
            System.arraycopy(parmText, 0, s_DFHCOMMAREA.bytes, 2, Math.min(parmText.length, s_DFHCOMMAREA.bytes.length - 2));
            try {
                perform(0, 26);
            } catch (Goback g) {
                // the program ended
            }
            return Cobol.num(f210_GG_RETURN_CODE, CS).intValue();
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
                if (next >= 27) {
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
            case 14: return p14();
            case 15: return p15();
            case 16: return p16();
            case 17: return p17();
            case 18: return p18();
            case 19: return p19();
            case 20: return p20();
            case 21: return p21();
            case 22: return p22();
            case 23: return p23();
            case 24: return p24();
            case 25: return p25();
            case 26: return p26();
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** PREMIERE. */
    private int p0() {

        return 1;
    }

    /** A010. */
    private int p1() {
        // INITIALIZE OUTPUT-DATA
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 0, 4, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 4, 10, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 14, 6, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 20, 8, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 28, 8, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 36, 6, 2, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 42, 8, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 50, 8, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 58, 8, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 66, 8, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 74, 12, 2, true, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 86, 12, 2, true, false, false), CS);
        // EXEC CICS HANDLE ABEND LABEL(ABEND-HANDLING) END-EXEC
        task.handleAbend("ABEND-HANDLING");
        // MOVE SORTCODE TO REQUIRED-SORT-CODE OF ACCOUNT-KY
        Cobol.move(f1_SORTCODE, f94_REQUIRED_SORT_CODE, CS);
        // IF INQACC-ACCNO = 99999999
        if (Cobol.num(f155_INQACC_ACCNO, CS).compareTo(D99999999) == 0) {
            // PERFORM READ-ACCOUNT-LAST
            perform(18, 20);
        } else {
            // PERFORM READ-ACCOUNT-DB2
            perform(3, 5);
        }
        // IF ACCOUNT-TYPE = SPACES OR LOW-VALUES
        if ((Cobol.compareFigurative(f48_ACCOUNT_TYPE, Figurative.SPACES, CS) == 0 || Cobol.compareFigurative(f48_ACCOUNT_TYPE, Figurative.LOW_VALUES, CS) == 0)) {
            // MOVE 'N' TO INQACC-SUCCESS
            Cobol.move("N", f176_INQACC_SUCCESS, CS);
        } else {
            // MOVE ACCOUNT-EYE-CATCHER TO INQACC-EYE
            Cobol.move(f43_ACCOUNT_EYE_CATCHER, f152_INQACC_EYE, CS);
            // MOVE ACCOUNT-CUST-NO TO INQACC-CUSTNO
            Cobol.move(f44_ACCOUNT_CUST_NO, f153_INQACC_CUSTNO, CS);
            // MOVE ACCOUNT-SORT-CODE TO INQACC-SCODE
            Cobol.move(f46_ACCOUNT_SORT_CODE, f154_INQACC_SCODE, CS);
            // MOVE ACCOUNT-NUMBER TO INQACC-ACCNO
            Cobol.move(f47_ACCOUNT_NUMBER, f155_INQACC_ACCNO, CS);
            // MOVE ACCOUNT-TYPE TO INQACC-ACC-TYPE
            Cobol.move(f48_ACCOUNT_TYPE, f156_INQACC_ACC_TYPE, CS);
            // MOVE ACCOUNT-INTEREST-RATE TO INQACC-INT-RATE
            Cobol.move(f49_ACCOUNT_INTEREST_RATE, f157_INQACC_INT_RATE, CS);
            // MOVE ACCOUNT-OPENED TO INQACC-OPENED
            Cobol.move(f50_ACCOUNT_OPENED, f158_INQACC_OPENED, CS);
            // MOVE ACCOUNT-OVERDRAFT-LIMIT TO INQACC-OVERDRAFT
            Cobol.move(f55_ACCOUNT_OVERDRAFT_LIMIT, f163_INQACC_OVERDRAFT, CS);
            // MOVE ACCOUNT-LAST-STMT-DATE TO INQACC-LAST-STMT-DT
            Cobol.move(f56_ACCOUNT_LAST_STMT_DATE, f164_INQACC_LAST_STMT_DT, CS);
            // MOVE ACCOUNT-NEXT-STMT-DATE TO INQACC-NEXT-STMT-DT
            Cobol.move(f61_ACCOUNT_NEXT_STMT_DATE, f169_INQACC_NEXT_STMT_DT, CS);
            // MOVE ACCOUNT-AVAILABLE-BALANCE TO INQACC-AVAIL-BAL
            Cobol.move(f66_ACCOUNT_AVAILABLE_BALANCE, f174_INQACC_AVAIL_BAL, CS);
            // MOVE ACCOUNT-ACTUAL-BALANCE TO INQACC-ACTUAL-BAL
            Cobol.move(f67_ACCOUNT_ACTUAL_BALANCE, f175_INQACC_ACTUAL_BAL, CS);
            // MOVE 'Y' TO INQACC-SUCCESS
            Cobol.move("Y", f176_INQACC_SUCCESS, CS);
        }
        // PERFORM GET-ME-OUT-OF-HERE
        perform(9, 11);
        return 2;
    }

    /** A999. */
    private int p2() {
        // EXIT
        return 3;
    }

    /** READ-ACCOUNT-DB2. */
    private int p3() {

        return 4;
    }

    /** RAD010. */
    private int p4() {
        // MOVE INQACC-ACCNO TO HV-ACCOUNT-ACC-NO
        Cobol.move(f155_INQACC_ACCNO, f6_HV_ACCOUNT_ACC_NO, CS);
        // MOVE SORTCODE TO HV-ACCOUNT-SORTCODE
        Cobol.move(f1_SORTCODE, f5_HV_ACCOUNT_SORTCODE, CS);
        // EXEC SQL OPEN ACC-CURSOR END-EXEC
        java.util.Map<String, Object> sqlParams1 = new java.util.HashMap<>();
        sqlParams1.put("hvAccountAccNo", DetSql.charIn(f6_HV_ACCOUNT_ACC_NO, CS));
        sqlParams1.put("hvAccountSortcode", DetSql.charIn(f5_HV_ACCOUNT_SORTCODE, CS));
        DetSql.open(f15_SQLCA, "INQACC:270", "ACC-CURSOR", () -> accountRepository.cursorAccCursorL66Inqacc(sqlParams1), CS);
        // IF SQLCODE NOT = 0
        if (!(Cobol.num(f18_SQLCODE, CS).compareTo(D0) == 0)) {
            // MOVE SQLCODE TO SQLCODE-DISPLAY
            Cobol.move(f18_SQLCODE, f99_SQLCODE_DISPLAY, CS);
            // INITIALIZE ABNDINFO-REC
            Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 0, 15, 0, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 8, 4, 0, false, false, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 12, 8, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 20, 4, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 24, 10, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 34, 8, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 42, 4, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 46, 8, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 54, 8, 0, true, true, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 63, 8, 0, true, true, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 72, 8, 0, true, true, true), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 81, 600, false), CS);
            // MOVE EIBRESP TO ABND-RESPCODE
            Cobol.move(f207_EIBRESP, f147_ABND_RESPCODE, CS);
            // MOVE EIBRESP2 TO ABND-RESP2CODE
            Cobol.move(f208_EIBRESP2, f148_ABND_RESP2CODE, CS);
            // EXEC CICS ASSIGN APPLID(ABND-APPLID) END-EXEC
            DetCics.putText(f141_ABND_APPLID, task.assignApplid(), CS);
            // MOVE EIBTASKN TO ABND-TASKNO-KEY
            Cobol.move(f182_EIBTASKN, f140_ABND_TASKNO_KEY, CS);
            // MOVE EIBTRNID TO ABND-TRANID
            Cobol.move(f181_EIBTRNID, f142_ABND_TRANID, CS);
            // PERFORM POPULATE-TIME-DATE
            perform(24, 26);
            // MOVE WS-ORIG-DATE TO ABND-DATE
            Cobol.move(f117_WS_ORIG_DATE, f143_ABND_DATE, CS);
            // STRING WS-TIME-NOW-GRP-HH DELIMITED BY SIZE, ':' DELIMITED BY SIZE, WS-TIME-NOW-GRP-MM DELIMITED BY SIZE, ':' DELIMITED BY SIZE, WS-TIME-NOW-GRP-MM DE
            Cobol.string(f144_ABND_TIME, null, CS, Cobol.StringPart.size(f133_WS_TIME_NOW_GRP_HH), Cobol.StringPart.size(":", CS), Cobol.StringPart.size(f134_WS_TIME_NOW_GRP_MM), Cobol.StringPart.size(":", CS), Cobol.StringPart.size(f134_WS_TIME_NOW_GRP_MM));
            // MOVE WS-U-TIME TO ABND-UTIME-KEY
            Cobol.move(f116_WS_U_TIME, f139_ABND_UTIME_KEY, CS);
            // MOVE 'HRAC' TO ABND-CODE
            Cobol.move("HRAC", f145_ABND_CODE, CS);
            // EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM) END-EXEC
            DetCics.putText(f146_ABND_PROGRAM, "INQACC  ", CS);
            // MOVE SQLCODE-DISPLAY TO ABND-SQLCODE
            Cobol.move(f99_SQLCODE_DISPLAY, f149_ABND_SQLCODE, CS);
            // STRING 'RAD010 -Failure when attempting to OPEN DB2 ' DELIMITED BY SIZE, 'CURSOR. Check SQLCODE. ' DELIMITED BY SIZE, 'SQLCODE=' DELIMITED BY SIZE, SQ
            Cobol.string(f150_ABND_FREEFORM, null, CS, Cobol.StringPart.size("RAD010 -Failure when attempting to OPEN DB2 ", CS), Cobol.StringPart.size("CURSOR. Check SQLCODE. ", CS), Cobol.StringPart.size("SQLCODE=", CS), Cobol.StringPart.size(f99_SQLCODE_DISPLAY));
            // EXEC CICS LINK PROGRAM(WS-ABEND-PGM) COMMAREA(ABNDINFO-REC) END-EXEC
            Storage cw4 = Cobol.commarea(f137_ABNDINFO_REC, 681);
            AbndprocDfhcommarea ca3 = out_AbndprocDfhcommarea(cw4, 0);
            String lr2 = task.link(f136_WS_ABEND_PGM.strip(), ca3, 681, cw4.bytes);
            if ("NORMAL".equals(lr2)) { in_AbndprocDfhcommarea(ca3, cw4, 0); Cobol.commareaBack(cw4, f137_ABNDINFO_REC); }
            String exit5 = task.abendExit();
            if (exit5 != null) return GOTO | paragraph(exit5);
            if (task.ended()) throw abended();
            Cobol.store(f207_EIBRESP, BigDecimal.valueOf(DetCics.resp(lr2)), false, CS);
            Cobol.store(f208_EIBRESP2, BigDecimal.valueOf(0), false, CS);
            if (DetCics.resp(lr2) != 0) {
                int to = condition(DetCics.condition(DetCics.resp(lr2)));
                if (to >= 0) return GOTO | to;
            }
            // DISPLAY 'Failure when attempting to open DB2 CURSOR ' 'ACC-CURSOR. With SQL code=' SQLCODE-DISPLAY
            Sysout.display("Failure when attempting to open DB2 CURSOR ", "ACC-CURSOR. With SQL code=", Cobol.displayText(f99_SQLCODE_DISPLAY, CS));
            // PERFORM CHECK-FOR-STORM-DRAIN-DB2
            perform(12, 14);
            // EXEC CICS ABEND ABCODE('HRAC') CANCEL NODUMP END-EXEC
            String exit6 = task.abendCancel("HRAC".strip());
            if (exit6 == null) throw abended();
            if (true) return GOTO | paragraph(exit6);
        }
        // PERFORM FETCH-DATA
        perform(6, 8);
        // EXEC SQL CLOSE ACC-CURSOR END-EXEC
        DetSql.close(f15_SQLCA, "INQACC:350", "ACC-CURSOR", CS);
        // IF SQLCODE NOT = 0
        if (!(Cobol.num(f18_SQLCODE, CS).compareTo(D0) == 0)) {
            // MOVE SQLCODE TO SQLCODE-DISPLAY
            Cobol.move(f18_SQLCODE, f99_SQLCODE_DISPLAY, CS);
            // INITIALIZE ABNDINFO-REC
            Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 0, 15, 0, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 8, 4, 0, false, false, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 12, 8, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 20, 4, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 24, 10, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 34, 8, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 42, 4, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 46, 8, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 54, 8, 0, true, true, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 63, 8, 0, true, true, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 72, 8, 0, true, true, true), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 81, 600, false), CS);
            // MOVE EIBRESP TO ABND-RESPCODE
            Cobol.move(f207_EIBRESP, f147_ABND_RESPCODE, CS);
            // MOVE EIBRESP2 TO ABND-RESP2CODE
            Cobol.move(f208_EIBRESP2, f148_ABND_RESP2CODE, CS);
            // EXEC CICS ASSIGN APPLID(ABND-APPLID) END-EXEC
            DetCics.putText(f141_ABND_APPLID, task.assignApplid(), CS);
            // MOVE EIBTASKN TO ABND-TASKNO-KEY
            Cobol.move(f182_EIBTASKN, f140_ABND_TASKNO_KEY, CS);
            // MOVE EIBTRNID TO ABND-TRANID
            Cobol.move(f181_EIBTRNID, f142_ABND_TRANID, CS);
            // PERFORM POPULATE-TIME-DATE
            perform(24, 26);
            // MOVE WS-ORIG-DATE TO ABND-DATE
            Cobol.move(f117_WS_ORIG_DATE, f143_ABND_DATE, CS);
            // STRING WS-TIME-NOW-GRP-HH DELIMITED BY SIZE, ':' DELIMITED BY SIZE, WS-TIME-NOW-GRP-MM DELIMITED BY SIZE, ':' DELIMITED BY SIZE, WS-TIME-NOW-GRP-MM DE
            Cobol.string(f144_ABND_TIME, null, CS, Cobol.StringPart.size(f133_WS_TIME_NOW_GRP_HH), Cobol.StringPart.size(":", CS), Cobol.StringPart.size(f134_WS_TIME_NOW_GRP_MM), Cobol.StringPart.size(":", CS), Cobol.StringPart.size(f134_WS_TIME_NOW_GRP_MM));
            // MOVE WS-U-TIME TO ABND-UTIME-KEY
            Cobol.move(f116_WS_U_TIME, f139_ABND_UTIME_KEY, CS);
            // MOVE 'HRAC' TO ABND-CODE
            Cobol.move("HRAC", f145_ABND_CODE, CS);
            // EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM) END-EXEC
            DetCics.putText(f146_ABND_PROGRAM, "INQACC  ", CS);
            // MOVE SQLCODE-DISPLAY TO ABND-SQLCODE
            Cobol.move(f99_SQLCODE_DISPLAY, f149_ABND_SQLCODE, CS);
            // STRING 'RAD010 -Failure when attempting to CLOSE DB2 ' DELIMITED BY SIZE, 'CURSOR (ACC-CUSOR). Check SQLCODE' DELIMITED BY SIZE, 'SQLCODE=' DELIMITED 
            Cobol.string(f150_ABND_FREEFORM, null, CS, Cobol.StringPart.size("RAD010 -Failure when attempting to CLOSE DB2 ", CS), Cobol.StringPart.size("CURSOR (ACC-CUSOR). Check SQLCODE", CS), Cobol.StringPart.size("SQLCODE=", CS), Cobol.StringPart.size(f99_SQLCODE_DISPLAY));
            // EXEC CICS LINK PROGRAM(WS-ABEND-PGM) COMMAREA(ABNDINFO-REC) END-EXEC
            Storage cw10 = Cobol.commarea(f137_ABNDINFO_REC, 681);
            AbndprocDfhcommarea ca9 = out_AbndprocDfhcommarea(cw10, 0);
            String lr8 = task.link(f136_WS_ABEND_PGM.strip(), ca9, 681, cw10.bytes);
            if ("NORMAL".equals(lr8)) { in_AbndprocDfhcommarea(ca9, cw10, 0); Cobol.commareaBack(cw10, f137_ABNDINFO_REC); }
            String exit11 = task.abendExit();
            if (exit11 != null) return GOTO | paragraph(exit11);
            if (task.ended()) throw abended();
            Cobol.store(f207_EIBRESP, BigDecimal.valueOf(DetCics.resp(lr8)), false, CS);
            Cobol.store(f208_EIBRESP2, BigDecimal.valueOf(0), false, CS);
            if (DetCics.resp(lr8) != 0) {
                int to = condition(DetCics.condition(DetCics.resp(lr8)));
                if (to >= 0) return GOTO | to;
            }
            // DISPLAY 'Failure when attempting to close the DB2 CURSOR' ' ACC-CURSOR. With SQL code=' SQLCODE-DISPLAY
            Sysout.display("Failure when attempting to close the DB2 CURSOR", " ACC-CURSOR. With SQL code=", Cobol.displayText(f99_SQLCODE_DISPLAY, CS));
            // PERFORM CHECK-FOR-STORM-DRAIN-DB2
            perform(12, 14);
            // EXEC CICS ABEND ABCODE('HRAC') CANCEL NODUMP END-EXEC
            String exit12 = task.abendCancel("HRAC".strip());
            if (exit12 == null) throw abended();
            if (true) return GOTO | paragraph(exit12);
        }
        return 5;
    }

    /** RAD999. */
    private int p5() {
        // EXIT
        return 6;
    }

    /** FETCH-DATA. */
    private int p6() {

        return 7;
    }

    /** FD010. */
    private int p7() {
        // EXEC SQL FETCH FROM ACC-CURSOR INTO :HV-ACCOUNT-EYECATCHER, :HV-ACCOUNT-CUST-NO, :HV-ACCOUNT-SORTCODE, :HV-ACCOUNT-ACC-NO, :HV-ACCOUNT-ACC-TYPE, :HV-A
        java.util.Map<String, Object> sqlRow14 = DetSql.fetch(f15_SQLCA, "INQACC:431", "ACC-CURSOR", CS);
        if (sqlRow14 != null) {
            DetSql.into(f15_SQLCA, sqlRow14, "XXXXXNXNXXNN", new Field[] {f3_HV_ACCOUNT_EYECATCHER, f4_HV_ACCOUNT_CUST_NO, f5_HV_ACCOUNT_SORTCODE, f6_HV_ACCOUNT_ACC_NO, f7_HV_ACCOUNT_ACC_TYPE, f8_HV_ACCOUNT_INT_RATE, f9_HV_ACCOUNT_OPENED, f10_HV_ACCOUNT_OVERDRAFT_LIM, f11_HV_ACCOUNT_LAST_STMT, f12_HV_ACCOUNT_NEXT_STMT, f13_HV_ACCOUNT_AVAIL_BAL, f14_HV_ACCOUNT_ACTUAL_BAL}, new Field[] {null, null, null, null, null, null, null, null, null, null, null, null}, null, CS);
        }
        // IF SQLCODE = +100
        if (Cobol.num(f18_SQLCODE, CS).compareTo(D100) == 0) {
            // INITIALIZE OUTPUT-DATA
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 0, 4, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 4, 10, 0, false, false, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 14, 6, 0, false, false, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 20, 8, 0, false, false, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 28, 8, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 36, 6, 2, false, false, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 42, 8, 0, false, false, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 50, 8, 0, false, false, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 58, 8, 0, false, false, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 66, 8, 0, false, false, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 74, 12, 2, true, false, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 86, 12, 2, true, false, false), CS);
            // MOVE SORTCODE TO ACCOUNT-SORT-CODE OF OUTPUT-DATA
            Cobol.move(f1_SORTCODE, f46_ACCOUNT_SORT_CODE, CS);
            // MOVE INQACC-ACCNO TO ACCOUNT-NUMBER OF OUTPUT-DATA
            Cobol.move(f155_INQACC_ACCNO, f47_ACCOUNT_NUMBER, CS);
            // GO TO FD999
            if (true) return GOTO | 8;
        }
        // IF SQLCODE NOT = 0
        if (!(Cobol.num(f18_SQLCODE, CS).compareTo(D0) == 0)) {
            // PERFORM CHECK-FOR-STORM-DRAIN-DB2
            perform(12, 14);
            // MOVE SQLCODE TO SQLCODE-DISPLAY
            Cobol.move(f18_SQLCODE, f99_SQLCODE_DISPLAY, CS);
            // INITIALIZE ABNDINFO-REC
            Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 0, 15, 0, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 8, 4, 0, false, false, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 12, 8, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 20, 4, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 24, 10, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 34, 8, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 42, 4, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 46, 8, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 54, 8, 0, true, true, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 63, 8, 0, true, true, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 72, 8, 0, true, true, true), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 81, 600, false), CS);
            // MOVE EIBRESP TO ABND-RESPCODE
            Cobol.move(f207_EIBRESP, f147_ABND_RESPCODE, CS);
            // MOVE EIBRESP2 TO ABND-RESP2CODE
            Cobol.move(f208_EIBRESP2, f148_ABND_RESP2CODE, CS);
            // EXEC CICS ASSIGN APPLID(ABND-APPLID) END-EXEC
            DetCics.putText(f141_ABND_APPLID, task.assignApplid(), CS);
            // MOVE EIBTASKN TO ABND-TASKNO-KEY
            Cobol.move(f182_EIBTASKN, f140_ABND_TASKNO_KEY, CS);
            // MOVE EIBTRNID TO ABND-TRANID
            Cobol.move(f181_EIBTRNID, f142_ABND_TRANID, CS);
            // PERFORM POPULATE-TIME-DATE
            perform(24, 26);
            // MOVE WS-ORIG-DATE TO ABND-DATE
            Cobol.move(f117_WS_ORIG_DATE, f143_ABND_DATE, CS);
            // STRING WS-TIME-NOW-GRP-HH DELIMITED BY SIZE, ':' DELIMITED BY SIZE, WS-TIME-NOW-GRP-MM DELIMITED BY SIZE, ':' DELIMITED BY SIZE, WS-TIME-NOW-GRP-MM DE
            Cobol.string(f144_ABND_TIME, null, CS, Cobol.StringPart.size(f133_WS_TIME_NOW_GRP_HH), Cobol.StringPart.size(":", CS), Cobol.StringPart.size(f134_WS_TIME_NOW_GRP_MM), Cobol.StringPart.size(":", CS), Cobol.StringPart.size(f134_WS_TIME_NOW_GRP_MM));
            // MOVE WS-U-TIME TO ABND-UTIME-KEY
            Cobol.move(f116_WS_U_TIME, f139_ABND_UTIME_KEY, CS);
            // MOVE 'HRAC' TO ABND-CODE
            Cobol.move("HRAC", f145_ABND_CODE, CS);
            // EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM) END-EXEC
            DetCics.putText(f146_ABND_PROGRAM, "INQACC  ", CS);
            // MOVE SQLCODE-DISPLAY TO ABND-SQLCODE
            Cobol.move(f99_SQLCODE_DISPLAY, f149_ABND_SQLCODE, CS);
            // STRING 'FD010 -Failure when attempting to FETCH from ' DELIMITED BY SIZE, 'DB2 CURSOR (ACC-CURSOR). Check SQLCODE' DELIMITED BY SIZE, 'SQLCODE=' DELIM
            Cobol.string(f150_ABND_FREEFORM, null, CS, Cobol.StringPart.size("FD010 -Failure when attempting to FETCH from ", CS), Cobol.StringPart.size("DB2 CURSOR (ACC-CURSOR). Check SQLCODE", CS), Cobol.StringPart.size("SQLCODE=", CS), Cobol.StringPart.size(f99_SQLCODE_DISPLAY));
            // EXEC CICS LINK PROGRAM(WS-ABEND-PGM) COMMAREA(ABNDINFO-REC) END-EXEC
            Storage cw17 = Cobol.commarea(f137_ABNDINFO_REC, 681);
            AbndprocDfhcommarea ca16 = out_AbndprocDfhcommarea(cw17, 0);
            String lr15 = task.link(f136_WS_ABEND_PGM.strip(), ca16, 681, cw17.bytes);
            if ("NORMAL".equals(lr15)) { in_AbndprocDfhcommarea(ca16, cw17, 0); Cobol.commareaBack(cw17, f137_ABNDINFO_REC); }
            String exit18 = task.abendExit();
            if (exit18 != null) return GOTO | paragraph(exit18);
            if (task.ended()) throw abended();
            Cobol.store(f207_EIBRESP, BigDecimal.valueOf(DetCics.resp(lr15)), false, CS);
            Cobol.store(f208_EIBRESP2, BigDecimal.valueOf(0), false, CS);
            if (DetCics.resp(lr15) != 0) {
                int to = condition(DetCics.condition(DetCics.resp(lr15)));
                if (to >= 0) return GOTO | to;
            }
            // DISPLAY 'Failure when attempting to FETCH from the DB2 ' 'CURSOR ACC-CURSOR. With SQL code=' SQLCODE-DISPLAY
            Sysout.display("Failure when attempting to FETCH from the DB2 ", "CURSOR ACC-CURSOR. With SQL code=", Cobol.displayText(f99_SQLCODE_DISPLAY, CS));
            // EXEC CICS ABEND ABCODE('HRAC') CANCEL NODUMP END-EXEC
            String exit19 = task.abendCancel("HRAC".strip());
            if (exit19 == null) throw abended();
            if (true) return GOTO | paragraph(exit19);
        }
        // MOVE HV-ACCOUNT-EYECATCHER TO ACCOUNT-EYE-CATCHER OF OUTPUT-DATA
        Cobol.move(f3_HV_ACCOUNT_EYECATCHER, f43_ACCOUNT_EYE_CATCHER, CS);
        // MOVE HV-ACCOUNT-CUST-NO TO ACCOUNT-CUST-NO OF OUTPUT-DATA
        Cobol.move(f4_HV_ACCOUNT_CUST_NO, f44_ACCOUNT_CUST_NO, CS);
        // MOVE HV-ACCOUNT-SORTCODE TO ACCOUNT-SORT-CODE OF OUTPUT-DATA
        Cobol.move(f5_HV_ACCOUNT_SORTCODE, f46_ACCOUNT_SORT_CODE, CS);
        // MOVE HV-ACCOUNT-ACC-NO TO ACCOUNT-NUMBER OF OUTPUT-DATA
        Cobol.move(f6_HV_ACCOUNT_ACC_NO, f47_ACCOUNT_NUMBER, CS);
        // MOVE HV-ACCOUNT-ACC-TYPE TO ACCOUNT-TYPE OF OUTPUT-DATA
        Cobol.move(f7_HV_ACCOUNT_ACC_TYPE, f48_ACCOUNT_TYPE, CS);
        // MOVE HV-ACCOUNT-INT-RATE TO ACCOUNT-INTEREST-RATE OF OUTPUT-DATA
        Cobol.move(f8_HV_ACCOUNT_INT_RATE, f49_ACCOUNT_INTEREST_RATE, CS);
        // MOVE HV-ACCOUNT-OPENED TO DB2-DATE-REFORMAT
        Cobol.move(f9_HV_ACCOUNT_OPENED, f83_DB2_DATE_REFORMAT, CS);
        // MOVE DB2-DATE-REF-DAY TO ACCOUNT-OPENED-DAY OF OUTPUT-DATA
        Cobol.move(f88_DB2_DATE_REF_DAY, f52_ACCOUNT_OPENED_DAY, CS);
        // MOVE DB2-DATE-REF-MNTH TO ACCOUNT-OPENED-MONTH OF OUTPUT-DATA
        Cobol.move(f86_DB2_DATE_REF_MNTH, f53_ACCOUNT_OPENED_MONTH, CS);
        // MOVE DB2-DATE-REF-YR TO ACCOUNT-OPENED-YEAR OF OUTPUT-DATA
        Cobol.move(f84_DB2_DATE_REF_YR, f54_ACCOUNT_OPENED_YEAR, CS);
        // MOVE HV-ACCOUNT-OVERDRAFT-LIM TO ACCOUNT-OVERDRAFT-LIMIT OF OUTPUT-DATA
        Cobol.move(f10_HV_ACCOUNT_OVERDRAFT_LIM, f55_ACCOUNT_OVERDRAFT_LIMIT, CS);
        // MOVE HV-ACCOUNT-LAST-STMT TO DB2-DATE-REFORMAT
        Cobol.move(f11_HV_ACCOUNT_LAST_STMT, f83_DB2_DATE_REFORMAT, CS);
        // MOVE DB2-DATE-REF-DAY TO ACCOUNT-LAST-STMT-DAY OF OUTPUT-DATA
        Cobol.move(f88_DB2_DATE_REF_DAY, f58_ACCOUNT_LAST_STMT_DAY, CS);
        // MOVE DB2-DATE-REF-MNTH TO ACCOUNT-LAST-STMT-MONTH OF OUTPUT-DATA
        Cobol.move(f86_DB2_DATE_REF_MNTH, f59_ACCOUNT_LAST_STMT_MONTH, CS);
        // MOVE DB2-DATE-REF-YR TO ACCOUNT-LAST-STMT-YEAR OF OUTPUT-DATA
        Cobol.move(f84_DB2_DATE_REF_YR, f60_ACCOUNT_LAST_STMT_YEAR, CS);
        // MOVE HV-ACCOUNT-NEXT-STMT TO DB2-DATE-REFORMAT
        Cobol.move(f12_HV_ACCOUNT_NEXT_STMT, f83_DB2_DATE_REFORMAT, CS);
        // MOVE DB2-DATE-REF-DAY TO ACCOUNT-NEXT-STMT-DAY OF OUTPUT-DATA
        Cobol.move(f88_DB2_DATE_REF_DAY, f63_ACCOUNT_NEXT_STMT_DAY, CS);
        // MOVE DB2-DATE-REF-MNTH TO ACCOUNT-NEXT-STMT-MONTH OF OUTPUT-DATA
        Cobol.move(f86_DB2_DATE_REF_MNTH, f64_ACCOUNT_NEXT_STMT_MONTH, CS);
        // MOVE DB2-DATE-REF-YR TO ACCOUNT-NEXT-STMT-YEAR OF OUTPUT-DATA
        Cobol.move(f84_DB2_DATE_REF_YR, f65_ACCOUNT_NEXT_STMT_YEAR, CS);
        // MOVE HV-ACCOUNT-AVAIL-BAL TO ACCOUNT-AVAILABLE-BALANCE OF OUTPUT-DATA
        Cobol.move(f13_HV_ACCOUNT_AVAIL_BAL, f66_ACCOUNT_AVAILABLE_BALANCE, CS);
        // MOVE HV-ACCOUNT-ACTUAL-BAL TO ACCOUNT-ACTUAL-BALANCE OF OUTPUT-DATA
        Cobol.move(f14_HV_ACCOUNT_ACTUAL_BAL, f67_ACCOUNT_ACTUAL_BALANCE, CS);
        return 8;
    }

    /** FD999. */
    private int p8() {
        // EXIT
        return 9;
    }

    /** GET-ME-OUT-OF-HERE. */
    private int p9() {

        return 10;
    }

    /** GMOFH010. */
    private int p10() {
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        // GOBACK
        if (true) throw new Goback();
        return 11;
    }

    /** GMOFH999. */
    private int p11() {
        // EXIT
        return 12;
    }

    /** CHECK-FOR-STORM-DRAIN-DB2. */
    private int p12() {

        return 13;
    }

    /** CFSDCD010. */
    private int p13() {
        // EVALUATE SQLCODE
        if ((Cobol.num(f18_SQLCODE, CS).compareTo(D923) == 0)) {
            // MOVE 'DB2 Connection lost ' TO STORM-DRAIN-CONDITION
            f98_STORM_DRAIN_CONDITION = "DB2 Connection lost ";
        } else if (true) {
            // MOVE 'Not Storm Drain ' TO STORM-DRAIN-CONDITION
            f98_STORM_DRAIN_CONDITION = "Not Storm Drain     ";
        }
        // MOVE SQLCODE TO SQLCODE-DISPLAY
        Cobol.move(f18_SQLCODE, f99_SQLCODE_DISPLAY, CS);
        // IF STORM-DRAIN-CONDITION NOT EQUAL 'Not Storm Drain '
        if (!(f98_STORM_DRAIN_CONDITION.equals("Not Storm Drain     "))) {
            // DISPLAY 'INQACC: Check-For-Storm-Drain-DB2: Storm ' 'Drain condition (' STORM-DRAIN-CONDITION ') ' 'has been met (' SQLCODE-DISPLAY ').'
            Sysout.display("INQACC: Check-For-Storm-Drain-DB2: Storm ", "Drain condition (", f98_STORM_DRAIN_CONDITION, ") ", "has been met (", Cobol.displayText(f99_SQLCODE_DISPLAY, CS), ").");
        } else {
            // CONTINUE
        }
        return 14;
    }

    /** CFSDCD999. */
    private int p14() {
        // EXIT
        return 15;
    }

    /** ABEND-HANDLING. */
    private int p15() {

        return 16;
    }

    /** AH010. */
    private int p16() {
        // EXEC CICS ASSIGN ABCODE(MY-ABEND-CODE) END-EXEC
        DetCics.putText(f96_MY_ABEND_CODE, task.abcode(), CS);
        // EVALUATE MY-ABEND-CODE
        if ((Cobol.compare(f96_MY_ABEND_CODE, "AD2Z", CS) == 0)) {
            // MOVE SQLCODE TO SQLCODE-DISPLAY
            Cobol.move(f18_SQLCODE, f99_SQLCODE_DISPLAY, CS);
            // DISPLAY 'DB2 DEADLOCK DETECTED IN INQACC, SQLCODE=' SQLCODE-DISPLAY
            Sysout.display("DB2 DEADLOCK DETECTED IN INQACC, SQLCODE=", Cobol.displayText(f99_SQLCODE_DISPLAY, CS));
            // DISPLAY 'DB2 DEADLOCK FOR ACCOUNT ' HV-ACCOUNT-ACC-NO
            Sysout.display("DB2 DEADLOCK FOR ACCOUNT ", Cobol.displayText(f6_HV_ACCOUNT_ACC_NO, CS));
            // DISPLAY 'SQLSTATE=' SQLSTATE ',SQLERRMC=' sqlerrmc(1:sqlerrmL) ',SQLERRD(1)=' SQLERRD(1) ',SQLERRD(2)=' SQLERRD(2) ',SQLERRD(3)=' SQLERRD(3) ',SQLERRD
            Sysout.display("SQLSTATE=", Cobol.displayText(f36_SQLSTATE, CS), ",SQLERRMC=", Cobol.displayText(f21_SQLERRMC.ref(1, Integer.valueOf(Cobol.num(f20_SQLERRML, CS).intValue())), CS), ",SQLERRD(1)=", Cobol.displayText(f23_SQLERRD.at(1, 4), CS), ",SQLERRD(2)=", Cobol.displayText(f23_SQLERRD.at(2, 4), CS), ",SQLERRD(3)=", Cobol.displayText(f23_SQLERRD.at(3, 4), CS), ",SQLERRD(4)=", Cobol.displayText(f23_SQLERRD.at(4, 4), CS), ",SQLERRD(5)=", Cobol.displayText(f23_SQLERRD.at(5, 4), CS), ",SQLERRD(6)=", Cobol.displayText(f23_SQLERRD.at(6, 4), CS));
        } else if ((Cobol.compare(f96_MY_ABEND_CODE, "AFCR", CS) == 0) || (Cobol.compare(f96_MY_ABEND_CODE, "AFCS", CS) == 0) || (Cobol.compare(f96_MY_ABEND_CODE, "AFCT", CS) == 0)) {
            // MOVE 'Y' TO WS-STORM-DRAIN
            f97_WS_STORM_DRAIN = "Y";
            // DISPLAY 'INQACC: Check-For-Storm-Drain-VSAM: Storm ' 'Drain condition (Abend ' MY-ABEND-CODE ') ' 'has been met.'
            Sysout.display("INQACC: Check-For-Storm-Drain-VSAM: Storm ", "Drain condition (Abend ", Cobol.displayText(f96_MY_ABEND_CODE, CS), ") ", "has been met.");
            // EXEC CICS SYNCPOINT ROLLBACK RESP(WS-CICS-RESP) RESP2(WS-CICS-RESP2) END-EXEC
            task.rollback();
            Cobol.store(f207_EIBRESP, BigDecimal.valueOf(0), false, CS);
            Cobol.store(f208_EIBRESP2, BigDecimal.valueOf(0), false, CS);
            Cobol.store(f38_WS_CICS_RESP, BigDecimal.valueOf(0), false, CS);
            Cobol.store(f39_WS_CICS_RESP2, BigDecimal.valueOf(0), false, CS);
            // IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
            if (!(Cobol.num(f38_WS_CICS_RESP, CS).compareTo(D0) == 0)) {
                // INITIALIZE ABNDINFO-REC
                Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 0, 15, 0, true), CS);
                Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 8, 4, 0, false, false, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 12, 8, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 20, 4, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 24, 10, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 34, 8, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 42, 4, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 46, 8, false), CS);
                Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 54, 8, 0, true, true, true), CS);
                Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 63, 8, 0, true, true, true), CS);
                Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 72, 8, 0, true, true, true), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 81, 600, false), CS);
                // MOVE EIBRESP TO ABND-RESPCODE
                Cobol.move(f207_EIBRESP, f147_ABND_RESPCODE, CS);
                // MOVE EIBRESP2 TO ABND-RESP2CODE
                Cobol.move(f208_EIBRESP2, f148_ABND_RESP2CODE, CS);
                // EXEC CICS ASSIGN APPLID(ABND-APPLID) END-EXEC
                DetCics.putText(f141_ABND_APPLID, task.assignApplid(), CS);
                // MOVE EIBTASKN TO ABND-TASKNO-KEY
                Cobol.move(f182_EIBTASKN, f140_ABND_TASKNO_KEY, CS);
                // MOVE EIBTRNID TO ABND-TRANID
                Cobol.move(f181_EIBTRNID, f142_ABND_TRANID, CS);
                // PERFORM POPULATE-TIME-DATE
                perform(24, 26);
                // MOVE WS-ORIG-DATE TO ABND-DATE
                Cobol.move(f117_WS_ORIG_DATE, f143_ABND_DATE, CS);
                // STRING WS-TIME-NOW-GRP-HH DELIMITED BY SIZE, ':' DELIMITED BY SIZE, WS-TIME-NOW-GRP-MM DELIMITED BY SIZE, ':' DELIMITED BY SIZE, WS-TIME-NOW-GRP-MM DE
                Cobol.string(f144_ABND_TIME, null, CS, Cobol.StringPart.size(f133_WS_TIME_NOW_GRP_HH), Cobol.StringPart.size(":", CS), Cobol.StringPart.size(f134_WS_TIME_NOW_GRP_MM), Cobol.StringPart.size(":", CS), Cobol.StringPart.size(f134_WS_TIME_NOW_GRP_MM));
                // MOVE WS-U-TIME TO ABND-UTIME-KEY
                Cobol.move(f116_WS_U_TIME, f139_ABND_UTIME_KEY, CS);
                // MOVE 'HROL' TO ABND-CODE
                Cobol.move("HROL", f145_ABND_CODE, CS);
                // EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM) END-EXEC
                DetCics.putText(f146_ABND_PROGRAM, "INQACC  ", CS);
                // MOVE 0 TO ABND-SQLCODE
                Cobol.move(D0, f149_ABND_SQLCODE, CS);
                // STRING 'AH010 -Unable to perform SYNCPOINT ROLLBACK.' DELIMITED BY SIZE, ' Possible integrity issue following VSAM RLS ' DELIMITED BY SIZE, ' abend.' 
                Cobol.string(f150_ABND_FREEFORM, null, CS, Cobol.StringPart.size("AH010 -Unable to perform SYNCPOINT ROLLBACK.", CS), Cobol.StringPart.size(" Possible integrity issue following VSAM RLS ", CS), Cobol.StringPart.size(" abend.", CS), Cobol.StringPart.size(" EIBRESP=", CS), Cobol.StringPart.size(f147_ABND_RESPCODE), Cobol.StringPart.size(" RESP2=", CS), Cobol.StringPart.size(f148_ABND_RESP2CODE));
                // EXEC CICS LINK PROGRAM(WS-ABEND-PGM) COMMAREA(ABNDINFO-REC) END-EXEC
                Storage cw22 = Cobol.commarea(f137_ABNDINFO_REC, 681);
                AbndprocDfhcommarea ca21 = out_AbndprocDfhcommarea(cw22, 0);
                String lr20 = task.link(f136_WS_ABEND_PGM.strip(), ca21, 681, cw22.bytes);
                if ("NORMAL".equals(lr20)) { in_AbndprocDfhcommarea(ca21, cw22, 0); Cobol.commareaBack(cw22, f137_ABNDINFO_REC); }
                String exit23 = task.abendExit();
                if (exit23 != null) return GOTO | paragraph(exit23);
                if (task.ended()) throw abended();
                Cobol.store(f207_EIBRESP, BigDecimal.valueOf(DetCics.resp(lr20)), false, CS);
                Cobol.store(f208_EIBRESP2, BigDecimal.valueOf(0), false, CS);
                if (DetCics.resp(lr20) != 0) {
                    int to = condition(DetCics.condition(DetCics.resp(lr20)));
                    if (to >= 0) return GOTO | to;
                }
                // DISPLAY 'INQACC: Unable to perform Syncpoint ' 'Rollback. Possible Integrity issue ' ' following VSAM RLS abend. ' ' RESP CODE=' WS-CICS-RESP ' RESP2 
                Sysout.display("INQACC: Unable to perform Syncpoint ", "Rollback. Possible Integrity issue ", " following VSAM RLS abend. ", " RESP CODE=", Cobol.displayText(f38_WS_CICS_RESP, CS), " RESP2 CODE=", Cobol.displayText(f39_WS_CICS_RESP2, CS));
                // EXEC CICS ABEND ABCODE ('HROL') NODUMP CANCEL END-EXEC
                String exit24 = task.abendCancel("HROL".strip());
                if (exit24 == null) throw abended();
                if (true) return GOTO | paragraph(exit24);
            }
            // MOVE 'N' TO INQACC-SUCCESS
            Cobol.move("N", f176_INQACC_SUCCESS, CS);
            // EXEC CICS RETURN END-EXEC
            caBack.run();
            task.returnTransid(null, null);
            if (true) throw new Goback();
        }
        // IF WS-STORM-DRAIN = 'N'
        if (f97_WS_STORM_DRAIN.equals("N")) {
            // INITIALIZE ABNDINFO-REC
            Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 0, 15, 0, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 8, 4, 0, false, false, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 12, 8, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 20, 4, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 24, 10, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 34, 8, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 42, 4, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 46, 8, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 54, 8, 0, true, true, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 63, 8, 0, true, true, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 72, 8, 0, true, true, true), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 81, 600, false), CS);
            // MOVE EIBRESP TO ABND-RESPCODE
            Cobol.move(f207_EIBRESP, f147_ABND_RESPCODE, CS);
            // MOVE EIBRESP2 TO ABND-RESP2CODE
            Cobol.move(f208_EIBRESP2, f148_ABND_RESP2CODE, CS);
            // EXEC CICS ASSIGN APPLID(ABND-APPLID) END-EXEC
            DetCics.putText(f141_ABND_APPLID, task.assignApplid(), CS);
            // MOVE EIBTASKN TO ABND-TASKNO-KEY
            Cobol.move(f182_EIBTASKN, f140_ABND_TASKNO_KEY, CS);
            // MOVE EIBTRNID TO ABND-TRANID
            Cobol.move(f181_EIBTRNID, f142_ABND_TRANID, CS);
            // PERFORM POPULATE-TIME-DATE
            perform(24, 26);
            // MOVE WS-ORIG-DATE TO ABND-DATE
            Cobol.move(f117_WS_ORIG_DATE, f143_ABND_DATE, CS);
            // STRING WS-TIME-NOW-GRP-HH DELIMITED BY SIZE, ':' DELIMITED BY SIZE, WS-TIME-NOW-GRP-MM DELIMITED BY SIZE, ':' DELIMITED BY SIZE, WS-TIME-NOW-GRP-MM DE
            Cobol.string(f144_ABND_TIME, null, CS, Cobol.StringPart.size(f133_WS_TIME_NOW_GRP_HH), Cobol.StringPart.size(":", CS), Cobol.StringPart.size(f134_WS_TIME_NOW_GRP_MM), Cobol.StringPart.size(":", CS), Cobol.StringPart.size(f134_WS_TIME_NOW_GRP_MM));
            // MOVE WS-U-TIME TO ABND-UTIME-KEY
            Cobol.move(f116_WS_U_TIME, f139_ABND_UTIME_KEY, CS);
            // MOVE MY-ABEND-CODE TO ABND-CODE
            Cobol.move(f96_MY_ABEND_CODE, f145_ABND_CODE, CS);
            // EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM) END-EXEC
            DetCics.putText(f146_ABND_PROGRAM, "INQACC  ", CS);
            // MOVE ZEROS TO ABND-SQLCODE
            Cobol.moveFigurative(Figurative.ZEROS, f149_ABND_SQLCODE, CS);
            // STRING 'AH010 -WVS-STORM-DRAIN=N' DELIMITED BY SIZE, ' EIBRESP=' DELIMITED BY SIZE, ABND-RESPCODE DELIMITED BY SIZE, ' RESP2=' DELIMITED BY SIZE, ABND
            Cobol.string(f150_ABND_FREEFORM, null, CS, Cobol.StringPart.size("AH010 -WVS-STORM-DRAIN=N", CS), Cobol.StringPart.size(" EIBRESP=", CS), Cobol.StringPart.size(f147_ABND_RESPCODE), Cobol.StringPart.size(" RESP2=", CS), Cobol.StringPart.size(f148_ABND_RESP2CODE));
            // EXEC CICS LINK PROGRAM(WS-ABEND-PGM) COMMAREA(ABNDINFO-REC) END-EXEC
            Storage cw27 = Cobol.commarea(f137_ABNDINFO_REC, 681);
            AbndprocDfhcommarea ca26 = out_AbndprocDfhcommarea(cw27, 0);
            String lr25 = task.link(f136_WS_ABEND_PGM.strip(), ca26, 681, cw27.bytes);
            if ("NORMAL".equals(lr25)) { in_AbndprocDfhcommarea(ca26, cw27, 0); Cobol.commareaBack(cw27, f137_ABNDINFO_REC); }
            String exit28 = task.abendExit();
            if (exit28 != null) return GOTO | paragraph(exit28);
            if (task.ended()) throw abended();
            Cobol.store(f207_EIBRESP, BigDecimal.valueOf(DetCics.resp(lr25)), false, CS);
            Cobol.store(f208_EIBRESP2, BigDecimal.valueOf(0), false, CS);
            if (DetCics.resp(lr25) != 0) {
                int to = condition(DetCics.condition(DetCics.resp(lr25)));
                if (to >= 0) return GOTO | to;
            }
            // EXEC CICS ABEND ABCODE( MY-ABEND-CODE) NODUMP CANCEL END-EXEC
            String exit29 = task.abendCancel(Cobol.text(f96_MY_ABEND_CODE, CS).strip());
            if (exit29 == null) throw abended();
            if (true) return GOTO | paragraph(exit29);
        }
        return 17;
    }

    /** AH999. */
    private int p17() {
        // EXIT
        return 18;
    }

    /** READ-ACCOUNT-LAST. */
    private int p18() {

        return 19;
    }

    /** RAN010. */
    private int p19() {
        // PERFORM GET-LAST-ACCOUNT-DB2
        perform(21, 23);
        // MOVE REQUIRED-ACC-NUMBER2 TO NCS-ACC-NO-VALUE
        Cobol.move(f111_REQUIRED_ACC_NUMBER2, f106_NCS_ACC_NO_VALUE, CS);
        return 20;
    }

    /** RAN999. */
    private int p20() {
        // EXIT
        return 21;
    }

    /** GET-LAST-ACCOUNT-DB2. */
    private int p21() {

        return 22;
    }

    /** GLAD010. */
    private int p22() {
        // INITIALIZE OUTPUT-DATA
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 0, 4, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 4, 10, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 14, 6, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 20, 8, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 28, 8, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 36, 6, 2, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 42, 8, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 50, 8, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 58, 8, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 66, 8, 0, false, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 74, 12, 2, true, false, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f41_OUTPUT_DATA.storage(), f41_OUTPUT_DATA.offset() + 86, 12, 2, true, false, false), CS);
        // MOVE REQUIRED-ACC-NUMBER2 TO HV-ACCOUNT-ACC-NO
        Cobol.move(f111_REQUIRED_ACC_NUMBER2, f6_HV_ACCOUNT_ACC_NO, CS);
        // MOVE REQUIRED-SORT-CODE TO HV-ACCOUNT-SORTCODE
        Cobol.move(f94_REQUIRED_SORT_CODE, f5_HV_ACCOUNT_SORTCODE, CS);
        // MOVE SORTCODE TO HV-ACCOUNT-SORTCODE
        Cobol.move(f1_SORTCODE, f5_HV_ACCOUNT_SORTCODE, CS);
        // EXEC SQL SELECT ACCOUNT_EYECATCHER, ACCOUNT_CUSTOMER_NUMBER, ACCOUNT_SORTCODE, ACCOUNT_NUMBER, ACCOUNT_TYPE, ACCOUNT_INTEREST_RATE, ACCOUNT_OPENED, AC
        java.util.Map<String, Object> sqlParams30 = new java.util.HashMap<>();
        sqlParams30.put("hvAccountSortcode", DetSql.charIn(f5_HV_ACCOUNT_SORTCODE, CS));
        java.util.Map<String, Object> sqlRow31 = DetSql.selectOne(f15_SQLCA, "INQACC:843", () -> accountRepository.selectL843Inqacc(sqlParams30), CS);
        if (sqlRow31 != null) {
            DetSql.into(f15_SQLCA, sqlRow31, "XXXXXNXNXXNN", new Field[] {f3_HV_ACCOUNT_EYECATCHER, f4_HV_ACCOUNT_CUST_NO, f5_HV_ACCOUNT_SORTCODE, f6_HV_ACCOUNT_ACC_NO, f7_HV_ACCOUNT_ACC_TYPE, f8_HV_ACCOUNT_INT_RATE, f9_HV_ACCOUNT_OPENED, f10_HV_ACCOUNT_OVERDRAFT_LIM, f11_HV_ACCOUNT_LAST_STMT, f12_HV_ACCOUNT_NEXT_STMT, f13_HV_ACCOUNT_AVAIL_BAL, f14_HV_ACCOUNT_ACTUAL_BAL}, new Field[] {null, null, null, null, null, null, null, null, null, null, null, null}, null, CS);
        }
        // IF SQLCODE IS NOT EQUAL TO ZERO
        if (!(Cobol.num(f18_SQLCODE, CS).compareTo(BigDecimal.ZERO) == 0)) {
            // MOVE SQLCODE TO SQLCODE-DISPLAY
            Cobol.move(f18_SQLCODE, f99_SQLCODE_DISPLAY, CS);
            // INITIALIZE ABNDINFO-REC
            Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 0, 15, 0, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 8, 4, 0, false, false, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 12, 8, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 20, 4, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 24, 10, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 34, 8, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 42, 4, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 46, 8, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 54, 8, 0, true, true, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 63, 8, 0, true, true, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 72, 8, 0, true, true, true), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f137_ABNDINFO_REC.storage(), f137_ABNDINFO_REC.offset() + 81, 600, false), CS);
            // MOVE EIBRESP TO ABND-RESPCODE
            Cobol.move(f207_EIBRESP, f147_ABND_RESPCODE, CS);
            // MOVE EIBRESP2 TO ABND-RESP2CODE
            Cobol.move(f208_EIBRESP2, f148_ABND_RESP2CODE, CS);
            // EXEC CICS ASSIGN APPLID(ABND-APPLID) END-EXEC
            DetCics.putText(f141_ABND_APPLID, task.assignApplid(), CS);
            // MOVE EIBTASKN TO ABND-TASKNO-KEY
            Cobol.move(f182_EIBTASKN, f140_ABND_TASKNO_KEY, CS);
            // MOVE EIBTRNID TO ABND-TRANID
            Cobol.move(f181_EIBTRNID, f142_ABND_TRANID, CS);
            // PERFORM POPULATE-TIME-DATE
            perform(24, 26);
            // MOVE WS-ORIG-DATE TO ABND-DATE
            Cobol.move(f117_WS_ORIG_DATE, f143_ABND_DATE, CS);
            // STRING WS-TIME-NOW-GRP-HH DELIMITED BY SIZE, ':' DELIMITED BY SIZE, WS-TIME-NOW-GRP-MM DELIMITED BY SIZE, ':' DELIMITED BY SIZE, WS-TIME-NOW-GRP-MM DE
            Cobol.string(f144_ABND_TIME, null, CS, Cobol.StringPart.size(f133_WS_TIME_NOW_GRP_HH), Cobol.StringPart.size(":", CS), Cobol.StringPart.size(f134_WS_TIME_NOW_GRP_MM), Cobol.StringPart.size(":", CS), Cobol.StringPart.size(f134_WS_TIME_NOW_GRP_MM));
            // MOVE WS-U-TIME TO ABND-UTIME-KEY
            Cobol.move(f116_WS_U_TIME, f139_ABND_UTIME_KEY, CS);
            // MOVE 'HNCS' TO ABND-CODE
            Cobol.move("HNCS", f145_ABND_CODE, CS);
            // EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM) END-EXEC
            DetCics.putText(f146_ABND_PROGRAM, "INQACC  ", CS);
            // MOVE SQLCODE-DISPLAY TO ABND-SQLCODE
            Cobol.move(f99_SQLCODE_DISPLAY, f149_ABND_SQLCODE, CS);
            // STRING 'GLAD010 -ACCOUNT NCS ' DELIMITED BY SIZE, NCS-ACC-NO-NAME DELIMITED BY SIZE, ' CANNOT be accessed and DB2 ' DELIMITED BY SIZE, ' SELECT failed
            Cobol.string(f150_ABND_FREEFORM, null, CS, Cobol.StringPart.size("GLAD010 -ACCOUNT NCS ", CS), Cobol.StringPart.size(f101_NCS_ACC_NO_NAME), Cobol.StringPart.size(" CANNOT be accessed and DB2 ", CS), Cobol.StringPart.size(" SELECT failed. SQLCODE=", CS), Cobol.StringPart.size(f99_SQLCODE_DISPLAY));
            // EXEC CICS LINK PROGRAM(WS-ABEND-PGM) COMMAREA(ABNDINFO-REC) END-EXEC
            Storage cw34 = Cobol.commarea(f137_ABNDINFO_REC, 681);
            AbndprocDfhcommarea ca33 = out_AbndprocDfhcommarea(cw34, 0);
            String lr32 = task.link(f136_WS_ABEND_PGM.strip(), ca33, 681, cw34.bytes);
            if ("NORMAL".equals(lr32)) { in_AbndprocDfhcommarea(ca33, cw34, 0); Cobol.commareaBack(cw34, f137_ABNDINFO_REC); }
            String exit35 = task.abendExit();
            if (exit35 != null) return GOTO | paragraph(exit35);
            if (task.ended()) throw abended();
            Cobol.store(f207_EIBRESP, BigDecimal.valueOf(DetCics.resp(lr32)), false, CS);
            Cobol.store(f208_EIBRESP2, BigDecimal.valueOf(0), false, CS);
            if (DetCics.resp(lr32) != 0) {
                int to = condition(DetCics.condition(DetCics.resp(lr32)));
                if (to >= 0) return GOTO | to;
            }
            // DISPLAY 'INQACC - ACCOUNT NCS ' NCS-ACC-NO-NAME ' CANNOT BE ACCESSED AND DB2 SELECT FAILED. SQLCODE=' SQLCODE-DISPLAY
            Sysout.display("INQACC - ACCOUNT NCS ", Cobol.displayText(f101_NCS_ACC_NO_NAME, CS), " CANNOT BE ACCESSED AND DB2 SELECT FAILED. SQLCODE=", Cobol.displayText(f99_SQLCODE_DISPLAY, CS));
            // EXEC CICS ABEND ABCODE('HNCS') NODUMP CANCEL END-EXEC
            String exit36 = task.abendCancel("HNCS".strip());
            if (exit36 == null) throw abended();
            if (true) return GOTO | paragraph(exit36);
        } else {
            // MOVE HV-ACCOUNT-EYECATCHER TO ACCOUNT-EYE-CATCHER OF OUTPUT-DATA
            Cobol.move(f3_HV_ACCOUNT_EYECATCHER, f43_ACCOUNT_EYE_CATCHER, CS);
            // MOVE HV-ACCOUNT-CUST-NO TO ACCOUNT-CUST-NO OF OUTPUT-DATA
            Cobol.move(f4_HV_ACCOUNT_CUST_NO, f44_ACCOUNT_CUST_NO, CS);
            // MOVE HV-ACCOUNT-SORTCODE TO ACCOUNT-SORT-CODE OF OUTPUT-DATA
            Cobol.move(f5_HV_ACCOUNT_SORTCODE, f46_ACCOUNT_SORT_CODE, CS);
            // MOVE HV-ACCOUNT-ACC-NO TO ACCOUNT-NUMBER OF OUTPUT-DATA
            Cobol.move(f6_HV_ACCOUNT_ACC_NO, f47_ACCOUNT_NUMBER, CS);
            // MOVE HV-ACCOUNT-ACC-TYPE TO ACCOUNT-TYPE OF OUTPUT-DATA
            Cobol.move(f7_HV_ACCOUNT_ACC_TYPE, f48_ACCOUNT_TYPE, CS);
            // MOVE HV-ACCOUNT-INT-RATE TO ACCOUNT-INTEREST-RATE OF OUTPUT-DATA
            Cobol.move(f8_HV_ACCOUNT_INT_RATE, f49_ACCOUNT_INTEREST_RATE, CS);
            // MOVE HV-ACCOUNT-OPENED TO DB2-DATE-REFORMAT
            Cobol.move(f9_HV_ACCOUNT_OPENED, f83_DB2_DATE_REFORMAT, CS);
            // MOVE DB2-DATE-REF-DAY TO ACCOUNT-OPENED-DAY OF OUTPUT-DATA
            Cobol.move(f88_DB2_DATE_REF_DAY, f52_ACCOUNT_OPENED_DAY, CS);
            // MOVE DB2-DATE-REF-MNTH TO ACCOUNT-OPENED-MONTH OF OUTPUT-DATA
            Cobol.move(f86_DB2_DATE_REF_MNTH, f53_ACCOUNT_OPENED_MONTH, CS);
            // MOVE DB2-DATE-REF-YR TO ACCOUNT-OPENED-YEAR OF OUTPUT-DATA
            Cobol.move(f84_DB2_DATE_REF_YR, f54_ACCOUNT_OPENED_YEAR, CS);
            // MOVE HV-ACCOUNT-OVERDRAFT-LIM TO ACCOUNT-OVERDRAFT-LIMIT OF OUTPUT-DATA
            Cobol.move(f10_HV_ACCOUNT_OVERDRAFT_LIM, f55_ACCOUNT_OVERDRAFT_LIMIT, CS);
            // MOVE HV-ACCOUNT-LAST-STMT TO DB2-DATE-REFORMAT
            Cobol.move(f11_HV_ACCOUNT_LAST_STMT, f83_DB2_DATE_REFORMAT, CS);
            // MOVE DB2-DATE-REF-DAY TO ACCOUNT-LAST-STMT-DAY OF OUTPUT-DATA
            Cobol.move(f88_DB2_DATE_REF_DAY, f58_ACCOUNT_LAST_STMT_DAY, CS);
            // MOVE DB2-DATE-REF-MNTH TO ACCOUNT-LAST-STMT-MONTH OF OUTPUT-DATA
            Cobol.move(f86_DB2_DATE_REF_MNTH, f59_ACCOUNT_LAST_STMT_MONTH, CS);
            // MOVE DB2-DATE-REF-YR TO ACCOUNT-LAST-STMT-YEAR OF OUTPUT-DATA
            Cobol.move(f84_DB2_DATE_REF_YR, f60_ACCOUNT_LAST_STMT_YEAR, CS);
            // MOVE HV-ACCOUNT-NEXT-STMT TO DB2-DATE-REFORMAT
            Cobol.move(f12_HV_ACCOUNT_NEXT_STMT, f83_DB2_DATE_REFORMAT, CS);
            // MOVE DB2-DATE-REF-DAY TO ACCOUNT-NEXT-STMT-DAY OF OUTPUT-DATA
            Cobol.move(f88_DB2_DATE_REF_DAY, f63_ACCOUNT_NEXT_STMT_DAY, CS);
            // MOVE DB2-DATE-REF-MNTH TO ACCOUNT-NEXT-STMT-MONTH OF OUTPUT-DATA
            Cobol.move(f86_DB2_DATE_REF_MNTH, f64_ACCOUNT_NEXT_STMT_MONTH, CS);
            // MOVE DB2-DATE-REF-YR TO ACCOUNT-NEXT-STMT-YEAR OF OUTPUT-DATA
            Cobol.move(f84_DB2_DATE_REF_YR, f65_ACCOUNT_NEXT_STMT_YEAR, CS);
            // MOVE HV-ACCOUNT-AVAIL-BAL TO ACCOUNT-AVAILABLE-BALANCE OF OUTPUT-DATA
            Cobol.move(f13_HV_ACCOUNT_AVAIL_BAL, f66_ACCOUNT_AVAILABLE_BALANCE, CS);
            // MOVE HV-ACCOUNT-ACTUAL-BAL TO ACCOUNT-ACTUAL-BALANCE OF OUTPUT-DATA
            Cobol.move(f14_HV_ACCOUNT_ACTUAL_BAL, f67_ACCOUNT_ACTUAL_BALANCE, CS);
        }
        return 23;
    }

    /** GLAD999. */
    private int p23() {
        // EXIT
        return 24;
    }

    /** POPULATE-TIME-DATE. */
    private int p24() {

        return 25;
    }

    /** PTD010. */
    private int p25() {
        // EXEC CICS ASKTIME ABSTIME(WS-U-TIME) END-EXEC
        Cobol.store(f116_WS_U_TIME, BigDecimal.valueOf(task.asktime()), false, CS);
        // EXEC CICS FORMATTIME ABSTIME(WS-U-TIME) DDMMYYYY(WS-ORIG-DATE) TIME(WS-TIME-NOW) DATESEP END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f116_WS_U_TIME, CS).longValue(), "DDMMYYYY", "/"), f117_WS_ORIG_DATE, CS);
        Cobol.move(CicsTask.formatTime(Cobol.num(f116_WS_U_TIME, CS).longValue(), ""), f131_WS_TIME_NOW, CS);
        return 26;
    }

    /** PTD999. */
    private int p26() {
        // EXIT
        return 27;
    }

}
