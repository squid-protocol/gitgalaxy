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
      *  GETNAME

      * This program is part of the CICS Credit Card Application example

      * GETNAME - Get the customer name details from the locally
      *           optimised data store.
      * An account number is used to retrieve the full name
      * of the customer. The customer names database is hosted on
      * a different system within the same organisation. It is also
      * evolving over time.
      * Generally responses are near instant, although the service can
      * slow down during peak usage.

      * This example does not call out to any external/other service
      * provider in order to show near instant response times.
      *
      ******************************************************************

       IDENTIFICATION DIVISION.
        PROGRAM-ID. GETNAME.
        AUTHOR. GOHILPR.

       ENVIRONMENT DIVISION.

       DATA DIVISION.
        WORKING-STORAGE SECTION.

      * Input record
       1 ACCOUNT-NUMBER-IN.
         2 CUST-NO-IN PIC X(4).

       1 RETURN-DATA.
         2 CUSTOMER-NAME          PIC X(80) VALUE ' '.

        LOCAL-STORAGE SECTION.

       1 CONTAINER-NAMES.
         2 INPUT-CONTAINER    PIC X(16) VALUE 'INPUTCONTAINER  '.
         2 GETNAME-CONTAINER  PIC X(16) VALUE 'GETNAMECONTAINER'.

       1 PROG-NAMES.
         2 GET-NAME           PIC X(8) VALUE 'GETNAME '.

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

      * "Call" the customer name retrieval service
           IF ACCOUNT-NUMBER-IN = '0001'
           THEN
             MOVE 'PRADEEP GOHIL' TO CUSTOMER-NAME
           ELSE
             MOVE 'JOE BLOGS' TO CUSTOMER-NAME
           END-IF

      * Pass the result back to parent
           EXEC CICS PUT CONTAINER ( GETNAME-CONTAINER )
                           FROM    ( CUSTOMER-NAME )
                           RESP    ( COMMAND-RESP )
                           RESP2   ( COMMAND-RESP2 )
           END-EXEC

      * --------------------------------------------------------------
      * Finished
      * --------------------------------------------------------------
           EXEC CICS RETURN
           END-EXEC.

       END PROGRAM 'GETNAME'.
