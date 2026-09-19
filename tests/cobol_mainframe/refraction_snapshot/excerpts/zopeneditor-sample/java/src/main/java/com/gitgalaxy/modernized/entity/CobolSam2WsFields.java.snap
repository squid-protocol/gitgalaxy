package com.gitgalaxy.modernized.entity;

import lombok.Data;
import lombok.NoArgsConstructor;
import jakarta.persistence.*;
import java.math.BigDecimal;

@Data
@NoArgsConstructor
@Entity
@Table(name = "WS_FIELDS")
public class CobolSam2WsFields {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "sys_id")
    private Long sysId;

    @Column(name = "WS_UPDATE_NUM")
    private BigDecimal wsUpdateNum;

    @Column(name = "WS_UPDATE_NUM_NEG")
    private String wsUpdateNumNeg;

    @Column(name = "TRAN_COUNT")
    private Integer tranCount;

    @Column(name = "LOOP_COUNT")
    private Integer loopCount;

    @Column(name = "WORK_SUM")
    private Integer workSum;

    @Column(name = "MONTH_AVERAGE")
    private Integer monthAverage;

    @Column(name = "MONTH_SUB")
    private Integer monthSub;

    @Column(name = "TRAN_OK")
    private String tranOk;

    @Column(name = "TRAN_MSG")
    private String tranMsg;

}