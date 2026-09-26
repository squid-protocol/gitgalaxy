/*
 * A hand translation of COACTVWC (app/cbl/COACTVWC.cbl) from
 * https://github.com/aws-samples/aws-mainframe-modernization-carddemo at commit
 * 59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e, onto the Java GitGalaxy generates from it. That source is
 * Copyright Amazon.com, Inc. or its affiliates and licensed Apache-2.0; this file is derived from it
 * and modified (translated), under the same licence -- see LICENSE and NOTICE in this case's directory.
 */
package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.MainframeClock;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.CoactvwcCommarea;
import com.gitgalaxy.modernized.dto.screen.CactvwaScreen;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import com.gitgalaxy.modernized.entity.vsam.AccountRecord;
import com.gitgalaxy.modernized.entity.vsam.CardXrefRecord;
import com.gitgalaxy.modernized.entity.vsam.CustomerRecord;
import com.gitgalaxy.modernized.exception.*;
import com.gitgalaxy.modernized.repository.vsam.AccountRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.CardXrefRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.CustomerRecordRepository;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * READ at line 727 tests NORMAL,NOTFND
 * READ at line 776 tests NORMAL,NOTFND
 * READ at line 826 tests NORMAL,NOTFND
 * TODO: the RESP of SEND at line 583 (paragraph 1400-SEND-SCREEN) is never tested
 * TODO: the RESP of RECEIVE at line 611 (paragraph 2100-RECEIVE-MAP) is never tested
 * TODO: the RESP of SEND at line 924 (paragraph ABEND-ROUTINE) is never tested
 * Screens (#3619): CactvwaScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class CoactvwcService {

    private static final Logger log = LoggerFactory.getLogger(CoactvwcService.class);

    private final ObjectProvider<Comen01cService> comen01cService;
    private final AccountRecordRepository accountRecordRepository;
    private final CardXrefRecordRepository cardXrefRecordRepository;
    private final CustomerRecordRepository customerRecordRepository;
    private final MainframeClock mainframeClock;

    public void executeCoactvwc(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for COACTVWC");
        // TODO: [AI AGENT] Implement extracted business rules here.
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public CoactvwcCommarea handleTransaction(String transid, CoactvwcCommarea request) {
        log.info("Coactvwc: handleTransaction");
        return request;
    }

    /**
     * COACTVWC's PROCEDURE DIVISION as one task (#3754): 0000-MAIN and the paragraphs it PERFORMs, each block
     * named after its paragraph. The program's own defects are kept (see DEFECT), since the port is proven by
     * comparing its outputs with the original's.
     */
    public void runTask(CicsTask task) {
        // 0000-MAIN: EXEC CICS HANDLE ABEND LABEL(ABEND-ROUTINE) -- no abend path is driven.
        Work w = new Work();
        CarddemoCommarea ca = blankCommarea();
        String thisFromProgram = "";
        String thisFromTranid = "";
        // DEFECT: CDEMO-FROM-PROGRAM is tested before DFHCOMMAREA is moved into CARDDEMO-COMMAREA, so on any
        // call with a COMMAREA the test reads working storage that holds no caller's data, never equals
        // 'COMEN01C', and the ELSE branch always runs. Fix: move DFHCOMMAREA first, then test.
        if (task.hasCommarea()) {
            CoactvwcCommarea in = task.commarea(CoactvwcCommarea.class);
            if (in.getCarddemoCommarea() != null) {
                ca = copy(in.getCarddemoCommarea());
            }
            if (in.getWsThisProgcommarea() != null) {
                thisFromProgram = nz(in.getWsThisProgcommarea().getCaFromProgram());
                thisFromTranid = nz(in.getWsThisProgcommarea().getCaFromTranid());
            }
        }
        // YYYY-STORE-PFKEY (CSSTRPFY): PF15 is PF3 on a 24-key keyboard; only ENTER and PF3 are valid here.
        String aid = task.aid();
        boolean pf3 = "PF3".equals(aid) || "PF15".equals(aid);
        if (pf3) {
            ca.setCdemoToTranid(isBlank(ca.getCdemoFromTranid()) ? "CM00" : ca.getCdemoFromTranid());
            ca.setCdemoToProgram(isBlank(ca.getCdemoFromProgram()) ? "COMEN01C" : ca.getCdemoFromProgram());
            ca.setCdemoFromTranid("CAVW");
            ca.setCdemoFromProgram("COACTVWC");
            ca.setCdemoUserType("U");
            ca.setCdemoPgmContext(0);
            ca.setCdemoLastMapset("COACTVW");
            ca.setCdemoLastMap("CACTVWA");
            task.xctl(ca.getCdemoToProgram().trim(), ca);
            return;
        }
        int context = ca.getCdemoPgmContext() == null ? 0 : ca.getCdemoPgmContext();
        if (context == 0) { // CDEMO-PGM-ENTER
            sendMap(task, ca, w);
        } else if (context == 1) { // CDEMO-PGM-REENTER
            processInputs(task, ca, w); // 2000-PROCESS-INPUTS
            if (!w.inputError) {
                readAcct(ca, w); // 9000-READ-ACCT
            }
            sendMap(task, ca, w);
        } else {
            // WHEN OTHER: SEND-PLAIN-TEXT, which ends the task with a plain RETURN.
            task.sendText(fit("UNEXPECTED DATA SCENARIO", 75));
            task.returnTransid(null, null);
            return;
        }
        // COMMON-RETURN: RETURN TRANSID(CAVW) COMMAREA(CARDDEMO-COMMAREA + WS-THIS-PROGCOMMAREA).
        CoactvwcCommarea out = new CoactvwcCommarea();
        out.setCarddemoCommarea(ca);
        var mine = new com.gitgalaxy.modernized.dto.contract.CoactvwcWsThisProgcommarea();
        mine.setCaFromProgram(thisFromProgram);
        mine.setCaFromTranid(thisFromTranid);
        out.setWsThisProgcommarea(mine);
        task.returnTransid("CAVW", out);
    }

    /** CC-WORK-AREA / WS-MISC-STORAGE: the flags and messages 0000-MAIN INITIALIZEs. */
    private static final class Work {
        boolean inputError;
        char acctFilter = ' '; // FLG-ACCTFILTER: ' ' blank, '0' not ok, '1' valid
        String ccAcctId = "";
        String returnMsg = ""; // WS-RETURN-MSG, X(75); '' is WS-RETURN-MSG-OFF
        boolean foundAcct;
        boolean foundCust;
        AccountRecord acct;
        CustomerRecord cust;
    }

    // 2000-PROCESS-INPUTS: 2100-RECEIVE-MAP, 2200-EDIT-MAP-INPUTS (and 2210-EDIT-ACCOUNT).
    private void processInputs(CicsTask task, CarddemoCommarea ca, Work w) {
        String typed = task.receive("CACTVWA", CactvwaScreen.class).map(CactvwaScreen::getAcctsid).orElse("");
        typed = typed == null ? "" : typed;
        w.inputError = false;
        w.acctFilter = '1';
        w.ccAcctId = "*".equals(typed.trim()) || typed.isBlank() ? "" : fit(typed, 11);
        // 2210-EDIT-ACCOUNT
        w.acctFilter = '0';
        if (w.ccAcctId.isBlank()) {
            w.inputError = true;
            w.acctFilter = ' ';
            if (w.returnMsg.isEmpty()) {
                w.returnMsg = "Account number not provided";
            }
            ca.setCdemoAcctId(0L);
        } else if (!w.ccAcctId.matches("[0-9]{11}") || Long.parseLong(w.ccAcctId) == 0) {
            w.inputError = true;
            w.acctFilter = '0';
            if (w.returnMsg.isEmpty()) {
                w.returnMsg = "Account Filter must  be a non-zero 11 digit number";
            }
            ca.setCdemoAcctId(0L);
        } else {
            ca.setCdemoAcctId(Long.parseLong(w.ccAcctId));
            w.acctFilter = '1';
        }
        if (w.acctFilter == ' ') { // SET NO-SEARCH-CRITERIA-RECEIVED
            w.returnMsg = "No input received";
        }
    }

    // 9000-READ-ACCT: 9200-GETCARDXREF-BYACCT, 9300-GETACCTDATA-BYACCT, 9400-GETCUSTDATA-BYCUST.
    private void readAcct(CarddemoCommarea ca, Work w) {
        String acctKey = String.format("%011d", ca.getCdemoAcctId());
        List<CardXrefRecord> xref = readCxacaix(ca.getCdemoAcctId());
        if (xref.isEmpty()) {
            w.inputError = true;
            w.acctFilter = '0';
            if (w.returnMsg.isEmpty()) {
                w.returnMsg = fit("Account:" + acctKey + " not found in Cross ref file.  Resp:" + resp(13)
                        + " Reas:" + resp(0), 75);
            }
            return;
        }
        CardXrefRecord x = xref.get(0);
        ca.setCdemoCustId(x.getXrefCustId());
        ca.setCdemoCardNum(Long.parseLong(x.getXrefCardNum().trim()));
        Optional<AccountRecord> acct = readAcctdat(ca.getCdemoAcctId());
        if (acct.isPresent()) {
            w.foundAcct = true;
            w.acct = acct.get();
        } else {
            w.inputError = true;
            w.acctFilter = '0';
            if (w.returnMsg.isEmpty()) {
                w.returnMsg = fit("Account:" + acctKey + " not found in Acct Master file.Resp:" + resp(13)
                        + " Reas:" + resp(0), 75);
            }
        }
        // DEFECT: 9000-READ-ACCT tests DID-NOT-FIND-ACCT-IN-ACCTDAT, an 88 on WS-RETURN-MSG that the message
        // above never equals, so a missing account still goes on to read the customer. Fix: test the flag.
        Optional<CustomerRecord> cust = readCustdat(ca.getCdemoCustId());
        if (cust.isPresent()) {
            w.foundCust = true;
            w.cust = cust.get();
        } else {
            w.inputError = true;
            if (w.returnMsg.isEmpty()) {
                w.returnMsg = fit("CustId:" + String.format("%09d", ca.getCdemoCustId())
                        + " not found in customer master.Resp: " + resp(13) + " REAS:" + resp(0), 75);
            }
        }
    }

    // 1000-SEND-MAP: 1100-SCREEN-INIT, 1200-SETUP-SCREEN-VARS, 1300-SETUP-SCREEN-ATTRS, 1400-SEND-SCREEN.
    private void sendMap(CicsTask task, CarddemoCommarea ca, Work w) {
        CactvwaScreen s = new CactvwaScreen();
        LocalDateTime now = mainframeClock.now();
        s.setTitle01("      AWS Mainframe Modernization       ");
        s.setTitle02("              CardDemo                  ");
        s.setTrnname("CAVW");
        s.setPgmname("COACTVWC");
        s.setCurdate(String.format("%02d/%02d/%02d", now.getMonthValue(), now.getDayOfMonth(), now.getYear() % 100));
        s.setCurtime(String.format("%02d:%02d:%02d", now.getHour(), now.getMinute(), now.getSecond()));
        // 1200-SETUP-SCREEN-VARS (EIBCALEN = 0 only prompts)
        if (task.hasCommarea()) {
            s.setAcctsid(w.acctFilter == ' ' ? "" : w.ccAcctId);
            if (w.foundAcct || w.foundCust) {
                AccountRecord a = w.acct == null ? new AccountRecord() : w.acct;
                s.setAcsttus(nz(a.getAcctActiveStatus()));
                s.setAcurbal(edited(a.getAcctCurrBal()));
                s.setAcrdlim(edited(a.getAcctCreditLimit()));
                s.setAcshlim(edited(a.getAcctCashCreditLimit()));
                s.setAcrcycr(edited(a.getAcctCurrCycCredit()));
                s.setAcrcydb(edited(a.getAcctCurrCycDebit()));
                s.setAdtopen(nz(a.getAcctOpenDate()));
                s.setAexpdt(nz(a.getAcctExpiraionDate()));
                s.setAreisdt(nz(a.getAcctReissueDate()));
                s.setAaddgrp(nz(a.getAcctGroupId()));
            }
            if (w.foundCust) {
                CustomerRecord c = w.cust;
                String ssn = String.format("%09d", c.getCustSsn() == null ? 0 : c.getCustSsn());
                s.setAcstnum(String.format("%09d", c.getCustId()));
                s.setAcstssn(ssn.substring(0, 3) + "-" + ssn.substring(3, 5) + "-" + ssn.substring(5, 9));
                s.setAcstfco(String.format("%03d", c.getCustFicoCreditScore() == null ? 0 : c.getCustFicoCreditScore()));
                s.setAcstdob(fit(nz(c.getCustDobYyyyMmDd()), 10));
                s.setAcsfnam(fit(nz(c.getCustFirstName()), 25));
                s.setAcsmnam(fit(nz(c.getCustMiddleName()), 25));
                s.setAcslnam(fit(nz(c.getCustLastName()), 25));
                s.setAcsadl1(fit(nz(c.getCustAddrLine1()), 50));
                s.setAcsadl2(fit(nz(c.getCustAddrLine2()), 50));
                s.setAcscity(fit(nz(c.getCustAddrLine3()), 50));
                s.setAcsstte(fit(nz(c.getCustAddrStateCd()), 2));
                s.setAcszipc(fit(nz(c.getCustAddrZip()), 5));
                s.setAcsctry(fit(nz(c.getCustAddrCountryCd()), 3));
                s.setAcsphn1(fit(nz(c.getCustPhoneNum1()), 13));
                s.setAcsphn2(fit(nz(c.getCustPhoneNum2()), 13));
                s.setAcsgovt(fit(nz(c.getCustGovtIssuedId()), 20));
                s.setAcseftc(fit(nz(c.getCustEftAccountId()), 10));
                s.setAcspflg(fit(nz(c.getCustPriCardHolderInd()), 1));
            }
        }
        // WS-INFO-MSG is only ever blank (9000-READ-ACCT sets WS-NO-INFO-MESSAGE), so the prompt always shows.
        s.setInfomsg("Enter or update id of account to display");
        s.setErrmsg(w.returnMsg);
        // 1300-SETUP-SCREEN-ATTRS: a blank filter on re-entry shows '*' (the colours are attributes).
        if (w.acctFilter == ' ' && ca.getCdemoPgmContext() != null && ca.getCdemoPgmContext() == 1) {
            s.setAcctsid("*");
        }
        // 1400-SEND-SCREEN
        ca.setCdemoPgmContext(1); // SET CDEMO-PGM-REENTER
        task.sendMap("CACTVWA", s);
    }

    /** PIC +ZZZ,ZZZ,ZZZ.99: a sign, nine integer digits with leading zeros (and their commas) blanked, cents. */
    static String edited(BigDecimal v) {
        BigDecimal d = v == null ? BigDecimal.ZERO : v.setScale(2, RoundingMode.DOWN);
        String digits = String.format("%011d", d.abs().movePointRight(2).longValueExact() % 100_000_000_000L);
        String whole = digits.substring(0, 9);
        StringBuilder out = new StringBuilder(d.signum() < 0 ? "-" : "+");
        boolean leading = true;
        for (int i = 0; i < 9; i++) {
            if (i == 3 || i == 6) {
                out.append(leading ? ' ' : ',');
            }
            leading &= whole.charAt(i) == '0';
            out.append(leading ? ' ' : whole.charAt(i));
        }
        return out.append('.').append(digits, 9, 11).toString();
    }

    /** MOVE of a DFHRESP code (PIC S9(9) COMP) to ERROR-RESP (PIC X(10)): nine digits, then a space. */
    private static String resp(int code) {
        return String.format("%09d ", code);
    }

    private static String fit(String s, int n) {
        return s.length() > n ? s.substring(0, n) : s;
    }

    private static String nz(String s) {
        return s == null ? "" : s;
    }

    private static boolean isBlank(String s) {
        return s == null || s.isBlank() || s.chars().allMatch(c -> c == 0);
    }

    private static CarddemoCommarea blankCommarea() {
        CarddemoCommarea c = new CarddemoCommarea();
        c.setCdemoPgmContext(0);
        c.setCdemoCustId(0);
        c.setCdemoAcctId(0L);
        c.setCdemoCardNum(0L);
        return c;
    }

    private static CarddemoCommarea copy(CarddemoCommarea in) {
        CarddemoCommarea c = new CarddemoCommarea();
        c.setCdemoFromTranid(in.getCdemoFromTranid());
        c.setCdemoFromProgram(in.getCdemoFromProgram());
        c.setCdemoToTranid(in.getCdemoToTranid());
        c.setCdemoToProgram(in.getCdemoToProgram());
        c.setCdemoUserId(in.getCdemoUserId());
        c.setCdemoUserType(in.getCdemoUserType());
        c.setCdemoPgmContext(in.getCdemoPgmContext());
        c.setCdemoCustId(in.getCdemoCustId());
        c.setCdemoCustFname(in.getCdemoCustFname());
        c.setCdemoCustMname(in.getCdemoCustMname());
        c.setCdemoCustLname(in.getCdemoCustLname());
        c.setCdemoAcctId(in.getCdemoAcctId());
        c.setCdemoAcctStatus(in.getCdemoAcctStatus());
        c.setCdemoCardNum(in.getCdemoCardNum());
        c.setCdemoLastMap(in.getCdemoLastMap());
        c.setCdemoLastMapset(in.getCdemoLastMapset());
        return c;
    }

    /** Another program LINKed / XCTLed to this one. TODO: [AI AGENT] implement from the program's business rules. */
    public CoactvwcCommarea handleLink(CoactvwcCommarea request) {
        log.info("Coactvwc: handleLink");
        return request;
    }

    /** XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COACTVWC.cbl:349: the target is data-driven. Candidates: COMEN01C (moves).
     *  Also MOVEd from CDEMO-FROM-PROGRAM, whose content is not known statically: those names reach the default branch.
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCdemoToProgramL349(String program, Object request) {
        switch (program.trim().toUpperCase()) {
            case "COMEN01C":
                return comen01cService.getObject().handleLink((CarddemoCommarea) request);
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COACTVWC.cbl:349: no known target " + program);
        }
    }

    /** AWS.M2.CARDDEMO.ACCTDATA.VSAM.KSDS as CICS file ACCTDAT at app/cbl/COACTVWC.cbl:776; VSAM defines field testing: open (3 public / 0 private estates). */
    public Optional<AccountRecord> readAcctdat(Long key) {
        return accountRecordRepository.findById(key);
    }

    /** AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS as CICS file CXACAIX at app/cbl/COACTVWC.cbl:727; VSAM defines field testing: open (3 public / 0 private estates). */
    public List<CardXrefRecord> readCxacaix(Long xrefAcctId) {
        return cardXrefRecordRepository.findByXrefAcctId(xrefAcctId);
    }

    /** AWS.M2.CARDDEMO.CUSTDATA.VSAM.KSDS as CICS file CUSTDAT at app/cbl/COACTVWC.cbl:826; VSAM defines field testing: open (3 public / 0 private estates). */
    public Optional<CustomerRecord> readCustdat(Integer key) {
        return customerRecordRepository.findById(key);
    }

    /**
     * EXEC CICS HANDLE ABEND at app/cbl/COACTVWC.cbl:264 (paragraph 0000-MAIN) routes abends to ABEND-ROUTINE.
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     */
    public void onAbendL264(CicsAbendException e) {
        log.info("HANDLE ABEND LABEL ABEND-ROUTINE at line 264", e);
        // TODO: port paragraph ABEND-ROUTINE's logic
    }

    /**
     * EXEC CICS HANDLE ABEND at app/cbl/COACTVWC.cbl:930 (paragraph ABEND-ROUTINE) routes abends to None.
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     */
    public void onAbendL930(CicsAbendException e) {
        log.info("HANDLE ABEND LABEL None at line 930", e);
        // TODO: port paragraph None's logic
    }

    /**
     * EXEC CICS ABEND ABCODE(9999) at app/cbl/COACTVWC.cbl:934 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendLegacy9999L934() {
        throw new CicsAbendException("9999", "COACTVWC", "app/cbl/COACTVWC.cbl:934");
    }

    /** SEND MAP(CACTVWA) MAPSET(COACTVW) FROM(CACTVWAO) at app/cbl/COACTVWC.cbl:583 (#3619).
     *  TODO: port the logic that fills CACTVWAO before the SEND.
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public CactvwaScreen renderCactvwa(CactvwaScreen screen) {
        return screen;
    }

    /** RECEIVE MAP(CACTVWA) MAPSET(COACTVW) INTO(CACTVWAI) at app/cbl/COACTVWC.cbl:611 (#3619).
     *  `aid` is the key the user pressed (EIBAID): ENTER, PF1-PF24, CLEAR, PA1-PA3.
     *  TODO: port the logic that reads CACTVWAI after the RECEIVE, and return the screen to show next.
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public ScreenModel submitCactvwa(CactvwaScreen input, String aid) {
        return renderCactvwa(input);
    }

}