// gitgalaxy-det-port: COBOL COPAUA0C (COPAUA0C.cbl), translated by rule, statement for statement
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
import com.gitgalaxy.modernized.cobolrt.Hfp;
import com.gitgalaxy.modernized.cobolrt.Hole;
import com.gitgalaxy.modernized.cobolrt.Storage;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.cobolrt.cics.DetCics;
import com.gitgalaxy.modernized.dto.screen.*;
import com.gitgalaxy.modernized.dto.contract.*;
import com.gitgalaxy.modernized.entity.vsam.*;
import com.gitgalaxy.modernized.repository.vsam.*;
import com.gitgalaxy.modernized.repository.vsam.AccountRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.CardXrefRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.CustomerRecordRepository;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * COPAUA0C: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 344, translated 344, holes 0.
 */
@Service
public class Copaua0cService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D0 = new BigDecimal("0");
    private static final BigDecimal D1 = new BigDecimal("1");
    private static final BigDecimal D50 = new BigDecimal("50");
    private static final BigDecimal D99999 = new BigDecimal("99999");
    private static final BigDecimal D999999999 = new BigDecimal("999999999");
    private final Cobol.Dc DC_1000 = new Cobol.Dc("1000");

    private static final byte[] IMAGE_s_WS_VARIABLES = Base64.getDecoder().decode(String.join("",
            "Q09QQVVBMENDUDAwQUNDVERBVCBDVVNUREFUIENBUkREQVQgQ0FSREFJWCBDQ1hSRUYgIAH0AAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAwMDBBAAAAAAAAAAAAAAAAAAAADCAgICAgICAgICAgIDAwMDAwMAAAAAAwMDAwMAAAAAAMAAAAAAAAAAAAAAAAAAAAADAwMDAwMDAwMAAAAAAADCAgICAgICAgICAgICAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgMDAwMDAwMDAwMDAwMDAwMDAwMDA="));
    private static final byte[] IMAGE_s_WS_IMS_VARIABLES = Base64.getDecoder().decode(String.join("",
            "UFNCUEFVVEIAASAgIA=="));
    private static final byte[] IMAGE_s_W01_HCONN_REQUEST = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_W01_HOBJ_REQUEST = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_W01_BUFFLEN = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_W01_DATALEN = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_W01_GET_BUFFER = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_W02_HCONN_REPLY = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_W02_BUFFLEN = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_W02_PUT_BUFFER = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_SWITCHES = Base64.getDecoder().decode(String.join("",
            "IE5NQ0MgICAgICA="));
    private static final byte[] IMAGE_s_MQM_OD_REQUEST = Base64.getDecoder().decode(String.join("",
            "T0QgIAAAAAEAAAABICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgQ1NRLiogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_MQM_MD_REQUEST = Base64.getDecoder().decode(String.join("",
            "TUQgIAAAAAEAAAAAAAAACP////8AAAAAAAADEQAAAAAgICAgICAgIP////8AAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAAAAAAICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_MQM_OD_REPLY = Base64.getDecoder().decode(String.join("",
            "T0QgIAAAAAEAAAABICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgQ1NRLiogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_MQM_MD_REPLY = Base64.getDecoder().decode(String.join("",
            "TUQgIAAAAAEAAAAAAAAACP////8AAAAAAAADEQAAAAAgICAgICAgIP////8AAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAAAAAAICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_MQM_CONSTANTS = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAEAAAACAAAAAAAAB9UAAAfjAAAH8QAAB/UAAAf3AAAH/gAACB8AAAggAAAIJQAAAAEAAAACAAAABAAAABAAAACAAAABAAAAAgAAACAAAAAAAAAAAAEAAAACAAAABAAAAEAAACAAAABAAAAAAAIAAAAEAAAAIAAAIAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAgICAgICAgTVFTVFIgICAAAAAAAAAAAQAAAAIAAAAIAAAAAQAAAAAAAAABAAAAAg=="));
    private static final byte[] IMAGE_s_MQM_TRIGGER_DATA = Base64.getDecoder().decode(String.join("",
            "VE0gIAAAAAEgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgAAAAACAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_MQM_PUT_MESSAGE_OPTIONS = Base64.getDecoder().decode(String.join("",
            "UE1PIAAAAAEAAAAA/////wAAAAAAAAAAAAAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_MQM_GET_MESSAGE_OPTIONS = Base64.getDecoder().decode(String.join("",
            "R01PIAAAAAEAAAAAAAAAAAAAAAAAAAAAICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_PENDING_AUTH_REQUEST = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgMDAwMDAwICAgICAgICAgICAgICAgICAgICAgMDAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_PENDING_AUTH_RESPONSE = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_ERROR_LOG_RECORD = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_PENDING_AUTH_SUMMARY = Base64.getDecoder().decode(String.join("",
            "AAAAAAAMMDAwMDAwMDAwICAgICAgICAgICAAAAAAAAwAAAAAAAwAAAAAAAwAAAAAAAwAAAAAAAAAAAAMAAAAAAAMICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_PENDING_AUTH_DETAILS = Base64.getDecoder().decode(String.join("",
            "AAAMAAAAAAwgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAwMDAwMDAAAAAAAAAMAAAAAAAADCAgICAgICAwMCAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_CARD_XREF_RECORD = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgIDAwMDAwMDAwMDAwMDAwMDAwMDAwICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_ACCOUNT_RECORD = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwMDAgMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_CUSTOMER_RECORD = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgMDAwMDAwMDAwICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAwMDAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_DFHCOMMAREA = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private static final byte[] IMAGE_s_DIB = Base64.getDecoder().decode(String.join("",
            "ICAgIA=="));
    private final Storage s_WS_VARIABLES = new Storage(IMAGE_s_WS_VARIABLES.length);
    private final Storage s_WS_IMS_VARIABLES = new Storage(IMAGE_s_WS_IMS_VARIABLES.length);
    private final Storage s_W01_HCONN_REQUEST = new Storage(IMAGE_s_W01_HCONN_REQUEST.length);
    private final Storage s_W01_HOBJ_REQUEST = new Storage(IMAGE_s_W01_HOBJ_REQUEST.length);
    private final Storage s_W01_BUFFLEN = new Storage(IMAGE_s_W01_BUFFLEN.length);
    private final Storage s_W01_DATALEN = new Storage(IMAGE_s_W01_DATALEN.length);
    private final Storage s_W01_GET_BUFFER = new Storage(IMAGE_s_W01_GET_BUFFER.length);
    private final Storage s_W02_HCONN_REPLY = new Storage(IMAGE_s_W02_HCONN_REPLY.length);
    private final Storage s_W02_BUFFLEN = new Storage(IMAGE_s_W02_BUFFLEN.length);
    private final Storage s_W02_PUT_BUFFER = new Storage(IMAGE_s_W02_PUT_BUFFER.length);
    private final Storage s_WS_SWITCHES = new Storage(IMAGE_s_WS_SWITCHES.length);
    private final Storage s_MQM_OD_REQUEST = new Storage(IMAGE_s_MQM_OD_REQUEST.length);
    private final Storage s_MQM_MD_REQUEST = new Storage(IMAGE_s_MQM_MD_REQUEST.length);
    private final Storage s_MQM_OD_REPLY = new Storage(IMAGE_s_MQM_OD_REPLY.length);
    private final Storage s_MQM_MD_REPLY = new Storage(IMAGE_s_MQM_MD_REPLY.length);
    private final Storage s_MQM_CONSTANTS = new Storage(IMAGE_s_MQM_CONSTANTS.length);
    private final Storage s_MQM_TRIGGER_DATA = new Storage(IMAGE_s_MQM_TRIGGER_DATA.length);
    private final Storage s_MQM_PUT_MESSAGE_OPTIONS = new Storage(IMAGE_s_MQM_PUT_MESSAGE_OPTIONS.length);
    private final Storage s_MQM_GET_MESSAGE_OPTIONS = new Storage(IMAGE_s_MQM_GET_MESSAGE_OPTIONS.length);
    private final Storage s_PENDING_AUTH_REQUEST = new Storage(IMAGE_s_PENDING_AUTH_REQUEST.length);
    private final Storage s_PENDING_AUTH_RESPONSE = new Storage(IMAGE_s_PENDING_AUTH_RESPONSE.length);
    private final Storage s_ERROR_LOG_RECORD = new Storage(IMAGE_s_ERROR_LOG_RECORD.length);
    private final Storage s_PENDING_AUTH_SUMMARY = new Storage(IMAGE_s_PENDING_AUTH_SUMMARY.length);
    private final Storage s_PENDING_AUTH_DETAILS = new Storage(IMAGE_s_PENDING_AUTH_DETAILS.length);
    private final Storage s_CARD_XREF_RECORD = new Storage(IMAGE_s_CARD_XREF_RECORD.length);
    private final Storage s_ACCOUNT_RECORD = new Storage(IMAGE_s_ACCOUNT_RECORD.length);
    private final Storage s_CUSTOMER_RECORD = new Storage(IMAGE_s_CUSTOMER_RECORD.length);
    private final Storage s_DFHCOMMAREA = new Storage(IMAGE_s_DFHCOMMAREA.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);
    private final Storage s_DIB = new Storage(IMAGE_s_DIB.length);

    private final Field f14_WS_RESP_LENGTH = Field.zoned(s_WS_VARIABLES, 176, 4, 0, true, false, false);
    private final Field f17_WS_ABS_TIME = Field.packed(s_WS_VARIABLES, 188, 15, 0, true);
    private final Field f18_WS_CUR_DATE_X6 = Field.alphanumeric(s_WS_VARIABLES, 196, 6, false);
    private final Field f19_WS_CUR_TIME_X6 = Field.alphanumeric(s_WS_VARIABLES, 202, 6, false);
    private final Field f20_WS_CUR_TIME_N6 = Field.zoned(s_WS_VARIABLES, 208, 6, 0, false, false, false);
    private final Field f22_WS_YYDDD = Field.zoned(s_WS_VARIABLES, 218, 5, 0, false, false, false);
    private final Field f24_WS_OPTIONS = Field.binary(s_WS_VARIABLES, 228, 9, 0, true, false);
    private final Field f25_WS_COMPCODE = Field.binary(s_WS_VARIABLES, 232, 9, 0, true, false);
    private final Field f26_WS_REASON = Field.binary(s_WS_VARIABLES, 236, 9, 0, true, false);
    private final Field f28_WS_CODE_DISPLAY = Field.zoned(s_WS_VARIABLES, 244, 9, 0, false, false, false);
    private final Field f30_WS_TRANSACTION_AMT_AN = Field.alphanumeric(s_WS_VARIABLES, 259, 13, false);
    private final Field f31_WS_TRANSACTION_AMT = Field.zoned(s_WS_VARIABLES, 272, 12, 2, true, false, false);
    private final Field f32_WS_APPROVED_AMT = Field.zoned(s_WS_VARIABLES, 284, 12, 2, true, false, false);
    private final Field f33_WS_APPROVED_AMT_DIS = Field.numericEdited(s_WS_VARIABLES, 296, 14, "-ZZZZZZZZZ9.99", false);
    private final Field f37_WS_CARD_RID_CUST_ID = Field.zoned(s_WS_VARIABLES, 390, 9, 0, false, false, false);
    private final Field f38_WS_CARD_RID_CUST_ID_X = Field.alphanumeric(s_WS_VARIABLES, 390, 9, false);
    private final Field f39_WS_CARD_RID_ACCT_ID = Field.zoned(s_WS_VARIABLES, 399, 11, 0, false, false, false);
    private final Field f40_WS_CARD_RID_ACCT_ID_X = Field.alphanumeric(s_WS_VARIABLES, 399, 11, false);
    private final Field f42_PSB_NAME = Field.alphanumeric(s_WS_IMS_VARIABLES, 0, 8, false);
    private final Field f47_W01_HCONN_REQUEST = Field.binary(s_W01_HCONN_REQUEST, 0, 9, 0, true, false);
    private final Field f48_W01_HOBJ_REQUEST = Field.binary(s_W01_HOBJ_REQUEST, 0, 9, 0, true, false);
    private final Field f49_W01_BUFFLEN = Field.binary(s_W01_BUFFLEN, 0, 9, 0, true, false);
    private final Field f50_W01_DATALEN = Field.binary(s_W01_DATALEN, 0, 9, 0, true, false);
    private final Field f51_W01_GET_BUFFER = Field.alphanumeric(s_W01_GET_BUFFER, 0, 500, false);
    private final Field f52_W02_HCONN_REPLY = Field.binary(s_W02_HCONN_REPLY, 0, 9, 0, true, false);
    private final Field f53_W02_BUFFLEN = Field.binary(s_W02_BUFFLEN, 0, 9, 0, true, false);
    private final Field f55_W02_PUT_BUFFER = Field.alphanumeric(s_W02_PUT_BUFFER, 0, 200, false);
    private final Field f68_MQM_OD_REQUEST = Field.group(s_MQM_OD_REQUEST, 0, 168);
    private final Field f72_MQOD_OBJECTTYPE = Field.binary(s_MQM_OD_REQUEST, 8, 9, 0, true, false);
    private final Field f73_MQOD_OBJECTNAME = Field.alphanumeric(s_MQM_OD_REQUEST, 12, 48, false);
    private final Field f77_MQM_MD_REQUEST = Field.group(s_MQM_MD_REQUEST, 0, 324);
    private final Field f87_MQMD_FORMAT = Field.alphanumeric(s_MQM_MD_REQUEST, 32, 8, false);
    private final Field f90_MQMD_MSGID = Field.alphanumeric(s_MQM_MD_REQUEST, 48, 24, false);
    private final Field f91_MQMD_CORRELID = Field.alphanumeric(s_MQM_MD_REQUEST, 72, 24, false);
    private final Field f93_MQMD_REPLYTOQ = Field.alphanumeric(s_MQM_MD_REQUEST, 100, 48, false);
    private final Field f103_MQM_OD_REPLY = Field.group(s_MQM_OD_REPLY, 0, 168);
    private final Field f107_MQOD_OBJECTTYPE = Field.binary(s_MQM_OD_REPLY, 8, 9, 0, true, false);
    private final Field f108_MQOD_OBJECTNAME = Field.alphanumeric(s_MQM_OD_REPLY, 12, 48, false);
    private final Field f112_MQM_MD_REPLY = Field.group(s_MQM_MD_REPLY, 0, 324);
    private final Field f117_MQMD_MSGTYPE = Field.binary(s_MQM_MD_REPLY, 12, 9, 0, true, false);
    private final Field f118_MQMD_EXPIRY = Field.binary(s_MQM_MD_REPLY, 16, 9, 0, true, false);
    private final Field f122_MQMD_FORMAT = Field.alphanumeric(s_MQM_MD_REPLY, 32, 8, false);
    private final Field f124_MQMD_PERSISTENCE = Field.binary(s_MQM_MD_REPLY, 44, 9, 0, true, false);
    private final Field f125_MQMD_MSGID = Field.alphanumeric(s_MQM_MD_REPLY, 48, 24, false);
    private final Field f126_MQMD_CORRELID = Field.alphanumeric(s_MQM_MD_REPLY, 72, 24, false);
    private final Field f128_MQMD_REPLYTOQ = Field.alphanumeric(s_MQM_MD_REPLY, 100, 48, false);
    private final Field f129_MQMD_REPLYTOQMGR = Field.alphanumeric(s_MQM_MD_REPLY, 148, 48, false);
    private final Field f172_MQCO_NONE = Field.binary(s_MQM_CONSTANTS, 132, 9, 0, true, false);
    private final Field f186_MQTM = Field.group(s_MQM_TRIGGER_DATA, 0, 684);
    private final Field f189_MQTM_QNAME = Field.alphanumeric(s_MQM_TRIGGER_DATA, 8, 48, false);
    private final Field f191_MQTM_TRIGGERDATA = Field.alphanumeric(s_MQM_TRIGGER_DATA, 104, 64, false);
    private final Field f196_MQM_PUT_MESSAGE_OPTIONS = Field.group(s_MQM_PUT_MESSAGE_OPTIONS, 0, 128);
    private final Field f200_MQPMO_OPTIONS = Field.binary(s_MQM_PUT_MESSAGE_OPTIONS, 8, 9, 0, true, false);
    private final Field f208_MQM_GET_MESSAGE_OPTIONS = Field.group(s_MQM_GET_MESSAGE_OPTIONS, 0, 72);
    private final Field f212_MQGMO_OPTIONS = Field.binary(s_MQM_GET_MESSAGE_OPTIONS, 8, 9, 0, true, false);
    private final Field f213_MQGMO_WAITINTERVAL = Field.binary(s_MQM_GET_MESSAGE_OPTIONS, 12, 9, 0, true, false);
    private final Field f218_PA_RQ_AUTH_DATE = Field.alphanumeric(s_PENDING_AUTH_REQUEST, 0, 6, false);
    private final Field f219_PA_RQ_AUTH_TIME = Field.alphanumeric(s_PENDING_AUTH_REQUEST, 6, 6, false);
    private final Field f220_PA_RQ_CARD_NUM = Field.alphanumeric(s_PENDING_AUTH_REQUEST, 12, 16, false);
    private final Field f221_PA_RQ_AUTH_TYPE = Field.alphanumeric(s_PENDING_AUTH_REQUEST, 28, 4, false);
    private final Field f222_PA_RQ_CARD_EXPIRY_DATE = Field.alphanumeric(s_PENDING_AUTH_REQUEST, 32, 4, false);
    private final Field f223_PA_RQ_MESSAGE_TYPE = Field.alphanumeric(s_PENDING_AUTH_REQUEST, 36, 6, false);
    private final Field f224_PA_RQ_MESSAGE_SOURCE = Field.alphanumeric(s_PENDING_AUTH_REQUEST, 42, 6, false);
    private final Field f225_PA_RQ_PROCESSING_CODE = Field.zoned(s_PENDING_AUTH_REQUEST, 48, 6, 0, false, false, false);
    private final Field f226_PA_RQ_TRANSACTION_AMT = Field.numericEdited(s_PENDING_AUTH_REQUEST, 54, 14, "+9999999999.99", false);
    private final Field f227_PA_RQ_MERCHANT_CATAGORY_CODE = Field.alphanumeric(s_PENDING_AUTH_REQUEST, 68, 4, false);
    private final Field f228_PA_RQ_ACQR_COUNTRY_CODE = Field.alphanumeric(s_PENDING_AUTH_REQUEST, 72, 3, false);
    private final Field f229_PA_RQ_POS_ENTRY_MODE = Field.zoned(s_PENDING_AUTH_REQUEST, 75, 2, 0, false, false, false);
    private final Field f230_PA_RQ_MERCHANT_ID = Field.alphanumeric(s_PENDING_AUTH_REQUEST, 77, 15, false);
    private final Field f231_PA_RQ_MERCHANT_NAME = Field.alphanumeric(s_PENDING_AUTH_REQUEST, 92, 22, false);
    private final Field f232_PA_RQ_MERCHANT_CITY = Field.alphanumeric(s_PENDING_AUTH_REQUEST, 114, 13, false);
    private final Field f233_PA_RQ_MERCHANT_STATE = Field.alphanumeric(s_PENDING_AUTH_REQUEST, 127, 2, false);
    private final Field f234_PA_RQ_MERCHANT_ZIP = Field.alphanumeric(s_PENDING_AUTH_REQUEST, 129, 9, false);
    private final Field f235_PA_RQ_TRANSACTION_ID = Field.alphanumeric(s_PENDING_AUTH_REQUEST, 138, 15, false);
    private final Field f237_PA_RL_CARD_NUM = Field.alphanumeric(s_PENDING_AUTH_RESPONSE, 0, 16, false);
    private final Field f238_PA_RL_TRANSACTION_ID = Field.alphanumeric(s_PENDING_AUTH_RESPONSE, 16, 15, false);
    private final Field f239_PA_RL_AUTH_ID_CODE = Field.alphanumeric(s_PENDING_AUTH_RESPONSE, 31, 6, false);
    private final Field f240_PA_RL_AUTH_RESP_CODE = Field.alphanumeric(s_PENDING_AUTH_RESPONSE, 37, 2, false);
    private final Field f241_PA_RL_AUTH_RESP_REASON = Field.alphanumeric(s_PENDING_AUTH_RESPONSE, 39, 4, false);
    private final Field f242_PA_RL_APPROVED_AMT = Field.numericEdited(s_PENDING_AUTH_RESPONSE, 43, 14, "+9999999999.99", false);
    private final Field f243_ERROR_LOG_RECORD = Field.group(s_ERROR_LOG_RECORD, 0, 122);
    private final Field f244_ERR_DATE = Field.alphanumeric(s_ERROR_LOG_RECORD, 0, 6, false);
    private final Field f245_ERR_TIME = Field.alphanumeric(s_ERROR_LOG_RECORD, 6, 6, false);
    private final Field f246_ERR_APPLICATION = Field.alphanumeric(s_ERROR_LOG_RECORD, 12, 8, false);
    private final Field f247_ERR_PROGRAM = Field.alphanumeric(s_ERROR_LOG_RECORD, 20, 8, false);
    private final Field f248_ERR_LOCATION = Field.alphanumeric(s_ERROR_LOG_RECORD, 28, 4, false);
    private final Field f249_ERR_LEVEL = Field.alphanumeric(s_ERROR_LOG_RECORD, 32, 1, false);
    private final Field f250_ERR_SUBSYSTEM = Field.alphanumeric(s_ERROR_LOG_RECORD, 33, 1, false);
    private final Field f251_ERR_CODE_1 = Field.alphanumeric(s_ERROR_LOG_RECORD, 34, 9, false);
    private final Field f252_ERR_CODE_2 = Field.alphanumeric(s_ERROR_LOG_RECORD, 43, 9, false);
    private final Field f253_ERR_MESSAGE = Field.alphanumeric(s_ERROR_LOG_RECORD, 52, 50, false);
    private final Field f254_ERR_EVENT_KEY = Field.alphanumeric(s_ERROR_LOG_RECORD, 102, 20, false);
    private final Field f255_PENDING_AUTH_SUMMARY = Field.group(s_PENDING_AUTH_SUMMARY, 0, 100);
    private final Field f256_PA_ACCT_ID = Field.packed(s_PENDING_AUTH_SUMMARY, 0, 11, 0, true);
    private final Field f257_PA_CUST_ID = Field.zoned(s_PENDING_AUTH_SUMMARY, 6, 9, 0, false, false, false);
    private final Field f260_PA_CREDIT_LIMIT = Field.packed(s_PENDING_AUTH_SUMMARY, 26, 11, 2, true);
    private final Field f261_PA_CASH_LIMIT = Field.packed(s_PENDING_AUTH_SUMMARY, 32, 11, 2, true);
    private final Field f262_PA_CREDIT_BALANCE = Field.packed(s_PENDING_AUTH_SUMMARY, 38, 11, 2, true);
    private final Field f263_PA_CASH_BALANCE = Field.packed(s_PENDING_AUTH_SUMMARY, 44, 11, 2, true);
    private final Field f264_PA_APPROVED_AUTH_CNT = Field.binary(s_PENDING_AUTH_SUMMARY, 50, 4, 0, true, false);
    private final Field f265_PA_DECLINED_AUTH_CNT = Field.binary(s_PENDING_AUTH_SUMMARY, 52, 4, 0, true, false);
    private final Field f266_PA_APPROVED_AUTH_AMT = Field.packed(s_PENDING_AUTH_SUMMARY, 54, 11, 2, true);
    private final Field f267_PA_DECLINED_AUTH_AMT = Field.packed(s_PENDING_AUTH_SUMMARY, 60, 11, 2, true);
    private final Field f269_PENDING_AUTH_DETAILS = Field.group(s_PENDING_AUTH_DETAILS, 0, 200);
    private final Field f271_PA_AUTH_DATE_9C = Field.packed(s_PENDING_AUTH_DETAILS, 0, 5, 0, true);
    private final Field f272_PA_AUTH_TIME_9C = Field.packed(s_PENDING_AUTH_DETAILS, 3, 9, 0, true);
    private final Field f273_PA_AUTH_ORIG_DATE = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 8, 6, false);
    private final Field f274_PA_AUTH_ORIG_TIME = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 14, 6, false);
    private final Field f275_PA_CARD_NUM = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 20, 16, false);
    private final Field f276_PA_AUTH_TYPE = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 36, 4, false);
    private final Field f277_PA_CARD_EXPIRY_DATE = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 40, 4, false);
    private final Field f278_PA_MESSAGE_TYPE = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 44, 6, false);
    private final Field f279_PA_MESSAGE_SOURCE = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 50, 6, false);
    private final Field f280_PA_AUTH_ID_CODE = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 56, 6, false);
    private final Field f281_PA_AUTH_RESP_CODE = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 62, 2, false);
    private final Field f282_PA_AUTH_RESP_REASON = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 64, 4, false);
    private final Field f283_PA_PROCESSING_CODE = Field.zoned(s_PENDING_AUTH_DETAILS, 68, 6, 0, false, false, false);
    private final Field f284_PA_TRANSACTION_AMT = Field.packed(s_PENDING_AUTH_DETAILS, 74, 12, 2, true);
    private final Field f285_PA_APPROVED_AMT = Field.packed(s_PENDING_AUTH_DETAILS, 81, 12, 2, true);
    private final Field f286_PA_MERCHANT_CATAGORY_CODE = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 88, 4, false);
    private final Field f287_PA_ACQR_COUNTRY_CODE = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 92, 3, false);
    private final Field f288_PA_POS_ENTRY_MODE = Field.zoned(s_PENDING_AUTH_DETAILS, 95, 2, 0, false, false, false);
    private final Field f289_PA_MERCHANT_ID = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 97, 15, false);
    private final Field f290_PA_MERCHANT_NAME = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 112, 22, false);
    private final Field f291_PA_MERCHANT_CITY = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 134, 13, false);
    private final Field f292_PA_MERCHANT_STATE = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 147, 2, false);
    private final Field f293_PA_MERCHANT_ZIP = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 149, 9, false);
    private final Field f294_PA_TRANSACTION_ID = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 158, 15, false);
    private final Field f295_PA_MATCH_STATUS = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 173, 1, false);
    private final Field f296_PA_AUTH_FRAUD = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 174, 1, false);
    private final Field f297_PA_FRAUD_RPT_DATE = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 175, 8, false);
    private final Field f299_CARD_XREF_RECORD = Field.group(s_CARD_XREF_RECORD, 0, 50);
    private final Field f300_XREF_CARD_NUM = Field.alphanumeric(s_CARD_XREF_RECORD, 0, 16, false);
    private final Field f301_XREF_CUST_ID = Field.zoned(s_CARD_XREF_RECORD, 16, 9, 0, false, false, false);
    private final Field f302_XREF_ACCT_ID = Field.zoned(s_CARD_XREF_RECORD, 25, 11, 0, false, false, false);
    private final Field f304_ACCOUNT_RECORD = Field.group(s_ACCOUNT_RECORD, 0, 300);
    private final Field f307_ACCT_CURR_BAL = Field.zoned(s_ACCOUNT_RECORD, 12, 12, 2, true, false, false);
    private final Field f308_ACCT_CREDIT_LIMIT = Field.zoned(s_ACCOUNT_RECORD, 24, 12, 2, true, false, false);
    private final Field f309_ACCT_CASH_CREDIT_LIMIT = Field.zoned(s_ACCOUNT_RECORD, 36, 12, 2, true, false, false);
    private final Field f318_CUSTOMER_RECORD = Field.group(s_CUSTOMER_RECORD, 0, 500);
    private final Field f341_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f342_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f343_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f344_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f345_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f348_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f369_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f370_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f372_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);
    private final Field f375_DIBSTAT = Field.alphanumeric(s_DIB, 2, 2, false);
    private String f2_WS_PGM_AUTH;  // WS-PGM-AUTH PIC X(08)
    private String f3_WS_CICS_TRANID;  // WS-CICS-TRANID PIC X(04)
    private String f4_WS_ACCTFILENAME;  // WS-ACCTFILENAME PIC X(8)
    private String f5_WS_CUSTFILENAME;  // WS-CUSTFILENAME PIC X(8)
    private String f6_WS_CARDFILENAME;  // WS-CARDFILENAME PIC X(8)
    private String f7_WS_CARDFILENAME_ACCT_PATH;  // WS-CARDFILENAME-ACCT-PATH PIC X(8)
    private String f8_WS_CCXREF_FILE;  // WS-CCXREF-FILE PIC X(08)
    private long f9_WS_REQSTS_PROCESS_LIMIT;  // WS-REQSTS-PROCESS-LIMIT PIC S9(4) BINARY
    private long f10_WS_MSG_PROCESSED;  // WS-MSG-PROCESSED PIC S9(4) BINARY
    private String f11_WS_REQUEST_QNAME;  // WS-REQUEST-QNAME PIC X(48)
    private String f12_WS_REPLY_QNAME;  // WS-REPLY-QNAME PIC X(48)
    private String f13_WS_SAVE_CORRELID;  // WS-SAVE-CORRELID PIC X(24)
    private long f15_WS_RESP_CD;  // WS-RESP-CD PIC S9(09) BINARY
    private long f16_WS_REAS_CD;  // WS-REAS-CD PIC S9(09) BINARY
    private long f21_WS_CUR_TIME_MS;  // WS-CUR-TIME-MS PIC S9(08) BINARY
    private BigDecimal f23_WS_TIME_WITH_MS;  // WS-TIME-WITH-MS PIC S9(09) PACKED
    private long f27_WS_WAIT_INTERVAL;  // WS-WAIT-INTERVAL PIC S9(9) BINARY
    private BigDecimal f29_WS_AVAILABLE_AMT;  // WS-AVAILABLE-AMT PIC S9(09)V99 PACKED
    private String f34_WS_TRIGGER_DATA;  // WS-TRIGGER-DATA PIC X(64)
    private String f36_WS_CARD_RID_CARDNUM;  // WS-CARD-RID-CARDNUM PIC X(16)
    private long f44_PAUT_PCB_NUM;  // PAUT-PCB-NUM PIC S9(4) BINARY
    private String f45_IMS_RETURN_CODE;  // IMS-RETURN-CODE PIC X(02)
    private String f46_WS_IMS_PSB_SCHD_FLG;  // WS-IMS-PSB-SCHD-FLG PIC X(1)
    private long f54_W02_DATALEN;  // W02-DATALEN PIC S9(9) BINARY
    private String f57_WS_AUTH_RESP_FLG;  // WS-AUTH-RESP-FLG PIC X(01)
    private String f58_WS_MSG_LOOP_FLG;  // WS-MSG-LOOP-FLG PIC X(01)
    private String f59_WS_MSG_AVAILABLE_FLG;  // WS-MSG-AVAILABLE-FLG PIC X(01)
    private String f60_WS_REQUEST_MQ_FLG;  // WS-REQUEST-MQ-FLG PIC X(01)
    private String f61_WS_REPLY_MQ_FLG;  // WS-REPLY-MQ-FLG PIC X(01)
    private String f62_WS_XREF_READ_FLG;  // WS-XREF-READ-FLG PIC X(1)
    private String f63_WS_ACCT_MASTER_READ_FLG;  // WS-ACCT-MASTER-READ-FLG PIC X(1)
    private String f64_WS_CUST_MASTER_READ_FLG;  // WS-CUST-MASTER-READ-FLG PIC X(1)
    private String f65_WS_PAUT_SMRY_SEG_FLG;  // WS-PAUT-SMRY-SEG-FLG PIC X(1)
    private String f66_WS_DECLINE_FLG;  // WS-DECLINE-FLG PIC X(1)
    private String f67_WS_DECLINE_REASON_FLG;  // WS-DECLINE-REASON-FLG PIC X(1)
    private long f139_MQCC_OK;  // MQCC-OK PIC S9(9) BINARY
    private long f140_MQCC_WARNING;  // MQCC-WARNING PIC S9(9) BINARY
    private long f141_MQCC_FAILED;  // MQCC-FAILED PIC S9(9) BINARY
    private long f142_MQRC_NONE;  // MQRC-NONE PIC S9(9) BINARY
    private long f143_MQRC_BUFFER_LENGTH_ERROR;  // MQRC-BUFFER-LENGTH-ERROR PIC S9(9) BINARY
    private long f144_MQRC_HOBJ_ERROR;  // MQRC-HOBJ-ERROR PIC S9(9) BINARY
    private long f145_MQRC_NO_MSG_AVAILABLE;  // MQRC-NO-MSG-AVAILABLE PIC S9(9) BINARY
    private long f146_MQRC_NOT_OPEN_FOR_INPUT;  // MQRC-NOT-OPEN-FOR-INPUT PIC S9(9) BINARY
    private long f147_MQRC_NOT_OPEN_FOR_OUTPUT;  // MQRC-NOT-OPEN-FOR-OUTPUT PIC S9(9) BINARY
    private long f148_MQRC_OPTIONS_ERROR;  // MQRC-OPTIONS-ERROR PIC S9(9) BINARY
    private long f149_MQRC_TRUNCATED_MSG_ACCEPTED;  // MQRC-TRUNCATED-MSG-ACCEPTED PIC S9(9) BINARY
    private long f150_MQRC_TRUNCATED_MSG_FAILED;  // MQRC-TRUNCATED-MSG-FAILED PIC S9(9) BINARY
    private long f151_MQRC_UNKNOWN_OBJECT_NAME;  // MQRC-UNKNOWN-OBJECT-NAME PIC S9(9) BINARY
    private long f152_MQOO_INPUT_AS_Q_DEF;  // MQOO-INPUT-AS-Q-DEF PIC S9(9) BINARY
    private long f153_MQOO_INPUT_SHARED;  // MQOO-INPUT-SHARED PIC S9(9) BINARY
    private long f154_MQOO_INPUT_EXCLUSIVE;  // MQOO-INPUT-EXCLUSIVE PIC S9(9) BINARY
    private long f155_MQOO_OUTPUT;  // MQOO-OUTPUT PIC S9(9) BINARY
    private long f156_MQOO_SAVE_ALL_CONTEXT;  // MQOO-SAVE-ALL-CONTEXT PIC S9(9) BINARY
    private long f157_MQOO_PASS_IDENTITY_CONTEXT;  // MQOO-PASS-IDENTITY-CONTEXT PIC S9(9) BINARY
    private long f158_MQOO_PASS_ALL_CONTEXT;  // MQOO-PASS-ALL-CONTEXT PIC S9(9) BINARY
    private long f159_MQOO_FAIL_IF_QUIESCING;  // MQOO-FAIL-IF-QUIESCING PIC S9(9) BINARY
    private long f160_MQGMO_NO_WAIT;  // MQGMO-NO-WAIT PIC S9(9) BINARY
    private long f161_MQGMO_WAIT;  // MQGMO-WAIT PIC S9(9) BINARY
    private long f162_MQGMO_SYNCPOINT;  // MQGMO-SYNCPOINT PIC S9(9) BINARY
    private long f163_MQGMO_NO_SYNCPOINT;  // MQGMO-NO-SYNCPOINT PIC S9(9) BINARY
    private long f164_MQGMO_ACCEPT_TRUNCATED_MSG;  // MQGMO-ACCEPT-TRUNCATED-MSG PIC S9(9) BINARY
    private long f165_MQGMO_FAIL_IF_QUIESCING;  // MQGMO-FAIL-IF-QUIESCING PIC S9(9) BINARY
    private long f166_MQGMO_CONVERT;  // MQGMO-CONVERT PIC S9(9) BINARY
    private long f167_MQPMO_SYNCPOINT;  // MQPMO-SYNCPOINT PIC S9(9) BINARY
    private long f168_MQPMO_NO_SYNCPOINT;  // MQPMO-NO-SYNCPOINT PIC S9(9) BINARY
    private long f169_MQPMO_DEFAULT_CONTEXT;  // MQPMO-DEFAULT-CONTEXT PIC S9(9) BINARY
    private long f170_MQPMO_FAIL_IF_QUIESCING;  // MQPMO-FAIL-IF-QUIESCING PIC S9(9) BINARY
    private long f171_MQPMO_NO_CONTEXT;  // MQPMO-NO-CONTEXT PIC S9(9) BINARY
    private String f173_MQMI_NONE;  // MQMI-NONE PIC X(24)
    private String f174_MQCI_NONE;  // MQCI-NONE PIC X(24)
    private String f175_MQFMT_NONE;  // MQFMT-NONE PIC X(8)
    private String f176_MQFMT_STRING;  // MQFMT-STRING PIC X(8)
    private long f177_MQCCSI_Q_MGR;  // MQCCSI-Q-MGR PIC S9(9) BINARY
    private long f178_MQMT_REQUEST;  // MQMT-REQUEST PIC S9(9) BINARY
    private long f179_MQMT_REPLY;  // MQMT-REPLY PIC S9(9) BINARY
    private long f180_MQMT_DATAGRAM;  // MQMT-DATAGRAM PIC S9(9) BINARY
    private long f181_MQOT_Q;  // MQOT-Q PIC S9(9) BINARY
    private long f182_MQPER_NOT_PERSISTENT;  // MQPER-NOT-PERSISTENT PIC S9(9) BINARY
    private long f183_MQPER_PERSISTENT;  // MQPER-PERSISTENT PIC S9(9) BINARY
    private long f184_MQPER_PERSISTENCE_AS_Q_DEF;  // MQPER-PERSISTENCE-AS-Q-DEF PIC S9(9) BINARY

    private static Long id_AccountRecord(byte[] rec) {
        Storage s = Storage.of(rec);
        return Cobol.num(Field.zoned(s, 0, 11, 0, false, false, false), CS).longValue();
    }

    private static String id_CardXrefRecord(byte[] rec) {
        Storage s = Storage.of(rec);
        return Cobol.text(Field.alphanumeric(s, 0, 16, false), CS);
    }

    private static Integer id_CustomerRecord(byte[] rec) {
        Storage s = Storage.of(rec);
        return Cobol.num(Field.zoned(s, 0, 9, 0, false, false, false), CS).intValue();
    }

    private CicsTask task;
    private static final Charset REGION = DetCics.region("IBM037");
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
        return (DetCics.Store<E>) stores.computeIfAbsent(name, n -> switch (n) {
            case "ACCTDAT" -> new DetCics.Store<AccountRecord>(accountRecordRepository::findAll, e -> e.toRecord(CS), b -> AccountRecord.fromRecord(b, CS), e -> task.write("ACCTDAT", () -> accountRecordRepository.save(e)), e -> task.write("ACCTDAT", () -> accountRecordRepository.delete(e)), 0, 11, CS).withFindById(rec -> accountRecordRepository.findById(id_AccountRecord(rec)));
            case "CCXREF" -> new DetCics.Store<CardXrefRecord>(cardXrefRecordRepository::findAll, e -> e.toRecord(CS), b -> CardXrefRecord.fromRecord(b, CS), e -> task.write("CCXREF", () -> cardXrefRecordRepository.save(e)), e -> task.write("CCXREF", () -> cardXrefRecordRepository.delete(e)), 0, 16, CS).withFindById(rec -> cardXrefRecordRepository.findById(id_CardXrefRecord(rec)));
            case "CUSTDAT" -> new DetCics.Store<CustomerRecord>(customerRecordRepository::findAll, e -> e.toRecord(CS), b -> CustomerRecord.fromRecord(b, CS), e -> task.write("CUSTDAT", () -> customerRecordRepository.save(e)), e -> task.write("CUSTDAT", () -> customerRecordRepository.delete(e)), 0, 9, CS).withFindById(rec -> customerRecordRepository.findById(id_CustomerRecord(rec)));
            default -> throw new Hole("CICS file " + n + ": no store in the generated project");
        });
    }

    private static final java.util.Map<String, Integer> PARAGRAPHS = java.util.Map.ofEntries(
            java.util.Map.entry("9990-EXIT", 42),
            java.util.Map.entry("9990-END-ROUTINE", 41),
            java.util.Map.entry("9500-EXIT", 40),
            java.util.Map.entry("9500-LOG-ERROR", 39),
            java.util.Map.entry("9100-EXIT", 38),
            java.util.Map.entry("9100-CLOSE-REQUEST-QUEUE", 37),
            java.util.Map.entry("9000-EXIT", 36),
            java.util.Map.entry("9000-TERMINATE", 35),
            java.util.Map.entry("8500-EXIT", 34),
            java.util.Map.entry("8500-INSERT-AUTH", 33),
            java.util.Map.entry("8400-EXIT", 32),
            java.util.Map.entry("8400-UPDATE-SUMMARY", 31),
            java.util.Map.entry("8000-EXIT", 30),
            java.util.Map.entry("8000-WRITE-AUTH-TO-DB", 29),
            java.util.Map.entry("7100-EXIT", 28),
            java.util.Map.entry("7100-SEND-RESPONSE", 27),
            java.util.Map.entry("6000-EXIT", 26),
            java.util.Map.entry("6000-MAKE-DECISION", 25),
            java.util.Map.entry("5600-EXIT", 24),
            java.util.Map.entry("5600-READ-PROFILE-DATA", 23),
            java.util.Map.entry("5500-EXIT", 22),
            java.util.Map.entry("5500-READ-AUTH-SUMMRY", 21),
            java.util.Map.entry("5300-EXIT", 20),
            java.util.Map.entry("5300-READ-CUST-RECORD", 19),
            java.util.Map.entry("5200-EXIT", 18),
            java.util.Map.entry("5200-READ-ACCT-RECORD", 17),
            java.util.Map.entry("5100-EXIT", 16),
            java.util.Map.entry("5100-READ-XREF-RECORD", 15),
            java.util.Map.entry("5000-EXIT", 14),
            java.util.Map.entry("5000-PROCESS-AUTH", 13),
            java.util.Map.entry("3100-EXIT", 12),
            java.util.Map.entry("3100-READ-REQUEST-MQ", 11),
            java.util.Map.entry("2100-EXIT", 10),
            java.util.Map.entry("2100-EXTRACT-REQUEST-MSG", 9),
            java.util.Map.entry("2000-EXIT", 8),
            java.util.Map.entry("2000-MAIN-PROCESS", 7),
            java.util.Map.entry("1200-EXIT", 6),
            java.util.Map.entry("1200-SCHEDULE-PSB", 5),
            java.util.Map.entry("1100-EXIT", 4),
            java.util.Map.entry("1100-OPEN-REQUEST-QUEUE", 3),
            java.util.Map.entry("1000-EXIT", 2),
            java.util.Map.entry("1000-INITIALIZE", 1),
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

    private void in_Copaua0cDfhcommarea(Copaua0cDfhcommarea d, Storage s, int base) {
        if (d == null) {
            return;
        }
        Cobol.move(d.getLkCommarea() == null ? "" : d.getLkCommarea(), Field.alphanumeric(s, base + 0, 4096, false), CS);
    }

    private void fill_Copaua0cDfhcommarea(Copaua0cDfhcommarea d, Storage s, int base) {
        d.setLkCommarea(Cobol.text(Field.alphanumeric(s, base + 0, 4096, false), CS));
    }

    private Copaua0cDfhcommarea out_Copaua0cDfhcommarea(Storage s, int base) {
        Copaua0cDfhcommarea d = new Copaua0cDfhcommarea();
        fill_Copaua0cDfhcommarea(d, s, base);
        return d;
    }

    /** #4270 (X23): DFHCOMMAREA's whole record again, with what the task left in its EIBCALEN bytes. */
    private void caWhole(byte[] whole) {
        if (s_DFHCOMMAREA.bytes != whole) {
            System.arraycopy(s_DFHCOMMAREA.bytes, 0, whole, 0, s_DFHCOMMAREA.bytes.length);
            s_DFHCOMMAREA.bytes = whole;
        }
    }


    private final AccountRecordRepository accountRecordRepository;
    private final CardXrefRecordRepository cardXrefRecordRepository;
    private final CustomerRecordRepository customerRecordRepository;
    private final DatasetResolver datasets;
    private final CobolFiles files;
    private final MainframeClock clock;

    public Copaua0cService(AccountRecordRepository accountRecordRepository, CardXrefRecordRepository cardXrefRecordRepository, CustomerRecordRepository customerRecordRepository, DatasetResolver datasets, CobolFiles files, MainframeClock clock) {
        this.accountRecordRepository = accountRecordRepository;
        this.cardXrefRecordRepository = cardXrefRecordRepository;
        this.customerRecordRepository = customerRecordRepository;
        this.datasets = datasets;
        this.files = files;
        this.clock = clock;
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_VARIABLES, 0, s_WS_VARIABLES.bytes, 0, IMAGE_s_WS_VARIABLES.length);
        System.arraycopy(IMAGE_s_WS_IMS_VARIABLES, 0, s_WS_IMS_VARIABLES.bytes, 0, IMAGE_s_WS_IMS_VARIABLES.length);
        System.arraycopy(IMAGE_s_W01_HCONN_REQUEST, 0, s_W01_HCONN_REQUEST.bytes, 0, IMAGE_s_W01_HCONN_REQUEST.length);
        System.arraycopy(IMAGE_s_W01_HOBJ_REQUEST, 0, s_W01_HOBJ_REQUEST.bytes, 0, IMAGE_s_W01_HOBJ_REQUEST.length);
        System.arraycopy(IMAGE_s_W01_BUFFLEN, 0, s_W01_BUFFLEN.bytes, 0, IMAGE_s_W01_BUFFLEN.length);
        System.arraycopy(IMAGE_s_W01_DATALEN, 0, s_W01_DATALEN.bytes, 0, IMAGE_s_W01_DATALEN.length);
        System.arraycopy(IMAGE_s_W01_GET_BUFFER, 0, s_W01_GET_BUFFER.bytes, 0, IMAGE_s_W01_GET_BUFFER.length);
        System.arraycopy(IMAGE_s_W02_HCONN_REPLY, 0, s_W02_HCONN_REPLY.bytes, 0, IMAGE_s_W02_HCONN_REPLY.length);
        System.arraycopy(IMAGE_s_W02_BUFFLEN, 0, s_W02_BUFFLEN.bytes, 0, IMAGE_s_W02_BUFFLEN.length);
        System.arraycopy(IMAGE_s_W02_PUT_BUFFER, 0, s_W02_PUT_BUFFER.bytes, 0, IMAGE_s_W02_PUT_BUFFER.length);
        System.arraycopy(IMAGE_s_WS_SWITCHES, 0, s_WS_SWITCHES.bytes, 0, IMAGE_s_WS_SWITCHES.length);
        System.arraycopy(IMAGE_s_MQM_OD_REQUEST, 0, s_MQM_OD_REQUEST.bytes, 0, IMAGE_s_MQM_OD_REQUEST.length);
        System.arraycopy(IMAGE_s_MQM_MD_REQUEST, 0, s_MQM_MD_REQUEST.bytes, 0, IMAGE_s_MQM_MD_REQUEST.length);
        System.arraycopy(IMAGE_s_MQM_OD_REPLY, 0, s_MQM_OD_REPLY.bytes, 0, IMAGE_s_MQM_OD_REPLY.length);
        System.arraycopy(IMAGE_s_MQM_MD_REPLY, 0, s_MQM_MD_REPLY.bytes, 0, IMAGE_s_MQM_MD_REPLY.length);
        System.arraycopy(IMAGE_s_MQM_CONSTANTS, 0, s_MQM_CONSTANTS.bytes, 0, IMAGE_s_MQM_CONSTANTS.length);
        System.arraycopy(IMAGE_s_MQM_TRIGGER_DATA, 0, s_MQM_TRIGGER_DATA.bytes, 0, IMAGE_s_MQM_TRIGGER_DATA.length);
        System.arraycopy(IMAGE_s_MQM_PUT_MESSAGE_OPTIONS, 0, s_MQM_PUT_MESSAGE_OPTIONS.bytes, 0, IMAGE_s_MQM_PUT_MESSAGE_OPTIONS.length);
        System.arraycopy(IMAGE_s_MQM_GET_MESSAGE_OPTIONS, 0, s_MQM_GET_MESSAGE_OPTIONS.bytes, 0, IMAGE_s_MQM_GET_MESSAGE_OPTIONS.length);
        System.arraycopy(IMAGE_s_PENDING_AUTH_REQUEST, 0, s_PENDING_AUTH_REQUEST.bytes, 0, IMAGE_s_PENDING_AUTH_REQUEST.length);
        System.arraycopy(IMAGE_s_PENDING_AUTH_RESPONSE, 0, s_PENDING_AUTH_RESPONSE.bytes, 0, IMAGE_s_PENDING_AUTH_RESPONSE.length);
        System.arraycopy(IMAGE_s_ERROR_LOG_RECORD, 0, s_ERROR_LOG_RECORD.bytes, 0, IMAGE_s_ERROR_LOG_RECORD.length);
        System.arraycopy(IMAGE_s_PENDING_AUTH_SUMMARY, 0, s_PENDING_AUTH_SUMMARY.bytes, 0, IMAGE_s_PENDING_AUTH_SUMMARY.length);
        System.arraycopy(IMAGE_s_PENDING_AUTH_DETAILS, 0, s_PENDING_AUTH_DETAILS.bytes, 0, IMAGE_s_PENDING_AUTH_DETAILS.length);
        System.arraycopy(IMAGE_s_CARD_XREF_RECORD, 0, s_CARD_XREF_RECORD.bytes, 0, IMAGE_s_CARD_XREF_RECORD.length);
        System.arraycopy(IMAGE_s_ACCOUNT_RECORD, 0, s_ACCOUNT_RECORD.bytes, 0, IMAGE_s_ACCOUNT_RECORD.length);
        System.arraycopy(IMAGE_s_CUSTOMER_RECORD, 0, s_CUSTOMER_RECORD.bytes, 0, IMAGE_s_CUSTOMER_RECORD.length);
        System.arraycopy(IMAGE_s_DFHCOMMAREA, 0, s_DFHCOMMAREA.bytes, 0, IMAGE_s_DFHCOMMAREA.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
        System.arraycopy(IMAGE_s_DIB, 0, s_DIB.bytes, 0, IMAGE_s_DIB.length);
        f2_WS_PGM_AUTH = "COPAUA0C";
        f3_WS_CICS_TRANID = "CP00";
        f4_WS_ACCTFILENAME = "ACCTDAT ";
        f5_WS_CUSTFILENAME = "CUSTDAT ";
        f6_WS_CARDFILENAME = "CARDDAT ";
        f7_WS_CARDFILENAME_ACCT_PATH = "CARDAIX ";
        f8_WS_CCXREF_FILE = "CCXREF  ";
        f9_WS_REQSTS_PROCESS_LIMIT = 500L;
        f10_WS_MSG_PROCESSED = 0L;
        f11_WS_REQUEST_QNAME = "                                                ";
        f12_WS_REPLY_QNAME = "                                                ";
        f13_WS_SAVE_CORRELID = "                        ";
        f15_WS_RESP_CD = 0L;
        f16_WS_REAS_CD = 0L;
        f21_WS_CUR_TIME_MS = 0L;
        f23_WS_TIME_WITH_MS = new BigDecimal("0");
        f27_WS_WAIT_INTERVAL = 0L;
        f29_WS_AVAILABLE_AMT = new BigDecimal("0");
        f34_WS_TRIGGER_DATA = "                                                                ";
        f36_WS_CARD_RID_CARDNUM = "                ";
        f44_PAUT_PCB_NUM = 1L;
        f45_IMS_RETURN_CODE = "  ";
        f46_WS_IMS_PSB_SCHD_FLG = " ";
        f54_W02_DATALEN = 0L;
        f57_WS_AUTH_RESP_FLG = " ";
        f58_WS_MSG_LOOP_FLG = "N";
        f59_WS_MSG_AVAILABLE_FLG = "M";
        f60_WS_REQUEST_MQ_FLG = "C";
        f61_WS_REPLY_MQ_FLG = "C";
        f62_WS_XREF_READ_FLG = " ";
        f63_WS_ACCT_MASTER_READ_FLG = " ";
        f64_WS_CUST_MASTER_READ_FLG = " ";
        f65_WS_PAUT_SMRY_SEG_FLG = " ";
        f66_WS_DECLINE_FLG = " ";
        f67_WS_DECLINE_REASON_FLG = " ";
        f139_MQCC_OK = 0L;
        f140_MQCC_WARNING = 1L;
        f141_MQCC_FAILED = 2L;
        f142_MQRC_NONE = 0L;
        f143_MQRC_BUFFER_LENGTH_ERROR = 2005L;
        f144_MQRC_HOBJ_ERROR = 2019L;
        f145_MQRC_NO_MSG_AVAILABLE = 2033L;
        f146_MQRC_NOT_OPEN_FOR_INPUT = 2037L;
        f147_MQRC_NOT_OPEN_FOR_OUTPUT = 2039L;
        f148_MQRC_OPTIONS_ERROR = 2046L;
        f149_MQRC_TRUNCATED_MSG_ACCEPTED = 2079L;
        f150_MQRC_TRUNCATED_MSG_FAILED = 2080L;
        f151_MQRC_UNKNOWN_OBJECT_NAME = 2085L;
        f152_MQOO_INPUT_AS_Q_DEF = 1L;
        f153_MQOO_INPUT_SHARED = 2L;
        f154_MQOO_INPUT_EXCLUSIVE = 4L;
        f155_MQOO_OUTPUT = 16L;
        f156_MQOO_SAVE_ALL_CONTEXT = 128L;
        f157_MQOO_PASS_IDENTITY_CONTEXT = 256L;
        f158_MQOO_PASS_ALL_CONTEXT = 512L;
        f159_MQOO_FAIL_IF_QUIESCING = 8192L;
        f160_MQGMO_NO_WAIT = 0L;
        f161_MQGMO_WAIT = 1L;
        f162_MQGMO_SYNCPOINT = 2L;
        f163_MQGMO_NO_SYNCPOINT = 4L;
        f164_MQGMO_ACCEPT_TRUNCATED_MSG = 64L;
        f165_MQGMO_FAIL_IF_QUIESCING = 8192L;
        f166_MQGMO_CONVERT = 16384L;
        f167_MQPMO_SYNCPOINT = 2L;
        f168_MQPMO_NO_SYNCPOINT = 4L;
        f169_MQPMO_DEFAULT_CONTEXT = 32L;
        f170_MQPMO_FAIL_IF_QUIESCING = 8192L;
        f171_MQPMO_NO_CONTEXT = 16384L;
        f173_MQMI_NONE = "\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000";
        f174_MQCI_NONE = "\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000";
        f175_MQFMT_NONE = "        ";
        f176_MQFMT_STRING = "MQSTR   ";
        f177_MQCCSI_Q_MGR = 0L;
        f178_MQMT_REQUEST = 1L;
        f179_MQMT_REPLY = 2L;
        f180_MQMT_DATAGRAM = 8L;
        f181_MQOT_Q = 1L;
        f182_MQPER_NOT_PERSISTENT = 0L;
        f183_MQPER_PERSISTENT = 1L;
        f184_MQPER_PERSISTENCE_AS_Q_DEF = 2L;
        Cobol.moveFigurative(Figurative.ZEROS, f33_WS_APPROVED_AMT_DIS, CS);
        Cobol.moveFigurative(Figurative.ZEROS, f226_PA_RQ_TRANSACTION_AMT, CS);
        Cobol.moveFigurative(Figurative.ZEROS, f242_PA_RL_APPROVED_AMT, CS);
        DC_1000.reset();
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 42);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f372_GG_RETURN_CODE, CS).intValue();
    }

    /** One task of the program: the EIB and COMMAREA from the task, then the PROCEDURE DIVISION. */
    public void runTask(CicsTask task) {
        boolean truncBefore = Cobol.swapTruncBinary(true);  // TRUNC(STD)
        boolean pfdBefore = Cobol.swapNumprocPfd(false);  // NUMPROC(NOPFD)
        try {
            this.task = task;
            caBack = () -> { };
            handlers.clear();
            heldKey.clear();
            initialState();
            Cobol.move(task.transid(), f343_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f345_EIBTRMID, CS);
            Cobol.store(f344_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f342_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f341_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (ca instanceof Copaua0cDfhcommarea x) {
                in_Copaua0cDfhcommarea(x, s_DFHCOMMAREA, 0);
                caBack = () -> fill_Copaua0cDfhcommarea(x, s_DFHCOMMAREA, 0);
                calen = cx(task, 4096);
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
            Cobol.store(f348_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                try {
                    perform(0, 42);
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

    public Copaua0cDfhcommarea handleTransaction(String transid, Copaua0cDfhcommarea request) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "COPAUA0C", this::runTask);
        return task.returned(Copaua0cDfhcommarea.class);
    }

    public Copaua0cDfhcommarea handleTransaction(String transid, Copaua0cDfhcommarea request, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request, area);
        region.run(task, "COPAUA0C", this::runTask);
        lastAnswerBytes = task.returnedBytes();
        return task.returned(Copaua0cDfhcommarea.class);
    }

    // @facade-helper: the bytes the last byte-carrying handleTransaction answered
    private byte[] lastAnswerBytes;

    /** The bytes the last byte-carrying handleTransaction's RETURN passed on (a copy; null: none).
     *  @facade-helper */
    public byte[] lastAnswerBytes() {
        return lastAnswerBytes == null ? null : java.util.Arrays.copyOf(lastAnswerBytes, lastAnswerBytes.length);
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
            try {
                perform(0, 42);
            } catch (Goback g) {
                // the program ended
            }
            return Cobol.num(f372_GG_RETURN_CODE, CS).intValue();
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
                if (next >= 43) {
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
            case 27: return p27();
            case 28: return p28();
            case 29: return p29();
            case 30: return p30();
            case 31: return p31();
            case 32: return p32();
            case 33: return p33();
            case 34: return p34();
            case 35: return p35();
            case 36: return p36();
            case 37: return p37();
            case 38: return p38();
            case 39: return p39();
            case 40: return p40();
            case 41: return p41();
            case 42: return p42();
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** MAIN-PARA. */
    private int p0() {
        // PERFORM 1000-INITIALIZE THRU 1000-EXIT
        perform(1, 2);
        // PERFORM 2000-MAIN-PROCESS THRU 2000-EXIT
        perform(7, 8);
        // PERFORM 9000-TERMINATE THRU 9000-EXIT
        perform(35, 36);
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        return 1;
    }

    /** 1000-INITIALIZE. */
    private int p1() {
        // EXEC CICS RETRIEVE INTO(MQTM) NOHANDLE END-EXEC
        CicsTask.RetrieveResult retrieved1 = task.retrieve(684, false, false, false);
        if (retrieved1.data() != null) DetCics.put(f186_MQTM, DetCics.fromRegion(retrieved1.data(), REGION, CS));
        Cobol.store(f369_EIBRESP, BigDecimal.valueOf(DetCics.resp(retrieved1.resp())), false, CS);
        Cobol.store(f370_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        // IF EIBRESP = DFHRESP(NORMAL)
        if (Cobol.num(f369_EIBRESP, CS).compareTo(D0) == 0) {
            // MOVE MQTM-QNAME TO WS-REQUEST-QNAME
            f11_WS_REQUEST_QNAME = Cobol.moveText(f189_MQTM_QNAME, 48, CS);
            // MOVE MQTM-TRIGGERDATA TO WS-TRIGGER-DATA
            f34_WS_TRIGGER_DATA = Cobol.moveText(f191_MQTM_TRIGGERDATA, 64, CS);
        }
        // MOVE 5000 TO WS-WAIT-INTERVAL
        f27_WS_WAIT_INTERVAL = 5000L;
        // PERFORM 1100-OPEN-REQUEST-QUEUE THRU 1100-EXIT
        perform(3, 4);
        // PERFORM 3100-READ-REQUEST-MQ THRU 3100-EXIT
        perform(11, 12);
        return 2;
    }

    /** 1000-EXIT. */
    private int p2() {
        // EXIT
        return 3;
    }

    /** 1100-OPEN-REQUEST-QUEUE. */
    private int p3() {
        // MOVE MQOT-Q TO MQOD-OBJECTTYPE OF MQM-OD-REQUEST
        Cobol.move(BigDecimal.valueOf(f181_MQOT_Q), f72_MQOD_OBJECTTYPE, CS);
        // MOVE WS-REQUEST-QNAME TO MQOD-OBJECTNAME OF MQM-OD-REQUEST
        Cobol.move(f11_WS_REQUEST_QNAME, f73_MQOD_OBJECTNAME, CS);
        // COMPUTE WS-OPTIONS = MQOO-INPUT-SHARED
        BigDecimal v2 = BigDecimal.valueOf(f153_MQOO_INPUT_SHARED);
        Cobol.store(f24_WS_OPTIONS, v2, false, CS);
        // CALL 'MQOPEN' USING W01-HCONN-REQUEST MQM-OD-REQUEST WS-OPTIONS W01-HOBJ-REQUEST WS-COMPCODE WS-REASON
        com.gitgalaxy.modernized.cobolrt.cics.DetMq.mqopen(task, f47_W01_HCONN_REQUEST, f68_MQM_OD_REQUEST, f24_WS_OPTIONS, f48_W01_HOBJ_REQUEST, f25_WS_COMPCODE, f26_WS_REASON);
        // IF WS-COMPCODE = MQCC-OK
        if (BigDecimal.valueOf(f139_MQCC_OK).compareTo(Cobol.num(f25_WS_COMPCODE, CS)) == 0) {
            // SET WS-REQUEST-MQ-OPEN TO TRUE
            f60_WS_REQUEST_MQ_FLG = "O";
        } else {
            // MOVE 'M001' TO ERR-LOCATION
            Cobol.move("M001", f248_ERR_LOCATION, CS);
            // SET ERR-CRITICAL TO TRUE
            Cobol.move("C", f249_ERR_LEVEL, CS);
            // SET ERR-MQ TO TRUE
            Cobol.move("M", f250_ERR_SUBSYSTEM, CS);
            // MOVE WS-COMPCODE TO WS-CODE-DISPLAY
            Cobol.move(f25_WS_COMPCODE, f28_WS_CODE_DISPLAY, CS);
            // MOVE WS-CODE-DISPLAY TO ERR-CODE-1
            Cobol.move(f28_WS_CODE_DISPLAY, f251_ERR_CODE_1, CS);
            // MOVE WS-REASON TO WS-CODE-DISPLAY
            Cobol.move(f26_WS_REASON, f28_WS_CODE_DISPLAY, CS);
            // MOVE WS-CODE-DISPLAY TO ERR-CODE-2
            Cobol.move(f28_WS_CODE_DISPLAY, f252_ERR_CODE_2, CS);
            // MOVE 'REQ MQ OPEN ERROR' TO ERR-MESSAGE
            Cobol.move("REQ MQ OPEN ERROR", f253_ERR_MESSAGE, CS);
            // PERFORM 9500-LOG-ERROR
            perform(39, 39);
        }
        return 4;
    }

    /** 1100-EXIT. */
    private int p4() {
        // EXIT
        return 5;
    }

    /** 1200-SCHEDULE-PSB. */
    private int p5() {
        // EXEC DLI SCHD PSB((PSB-NAME)) NODHABEND END-EXEC
        Cobol.move(com.gitgalaxy.modernized.cobolrt.dli.DetDli.schedule(f42_PSB_NAME, true), f375_DIBSTAT, CS);
        // MOVE DIBSTAT TO IMS-RETURN-CODE
        f45_IMS_RETURN_CODE = Cobol.moveText(f375_DIBSTAT, 2, CS);
        // IF PSB-SCHEDULED-MORE-THAN-ONCE
        if (isPsbScheduledMoreThanOnce()) {
            // EXEC DLI TERM END-EXEC
            Cobol.move(com.gitgalaxy.modernized.cobolrt.dli.DetDli.terminate(), f375_DIBSTAT, CS);
            // EXEC DLI SCHD PSB((PSB-NAME)) NODHABEND END-EXEC
            Cobol.move(com.gitgalaxy.modernized.cobolrt.dli.DetDli.schedule(f42_PSB_NAME, true), f375_DIBSTAT, CS);
            // MOVE DIBSTAT TO IMS-RETURN-CODE
            f45_IMS_RETURN_CODE = Cobol.moveText(f375_DIBSTAT, 2, CS);
        }
        // IF STATUS-OK
        if (isStatusOk()) {
            // SET IMS-PSB-SCHD TO TRUE
            f46_WS_IMS_PSB_SCHD_FLG = "Y";
        } else {
            // MOVE 'I001' TO ERR-LOCATION
            Cobol.move("I001", f248_ERR_LOCATION, CS);
            // SET ERR-CRITICAL TO TRUE
            Cobol.move("C", f249_ERR_LEVEL, CS);
            // SET ERR-IMS TO TRUE
            Cobol.move("I", f250_ERR_SUBSYSTEM, CS);
            // MOVE IMS-RETURN-CODE TO ERR-CODE-1
            Cobol.move(f45_IMS_RETURN_CODE, f251_ERR_CODE_1, CS);
            // MOVE 'IMS SCHD FAILED' TO ERR-MESSAGE
            Cobol.move("IMS SCHD FAILED", f253_ERR_MESSAGE, CS);
            // PERFORM 9500-LOG-ERROR
            perform(39, 39);
        }
        return 6;
    }

    /** 1200-EXIT. */
    private int p6() {
        // EXIT
        return 7;
    }

    /** 2000-MAIN-PROCESS. */
    private int p7() {
        // PERFORM UNTIL NO-MORE-MSG-AVAILABLE OR WS-LOOP-END
        while (!((isNoMoreMsgAvailable() || isWsLoopEnd()))) {
            // PERFORM 2100-EXTRACT-REQUEST-MSG THRU 2100-EXIT
            perform(9, 10);
            // PERFORM 5000-PROCESS-AUTH THRU 5000-EXIT
            perform(13, 14);
            // ADD 1 TO WS-MSG-PROCESSED
            BigDecimal t3 = D1;
            f10_WS_MSG_PROCESSED = Cobol.binary(BigDecimal.valueOf(f10_WS_MSG_PROCESSED).add(t3), 4, true, false, CS);
            // EXEC CICS SYNCPOINT END-EXEC
            task.syncpoint();
            Cobol.store(f369_EIBRESP, BigDecimal.valueOf(0), false, CS);
            Cobol.store(f370_EIBRESP2, BigDecimal.valueOf(0), false, CS);
            // SET IMS-PSB-NOT-SCHD TO TRUE
            f46_WS_IMS_PSB_SCHD_FLG = "N";
            // IF WS-MSG-PROCESSED > WS-REQSTS-PROCESS-LIMIT
            if (f10_WS_MSG_PROCESSED > f9_WS_REQSTS_PROCESS_LIMIT) {
                // SET WS-LOOP-END TO TRUE
                f58_WS_MSG_LOOP_FLG = "E";
            } else {
                // PERFORM 3100-READ-REQUEST-MQ THRU 3100-EXIT
                perform(11, 12);
            }
        }
        return 8;
    }

    /** 2000-EXIT. */
    private int p8() {
        // EXIT
        return 9;
    }

    /** 2100-EXTRACT-REQUEST-MSG. */
    private int p9() {
        // UNSTRING W01-GET-BUFFER(1:W01-DATALEN) DELIMITED BY ',' INTO PA-RQ-AUTH-DATE PA-RQ-AUTH-TIME PA-RQ-CARD-NUM PA-RQ-AUTH-TYPE PA-RQ-CARD-EXPIRY-DATE PA-
        Cobol.unstring(f51_W01_GET_BUFFER.ref(1, Integer.valueOf(Cobol.num(f50_W01_DATALEN, CS).intValue())), null, null, java.util.List.of(Cobol.Delim.of(",", false, CS)), CS, Cobol.Into.of(f218_PA_RQ_AUTH_DATE), Cobol.Into.of(f219_PA_RQ_AUTH_TIME), Cobol.Into.of(f220_PA_RQ_CARD_NUM), Cobol.Into.of(f221_PA_RQ_AUTH_TYPE), Cobol.Into.of(f222_PA_RQ_CARD_EXPIRY_DATE), Cobol.Into.of(f223_PA_RQ_MESSAGE_TYPE), Cobol.Into.of(f224_PA_RQ_MESSAGE_SOURCE), Cobol.Into.of(f225_PA_RQ_PROCESSING_CODE), Cobol.Into.of(f30_WS_TRANSACTION_AMT_AN), Cobol.Into.of(f227_PA_RQ_MERCHANT_CATAGORY_CODE), Cobol.Into.of(f228_PA_RQ_ACQR_COUNTRY_CODE), Cobol.Into.of(f229_PA_RQ_POS_ENTRY_MODE), Cobol.Into.of(f230_PA_RQ_MERCHANT_ID), Cobol.Into.of(f231_PA_RQ_MERCHANT_NAME), Cobol.Into.of(f232_PA_RQ_MERCHANT_CITY), Cobol.Into.of(f233_PA_RQ_MERCHANT_STATE), Cobol.Into.of(f234_PA_RQ_MERCHANT_ZIP), Cobol.Into.of(f235_PA_RQ_TRANSACTION_ID));
        // COMPUTE PA-RQ-TRANSACTION-AMT = FUNCTION NUMVAL(WS-TRANSACTION-AMT-AN)
        BigDecimal v5 = Hfp.numval(Cobol.text(f30_WS_TRANSACTION_AMT_AN, CS), false);
        Cobol.store(f226_PA_RQ_TRANSACTION_AMT, Hfp.fixedStore(v5, 2, false), false, CS);
        // MOVE PA-RQ-TRANSACTION-AMT TO WS-TRANSACTION-AMT
        Cobol.move(f226_PA_RQ_TRANSACTION_AMT, f31_WS_TRANSACTION_AMT, CS);
        return 10;
    }

    /** 2100-EXIT. */
    private int p10() {
        // EXIT
        return 11;
    }

    /** 3100-READ-REQUEST-MQ. */
    private int p11() {
        // COMPUTE MQGMO-OPTIONS = MQGMO-NO-SYNCPOINT + MQGMO-WAIT + MQGMO-CONVERT + MQGMO-FAIL-IF-QUIESCING
        BigDecimal v6 = Cobol.align(Cobol.align(BigDecimal.valueOf(f163_MQGMO_NO_SYNCPOINT).add(BigDecimal.valueOf(f161_MQGMO_WAIT)), 0).add(BigDecimal.valueOf(f166_MQGMO_CONVERT)), 0).add(BigDecimal.valueOf(f165_MQGMO_FAIL_IF_QUIESCING));
        Cobol.store(f212_MQGMO_OPTIONS, v6, false, CS);
        // MOVE WS-WAIT-INTERVAL TO MQGMO-WAITINTERVAL
        Cobol.move(BigDecimal.valueOf(f27_WS_WAIT_INTERVAL), f213_MQGMO_WAITINTERVAL, CS);
        // MOVE MQMI-NONE TO MQMD-MSGID OF MQM-MD-REQUEST
        Cobol.move(f173_MQMI_NONE, f90_MQMD_MSGID, CS);
        // MOVE MQCI-NONE TO MQMD-CORRELID OF MQM-MD-REQUEST
        Cobol.move(f174_MQCI_NONE, f91_MQMD_CORRELID, CS);
        // MOVE MQFMT-STRING TO MQMD-FORMAT OF MQM-MD-REQUEST
        Cobol.move(f176_MQFMT_STRING, f87_MQMD_FORMAT, CS);
        // MOVE LENGTH OF W01-GET-BUFFER TO W01-BUFFLEN
        Cobol.move(BigDecimal.valueOf(500), f49_W01_BUFFLEN, CS);
        // CALL 'MQGET' USING W01-HCONN-REQUEST W01-HOBJ-REQUEST MQM-MD-REQUEST MQM-GET-MESSAGE-OPTIONS W01-BUFFLEN W01-GET-BUFFER W01-DATALEN WS-COMPCODE WS-REA
        com.gitgalaxy.modernized.cobolrt.cics.DetMq.mqget(task, f47_W01_HCONN_REQUEST, f48_W01_HOBJ_REQUEST, f77_MQM_MD_REQUEST, f208_MQM_GET_MESSAGE_OPTIONS, f49_W01_BUFFLEN, f51_W01_GET_BUFFER, f50_W01_DATALEN, f25_WS_COMPCODE, f26_WS_REASON);
        // IF WS-COMPCODE = MQCC-OK
        if (BigDecimal.valueOf(f139_MQCC_OK).compareTo(Cobol.num(f25_WS_COMPCODE, CS)) == 0) {
            // MOVE MQMD-CORRELID OF MQM-MD-REQUEST TO WS-SAVE-CORRELID
            f13_WS_SAVE_CORRELID = Cobol.moveText(f91_MQMD_CORRELID, 24, CS);
            // MOVE MQMD-REPLYTOQ OF MQM-MD-REQUEST TO WS-REPLY-QNAME
            f12_WS_REPLY_QNAME = Cobol.moveText(f93_MQMD_REPLYTOQ, 48, CS);
        } else {
            // ELSE IF WS-REASON = MQRC-NO-MSG-AVAILABLE
            if (BigDecimal.valueOf(f145_MQRC_NO_MSG_AVAILABLE).compareTo(Cobol.num(f26_WS_REASON, CS)) == 0) {
                // SET NO-MORE-MSG-AVAILABLE TO TRUE
                f59_WS_MSG_AVAILABLE_FLG = "N";
            } else {
                // MOVE 'M003' TO ERR-LOCATION
                Cobol.move("M003", f248_ERR_LOCATION, CS);
                // SET ERR-CRITICAL TO TRUE
                Cobol.move("C", f249_ERR_LEVEL, CS);
                // SET ERR-CICS TO TRUE
                Cobol.move("C", f250_ERR_SUBSYSTEM, CS);
                // MOVE WS-COMPCODE TO WS-CODE-DISPLAY
                Cobol.move(f25_WS_COMPCODE, f28_WS_CODE_DISPLAY, CS);
                // MOVE WS-CODE-DISPLAY TO ERR-CODE-1
                Cobol.move(f28_WS_CODE_DISPLAY, f251_ERR_CODE_1, CS);
                // MOVE WS-REASON TO WS-CODE-DISPLAY
                Cobol.move(f26_WS_REASON, f28_WS_CODE_DISPLAY, CS);
                // MOVE WS-CODE-DISPLAY TO ERR-CODE-2
                Cobol.move(f28_WS_CODE_DISPLAY, f252_ERR_CODE_2, CS);
                // MOVE 'FAILED TO READ REQUEST MQ' TO ERR-MESSAGE
                Cobol.move("FAILED TO READ REQUEST MQ", f253_ERR_MESSAGE, CS);
                // MOVE PA-CARD-NUM TO ERR-EVENT-KEY
                Cobol.move(f275_PA_CARD_NUM, f254_ERR_EVENT_KEY, CS);
                // PERFORM 9500-LOG-ERROR
                perform(39, 39);
            }
        }
        return 12;
    }

    /** 3100-EXIT. */
    private int p12() {
        // EXIT
        return 13;
    }

    /** 5000-PROCESS-AUTH. */
    private int p13() {
        // SET APPROVE-AUTH TO TRUE
        f66_WS_DECLINE_FLG = "A";
        // PERFORM 1200-SCHEDULE-PSB THRU 1200-EXIT
        perform(5, 6);
        // SET CARD-FOUND-XREF TO TRUE
        f62_WS_XREF_READ_FLG = "Y";
        // SET FOUND-ACCT-IN-MSTR TO TRUE
        f63_WS_ACCT_MASTER_READ_FLG = "Y";
        // PERFORM 5100-READ-XREF-RECORD THRU 5100-EXIT
        perform(15, 16);
        // IF CARD-FOUND-XREF
        if (isCardFoundXref()) {
            // PERFORM 5200-READ-ACCT-RECORD THRU 5200-EXIT
            perform(17, 18);
            // PERFORM 5300-READ-CUST-RECORD THRU 5300-EXIT
            perform(19, 20);
            // PERFORM 5500-READ-AUTH-SUMMRY THRU 5500-EXIT
            perform(21, 22);
            // PERFORM 5600-READ-PROFILE-DATA THRU 5600-EXIT
            perform(23, 24);
        }
        // PERFORM 6000-MAKE-DECISION THRU 6000-EXIT
        perform(25, 26);
        // PERFORM 7100-SEND-RESPONSE THRU 7100-EXIT
        perform(27, 28);
        // IF CARD-FOUND-XREF
        if (isCardFoundXref()) {
            // PERFORM 8000-WRITE-AUTH-TO-DB THRU 8000-EXIT
            perform(29, 30);
        }
        return 14;
    }

    /** 5000-EXIT. */
    private int p14() {
        // EXIT
        return 15;
    }

    /** 5100-READ-XREF-RECORD. */
    private int p15() {
        // MOVE PA-RQ-CARD-NUM TO XREF-CARD-NUM
        Cobol.move(f220_PA_RQ_CARD_NUM, f300_XREF_CARD_NUM, CS);
        // EXEC CICS READ DATASET (WS-CCXREF-FILE) INTO (CARD-XREF-RECORD) LENGTH (LENGTH OF CARD-XREF-RECORD) RIDFLD (XREF-CARD-NUM) KEYLENGTH (LENGTH OF XREF-C
        byte[] rec8 = DetCics.bytes(f300_XREF_CARD_NUM);
        CicsTask.FileRead<byte[]> read7 = task.read(f8_WS_CCXREF_FILE.strip(), () -> store(f8_WS_CCXREF_FILE.strip()).find(rec8));
        if (read7.record() != null) {
            DetCics.put(f299_CARD_XREF_RECORD, read7.record());
        }
        Cobol.store(f369_EIBRESP, BigDecimal.valueOf(read7.resp()), false, CS);
        Cobol.store(f370_EIBRESP2, BigDecimal.valueOf(read7.resp2()), false, CS);
        f15_WS_RESP_CD = Cobol.binary(BigDecimal.valueOf(read7.resp()), 9, true, false, CS);
        f16_WS_REAS_CD = Cobol.binary(BigDecimal.valueOf(read7.resp2()), 9, true, false, CS);
        // EVALUATE WS-RESP-CD
        if ((f15_WS_RESP_CD == 0L)) {
            // SET CARD-FOUND-XREF TO TRUE
            f62_WS_XREF_READ_FLG = "Y";
        } else if ((f15_WS_RESP_CD == 13L)) {
            // SET CARD-NFOUND-XREF TO TRUE
            f62_WS_XREF_READ_FLG = "N";
            // SET NFOUND-ACCT-IN-MSTR TO TRUE
            f63_WS_ACCT_MASTER_READ_FLG = "N";
            // MOVE 'A001' TO ERR-LOCATION
            Cobol.move("A001", f248_ERR_LOCATION, CS);
            // SET ERR-WARNING TO TRUE
            Cobol.move("W", f249_ERR_LEVEL, CS);
            // SET ERR-APP TO TRUE
            Cobol.move("A", f250_ERR_SUBSYSTEM, CS);
            // MOVE 'CARD NOT FOUND IN XREF' TO ERR-MESSAGE
            Cobol.move("CARD NOT FOUND IN XREF", f253_ERR_MESSAGE, CS);
            // MOVE XREF-CARD-NUM TO ERR-EVENT-KEY
            Cobol.move(f300_XREF_CARD_NUM, f254_ERR_EVENT_KEY, CS);
            // PERFORM 9500-LOG-ERROR
            perform(39, 39);
        } else if (true) {
            // MOVE 'C001' TO ERR-LOCATION
            Cobol.move("C001", f248_ERR_LOCATION, CS);
            // SET ERR-CRITICAL TO TRUE
            Cobol.move("C", f249_ERR_LEVEL, CS);
            // SET ERR-CICS TO TRUE
            Cobol.move("C", f250_ERR_SUBSYSTEM, CS);
            // MOVE WS-RESP-CD TO WS-CODE-DISPLAY
            Cobol.move(BigDecimal.valueOf(f15_WS_RESP_CD), f28_WS_CODE_DISPLAY, CS);
            // MOVE WS-CODE-DISPLAY TO ERR-CODE-1
            Cobol.move(f28_WS_CODE_DISPLAY, f251_ERR_CODE_1, CS);
            // MOVE WS-REAS-CD TO WS-CODE-DISPLAY
            Cobol.move(BigDecimal.valueOf(f16_WS_REAS_CD), f28_WS_CODE_DISPLAY, CS);
            // MOVE WS-CODE-DISPLAY TO ERR-CODE-2
            Cobol.move(f28_WS_CODE_DISPLAY, f252_ERR_CODE_2, CS);
            // MOVE 'FAILED TO READ XREF FILE' TO ERR-MESSAGE
            Cobol.move("FAILED TO READ XREF FILE", f253_ERR_MESSAGE, CS);
            // MOVE XREF-CARD-NUM TO ERR-EVENT-KEY
            Cobol.move(f300_XREF_CARD_NUM, f254_ERR_EVENT_KEY, CS);
            // PERFORM 9500-LOG-ERROR
            perform(39, 39);
        }
        return 16;
    }

    /** 5100-EXIT. */
    private int p16() {
        // EXIT
        return 17;
    }

    /** 5200-READ-ACCT-RECORD. */
    private int p17() {
        // MOVE XREF-ACCT-ID TO WS-CARD-RID-ACCT-ID
        Cobol.move(f302_XREF_ACCT_ID, f39_WS_CARD_RID_ACCT_ID, CS);
        // EXEC CICS READ DATASET (WS-ACCTFILENAME) RIDFLD (WS-CARD-RID-ACCT-ID-X) KEYLENGTH (LENGTH OF WS-CARD-RID-ACCT-ID-X) INTO (ACCOUNT-RECORD) LENGTH (LENG
        byte[] rec10 = DetCics.bytes(f40_WS_CARD_RID_ACCT_ID_X);
        CicsTask.FileRead<byte[]> read9 = task.read(f4_WS_ACCTFILENAME.strip(), () -> store(f4_WS_ACCTFILENAME.strip()).find(rec10));
        if (read9.record() != null) {
            DetCics.put(f304_ACCOUNT_RECORD, read9.record());
        }
        Cobol.store(f369_EIBRESP, BigDecimal.valueOf(read9.resp()), false, CS);
        Cobol.store(f370_EIBRESP2, BigDecimal.valueOf(read9.resp2()), false, CS);
        f15_WS_RESP_CD = Cobol.binary(BigDecimal.valueOf(read9.resp()), 9, true, false, CS);
        f16_WS_REAS_CD = Cobol.binary(BigDecimal.valueOf(read9.resp2()), 9, true, false, CS);
        // EVALUATE WS-RESP-CD
        if ((f15_WS_RESP_CD == 0L)) {
            // SET FOUND-ACCT-IN-MSTR TO TRUE
            f63_WS_ACCT_MASTER_READ_FLG = "Y";
        } else if ((f15_WS_RESP_CD == 13L)) {
            // SET NFOUND-ACCT-IN-MSTR TO TRUE
            f63_WS_ACCT_MASTER_READ_FLG = "N";
            // MOVE 'A002' TO ERR-LOCATION
            Cobol.move("A002", f248_ERR_LOCATION, CS);
            // SET ERR-WARNING TO TRUE
            Cobol.move("W", f249_ERR_LEVEL, CS);
            // SET ERR-APP TO TRUE
            Cobol.move("A", f250_ERR_SUBSYSTEM, CS);
            // MOVE 'ACCT NOT FOUND IN XREF' TO ERR-MESSAGE
            Cobol.move("ACCT NOT FOUND IN XREF", f253_ERR_MESSAGE, CS);
            // MOVE WS-CARD-RID-ACCT-ID-X TO ERR-EVENT-KEY
            Cobol.move(f40_WS_CARD_RID_ACCT_ID_X, f254_ERR_EVENT_KEY, CS);
            // PERFORM 9500-LOG-ERROR
            perform(39, 39);
        } else if (true) {
            // MOVE 'C002' TO ERR-LOCATION
            Cobol.move("C002", f248_ERR_LOCATION, CS);
            // SET ERR-CRITICAL TO TRUE
            Cobol.move("C", f249_ERR_LEVEL, CS);
            // SET ERR-CICS TO TRUE
            Cobol.move("C", f250_ERR_SUBSYSTEM, CS);
            // MOVE WS-RESP-CD TO WS-CODE-DISPLAY
            Cobol.move(BigDecimal.valueOf(f15_WS_RESP_CD), f28_WS_CODE_DISPLAY, CS);
            // MOVE WS-CODE-DISPLAY TO ERR-CODE-1
            Cobol.move(f28_WS_CODE_DISPLAY, f251_ERR_CODE_1, CS);
            // MOVE WS-REAS-CD TO WS-CODE-DISPLAY
            Cobol.move(BigDecimal.valueOf(f16_WS_REAS_CD), f28_WS_CODE_DISPLAY, CS);
            // MOVE WS-CODE-DISPLAY TO ERR-CODE-2
            Cobol.move(f28_WS_CODE_DISPLAY, f252_ERR_CODE_2, CS);
            // MOVE 'FAILED TO READ ACCT FILE' TO ERR-MESSAGE
            Cobol.move("FAILED TO READ ACCT FILE", f253_ERR_MESSAGE, CS);
            // MOVE WS-CARD-RID-ACCT-ID-X TO ERR-EVENT-KEY
            Cobol.move(f40_WS_CARD_RID_ACCT_ID_X, f254_ERR_EVENT_KEY, CS);
            // PERFORM 9500-LOG-ERROR
            perform(39, 39);
        }
        return 18;
    }

    /** 5200-EXIT. */
    private int p18() {
        // EXIT
        return 19;
    }

    /** 5300-READ-CUST-RECORD. */
    private int p19() {
        // MOVE XREF-CUST-ID TO WS-CARD-RID-CUST-ID
        Cobol.move(f301_XREF_CUST_ID, f37_WS_CARD_RID_CUST_ID, CS);
        // EXEC CICS READ DATASET (WS-CUSTFILENAME) RIDFLD (WS-CARD-RID-CUST-ID-X) KEYLENGTH (LENGTH OF WS-CARD-RID-CUST-ID-X) INTO (CUSTOMER-RECORD) LENGTH (LEN
        byte[] rec12 = DetCics.bytes(f38_WS_CARD_RID_CUST_ID_X);
        CicsTask.FileRead<byte[]> read11 = task.read(f5_WS_CUSTFILENAME.strip(), () -> store(f5_WS_CUSTFILENAME.strip()).find(rec12));
        if (read11.record() != null) {
            DetCics.put(f318_CUSTOMER_RECORD, read11.record());
        }
        Cobol.store(f369_EIBRESP, BigDecimal.valueOf(read11.resp()), false, CS);
        Cobol.store(f370_EIBRESP2, BigDecimal.valueOf(read11.resp2()), false, CS);
        f15_WS_RESP_CD = Cobol.binary(BigDecimal.valueOf(read11.resp()), 9, true, false, CS);
        f16_WS_REAS_CD = Cobol.binary(BigDecimal.valueOf(read11.resp2()), 9, true, false, CS);
        // EVALUATE WS-RESP-CD
        if ((f15_WS_RESP_CD == 0L)) {
            // SET FOUND-CUST-IN-MSTR TO TRUE
            f64_WS_CUST_MASTER_READ_FLG = "Y";
        } else if ((f15_WS_RESP_CD == 13L)) {
            // SET NFOUND-CUST-IN-MSTR TO TRUE
            f64_WS_CUST_MASTER_READ_FLG = "N";
            // MOVE 'A003' TO ERR-LOCATION
            Cobol.move("A003", f248_ERR_LOCATION, CS);
            // SET ERR-WARNING TO TRUE
            Cobol.move("W", f249_ERR_LEVEL, CS);
            // SET ERR-APP TO TRUE
            Cobol.move("A", f250_ERR_SUBSYSTEM, CS);
            // MOVE 'CUST NOT FOUND IN XREF' TO ERR-MESSAGE
            Cobol.move("CUST NOT FOUND IN XREF", f253_ERR_MESSAGE, CS);
            // MOVE WS-CARD-RID-CUST-ID TO ERR-EVENT-KEY
            Cobol.move(f37_WS_CARD_RID_CUST_ID, f254_ERR_EVENT_KEY, CS);
            // PERFORM 9500-LOG-ERROR
            perform(39, 39);
        } else if (true) {
            // MOVE 'C003' TO ERR-LOCATION
            Cobol.move("C003", f248_ERR_LOCATION, CS);
            // SET ERR-CRITICAL TO TRUE
            Cobol.move("C", f249_ERR_LEVEL, CS);
            // SET ERR-CICS TO TRUE
            Cobol.move("C", f250_ERR_SUBSYSTEM, CS);
            // MOVE WS-RESP-CD TO WS-CODE-DISPLAY
            Cobol.move(BigDecimal.valueOf(f15_WS_RESP_CD), f28_WS_CODE_DISPLAY, CS);
            // MOVE WS-CODE-DISPLAY TO ERR-CODE-1
            Cobol.move(f28_WS_CODE_DISPLAY, f251_ERR_CODE_1, CS);
            // MOVE WS-REAS-CD TO WS-CODE-DISPLAY
            Cobol.move(BigDecimal.valueOf(f16_WS_REAS_CD), f28_WS_CODE_DISPLAY, CS);
            // MOVE WS-CODE-DISPLAY TO ERR-CODE-2
            Cobol.move(f28_WS_CODE_DISPLAY, f252_ERR_CODE_2, CS);
            // MOVE 'FAILED TO READ CUST FILE' TO ERR-MESSAGE
            Cobol.move("FAILED TO READ CUST FILE", f253_ERR_MESSAGE, CS);
            // MOVE WS-CARD-RID-CUST-ID TO ERR-EVENT-KEY
            Cobol.move(f37_WS_CARD_RID_CUST_ID, f254_ERR_EVENT_KEY, CS);
            // PERFORM 9500-LOG-ERROR
            perform(39, 39);
        }
        return 20;
    }

    /** 5300-EXIT. */
    private int p20() {
        // EXIT
        return 21;
    }

    /** 5500-READ-AUTH-SUMMRY. */
    private int p21() {
        // MOVE XREF-ACCT-ID TO PA-ACCT-ID
        Cobol.move(f302_XREF_ACCT_ID, f256_PA_ACCT_ID, CS);
        // EXEC DLI GU USING PCB(PAUT-PCB-NUM) SEGMENT (PAUTSUM0) INTO (PENDING-AUTH-SUMMARY) WHERE (ACCNTID = PA-ACCT-ID) END-EXEC
        Cobol.move(com.gitgalaxy.modernized.cobolrt.dli.DetDli.get("GU", BigDecimal.valueOf(f44_PAUT_PCB_NUM).intValue(), f255_PENDING_AUTH_SUMMARY, com.gitgalaxy.modernized.cobolrt.dli.DetDli.ssa("PAUTSUM0", "ACCNTID", "EQ", f256_PA_ACCT_ID)), f375_DIBSTAT, CS);
        // MOVE DIBSTAT TO IMS-RETURN-CODE
        f45_IMS_RETURN_CODE = Cobol.moveText(f375_DIBSTAT, 2, CS);
        // EVALUATE TRUE
        if ((isStatusOk())) {
            // SET FOUND-PAUT-SMRY-SEG TO TRUE
            f65_WS_PAUT_SMRY_SEG_FLG = "Y";
        } else if ((isSegmentNotFound())) {
            // SET NFOUND-PAUT-SMRY-SEG TO TRUE
            f65_WS_PAUT_SMRY_SEG_FLG = "N";
        } else if (true) {
            // MOVE 'I002' TO ERR-LOCATION
            Cobol.move("I002", f248_ERR_LOCATION, CS);
            // SET ERR-CRITICAL TO TRUE
            Cobol.move("C", f249_ERR_LEVEL, CS);
            // SET ERR-IMS TO TRUE
            Cobol.move("I", f250_ERR_SUBSYSTEM, CS);
            // MOVE IMS-RETURN-CODE TO ERR-CODE-1
            Cobol.move(f45_IMS_RETURN_CODE, f251_ERR_CODE_1, CS);
            // MOVE 'IMS GET SUMMARY FAILED' TO ERR-MESSAGE
            Cobol.move("IMS GET SUMMARY FAILED", f253_ERR_MESSAGE, CS);
            // MOVE PA-CARD-NUM TO ERR-EVENT-KEY
            Cobol.move(f275_PA_CARD_NUM, f254_ERR_EVENT_KEY, CS);
            // PERFORM 9500-LOG-ERROR
            perform(39, 39);
        }
        return 22;
    }

    /** 5500-EXIT. */
    private int p22() {
        // EXIT
        return 23;
    }

    /** 5600-READ-PROFILE-DATA. */
    private int p23() {
        // CONTINUE
        return 24;
    }

    /** 5600-EXIT. */
    private int p24() {
        // EXIT
        return 25;
    }

    /** 6000-MAKE-DECISION. */
    private int p25() {
        // MOVE PA-RQ-CARD-NUM TO PA-RL-CARD-NUM
        Cobol.move(f220_PA_RQ_CARD_NUM, f237_PA_RL_CARD_NUM, CS);
        // MOVE PA-RQ-TRANSACTION-ID TO PA-RL-TRANSACTION-ID
        Cobol.move(f235_PA_RQ_TRANSACTION_ID, f238_PA_RL_TRANSACTION_ID, CS);
        // MOVE PA-RQ-AUTH-TIME TO PA-RL-AUTH-ID-CODE
        Cobol.move(f219_PA_RQ_AUTH_TIME, f239_PA_RL_AUTH_ID_CODE, CS);
        // IF FOUND-PAUT-SMRY-SEG
        if (isFoundPautSmrySeg()) {
            // COMPUTE WS-AVAILABLE-AMT = PA-CREDIT-LIMIT - PA-CREDIT-BALANCE
            BigDecimal v13 = Cobol.num(f260_PA_CREDIT_LIMIT, CS).subtract(Cobol.num(f262_PA_CREDIT_BALANCE, CS));
            f29_WS_AVAILABLE_AMT = Cobol.packed(v13, 11, 2, true, false, CS);
            // IF WS-TRANSACTION-AMT > WS-AVAILABLE-AMT
            if (f29_WS_AVAILABLE_AMT.compareTo(Cobol.num(f31_WS_TRANSACTION_AMT, CS)) < 0) {
                // SET DECLINE-AUTH TO TRUE
                f66_WS_DECLINE_FLG = "D";
                // SET INSUFFICIENT-FUND TO TRUE
                f67_WS_DECLINE_REASON_FLG = "I";
            }
        } else {
            // ELSE IF FOUND-ACCT-IN-MSTR
            if (isFoundAcctInMstr()) {
                // COMPUTE WS-AVAILABLE-AMT = ACCT-CREDIT-LIMIT - ACCT-CURR-BAL
                BigDecimal v14 = Cobol.num(f308_ACCT_CREDIT_LIMIT, CS).subtract(Cobol.num(f307_ACCT_CURR_BAL, CS));
                f29_WS_AVAILABLE_AMT = Cobol.packed(v14, 11, 2, true, false, CS);
                // IF WS-TRANSACTION-AMT > WS-AVAILABLE-AMT
                if (f29_WS_AVAILABLE_AMT.compareTo(Cobol.num(f31_WS_TRANSACTION_AMT, CS)) < 0) {
                    // SET DECLINE-AUTH TO TRUE
                    f66_WS_DECLINE_FLG = "D";
                    // SET INSUFFICIENT-FUND TO TRUE
                    f67_WS_DECLINE_REASON_FLG = "I";
                }
            } else {
                // SET DECLINE-AUTH TO TRUE
                f66_WS_DECLINE_FLG = "D";
            }
        }
        // IF DECLINE-AUTH
        if (isDeclineAuth()) {
            // SET AUTH-RESP-DECLINED TO TRUE
            f57_WS_AUTH_RESP_FLG = "D";
            // MOVE '05' TO PA-RL-AUTH-RESP-CODE
            Cobol.move("05", f240_PA_RL_AUTH_RESP_CODE, CS);
            // MOVE 0 TO PA-RL-APPROVED-AMT WS-APPROVED-AMT
            Cobol.move(D0, f242_PA_RL_APPROVED_AMT, CS);
            Cobol.move(D0, f32_WS_APPROVED_AMT, CS);
        } else {
            // SET AUTH-RESP-APPROVED TO TRUE
            f57_WS_AUTH_RESP_FLG = "A";
            // MOVE '00' TO PA-RL-AUTH-RESP-CODE
            Cobol.move("00", f240_PA_RL_AUTH_RESP_CODE, CS);
            // MOVE PA-RQ-TRANSACTION-AMT TO PA-RL-APPROVED-AMT WS-APPROVED-AMT
            Cobol.move(f226_PA_RQ_TRANSACTION_AMT, f242_PA_RL_APPROVED_AMT, CS);
            Cobol.move(f226_PA_RQ_TRANSACTION_AMT, f32_WS_APPROVED_AMT, CS);
        }
        // MOVE '0000' TO PA-RL-AUTH-RESP-REASON
        Cobol.move("0000", f241_PA_RL_AUTH_RESP_REASON, CS);
        // IF AUTH-RESP-DECLINED
        if (isAuthRespDeclined()) {
            // EVALUATE TRUE
            if ((isCardNfoundXref()) || (isNfoundAcctInMstr()) || (isNfoundCustInMstr())) {
                // MOVE '3100' TO PA-RL-AUTH-RESP-REASON
                Cobol.move("3100", f241_PA_RL_AUTH_RESP_REASON, CS);
            } else if ((isInsufficientFund())) {
                // MOVE '4100' TO PA-RL-AUTH-RESP-REASON
                Cobol.move("4100", f241_PA_RL_AUTH_RESP_REASON, CS);
            } else if ((isCardNotActive())) {
                // MOVE '4200' TO PA-RL-AUTH-RESP-REASON
                Cobol.move("4200", f241_PA_RL_AUTH_RESP_REASON, CS);
            } else if ((isAccountClosed())) {
                // MOVE '4300' TO PA-RL-AUTH-RESP-REASON
                Cobol.move("4300", f241_PA_RL_AUTH_RESP_REASON, CS);
            } else if ((isCardFraud())) {
                // MOVE '5100' TO PA-RL-AUTH-RESP-REASON
                Cobol.move("5100", f241_PA_RL_AUTH_RESP_REASON, CS);
            } else if ((isMerchantFraud())) {
                // MOVE '5200' TO PA-RL-AUTH-RESP-REASON
                Cobol.move("5200", f241_PA_RL_AUTH_RESP_REASON, CS);
            } else if (true) {
                // MOVE '9000' TO PA-RL-AUTH-RESP-REASON
                Cobol.move("9000", f241_PA_RL_AUTH_RESP_REASON, CS);
            }
        }
        // MOVE WS-APPROVED-AMT TO WS-APPROVED-AMT-DIS
        Cobol.move(f32_WS_APPROVED_AMT, f33_WS_APPROVED_AMT_DIS, CS);
        // STRING PA-RL-CARD-NUM ',' PA-RL-TRANSACTION-ID ',' PA-RL-AUTH-ID-CODE ',' PA-RL-AUTH-RESP-CODE ',' PA-RL-AUTH-RESP-REASON ',' WS-APPROVED-AMT-DIS ',' 
        Cobol.string(f55_W02_PUT_BUFFER, f14_WS_RESP_LENGTH, CS, Cobol.StringPart.size(f237_PA_RL_CARD_NUM), Cobol.StringPart.size(",", CS), Cobol.StringPart.size(f238_PA_RL_TRANSACTION_ID), Cobol.StringPart.size(",", CS), Cobol.StringPart.size(f239_PA_RL_AUTH_ID_CODE), Cobol.StringPart.size(",", CS), Cobol.StringPart.size(f240_PA_RL_AUTH_RESP_CODE), Cobol.StringPart.size(",", CS), Cobol.StringPart.size(f241_PA_RL_AUTH_RESP_REASON), Cobol.StringPart.size(",", CS), Cobol.StringPart.size(f33_WS_APPROVED_AMT_DIS), Cobol.StringPart.size(",", CS));
        return 26;
    }

    /** 6000-EXIT. */
    private int p26() {
        // EXIT
        return 27;
    }

    /** 7100-SEND-RESPONSE. */
    private int p27() {
        // MOVE MQOT-Q TO MQOD-OBJECTTYPE OF MQM-OD-REPLY
        Cobol.move(BigDecimal.valueOf(f181_MQOT_Q), f107_MQOD_OBJECTTYPE, CS);
        // MOVE WS-REPLY-QNAME TO MQOD-OBJECTNAME OF MQM-OD-REPLY
        Cobol.move(f12_WS_REPLY_QNAME, f108_MQOD_OBJECTNAME, CS);
        // MOVE MQMT-REPLY TO MQMD-MSGTYPE OF MQM-MD-REPLY
        Cobol.move(BigDecimal.valueOf(f179_MQMT_REPLY), f117_MQMD_MSGTYPE, CS);
        // MOVE WS-SAVE-CORRELID TO MQMD-CORRELID OF MQM-MD-REPLY
        Cobol.move(f13_WS_SAVE_CORRELID, f126_MQMD_CORRELID, CS);
        // MOVE MQMI-NONE TO MQMD-MSGID OF MQM-MD-REPLY
        Cobol.move(f173_MQMI_NONE, f125_MQMD_MSGID, CS);
        // MOVE SPACES TO MQMD-REPLYTOQ OF MQM-MD-REPLY
        Cobol.moveFigurative(Figurative.SPACES, f128_MQMD_REPLYTOQ, CS);
        // MOVE SPACES TO MQMD-REPLYTOQMGR OF MQM-MD-REPLY
        Cobol.moveFigurative(Figurative.SPACES, f129_MQMD_REPLYTOQMGR, CS);
        // MOVE MQPER-NOT-PERSISTENT TO MQMD-PERSISTENCE OF MQM-MD-REPLY
        Cobol.move(BigDecimal.valueOf(f182_MQPER_NOT_PERSISTENT), f124_MQMD_PERSISTENCE, CS);
        // MOVE 50 TO MQMD-EXPIRY OF MQM-MD-REPLY
        Cobol.move(D50, f118_MQMD_EXPIRY, CS);
        // MOVE MQFMT-STRING TO MQMD-FORMAT OF MQM-MD-REPLY
        Cobol.move(f176_MQFMT_STRING, f122_MQMD_FORMAT, CS);
        // COMPUTE MQPMO-OPTIONS = MQPMO-NO-SYNCPOINT + MQPMO-DEFAULT-CONTEXT
        BigDecimal v15 = BigDecimal.valueOf(f168_MQPMO_NO_SYNCPOINT).add(BigDecimal.valueOf(f169_MQPMO_DEFAULT_CONTEXT));
        Cobol.store(f200_MQPMO_OPTIONS, v15, false, CS);
        // MOVE WS-RESP-LENGTH TO W02-BUFFLEN
        Cobol.move(f14_WS_RESP_LENGTH, f53_W02_BUFFLEN, CS);
        // CALL 'MQPUT1' USING W02-HCONN-REPLY MQM-OD-REPLY MQM-MD-REPLY MQM-PUT-MESSAGE-OPTIONS W02-BUFFLEN W02-PUT-BUFFER WS-COMPCODE WS-REASON
        com.gitgalaxy.modernized.cobolrt.cics.DetMq.mqput1(task, f52_W02_HCONN_REPLY, f103_MQM_OD_REPLY, f112_MQM_MD_REPLY, f196_MQM_PUT_MESSAGE_OPTIONS, f53_W02_BUFFLEN, f55_W02_PUT_BUFFER, f25_WS_COMPCODE, f26_WS_REASON);
        // IF WS-COMPCODE NOT = MQCC-OK
        if (!(BigDecimal.valueOf(f139_MQCC_OK).compareTo(Cobol.num(f25_WS_COMPCODE, CS)) == 0)) {
            // MOVE 'M004' TO ERR-LOCATION
            Cobol.move("M004", f248_ERR_LOCATION, CS);
            // SET ERR-CRITICAL TO TRUE
            Cobol.move("C", f249_ERR_LEVEL, CS);
            // SET ERR-MQ TO TRUE
            Cobol.move("M", f250_ERR_SUBSYSTEM, CS);
            // MOVE WS-COMPCODE TO WS-CODE-DISPLAY
            Cobol.move(f25_WS_COMPCODE, f28_WS_CODE_DISPLAY, CS);
            // MOVE WS-CODE-DISPLAY TO ERR-CODE-1
            Cobol.move(f28_WS_CODE_DISPLAY, f251_ERR_CODE_1, CS);
            // MOVE WS-REASON TO WS-CODE-DISPLAY
            Cobol.move(f26_WS_REASON, f28_WS_CODE_DISPLAY, CS);
            // MOVE WS-CODE-DISPLAY TO ERR-CODE-2
            Cobol.move(f28_WS_CODE_DISPLAY, f252_ERR_CODE_2, CS);
            // MOVE 'FAILED TO PUT ON REPLY MQ' TO ERR-MESSAGE
            Cobol.move("FAILED TO PUT ON REPLY MQ", f253_ERR_MESSAGE, CS);
            // MOVE PA-CARD-NUM TO ERR-EVENT-KEY
            Cobol.move(f275_PA_CARD_NUM, f254_ERR_EVENT_KEY, CS);
            // PERFORM 9500-LOG-ERROR
            perform(39, 39);
        }
        return 28;
    }

    /** 7100-EXIT. */
    private int p28() {
        // EXIT
        return 29;
    }

    /** 8000-WRITE-AUTH-TO-DB. */
    private int p29() {
        // PERFORM 8400-UPDATE-SUMMARY THRU 8400-EXIT
        perform(31, 32);
        // PERFORM 8500-INSERT-AUTH THRU 8500-EXIT
        perform(33, 34);
        return 30;
    }

    /** 8000-EXIT. */
    private int p30() {
        // EXIT
        return 31;
    }

    /** 8400-UPDATE-SUMMARY. */
    private int p31() {
        // IF NFOUND-PAUT-SMRY-SEG
        if (isNfoundPautSmrySeg()) {
            // INITIALIZE PENDING-AUTH-SUMMARY REPLACING NUMERIC DATA BY ZERO
            Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 0, 11, 0, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 6, 9, 0, false, false, false), CS);
            if (!Cobol.sameBytes(Field.alphanumeric(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 16, 2, false), Field.alphanumeric(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 18, 2, false))) throw new Hole("INITIALIZE REPLACING of the table PA-ACCOUNT-STATUS: occurrence 2 of PA-ACCOUNT-STATUS differs from the first, which the oracle would copy (register C17)");
            if (!Cobol.sameBytes(Field.alphanumeric(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 16, 2, false), Field.alphanumeric(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 20, 2, false))) throw new Hole("INITIALIZE REPLACING of the table PA-ACCOUNT-STATUS: occurrence 3 of PA-ACCOUNT-STATUS differs from the first, which the oracle would copy (register C17)");
            if (!Cobol.sameBytes(Field.alphanumeric(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 16, 2, false), Field.alphanumeric(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 22, 2, false))) throw new Hole("INITIALIZE REPLACING of the table PA-ACCOUNT-STATUS: occurrence 4 of PA-ACCOUNT-STATUS differs from the first, which the oracle would copy (register C17)");
            if (!Cobol.sameBytes(Field.alphanumeric(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 16, 2, false), Field.alphanumeric(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 24, 2, false))) throw new Hole("INITIALIZE REPLACING of the table PA-ACCOUNT-STATUS: occurrence 5 of PA-ACCOUNT-STATUS differs from the first, which the oracle would copy (register C17)");
            Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 26, 11, 2, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 32, 11, 2, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 38, 11, 2, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 44, 11, 2, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.binary(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 50, 4, 0, true, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.binary(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 52, 4, 0, true, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 54, 11, 2, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f255_PENDING_AUTH_SUMMARY.storage(), f255_PENDING_AUTH_SUMMARY.offset() + 60, 11, 2, true), CS);
            // MOVE XREF-ACCT-ID TO PA-ACCT-ID
            Cobol.move(f302_XREF_ACCT_ID, f256_PA_ACCT_ID, CS);
            // MOVE XREF-CUST-ID TO PA-CUST-ID
            Cobol.move(f301_XREF_CUST_ID, f257_PA_CUST_ID, CS);
        }
        // MOVE ACCT-CREDIT-LIMIT TO PA-CREDIT-LIMIT
        Cobol.move(f308_ACCT_CREDIT_LIMIT, f260_PA_CREDIT_LIMIT, CS);
        // MOVE ACCT-CASH-CREDIT-LIMIT TO PA-CASH-LIMIT
        Cobol.move(f309_ACCT_CASH_CREDIT_LIMIT, f261_PA_CASH_LIMIT, CS);
        // IF AUTH-RESP-APPROVED
        if (isAuthRespApproved()) {
            // ADD 1 TO PA-APPROVED-AUTH-CNT
            BigDecimal t16 = D1;
            Cobol.store(f264_PA_APPROVED_AUTH_CNT, Cobol.receiverNum(f264_PA_APPROVED_AUTH_CNT, CS).add(t16), false, CS);
            // ADD WS-APPROVED-AMT TO PA-APPROVED-AUTH-AMT
            BigDecimal t18 = Cobol.num(f32_WS_APPROVED_AMT, CS);
            Cobol.store(f266_PA_APPROVED_AUTH_AMT, Cobol.receiverNum(f266_PA_APPROVED_AUTH_AMT, CS).add(t18), false, CS);
            // ADD WS-APPROVED-AMT TO PA-CREDIT-BALANCE
            BigDecimal t20 = Cobol.num(f32_WS_APPROVED_AMT, CS);
            Cobol.store(f262_PA_CREDIT_BALANCE, Cobol.receiverNum(f262_PA_CREDIT_BALANCE, CS).add(t20), false, CS);
            // MOVE 0 TO PA-CASH-BALANCE
            Cobol.move(D0, f263_PA_CASH_BALANCE, CS);
        } else {
            // ADD 1 TO PA-DECLINED-AUTH-CNT
            BigDecimal t22 = D1;
            Cobol.store(f265_PA_DECLINED_AUTH_CNT, Cobol.receiverNum(f265_PA_DECLINED_AUTH_CNT, CS).add(t22), false, CS);
            // ADD PA-TRANSACTION-AMT TO PA-DECLINED-AUTH-AMT
            BigDecimal t24 = Cobol.num(f284_PA_TRANSACTION_AMT, CS);
            Cobol.store(f267_PA_DECLINED_AUTH_AMT, Cobol.receiverNum(f267_PA_DECLINED_AUTH_AMT, CS).add(t24), false, CS);
        }
        // IF FOUND-PAUT-SMRY-SEG
        if (isFoundPautSmrySeg()) {
            // EXEC DLI REPL USING PCB(PAUT-PCB-NUM) SEGMENT (PAUTSUM0) FROM (PENDING-AUTH-SUMMARY) END-EXEC
            Cobol.move(com.gitgalaxy.modernized.cobolrt.dli.DetDli.execChange("REPL", BigDecimal.valueOf(f44_PAUT_PCB_NUM).intValue(), f255_PENDING_AUTH_SUMMARY, "PAUTSUM0"), f375_DIBSTAT, CS);
        } else {
            // EXEC DLI ISRT USING PCB(PAUT-PCB-NUM) SEGMENT (PAUTSUM0) FROM (PENDING-AUTH-SUMMARY) END-EXEC
            Cobol.move(com.gitgalaxy.modernized.cobolrt.dli.DetDli.execIsrt(BigDecimal.valueOf(f44_PAUT_PCB_NUM).intValue(), f255_PENDING_AUTH_SUMMARY, -1, com.gitgalaxy.modernized.cobolrt.dli.DetDli.ssa("PAUTSUM0")), f375_DIBSTAT, CS);
        }
        // MOVE DIBSTAT TO IMS-RETURN-CODE
        f45_IMS_RETURN_CODE = Cobol.moveText(f375_DIBSTAT, 2, CS);
        // IF STATUS-OK
        if (isStatusOk()) {
            // CONTINUE
        } else {
            // MOVE 'I003' TO ERR-LOCATION
            Cobol.move("I003", f248_ERR_LOCATION, CS);
            // SET ERR-CRITICAL TO TRUE
            Cobol.move("C", f249_ERR_LEVEL, CS);
            // SET ERR-IMS TO TRUE
            Cobol.move("I", f250_ERR_SUBSYSTEM, CS);
            // MOVE IMS-RETURN-CODE TO ERR-CODE-1
            Cobol.move(f45_IMS_RETURN_CODE, f251_ERR_CODE_1, CS);
            // MOVE 'IMS UPDATE SUMRY FAILED' TO ERR-MESSAGE
            Cobol.move("IMS UPDATE SUMRY FAILED", f253_ERR_MESSAGE, CS);
            // MOVE PA-CARD-NUM TO ERR-EVENT-KEY
            Cobol.move(f275_PA_CARD_NUM, f254_ERR_EVENT_KEY, CS);
            // PERFORM 9500-LOG-ERROR
            perform(39, 39);
        }
        return 32;
    }

    /** 8400-EXIT. */
    private int p32() {
        // EXIT
        return 33;
    }

    /** 8500-INSERT-AUTH. */
    private int p33() {
        // EXEC CICS ASKTIME NOHANDLE ABSTIME(WS-ABS-TIME) END-EXEC
        Cobol.store(f17_WS_ABS_TIME, BigDecimal.valueOf(task.asktime()), false, CS);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS-TIME) YYDDD(WS-CUR-DATE-X6) TIME(WS-CUR-TIME-X6) MILLISECONDS(WS-CUR-TIME-MS) END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f17_WS_ABS_TIME, CS).longValue(), "YYDDD", ""), f18_WS_CUR_DATE_X6, CS);
        f21_WS_CUR_TIME_MS = Cobol.binary(BigDecimal.valueOf(CicsTask.formatNumber(Cobol.num(f17_WS_ABS_TIME, CS).longValue(), "MILLISECONDS")), 8, true, false, CS);
        Cobol.move(CicsTask.formatTime(Cobol.num(f17_WS_ABS_TIME, CS).longValue(), ""), f19_WS_CUR_TIME_X6, CS);
        // MOVE WS-CUR-DATE-X6(1:5) TO WS-YYDDD
        Cobol.move(f18_WS_CUR_DATE_X6.ref(1, Integer.valueOf(5)), f22_WS_YYDDD, CS);
        // MOVE WS-CUR-TIME-X6 TO WS-CUR-TIME-N6
        Cobol.move(f19_WS_CUR_TIME_X6, f20_WS_CUR_TIME_N6, CS);
        // COMPUTE WS-TIME-WITH-MS = (WS-CUR-TIME-N6 * 1000) + WS-CUR-TIME-MS
        BigDecimal v26 = Cobol.align(Cobol.multiply(Cobol.num(f20_WS_CUR_TIME_N6, CS), DC_1000), 0).add(BigDecimal.valueOf(f21_WS_CUR_TIME_MS));
        f23_WS_TIME_WITH_MS = Cobol.packed(v26, 9, 0, true, false, CS);
        // COMPUTE PA-AUTH-DATE-9C = 99999 - WS-YYDDD
        BigDecimal v27 = D99999.subtract(Cobol.num(f22_WS_YYDDD, CS));
        Cobol.store(f271_PA_AUTH_DATE_9C, v27, false, CS);
        // COMPUTE PA-AUTH-TIME-9C = 999999999 - WS-TIME-WITH-MS
        BigDecimal v28 = D999999999.subtract(f23_WS_TIME_WITH_MS);
        Cobol.store(f272_PA_AUTH_TIME_9C, v28, false, CS);
        // MOVE PA-RQ-AUTH-DATE TO PA-AUTH-ORIG-DATE
        Cobol.move(f218_PA_RQ_AUTH_DATE, f273_PA_AUTH_ORIG_DATE, CS);
        // MOVE PA-RQ-AUTH-TIME TO PA-AUTH-ORIG-TIME
        Cobol.move(f219_PA_RQ_AUTH_TIME, f274_PA_AUTH_ORIG_TIME, CS);
        // MOVE PA-RQ-CARD-NUM TO PA-CARD-NUM
        Cobol.move(f220_PA_RQ_CARD_NUM, f275_PA_CARD_NUM, CS);
        // MOVE PA-RQ-AUTH-TYPE TO PA-AUTH-TYPE
        Cobol.move(f221_PA_RQ_AUTH_TYPE, f276_PA_AUTH_TYPE, CS);
        // MOVE PA-RQ-CARD-EXPIRY-DATE TO PA-CARD-EXPIRY-DATE
        Cobol.move(f222_PA_RQ_CARD_EXPIRY_DATE, f277_PA_CARD_EXPIRY_DATE, CS);
        // MOVE PA-RQ-MESSAGE-TYPE TO PA-MESSAGE-TYPE
        Cobol.move(f223_PA_RQ_MESSAGE_TYPE, f278_PA_MESSAGE_TYPE, CS);
        // MOVE PA-RQ-MESSAGE-SOURCE TO PA-MESSAGE-SOURCE
        Cobol.move(f224_PA_RQ_MESSAGE_SOURCE, f279_PA_MESSAGE_SOURCE, CS);
        // MOVE PA-RQ-PROCESSING-CODE TO PA-PROCESSING-CODE
        Cobol.move(f225_PA_RQ_PROCESSING_CODE, f283_PA_PROCESSING_CODE, CS);
        // MOVE PA-RQ-TRANSACTION-AMT TO PA-TRANSACTION-AMT
        Cobol.move(f226_PA_RQ_TRANSACTION_AMT, f284_PA_TRANSACTION_AMT, CS);
        // MOVE PA-RQ-MERCHANT-CATAGORY-CODE TO PA-MERCHANT-CATAGORY-CODE
        Cobol.move(f227_PA_RQ_MERCHANT_CATAGORY_CODE, f286_PA_MERCHANT_CATAGORY_CODE, CS);
        // MOVE PA-RQ-ACQR-COUNTRY-CODE TO PA-ACQR-COUNTRY-CODE
        Cobol.move(f228_PA_RQ_ACQR_COUNTRY_CODE, f287_PA_ACQR_COUNTRY_CODE, CS);
        // MOVE PA-RQ-POS-ENTRY-MODE TO PA-POS-ENTRY-MODE
        Cobol.move(f229_PA_RQ_POS_ENTRY_MODE, f288_PA_POS_ENTRY_MODE, CS);
        // MOVE PA-RQ-MERCHANT-ID TO PA-MERCHANT-ID
        Cobol.move(f230_PA_RQ_MERCHANT_ID, f289_PA_MERCHANT_ID, CS);
        // MOVE PA-RQ-MERCHANT-NAME TO PA-MERCHANT-NAME
        Cobol.move(f231_PA_RQ_MERCHANT_NAME, f290_PA_MERCHANT_NAME, CS);
        // MOVE PA-RQ-MERCHANT-CITY TO PA-MERCHANT-CITY
        Cobol.move(f232_PA_RQ_MERCHANT_CITY, f291_PA_MERCHANT_CITY, CS);
        // MOVE PA-RQ-MERCHANT-STATE TO PA-MERCHANT-STATE
        Cobol.move(f233_PA_RQ_MERCHANT_STATE, f292_PA_MERCHANT_STATE, CS);
        // MOVE PA-RQ-MERCHANT-ZIP TO PA-MERCHANT-ZIP
        Cobol.move(f234_PA_RQ_MERCHANT_ZIP, f293_PA_MERCHANT_ZIP, CS);
        // MOVE PA-RQ-TRANSACTION-ID TO PA-TRANSACTION-ID
        Cobol.move(f235_PA_RQ_TRANSACTION_ID, f294_PA_TRANSACTION_ID, CS);
        // MOVE PA-RL-AUTH-ID-CODE TO PA-AUTH-ID-CODE
        Cobol.move(f239_PA_RL_AUTH_ID_CODE, f280_PA_AUTH_ID_CODE, CS);
        // MOVE PA-RL-AUTH-RESP-CODE TO PA-AUTH-RESP-CODE
        Cobol.move(f240_PA_RL_AUTH_RESP_CODE, f281_PA_AUTH_RESP_CODE, CS);
        // MOVE PA-RL-AUTH-RESP-REASON TO PA-AUTH-RESP-REASON
        Cobol.move(f241_PA_RL_AUTH_RESP_REASON, f282_PA_AUTH_RESP_REASON, CS);
        // MOVE PA-RL-APPROVED-AMT TO PA-APPROVED-AMT
        Cobol.move(f242_PA_RL_APPROVED_AMT, f285_PA_APPROVED_AMT, CS);
        // IF AUTH-RESP-APPROVED
        if (isAuthRespApproved()) {
            // SET PA-MATCH-PENDING TO TRUE
            Cobol.move("P", f295_PA_MATCH_STATUS, CS);
        } else {
            // SET PA-MATCH-AUTH-DECLINED TO TRUE
            Cobol.move("D", f295_PA_MATCH_STATUS, CS);
        }
        // MOVE SPACE TO PA-AUTH-FRAUD PA-FRAUD-RPT-DATE
        Cobol.moveFigurative(Figurative.SPACES, f296_PA_AUTH_FRAUD, CS);
        Cobol.moveFigurative(Figurative.SPACES, f297_PA_FRAUD_RPT_DATE, CS);
        // MOVE XREF-ACCT-ID TO PA-ACCT-ID
        Cobol.move(f302_XREF_ACCT_ID, f256_PA_ACCT_ID, CS);
        // EXEC DLI ISRT USING PCB(PAUT-PCB-NUM) SEGMENT (PAUTSUM0) WHERE (ACCNTID = PA-ACCT-ID) SEGMENT (PAUTDTL1) FROM (PENDING-AUTH-DETAILS) SEGLENGTH (LENGTH
        Cobol.move(com.gitgalaxy.modernized.cobolrt.dli.DetDli.execIsrt(BigDecimal.valueOf(f44_PAUT_PCB_NUM).intValue(), f269_PENDING_AUTH_DETAILS, BigDecimal.valueOf(200).intValue(), com.gitgalaxy.modernized.cobolrt.dli.DetDli.ssa("PAUTSUM0", "ACCNTID", "EQ", f256_PA_ACCT_ID), com.gitgalaxy.modernized.cobolrt.dli.DetDli.ssa("PAUTDTL1")), f375_DIBSTAT, CS);
        // MOVE DIBSTAT TO IMS-RETURN-CODE
        f45_IMS_RETURN_CODE = Cobol.moveText(f375_DIBSTAT, 2, CS);
        // IF STATUS-OK
        if (isStatusOk()) {
            // CONTINUE
        } else {
            // MOVE 'I004' TO ERR-LOCATION
            Cobol.move("I004", f248_ERR_LOCATION, CS);
            // SET ERR-CRITICAL TO TRUE
            Cobol.move("C", f249_ERR_LEVEL, CS);
            // SET ERR-IMS TO TRUE
            Cobol.move("I", f250_ERR_SUBSYSTEM, CS);
            // MOVE IMS-RETURN-CODE TO ERR-CODE-1
            Cobol.move(f45_IMS_RETURN_CODE, f251_ERR_CODE_1, CS);
            // MOVE 'IMS INSERT DETL FAILED' TO ERR-MESSAGE
            Cobol.move("IMS INSERT DETL FAILED", f253_ERR_MESSAGE, CS);
            // MOVE PA-CARD-NUM TO ERR-EVENT-KEY
            Cobol.move(f275_PA_CARD_NUM, f254_ERR_EVENT_KEY, CS);
            // PERFORM 9500-LOG-ERROR
            perform(39, 39);
        }
        return 34;
    }

    /** 8500-EXIT. */
    private int p34() {
        // EXIT
        return 35;
    }

    /** 9000-TERMINATE. */
    private int p35() {
        // IF IMS-PSB-SCHD
        if (isImsPsbSchd()) {
            // EXEC DLI TERM END-EXEC
            Cobol.move(com.gitgalaxy.modernized.cobolrt.dli.DetDli.terminate(), f375_DIBSTAT, CS);
        }
        // PERFORM 9100-CLOSE-REQUEST-QUEUE THRU 9100-EXIT
        perform(37, 38);
        return 36;
    }

    /** 9000-EXIT. */
    private int p36() {
        // EXIT
        return 37;
    }

    /** 9100-CLOSE-REQUEST-QUEUE. */
    private int p37() {
        // IF WS-REQUEST-MQ-OPEN
        if (isWsRequestMqOpen()) {
            // CALL 'MQCLOSE' USING W01-HCONN-REQUEST W01-HOBJ-REQUEST MQCO-NONE WS-COMPCODE WS-REASON
            com.gitgalaxy.modernized.cobolrt.cics.DetMq.mqclose(task, f47_W01_HCONN_REQUEST, f48_W01_HOBJ_REQUEST, f172_MQCO_NONE, f25_WS_COMPCODE, f26_WS_REASON);
            // IF WS-COMPCODE = MQCC-OK
            if (BigDecimal.valueOf(f139_MQCC_OK).compareTo(Cobol.num(f25_WS_COMPCODE, CS)) == 0) {
                // SET WS-REQUEST-MQ-CLSE TO TRUE
                f60_WS_REQUEST_MQ_FLG = "C";
            } else {
                // MOVE 'M005' TO ERR-LOCATION
                Cobol.move("M005", f248_ERR_LOCATION, CS);
                // SET ERR-WARNING TO TRUE
                Cobol.move("W", f249_ERR_LEVEL, CS);
                // SET ERR-MQ TO TRUE
                Cobol.move("M", f250_ERR_SUBSYSTEM, CS);
                // MOVE WS-COMPCODE TO WS-CODE-DISPLAY
                Cobol.move(f25_WS_COMPCODE, f28_WS_CODE_DISPLAY, CS);
                // MOVE WS-CODE-DISPLAY TO ERR-CODE-1
                Cobol.move(f28_WS_CODE_DISPLAY, f251_ERR_CODE_1, CS);
                // MOVE WS-REASON TO WS-CODE-DISPLAY
                Cobol.move(f26_WS_REASON, f28_WS_CODE_DISPLAY, CS);
                // MOVE WS-CODE-DISPLAY TO ERR-CODE-2
                Cobol.move(f28_WS_CODE_DISPLAY, f252_ERR_CODE_2, CS);
                // MOVE 'FAILED TO CLOSE REQUEST MQ' TO ERR-MESSAGE
                Cobol.move("FAILED TO CLOSE REQUEST MQ", f253_ERR_MESSAGE, CS);
                // PERFORM 9500-LOG-ERROR
                perform(39, 39);
            }
        }
        return 38;
    }

    /** 9100-EXIT. */
    private int p38() {
        // EXIT
        return 39;
    }

    /** 9500-LOG-ERROR. */
    private int p39() {
        // EXEC CICS ASKTIME NOHANDLE ABSTIME(WS-ABS-TIME) END-EXEC
        Cobol.store(f17_WS_ABS_TIME, BigDecimal.valueOf(task.asktime()), false, CS);
        // EXEC CICS FORMATTIME ABSTIME(WS-ABS-TIME) YYMMDD(WS-CUR-DATE-X6) TIME(WS-CUR-TIME-X6) END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f17_WS_ABS_TIME, CS).longValue(), "YYMMDD", ""), f18_WS_CUR_DATE_X6, CS);
        Cobol.move(CicsTask.formatTime(Cobol.num(f17_WS_ABS_TIME, CS).longValue(), ""), f19_WS_CUR_TIME_X6, CS);
        // MOVE WS-CICS-TRANID TO ERR-APPLICATION
        Cobol.move(f3_WS_CICS_TRANID, f246_ERR_APPLICATION, CS);
        // MOVE WS-PGM-AUTH TO ERR-PROGRAM
        Cobol.move(f2_WS_PGM_AUTH, f247_ERR_PROGRAM, CS);
        // MOVE WS-CUR-DATE-X6 TO ERR-DATE
        Cobol.move(f18_WS_CUR_DATE_X6, f244_ERR_DATE, CS);
        // MOVE WS-CUR-TIME-X6 TO ERR-TIME
        Cobol.move(f19_WS_CUR_TIME_X6, f245_ERR_TIME, CS);
        // EXEC CICS WRITEQ TD QUEUE('CSSL') FROM (ERROR-LOG-RECORD) LENGTH (LENGTH OF ERROR-LOG-RECORD) NOHANDLE END-EXEC
        int resp29 = task.writeqTd("CSSL".strip(), Cobol.text(f243_ERROR_LOG_RECORD, CS).substring(0, DetCics.within(f243_ERROR_LOG_RECORD, BigDecimal.valueOf(122).intValue(), "WRITEQ TD")));
        Cobol.store(f369_EIBRESP, BigDecimal.valueOf(resp29), false, CS);
        Cobol.store(f370_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        // IF ERR-CRITICAL
        if (isErrCritical()) {
            // PERFORM 9990-END-ROUTINE
            perform(41, 41);
        }
        return 40;
    }

    /** 9500-EXIT. */
    private int p40() {
        // EXIT
        return 41;
    }

    /** 9990-END-ROUTINE. */
    private int p41() {
        // PERFORM 9000-TERMINATE
        perform(35, 35);
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        return 42;
    }

    /** 9990-EXIT. */
    private int p42() {
        // EXIT
        return 43;
    }

    /** 88 PSB-SCHEDULED-MORE-THAN-ONCE of IMS-RETURN-CODE. */
    private boolean isPsbScheduledMoreThanOnce() { return f45_IMS_RETURN_CODE.equals("TC"); }

    /** 88 STATUS-OK of IMS-RETURN-CODE. */
    private boolean isStatusOk() { return (f45_IMS_RETURN_CODE.equals("  ") || f45_IMS_RETURN_CODE.equals("FW")); }

    /** 88 NO-MORE-MSG-AVAILABLE of WS-MSG-AVAILABLE-FLG. */
    private boolean isNoMoreMsgAvailable() { return f59_WS_MSG_AVAILABLE_FLG.equals("N"); }

    /** 88 WS-LOOP-END of WS-MSG-LOOP-FLG. */
    private boolean isWsLoopEnd() { return f58_WS_MSG_LOOP_FLG.equals("E"); }

    /** 88 CARD-FOUND-XREF of WS-XREF-READ-FLG. */
    private boolean isCardFoundXref() { return f62_WS_XREF_READ_FLG.equals("Y"); }

    /** 88 SEGMENT-NOT-FOUND of IMS-RETURN-CODE. */
    private boolean isSegmentNotFound() { return f45_IMS_RETURN_CODE.equals("GE"); }

    /** 88 FOUND-PAUT-SMRY-SEG of WS-PAUT-SMRY-SEG-FLG. */
    private boolean isFoundPautSmrySeg() { return f65_WS_PAUT_SMRY_SEG_FLG.equals("Y"); }

    /** 88 FOUND-ACCT-IN-MSTR of WS-ACCT-MASTER-READ-FLG. */
    private boolean isFoundAcctInMstr() { return f63_WS_ACCT_MASTER_READ_FLG.equals("Y"); }

    /** 88 DECLINE-AUTH of WS-DECLINE-FLG. */
    private boolean isDeclineAuth() { return f66_WS_DECLINE_FLG.equals("D"); }

    /** 88 AUTH-RESP-DECLINED of WS-AUTH-RESP-FLG. */
    private boolean isAuthRespDeclined() { return f57_WS_AUTH_RESP_FLG.equals("D"); }

    /** 88 CARD-NFOUND-XREF of WS-XREF-READ-FLG. */
    private boolean isCardNfoundXref() { return f62_WS_XREF_READ_FLG.equals("N"); }

    /** 88 NFOUND-ACCT-IN-MSTR of WS-ACCT-MASTER-READ-FLG. */
    private boolean isNfoundAcctInMstr() { return f63_WS_ACCT_MASTER_READ_FLG.equals("N"); }

    /** 88 NFOUND-CUST-IN-MSTR of WS-CUST-MASTER-READ-FLG. */
    private boolean isNfoundCustInMstr() { return f64_WS_CUST_MASTER_READ_FLG.equals("N"); }

    /** 88 INSUFFICIENT-FUND of WS-DECLINE-REASON-FLG. */
    private boolean isInsufficientFund() { return f67_WS_DECLINE_REASON_FLG.equals("I"); }

    /** 88 CARD-NOT-ACTIVE of WS-DECLINE-REASON-FLG. */
    private boolean isCardNotActive() { return f67_WS_DECLINE_REASON_FLG.equals("A"); }

    /** 88 ACCOUNT-CLOSED of WS-DECLINE-REASON-FLG. */
    private boolean isAccountClosed() { return f67_WS_DECLINE_REASON_FLG.equals("C"); }

    /** 88 CARD-FRAUD of WS-DECLINE-REASON-FLG. */
    private boolean isCardFraud() { return f67_WS_DECLINE_REASON_FLG.equals("F"); }

    /** 88 MERCHANT-FRAUD of WS-DECLINE-REASON-FLG. */
    private boolean isMerchantFraud() { return f67_WS_DECLINE_REASON_FLG.equals("M"); }

    /** 88 NFOUND-PAUT-SMRY-SEG of WS-PAUT-SMRY-SEG-FLG. */
    private boolean isNfoundPautSmrySeg() { return f65_WS_PAUT_SMRY_SEG_FLG.equals("N"); }

    /** 88 AUTH-RESP-APPROVED of WS-AUTH-RESP-FLG. */
    private boolean isAuthRespApproved() { return f57_WS_AUTH_RESP_FLG.equals("A"); }

    /** 88 IMS-PSB-SCHD of WS-IMS-PSB-SCHD-FLG. */
    private boolean isImsPsbSchd() { return f46_WS_IMS_PSB_SCHD_FLG.equals("Y"); }

    /** 88 WS-REQUEST-MQ-OPEN of WS-REQUEST-MQ-FLG. */
    private boolean isWsRequestMqOpen() { return f60_WS_REQUEST_MQ_FLG.equals("O"); }

    /** 88 ERR-CRITICAL of ERR-LEVEL. */
    private boolean isErrCritical() { return Cobol.compare(f249_ERR_LEVEL, "C", CS) == 0; }

}
