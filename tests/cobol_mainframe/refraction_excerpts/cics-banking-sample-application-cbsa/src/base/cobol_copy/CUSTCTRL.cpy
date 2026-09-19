      ******************************************************************
      *                                                                *
      *  Copyright IBM Corp. 2023                                      *
      *                                                                *
      *                                                                *
      ******************************************************************
           03 CUSTOMER-CONTROL-RECORD.
              05 CUSTOMER-CONTROL-EYECATCHER             PIC X(4).
                 88 CUSTOMER-CONTROL-EYECATCHER-V        VALUE 'CTRL'.
              05 CUSTOMER-CONTROL-KEY.
                 07 CUSTOMER-CONTROL-SORTCODE        PIC 9(6) DISPLAY.
                 07 CUSTOMER-CONTROL-NUMBER          PIC 9(10) DISPLAY.
              05 NUMBER-OF-CUSTOMERS                 PIC 9(10) DISPLAY.
              05 LAST-CUSTOMER-NUMBER                PIC 9(10) DISPLAY.
              05 CUSTOMER-CONTROL-SUCCESS-FLAG       PIC X.
              88 CUSTOMER-CONTROL-SUCCESS VALUE 'Y'.
              05 CUSTOMER-CONTROL-FAIL-CODE PIC X.
              05 FILLER                              PIC X(38).
              05 FILLER                              PIC X(160).
              05 FILLER                              PIC 9(8).
              05 FILLER                              PIC 999.
              05 FILLER                              PIC 9(8).
