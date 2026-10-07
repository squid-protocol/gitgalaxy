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
      *  CSSTATUS

      * This program is part of the CICS Credit Card Application example

      * CSSTATUS - Get the importance (status) of the customer.
      * The business metrics used to calculate the importance of the
      * customer are the number of policies currently held
      * by the customer and the amount they have spent with the company
      * over the year.
      *
      * Calls programs GETPOL (get current policies) and
      * GETSPND (get the yearly spend figure), sequentially.
      *
      ******************************************************************

       IDENTIFICATION DIVISION.
        PROGRAM-ID. CSSTATUS.
        AUTHOR. GOHILPR.

       ENVIRONMENT DIVISION.

       DATA DIVISION.
        WORKING-STORAGE SECTION.

      * Input record
       1 ACCOUNT-NUMBER-IN.
         2 CUST-NO-IN PIC X(4).

       1 RETURN-DATA.
         2 CUSTOMER-IMPORTANCE    PIC X(8)  VALUE ' '.

        LOCAL-STORAGE SECTION.

       1 OK                 PIC S9(8) COMP.

       1 CONTAINER-NAMES.
         2 INPUT-CONTAINER    PIC X(16) VALUE 'INPUTCONTAINER  '.
         2 CSSTATUS-CONTAINER PIC X(16) VALUE 'GETVIPSTATUS    '.

       1 PROG-NAMES.
         2 GETPOL             PIC X(8) VALUE 'GETPOL  '.
         2 GETSPND            PIC X(8) VALUE 'GETSPND '.

       1 COMMAND-RESP  PIC S9(8) COMP.
       1 COMMAND-RESP2 PIC S9(8) COMP.

        LINKAGE SECTION.


       PROCEDURE DIVISION .

       MAINLINE SECTION.

      * Get the input account number

           EXEC CICS GET CONTAINER (INPUT-CONTAINER)
                           INTO    ( ACCOUNT-NUMBER-IN )
                           RESP    ( COMMAND-RESP )
                           RESP2   ( COMMAND-RESP2 )
           END-EXEC

      * The status is calculated by the existing custom of the client
      * and the amount they spent with us in the previous year
           EXEC CICS LINK PROGRAM(GETPOL)
           END-EXEC

           EXEC CICS LINK PROGRAM(GETSPND)
           END-EXEC


      * Algorithm to "calculate" status
           IF ACCOUNT-NUMBER-IN = '0001'
           THEN
             MOVE 'VERY VIP' TO CUSTOMER-IMPORTANCE
           ELSE
             MOVE 'REGULAR ' TO CUSTOMER-IMPORTANCE
           END-IF

      * Pass the result back to parent
           EXEC CICS PUT CONTAINER ( CSSTATUS-CONTAINER )
                           FROM    ( CUSTOMER-IMPORTANCE )
                           RESP    ( COMMAND-RESP )
                           RESP2   ( COMMAND-RESP2 )
           END-EXEC

      * --------------------------------------------------------------
      * Finished
      * --------------------------------------------------------------
           EXEC CICS RETURN
           END-EXEC.

       END PROGRAM 'CSSTATUS'.
