# Benchmark: COACTUPC, the deterministic port refined by a model under proof (B2)

COACTUPC is CardDemo's account update. It is the largest CICS program in CardDemo: 66 GO TOs, a PERFORM … THRU dispatcher, and 4,200 lines of COBOL. `det_port.py` translated it with no model and the translation proved. Then `det_refine.py` gave each of its 109 paragraph methods to a model (claude-sonnet-5-5, through the command backend) to rewrite for a reader. Every rewrite was proven against GnuCOBOL before it was kept.

| | det port (dispatch style) | refined, every step proven |
|---|---|---|
| paragraph methods | 109 | 109 rewritten, **109 kept**: 98 on the first attempt, 11 on the retry, 0 reverted |
| `Cobol.*` runtime calls | 3,614 | **1,347** (−63%) |
| `if (true)` scaffolding | 77 | **0** |
| lines (non-comment) | 6,816 | 6,843 (Javadoc per paragraph, 88 helper methods) |
| model time | | 585 s (10 largest) + 2,958 s (the other 99) |

**Final proof.** The refined port was proven from scratch, without reusing the build of any step: `equivalence.py run carddemo-acctupdate --port … --faults all`. All 54 scenarios pass, with **156 of 156 events equal**, covering 89 of 95 paragraphs and 256 of 397 branches.

## What the model does, and does not do

Example: paragraph 3100-SCREEN-INIT, before and after.

```java
// before: as translated
/** 3100-SCREEN-INIT. */
private int p47() {
    // MOVE LOW-VALUES TO CACTUPAO
    Cobol.moveFigurative(Figurative.LOW_VALUES, f704_CACTUPAO, CS);
    ... 13 more MOVEs of titles, names, date and time parts ...
    return 48;
}

// after: proven equal
/**
 * 3100-SCREEN-INIT.
 * Clears the CACTUPAO output map, then fills in the standard header:
 * screen titles, transaction id, program name, and the current date
 * (MM/DD/YY) and time (HH:MM:SS).
 */
private int p47() {
    Cobol.moveFigurative(Figurative.LOW_VALUES, f704_CACTUPAO, CS);
    Cobol.move(DetCics.currentDate(task.now()), f1031_WS_CURDATE_DATA, CS);
    moveHeaderTexts();
    Cobol.move(DetCics.currentDate(task.now()), f1031_WS_CURDATE_DATA, CS);
    formatCurrentDate();
    formatCurrentTime();
    return 48;
}
```

Across the program, the model's changes are of these kinds:
- a Javadoc on every paragraph;
- 88-level conditions as named predicates;
- else-if chains;
- `if (true) throw` scaffolding gone;
- statement runs extracted into named helpers.

The model does not touch the data or the control machinery. Fields are still byte storage, and the dispatcher's `return GOTO | n` values are kept exactly. Note also that the COBOL read `FUNCTION CURRENT-DATE` twice, and the rewrite reads it twice too, because removing the second read would change behaviour if the clock ticks between them.

Typed state (B3) does not apply here: COACTUPC has GO TOs, so it stays in the dispatcher style, and B3 runs on the structured style.

## Files

- `CoactupcService.refined.java`: the refined port.
- `refine-largest10.json` and `refine-rest.json`: per method, the verdict, the attempts, and the size before and after.

Reproduce:

```
det_port.py run carddemo-acctupdate --work W
det_refine.py run carddemo-acctupdate --port W/carddemo-acctupdate/port --work R --largest 10
det_refine.py run carddemo-acctupdate --port R/port --work R2 --skip <the 10>
```
