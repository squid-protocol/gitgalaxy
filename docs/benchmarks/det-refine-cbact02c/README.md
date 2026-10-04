---
description: "- `Cbact02cService.structured.java` -- the deterministic port (`tests/tools/det_port.py --style structured`), proven"
---
# CBACT02C: a deterministic port, refactored by a model under proof

- `Cbact02cService.structured.java` -- the deterministic port (`tests/tools/det_port.py --style structured`), proven
  equivalent to the COBOL: no model involved.
- `Cbact02cService.refined.java` -- the same port after `tests/tools/det_refine.py` (model: claude-sonnet-5-5 via
  `claude -p`): each paragraph method rewritten by the model, applied, and the case proven again (every scenario and
  fault run) before it was kept. 7/7 methods kept; 2 needed a second attempt after the proof rejected the first.
- `refine.json` -- per method: attempts, verdict, size before / after.

What the model changed: a Javadoc per paragraph saying what it does, else-if chains for nested IF / ELSE IF, the
88-level conditions as named predicates (`isApplAok()`), the `if (true)` artefacts gone. What it could not change:
the program's data is still COBOL's byte storage (`Cobol.move(D16, applResult, CS)`) -- lifting it into typed Java
state is the next step, under the same proof.

The model only ever rewrites code that is already proven; a rewrite the proof rejects is reverted, so the port is
proven after every step.
