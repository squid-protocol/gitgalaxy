      * The SQL descriptor area as EXEC SQL INCLUDE SQLDA declares it in
      * COBOL (IBM Db2 for z/OS, "SQLDA"): a header and SQLN SQLVAR
      * entries. Declared only -- dynamic SQL (PREPARE / DESCRIBE /
      * EXECUTE) that would fill it is refused by name.
       01  SQLDA.
           05 SQLDAID     PIC X(8).
           05 SQLDABC     PIC S9(9) COMP-5.
           05 SQLN        PIC S9(4) COMP-5.
           05 SQLD        PIC S9(4) COMP-5.
           05 SQLVAR OCCURS 1 TO 750 TIMES DEPENDING ON SQLN.
              10 SQLTYPE  PIC S9(4) COMP-5.
              10 SQLLEN   PIC S9(4) COMP-5.
              10 SQLDATA  USAGE POINTER.
              10 SQLIND   USAGE POINTER.
              10 SQLNAME.
                 49 SQLNAMEL PIC S9(4) COMP-5.
                 49 SQLNAMEC PIC X(30).
