# The `cleanup` rule contract (#2888)

> **One hit is a site that explicitly destroys state or releases a held
> resource — a deallocation or finalization call, a handle or connection
> close, removal of an entry from a live container or of external state the
> program owns, or the opener of a guaranteed-teardown region — in call or
> statement form.**

Stated 2026-09-08 by the #2888 audit (roadmap Phase 3, epic #2812). Precedents:
`docs/api_rule_contract.md` (#2730), `docs/args_rule_contract.md` (#2773),
`docs/state_mutation_rule_contract.md` (#2765), `docs/branch_rule_contract.md`
(#2822), `docs/io_rule_contract.md` (#2841), `docs/safety_rule_contract.md`
(#2869). The machine-readable row is `gitgalaxy/standards/signal_contracts.py`;
the cross-language pins are
`tests/extraction/languages/test_cleanup_contract_2888.py`.

`cleanup` is a **site**-kind signal. Its consumers: the score layer's
memory-leak/UAF proximity pair (`spatial_correlation.py` Block 5 reads cleanup
*positions* as dampeners for `memory_alloc` — the golden-master bless moved
`Mitigated Memory Allocs` and the weighted alloc view alongside the raw count,
and nothing else). Before this contract it carried 1 of the corpus's open-defect
cells (makefile 3 vs the planted 2); after it, every corpus language that can
express the construct reads **2** (css and markdown stay `n/a`).

## Corollaries

**C1 · A declaration is not a site.** `def close(self):`, `fn drop(&mut
self)`, `public void Dispose()`, `void dispose() {`, `dispose(): void;`,
`sub finish {` / `sub DESTROY {`, `- free` / `- (void)free`, `pub fn deinit(`,
scala `def close(): Unit`, an ABAP `ALIASES ... clear FOR zif~clear`
continuation line, and — the corpus's one open cell — a makefile `clean:` /
`distclean:` **target header** all declare or name the teardown routine. The
hit is where teardown runs: the routine's body carries the real sites, and the
header is `func_start`'s unit (makefile's manifest had priced the double-count
since its bless: `c.mk cleanup 3 = clean: + two rm -f`).

**C2 · Termination is not release.** `exit`/`logout` end the process and let
the OS reclaim wholesale — counting them made every early-exit line in a shell
script read as tidiness (shell: 757 crucible hits, ~300 of them `exit`,
including `-s exit:0` test arguments; `exit` is `panics_and_aborts`' token, so
it was double-owned as well). agc `EXIT` is a control transfer and is dropped;
`ENDOFJOB` (releases the job's core set) and `RESUME` (releases the interrupt
context) are the executive model's own release forms and stay as agc's
fallback family.

**C3 · A name is not a site.** cobol's `\bCLOSE\b` fired inside hyphenated
paragraph names (`PERFORM 9000-DALYTRAN-CLOSE`) and quoted literals
(`MOVE 'CLOSE CUR1' ...`) — the rule now carries hyphen/quote guards, the
same fix shape #2869 used. scheme counted handler-table arguments
(`(call-port-handler close-port who port)`) and `(set-who! close-port` —
head position only now. perl's `undef` fired on `return undef;` and
`undef,` placeholders — an operand (`undef $x` / `undef($x)`) is required;
`finish` fired on POD headings (`=head2 finish`) — call or `->` form only.
scala and matlab counted bare verbs inside log/eval strings — call form or
(matlab) statement position required. A matlab eval-string that *executes*
(`e_catch = '...; clear EEGTMP; ...'`) still reads its statement-position
hits: that string is deferred code, matlab's eval idiom, and dropping it
would blind the rule to real teardown.

**C4 · Configuring the reclaimer is not reclaiming.** lua's
`collectgarbage("stop")` / `("restart")` / `("count")` / tuning forms
configure or query the collector — the opposite of collecting. Bare
`collectgarbage()`, `("collect")` and `("step")` stay.

**C5 · One token, one owner.** go's `Unlock`/`RUnlock` are `sync_locks`'
(the release half of coordination belongs to the coordination signal);
js/ts `.delete(` is `state_mutation`'s container-mutator token (#2765) and
the bare `delete` alternative left both rules; cobol `END-DECLARATIVES` is a
structural closer (#2869's `END-*` family); the root form `rm -rf /` stays
`high_risk_execution`'s (whole-store destruction) while the non-root `rm`
flags-with-f family is cleanup's. Kept deliberate duals: haskell/scala
`finally`/`bracket`/`onException` (the guaranteed-teardown region opener —
safety ceded these in #2869), agc `RESUME` (cleanup+branch, batch4's
itemised dual), makefile `clean:`'s **api** half (the lifecycle-surface
reading survives; only the cleanup half retired).

**#2843 resolved · destruction of external state is cleanup's.** The sqlite
precedent (`DROP TABLE`, `DELETE FROM`, `DETACH` have always been its rule)
generalises: c gains `remove(`, tcl gains `file delete`, cobol gains `DELETE`
(a record/file, not a store — `DROP DATABASE`/`TRUNCATE` remain
high_risk_execution's), shell gains the non-root `rm` family, and yaml
(`rm -rf` + `docker compose down`) and powershell (`Remove-Item`) were
already there. `#2843` closes with this document.

## The audit — all 46 corpus languages

Counts are `cleanup` matches over the code stream on the `keyword-rosetta`
control corpus (SPEC plants 2 — one per each of two probes) and the
`language-crucible` real-world corpus. `a → b` is this change; a single number
means the rule was already inside the contract and is untouched.

| language | keyword-rosetta (planted 2) | crucible | verdict |
|---|---|---|---|
| `abap` | 2 | 20 → 19 | C1: an `ALIASES ... clear FOR` continuation line declared an alias |
| `ada` | 2 | — | in contract (`Finalize`, `Unchecked_Deallocation`) |
| `agc_assembly` | 2 | 73 → 51 | C2: `EXIT` transfers control; `ENDOFJOB`/`RESUME` stay as the executive's release forms |
| `apex` | 2 | 0 | in contract (#2878 already gave `emptyRecycleBin` to high_risk) |
| `assembly` | 2 | 0 | in contract (`call/bl free`, call-anchored) |
| `c` | 2 | 17 | #2843: gains `remove(` |
| `cobol` | 2 | 630 → 389 | C3: `\bCLOSE\b` fired inside hyphenated names and string literals; C5: `END-DECLARATIVES` is structure; #2843: gains `DELETE` |
| `cpp` | 2 | 15 | in contract (call-anchored) |
| `csharp` | 2 | 75 → 69 | C1: `public void Dispose()` declared |
| `css` | n/a | — | no runtime payload (`css-declarative-no-runtime-payload-morphology`) |
| `dart` | 2 | 55 → 44 | C1: `void dispose() {` declared (11 of 55) |
| `dockerfile` | 2 | 0 | in contract (package-cache clean forms) |
| `embedded_python` | 2 | 17 → 11 | C1: `def close(self):` / `def __exit__(` declared (python twin) |
| `fortran` | 2 | 90 | in contract (`CLOSE`/`DEALLOCATE`/`NULLIFY`) |
| `go` | 2 | 68 → 31 | C5: `Unlock`/`RUnlock` are sync_locks' (~28 hits) |
| `groovy` | 2 | 2 | in contract |
| `haskell` | 2 | 1 | in contract (`finally`/`bracket` kept per #2869's cession) |
| `html` | 2 | 0 | in contract (embedded-JS timer/listener releases) |
| `java` | 2 | 5 → 4 | C1: `private static void close(` declared |
| `javascript` | 2 | 76 → 34 | C1: bare verbs counted declarations/prose; C5: `delete` is state_mutation's |
| `jcl` | 2 | 36 | in contract (`DISP=(...,DELETE)` deallocation disposition) |
| `kotlin` | 2 | 0 | in contract (call-anchored; `use(`) |
| `livecode` | 2 | 18 | in contract (statement forms) |
| `lua` | 2 | 375 → 310 | C4: `collectgarbage("stop"/"restart"/...)` configures the collector |
| `m4` | 2 | 0 | in contract (`popdef` destroys a definition) |
| `makefile` | **3 → 2** | 0 | C1+C5: the `clean:` header is func_start's unit; its `rm -f` recipe carries the sites — **the open cell** |
| `markdown` | n/a | — | literate plane (`markdown-lit-plane-morphology`) |
| `matlab` | 2 | 39 → 36 | C3: statement position or call form; executing eval-strings keep their hits |
| `objective-c` | 2 | 23 → 21 | C1: `- free` / `- (void)free` declared the method |
| `perl` | 2 | 527 → 138 | C3: `return undef` yields a value, `undef,` is a placeholder, `=head2 finish` documents; C1: `sub finish`/`sub DESTROY` declare |
| `php` | 2 | 126 | in contract (call-anchored `unset(` etc.) |
| `powershell` | 2 | 181 | in contract (`Remove-Item` family — #2843's shape, already owned) |
| `python` | 2 | 30 → 27 | C1: `def close(self):` declared (embedded_python twin) |
| `ruby` | 2 | 0 | in contract (call-anchored) |
| `rust` | 2 | 22 → 11 | C1: `fn drop(&mut self)` declared the Drop impl (9 of 22) |
| `scala` | 2 | 43 → 32 | C1/C3: `def close():` declared, log-string verbs were names; region openers (`finally`/`bracket`) stay |
| `scheme` | 2 | 44 → 35 | C3: handler-table and `set-who!` positions passed the name; head position only |
| `shell` | 2 | 757 → 185 | C2: `exit`/`logout` terminate (panics_and_aborts owns exit); #2843: gains non-root `rm` flags-with-f (root form stays high_risk's). Plant re-authored: `exit 0` → `rm -f scratch` |
| `solidity` | 2 | 0 | in contract (`delete` statement) |
| `sqlite` | 2 | 96 | in contract — the #2843 precedent (`DROP TABLE`/`DELETE FROM`/`DETACH`/`VACUUM`) |
| `swift` | 2 | 3 | in contract (call-anchored; `deinit {` has no parens and correctly never fired) |
| `tcl` | 2 | 129 → 176 | #2843: gains `file delete` — every added hit a real deletion (`file delete -force ${distpath}/...`) |
| `typescript` | 2 | 299 → 121 | C1: `dispose(): void;` / `dispose() {` declared (~46); C5: `delete` is state_mutation's |
| `yacc` | 2 | 14 | in contract (call-anchored `free`/`YYFREE`) |
| `yaml` | 2 | 0 | in contract (`rm -rf` non-root + `docker compose down` — #2843's shape, already owned) |
| `zig` | 2 | 1130 → 1064 | C1: `pub fn deinit(` declared; the defer/errdefer call mass is genuine allocator discipline |

## Recorded residue (no issue filed; no cell evidence)

- cobol's quote guard stops `'CLOSE ...'` at string **start**; a mid-string
  ` CLOSE ` still matches. The remaining 389 are dominated by real
  `CLOSE <file>` statements; a statement-position anchor would need the
  #2824-style scope filter and there is no cell to move.
- js/ts method-shorthand declarations **with parameters** (`close(fd) {`)
  survive the empty-paren declaration lookahead; the crucible mass was the
  empty-paren interface form, which is excluded.
- ada's bare `\bFinalize\b` would count a `procedure Finalize` declaration
  (C1) — the crucible has no ada corpus to measure against.
- agc `DOALARM EQUALS ENDOFJOB` (an alias definition) and label-position
  `ENDOFJOB` are C1-shaped; Mode-A label semantics make a regex-level
  exclusion unsafe (the #2824 statement filter has no ABAP-style period to
  anchor on).
