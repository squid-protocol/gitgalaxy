# The `encapsulation` rule contract (#2766)

Phase 3 of the contract roadmap (`docs/contract_roadmap.md`, epic #2812): the sheet row
`encapsulation` goes from `draft` to **`stated`**. This was the bucket's carve-out — it is
unplanted but it feeds gated formulas (`def_encapsulation`, and `_calc_api_exposure`'s
`exposure_ratio = api_hits / max(api_hits + encapsulation, 1.0)`), so per
`docs/domain_sensor_contracts.md`'s lifecycle rule (a declared row becomes stated the day
it gains **a plant or a gated consumer** and gets the family audit) the gated consumer
plus this audit qualifies it. The precedents are the fifteen stated rows, most directly
`docs/safety_rule_contract.md` (#2869) and `docs/api_rule_contract.md` (#2730).

The draft sentence was "Explicitly hiding logic from the rest of the application".
Forty-odd rules read it forty-odd ways: rust counted `pub` (the *complement* of hiding),
agc_assembly matched every identifier-shaped line (~12.5 hits/file of opcode mnemonics),
go and zig counted every function-local variable (4521 and 15430 crucible hits of
`gp := ...`-shaped locals), perl/lua/shell counted lexical scoping, python and dart
counted every *usage* of an underscore-prefixed name, cobol counted a memory-allocation
section, and java/php/typescript listed an `internal` keyword their languages don't have.

## The contract

> **One hit is a declaration-position marker that excludes a name from the public
> surface, in the language's own morphology.**

Kind `annotation`, unit `annotations`. The score layer reads it as the counterweight in
`exposure_ratio` and via `def_encapsulation` — which is what fixes the comparator (see C2).

## Corollaries

**C1 — declaration position, not usage.** Where the marker is a keyword (`private`,
`protected`, `hidden`), the keyword site is the declaration. Where privacy is part of the
identifier itself — python/dart `_name`, javascript/typescript `#field` — only the
*declaration* counts (`def _x`, `class _x`, `_x = ...`, `self._x = ...`, `#x = / #x( /
#x;` at member position), never the reads and calls that reuse the name. Counting usages
made density incomparable with keyword-morphology languages (python read 3000+ where java
read 264 for comparable hiding effort). Python's dunders (`__init__`, `__all__`) are the
*public* protocol surface and are excluded; `_single` and `__mangled` count.

**C2 — the comparator is PUBLIC, not the language's default.** The formula this signal
feeds measures public-vs-hidden surface, and its sibling `api` counts the marked-public
side (`pub`, `public`, `export`) — so `encapsulation` counts the marked-non-public side,
symmetric with `api`. A marker that merely *restates* a default still counts when it
marks the name non-public: apex `private` (private is apex's default), swift and
solidity `internal`, java `protected` (wider than java's package default, still not
public). The alternative "below the default" reading was considered and rejected: it
rewards strict-default languages and scores an author's explicit `private` as zero —
style-policing, not measurement. Redundant-restatement tokens with near-zero idiomatic
use (an explicit swift `internal`) are low-signal, which is the fidelity/strictness
tables' concern (#2716), not the counting rule's.

**C3 — a marker of the PUBLIC side never counts.** rust's bare `pub` is `api`'s token;
counting it here double-counted exposure as hiding (backward polarity — the #2766
headline defect). rust's genuine non-public markers are the restricted-pub forms:
`pub(crate)`, `pub(super)`, `pub(self)`.

**C4 — scope is not visibility.** perl `my`/`state`/`local`, lua `local`, shell
`local`/`typeset`/`declare` scope a *variable's lifetime and lookup*, not a name's
membership in a public surface — every one of those languages' module-level names stays
reachable. Those rules record the stated absence (`None`). Go is the counter-example
that proves the line: a lowercase first letter IS a per-name visibility marker in go's
grammar (unexported from the package) — it counts, but only at package scope; a
function-local has no visibility to mark (the old indented arm was the 4521-hit bug).

**C5 — no marker morphology means None, not invention.** zig (hiding is the unmarked
default; no private keyword), agc_assembly (no visibility construct), m4
(`m4_pattern_forbid` is error generation), css/html (DOM/style isolation is not name
visibility), dockerfile (`FROM ... AS` is a stage alias), tcl (`namespace eval` is a
structural boundary) — all `None`, the established contract-level-absence pattern.
cobol's `LOCAL-STORAGE SECTION` (per-invocation memory, recursion support) left the rule
for the same reason; OO COBOL's `PRIVATE` stays. makefile's `.SILENT:` (command-echo
suppression) left; `unexport` and the target-specific `private` modifier stay (#2872
tracks the wider m4/makefile visibility questions).

## The 46-language audit

`rule_probe.py encapsulation <lang>` before/after on language-crucible v1.2.0. "—" = no
crucible presence; verdicts from the four-group audit pass (2026-09-09), each verified
against the probe before editing.

| language | crucible | what changed |
|---|---|---|
| abap | — | agrees (PRIVATE/PROTECTED SECTION) |
| ada | — | agrees (`private`) |
| agc_assembly | 7608 → None | catch-all matched every line; no visibility construct (C5) |
| apex | — | agrees under C2 (private counts though it restates the default) |
| assembly | 0 | agrees (.local/.private; honest zero) |
| c | 1246 | agrees (`static` restricts linkage below external) |
| cobol | — | LOCAL-STORAGE SECTION dropped (memory, not visibility); PRIVATE stays |
| cpp | 28 | `internal:` dropped (not a C++ label) |
| csharp | 992 | agrees (private/protected/internal/file are all non-public markers) |
| css | — → None | style isolation is not name visibility (C5) |
| dart | 564 → 506 | usage-counting → declaration anchors; `@private` dropped (not real); `final _Type name` (private-type usage) no longer counts |
| dockerfile | — → None | stage alias is not visibility (C5) |
| embedded_python | → 19 | python twin parity: declaration-position, dunders excluded |
| fortran | 2 | agrees (module PRIVATE) |
| go | 4521 → 700 | top-level declarations only — the indented arm counted every local (C4) |
| groovy | — | agrees |
| haskell | — | agrees (module export lists) |
| html | 0 → None | DOM isolation is not name visibility (C5) |
| java | 264 | `internal` dropped (not a java keyword); protected stays (C2) |
| javascript | → 0 | keyword list dropped (js has no private/protected keywords; `#` matched `#endif` in shader strings); #field declarations only — corpus predates # fields, honest zero |
| jcl | None | already None (agrees) |
| kotlin | — | agrees |
| livecode | — | agrees (`private command/function`) |
| lua | → None | `local` is scope, not visibility (C4) |
| m4 | → None | pattern_forbid is error generation (C5) |
| makefile | 0 | `.SILENT:` dropped; unexport + target `private` stay |
| markdown | None | agrees |
| matlab | 0 | agrees (Access = private/protected) |
| objective-c | — | agrees (@private/@protected/@package) |
| perl | → None | my/state/local are scope, not visibility (C4) |
| php | — | `internal` dropped (not a php keyword) |
| powershell | → 0 | bare words matched 'Private' string literals; anchored to `hidden` member modifier, `$private:`, `function private:` — corpus reads an honest zero |
| python | ~3000+ → 502 | usage-counting → declaration anchors; dunders excluded (C1) |
| ruby | — | agrees (private/protected) |
| rust | 943 → 158 | polarity reversed: bare `pub` was api's token (C3); restricted-pub forms only |
| scala | — | agrees (incl. `private[scope]`) |
| scheme | 0 | agrees (define-private; honest zero) |
| shell | → None | local/typeset/declare are scope, not visibility (C4) |
| solidity | — | agrees under C2 (internal counts; for functions it is a genuine choice — modern solidity has no function default) |
| sqlite | — | agrees (TEMP/TEMPORARY/HIDDEN) |
| swift | — | agrees under C2 (internal = module-only, non-public) |
| tcl | → None | namespace eval is structure, not a per-name marker (C5) |
| typescript | 567 | `internal` dropped (matched './internal' import strings); #fields at declaration position only |
| yacc | — | agrees (`static`) |
| yaml | None | agrees |
| zig | 15430 → None | counting non-pub declarations (incl. locals) measured volume; hiding is the unmarked default (C5) |

## Bless scope

`tests/golden_master_*.json`: the `encapsulation` leaf and the gated readers —
`def_encapsulation`, `encapsulation_ratio`, `risk_api_exposure` via `exposure_ratio`,
and the aggregates that sum them. The largest single movements: zig/agc/perl/lua/shell/
tcl (rules → None), go (−84%), rust (−83%), python (−~80%). This signal remains
**unplanted** in keyword-rosetta; planting it (so `stated` gains the full plant-backed
audit the fifteen precedents have) is the natural corpus companion and is left to a
follow-up PR — the gated-consumer clause covers the lifecycle in the meantime.
