       PROCESS CICS,NODYNAM,NSYMBOL(NATIONAL),TRUNC(STD)
      * Licensed Materials - Property of IBM
      *
      * SAMPLE
      *
      * (c) Copyright IBM Corp. 2016 All Rights Reserved
      *
      * US Government Users Restricted Rights - Use, duplication or
      * disclosure restricted by GSA ADP Schedule Contract with IBM Corp
      *
      ******************************************************************
      *  CRDTCHK

      * This program is part of the CICS Credit Card Application example

      * CRDTCHK - Credit check for an account. An account number
      * is used to call an external credit check service which returns
      * a three digit crdit score.

      * This example executes a 5 second delay to simulate
      * a credit check being made via a web service to
      * an external service provider.
      *
      ******************************************************************

       IDENTIFICATION DIVISION.
        PROGRAM-ID. CRDTCHK.
        AUTHOR. GOHILPR.

       ENVIRONMENT DIVISION.

       DATA DIVISION.
        WORKING-STORAGE SECTION.

      * Input record
       1 ACCOUNT-NUMBER-IN.
         2 CUST-NO-IN PIC X(4).

       1 RETURN-DATA.
         2 CREDIT-CHECK-RESULT    PIC X(3)  VALUE '   '.

        LOCAL-STORAGE SECTION.

       1 CONTAINER-NAMES.
         2 INPUT-CONTAINER    PIC X(16) VALUE 'INPUTCONTAINER  '.
         2 CRDTCHK-CONTAINER  PIC X(16) VALUE 'CREDITCHECKCONT '.

       1 PROG-NAMES.
         2 CREDIT-CHECK       PIC X(8) VALUE 'CRDTCHK '.

       1 COMMAND-RESP  PIC S9(8) COMP.
       1 COMMAND-RESP2 PIC S9(8) COMP.

        LINKAGE SECTION.


       PROCEDURE DIVISION .

       MAINLINE SECTION.

      * Get the input account number

           EXEC CICS GET CONTAINER ( INPUT-CONTAINER )
                           INTO    ( ACCOUNT-NUMBER-IN )
                           RESP    ( COMMAND-RESP )
                           RESP2   ( COMMAND-RESP2 )
           END-EXEC

      * "Call" the credit check service
           IF ACCOUNT-NUMBER-IN = '0001'
           THEN
             MOVE '998' TO CREDIT-CHECK-RESULT
           ELSE
             MOVE '537' TO CREDIT-CHECK-RESULT
           END-IF

           EXEC CICS DELAY FOR SECONDS(5)
           END-EXEC

      * Pass the result back to parent
           EXEC CICS PUT CONTAINER ( CRDTCHK-CONTAINER )
                           FROM    ( CREDIT-CHECK-RESULT )
                           RESP    ( COMMAND-RESP )
                           RESP2   ( COMMAND-RESP2 )
           END-EXEC

      * --------------------------------------------------------------
      * Finished
      * --------------------------------------------------------------
           EXEC CICS RETURN
           END-EXEC.

       END PROGRAM 'CRDTCHK'.
