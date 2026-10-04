// gitgalaxy-det-port: COBOL CBTRN01C (CBTRN01C.cbl), translated by rule, statement for statement
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
import com.gitgalaxy.modernized.entity.vsam.*;
import com.gitgalaxy.modernized.entity.vsam.AccountRecord;
import com.gitgalaxy.modernized.entity.vsam.CardRecord;
import com.gitgalaxy.modernized.entity.vsam.CardXrefRecord;
import com.gitgalaxy.modernized.entity.vsam.CustomerRecord;
import com.gitgalaxy.modernized.repository.vsam.AccountRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.CardRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.CardXrefRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.CustomerRecordRepository;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * CBTRN01C: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 216, translated 216, holes 0.
 * Inferred: CUSTOMER-FILE (DD CUSTFILE) -> customerRecordRepository: the dataset other jobs bind CUSTFILE to.
 * Inferred: XREF-FILE (DD XREFFILE) -> cardXrefRecordRepository: the dataset other jobs bind XREFFILE to.
 * Inferred: CARD-FILE (DD CARDFILE) -> cardRecordRepository: the dataset other jobs bind CARDFILE to.
 * Inferred: ACCOUNT-FILE (DD ACCTFILE) -> accountRecordRepository: the dataset other jobs bind ACCTFILE to.
 * Inferred: TRANSACT-FILE: no store bound; the program only opens and closes it.
 */
@Service
public class Cbtrn01cService {

    private static final Charset CS = CobolRecords.charset();
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D0 = new BigDecimal("0");
    private static final BigDecimal D16 = new BigDecimal("16");
    private static final BigDecimal D12 = new BigDecimal("12");
    private static final BigDecimal D4 = new BigDecimal("4");
    private static final BigDecimal D8 = new BigDecimal("8");
    private static final BigDecimal D999 = new BigDecimal("999");

    private static final byte[] IMAGE_s_FD_TRAN_RECORD = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_FD_CUSTFILE_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_FD_XREFFILE_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_FD_CARDFILE_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_FD_ACCTFILE_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_FD_TRANFILE_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_DALYTRAN_RECORD = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgMDAwMCAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgMDAwMDAwMDAwMDAwMDAwMDAwMDAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_DALYTRAN_STATUS = Base64.getDecoder().decode(String.join("",
            "ICA="));
    private static final byte[] IMAGE_s_CUSTOMER_RECORD = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgMDAwMDAwMDAwICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAwMDAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_CUSTFILE_STATUS = Base64.getDecoder().decode(String.join("",
            "ICA="));
    private static final byte[] IMAGE_s_CARD_XREF_RECORD = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgIDAwMDAwMDAwMDAwMDAwMDAwMDAwICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_XREFFILE_STATUS = Base64.getDecoder().decode(String.join("",
            "ICA="));
    private static final byte[] IMAGE_s_CARD_RECORD = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgIDAwMDAwMDAwMDAwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_CARDFILE_STATUS = Base64.getDecoder().decode(String.join("",
            "ICA="));
    private static final byte[] IMAGE_s_ACCOUNT_RECORD = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwMDAgMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_ACCTFILE_STATUS = Base64.getDecoder().decode(String.join("",
            "ICA="));
    private static final byte[] IMAGE_s_TRAN_RECORD = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgMDAwMCAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgMDAwMDAwMDAwMDAwMDAwMDAwMDAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_TRANFILE_STATUS = Base64.getDecoder().decode(String.join("",
            "ICA="));
    private static final byte[] IMAGE_s_IO_STATUS = Base64.getDecoder().decode(String.join("",
            "ICA="));
    private static final byte[] IMAGE_s_TWO_BYTES_BINARY = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private static final byte[] IMAGE_s_IO_STATUS_04 = Base64.getDecoder().decode(String.join("",
            "MDAwMA=="));
    private static final byte[] IMAGE_s_APPL_RESULT = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_END_OF_DAILY_TRANS_FILE = Base64.getDecoder().decode(String.join("",
            "Tg=="));
    private static final byte[] IMAGE_s_ABCODE = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_TIMING = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_MISC_VARIABLES = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDA="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_FD_TRAN_RECORD = new Storage(IMAGE_s_FD_TRAN_RECORD.length);
    private final Storage s_FD_CUSTFILE_REC = new Storage(IMAGE_s_FD_CUSTFILE_REC.length);
    private final Storage s_FD_XREFFILE_REC = new Storage(IMAGE_s_FD_XREFFILE_REC.length);
    private final Storage s_FD_CARDFILE_REC = new Storage(IMAGE_s_FD_CARDFILE_REC.length);
    private final Storage s_FD_ACCTFILE_REC = new Storage(IMAGE_s_FD_ACCTFILE_REC.length);
    private final Storage s_FD_TRANFILE_REC = new Storage(IMAGE_s_FD_TRANFILE_REC.length);
    private final Storage s_DALYTRAN_RECORD = new Storage(IMAGE_s_DALYTRAN_RECORD.length);
    private final Storage s_DALYTRAN_STATUS = new Storage(IMAGE_s_DALYTRAN_STATUS.length);
    private final Storage s_CUSTOMER_RECORD = new Storage(IMAGE_s_CUSTOMER_RECORD.length);
    private final Storage s_CUSTFILE_STATUS = new Storage(IMAGE_s_CUSTFILE_STATUS.length);
    private final Storage s_CARD_XREF_RECORD = new Storage(IMAGE_s_CARD_XREF_RECORD.length);
    private final Storage s_XREFFILE_STATUS = new Storage(IMAGE_s_XREFFILE_STATUS.length);
    private final Storage s_CARD_RECORD = new Storage(IMAGE_s_CARD_RECORD.length);
    private final Storage s_CARDFILE_STATUS = new Storage(IMAGE_s_CARDFILE_STATUS.length);
    private final Storage s_ACCOUNT_RECORD = new Storage(IMAGE_s_ACCOUNT_RECORD.length);
    private final Storage s_ACCTFILE_STATUS = new Storage(IMAGE_s_ACCTFILE_STATUS.length);
    private final Storage s_TRAN_RECORD = new Storage(IMAGE_s_TRAN_RECORD.length);
    private final Storage s_TRANFILE_STATUS = new Storage(IMAGE_s_TRANFILE_STATUS.length);
    private final Storage s_IO_STATUS = new Storage(IMAGE_s_IO_STATUS.length);
    private final Storage s_TWO_BYTES_BINARY = new Storage(IMAGE_s_TWO_BYTES_BINARY.length);
    private final Storage s_IO_STATUS_04 = new Storage(IMAGE_s_IO_STATUS_04.length);
    private final Storage s_APPL_RESULT = new Storage(IMAGE_s_APPL_RESULT.length);
    private final Storage s_END_OF_DAILY_TRANS_FILE = new Storage(IMAGE_s_END_OF_DAILY_TRANS_FILE.length);
    private final Storage s_ABCODE = new Storage(IMAGE_s_ABCODE.length);
    private final Storage s_TIMING = new Storage(IMAGE_s_TIMING.length);
    private final Storage s_WS_MISC_VARIABLES = new Storage(IMAGE_s_WS_MISC_VARIABLES.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private Field f100_TRAN_SOURCE;
    private Field f101_TRAN_DESC;
    private Field f102_TRAN_AMT;
    private Field f103_TRAN_MERCHANT_ID;
    private Field f104_TRAN_MERCHANT_NAME;
    private Field f105_TRAN_MERCHANT_CITY;
    private Field f106_TRAN_MERCHANT_ZIP;
    private Field f107_TRAN_CARD_NUM;
    private Field f108_TRAN_ORIG_TS;
    private Field f109_TRAN_PROC_TS;
    private Field f10_FD_CARDFILE_REC;
    private Field f110_FILLER;
    private Field f111_TRANFILE_STATUS;
    private Field f112_TRANFILE_STAT1;
    private Field f113_TRANFILE_STAT2;
    private Field f114_IO_STATUS;
    private Field f115_IO_STAT1;
    private Field f116_IO_STAT2;
    private Field f117_TWO_BYTES_BINARY;
    private Field f118_TWO_BYTES_ALPHA;
    private Field f119_TWO_BYTES_LEFT;
    private Field f11_FD_CARD_NUM;
    private Field f120_TWO_BYTES_RIGHT;
    private Field f121_IO_STATUS_04;
    private Field f122_IO_STATUS_0401;
    private Field f123_IO_STATUS_0403;
    private Field f124_APPL_RESULT;
    private Field f125_END_OF_DAILY_TRANS_FILE;
    private Field f126_ABCODE;
    private Field f127_TIMING;
    private Field f128_WS_MISC_VARIABLES;
    private Field f129_WS_XREF_READ_STATUS;
    private Field f12_FD_CARD_DATA;
    private Field f130_WS_ACCT_READ_STATUS;
    private Field f131_GG_RETURN_CODE;
    private Field f13_FD_ACCTFILE_REC;
    private Field f14_FD_ACCT_ID;
    private Field f15_FD_ACCT_DATA;
    private Field f16_FD_TRANFILE_REC;
    private Field f17_FD_TRANS_ID;
    private Field f18_FD_ACCT_DATA;
    private Field f19_DALYTRAN_RECORD;
    private Field f1_FD_TRAN_RECORD;
    private Field f20_DALYTRAN_ID;
    private Field f21_DALYTRAN_TYPE_CD;
    private Field f22_DALYTRAN_CAT_CD;
    private Field f23_DALYTRAN_SOURCE;
    private Field f24_DALYTRAN_DESC;
    private Field f25_DALYTRAN_AMT;
    private Field f26_DALYTRAN_MERCHANT_ID;
    private Field f27_DALYTRAN_MERCHANT_NAME;
    private Field f28_DALYTRAN_MERCHANT_CITY;
    private Field f29_DALYTRAN_MERCHANT_ZIP;
    private Field f2_FD_TRAN_ID;
    private Field f30_DALYTRAN_CARD_NUM;
    private Field f31_DALYTRAN_ORIG_TS;
    private Field f32_DALYTRAN_PROC_TS;
    private Field f33_FILLER;
    private Field f34_DALYTRAN_STATUS;
    private Field f35_DALYTRAN_STAT1;
    private Field f36_DALYTRAN_STAT2;
    private Field f37_CUSTOMER_RECORD;
    private Field f38_CUST_ID;
    private Field f39_CUST_FIRST_NAME;
    private Field f3_FD_CUST_DATA;
    private Field f40_CUST_MIDDLE_NAME;
    private Field f41_CUST_LAST_NAME;
    private Field f42_CUST_ADDR_LINE_1;
    private Field f43_CUST_ADDR_LINE_2;
    private Field f44_CUST_ADDR_LINE_3;
    private Field f45_CUST_ADDR_STATE_CD;
    private Field f46_CUST_ADDR_COUNTRY_CD;
    private Field f47_CUST_ADDR_ZIP;
    private Field f48_CUST_PHONE_NUM_1;
    private Field f49_CUST_PHONE_NUM_2;
    private Field f4_FD_CUSTFILE_REC;
    private Field f50_CUST_SSN;
    private Field f51_CUST_GOVT_ISSUED_ID;
    private Field f52_CUST_DOB_YYYY_MM_DD;
    private Field f53_CUST_EFT_ACCOUNT_ID;
    private Field f54_CUST_PRI_CARD_HOLDER_IND;
    private Field f55_CUST_FICO_CREDIT_SCORE;
    private Field f56_FILLER;
    private Field f57_CUSTFILE_STATUS;
    private Field f58_CUSTFILE_STAT1;
    private Field f59_CUSTFILE_STAT2;
    private Field f5_FD_CUST_ID;
    private Field f60_CARD_XREF_RECORD;
    private Field f61_XREF_CARD_NUM;
    private Field f62_XREF_CUST_ID;
    private Field f63_XREF_ACCT_ID;
    private Field f64_FILLER;
    private Field f65_XREFFILE_STATUS;
    private Field f66_XREFFILE_STAT1;
    private Field f67_XREFFILE_STAT2;
    private Field f68_CARD_RECORD;
    private Field f69_CARD_NUM;
    private Field f6_FD_CUST_DATA;
    private Field f70_CARD_ACCT_ID;
    private Field f71_CARD_CVV_CD;
    private Field f72_CARD_EMBOSSED_NAME;
    private Field f73_CARD_EXPIRAION_DATE;
    private Field f74_CARD_ACTIVE_STATUS;
    private Field f75_FILLER;
    private Field f76_CARDFILE_STATUS;
    private Field f77_CARDFILE_STAT1;
    private Field f78_CARDFILE_STAT2;
    private Field f79_ACCOUNT_RECORD;
    private Field f7_FD_XREFFILE_REC;
    private Field f80_ACCT_ID;
    private Field f81_ACCT_ACTIVE_STATUS;
    private Field f82_ACCT_CURR_BAL;
    private Field f83_ACCT_CREDIT_LIMIT;
    private Field f84_ACCT_CASH_CREDIT_LIMIT;
    private Field f85_ACCT_OPEN_DATE;
    private Field f86_ACCT_EXPIRAION_DATE;
    private Field f87_ACCT_REISSUE_DATE;
    private Field f88_ACCT_CURR_CYC_CREDIT;
    private Field f89_ACCT_CURR_CYC_DEBIT;
    private Field f8_FD_XREF_CARD_NUM;
    private Field f90_ACCT_ADDR_ZIP;
    private Field f91_ACCT_GROUP_ID;
    private Field f92_FILLER;
    private Field f93_ACCTFILE_STATUS;
    private Field f94_ACCTFILE_STAT1;
    private Field f95_ACCTFILE_STAT2;
    private Field f96_TRAN_RECORD;
    private Field f97_TRAN_ID;
    private Field f98_TRAN_TYPE_CD;
    private Field f99_TRAN_CAT_CD;
    private Field f9_FD_XREF_DATA;

    private static Integer id_CustomerRecord(byte[] rec) {
        Storage s = Storage.of(rec);
        return Cobol.num(Field.zoned(s, 0, 9, 0, false, false, false), CS).intValue();
    }

    private static String id_CardXrefRecord(byte[] rec) {
        Storage s = Storage.of(rec);
        return Cobol.text(Field.alphanumeric(s, 0, 16, false), CS);
    }

    private static String id_CardRecord(byte[] rec) {
        Storage s = Storage.of(rec);
        return Cobol.text(Field.alphanumeric(s, 0, 16, false), CS);
    }

    private static Long id_AccountRecord(byte[] rec) {
        Storage s = Storage.of(rec);
        return Cobol.num(Field.zoned(s, 0, 11, 0, false, false, false), CS).longValue();
    }

    private DetFiles.DetFile DALYTRAN_FILE;
    private DetFiles.DetFile CUSTOMER_FILE;
    private DetFiles.DetFile XREF_FILE;
    private DetFiles.DetFile CARD_FILE;
    private DetFiles.DetFile ACCOUNT_FILE;
    private DetFiles.DetFile TRANSACT_FILE;

    private final CustomerRecordRepository customerRecordRepository;
    private final CardXrefRecordRepository cardXrefRecordRepository;
    private final CardRecordRepository cardRecordRepository;
    private final AccountRecordRepository accountRecordRepository;
    private final DatasetResolver datasets;
    private final CobolFiles files;
    private final MainframeClock clock;

    public Cbtrn01cService(CustomerRecordRepository customerRecordRepository, CardXrefRecordRepository cardXrefRecordRepository, CardRecordRepository cardRecordRepository, AccountRecordRepository accountRecordRepository, DatasetResolver datasets, CobolFiles files, MainframeClock clock) {
        this.customerRecordRepository = customerRecordRepository;
        this.cardXrefRecordRepository = cardXrefRecordRepository;
        this.cardRecordRepository = cardRecordRepository;
        this.accountRecordRepository = accountRecordRepository;
        this.datasets = datasets;
        this.files = files;
        this.clock = clock;
        fields0();
    }

    private void fields0() {
        f1_FD_TRAN_RECORD = Field.group(s_FD_TRAN_RECORD, 0, 350);
        f2_FD_TRAN_ID = Field.alphanumeric(s_FD_TRAN_RECORD, 0, 16, false);
        f3_FD_CUST_DATA = Field.alphanumeric(s_FD_TRAN_RECORD, 16, 334, false);
        f4_FD_CUSTFILE_REC = Field.group(s_FD_CUSTFILE_REC, 0, 500);
        f5_FD_CUST_ID = Field.zoned(s_FD_CUSTFILE_REC, 0, 9, 0, false, false, false);
        f6_FD_CUST_DATA = Field.alphanumeric(s_FD_CUSTFILE_REC, 9, 491, false);
        f7_FD_XREFFILE_REC = Field.group(s_FD_XREFFILE_REC, 0, 50);
        f8_FD_XREF_CARD_NUM = Field.alphanumeric(s_FD_XREFFILE_REC, 0, 16, false);
        f9_FD_XREF_DATA = Field.alphanumeric(s_FD_XREFFILE_REC, 16, 34, false);
        f10_FD_CARDFILE_REC = Field.group(s_FD_CARDFILE_REC, 0, 150);
        f11_FD_CARD_NUM = Field.alphanumeric(s_FD_CARDFILE_REC, 0, 16, false);
        f12_FD_CARD_DATA = Field.alphanumeric(s_FD_CARDFILE_REC, 16, 134, false);
        f13_FD_ACCTFILE_REC = Field.group(s_FD_ACCTFILE_REC, 0, 300);
        f14_FD_ACCT_ID = Field.zoned(s_FD_ACCTFILE_REC, 0, 11, 0, false, false, false);
        f15_FD_ACCT_DATA = Field.alphanumeric(s_FD_ACCTFILE_REC, 11, 289, false);
        f16_FD_TRANFILE_REC = Field.group(s_FD_TRANFILE_REC, 0, 350);
        f17_FD_TRANS_ID = Field.alphanumeric(s_FD_TRANFILE_REC, 0, 16, false);
        f18_FD_ACCT_DATA = Field.alphanumeric(s_FD_TRANFILE_REC, 16, 334, false);
        f19_DALYTRAN_RECORD = Field.group(s_DALYTRAN_RECORD, 0, 350);
        f20_DALYTRAN_ID = Field.alphanumeric(s_DALYTRAN_RECORD, 0, 16, false);
        f21_DALYTRAN_TYPE_CD = Field.alphanumeric(s_DALYTRAN_RECORD, 16, 2, false);
        f22_DALYTRAN_CAT_CD = Field.zoned(s_DALYTRAN_RECORD, 18, 4, 0, false, false, false);
        f23_DALYTRAN_SOURCE = Field.alphanumeric(s_DALYTRAN_RECORD, 22, 10, false);
        f24_DALYTRAN_DESC = Field.alphanumeric(s_DALYTRAN_RECORD, 32, 100, false);
        f25_DALYTRAN_AMT = Field.zoned(s_DALYTRAN_RECORD, 132, 11, 2, true, false, false);
        f26_DALYTRAN_MERCHANT_ID = Field.zoned(s_DALYTRAN_RECORD, 143, 9, 0, false, false, false);
        f27_DALYTRAN_MERCHANT_NAME = Field.alphanumeric(s_DALYTRAN_RECORD, 152, 50, false);
        f28_DALYTRAN_MERCHANT_CITY = Field.alphanumeric(s_DALYTRAN_RECORD, 202, 50, false);
        f29_DALYTRAN_MERCHANT_ZIP = Field.alphanumeric(s_DALYTRAN_RECORD, 252, 10, false);
        f30_DALYTRAN_CARD_NUM = Field.alphanumeric(s_DALYTRAN_RECORD, 262, 16, false);
        f31_DALYTRAN_ORIG_TS = Field.alphanumeric(s_DALYTRAN_RECORD, 278, 26, false);
        f32_DALYTRAN_PROC_TS = Field.alphanumeric(s_DALYTRAN_RECORD, 304, 26, false);
        f33_FILLER = Field.alphanumeric(s_DALYTRAN_RECORD, 330, 20, false);
        f34_DALYTRAN_STATUS = Field.group(s_DALYTRAN_STATUS, 0, 2);
        f35_DALYTRAN_STAT1 = Field.alphanumeric(s_DALYTRAN_STATUS, 0, 1, false);
        f36_DALYTRAN_STAT2 = Field.alphanumeric(s_DALYTRAN_STATUS, 1, 1, false);
        f37_CUSTOMER_RECORD = Field.group(s_CUSTOMER_RECORD, 0, 500);
        f38_CUST_ID = Field.zoned(s_CUSTOMER_RECORD, 0, 9, 0, false, false, false);
        f39_CUST_FIRST_NAME = Field.alphanumeric(s_CUSTOMER_RECORD, 9, 25, false);
        f40_CUST_MIDDLE_NAME = Field.alphanumeric(s_CUSTOMER_RECORD, 34, 25, false);
        f41_CUST_LAST_NAME = Field.alphanumeric(s_CUSTOMER_RECORD, 59, 25, false);
        f42_CUST_ADDR_LINE_1 = Field.alphanumeric(s_CUSTOMER_RECORD, 84, 50, false);
        f43_CUST_ADDR_LINE_2 = Field.alphanumeric(s_CUSTOMER_RECORD, 134, 50, false);
        f44_CUST_ADDR_LINE_3 = Field.alphanumeric(s_CUSTOMER_RECORD, 184, 50, false);
        f45_CUST_ADDR_STATE_CD = Field.alphanumeric(s_CUSTOMER_RECORD, 234, 2, false);
        f46_CUST_ADDR_COUNTRY_CD = Field.alphanumeric(s_CUSTOMER_RECORD, 236, 3, false);
        f47_CUST_ADDR_ZIP = Field.alphanumeric(s_CUSTOMER_RECORD, 239, 10, false);
        f48_CUST_PHONE_NUM_1 = Field.alphanumeric(s_CUSTOMER_RECORD, 249, 15, false);
        f49_CUST_PHONE_NUM_2 = Field.alphanumeric(s_CUSTOMER_RECORD, 264, 15, false);
        f50_CUST_SSN = Field.zoned(s_CUSTOMER_RECORD, 279, 9, 0, false, false, false);
        f51_CUST_GOVT_ISSUED_ID = Field.alphanumeric(s_CUSTOMER_RECORD, 288, 20, false);
        f52_CUST_DOB_YYYY_MM_DD = Field.alphanumeric(s_CUSTOMER_RECORD, 308, 10, false);
        f53_CUST_EFT_ACCOUNT_ID = Field.alphanumeric(s_CUSTOMER_RECORD, 318, 10, false);
        f54_CUST_PRI_CARD_HOLDER_IND = Field.alphanumeric(s_CUSTOMER_RECORD, 328, 1, false);
        f55_CUST_FICO_CREDIT_SCORE = Field.zoned(s_CUSTOMER_RECORD, 329, 3, 0, false, false, false);
        f56_FILLER = Field.alphanumeric(s_CUSTOMER_RECORD, 332, 168, false);
        f57_CUSTFILE_STATUS = Field.group(s_CUSTFILE_STATUS, 0, 2);
        f58_CUSTFILE_STAT1 = Field.alphanumeric(s_CUSTFILE_STATUS, 0, 1, false);
        f59_CUSTFILE_STAT2 = Field.alphanumeric(s_CUSTFILE_STATUS, 1, 1, false);
        f60_CARD_XREF_RECORD = Field.group(s_CARD_XREF_RECORD, 0, 50);
        f61_XREF_CARD_NUM = Field.alphanumeric(s_CARD_XREF_RECORD, 0, 16, false);
        f62_XREF_CUST_ID = Field.zoned(s_CARD_XREF_RECORD, 16, 9, 0, false, false, false);
        f63_XREF_ACCT_ID = Field.zoned(s_CARD_XREF_RECORD, 25, 11, 0, false, false, false);
        f64_FILLER = Field.alphanumeric(s_CARD_XREF_RECORD, 36, 14, false);
        f65_XREFFILE_STATUS = Field.group(s_XREFFILE_STATUS, 0, 2);
        f66_XREFFILE_STAT1 = Field.alphanumeric(s_XREFFILE_STATUS, 0, 1, false);
        f67_XREFFILE_STAT2 = Field.alphanumeric(s_XREFFILE_STATUS, 1, 1, false);
        f68_CARD_RECORD = Field.group(s_CARD_RECORD, 0, 150);
        f69_CARD_NUM = Field.alphanumeric(s_CARD_RECORD, 0, 16, false);
        f70_CARD_ACCT_ID = Field.zoned(s_CARD_RECORD, 16, 11, 0, false, false, false);
        f71_CARD_CVV_CD = Field.zoned(s_CARD_RECORD, 27, 3, 0, false, false, false);
        f72_CARD_EMBOSSED_NAME = Field.alphanumeric(s_CARD_RECORD, 30, 50, false);
        f73_CARD_EXPIRAION_DATE = Field.alphanumeric(s_CARD_RECORD, 80, 10, false);
        f74_CARD_ACTIVE_STATUS = Field.alphanumeric(s_CARD_RECORD, 90, 1, false);
        f75_FILLER = Field.alphanumeric(s_CARD_RECORD, 91, 59, false);
        f76_CARDFILE_STATUS = Field.group(s_CARDFILE_STATUS, 0, 2);
        f77_CARDFILE_STAT1 = Field.alphanumeric(s_CARDFILE_STATUS, 0, 1, false);
        f78_CARDFILE_STAT2 = Field.alphanumeric(s_CARDFILE_STATUS, 1, 1, false);
        f79_ACCOUNT_RECORD = Field.group(s_ACCOUNT_RECORD, 0, 300);
        f80_ACCT_ID = Field.zoned(s_ACCOUNT_RECORD, 0, 11, 0, false, false, false);
        f81_ACCT_ACTIVE_STATUS = Field.alphanumeric(s_ACCOUNT_RECORD, 11, 1, false);
        f82_ACCT_CURR_BAL = Field.zoned(s_ACCOUNT_RECORD, 12, 12, 2, true, false, false);
        f83_ACCT_CREDIT_LIMIT = Field.zoned(s_ACCOUNT_RECORD, 24, 12, 2, true, false, false);
        f84_ACCT_CASH_CREDIT_LIMIT = Field.zoned(s_ACCOUNT_RECORD, 36, 12, 2, true, false, false);
        f85_ACCT_OPEN_DATE = Field.alphanumeric(s_ACCOUNT_RECORD, 48, 10, false);
        f86_ACCT_EXPIRAION_DATE = Field.alphanumeric(s_ACCOUNT_RECORD, 58, 10, false);
        f87_ACCT_REISSUE_DATE = Field.alphanumeric(s_ACCOUNT_RECORD, 68, 10, false);
        f88_ACCT_CURR_CYC_CREDIT = Field.zoned(s_ACCOUNT_RECORD, 78, 12, 2, true, false, false);
        f89_ACCT_CURR_CYC_DEBIT = Field.zoned(s_ACCOUNT_RECORD, 90, 12, 2, true, false, false);
        f90_ACCT_ADDR_ZIP = Field.alphanumeric(s_ACCOUNT_RECORD, 102, 10, false);
        f91_ACCT_GROUP_ID = Field.alphanumeric(s_ACCOUNT_RECORD, 112, 10, false);
        f92_FILLER = Field.alphanumeric(s_ACCOUNT_RECORD, 122, 178, false);
        f93_ACCTFILE_STATUS = Field.group(s_ACCTFILE_STATUS, 0, 2);
        f94_ACCTFILE_STAT1 = Field.alphanumeric(s_ACCTFILE_STATUS, 0, 1, false);
        f95_ACCTFILE_STAT2 = Field.alphanumeric(s_ACCTFILE_STATUS, 1, 1, false);
        f96_TRAN_RECORD = Field.group(s_TRAN_RECORD, 0, 350);
        f97_TRAN_ID = Field.alphanumeric(s_TRAN_RECORD, 0, 16, false);
        f98_TRAN_TYPE_CD = Field.alphanumeric(s_TRAN_RECORD, 16, 2, false);
        f99_TRAN_CAT_CD = Field.zoned(s_TRAN_RECORD, 18, 4, 0, false, false, false);
        f100_TRAN_SOURCE = Field.alphanumeric(s_TRAN_RECORD, 22, 10, false);
        f101_TRAN_DESC = Field.alphanumeric(s_TRAN_RECORD, 32, 100, false);
        f102_TRAN_AMT = Field.zoned(s_TRAN_RECORD, 132, 11, 2, true, false, false);
        f103_TRAN_MERCHANT_ID = Field.zoned(s_TRAN_RECORD, 143, 9, 0, false, false, false);
        f104_TRAN_MERCHANT_NAME = Field.alphanumeric(s_TRAN_RECORD, 152, 50, false);
        f105_TRAN_MERCHANT_CITY = Field.alphanumeric(s_TRAN_RECORD, 202, 50, false);
        f106_TRAN_MERCHANT_ZIP = Field.alphanumeric(s_TRAN_RECORD, 252, 10, false);
        f107_TRAN_CARD_NUM = Field.alphanumeric(s_TRAN_RECORD, 262, 16, false);
        f108_TRAN_ORIG_TS = Field.alphanumeric(s_TRAN_RECORD, 278, 26, false);
        f109_TRAN_PROC_TS = Field.alphanumeric(s_TRAN_RECORD, 304, 26, false);
        f110_FILLER = Field.alphanumeric(s_TRAN_RECORD, 330, 20, false);
        f111_TRANFILE_STATUS = Field.group(s_TRANFILE_STATUS, 0, 2);
        f112_TRANFILE_STAT1 = Field.alphanumeric(s_TRANFILE_STATUS, 0, 1, false);
        f113_TRANFILE_STAT2 = Field.alphanumeric(s_TRANFILE_STATUS, 1, 1, false);
        f114_IO_STATUS = Field.group(s_IO_STATUS, 0, 2);
        f115_IO_STAT1 = Field.alphanumeric(s_IO_STATUS, 0, 1, false);
        f116_IO_STAT2 = Field.alphanumeric(s_IO_STATUS, 1, 1, false);
        f117_TWO_BYTES_BINARY = Field.binary(s_TWO_BYTES_BINARY, 0, 4, 0, false, false);
        f118_TWO_BYTES_ALPHA = Field.group(s_TWO_BYTES_BINARY, 0, 2);
        f119_TWO_BYTES_LEFT = Field.alphanumeric(s_TWO_BYTES_BINARY, 0, 1, false);
        f120_TWO_BYTES_RIGHT = Field.alphanumeric(s_TWO_BYTES_BINARY, 1, 1, false);
        f121_IO_STATUS_04 = Field.group(s_IO_STATUS_04, 0, 4);
        f122_IO_STATUS_0401 = Field.zoned(s_IO_STATUS_04, 0, 1, 0, false, false, false);
        f123_IO_STATUS_0403 = Field.zoned(s_IO_STATUS_04, 1, 3, 0, false, false, false);
        f124_APPL_RESULT = Field.binary(s_APPL_RESULT, 0, 9, 0, true, false);
        f125_END_OF_DAILY_TRANS_FILE = Field.alphanumeric(s_END_OF_DAILY_TRANS_FILE, 0, 1, false);
        f126_ABCODE = Field.binary(s_ABCODE, 0, 9, 0, true, false);
        f127_TIMING = Field.binary(s_TIMING, 0, 9, 0, true, false);
        f128_WS_MISC_VARIABLES = Field.group(s_WS_MISC_VARIABLES, 0, 8);
        f129_WS_XREF_READ_STATUS = Field.zoned(s_WS_MISC_VARIABLES, 0, 4, 0, false, false, false);
        f130_WS_ACCT_READ_STATUS = Field.zoned(s_WS_MISC_VARIABLES, 4, 4, 0, false, false, false);
        f131_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        System.arraycopy(IMAGE_s_FD_TRAN_RECORD, 0, s_FD_TRAN_RECORD.bytes, 0, IMAGE_s_FD_TRAN_RECORD.length);
        System.arraycopy(IMAGE_s_FD_CUSTFILE_REC, 0, s_FD_CUSTFILE_REC.bytes, 0, IMAGE_s_FD_CUSTFILE_REC.length);
        System.arraycopy(IMAGE_s_FD_XREFFILE_REC, 0, s_FD_XREFFILE_REC.bytes, 0, IMAGE_s_FD_XREFFILE_REC.length);
        System.arraycopy(IMAGE_s_FD_CARDFILE_REC, 0, s_FD_CARDFILE_REC.bytes, 0, IMAGE_s_FD_CARDFILE_REC.length);
        System.arraycopy(IMAGE_s_FD_ACCTFILE_REC, 0, s_FD_ACCTFILE_REC.bytes, 0, IMAGE_s_FD_ACCTFILE_REC.length);
        System.arraycopy(IMAGE_s_FD_TRANFILE_REC, 0, s_FD_TRANFILE_REC.bytes, 0, IMAGE_s_FD_TRANFILE_REC.length);
        System.arraycopy(IMAGE_s_DALYTRAN_RECORD, 0, s_DALYTRAN_RECORD.bytes, 0, IMAGE_s_DALYTRAN_RECORD.length);
        System.arraycopy(IMAGE_s_DALYTRAN_STATUS, 0, s_DALYTRAN_STATUS.bytes, 0, IMAGE_s_DALYTRAN_STATUS.length);
        System.arraycopy(IMAGE_s_CUSTOMER_RECORD, 0, s_CUSTOMER_RECORD.bytes, 0, IMAGE_s_CUSTOMER_RECORD.length);
        System.arraycopy(IMAGE_s_CUSTFILE_STATUS, 0, s_CUSTFILE_STATUS.bytes, 0, IMAGE_s_CUSTFILE_STATUS.length);
        System.arraycopy(IMAGE_s_CARD_XREF_RECORD, 0, s_CARD_XREF_RECORD.bytes, 0, IMAGE_s_CARD_XREF_RECORD.length);
        System.arraycopy(IMAGE_s_XREFFILE_STATUS, 0, s_XREFFILE_STATUS.bytes, 0, IMAGE_s_XREFFILE_STATUS.length);
        System.arraycopy(IMAGE_s_CARD_RECORD, 0, s_CARD_RECORD.bytes, 0, IMAGE_s_CARD_RECORD.length);
        System.arraycopy(IMAGE_s_CARDFILE_STATUS, 0, s_CARDFILE_STATUS.bytes, 0, IMAGE_s_CARDFILE_STATUS.length);
        System.arraycopy(IMAGE_s_ACCOUNT_RECORD, 0, s_ACCOUNT_RECORD.bytes, 0, IMAGE_s_ACCOUNT_RECORD.length);
        System.arraycopy(IMAGE_s_ACCTFILE_STATUS, 0, s_ACCTFILE_STATUS.bytes, 0, IMAGE_s_ACCTFILE_STATUS.length);
        System.arraycopy(IMAGE_s_TRAN_RECORD, 0, s_TRAN_RECORD.bytes, 0, IMAGE_s_TRAN_RECORD.length);
        System.arraycopy(IMAGE_s_TRANFILE_STATUS, 0, s_TRANFILE_STATUS.bytes, 0, IMAGE_s_TRANFILE_STATUS.length);
        System.arraycopy(IMAGE_s_IO_STATUS, 0, s_IO_STATUS.bytes, 0, IMAGE_s_IO_STATUS.length);
        System.arraycopy(IMAGE_s_TWO_BYTES_BINARY, 0, s_TWO_BYTES_BINARY.bytes, 0, IMAGE_s_TWO_BYTES_BINARY.length);
        System.arraycopy(IMAGE_s_IO_STATUS_04, 0, s_IO_STATUS_04.bytes, 0, IMAGE_s_IO_STATUS_04.length);
        System.arraycopy(IMAGE_s_APPL_RESULT, 0, s_APPL_RESULT.bytes, 0, IMAGE_s_APPL_RESULT.length);
        System.arraycopy(IMAGE_s_END_OF_DAILY_TRANS_FILE, 0, s_END_OF_DAILY_TRANS_FILE.bytes, 0, IMAGE_s_END_OF_DAILY_TRANS_FILE.length);
        System.arraycopy(IMAGE_s_ABCODE, 0, s_ABCODE.bytes, 0, IMAGE_s_ABCODE.length);
        System.arraycopy(IMAGE_s_TIMING, 0, s_TIMING.bytes, 0, IMAGE_s_TIMING.length);
        System.arraycopy(IMAGE_s_WS_MISC_VARIABLES, 0, s_WS_MISC_VARIABLES.bytes, 0, IMAGE_s_WS_MISC_VARIABLES.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
        performDepth = 0;
        try {
            perform(0, 17);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f131_GG_RETURN_CODE, CS).intValue();
    }

    public void executeCbtrn01c() {
        runBatch(List.of(), null);
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
            System.arraycopy(IMAGE_s_FD_TRAN_RECORD, 0, s_FD_TRAN_RECORD.bytes, 0, IMAGE_s_FD_TRAN_RECORD.length);
            System.arraycopy(IMAGE_s_FD_CUSTFILE_REC, 0, s_FD_CUSTFILE_REC.bytes, 0, IMAGE_s_FD_CUSTFILE_REC.length);
            System.arraycopy(IMAGE_s_FD_XREFFILE_REC, 0, s_FD_XREFFILE_REC.bytes, 0, IMAGE_s_FD_XREFFILE_REC.length);
            System.arraycopy(IMAGE_s_FD_CARDFILE_REC, 0, s_FD_CARDFILE_REC.bytes, 0, IMAGE_s_FD_CARDFILE_REC.length);
            System.arraycopy(IMAGE_s_FD_ACCTFILE_REC, 0, s_FD_ACCTFILE_REC.bytes, 0, IMAGE_s_FD_ACCTFILE_REC.length);
            System.arraycopy(IMAGE_s_FD_TRANFILE_REC, 0, s_FD_TRANFILE_REC.bytes, 0, IMAGE_s_FD_TRANFILE_REC.length);
            System.arraycopy(IMAGE_s_DALYTRAN_RECORD, 0, s_DALYTRAN_RECORD.bytes, 0, IMAGE_s_DALYTRAN_RECORD.length);
            System.arraycopy(IMAGE_s_DALYTRAN_STATUS, 0, s_DALYTRAN_STATUS.bytes, 0, IMAGE_s_DALYTRAN_STATUS.length);
            System.arraycopy(IMAGE_s_CUSTOMER_RECORD, 0, s_CUSTOMER_RECORD.bytes, 0, IMAGE_s_CUSTOMER_RECORD.length);
            System.arraycopy(IMAGE_s_CUSTFILE_STATUS, 0, s_CUSTFILE_STATUS.bytes, 0, IMAGE_s_CUSTFILE_STATUS.length);
            System.arraycopy(IMAGE_s_CARD_XREF_RECORD, 0, s_CARD_XREF_RECORD.bytes, 0, IMAGE_s_CARD_XREF_RECORD.length);
            System.arraycopy(IMAGE_s_XREFFILE_STATUS, 0, s_XREFFILE_STATUS.bytes, 0, IMAGE_s_XREFFILE_STATUS.length);
            System.arraycopy(IMAGE_s_CARD_RECORD, 0, s_CARD_RECORD.bytes, 0, IMAGE_s_CARD_RECORD.length);
            System.arraycopy(IMAGE_s_CARDFILE_STATUS, 0, s_CARDFILE_STATUS.bytes, 0, IMAGE_s_CARDFILE_STATUS.length);
            System.arraycopy(IMAGE_s_ACCOUNT_RECORD, 0, s_ACCOUNT_RECORD.bytes, 0, IMAGE_s_ACCOUNT_RECORD.length);
            System.arraycopy(IMAGE_s_ACCTFILE_STATUS, 0, s_ACCTFILE_STATUS.bytes, 0, IMAGE_s_ACCTFILE_STATUS.length);
            System.arraycopy(IMAGE_s_TRAN_RECORD, 0, s_TRAN_RECORD.bytes, 0, IMAGE_s_TRAN_RECORD.length);
            System.arraycopy(IMAGE_s_TRANFILE_STATUS, 0, s_TRANFILE_STATUS.bytes, 0, IMAGE_s_TRANFILE_STATUS.length);
            System.arraycopy(IMAGE_s_IO_STATUS, 0, s_IO_STATUS.bytes, 0, IMAGE_s_IO_STATUS.length);
            System.arraycopy(IMAGE_s_TWO_BYTES_BINARY, 0, s_TWO_BYTES_BINARY.bytes, 0, IMAGE_s_TWO_BYTES_BINARY.length);
            System.arraycopy(IMAGE_s_IO_STATUS_04, 0, s_IO_STATUS_04.bytes, 0, IMAGE_s_IO_STATUS_04.length);
            System.arraycopy(IMAGE_s_APPL_RESULT, 0, s_APPL_RESULT.bytes, 0, IMAGE_s_APPL_RESULT.length);
            System.arraycopy(IMAGE_s_END_OF_DAILY_TRANS_FILE, 0, s_END_OF_DAILY_TRANS_FILE.bytes, 0, IMAGE_s_END_OF_DAILY_TRANS_FILE.length);
            System.arraycopy(IMAGE_s_ABCODE, 0, s_ABCODE.bytes, 0, IMAGE_s_ABCODE.length);
            System.arraycopy(IMAGE_s_TIMING, 0, s_TIMING.bytes, 0, IMAGE_s_TIMING.length);
            System.arraycopy(IMAGE_s_WS_MISC_VARIABLES, 0, s_WS_MISC_VARIABLES.bytes, 0, IMAGE_s_WS_MISC_VARIABLES.length);
            System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
            DALYTRAN_FILE = new DetFiles.Sequential(files, "DALYTRAN", () -> datasets.path(dd(dds, "DALYTRAN")), s_FD_TRAN_RECORD, 0, 350);
            CUSTOMER_FILE = new DetFiles.Indexed<CustomerRecord>(files, "CUSTFILE", s_FD_CUSTFILE_REC, 0, 500, 0, 9, customerRecordRepository::findAll, e -> e.toRecord(CS), b -> CustomerRecord.fromRecord(b, CS), customerRecordRepository::save, CS).withFindById(rec -> customerRecordRepository.findById(id_CustomerRecord(rec)));
            XREF_FILE = new DetFiles.Indexed<CardXrefRecord>(files, "XREFFILE", s_FD_XREFFILE_REC, 0, 50, 0, 16, cardXrefRecordRepository::findAll, e -> e.toRecord(CS), b -> CardXrefRecord.fromRecord(b, CS), cardXrefRecordRepository::save, CS).withFindById(rec -> cardXrefRecordRepository.findById(id_CardXrefRecord(rec)));
            CARD_FILE = new DetFiles.Indexed<CardRecord>(files, "CARDFILE", s_FD_CARDFILE_REC, 0, 150, 0, 16, cardRecordRepository::findAll, e -> e.toRecord(CS), b -> CardRecord.fromRecord(b, CS), cardRecordRepository::save, CS).withFindById(rec -> cardRecordRepository.findById(id_CardRecord(rec)));
            ACCOUNT_FILE = new DetFiles.Indexed<AccountRecord>(files, "ACCTFILE", s_FD_ACCTFILE_REC, 0, 300, 0, 11, accountRecordRepository::findAll, e -> e.toRecord(CS), b -> AccountRecord.fromRecord(b, CS), accountRecordRepository::save, CS).withFindById(rec -> accountRecordRepository.findById(id_AccountRecord(rec)));
            TRANSACT_FILE = new DetFiles.Unbound(files, "TRANFILE");
            try {
                perform(0, 17);
            } catch (Goback g) {
                // the program ended
            }
            return Cobol.num(f131_GG_RETURN_CODE, CS).intValue();
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
                if (next >= 18) {
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
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** MAIN-PARA. */
    private int p0() {
        // DISPLAY 'START OF EXECUTION OF PROGRAM CBTRN01C'
        Sysout.display("START OF EXECUTION OF PROGRAM CBTRN01C");
        // PERFORM 0000-DALYTRAN-OPEN
        perform(4, 4);
        // PERFORM 0100-CUSTFILE-OPEN
        perform(5, 5);
        // PERFORM 0200-XREFFILE-OPEN
        perform(6, 6);
        // PERFORM 0300-CARDFILE-OPEN
        perform(7, 7);
        // PERFORM 0400-ACCTFILE-OPEN
        perform(8, 8);
        // PERFORM 0500-TRANFILE-OPEN
        perform(9, 9);
        // PERFORM UNTIL END-OF-DAILY-TRANS-FILE = 'Y'
        while (!(Cobol.compare(f125_END_OF_DAILY_TRANS_FILE, "Y", CS) == 0)) {
            // IF END-OF-DAILY-TRANS-FILE = 'N'
            if (Cobol.compare(f125_END_OF_DAILY_TRANS_FILE, "N", CS) == 0) {
                // PERFORM 1000-DALYTRAN-GET-NEXT
                perform(1, 1);
                // IF END-OF-DAILY-TRANS-FILE = 'N'
                if (Cobol.compare(f125_END_OF_DAILY_TRANS_FILE, "N", CS) == 0) {
                    // DISPLAY DALYTRAN-RECORD
                    Sysout.display(Cobol.displayText(f19_DALYTRAN_RECORD, CS));
                }
                // MOVE 0 TO WS-XREF-READ-STATUS
                Cobol.move(D0, f129_WS_XREF_READ_STATUS, CS);
                // MOVE DALYTRAN-CARD-NUM TO XREF-CARD-NUM
                Cobol.move(f30_DALYTRAN_CARD_NUM, f61_XREF_CARD_NUM, CS);
                // PERFORM 2000-LOOKUP-XREF
                perform(2, 2);
                // IF WS-XREF-READ-STATUS = 0
                if (Cobol.num(f129_WS_XREF_READ_STATUS, CS).compareTo(D0) == 0) {
                    // MOVE 0 TO WS-ACCT-READ-STATUS
                    Cobol.move(D0, f130_WS_ACCT_READ_STATUS, CS);
                    // MOVE XREF-ACCT-ID TO ACCT-ID
                    Cobol.move(f63_XREF_ACCT_ID, f80_ACCT_ID, CS);
                    // PERFORM 3000-READ-ACCOUNT
                    perform(3, 3);
                    // IF WS-ACCT-READ-STATUS NOT = 0
                    if (!(Cobol.num(f130_WS_ACCT_READ_STATUS, CS).compareTo(D0) == 0)) {
                        // DISPLAY 'ACCOUNT ' ACCT-ID ' NOT FOUND'
                        Sysout.display("ACCOUNT ", Cobol.displayText(f80_ACCT_ID, CS), " NOT FOUND");
                    }
                } else {
                    // DISPLAY 'CARD NUMBER ' DALYTRAN-CARD-NUM ' COULD NOT BE VERIFIED. SKIPPING TRANSACTION ID-' DALYTRAN-ID
                    Sysout.display("CARD NUMBER ", Cobol.displayText(f30_DALYTRAN_CARD_NUM, CS), " COULD NOT BE VERIFIED. SKIPPING TRANSACTION ID-", Cobol.displayText(f20_DALYTRAN_ID, CS));
                }
            }
        }
        // PERFORM 9000-DALYTRAN-CLOSE
        perform(10, 10);
        // PERFORM 9100-CUSTFILE-CLOSE
        perform(11, 11);
        // PERFORM 9200-XREFFILE-CLOSE
        perform(12, 12);
        // PERFORM 9300-CARDFILE-CLOSE
        perform(13, 13);
        // PERFORM 9400-ACCTFILE-CLOSE
        perform(14, 14);
        // PERFORM 9500-TRANFILE-CLOSE
        perform(15, 15);
        // DISPLAY 'END OF EXECUTION OF PROGRAM CBTRN01C'
        Sysout.display("END OF EXECUTION OF PROGRAM CBTRN01C");
        // GOBACK
        if (true) throw new Goback();
        return 1;
    }

    /** 1000-DALYTRAN-GET-NEXT. */
    private int p1() {
        // READ DALYTRAN-FILE INTO DALYTRAN-RECORD
        String st1 = DALYTRAN_FILE.readNext();
        Cobol.move(st1, f34_DALYTRAN_STATUS, CS);
        if (st1.startsWith("0")) {
            Cobol.move(f1_FD_TRAN_RECORD, f19_DALYTRAN_RECORD, CS);
        }
        // IF DALYTRAN-STATUS = '00'
        if (Cobol.compare(f34_DALYTRAN_STATUS, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            Cobol.move(D0, f124_APPL_RESULT, CS);
        } else {
            // ELSE IF DALYTRAN-STATUS = '10'
            if (Cobol.compare(f34_DALYTRAN_STATUS, "10", CS) == 0) {
                // MOVE 16 TO APPL-RESULT
                Cobol.move(D16, f124_APPL_RESULT, CS);
            } else {
                // MOVE 12 TO APPL-RESULT
                Cobol.move(D12, f124_APPL_RESULT, CS);
            }
        }
        // IF APPL-AOK
        if (Cobol.compare(f124_APPL_RESULT, D0, CS) == 0) {
            // CONTINUE
        } else {
            // ELSE IF APPL-EOF
            if (Cobol.compare(f124_APPL_RESULT, D16, CS) == 0) {
                // MOVE 'Y' TO END-OF-DAILY-TRANS-FILE
                Cobol.move("Y", f125_END_OF_DAILY_TRANS_FILE, CS);
            } else {
                // DISPLAY 'ERROR READING DAILY TRANSACTION FILE'
                Sysout.display("ERROR READING DAILY TRANSACTION FILE");
                // MOVE DALYTRAN-STATUS TO IO-STATUS
                Cobol.move(f34_DALYTRAN_STATUS, f114_IO_STATUS, CS);
                // PERFORM Z-DISPLAY-IO-STATUS
                perform(17, 17);
                // PERFORM Z-ABEND-PROGRAM
                perform(16, 16);
            }
        }
        // EXIT
        return 2;
    }

    /** 2000-LOOKUP-XREF. */
    private int p2() {
        // MOVE XREF-CARD-NUM TO FD-XREF-CARD-NUM
        Cobol.move(f61_XREF_CARD_NUM, f8_FD_XREF_CARD_NUM, CS);
        // READ XREF-FILE RECORD INTO CARD-XREF-RECORD KEY IS FD-XREF-CARD-NUM
        String st2 = XREF_FILE.readKey(0, 16);
        Cobol.move(st2, f65_XREFFILE_STATUS, CS);
        if (st2.startsWith("0")) {
            Cobol.move(f7_FD_XREFFILE_REC, f60_CARD_XREF_RECORD, CS);
        }
        if (st2.equals("21") || st2.equals("22") || st2.equals("23") || st2.equals("24")) {
            // DISPLAY 'INVALID CARD NUMBER FOR XREF'
            Sysout.display("INVALID CARD NUMBER FOR XREF");
            // MOVE 4 TO WS-XREF-READ-STATUS
            Cobol.move(D4, f129_WS_XREF_READ_STATUS, CS);
        }
        if (st2.startsWith("0")) {
            // DISPLAY 'SUCCESSFUL READ OF XREF'
            Sysout.display("SUCCESSFUL READ OF XREF");
            // DISPLAY 'CARD NUMBER: ' XREF-CARD-NUM
            Sysout.display("CARD NUMBER: ", Cobol.displayText(f61_XREF_CARD_NUM, CS));
            // DISPLAY 'ACCOUNT ID : ' XREF-ACCT-ID
            Sysout.display("ACCOUNT ID : ", Cobol.displayText(f63_XREF_ACCT_ID, CS));
            // DISPLAY 'CUSTOMER ID: ' XREF-CUST-ID
            Sysout.display("CUSTOMER ID: ", Cobol.displayText(f62_XREF_CUST_ID, CS));
        }
        return 3;
    }

    /** 3000-READ-ACCOUNT. */
    private int p3() {
        // MOVE ACCT-ID TO FD-ACCT-ID
        Cobol.move(f80_ACCT_ID, f14_FD_ACCT_ID, CS);
        // READ ACCOUNT-FILE RECORD INTO ACCOUNT-RECORD KEY IS FD-ACCT-ID
        String st3 = ACCOUNT_FILE.readKey(0, 11);
        Cobol.move(st3, f93_ACCTFILE_STATUS, CS);
        if (st3.startsWith("0")) {
            Cobol.move(f13_FD_ACCTFILE_REC, f79_ACCOUNT_RECORD, CS);
        }
        if (st3.equals("21") || st3.equals("22") || st3.equals("23") || st3.equals("24")) {
            // DISPLAY 'INVALID ACCOUNT NUMBER FOUND'
            Sysout.display("INVALID ACCOUNT NUMBER FOUND");
            // MOVE 4 TO WS-ACCT-READ-STATUS
            Cobol.move(D4, f130_WS_ACCT_READ_STATUS, CS);
        }
        if (st3.startsWith("0")) {
            // DISPLAY 'SUCCESSFUL READ OF ACCOUNT FILE'
            Sysout.display("SUCCESSFUL READ OF ACCOUNT FILE");
        }
        return 4;
    }

    /** 0000-DALYTRAN-OPEN. */
    private int p4() {
        // MOVE 8 TO APPL-RESULT
        Cobol.move(D8, f124_APPL_RESULT, CS);
        // OPEN INPUT DALYTRAN-FILE
        String st4 = DALYTRAN_FILE.open("INPUT");
        Cobol.move(st4, f34_DALYTRAN_STATUS, CS);
        // IF DALYTRAN-STATUS = '00'
        if (Cobol.compare(f34_DALYTRAN_STATUS, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            Cobol.move(D0, f124_APPL_RESULT, CS);
        } else {
            // MOVE 12 TO APPL-RESULT
            Cobol.move(D12, f124_APPL_RESULT, CS);
        }
        // IF APPL-AOK
        if (Cobol.compare(f124_APPL_RESULT, D0, CS) == 0) {
            // CONTINUE
        } else {
            // DISPLAY 'ERROR OPENING DAILY TRANSACTION FILE'
            Sysout.display("ERROR OPENING DAILY TRANSACTION FILE");
            // MOVE DALYTRAN-STATUS TO IO-STATUS
            Cobol.move(f34_DALYTRAN_STATUS, f114_IO_STATUS, CS);
            // PERFORM Z-DISPLAY-IO-STATUS
            perform(17, 17);
            // PERFORM Z-ABEND-PROGRAM
            perform(16, 16);
        }
        // EXIT
        return 5;
    }

    /** 0100-CUSTFILE-OPEN. */
    private int p5() {
        // MOVE 8 TO APPL-RESULT
        Cobol.move(D8, f124_APPL_RESULT, CS);
        // OPEN INPUT CUSTOMER-FILE
        String st5 = CUSTOMER_FILE.open("INPUT");
        Cobol.move(st5, f57_CUSTFILE_STATUS, CS);
        // IF CUSTFILE-STATUS = '00'
        if (Cobol.compare(f57_CUSTFILE_STATUS, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            Cobol.move(D0, f124_APPL_RESULT, CS);
        } else {
            // MOVE 12 TO APPL-RESULT
            Cobol.move(D12, f124_APPL_RESULT, CS);
        }
        // IF APPL-AOK
        if (Cobol.compare(f124_APPL_RESULT, D0, CS) == 0) {
            // CONTINUE
        } else {
            // DISPLAY 'ERROR OPENING CUSTOMER FILE'
            Sysout.display("ERROR OPENING CUSTOMER FILE");
            // MOVE CUSTFILE-STATUS TO IO-STATUS
            Cobol.move(f57_CUSTFILE_STATUS, f114_IO_STATUS, CS);
            // PERFORM Z-DISPLAY-IO-STATUS
            perform(17, 17);
            // PERFORM Z-ABEND-PROGRAM
            perform(16, 16);
        }
        // EXIT
        return 6;
    }

    /** 0200-XREFFILE-OPEN. */
    private int p6() {
        // MOVE 8 TO APPL-RESULT
        Cobol.move(D8, f124_APPL_RESULT, CS);
        // OPEN INPUT XREF-FILE
        String st6 = XREF_FILE.open("INPUT");
        Cobol.move(st6, f65_XREFFILE_STATUS, CS);
        // IF XREFFILE-STATUS = '00'
        if (Cobol.compare(f65_XREFFILE_STATUS, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            Cobol.move(D0, f124_APPL_RESULT, CS);
        } else {
            // MOVE 12 TO APPL-RESULT
            Cobol.move(D12, f124_APPL_RESULT, CS);
        }
        // IF APPL-AOK
        if (Cobol.compare(f124_APPL_RESULT, D0, CS) == 0) {
            // CONTINUE
        } else {
            // DISPLAY 'ERROR OPENING CROSS REF FILE'
            Sysout.display("ERROR OPENING CROSS REF FILE");
            // MOVE XREFFILE-STATUS TO IO-STATUS
            Cobol.move(f65_XREFFILE_STATUS, f114_IO_STATUS, CS);
            // PERFORM Z-DISPLAY-IO-STATUS
            perform(17, 17);
            // PERFORM Z-ABEND-PROGRAM
            perform(16, 16);
        }
        // EXIT
        return 7;
    }

    /** 0300-CARDFILE-OPEN. */
    private int p7() {
        // MOVE 8 TO APPL-RESULT
        Cobol.move(D8, f124_APPL_RESULT, CS);
        // OPEN INPUT CARD-FILE
        String st7 = CARD_FILE.open("INPUT");
        Cobol.move(st7, f76_CARDFILE_STATUS, CS);
        // IF CARDFILE-STATUS = '00'
        if (Cobol.compare(f76_CARDFILE_STATUS, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            Cobol.move(D0, f124_APPL_RESULT, CS);
        } else {
            // MOVE 12 TO APPL-RESULT
            Cobol.move(D12, f124_APPL_RESULT, CS);
        }
        // IF APPL-AOK
        if (Cobol.compare(f124_APPL_RESULT, D0, CS) == 0) {
            // CONTINUE
        } else {
            // DISPLAY 'ERROR OPENING CARD FILE'
            Sysout.display("ERROR OPENING CARD FILE");
            // MOVE CARDFILE-STATUS TO IO-STATUS
            Cobol.move(f76_CARDFILE_STATUS, f114_IO_STATUS, CS);
            // PERFORM Z-DISPLAY-IO-STATUS
            perform(17, 17);
            // PERFORM Z-ABEND-PROGRAM
            perform(16, 16);
        }
        // EXIT
        return 8;
    }

    /** 0400-ACCTFILE-OPEN. */
    private int p8() {
        // MOVE 8 TO APPL-RESULT
        Cobol.move(D8, f124_APPL_RESULT, CS);
        // OPEN INPUT ACCOUNT-FILE
        String st8 = ACCOUNT_FILE.open("INPUT");
        Cobol.move(st8, f93_ACCTFILE_STATUS, CS);
        // IF ACCTFILE-STATUS = '00'
        if (Cobol.compare(f93_ACCTFILE_STATUS, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            Cobol.move(D0, f124_APPL_RESULT, CS);
        } else {
            // MOVE 12 TO APPL-RESULT
            Cobol.move(D12, f124_APPL_RESULT, CS);
        }
        // IF APPL-AOK
        if (Cobol.compare(f124_APPL_RESULT, D0, CS) == 0) {
            // CONTINUE
        } else {
            // DISPLAY 'ERROR OPENING ACCOUNT FILE'
            Sysout.display("ERROR OPENING ACCOUNT FILE");
            // MOVE ACCTFILE-STATUS TO IO-STATUS
            Cobol.move(f93_ACCTFILE_STATUS, f114_IO_STATUS, CS);
            // PERFORM Z-DISPLAY-IO-STATUS
            perform(17, 17);
            // PERFORM Z-ABEND-PROGRAM
            perform(16, 16);
        }
        // EXIT
        return 9;
    }

    /** 0500-TRANFILE-OPEN. */
    private int p9() {
        // MOVE 8 TO APPL-RESULT
        Cobol.move(D8, f124_APPL_RESULT, CS);
        // OPEN INPUT TRANSACT-FILE
        String st9 = TRANSACT_FILE.open("INPUT");
        Cobol.move(st9, f111_TRANFILE_STATUS, CS);
        // IF TRANFILE-STATUS = '00'
        if (Cobol.compare(f111_TRANFILE_STATUS, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            Cobol.move(D0, f124_APPL_RESULT, CS);
        } else {
            // MOVE 12 TO APPL-RESULT
            Cobol.move(D12, f124_APPL_RESULT, CS);
        }
        // IF APPL-AOK
        if (Cobol.compare(f124_APPL_RESULT, D0, CS) == 0) {
            // CONTINUE
        } else {
            // DISPLAY 'ERROR OPENING TRANSACTION FILE'
            Sysout.display("ERROR OPENING TRANSACTION FILE");
            // MOVE TRANFILE-STATUS TO IO-STATUS
            Cobol.move(f111_TRANFILE_STATUS, f114_IO_STATUS, CS);
            // PERFORM Z-DISPLAY-IO-STATUS
            perform(17, 17);
            // PERFORM Z-ABEND-PROGRAM
            perform(16, 16);
        }
        // EXIT
        return 10;
    }

    /** 9000-DALYTRAN-CLOSE. */
    private int p10() {
        // ADD 8 TO ZERO GIVING APPL-RESULT
        BigDecimal v10 = D8.add(BigDecimal.ZERO);
        Cobol.store(f124_APPL_RESULT, v10, false, CS);
        // CLOSE DALYTRAN-FILE
        String st11 = DALYTRAN_FILE.close();
        Cobol.move(st11, f34_DALYTRAN_STATUS, CS);
        // IF DALYTRAN-STATUS = '00'
        if (Cobol.compare(f34_DALYTRAN_STATUS, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            Cobol.move(D0, f124_APPL_RESULT, CS);
        } else {
            // MOVE 12 TO APPL-RESULT
            Cobol.move(D12, f124_APPL_RESULT, CS);
        }
        // IF APPL-AOK
        if (Cobol.compare(f124_APPL_RESULT, D0, CS) == 0) {
            // CONTINUE
        } else {
            // DISPLAY 'ERROR CLOSING CUSTOMER FILE'
            Sysout.display("ERROR CLOSING CUSTOMER FILE");
            // MOVE CUSTFILE-STATUS TO IO-STATUS
            Cobol.move(f57_CUSTFILE_STATUS, f114_IO_STATUS, CS);
            // PERFORM Z-DISPLAY-IO-STATUS
            perform(17, 17);
            // PERFORM Z-ABEND-PROGRAM
            perform(16, 16);
        }
        // EXIT
        return 11;
    }

    /** 9100-CUSTFILE-CLOSE. */
    private int p11() {
        // ADD 8 TO ZERO GIVING APPL-RESULT
        BigDecimal v12 = D8.add(BigDecimal.ZERO);
        Cobol.store(f124_APPL_RESULT, v12, false, CS);
        // CLOSE CUSTOMER-FILE
        String st13 = CUSTOMER_FILE.close();
        Cobol.move(st13, f57_CUSTFILE_STATUS, CS);
        // IF CUSTFILE-STATUS = '00'
        if (Cobol.compare(f57_CUSTFILE_STATUS, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            Cobol.move(D0, f124_APPL_RESULT, CS);
        } else {
            // MOVE 12 TO APPL-RESULT
            Cobol.move(D12, f124_APPL_RESULT, CS);
        }
        // IF APPL-AOK
        if (Cobol.compare(f124_APPL_RESULT, D0, CS) == 0) {
            // CONTINUE
        } else {
            // DISPLAY 'ERROR CLOSING CUSTOMER FILE'
            Sysout.display("ERROR CLOSING CUSTOMER FILE");
            // MOVE CUSTFILE-STATUS TO IO-STATUS
            Cobol.move(f57_CUSTFILE_STATUS, f114_IO_STATUS, CS);
            // PERFORM Z-DISPLAY-IO-STATUS
            perform(17, 17);
            // PERFORM Z-ABEND-PROGRAM
            perform(16, 16);
        }
        // EXIT
        return 12;
    }

    /** 9200-XREFFILE-CLOSE. */
    private int p12() {
        // ADD 8 TO ZERO GIVING APPL-RESULT
        BigDecimal v14 = D8.add(BigDecimal.ZERO);
        Cobol.store(f124_APPL_RESULT, v14, false, CS);
        // CLOSE XREF-FILE
        String st15 = XREF_FILE.close();
        Cobol.move(st15, f65_XREFFILE_STATUS, CS);
        // IF XREFFILE-STATUS = '00'
        if (Cobol.compare(f65_XREFFILE_STATUS, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            Cobol.move(D0, f124_APPL_RESULT, CS);
        } else {
            // MOVE 12 TO APPL-RESULT
            Cobol.move(D12, f124_APPL_RESULT, CS);
        }
        // IF APPL-AOK
        if (Cobol.compare(f124_APPL_RESULT, D0, CS) == 0) {
            // CONTINUE
        } else {
            // DISPLAY 'ERROR CLOSING CROSS REF FILE'
            Sysout.display("ERROR CLOSING CROSS REF FILE");
            // MOVE XREFFILE-STATUS TO IO-STATUS
            Cobol.move(f65_XREFFILE_STATUS, f114_IO_STATUS, CS);
            // PERFORM Z-DISPLAY-IO-STATUS
            perform(17, 17);
            // PERFORM Z-ABEND-PROGRAM
            perform(16, 16);
        }
        // EXIT
        return 13;
    }

    /** 9300-CARDFILE-CLOSE. */
    private int p13() {
        // ADD 8 TO ZERO GIVING APPL-RESULT
        BigDecimal v16 = D8.add(BigDecimal.ZERO);
        Cobol.store(f124_APPL_RESULT, v16, false, CS);
        // CLOSE CARD-FILE
        String st17 = CARD_FILE.close();
        Cobol.move(st17, f76_CARDFILE_STATUS, CS);
        // IF CARDFILE-STATUS = '00'
        if (Cobol.compare(f76_CARDFILE_STATUS, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            Cobol.move(D0, f124_APPL_RESULT, CS);
        } else {
            // MOVE 12 TO APPL-RESULT
            Cobol.move(D12, f124_APPL_RESULT, CS);
        }
        // IF APPL-AOK
        if (Cobol.compare(f124_APPL_RESULT, D0, CS) == 0) {
            // CONTINUE
        } else {
            // DISPLAY 'ERROR CLOSING CARD FILE'
            Sysout.display("ERROR CLOSING CARD FILE");
            // MOVE CARDFILE-STATUS TO IO-STATUS
            Cobol.move(f76_CARDFILE_STATUS, f114_IO_STATUS, CS);
            // PERFORM Z-DISPLAY-IO-STATUS
            perform(17, 17);
            // PERFORM Z-ABEND-PROGRAM
            perform(16, 16);
        }
        // EXIT
        return 14;
    }

    /** 9400-ACCTFILE-CLOSE. */
    private int p14() {
        // ADD 8 TO ZERO GIVING APPL-RESULT
        BigDecimal v18 = D8.add(BigDecimal.ZERO);
        Cobol.store(f124_APPL_RESULT, v18, false, CS);
        // CLOSE ACCOUNT-FILE
        String st19 = ACCOUNT_FILE.close();
        Cobol.move(st19, f93_ACCTFILE_STATUS, CS);
        // IF ACCTFILE-STATUS = '00'
        if (Cobol.compare(f93_ACCTFILE_STATUS, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            Cobol.move(D0, f124_APPL_RESULT, CS);
        } else {
            // MOVE 12 TO APPL-RESULT
            Cobol.move(D12, f124_APPL_RESULT, CS);
        }
        // IF APPL-AOK
        if (Cobol.compare(f124_APPL_RESULT, D0, CS) == 0) {
            // CONTINUE
        } else {
            // DISPLAY 'ERROR CLOSING ACCOUNT FILE'
            Sysout.display("ERROR CLOSING ACCOUNT FILE");
            // MOVE ACCTFILE-STATUS TO IO-STATUS
            Cobol.move(f93_ACCTFILE_STATUS, f114_IO_STATUS, CS);
            // PERFORM Z-DISPLAY-IO-STATUS
            perform(17, 17);
            // PERFORM Z-ABEND-PROGRAM
            perform(16, 16);
        }
        // EXIT
        return 15;
    }

    /** 9500-TRANFILE-CLOSE. */
    private int p15() {
        // ADD 8 TO ZERO GIVING APPL-RESULT
        BigDecimal v20 = D8.add(BigDecimal.ZERO);
        Cobol.store(f124_APPL_RESULT, v20, false, CS);
        // CLOSE TRANSACT-FILE
        String st21 = TRANSACT_FILE.close();
        Cobol.move(st21, f111_TRANFILE_STATUS, CS);
        // IF TRANFILE-STATUS = '00'
        if (Cobol.compare(f111_TRANFILE_STATUS, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            Cobol.move(D0, f124_APPL_RESULT, CS);
        } else {
            // MOVE 12 TO APPL-RESULT
            Cobol.move(D12, f124_APPL_RESULT, CS);
        }
        // IF APPL-AOK
        if (Cobol.compare(f124_APPL_RESULT, D0, CS) == 0) {
            // CONTINUE
        } else {
            // DISPLAY 'ERROR CLOSING TRANSACTION FILE'
            Sysout.display("ERROR CLOSING TRANSACTION FILE");
            // MOVE TRANFILE-STATUS TO IO-STATUS
            Cobol.move(f111_TRANFILE_STATUS, f114_IO_STATUS, CS);
            // PERFORM Z-DISPLAY-IO-STATUS
            perform(17, 17);
            // PERFORM Z-ABEND-PROGRAM
            perform(16, 16);
        }
        // EXIT
        return 16;
    }

    /** Z-ABEND-PROGRAM. */
    private int p16() {
        // DISPLAY 'ABENDING PROGRAM'
        Sysout.display("ABENDING PROGRAM");
        // MOVE 0 TO TIMING
        Cobol.move(D0, f127_TIMING, CS);
        // MOVE 999 TO ABCODE
        Cobol.move(D999, f126_ABCODE, CS);
        // CALL 'CEE3ABD' USING ABCODE, TIMING
        if (true) throw CobolAbend.user(Cobol.num(f126_ABCODE, CS).intValue(), "CEE3ABD");
        return 17;
    }

    /** Z-DISPLAY-IO-STATUS. */
    private int p17() {
        // IF IO-STATUS NOT NUMERIC OR IO-STAT1 = '9'
        if ((!(Cobol.isNumeric(f114_IO_STATUS, CS)) || Cobol.compare(f115_IO_STAT1, "9", CS) == 0)) {
            // MOVE IO-STAT1 TO IO-STATUS-04(1:1)
            Cobol.move(f115_IO_STAT1, f121_IO_STATUS_04.ref(1, Integer.valueOf(1)), CS);
            // MOVE 0 TO TWO-BYTES-BINARY
            Cobol.move(D0, f117_TWO_BYTES_BINARY, CS);
            // MOVE IO-STAT2 TO TWO-BYTES-RIGHT
            Cobol.move(f116_IO_STAT2, f120_TWO_BYTES_RIGHT, CS);
            // MOVE TWO-BYTES-BINARY TO IO-STATUS-0403
            Cobol.move(f117_TWO_BYTES_BINARY, f123_IO_STATUS_0403, CS);
            // DISPLAY 'FILE STATUS IS: NNNN' IO-STATUS-04
            Sysout.display("FILE STATUS IS: NNNN", Cobol.displayText(f121_IO_STATUS_04, CS));
        } else {
            // MOVE '0000' TO IO-STATUS-04
            Cobol.move("0000", f121_IO_STATUS_04, CS);
            // MOVE IO-STATUS TO IO-STATUS-04(3:2)
            Cobol.move(f114_IO_STATUS, f121_IO_STATUS_04.ref(3, Integer.valueOf(2)), CS);
            // DISPLAY 'FILE STATUS IS: NNNN' IO-STATUS-04
            Sysout.display("FILE STATUS IS: NNNN", Cobol.displayText(f121_IO_STATUS_04, CS));
        }
        // EXIT
        return 18;
    }

}
