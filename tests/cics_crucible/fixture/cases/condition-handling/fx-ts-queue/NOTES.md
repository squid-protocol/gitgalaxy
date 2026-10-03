# fx-ts-queue (runner fixture)

Not a cics-crucible case: a fixture for gitgalaxy's CICS crucible runner (#3989) in the crucible's
format (`cics-crucible/1`), used by `tests/cics_crucible/test_cics_crucible_runner.py`. It uses only
commands the harness's stub runtime models: terminal RECEIVE (#4005), READQ / WRITEQ TS (#4002),
SEND TEXT and RETURN. Its COBOL side must pass end to end, which proves the translation of those
commands, the TS seeding and the final queue state.

## The trap

None beyond the in/out LENGTH of READQ TS.

## Why a naive translation breaks

A LENGTH passed by value never raises LENGERR and never reports the item's full length.

## Expected behaviour

* `FX02 T` typed on a cleared screen: RECEIVE returns those 6 bytes [RECEIVE].
* READQ TS FXQ ITEM(1) with LENGTH 8: `HELLO`, LENGTH set to 5 [READQ-TS].
* WRITEQ TS FXQ with LENGTH 5 appends item 2 and returns 2 in ITEM [WRITEQ-TS].
* READQ TS FXQ ITEM(2) into 3 bytes: LENGERR (22), `HEL`, LENGTH set to 5 [READQ-TS]; RESP given, so
  no abend.
* READQ TS FXNONE: QIDERR (44) under RESP.
* The line `FX02 T 5 2 HEL 5 22 44` is sent; RETURN ends the task. FXQ ends as `HELLO`, `HELLO`.

## What a correct port must do

Treat READQ's LENGTH as in/out, and keep TS queues outside the task.

## Avoided ambiguities

LENGTH after QIDERR is not documented; the program does not use it (WS-LEN stays 5 either way:
the harness sets it only on NORMAL and LENGERR).

## Citations

* [RECEIVE] https://www.ibm.com/docs/en/cics-ts/5.5.0?topic=summary-receive-zos-communications-server-default
* [READQ-TS] https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-readq-ts
* [WRITEQ-TS] https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-writeq-ts
