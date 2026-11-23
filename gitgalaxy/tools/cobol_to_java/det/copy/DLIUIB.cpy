      * DLIUIB stand-in (GitGalaxy-written, NOT IBM's member).
      * The CICS-DL/I user interface block, as published in IBM IMS 15.4
      * Application Programming, "Defining the UIB, PCB address list, and
      * the PCB mask" (COBOL COPY DLIUIB example). Field names, PIC and
      * USAGE only. The condition values are the hexadecimal values that
      * section lists (FCNORESP X'00' ... DLINA X'FF'). Used only where the
      * estate has no DLIUIB of its own.
       01  DLIUIB.
           02  UIBPCBAL PIC S9(8) COMP.
           02  UIBRCODE.
               03  UIBFCTR PIC X.
                   88  FCNORESP  VALUE X'00'.
                   88  FCNOTOPEN VALUE X'0C'.
                   88  FCINVREQ  VALUE X'08'.
                   88  FCINVPCB  VALUE X'10'.
               03  UIBDLTR PIC X.
                   88  DLPSBNF   VALUE X'01'.
                   88  DLTASKNA  VALUE X'02'.
                   88  DLPSBSCH  VALUE X'03'.
                   88  DLLANGCON VALUE X'04'.
                   88  DLPSBFAIL VALUE X'05'.
                   88  DLPSBNA   VALUE X'06'.
                   88  DLTERMNS  VALUE X'07'.
                   88  DLFUNCNS  VALUE X'08'.
                   88  DLINA     VALUE X'FF'.
