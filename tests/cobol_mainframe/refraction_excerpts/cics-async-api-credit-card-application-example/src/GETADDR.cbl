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
      *  GETADDR

      * This program is part of the CICS Credit Card Application example

      * GETADDR - Get the postal address for the customer.
      * An account number is used to retrieve the address for the client
      * as stored locally. The address is then used to call an external
      * address service, via web service, to retrieve a verified and
      * canonicalised address and postcode/zipcode.

      * This example executes a 5 second delay to simulate
      * the fetching of a canonicalised address.
      *
      ******************************************************************

       IDENTIFICATION DIVISION.
        PROGRAM-ID. GETADDR.
        AUTHOR. GOHILPR.

       ENVIRONMENT DIVISION.

       DATA DIVISION.
        WORKING-STORAGE SECTION.

      * Input record
       1 ACCOUNT-NUMBER-IN.
         2 CUST-NO-IN PIC X(4).

       1 RETURN-DATA.
         2 CUSTOMER-ADDRESS       PIC X(80) VALUE ' '.
         2 CUSTOMER-POSTCODE      PIC X(8)  VALUE ' '.

        LOCAL-STORAGE SECTION.

       1 CONTAINER-NAMES.
         2 INPUT-CONTAINER    PIC X(16) VALUE 'INPUTCONTAINER  '.
         2 GETADDR-CONTAINER  PIC X(16) VALUE 'GETADDRCONTAINER'.
         2 GETPOST-CONTAINER  PIC X(16) VALUE 'GETPOSTCODE     '.

       1 PROG-NAMES.
         2 GET-ADDR           PIC X(8) VALUE 'GETADDR '.

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

      * "Call" the credit check service
           IF ACCOUNT-NUMBER-IN = '0001'
           THEN
             MOVE '1 HURSLEY PARK, WINCHESTER, UK' TO CUSTOMER-ADDRESS
             MOVE 'SO21 2JN'                       TO CUSTOMER-POSTCODE
           ELSE
             MOVE '123 HIGH STREET, LONDON, UK'    TO CUSTOMER-ADDRESS
             MOVE 'S14 4WG'                        TO CUSTOMER-POSTCODE
           END-IF

      * Symbolic delay to cover
      * the time it takes to call external services
      * to validate and standadise the address
           EXEC CICS DELAY FOR SECONDS(5)
           END-EXEC

      * Pass the result back to parent
           EXEC CICS PUT CONTAINER ( GETADDR-CONTAINER )
                           FROM    ( CUSTOMER-ADDRESS )
                           RESP    ( COMMAND-RESP )
                           RESP2   ( COMMAND-RESP2 )
           END-EXEC
           EXEC CICS PUT CONTAINER ( GETPOST-CONTAINER )
                           FROM    ( CUSTOMER-POSTCODE )
                           RESP    ( COMMAND-RESP )
                           RESP2   ( COMMAND-RESP2 )
           END-EXEC
      * --------------------------------------------------------------
      * Finished
      * --------------------------------------------------------------
           EXEC CICS RETURN
           END-EXEC.

       END PROGRAM 'GETADDR'.
