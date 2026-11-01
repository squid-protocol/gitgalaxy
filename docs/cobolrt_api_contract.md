# The cobolrt API contract

`cobolrt` is the Java runtime a translated program runs on. It ships inside every port, so what a port may call is a
promise to the people who maintain that Java (#4718, epic #4710). This page says what the promise is.
The list itself is `docs/language_status/cobolrt_api.json`, written and checked by `tests/tools/cobolrt_api.py`.

## What counts as the runtime

There is no single runtime artifact. A project gets a selection of these, and all of them are in scope:

| Part | Where it comes from |
| --- | --- |
| `cobolrt.*` | the Java files under `gitgalaxy/tools/cobol_to_java/det/cobolrt` |
| `cics.CicsSpec` | `gitgalaxy/tools/cobol_to_java/CicsSpec.java` |
| `cics.CicsTask` | a Python string in `cobol_to_java_transaction_forge.py` |
| `batch.*` (`CobolFiles`, `Sysout`, `CobolAbend`, `Dd`, ...) | strings in `cobol_to_java_batch_forge.py` |
| `entity.vsam.CobolRecords`, `entity.vsam.CobolEdit` | `cobol_to_java_repository_forge.py` |
| `util.CobolCompare`, `repository.db2.Db2Dates`, `call.CobolRef` | the compare, Db2 and call forges |

Type names are relative to the project's base package. `cobolrt.standalone.Sysout` and `batch.Sysout` are different
classes with different methods, so the manifest uses the qualified name.

Generated per estate and not in scope: `CicsRegion`, the service classes, DTOs and the Spring job configuration. They
are callers of the runtime, and the check reads them as callers.

## Variants

Each type in the manifest lists the variants that carry it:

| Variant | Who gets it | Chosen by |
| --- | --- | --- |
| `det-batch` | a det port in a project with a `batch` package | `det/program.py::runtime_files(batch=True)` |
| `det-standalone` | a det port in a project without one | `runtime_files(batch=False)` |
| `sort-job` | a lowered SORT step: `det-batch` without `cics/` and `sql/` | `cobol_to_java_batch_forge.py::_sort_sources` |
| `forge-cics` | a project with a CICS program | `TransactionForge.runtime_sources` |
| `forge-batch-jobs` | a project with application JCL | `BatchForge.sources` |
| `forge-batch-files` | a no-JCL batch estate: the file runtime, no Spring job classes | `BatchForge.sources` |
| `forge-always`, `forge-db2`, `forge-call` | every project; one with Db2 tables; one with a `BY REFERENCE` CALL | the forges |

A member being public does not mean every project has it. A port compiles against its own variant.

## What public means

`public` means generated code or a port may call it. `internal` means it exists for the runtime's own use, whatever the
Java modifier says. Java's `public` is often needed just to cross a package inside the runtime, so it decides what is
in scope, not what is promised.

A member is public when a caller uses it: a committed port, translator output, or a string the translator emits. Its
`evidence` field records which, as of the last refresh:

| Evidence | Meaning |
| --- | --- |
| `det-port`, `model-port` | called by a committed deterministic or model-written port |
| `frozen-overlay` | called by a frozen runtime copy (see below) |
| `generated` | called in translator output (a `det_port.py --translate-only` work directory) |
| `emitter` | named in a string constant of the translator |
| `emitter-dynamic` | may be reached by a computed emission: `f"Cobol.{fn}(...)"` where the module holds that name, or `f"{var}.nextInput()"` on a type callers can reach |
| `signature` | a type named by a public member's signature, an enclosing type or a supertype |
| `runtime`, `harness` | on an internal member: called by the runtime itself, or by Java the tests and the proof harness write |
| none | no caller was found by these scans. This does not prove it is dead |

`emitter-dynamic` over-approximates on purpose. A member wrongly marked public costs a little freedom. One wrongly
marked internal breaks a port.

## The compatibility promise

Until #4718's version work lands, the promise is about source, within one generation:

- A public member stays, with its name, parameters, return type and static-ness, or its change is a deliberate edit that
  a reviewer sees in the manifest diff.
- A generated project is consistent: its port and its runtime come from the same generator.
- An internal member can change or go at any time.
- Behaviour is governed by the rule catalogue (`docs/language_status/cobolrt_rules.json`), not by this manifest. The two
  answer different questions: a rule can live in an internal method, and a public method can be plumbing.

It does not yet promise that a port generated today runs on a later runtime. That needs the version stamp and the
compatibility tests #4718 still owes.

## Changing the surface

```bash
python tests/tools/cobolrt_api.py --check     # the check, also tests/cobol_mainframe/test_cobolrt_api.py
python tests/tools/cobolrt_api.py generate    # rewrite the manifest from the sources, keeping every classification
```

- **Adding a member:** run `generate`. It starts `internal`. If a port or the translator calls it, the check fails until
  you change its `visibility` to `public` in the manifest. That one word is the decision, and it shows in the diff.
- **Removing or changing a public member:** the check names it `PUBLIC` and stays red until `generate` is run. Say why in
  the PR, and regenerate or re-prove every port that calls it. Remember the frozen copies below.
- **Making a public member internal:** nothing may call it, or the check fails.
- **A failure naming a computed emission:** the name matched a string in a module with a computed site. If it really is
  not emitted, make it public anyway or rename it. The check cannot tell the two apart.

A public member needs a public type, and a public signature cannot name an internal type.

## What the check covers

The test runs on every PR and reads only the repository:

- the manifest against the parsed sources, both ways;
- every committed port: `tests/equivalence/*/port`, `tests/cics_crucible/{ports,det-ports,fixture/ports}`,
  `tests/cobol_mainframe/port_invariance`, `docs/benchmarks/det-refine-*`. A committed `.java` file in any other place
  fails the test until someone decides what it is;
- the translator's own strings, which is what catches a new emission before any port has it;
- one small program through the real translator.

The full scan needs the corpora, so it runs by hand after a translator change:

```bash
python tests/tools/det_port.py run --all-cases --translate-only --work DIR
python tests/tools/cobolrt_api.py --check --generated DIR
```

Add `--promote-used` to `generate` to take the evidence from a fresh scan. It makes every used member public, so read
the diff.

The parser is tree-sitter-java, with a small type inference over imports, fields, locals, `var`, casts, `new` and the
runtime's own return types. It has known limits:

- It tells overloads apart by argument count, so a call binds every overload of that count.
- A receiver it cannot type, such as a lambda parameter, is not checked.
- A string constant is the only view of the translator, so a name built at run time and never stated in the module is
  seen only with `--generated`.

## Frozen runtime copies

Two committed crucible ports carry a whole runtime in their overlay:
`tests/cics_crucible/ports/pc-wizard/PCCONF/overlay/cobolrt` and `.../pc-return-immediate/PCIMMA/overlay/cobolrt`. They
are the only place in the repository where a port runs on an older runtime than the current one.

- The copies are not part of the surface: their declarations are not read.
- Their calls to each other bind to the copy, so they are ignored.
- Their calls out to classes a project generates afresh (`CicsTask`, `CicsSpec`) do reach the live classes. Those are
  scanned, and those members are public with `frozen-overlay` evidence.
- The services beside them are scanned as ordinary ports against the current manifest.
