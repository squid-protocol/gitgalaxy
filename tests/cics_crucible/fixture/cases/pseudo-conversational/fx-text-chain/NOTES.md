# fx-text-chain (runner fixture)

Not a cics-crucible case: a fixture for gitgalaxy's CICS crucible runner (#3989) in the crucible's
format (`cics-crucible/1`), used by `tests/cics_crucible/test_cics_crucible_runner.py`. It uses only
commands the harness's stub runtime models (SEND TEXT, RETURN TRANSID COMMAREA, XCTL), so its COBOL
side must pass end to end, which proves the runner's task driver, XCTL hop and COMMAREA comparison.

## The trap

None; it is the happy path of a pseudo-conversation.

## Why a naive translation breaks

It does not; the fixture tests the instrument, not a translator.

## Expected behaviour

* Task 1 (FX01 typed, EIBCALEN = 0): count 1, SEND TEXT `VISIT 001`, RETURN TRANSID(FX01) with the
  11-byte COMMAREA.
* Task 2 (ENTER): FX01 restarts with that COMMAREA (EIBCALEN = 11), count 2, RETURN TRANSID(FX01).
* Task 3 (PF3, which still starts the pending FX01): count 3, SEND TEXT, then XCTL to FXLAST with the
  COMMAREA; FXLAST runs at the same level in the same task, sends `DONE FIRST` and RETURNs with no
  TRANSID, ending the task normally.

## What a correct port must do

Carry the COMMAREA between tasks and run the XCTL target in the same task.

## Avoided ambiguities

No terminal input is read, so the contents of an unformatted RECEIVE never matter.

## Citations

* RETURN: https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-return
* XCTL: https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-xctl
