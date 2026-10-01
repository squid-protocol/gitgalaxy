# Porting loop: COACTUPC (carddemo-acctupdate)

Model `claude-sonnet-5-5` (agent): **proven on attempt 1**, 1313 s.

| attempt | verdict | outputs | faults proven | prompt tokens | port s | prove s |
|---|---|---|---|---|---|---|
| 1 | proven | enter-from-menu 2/2, no-commarea 2/2, enter-from-card-list 2/2, search-account 3/3, search-account-blank 3/3, search-account-not-numeric 3/3, search-account-zeros 3/3, search-account-not-in-xref 3/3, search-xref-read-error 3/3, search-account-not-in-master 3/3, search-account-file-not-open 3/3, search-customer-not-in-master 3/3, search-customer-read-error 3/3, search-zip-plus4-shown-as-5-digits 3/3, edit-no-changes 3/3, edit-only-case-differs 3/3, edit-status-not-yes-no 3/3, edit-status-blank 3/3, edit-days-blank 3/3, edit-dates-out-of-range 3/3, edit-dates-not-numeric 3/3, edit-dates-not-on-calendar 3/3, edit-credit-limit-not-numeric 3/3, edit-credit-limit-blank 3/3, edit-signed-amounts 3/3, edit-ssn-part1-666 3/3, edit-ssn-parts-not-numeric 3/3, edit-fico-out-of-range 3/3, edit-names-not-alphabetic 3/3, edit-last-name-and-address-blank 3/3, edit-city-and-country-not-alphabetic 3/3, edit-state-not-valid 3/3, edit-zip-not-numeric 3/3, edit-zip-leading-zero-refused 3/3, edit-phone-parts-missing 3/3, edit-phone-area-code-not-general-purpose 3/3, edit-eft-zero-and-holder-not-yes-no 3/3, edit-again-after-errors 3/3, enter-again-awaiting-confirmation 3/3, pf5-confirms-and-rewrites 3/3, pf5-account-changed-meanwhile 3/3, pf5-customer-changed-meanwhile 3/3, pf5-account-lock-fails 3/3, pf5-customer-lock-fails 3/3, pf5-account-rewrite-fails 3/3, pf5-customer-rewrite-fails 4/4, pf5-before-changes-acts-as-enter 3/3, invalid-key-acts-as-enter 3/3, pf12-rereads-discarding-edits 3/3, pf12-before-search-acts-as-enter 3/3, done-starts-over 2/2, lock-error-starts-over 2/2, pf3-back-to-menu 2/2, pf3-back-to-caller 2/2 | -- | None | 1271 | 16 |

## Attempt 1: proven


The model's notes:

```
# COACTUPC port notes

`./prove.sh`: PROVEN (every output equal, every fault run equal).

## Defects of the original, kept (each with its one-line fix)

1. **0000-MAIN, first IF** tests `CDEMO-FROM-PROGRAM = LIT-MENUPGM AND NOT CDEMO-PGM-REENTER` before
   CARDDEMO-COMMAREA is loaded from DFHCOMMAREA, so it only ever sees the initial spaces and the OR is never true (only
   `EIBCALEN = 0` re-initialises). The same test in the EVALUATE (after the load) is the one that works.
   Fix: move the IF below the two MOVEs of DFHCOMMAREA.
2. **1260-EDIT-US-PHONE-NUM**, "phone not entered" test: its third clause is `NUMA = SPACES OR NUMC = LOW-VALUES`
   (NUMA again, and NUMC against LOW-VALUES only). Fix: `(NUMC = SPACES OR NUMC = LOW-VALUES)`.
3. **EDIT-DATE-LE** (CSUTLDPY): when CSUTLDTC rejects a date, `GO TO EDIT-DATE-LE-EXIT` falls into
   `SET WS-EDIT-DATE-IS-VALID TO TRUE`, so the year/month/day flags come back valid (only INPUT-ERROR and the message
   show the failure; no field is highlighted). Fix: `GO TO EDIT-DATE-CCYYMMDD-EXIT`.
4. **2000-DECIDE-ACTION**, after 9600-WRITE-PROCESSING: `COULD-NOT-LOCK-CUST-FOR-UPDATE` is not tested, so a customer
   record that could not be locked ends as "changes committed" (state `C`). Fix: add it to the lock-error WHEN.
5. **9000-READ-ACCT**: `DID-NOT-FIND-ACCT-IN-ACCTDAT` / `DID-NOT-FIND-CUST-IN-CUSTDAT` are WS-RETURN-MSG values that
   9300 / 9400 no longer set (their SETs are commented out), so the exits are dead: a missing account or customer
   record goes on to the next read and to 9500-STORE-FETCHED-DATA with the previous (blank) ACCOUNT-RECORD /
   CUSTOMER-RECORD. Fix: test `FLG-ACCTFILTER-NOT-OK` / `FLG-CUSTFILTER-NOT-OK` instead.
6. **9600-WRITE-PROCESSING**: ACCT-UPDATE-RECORD has no ACCT-ADDR-ZIP, so its GROUP-ID lands on the ACCOUNT-RECORD's
   ACCT-ADDR-ZIP bytes (102-111) and ACCT-GROUP-ID (112-121) is rewritten as spaces. Fix: add
   `15 ACCT-UPDATE-ADDR-ZIP PIC X(10)` before GROUP-ID (and move ACCT-ADDR-ZIP into it).
7. **1230-EDIT-ALPHANUM-REQD / 1240-EDIT-ALPHANUM-OPT** are never PERFORMed (dead); ported as unused methods.
   In **2000-DECIDE-ACTION** the `ACUP-CHANGES-OKAYED-AND-DONE` WHEN is unreachable (0000-MAIN handles that state
   first) and WHEN OTHER (abend 0001) is reached only by an unknown ACUP-CHANGE-ACTION value.
8. 9200/9300/9400 test `WS-RETURN-MSG-OFF` before building the not-found message, but 9400 moves ERROR-RESP / RESP2
   first; harmless, kept as is.

## Facts found contradicted / not in the facts

- facts.json lists only the XCTL and the RETURN TRANSID as calls. The CSUTLDPY copybook also does
  `CALL 'CSUTLDTC'` (EDIT-DATE-LE) for every date edit; the port calls the generated CsutldtcService for it
  (the date is passed as its 8 characters, space padded to the called program's X(10)).
- RETURN passes the generated CoactupcCommarea (CARDDEMO-COMMAREA + WS-THIS-PROGCOMMAREA, 1033 bytes) with
  LENGTH 2000 (LENGTH OF WS-COMMAREA), as the source says.
- The task's COMMAREA DTO hands numeric-looking X items that a PIC 9 item redefines (ACUP-OLD-CUST-ID-X,
  ACUP-OLD-CUST-SSN-X, ...) without their leading zeros ("24" for "000000024"); the port zero-fills such a value back to the
  item's width on load (`numX`). The ACCT-ID-X items arrive intact.
- TEST-NUMVAL-C accepts the default currency sign `$` before the number (`$25.75` is valid), which the generated
  CobolRecords.numval does not parse: the port validates with its own TEST-NUMVAL-C and hands the text, commas and `$`
  removed, to CobolRecords.numval.
```
