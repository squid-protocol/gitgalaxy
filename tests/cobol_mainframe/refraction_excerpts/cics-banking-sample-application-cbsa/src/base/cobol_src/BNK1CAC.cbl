       PROCESS CICS,NODYNAM,NSYMBOL(NATIONAL),TRUNC(STD)
       CBL CICS('SP,EDF')
      ******************************************************************
      *                                                                *
      *  Copyright IBM Corp. 2023                                      *
      *                                                                *
      ******************************************************************

      ******************************************************************
      * This is the Create Account program. It verifies the input
      * and assuming it passes verification, it links to the CREACC
      * program to add it to the Account datastore.
      *
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BNK1CAC.
       AUTHOR. Jon Collett.

       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
      *SOURCE-COMPUTER.   IBM-370 WITH DEBUGGING MODE.
       SOURCE-COMPUTER.  IBM-370.
       OBJECT-COMPUTER.  IBM-370.

       INPUT-OUTPUT SECTION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-CICS-WORK-AREA.
          03 WS-CICS-RESP              PIC S9(8) COMP VALUE 0.
          03 WS-CICS-RESP2             PIC S9(8) COMP VALUE 0.

       01 WS-FAIL-INFO.
          03 FILLER                    PIC X(9)  VALUE 'BNK1CAC  '.
          03 WS-CICS-FAIL-MSG          PIC X(70) VALUE ' '.
          03 FILLER                    PIC X(6)  VALUE ' RESP='.
          03 WS-CICS-RESP-DISP         PIC 9(10) VALUE 0.
          03 FILLER                    PIC X(7)  VALUE ' RESP2='.
          03 WS-CICS-RESP2-DISP        PIC 9(10) VALUE 0.
          03 FILLER                    PIC X(15)
                                          VALUE ' ABENDING TASK.'.

       01 SWITCHES.
           03 VALID-DATA-SW            PIC X VALUE 'Y'.
              88 VALID-DATA               VALUE 'Y'.

       01 FLAGS.
           03 SEND-FLAG                PIC X.
              88 SEND-ERASE               VALUE '1'.
              88 SEND-DATAONLY            VALUE '2'.
              88 SEND-DATAONLY-ALARM      VALUE '3'.

       01 ACTION-ALPHA.
           03 ACTION-NUM               PIC 9.

      *
      * The end of session message
      *
       01 END-OF-SESSION-MESSAGE       PIC X(13) VALUE 'Session Ended'.

       01 RESPONSE-CODE                PIC S9(8) COMP.

       01 COMMUNICATION-AREA           PIC X.

       COPY BNK1CAM.

       COPY DFHAID.

       01 COMM-DOB-SPLIT.
          03 COMM-DOB-SPLIT-DD         PIC 99.
          03 COMM-DOB-SPLIT-MM         PIC 99.
          03 COMM-DOB-SPLIT-YYYY       PIC 9999.

       01 WS-COMM-AREA.
          03 WS-COMM-CUSTNO            PIC 9(10).
          03 WS-COMM-ACCTYPE           PIC X(8).
          03 WS-COMM-INTRT             PIC 9(4)V99.
          03 WS-COMM-OVERDR            PIC 9(8).

       01 DATE-REFORMED.
          03 NSTMTDD-CHAR             PIC XX.
          03 NSTMTDD-REFORM REDEFINES NSTMTDD-CHAR.
             05 NSTMTDD-NUM              PIC 99.
          03 NSTMTMMI-CHAR               PIC XX.
          03 NSTMTMMI-REFORM REDEFINES NSTMTMMI-CHAR.
             05 NSTMTMMI-NUM             PIC 99.
          03 NSTMTYYI-CHAR               PIC XX.
          03 NSTMTYYI-REFORM REDEFINES NSTMTYYI-CHAR.
             05 NSTMTYYI-NUM             PIC 99.

       01 MORE-STRING-CONVS.
          03 NST-CHAR                  PIC X(8).
          03 NST-DATE-GRP REDEFINES NST-CHAR.
             05 NST-NUM                PIC 9(8).

       01 INTRTI-COMP-1 USAGE COMP-1.
       01 INTRT-PIC9                   PIC 9999.99.
       01 WS-NUM-COUNT-POINT           PIC S9(8) BINARY.
       01 WS-NUM-COUNT-TOTAL           PIC S9(8) BINARY.
       01 WS-REVERSE                   PIC X(8).

       01 SUBPGM-PARMS.
          03 SUBPGM-EYECATCHER         PIC X(4).
          03 SUBPGM-CUSTNO             PIC 9(10).
          03 SUBPGM-KEY.
             05 SUBPGM-SORTCODE        PIC 9(6) DISPLAY.
             05 SUBPGM-NUMBER          PIC 9(8) DISPLAY.
          03 SUBPGM-ACC-TYPE           PIC X(8).
          03 SUBPGM-INT-RT             PIC 9(4)V99.
          03 SUBPGM-OPENED             PIC 9(8).
          03 SUBPGM-OVERDR-LIM         PIC 9(8).
          03 SUBPGM-LAST-STMT-DT       PIC 9(8).
          03 SUBPGM-NEXT-STMT-DT       PIC 9(8).
          03 SUBPGM-AVAIL-BAL          PIC S9(10)V99.
          03 SUBPGM-ACT-BAL            PIC S9(10)V99.
          03 SUBPGM-SUCCESS            PIC X.
          03 SUBPGM-FAIL-CODE          PIC X.

       01 COMPANY-NAME-FULL            PIC X(32).

       01 AVAILABLE-BALANCE-DISPLAY    PIC +9(10).99.
       01 ACTUAL-BALANCE-DISPLAY       PIC +9(10).99.

       01 WS-U-TIME                    PIC S9(15) COMP-3.
       01 WS-ORIG-DATE                 PIC X(10).
       01 WS-ORIG-DATE-GRP REDEFINES WS-ORIG-DATE.
          03 WS-ORIG-DATE-DD           PIC 99.
          03 FILLER                    PIC X.
          03 WS-ORIG-DATE-MM           PIC 99.
          03 FILLER                    PIC X.
          03 WS-ORIG-DATE-YYYY         PIC 9999.

       01 WS-ORIG-DATE-GRP-X.
          03 WS-ORIG-DATE-DD-X         PIC XX.
          03 FILLER                    PIC X VALUE '.'.
          03 WS-ORIG-DATE-MM-X         PIC XX.
          03 FILLER                    PIC X VALUE '.'.
          03 WS-ORIG-DATE-YYYY-X       PIC X(4).

       01 WS-TIME-DATA.
           03 WS-TIME-NOW              PIC 9(6).
           03 WS-TIME-NOW-GRP REDEFINES WS-TIME-NOW.
              05 WS-TIME-NOW-GRP-HH       PIC 99.
              05 WS-TIME-NOW-GRP-MM       PIC 99.
              05 WS-TIME-NOW-GRP-SS       PIC 99.

       01 WS-ABEND-PGM                 PIC X(8) VALUE 'ABNDPROC'.

       01 ABNDINFO-REC.
           COPY ABNDINFO.

       LINKAGE SECTION.
       01 DFHCOMMAREA.
          03 COMM-CUSTNO            PIC 9(10).
          03 COMM-ACCTYPE           PIC X(8).
          03 COMM-INTRT             PIC 9(4)V99.
          03 COMM-OVERDR            PIC 9(8).

       PROCEDURE DIVISION USING DFHCOMMAREA.
       PREMIERE SECTION.
       A010.

           EVALUATE TRUE

      *
      *       Is it the first time through? If so, send the map
      *       with erased (empty) data fields.
      *
              WHEN EIBCALEN = ZERO
                 MOVE LOW-VALUE TO BNK1CAO
                 MOVE -1 TO CUSTNOL
                 SET SEND-ERASE TO TRUE
                 MOVE SPACES TO MESSAGEO
                 PERFORM SEND-MAP

      *
      *       If a PA key is pressed, just carry on
      *
              WHEN EIBAID = DFHPA1 OR DFHPA2 OR DFHPA3
                 CONTINUE

      *
      *       When Pf3 is pressed, return to the main menu
      *
              WHEN EIBAID = DFHPF3
                 EXEC CICS RETURN
                    TRANSID('OMEN')
                    IMMEDIATE
                    RESP(WS-CICS-RESP)
                    RESP2(WS-CICS-RESP2)
                 END-EXEC

      *
      *       If the aid or Pf12 is pressed, then send a termination
      *       message.
      *
              WHEN EIBAID = DFHAID OR DFHPF12
                 PERFORM SEND-TERMINATION-MSG
                 EXEC CICS
                    RETURN
                 END-EXEC

      *
      *       When CLEAR is pressed
      *
              WHEN EIBAID = DFHCLEAR
                 EXEC CICS SEND CONTROL
                          ERASE
                          FREEKB
                 END-EXEC

                 EXEC CICS RETURN
                 END-EXEC

      *
      *       When enter is pressed then process the content
      *
              WHEN EIBAID = DFHENTER
                 PERFORM PROCESS-MAP

      *
      *       When anything else happens, send the invalid key message
      *
              WHEN OTHER
                 MOVE LOW-VALUES TO BNK1CAO
                 MOVE SPACES TO MESSAGEO
                 MOVE 'Invalid key pressed.' TO MESSAGEO
                 SET SEND-DATAONLY-ALARM TO TRUE
                 PERFORM SEND-MAP

           END-EVALUATE.

      *
      *     Having processed the input or processed the error check
      *     to see if it is the first time through. If it is then
      *     initialise the returned information. If it is not, set
      *     the return information accordingly.
      *
            IF EIBCALEN NOT = 0
               MOVE SUBPGM-CUSTNO     TO WS-COMM-CUSTNO
               MOVE SUBPGM-ACC-TYPE   TO WS-COMM-ACCTYPE
               MOVE SUBPGM-INT-RT     TO WS-COMM-INTRT
               MOVE SUBPGM-OVERDR-LIM TO WS-COMM-OVERDR
            ELSE
               INITIALIZE WS-COMM-AREA
            END-IF.

            EXEC CICS
               RETURN TRANSID('OCAC')
               COMMAREA(WS-COMM-AREA)
               LENGTH(32)
               RESP(WS-CICS-RESP)
               RESP2(WS-CICS-RESP2)
            END-EXEC.

           IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
              INITIALIZE WS-FAIL-INFO
              MOVE 'BNK1CAC - A010 - RETURN TRANSID(OCAC) FAIL' TO
                 WS-CICS-FAIL-MSG
              MOVE WS-CICS-RESP  TO WS-CICS-RESP-DISP
              MOVE WS-CICS-RESP2 TO WS-CICS-RESP2-DISP

      *
      *         Preserve the RESP and RESP2, then set up the
      *         standard ABEND info before getting the applid,
      *         date/time etc. and linking to the Abend Handler
      *         program.
      *
                INITIALIZE ABNDINFO-REC
                MOVE EIBRESP    TO ABND-RESPCODE
                MOVE EIBRESP2   TO ABND-RESP2CODE
      *
      *         Get supplemental information
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
                MOVE 'HBNK'      TO ABND-CODE

                EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM)
                END-EXEC

                MOVE ZEROS      TO ABND-SQLCODE

                STRING 'A010- RETURN TRANSID(OCAC) ' DELIMITED BY SIZE,
                       ' EIBRESP=' DELIMITED BY SIZE,
                       ABND-RESPCODE DELIMITED BY SIZE,
                       ' RESP2=' DELIMITED BY SIZE,
                       ABND-RESP2CODE DELIMITED BY SIZE
                       INTO ABND-FREEFORM
                END-STRING

                EXEC CICS LINK PROGRAM(WS-ABEND-PGM)
                          COMMAREA(ABNDINFO-REC)
                END-EXEC

                PERFORM ABEND-THIS-TASK
           END-IF.

       A999.
           EXIT.


       PROCESS-MAP SECTION.
       PM010.
      *
      *    Retrieve the data from the map
      *
           PERFORM RECEIVE-MAP.

      *
      *    Validate the received data
      *
           PERFORM EDIT-DATA.

      *
      *    If the data passes validation go on to
      *    create an account
      *
           IF VALID-DATA
              PERFORM CRE-ACC-DATA
           END-IF.

           SET SEND-DATAONLY-ALARM TO TRUE.

      *
      *    Output the data to the screen
      *
           PERFORM SEND-MAP.

       PM999.
           EXIT.


       RECEIVE-MAP SECTION.
       RM010.
      *
      *    Retrieve the data
      *
           EXEC CICS
              RECEIVE MAP('BNK1CA')
              MAPSET('BNK1CAM')
              INTO(BNK1CAI)
              RESP(WS-CICS-RESP)
              RESP2(WS-CICS-RESP2)
           END-EXEC.

           IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
              INITIALIZE WS-FAIL-INFO
              MOVE 'BNK1CAC - RM010 - RECEIVE MAP FAIL ' TO
                 WS-CICS-FAIL-MSG
              MOVE WS-CICS-RESP  TO WS-CICS-RESP-DISP
              MOVE WS-CICS-RESP2 TO WS-CICS-RESP2-DISP

      *
      *       Preserve the RESP and RESP2, then set up the
      *       standard ABEND info before getting the applid,
      *       date/time etc. and linking to the Abend Handler
      *       program.
      *
              INITIALIZE ABNDINFO-REC
              MOVE EIBRESP    TO ABND-RESPCODE
              MOVE EIBRESP2   TO ABND-RESP2CODE
      *
      *       Get supplemental information
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
              MOVE 'HBNK'      TO ABND-CODE

              EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM)
              END-EXEC

              MOVE ZEROS      TO ABND-SQLCODE

              STRING 'RM010 - RECEIVE MAP FAIL ' DELIMITED BY SIZE,
                     ' EIBRESP=' DELIMITED BY SIZE,
                     ABND-RESPCODE DELIMITED BY SIZE,
                     ' RESP2=' DELIMITED BY SIZE,
                     ABND-RESP2CODE DELIMITED BY SIZE
                     INTO ABND-FREEFORM
              END-STRING

              EXEC CICS LINK PROGRAM(WS-ABEND-PGM)
                          COMMAREA(ABNDINFO-REC)
              END-EXEC

              PERFORM ABEND-THIS-TASK

           END-IF.

       RM999.
           EXIT.


       EDIT-DATA SECTION.
       ED010.
      *
      *    Perform validation on the incoming fields
      *
           EXEC CICS BIF DEEDIT
              FIELD(CUSTNOI)
           END-EXEC.

           IF CUSTNOL < 1 OR CUSTNOI = '__________'
              MOVE SPACES TO MESSAGEO
              STRING 'Please enter a 10 digit Customer Number '
                    DELIMITED BY SIZE,
                     ' ' DELIMITED BY SIZE
                 INTO MESSAGEO
              MOVE 'N' TO VALID-DATA-SW
              MOVE -1 TO CUSTNOL
              GO TO ED999
           END-IF.

           IF CUSTNOI NOT NUMERIC
              MOVE SPACES TO MESSAGEO
              STRING 'Please enter a numeric Customer number '
                    DELIMITED BY SIZE,
                     ' ' DELIMITED BY SIZE
                 INTO MESSAGEO
              MOVE 'N' TO VALID-DATA-SW
              MOVE -1 TO CUSTNOL
              GO TO ED999
           END-IF.

           IF ACCTYPI = '________' OR ACCTYPL < 1
              MOVE SPACES TO MESSAGEO
              STRING 'Account Type should be ISA,CURRENT,LOAN,'
                 DELIMITED BY SIZE,
                    'SAVING or MORTGAGE' DELIMITED BY SIZE
                 INTO MESSAGEO
              MOVE 'N' TO VALID-DATA-SW
              move -1 to acctypl
              GO TO ED999
           END-IF.

           MOVE SPACES TO MESSAGEO.

           IF ACCTYPL > 0

              EVALUATE ACCTYPI
                 WHEN 'ISA_____'
                    MOVE 'ISA     ' TO ACCTYPI
                    CONTINUE
                 WHEN 'isa_____'
                    MOVE 'ISA     ' TO ACCTYPI
                    CONTINUE
                 WHEN 'ISA     '
                    CONTINUE
                 WHEN 'isa     '
                    MOVE 'ISA     ' TO ACCTYPI
                    CONTINUE
                 WHEN 'CURRENT_'
                    MOVE 'CURRENT ' TO ACCTYPI
                    CONTINUE
                 WHEN 'current_'
                    MOVE 'CURRENT ' TO ACCTYPI
                    CONTINUE
                 WHEN 'CURRENT '
                    CONTINUE
                 WHEN 'current '
                    MOVE 'CURRENT ' TO ACCTYPI
                    CONTINUE
                 WHEN 'LOAN____'
                    MOVE 'LOAN    ' TO ACCTYPI
                    CONTINUE
                 WHEN 'loan____'
                    MOVE 'LOAN    ' TO ACCTYPI
                    CONTINUE
                 WHEN 'loan    '
                    MOVE 'LOAN    ' TO ACCTYPI
                    CONTINUE
                 WHEN 'LOAN    '
                    CONTINUE
                 WHEN 'SAVING__'
                    MOVE 'SAVING  ' TO ACCTYPI
                    CONTINUE
                 WHEN 'saving__'
                    MOVE 'SAVING  ' TO ACCTYPI
                    CONTINUE
                 WHEN 'saving  '
                    MOVE 'SAVING  ' TO ACCTYPI
                    CONTINUE
                 WHEN 'SAVING  '
                    CONTINUE
                 WHEN 'MORTGAGE'
                    CONTINUE
                 WHEN 'mortgage'
                    MOVE 'MORTGAGE' TO ACCTYPI
                    CONTINUE
                 WHEN OTHER
                    MOVE SPACES TO MESSAGEO
                    STRING 'Account Type should be ISA,CURRENT,LOAN,'
                       DELIMITED BY SIZE,
                       'SAVING or MORTGAGE' DELIMITED BY SIZE
                       INTO MESSAGEO
                    MOVE 'N' TO VALID-DATA-SW
                    MOVE -1 TO ACCTYPL
                    GO TO ED999

              END-EVALUATE

           END-IF.

           IF INTRTL = ZERO
              MOVE SPACES TO MESSAGEO
              STRING 'Please supply a numeric interest rate'
                    DELIMITED BY SIZE,
              INTO MESSAGEO
              MOVE 'N' TO VALID-DATA-SW
              MOVE -1 TO INTRTL
              GO TO ED999
           END-IF

           IF INTRTI(1:INTRTL) IS NOT NUMERIC
              MOVE ZERO TO WS-NUM-COUNT-TOTAL
              INSPECT INTRTI(1:INTRTL) TALLYING
                 WS-NUM-COUNT-TOTAL FOR ALL '0'
                 WS-NUM-COUNT-TOTAL FOR ALL '1'
                 WS-NUM-COUNT-TOTAL FOR ALL '2'
                 WS-NUM-COUNT-TOTAL FOR ALL '3'
                 WS-NUM-COUNT-TOTAL FOR ALL '4'
                 WS-NUM-COUNT-TOTAL FOR ALL '5'
                 WS-NUM-COUNT-TOTAL FOR ALL '6'
                 WS-NUM-COUNT-TOTAL FOR ALL '7'
                 WS-NUM-COUNT-TOTAL FOR ALL '8'
                 WS-NUM-COUNT-TOTAL FOR ALL '9'
                 WS-NUM-COUNT-TOTAL FOR ALL '.'
                 WS-NUM-COUNT-TOTAL FOR ALL '-'
                 WS-NUM-COUNT-TOTAL FOR ALL '+'
                 WS-NUM-COUNT-TOTAL FOR ALL ' '
      *
      *       So the idea here is that if there is a
      *       decimal point, the field is not numeric. But if it
      *       is 1.1 then it is valid. So first of all we check
      *       to see that only the above chars are OK. We also
      *       want to tolerate the minus and plus signs. We don't
      *       support negative interest though. We tolerate
      *       trailing spaces too.
      *

              IF WS-NUM-COUNT-TOTAL < INTRTL
                 MOVE SPACES TO MESSAGEO
                 STRING 'Please supply a numeric interest rate'
                      DELIMITED BY SIZE,
                 INTO MESSAGEO
                 MOVE 'N' TO VALID-DATA-SW
                 MOVE -1 TO INTRTL
                 GO TO ED999
              END-IF
      *
      *       And let's check to make sure we only have 0 to 1
      *       decimal points
      *
              MOVE ZERO TO WS-NUM-COUNT-POINT

              INSPECT INTRTI(1:INTRTL) TALLYING
                 WS-NUM-COUNT-POINT for ALL '.'


              IF WS-NUM-COUNT-POINT > 1
                 MOVE SPACES TO MESSAGEO
                 STRING 'Use one decimal point for interest rate only'
                      DELIMITED BY SIZE,
                 INTO MESSAGEO
                 MOVE 'N' TO VALID-DATA-SW
                 MOVE -1 TO INTRTL
                 GO TO ED999
              END-If
      *
      *       Now let's check to see if we have too many decimals!
      *
              IF WS-NUM-COUNT-POINT = 1
                 MOVE ZERO TO WS-NUM-COUNT-TOTAL
                 INSPECT INTRTI(1:INTRTL) TALLYING
                    WS-NUM-COUNT-TOTAL FOR CHARACTERS AFTER '.'

                 IF WS-NUM-COUNT-TOTAL > 2
      *
      *             There are more than 2 characters after the point
      *
                    MOVE ZERO TO WS-NUM-COUNT-TOTAL WS-NUM-COUNT-POINT
                    INSPECT INTRTI(1:INTRTL) TALLYING
                       WS-NUM-COUNT-POINT FOR CHARACTERS BEFORE '.'

                    ADD 2 TO WS-NUM-COUNT-POINT
                       GIVING WS-NUM-COUNT-POINT

                    INSPECT INTRTI(WS-NUM-COUNT-POINT:INTRTL) TALLYING
                       WS-NUM-COUNT-TOTAL FOR ALL '0'
                       WS-NUM-COUNT-TOTAL FOR ALL '1'
                       WS-NUM-COUNT-TOTAL FOR ALL '2'
                       WS-NUM-COUNT-TOTAL FOR ALL '3'
                       WS-NUM-COUNT-TOTAL FOR ALL '4'
                       WS-NUM-COUNT-TOTAL FOR ALL '5'
                       WS-NUM-COUNT-TOTAL FOR ALL '6'
                       WS-NUM-COUNT-TOTAL FOR ALL '7'
                       WS-NUM-COUNT-TOTAL FOR ALL '8'
                       WS-NUM-COUNT-TOTAL FOR ALL '9'
                       WS-NUM-COUNT-TOTAL FOR ALL '-'
                       WS-NUM-COUNT-TOTAL FOR ALL '+'
                       AFTER '.'

                    IF WS-NUM-COUNT-TOTAL > 2
      *
      *                More than two of them are numeric
      *
                       MOVE SPACES TO MESSAGEO
                       STRING
                         'Only up to two decimal places are supported'
                         DELIMITED BY SIZE,
                       INTO MESSAGEO

                       MOVE 'N' TO VALID-DATA-SW
                       MOVE -1 TO INTRTL
                       GO TO ED999
                    END-IF

                 END-IF

              END-IF

           END-IF

           COMPUTE INTRTI-COMP-1 = FUNCTION NUMVAL(INTRTI)

      *
      *    Validate the interest rate
      *
           IF INTRTI-COMP-1 < 0
              MOVE SPACES TO MESSAGEO
              STRING 'Please supply a zero or positive interest rate'
                    DELIMITED BY SIZE,
              INTO MESSAGEO
              MOVE 'N' TO VALID-DATA-SW
              MOVE -1 TO INTRTL
              GO TO ED999
           END-IF

           IF INTRTI-COMP-1 > 9999.99
              MOVE SPACES TO MESSAGEO
              STRING 'Please supply an interest rate less than 9999.99%'
                    DELIMITED BY SIZE,
              INTO MESSAGEO
              MOVE 'N' TO VALID-DATA-SW
              MOVE -1 TO INTRTL
              GO TO ED999
           END-IF
      * Remove trailing spaces from OVERDRAFT
           MOVE FUNCTION REVERSE(OVERDRI) TO WS-REVERSE
           MOVE ZERO TO WS-NUM-COUNT-TOTAL
           INSPECT WS-REVERSE TALLYING WS-NUM-COUNT-TOTAL
           FOR LEADING SPACES
           SUBTRACT WS-NUM-COUNT-TOTAL FROM OVERDRL
             GIVING OVERDRL
           MOVE ZERO TO WS-NUM-COUNT-TOTAL
           INSPECT OVERDRI(1:OVERDRL) TALLYING
              WS-NUM-COUNT-TOTAL FOR ALL '0'
              WS-NUM-COUNT-TOTAL FOR ALL '1'
              WS-NUM-COUNT-TOTAL FOR ALL '2'
              WS-NUM-COUNT-TOTAL FOR ALL '3'
              WS-NUM-COUNT-TOTAL FOR ALL '4'
              WS-NUM-COUNT-TOTAL FOR ALL '5'
              WS-NUM-COUNT-TOTAL FOR ALL '6'
              WS-NUM-COUNT-TOTAL FOR ALL '7'
              WS-NUM-COUNT-TOTAL FOR ALL '8'
              WS-NUM-COUNT-TOTAL FOR ALL '9'.
           IF WS-NUM-COUNT-TOTAL < OVERDRL
              MOVE SPACES TO MESSAGEO
              MOVE 'Overdraft Limit must be numeric positive int' TO
                 MESSAGEO
              MOVE 'N' TO VALID-DATA-SW
              MOVE -1 TO OVERDRL
              GO TO ED999
           END-IF.

           EXEC CICS BIF DEEDIT FIELD(OVERDRI)
           END-EXEC.

      *
      *    If the overdraft limit hasn't been supplied then make it
      *    zero
      *
           IF OVERDRL < 1 OR OVERDRI = '________' or overdri = spaces
              MOVE ZERO TO OVERDRI
           END-IF.

      *
      *    If the overdraft limit is supplied it must be numeric
      *
           IF OVERDRI NOT NUMERIC
              MOVE SPACES TO MESSAGEO
              MOVE 'The Overdraft Limit must be numeric ' TO
                 MESSAGEO
              MOVE 'N' TO VALID-DATA-SW
              MOVE -1 TO OVERDRL
              GO TO ED999
           END-IF.

      *
      *    Check to see if we have all the data we expected
      *
           IF CUSTNOL < 1 OR ACCTYPL < 1
              MOVE SPACES TO MESSAGEO
              MOVE 'Missing expected data.               ' TO
                 MESSAGEO
              MOVE 'N' TO VALID-DATA-SW
              GO TO ED999
           END-IF.

       ED999.
           EXIT.


       CRE-ACC-DATA SECTION.
       CAD010.
      *
      *    Set up the fields required by CREACC then link to it
      *
           INITIALIZE SUBPGM-PARMS.
           MOVE 'ACCT' TO SUBPGM-EYECATCHER.
           MOVE 'N' TO SUBPGM-SUCCESS.

           MOVE CUSTNOI      TO SUBPGM-CUSTNO.
           MOVE ZEROS        TO SUBPGM-SORTCODE.
           MOVE ZEROS        TO SUBPGM-NUMBER.

           MOVE ACCTYPI      TO SUBPGM-ACC-TYPE.

           COMPUTE INTRTI-COMP-1 = FUNCTION NUMVAL(INTRTI)

           MOVE INTRTI-COMP-1 TO SUBPGM-INT-RT.

           MOVE ZEROS        TO SUBPGM-OPENED.
           MOVE OVERDRI      TO SUBPGM-OVERDR-LIM.
           MOVE ZEROS        TO SUBPGM-LAST-STMT-DT.
           MOVE ZEROS        TO SUBPGM-NEXT-STMT-DT.
           MOVE ZEROS        TO SUBPGM-AVAIL-BAL.
           MOVE ZEROS        TO SUBPGM-ACT-BAL.
           MOVE ' '          TO SUBPGM-FAIL-CODE.

           EXEC CICS LINK
              PROGRAM('CREACC')
              COMMAREA(SUBPGM-PARMS)
              RESP(WS-CICS-RESP)
              RESP2(WS-CICS-RESP2)
              SYNCONRETURN
           END-EXEC.

           IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
              INITIALIZE WS-FAIL-INFO
              MOVE 'BNK1CAC - CAD010 - LINK CREACC FAILED    '
                 TO WS-CICS-FAIL-MSG
              MOVE WS-CICS-RESP  TO WS-CICS-RESP-DISP
              MOVE WS-CICS-RESP2 TO WS-CICS-RESP2-DISP
      *
      *       Preserve the RESP and RESP2, then set up the
      *       standard ABEND info before getting the applid,
      *       date/time etc. and linking to the Abend Handler
      *       program.
      *
              INITIALIZE ABNDINFO-REC
              MOVE EIBRESP    TO ABND-RESPCODE
              MOVE EIBRESP2   TO ABND-RESP2CODE
      *
      *       Get supplemental information
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
              MOVE 'HBNK'      TO ABND-CODE

              EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM)
              END-EXEC

              MOVE ZEROS      TO ABND-SQLCODE

              STRING 'CAD010 - LINK CREACC FAILED ' DELIMITED BY SIZE,
                       ' EIBRESP=' DELIMITED BY SIZE,
                       ABND-RESPCODE DELIMITED BY SIZE,
                       ' RESP2=' DELIMITED BY SIZE,
                       ABND-RESP2CODE DELIMITED BY SIZE
                       INTO ABND-FREEFORM
              END-STRING

              EXEC CICS LINK PROGRAM(WS-ABEND-PGM)
                          COMMAREA(ABNDINFO-REC)
              END-EXEC

              PERFORM ABEND-THIS-TASK

           END-IF.

      *
      *    Check to see if the creation was successful or not
      *
           IF SUBPGM-SUCCESS = 'N'
              MOVE SPACES TO MESSAGEO
              MOVE 'N' TO VALID-DATA-SW

              EVALUATE SUBPGM-FAIL-CODE

                 WHEN '1'
                    MOVE 'The supplied customer number does not exist.'
                       TO  MESSAGEO

                 WHEN '2'
                    STRING 'The customer data cannot be accessed, '
                       DELIMITED BY SIZE,
                       ' unable to create account.'
                       DELIMITED BY SIZE
                    INTO MESSAGEO

                 WHEN '3'
                    STRING 'Account record creation failed.'
                       DELIMITED BY SIZE,
                       ' (unable to ENQ ACCOUNT NC).'
                       DELIMITED BY SIZE
                    INTO MESSAGEO

                 WHEN '4'
                    STRING 'Account record creation failed,'
                       DELIMITED BY SIZE,
                       ' (unable to increment ACCOUNT NC).'
                       DELIMITED BY SIZE
                    INTO MESSAGEO

                 WHEN '5'
                    STRING 'Account record creation failed,'
                       DELIMITED BY SIZE,
                       ' (unable to restore ACCOUNT NC).'
                       DELIMITED BY SIZE
                    INTO MESSAGEO

                 WHEN '6'
                    STRING 'Account record creation failed,'
                       DELIMITED BY SIZE,
                       ' (unable to WRITE to ACCOUNT file).'
                       DELIMITED BY SIZE
                    INTO MESSAGEO

                 WHEN '7'
                    STRING 'Account record creation failed,'
                       DELIMITED BY SIZE,
                       ' (unable to INSERT into ACCOUNT).'
                       DELIMITED BY SIZE
                    INTO MESSAGEO

                 WHEN '8'
                    STRING 'Account record creation failed,'
                       DELIMITED BY SIZE,
                       ' (too many accounts).'
                       DELIMITED BY SIZE
                    INTO MESSAGEO

                 WHEN '9'
                    STRING 'Account record creation failed, '
                       DELIMITED BY SIZE,
                       ' unable to count accounts.'
                       DELIMITED BY SIZE
                    INTO MESSAGEO

                 WHEN 'A'
                    STRING 'Account record creation failed, '
                       DELIMITED BY SIZE,
                       ' account type unsupported.'
                       DELIMITED BY SIZE
                    INTO MESSAGEO

                 WHEN OTHER
                    MOVE 'The account was not created.'
                       TO  MESSAGEO

              END-EVALUATE
           ELSE
      *
      *       If the account creation was successful then set
      *       the values on the map
      *
              MOVE SPACES TO MESSAGEO
              MOVE 'The Account has been successfully created' TO
                 MESSAGEO

              MOVE SUBPGM-SORTCODE          TO SRTCDO
              MOVE SUBPGM-NUMBER            TO ACCNOO
              MOVE SUBPGM-OPENED(1:2)       TO OPENDDO
              MOVE SUBPGM-OPENED(3:2)       TO OPENMMO
              MOVE SUBPGM-OPENED(5:4)       TO OPENYYO
              MOVE SUBPGM-NEXT-STMT-DT(1:2) TO NSTMTDDO
              MOVE SUBPGM-NEXT-STMT-DT(3:2) TO NSTMTMMO
              MOVE SUBPGM-NEXT-STMT-DT(5:4) TO NSTMTYYO
              MOVE SUBPGM-LAST-STMT-DT(1:2) TO LSTMDDO
              MOVE SUBPGM-LAST-STMT-DT(3:2) TO LSTMMMO
              MOVE SUBPGM-LAST-STMT-DT(5:4) TO LSTMYYO
              MOVE SUBPGM-AVAIL-BAL         TO AVAILABLE-BALANCE-DISPLAY
              MOVE SUBPGM-ACT-BAL           TO ACTUAL-BALANCE-DISPLAY
              MOVE AVAILABLE-BALANCE-DISPLAY TO AVAILO
              MOVE ACTUAL-BALANCE-DISPLAY   TO ACTBALO
           END-IF.


           MOVE SUBPGM-CUSTNO               TO CUSTNOO.
           MOVE SUBPGM-ACC-TYPE             TO ACCTYPO.
           MOVE SUBPGM-INT-RT               TO INTRT-PIC9.
           MOVE INTRT-PIC9                  TO INTRTO.
           MOVE SUBPGM-OVERDR-LIM           TO OVERDRO.

       CAD999.
           EXIT.


        SEND-MAP SECTION.
        SM010.
      *
      *    If the map needs to have its data erased
      *
           IF SEND-ERASE
              EXEC CICS SEND MAP('BNK1CA')
                 MAPSET('BNK1CAM')
                 FROM(BNK1CAO)
                 ERASE
                 CURSOR
                 RESP(WS-CICS-RESP)
                 RESP2(WS-CICS-RESP2)
              END-EXEC

              IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
                 INITIALIZE WS-FAIL-INFO
                 MOVE 'BNK1CAC - SM010 - SEND MAP ERASE FAIL '
                    TO WS-CICS-FAIL-MSG
                 MOVE WS-CICS-RESP  TO WS-CICS-RESP-DISP
                 MOVE WS-CICS-RESP2 TO WS-CICS-RESP2-DISP
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
                 MOVE 'HBNK'      TO ABND-CODE

                 EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM)
                 END-EXEC

                 MOVE ZEROS      TO ABND-SQLCODE

                 STRING 'SM010 -SEND MAP ERASE FAIL' DELIMITED BY SIZE,
                       ' EIBRESP=' DELIMITED BY SIZE,
                       ABND-RESPCODE DELIMITED BY SIZE,
                       ' RESP2=' DELIMITED BY SIZE,
                       ABND-RESP2CODE DELIMITED BY SIZE
                       INTO ABND-FREEFORM
                 END-STRING

                 EXEC CICS LINK PROGRAM(WS-ABEND-PGM)
                           COMMAREA(ABNDINFO-REC)
                 END-EXEC

                 PERFORM ABEND-THIS-TASK
              END-IF

              GO TO SM999
           END-IF.

      *
      *    If the map just needs a resend of only the data
      *
           IF SEND-DATAONLY
              EXEC CICS SEND MAP('BNK1CA')
                 MAPSET('BNK1CAM')
                 FROM(BNK1CAO)
                 DATAONLY
                 CURSOR
                 RESP(WS-CICS-RESP)
                 RESP2(WS-CICS-RESP2)
              END-EXEC

              IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
                 INITIALIZE WS-FAIL-INFO
                 MOVE 'BNK1CAC - SM010 - SEND MAP DATAONLY FAIL '
                    TO WS-CICS-FAIL-MSG
                 MOVE WS-CICS-RESP  TO WS-CICS-RESP-DISP
                 MOVE WS-CICS-RESP2 TO WS-CICS-RESP2-DISP

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
                 MOVE 'HBNK'      TO ABND-CODE

                 EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM)
                 END-EXEC

                 MOVE ZEROS      TO ABND-SQLCODE

                 STRING 'SM010 - SEND MAP DATAONLY Fail'
                      DELIMITED BY SIZE,
                      ' EIBRESP=' DELIMITED BY SIZE,
                      ABND-RESPCODE DELIMITED BY SIZE,
                      ' RESP2=' DELIMITED BY SIZE,
                      ABND-RESP2CODE DELIMITED BY SIZE
                      INTO ABND-FREEFORM
                 END-STRING

                 EXEC CICS LINK PROGRAM(WS-ABEND-PGM)
                           COMMAREA(ABNDINFO-REC)
                 END-EXEC

                 PERFORM ABEND-THIS-TASK
              END-IF

              GO TO SM999

           END-IF.

      *
      *    If we have elected to send the map and a beep
      *
           IF SEND-DATAONLY-ALARM
              EXEC CICS SEND MAP('BNK1CA')
                 MAPSET('BNK1CAM')
                 FROM(BNK1CAO)
                 DATAONLY
                 ALARM
                 CURSOR
                 RESP(WS-CICS-RESP)
                 RESP2(WS-CICS-RESP2)
              END-EXEC

              IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
                 INITIALIZE WS-FAIL-INFO
                 MOVE 'BNK1CAC - SM010 - SEND MAP DATAONLY ALARM FAIL '
                    TO WS-CICS-FAIL-MSG
                 MOVE WS-CICS-RESP  TO WS-CICS-RESP-DISP
                 MOVE WS-CICS-RESP2 TO WS-CICS-RESP2-DISP
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
                 MOVE 'HBNK'      TO ABND-CODE

                 EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM)
                 END-EXEC

                 MOVE ZEROS      TO ABND-SQLCODE

                 STRING 'SM010 - SEND MAP DATAONLY ALARM fail'
                      DELIMITED BY SIZE,
                      ' EIBRESP=' DELIMITED BY SIZE,
                      ABND-RESPCODE DELIMITED BY SIZE,
                      ' RESP2=' DELIMITED BY SIZE,
                      ABND-RESP2CODE DELIMITED BY SIZE
                      INTO ABND-FREEFORM
                 END-STRING

                 EXEC CICS LINK PROGRAM(WS-ABEND-PGM)
                           COMMAREA(ABNDINFO-REC)
                 END-EXEC

                 PERFORM ABEND-THIS-TASK
              END-IF

           END-IF.

       SM999.
           EXIT.


       SEND-TERMINATION-MSG SECTION.
       STM010.
      *
      *    Send the termination message
      *
           EXEC CICS SEND TEXT
              FROM(END-OF-SESSION-MESSAGE)
              ERASE
              FREEKB
              RESP(WS-CICS-RESP)
              RESP2(WS-CICS-RESP2)
           END-EXEC.

           IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
              INITIALIZE WS-FAIL-INFO
              MOVE 'BNK1CAC - STM010 - SEND TEXT FAIL'
                 TO WS-CICS-FAIL-MSG
              MOVE WS-CICS-RESP  TO WS-CICS-RESP-DISP
              MOVE WS-CICS-RESP2 TO WS-CICS-RESP2-DISP
      *
      *       Preserve the RESP and RESP2, then set up the
      *       standard ABEND info before getting the applid,
      *       date/time etc. and linking to the Abend Handler
      *       program.
      *
              INITIALIZE ABNDINFO-REC
              MOVE EIBRESP    TO ABND-RESPCODE
              MOVE EIBRESP2   TO ABND-RESP2CODE
      *
      *       Get supplemental information
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
              MOVE 'HBNK'      TO ABND-CODE

              EXEC CICS ASSIGN PROGRAM(ABND-PROGRAM)
              END-EXEC

              MOVE ZEROS      TO ABND-SQLCODE

              STRING 'STM010 - SEND TEXT FAIL'
                   DELIMITED BY SIZE,
                   ' EIBRESP=' DELIMITED BY SIZE,
                   ABND-RESPCODE DELIMITED BY SIZE,
                   ' RESP2=' DELIMITED BY SIZE,
                   ABND-RESP2CODE DELIMITED BY SIZE
                   INTO ABND-FREEFORM
              END-STRING

              EXEC CICS LINK PROGRAM(WS-ABEND-PGM)
                           COMMAREA(ABNDINFO-REC)
              END-EXEC

              PERFORM ABEND-THIS-TASK

           END-IF.

       STM999.
           EXIT.


       ABEND-THIS-TASK SECTION.
       ATT010.

           DISPLAY WS-FAIL-INFO.

           EXEC CICS ABEND
              ABCODE('HBNK')
              NODUMP
           END-EXEC.

       ATT999.
           EXIT.


       POPULATE-TIME-DATE SECTION.
       PTD010.

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

