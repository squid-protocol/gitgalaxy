# COBOL ↔ Java Scan Parity

> **Related:** [`tests/tools/det_port.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/tests/tools/det_port.py) · [`tests/tools/proof_sweep.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/tests/tools/proof_sweep.py) · [`docs/language_status/oracle_assumptions.md`](https://github.com/squid-protocol/gitgalaxy/blob/main/docs/language_status/oracle_assumptions.md) · [`gitgalaxy/core/aperture.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/core/aperture.py)

## Summary
We scanned the same programs three ways with GitGalaxy: the original COBOL, the deterministic Java port (the "det port", proven equivalent to the COBOL under GnuCOBOL, the CICS model and Db2), and, where one exists, the model-written Java port. That gives 49 programs from three estates (CardDemo, CBSA, GenApp) where both sides are known to behave the same. Any difference between their scans therefore comes from the language and the translation, not from a change in behaviour.

The short version:

- **Structure keeps its rank.** The programs that have the most paragraphs, branches and state changes in COBOL also have the most in Java. Paragraph count → method count has Spearman ρ = 0.94.
- **Size does not.** The det port is about five times the code lines and nine times the token mass of the COBOL. The model port is about the same size as the COBOL.
- **I/O moves out of the program.** In the det port, file, queue, CICS and SQL operations are calls into the `cobolrt` runtime, which the scanner did not recognise as I/O. The scanner recognises them since #4163.
- **Risk scores do not compare across languages.** They are normalised within each scan, so they rank files inside one language only.
- **Debt is written differently.** The model ports carry 46 TODO/FIXME lines; the det ports carry none and instead throw named `Hole`s for anything not translated.

## Scope

| Estate | Programs | COBOL code lines | Det-port code lines | Ratio | COBOL paragraphs → Java methods | Model ports |
|---|---:|---:|---:|---:|---:|---:|
| CardDemo (AWS) | 28 | 17,279 | 64,899 | ×3.76 | 613 → 1,231 | 23 |
| CBSA (IBM CICS Bank Sample) | 8 | 3,501 | 10,250 | ×2.93 | 144 → 313 | 0 |
| GenApp (IBM CICS General Insurance) | 13 | 2,818 | 21,892 | ×7.77 | 69 → 365 | 0 |

All 49 det ports translate fully; 48 of the 49 equivalence cases behind them prove (the exceptions are listed in `proof_sweep.py`'s `KNOWN_UNPROVEN`; of the programs in this table only COCRDUPC is affected). All 23 model ports prove.

## Method

1. For each estate and each form, build a separate git repository: the COBOL programs with their copybooks; the det-port service classes from a full sweep (the `cobolrt` runtime excluded); the committed model ports from `tests/equivalence/<case>/port/service/`. Where a program appears in several equivalence cases, the first case is used.
2. Commit each tree (the scanner reads committed files) and run `galaxyscope` on it.
3. Read per-file metrics from each scan's `<repo>_galaxy_master.db`, table `file_data`.
4. Pair each COBOL program with its Java file(s). For each metric report:
   - **Spearman ρ** between the COBOL values and the Java values across the programs, with tied values given their average rank (1.0 means both forms rank the programs in the same order; "–" means one side is constant, so no ranking exists);
   - the **median** in each form;
   - the **median per-program ratio** Java ÷ COBOL.

Two adjustments were needed for the det trees, because the default scan excludes almost all of them (see [Scanner lessons](#scanner-lessons)):

- long lines were rewrapped (formatting only: long string literals split into chunks, long conditions broken at `&&`, `||` and `,`);
- the Lexical Monotony gate was lifted through a wrapper script. Every other gate and every measurement is the scanner's own.

The rewrapping adds lines: the median det file gains 19% more non-blank lines (maximum ×2.1). Read the det-port line counts and line ratios below with that in mind; the as-emitted line ratio is closer to ×4.2 than ×5.

## What stays the same

Rank agreement, COBOL vs det port, all 49 programs:

| Metric | ρ det | COBOL median | Det median | Det ÷ COBOL | ρ model (23) | Model ÷ COBOL |
|---|---:|---:|---:|---:|---:|---:|
| Functions / paragraphs | 0.94 | 11 | 32 | ×3.00 | 0.60 | ×2.44 |
| Branch points | 0.83 | 27 | 159 | ×5.14 | 0.62 | ×1.62 |
| State mutations | 0.76 | 62 | 333 | ×5.25 | 0.62 | ×0.90 |
| Code lines | 0.71 | 251 | 1,792 | ×4.96 | 0.69 | ×1.09 |
| Linear statements | 0.69 | 35 | 126 | ×3.91 | 0.62 | ×1.93 |
| Guards / safety checks | 0.69 | 2 | 14 | ×3.50 | −0.18 | ×0.00 |
| Imports / copybooks | 0.75 | 6 | 26 | ×4.58 | 0.29 | ×3.05 |
| Largest function complexity | 0.69 | 8 | 44 | ×3.60 | 0.77 | ×1.25 |
| Token mass | 0.62 | 3,606 | 50,688 | ×9.15 | 0.82 | ×1.18 |
| Mean function complexity | 0.57 | 3.2 | 4.3 | ×1.78 | 0.34 | ×0.86 |

The same structural metrics hold their rank within each estate:

| Metric (ρ, COBOL vs det) | CardDemo (28) | CBSA (8) | GenApp (13) |
|---|---:|---:|---:|
| Functions / paragraphs | 0.97 | 0.98 | 0.94 |
| Branch points | 0.83 | 0.95 | 0.86 |
| State mutations | 0.84 | 0.90 | 0.80 |
| Code lines | 0.74 | 0.97 | 0.87 |
| Linear statements | 0.76 | 0.86 | 0.94 |
| Guards / safety checks | 0.82 | 0.87 | 0.24 |
| Largest function complexity | 0.69 | 0.66 | 0.73 |
| Imports / copybooks | 0.56 | 0.96 | 0.90 |
| Risk: cognitive load | 0.61 | −0.33 | 0.25 |
| Risk: safety | 0.65 | 0.10 | 0.38 |
| Risk: tech debt | 0.22 | 0.44 | 0.75 |

The det port keeps the COBOL's shape because it translates paragraph by paragraph and statement by statement. Each COBOL paragraph becomes about three Java methods: the paragraph itself plus methods the emitter generates around it. The model port restructures more freely, so its rank agreement is lower on structure (ρ 0.60 for functions) even though its size is much closer to the COBOL.

## What changes, and why

| Metric | ρ det | COBOL median | Det median | Det ÷ COBOL | ρ model | Model ÷ COBOL |
|---|---:|---:|---:|---:|---:|---:|
| I/O signals | 0.24 | 4 | 0 | ×0.00 | 0.74 | ×0.00 |
| API-surface signals | 0.35 | 1 | 8 | ×8.00 | 0.69 | ×11.00 |
| Doc markers | 0.61 | 0 | 21 | ×28.50 | 0.42 | ×11.50 |
| Risk: cognitive load | 0.49 | 81.2 | 39.0 | ×0.47 | 0.42 | ×0.59 |
| Risk: safety | 0.25 | 90.5 | 82.8 | ×0.91 | 0.51 | ×1.01 |
| Risk: tech debt | 0.24 | 13.0 | 9.6 | ×0.66 | 0.48 | ×4.13 |
| Risk: documentation | – | 100 | 42.6 | ×0.43 | – | ×0.38 |
| Risk: verification | – | 2.5 | 80 | ×32.55 | 0.32 | ×1.00 |

**Size.** The det port spells out what the COBOL compiler does implicitly: byte-level storage, explicit truncation (`TRUNC(STD)`), sign and packed-decimal handling, `Field` accessors, CICS response checks. That is where the ×5 code lines and ×9 token mass come from. The model port is ×1.09 code lines and ×1.18 token mass.

**I/O.** `READ`, `WRITE`, `EXEC CICS` and `EXEC SQL` are I/O signals in COBOL. In the det port they become calls such as `DetCics` and `DetSql` methods in the `cobolrt` runtime. The scanner does not know those calls, and the runtime itself was not part of the scan, so the det-port I/O reading falls to zero in most files (ρ 0.24) and the API reading rises instead. Since #4163 the scanner counts these runtime calls as I/O and IPC; a rescan of the same 49 pairs gives I/O ρ 0.87 and IPC ρ 0.84. The model ports gained readings from the same change (13 of 23 now show I/O, 15 of 23 IPC).

**Risk scores.** The risk vectors are percentile-style and normalised within each scan. A COBOL cognitive-load score of 81 and a Java score of 39 are not on the same scale, and even the ranking only partly carries over (ρ 0.49 overall, −0.33 in CBSA). Use risk scores to rank files within one language.

**Archetype.** Only 9 of the 49 programs keep exactly the same composition archetype:

| Programs | COBOL archetype | Det-port archetype |
|---:|---|---|
| 15 | Large Core Modules | Large Core Modules (3) |
| 12 | Interface Declarations Files | Encapsulated Accessors Files |
| 9 | Large Core Modules | Large Core Modules |
| 9 | Large Core Modules | Encapsulated Accessors Files |
| 3 | Large Core Modules (3) | Encapsulated Accessors Files |
| 1 | Interface Declarations Files | Large Core Modules (3) |

Copybook-heavy COBOL reads as "Interface Declarations"; the same records in the det port become typed `Field` accessors and read as "Encapsulated Accessors". This is a change of representation, not of behaviour.

**Debt.** In the CardDemo model ports, 46 lines across 12 files carry TODO/FIXME markers; tech-debt risk is ×4.13 the COBOL's. The det ports have no TODO/FIXME lines. Anything the det port does not translate becomes a named `Hole` that throws when reached (51 `new Hole(` sites in 40 of the 49 files; 40 of them guard CICS files the generated project has no store for, 10 guard BMS maps and mapsets, and 1 is an untranslated dynamic `CALL`). The scanner counts the TODOs but not the holes, so the det ports' debt reads lower than it is.

**Branch growth in small programs.** The median program gains ×5.1 branch points in the det port. The programs furthest from that median are all small:

| Program | Estate | COBOL code lines | COBOL branches | Det branches | Ratio |
|---|---|---:|---:|---:|---:|
| ABNDPROC | CBSA | 114 | 1 | 73 | ×73.0 |
| UPDACC | CBSA | 208 | 3 | 89 | ×29.7 |
| DELACC | CBSA | 437 | 7 | 159 | ×22.7 |
| CUSTCTRL | CBSA | 146 | 4 | 79 | ×19.8 |
| LGACVS01 | GenApp | 88 | 4 | 74 | ×18.5 |
| LGDPVS01 | GenApp | 97 | 4 | 72 | ×18.0 |

Every det port carries a fixed amount of code (response checks, abend paths, storage setup, resource dispatch). In a program with a handful of COBOL branches that overhead dominates. At the other end, the large batch programs grow least (CBTRN02C ×1.77, CBACT04C ×1.83, CBTRN01C ×1.84).

**Largest functions.** The most complex det-port functions come from long compound conditions translated literally:

| Program | COBOL max function complexity | Det max function complexity |
|---|---:|---:|
| COACTUPC | 97 | 205 |
| COTRTUPC | 33 | 133 |
| COTRTLIC | 40 | 129 |
| COCRDUPC | 39 | 97 |
| XFRFUN | 21 | 92 |

## Scanner lessons

1. **The default scan skips det ports.** On the first scan 45 of the 49 det-port files were excluded: lines over 500 characters (`MAX_LINE_LENGTH`, packed literals and deeply nested conditions) and the Lexical Monotony gate (aperture Gate 5.1), which classifies repetitive indentation as generated noise. The classification is correct, since the files are generated, but a ported estate would look nearly empty. A det port needs a way to declare itself as intended code without lifting those gates for everyone. That is pending in #4164.
2. **Runtime calls were not recognised.** The scanner knew JDBC and common Java I/O, not `cobolrt`, so I/O could not be compared before and after a det port. #4163 fixed this (I/O ρ 0.24 → 0.87).
3. **Holes were not counted as debt.** The det port's named `Hole`s are its explicit list of untranslated work. Since #4163 the scanner counts an untranslated `throw new Hole` as planned debt, the way it counts TODO markers.
4. **Risk scores need a cross-language mode to answer "did the migration make this riskier?".** Today they only rank files within one scan.
5. **The pairs are a test corpus for the scanner.** Because each pair behaves identically, metrics that should be invariant (function, branch and mutation rank) can be checked across all 49 pairs. A change to the scanner that makes those rankings depend on the language would show up there.

## Translation lessons

1. **Structural parity is a cheap pre-proof check.** Function and branch counts track the COBOL closely. A det port whose ratios fall far outside its estate's norm, after allowing for the fixed per-program overhead, is worth a look before running GnuCOBOL or Db2.
2. **Readability layers have measurable targets.** Today's det port is ×5 the code lines, its largest functions are ×3.6 as complex, it has lines over 500 characters and it fails the monotony gate. The model port shows what ordinary Java of the same programs looks like (×1.09 lines). A det port that passes the default aperture gates without help is a concrete milestone.
3. **Refactor the biggest conditions first.** The largest det functions (COACTUPC, COTRTUPC, COTRTLIC) are long `IF` conditions translated literally; the scan ranks them, so the readability work can start there.
4. **Report proof and debt together for model ports.** The proof shows a model port behaves like the COBOL; the TODO count shows what it still leaves unfinished.

## Follow-ups

- **Merged, #4163:** the Java scanner counts `cobolrt` calls as I/O (CICS file, queue and counter operations on the task, `DetSql` statements, batch file operations) and `task.link` / `xctl` / `returnTransid` as IPC, and counts an untranslated `throw new Hole` as planned debt.
- **Merged, #4162:** `tests/tools/det_parity.py` adds a structural parity warning (never a failure) to `det_port.py run` and `check`. It fits a fixed overhead and a slope separately for batch and CICS programs; none of the 49 pairs warn.
- **Pending, #4164:** det ports carry a provenance header, and the aperture admits a declared port past the generated-noise gates, so a det-ported estate scans without the adjustments described in [Method](#method).
- **In progress:** a scanner test over the 49 pairs checking that structural rankings stay invariant.
