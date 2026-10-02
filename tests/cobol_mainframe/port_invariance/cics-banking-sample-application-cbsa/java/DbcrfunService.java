// gitgalaxy-det-port: COBOL DBCRFUN (DBCRFUN.cbl), translated by rule, statement for statement
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
import com.gitgalaxy.modernized.repository.db2.ProctranRepository;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * DBCRFUN: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 148, translated 148, holes 0.
 */
@Service
public class DbcrfunService {

    private static final Charset CS = CobolRecords.charset();
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D0 = new BigDecimal("0");
    private static final BigDecimal D100 = new BigDecimal("100");
    private static final BigDecimal D496 = new BigDecimal("496");
    private static final BigDecimal D923 = new BigDecimal("923");

    private static final byte[] IMAGE_s_SORTCODE = Base64.getDecoder().decode(String.join("",
            "OTg3NjU0"));
    private static final byte[] IMAGE_s_SYSIDERR_RETRY = Base64.getDecoder().decode(String.join("",
            "MDAw"));
    private static final byte[] IMAGE_s_HOST_ACCOUNT_ROW = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgAAAADCAgICAgICAgICAAAAAAICAgICAgICAgICAgICAgICAgICAAAAAAAAAMAAAAAAAADA=="));
    private static final byte[] IMAGE_s_HOST_PROCTRAN_ROW = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAAAAAAAAAM"));
    private static final byte[] IMAGE_s_SQLCA = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAAAAAAAAAAAAAAICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_CICS_WORK_AREA = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAA="));
    private static final byte[] IMAGE_s_FILE_RETRY = Base64.getDecoder().decode(String.join("",
            "MDAw"));
    private static final byte[] IMAGE_s_WS_EXIT_RETRY_LOOP = Base64.getDecoder().decode(String.join("",
            "IA=="));
    private static final byte[] IMAGE_s_DB2_DATE_REFORMAT = Base64.getDecoder().decode(String.join("",
            "MDAwMCAwMCAwMA=="));
    private static final byte[] IMAGE_s_DATA_STORE_TYPE = Base64.getDecoder().decode(String.join("",
            "IA=="));
    private static final byte[] IMAGE_s_WS_ACC_DATA = Base64.getDecoder().decode(String.join("",
            "ICAgIDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMCAgICAgICAgMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="));
    private static final byte[] IMAGE_s_WS_EIBTASKN12 = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwMDAw"));
    private static final byte[] IMAGE_s_WS_SQLCODE_DISP = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAw"));
    private static final byte[] IMAGE_s_DESIRED_ACC_KEY = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwMDAwMDA="));
    private static final byte[] IMAGE_s_NEW_ACCOUNT_AVAILABLE_BALANCE = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwMDB7"));
    private static final byte[] IMAGE_s_NEW_ACCOUNT_ACTUAL_BALANCE = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwMDB7"));
    private static final byte[] IMAGE_s_WS_ACC_REC_LEN = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private static final byte[] IMAGE_s_WS_U_TIME = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAw="));
    private static final byte[] IMAGE_s_WS_ORIG_DATE = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_ORIG_DATE_GRP_X = Base64.getDecoder().decode(String.join("",
            "ICAuICAuICAgIA=="));
    private static final byte[] IMAGE_s_PROCTRAN_AREA = Base64.getDecoder().decode(String.join("",
            "ICAgIDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgMDAwMDAwMDAwMDAw"));
    private static final byte[] IMAGE_s_WS_PASSED_DATA = Base64.getDecoder().decode(String.join("",
            "ICAgIDAwMDAwMCAgIA=="));
    private static final byte[] IMAGE_s_PROCTRAN_RIDFLD = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_SQLCODE_DISPLAY = Base64.getDecoder().decode(String.join("",
            "KzAwMDAwMDAw"));
    private static final byte[] IMAGE_s_MY_ABEND_CODE = Base64.getDecoder().decode(String.join("",
            "ICAgIA=="));
    private static final byte[] IMAGE_s_WS_STORM_DRAIN = Base64.getDecoder().decode(String.join("",
            "Tg=="));
    private static final byte[] IMAGE_s_STORM_DRAIN_CONDITION = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_NUMERIC_AMOUNT_DISPLAY = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_TIME_DATA = Base64.getDecoder().decode(String.join("",
            "MDAwMDAw"));
    private static final byte[] IMAGE_s_WS_ABEND_PGM = Base64.getDecoder().decode(String.join("",
            "QUJORFBST0M="));
    private static final byte[] IMAGE_s_ABNDINFO_REC = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAwwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgKzAwMDAwMDAwKzAwMDAwMDAwKzAwMDAwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_WS_SUFFICIENT_FUNDS = Base64.getDecoder().decode(String.join("",
            "Tg=="));
    private static final byte[] IMAGE_s_WS_DIFFERENCE = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwMDAw"));
    private static final byte[] IMAGE_s_DFHCOMMAREA = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAgICAgICAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_SORTCODE = new Storage(IMAGE_s_SORTCODE.length);
    private final Storage s_SYSIDERR_RETRY = new Storage(IMAGE_s_SYSIDERR_RETRY.length);
    private final Storage s_HOST_ACCOUNT_ROW = new Storage(IMAGE_s_HOST_ACCOUNT_ROW.length);
    private final Storage s_HOST_PROCTRAN_ROW = new Storage(IMAGE_s_HOST_PROCTRAN_ROW.length);
    private final Storage s_SQLCA = new Storage(IMAGE_s_SQLCA.length);
    private final Storage s_WS_CICS_WORK_AREA = new Storage(IMAGE_s_WS_CICS_WORK_AREA.length);
    private final Storage s_FILE_RETRY = new Storage(IMAGE_s_FILE_RETRY.length);
    private final Storage s_WS_EXIT_RETRY_LOOP = new Storage(IMAGE_s_WS_EXIT_RETRY_LOOP.length);
    private final Storage s_DB2_DATE_REFORMAT = new Storage(IMAGE_s_DB2_DATE_REFORMAT.length);
    private final Storage s_DATA_STORE_TYPE = new Storage(IMAGE_s_DATA_STORE_TYPE.length);
    private final Storage s_WS_ACC_DATA = new Storage(IMAGE_s_WS_ACC_DATA.length);
    private final Storage s_WS_EIBTASKN12 = new Storage(IMAGE_s_WS_EIBTASKN12.length);
    private final Storage s_WS_SQLCODE_DISP = new Storage(IMAGE_s_WS_SQLCODE_DISP.length);
    private final Storage s_DESIRED_ACC_KEY = new Storage(IMAGE_s_DESIRED_ACC_KEY.length);
    private final Storage s_NEW_ACCOUNT_AVAILABLE_BALANCE = new Storage(IMAGE_s_NEW_ACCOUNT_AVAILABLE_BALANCE.length);
    private final Storage s_NEW_ACCOUNT_ACTUAL_BALANCE = new Storage(IMAGE_s_NEW_ACCOUNT_ACTUAL_BALANCE.length);
    private final Storage s_WS_ACC_REC_LEN = new Storage(IMAGE_s_WS_ACC_REC_LEN.length);
    private final Storage s_WS_U_TIME = new Storage(IMAGE_s_WS_U_TIME.length);
    private final Storage s_WS_ORIG_DATE = new Storage(IMAGE_s_WS_ORIG_DATE.length);
    private final Storage s_WS_ORIG_DATE_GRP_X = new Storage(IMAGE_s_WS_ORIG_DATE_GRP_X.length);
    private final Storage s_PROCTRAN_AREA = new Storage(IMAGE_s_PROCTRAN_AREA.length);
    private final Storage s_WS_PASSED_DATA = new Storage(IMAGE_s_WS_PASSED_DATA.length);
    private final Storage s_PROCTRAN_RIDFLD = new Storage(IMAGE_s_PROCTRAN_RIDFLD.length);
    private final Storage s_SQLCODE_DISPLAY = new Storage(IMAGE_s_SQLCODE_DISPLAY.length);
    private final Storage s_MY_ABEND_CODE = new Storage(IMAGE_s_MY_ABEND_CODE.length);
    private final Storage s_WS_STORM_DRAIN = new Storage(IMAGE_s_WS_STORM_DRAIN.length);
    private final Storage s_STORM_DRAIN_CONDITION = new Storage(IMAGE_s_STORM_DRAIN_CONDITION.length);
    private final Storage s_NUMERIC_AMOUNT_DISPLAY = new Storage(IMAGE_s_NUMERIC_AMOUNT_DISPLAY.length);
    private final Storage s_WS_TIME_DATA = new Storage(IMAGE_s_WS_TIME_DATA.length);
    private final Storage s_WS_ABEND_PGM = new Storage(IMAGE_s_WS_ABEND_PGM.length);
    private final Storage s_ABNDINFO_REC = new Storage(IMAGE_s_ABNDINFO_REC.length);
    private final Storage s_WS_SUFFICIENT_FUNDS = new Storage(IMAGE_s_WS_SUFFICIENT_FUNDS.length);
    private final Storage s_WS_DIFFERENCE = new Storage(IMAGE_s_WS_DIFFERENCE.length);
    private final Storage s_DFHCOMMAREA = new Storage(IMAGE_s_DFHCOMMAREA.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private Field f100_FILLER;
    private Field f101_WS_ORIG_DATE_MM;
    private Field f102_FILLER;
    private Field f103_WS_ORIG_DATE_YYYY;
    private Field f104_WS_ORIG_DATE_GRP_X;
    private Field f105_WS_ORIG_DATE_DD_X;
    private Field f106_FILLER;
    private Field f107_WS_ORIG_DATE_MM_X;
    private Field f108_FILLER;
    private Field f109_WS_ORIG_DATE_YYYY_X;
    private Field f10_HV_ACCOUNT_INT_RATE;
    private Field f110_PROCTRAN_AREA;
    private Field f111_PROC_TRAN_DATA;
    private Field f112_PROC_TRAN_EYE_CATCHER;
    private Field f113_PROC_TRAN_LOGICAL_DELETE_AREA;
    private Field f114_PROC_TRAN_LOGICAL_DELETE_FLAG;
    private Field f115_FILLER;
    private Field f116_PROC_TRAN_ID;
    private Field f117_PROC_TRAN_SORT_CODE;
    private Field f118_PROC_TRAN_NUMBER;
    private Field f119_PROC_TRAN_DATE;
    private Field f11_HV_ACCOUNT_OPENED;
    private Field f120_PROC_TRAN_DATE_GRP;
    private Field f121_PROC_TRAN_DATE_GRP_YYYY;
    private Field f122_PROC_TRAN_DATE_GRP_MM;
    private Field f123_PROC_TRAN_DATE_GRP_DD;
    private Field f124_PROC_TRAN_TIME;
    private Field f125_PROC_TRAN_TIME_GRP;
    private Field f126_PROC_TRAN_TIME_GRP_HH;
    private Field f127_PROC_TRAN_TIME_GRP_MM;
    private Field f128_PROC_TRAN_TIME_GRP_SS;
    private Field f129_PROC_TRAN_REF;
    private Field f12_HV_ACCOUNT_OVERDRAFT_LIM;
    private Field f130_PROC_TRAN_TYPE;
    private Field f131_PROC_TRAN_DESC;
    private Field f132_PROC_TRAN_DESC_XFR;
    private Field f133_PROC_TRAN_DESC_XFR_HEADER;
    private Field f134_PROC_TRAN_DESC_XFR_SORTCODE;
    private Field f135_PROC_TRAN_DESC_XFR_ACCOUNT;
    private Field f136_PROC_TRAN_DESC_DELACC;
    private Field f137_PROC_DESC_DELACC_CUSTOMER;
    private Field f138_PROC_DESC_DELACC_ACCTYPE;
    private Field f139_PROC_DESC_DELACC_LAST_DD;
    private Field f13_HV_ACCOUNT_LAST_STMT;
    private Field f140_PROC_DESC_DELACC_LAST_MM;
    private Field f141_PROC_DESC_DELACC_LAST_YYYY;
    private Field f142_PROC_DESC_DELACC_NEXT_DD;
    private Field f143_PROC_DESC_DELACC_NEXT_MM;
    private Field f144_PROC_DESC_DELACC_NEXT_YYYY;
    private Field f145_PROC_DESC_DELACC_FOOTER;
    private Field f146_PROC_TRAN_DESC_CREACC;
    private Field f147_PROC_DESC_CREACC_CUSTOMER;
    private Field f148_PROC_DESC_CREACC_ACCTYPE;
    private Field f149_PROC_DESC_CREACC_LAST_DD;
    private Field f14_HV_ACCOUNT_NEXT_STMT;
    private Field f150_PROC_DESC_CREACC_LAST_MM;
    private Field f151_PROC_DESC_CREACC_LAST_YYYY;
    private Field f152_PROC_DESC_CREACC_NEXT_DD;
    private Field f153_PROC_DESC_CREACC_NEXT_MM;
    private Field f154_PROC_DESC_CREACC_NEXT_YYYY;
    private Field f155_PROC_DESC_CREACC_FOOTER;
    private Field f156_PROC_TRAN_DESC_DELCUS;
    private Field f157_PROC_DESC_DELCUS_SORTCODE;
    private Field f158_PROC_DESC_DELCUS_CUSTOMER;
    private Field f159_PROC_DESC_DELCUS_NAME;
    private Field f15_HV_ACCOUNT_AVAIL_BAL;
    private Field f160_PROC_DESC_DELCUS_DOB_YYYY;
    private Field f161_PROC_DESC_DELCUS_FILLER;
    private Field f162_PROC_DESC_DELCUS_DOB_MM;
    private Field f163_PROC_DESC_DELCUS_FILLER2;
    private Field f164_PROC_DESC_DELCUS_DOB_DD;
    private Field f165_PROC_TRAN_DESC_CRECUS;
    private Field f166_PROC_DESC_CRECUS_SORTCODE;
    private Field f167_PROC_DESC_CRECUS_CUSTOMER;
    private Field f168_PROC_DESC_CRECUS_NAME;
    private Field f169_PROC_DESC_CRECUS_DOB_YYYY;
    private Field f16_HV_ACCOUNT_ACTUAL_BAL;
    private Field f170_PROC_DESC_CRECUS_FILLER;
    private Field f171_PROC_DESC_CRECUS_DOB_MM;
    private Field f172_PROC_DESC_CRECUS_FILLER2;
    private Field f173_PROC_DESC_CRECUS_DOB_DD;
    private Field f174_PROC_TRAN_AMOUNT;
    private Field f175_WS_PASSED_DATA;
    private Field f176_WS_TEST_KEY;
    private Field f177_WS_SORT_CODE;
    private Field f178_WS_CUSTOMER_RANGE;
    private Field f179_WS_CUSTOMER_RANGE_TOP;
    private Field f17_HOST_PROCTRAN_ROW;
    private Field f180_WS_CUSTOMER_RANGE_MIDDLE;
    private Field f181_WS_CUSTOMER_RANGE_BOTTOM;
    private Field f182_PROCTRAN_RIDFLD;
    private Field f183_SQLCODE_DISPLAY;
    private Field f184_MY_ABEND_CODE;
    private Field f185_WS_STORM_DRAIN;
    private Field f186_STORM_DRAIN_CONDITION;
    private Field f187_NUMERIC_AMOUNT_DISPLAY;
    private Field f188_WS_TIME_DATA;
    private Field f189_WS_TIME_NOW;
    private Field f18_HV_PROCTRAN_EYECATCHER;
    private Field f190_WS_TIME_NOW_GRP;
    private Field f191_WS_TIME_NOW_GRP_HH;
    private Field f192_WS_TIME_NOW_GRP_MM;
    private Field f193_WS_TIME_NOW_GRP_SS;
    private Field f194_WS_ABEND_PGM;
    private Field f195_ABNDINFO_REC;
    private Field f196_ABND_VSAM_KEY;
    private Field f197_ABND_UTIME_KEY;
    private Field f198_ABND_TASKNO_KEY;
    private Field f199_ABND_APPLID;
    private Field f19_HV_PROCTRAN_SORT_CODE;
    private Field f1_SORTCODE;
    private Field f200_ABND_TRANID;
    private Field f201_ABND_DATE;
    private Field f202_ABND_TIME;
    private Field f203_ABND_CODE;
    private Field f204_ABND_PROGRAM;
    private Field f205_ABND_RESPCODE;
    private Field f206_ABND_RESP2CODE;
    private Field f207_ABND_SQLCODE;
    private Field f208_ABND_FREEFORM;
    private Field f209_WS_SUFFICIENT_FUNDS;
    private Field f20_HV_PROCTRAN_ACC_NUMBER;
    private Field f210_WS_DIFFERENCE;
    private Field f211_DFHCOMMAREA;
    private Field f212_COMM_ACCNO;
    private Field f213_COMM_AMT;
    private Field f214_COMM_SORTC;
    private Field f215_COMM_AV_BAL;
    private Field f216_COMM_ACT_BAL;
    private Field f217_COMM_ORIGIN;
    private Field f218_COMM_APPLID;
    private Field f219_COMM_USERID;
    private Field f21_HV_PROCTRAN_DATE;
    private Field f220_COMM_FACILITY_NAME;
    private Field f221_COMM_NETWRK_ID;
    private Field f222_COMM_FACILTYPE;
    private Field f223_FILLER;
    private Field f224_COMM_SUCCESS;
    private Field f225_COMM_FAIL_CODE;
    private Field f226_DFHEIBLK;
    private Field f227_EIBTIME;
    private Field f228_EIBDATE;
    private Field f229_EIBTRNID;
    private Field f22_HV_PROCTRAN_TIME;
    private Field f230_EIBTASKN;
    private Field f231_EIBTRMID;
    private Field f232_DFHEIGDI;
    private Field f233_EIBCPOSN;
    private Field f234_EIBCALEN;
    private Field f235_EIBAID;
    private Field f236_EIBFN;
    private Field f237_EIBRCODE;
    private Field f238_EIBDS;
    private Field f239_EIBREQID;
    private Field f23_HV_PROCTRAN_REF;
    private Field f240_EIBRSRCE;
    private Field f241_EIBSYNC;
    private Field f242_EIBFREE;
    private Field f243_EIBRECV;
    private Field f244_EIBSEND;
    private Field f245_EIBATT;
    private Field f246_EIBEOC;
    private Field f247_EIBFMH;
    private Field f248_EIBCOMPL;
    private Field f249_EIBSIG;
    private Field f24_HV_PROCTRAN_TYPE;
    private Field f250_EIBCONF;
    private Field f251_EIBERR;
    private Field f252_EIBERRCD;
    private Field f253_EIBSYNRB;
    private Field f254_EIBNODAT;
    private Field f255_EIBRESP;
    private Field f256_EIBRESP2;
    private Field f257_EIBRLDBK;
    private Field f258_GG_RETURN_CODE;
    private Field f25_HV_PROCTRAN_DESC;
    private Field f26_HV_PROCTRAN_AMOUNT;
    private Field f27_SQLCA;
    private Field f28_SQLCAID;
    private Field f29_SQLCABC;
    private Field f2_SYSIDERR_RETRY;
    private Field f30_SQLCODE;
    private Field f31_SQLERRM;
    private Field f32_SQLERRML;
    private Field f33_SQLERRMC;
    private Field f34_SQLERRP;
    private Field f35_SQLERRD;
    private Field f36_SQLWARN;
    private Field f37_SQLWARN0;
    private Field f38_SQLWARN1;
    private Field f39_SQLWARN2;
    private Field f3_HOST_ACCOUNT_ROW;
    private Field f40_SQLWARN3;
    private Field f41_SQLWARN4;
    private Field f42_SQLWARN5;
    private Field f43_SQLWARN6;
    private Field f44_SQLWARN7;
    private Field f45_SQLWARN8;
    private Field f46_SQLWARN9;
    private Field f47_SQLWARNA;
    private Field f48_SQLSTATE;
    private Field f49_WS_CICS_WORK_AREA;
    private Field f4_HV_ACCOUNT_EYECATCHER;
    private Field f50_WS_CICS_RESP;
    private Field f51_WS_CICS_RESP2;
    private Field f52_FILE_RETRY;
    private Field f53_WS_EXIT_RETRY_LOOP;
    private Field f54_DB2_DATE_REFORMAT;
    private Field f55_DB2_DATE_REF_YR;
    private Field f56_FILLER;
    private Field f57_DB2_DATE_REF_MNTH;
    private Field f58_FILLER;
    private Field f59_DB2_DATE_REF_DAY;
    private Field f5_HV_ACCOUNT_CUST_NO;
    private Field f60_DATA_STORE_TYPE;
    private Field f61_WS_ACC_DATA;
    private Field f62_ACCOUNT_DATA;
    private Field f63_ACCOUNT_EYE_CATCHER;
    private Field f64_ACCOUNT_CUST_NO;
    private Field f65_ACCOUNT_KEY;
    private Field f66_ACCOUNT_SORT_CODE;
    private Field f67_ACCOUNT_NUMBER;
    private Field f68_ACCOUNT_TYPE;
    private Field f69_ACCOUNT_INTEREST_RATE;
    private Field f6_HV_ACCOUNT_KEY;
    private Field f70_ACCOUNT_OPENED;
    private Field f71_ACCOUNT_OPENED_GROUP;
    private Field f72_ACCOUNT_OPENED_DAY;
    private Field f73_ACCOUNT_OPENED_MONTH;
    private Field f74_ACCOUNT_OPENED_YEAR;
    private Field f75_ACCOUNT_OVERDRAFT_LIMIT;
    private Field f76_ACCOUNT_LAST_STMT_DATE;
    private Field f77_ACCOUNT_LAST_STMT_GROUP;
    private Field f78_ACCOUNT_LAST_STMT_DAY;
    private Field f79_ACCOUNT_LAST_STMT_MONTH;
    private Field f7_HV_ACCOUNT_SORTCODE;
    private Field f80_ACCOUNT_LAST_STMT_YEAR;
    private Field f81_ACCOUNT_NEXT_STMT_DATE;
    private Field f82_ACCOUNT_NEXT_STMT_GROUP;
    private Field f83_ACCOUNT_NEXT_STMT_DAY;
    private Field f84_ACCOUNT_NEXT_STMT_MONTH;
    private Field f85_ACCOUNT_NEXT_STMT_YEAR;
    private Field f86_ACCOUNT_AVAILABLE_BALANCE;
    private Field f87_ACCOUNT_ACTUAL_BALANCE;
    private Field f88_WS_EIBTASKN12;
    private Field f89_WS_SQLCODE_DISP;
    private Field f8_HV_ACCOUNT_ACC_NO;
    private Field f90_DESIRED_ACC_KEY;
    private Field f91_DESIRED_SORT_CODE;
    private Field f92_DESIRED_ACC_NO;
    private Field f93_NEW_ACCOUNT_AVAILABLE_BALANCE;
    private Field f94_NEW_ACCOUNT_ACTUAL_BALANCE;
    private Field f95_WS_ACC_REC_LEN;
    private Field f96_WS_U_TIME;
    private Field f97_WS_ORIG_DATE;
    private Field f98_WS_ORIG_DATE_GRP;
    private Field f99_WS_ORIG_DATE_DD;
    private Field f9_HV_ACCOUNT_ACC_TYPE;

    private CicsTask task;
    private final java.util.Map<String, Integer> handlers = new java.util.HashMap<>();
    private final java.util.Map<String, DetCics.Store<?>> stores = new java.util.HashMap<>();
    private final java.util.Map<String, byte[]> heldKey = new java.util.HashMap<>();
    /** Writes the COMMAREA's bytes back into the object the task carries (a LINKed program's is its caller's). */
    private Runnable caBack = () -> { };

    @SuppressWarnings("unchecked")
    private <E> DetCics.Store<E> store(String name) {
        throw new Hole("CICS file " + name + ": the program names no file the generated project stores");
    }

    private static final java.util.Map<String, Integer> PARAGRAPHS = java.util.Map.ofEntries(
            java.util.Map.entry("PTD999", 23),
            java.util.Map.entry("PTD10", 22),
            java.util.Map.entry("POPULATE-TIME-DATE", 21),
            java.util.Map.entry("AH999", 20),
            java.util.Map.entry("AH010", 19),
            java.util.Map.entry("ABEND-HANDLING", 18),
            java.util.Map.entry("CFSDD999", 17),
            java.util.Map.entry("CFSDD010", 16),
            java.util.Map.entry("CHECK-FOR-STORM-DRAIN-DB2", 15),
            java.util.Map.entry("GMOOH999", 14),
            java.util.Map.entry("GMOOH010", 13),
            java.util.Map.entry("GET-ME-OUT-OF-HERE", 12),
            java.util.Map.entry("WTPD999", 11),
            java.util.Map.entry("WTPD010", 10),
            java.util.Map.entry("WRITE-TO-PROCTRAN-DB2", 9),
            java.util.Map.entry("WTP999", 8),
            java.util.Map.entry("WTP010", 7),
            java.util.Map.entry("WRITE-TO-PROCTRAN", 6),
            java.util.Map.entry("UAD999", 5),
            java.util.Map.entry("UAD010", 4),
            java.util.Map.entry("UPDATE-ACCOUNT-DB2", 3),
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

    /** A condition the command neither returned in RESP nor ignored: its HANDLE CONDITION label, or CICS's
     *  default action -- an abend, to this program's HANDLE ABEND exit or ending the task. */
    private int condition(String cond) {
        Integer h = handlers.get(cond);
        if (h != null) {
            return h;
        }
        String label = task.abendOnCondition(cond);
        if (label == null) {
            throw new Goback();
        }
        return paragraph(label);
    }

    private static int cx(CicsTask task, int whole) {
        return task.eibcalen() == null ? whole : task.eibcalen();
    }

    private void in_AbndprocAbndinfoRec(AbndprocAbndinfoRec d, Storage s, int base) {
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

    private void fill_AbndprocAbndinfoRec(AbndprocAbndinfoRec d, Storage s, int base) {
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

    private AbndprocAbndinfoRec out_AbndprocAbndinfoRec(Storage s, int base) {
        AbndprocAbndinfoRec d = new AbndprocAbndinfoRec();
        fill_AbndprocAbndinfoRec(d, s, base);
        return d;
    }

    private void in_Bnk1craSubpgmParms(Bnk1craSubpgmParms d, Storage s, int base) {
        if (d == null) {
            return;
        }
        Cobol.move(d.getSubpgmAccno() == null ? "" : d.getSubpgmAccno(), Field.alphanumeric(s, base + 0, 8, false), CS);
        Cobol.move(d.getSubpgmAmt() == null ? BigDecimal.ZERO : new BigDecimal(d.getSubpgmAmt().toString()), Field.zoned(s, base + 8, 12, 2, true, false, false), CS);
        Cobol.move(d.getSubpgmSortc() == null ? BigDecimal.ZERO : new BigDecimal(d.getSubpgmSortc().toString()), Field.zoned(s, base + 20, 6, 0, false, false, false), CS);
        Cobol.move(d.getSubpgmAvBal() == null ? BigDecimal.ZERO : new BigDecimal(d.getSubpgmAvBal().toString()), Field.zoned(s, base + 26, 12, 2, true, false, false), CS);
        Cobol.move(d.getSubpgmActBal() == null ? BigDecimal.ZERO : new BigDecimal(d.getSubpgmActBal().toString()), Field.zoned(s, base + 38, 12, 2, true, false, false), CS);
        Cobol.move(d.getSubpgmApplid() == null ? "" : d.getSubpgmApplid(), Field.alphanumeric(s, base + 50, 8, false), CS);
        Cobol.move(d.getSubpgmUserid() == null ? "" : d.getSubpgmUserid(), Field.alphanumeric(s, base + 58, 8, false), CS);
        Cobol.move(d.getSubpgmFacilityName() == null ? "" : d.getSubpgmFacilityName(), Field.alphanumeric(s, base + 66, 8, false), CS);
        Cobol.move(d.getSubpgmNetwrkId() == null ? "" : d.getSubpgmNetwrkId(), Field.alphanumeric(s, base + 74, 8, false), CS);
        Cobol.move(d.getSubpgmFaciltype() == null ? BigDecimal.ZERO : new BigDecimal(d.getSubpgmFaciltype().toString()), Field.binary(s, base + 82, 8, 0, true, false), CS);
        Cobol.move(d.getSubpgmSuccess() == null ? "" : d.getSubpgmSuccess(), Field.alphanumeric(s, base + 90, 1, false), CS);
        Cobol.move(d.getSubpgmFailCode() == null ? "" : d.getSubpgmFailCode(), Field.alphanumeric(s, base + 91, 1, false), CS);
    }

    private void fill_Bnk1craSubpgmParms(Bnk1craSubpgmParms d, Storage s, int base) {
        d.setSubpgmAccno(Cobol.text(Field.alphanumeric(s, base + 0, 8, false), CS));
        d.setSubpgmAmt(Cobol.num(Field.zoned(s, base + 8, 12, 2, true, false, false), CS));
        d.setSubpgmSortc(Cobol.num(Field.zoned(s, base + 20, 6, 0, false, false, false), CS).intValue());
        d.setSubpgmAvBal(Cobol.num(Field.zoned(s, base + 26, 12, 2, true, false, false), CS));
        d.setSubpgmActBal(Cobol.num(Field.zoned(s, base + 38, 12, 2, true, false, false), CS));
        d.setSubpgmApplid(Cobol.text(Field.alphanumeric(s, base + 50, 8, false), CS));
        d.setSubpgmUserid(Cobol.text(Field.alphanumeric(s, base + 58, 8, false), CS));
        d.setSubpgmFacilityName(Cobol.text(Field.alphanumeric(s, base + 66, 8, false), CS));
        d.setSubpgmNetwrkId(Cobol.text(Field.alphanumeric(s, base + 74, 8, false), CS));
        d.setSubpgmFaciltype(Cobol.num(Field.binary(s, base + 82, 8, 0, true, false), CS).intValue());
        d.setSubpgmSuccess(Cobol.text(Field.alphanumeric(s, base + 90, 1, false), CS));
        d.setSubpgmFailCode(Cobol.text(Field.alphanumeric(s, base + 91, 1, false), CS));
    }

    private Bnk1craSubpgmParms out_Bnk1craSubpgmParms(Storage s, int base) {
        Bnk1craSubpgmParms d = new Bnk1craSubpgmParms();
        fill_Bnk1craSubpgmParms(d, s, base);
        return d;
    }


    private final AccountRepository accountRepository;
    private final ProctranRepository proctranRepository;
    private final DatasetResolver datasets;
    private final CobolFiles files;
    private final MainframeClock clock;

    public DbcrfunService(AccountRepository accountRepository, ProctranRepository proctranRepository, DatasetResolver datasets, CobolFiles files, MainframeClock clock) {
        this.accountRepository = accountRepository;
        this.proctranRepository = proctranRepository;
        this.datasets = datasets;
        this.files = files;
        this.clock = clock;
        fields0();
    }

    private void fields0() {
        f1_SORTCODE = Field.zoned(s_SORTCODE, 0, 6, 0, false, false, false);
        f2_SYSIDERR_RETRY = Field.zoned(s_SYSIDERR_RETRY, 0, 3, 0, false, false, false);
        f3_HOST_ACCOUNT_ROW = Field.group(s_HOST_ACCOUNT_ROW, 0, 88);
        f4_HV_ACCOUNT_EYECATCHER = Field.alphanumeric(s_HOST_ACCOUNT_ROW, 0, 4, false);
        f5_HV_ACCOUNT_CUST_NO = Field.alphanumeric(s_HOST_ACCOUNT_ROW, 4, 10, false);
        f6_HV_ACCOUNT_KEY = Field.group(s_HOST_ACCOUNT_ROW, 14, 14);
        f7_HV_ACCOUNT_SORTCODE = Field.alphanumeric(s_HOST_ACCOUNT_ROW, 14, 6, false);
        f8_HV_ACCOUNT_ACC_NO = Field.alphanumeric(s_HOST_ACCOUNT_ROW, 20, 8, false);
        f9_HV_ACCOUNT_ACC_TYPE = Field.alphanumeric(s_HOST_ACCOUNT_ROW, 28, 8, false);
        f10_HV_ACCOUNT_INT_RATE = Field.packed(s_HOST_ACCOUNT_ROW, 36, 6, 2, true);
        f11_HV_ACCOUNT_OPENED = Field.alphanumeric(s_HOST_ACCOUNT_ROW, 40, 10, false);
        f12_HV_ACCOUNT_OVERDRAFT_LIM = Field.binary(s_HOST_ACCOUNT_ROW, 50, 9, 0, true, false);
        f13_HV_ACCOUNT_LAST_STMT = Field.alphanumeric(s_HOST_ACCOUNT_ROW, 54, 10, false);
        f14_HV_ACCOUNT_NEXT_STMT = Field.alphanumeric(s_HOST_ACCOUNT_ROW, 64, 10, false);
        f15_HV_ACCOUNT_AVAIL_BAL = Field.packed(s_HOST_ACCOUNT_ROW, 74, 12, 2, true);
        f16_HV_ACCOUNT_ACTUAL_BAL = Field.packed(s_HOST_ACCOUNT_ROW, 81, 12, 2, true);
        f17_HOST_PROCTRAN_ROW = Field.group(s_HOST_PROCTRAN_ROW, 0, 96);
        f18_HV_PROCTRAN_EYECATCHER = Field.alphanumeric(s_HOST_PROCTRAN_ROW, 0, 4, false);
        f19_HV_PROCTRAN_SORT_CODE = Field.alphanumeric(s_HOST_PROCTRAN_ROW, 4, 6, false);
        f20_HV_PROCTRAN_ACC_NUMBER = Field.alphanumeric(s_HOST_PROCTRAN_ROW, 10, 8, false);
        f21_HV_PROCTRAN_DATE = Field.alphanumeric(s_HOST_PROCTRAN_ROW, 18, 10, false);
        f22_HV_PROCTRAN_TIME = Field.alphanumeric(s_HOST_PROCTRAN_ROW, 28, 6, false);
        f23_HV_PROCTRAN_REF = Field.alphanumeric(s_HOST_PROCTRAN_ROW, 34, 12, false);
        f24_HV_PROCTRAN_TYPE = Field.alphanumeric(s_HOST_PROCTRAN_ROW, 46, 3, false);
        f25_HV_PROCTRAN_DESC = Field.alphanumeric(s_HOST_PROCTRAN_ROW, 49, 40, false);
        f26_HV_PROCTRAN_AMOUNT = Field.packed(s_HOST_PROCTRAN_ROW, 89, 12, 2, true);
        f27_SQLCA = Field.group(s_SQLCA, 0, 136);
        f28_SQLCAID = Field.alphanumeric(s_SQLCA, 0, 8, false);
        f29_SQLCABC = Field.binary(s_SQLCA, 8, 9, 0, true, true);
        f30_SQLCODE = Field.binary(s_SQLCA, 12, 9, 0, true, true);
        f31_SQLERRM = Field.group(s_SQLCA, 16, 72);
        f32_SQLERRML = Field.binary(s_SQLCA, 16, 4, 0, true, true);
        f33_SQLERRMC = Field.alphanumeric(s_SQLCA, 18, 70, false);
        f34_SQLERRP = Field.alphanumeric(s_SQLCA, 88, 8, false);
        f35_SQLERRD = Field.binary(s_SQLCA, 96, 9, 0, true, true);
        f36_SQLWARN = Field.group(s_SQLCA, 120, 11);
        f37_SQLWARN0 = Field.alphanumeric(s_SQLCA, 120, 1, false);
        f38_SQLWARN1 = Field.alphanumeric(s_SQLCA, 121, 1, false);
        f39_SQLWARN2 = Field.alphanumeric(s_SQLCA, 122, 1, false);
        f40_SQLWARN3 = Field.alphanumeric(s_SQLCA, 123, 1, false);
        f41_SQLWARN4 = Field.alphanumeric(s_SQLCA, 124, 1, false);
        f42_SQLWARN5 = Field.alphanumeric(s_SQLCA, 125, 1, false);
        f43_SQLWARN6 = Field.alphanumeric(s_SQLCA, 126, 1, false);
        f44_SQLWARN7 = Field.alphanumeric(s_SQLCA, 127, 1, false);
        f45_SQLWARN8 = Field.alphanumeric(s_SQLCA, 128, 1, false);
        f46_SQLWARN9 = Field.alphanumeric(s_SQLCA, 129, 1, false);
        f47_SQLWARNA = Field.alphanumeric(s_SQLCA, 130, 1, false);
        f48_SQLSTATE = Field.alphanumeric(s_SQLCA, 131, 5, false);
        f49_WS_CICS_WORK_AREA = Field.group(s_WS_CICS_WORK_AREA, 0, 8);
        f50_WS_CICS_RESP = Field.binary(s_WS_CICS_WORK_AREA, 0, 8, 0, true, false);
        f51_WS_CICS_RESP2 = Field.binary(s_WS_CICS_WORK_AREA, 4, 8, 0, true, false);
        f52_FILE_RETRY = Field.zoned(s_FILE_RETRY, 0, 3, 0, false, false, false);
        f53_WS_EXIT_RETRY_LOOP = Field.alphanumeric(s_WS_EXIT_RETRY_LOOP, 0, 1, false);
        f54_DB2_DATE_REFORMAT = Field.group(s_DB2_DATE_REFORMAT, 0, 10);
        f55_DB2_DATE_REF_YR = Field.zoned(s_DB2_DATE_REFORMAT, 0, 4, 0, false, false, false);
        f56_FILLER = Field.alphanumeric(s_DB2_DATE_REFORMAT, 4, 1, false);
        f57_DB2_DATE_REF_MNTH = Field.zoned(s_DB2_DATE_REFORMAT, 5, 2, 0, false, false, false);
        f58_FILLER = Field.alphanumeric(s_DB2_DATE_REFORMAT, 7, 1, false);
        f59_DB2_DATE_REF_DAY = Field.zoned(s_DB2_DATE_REFORMAT, 8, 2, 0, false, false, false);
        f60_DATA_STORE_TYPE = Field.alphanumeric(s_DATA_STORE_TYPE, 0, 1, false);
        f61_WS_ACC_DATA = Field.group(s_WS_ACC_DATA, 0, 98);
        f62_ACCOUNT_DATA = Field.group(s_WS_ACC_DATA, 0, 98);
        f63_ACCOUNT_EYE_CATCHER = Field.alphanumeric(s_WS_ACC_DATA, 0, 4, false);
        f64_ACCOUNT_CUST_NO = Field.zoned(s_WS_ACC_DATA, 4, 10, 0, false, false, false);
        f65_ACCOUNT_KEY = Field.group(s_WS_ACC_DATA, 14, 14);
        f66_ACCOUNT_SORT_CODE = Field.zoned(s_WS_ACC_DATA, 14, 6, 0, false, false, false);
        f67_ACCOUNT_NUMBER = Field.zoned(s_WS_ACC_DATA, 20, 8, 0, false, false, false);
        f68_ACCOUNT_TYPE = Field.alphanumeric(s_WS_ACC_DATA, 28, 8, false);
        f69_ACCOUNT_INTEREST_RATE = Field.zoned(s_WS_ACC_DATA, 36, 6, 2, false, false, false);
        f70_ACCOUNT_OPENED = Field.zoned(s_WS_ACC_DATA, 42, 8, 0, false, false, false);
        f71_ACCOUNT_OPENED_GROUP = Field.group(s_WS_ACC_DATA, 42, 8);
        f72_ACCOUNT_OPENED_DAY = Field.zoned(s_WS_ACC_DATA, 42, 2, 0, false, false, false);
        f73_ACCOUNT_OPENED_MONTH = Field.zoned(s_WS_ACC_DATA, 44, 2, 0, false, false, false);
        f74_ACCOUNT_OPENED_YEAR = Field.zoned(s_WS_ACC_DATA, 46, 4, 0, false, false, false);
        f75_ACCOUNT_OVERDRAFT_LIMIT = Field.zoned(s_WS_ACC_DATA, 50, 8, 0, false, false, false);
        f76_ACCOUNT_LAST_STMT_DATE = Field.zoned(s_WS_ACC_DATA, 58, 8, 0, false, false, false);
        f77_ACCOUNT_LAST_STMT_GROUP = Field.group(s_WS_ACC_DATA, 58, 8);
        f78_ACCOUNT_LAST_STMT_DAY = Field.zoned(s_WS_ACC_DATA, 58, 2, 0, false, false, false);
        f79_ACCOUNT_LAST_STMT_MONTH = Field.zoned(s_WS_ACC_DATA, 60, 2, 0, false, false, false);
        f80_ACCOUNT_LAST_STMT_YEAR = Field.zoned(s_WS_ACC_DATA, 62, 4, 0, false, false, false);
        f81_ACCOUNT_NEXT_STMT_DATE = Field.zoned(s_WS_ACC_DATA, 66, 8, 0, false, false, false);
        f82_ACCOUNT_NEXT_STMT_GROUP = Field.group(s_WS_ACC_DATA, 66, 8);
        f83_ACCOUNT_NEXT_STMT_DAY = Field.zoned(s_WS_ACC_DATA, 66, 2, 0, false, false, false);
        f84_ACCOUNT_NEXT_STMT_MONTH = Field.zoned(s_WS_ACC_DATA, 68, 2, 0, false, false, false);
        f85_ACCOUNT_NEXT_STMT_YEAR = Field.zoned(s_WS_ACC_DATA, 70, 4, 0, false, false, false);
        f86_ACCOUNT_AVAILABLE_BALANCE = Field.zoned(s_WS_ACC_DATA, 74, 12, 2, true, false, false);
        f87_ACCOUNT_ACTUAL_BALANCE = Field.zoned(s_WS_ACC_DATA, 86, 12, 2, true, false, false);
        f88_WS_EIBTASKN12 = Field.zoned(s_WS_EIBTASKN12, 0, 12, 0, false, false, false);
        f89_WS_SQLCODE_DISP = Field.zoned(s_WS_SQLCODE_DISP, 0, 9, 0, false, false, false);
        f90_DESIRED_ACC_KEY = Field.group(s_DESIRED_ACC_KEY, 0, 14);
        f91_DESIRED_SORT_CODE = Field.zoned(s_DESIRED_ACC_KEY, 0, 6, 0, false, false, false);
        f92_DESIRED_ACC_NO = Field.zoned(s_DESIRED_ACC_KEY, 6, 8, 0, false, false, false);
        f93_NEW_ACCOUNT_AVAILABLE_BALANCE = Field.zoned(s_NEW_ACCOUNT_AVAILABLE_BALANCE, 0, 12, 2, true, false, false);
        f94_NEW_ACCOUNT_ACTUAL_BALANCE = Field.zoned(s_NEW_ACCOUNT_ACTUAL_BALANCE, 0, 12, 2, true, false, false);
        f95_WS_ACC_REC_LEN = Field.binary(s_WS_ACC_REC_LEN, 0, 4, 0, true, false);
        f96_WS_U_TIME = Field.packed(s_WS_U_TIME, 0, 15, 0, true);
        f97_WS_ORIG_DATE = Field.alphanumeric(s_WS_ORIG_DATE, 0, 10, false);
        f98_WS_ORIG_DATE_GRP = Field.group(s_WS_ORIG_DATE, 0, 10);
        f99_WS_ORIG_DATE_DD = Field.zoned(s_WS_ORIG_DATE, 0, 2, 0, false, false, false);
        f100_FILLER = Field.alphanumeric(s_WS_ORIG_DATE, 2, 1, false);
        f101_WS_ORIG_DATE_MM = Field.zoned(s_WS_ORIG_DATE, 3, 2, 0, false, false, false);
        f102_FILLER = Field.alphanumeric(s_WS_ORIG_DATE, 5, 1, false);
        f103_WS_ORIG_DATE_YYYY = Field.zoned(s_WS_ORIG_DATE, 6, 4, 0, false, false, false);
        f104_WS_ORIG_DATE_GRP_X = Field.group(s_WS_ORIG_DATE_GRP_X, 0, 10);
        f105_WS_ORIG_DATE_DD_X = Field.alphanumeric(s_WS_ORIG_DATE_GRP_X, 0, 2, false);
        f106_FILLER = Field.alphanumeric(s_WS_ORIG_DATE_GRP_X, 2, 1, false);
        f107_WS_ORIG_DATE_MM_X = Field.alphanumeric(s_WS_ORIG_DATE_GRP_X, 3, 2, false);
        f108_FILLER = Field.alphanumeric(s_WS_ORIG_DATE_GRP_X, 5, 1, false);
        f109_WS_ORIG_DATE_YYYY_X = Field.alphanumeric(s_WS_ORIG_DATE_GRP_X, 6, 4, false);
        f110_PROCTRAN_AREA = Field.group(s_PROCTRAN_AREA, 0, 99);
        f111_PROC_TRAN_DATA = Field.group(s_PROCTRAN_AREA, 0, 99);
        f112_PROC_TRAN_EYE_CATCHER = Field.alphanumeric(s_PROCTRAN_AREA, 0, 4, false);
        f113_PROC_TRAN_LOGICAL_DELETE_AREA = Field.group(s_PROCTRAN_AREA, 0, 4);
        f114_PROC_TRAN_LOGICAL_DELETE_FLAG = Field.alphanumeric(s_PROCTRAN_AREA, 0, 1, false);
        f115_FILLER = Field.alphanumeric(s_PROCTRAN_AREA, 1, 3, false);
        f116_PROC_TRAN_ID = Field.group(s_PROCTRAN_AREA, 4, 14);
        f117_PROC_TRAN_SORT_CODE = Field.zoned(s_PROCTRAN_AREA, 4, 6, 0, false, false, false);
        f118_PROC_TRAN_NUMBER = Field.zoned(s_PROCTRAN_AREA, 10, 8, 0, false, false, false);
        f119_PROC_TRAN_DATE = Field.zoned(s_PROCTRAN_AREA, 18, 8, 0, false, false, false);
        f120_PROC_TRAN_DATE_GRP = Field.group(s_PROCTRAN_AREA, 18, 8);
        f121_PROC_TRAN_DATE_GRP_YYYY = Field.zoned(s_PROCTRAN_AREA, 18, 4, 0, false, false, false);
        f122_PROC_TRAN_DATE_GRP_MM = Field.zoned(s_PROCTRAN_AREA, 22, 2, 0, false, false, false);
        f123_PROC_TRAN_DATE_GRP_DD = Field.zoned(s_PROCTRAN_AREA, 24, 2, 0, false, false, false);
        f124_PROC_TRAN_TIME = Field.zoned(s_PROCTRAN_AREA, 26, 6, 0, false, false, false);
        f125_PROC_TRAN_TIME_GRP = Field.group(s_PROCTRAN_AREA, 26, 6);
        f126_PROC_TRAN_TIME_GRP_HH = Field.zoned(s_PROCTRAN_AREA, 26, 2, 0, false, false, false);
        f127_PROC_TRAN_TIME_GRP_MM = Field.zoned(s_PROCTRAN_AREA, 28, 2, 0, false, false, false);
        f128_PROC_TRAN_TIME_GRP_SS = Field.zoned(s_PROCTRAN_AREA, 30, 2, 0, false, false, false);
        f129_PROC_TRAN_REF = Field.zoned(s_PROCTRAN_AREA, 32, 12, 0, false, false, false);
        f130_PROC_TRAN_TYPE = Field.alphanumeric(s_PROCTRAN_AREA, 44, 3, false);
        f131_PROC_TRAN_DESC = Field.alphanumeric(s_PROCTRAN_AREA, 47, 40, false);
        f132_PROC_TRAN_DESC_XFR = Field.group(s_PROCTRAN_AREA, 47, 40);
        f133_PROC_TRAN_DESC_XFR_HEADER = Field.alphanumeric(s_PROCTRAN_AREA, 47, 26, false);
        f134_PROC_TRAN_DESC_XFR_SORTCODE = Field.zoned(s_PROCTRAN_AREA, 73, 6, 0, false, false, false);
        f135_PROC_TRAN_DESC_XFR_ACCOUNT = Field.zoned(s_PROCTRAN_AREA, 79, 8, 0, false, false, false);
        f136_PROC_TRAN_DESC_DELACC = Field.group(s_PROCTRAN_AREA, 47, 40);
        f137_PROC_DESC_DELACC_CUSTOMER = Field.zoned(s_PROCTRAN_AREA, 47, 10, 0, false, false, false);
        f138_PROC_DESC_DELACC_ACCTYPE = Field.alphanumeric(s_PROCTRAN_AREA, 57, 8, false);
        f139_PROC_DESC_DELACC_LAST_DD = Field.zoned(s_PROCTRAN_AREA, 65, 2, 0, false, false, false);
        f140_PROC_DESC_DELACC_LAST_MM = Field.zoned(s_PROCTRAN_AREA, 67, 2, 0, false, false, false);
        f141_PROC_DESC_DELACC_LAST_YYYY = Field.zoned(s_PROCTRAN_AREA, 69, 4, 0, false, false, false);
        f142_PROC_DESC_DELACC_NEXT_DD = Field.zoned(s_PROCTRAN_AREA, 73, 2, 0, false, false, false);
        f143_PROC_DESC_DELACC_NEXT_MM = Field.zoned(s_PROCTRAN_AREA, 75, 2, 0, false, false, false);
        f144_PROC_DESC_DELACC_NEXT_YYYY = Field.zoned(s_PROCTRAN_AREA, 77, 4, 0, false, false, false);
        f145_PROC_DESC_DELACC_FOOTER = Field.alphanumeric(s_PROCTRAN_AREA, 81, 6, false);
        f146_PROC_TRAN_DESC_CREACC = Field.group(s_PROCTRAN_AREA, 47, 40);
        f147_PROC_DESC_CREACC_CUSTOMER = Field.zoned(s_PROCTRAN_AREA, 47, 10, 0, false, false, false);
        f148_PROC_DESC_CREACC_ACCTYPE = Field.alphanumeric(s_PROCTRAN_AREA, 57, 8, false);
        f149_PROC_DESC_CREACC_LAST_DD = Field.zoned(s_PROCTRAN_AREA, 65, 2, 0, false, false, false);
        f150_PROC_DESC_CREACC_LAST_MM = Field.zoned(s_PROCTRAN_AREA, 67, 2, 0, false, false, false);
        f151_PROC_DESC_CREACC_LAST_YYYY = Field.zoned(s_PROCTRAN_AREA, 69, 4, 0, false, false, false);
        f152_PROC_DESC_CREACC_NEXT_DD = Field.zoned(s_PROCTRAN_AREA, 73, 2, 0, false, false, false);
        f153_PROC_DESC_CREACC_NEXT_MM = Field.zoned(s_PROCTRAN_AREA, 75, 2, 0, false, false, false);
        f154_PROC_DESC_CREACC_NEXT_YYYY = Field.zoned(s_PROCTRAN_AREA, 77, 4, 0, false, false, false);
        f155_PROC_DESC_CREACC_FOOTER = Field.alphanumeric(s_PROCTRAN_AREA, 81, 6, false);
        f156_PROC_TRAN_DESC_DELCUS = Field.group(s_PROCTRAN_AREA, 47, 40);
        f157_PROC_DESC_DELCUS_SORTCODE = Field.zoned(s_PROCTRAN_AREA, 47, 6, 0, false, false, false);
        f158_PROC_DESC_DELCUS_CUSTOMER = Field.zoned(s_PROCTRAN_AREA, 53, 10, 0, false, false, false);
        f159_PROC_DESC_DELCUS_NAME = Field.alphanumeric(s_PROCTRAN_AREA, 63, 14, false);
        f160_PROC_DESC_DELCUS_DOB_YYYY = Field.zoned(s_PROCTRAN_AREA, 77, 4, 0, false, false, false);
        f161_PROC_DESC_DELCUS_FILLER = Field.alphanumeric(s_PROCTRAN_AREA, 81, 1, false);
        f162_PROC_DESC_DELCUS_DOB_MM = Field.zoned(s_PROCTRAN_AREA, 82, 2, 0, false, false, false);
        f163_PROC_DESC_DELCUS_FILLER2 = Field.alphanumeric(s_PROCTRAN_AREA, 84, 1, false);
        f164_PROC_DESC_DELCUS_DOB_DD = Field.zoned(s_PROCTRAN_AREA, 85, 2, 0, false, false, false);
        f165_PROC_TRAN_DESC_CRECUS = Field.group(s_PROCTRAN_AREA, 47, 40);
        f166_PROC_DESC_CRECUS_SORTCODE = Field.zoned(s_PROCTRAN_AREA, 47, 6, 0, false, false, false);
        f167_PROC_DESC_CRECUS_CUSTOMER = Field.zoned(s_PROCTRAN_AREA, 53, 10, 0, false, false, false);
        f168_PROC_DESC_CRECUS_NAME = Field.alphanumeric(s_PROCTRAN_AREA, 63, 14, false);
        f169_PROC_DESC_CRECUS_DOB_YYYY = Field.zoned(s_PROCTRAN_AREA, 77, 4, 0, false, false, false);
        f170_PROC_DESC_CRECUS_FILLER = Field.alphanumeric(s_PROCTRAN_AREA, 81, 1, false);
        f171_PROC_DESC_CRECUS_DOB_MM = Field.zoned(s_PROCTRAN_AREA, 82, 2, 0, false, false, false);
        f172_PROC_DESC_CRECUS_FILLER2 = Field.alphanumeric(s_PROCTRAN_AREA, 84, 1, false);
        f173_PROC_DESC_CRECUS_DOB_DD = Field.zoned(s_PROCTRAN_AREA, 85, 2, 0, false, false, false);
        f174_PROC_TRAN_AMOUNT = Field.zoned(s_PROCTRAN_AREA, 87, 12, 2, true, false, false);
        f175_WS_PASSED_DATA = Field.group(s_WS_PASSED_DATA, 0, 13);
        f176_WS_TEST_KEY = Field.alphanumeric(s_WS_PASSED_DATA, 0, 4, false);
        f177_WS_SORT_CODE = Field.zoned(s_WS_PASSED_DATA, 4, 6, 0, false, false, false);
        f178_WS_CUSTOMER_RANGE = Field.group(s_WS_PASSED_DATA, 10, 3);
        f179_WS_CUSTOMER_RANGE_TOP = Field.alphanumeric(s_WS_PASSED_DATA, 10, 1, false);
        f180_WS_CUSTOMER_RANGE_MIDDLE = Field.alphanumeric(s_WS_PASSED_DATA, 11, 1, false);
        f181_WS_CUSTOMER_RANGE_BOTTOM = Field.alphanumeric(s_WS_PASSED_DATA, 12, 1, false);
        f182_PROCTRAN_RIDFLD = Field.binary(s_PROCTRAN_RIDFLD, 0, 8, 0, true, false);
        f183_SQLCODE_DISPLAY = Field.zoned(s_SQLCODE_DISPLAY, 0, 8, 0, true, true, true);
        f184_MY_ABEND_CODE = Field.alphanumeric(s_MY_ABEND_CODE, 0, 4, false);
        f185_WS_STORM_DRAIN = Field.alphanumeric(s_WS_STORM_DRAIN, 0, 1, false);
        f186_STORM_DRAIN_CONDITION = Field.alphanumeric(s_STORM_DRAIN_CONDITION, 0, 20, false);
        f187_NUMERIC_AMOUNT_DISPLAY = Field.numericEdited(s_NUMERIC_AMOUNT_DISPLAY, 0, 14, "+9999999999.99", false);
        f188_WS_TIME_DATA = Field.group(s_WS_TIME_DATA, 0, 6);
        f189_WS_TIME_NOW = Field.zoned(s_WS_TIME_DATA, 0, 6, 0, false, false, false);
        f190_WS_TIME_NOW_GRP = Field.group(s_WS_TIME_DATA, 0, 6);
        f191_WS_TIME_NOW_GRP_HH = Field.zoned(s_WS_TIME_DATA, 0, 2, 0, false, false, false);
        f192_WS_TIME_NOW_GRP_MM = Field.zoned(s_WS_TIME_DATA, 2, 2, 0, false, false, false);
        f193_WS_TIME_NOW_GRP_SS = Field.zoned(s_WS_TIME_DATA, 4, 2, 0, false, false, false);
        f194_WS_ABEND_PGM = Field.alphanumeric(s_WS_ABEND_PGM, 0, 8, false);
        f195_ABNDINFO_REC = Field.group(s_ABNDINFO_REC, 0, 681);
        f196_ABND_VSAM_KEY = Field.group(s_ABNDINFO_REC, 0, 12);
        f197_ABND_UTIME_KEY = Field.packed(s_ABNDINFO_REC, 0, 15, 0, true);
        f198_ABND_TASKNO_KEY = Field.zoned(s_ABNDINFO_REC, 8, 4, 0, false, false, false);
        f199_ABND_APPLID = Field.alphanumeric(s_ABNDINFO_REC, 12, 8, false);
        f200_ABND_TRANID = Field.alphanumeric(s_ABNDINFO_REC, 20, 4, false);
        f201_ABND_DATE = Field.alphanumeric(s_ABNDINFO_REC, 24, 10, false);
        f202_ABND_TIME = Field.alphanumeric(s_ABNDINFO_REC, 34, 8, false);
        f203_ABND_CODE = Field.alphanumeric(s_ABNDINFO_REC, 42, 4, false);
        f204_ABND_PROGRAM = Field.alphanumeric(s_ABNDINFO_REC, 46, 8, false);
        f205_ABND_RESPCODE = Field.zoned(s_ABNDINFO_REC, 54, 8, 0, true, true, true);
        f206_ABND_RESP2CODE = Field.zoned(s_ABNDINFO_REC, 63, 8, 0, true, true, true);
        f207_ABND_SQLCODE = Field.zoned(s_ABNDINFO_REC, 72, 8, 0, true, true, true);
        f208_ABND_FREEFORM = Field.alphanumeric(s_ABNDINFO_REC, 81, 600, false);
        f209_WS_SUFFICIENT_FUNDS = Field.alphanumeric(s_WS_SUFFICIENT_FUNDS, 0, 1, false);
        f210_WS_DIFFERENCE = Field.zoned(s_WS_DIFFERENCE, 0, 12, 2, true, false, false);
        f211_DFHCOMMAREA = Field.group(s_DFHCOMMAREA, 0, 92);
        f212_COMM_ACCNO = Field.alphanumeric(s_DFHCOMMAREA, 0, 8, false);
        f213_COMM_AMT = Field.zoned(s_DFHCOMMAREA, 8, 12, 2, true, false, false);
        f214_COMM_SORTC = Field.zoned(s_DFHCOMMAREA, 20, 6, 0, false, false, false);
        f215_COMM_AV_BAL = Field.zoned(s_DFHCOMMAREA, 26, 12, 2, true, false, false);
        f216_COMM_ACT_BAL = Field.zoned(s_DFHCOMMAREA, 38, 12, 2, true, false, false);
        f217_COMM_ORIGIN = Field.group(s_DFHCOMMAREA, 50, 40);
        f218_COMM_APPLID = Field.alphanumeric(s_DFHCOMMAREA, 50, 8, false);
        f219_COMM_USERID = Field.alphanumeric(s_DFHCOMMAREA, 58, 8, false);
        f220_COMM_FACILITY_NAME = Field.alphanumeric(s_DFHCOMMAREA, 66, 8, false);
        f221_COMM_NETWRK_ID = Field.alphanumeric(s_DFHCOMMAREA, 74, 8, false);
        f222_COMM_FACILTYPE = Field.binary(s_DFHCOMMAREA, 82, 8, 0, true, false);
        f223_FILLER = Field.alphanumeric(s_DFHCOMMAREA, 86, 4, false);
        f224_COMM_SUCCESS = Field.alphanumeric(s_DFHCOMMAREA, 90, 1, false);
        f225_COMM_FAIL_CODE = Field.alphanumeric(s_DFHCOMMAREA, 91, 1, false);
        f226_DFHEIBLK = Field.group(s_DFHEIBLK, 0, 85);
        f227_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
        f228_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
        f229_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
        f230_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
        f231_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
        f232_DFHEIGDI = Field.binary(s_DFHEIBLK, 20, 4, 0, true, false);
        f233_EIBCPOSN = Field.binary(s_DFHEIBLK, 22, 4, 0, true, false);
        f234_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
        f235_EIBAID = Field.alphanumeric(s_DFHEIBLK, 26, 1, false);
        f236_EIBFN = Field.alphanumeric(s_DFHEIBLK, 27, 2, false);
        f237_EIBRCODE = Field.alphanumeric(s_DFHEIBLK, 29, 6, false);
        f238_EIBDS = Field.alphanumeric(s_DFHEIBLK, 35, 8, false);
        f239_EIBREQID = Field.alphanumeric(s_DFHEIBLK, 43, 8, false);
        f240_EIBRSRCE = Field.alphanumeric(s_DFHEIBLK, 51, 8, false);
        f241_EIBSYNC = Field.alphanumeric(s_DFHEIBLK, 59, 1, false);
        f242_EIBFREE = Field.alphanumeric(s_DFHEIBLK, 60, 1, false);
        f243_EIBRECV = Field.alphanumeric(s_DFHEIBLK, 61, 1, false);
        f244_EIBSEND = Field.alphanumeric(s_DFHEIBLK, 62, 1, false);
        f245_EIBATT = Field.alphanumeric(s_DFHEIBLK, 63, 1, false);
        f246_EIBEOC = Field.alphanumeric(s_DFHEIBLK, 64, 1, false);
        f247_EIBFMH = Field.alphanumeric(s_DFHEIBLK, 65, 1, false);
        f248_EIBCOMPL = Field.alphanumeric(s_DFHEIBLK, 66, 1, false);
        f249_EIBSIG = Field.alphanumeric(s_DFHEIBLK, 67, 1, false);
        f250_EIBCONF = Field.alphanumeric(s_DFHEIBLK, 68, 1, false);
        f251_EIBERR = Field.alphanumeric(s_DFHEIBLK, 69, 1, false);
        f252_EIBERRCD = Field.alphanumeric(s_DFHEIBLK, 70, 4, false);
        f253_EIBSYNRB = Field.alphanumeric(s_DFHEIBLK, 74, 1, false);
        f254_EIBNODAT = Field.alphanumeric(s_DFHEIBLK, 75, 1, false);
        f255_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
        f256_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
        f257_EIBRLDBK = Field.alphanumeric(s_DFHEIBLK, 84, 1, false);
        f258_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        System.arraycopy(IMAGE_s_SORTCODE, 0, s_SORTCODE.bytes, 0, IMAGE_s_SORTCODE.length);
        System.arraycopy(IMAGE_s_SYSIDERR_RETRY, 0, s_SYSIDERR_RETRY.bytes, 0, IMAGE_s_SYSIDERR_RETRY.length);
        System.arraycopy(IMAGE_s_HOST_ACCOUNT_ROW, 0, s_HOST_ACCOUNT_ROW.bytes, 0, IMAGE_s_HOST_ACCOUNT_ROW.length);
        System.arraycopy(IMAGE_s_HOST_PROCTRAN_ROW, 0, s_HOST_PROCTRAN_ROW.bytes, 0, IMAGE_s_HOST_PROCTRAN_ROW.length);
        System.arraycopy(IMAGE_s_SQLCA, 0, s_SQLCA.bytes, 0, IMAGE_s_SQLCA.length);
        System.arraycopy(IMAGE_s_WS_CICS_WORK_AREA, 0, s_WS_CICS_WORK_AREA.bytes, 0, IMAGE_s_WS_CICS_WORK_AREA.length);
        System.arraycopy(IMAGE_s_FILE_RETRY, 0, s_FILE_RETRY.bytes, 0, IMAGE_s_FILE_RETRY.length);
        System.arraycopy(IMAGE_s_WS_EXIT_RETRY_LOOP, 0, s_WS_EXIT_RETRY_LOOP.bytes, 0, IMAGE_s_WS_EXIT_RETRY_LOOP.length);
        System.arraycopy(IMAGE_s_DB2_DATE_REFORMAT, 0, s_DB2_DATE_REFORMAT.bytes, 0, IMAGE_s_DB2_DATE_REFORMAT.length);
        System.arraycopy(IMAGE_s_DATA_STORE_TYPE, 0, s_DATA_STORE_TYPE.bytes, 0, IMAGE_s_DATA_STORE_TYPE.length);
        System.arraycopy(IMAGE_s_WS_ACC_DATA, 0, s_WS_ACC_DATA.bytes, 0, IMAGE_s_WS_ACC_DATA.length);
        System.arraycopy(IMAGE_s_WS_EIBTASKN12, 0, s_WS_EIBTASKN12.bytes, 0, IMAGE_s_WS_EIBTASKN12.length);
        System.arraycopy(IMAGE_s_WS_SQLCODE_DISP, 0, s_WS_SQLCODE_DISP.bytes, 0, IMAGE_s_WS_SQLCODE_DISP.length);
        System.arraycopy(IMAGE_s_DESIRED_ACC_KEY, 0, s_DESIRED_ACC_KEY.bytes, 0, IMAGE_s_DESIRED_ACC_KEY.length);
        System.arraycopy(IMAGE_s_NEW_ACCOUNT_AVAILABLE_BALANCE, 0, s_NEW_ACCOUNT_AVAILABLE_BALANCE.bytes, 0, IMAGE_s_NEW_ACCOUNT_AVAILABLE_BALANCE.length);
        System.arraycopy(IMAGE_s_NEW_ACCOUNT_ACTUAL_BALANCE, 0, s_NEW_ACCOUNT_ACTUAL_BALANCE.bytes, 0, IMAGE_s_NEW_ACCOUNT_ACTUAL_BALANCE.length);
        System.arraycopy(IMAGE_s_WS_ACC_REC_LEN, 0, s_WS_ACC_REC_LEN.bytes, 0, IMAGE_s_WS_ACC_REC_LEN.length);
        System.arraycopy(IMAGE_s_WS_U_TIME, 0, s_WS_U_TIME.bytes, 0, IMAGE_s_WS_U_TIME.length);
        System.arraycopy(IMAGE_s_WS_ORIG_DATE, 0, s_WS_ORIG_DATE.bytes, 0, IMAGE_s_WS_ORIG_DATE.length);
        System.arraycopy(IMAGE_s_WS_ORIG_DATE_GRP_X, 0, s_WS_ORIG_DATE_GRP_X.bytes, 0, IMAGE_s_WS_ORIG_DATE_GRP_X.length);
        System.arraycopy(IMAGE_s_PROCTRAN_AREA, 0, s_PROCTRAN_AREA.bytes, 0, IMAGE_s_PROCTRAN_AREA.length);
        System.arraycopy(IMAGE_s_WS_PASSED_DATA, 0, s_WS_PASSED_DATA.bytes, 0, IMAGE_s_WS_PASSED_DATA.length);
        System.arraycopy(IMAGE_s_PROCTRAN_RIDFLD, 0, s_PROCTRAN_RIDFLD.bytes, 0, IMAGE_s_PROCTRAN_RIDFLD.length);
        System.arraycopy(IMAGE_s_SQLCODE_DISPLAY, 0, s_SQLCODE_DISPLAY.bytes, 0, IMAGE_s_SQLCODE_DISPLAY.length);
        System.arraycopy(IMAGE_s_MY_ABEND_CODE, 0, s_MY_ABEND_CODE.bytes, 0, IMAGE_s_MY_ABEND_CODE.length);
        System.arraycopy(IMAGE_s_WS_STORM_DRAIN, 0, s_WS_STORM_DRAIN.bytes, 0, IMAGE_s_WS_STORM_DRAIN.length);
        System.arraycopy(IMAGE_s_STORM_DRAIN_CONDITION, 0, s_STORM_DRAIN_CONDITION.bytes, 0, IMAGE_s_STORM_DRAIN_CONDITION.length);
        System.arraycopy(IMAGE_s_NUMERIC_AMOUNT_DISPLAY, 0, s_NUMERIC_AMOUNT_DISPLAY.bytes, 0, IMAGE_s_NUMERIC_AMOUNT_DISPLAY.length);
        System.arraycopy(IMAGE_s_WS_TIME_DATA, 0, s_WS_TIME_DATA.bytes, 0, IMAGE_s_WS_TIME_DATA.length);
        System.arraycopy(IMAGE_s_WS_ABEND_PGM, 0, s_WS_ABEND_PGM.bytes, 0, IMAGE_s_WS_ABEND_PGM.length);
        System.arraycopy(IMAGE_s_ABNDINFO_REC, 0, s_ABNDINFO_REC.bytes, 0, IMAGE_s_ABNDINFO_REC.length);
        System.arraycopy(IMAGE_s_WS_SUFFICIENT_FUNDS, 0, s_WS_SUFFICIENT_FUNDS.bytes, 0, IMAGE_s_WS_SUFFICIENT_FUNDS.length);
        System.arraycopy(IMAGE_s_WS_DIFFERENCE, 0, s_WS_DIFFERENCE.bytes, 0, IMAGE_s_WS_DIFFERENCE.length);
        System.arraycopy(IMAGE_s_DFHCOMMAREA, 0, s_DFHCOMMAREA.bytes, 0, IMAGE_s_DFHCOMMAREA.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
        Cobol.moveFigurative(Figurative.ZEROS, f187_NUMERIC_AMOUNT_DISPLAY, CS);
        performDepth = 0;
        try {
            perform(0, 23);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f258_GG_RETURN_CODE, CS).intValue();
    }

    public void executeDbcrfun() {
        runBatch(List.of(), null);
    }

    /** One task of the program: the EIB and COMMAREA from the task, then the PROCEDURE DIVISION. */
    public void runTask(CicsTask task) {
        boolean truncBefore = Cobol.swapTruncBinary(true);  // TRUNC(STD)
        try {
            this.task = task;
            DetSql.closeAll();  // a task's cursors are its own
            caBack = () -> { };
            handlers.clear();
            heldKey.clear();
            System.arraycopy(IMAGE_s_SORTCODE, 0, s_SORTCODE.bytes, 0, IMAGE_s_SORTCODE.length);
            System.arraycopy(IMAGE_s_SYSIDERR_RETRY, 0, s_SYSIDERR_RETRY.bytes, 0, IMAGE_s_SYSIDERR_RETRY.length);
            System.arraycopy(IMAGE_s_HOST_ACCOUNT_ROW, 0, s_HOST_ACCOUNT_ROW.bytes, 0, IMAGE_s_HOST_ACCOUNT_ROW.length);
            System.arraycopy(IMAGE_s_HOST_PROCTRAN_ROW, 0, s_HOST_PROCTRAN_ROW.bytes, 0, IMAGE_s_HOST_PROCTRAN_ROW.length);
            System.arraycopy(IMAGE_s_SQLCA, 0, s_SQLCA.bytes, 0, IMAGE_s_SQLCA.length);
            System.arraycopy(IMAGE_s_WS_CICS_WORK_AREA, 0, s_WS_CICS_WORK_AREA.bytes, 0, IMAGE_s_WS_CICS_WORK_AREA.length);
            System.arraycopy(IMAGE_s_FILE_RETRY, 0, s_FILE_RETRY.bytes, 0, IMAGE_s_FILE_RETRY.length);
            System.arraycopy(IMAGE_s_WS_EXIT_RETRY_LOOP, 0, s_WS_EXIT_RETRY_LOOP.bytes, 0, IMAGE_s_WS_EXIT_RETRY_LOOP.length);
            System.arraycopy(IMAGE_s_DB2_DATE_REFORMAT, 0, s_DB2_DATE_REFORMAT.bytes, 0, IMAGE_s_DB2_DATE_REFORMAT.length);
            System.arraycopy(IMAGE_s_DATA_STORE_TYPE, 0, s_DATA_STORE_TYPE.bytes, 0, IMAGE_s_DATA_STORE_TYPE.length);
            System.arraycopy(IMAGE_s_WS_ACC_DATA, 0, s_WS_ACC_DATA.bytes, 0, IMAGE_s_WS_ACC_DATA.length);
            System.arraycopy(IMAGE_s_WS_EIBTASKN12, 0, s_WS_EIBTASKN12.bytes, 0, IMAGE_s_WS_EIBTASKN12.length);
            System.arraycopy(IMAGE_s_WS_SQLCODE_DISP, 0, s_WS_SQLCODE_DISP.bytes, 0, IMAGE_s_WS_SQLCODE_DISP.length);
            System.arraycopy(IMAGE_s_DESIRED_ACC_KEY, 0, s_DESIRED_ACC_KEY.bytes, 0, IMAGE_s_DESIRED_ACC_KEY.length);
            System.arraycopy(IMAGE_s_NEW_ACCOUNT_AVAILABLE_BALANCE, 0, s_NEW_ACCOUNT_AVAILABLE_BALANCE.bytes, 0, IMAGE_s_NEW_ACCOUNT_AVAILABLE_BALANCE.length);
            System.arraycopy(IMAGE_s_NEW_ACCOUNT_ACTUAL_BALANCE, 0, s_NEW_ACCOUNT_ACTUAL_BALANCE.bytes, 0, IMAGE_s_NEW_ACCOUNT_ACTUAL_BALANCE.length);
            System.arraycopy(IMAGE_s_WS_ACC_REC_LEN, 0, s_WS_ACC_REC_LEN.bytes, 0, IMAGE_s_WS_ACC_REC_LEN.length);
            System.arraycopy(IMAGE_s_WS_U_TIME, 0, s_WS_U_TIME.bytes, 0, IMAGE_s_WS_U_TIME.length);
            System.arraycopy(IMAGE_s_WS_ORIG_DATE, 0, s_WS_ORIG_DATE.bytes, 0, IMAGE_s_WS_ORIG_DATE.length);
            System.arraycopy(IMAGE_s_WS_ORIG_DATE_GRP_X, 0, s_WS_ORIG_DATE_GRP_X.bytes, 0, IMAGE_s_WS_ORIG_DATE_GRP_X.length);
            System.arraycopy(IMAGE_s_PROCTRAN_AREA, 0, s_PROCTRAN_AREA.bytes, 0, IMAGE_s_PROCTRAN_AREA.length);
            System.arraycopy(IMAGE_s_WS_PASSED_DATA, 0, s_WS_PASSED_DATA.bytes, 0, IMAGE_s_WS_PASSED_DATA.length);
            System.arraycopy(IMAGE_s_PROCTRAN_RIDFLD, 0, s_PROCTRAN_RIDFLD.bytes, 0, IMAGE_s_PROCTRAN_RIDFLD.length);
            System.arraycopy(IMAGE_s_SQLCODE_DISPLAY, 0, s_SQLCODE_DISPLAY.bytes, 0, IMAGE_s_SQLCODE_DISPLAY.length);
            System.arraycopy(IMAGE_s_MY_ABEND_CODE, 0, s_MY_ABEND_CODE.bytes, 0, IMAGE_s_MY_ABEND_CODE.length);
            System.arraycopy(IMAGE_s_WS_STORM_DRAIN, 0, s_WS_STORM_DRAIN.bytes, 0, IMAGE_s_WS_STORM_DRAIN.length);
            System.arraycopy(IMAGE_s_STORM_DRAIN_CONDITION, 0, s_STORM_DRAIN_CONDITION.bytes, 0, IMAGE_s_STORM_DRAIN_CONDITION.length);
            System.arraycopy(IMAGE_s_NUMERIC_AMOUNT_DISPLAY, 0, s_NUMERIC_AMOUNT_DISPLAY.bytes, 0, IMAGE_s_NUMERIC_AMOUNT_DISPLAY.length);
            System.arraycopy(IMAGE_s_WS_TIME_DATA, 0, s_WS_TIME_DATA.bytes, 0, IMAGE_s_WS_TIME_DATA.length);
            System.arraycopy(IMAGE_s_WS_ABEND_PGM, 0, s_WS_ABEND_PGM.bytes, 0, IMAGE_s_WS_ABEND_PGM.length);
            System.arraycopy(IMAGE_s_ABNDINFO_REC, 0, s_ABNDINFO_REC.bytes, 0, IMAGE_s_ABNDINFO_REC.length);
            System.arraycopy(IMAGE_s_WS_SUFFICIENT_FUNDS, 0, s_WS_SUFFICIENT_FUNDS.bytes, 0, IMAGE_s_WS_SUFFICIENT_FUNDS.length);
            System.arraycopy(IMAGE_s_WS_DIFFERENCE, 0, s_WS_DIFFERENCE.bytes, 0, IMAGE_s_WS_DIFFERENCE.length);
            System.arraycopy(IMAGE_s_DFHCOMMAREA, 0, s_DFHCOMMAREA.bytes, 0, IMAGE_s_DFHCOMMAREA.length);
            System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
            System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
            Cobol.moveFigurative(Figurative.ZEROS, f187_NUMERIC_AMOUNT_DISPLAY, CS);
            Cobol.move(task.transid(), f229_EIBTRNID, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f228_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f227_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (ca instanceof Bnk1craSubpgmParms x) {
                in_Bnk1craSubpgmParms(x, s_DFHCOMMAREA, 0);
                caBack = () -> fill_Bnk1craSubpgmParms(x, s_DFHCOMMAREA, 0);
                calen = cx(task, 92);
            } else if (ca instanceof AbndprocAbndinfoRec x) {
                in_AbndprocAbndinfoRec(x, s_DFHCOMMAREA, 0);
                caBack = () -> fill_AbndprocAbndinfoRec(x, s_DFHCOMMAREA, 0);
                calen = cx(task, 681);
            }
            Cobol.store(f234_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                perform(0, 23);
            } catch (Goback g) {
                // RETURN / XCTL / an abend ended the program
            }
            if (!task.ended()) {
                caBack.run();
                task.returnTransid(null, null);  // a GOBACK is a RETURN
            }
        } finally {
            Cobol.swapTruncBinary(truncBefore);
        }
    }

    public Bnk1craSubpgmParms handleLink(Bnk1craSubpgmParms request) {
        throw new UnsupportedOperationException("handleLink: this port runs as runTask");
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
        try {
            DetSql.closeAll();  // a step's cursors are its own
            System.arraycopy(IMAGE_s_SORTCODE, 0, s_SORTCODE.bytes, 0, IMAGE_s_SORTCODE.length);
            System.arraycopy(IMAGE_s_SYSIDERR_RETRY, 0, s_SYSIDERR_RETRY.bytes, 0, IMAGE_s_SYSIDERR_RETRY.length);
            System.arraycopy(IMAGE_s_HOST_ACCOUNT_ROW, 0, s_HOST_ACCOUNT_ROW.bytes, 0, IMAGE_s_HOST_ACCOUNT_ROW.length);
            System.arraycopy(IMAGE_s_HOST_PROCTRAN_ROW, 0, s_HOST_PROCTRAN_ROW.bytes, 0, IMAGE_s_HOST_PROCTRAN_ROW.length);
            System.arraycopy(IMAGE_s_SQLCA, 0, s_SQLCA.bytes, 0, IMAGE_s_SQLCA.length);
            System.arraycopy(IMAGE_s_WS_CICS_WORK_AREA, 0, s_WS_CICS_WORK_AREA.bytes, 0, IMAGE_s_WS_CICS_WORK_AREA.length);
            System.arraycopy(IMAGE_s_FILE_RETRY, 0, s_FILE_RETRY.bytes, 0, IMAGE_s_FILE_RETRY.length);
            System.arraycopy(IMAGE_s_WS_EXIT_RETRY_LOOP, 0, s_WS_EXIT_RETRY_LOOP.bytes, 0, IMAGE_s_WS_EXIT_RETRY_LOOP.length);
            System.arraycopy(IMAGE_s_DB2_DATE_REFORMAT, 0, s_DB2_DATE_REFORMAT.bytes, 0, IMAGE_s_DB2_DATE_REFORMAT.length);
            System.arraycopy(IMAGE_s_DATA_STORE_TYPE, 0, s_DATA_STORE_TYPE.bytes, 0, IMAGE_s_DATA_STORE_TYPE.length);
            System.arraycopy(IMAGE_s_WS_ACC_DATA, 0, s_WS_ACC_DATA.bytes, 0, IMAGE_s_WS_ACC_DATA.length);
            System.arraycopy(IMAGE_s_WS_EIBTASKN12, 0, s_WS_EIBTASKN12.bytes, 0, IMAGE_s_WS_EIBTASKN12.length);
            System.arraycopy(IMAGE_s_WS_SQLCODE_DISP, 0, s_WS_SQLCODE_DISP.bytes, 0, IMAGE_s_WS_SQLCODE_DISP.length);
            System.arraycopy(IMAGE_s_DESIRED_ACC_KEY, 0, s_DESIRED_ACC_KEY.bytes, 0, IMAGE_s_DESIRED_ACC_KEY.length);
            System.arraycopy(IMAGE_s_NEW_ACCOUNT_AVAILABLE_BALANCE, 0, s_NEW_ACCOUNT_AVAILABLE_BALANCE.bytes, 0, IMAGE_s_NEW_ACCOUNT_AVAILABLE_BALANCE.length);
            System.arraycopy(IMAGE_s_NEW_ACCOUNT_ACTUAL_BALANCE, 0, s_NEW_ACCOUNT_ACTUAL_BALANCE.bytes, 0, IMAGE_s_NEW_ACCOUNT_ACTUAL_BALANCE.length);
            System.arraycopy(IMAGE_s_WS_ACC_REC_LEN, 0, s_WS_ACC_REC_LEN.bytes, 0, IMAGE_s_WS_ACC_REC_LEN.length);
            System.arraycopy(IMAGE_s_WS_U_TIME, 0, s_WS_U_TIME.bytes, 0, IMAGE_s_WS_U_TIME.length);
            System.arraycopy(IMAGE_s_WS_ORIG_DATE, 0, s_WS_ORIG_DATE.bytes, 0, IMAGE_s_WS_ORIG_DATE.length);
            System.arraycopy(IMAGE_s_WS_ORIG_DATE_GRP_X, 0, s_WS_ORIG_DATE_GRP_X.bytes, 0, IMAGE_s_WS_ORIG_DATE_GRP_X.length);
            System.arraycopy(IMAGE_s_PROCTRAN_AREA, 0, s_PROCTRAN_AREA.bytes, 0, IMAGE_s_PROCTRAN_AREA.length);
            System.arraycopy(IMAGE_s_WS_PASSED_DATA, 0, s_WS_PASSED_DATA.bytes, 0, IMAGE_s_WS_PASSED_DATA.length);
            System.arraycopy(IMAGE_s_PROCTRAN_RIDFLD, 0, s_PROCTRAN_RIDFLD.bytes, 0, IMAGE_s_PROCTRAN_RIDFLD.length);
            System.arraycopy(IMAGE_s_SQLCODE_DISPLAY, 0, s_SQLCODE_DISPLAY.bytes, 0, IMAGE_s_SQLCODE_DISPLAY.length);
            System.arraycopy(IMAGE_s_MY_ABEND_CODE, 0, s_MY_ABEND_CODE.bytes, 0, IMAGE_s_MY_ABEND_CODE.length);
            System.arraycopy(IMAGE_s_WS_STORM_DRAIN, 0, s_WS_STORM_DRAIN.bytes, 0, IMAGE_s_WS_STORM_DRAIN.length);
            System.arraycopy(IMAGE_s_STORM_DRAIN_CONDITION, 0, s_STORM_DRAIN_CONDITION.bytes, 0, IMAGE_s_STORM_DRAIN_CONDITION.length);
            System.arraycopy(IMAGE_s_NUMERIC_AMOUNT_DISPLAY, 0, s_NUMERIC_AMOUNT_DISPLAY.bytes, 0, IMAGE_s_NUMERIC_AMOUNT_DISPLAY.length);
            System.arraycopy(IMAGE_s_WS_TIME_DATA, 0, s_WS_TIME_DATA.bytes, 0, IMAGE_s_WS_TIME_DATA.length);
            System.arraycopy(IMAGE_s_WS_ABEND_PGM, 0, s_WS_ABEND_PGM.bytes, 0, IMAGE_s_WS_ABEND_PGM.length);
            System.arraycopy(IMAGE_s_ABNDINFO_REC, 0, s_ABNDINFO_REC.bytes, 0, IMAGE_s_ABNDINFO_REC.length);
            System.arraycopy(IMAGE_s_WS_SUFFICIENT_FUNDS, 0, s_WS_SUFFICIENT_FUNDS.bytes, 0, IMAGE_s_WS_SUFFICIENT_FUNDS.length);
            System.arraycopy(IMAGE_s_WS_DIFFERENCE, 0, s_WS_DIFFERENCE.bytes, 0, IMAGE_s_WS_DIFFERENCE.length);
            System.arraycopy(IMAGE_s_DFHCOMMAREA, 0, s_DFHCOMMAREA.bytes, 0, IMAGE_s_DFHCOMMAREA.length);
            System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
            System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
            Cobol.moveFigurative(Figurative.ZEROS, f187_NUMERIC_AMOUNT_DISPLAY, CS);
            byte[] parmText = (parm == null ? "" : parm).getBytes(CS);
            s_DFHCOMMAREA.bytes[0] = (byte) (parmText.length >> 8);
            s_DFHCOMMAREA.bytes[1] = (byte) parmText.length;
            System.arraycopy(parmText, 0, s_DFHCOMMAREA.bytes, 2, Math.min(parmText.length, s_DFHCOMMAREA.bytes.length - 2));
            try {
                perform(0, 23);
            } catch (Goback g) {
                // the program ended
            }
            return Cobol.num(f258_GG_RETURN_CODE, CS).intValue();
        } finally {
            Cobol.swapTruncBinary(truncBefore);
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
                if (next >= 24) {
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
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** PREMIERE. */
    private int p0() {

        return 1;
    }

    /** A010. */
    private int p1() {
        // MOVE 'N' TO COMM-SUCCESS
        Cobol.move("N", f224_COMM_SUCCESS, CS);
        // MOVE '0' TO COMM-FAIL-CODE
        Cobol.move("0", f225_COMM_FAIL_CODE, CS);
        // EXEC CICS HANDLE ABEND LABEL(ABEND-HANDLING) END-EXEC
        task.handleAbend("ABEND-HANDLING");
        // MOVE SORTCODE TO COMM-SORTC
        Cobol.move(f1_SORTCODE, f214_COMM_SORTC, CS);
        // MOVE SORTCODE TO DESIRED-SORT-CODE
        Cobol.move(f1_SORTCODE, f91_DESIRED_SORT_CODE, CS);
        // PERFORM UPDATE-ACCOUNT-DB2
        perform(3, 5);
        // PERFORM GET-ME-OUT-OF-HERE
        perform(12, 14);
        return 2;
    }

    /** A999. */
    private int p2() {
        // EXIT
        return 3;
    }

    /** UPDATE-ACCOUNT-DB2. */
    private int p3() {

        return 4;
    }

    /** UAD010. */
    private int p4() {
        // MOVE COMM-ACCNO TO DESIRED-ACC-NO
        Cobol.move(f212_COMM_ACCNO, f92_DESIRED_ACC_NO, CS);
        // MOVE DESIRED-SORT-CODE TO HV-ACCOUNT-SORTCODE
        Cobol.move(f91_DESIRED_SORT_CODE, f7_HV_ACCOUNT_SORTCODE, CS);
        // MOVE DESIRED-ACC-NO TO HV-ACCOUNT-ACC-NO
        Cobol.move(f92_DESIRED_ACC_NO, f8_HV_ACCOUNT_ACC_NO, CS);
        // EXEC SQL SELECT ACCOUNT_EYECATCHER, ACCOUNT_CUSTOMER_NUMBER, ACCOUNT_SORTCODE, ACCOUNT_NUMBER, ACCOUNT_TYPE, ACCOUNT_INTEREST_RATE, ACCOUNT_OPENED, AC
        java.util.Map<String, Object> sqlParams1 = new java.util.HashMap<>();
        sqlParams1.put("hvAccountSortcode", DetSql.charIn(f7_HV_ACCOUNT_SORTCODE, CS));
        sqlParams1.put("hvAccountAccNo", DetSql.charIn(f8_HV_ACCOUNT_ACC_NO, CS));
        java.util.Map<String, Object> sqlRow2 = DetSql.selectOne(f27_SQLCA, () -> accountRepository.selectL245Dbcrfun(sqlParams1), CS);
        if (sqlRow2 != null) {
            DetSql.into(f27_SQLCA, sqlRow2, "XXXXXNXNXXNN", new Field[] {f4_HV_ACCOUNT_EYECATCHER, f5_HV_ACCOUNT_CUST_NO, f7_HV_ACCOUNT_SORTCODE, f8_HV_ACCOUNT_ACC_NO, f9_HV_ACCOUNT_ACC_TYPE, f10_HV_ACCOUNT_INT_RATE, f11_HV_ACCOUNT_OPENED, f12_HV_ACCOUNT_OVERDRAFT_LIM, f13_HV_ACCOUNT_LAST_STMT, f14_HV_ACCOUNT_NEXT_STMT, f15_HV_ACCOUNT_AVAIL_BAL, f16_HV_ACCOUNT_ACTUAL_BAL}, new Field[] {null, null, null, null, null, null, null, null, null, null, null, null}, null, CS);
        }
        // IF SQLCODE NOT = 0
        if (!(Cobol.num(f30_SQLCODE, CS).compareTo(D0) == 0)) {
            // MOVE 'N' TO COMM-SUCCESS
            Cobol.move("N", f224_COMM_SUCCESS, CS);
            // IF SQLCODE = +100
            if (Cobol.num(f30_SQLCODE, CS).compareTo(D100) == 0) {
                // MOVE '1' TO COMM-FAIL-CODE
                Cobol.move("1", f225_COMM_FAIL_CODE, CS);
            } else {
                // MOVE '2' TO COMM-FAIL-CODE
                Cobol.move("2", f225_COMM_FAIL_CODE, CS);
            }
            // PERFORM CHECK-FOR-STORM-DRAIN-DB2
            perform(15, 17);
            // GO TO UAD999
            if (true) return GOTO | 5;
        }
        // IF COMM-AMT < 0
        if (Cobol.num(f213_COMM_AMT, CS).compareTo(D0) < 0) {
            // IF (HV-ACCOUNT-ACC-TYPE = 'MORTGAGE' AND COMM-FACILTYPE = 496) OR (HV-ACCOUNT-ACC-TYPE = 'LOAN ' AND COMM-FACILTYPE = 496)
            if (((Cobol.compare(f9_HV_ACCOUNT_ACC_TYPE, "MORTGAGE", CS) == 0 && Cobol.num(f222_COMM_FACILTYPE, CS).compareTo(D496) == 0) || (Cobol.compare(f9_HV_ACCOUNT_ACC_TYPE, "LOAN    ", CS) == 0 && Cobol.num(f222_COMM_FACILTYPE, CS).compareTo(D496) == 0))) {
                // MOVE 'N' TO COMM-SUCCESS
                Cobol.move("N", f224_COMM_SUCCESS, CS);
                // MOVE '4' TO COMM-FAIL-CODE
                Cobol.move("4", f225_COMM_FAIL_CODE, CS);
                // GO TO UAD999
                if (true) return GOTO | 5;
            }
            // MOVE 0 TO WS-DIFFERENCE
            Cobol.move(D0, f210_WS_DIFFERENCE, CS);
            // COMPUTE WS-DIFFERENCE = HV-ACCOUNT-AVAIL-BAL + COMM-AMT
            BigDecimal v3 = Cobol.num(f15_HV_ACCOUNT_AVAIL_BAL, CS).add(Cobol.num(f213_COMM_AMT, CS));
            Cobol.store(f210_WS_DIFFERENCE, v3, false, CS);
            // IF WS-DIFFERENCE < 0 AND COMM-FACILTYPE = 496
            if ((Cobol.num(f210_WS_DIFFERENCE, CS).compareTo(D0) < 0 && Cobol.num(f222_COMM_FACILTYPE, CS).compareTo(D496) == 0)) {
                // MOVE 'N' TO COMM-SUCCESS
                Cobol.move("N", f224_COMM_SUCCESS, CS);
                // MOVE '3' TO COMM-FAIL-CODE
                Cobol.move("3", f225_COMM_FAIL_CODE, CS);
                // GO TO UAD999
                if (true) return GOTO | 5;
            }
        }
        // IF (HV-ACCOUNT-ACC-TYPE = 'MORTGAGE' AND COMM-FACILTYPE = 496) OR (HV-ACCOUNT-ACC-TYPE = 'LOAN ' AND COMM-FACILTYPE = 496)
        if (((Cobol.compare(f9_HV_ACCOUNT_ACC_TYPE, "MORTGAGE", CS) == 0 && Cobol.num(f222_COMM_FACILTYPE, CS).compareTo(D496) == 0) || (Cobol.compare(f9_HV_ACCOUNT_ACC_TYPE, "LOAN    ", CS) == 0 && Cobol.num(f222_COMM_FACILTYPE, CS).compareTo(D496) == 0))) {
            // MOVE 'N' TO COMM-SUCCESS
            Cobol.move("N", f224_COMM_SUCCESS, CS);
            // MOVE '4' TO COMM-FAIL-CODE
            Cobol.move("4", f225_COMM_FAIL_CODE, CS);
            // GO TO UAD999
            if (true) return GOTO | 5;
        }
        // COMPUTE HV-ACCOUNT-AVAIL-BAL = HV-ACCOUNT-AVAIL-BAL + COMM-AMT
        BigDecimal v4 = Cobol.num(f15_HV_ACCOUNT_AVAIL_BAL, CS).add(Cobol.num(f213_COMM_AMT, CS));
        Cobol.store(f15_HV_ACCOUNT_AVAIL_BAL, v4, false, CS);
        // COMPUTE HV-ACCOUNT-ACTUAL-BAL = HV-ACCOUNT-ACTUAL-BAL + COMM-AMT
        BigDecimal v5 = Cobol.num(f16_HV_ACCOUNT_ACTUAL_BAL, CS).add(Cobol.num(f213_COMM_AMT, CS));
        Cobol.store(f16_HV_ACCOUNT_ACTUAL_BAL, v5, false, CS);
        // EXEC SQL UPDATE ACCOUNT SET ACCOUNT_EYECATCHER = :HV-ACCOUNT-EYECATCHER, ACCOUNT_CUSTOMER_NUMBER = :HV-ACCOUNT-CUST-NO, ACCOUNT_SORTCODE = :HV-ACCOUNT
        java.util.Map<String, Object> sqlParams6 = new java.util.HashMap<>();
        sqlParams6.put("hvAccountEyecatcher", DetSql.charIn(f4_HV_ACCOUNT_EYECATCHER, CS));
        sqlParams6.put("hvAccountCustNo", DetSql.charIn(f5_HV_ACCOUNT_CUST_NO, CS));
        sqlParams6.put("hvAccountSortcode", DetSql.charIn(f7_HV_ACCOUNT_SORTCODE, CS));
        sqlParams6.put("hvAccountAccNo", DetSql.charIn(f8_HV_ACCOUNT_ACC_NO, CS));
        sqlParams6.put("hvAccountAccType", DetSql.charIn(f9_HV_ACCOUNT_ACC_TYPE, CS));
        sqlParams6.put("hvAccountIntRate", DetSql.numIn(f10_HV_ACCOUNT_INT_RATE, CS));
        sqlParams6.put("hvAccountOpened", DetSql.charIn(f11_HV_ACCOUNT_OPENED, CS));
        sqlParams6.put("hvAccountOverdraftLim", DetSql.numIn(f12_HV_ACCOUNT_OVERDRAFT_LIM, CS));
        sqlParams6.put("hvAccountLastStmt", DetSql.charIn(f13_HV_ACCOUNT_LAST_STMT, CS));
        sqlParams6.put("hvAccountNextStmt", DetSql.charIn(f14_HV_ACCOUNT_NEXT_STMT, CS));
        sqlParams6.put("hvAccountAvailBal", DetSql.numIn(f15_HV_ACCOUNT_AVAIL_BAL, CS));
        sqlParams6.put("hvAccountActualBal", DetSql.numIn(f16_HV_ACCOUNT_ACTUAL_BAL, CS));
        sqlParams6.put("hvAccountSortcode", DetSql.charIn(f7_HV_ACCOUNT_SORTCODE, CS));
        sqlParams6.put("hvAccountAccNo", DetSql.charIn(f8_HV_ACCOUNT_ACC_NO, CS));
        DetSql.update(f27_SQLCA, () -> accountRepository.updateL392Dbcrfun(sqlParams6), true, CS);
        // MOVE SQLCODE TO SQLCODE-DISPLAY
        Cobol.move(f30_SQLCODE, f183_SQLCODE_DISPLAY, CS);
        // MOVE HV-ACCOUNT-AVAIL-BAL TO COMM-AV-BAL
        Cobol.move(f15_HV_ACCOUNT_AVAIL_BAL, f215_COMM_AV_BAL, CS);
        // MOVE HV-ACCOUNT-ACTUAL-BAL TO COMM-ACT-BAL
        Cobol.move(f16_HV_ACCOUNT_ACTUAL_BAL, f216_COMM_ACT_BAL, CS);
        // IF SQLCODE NOT = 0
        if (!(Cobol.num(f30_SQLCODE, CS).compareTo(D0) == 0)) {
            // MOVE 'N' TO COMM-SUCCESS
            Cobol.move("N", f224_COMM_SUCCESS, CS);
            // MOVE '2' TO COMM-FAIL-CODE
            Cobol.move("2", f225_COMM_FAIL_CODE, CS);
            // PERFORM CHECK-FOR-STORM-DRAIN-DB2
            perform(15, 17);
            // GO TO UAD999
            if (true) return GOTO | 5;
        }
        // PERFORM WRITE-TO-PROCTRAN
        perform(6, 8);
        return 5;
    }

    /** UAD999. */
    private int p5() {
        // EXIT
        return 6;
    }

    /** WRITE-TO-PROCTRAN. */
    private int p6() {

        return 7;
    }

    /** WTP010. */
    private int p7() {
        // PERFORM WRITE-TO-PROCTRAN-DB2
        perform(9, 11);
        return 8;
    }

    /** WTP999. */
    private int p8() {
        // EXIT
        return 9;
    }

    /** WRITE-TO-PROCTRAN-DB2. */
    private int p9() {

        return 10;
    }

    /** WTPD010. */
    private int p10() {
        // INITIALIZE HOST-PROCTRAN-ROW
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f17_HOST_PROCTRAN_ROW.storage(), f17_HOST_PROCTRAN_ROW.offset() + 0, 4, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f17_HOST_PROCTRAN_ROW.storage(), f17_HOST_PROCTRAN_ROW.offset() + 4, 6, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f17_HOST_PROCTRAN_ROW.storage(), f17_HOST_PROCTRAN_ROW.offset() + 10, 8, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f17_HOST_PROCTRAN_ROW.storage(), f17_HOST_PROCTRAN_ROW.offset() + 18, 10, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f17_HOST_PROCTRAN_ROW.storage(), f17_HOST_PROCTRAN_ROW.offset() + 28, 6, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f17_HOST_PROCTRAN_ROW.storage(), f17_HOST_PROCTRAN_ROW.offset() + 34, 12, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f17_HOST_PROCTRAN_ROW.storage(), f17_HOST_PROCTRAN_ROW.offset() + 46, 3, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f17_HOST_PROCTRAN_ROW.storage(), f17_HOST_PROCTRAN_ROW.offset() + 49, 40, false), CS);
        Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f17_HOST_PROCTRAN_ROW.storage(), f17_HOST_PROCTRAN_ROW.offset() + 89, 12, 2, true), CS);
        // INITIALIZE WS-EIBTASKN12
        Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f88_WS_EIBTASKN12.storage(), f88_WS_EIBTASKN12.offset() + 0, 12, 0, false, false, false), CS);
        // MOVE 'PRTR' TO HV-PROCTRAN-EYECATCHER
        Cobol.move("PRTR", f18_HV_PROCTRAN_EYECATCHER, CS);
        // MOVE COMM-SORTC TO HV-PROCTRAN-SORT-CODE
        Cobol.move(f214_COMM_SORTC, f19_HV_PROCTRAN_SORT_CODE, CS);
        // MOVE COMM-ACCNO TO HV-PROCTRAN-ACC-NUMBER
        Cobol.move(f212_COMM_ACCNO, f20_HV_PROCTRAN_ACC_NUMBER, CS);
        // MOVE EIBTASKN TO WS-EIBTASKN12
        Cobol.move(f230_EIBTASKN, f88_WS_EIBTASKN12, CS);
        // MOVE WS-EIBTASKN12 TO HV-PROCTRAN-REF
        Cobol.move(f88_WS_EIBTASKN12, f23_HV_PROCTRAN_REF, CS);
        // EXEC CICS ASKTIME ABSTIME(WS-U-TIME) END-EXEC
        Cobol.store(f96_WS_U_TIME, BigDecimal.valueOf(task.asktime()), false, CS);
        // EXEC CICS FORMATTIME ABSTIME(WS-U-TIME) DDMMYYYY(WS-ORIG-DATE) TIME(HV-PROCTRAN-TIME) DATESEP('.') END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f96_WS_U_TIME, CS).longValue(), "DDMMYYYY", "."), f97_WS_ORIG_DATE, CS);
        Cobol.move(CicsTask.formatTime(Cobol.num(f96_WS_U_TIME, CS).longValue(), ""), f22_HV_PROCTRAN_TIME, CS);
        // MOVE WS-ORIG-DATE TO WS-ORIG-DATE-GRP-X
        Cobol.move(f97_WS_ORIG_DATE, f104_WS_ORIG_DATE_GRP_X, CS);
        // MOVE WS-ORIG-DATE-GRP-X TO HV-PROCTRAN-DATE
        Cobol.move(f104_WS_ORIG_DATE_GRP_X, f21_HV_PROCTRAN_DATE, CS);
        // MOVE SPACES TO HV-PROCTRAN-DESC
        Cobol.moveFigurative(Figurative.SPACES, f25_HV_PROCTRAN_DESC, CS);
        // IF COMM-AMT < 0
        if (Cobol.num(f213_COMM_AMT, CS).compareTo(D0) < 0) {
            // MOVE 'DEB' TO HV-PROCTRAN-TYPE
            Cobol.move("DEB", f24_HV_PROCTRAN_TYPE, CS);
            // MOVE 'COUNTER WTHDRW' TO HV-PROCTRAN-DESC
            Cobol.move("COUNTER WTHDRW", f25_HV_PROCTRAN_DESC, CS);
            // IF COMM-FACILTYPE = 496
            if (Cobol.num(f222_COMM_FACILTYPE, CS).compareTo(D496) == 0) {
                // MOVE 'PDR' TO HV-PROCTRAN-TYPE
                Cobol.move("PDR", f24_HV_PROCTRAN_TYPE, CS);
                // MOVE COMM-ORIGIN(1:14) TO HV-PROCTRAN-DESC
                Cobol.move(f217_COMM_ORIGIN.ref(1, Integer.valueOf(14)), f25_HV_PROCTRAN_DESC, CS);
            }
        } else {
            // MOVE 'CRE' TO HV-PROCTRAN-TYPE
            Cobol.move("CRE", f24_HV_PROCTRAN_TYPE, CS);
            // MOVE 'COUNTER RECVED' TO HV-PROCTRAN-DESC
            Cobol.move("COUNTER RECVED", f25_HV_PROCTRAN_DESC, CS);
            // IF COMM-FACILTYPE = 496
            if (Cobol.num(f222_COMM_FACILTYPE, CS).compareTo(D496) == 0) {
                // MOVE 'PCR' TO HV-PROCTRAN-TYPE
                Cobol.move("PCR", f24_HV_PROCTRAN_TYPE, CS);
                // MOVE COMM-ORIGIN(1:14) TO HV-PROCTRAN-DESC
                Cobol.move(f217_COMM_ORIGIN.ref(1, Integer.valueOf(14)), f25_HV_PROCTRAN_DESC, CS);
            }
        }
        // MOVE COMM-AMT TO HV-PROCTRAN-AMOUNT
        Cobol.move(f213_COMM_AMT, f26_HV_PROCTRAN_AMOUNT, CS);
        // EXEC SQL INSERT INTO PROCTRAN ( PROCTRAN_EYECATCHER, PROCTRAN_SORTCODE, PROCTRAN_NUMBER, PROCTRAN_DATE, PROCTRAN_TIME, PROCTRAN_REF, PROCTRAN_TYPE, PR
        java.util.Map<String, Object> sqlParams7 = new java.util.HashMap<>();
        sqlParams7.put("hvProctranEyecatcher", DetSql.charIn(f18_HV_PROCTRAN_EYECATCHER, CS));
        sqlParams7.put("hvProctranSortCode", DetSql.charIn(f19_HV_PROCTRAN_SORT_CODE, CS));
        sqlParams7.put("hvProctranAccNumber", DetSql.charIn(f20_HV_PROCTRAN_ACC_NUMBER, CS));
        sqlParams7.put("hvProctranDate", DetSql.charIn(f21_HV_PROCTRAN_DATE, CS));
        sqlParams7.put("hvProctranTime", DetSql.charIn(f22_HV_PROCTRAN_TIME, CS));
        sqlParams7.put("hvProctranRef", DetSql.charIn(f23_HV_PROCTRAN_REF, CS));
        sqlParams7.put("hvProctranType", DetSql.charIn(f24_HV_PROCTRAN_TYPE, CS));
        sqlParams7.put("hvProctranDesc", DetSql.charIn(f25_HV_PROCTRAN_DESC, CS));
        sqlParams7.put("hvProctranAmount", DetSql.numIn(f26_HV_PROCTRAN_AMOUNT, CS));
        DetSql.update(f27_SQLCA, () -> proctranRepository.insertL524Dbcrfun(sqlParams7), false, CS);
        // IF SQLCODE NOT = 0
        if (!(Cobol.num(f30_SQLCODE, CS).compareTo(D0) == 0)) {
            // MOVE SQLCODE TO SQLCODE-DISPLAY
            Cobol.move(f30_SQLCODE, f183_SQLCODE_DISPLAY, CS);
            // DISPLAY 'UNABLE TO WRITE TO PROCTRAN DB2 DATASTORE' ' SQLCODE=' SQLCODE-DISPLAY 'WITH THE FOLLOWING DATA:' HOST-PROCTRAN-ROW
            Sysout.display("UNABLE TO WRITE TO PROCTRAN DB2 DATASTORE", " SQLCODE=", Cobol.displayText(f183_SQLCODE_DISPLAY, CS), "WITH THE FOLLOWING DATA:", Cobol.displayText(f17_HOST_PROCTRAN_ROW, CS));
            // EXEC CICS SYNCPOINT ROLLBACK RESP(WS-CICS-RESP) RESP2(WS-CICS-RESP2) END-EXEC
            task.rollback();
            // IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
            if (!(Cobol.num(f50_WS_CICS_RESP, CS).compareTo(D0) == 0)) {
                // INITIALIZE ABNDINFO-REC
                Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 0, 15, 0, true), CS);
                Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 8, 4, 0, false, false, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 12, 8, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 20, 4, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 24, 10, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 34, 8, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 42, 4, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 46, 8, false), CS);
                Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 54, 8, 0, true, true, true), CS);
                Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 63, 8, 0, true, true, true), CS);
                Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 72, 8, 0, true, true, true), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 81, 600, false), CS);
                // MOVE EIBRESP TO ABND-RESPCODE
                Cobol.move(f255_EIBRESP, f205_ABND_RESPCODE, CS);
                // MOVE EIBRESP2 TO ABND-RESP2CODE
                Cobol.move(f256_EIBRESP2, f206_ABND_RESP2CODE, CS);
                // EXEC CICS ASSIGN APPLID(ABND-APPLID) END-EXEC
                DetCics.putText(f199_ABND_APPLID, task.assignApplid(), CS);
                // MOVE EIBTASKN TO ABND-TASKNO-KEY
                Cobol.move(f230_EIBTASKN, f198_ABND_TASKNO_KEY, CS);
                // MOVE EIBTRNID TO ABND-TRANID
                Cobol.move(f229_EIBTRNID, f200_ABND_TRANID, CS);
                // PERFORM POPULATE-TIME-DATE
                perform(21, 23);
                // MOVE WS-ORIG-DATE TO ABND-DATE
                Cobol.move(f97_WS_ORIG_DATE, f201_ABND_DATE, CS);
                // STRING WS-TIME-NOW-GRP-HH DELIMITED BY SIZE, ':' DELIMITED BY SIZE, WS-TIME-NOW-GRP-MM DELIMITED BY SIZE, ':' DELIMITED BY SIZE, WS-TIME-NOW-GRP-MM DE
                Cobol.string(f202_ABND_TIME, null, CS, Cobol.StringPart.size(f191_WS_TIME_NOW_GRP_HH), Cobol.StringPart.size(":", CS), Cobol.StringPart.size(f192_WS_TIME_NOW_GRP_MM), Cobol.StringPart.size(":", CS), Cobol.StringPart.size(f192_WS_TIME_NOW_GRP_MM));
                // MOVE WS-U-TIME TO ABND-UTIME-KEY
                Cobol.move(f96_WS_U_TIME, f197_ABND_UTIME_KEY, CS);
                // MOVE 'HROL' TO ABND-CODE
                Cobol.move("HROL", f203_ABND_CODE, CS);
                // EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM) END-EXEC
                DetCics.putText(f204_ABND_PROGRAM, "DBCRFUN ", CS);
                // MOVE ZEROS TO ABND-SQLCODE
                Cobol.moveFigurative(Figurative.ZEROS, f207_ABND_SQLCODE, CS);
                // STRING 'WTPD010 - COULD NOT ROLL BACK, POSSIBLE DATA' DELIMITED BY SIZE, 'INTEGRITY ISSUE BETWEEN ACCOUNT AND PROCTRAN ' DELIMITED BY SIZE, 'FOR ROW:'
                Cobol.string(f208_ABND_FREEFORM, null, CS, Cobol.StringPart.size("WTPD010 - COULD NOT ROLL BACK, POSSIBLE DATA", CS), Cobol.StringPart.size("INTEGRITY ISSUE BETWEEN ACCOUNT AND PROCTRAN ", CS), Cobol.StringPart.size("FOR ROW:", CS), Cobol.StringPart.size(f17_HOST_PROCTRAN_ROW), Cobol.StringPart.size("EIBRESP=", CS), Cobol.StringPart.size(f205_ABND_RESPCODE), Cobol.StringPart.size(" RESP2=", CS), Cobol.StringPart.size(f206_ABND_RESP2CODE));
                // EXEC CICS LINK PROGRAM(WS-ABEND-PGM) COMMAREA(ABNDINFO-REC) END-EXEC
                AbndprocAbndinfoRec ca9 = out_AbndprocAbndinfoRec(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset());
                String lr8 = task.link(Cobol.text(f194_WS_ABEND_PGM, CS).strip(), ca9, 681);
                if ("NORMAL".equals(lr8)) in_AbndprocAbndinfoRec(ca9, f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset());
                String exit10 = task.abendExit();
                if (exit10 != null) return GOTO | paragraph(exit10);
                if (task.ended()) throw new Goback();
                Cobol.store(f255_EIBRESP, BigDecimal.valueOf(DetCics.resp(lr8)), false, CS);
                Cobol.store(f256_EIBRESP2, BigDecimal.valueOf(0), false, CS);
                if (DetCics.resp(lr8) != 0) {
                    int to = condition(DetCics.condition(DetCics.resp(lr8)));
                    if (to >= 0) return GOTO | to;
                }
                // DISPLAY ' COULD NOT ROLL BACK, POSSIBLE DATA ' 'INTEGRITY ISSUE BETWEEN ACCOUNT AND PROCTRAN ' 'FOR ROW:' HOST-PROCTRAN-ROW 'RESP CODE=' WS-CICS-RESP 
                Sysout.display(" COULD NOT ROLL BACK, POSSIBLE DATA ", "INTEGRITY ISSUE BETWEEN ACCOUNT AND PROCTRAN ", "FOR ROW:", Cobol.displayText(f17_HOST_PROCTRAN_ROW, CS), "RESP CODE=", Cobol.displayText(f50_WS_CICS_RESP, CS), " RESP2 CODE=", Cobol.displayText(f51_WS_CICS_RESP2, CS));
                // EXEC CICS ABEND ABCODE ('HROL') CANCEL END-EXEC
                String exit11 = task.abendCancel("HROL".strip());
                if (exit11 == null) throw new Goback();
                if (true) return GOTO | paragraph(exit11);
            }
            // MOVE 'N' TO COMM-SUCCESS
            Cobol.move("N", f224_COMM_SUCCESS, CS);
            // MOVE '02' TO COMM-FAIL-CODE
            Cobol.move("02", f225_COMM_FAIL_CODE, CS);
            // PERFORM CHECK-FOR-STORM-DRAIN-DB2
            perform(15, 17);
        } else {
            // MOVE 'Y' TO COMM-SUCCESS
            Cobol.move("Y", f224_COMM_SUCCESS, CS);
            // MOVE '0' TO COMM-FAIL-CODE
            Cobol.move("0", f225_COMM_FAIL_CODE, CS);
        }
        return 11;
    }

    /** WTPD999. */
    private int p11() {
        // EXIT
        return 12;
    }

    /** GET-ME-OUT-OF-HERE. */
    private int p12() {

        return 13;
    }

    /** GMOOH010. */
    private int p13() {
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        // GOBACK
        if (true) throw new Goback();
        return 14;
    }

    /** GMOOH999. */
    private int p14() {
        // EXIT
        return 15;
    }

    /** CHECK-FOR-STORM-DRAIN-DB2. */
    private int p15() {

        return 16;
    }

    /** CFSDD010. */
    private int p16() {
        // EVALUATE SQLCODE
        if ((Cobol.num(f30_SQLCODE, CS).compareTo(D923) == 0)) {
            // MOVE 'DB2 Connection lost ' TO STORM-DRAIN-CONDITION
            Cobol.move("DB2 Connection lost ", f186_STORM_DRAIN_CONDITION, CS);
        } else if (true) {
            // MOVE 'Not Storm Drain ' TO STORM-DRAIN-CONDITION
            Cobol.move("Not Storm Drain     ", f186_STORM_DRAIN_CONDITION, CS);
        }
        // IF STORM-DRAIN-CONDITION NOT EQUAL 'Not Storm Drain '
        if (!(Cobol.compare(f186_STORM_DRAIN_CONDITION, "Not Storm Drain     ", CS) == 0)) {
            // DISPLAY 'DBCRFUN: Check-For-Storm-Drain-DB2: Storm ' 'Drain condition (' STORM-DRAIN-CONDITION ') ' 'has been met (' SQLCODE-DISPLAY ').'
            Sysout.display("DBCRFUN: Check-For-Storm-Drain-DB2: Storm ", "Drain condition (", Cobol.displayText(f186_STORM_DRAIN_CONDITION, CS), ") ", "has been met (", Cobol.displayText(f183_SQLCODE_DISPLAY, CS), ").");
        } else {
            // CONTINUE
        }
        return 17;
    }

    /** CFSDD999. */
    private int p17() {
        // EXIT
        return 18;
    }

    /** ABEND-HANDLING. */
    private int p18() {

        return 19;
    }

    /** AH010. */
    private int p19() {
        // EXEC CICS ASSIGN ABCODE(MY-ABEND-CODE) END-EXEC
        DetCics.putText(f184_MY_ABEND_CODE, task.abcode(), CS);
        // EVALUATE MY-ABEND-CODE
        if ((Cobol.compare(f184_MY_ABEND_CODE, "AD2Z", CS) == 0)) {
            // MOVE SQLCODE TO SQLCODE-DISPLAY
            Cobol.move(f30_SQLCODE, f183_SQLCODE_DISPLAY, CS);
            // DISPLAY 'DB2 DEADLOCK DETECTED IN DBCRFUN, SQLCODE=' SQLCODE-DISPLAY
            Sysout.display("DB2 DEADLOCK DETECTED IN DBCRFUN, SQLCODE=", Cobol.displayText(f183_SQLCODE_DISPLAY, CS));
            // DISPLAY 'DB2 DEADLOCK FOR ACCOUNT ' HV-ACCOUNT-ACC-NO
            Sysout.display("DB2 DEADLOCK FOR ACCOUNT ", Cobol.displayText(f8_HV_ACCOUNT_ACC_NO, CS));
            // DISPLAY 'SQLSTATE=' SQLSTATE ',SQLERRMC=' SQLERRMC(1:SQLERRML) ',SQLERRD(1)=' SQLERRD(1) ',SQLERRD(2)=' SQLERRD(2) ',SQLERRD(3)=' SQLERRD(3) ',SQLERRD
            Sysout.display("SQLSTATE=", Cobol.displayText(f48_SQLSTATE, CS), ",SQLERRMC=", Cobol.displayText(f33_SQLERRMC.ref(1, Integer.valueOf(Cobol.num(f32_SQLERRML, CS).intValue())), CS), ",SQLERRD(1)=", Cobol.displayText(f35_SQLERRD.at(1, 4), CS), ",SQLERRD(2)=", Cobol.displayText(f35_SQLERRD.at(2, 4), CS), ",SQLERRD(3)=", Cobol.displayText(f35_SQLERRD.at(3, 4), CS), ",SQLERRD(4)=", Cobol.displayText(f35_SQLERRD.at(4, 4), CS), ",SQLERRD(5)=", Cobol.displayText(f35_SQLERRD.at(5, 4), CS), ",SQLERRD(6)=", Cobol.displayText(f35_SQLERRD.at(6, 4), CS));
        } else if ((Cobol.compare(f184_MY_ABEND_CODE, "AFCR", CS) == 0) || (Cobol.compare(f184_MY_ABEND_CODE, "AFCS", CS) == 0) || (Cobol.compare(f184_MY_ABEND_CODE, "AFCT", CS) == 0)) {
            // MOVE 'Y' TO WS-STORM-DRAIN
            Cobol.move("Y", f185_WS_STORM_DRAIN, CS);
            // DISPLAY 'DBCRFUN: Check-For-Storm-Drain-VSAM: Storm ' 'Drain condition (Abend ' MY-ABEND-CODE ') ' 'has been met.'
            Sysout.display("DBCRFUN: Check-For-Storm-Drain-VSAM: Storm ", "Drain condition (Abend ", Cobol.displayText(f184_MY_ABEND_CODE, CS), ") ", "has been met.");
            // EXEC CICS SYNCPOINT ROLLBACK RESP(WS-CICS-RESP) RESP2(WS-CICS-RESP2) END-EXEC
            task.rollback();
            // IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
            if (!(Cobol.num(f50_WS_CICS_RESP, CS).compareTo(D0) == 0)) {
                // INITIALIZE ABNDINFO-REC
                Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 0, 15, 0, true), CS);
                Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 8, 4, 0, false, false, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 12, 8, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 20, 4, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 24, 10, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 34, 8, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 42, 4, false), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 46, 8, false), CS);
                Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 54, 8, 0, true, true, true), CS);
                Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 63, 8, 0, true, true, true), CS);
                Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 72, 8, 0, true, true, true), CS);
                Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset() + 81, 600, false), CS);
                // MOVE EIBRESP TO ABND-RESPCODE
                Cobol.move(f255_EIBRESP, f205_ABND_RESPCODE, CS);
                // MOVE EIBRESP2 TO ABND-RESP2CODE
                Cobol.move(f256_EIBRESP2, f206_ABND_RESP2CODE, CS);
                // EXEC CICS ASSIGN APPLID(ABND-APPLID) END-EXEC
                DetCics.putText(f199_ABND_APPLID, task.assignApplid(), CS);
                // MOVE EIBTASKN TO ABND-TASKNO-KEY
                Cobol.move(f230_EIBTASKN, f198_ABND_TASKNO_KEY, CS);
                // MOVE EIBTRNID TO ABND-TRANID
                Cobol.move(f229_EIBTRNID, f200_ABND_TRANID, CS);
                // PERFORM POPULATE-TIME-DATE
                perform(21, 23);
                // MOVE WS-ORIG-DATE TO ABND-DATE
                Cobol.move(f97_WS_ORIG_DATE, f201_ABND_DATE, CS);
                // STRING WS-TIME-NOW-GRP-HH DELIMITED BY SIZE, ':' DELIMITED BY SIZE, WS-TIME-NOW-GRP-MM DELIMITED BY SIZE, ':' DELIMITED BY SIZE, WS-TIME-NOW-GRP-MM DE
                Cobol.string(f202_ABND_TIME, null, CS, Cobol.StringPart.size(f191_WS_TIME_NOW_GRP_HH), Cobol.StringPart.size(":", CS), Cobol.StringPart.size(f192_WS_TIME_NOW_GRP_MM), Cobol.StringPart.size(":", CS), Cobol.StringPart.size(f192_WS_TIME_NOW_GRP_MM));
                // MOVE WS-U-TIME TO ABND-UTIME-KEY
                Cobol.move(f96_WS_U_TIME, f197_ABND_UTIME_KEY, CS);
                // MOVE 'HROL' TO ABND-CODE
                Cobol.move("HROL", f203_ABND_CODE, CS);
                // EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM) END-EXEC
                DetCics.putText(f204_ABND_PROGRAM, "DBCRFUN ", CS);
                // MOVE ZEROS TO ABND-SQLCODE
                Cobol.moveFigurative(Figurative.ZEROS, f207_ABND_SQLCODE, CS);
                // STRING 'AH010 - Unable to perform Synpoint ' DELIMITED BY SIZE, 'Rollback.' DELIMITED BY SIZE, ' Possible Integrity issue following VSAM RLS ' DELIMIT
                Cobol.string(f208_ABND_FREEFORM, null, CS, Cobol.StringPart.size("AH010 - Unable to perform Synpoint ", CS), Cobol.StringPart.size("Rollback.", CS), Cobol.StringPart.size(" Possible Integrity issue following VSAM RLS ", CS), Cobol.StringPart.size("abend.", CS), Cobol.StringPart.size("EIBRESP=", CS), Cobol.StringPart.size(f205_ABND_RESPCODE), Cobol.StringPart.size(" RESP2=", CS), Cobol.StringPart.size(f206_ABND_RESP2CODE));
                // EXEC CICS LINK PROGRAM(WS-ABEND-PGM) COMMAREA(ABNDINFO-REC) END-EXEC
                AbndprocAbndinfoRec ca13 = out_AbndprocAbndinfoRec(f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset());
                String lr12 = task.link(Cobol.text(f194_WS_ABEND_PGM, CS).strip(), ca13, 681);
                if ("NORMAL".equals(lr12)) in_AbndprocAbndinfoRec(ca13, f195_ABNDINFO_REC.storage(), f195_ABNDINFO_REC.offset());
                String exit14 = task.abendExit();
                if (exit14 != null) return GOTO | paragraph(exit14);
                if (task.ended()) throw new Goback();
                Cobol.store(f255_EIBRESP, BigDecimal.valueOf(DetCics.resp(lr12)), false, CS);
                Cobol.store(f256_EIBRESP2, BigDecimal.valueOf(0), false, CS);
                if (DetCics.resp(lr12) != 0) {
                    int to = condition(DetCics.condition(DetCics.resp(lr12)));
                    if (to >= 0) return GOTO | to;
                }
                // DISPLAY 'DBCRFUN: Unable to perform Synpoint ' 'Rollback.' ' Possible Integrity issue following VSAM RLS' ' abend' ' RESP CODE=' WS-CICS-RESP ' RESP2 
                Sysout.display("DBCRFUN: Unable to perform Synpoint ", "Rollback.", " Possible Integrity issue following VSAM RLS", " abend", " RESP CODE=", Cobol.displayText(f50_WS_CICS_RESP, CS), " RESP2 CODE=", Cobol.displayText(f51_WS_CICS_RESP2, CS));
                // EXEC CICS ABEND ABCODE ('HROL') CANCEL END-EXEC
                String exit15 = task.abendCancel("HROL".strip());
                if (exit15 == null) throw new Goback();
                if (true) return GOTO | paragraph(exit15);
            }
            // MOVE 'N' TO COMM-SUCCESS
            Cobol.move("N", f224_COMM_SUCCESS, CS);
            // MOVE '2' TO COMM-FAIL-CODE
            Cobol.move("2", f225_COMM_FAIL_CODE, CS);
            // EXEC CICS RETURN END-EXEC
            caBack.run();
            task.returnTransid(null, null);
            if (true) throw new Goback();
        }
        // IF WS-STORM-DRAIN = 'N'
        if (Cobol.compare(f185_WS_STORM_DRAIN, "N", CS) == 0) {
            // EXEC CICS ABEND ABCODE( MY-ABEND-CODE) NODUMP CANCEL END-EXEC
            String exit16 = task.abendCancel(Cobol.text(f184_MY_ABEND_CODE, CS).strip());
            if (exit16 == null) throw new Goback();
            if (true) return GOTO | paragraph(exit16);
        }
        return 20;
    }

    /** AH999. */
    private int p20() {
        // EXIT
        return 21;
    }

    /** POPULATE-TIME-DATE. */
    private int p21() {

        return 22;
    }

    /** PTD10. */
    private int p22() {
        // EXEC CICS ASKTIME ABSTIME(WS-U-TIME) END-EXEC
        Cobol.store(f96_WS_U_TIME, BigDecimal.valueOf(task.asktime()), false, CS);
        // EXEC CICS FORMATTIME ABSTIME(WS-U-TIME) DDMMYYYY(WS-ORIG-DATE) TIME(WS-TIME-NOW) DATESEP END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f96_WS_U_TIME, CS).longValue(), "DDMMYYYY", "/"), f97_WS_ORIG_DATE, CS);
        Cobol.move(CicsTask.formatTime(Cobol.num(f96_WS_U_TIME, CS).longValue(), ""), f189_WS_TIME_NOW, CS);
        return 23;
    }

    /** PTD999. */
    private int p23() {
        // EXIT
        return 24;
    }

}
