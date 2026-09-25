"""
#3351-#3354: the CICS resource-operation extractor (core/cics_resources.py), run
through `extract_boundary` exactly as a scan does.

Every source below is a real shape from the pinned corpora (CBSA, carddemo) or a
documented CICS form, reduced to the lines that matter. Each test pins one
decision: which commands draw a row, which operand is the name, how a data-name
resolves (VALUE, then a single MOVEd literal), and that every scan is bounded.
"""

import time

from gitgalaxy.core.cics_resources import extract_cics_resources
from gitgalaxy.core.mainframe_boundary import extract_boundary


def _ops(source: str, dialect: str = "cobol") -> list[dict]:
    return extract_boundary(dialect, source)["cics_resources"]


def _one(source: str, dialect: str = "cobol") -> dict:
    ops = _ops(source, dialect)
    assert len(ops) == 1, ops
    return ops[0]


# ---- FILE (#3351) -------------------------------------------------------------


def test_read_file_literal_with_into_record_and_options():
    # CBSA DELCUS.cbl
    op = _one(
        "           EXEC CICS READ FILE('CUSTOMER')\n"
        "                RIDFLD(DESIRED-KEY)\n"
        "                INTO(OUTPUT-CUST-DATA)\n"
        "                UPDATE\n"
        "                TOKEN(WS-TOKEN)\n"
        "                RESP(WS-CICS-RESP)\n"
        "                RESP2(WS-CICS-RESP2)\n"
        "           END-EXEC.\n"
    )
    assert op == {
        "verb": "READ",
        "kind": "FILE",
        "access": "read",
        "operand": "'CUSTOMER'",
        "name": "CUSTOMER",
        "resolution": "literal",
        "candidates": None,
        "qualifier_operand": None,
        "qualifier": None,
        "record_clause": "INTO",
        "record": "OUTPUT-CUST-DATA",
        # RESP/RESP2 are error plumbing, not resource facts.
        "attributes": "RIDFLD(DESIRED-KEY) UPDATE TOKEN(WS-TOKEN)",
        "line": 1,
    }


def test_dataset_synonym_resolves_through_value_on_a_continuation_line():
    # carddemo COACTVWC.cbl: the VALUE is on the line after the PIC, and the
    # operand is written `DATASET   (LIT-ACCTFILENAME)` with a blank before `(`.
    src = (
        "       WORKING-STORAGE SECTION.\n"
        "          05 LIT-ACCTFILENAME                      PIC X(8)\n"
        "                                                   VALUE 'ACCTDAT '.\n"
        "       PROCEDURE DIVISION.\n"
        "           EXEC CICS READ\n"
        "                DATASET   (LIT-ACCTFILENAME)\n"
        "                INTO      (ACCOUNT-RECORD)\n"
        "           END-EXEC\n"
    )
    op = _one(src)
    assert (op["name"], op["resolution"], op["operand"]) == ("ACCTDAT", "value", "LIT-ACCTFILENAME")
    assert (op["record_clause"], op["record"], op["line"]) == ("INTO", "ACCOUNT-RECORD", 5)


def test_every_file_verb_maps_to_its_access():
    verbs = {
        "READ": "read",
        "READNEXT": "read",
        "READPREV": "read",
        "STARTBR": "browse",
        "RESETBR": "browse",
        "ENDBR": "browse",
        "WRITE": "write",
        "REWRITE": "update",
        "DELETE": "delete",
        "UNLOCK": "unlock",
    }
    src = "".join(f"           EXEC CICS {v} FILE('F') END-EXEC\n" for v in verbs)
    assert [(o["verb"], o["access"]) for o in _ops(src)] == list(verbs.items())


def test_a_write_without_file_draws_nothing():
    # WRITE OPERATOR / WRITE JOURNALNAME name no file.
    assert _ops("           EXEC CICS WRITE OPERATOR TEXT(WS-MSG) END-EXEC\n") == []


# ---- MAP (#3352) --------------------------------------------------------------


def test_send_and_receive_map_with_mapset():
    # carddemo COSGN00C.cbl, EXEC CICS on its own line.
    src = (
        "           EXEC CICS RECEIVE\n"
        "                     MAP('COSGN0A')\n"
        "                     MAPSET('COSGN00')\n"
        "                     RESP(WS-RESP-CD)\n"
        "           END-EXEC.\n"
        "           EXEC CICS SEND\n"
        "                     MAP('COSGN0A')\n"
        "                     MAPSET('COSGN00')\n"
        "                     FROM(COSGN0AO)\n"
        "                     ERASE\n"
        "                     CURSOR\n"
        "           END-EXEC.\n"
    )
    recv, send = _ops(src)
    assert (recv["verb"], recv["kind"], recv["access"], recv["name"], recv["qualifier"]) == (
        "RECEIVE",
        "MAP",
        "read",
        "COSGN0A",
        "COSGN00",
    )
    assert recv["record"] is None
    assert (send["access"], send["record_clause"], send["record"], send["attributes"]) == (
        "write",
        "FROM",
        "COSGN0AO",
        "ERASE CURSOR",
    )


def test_map_and_mapset_data_names_resolve_or_stay_unresolved():
    # carddemo COACTUPC: LIT-THISMAP has a VALUE; CCARD-NEXT-MAP is set at run time.
    src = (
        "       01 LIT-THISMAP     PIC X(7) VALUE 'CACTUPA'.\n"
        "       01 LIT-THISMAPSET  PIC X(7) VALUE 'COACTUP'.\n"
        "       01 CCARD-NEXT-MAP  PIC X(7).\n"
        "           EXEC CICS RECEIVE MAP(LIT-THISMAP) MAPSET(LIT-THISMAPSET)\n"
        "                INTO(CACTUPAI) END-EXEC\n"
        "           EXEC CICS SEND MAP(CCARD-NEXT-MAP) MAPSET(CCARD-NEXT-MAPSET)\n"
        "                FROM(CACTUPAO) END-EXEC\n"
    )
    known, runtime = _ops(src)
    assert (known["name"], known["resolution"], known["qualifier"]) == ("CACTUPA", "value", "COACTUP")
    assert (runtime["name"], runtime["resolution"], runtime["qualifier"]) == (None, "unresolved", None)
    assert runtime["qualifier_operand"] == "CCARD-NEXT-MAPSET"


def test_send_text_and_send_control_are_not_maps():
    src = (
        "           EXEC CICS SEND TEXT FROM(WS-MSG) ERASE END-EXEC\n           EXEC CICS SEND CONTROL ERASE END-EXEC\n"
    )
    assert _ops(src) == []


# ---- QUEUE (#3353) ------------------------------------------------------------


def test_writeq_td_with_spaced_operands():
    # carddemo CORPT00C.cbl -- `QUEUE ('JOBS')`, `FROM (JCL-RECORD)`.
    op = _one(
        "           EXEC CICS WRITEQ TD\n"
        "             QUEUE ('JOBS')\n"
        "             FROM (JCL-RECORD)\n"
        "             LENGTH (LENGTH OF JCL-RECORD)\n"
        "             RESP(WS-RESP-CD)\n"
        "           END-EXEC.\n"
    )
    assert (op["verb"], op["kind"], op["access"], op["name"], op["qualifier"]) == (
        "WRITEQ",
        "QUEUE",
        "write",
        "JOBS",
        "TD",
    )
    assert (op["record"], op["attributes"]) == ("JCL-RECORD", "LENGTH(LENGTH OF JCL-RECORD)")


def test_queue_type_defaults_to_ts_and_qname_and_sysid_are_read():
    src = (
        "           EXEC CICS READQ QNAME('SCRATCH-QUEUE-01') INTO(WS-REC) ITEM(1) END-EXEC\n"
        "           EXEC CICS DELETEQ TS QUEUE(WS-Q) SYSID('CICB') END-EXEC\n"
        "           EXEC CICS WRITEQ TS QUEUE('MYQ') FROM(WS-REC) MAIN END-EXEC\n"
    )
    readq, deleteq, writeq = _ops(src)
    assert (readq["access"], readq["name"], readq["qualifier"], readq["attributes"]) == (
        "read",
        "SCRATCH-QUEUE-01",
        "TS",
        "ITEM(1)",
    )
    assert (deleteq["access"], deleteq["resolution"], deleteq["attributes"]) == (
        "delete",
        "unresolved",
        "SYSID('CICB')",
    )
    assert (writeq["qualifier"], writeq["attributes"]) == ("TS", "MAIN")


# ---- CONTAINER / CHANNEL (#3354) ---------------------------------------------


def test_container_names_set_by_one_move_resolve_as_move():
    # CBSA CRDTAGY1.cbl: VALUE SPACES, then a single MOVE of each name.
    src = (
        "       01 WS-CONTAINER-NAME  PIC X(16)  VALUE SPACES.\n"
        "       01 WS-CHANNEL-NAME    PIC X(16)  VALUE SPACES.\n"
        "           MOVE 'CIPA            ' TO WS-CONTAINER-NAME.\n"
        "           MOVE 'CIPCREDCHANN    ' TO WS-CHANNEL-NAME.\n"
        "           EXEC CICS GET CONTAINER(WS-CONTAINER-NAME)\n"
        "                     CHANNEL(WS-CHANNEL-NAME)\n"
        "                     INTO(WS-CONT-IN)\n"
        "                     FLENGTH(WS-CONTAINER-LEN)\n"
        "           END-EXEC.\n"
    )
    op = _one(src)
    assert (op["kind"], op["access"], op["name"], op["resolution"]) == ("CONTAINER", "read", "CIPA", "move")
    assert (op["qualifier_operand"], op["qualifier"], op["record"]) == ("WS-CHANNEL-NAME", "CIPCREDCHANN", "WS-CONT-IN")


def test_several_moved_literals_are_ambiguous_candidates_not_a_guess():
    # CBSA CRECUST.cbl: an EVALUATE moves CIPA..CIPE into one name.
    moves = "".join(f"              MOVE 'CIP{c}' TO WS-PUT-CONT-NAME\n" for c in "ABCDE")
    op = _one(moves + "           EXEC CICS PUT CONTAINER(WS-PUT-CONT-NAME) FROM(DFHCOMMAREA) END-EXEC\n")
    assert (op["name"], op["resolution"], op["candidates"]) == (None, "ambiguous", "CIPA,CIPB,CIPC,CIPD,CIPE")


def test_value_wins_over_a_move():
    src = (
        "       01 WS-Q PIC X(8) VALUE 'FIRSTQ'.\n"
        "           MOVE 'OTHERQ' TO WS-Q.\n"
        "           EXEC CICS WRITEQ TS QUEUE(WS-Q) FROM(X) END-EXEC\n"
    )
    assert (_one(src)["name"], _one(src)["resolution"]) == ("FIRSTQ", "value")


def test_delete_container_is_a_container_and_move_container_is_move():
    src = (
        "           EXEC CICS DELETE CONTAINER('A') CHANNEL('C') END-EXEC\n"
        "           EXEC CICS MOVE CONTAINER('A') AS('B') CHANNEL('C') TOCHANNEL('D') END-EXEC\n"
    )
    delete, move = _ops(src)
    assert (delete["kind"], delete["access"], delete["qualifier"]) == ("CONTAINER", "delete", "C")
    assert (move["access"], move["attributes"]) == ("move", "AS('B') TOCHANNEL('D')")


def test_a_channel_passed_on_link_and_run_names_its_receiver():
    src = (
        "           EXEC CICS LINK PROGRAM('CRDTAGY1') CHANNEL('CIPCREDCHANN') END-EXEC\n"
        "           EXEC CICS RUN TRANSID(WS-RUN-TRANSID) CHANNEL('CIPCREDCHANN')\n"
        "                CHILD(WS-ANY-CHILD-TKN) END-EXEC\n"
        # No CHANNEL: an ordinary LINK is the call graph's (#3200), not a row here.
        "           EXEC CICS LINK PROGRAM('ABNDPROC') COMMAREA(WS-X) END-EXEC\n"
    )
    link, run = _ops(src)
    assert (link["kind"], link["access"], link["name"], link["qualifier"]) == (
        "CHANNEL",
        "pass",
        "CIPCREDCHANN",
        "CRDTAGY1",
    )
    assert (run["verb"], run["qualifier_operand"], run["qualifier"], run["attributes"]) == (
        "RUN",
        "WS-RUN-TRANSID",
        None,
        "CHILD(WS-ANY-CHILD-TKN)",
    )


def test_a_subscripted_operand_is_an_expression():
    op = _one("           EXEC CICS READ FILE(WS-FILES(WS-I)) INTO(X) END-EXEC\n")
    assert (op["name"], op["resolution"], op["operand"]) == (None, "expression", "WS-FILES(WS-I)")


# ---- what is NOT a resource operation ---------------------------------------


def test_exec_cics_inside_a_literal_is_not_a_command():
    # CBSA CRECUST.cbl: DISPLAY 'EXEC CICS FETCH ANY failed. RESP='
    src = "           DISPLAY 'EXEC CICS READ FILE(X) failed. RESP='\n                WS-CICS-RESP\n"
    assert _ops(src) == []


def test_unrelated_commands_draw_nothing():
    src = (
        "           EXEC CICS HANDLE CONDITION NOTFND(X) END-EXEC\n"
        "           EXEC CICS ASKTIME ABSTIME(WS-T) END-EXEC\n"
        "           EXEC CICS RETURN TRANSID('OCRA') COMMAREA(X) END-EXEC\n"
        "           EXEC CICS SYNCPOINT END-EXEC\n"
    )
    assert _ops(src) == []


def test_the_block_stops_at_end_exec():
    # The FILE of the NEXT command must not be read as this RECEIVE's.
    src = "           EXEC CICS RECEIVE INTO(X) END-EXEC\n           EXEC CICS READ FILE('F') END-EXEC\n"
    op = _one(src)
    assert (op["verb"], op["line"]) == ("READ", 2)


def test_word_boundaries_respect_cobol_hyphens():
    # `MY-EXEC CICS-...` is not an EXEC CICS command.
    assert _ops("           MOVE MY-EXEC TO CICS-READ FILE-X.\n") == []


# ---- PL/I --------------------------------------------------------------------


def test_pli_commands_end_at_semicolon_and_resolve_through_init():
    src = (
        " DCL QNAME_VAR CHAR(8) INIT('PLIQUE');\n"
        " EXEC CICS WRITEQ TS QUEUE(QNAME_VAR) FROM(REC);\n"
        " EXEC CICS READ FILE('ACCTS') INTO(ACCT_REC) RIDFLD(KEY);\n"
    )
    writeq, read = _ops(src, "pli")
    assert (writeq["name"], writeq["resolution"], writeq["record"]) == ("PLIQUE", "value", "REC")
    assert (read["name"], read["record"], read["line"]) == ("ACCTS", "ACCT_REC", 3)


# ---- bounded ----------------------------------------------------------------


def test_an_unterminated_exec_is_capped_and_linear():
    src = "           EXEC CICS READ FILE('F') " + "(" * 20000 + " 'x" * 20000
    start = time.perf_counter()
    extract_cics_resources(src)
    extract_boundary("cobol", "           EXEC CICS\n" * 5000)
    assert time.perf_counter() - start < 2.0


def test_many_move_statements_stay_linear():
    src = "           MOVE 'X' TO " * 20000
    start = time.perf_counter()
    extract_boundary("cobol", src + "\n           EXEC CICS READ FILE(A) END-EXEC\n")
    assert time.perf_counter() - start < 2.0


# ---- WEB / SERVICE / TRANSFORM (#3512) ----------------------------------------


def _brief(op: dict) -> tuple:
    return (op["verb"], op["kind"], op["access"], op["name"], op["qualifier"], op["record_clause"], op["record"])


def test_a_hand_written_http_provider_is_server_side():
    # zECS ZECS001.cbl: WEB RECEIVE / READ HTTPHEADER / WRITE HTTPHEADER / SEND, no session token.
    ops = _ops(
        "       01  HEADER-ACAO  PIC X(27) VALUE 'Access-Control-Allow-Origin'.\n"
        "           EXEC CICS WEB RECEIVE SET(CACHE-ADDRESS) LENGTH(RECEIVE-LENGTH)\n"
        "                MEDIATYPE(WEB-MEDIA-TYPE) RESP(WEBRESP) NOHANDLE END-EXEC.\n"
        "           EXEC CICS WEB READ HTTPHEADER(HTTP-HEADER) VALUE(HTTP-HEADER-VALUE)\n"
        "                NOHANDLE END-EXEC.\n"
        "           EXEC CICS WEB WRITE HTTPHEADER(HEADER-ACAO) VALUE(VALUE-ACAO)\n"
        "                NOHANDLE END-EXEC.\n"
        "           EXEC CICS WEB SEND FROM (CACHE-MESSAGE) FROMLENGTH(CACHE-LENGTH)\n"
        "                MEDIATYPE (WEB-MEDIA-TYPE) STATUSCODE(HTTP-STATUS-200) SRVCONVERT\n"
        "                NOHANDLE END-EXEC.\n"
    )
    assert [_brief(op) for op in ops] == [
        ("WEB RECEIVE", "WEB", "read", None, "SERVER", "SET", "CACHE-ADDRESS"),
        ("WEB READ", "WEB", "read", None, "SERVER", None, None),  # HTTP-HEADER has no fixed value
        ("WEB WRITE", "WEB", "write", "Access-Control-Allow-Origin", "SERVER", None, None),
        ("WEB SEND", "WEB", "write", None, "SERVER", "FROM", "CACHE-MESSAGE"),
    ]
    assert ops[0]["attributes"] == "LENGTH(RECEIVE-LENGTH) MEDIATYPE(WEB-MEDIA-TYPE)"
    assert ops[1]["operand"] == "HTTP-HEADER" and ops[1]["resolution"] == "unresolved"


def test_an_outbound_session_is_client_side():
    # zECS ZECS001.cbl replication: OPEN a host, CONVERSE on the session, CLOSE it.
    ops = _ops(
        "           EXEC CICS WEB OPEN HOST(URL-HOST-NAME) PORTNUMBER(URL-PORT)\n"
        "                SCHEME(URL-SCHEME) SESSTOKEN(SESSION-TOKEN) NOHANDLE END-EXEC.\n"
        "           EXEC CICS WEB CONVERSE SESSTOKEN(SESSION-TOKEN) PATH(WEB-PATH)\n"
        "                METHOD(WEB-METHOD) FROM(CACHE-MESSAGE) INTO(CONVERSE-RESPONSE)\n"
        "                NOHANDLE END-EXEC.\n"
        "           EXEC CICS WEB SEND SESSTOKEN(SESSION-TOKEN) PATH('/api/v1')\n"
        "                FROM(REQ) END-EXEC.\n"
        "           EXEC CICS WEB OPEN URIMAP('ZECSREPL') SESSTOKEN(S) END-EXEC.\n"
        "           EXEC CICS WEB CLOSE SESSTOKEN(SESSION-TOKEN) NOHANDLE END-EXEC.\n"
    )
    assert [_brief(op) for op in ops] == [
        ("WEB OPEN", "WEB", "open", None, "CLIENT", None, None),
        ("WEB CONVERSE", "WEB", "converse", None, "CLIENT", "INTO", "CONVERSE-RESPONSE"),  # INTO before FROM
        ("WEB SEND", "WEB", "write", "/api/v1", "CLIENT", "FROM", "REQ"),
        ("WEB OPEN", "WEB", "open", "ZECSREPL", "CLIENT", None, None),  # a URIMAP wins over HOST
        ("WEB CLOSE", "WEB", "close", None, "CLIENT", None, None),
    ]
    assert ops[0]["operand"] == "URL-HOST-NAME"


def test_web_commands_that_name_nothing_draw_nothing():
    assert not _ops(
        "           EXEC CICS WEB EXTRACT SCHEME(S) HOST(H) PATH(P) NOHANDLE END-EXEC.\n"
        "           EXEC CICS WEB PARSE URL(U) HOST(H) NOHANDLE END-EXEC.\n"
        "           EXEC CICS WEB READ FORMFIELD(F) VALUE(V) END-EXEC.\n"
        "           EXEC CICS WEB STARTBROWSE HTTPHEADER END-EXEC.\n"
    )


def test_invoke_service_names_the_service_and_its_channel():
    ops = _ops(
        "       01  WS-CHAN  PIC X(16) VALUE 'QUOTE-CHANNEL'.\n"
        "           EXEC CICS INVOKE SERVICE('GETQUOTE') CHANNEL(WS-CHAN)\n"
        "                OPERATION('getQuote') RESP(R) END-EXEC.\n"
        "           EXEC CICS INVOKE WEBSERVICE(WS-NAME) CHANNEL('C2')\n"
        "                OPERATION(OP-NAME) URI('http://example.com/q') END-EXEC.\n"
    )
    assert [_brief(op) for op in ops] == [
        ("INVOKE SERVICE", "SERVICE", "invoke", "GETQUOTE", "QUOTE-CHANNEL", None, None),
        ("INVOKE WEBSERVICE", "SERVICE", "invoke", None, "C2", None, None),
    ]
    assert ops[0]["attributes"] == "OPERATION('getQuote')"
    assert ops[1]["attributes"] == "OPERATION(OP-NAME) URI('http://example.com/q')"


def test_transform_names_its_transformer_and_channel():
    ops = _ops(
        "           EXEC CICS TRANSFORM DATATOXML CHANNEL('ORDERS')\n"
        "                XMLTRANSFORM('ORDERXF') DATCONTAINER('DATA') XMLCONTAINER('XML')\n"
        "           END-EXEC.\n"
        "           EXEC CICS TRANSFORM JSONTODATA CHANNEL(CH) JSONTRANSFRM('CUSTJS') END-EXEC.\n"
        "           EXEC CICS TRANSFORM XMLTODATA CHANNEL(CH) ELEMNAME(E) END-EXEC.\n"
    )
    assert [_brief(op) for op in ops] == [
        ("TRANSFORM DATATOXML", "TRANSFORM", "encode", "ORDERXF", "ORDERS", None, None),
        ("TRANSFORM JSONTODATA", "TRANSFORM", "decode", "CUSTJS", None, None, None),
        ("TRANSFORM XMLTODATA", "TRANSFORM", "decode", None, None, None, None),
    ]
    assert ops[0]["attributes"] == "DATCONTAINER('DATA') XMLCONTAINER('XML')"


def test_pli_web_commands_end_at_semicolon():
    op = _one(" EXEC CICS WEB SEND FROM(BUF) FROMLENGTH(L) MEDIATYPE('text/plain');\n X = 1;\n", "pli")
    assert _brief(op) == ("WEB SEND", "WEB", "write", None, "SERVER", "FROM", "BUF")


def test_a_pli_operand_continued_past_a_sequence_field_is_its_value():
    # #3577, navikt/DSF R0010102: the MAPSET operand's `(` ends a line whose columns
    # 73-80 hold a sequence number; the literal is on the next line.
    src = "\n".join(
        [
            "    EXEC CICS RECEIVE MAP('S001011') MAPSET (".ljust(72) + "00001010",
            "     'S001013') SET(BMSMAPBR);".ljust(72) + "00001020",
            "    EXEC CICS SEND MAP(".ljust(72) + "00018110",
            "                'S001014') MAPSET('S001013') ERASE MAPONLY;".ljust(72) + "00018120",
        ]
    )
    ops = _ops(src, "pli")
    assert [(o["verb"], o["name"], o["qualifier"], o["line"]) for o in ops] == [
        ("RECEIVE", "S001011", "S001013", 1),
        ("SEND", "S001014", "S001013", 3),
    ]


# ---- MOVE chains (#3578) --------------------------------------------------------


def test_a_name_moved_from_a_valued_name_resolves_through_it():
    # CardDemo COACTUPC: SEND MAP(CCARD-NEXT-MAP) after MOVE LIT-THISMAP TO CCARD-NEXT-MAP.
    op = _one(
        "       01  LIT-THISMAP     PIC X(7) VALUE 'CACTUPA'.\n"
        "       01  LIT-THISMAPSET  PIC X(8) VALUE 'COACTUP'.\n"
        "       01  CCARD-NEXT-MAP     PIC X(7).\n"
        "       01  CCARD-NEXT-MAPSET  PIC X(8).\n"
        "           MOVE LIT-THISMAPSET         TO CCARD-NEXT-MAPSET\n"
        "           MOVE LIT-THISMAP            TO CCARD-NEXT-MAP\n"
        "           EXEC CICS SEND MAP(CCARD-NEXT-MAP) MAPSET(CCARD-NEXT-MAPSET)\n"
        "                FROM(CACTUPAO) END-EXEC.\n"
    )
    assert (op["name"], op["resolution"], op["qualifier"]) == ("CACTUPA", "move", "COACTUP")


def test_chains_stop_at_three_hops_and_at_cycles():
    src = (
        "           MOVE 'F1' TO A\n"
        "           MOVE A TO B\n"
        "           MOVE B TO C\n"
        "           MOVE C TO D\n"
        "           MOVE D TO E\n"
        "           MOVE P TO Q\n"
        "           MOVE Q TO P\n"
        "           EXEC CICS READ FILE(D) INTO(R) END-EXEC.\n"
        "           EXEC CICS READ FILE(E) INTO(R) END-EXEC.\n"
        "           EXEC CICS READ FILE(Q) INTO(R) END-EXEC.\n"
    )
    assert [(op["name"], op["resolution"]) for op in _ops(src)] == [
        ("F1", "move"),  # D <- C <- B <- A <- 'F1': three name hops
        (None, "unresolved"),  # E is four hops away
        (None, "unresolved"),  # P and Q only feed each other
    ]


def test_a_chain_that_can_hold_two_values_is_ambiguous_and_figuratives_are_not_sources():
    ops = _ops(
        "       01  FILE-A  PIC X(8) VALUE 'ACCTFILE'.\n"
        "           MOVE 'CARDFILE' TO WS-FILE\n"
        "           MOVE FILE-A TO WS-FILE\n"
        "           MOVE SPACES TO WS-Q\n"
        "           EXEC CICS READ FILE(WS-FILE) INTO(R) END-EXEC.\n"
        "           EXEC CICS WRITEQ TS QUEUE(WS-Q) FROM(R) END-EXEC.\n"
    )
    assert [(op["name"], op["resolution"], op["candidates"]) for op in ops] == [
        (None, "ambiguous", "ACCTFILE,CARDFILE"),
        (None, "unresolved", None),
    ]


def test_a_subscripted_or_qualified_move_is_not_a_chain():
    ops = _ops(
        "       01  NAMES  VALUE 'X'.\n"
        "           MOVE TAB(I) TO WS-F\n"
        "           MOVE NAMES TO WS-G(2)\n"
        "           EXEC CICS READ FILE(WS-F) INTO(R) END-EXEC.\n"
    )
    assert (ops[0]["name"], ops[0]["resolution"]) == (None, "unresolved")
