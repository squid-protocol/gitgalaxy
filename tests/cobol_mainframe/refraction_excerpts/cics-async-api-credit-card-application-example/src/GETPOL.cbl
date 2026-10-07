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
      *  GETPOL

      * This program is part of the CICS Credit Card Application example

      * GETPOL - Get currently held policies by the customer.
      * An account number is used to retrieve all of the policies that
      * the customer currently holds with the company.
      * This metric is used to identify how important the customer is.

      * This example executes a 2 second delay to simulate the
      * fetching of all policies.
      * This is a rather conservative figure as our research shows that
      * is real situations, details can be distributed over many
      * departments and systems. Often involving large amounts of data
      * and numerous databases to search.
      *
      ******************************************************************

       IDENTIFICATION DIVISION.
        PROGRAM-ID. GETPOL.
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

       END PROGRAM 'GETPOL'.
