CBL    CICS(SP)
       IDENTIFICATION DIVISION.
       PROGRAM-ID.      ECS001.
      ******************************************************************
      ** Sample CICS program initiated via a terminal.                **
      ** Program accepts 3 commands from the terminal,                **
      ** GET,PUT,DEL to execute on the zECS service.                  **
      ** GET - Retrieve a key/value pair                              **
      ** PUT - Put a key/value pair in the instance.                  **
      ** DEL - Delete a key/value pair from the instance.             **
      ** The data for the PUT command is accepted from the line       **
      ** following the tran id and command up to 23 lines on the      **
      ** screen.                                                      **
      ** --- MAKE SURE LINES ARE PADDED WITH SPACES. ---              **
      ** --- MAKE SURE LINES ARE PADDED WITH SPACES. ---              **
      ** --- MAKE SURE LINES ARE PADDED WITH SPACES. ---              **
      ** Example PUT command                                          **
      **   TRAN PUT {key_name}                                        **
      **   { "name" : "Los Angeles Dodgers",                          **
      **     "players" : 26,                                          **
      **     "salaries" : 248606156,                                  **
      **     "won_world_series" : true }                              **
      ** Example GET command, output returned to screen.              **
      **   TRAN GET {key_name}                                        **
      ** Example DELETE command                                       **
      **   TRAN DEL {key_name}                                        **
      ******************************************************************
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       INPUT-OUTPUT SECTION.
       DATA DIVISION.
       FILE SECTION.

      *----------------------------------------------------------------
       WORKING-STORAGE SECTION.
      *----------------------------------------------------------------
       01  URIMAP-NAME                 PIC X(08) VALUE 'ECS001'.
       01  SESSION-TOKEN               PIC X(08).
       01  ECS-KEY                     PIC X(80).
       01  ECS-KEY-LEN                 PIC 9(09) COMP.
       01  TERM-DATA-LEN               PIC 9(04) COMP.
       01  BODY-DATA                   PIC X(3000).
       01  BODY-DATA-LEN               PIC 9(09) COMP.
       01  ECS-DATA                    PIC X(3000).
       01  ECS-DATA-LEN                PIC 9(09) COMP.
       01  PATH-NAME                   PIC X(400).
       01  PATH-NAME-LEN               PIC 9(09) COMP.
       01  HTTP-STATUS-CODE            PIC 9(04) COMP.
       01  HTTP-STATUS-LEN             PIC 9(09) COMP.
       01  HTTP-STATUS-TEXT            PIC X(100).
       01  METHOD-CDVA                 PIC 9(09) COMP.
       01  I                           PIC 9(04) COMP.
       01  MEDIA-TYPE                  PIC X(56) VALUE
           'text/plain'.
       01  INPUT-PARMS.
           05  INPUT-PARM1             PIC X(80).
           05  INPUT-PARM2             PIC X(80).

       01  TERM-DATA.
           05  TERM-LINES OCCURS 24 TIMES
                          INDEXED BY TERM-IDX
                                       PIC X(80) VALUE SPACES.

       01  CICS-MSG.
           05  CICS-MSG-TEXT           PIC X(34).
           05  FILLER                  PIC X(09) VALUE ' EIBRESP='.
           05  CICS-MSG-RESP           PIC 9(04).
           05  FILLER                  PIC X(10) VALUE ' EIBRESP2='.
           05  CICS-MSG-RESP2          PIC 9(04).

       01  CICS-MSG2.
           05  CICS-MSG-HTTP           PIC X(20).
           05  FILLER                  PIC X(06) VALUE ' HTTP='.
           05  CICS-MSG-CODE           PIC 9(03).
           05  FILLER                  PIC X(01) VALUE ':'.
           05  CICS-MSG-STATUS         PIC X(31).

      *----------------------------------------------------------
       PROCEDURE DIVISION.
      *----------------------------------------------------------

           PERFORM A1000-GET-INPUT-REQUEST THRU A1000-EXIT.
           PERFORM A2000-SETUP-ECS-REQUEST THRU A2000-EXIT.
           PERFORM A3000-OPEN-CONNECTION THRU A3000-EXIT.
           PERFORM A4000-EXECUTE-SERVICE THRU A4000-EXIT.
           PERFORM A5000-CLOSE-CONNECTION THRU A5000-EXIT.
           PERFORM A6000-DISPLAY-RESULTS THRU A6000-EXIT.

           PERFORM Z1000-EXIT-PROGRAM THRU Z1000-EXIT.

      ******************************************************************
      * Use a URIMAP defintion to execute the service.                 *
      ******************************************************************

       A1000-GET-INPUT-REQUEST.

           MOVE LENGTH OF TERM-DATA          TO TERM-DATA-LEN.

           EXEC CICS RECEIVE
                INTO      ( TERM-DATA )
                LENGTH    ( TERM-DATA-LEN )
                MAXLENGTH ( TERM-DATA-LEN )
                NOHANDLE
           END-EXEC.

           IF EIBRESP = DFHRESP(NORMAL) OR 6
              GO TO A1000-EXIT
           END-IF.

      *    *--------------------------------------------------------*
      *    * Handle your error condition.                           *
      *    *--------------------------------------------------------*
           MOVE SPACES                       TO TERM-DATA.
           MOVE EIBRESP                      TO CICS-MSG-RESP.
           MOVE EIBRESP2                     TO CICS-MSG-RESP2.
           MOVE 'A1000: RECEIVE ERROR:'      TO CICS-MSG-TEXT.
           MOVE CICS-MSG                     TO TERM-LINES(1).

           PERFORM Z1000-EXIT-PROGRAM THRU Z1000-EXIT.

       A1000-EXIT.
           EXIT.

      ******************************************************************
      *                                                                *
      ******************************************************************

       A2000-SETUP-ECS-REQUEST.

           MOVE SPACES                      TO INPUT-PARMS.
           MOVE ZEROS                       TO ECS-KEY-LEN.

           UNSTRING TERM-LINES(1)
                    DELIMITED BY ALL SPACES
                    INTO INPUT-PARM1,
                         INPUT-PARM2,
                         ECS-KEY COUNT IN ECS-KEY-LEN
           END-UNSTRING.

           MOVE FUNCTION UPPER-CASE(INPUT-PARM2)   TO INPUT-PARM2.

           EVALUATE INPUT-PARM2
              WHEN 'GET'
                 MOVE DFHVALUE(GET)         TO METHOD-CDVA
              WHEN 'PUT'
                 MOVE DFHVALUE(PUT)         TO METHOD-CDVA
              WHEN 'DEL'
                 MOVE DFHVALUE(DELETE)      TO METHOD-CDVA
              WHEN OTHER
                 MOVE SPACES                TO TERM-DATA
                 MOVE 'Invalid command option, expecting GET,PUT or DEL'
                                            TO TERM-LINES(1)
                 PERFORM Z1000-EXIT-PROGRAM THRU Z1000-EXIT
           END-EVALUATE.

           MOVE 1                            TO BODY-DATA-LEN.

           PERFORM VARYING TERM-IDX FROM 2 BY 1 UNTIL TERM-IDX > 24
              IF TERM-LINES(TERM-IDX) > SPACES
                 PERFORM VARYING I FROM LENGTH OF TERM-LINES(1) BY -1
                         UNTIL   I < 1
                         OR      TERM-LINES(TERM-IDX)(I:1) > SPACES
                 END-PERFORM
                 STRING TERM-LINES(TERM-IDX)(1:I)  DELIMITED BY SIZE
                        X'0D25'                    DELIMITED BY SIZE
                        INTO BODY-DATA
                        WITH POINTER BODY-DATA-LEN
                 END-STRING
              END-IF
           END-PERFORM.

           SUBTRACT 1                       FROM BODY-DATA-LEN.

       A2000-EXIT.
           EXIT.

      ******************************************************************
      * Open the HTTP connection with the URIMAP name.                 *
      ******************************************************************

       A3000-OPEN-CONNECTION.

      *    *--------------------------------------------------------*
      *    * Open the URIMAP to establish connection to service.    *
      *    *  Host:   _your_host_name_ (installation specific)      *
      *    *  Port:   80 (can override this if needed)              *
      *    *  Path:   _your_path_name_ (based on installation)      *
      *    *  Scheme: HTTP                                          *
      *    *  Usage:  CLIENT                                        *
      *    *--------------------------------------------------------*
           EXEC CICS WEB OPEN
                SESSTOKEN( SESSION-TOKEN )
                URIMAP   ( URIMAP-NAME )
                NOHANDLE
           END-EXEC.

           IF EIBRESP = DFHRESP(NORMAL)
              GO TO A3000-EXIT
           END-IF.

      *    *--------------------------------------------------------*
      *    * Handle your error condition.                           *
      *    *--------------------------------------------------------*
           MOVE SPACES                      TO TERM-DATA.
           MOVE EIBRESP                     TO CICS-MSG-RESP.
           MOVE EIBRESP2                    TO CICS-MSG-RESP2.
           MOVE 'A3000: WEB_OPEN ERROR:'    TO CICS-MSG-TEXT.
           MOVE CICS-MSG                    TO TERM-LINES(1).

           PERFORM Z1000-EXIT-PROGRAM THRU Z1000-EXIT.

       A3000-EXIT.
           EXIT.

      ******************************************************************
      * Execute the zECS service with the WEB CONVERSE API.            *
      ******************************************************************

       A4000-EXECUTE-SERVICE.

           MOVE LENGTH OF HTTP-STATUS-TEXT    TO HTTP-STATUS-LEN.
           MOVE LENGTH OF ECS-DATA            TO ECS-DATA-LEN.
           MOVE LENGTH OF PATH-NAME           TO PATH-NAME-LEN.
           MOVE SPACES                        TO HTTP-STATUS-TEXT,
                                                 ECS-DATA,
                                                 PATH-NAME.

      *    *--------------------------------------------------------*
      *    * The base "path" is defined on the URIMAP and we need   *
      *    * to add to it to append the {key} name. A4100 issues    *
      *    * an inquire on the URIMAP to pull in the base "path"    *
      *    * name. It also appends the {key} name to it.            *
      *    *--------------------------------------------------------*
           PERFORM A4100-GET-EXISTING-PATH THRU A4100-EXIT.

      *    *--------------------------------------------------------*
      *    * Execute the zECS service.                              *
      *    * For PUT requests we need to pass the payload to        *
      *    * save for the {key}. The other GET and DELETE requests  *
      *    * do not use body payloads so there is nothing to pass.  *
      *    *--------------------------------------------------------*
           IF METHOD-CDVA = DFHVALUE(PUT)
              EXEC CICS WEB CONVERSE
                   SESSTOKEN  ( SESSION-TOKEN )
                   METHOD     ( METHOD-CDVA )
                   PATH       ( PATH-NAME )
                   PATHLENGTH ( PATH-NAME-LEN )
                   FROM       ( BODY-DATA )
                   FROMLENGTH ( BODY-DATA-LEN )
                   MEDIATYPE  ( MEDIA-TYPE )
                   INTO       ( ECS-DATA )
                   TOLENGTH   ( ECS-DATA-LEN )
                   STATUSCODE ( HTTP-STATUS-CODE )
                   STATUSLEN  ( HTTP-STATUS-LEN )
                   STATUSTEXT ( HTTP-STATUS-TEXT )
                   NOHANDLE
              END-EXEC
           ELSE
              EXEC CICS WEB CONVERSE
                   SESSTOKEN  ( SESSION-TOKEN )
                   METHOD     ( METHOD-CDVA )
                   PATH       ( PATH-NAME )
                   PATHLENGTH ( PATH-NAME-LEN )
                   INTO       ( ECS-DATA )
                   TOLENGTH   ( ECS-DATA-LEN )
                   STATUSCODE ( HTTP-STATUS-CODE )
                   STATUSLEN  ( HTTP-STATUS-LEN )
                   STATUSTEXT ( HTTP-STATUS-TEXT )
                   NOHANDLE
              END-EXEC
           END-IF.

           IF EIBRESP = DFHRESP(NORMAL) AND HTTP-STATUS-CODE = 200
              GO TO A4000-EXIT
           END-IF.

      *    *--------------------------------------------------------*
      *    * Handle your error condition.                           *
      *    *--------------------------------------------------------*
           MOVE SPACES                       TO TERM-DATA.
           MOVE EIBRESP                      TO CICS-MSG-RESP.
           MOVE EIBRESP2                     TO CICS-MSG-RESP2.
           MOVE 'A4000: WEB_CONVERSE ERROR:' TO CICS-MSG-TEXT.
           MOVE CICS-MSG                     TO TERM-LINES(1).

           IF EIBRESP = DFHRESP(NORMAL)
              MOVE HTTP-STATUS-CODE          TO CICS-MSG-CODE
              MOVE HTTP-STATUS-TEXT          TO CICS-MSG-STATUS
              MOVE 'A4000: HTTP ERROR'       TO CICS-MSG-HTTP
              MOVE CICS-MSG2                 TO TERM-LINES(1)
           END-IF.

           PERFORM Z1000-EXIT-PROGRAM THRU Z1000-EXIT.

       A4000-EXIT.
           EXIT.

      ******************************************************************
      *                                                                *
      ******************************************************************

       A4100-GET-EXISTING-PATH.

      *    *--------------------------------------------------------*
      *    * Get pass "path" name from URIMAP.                      *
      *    *--------------------------------------------------------*
           EXEC CICS INQUIRE
                URIMAP    ( URIMAP-NAME )
                PATH      ( PATH-NAME )
                NOHANDLE
           END-EXEC.

           IF EIBRESP = DFHRESP(NORMAL)
              NEXT SENTENCE
           ELSE
              MOVE SPACES                         TO TERM-DATA
              MOVE EIBRESP                        TO CICS-MSG-RESP
              MOVE EIBRESP2                       TO CICS-MSG-RESP2
              MOVE 'A4000: INQUIRE_URIMAP ERROR:' TO CICS-MSG-TEXT
              MOVE CICS-MSG                       TO TERM-LINES(1)
              PERFORM Z1000-EXIT-PROGRAM THRU Z1000-EXIT
           END-IF.

      *    *--------------------------------------------------------*
      *    * Append the {key} name to the base "path".              *
      *    *--------------------------------------------------------*
           PERFORM VARYING PATH-NAME-LEN FROM LENGTH OF PATH-NAME BY -1
                   UNTIL   PATH-NAME-LEN < 1
                   OR      PATH-NAME(PATH-NAME-LEN:1) > SPACES
           END-PERFORM.

           MOVE ECS-KEY                           TO
                PATH-NAME(PATH-NAME-LEN + 1:).
           ADD  ECS-KEY-LEN                       TO PATH-NAME-LEN.

       A4100-EXIT.
           EXIT.

      ******************************************************************
      * Close the open connection.                                     *
      ******************************************************************

       A5000-CLOSE-CONNECTION.

      *    *--------------------------------------------------------*
      *    * Close open connection.                                 *
      *    *--------------------------------------------------------*
           EXEC CICS WEB CLOSE
                SESSTOKEN( SESSION-TOKEN )
                NOHANDLE
           END-EXEC.

           IF EIBRESP = DFHRESP(NORMAL)
              GO TO A5000-EXIT
           END-IF.

      *    *--------------------------------------------------------*
      *    * Handle your error condition.                           *
      *    *--------------------------------------------------------*
           MOVE SPACES                       TO TERM-DATA.
           MOVE EIBRESP                      TO CICS-MSG-RESP.
           MOVE EIBRESP2                     TO CICS-MSG-RESP2.
           MOVE 'A5000: WEB_CLOSE ERROR:'    TO CICS-MSG-TEXT.
           MOVE CICS-MSG                     TO TERM-LINES(1).

           PERFORM Z1000-EXIT-PROGRAM THRU Z1000-EXIT.

       A5000-EXIT.
           EXIT.

      ******************************************************************
      *                                                                *
      ******************************************************************

       A6000-DISPLAY-RESULTS.

           MOVE SPACES                             TO TERM-DATA.
           MOVE 'Command successfully processed.'  TO TERM-LINES(1).

      *    *--------------------------------------------------------*
      *    * Split the data by new lines.                           *
      *    *--------------------------------------------------------*
           SET  TERM-IDX                           TO 2.
           MOVE 1                                  TO I.

           PERFORM UNTIL TERM-IDX > 24
                   OR    I >= LENGTH OF ECS-DATA
              MOVE ZEROS                   TO BODY-DATA-LEN
              MOVE SPACES                  TO TERM-LINES(TERM-IDX)
              UNSTRING ECS-DATA(I:)
                       DELIMITED BY X'0D25'
                       INTO TERM-LINES(TERM-IDX)
                       COUNT IN BODY-DATA-LEN
              END-UNSTRING
              ADD  BODY-DATA-LEN, 2        TO I
              SET  TERM-IDX                UP BY 1
           END-PERFORM.

       A6000-EXIT.
           EXIT.

      ******************************************************************
      * All done, post appropiate message to terminal and exit.        *
      ******************************************************************

       Z1000-EXIT-PROGRAM.

      *    *--------------------------------------------------------*
      *    * Send response to terminal.                             *
      *    *--------------------------------------------------------*
           EXEC CICS SEND
                FROM  ( TERM-DATA )
                LENGTH( LENGTH OF TERM-DATA )
                ERASE
                NOHANDLE
           END-EXEC.

           EXEC CICS RETURN
           END-EXEC.

       Z1000-EXIT.
           EXIT.