# Benchmark: COTRN02C, typed then refined, every step proven (B3 + B2)

COTRN02C is CardDemo's "add a transaction" screen. It is the largest CardDemo CICS program with no GO TO, so it takes the structured style. That makes it the first program where all three readability layers stack:

| stage | tool | `Cobol.*` runtime call sites | proven |
|---|---|---|---|
| deterministic port, structured | `det_port.py --style structured` | 494 | yes |
| + typed state: 35 items as `String` / `long` / `BigDecimal` | `det_port.py --style structured --typed` | 442 | yes |
| + a model refactors every method | `det_refine.py` (claude-sonnet-5-5) | **319** (−35%) | yes, after every step |

**The refinement.** 19 of 19 methods were kept: 18 on the first attempt, 1 on the retry, and none reverted. It took 518 s. All 15 `if (true)` workarounds are gone.

**The final proof.** The refined port was proven again from scratch, with no build reused. It passes all **31 scenarios with 88 of 88 events equal**, covering 18 of 18 paragraphs and 56 of 75 branches, with faults on.

## Example: INITIALIZE-ALL-FIELDS

```java
// typed det port: 16 runtime calls
/** INITIALIZE-ALL-FIELDS. */
private void initializeAllFields() {
    Cobol.move(DM1, actidinl, CS);
    Cobol.moveFigurative(Figurative.SPACES, actidini, CS);
    ... 13 more moveFigurative(SPACES, ...) ...
    Cobol.moveFigurative(Figurative.SPACES, wsMessage, CS);
}

// refined: proven equal
/**
 * INITIALIZE-ALL-FIELDS: resets the transaction-add screen (COTRN2AI).
 * The account id length is set to -1 (cursor position flag), and every
 * input field plus the message line is cleared to spaces.
 */
private void initializeAllFields() {
    Cobol.move(DM1, actidinl, CS);
    moveSpaces(actidini, cardnini, ttypcdi, tcatcdi, trnsrci, trnamti, tdesci,
            torigdti, tprocdti, midi, mnamei, mcityi, mzipi, confirmi, wsMessage);
}
```

**Reading the metric.** The count is of runtime *call sites*, and part of the drop comes from helpers like `moveSpaces(...)` that collapse repeated calls. The runtime does the same work. The fields above are the screen map's, which stay as byte storage: typing those groups is the next step.

## Files

- `Cotrn02cService.typed.java`: the typed det port.
- `Cotrn02cService.typed-refined.java`: the typed port after refinement.
- `refine.json`: per method, the verdict, attempts and size.

With port_runner, the same flow on a generated project:

```
port_runner run    <project> --ticket COTRN02C --backend det --typed --source-root <estate>
port_runner prove  <project> --ticket COTRN02C --command "<proof with {port_dir} {report_dir}>"
port_runner refine <project> --ticket COTRN02C --backend command --command "..." --prove-command "<same proof>"
port_runner review <project> --ticket COTRN02C --approve --by <reviewer>
```
