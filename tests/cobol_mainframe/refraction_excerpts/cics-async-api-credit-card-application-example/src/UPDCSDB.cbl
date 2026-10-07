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
      *  UPDCSDB

      * This program is part of the CICS Credit Card Application example

      * UPDCSDB - The credit check is stored in a local cache.
      * An account number is used to store the previously returned
      * credit check score in a local database to serve as a quick cache
      * No return data is expected (one way data service)
      *
      * This example executes a 3 second delay to simulate the
      * update to the DB.
      *
      ******************************************************************

       IDENTIFICATION DIVISION.
        PROGRAM-ID. UPDCSDB.
        AUTHOR. GOHILPR.

       ENVIRONMENT DIVISION.

       DATA DIVISION.
        WORKING-STORAGE SECTION.

      * Input record
       1 ACCOUNT-NUMBER-IN.
         2 CUST-NO-IN PIC X(4).

        LOCAL-STORAGE SECTION.

       1 CONTAINER-NAMES.
         2 INPUT-CONTAINER    PIC X(16) VALUE 'INPUTCONTAINER  '.
         2 CRDTCHK-CONTAINER  PIC X(16) VALUE 'CREDITCHECKCONT '.
         2 UPDCSDB-CONTAINER  PIC X(16) VALUE 'UPDATEDB2       '.

       1 PROG-NAMES.
         2 DB-CACHE           PIC X(8) VALUE 'UPDCSDB '.

       1 COMMAND-RESP  PIC S9(8) COMP.
       1 COMMAND-RESP2 PIC S9(8) COMP.

        LINKAGE SECTION.


       PROCEDURE DIVISION .

       MAINLINE SECTION.

      * Time taken to update database
           EXEC CICS DELAY FOR SECONDS(3)
           END-EXEC

      * --------------------------------------------------------------
      * Finished
      * --------------------------------------------------------------
           EXEC CICS RETURN
           END-EXEC.

       END PROGRAM 'UPDCSDB'.
