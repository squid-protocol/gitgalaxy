      ******************************************************************
      *                                                                *
      *  Copyright IBM Corp. 2023                                      *
      *                                                                *
      *                                                                *
      ******************************************************************
              03 ACCOUNT-CONTROL-RECORD.
                 05 ACCOUNT-CONTROL-EYE-CATCHER        PIC X(4).
                 88 ACCOUNT-CONTROL-EYECATCHER-V   VALUE 'CTRL'.
                 05 FILLER                     PIC 9(10).
                 05 ACCOUNT-CONTROL-KEY.
                    07 ACCOUNT-CONTROL-SORT-CODE       PIC 9(6).
                    07 ACCOUNT-CONTROL-NUMBER          PIC 9(8).
                 05 NUMBER-OF-ACCOUNTS                 PIC 9(8).
                 05 LAST-ACCOUNT-NUMBER                PIC 9(8).
                 05 ACCOUNT-CONTROL-SUCCESS-FLAG       PIC X.
                 88 ACCOUNT-CONTROL-SUCCESS VALUE 'Y'.
                 05 ACCOUNT-CONTROL-FAIL-CODE PIC X.
                 05 FILLER                     PIC 9(4)V99.
                 05 FILLER                     PIC 9(8).
                 05 FILLER                     PIC 9(8).
                 05 FILLER                     PIC 9(8).
                 05 FILLER                     PIC 9(8).
                 05 FILLER                     PIC S9(10)V99.
                 05 FILLER                     PIC X(2).
