# The `api` rule's contract

> Filed as [#2730](https://github.com/squid-protocol/gitgalaxy/issues/2730). This document is the
> stated contract the issue asked for, plus the audit of all 46 corpus languages against it.
> `gitgalaxy/standards/how_to_add_a_language.md` carries the one-line form next to the rule in the
> output schema; this file carries the reasoning, the fallback family, and the per-language verdicts.

## The contract

> **`api` matches a declaration that makes a named function or type visible outside the file it is
> declared in.**

Three corollaries, each of which the audit below found a language violating:

1. **A reference is not a declaration.** A call site, an import, a struct-literal field key, a
   `switch` case on the keyword, a package segment that happens to be spelled `internal` — none of
   these publish a name, they consume one. (`cobol` counted `CALL`; `go` counted `Protocol:
   protocol,`; `kotlin` counted `import okhttp3.internal.X`; `powershell` counted `return (`.)
2. **A modifier counts where it modifies a declaration, not wherever it appears.** `\bpublic\b`
   against a raw code stream is not a measurement of public surface; it is a measurement of how
   often the word occurs, string literals included. The modifier must be anchored to the
   declaration it applies to. (`java`, `csharp`, `kotlin`, `php`, `groovy`, `swift`, `typescript`.)
3. **Where the language makes things public by default, the declaration itself IS the marker.**
   `python` has always read `def <name>` this way, and `lua`, `scala`, `livecode`, `fortran` and
   `powershell` follow it. A language whose functions are public unless marked otherwise must count
   the declaration, or it measures 0 forever. (`abap` `FORM`, `perl` `sub`, `matlab` `function`,
   `dart`'s top-level function, `ada`'s library-level subprogram.)

### The documented fallback family

Some languages have no per-function visibility concept at all. For those, `api` counts the
**file-level declaration that exposes the file's surface**, and that substitution is deliberate,
not a defect:

| language | stands in for a public function declaration |
|---|---|
| `dockerfile` | `EXPOSE <port>` |
| `yaml` | a workflow `on:` trigger block |
| `css` | `:root`, `@property`, a `--custom-property:` definition |
| `html` | `id=`/`name=`/`itemprop=`/`<slot>`/`og:`/`twitter:` — the document's addressable surface |
| `yacc` | `%define`/`%code`/`%provides`/`%requires` |
| `m4` | `AC_SUBST`/`AC_DEFINE`/`AC_PROVIDE`/`m4_provide` |
| `cobol` | `ENTRY`, `LINKAGE SECTION` |
| `agc_assembly` | `<LABEL> EQUALS` |
| `makefile` | `.PHONY`, `export`, the conventional public targets |
| `sqlite` | `CREATE [TEMP] VIEW` / `CREATE VIRTUAL TABLE` |
| `matlab` | a column-0 `function` declaration (a function file's callable surface) |
| `jcl` | `//name PROC` — a cataloged or in-stream procedure, what `EXEC name` in other members invokes ([#2748](https://github.com/squid-protocol/gitgalaxy/issues/2748)) |

`matlab` is the one place where the fallback is knowingly approximate: a `.m` function file
publishes only its *leading* function, and local functions after it are file-private, but nothing
in the syntax distinguishes them — the file's name does. Counting every column-0 `function` is the
same order of approximation as `python` counting a nested `def`, and it is strictly better than the
0 the rule reported before, which said a file full of callable functions had no public surface at
all.

## What this is used for

`api` feeds `_calc_api_exposure` and `_calc_documentation` in `signal_processor.py`, both of which
land in scored risk, and `galaxyscope.py`'s Contextual Baseline Fix converts an imported file's
uncalled orphans into `api` on top of the rule's own count (see #2731/#2734 for why the conversion
now subtracts the orphans the rule already declared). A rule that is too narrow reads 0 for a file
that exposes everything it defines; a rule that is too broad turns a modifier's word frequency into
scored risk. Both directions are wrong in the same units.

## The audit — all 46 corpus languages

Counts are `api` matches over the **code stream** (comments stripped, exactly what the engine
scans), on the `language-crucible` corpus at `v1.2.0` and on the `keyword-rosetta` control corpus.
`a → b` is this change; a single number means the rule was already inside the contract and is
untouched.

| language | crucible | keyword-rosetta |
|---|---|---|
| `abap` | 6 | 0 → 13 |
| `ada` | 0 | 0 → 13 |
| `agc_assembly` | 367 → 44 | 4 |
| `apex` | 0 | 12 |
| `assembly` | 284 → 281 | 12 |
| `c` | 8675 → 1141 | 29 → 15 |
| `cobol` | 1396 → 553 | 10 |
| `cpp` | 4 | 12 |
| `csharp` | 387 | 12 |
| `css` | 3618 | 4 |
| `dart` | 174 → 149 | 0 → 13 |
| `dockerfile` | 0 | 4 |
| `embedded_python` | 123 | 13 |
| `fortran` | 0 | 13 |
| `go` | 614 → 438 | 12 |
| `groovy` | 16 → 12 | 12 |
| `haskell` | 3 | 4 |
| `html` | 514 | 5 |
| `java` | 220 | 12 |
| `javascript` | 267 | 12 |
| `jcl` | `None` → 13 | n/a → 1 (#2748) |
| `kotlin` | 17 → 5 | 12 |
| `livecode` | 607 | 13 |
| `lua` | 288 → 272 | 13 |
| `m4` | 242 | 12 |
| `makefile` | 0 | 13 |
| `markdown` | rule is `None` | n/a |
| `matlab` | 0 → 23 | 0 → 13 |
| `objective-c` | 5 → 13 | 0 |
| `perl` | 20 → 840 | 0 → 13 |
| `php` | 1153 → 1146 | 12 |
| `powershell` | 199 → 154 | 12 |
| `python` | 4086 | 13 |
| `ruby` | 0 | 12 |
| `rust` | 943 | 12 |
| `scala` | 354 | 13 |
| `scheme` | 1 | 12 |
| `shell` | 178 | 12 |
| `solidity` | 49 | 12 |
| `sqlite` | 2 | 0 |
| `swift` | 214 → 212 | 12 |
| `tcl` | 24 | 12 |
| `typescript` | 3730 → 3726 | 12 |
| `yacc` | 0 | 4 |
| `yaml` | 0 | 4 |
| `zig` | 3880 | 12 |

### Verdicts, by finding

**Too narrow — the language's own visibility idiom was invisible (7, the issue's table):**

| language | the idiom | what was added |
|---|---|---|
| `abap` | `FORM` subroutines and function modules are public by default | `^FORM\|FUNCTION <name>`, line-anchored so `CALL FUNCTION '...'` cannot match |
| `ada` | a library-level subprogram is its own compilation unit | a `procedure`/`function` at **column 0**; nested (body-local, private) ones are indented |
| `dart` | a top-level function whose name has no leading `_` | a column-0 return-type + public name + `(` |
| `matlab` | a function file is callable by name | a column-0 `function` (the fallback family above) |
| `objective-c` | a method declared in an `@interface` | a `-`/`+` method line terminated by `;` rather than a `{` body |
| `ruby` | `public :name` (a top-level `def` is private on `Object`) | `public`/`public_class_method` followed by a symbol |
| `shell` | `export -f name` | the flag run between `export` and the name |

Two more of the same family, from the issue's closing paragraph:

* `yaml` — `workflow_call`, the trigger that makes a workflow callable by another repository, was
  missing from the trigger set.
* `perl` — every alternative was a module-level export *list*, and each also lands on a rule that
  already owns it (`@EXPORT_OK = (...)` is a `state_mutation`; `use Exporter|parent|base` is an
  `import`), so `api` could only move by moving another planted count with it. A Perl `sub` is
  package-scoped and callable as `Pkg::name` — public by default, corollary 3.

**Too broad — a token counted where no declaration exists (11):**

| language | what it counted | evidence |
|---|---|---|
| `c` | any indented declaration-shaped line, so every body-local declaration and every two-word statement | `return NULL;` alone was 513 crucible matches; 7534 of 8675 were not file-scope declarations |
| `cobol` | `CALL`/`INVOKE` call sites, plus `END-CALL` via the hyphen boundary | 843 of 1396 |
| `agc_assembly` | the `EXTEND` opcode | 323 of 367 |
| `powershell` | `<name>(` at line start — a .NET method call or a statement | 61 of 199, every one a statement; #2656's exclusion set was lowercase against an `re.I` pattern, so `If (`/`Param(` matched anyway |
| `go` | any line starting with an exported identifier — struct-literal keys, method calls on exported vars | 176 of 614 |
| `lua` | `function ()`, an anonymous function that declares no name | 16 of 288 |
| `assembly` | `EXTERN`/`IMPORT`, which import a name rather than publish one | 3 |
| `dart` | `@pragma(...)`, a compiler hint | 34 of 174 |
| `java`, `csharp`, `kotlin`, `php`, `groovy`, `swift`, `typescript` | a bare access modifier anywhere in the code stream | `import okhttp3.internal.X` (kotlin), `let package = Package(...)` (swift), `$public` and `'path.public'` (php), `case "public":` (typescript/csharp), prose in a log message (groovy) |

`java` and `csharp` move zero matches on either corpus: real Java and C# put `public` in front of a
declaration nearly always, so the anchor is a precision guard rather than a recount. That is the
answer to "why did a real fix produce no diff" for those two — the strict tests
(`test_java_api_contract_2730`, `test_csharp_api_contract_2730`) hold the guard in place.

**Already inside the contract (23, untouched):** `apex`, `cpp`, `css`, `dockerfile`,
`embedded_python`, `fortran`, `haskell`, `html`, `javascript`, `jcl` (`None` at the time; #2748 later gave it the PROC statement, fallback family), `livecode`, `m4`,
`makefile`, `markdown` (`None`), `python`, `rust`, `scala`, `scheme`, `solidity`, `sqlite`, `tcl`,
`yacc`, `zig`.

Two of these are worth naming, because they look like violations and are not:

* `cpp` counts `public:` — a section label, so one hit per access section rather than one per
  member. That is C++'s only file-visible marker short of parsing the class body, and it is
  under-counting, not over-counting.
* `rust`/`zig`/`solidity` count a bare `pub`/`export`/`public`/`external`. In all three the token is
  a reserved word that can *only* introduce a declaration, so it is already anchored by the
  grammar.

## Adding a language after this

When you write a new language's `api` rule, answer these in order:

1. Does the language have an explicit per-function visibility marker? Anchor it to the declaration
   it modifies — never `\b<modifier>\b` on its own.
2. If not, is the language public-by-default? Then match the declaration itself (corollary 3), with
   the language's private-by-convention prefix excluded if it has one (`_`, in python/lua/perl/dart).
3. If the language has no per-function concept at all, pick the file-level declaration that exposes
   the file, add it to the fallback table above, and say so in the rule's comment.
4. Never match a call site, an import, or a literal that merely mentions the keyword. If a corpus
   measurement shows the rule firing on one, that is a bug in the rule, not a quirk of the corpus.
