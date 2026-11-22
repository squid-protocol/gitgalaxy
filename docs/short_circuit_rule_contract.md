---
description: "> **One hit is a boolean operator whose right operand is evaluated only when the left does not already decide the result.**"
---
# The `short_circuit` rule contract (#8862)

> **One hit is a boolean operator whose right operand is evaluated only when the
> left does not already decide the result: `&&`/`||`, `and`/`or`,
> `and then`/`or else`, and the shell's `&&`/`||` chaining.**

Split out of `branch` on 2026-11-21 (Eagle Eye, #8863; decision recorded in
#8862/#8905). The `branch` contract (`docs/branch_rule_contract.md`) defines a
hit as "a keyword or operator that opens a runtime choice between control-flow
paths: the choosing construct or one of its alternative arms". A short-circuit
operator does pick a path (the right operand runs on one path only), but it is
an operator inside an expression, not a construct with arms, and the corpus
languages disagreed about it: 36 rules counted it in `branch`, Solidity, Nim,
Groovy and the dead Zig pattern did not. Two families with one-sentence
contracts replace one family with a disputed boundary.

## Levels

| level | family | what it measures |
|---|---|---|
| leaf | `branch` | statement-level choosing constructs and their arms: `if`, `else`, `switch`/`case`, loops, the ternary and `??`-style value selection |
| leaf | `short_circuit` | boolean operators that skip their right operand |
| composite | `decision_points` | `branch + short_circuit`, computed, never scanned: the cyclomatic-style count the old `branch` approximated |

Leaves are scanned and validated against a parser oracle one at a time.
Composites are arithmetic on leaves, so they inherit the leaves' validation and
add no rule of their own.

## Corollaries

**1 · Negation is not a short circuit and not a branch.** `not`, `!`, `-not`
evaluate both ways. They were counted in `branch` for lua, livecode, csharp and
powershell; they are removed from both families.

**2 · Bitwise `&`, `|` are not short circuits.** They always evaluate both
operands (`bitwise_ops` owns them).

**3 · The null-coalescing family stays in `branch`.** `??`, `?:`, `//` and the
ternary select a *value* by a condition; the branch contract names them. Only
operators on boolean operands move.

**4 · Literal shielding follows `branch`.** In every language where `branch`
reads outside string and comment literals, `short_circuit` does too.

**5 · Spellings.** C-family `&&`/`||`; word forms `and`/`or` (Python, Lua,
Zig, Scheme, Elixir, LiveCode, C# patterns); PowerShell `-and`/`-or`/`-xor`;
the shell/Makefile/Dockerfile `&&`/`||` command chaining is a short circuit
(the right command runs only on one outcome of the left).

## Verdicts

Every language whose `branch` rule counted a boolean operator moved that token
to `short_circuit` with no other change (verified per function on 71,000+
functions of 15 repositories: old `branch` = new `branch` + `short_circuit`).
Deliberate differences: negation removed (above); C# gained `&&`/`||` (it
counted only its `and`/`or` patterns); Zig now counts `and`/`or` (its rule
listed `&&`/`||`, which Zig lacks).
