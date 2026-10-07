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
      *  GETSPND

      * This program is part of the CICS Credit Card Application example

      * GETSPND - Get the spending figures of the client for the year.
      * An account number is used to calculate the amount the customer
      * has spent with the company over the year.
      * This metric is used to identify how important the customer is.

      * This example executes a 2 second delay to simulate the
      * fetching of data.
      *
      ******************************************************************

       IDENTIFICATION DIVISION.
        PROGRAM-ID. GETSPND.
        AUTHOR. GOHILPR.

       ENVIRONMENT DIVISION.

       DATA DIVISION.
        WORKING-STORAGE SECTION.

        LOCAL-STORAGE SECTION.

        LINKAGE SECTION.


       PROCEDURE DIVISION .

       MAINLINE SECTION.

      * Symbolise the effort with a two second wait

           EXEC CICS DELAY FOR SECONDS(2)
           END-EXEC

      * --------------------------------------------------------------
      * Finished
      * --------------------------------------------------------------
           EXEC CICS RETURN
           END-EXEC.

       END PROGRAM 'GETSPND'.
