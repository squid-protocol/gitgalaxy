      ******************************************************************
      * Copyright 2014 IBM Corp. All Rights Reserved.
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
      *                    Patient Add Prescription Menu               *
      *                                                                *
      *                                                                *
      *                                                LGTESTP1        *
      *                                                                *
      *                                                                *
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HCMAPL01.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
      *
       DATA DIVISION.
       WORKING-STORAGE SECTION.

       77 MSGEND                       PIC X(24) VALUE
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

           Initialize HCMAMAPI.
           Initialize HCMAMAPO.
           Initialize COMM-AREA.
           Move LOW-VALUES To HCMACNOI.
           Move SPACES to CA-REQUEST-ID.
           Move 0 to CA-RETURN-CODE.
           Move 0 to CA-PATIENT-ID.
           Move -1 To HCMACNOL.
      *
      * Display screen
           EXEC CICS SEND MAP ('HCMAMAP')
                     MAPSET ('HCMAPS')
                     ERASE
                     CURSOR
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

           EXEC CICS RECEIVE MAP('HCMAMAP')
                     INTO(HCMAMAPI) ASIS TERMINAL
                     MAPSET('HCMAPS') END-EXEC.

           IF HCMADNAMO EQUAL ZEROS OR SPACES OR LOW-VALUES
              PERFORM GET-PATIENT
              Move 'Enter medication information'
                  To  HCMAMSGO
           ELSE
              Move '01AMED'          To CA-REQUEST-ID
              Move HCMACNOI          To CA-PATIENT-ID

              MOVE HCMADNAMI TO CA-DRUG-NAME
              MOVE HCMADSTRI TO CA-STRENGTH
              MOVE HCMADAMOI TO CA-AMOUNT
              MOVE HCMADROUI TO CA-ROUTE
              MOVE HCMADFREI TO CA-FREQUENCY OF CA-MEDICATION-REQUEST
              MOVE HCMAIDENI TO CA-IDENTIFIER
              MOVE HCMATYPEI TO CA-BIOMED-TYPE
              MOVE HCMASDTAI TO CA-START-DATE
              MOVE HCMAEDTAI TO CA-END-DATE

      * Link to business logic for adding medication
              EXEC CICS LINK PROGRAM('HCMABA01')
                        COMMAREA(COMM-AREA)
                        LENGTH(32500)
              END-EXEC
              IF CA-RETURN-CODE > 0
                 Exec CICS Syncpoint Rollback End-Exec
                 GO TO NO-ADD
              END-IF

              Move 'New medication added'
                  To  HCMAMSGO
           END-IF

           Move -1 To HCMADNAML
           EXEC CICS SEND MAP ('HCMAMAP')
                     FROM(HCMAMAPO)
                     MAPSET ('HCMAPS')
                     CURSOR
           END-EXEC
           GO TO ENDIT-STARTIT

      *    Send message to terminal and return

           EXEC CICS RETURN
           END-EXEC.

       ENDIT-STARTIT.
           EXEC CICS RETURN
                TRANSID('HCMA')
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

       CANCELIT.

           EXEC CICS RETURN
                TRANSID('HCAZ')
                IMMEDIATE
                END-EXEC.

       GET-PATIENT.
      * Get patient name
           Move '01IPAT'   To CA-REQUEST-ID
           Move HCMACNOO   To CA-PATIENT-ID
      * Link to business logic for inquire patient
           EXEC CICS LINK PROGRAM('HCP1BI01')
                     COMMAREA(COMM-AREA)
                     LENGTH(32500)
           END-EXEC

           IF CA-RETURN-CODE > 0
              GO TO NO-PATIENT-DATA
           END-IF

           Move CA-FIRST-NAME to HCMAFNAI
           Move CA-LAST-NAME  to HCMALNAI.

       CLEARIT.

           Initialize HCMAMAPI.
           EXEC CICS SEND MAP ('HCMAMAP')
                     MAPSET ('HCMAPS')
                     MAPONLY
           END-EXEC

           EXEC CICS RETURN
                TRANSID('HCMA')
                COMMAREA(COMM-AREA)
                END-EXEC.

       NO-ADD.
           Evaluate CA-RETURN-CODE
             When 70
               Move 'Patient does not exist'          To  HCMAMSGO
               Go To ERROR-OUT
             When Other
               Move 'Error Adding Medication'        To  HCMAMSGO
               Go To ERROR-OUT
           End-Evaluate.

       NO-UPD.
           Move 'Error Updating Medication'    To  HCMAMSGO
           Go To ERROR-OUT.

       NO-DELETE.
           Move 'Error Deleting Medication'    To  HCMAMSGO
           Go To ERROR-OUT.

       NO-PATIENT-DATA.
           Move 'No patient data was returned.'  To  HCMAMSGO
           Go To ERROR-OUT.

       NO-MED-DATA.
           Move 'No medication data was returned.' To  HCMAMSGO
           Go To ERROR-OUT.

       ERROR-OUT.
           EXEC CICS SEND MAP ('HCMAMAP')
                     FROM(HCMAMAPO)
                     MAPSET ('HCMAPS')
                     CURSOR
           END-EXEC.

           Initialize HCMAMAPI.
           Initialize HCMAMAPO.
      *    Initialize COMM-AREA.

           GO TO ENDIT-STARTIT.