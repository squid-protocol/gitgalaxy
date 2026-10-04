---
description: "> **One hit is a comment that holds code: a keyword-led line (the original"
---
# The `dead_code` rule: commented-out statements (#4171)

> **One hit is a comment that holds code: a keyword-led line (the original
> rule), or, in a `;`-terminated C-family language, a commented-out
> statement (a call, an assignment, or a declaration) ending in `;`.**

This is a partial contract. The `dead_code` row in
`gitgalaxy/standards/signal_contracts.py` is still `draft`; this note states
the statement-shaped extension added in #4171 and its limits.

## Why

The rules only recognised a commented line that starts with a keyword
(`// public …`, `// if (…)`, `// return …`). Commented-out statements did not
count, and in machine-translated code they are often where the translator gave
up. IBM WCA4Z's published `Lgacdb01.java` (sandeephans/validation-c2j @
967d00b) has 11 commented-out code lines, the dropped date-of-birth binding and
error path among them; it read 0 and now reads 11.

## What counts

The shared fragment is `COMMENTED_STATEMENT_C_FAMILY` in
`gitgalaxy/standards/language_standards/_shared_patterns.py`. It applies after
`//` or `/*` (never a `///` or `/**` doc line), to one line, ending in `;`:

| Form | Counts | Does not count |
|---|---|---|
| Call | `// errorMsg.writeErrorMessage();`, `/* foo.bar(x); */` | `// see foo(bar) for details` (no `;`) |
| Assignment | `// caReturnCode = 90;`, `// count += 1;` | `// e.g. x == y;` (a comparison) |
| Declaration, capitalised type | `// CaCustomerRequest r = new CaCustomerRequest();` | `// Load data;`, `// Returns the value;` (no initializer) |
| Declaration, primitive or inferred type | `// long n = 0;`, `// int x;` | `// Version 2;` |

Prose is protected by the terminal `;` and by the identifier-first shape:
`// Note that a = b;` and `// TODO: fix this later;` don't count.

## Languages

- **Applied:** java, c, cpp, csharp, javascript, typescript, dart, rust. Each
  keeps its keyword alternative, plus the statement fragment.
- **Not applied:** kotlin, go, swift, scala, and groovy (where `;` is
  optional). These languages have no statement terminator to anchor on, so a
  statement shape would also match prose. Their keyword-led rule is unchanged.
- **php:** keeps its own `$`-variable rule.

The pins are in `tests/extraction/languages/test_dead_code_statements.py`.
