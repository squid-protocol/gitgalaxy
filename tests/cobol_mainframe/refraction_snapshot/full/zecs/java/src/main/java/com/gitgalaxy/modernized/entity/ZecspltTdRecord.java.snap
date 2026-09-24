package com.gitgalaxy.modernized.entity;

import lombok.Data;
import lombok.NoArgsConstructor;
import jakarta.persistence.*;
import java.math.BigDecimal;

@Data
@NoArgsConstructor
@Entity
@Table(name = "TD_RECORD")
public class ZecspltTdRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "sys_id")
    private Long sysId;

    @Column(name = "EOF")
    private String eof;

    @Column(name = "ZC")
    private String zc;

    @Column(name = "URI_PREFIX")
    private String uriPrefix;

    @Column(name = "URI_SUFFIX")
    private String uriSuffix;

    @Column(name = "URI_TRAN")
    private String uriTran;

    @Column(name = "ZX_SUFFIX")
    private String zxSuffix;

    @Column(name = "CSSL")
    private String cssl;

    @Column(name = "TD_LENGTH")
    private Integer tdLength;

    @Column(name = "TD_SUFFIX")
    private String tdSuffix;

    @Column(name = "TD_TRAN")
    private String tdTran;

    @Column(name = "TD_PATH")
    private String tdPath;

    @Column(name = "URI_PATH")
    private String uriPath;

}