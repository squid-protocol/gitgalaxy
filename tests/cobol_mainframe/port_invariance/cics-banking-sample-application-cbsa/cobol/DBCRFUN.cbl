       PROCESS CICS,NODYNAM,NSYMBOL(NATIONAL),TRUNC(STD)
       CBL CICS('SP,EDF')
       CBL SQL
      ******************************************************************
      *                                                                *
      *  Copyright IBM Corp. 2023                                      *
      *                                                                *
      ******************************************************************
      ******************************************************************
      * This program will get called when someone pays some cash in to
      * the bank over the counter or takes out some cash out over the
      * counter.
      *
      * This program takes an account number and amount, it then
      * accesses the DB2 datastore and retrieves the associated
      * Account record and applies the amount and returns the
      * updated actual amount and the available balance from the Account
      * datastore.
      *
      * If the update is successfully applied to the Account then a
      * record is written to the PROCTRAN (Processed Transaction)
      * datastore.
      *
      * If the transaction cannot be successfullty applied to the
      * Account datastore, because the account no longer exists
      * (for example) then the SUCCESS flag is set to 'N' and a fail
      * code gets written to the return data, for the calling routine
      * to handle.
      *
      ******************************************************************

       IDENTIFICATION DIVISION.
       PROGRAM-ID. DBCRFUN.
       AUTHOR. Jon Collett.

       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
      *SOURCE-COMPUTER.   IBM-370 WITH DEBUGGING MODE.
       SOURCE-COMPUTER.  IBM-370.
       OBJECT-COMPUTER.  IBM-370.

       INPUT-OUTPUT SECTION.


       DATA DIVISION.
       WORKING-STORAGE SECTION.

       COPY SORTCODE.



       77 SYSIDERR-RETRY                PIC 999.

      * Get the ACCOUNT DB2 copybook
           EXEC SQL
              INCLUDE ACCDB2
           END-EXEC.

      * ACCOUNT Host variables for DB2
       01 HOST-ACCOUNT-ROW.
          03 HV-ACCOUNT-EYECATCHER      PIC X(4).
          03 HV-ACCOUNT-CUST-NO         PIC X(10).
          03 HV-ACCOUNT-KEY.
             05 HV-ACCOUNT-SORTCODE     PIC X(6).
             05 HV-ACCOUNT-ACC-NO       PIC X(8).
          03 HV-ACCOUNT-ACC-TYPE        PIC X(8).
          03 HV-ACCOUNT-INT-RATE        PIC S9(4)V99 COMP-3.
          03 HV-ACCOUNT-OPENED          PIC X(10).
          03 HV-ACCOUNT-OVERDRAFT-LIM   PIC S9(9) COMP.
          03 HV-ACCOUNT-LAST-STMT       PIC X(10).
          03 HV-ACCOUNT-NEXT-STMT       PIC X(10).
          03 HV-ACCOUNT-AVAIL-BAL       PIC S9(10)V99 COMP-3.
          03 HV-ACCOUNT-ACTUAL-BAL      PIC S9(10)V99 COMP-3.

      * PROCTRAN DB2 copybook
          EXEC SQL
             INCLUDE PROCDB2
          END-EXEC.

      * PROCTRAN host variables for DB2
       01 HOST-PROCTRAN-ROW.
          03 HV-PROCTRAN-EYECATCHER     PIC X(4).
          03 HV-PROCTRAN-SORT-CODE      PIC X(6).
          03 HV-PROCTRAN-ACC-NUMBER     PIC X(8).
          03 HV-PROCTRAN-DATE           PIC X(10).
          03 HV-PROCTRAN-TIME           PIC X(6).
          03 HV-PROCTRAN-REF            PIC X(12).
          03 HV-PROCTRAN-TYPE           PIC X(3).
          03 HV-PROCTRAN-DESC           PIC X(40).
          03 HV-PROCTRAN-AMOUNT         PIC S9(10)V99 COMP-3.

      * Pull in the SQL COMMAREA
        EXEC SQL
          INCLUDE SQLCA
        END-EXEC.

       01 WS-CICS-WORK-AREA.
          05 WS-CICS-RESP               PIC S9(8) COMP.
          05 WS-CICS-RESP2              PIC S9(8) COMP.


       LOCAL-STORAGE SECTION.
       01 FILE-RETRY                    PIC 999.
       01 WS-EXIT-RETRY-LOOP            PIC X         VALUE ' '.

       01 DB2-DATE-REFORMAT.
          03 DB2-DATE-REF-YR            PIC 9(4).
          03 FILLER                     PIC X.
          03 DB2-DATE-REF-MNTH          PIC 99.
          03 FILLER                     PIC X.
          03 DB2-DATE-REF-DAY           PIC 99.

       01 DATA-STORE-TYPE               PIC X.
          88 DATASTORE-TYPE-DLI                       VALUE '1'.
          88 DATASTORE-TYPE-DB2                       VALUE '2'.
          88 DATASTORE-TYPE-VSAM                      VALUE 'V'.

       01 WS-ACC-DATA.
          COPY ACCOUNT.

       01 WS-EIBTASKN12                 PIC 9(12)     VALUE 0.
       01 WS-SQLCODE-DISP               PIC 9(9)      VALUE 0.

       01 DESIRED-ACC-KEY.
          03 DESIRED-SORT-CODE          PIC 9(6).
          03 DESIRED-ACC-NO             PIC 9(8).

       01 NEW-ACCOUNT-AVAILABLE-BALANCE PIC S9(10)V99 VALUE 0.
       01 NEW-ACCOUNT-ACTUAL-BALANCE    PIC S9(10)V99 VALUE 0.
       01 WS-ACC-REC-LEN                PIC S9(4) COMP
                                                      VALUE 0.

       01 WS-U-TIME                     PIC S9(15) COMP-3.
       01 WS-ORIG-DATE                  PIC X(10).
       01 WS-ORIG-DATE-GRP REDEFINES WS-ORIG-DATE.
          03 WS-ORIG-DATE-DD            PIC 99.
          03 FILLER                     PIC X.
          03 WS-ORIG-DATE-MM            PIC 99.
          03 FILLER                     PIC X.
          03 WS-ORIG-DATE-YYYY          PIC 9999.

       01 WS-ORIG-DATE-GRP-X.
          03 WS-ORIG-DATE-DD-X          PIC XX.
          03 FILLER                     PIC X         VALUE '.'.
          03 WS-ORIG-DATE-MM-X          PIC XX.
          03 FILLER                     PIC X         VALUE '.'.
          03 WS-ORIG-DATE-YYYY-X        PIC X(4).

       01 PROCTRAN-AREA.
          COPY PROCTRAN.

       01 WS-PASSED-DATA.
          02 WS-TEST-KEY                PIC X(4).
          02 WS-SORT-CODE               PIC 9(6).
          02 WS-CUSTOMER-RANGE.
             07 WS-CUSTOMER-RANGE-TOP   PIC X.
             07 WS-CUSTOMER-RANGE-MIDDLE
                                        PIC X.
             07 WS-CUSTOMER-RANGE-BOTTOM
                                        PIC X.

      * 01 CUSTOMER-KY.
      *    03 REQUIRED-SORT-CODE         PIC 9(6)      VALUE 0.
      *    03 REQUIRED-ACC-NUM           PIC 9(8)      VALUE 0.

       01 PROCTRAN-RIDFLD               PIC S9(8) COMP.

       01 SQLCODE-DISPLAY               PIC S9(8) DISPLAY
             SIGN LEADING SEPARATE.

       01 MY-ABEND-CODE                 PIC XXXX.

       01 WS-STORM-DRAIN                PIC X         VALUE 'N'.
       01 STORM-DRAIN-CONDITION         PIC X(20).

       01 NUMERIC-AMOUNT-DISPLAY        PIC +9(10).99.

       01 WS-TIME-DATA.
          03 WS-TIME-NOW                PIC 9(6).
          03 WS-TIME-NOW-GRP REDEFINES WS-TIME-NOW.
             05 WS-TIME-NOW-GRP-HH      PIC 99.
             05 WS-TIME-NOW-GRP-MM      PIC 99.
             05 WS-TIME-NOW-GRP-SS      PIC 99.

       01 WS-ABEND-PGM                  PIC X(8)      VALUE 'ABNDPROC'.

       01 ABNDINFO-REC.
           COPY ABNDINFO.

       01 WS-SUFFICIENT-FUNDS           PIC X VALUE 'N'.
       01 WS-DIFFERENCE                 PIC S9(10)V99.

       LINKAGE SECTION.
       01 DFHCOMMAREA.
          COPY PAYDBCR.


       PROCEDURE DIVISION USING DFHCOMMAREA.
       PREMIERE SECTION.
       A010.
           MOVE 'N' TO COMM-SUCCESS
           MOVE '0' TO COMM-FAIL-CODE

      *
      *    Set up some Abend handling
      *
           EXEC CICS HANDLE ABEND
              LABEL(ABEND-HANDLING)
           END-EXEC.

           MOVE SORTCODE TO COMM-SORTC.
           MOVE SORTCODE TO DESIRED-SORT-CODE.

      *
      *    Determine what kind of ACCOUNT datastore we should
      *    be accessing
      *


      *
      *           Go and update the ACCOUNT record
      *
            PERFORM UPDATE-ACCOUNT-DB2.
      *
      *    The COMMAREA values have now been set so all we need to do
      *    is finish
      *

           PERFORM GET-ME-OUT-OF-HERE.

       A999.
           EXIT.


       UPDATE-ACCOUNT-DB2 SECTION.
       UAD010.

           MOVE COMM-ACCNO TO DESIRED-ACC-NO.
           MOVE DESIRED-SORT-CODE TO HV-ACCOUNT-SORTCODE.
           MOVE DESIRED-ACC-NO TO HV-ACCOUNT-ACC-NO.

      *
      *    Retrieve the account information
      *
           EXEC SQL
              SELECT ACCOUNT_EYECATCHER,
                     ACCOUNT_CUSTOMER_NUMBER,
                     ACCOUNT_SORTCODE,
                     ACCOUNT_NUMBER,
                     ACCOUNT_TYPE,
                     ACCOUNT_INTEREST_RATE,
                     ACCOUNT_OPENED,
                     ACCOUNT_OVERDRAFT_LIMIT,
                     ACCOUNT_LAST_STATEMENT,
                     ACCOUNT_NEXT_STATEMENT,
                     ACCOUNT_AVAILABLE_BALANCE,
                     ACCOUNT_ACTUAL_BALANCE
              INTO  :HV-ACCOUNT-EYECATCHER,
                    :HV-ACCOUNT-CUST-NO,
                    :HV-ACCOUNT-SORTCODE,
                    :HV-ACCOUNT-ACC-NO,
                    :HV-ACCOUNT-ACC-TYPE,
                    :HV-ACCOUNT-INT-RATE,
                    :HV-ACCOUNT-OPENED,
                    :HV-ACCOUNT-OVERDRAFT-LIM,
                    :HV-ACCOUNT-LAST-STMT,
                    :HV-ACCOUNT-NEXT-STMT,
                    :HV-ACCOUNT-AVAIL-BAL,
                    :HV-ACCOUNT-ACTUAL-BAL
              FROM ACCOUNT
              WHERE  (ACCOUNT_SORTCODE = :HV-ACCOUNT-SORTCODE AND
                      ACCOUNT_NUMBER = :HV-ACCOUNT-ACC-NO)
           END-EXEC.

      *
      *    Check that select was successful. If it wasn't then deal with
      *    it
      *
           IF SQLCODE NOT = 0

              MOVE 'N' TO COMM-SUCCESS

              IF SQLCODE = +100
                 MOVE '1' TO COMM-FAIL-CODE
              ELSE
                 MOVE '2' TO COMM-FAIL-CODE
              END-IF

      *
      *       Check if SQLCODE indicates that Storm Drain processing
      *       is applicable in a workload if activated
      *
              PERFORM CHECK-FOR-STORM-DRAIN-DB2

              GO TO UAD999

           END-IF.


      *
      *    Is the amount being requested a debit or a credit?
      *    If it is a CREDIT (+) then we don't need to ensure that
      *    the available balance has sufficient funds, because this
      *    is money coming in.
      *

           IF COMM-AMT < 0
      *
      *       The amount being requested is a DEBIT/Payment (-)
      *       so we do need to check that the available
      *       balance is sufficient to cover the amount being
      *       asked for. If there are NOT sufficient funds the
      *       request is denied so remove the record LOCK and
      *       and finish.
      *
      D       DISPLAY 'COMM-AMT IS negative'


      *
      *       Check to see whether the Payment is being
      *       requested from a MORTGAGE or LOAN account. We only make
      *       this check for PAYMENTs (we don't make this check for
      *       requests via the Teller). How do we know it is a PAYMENT
      *       as opposed to a Teller, this is determined by the
      *       COMM-FACILTYPE(496 = NONE)
      *       If it is a PAYMENT being requested from a MORTGAGE or
      *       LOAN account then set an appropriate fail code (4)
      *       and finish up.
      *
              IF (HV-ACCOUNT-ACC-TYPE = 'MORTGAGE'
              AND COMM-FACILTYPE = 496)
              OR (HV-ACCOUNT-ACC-TYPE = 'LOAN    '
              AND COMM-FACILTYPE = 496)
                 MOVE 'N' TO COMM-SUCCESS
                 MOVE '4' TO COMM-FAIL-CODE

                 GO TO UAD999
              END-IF

              MOVE 0 TO WS-DIFFERENCE
              COMPUTE WS-DIFFERENCE = HV-ACCOUNT-AVAIL-BAL
                 + COMM-AMT

              IF WS-DIFFERENCE < 0 AND COMM-FACILTYPE = 496
      D          DISPLAY 'insufficient funds!'
                 MOVE 'N' TO COMM-SUCCESS
                 MOVE '3' TO COMM-FAIL-CODE

                 GO TO UAD999
              END-IF

           END-IF.


      *
      *    Check to see whether a Credit is being
      *    requested from a MORTGAGE or LOAN account. We only make
      *    this check for requests via the PAYMENT link
      *    (we don't make this check for
      *    requests via the Teller). How do we know it is a PAYMENT
      *    as opposed to a Teller, this is determined by the
      *    COMM-FACILTYPE(496 = NONE)
      *    If it is a PAYMENT credit being requested
      *    from a MORTGAGE or LOAN
      *    account then set an appropriate fail code (4), remove
      *    the record lock and finish up.
      *
           IF (HV-ACCOUNT-ACC-TYPE = 'MORTGAGE' AND
           COMM-FACILTYPE = 496)
           OR (HV-ACCOUNT-ACC-TYPE = 'LOAN    '
           AND COMM-FACILTYPE = 496)
              MOVE 'N' TO COMM-SUCCESS
              MOVE '4' TO COMM-FAIL-CODE

              GO TO UAD999
           END-IF.


      *
      *    If the SQLCODE from the SELECT is OK then update
      *    the record and update the details on the
      *    PROCTRAN (Processed transaction) datastore.
      *
           COMPUTE HV-ACCOUNT-AVAIL-BAL =
              HV-ACCOUNT-AVAIL-BAL + COMM-AMT.
           COMPUTE HV-ACCOUNT-ACTUAL-BAL =
              HV-ACCOUNT-ACTUAL-BAL + COMM-AMT.

      *
      *    Update the account record
      *
           EXEC SQL
              UPDATE ACCOUNT
              SET ACCOUNT_EYECATCHER = :HV-ACCOUNT-EYECATCHER,
                  ACCOUNT_CUSTOMER_NUMBER = :HV-ACCOUNT-CUST-NO,
                  ACCOUNT_SORTCODE = :HV-ACCOUNT-SORTCODE,
                  ACCOUNT_NUMBER = :HV-ACCOUNT-ACC-NO,
                  ACCOUNT_TYPE = :HV-ACCOUNT-ACC-TYPE,
                  ACCOUNT_INTEREST_RATE = :HV-ACCOUNT-INT-RATE,
                  ACCOUNT_OPENED = :HV-ACCOUNT-OPENED,
                  ACCOUNT_OVERDRAFT_LIMIT = :HV-ACCOUNT-OVERDRAFT-LIM,
                  ACCOUNT_LAST_STATEMENT = :HV-ACCOUNT-LAST-STMT,
                  ACCOUNT_NEXT_STATEMENT = :HV-ACCOUNT-NEXT-STMT,
                  ACCOUNT_AVAILABLE_BALANCE = :HV-ACCOUNT-AVAIL-BAL,
                  ACCOUNT_ACTUAL_BALANCE = :HV-ACCOUNT-ACTUAL-BAL
              WHERE (ACCOUNT_SORTCODE = :HV-ACCOUNT-SORTCODE AND
                     ACCOUNT_NUMBER = :HV-ACCOUNT-ACC-NO)
           END-EXEC.

      *
      *    If the rewrite was successful then we need to pass back
      *    the amended available balance and actual balance.
      *
           MOVE SQLCODE TO SQLCODE-DISPLAY.

           MOVE HV-ACCOUNT-AVAIL-BAL TO
              COMM-AV-BAL.
           MOVE HV-ACCOUNT-ACTUAL-BAL TO
              COMM-ACT-BAL.

      *
      *    If the RESP CODE was NOT OK then we need to set flags
      *    accordingly
      *
           IF SQLCODE NOT = 0
              MOVE 'N' TO COMM-SUCCESS
              MOVE '2' TO COMM-FAIL-CODE
      *
      *       Check if SQLCODE indicates that Storm Drain processing
      *       is applicable in a workload if activated
      *
              PERFORM CHECK-FOR-STORM-DRAIN-DB2
              GO TO UAD999

           END-IF.

      *
      *    If the RESP CODE was normal then we need to write to the
      *    PROCTRAN (processed transaction) datastore.
      *
           PERFORM WRITE-TO-PROCTRAN.

       UAD999.
           EXIT.


       WRITE-TO-PROCTRAN SECTION.
       WTP010.

      *
      *          Write to the PROCTRAN datastore deatils regarding the
      *          successfully applied transaction.
      *
            PERFORM WRITE-TO-PROCTRAN-DB2.

       WTP999.
           EXIT.


       WRITE-TO-PROCTRAN-DB2 SECTION.
       WTPD010.

           INITIALIZE HOST-PROCTRAN-ROW.
           INITIALIZE WS-EIBTASKN12.

           MOVE 'PRTR' TO HV-PROCTRAN-EYECATCHER.
           MOVE COMM-SORTC TO HV-PROCTRAN-SORT-CODE.
           MOVE COMM-ACCNO TO HV-PROCTRAN-ACC-NUMBER.
           MOVE EIBTASKN TO WS-EIBTASKN12.
           MOVE WS-EIBTASKN12 TO HV-PROCTRAN-REF.

      *
      *    Populate the current time and date
      *
           EXEC CICS ASKTIME
              ABSTIME(WS-U-TIME)
           END-EXEC.

           EXEC CICS FORMATTIME
                     ABSTIME(WS-U-TIME)
                     DDMMYYYY(WS-ORIG-DATE)
                     TIME(HV-PROCTRAN-TIME)
                     DATESEP('.')
           END-EXEC.

           MOVE WS-ORIG-DATE TO WS-ORIG-DATE-GRP-X.
           MOVE WS-ORIG-DATE-GRP-X TO HV-PROCTRAN-DATE.

           MOVE SPACES TO HV-PROCTRAN-DESC.

           IF COMM-AMT < 0
              MOVE 'DEB' TO HV-PROCTRAN-TYPE
              MOVE 'COUNTER WTHDRW' TO HV-PROCTRAN-DESC

      *
      *       If it is a debit from a PAYMENT
      *
              IF COMM-FACILTYPE = 496
                 MOVE 'PDR' TO HV-PROCTRAN-TYPE
                 MOVE COMM-ORIGIN(1:14) TO
                    HV-PROCTRAN-DESC
              END-IF

           ELSE
              MOVE 'CRE' TO HV-PROCTRAN-TYPE
              MOVE 'COUNTER RECVED' TO HV-PROCTRAN-DESC

      *
      *       If it is a credit from a PAYMENT
      *
              IF COMM-FACILTYPE = 496
                 MOVE 'PCR' TO HV-PROCTRAN-TYPE
                 MOVE COMM-ORIGIN(1:14) TO
                    HV-PROCTRAN-DESC
              END-IF

           END-IF.

           MOVE COMM-AMT TO HV-PROCTRAN-AMOUNT.

      *
      *    Write a record to PROCTRAN
      *
           EXEC SQL
              INSERT INTO PROCTRAN
                     (
                      PROCTRAN_EYECATCHER,
                      PROCTRAN_SORTCODE,
                      PROCTRAN_NUMBER,
                      PROCTRAN_DATE,
                      PROCTRAN_TIME,
                      PROCTRAN_REF,
                      PROCTRAN_TYPE,
                      PROCTRAN_DESC,
                      PROCTRAN_AMOUNT
                     )
              VALUES
                     (
                      :HV-PROCTRAN-EYECATCHER,
                      :HV-PROCTRAN-SORT-CODE,
                      :HV-PROCTRAN-ACC-NUMBER,
                      :HV-PROCTRAN-DATE,
                      :HV-PROCTRAN-TIME,
                      :HV-PROCTRAN-REF,
                      :HV-PROCTRAN-TYPE,
                      :HV-PROCTRAN-DESC,
                      :HV-PROCTRAN-AMOUNT
                     )
           END-EXEC.

      *
      *    Check the SQLCODE
      *
           IF SQLCODE NOT = 0
              MOVE SQLCODE TO SQLCODE-DISPLAY

              DISPLAY 'UNABLE TO WRITE TO PROCTRAN DB2 DATASTORE'
              ' SQLCODE=' SQLCODE-DISPLAY
              'WITH THE FOLLOWING DATA:' HOST-PROCTRAN-ROW
      *
      *       You need to issue a ROLLBACK to get rid of the updated
      *       ACCOUNT record
      *
              EXEC CICS SYNCPOINT ROLLBACK
                 RESP(WS-CICS-RESP)
                 RESP2(WS-CICS-RESP2)
              END-EXEC

              IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
      *
      *          Preserve the RESP and RESP2, then set up the
      *          standard ABEND info before getting the applid,
      *          date/time etc. and linking to the Abend Handler
      *          program.
      *
                 INITIALIZE ABNDINFO-REC
                 MOVE EIBRESP    TO ABND-RESPCODE
                 MOVE EIBRESP2   TO ABND-RESP2CODE
      *
      *          Get supplemental information
      *
                 EXEC CICS ASSIGN APPLID(ABND-APPLID)
                 END-EXEC

                 MOVE EIBTASKN   TO ABND-TASKNO-KEY
                 MOVE EIBTRNID   TO ABND-TRANID

                 PERFORM POPULATE-TIME-DATE

                 MOVE WS-ORIG-DATE TO ABND-DATE
                 STRING WS-TIME-NOW-GRP-HH DELIMITED BY SIZE,
                       ':' DELIMITED BY SIZE,
                        WS-TIME-NOW-GRP-MM DELIMITED BY SIZE,
                        ':' DELIMITED BY SIZE,
                        WS-TIME-NOW-GRP-MM DELIMITED BY SIZE
                        INTO ABND-TIME
                 END-STRING

                 MOVE WS-U-TIME   TO ABND-UTIME-KEY
                 MOVE 'HROL'      TO ABND-CODE

                 EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM)
                 END-EXEC

                 MOVE ZEROS      TO ABND-SQLCODE

                 STRING 'WTPD010 - COULD NOT ROLL BACK, POSSIBLE DATA'
                       DELIMITED BY SIZE,
                       'INTEGRITY ISSUE BETWEEN ACCOUNT AND PROCTRAN '
                       DELIMITED BY SIZE,
                       'FOR ROW:' DELIMITED BY SIZE,
                       HOST-PROCTRAN-ROW DELIMITED BY SIZE,
                       'EIBRESP=' DELIMITED BY SIZE,
                       ABND-RESPCODE DELIMITED BY SIZE,
                       ' RESP2=' DELIMITED BY SIZE,
                       ABND-RESP2CODE DELIMITED BY SIZE
                       INTO ABND-FREEFORM
                 END-STRING

                 EXEC CICS LINK PROGRAM(WS-ABEND-PGM)
                           COMMAREA(ABNDINFO-REC)
                 END-EXEC

                 DISPLAY ' COULD NOT ROLL BACK, POSSIBLE DATA '
                    'INTEGRITY ISSUE BETWEEN ACCOUNT AND PROCTRAN '
                    'FOR ROW:' HOST-PROCTRAN-ROW
                    'RESP CODE=' WS-CICS-RESP ' RESP2 CODE='
                    WS-CICS-RESP2

                 EXEC CICS ABEND
                    ABCODE ('HROL')
                    CANCEL
                 END-EXEC
              END-IF

              MOVE 'N' TO COMM-SUCCESS
              MOVE '02' TO COMM-FAIL-CODE
      *
      *       Check if SQLCODE indicates that Storm Drain processing
      *       is applicable in a workload if activated
      *
              PERFORM CHECK-FOR-STORM-DRAIN-DB2

           ELSE

      *
      *       If the WRITE to PROCTRAN worked then it was a success
      *
              MOVE 'Y' TO COMM-SUCCESS
              MOVE '0' TO COMM-FAIL-CODE

           END-IF.

       WTPD999.
           EXIT.


       GET-ME-OUT-OF-HERE SECTION.
       GMOOH010.
           EXEC CICS RETURN
           END-EXEC.
           GOBACK.

       GMOOH999.
           EXIT.


       CHECK-FOR-STORM-DRAIN-DB2 SECTION.
       CFSDD010.
      *
      *    Check if the Sqclode that is returned one that will
      *    trigger Storm Drain is active in Workload
      *

           EVALUATE SQLCODE

              WHEN 923
                 MOVE 'DB2 Connection lost ' TO STORM-DRAIN-CONDITION

              WHEN OTHER
                 MOVE 'Not Storm Drain     ' TO STORM-DRAIN-CONDITION

           END-EVALUATE.

           IF STORM-DRAIN-CONDITION NOT EQUAL 'Not Storm Drain     '
              DISPLAY 'DBCRFUN: Check-For-Storm-Drain-DB2: Storm '
                      'Drain condition (' STORM-DRAIN-CONDITION ') '
                      'has been met (' SQLCODE-DISPLAY ').'
           ELSE

              CONTINUE
           END-IF.

       CFSDD999.
           EXIT.


      *
      * How ABENDs are dealt with
      *
       ABEND-HANDLING SECTION.
       AH010.

           EXEC CICS ASSIGN ABCODE(MY-ABEND-CODE)
           END-EXEC.

      *
      *    Evaluate the Abend code that is returned
      *      - For DB2 AD2Z ... provide some diagnostics
      *      - For VSAM RLS abends: AFCR, AFCS and AFCT record the
      *        Abend as happening but do not abend ... leave this to
      *        CPSM WLM "Storm drain" (Abend probability) to handle
      *    If not a "storm drain" ... take the abend afterwards
      *

           EVALUATE MY-ABEND-CODE
      *
      *       DB2 AD2Z abend
      *
              WHEN 'AD2Z'

                 MOVE SQLCODE TO SQLCODE-DISPLAY
                 DISPLAY 'DB2 DEADLOCK DETECTED IN DBCRFUN, SQLCODE='
                    SQLCODE-DISPLAY

                 DISPLAY 'DB2 DEADLOCK FOR ACCOUNT '
                   HV-ACCOUNT-ACC-NO
                 DISPLAY  'SQLSTATE=' SQLSTATE
                        ',SQLERRMC=' SQLERRMC(1:SQLERRML)
                        ',SQLERRD(1)=' SQLERRD(1)
                        ',SQLERRD(2)=' SQLERRD(2)
                        ',SQLERRD(3)=' SQLERRD(3)
                        ',SQLERRD(4)=' SQLERRD(4)
                        ',SQLERRD(5)=' SQLERRD(5)
                        ',SQLERRD(6)=' SQLERRD(6)

      *
      *          VSAM RLS abends, subject to CPSM WLM Storm Drain check
      *          if handled (as here) and Workload Abend Thresholds are
      *          set.
      *
              WHEN 'AFCR'
              WHEN 'AFCS'
              WHEN 'AFCT'
                 MOVE 'Y' TO WS-STORM-DRAIN
                 DISPLAY 'DBCRFUN: Check-For-Storm-Drain-VSAM: Storm '
                        'Drain condition (Abend ' MY-ABEND-CODE ') '
                        'has been met.'

                 EXEC CICS SYNCPOINT
                    ROLLBACK
                    RESP(WS-CICS-RESP)
                    RESP2(WS-CICS-RESP2)
                 END-EXEC

                 IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
      *
      *             Preserve the RESP and RESP2, then set up the
      *             standard ABEND info before getting the applid,
      *             date/time etc. and linking to the Abend Handler
      *             program.
      *
                    INITIALIZE ABNDINFO-REC
                    MOVE EIBRESP    TO ABND-RESPCODE
                    MOVE EIBRESP2   TO ABND-RESP2CODE
      *
      *             Get supplemental information
      *
                    EXEC CICS ASSIGN APPLID(ABND-APPLID)
                    END-EXEC

                    MOVE EIBTASKN   TO ABND-TASKNO-KEY
                    MOVE EIBTRNID   TO ABND-TRANID

                    PERFORM POPULATE-TIME-DATE

                    MOVE WS-ORIG-DATE TO ABND-DATE
                    STRING WS-TIME-NOW-GRP-HH DELIMITED BY SIZE,
                       ':' DELIMITED BY SIZE,
                        WS-TIME-NOW-GRP-MM DELIMITED BY SIZE,
                        ':' DELIMITED BY SIZE,
                        WS-TIME-NOW-GRP-MM DELIMITED BY SIZE
                        INTO ABND-TIME
                    END-STRING

                    MOVE WS-U-TIME   TO ABND-UTIME-KEY
                    MOVE 'HROL'      TO ABND-CODE

                    EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM)
                    END-EXEC

                    MOVE ZEROS      TO ABND-SQLCODE

                    STRING 'AH010 - Unable to perform Synpoint '
                       DELIMITED BY SIZE,
                       'Rollback.' DELIMITED BY SIZE,
                       ' Possible Integrity issue following VSAM RLS '
                       DELIMITED BY SIZE,
                       'abend.' DELIMITED BY SIZE,
                       'EIBRESP=' DELIMITED BY SIZE,
                       ABND-RESPCODE DELIMITED BY SIZE,
                       ' RESP2=' DELIMITED BY SIZE,
                       ABND-RESP2CODE DELIMITED BY SIZE
                       INTO ABND-FREEFORM
                    END-STRING

                    EXEC CICS LINK PROGRAM(WS-ABEND-PGM)
                           COMMAREA(ABNDINFO-REC)
                    END-EXEC

                    DISPLAY 'DBCRFUN: Unable to perform Synpoint '
                       'Rollback.'
                       ' Possible Integrity issue following VSAM RLS'
                       ' abend'
                       ' RESP CODE=' WS-CICS-RESP
                       ' RESP2 CODE=' WS-CICS-RESP2

                    EXEC CICS ABEND
                       ABCODE ('HROL')
                       CANCEL
                    END-EXEC

                 END-IF

                 MOVE 'N' TO COMM-SUCCESS
                 MOVE '2' TO COMM-FAIL-CODE

                 EXEC CICS RETURN
                 END-EXEC

           END-EVALUATE.

           IF WS-STORM-DRAIN = 'N'
              EXEC CICS ABEND
                 ABCODE( MY-ABEND-CODE)
                 NODUMP
                 CANCEL
              END-EXEC

           END-IF.

       AH999.
           EXIT.


       POPULATE-TIME-DATE SECTION.
       PTD10.

           EXEC CICS ASKTIME
              ABSTIME(WS-U-TIME)
           END-EXEC.

           EXEC CICS FORMATTIME
                     ABSTIME(WS-U-TIME)
                     DDMMYYYY(WS-ORIG-DATE)
                     TIME(WS-TIME-NOW)
                     DATESEP
           END-EXEC.

       PTD999.
           EXIT.
