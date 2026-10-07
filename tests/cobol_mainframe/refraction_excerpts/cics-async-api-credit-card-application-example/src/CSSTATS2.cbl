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
      *  CSSTATS2

      * This program is part of the CICS Credit Card Application example

      * CSSTATS2 - Get the importance (status) of the customer.
      * The business metrics used to calculate the importance of the
      * customer are the number of policies currently held
      * by the customer and the amount they have spent with the company
      * over the year.
      *
      * Calls programs GETPOL (get current policies) and
      * GETSPND (get the yearly spend figure), asynchronously.
      *
      ******************************************************************

       IDENTIFICATION DIVISION.
        PROGRAM-ID. CSSTATS2.
        AUTHOR. GOHILPR.

       ENVIRONMENT DIVISION.

       DATA DIVISION.
        WORKING-STORAGE SECTION.

      * Input record
       1 ACCOUNT-NUMBER-IN.
         2 CUST-NO-IN PIC X(4).

       1 RETURN-DATA.
         2 CUSTOMER-IMPORTANCE    PIC X(8)  VALUE '        '.

        LOCAL-STORAGE SECTION.

       1 CONTAINER-NAMES.
         2 INPUT-CONTAINER    PIC X(16) VALUE 'INPUTCONTAINER  '.
         2 CSSTATS2-CONTAINER PIC X(16) VALUE 'GETVIPSTATUS    '.

       1 PROG-NAMES.
         2 GETPOL             PIC X(8) VALUE 'GETPOL  '.
         2 GETSPND            PIC X(8) VALUE 'GETSPND '.

       1 COMMAND-RESP  PIC S9(8) COMP.
       1 COMMAND-RESP2 PIC S9(8) COMP.

       1 TRANSIDS.
         2 GET-POLICY-TRAN    PIC X(4) VALUE 'GETP'.
         2 GET-SPEND-TRAN     PIC X(4) VALUE 'SPND'.

       1 CHILD-TOKENS.
         2 GET-POLICY-TKN     PIC X(16).
         2 GET-SPEND-TKN      PIC X(16).
        LINKAGE SECTION.


       PROCEDURE DIVISION .

       MAINLINE SECTION.

      * Get the input account number

           EXEC CICS GET CONTAINER ( INPUT-CONTAINER )
                           INTO    ( ACCOUNT-NUMBER-IN )
                           RESP    ( COMMAND-RESP )
                           RESP2   ( COMMAND-RESP2 )
           END-EXEC

      * The status is calculated by the existing custom of the client
      * and the amount they spent with us in the previous year
           EXEC CICS RUN TRANSID      (GET-POLICY-TRAN)
                         CHILD        (GET-POLICY-TKN)
           END-EXEC
           EXEC CICS RUN TRANSID      (GET-SPEND-TRAN)
                         CHILD        (GET-SPEND-TKN)
           END-EXEC

      * Algorithm to "calculate" status
           IF ACCOUNT-NUMBER-IN = '0001'
           THEN
             MOVE 'VERY VIP' TO CUSTOMER-IMPORTANCE
           ELSE
             MOVE 'REGULAR ' TO CUSTOMER-IMPORTANCE
           END-IF

      * Pass the result back to parent
           EXEC CICS PUT CONTAINER ( CSSTATS2-CONTAINER )
                           FROM    ( CUSTOMER-IMPORTANCE )
                           RESP    ( COMMAND-RESP )
                           RESP2   ( COMMAND-RESP2 )
           END-EXEC

      * --------------------------------------------------------------
      * Finished
      * --------------------------------------------------------------
           EXEC CICS RETURN
           END-EXEC.

       END PROGRAM 'CSSTATS2'.
