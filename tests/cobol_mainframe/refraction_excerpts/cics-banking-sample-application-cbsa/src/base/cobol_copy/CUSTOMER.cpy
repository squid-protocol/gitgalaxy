      ******************************************************************
      *                                                                *
      *  Copyright IBM Corp. 2023                                      *
      *                                                                
      *                                                                *
      ******************************************************************
           03 CUSTOMER-RECORD.
              05 CUSTOMER-EYECATCHER                 PIC X(4).
                 88 CUSTOMER-EYECATCHER-VALUE        VALUE 'CUST'.
              05 CUSTOMER-KEY.
                 07 CUSTOMER-SORTCODE                PIC 9(6) DISPLAY.
                 07 CUSTOMER-NUMBER                  PIC 9(10) DISPLAY.
              05 CUSTOMER-NAME                       PIC X(60).
      *          07 CUSTOMER-TITLE                   PIC X(8).
      *          07 CUSTOMER-GIVEN-NAME              PIC X(20).
      *          07 CUSTOMER-INITIALS                PIC X(10).
      *          07 CUSTOMER-FAMILY-NAME             PIC X(20).
              05 CUSTOMER-ADDRESS                    PIC X(160).
      *          07 CUSTOMER-STREET-ADDRESS          PIC X(50).
      *          07 CUSTOMER-ADDRESS-DISTRICT        PIC X(50).
      *          07 CUSTOMER-ADDRESS-TOWN            PIC X(50).
      *          07 CUSTOMER-POSTCODE-OR-ZIP         PIC X(10).
              05 CUSTOMER-DATE-OF-BIRTH              PIC 9(8).
              05 CUSTOMER-DOB-GROUP REDEFINES CUSTOMER-DATE-OF-BIRTH.
                 07 CUSTOMER-BIRTH-DAY               PIC 99.
                 07 CUSTOMER-BIRTH-MONTH             PIC 99.
                 07 CUSTOMER-BIRTH-YEAR              PIC 9999.
              05 CUSTOMER-CREDIT-SCORE               PIC 999.
              05 CUSTOMER-CS-REVIEW-DATE             PIC 9(8).
              05 CUSTOMER-CS-GROUP
                 REDEFINES CUSTOMER-CS-REVIEW-DATE.
                 07 CUSTOMER-CS-REVIEW-DAY           PIC 99.
                 07 CUSTOMER-CS-REVIEW-MONTH         PIC 99.
                 07 CUSTOMER-CS-REVIEW-YEAR          PIC 9999.
