<div align="center">

# CICS Command Specification (`gitgalaxy/standards/cics`)

### One declarative specification for the `EXEC CICS` commands—driving the translator, the Java runtime, the C oracle stub, and the readiness scanner.

`gitgalaxy/standards/cics/` is the single source of truth for how GitGalaxy parses, translates,
executes, and refuses `EXEC CICS` commands. Every command entry declares its status (`modelled`,
`engine_only`, or `refused`), its valid and mutually exclusive option groups, its explicitly
refused options with reasons, its `RESP` / `RESP2` outcome conditions, its default `AEIx`/`AEYx`
abend code, its entry in the [oracle-assumptions register](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/oracle_assumptions.md),
and its IBM CICS Transaction Server documentation URL. From this package, `python -m gitgalaxy.standards.cics regen`
generates both the Java runtime lookup tables ([`CicsSpec.java`](../../tools/cobol_to_java/CicsSpec.java))
and the C header (`tests/equivalence/cics/ggcics_spec.h`) compiled into the GnuCOBOL CICS stub.

<table>
<tr>
<td align="center" width="190"><h2>1</h2></td>
<td align="center" width="190"><h2>2</h2></td>
<td align="center" width="190"><h2>2</h2></td>
<td align="center" width="190"><h2>0</h2></td>
</tr>
<tr>
<td align="center" valign="top"><sub><strong>declarative spec for every CICS command</strong><br />full · engine-only · name-only, counted on the live page<br /><em><a href="#command-coverage-by-family">command families</a> · IBM URLs cited</em></sub></td>
<td align="center" valign="top"><sub><strong>runtimes the modelled commands run on</strong><br /><code>det</code> translator + GnuCOBOL CICS stub<br /><em><a href="https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/cics_spec_status.md">live spec status</a> · parity-checked</em></sub></td>
<td align="center" valign="top"><sub><strong>generated runtime targets</strong><br /><code>CicsSpec.java</code> &amp; <code>ggcics_spec.h</code><br /><em><a href="#generated-runtime-tables-and-ci-ratchet">regen CLI</a> · gated in CI</em></sub></td>
<td align="center" valign="top"><sub><strong>unlisted spec importers allowed</strong><br />enforced by <code>test_cics_spec.py</code><br /><em><a href="#strict-import-and-consistency-gates">import gate</a> · single authority</em></sub></td>
</tr>
</table>

<a href="#quickstart"><strong>Quickstart</strong></a> ·
<a href="#what-you-ask-what-you-get"><strong>Ask / get</strong></a> ·
<a href="#command-coverage-by-family"><strong>Command families</strong></a> ·
<a href="#generated-runtime-tables-and-ci-ratchet"><strong>Generated tables</strong></a> ·
<a href="#modules"><strong>Modules</strong></a> ·
<a href="#strict-import-and-consistency-gates"><strong>CI gates</strong></a>

</div>

---

<a id="quickstart"></a>

## Quickstart

```sh
# List every CICS command entry (status, X-register, option counts, IBM doc URL)
python -m gitgalaxy.standards.cics emit

# Inspect specific command entries as full JSON (options, groups, refusals, outcomes)
python -m gitgalaxy.standards.cics emit --json "GET CONTAINER" "READ" "SEND MAP"

# Check internal consistency of all command dataclasses, groups, outcomes, and X-register links
python -m gitgalaxy.standards.cics check

# Verify that committed CicsSpec.java and ggcics_spec.h match the spec (or regenerate them)
python -m gitgalaxy.standards.cics regen --check
python -m gitgalaxy.standards.cics regen
```

---

<a id="what-you-ask-what-you-get"></a>

## What you ask, what you get

| You ask | `gitgalaxy/standards/cics` gives you |
|---|---|
| *How do you keep the Java runtime and the C oracle stub from disagreeing on `DFHRESP` numbers or abend codes?* | [`resp.py`](resp.py) defines `DFHRESP`, condition aliases (`DSIDERR` = `FILENOTFOUND`), and `CONDITION_ABEND` (`AEI0`..`AEY9`) once; [`cli.py`](cli.py) renders both [`CicsSpec.java`](../../tools/cobol_to_java/CicsSpec.java) and `tests/equivalence/cics/ggcics_spec.h`. |
| *What happens when a COBOL program uses a CICS option we haven't modelled yet (e.g. `READ UPDATE NOSUSPEND` or `GETMAIN SHARED`)?* | Every `CommandSpec` in [`commands/`](commands/) lists its accepted `options` and its `refused` option dictionary (`Refusal(reason, register)`). Both the `det` translator and `equivalence_cics.py` read the same spec entry and refuse the option by name with the same message. |
| *How are mutually exclusive or required option combinations enforced?* | `OptionGroup` rules (`one_of`, `at_most_one`, `together`, `required`) in [`model.py`](model.py) validate option combinations structurally before code generation. |
| *Where are the differences from IBM z/OS documented?* | Every modelled command or refusal links to its `X1`–`X63` entry in [`docs/language_status/register/`](../../../docs/language_status/register/) (rendered to [`oracle_assumptions.md`](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/oracle_assumptions.md)), and `python -m gitgalaxy.standards.cics check` verifies that option refusals match their command's register entry. |

---

<a id="command-coverage-by-family"></a>

## Command coverage by family

The command entries in [`commands/`](commands/) are organized by CICS functional domain
([live per-command table](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/cics_spec_status.md)):

| Module | Domain | Modelled Commands (full and engine-only) | Refused by Name |
|---|---|---|---|
| [`commands/files.py`](commands/files.py) | **File control (VSAM)** | `READ`, `WRITE`, `REWRITE`, `DELETE`, `UNLOCK`, `STARTBR`, `READNEXT`, `READPREV`, `ENDBR`, `RESETBR` | RLS-only options (`UPDATE` on `READNEXT`/`READPREV`, `CONSISTENT`, `NOSUSPEND`) refused by option name |
| [`commands/terminal.py`](commands/terminal.py), [`commands/send.py`](commands/send.py) | **BMS 3270 & terminal control** | `SEND MAP`, `RECEIVE MAP`, `SEND TEXT`, `SEND CONTROL`, `SEND`, `RECEIVE`, `CONVERSE`, `ISSUE ERASEAUP` | `SEND PAGE`, `PURGE MESSAGE`, LU6.2 / APPC conversation verbs (`ALLOCATE`, `CONNECT PROCESS`, `FREE`, `GDS *`, `ISSUE *`) |
| [`commands/control.py`](commands/control.py), [`commands/task.py`](commands/task.py), [`commands/storage.py`](commands/storage.py) | **Program, task, syncpoint & storage** | `LINK`, `XCTL`, `RETURN`, `LOAD`, `RELEASE`, `ABEND`, `HANDLE CONDITION`, `HANDLE AID`, `HANDLE ABEND`, `IGNORE CONDITION`, `PUSH HANDLE`, `POP HANDLE`, `SYNCPOINT`, `SYNCPOINT ROLLBACK`, `ASSIGN`, `ADDRESS`, `ADDRESS SET`, `GETMAIN`, `FREEMAIN`, `ENQ`, `DEQ`, `SUSPEND`, `ENTER TRACENUM` | `GETMAIN` without `INITIMG`, `GETMAIN SHARED`, `FREEMAIN DATA`, `HANDLE ABEND PROGRAM`, `WAIT EXTERNAL`/`CICS` |
| [`commands/containers.py`](commands/containers.py) | **Channels & containers** | `PUT CONTAINER`, `GET CONTAINER`, `MOVE CONTAINER`, `DELETE CONTAINER`, `STARTBROWSE CONTAINER`, `GETNEXT CONTAINER`, `ENDBROWSE CONTAINER`, `DELETE CHANNEL`, `QUERY CHANNEL` | `APPEND CONTAINER`, `PUT64`/`GET64 CONTAINER` |
| [`commands/interval.py`](commands/interval.py), [`commands/async_api.py`](commands/async_api.py) | **Interval control, events & async** | `ASKTIME`, `FORMATTIME`, `DELAY`, `POST`, `WAIT EVENT`, `START`, `RETRIEVE`, `CANCEL`, `RUN TRANSID`, `FETCH CHILD`, `FETCH ANY`, `FREE CHILD` | `START BREXIT` / `TERMID` (multi-terminal), `FORMATTIME DATE`/`FULLDATE`/`DATESTRING` (region `DATFORM`-dependent) |
| [`commands/queues.py`](commands/queues.py), [`commands/counters.py`](commands/counters.py) | **TS/TD queues & named counters** | `WRITEQ TS`, `READQ TS`, `DELETEQ TS`, `WRITEQ TD`, `READQ TD`, `DELETEQ TD`, `DEFINE/GET/QUERY/UPDATE/REWIND/DELETE COUNTER` & `DCOUNTER` | `UPDATE COMPAREMIN/MAX`, negative fullword counter values |
| [`commands/web.py`](commands/web.py) | **Web, HTTP & documents** | `DOCUMENT CREATE/INSERT/SET/RETRIEVE`, `WEB OPEN/CONVERSE/SEND/RECEIVE/CLOSE/PARSE URL/EXTRACT`, `WEB READ/WRITE/STARTBROWSE/READNEXT/ENDBROWSE HTTPHEADER`, `EXTRACT WEB`, `EXTRACT TCPIP` | `SOAPFAULT CREATE/ADD/DELETE`, `INVOKE SERVICE`/`WEBSERVICE`, `TRANSFORM XMLTODATA`/`DATATOXML` |
| [`commands/system.py`](commands/system.py), [`commands/refused.py`](commands/refused.py) | **SPI (`INQUIRE`/`SET`), security & rest** | `INQUIRE/SET FILE`, `INQUIRE/SET TDQUEUE`, `INQUIRE PROGRAM/TRANSACTION/SYSTEM/APPKEY`, `SIGNON`, `SIGNOFF`, `VERIFY/CHANGE PASSWORD`, `BIF DEEDIT` | `CREATE *`, `DISCARD *`, `PERFORM *`, `COLLECT STATISTICS`, FEPI (`FEPI *`), BTS (`DEFINE ACTIVITY`/`PROCESS`), Event Processing (`SIGNAL EVENT`), Socket/ONC RPC |

---

<a id="generated-runtime-tables-and-ci-ratchet"></a>

## Generated runtime tables and CI ratchet

Only declarative tables are generated from this package; each runtime's execution logic stays
hand-written in [`DetCics.java`](../../tools/cobol_to_java/det/cobolrt/) / [`cobol_to_java_transaction_forge.py`](../../tools/cobol_to_java/cobol_to_java_transaction_forge.py)
and `tests/equivalence/cics/ggcics.c`:

| Generated File | Consumer | Contents |
|---|---|---|
| [`gitgalaxy/tools/cobol_to_java/CicsSpec.java`](../../tools/cobol_to_java/CicsSpec.java) | `DetCics` and `CicsTask` in generated Spring Boot projects | `CicsSpec.name(int resp)`, `CicsSpec.condition(int resp)`, `CicsSpec.resp(String condition)`, `CicsSpec.abcodeFor(String condition)` |
| [`tests/equivalence/cics/ggcics_spec.h`](../../../tests/equivalence/cics/ggcics_spec.h) | `ggcics.c` (the C runtime linked into GnuCOBOL equivalence builds) | `enum { DFHRESP_NORMAL = 0, ... }` and `static const char *condition_abcode(int resp)` |

If you edit `resp.py` or any command entry in `commands/`, run `python -m gitgalaxy.standards.cics regen`.
CI runs `python -m gitgalaxy.standards.cics regen --check` in `pr_gates.py --ratchets` and fails if
either file is stale.

---

<a id="modules"></a>

## Modules

| Module | Role |
|---|---|
| [`model.py`](model.py) | Immutable dataclasses: `CommandSpec`, `OptionSpec`, `OptionGroup`, `Refusal`, `Outcome`, `IbmDoc` |
| [`resp.py`](resp.py) | `DFHRESP` condition numbers, condition aliases (`ALIASES`), and default unhandled abend codes (`CONDITION_ABEND`) |
| [`eib.py`](eib.py) | Execute Interface Block (`DFHEIBLK`) field definitions, types, and lengths |
| [`commands/`](commands/) | Per-domain command specifications assembled into `COMMANDS` |
| [`cli.py`](cli.py) | `emit`, `check`, and `regen` CLI implementation |

---

<a id="strict-import-and-consistency-gates"></a>

## Strict import and consistency gates

To prevent duplicate hand-rolled CICS tables from creeping back into the codebase,
[`tests/core_engine/test_cics_spec.py`](../../../tests/core_engine/test_cics_spec.py) and
[`tests/cobol_mainframe/test_cics_spec_equality.py`](../../../tests/cobol_mainframe/test_cics_spec_equality.py)
enforce:
1. **Explicit importer allowlist (`test_only_the_listed_modules_import_the_spec`):** Only designated translator, stub, and readiness modules may import `gitgalaxy.standards.cics`.
2. **Zero duplicate tables:** Translator and stub option/refusal/DFHRESP lookups must come from `COMMANDS` and `resp.py`.
3. **Live status freshness (`tests/tools/cics_spec_status.py`):** Renders the live command matrix to the `generated` branch alongside census counts and CICS crucible coverage.

---

## Explore further

| Resource | What it contains |
|---|---|
| [CICS command spec design (`cics_command_spec.md`)](../../../docs/language_status/cics_command_spec.md) | Architectural design and PR rollout plan for the unified CICS specification |
| [Live CICS spec status (`generated` branch)](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/cics_spec_status.md) | Generated table of every command with census frequency and crucible test coverage |
| [CICS to Java (`cobol_to_java/README.md`)](../../tools/cobol_to_java/README.md) | How the spec drives `det/cics.py`, `CicsTask`, and equivalence proofs |
| [Oracle assumptions register (`generated` branch)](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/oracle_assumptions.md) | Full text of the `X1`–`X63` CICS oracle assumptions referenced by the spec |
