# The `high_risk_execution` rule contract (#2878)

Phase 3 of the contract roadmap (`docs/contract_roadmap.md`, epic #2812): the sheet row
`high_risk_execution` goes from `draft` to `stated`. The precedents are
`docs/api_rule_contract.md` (#2730), `docs/args_rule_contract.md` (#2773),
`docs/state_mutation_rule_contract.md` (#2765), `docs/branch_rule_contract.md` (#2822),
`docs/io_rule_contract.md` (#2841), `docs/globals_rule_contract.md` (#2858),
`docs/safety_rule_contract.md` (#2869) and `docs/import_rule_contract.md` (#2875).

The sheet's draft sentence was "Process-killing commands and catastrophic runtime
vulnerabilities". Forty-five rules read it forty-five ways: cpp counted `memcpy`, haskell
counted `trace`, javascript counted `alert`, livecode counted a dialog, matlab counted a
workspace reset, apex counted a hard-coded ID literal and `undelete`, csharp and fortran
counted `goto` while c, go, perl and php counted it nowhere, four shell-carrying languages
disagreed on which `rm -rf` is dangerous, and python had no `sys.exit` while its embedded
twin did. Every one of those is a different answer to "what is one hit".

## The contract

> **One hit is a site that hands control out of the program's own semantics -- it ends or
> halts the process, runs text or another program as code, loads or rewrites executable
> code at run time, destroys a whole store the program does not own, or steps outside the
> runtime's protections -- in the primitive's own invocation or statement form.**

Kind `site`, unit `sites` (the module's `KINDS` table): a code site where the construct is
used. The score layer reads it at `danger_weight` 4.0 in `_calc_safety`, as the numerator of
`danger_density`, and as unverified mass in `_calc_verification`; the Silencer Region
(`high_risk_execution` <- `safety`, 500 chars) and the RCE taint pair (`<- io`, 250 chars)
tally proximity in `mitigation_telemetry` and never touch the count (#2813).

## Corollaries

**C1 -- five families, one owner each.** A rule names the language's own forms of:
(a) *termination and traps* -- `exit`, `abort`, `STOP RUN`, `os.Exit`, `panic!`/`panic(`/
`@panic`, `fatalError`, `hlt`/`ud2`/`int 3`, `debugger`, `kill`; (b) *running text or another
program* -- `eval`, `exec`, `system`, `popen`, backtick commands, `Invoke-Expression`,
`syscmd`, `Process.Start`, `ProcessBuilder`, jcl's command interpreters (`PGM=IKJEFT01`);
(c) *loading or rewriting code* -- cobol `ALTER`/`CANCEL`, abap `GENERATE SUBROUTINE POOL`,
lua `load`/`dofile`, html `srcdoc`, the DOM sinks `innerHTML =`/`document.write`, css
`expression(`/`behavior:`, sqlite `load_extension(`, solidity `delegatecall`;
(d) *whole-store destruction* -- `rm -rf /`, `mkfs`, `dd`, `DROP DATABASE`, `TRUNCATE`,
`emptyRecycleBin`, `selfdestruct`; (e) *protection escape* -- `sudo`, `chmod 777`,
`chown root`, java `Unsafe`, `Thread.stop`/`Thread.Abort`, raw syscalls, `machine.reset`/
`machine.disable_irq`. A form invisible to one language but counted by its siblings joins:
python `sys.exit`/`os._exit`/`os.abort`/`os.exec*` (embedded_python parity), c `exit(`/
`abort(` (cpp/objective-c parity), go `panic(`/`exec.Command` (rust/zig parity), php
`eval(`/`exit`/`die`, fortran `STOP`/`ERROR STOP`/`CALL EXIT`/`EXECUTE_COMMAND_LINE`,
haskell `error "..."`, rust `unreachable!`/`Command::new`, powershell `Start-Process`,
objective-c `system(`/`NSTask`, livecode `shell(`, lua `io.popen`/`dofile`.

**C2 -- the site is the invocation.** A bound alias (`runner = eval`), a type or property
reference (`ProcessBuilder builder;`, `exitCode;`), a landing point (`setjmp`) or a bare
identifier that happens to spell the name is not a site. Where an ordinary identifier can
carry the name, the rule anchors on the form: cpp/c `exit(`/`abort(`/`system(` (Godot's
`bool exit = false; exit = true; return exit;` was 18 of cpp's 29 files' hits; c's only hit
was `"Load system defaults"`), perl `system(`/`system "..."` (9 hits were config prose:
`the current login system allows`), php call parens and a backtick at expression position
(the crucible's backticks were MySQL identifier quotes inside SQL strings), groovy's GDK
spawn on a string or list literal (`"ls".execute()`; bare `execute` was retrofit's
`.execute().body()` and `void execute()`), zig `panic(` and `@panic` (bare `panic` was its
own compiler's `.panic` enum tags and the `pub fn panic` handler), javascript/typescript
`.innerHTML =` as the sink (a read and a method named `innerHTML` are not) and `debugger`
as a statement (not the path `'./debugger'`), css `expression(` and `behavior:` (not
`scroll-behavior:`), cobol and tcl hyphen guards (`ALTER-TEST-INIT.`,
`ports_deactivate_no-exec`), java `new ProcessBuilder`, kotlin `Runtime.getRuntime().exec`
(bare `Runtime.getRuntime` was every `.availableProcessors()`), csharp without the `@goto`
verbatim identifier. Where the name cannot be an ordinary identifier in the language's idiom
and the crucible measures no collision, the bare name is allowed (python `eval`, rust
`panic!`, solidity `selfdestruct`, cobol `STOP RUN`, powershell `exit`) -- and then a string
literal carrying the name counts by the stream contract (RULE 18, #2535), which is exactly
what the corpus's string decoy asserts. Corpus plants are invocations.

**C3 -- a jump is nobody's signal.** `goto`, `GO TO` and a computed jump transfer control
inside the unit: they end nothing, execute nothing and destroy nothing. csharp and fortran
stop counting them, as c, cpp, go, perl and php never did. This reverses #2822 C3's hand-off
("high_risk_execution alone owns goto"): branch does not count an unconditional transfer
(#2832 holds the break/continue residue) and neither does this signal. Non-local
abandonment stays -- `longjmp`, fortran's alternate `RETURN n`, livecode's `exit to top` --
and so does rewriting where control will go: cobol `ALTER`, fortran `ASSIGN`.

**C4 -- deletion below the store is cleanup's question (#2843).** One file, record or table
is not this signal: lua `os.remove`/`os.rename`, livecode `delete file|folder|url`, tcl
`file delete -force`, apex `delete` DML, abap `DELETE FROM` (sqlite's cleanup rule owns the
same statement), and `rm -rf <path>`. What stays is the store itself: `rm -rf /`, `mkfs`,
`dd`, `DROP DATABASE`, `TRUNCATE`, `emptyRecycleBin`, `selfdestruct`. The four
shell-carrying languages now agree: shell, makefile, dockerfile and yaml count a recursive
delete of the root only (dockerfile's `/(?![A-Za-z])` form, which yaml's cleanup rule
already complements with the non-root form). shell's non-root `rm -rf "${dir}"` (70 crucible
hits) and makefile's `rm -rf $(BUILD)` are counted by nobody until #2843 lands -- named there.

**C5 -- not danger.** Debug or dialog output (haskell `trace`/`Debug.Trace`, javascript
`alert`, livecode `answer`/`ask`), memory primitives (cpp `memcpy`/`memset`), workspace
resets (matlab `clear all`/`clc` -- cleanup's, batch4 dual retired), a property that records
an exit code (dart `exitCode`), a compatibility pragma (sqlite `PRAGMA legacy_alter_table`),
a hard-coded ID literal (apex), and `undelete` (it restores).

**C6 -- one verified owner.** apex `Database.query` is `safety_bypasses`' alone (its rule
already reads the `WITH SECURITY_ENFORCED` exception; batch4's dual retires) and
`emptyRecycleBin` is this signal's alone (apex's cleanup rule released it). `eval` in
matlab, ruby, shell and tcl is `safety_bypasses`' by ledger (`string-literal-selective-
shielding`) and stays there until that row's contract makes the one-owner call (#2879).
Deliberate duals kept: groovy/java `System.exit` with `panics_and_aborts` (unscored,
pinned in `test_groovy_strict.py`), shell `kill` with `panics_and_aborts`, jcl `PGM=`
per step (batch5), csharp `Environment.Exit`/`FailFast` no longer with globals (#2858 C5).

## The open cell

`agc_assembly` reads 2 against a median of 3. The corpus plants 2 and every other language
reads 3 because SPEC §Decoys' string decoy asserts a +1 (strings count; #2535); agc has no
character-literal type and cannot carry one. The ledger already says so
(`string-decoy-unplantable-no-literal-surface`, `language-morphology` -> inherency), but the
report read the cell as *extraction* because `batch4-dual-keyword-overlaps` carried
`high_risk_execution` in its signal union (for apex `Database.query`) and `agc_assembly` in
`languages_seen` (for `RESUME`), and `categorize_out_of_band` takes the most severe category
across every entry a cell names -- the #2856 A.4 cross-product shape. C6 resolves apex's
dual, `high_risk_execution` leaves batch4's union, and the cell reads what its own entry
says. No rule moves it and none should: the +1 is the stream contract's fact, not this
signal's.

## Measured with no red cell

The crucible (language-crucible v1.2.0, `tests/tools/rule_probe.py`, raw hits over the
Prism code stream) before -> after, with the reason:

- **cpp 18 -> 1**: Godot's `exit` identifier and `"Thread exit status"`/`--gpu-abort` prose
  (C2); `memcpy`/`memset` out (C5); `setjmp` out (C2).
- **c 1 -> 32**: the one hit was `"Load system defaults"` (C2); `exit(`/`abort(` join (C1a).
- **csharp 20 -> 0**: every hit was `goto` (C3) or the `@goto` identifier (C2).
- **groovy 22 -> 2**: retrofit's `.execute().body()` and `void execute()` (C2); the two
  survivors are `new GroovyShell()`.
- **zig 203 -> 82**: `.panic` enum tags, `panic,` fields, `.@"panic.sliceCastLenRemainder"`
  and the `pub fn panic` handler (C2).
- **perl 28 -> 9**: `system` in config prose (C2).
- **shell 147 -> 77**: 70 non-root `rm -rf "${...}"` (C4), `kill -0`/`kill -l` (C1a),
  `--sudo-service-user` (C2).
- **tcl 118 -> 82**: `file delete -force` (C4), `ports_deactivate_no-exec` (C2).
- **cobol 310 -> 257**: `ALTER-TEST-INIT.`/`BEGIN-ALTER-PARAGRAPH.` paragraph names (C2).
- **css 5 -> 0**: `scroll-behavior:`/`overscroll-behavior:` (C2).
- **php 16 -> 43**: backticks inside SQL strings out (C2, 13 of 16); `exit;`/`die(`/
  `eval(` in (C1).
- **go 4 -> 175**: `panic(` in (C1a; the crucible is the go compiler and reflect).
- **rust 69 -> 101**: `unreachable!` in (C1a).
- **livecode 109 -> 122**: `shell(` in (C1b); `answer`/`ask` out (C5).
- **powershell 213 -> 228**: `Start-Process` in (C1b).
- **typescript 9 -> 7**: `'./debugger'` path and `async innerHTML(`/`=> element.innerHTML`
  out (C2); `new Function(` in (C1b).
- **javascript 3 -> 4**: `execSync` in (C1b); `innerHTML =` kept as the sink.
- **fortran 3 -> 4**: `goto` out (C3), `stop` in (C1a).
- **haskell 0 -> 2**: `exitSuccess` (one on its import line -- residue, #2879).
- **matlab 3 -> 2**: `Clear all` out (C5). **abap 1 -> 0**: `DELETE FROM` (C4).
- **solidity 0 -> 1**: `delegatecall` in (C1c). **lua 239 -> 241**: `os.remove` out (C4),
  `dofile`/`io.popen` in. **python 11 -> 12**: `sys.exit` in. **ruby 4 -> 3**: the
  three-line `$\`` prematch span (C2).

## The corpus (keyword-rosetta#103)

Every cell reads what it read before -- 2 planted in `main`, +1 for the decoy in `b` -- so
no manifest value moves; what moves is the plants and decoys that were authored to the old
rules, each screened as a replacement pair (every rule of the language over the Prism code
stream, HEAD vs branch, only `high_risk_execution` may move among the scored columns):

| language | was | now | why |
|---|---|---|---|
| apex `main.cls` | `String rid = '001…abc';` + `undelete payload;` | `Database.emptyRecycleBin(payload);` + `System.abortJob(payload);` | C4/C5 |
| c, cpp, perl `b.*` decoy | `"plain system decoy text"` | `"plain system() decoy text"` | C2 call form |
| php `b.php` decoy | `"plain popen decoy text"` | `"plain popen() decoy text"` | C2 |
| css `c.css` / `b.css` | `y: behavior(z)` / `"plain expression decoy text"` | `behavior: z;` / `"plain expression() decoy text"` | C2 |
| csharp `main.cs` | `goto done;` | `Environment.FailFast(payload);` | C3 |
| fortran `main.f90` | `GOTO 100` | `STOP` | C3 |
| dart `main.dart` | `exitCode;` | `Process.killPid(payload);` | C5 |
| java `main.java` | `ProcessBuilder builder;` | `new ProcessBuilder(payload);` | C2 |
| groovy `main.groovy` / `b.groovy` | `payload.execute()` / `"plain execute decoy text"` | `"true".execute()` / `"plain System.exit() decoy text"` | C2 |
| livecode `main.lc` / `b.lc` | `answer pPayload` / `"plain answer decoy text"` | `get shell(pPayload)` / `"plain quit decoy text"` | C5 (`do` was rejected: livecode's reflection rule counts it) |
| lua `b.lua` decoy | `"plain os.remove decoy text"` | `"plain os.exit decoy text"` | C4 |
| python, ruby, rust, javascript, typescript `main.*` | `runner = eval` / `let stop = abort;` … | `eval(payload)` / `abort();` … (js/ts keep `const runner = eval(payload);` so `immutability_locks` does not move) | C2 |

The screen's only other movers are unscored columns (`panics_and_aborts`,
`structural_boundaries`, `ipc_rpc_bridges`). Ledger: `high-risk-execution-contract-2878`
added; `batch4-dual-keyword-overlaps` loses `high_risk_execution` (apex's dual is stated
here) and with it the cross-product over agc; `fortran-goto-dual-branch-highrisk` gains
the C3 note; `string-decoy-unplantable-no-literal-surface` is now the agc cell's only
entry. Deliberate dual pinned on the corpus side: none new.

## The 46-language audit

Raw rule hits on both corpora before -> after (`rule_probe.py --compare`); a single number
did not move. The keyword-rosetta column is the corpus cell (2 planted + 1 decoy = 3;
agc_assembly 2 by inherency; markdown n/a).

| language | crucible | keyword-rosetta |
|---|---|---|
| `abap` | 1 -> 0 | 3 |
| `ada` | -- | 3 |
| `agc_assembly` | 4 | 2 |
| `apex` | 0 | 3 |
| `assembly` | 142 | 3 |
| `c` | 1 -> 32 | 3 |
| `cobol` | 310 -> 257 | 3 |
| `cpp` | 18 -> 1 | 3 |
| `csharp` | 20 -> 0 | 3 |
| `css` | 5 -> 0 | 3 |
| `dart` | 0 | 3 |
| `dockerfile` | 0 | 3 |
| `embedded_python` | 5 | 3 |
| `fortran` | 3 -> 4 | 3 |
| `go` | 4 -> 175 | 3 |
| `groovy` | 22 -> 2 | 3 |
| `haskell` | 0 -> 2 | 3 |
| `html` | 0 | 3 |
| `java` | 0 | 3 |
| `javascript` | 3 -> 4 | 3 |
| `jcl` | 61 | 3 |
| `kotlin` | 0 | 3 |
| `livecode` | 109 -> 122 | 3 |
| `lua` | 239 -> 241 | 3 |
| `m4` | 0 | 3 |
| `makefile` | -- | 3 |
| `markdown` | n/a | n/a |
| `matlab` | 3 -> 2 | 3 |
| `objective-c` | 1 | 3 |
| `perl` | 28 -> 9 | 3 |
| `php` | 16 -> 43 | 3 |
| `powershell` | 213 -> 228 | 3 |
| `python` | 11 -> 12 | 3 |
| `ruby` | 4 -> 3 | 3 |
| `rust` | 69 -> 101 | 3 |
| `scala` | 0 | 3 |
| `scheme` | 13 | 3 |
| `shell` | 147 -> 77 | 3 |
| `solidity` | 0 -> 1 | 3 |
| `sqlite` | 0 | 3 |
| `swift` | 4 | 3 |
| `tcl` | 118 -> 82 | 3 |
| `typescript` | 9 -> 7 | 3 |
| `yacc` | 0 | 3 |
| `yaml` | 0 | 3 |
| `zig` | 203 -> 82 | 3 |

Unchanged rules (already on the contract): ada, agc_assembly, assembly, html, jcl, m4,
scheme, swift, yacc. Scala gained the `Runtime.getRuntime().exec` spelling and
`sys.process`; embedded_python gained `os._exit`/`os.abort`.

## Known limits

- The stream contract: a string literal carrying the form counts (shell `echo "<dd>"`,
  fortran `'... Stop.'`, php `'&die;'`, cobol `"ALTER FAILED"`). Deliberate, corpus-wide,
  the decoy's premise.
- haskell counts a name on its own import line; javascript counts a user method named
  `eval`; scheme admits `(mutable exit)`; php's backtick anchor cannot see an enclosing
  quote. All measured at one to three hits and named in #2879.
- `kill` in shell/makefile counts any signal; the `-0` probe and `-l` listing are the only
  exclusions the crucible showed.

## Deferred by design (#2879)

The one-owner call on `eval` in matlab/ruby/shell/tcl (safety_bypasses' contract), the
non-root `rm -rf` and single-resource deletions now counted by nobody (#2843), and the
family's forms no rule carries yet (cobol `CALL 'SYSTEM'`/`EXEC CICS ABEND`, ada `abort`,
swift `Process()`, java `ScriptEngine.eval`).

## Bless scope

`tests/golden_master_*.json`: the `high_risk_execution` leaf, the security keys that read
it (`sec_high_risk_execution`, `state_danger`), the risk formulas above (`risk_safety_score`,
`risk_verification`), and the aggregates that sum them; `mitigated_danger`/`amplified_rce`
tallies follow the sites. No topological movement expected beyond the layout's usual
ripple; newly parsed / newly excluded: none (the aperture's density guard reads structure,
not this signal). The scoped table is in the PR body.
