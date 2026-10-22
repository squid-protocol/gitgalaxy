# Spot-check of the "equivalent" mutation verdicts (#4443)

The crucible mutation re-run (`mutation_scores.json`, seed 0, 24 mutants per port) judged its equivalent survivors by
reading the code. This note re-reads a sample against the port source (`tests/cics_crucible/ports/<case>/<PROGRAM>/overlay`)
and, where the logs matter, the cics-crucible expected logs. A verdict is *verified* when the port source shows no input,
scenario or log field that can tell the mutant from the original.

Population: 45 `equivalent` survivors on the 13 re-run non-PC ports (the issue's "35" was the count at the first run; CAXB's
`* 10000` and the byte-overload mutants were triaged later). Sample: 22, at least one per port (GTWORK has no equivalent survivor) and one per reason
pattern. Result: **22 of 22 verdicts hold; no new case.** The sample is not the population: the 23 left are the same
patterns (PIC-width padding, `>` against `>=` at an exact length) on other lines.

| Id | Port | Mutant | Why it is equivalent (re-read) |
|---|---|---|---|
| 53c5ddc54f | CALINK | delete `lastAnswerBytes = task.returnedBytes()` | The program RETURNs with no COMMAREA, so `returnedBytes()` is null on every path and the field is already null. |
| 73e0381a3f | CALINK | `CA-SPARE` pad 52 -> `""` | Only moved into the DTO, whose setter fits the field. |
| 1aad44314d | CALINK | `caRc` initial width | WS-BLOCK's `caRc` has no VALUE and is set by INITIALIZE before any read. |
| 5aa61355b2 | CASUB | `CA_RC_LEN` 2 -> 3 | Padded literal goes through the fitting DTO setter. |
| dd9339193f | CASUB | delete the early-branch `returnTransid(null, null)` | Followed by `return;`: the task ends with the same RETURN. |
| 49780bea21 | CAXA | delete `lastAnswerBytes = ...` | Same as CALINK: RETURN carries no COMMAREA. |
| 712ac2d987 | CAXA | `NB-NOTE` padded to 56 | NB-NOTE is X(55); the setter cuts the extra byte. |
| 2e18d5d59b | CAXB | `% 10000` -> `* 10000` on the destination | The destination is WS-V2's V2-VISITS, zeroed by INITIALIZE, so it is 0 and `0 * 10000 == 0 % 10000`. |
| 75ff65736f | CAXB | `HALF_UP` for `DOWN` in `packedValue` | Every argument is a DTO balance of scale 2 (`ws.setV2Balance(ZERO.setScale(2))`), so the rounding mode never runs. |
| 6c161a5327 | GTSTART | `WS-MSG` padded to 21 | Read through `from(WS_MSG, 20)`: the same 20 bytes. |
| 76e09c858a | GTSHOW | `ptr < 2` for `ptr < 1` | `wsPtr` starts at 6 (`VALUE 6`) and only grows. |
| e1af5f4c7f | GTSHOW | negate the `retrieved.length() >= 0` guard | `wsLen` is read only by `log.info`, not compared or sent. |
| bc5f415dc9 | GTSHOW | `\|\|` -> `&&` in the pointer guard | With the guard off, an overflowing pointer leaves at the loop's own `ptr > receiver.length` break. |
| fb26767f06 | GTTERM | `spaces(21)` for `spaces(20)` | `wsInput` is read only at `charAt(5)`. |
| 2ec7aa6941 | HCMAIN | `WS-JUNK` 8 -> 9 | Never read, only its length bounds a copy. |
| 0aeb937462 | HCMAIN | negate `mode.length() >= 0` | `ws.mlen` is not read after the READQ TS that sets it. |
| 16686d8eec | HCSUB | negate `previous == null` | HCSUB never LINKs, so `previous` is always null: `set(null)` and `remove()` both give `get() == null`. Holds while HCSUB.cbl issues no LINK/XCTL. |
| b3a42395d3 | HCSUB | `sum <= 0` for `sum < 0` | At `sum == 0` the magnitude is 0, and `-0 == 0`. |
| ba2f399e63 | HCQREAD | `resp` initial 1 for 0 | `ws.resp` is assigned from the first READQ (`run.respond`) before `respD` reads it. |
| c059512ee1 | HCQREAD | `eibresp` initial 1 for 0 | Set by `Run.eibresp(..)` after each command, before line 52's `MOVE EIBRESP`. |
| d0ffb53476 | HXATTR | delete `map.setBrite(low(..))` | First screen: line 145 sets BRITE right after. Echo screen: BRITE is not received, and the cics-crucible `echo-dataonly` log shows a DATAONLY send omits BRITE (no data, no real attribute) whether it is null or X'00'. RAW and TWIDDLE follow the same way. |
| 97c29c5729 | HXEXT | delete `out.setAcct(lowValues(..))` | Same: LOW-VALUES and an unset DTO field both log as no data in the SEND MAP event. |

The population is `mutation_scores.json` (`verdict == "equivalent"`); `tests/cobol_mainframe/test_equivalent_spot_check.py`
fails if a sampled id above stops being equivalent or a port loses its sample.

## Assumptions the verdicts rest on

- HCSUB's `previous == null` mutant is equivalent only while HCSUB never runs nested in itself. A case that LINKs HCSUB
  from HCSUB would make it a case gap.
- The HXATTR/HXEXT "no data" claim rests on the SEND MAP log treating null and X'00' alike (the DATAONLY rule in the
  cics-crucible expected logs). I read that rule; I did not rebuild the mutant for this note.
- The rest are read, not run: the survivors already ran green against every scenario in the mutation re-run, so they
  confirm the reading without proving it. The oracle is the stub, not z/OS.
