*
*  PROGRAM:    ZECSNC
*  AUTHOR:     Randy Frerking and Rich Jackson.
*  COMMENTS:   z/OS Enterprise Caching Services.
*
*              Create zECS 'named counter' for a specific table.
*              The 'named counter' is used to create the internal key
*              for the file/data store within zECS.
*
*              This program can be executed from another program via
*              LINK command for from the terminal using the following
*              format:
*
*              Tran,XXXX    Where 'xxxx' is the zECS transaction ID
*
*              This program will also start the expiration task for
*              the zECS service, which will be started in only the
*              current region/server.  The PLT program ZECSPLT will
*              start the expiration process across all servers within
*              a Sysplex.
*
***********************************************************************
* Dynamic Storage Area (Start)                                        *
***********************************************************************
DFHEISTG DSECT
ABSTIME  DS    D                  Absolute time
         DS   0F
APPLID   DS    CL08               CICS/VTAM APPLID
         DS   0F
SYSID    DS    CL04               CICS SYSID
         DS   0F
STCODE   DS    CL02               Transaction start code
         DS   0F
USERID   DS    CL08               UserID
         DS   0F
Z_EXP    DS    CL04               zECS   Expiration TransID
         DS   0F
Z_NC     DS   0CL16               zECS   Named Counter
Z_TRAN   DS    CL04               zECS   Service TransID
Z_SUFFIX DS    CL12               _zECS
         DS   0F
BAS_REG  DS    F                  Return register
         DS   0F
*
TC_LEN   DS    H                  Terminal input length
*
         DS   0F
TC_DATA  DS   0CL09               TC input
TC_ZCNC  DS    CL04               CICS transaction ID
         DS    CL01               comma
TC_TRAN  DS    CL04               zECS   transaction ID
TC_L     EQU   *-TC_DATA
*
WTO_LEN  DS    F                  WTO length
TD_LEN   DS    H                  Transient Data message length
*
         DS   0F
TD_DATA  DS   0CL74               TD/WTO output
TD_DATE  DS    CL10
         DS    CL01
TD_TIME  DS    CL08
         DS    CL01
TD_TRAN  DS    CL04
         DS    CL50
TD_L     EQU   *-TD_DATA
*
ER_LEN   DS    H                  Error/Invalid message length
*
         DS   0F
ER_DATA  DS   0CL73               Error/Invalid message
ER_TRAN  DS    CL04
         DS    CL69
ER_L     EQU   *-ER_DATA
*
***********************************************************************
* Dynamic Storage Area (End)                                          *
***********************************************************************
*
***********************************************************************
* DFHCOMMAREA                                                         *
***********************************************************************
DFHCA    DSECT
CA_RC    DS    CL02               Return Code
         DS    CL02               not used (alignment)
CA_TRAN  DS    CL04               zECS   Transaction ID
CA_L     EQU   *-CA_RC            DFHCA length
*
***********************************************************************
* Control Section                                                     *
***********************************************************************
ZECSNC   DFHEIENT CODEREG=(R12),DATAREG=R10,EIBREG=R11
ZECSNC   AMODE 31
ZECSNC   RMODE 31
         B     SYSDATE                 BRANCH AROUND LITERALS
         DC    CL08'ZNC  '
         DC    CL48' -- zECS   Named Counter creation               '
         DC    CL08'        '
         DC    CL08'&SYSDATE'
         DC    CL08'        '
         DC    CL08'&SYSTIME'
SYSDATE  DS   0H
***********************************************************************
* Address DFHCOMMAREA                                                 *
* ABEND if the DFHCOMMAREA length is not the same as the DSECT.       *
***********************************************************************
SY_0010  DS   0H
         EXEC CICS ASSIGN APPLID(APPLID) SYSID(SYSID)                  X
               STARTCODE(STCODE) NOHANDLE
*
         MVC   Z_SUFFIX,C_SUFFIX       Move zECS   NC suffix
*
         L     R9,DFHEICAP             Load DFHCOMMAREA address
         USING DFHCA,R9                ... tell assembler
         CLC   EIBCALEN,=H'0'          DFHCOMMAREA length zero?
         BC    B'1000',SY_0030         ... yes, RECEIVE terminal input
         LA    R1,CA_L                 Load DFHCOMMAREA length
         CH    R1,EIBCALEN             DFHCOMMAREA equal to DSECT?
         BC    B'1000',SY_0020         ... yes, continue
         EXEC CICS ABEND ABCODE(EIBTRNID) NOHANDLE
***********************************************************************
* Set xxxx_ZECS   using DFHCOMMAREA                                   *
***********************************************************************
SY_0020  DS   0H
         MVC   Z_TRAN,CA_TRAN          Move NC TranID from COMMAREA
         BC    B'1111',SY_0100         Continue process
*
***********************************************************************
* Set xxxx_ZECS   using terminal input.                               *
***********************************************************************
SY_0030  DS   0H
         LA    R1,TC_L                 Load maximum TC length
         STH   R1,TC_LEN               Save maximum TC length
*
         EXEC CICS RECEIVE INTO(TC_DATA) NOHANDLE
*
         CLC   TC_ZCNC,EIBTRNID        TransID in first four bytes?
         BC    B'0111',ER_0010         ... no,  invalid format
         MVC   Z_TRAN,TC_TRAN          Move NC TranID from TC input
         BC    B'1111',SY_0100         Continue process
*
***********************************************************************
* Create xxxx_ZECS   named counter.                                   *
***********************************************************************
SY_0100  DS   0H
         EXEC CICS DEFINE DCOUNTER(Z_NC)                               X
               VALUE  (C_VAL)                                          X
               MINIMUM(C_MIN)                                          X
               MAXIMUM(C_MAX)                                          X
               NOHANDLE
*
         OC    EIBRESP,EIBRESP         Normal response?
         BC    B'0111',ER_0020         ... no,  Duplicate Counter
*
         BAS   R14,SY_9000             WTO and WRITEQ TD
***********************************************************************
* Issue START TRANSID for the new service                             *
***********************************************************************
SY_0200  DS   0H
         MVC   Z_EXP,C_EXP             Move expiration model name
         MVC   Z_EXP+2(2),Z_TRAN+2     Move service ID
*
         EXEC CICS START                                               X
               TRANSID(Z_EXP)                                          X
               FROM   (Z_TRAN)                                         X
               LENGTH (4)                                              X
               NOHANDLE
***********************************************************************
* Send terminal response                                              *
***********************************************************************
SY_0800  DS   0H
         CLI   STCODE,C'T'             Terminal task?
         BC    B'0111',SY_0900         ... no,  bypass SEND
         EXEC CICS SEND FROM(TD_DATA) LENGTH(TD_LEN)                   X
               ERASE NOHANDLE
***********************************************************************
* RETURN                                                              *
***********************************************************************
SY_0900  DS   0H
         EXEC CICS RETURN
***********************************************************************
* Invalid terminal input                                              *
***********************************************************************
ER_0010  DS   0H
         LA    R1,TD_L                 Load TD message length
         STH   R1,TD_LEN               Save TD Message length
         EXEC CICS SEND FROM(MSG_0010) LENGTH(TD_LEN)                  X
               ERASE NOHANDLE
         BC   B'1111',SY_0900          Return to caller
***********************************************************************
* Named Counter already defined                                       *
***********************************************************************
ER_0020  DS   0H
         MVC   ER_DATA,MSG_0020        Move template
         MVC   ER_TRAN,Z_TRAN          Move TransID
         LA    R1,ER_L                 Load ER message length
         STH   R1,ER_LEN               Save ER Message length
         EXEC CICS SEND FROM(ER_DATA)  LENGTH(ER_LEN)                  X
               ERASE NOHANDLE
         BC   B'1111',SY_0900          Return to caller
***********************************************************************
* Format time stamp                                                   *
* Write TD Message                                                    *
* Issue WTO                                                           *
***********************************************************************
SY_9000  DS   0H
         ST    R14,BAS_REG             Save return register
*
         MVC   TD_DATA,MSG_TEXT        Set message text
         MVC   TD_TRAN,Z_TRAN          Move NC TranID
*
         EXEC CICS ASKTIME ABSTIME(ABSTIME) NOHANDLE
         EXEC CICS FORMATTIME ABSTIME(ABSTIME) YYYYMMDD(TD_DATE)       X
               TIME(TD_TIME)  DATESEP('/') TIMESEP(':') NOHANDLE
*
         LA    R1,TD_L                 Load TD message length
         STH   R1,TD_LEN               Save TD Message length
         ST    R1,WTO_LEN              WTO length
*
         EXEC CICS WRITEQ TD QUEUE('@tdq@') FROM(TD_DATA)               X
               LENGTH(TD_LEN) NOHANDLE
*
         BC    B'0000',SY_9100         Bypass WTO
*
         EXEC CICS WRITE OPERATOR TEXT(TD_DATA) TEXTLENGTH(WTO_LEN)    X
               ROUTECODES(WTO_RC) NUMROUTES(WTO_RC_L) EVENTUAL         X
               NOHANDLE
***********************************************************************
* Label to bypass WTO                                                 *
***********************************************************************
SY_9100  DS   0H
         L     R14,BAS_REG             Load return register
         BCR   B'1111',R14             Return to caller
*
*
***********************************************************************
* Literal Pool                                                        *
***********************************************************************
         LTORG
*
         DS   0F
*
         DS   0F
C_VAL    DC    XL08'1'
C_MIN    DC    XL08'1'
C_MAX    DC    XL08'00000000FFFFFFFF'
*_MAX    DC    XL08'38D7EA4C67FFF'
*
         DS   0F
C_SUFFIX DC    CL12'_ZECS    '
         DS   0F
C_EXP    DC    CL04'ZX  '
         DS   0F
*
MSG_0010 DC   0CL74
         DC    CL25'Invalid format.  Must be '
         DC    CL25'TRAN,xxxx where xxxx is t'
         DC    CL24'he zECS   Transaction ID'
         DS   0F
*
MSG_0020 DC   0CL74
         DC    CL25'xxxx_ZECS   already defin'
         DC    CL25'ed.  You might want to co'
         DC    CL24'nsider checking DFHNC*  '
         DS   0F
*
MSG_TEXT DC   0CL74
         DC    CL25'YYYY/MM/DD HH:MM:SS tttt_'
         DC    CL25'ZECS   - zECS   Named Cou'
         DC    CL24'nter created            '
         DS   0F
WTO_RC_L DC    F'02'                   WTO Routecode length
WTO_RC   DC    XL02'0111'
         DS   0F
*
***********************************************************************
* Register assignments                                                *
***********************************************************************
         DS   0F
R0       EQU   0
R1       EQU   1
R2       EQU   2
R3       EQU   3
R4       EQU   4
R5       EQU   5
R6       EQU   6
R7       EQU   7
R8       EQU   8
R9       EQU   9
R10      EQU   10
R11      EQU   11
R12      EQU   12
R13      EQU   13
R14      EQU   14
R15      EQU   15
*
         PRINT ON
***********************************************************************
* End of Program                                                      *
***********************************************************************
         END   ZECSNC