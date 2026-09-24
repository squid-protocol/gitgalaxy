*
*  PROGRAM:    ZECS002
*  AUTHOR:     Randy Frerking and Rich Jackson.
*  COMMENTS:   z/OS Enterprise Caching Services.
*
*              Called by zECS caching service.
*              Decode Base64Binary Basic Authentication
*              Convert results from ASCII to EBCDIC
*              UserID:Password
*              Call RACF to validate and set return code
*
*              This program is specifically written for zECS
*              and is not a generic Base64Binary encode and/or
*              decode subroutine.
*
*
***********************************************************************
* Dynamic Storage Area (Start)                                        *
***********************************************************************
DFHEISTG DSECT
ABSTIME  DS    D                  Absolute time
APPLID   DS    CL08               CICS/VTAM APPLID
SYSID    DS    CL04               CICS SYSID
         DS   0F
USERID   DS    CL08               UserID
         DS   0F
PASSWORD DS    CL08               Password
         DS   0F
BAS_REG  DS    F                  Return register
         DS   0F
WTO_LEN  DS    F                  WTO length
TD_LEN   DS    H                  Transient Data message length
*
         DS   0F
TD_DATA  DS   0CL68               TD/WTO output
TD_DATE  DS    CL10
         DS    CL01
TD_TIME  DS    CL08
         DS    CL01
TD_TRAN  DS    CL04
         DS    CL01
         DS    CL26
TD_UID   DS    CL08
         DS    CL01
TD_PW    DS    CL08
TD_L     EQU   *-TD_DATA
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
CA_USER  DS    CL08               UserID
CA_PASS  DS    CL08               Password
CA_ENC   DS    CL24               Encoded field (max 24 bytes)
         DS    CL04               not used (alignment)
CA_DEC   DS    CL18               Decoded field (max 18 byte)
CA_L     EQU   *-CA_RC            DFHCA length
*
***********************************************************************
* Control Section                                                     *
***********************************************************************
ZECS002  DFHEIENT CODEREG=(R12),DATAREG=R10,EIBREG=R11
ZECS002  AMODE 31
ZECS002  RMODE 31
         B     SYSDATE                 BRANCH AROUND LITERALS
         DC    CL08'ZECS002  '
         DC    CL48' -- CICS/REST Basic Authentication              '
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
*        EXEC CICS ASSIGN APPLID(APPLID) SYSID(SYSID) NOHANDLE
         L     R9,DFHEICAP             Load DFHCOMMAREA address
         USING DFHCA,R9                ... tell assembler
         LA    R1,CA_L                 Load DFHCOMMAREA length
         CH    R1,EIBCALEN             DFHCOMMAREA equal to DSECT?
         BC    B'1000',SY_0020         ... yes, continue
         EXEC CICS ABEND ABCODE(AB_001) NOHANDLE
***********************************************************************
* Decode Base64Binary UserID:Password                                 *
***********************************************************************
SY_0020  DS   0H
         MVC   CA_RC,=C'00'            Set default RC
*        BC    B'1111',SY_0900         Bypass RACF VERIFY
*
         MVC   CA_DEC,ASCII_20         Initialize to ASCII spaces
         LA    R2,6                    Load Octet count
         LA    R3,CA_ENC               Address encoded field (source)
         LA    R6,CA_DEC               Address decoded field (target)
*
***********************************************************************
* Process six octets                                                  *
* R4 and R5 are used as the even/odd pair registers for SLL and SLDL  *
* instructions.                                                       *
***********************************************************************
SY_0030  DS   0H
         SR    R4,R4                   Clear R4
         SR    R5,R5                   Clear R5
*
         BAS   R14,SY_1000             Decode four bytes into three
         BCT   R2,SY_0030              ... for each octet
***********************************************************************
* At this point, the UserID:Password has been decoded and converted   *
* from ASCII to EBCDIC.                                               *
* Move decoded and converted UserID                            .      *
***********************************************************************
SY_0100  DS   0H
         MVC   USERID,EIGHT_40         Initialize to spaces
         MVC   PASSWORD,EIGHT_40       Initialize to spaces
*
         LA    R2,8                    Set max field length
         LA    R3,CA_DEC               Address decoded field (source)
         LA    R6,USERID               Address UserID  field (target)
*
***********************************************************************
* Move decoded/converted field until ':' has been encountered.        *
***********************************************************************
SY_0110  DS   0H
         MVC   0(1,R6),0(R3)           Move byte to UserId
         LA    R3,1(,R3)               Increment source field
         LA    R6,1(,R6)               Increment target field
         CLI   0(R3),C':'              Colon?
         BC    B'1000',SY_0200         ... yes, process Password
         BCT   R2,SY_0110              ... no,  continue
***********************************************************************
* At this point, the UserID has been moved.  Now, move the Password   *
***********************************************************************
SY_0200  DS   0H
         LA    R2,8                    Set max field length
         LA    R3,1(,R3)               skip past ':'
         LA    R6,PASSWORD             Address Password field (target)
***********************************************************************
* Move decoded/converted field until spaces or nulls are encountered. *
***********************************************************************
SY_0210  DS   0H
         MVC   0(1,R6),0(R3)           Move byte to UserId
         LA    R3,1(,R3)               Increment source field
         LA    R6,1(,R6)               Increment target field
         CLI   0(R3),X'00'             Null?
         BC    B'1000',SY_0300         ... yes, call RACF
         CLI   0(R3),X'40'             Space?
         BC    B'1000',SY_0300         ... yes, call RACF
         BCT   R2,SY_0210              ... no,  continue
***********************************************************************
* At this point, the UserID and Password have been moved.             *
* Call RACF to verify the UserID and Password.                        *
***********************************************************************
SY_0300  DS   0H
         MVC   CA_RC,=C'00'            Set default return code
         MVC   CA_USER,USERID          Set UserID   in DFHCOMMAREA
         MVC   CA_PASS,PASSWORD        Set Password in DFHCOMMAREA
         EXEC CICS VERIFY USERID(USERID) PASSWORD(PASSWORD)            X
              NOHANDLE
*
         OC   EIBRESP,EIBRESP          Zero return code?
         BC   B'0111',RC_0008          ... no,  set 08 return code
*
***********************************************************************
* Return to CICS                                                      *
***********************************************************************
SY_0900  DS   0H
         EXEC CICS RETURN
*
***********************************************************************
* Decode Base64Binary                                                 *
***********************************************************************
SY_1000  DS   0H
         ST    R14,BAS_REG             Save return register
*
***********************************************************************
* This routine will convert the first of four encoded bytes.          *
***********************************************************************
SY_1010  DS   0H
         CLI   0(R3),X'7E'             EOF (=)?
         BC    B'1000',RC_0012         ... yes, invalid encode
         SR    R5,R5                   Clear odd register
         IC    R5,0(R3)                Load first encoded byte
         LA    R3,1(,R3)               Point to next encoded byte
         IC    R5,B64XLT(R5)           Translate from B64 alphabet
         SLL   R5,26                   Shift out the 2 Hi order bits
         SLDL  R4,6                    Merge 6 bits of R5 into R4
*
***********************************************************************
* This routine will convert the second of four encoded bytes.         *
***********************************************************************
SY_1020  DS   0H
         CLI   0(R3),X'7E'             EOF (=)?
         BC    B'1000',RC_0012         ... yes, invalid encode
         SR    R5,R5                   Clear odd register
         IC    R5,0(R3)                Load first encoded byte
         LA    R3,1(,R3)               Point to next encoded byte
         IC    R5,B64XLT(R5)           Translate from B64 alphabet
         SLL   R5,26                   Shift out the 2 Hi order bits
         SLDL  R4,6                    Merge 6 bits of R5 into R4
***********************************************************************
* This routine will convert the third of four encoded bytes.          *
***********************************************************************
SY_1030  DS   0H
         CLI   0(R3),X'7E'             EOF (=)?
         BC    B'1000',SY_1100         ... yes, process one octet
         SR    R5,R5                   Clear odd register
         IC    R5,0(R3)                Load first encoded byte
         LA    R3,1(,R3)               Point to next encoded byte
         IC    R5,B64XLT(R5)           Translate from B64 alphabet
         SLL   R5,26                   Shift out the 2 Hi order bits
         SLDL  R4,6                    Merge 6 bits of R5 into R4
***********************************************************************
* This routine will convert the fourth of four encoded bytes.         *
***********************************************************************
SY_1040  DS   0H
         CLI   0(R3),X'7E'             EOF (=)?
         BC    B'1000',SY_1200         ... yes, process two octets
         SR    R5,R5                   Clear odd register
         IC    R5,0(R3)                Load first encoded byte
         LA    R3,1(,R3)               Point to next encoded byte
         IC    R5,B64XLT(R5)           Translate from B64 alphabet
         SLL   R5,26                   Shift out the 2 Hi order bits
         SLDL  R4,6                    Merge 6 bits of R5 into R4
***********************************************************************
* Process the three decoded bytes.                                    *
***********************************************************************
SY_1050  DS   0H
         STCM  R4,7,0(R6)              Save three decoded bytes
         TR    0(3,R6),A_TO_E          Convert to EBCDIC
         LA    R6,3(R6)                Increment pointer
         L     R14,BAS_REG             Load return register
         BCR   B'1111',R14             Return to caller
***********************************************************************
* Process single octet                                                *
***********************************************************************
SY_1100  DS   0H
         SLL   R4,12                   Shift a null digit into R4
         STCM  R4,4,0(R6)              Save single octet
         TR    0(3,R6),A_TO_E          Convert to EBCDIC
         LA    R2,1                    Set counter to end process
         L     R14,BAS_REG             Load return register
         BCR   B'1111',R14             Return to caller
***********************************************************************
* Process double octet                                                *
***********************************************************************
SY_1200  DS   0H
         SLL   R4,6                    Shift a null digit into R4
         STCM  R4,6,0(R6)              Save double octet
         TR    0(3,R6),A_TO_E          Convert to EBCDIC
         LA    R2,1                    Set counter to end process
         L     R14,BAS_REG             Load return register
         BCR   B'1111',R14             Return to caller
***********************************************************************
* Return code 08 - RACF error                                         *
***********************************************************************
RC_0008  DS   0H
         MVC   CA_RC,=C'08'            Set return code 08
         XC    PASSWORD,PASSWORD       Clear Password before logging
         BAS   R14,SY_9000             Log the error
         BC   B'1111',SY_0900          Return to caller
***********************************************************************
* Return code 12 - Invalid encode field provided                      *
***********************************************************************
RC_0012  DS   0H
         MVC   CA_RC,=C'12'            Set return code 12
         BC   B'1111',SY_0900          Return to caller
*
***********************************************************************
* Format time stamp                                                   *
* Write TD Message                                                    *
* Issue WTO                                                           *
***********************************************************************
SY_9000  DS   0H
         ST    R14,BAS_REG             Save return register
*
         MVC   TD_DATA,MSG_TEXT        Set message text
         MVC   TD_TRAN,EIBTRNID        Set Transaction ID
         MVC   TD_UID,USERID           Set UserID
         MVC   TD_PW,PASSWORD          Set Password
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
         BC    B'1111',SY_9100         Bypass WTO
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
AB_001   DC    CL04'Z001'
         DS   0F
EIGHT_40 DC    08XL01'40'              EBCDIC spaces
ASCII_20 DC    18XL01'20'              ASCII  spaces
*
MSG_TEXT DC   0CL69
         DC    CL25'YYYY/MM/DD HH:MM:SS tttt '
         DC    CL27'ZECS002 security failure - '
         DC    CL17'uuuuuuuu pppppppp'
         DS   0F
WTO_RC_L DC    F'02'                   WTO Routecode length
WTO_RC   DC    XL02'0111'
         DS   0F
*
***********************************************************************
* Translate table                                                     *
* Base64Binary alphabet and corresponding six bit representation      *
***********************************************************************
         DS   0F
B64XLT   DC    XL16'00000000000000000000000000000000'       00-0F
         DC    XL16'00000000000000000000000000000000'       10-1F
         DC    XL16'00000000000000000000000000000000'       20-2F
         DC    XL16'00000000000000000000000000000000'       30-3F
         DC    XL16'00000000000000000000000000003E00'       40-4F
         DC    XL16'00000000000000000000000000000000'       50-5F
         DC    XL16'003F0000000000000000000000000000'       60-6F
         DC    XL16'00000000000000000000000000000000'       70-7F
         DC    XL16'001A1B1C1D1E1F202122000000000000'       80-8F
         DC    XL16'00232425262728292A2B000000000000'       90-9F
         DC    XL16'00002C2D2E2F30313233000000000000'       A0-AF
         DC    XL16'00000000000000000000000000000000'       B0-BF
         DC    XL16'00000102030405060708000000000000'       C0-CF
         DC    XL16'00090A0B0C0D0E0F1011000000000000'       D0-DF
         DC    XL16'00001213141516171819000000000000'       E0-EF
         DC    XL16'3435363738393A3B3C3D000000000000'       F0-FF
*
***********************************************************************
* Translate table                                                     *
* ASCII to EBCDIC                                                     *
***********************************************************************
         DS   0F
A_TO_E   DC    XL16'00000000000000000000000000000000'       00-0F
         DC    XL16'00000000000000000000000000000000'       10-1F
         DC    XL16'405A7F7B5B6C507D4D5D5C4E6B604B61'       20-2F
         DC    XL16'F0F1F2F3F4F5F6F7F8F97A5E4C7E6E6F'       30-3F
         DC    XL16'7CC1C2C3C4C5C6C7C8C9D1D2D3D4D5D6'       40-4F
         DC    XL16'D7D8D9E2E3E4E5E6E7E8E9BAE0BB5F6D'       50-5F
         DC    XL16'79818283848586878889919293949596'       60-6F
         DC    XL16'979899A2A3A4A5A6A7A8A9C06AD0A107'       70-7F
         DC    XL16'00000000000000000000000000000000'       80-8F
         DC    XL16'00000000000000000000000000000000'       90-9F
         DC    XL16'00000000000000000000000000000000'       A0-AF
         DC    XL16'00000000000000000000000000000000'       B0-BF
         DC    XL16'00000000000000000000000000000000'       C0-CF
         DC    XL16'00000000000000000000000000000000'       D0-DF
         DC    XL16'00000000000000000000000000000000'       E0-EF
         DC    XL16'00000000000000000000000000000000'       F0-FF
*
         DS   0F
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
         END   ZECS002