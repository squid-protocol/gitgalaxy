       PROCESS CICS,NODYNAM,NSYMBOL(NATIONAL),TRUNC(STD)
       CBL CICS('SP,EDF,DLI')
      ******************************************************************
      *                                                                *
      *  Copyright IBM Corp. 2023                                      *
      *                                                                *
      ******************************************************************


      ******************************************************************
      * This program processes application abends and writes them to
      * a centralised CF (KSDS) datastore - this is so that they can be
      * viewed from one place, without having to go hunting for them.
      ******************************************************************

       IDENTIFICATION DIVISION.
       PROGRAM-ID. ABNDPROC.
       AUTHOR. JONCOLLETT.

       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
      *SOURCE-COMPUTER.   IBM-370 WITH DEBUGGING MODE.
       SOURCE-COMPUTER.  IBM-370.
       OBJECT-COMPUTER.  IBM-370.

       INPUT-OUTPUT SECTION.


       DATA DIVISION.
       WORKING-STORAGE SECTION.

       01 WS-CICS-WORK-AREA.
          05 WS-CICS-RESP      PIC S9(8) COMP.
          05 WS-CICS-RESP2     PIC S9(8) COMP.


       01 WS-ABND-AREA.
           COPY ABNDINFO.

       01 WS-ABND-KEY-LEN      PIC S9(8) COMP VALUE +12.

       LOCAL-STORAGE SECTION.


       01 DB2-DATE-REFORMAT.
          03 DB2-DATE-REF-YR           PIC 9(4).
          03 FILLER                    PIC X.
          03 DB2-DATE-REF-MNTH         PIC 99.
          03 FILLER                    PIC X.
          03 DB2-DATE-REF-DAY          PIC 99.

       01 DATA-STORE-TYPE      PIC X.
          88 DATASTORE-TYPE-DLI     VALUE '1'.
          88 DATASTORE-TYPE-DB2     VALUE '2'.
          88 DATASTORE-TYPE-VSAM    VALUE 'V'.

       01 WS-EIBTASKN12                PIC 9(12) VALUE 0.
       01 WS-SQLCODE-DISP              PIC 9(9) VALUE 0.

      * **************************************************************
      * Pull in the input and output data structures
      * **************************************************************


       01 WS-U-TIME                      PIC S9(15) COMP-3.
       01 WS-ORIG-DATE                   PIC X(10).
       01 WS-ORIG-DATE-GRP REDEFINES WS-ORIG-DATE.
          03 WS-ORIG-DATE-DD             PIC 99.
          03 FILLER                      PIC X.
          03 WS-ORIG-DATE-MM             PIC 99.
          03 FILLER                      PIC X.
          03 WS-ORIG-DATE-YYYY           PIC 9999.

       01 WS-ORIG-DATE-GRP-X.
          03 WS-ORIG-DATE-DD-X           PIC XX.
          03 FILLER                      PIC X VALUE '.'.
          03 WS-ORIG-DATE-MM-X           PIC XX.
          03 FILLER                      PIC X VALUE '.'.
          03 WS-ORIG-DATE-YYYY-X         PIC X(4).


       01 WS-PASSED-DATA.
          02 WS-TEST-KEY                             PIC X(4).
          02 WS-SORT-CODE                            PIC 9(6).
          02 WS-CUSTOMER-RANGE.
             07 WS-CUSTOMER-RANGE-TOP                PIC X.
             07 WS-CUSTOMER-RANGE-MIDDLE             PIC X.
             07 WS-CUSTOMER-RANGE-BOTTOM             PIC X.

       01 WS-SORT-DIV.
          03 WS-SORT-DIV1                         PIC XX.
          03 WS-SORT-DIV2                         PIC XX.
          03 WS-SORT-DIV3                         PIC XX.

       01 CUSTOMER-KY.
          03 REQUIRED-SORT-CODE       PIC 9(6)  VALUE 0.
          03 REQUIRED-ACC-NUM         PIC 9(8)  VALUE 0.

       01 PROCTRAN-RIDFLD             PIC S9(8) COMP.

       01 SQLCODE-DISPLAY             PIC S9(8) DISPLAY
           SIGN LEADING SEPARATE.

       01 MY-ABEND-CODE               PIC XXXX.



       LINKAGE SECTION.

       01 DFHCOMMAREA.
           03 COMM-VSAM-KEY.
              05 COMM-UTIME-KEY                  PIC S9(15) COMP-3.
              05 COMM-TASKNO-KEY                 PIC 9(4).
           03 COMM-APPLID                        PIC X(8).
           03 COMM-TRANID                        PIC X(4).
           03 COMM-DATE                          PIC X(10).
           03 COMM-TIME                          PIC X(8).
           03 COMM-CODE                          PIC X(4).
           03 COMM-PROGRAM                       PIC X(8).
           03 COMM-RESPCODE                      PIC S9(8) DISPLAY
              SIGN LEADING SEPARATE.
           03 COMM-RESP2CODE                     PIC S9(8) DISPLAY
              SIGN LEADING SEPARATE.
           03 COMM-SQLCODE                       PIC S9(8) DISPLAY
              SIGN LEADING SEPARATE.
           03 COMM-FREEFORM                      PIC X(600).



       PROCEDURE DIVISION USING DFHCOMMAREA.
       PREMIERE SECTION.
       A010.


      D    DISPLAY 'Started ABNDPROC:'.
      D    DISPLAY 'COMMAREA passed=' DFHCOMMAREA.


           MOVE DFHCOMMAREA TO WS-ABND-AREA.

           EXEC CICS WRITE
              FILE('ABNDFILE')
              FROM(WS-ABND-AREA)
              RIDFLD(ABND-VSAM-KEY)
              RESP(WS-CICS-RESP)
              RESP2(WS-CICS-RESP2)
           END-EXEC.

           IF WS-CICS-RESP NOT= DFHRESP(NORMAL)
              DISPLAY '*********************************************'
              DISPLAY '**** Unable to write to the file ABNDFILE !!!'
              DISPLAY 'RESP=' WS-CICS-RESP ' RESP2=' WS-CICS-RESP2
              DISPLAY '*********************************************'

              EXEC CICS RETURN
              END-EXEC

           END-IF.

      D    DISPLAY 'ABEND record successfully written to ABNDFILE'.
      D    DISPLAY WS-ABND-AREA.

           PERFORM GET-ME-OUT-OF-HERE.

       A999.
           EXIT.

      /
       GET-ME-OUT-OF-HERE SECTION.
       GMOOH010.
           EXEC CICS RETURN
           END-EXEC.
           GOBACK.

       GMOOH999.
           EXIT.

