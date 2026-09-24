package com.gitgalaxy.modernized.entity;

import lombok.Data;
import lombok.NoArgsConstructor;
import jakarta.persistence.*;
import java.math.BigDecimal;

@Data
@NoArgsConstructor
@Entity
@Table(name = "WS_ERROR_RECORD")
public class CbimportWsErrorRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "sys_id")
    private Long sysId;

    @Column(name = "ERROR_OUTPUT_RECORD")
    private String errorOutputRecord;

    @Column(name = "WS_EXPORT_STATUS")
    private String wsExportStatus;

    @Column(name = "WS_CUSTOMER_STATUS")
    private String wsCustomerStatus;

    @Column(name = "WS_ACCOUNT_STATUS")
    private String wsAccountStatus;

    @Column(name = "WS_XREF_STATUS")
    private String wsXrefStatus;

    @Column(name = "WS_TRANSACTION_STATUS")
    private String wsTransactionStatus;

    @Column(name = "WS_CARD_STATUS")
    private String wsCardStatus;

    @Column(name = "WS_ERROR_STATUS")
    private String wsErrorStatus;

    @Column(name = "WS_IMPORT_DATE")
    private String wsImportDate;

    @Column(name = "WS_IMPORT_TIME")
    private String wsImportTime;

    @Column(name = "WS_TOTAL_RECORDS_READ")
    private Integer wsTotalRecordsRead;

    @Column(name = "WS_CUSTOMER_RECORDS_IMPORTED")
    private Integer wsCustomerRecordsImported;

    @Column(name = "WS_ACCOUNT_RECORDS_IMPORTED")
    private Integer wsAccountRecordsImported;

    @Column(name = "WS_XREF_RECORDS_IMPORTED")
    private Integer wsXrefRecordsImported;

    @Column(name = "WS_TRAN_RECORDS_IMPORTED")
    private Integer wsTranRecordsImported;

    @Column(name = "WS_CARD_RECORDS_IMPORTED")
    private Integer wsCardRecordsImported;

    @Column(name = "WS_ERROR_RECORDS_WRITTEN")
    private Integer wsErrorRecordsWritten;

    @Column(name = "WS_UNKNOWN_RECORD_TYPE_COUNT")
    private Integer wsUnknownRecordTypeCount;

    @Column(name = "ERR_TIMESTAMP")
    private String errTimestamp;

    @Column(name = "ERR_RECORD_TYPE")
    private String errRecordType;

    @Column(name = "ERR_SEQUENCE")
    private Integer errSequence;

    @Column(name = "ERR_MESSAGE")
    private String errMessage;

}