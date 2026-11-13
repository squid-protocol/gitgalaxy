# EXEC CICS operand types: det's data-area / data-value audit (#8058)

IBM's CICS TS 6.x command pages declare each operand a **data-area** (a COBOL data name only), a **data-value** (a
sender: a data name or a constant) or a pointer / CVDA ("EXEC CICS command argument values": "For a data-value, you can
also use a constant"). det reads a data-area through `Cics.ref` / `field` / `read_field` and refuses a literal there
(`not a data area ... source defect`, #7959). A data-value goes through `Cics.value_text` (#8057, #8066): a data name
keeps its old path, a constant is its value, a figurative constant is refused by name. The option-by-option audit was
done in #8066 (IBM topic names below are `summary-<command>` under CICS TS 6.x); this page keeps it in the repo.
`tests/cobol_mainframe/test_det_cics_operand_forms_8058.py` pins every call site, so a new one needs a row here.

## Senders and options checked

| Command | Option | IBM type | det path |
|---|---|---|---|
| WEB CONVERSE | SESSTOKEN, URIMAP | data-value | `value_text` |
| WEB CONVERSE | PATH, QUERYSTRING, FROM, MEDIATYPE, STATUSTEXT, INTO | data-area | `read_field` / `field` |
| WEB CLOSE | SESSTOKEN | data-value | `value_text` |
| WEB OPEN | HOST | data-value | `value_text` |
| WEB OPEN | SESSTOKEN (receiver) | data-area | `field` |
| WEB SEND (server) | DOCTOKEN, MEDIATYPE | data-value | `value_text` (a quoted MEDIATYPE literal keeps #6876's path) |
| WEB SEND | FROM, STATUSTEXT | data-area | `read_field` |
| WEB PARSE URL | URL | data-value | `value_text` |
| WEB PARSE URL | SCHEMENAME, HOST, HOSTLENGTH, PATH, PATHLENGTH, QUERYSTRING, QUERYSTRLEN, PORTNUMBER (receivers) | data-area | `field` / `ref` |
| WEB WRITE HTTPHEADER | SESSTOKEN | data-value | `value_text` |
| WEB WRITE HTTPHEADER | HTTPHEADER, VALUE | data-area | literal accepted (#6876): looser than IBM, see gaps |
| WEB READ HTTPHEADER | HTTPHEADER | data-area | literal accepted: looser than IBM, see gaps |
| WEB READ HTTPHEADER | VALUE, VALUELENGTH (receivers) | data-area | `field` / `ref` |
| WEB READ QUERYPARM | QUERYPARM | data-value | `value_text` |
| WEB READ FORMFIELD, WEB STARTBROWSE FORMFIELD / QUERYPARM | FORMFIELD, QUERYPARM | data-area | `read_field` |
| WEB READNEXT / EXTRACT / RECEIVE / RETRIEVE, EXTRACT TCPIP | every operand read through `field` / `ref` | receivers | `field` / `ref` |
| DOCUMENT CREATE | TEXT, BINARY; DOCTOKEN (receiver) | data-area | `read_field` / `field` |
| DOCUMENT RETRIEVE | DOCTOKEN; INTO, LENGTH (receivers) | data-area | `read_field` / `field` / `ref` |
| WRITE OPERATOR | TEXT, ROUTECODES | data-value | `value_text` |
| VERIFY PASSWORD | USERID | data-value | `value_text` |
| GETMAIN | INITIMG | data-value, but "In COBOL programs only, you must use a data area" | literal refused (IBM's COBOL rule) |
| PUT / GET / GETNEXT CONTAINER | FROM; INTO, FLENGTH, CCSID, CONTAINER (receivers) | data-area | `read_field` / `field` / `ref` |
| WRITEQ TS / TD | FROM | data-area | `read_field` |
| READQ TS / TD | INTO, LENGTH, ITEM, NUMITEMS (receivers) | data-area | `field` / `ref` |
| START | FROM | data-area | `read_field` |
| CONVERSE | FROM; INTO, TOLENGTH (receivers) | data-area | `read_field` / `ref` / `field` |
| SEND MAP | FROM | data-area | `ref` |
| SEND TEXT | FROM; LENGTH | data-area; data-value (`summary-send-text`, read 2026-11-09) | `read_field`; `int_` (a literal length is accepted) |
| SEND (terminal, no MAP / TEXT) | FROM; LENGTH, FLENGTH, CTLCHAR | data-area; data-value (`summary-send-3270-logical`, read 2026-11-09) | `read_field`; `int_` (a literal length is accepted); non-empty CTLCHAR / CURSOR refused by name ("not modelled", not a data-area refusal); shares SEND TEXT's path |
| RECEIVE / RECEIVE MAP | INTO, LENGTH (receivers) | data-area | `field` / `ref` |
| READ / READNEXT / READPREV / STARTBR / RESETBR / DELETE / WRITE | RIDFLD | data-area | `field` |
| READ | INTO, LENGTH, TOKEN (receivers) | data-area | `field` / `ref` |
| WRITE / REWRITE | FROM | data-area | `read_field` |
| LINK / XCTL / RETURN | COMMAREA | data-area | `ref` |
| FORMATTIME / ASKTIME | ABSTIME, the date and time forms | data-area / receivers | `field` / `ref` |
| BIF DEEDIT | FIELD (read and written) | data-area | `field` |
| ASSIGN, INQUIRE ASSOCIATION / URIMAP / PROGRAM, RESP / RESP2, FETCH, RUN TRANSID, RETRIEVE, WAIT / POST, FREEMAIN | receivers | data-area | `field` / `ref` |
| GET / UPDATE COUNTER | VALUE, INCREMENT, COMPAREMIN / COMPAREMAX (senders) | not a data-area path | `ref` only for a raw data area, else `long_` / `int_` |

12 data-value options were read as data-areas: 2 fixed in #8057, 10 (in 8 commands) in #8066.

## Sibling gaps

- **WEB WRITE / READ HTTPHEADER** `HTTPHEADER` and `VALUE`: IBM declares them data-areas, det accepts a literal
  (#6876). The opposite direction (det looser than IBM); tightening could change burned ports, so it waits for an
  owner ruling.
- **Figurative constant as a data-value** (`TEXT(SPACES)`): refused by name; its length at each option is not modelled.
- **GETMAIN INITIMG**: refusal is right (IBM's COBOL rule).

## Call sites pinned by the test

Each entry is `function` (kind, count): `area` is the strict path, `value` is `value_text`.

- `cics.py`: `_value_name` (area 1), `commarea_bytes` (area 1), `commarea_out` (area 1), `constant` (area 1), `constant_int` (area 1), `field` (area 1), `in_dfhcommarea` (area 1), `linkage_record` (area 1), `outcome` (area 2), `pointer` (area 1), `read_field` (area 1), `size` (area 1), `value_text` (area 1)
- `cics_conditions.py`: `assign` (area 2)
- `cics_containers.py`: `channel_command` (area 1), `container` (area 4), `container_browse` (area 2)
- `cics_counters.py`: `_cint` (area 1), `_clong` (area 1), `_cstore` (area 2)
- `cics_filecontrol.py`: `browse_length` (area 1), `delete_generic` (area 1), `file_update` (area 3), `rba_browse` (area 2), `read` (area 3), `read_length` (area 1), `read_set` (area 2), `record_from` (area 1), `token_out` (area 1)
- `cics_program.py`: `dispatch_program` (area 1)
- `cics_queues.py`: `dispatch_queues` (area 3), `readq_td` (area 2), `ts_queue` (area 6)
- `cics_storage.py`: `load_release` (area 1), `storage` (area 1)
- `cics_system.py`: `dispatch_system` (area 8), `dispatch_system` (value 3), `inquire_association` (area 2), `inquire_urimap` (area 1)
- `cics_taskcontrol.py`: `converse` (area 4), `fetch` (area 4), `post` (area 1), `retrieve` (area 4), `run_transid` (area 1), `start` (area 1)
- `cics_terminal.py`: `dispatch_terminal` (area 3), `map_names` (area 1), `receive` (area 3), `receive_map` (area 1), `send_map` (area 1)
- `cics_web.py`: `document` (area 5), `extract_tcpip` (area 1), `put` (area 1), `received` (area 1), `store` (area 2), `text` (area 3), `text` (value 1), `value` (value 1), `web` (area 4), `web` (value 2), `web_forms` (value 1), `web_parse` (area 4), `web_parse` (value 1), `web_request` (area 2), `web_request` (value 1), `web_send` (area 1)
