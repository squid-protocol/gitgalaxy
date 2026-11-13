      ******************************************************************
      * Copyright 2011,2014 IBM Corp. All Rights Reserved.
      *
      * Licensed under the Apache License, Version 2.0 (the "License");
      * you may not use this file except in compliance with the License.
      * You may obtain a copy of the License at
      * http://www.apache.org/licenses/LICENSE-2.0
      *
      * Unless required by applicable law or agreed to in writing,
      * software distributed under the License is distributed on an
      * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
      * either express or implied.
      * See the License for the specific language governing permissions
      * and limitations under the License.
      ******************************************************************

      *                                                                *
      *                    Patient Visit menu                          *
      *                                                                *
      * Menu for Patient transactions                                  *
      *                                                                *
      *                                                                *
      *                                                                *
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HCV1PL01.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
      *
       DATA DIVISION.
       WORKING-STORAGE SECTION.

       01  WS-RESP                   PIC S9(8) COMP.

       77 INQ-TRANS                    PIC X(4) VALUE 'HCV1'.
       77 ADD-TRANS                    PIC X(4) VALUE 'HCVA'.

       77 MSGEND                     PIC X(24) VALUE
                                        'Transaction ended      '.

        COPY HCMAPS.
        01 COMM-AREA.
        COPY HCCMAREA.

      *----------------------------------------------------------------*
      *****************************************************************
       PROCEDURE DIVISION.

      *---------------------------------------------------------------*
       MAINLINE SECTION.

           IF EIBCALEN > 0
              GO TO A-GAIN.

           Initialize HCV1MAPI.
           Initialize HCV1MAPO.
           Initialize COMM-AREA.
           MOVE LOW-VALUES To HCV1PNOO.

           MOVE -1 TO HCV1PNOL

           PERFORM SETUP-SCREEN.

      * Display appropriate screen
           EXEC CICS SEND MAP ('HCV1MAP')
                     FROM(HCV1MAPO)
                     MAPSET ('HCMAPS')
                     ERASE
                     CURSOR
                     RESP(WS-RESP)
                     END-EXEC.

        A-GAIN.

           EXEC CICS HANDLE AID
                     CLEAR(CLEARIT)
                     PF3(ENDIT)
                     PF12(CANCELIT)
                     END-EXEC.
           EXEC CICS HANDLE CONDITION
                     MAPFAIL(ENDIT)
                     END-EXEC.

           EXEC CICS RECEIVE MAP('HCV1MAP')
                     INTO(HCV1MAPI) ASIS TERMINAL
                     MAPSET('HCMAPS') END-EXEC.

           PERFORM GET-PATIENT.

           PERFORM GET-THRESHOLD.

      * Get patient visit data
           IF (HCV1DATEI EQUAL ZEROS OR SPACES OR LOW-VALUES) OR
              (HCV1TIMEI EQUAL ZEROS OR SPACES OR LOW-VALUES)
                 Move 'Enter visit date and time'
                       To  HCV1MSGO
                 MOVE -1 TO HCV1DATEL
           ELSE
      * Handle the Inquiry request
              IF EIBTRNID EQUAL INQ-TRANS
                 Move '01IVIS'   To CA-REQUEST-ID
                 Move HCV1PNOI   To CA-PATIENT-ID
                 Move HCV1DATEI  To CA-VISIT-DATE
                 Move HCV1TIMEI  To CA-VISIT-TIME

                 EXEC CICS LINK PROGRAM('HCV1BI01')
                        COMMAREA(COMM-AREA)
                        LENGTH(32500)
                 END-EXEC

                 IF CA-RETURN-CODE <= 1
                    Move CA-HEART-RATE     to HCV1HRATEI
                    Move CA-BLOOD-PRESSURE to HCV1BLPRI
      *             Move SPACES   to HCV1MSTATEI
                 END-IF
              ELSE
      * Handle the Add request
                 IF EIBTRNID EQUAL ADD-TRANS
                    Move '01AVIS'   To CA-REQUEST-ID
                    Move HCV1DATEI  To CA-VISIT-DATE
                    Move HCV1TIMEI  To CA-VISIT-TIME
                    Move HCV1HRATEI To CA-HEART-RATE
                    Move HCV1BLPRI  To CA-BLOOD-PRESSURE
      *             Move HCV1MSTATEI To CA-MENTAL-STATE

                    EXEC CICS LINK PROGRAM('HCV1BA01')
                              COMMAREA(COMM-AREA)
                             LENGTH(32500)
                    END-EXEC
                    IF CA-RETURN-CODE > 0
                       Exec CICS Syncpoint Rollback End-Exec
                       GO TO NO-ADD
                    END-IF

                    Move CA-PATIENT-ID   To HCV1PNOI
                    Move 'New Patient Visit Inserted'
                      To  HCV1MSGO

                 END-IF
              END-IF
           END-IF

           PERFORM SETUP-SCREEN.

           EXEC CICS SEND MAP ('HCV1MAP')
                     FROM(HCV1MAPO)
                     MAPSET ('HCMAPS')
                     CURSOR
           END-EXEC
           GO TO ENDIT-STARTIT.

      *          Move '01UVIS'   To CA-REQUEST-ID
      *          Move HCV1CNOI   To CA-PATIENT-ID
      *
      *          IF HCV1DATEI > SPACES
      *                Move HCV1HRATEI  to CA-HEART-RATE
      *                Move HCV1BLPRI   to CA-BLOOD-PRESSURE
      *                Move HCV1MSTATEI to CA-MENTAL-STATE
      *
      *                EXEC CICS LINK PROGRAM('HCV1BU01')
      *                    COMMAREA(COMM-AREA)
      *                    LENGTH(32500)
      *                END-EXEC
      *          ELSE
      *             Move HCV1HRTHI  to CA-HR-THRESHOLD
      *             Move HCV1BPTHI  to CA-BP-THRESHOLD
      *             Move HCV1MSTHI  to CA-MS-THRESHOLD
      *
      *             EXEC CICS LINK PROGRAM('HCT1BU01')
      *                  COMMAREA(COMM-AREA)
      *                  LENGTH(32500)
      *             END-EXEC
      *          END-IF
      *
      *          IF CA-RETURN-CODE > 0
      *            GO TO NO-UPD
      *          END-IF
      *
      *          Move CA-PATIENT-ID   To HCV1CNOI
      *          Move ' '             To HCV1OPTI
      *          IF HCV1DATEI > SPACES
      *             Move 'Patient visit details updated'
      *                  To  HCV1MSGO
      *          ELSE
      *             Move 'Patient threshold details updated'
      *                  To  HCV1MSGO
      *          END-IF
      *          EXEC CICS SEND MAP ('HCV1MAP')
      *                    FROM(HCV1MAPO)
      *                    MAPSET ('HCMAPS')
      *          END-EXEC
      *          GO TO ENDIT-STARTIT

      *    Send message to terminal and return

           EXEC CICS RETURN
           END-EXEC.

       ENDIT-STARTIT.
           EXEC CICS RETURN
                TRANSID(EIBTRNID)
                COMMAREA(COMM-AREA)
                END-EXEC.

       ENDIT.
           EXEC CICS SEND TEXT
                     FROM(MSGEND)
                     LENGTH(LENGTH OF MSGEND)
                     ERASE
                     FREEKB
           END-EXEC
           EXEC CICS RETURN
           END-EXEC.

       CLEARIT.

           Initialize HCV1MAPI.
           EXEC CICS SEND MAP ('HCV1MAP')
                     MAPSET ('HCMAPS')
                     MAPONLY
           END-EXEC

           EXEC CICS RETURN
                TRANSID(EIBTRNID)
                COMMAREA(COMM-AREA)
                END-EXEC.

       CANCELIT.

           EXEC CICS RETURN
                TRANSID('HCAZ')
                IMMEDIATE
                END-EXEC.

       SETUP-SCREEN.
      * Determine appropriate heading
           IF EIBTRNID EQUAL INQ-TRANS
              MOVE INQ-TRANS TO HCV1TRNO
              MOVE 'Inquire Visit Information' to HCV1TITO
           ELSE
           IF EIBTRNID EQUAL ADD-TRANS
              MOVE ADD-TRANS TO HCV1TRNO
              MOVE 'Add Visit Information' to HCV1TITO
           END-IF.

       GET-PATIENT.
      * Get patient name
           Move '01IPAT'   To CA-REQUEST-ID
           Move HCV1PNOI   To CA-PATIENT-ID
           EXEC CICS LINK PROGRAM('HCP1BI01')
                     COMMAREA(COMM-AREA)
                     LENGTH(32500)
           END-EXEC

           IF CA-RETURN-CODE > 0
              GO TO NO-PATIENT-DATA
           END-IF

           Move CA-FIRST-NAME to HCV1FNAI
           Move CA-LAST-NAME  to HCV1LNAI.

       GET-THRESHOLD.
      * Get patient threshold data
           Move '01ITHR'   To CA-REQUEST-ID
           Move HCV1PNOO   To CA-PATIENT-ID
           EXEC CICS LINK PROGRAM('HCT1BI01')
                     COMMAREA(COMM-AREA)
                     LENGTH(32500)
           END-EXEC

           IF CA-RETURN-CODE = 0
              Move CA-HR-THRESHOLD to HCV1HRTHI
              Move CA-BP-THRESHOLD to HCV1BPTHI
      *       Move CA-MS-THRESHOLD to HCV1MSTHI
           END-IF.

       NO-UPD.
           Move 'Error Updating Patient visit'    To  HCV1MSGO.
           Go To ERROR-OUT.

       NO-ADD.
           Move 'Error Adding Patient visit'      To  HCV1MSGO.
           Go To ERROR-OUT.

       NO-DATA.
           Move 'No data was returned.'           To  HCV1MSGO.
           Go To ERROR-OUT.

       NO-PATIENT-DATA.
           Move 'No patient data was returned.'  To  HCV1MSGO
           Go To ERROR-OUT.

       ERROR-OUT.
           EXEC CICS SEND MAP ('HCV1MAP')
                     FROM(HCV1MAPO)
                     CURSOR
                     MAPSET ('HCMAPS')
           END-EXEC.

           Initialize HCV1MAPI.
           Initialize HCV1MAPO.
           Initialize COMM-AREA.

           GO TO ENDIT-STARTIT.
           EXIT.