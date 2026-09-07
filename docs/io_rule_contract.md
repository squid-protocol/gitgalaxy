# The `io` rule contract (#2841)

> **One hit is an operation that moves data between the program and a system
> outside its own runtime — a file, stream, socket, device, terminal, or
> external data store — expressed in a form an ordinary identifier cannot
> match.**

Stated 2026-09-07 by the #2841 audit (roadmap Phase 3, epic #2812). Precedents:
`docs/api_rule_contract.md` (#2730), `docs/args_rule_contract.md` (#2773),
`docs/state_mutation_rule_contract.md` (#2765), `docs/branch_rule_contract.md`
(#2822). The machine-readable row is `gitgalaxy/standards/signal_contracts.py`;
the cross-language pins are
`tests/extraction/languages/test_io_contract_2841.py`.

`io` is a **site**-kind signal. Its consumers: the score layer's
RCE-corroboration proximity pair (`spatial_correlation.py` reads io *positions*
as dampeners for `high_risk_execution` → `amplified_rce`), the
`statistical_auditor` extraction-density group, and `_classify_function`'s
fallback tag (a function whose body fires the io rule and no name verb is
tagged `io`). Before this contract it carried 4 of the corpus's 39 open-defect
cells (javascript, jcl, sqlite, tcl — 9% of its comparable cells), each a
different disease; after it, every corpus language reads **3**.

## Corollaries

**C1 · The ambiguity anchor.** A token may fire bare only when it names the
language's I/O facility itself and the crucible shows no non-I/O collisions
(python's builtin `open` referenced bare, `fetch`/`axios`/`fs`, swift's
`URLSession`, assembly's `svc`). A token the crucible showed matching an
ordinary identifier, string, or comment fires only anchored to its operative
form: javascript's bare `path` matched probeIo's own `path` *parameter* (the
`identifier-name-token-collision` ledger entry) and bare `https` matched
string-literal URLs — both now require the module/call form
(`require('path')`, `path.join`, `https.get`); c's bare `read` matched
`if (read)` and `stat` matched `#include <sys/stat.h>` — the c calls are now
paren-anchored; assembly's bare `in`/`out` matched comment prose — now
line-anchored with an operand; groovy's lowercase `file`/`copy`/`sync`/`uri`/
`url` and dart's case-insensitive `File` matched strings and imports — groovy
keeps the type names plus Gradle's `file(...)` call, dart's types are now
case-sensitive. `database`/`sql` left javascript entirely: everyday words,
nothing plants them.

**C2 · One owner per token** (count contract corollary 4). Dependency
inclusion is `import`'s hit: tcl `source` (was +3 on the corpus chain),
sqlite `.read`/`.import` (the `sqlite-dot-read-dual-import-io` entry — every
corpus chain link added +1 io), `ATTACH DATABASE` (sqlite's own import rule
already claims it). Releasing a resource is `cleanup`'s hit: `close`-family
left the io rules of abap, c, cobol, cpp, fortran, livecode, lua, matlab,
perl, tcl and yacc — in every one of those languages the cleanup rule already
claimed the same token, so the dual collapses to its owner and no mass is
lost (the c/lua/tcl probe-idiom surpluses ledgered as "cannot be authored
away" are authored away exactly here). Executing a command stays
`high_risk_execution`'s (sqlite `.shell` was never io's). File *transfer*
forms stay io's: `rename(`, fortran `REWIND`, cobol `DELETE` (a record write
against an external file, unlike sqlite's in-engine `DELETE FROM`, which is
cleanup's).

**C3 · The boundary is the program's runtime.** A language whose program
executes *inside* the data store counts only operations that leave the
engine: sqlite io is now `readfile`/`writefile` and the outbound dot-commands
(`.output`/`.once`/`.dump`/`.backup`) — DML is computation there, so the
SELECT/INSERT decoys other signals plant no longer leak into io (the cell
read 9 against a median of 3 through exactly that leak). In a *client*
language the same keyword is the crossing: abap's statement-anchored
`SELECT`/`UPDATE`/`MODIFY` address a remote DB server and stay. solidity is
the stated absence: the EVM cannot reach outside itself, `io: None` with
manifest 0 (the `solidity-io-observable-output-via-events` entry documents
where io-intent is measured instead). css/html/yaml keep their #2775-era
anchored resource-fetch rules — the absence answer and the rule answer cannot
coexist in one language (count contract corollary 3).

**C4 · One statement is one hit.** jcl's rule counted operand *tokens*: one
`//DD1 DD DSN=CORPUS.DATA,DISP=SHR` line fired twice (DSN + DISP=), and
`//SYSPRINT DD SYSOUT=*` twice (SYSPRINT + SYSOUT). The rule is now anchored
to the DD statement itself — one hit per DD that allocates an external target
(a cataloged `DSN=`/`DSNAME=` or spooled `SYSOUT=`), including the
one-continuation-line form (`//SYSUT1 DD DSN=HLQ.WORK,` … `// DISP=`).

**C5 · A job-local temporary never crosses the boundary.** `DSN=&&` names a
dataset that exists only inside the job — the same reasoning that keeps it
out of the dependency DAG (`_dependency_capture` excludes `&&`). c.jcl's
teardown DDs (the probe-idiom "jcl io +2") stop counting; the corpus plants a
third external allocation (`//DD5 DD SYSOUT=L`) so the jcl shell carries the
SPEC's three io constructs like every other language.

## Deliberate duals and deferred residue

- **Kept:** c/cpp `socket(` is io + `ipc_rpc_bridges` (both own the primitive
  from different layers, pinned in the strict suites); matlab `load(` is io +
  `serialization_parsing`; jcl an external `DISP=(OLD,…)` DD is io +
  `sync_locks` (the ENQ and the allocation are different facts about one
  statement — the *temp*-only overlap is retired instead).
- **Deferred to the cleanup contract session (#2843):** c `remove(` left io
  (destroying external state is cleanup-family per sqlite's `DROP TABLE`/
  `DETACH` precedent) but c's cleanup rule does not yet claim it; the cleanup
  audit owns that relocation.
- **Deferred, crucible-level:** perl's bare `open`/`connect`/`bind` and
  python's bare module names (`socket`, `requests`) have the C1 surface but no
  measured corpus collision; they stay until a cell moves or the crucible
  shows one (the python plant's `reader = open` is the bare-builtin reference
  C1 explicitly allows).
- jcl DD statements whose external `DSN=` sits past the *second* continuation
  line are not counted (the lookahead spans one continuation); no crucible DD
  does this today.

## The 46-language audit

`rule_probe.py io all --samples 8` before → after. crucible = hits across the
control corpus; rosetta = hits across the 4 keyword-rosetta shell files
(median plant: 3). Languages not listed: rule `None` by stated absence
(solidity) or no io morphology declared yet (batch, blp, csv, glsl, hlo, json,
markdown, mlir, nix, pbtxt, plaintext, proto, td, xml — markdown's 0 is
ledgered `markdown-lit-plane-morphology`).

| language | crucible | rosetta | verdict |
|---|---|---|---|
| abap | 21 | 3 | conforms; `CLOSE DATASET` → cleanup's (C2) |
| ada | — | 3 | conforms |
| agc_assembly | 30 | 3 | conforms (device ops are its io) |
| apex | 23 | 3 | conforms (SOQL brackets are a client's DB crossing, C3) |
| assembly | 230 → 90 | 3 | C1: bare `in`/`out` matched comment prose; now instruction-anchored |
| c | 63 → 21 | 4 → 3 | C1 paren-anchored; C2 close/fclose → cleanup's (probe-idiom slice retired) |
| cobol | 9925 → 9295 | 3 | C2: `CLOSE` → cleanup's |
| cpp | 2 | 3 | C2: `fclose` → cleanup's |
| csharp | 2 | 3 | conforms |
| css | 14 | 3 | conforms (#2775 anchored resource-fetch precedent) |
| dart | 2 → 1 | 3 | C1: types are case-sensitive; prose `file` was a hit |
| dockerfile | 86 | 3 | conforms (COPY/ADD/network commands) |
| embedded_python | 75 | 3 | conforms (Pin/I2C/UART are device facilities) |
| fortran | 322 → 297 | 3 | C2: `CLOSE` → cleanup's |
| go | 31 | 3 | conforms |
| groovy | 418 → 244 | 3 | C1: bare `file`/`copy`/`sync`/`uri`/`url` dropped; `file(...)` kept |
| haskell | 14 | 3 | conforms |
| html | 362 | 3 | conforms (#2775 resource-loading constructs) |
| java | 0 | 3 | conforms |
| javascript | 30 → 10 | 4 → 3 | C1: bare `path`/`https` anchored, `database`/`sql` dropped (identifier-name-token-collision retired) |
| jcl | 1590 → 884 | 5 → 3 | C4 one DD one hit; C5 `&&` temps out; +1 plant (//DD5) |
| kotlin | 0 | 3 | conforms |
| livecode | 191 → 122 | 3 | C2: `close file/socket/process` → cleanup's |
| lua | 243 → 220 | 4 → 3 | C2: `io.close` → cleanup's (probe-idiom slice retired) |
| m4 | 9 | 3 | conforms |
| makefile | — | 3 | conforms |
| matlab | 18 → 13 | 3 | C2: `fclose` → cleanup's |
| objective-c | 35 | 3 | conforms |
| perl | 132 → 107 | 3 | C2: `close`/`closedir` → cleanup's |
| php | 202 | 3 | conforms |
| powershell | 259 | 3 | conforms |
| python | 185 | 3 | conforms (bare builtin `open` reference allowed by C1) |
| ruby | 33 | 3 | conforms |
| rust | 45 | 3 | conforms |
| scala | 16 | 3 | conforms |
| scheme | 189 | 3 | conforms |
| shell | 5655 | 3 | conforms (every command's io is textual) |
| sqlite | 321 → 8 | 9 → 3 | C3 DML out; C2 `.read`/`.import`/ATTACH → import's; re-planted to readfile/writefile/.output |
| swift | 17 | 3 | conforms (URLSession/FileManager/FileHandle facility references) |
| tcl | 871 → 416 | 7 → 3 | C2 `source` → import's, `close` → cleanup's; C1 command-position anchor |
| typescript | 153 | 3 | conforms |
| yacc | 2 | 3 | C2: `fclose` → cleanup's |
| yaml | 0 | 3 | conforms (embedded network commands; crucible corpus has none) |
| zig | 48 | 3 | conforms |

**Result:** every one of the 46 corpus cells reads 3 — including the four
open defects (javascript 4, jcl 5, sqlite 9, tcl 7) and the two grey
probe-idiom surpluses (c 4, lua 4). `rosetta_audit.py` against the re-blessed
corpus: 46/46.

## Ledger dispositions this contract settles

| entry | disposition |
|---|---|
| `identifier-name-token-collision` | retired — the one verified collision (javascript `path`) cannot fire; C1 is the standing guidance |
| `sqlite-dot-read-dual-import-io` | retired — `.read` is import's hit alone (C2) |
| `probe-idiom-collides-with-measured-signal` | narrowed to haskell's safety_bypasses slice — the c/lua/tcl close idiom and jcl teardown-DD io surpluses are single-owner now |
| `batch4-dual-keyword-overlaps` | tcl `source`/`close` retired from the itemization; io leaves the signal union |
| `css-import-url-io-triple-overlap` | already `still_reproduces: false` (#2775); the RE-SCOPED note's non-import `url()` population is what css's current rule counts |
| `solidity-io-observable-output-via-events` | unchanged — the C3 stated-absence precedent |
