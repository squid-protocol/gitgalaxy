package com.gitgalaxy.modernized.entity;

import lombok.Data;
import lombok.NoArgsConstructor;
import jakarta.persistence.*;
import java.math.BigDecimal;

@Data
@NoArgsConstructor
@Entity
@Table(name = "WS_INPUT_REC")
public class CobtupdtWsInputRec {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "sys_id")
    private Long sysId;

    @Column(name = "LASTREC")
    private String lastrec;

    @Column(name = "WS_RETURN_MSG")
    private String wsReturnMsg;

    @Column(name = "WS_VAR_SQLCODE")
    private Integer wsVarSqlcode;

    @Column(name = "INPUT_REC_TYPE")
    private String inputRecType;

    @Column(name = "INPUT_REC_NUMBER")
    private String inputRecNumber;

    @Column(name = "INPUT_REC_DESC")
    private String inputRecDesc;

}