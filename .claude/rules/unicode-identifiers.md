---
description: "How to write non-ASCII identifier classes in regexes and constants without tripping X-Ray or changing ASCII behaviour"
globs: "gitgalaxy/**/*.py"
---
# Unicode Identifier Classes

* **Never write literal runs of non-ASCII characters** in regexes or constants: X-Ray flags them as high entropy.
  Splice the named classes from `gitgalaxy/standards/language_standards/identifiers.py` (`ID_START`, `ID_CONTINUE`,
  `CAPITAL`, `SMALL`, `VIRAMA`, `NAME`, `NATIONAL`, `WIDE_DIGITS`, `WIDE_HYPHENS`), or build characters with `chr()`.
* **Keep each class's ASCII meaning** when swapping `[A-Z]` / `[a-z_]` / `\w` for a Unicode class: `[A-Z]` ->
  `CAPITAL`, `[a-z_]` -> `SMALL`; `\w` has no combining marks (Mn / Mc), so use `ID_CONTINUE`, not `\w`.
* Diff the changed rules' comments against main, and prove the swap with byte-identical golden masters.
