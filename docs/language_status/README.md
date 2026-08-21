# Language Status

One doc per language describing what GitGalaxy's structural-signature engine actually covers —
what it detects, what it explicitly doesn't, how deep the test evidence is, which closed
issues/PRs shaped it, and real-world scan output proving it runs on production code in that
language. Built entirely from primary sources (`gitgalaxy/standards/language_standards.py`, the
`tests/extraction/languages/` suite, closed GitHub issues, and the
[`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output) corpus) — see the
`language-status` skill (`.claude/skills/language-status/SKILL.md`) for the exact process and
commands used to produce each one.

**These are snapshots, not a live view.** The "at a glance" numbers below were generated
2026-08-09 against `main`. `language_standards.py`, the test suite, and issue history all keep
moving — re-run the skill's data-gathering commands rather than trusting a stale table if the
answer matters.

**`python.md` also has a "Measured accuracy" section (§9)** — a real-corpus diff of GitGalaxy's
own extraction against Python's `ast` module as ground truth, not just the isolated-snippet unit
tests every other section describes. Across two rounds of measurement it found four real defects
([#1182](https://github.com/squid-protocol/gitgalaxy/issues/1182),
[#1183](https://github.com/squid-protocol/gitgalaxy/issues/1183), and
[#1184](https://github.com/squid-protocol/gitgalaxy/issues/1184) — all now fixed — plus
[#1193](https://github.com/squid-protocol/gitgalaxy/issues/1193), still open) and measured
function recall on real code well below what the unit-test suite alone would suggest — read it
before assuming "tests pass" means "finds everything on real code." It's also a worked example of
a subtler lesson: #1184 is a fully-verified fix (the component it touches is provably 100%
correct in isolation now), but real-pipeline recall barely moved, because #1193 — undiscovered
until the *second* measurement round — sits upstream of it and corrupts the input before #1184's
fix ever gets a chance to run. Worth repeating for other languages with an available AST/grammar
(see §9's `tree-sitter-language-pack` note) once a language's base doc exists.

**`javascript.md`'s §9 is the first repeat of that methodology via `tree-sitter-language-pack`**
(python.md's own §9 flagged this as the path to scale beyond Python's stdlib `ast`) — confirms
#1209/#1216's `args` capture-group fix works on real code (100% args-count exact match across two
corpora), and found one blocking infra bug (fixed same-day,
[#1220](https://github.com/squid-protocol/gitgalaxy/pull/1220)) plus two open extraction defects
([#1221](https://github.com/squid-protocol/gitgalaxy/issues/1221) — phantom functions from
unguarded bare call statements, also affects `typescript`/`java`/`csharp`/`apex`/`dart`/`groovy`;
[#1222](https://github.com/squid-protocol/gitgalaxy/issues/1222) — real functions silently dropped
from class bodies, tied to a previously-unfixed diagnosis in #789). Worth reading before assuming
`tree-sitter-language-pack` is a trivial drop-in for the next language's §9 — javascript's pass
needed a from-scratch tree-sitter node-walker (no existing helper), and surfaced a genuine,
separate infra bug along the way.

## Signature-bearing languages (46)

`LANGUAGE_DEFINITIONS` recognizes 59 languages/formats; these 46 have at least one non-`None`
structural-signature rule (`func_start`/`branch`/`io`/etc.) — the ones a per-language status doc
in this folder is actually for. "Rules" is wired-keys/total-keys in that language's `rules` dict.
"Extraction tests" / "Strict tests" are live `pytest --collect-only` counts for
`tests/extraction/languages/test_<lang>.py` / `test_<lang>_strict.py` — a blank extraction count
means that language's four extraction-gauntlet cases (`func_start`/`args`/`class_start`/
`_dependency_capture`) haven't been migrated out of the old monolithic gauntlet files yet (see
epic #813), not that no cases exist.

| Language | Status | Lexical family | Rules wired/total | Extraction tests | Strict tests | Status doc |
|---|---|---|---|---|---|---|
| **[abap](abap.md)** | production | positional_abap | 46/48 | 42 | 87 | **written** |
| ada | production | line_exclusive_dash | 49/53 | 48 | 73 | not written |
| **[agc_assembly](agc_assembly.md)** | production | line_exclusive | 39/48 | 155 | 76 | **written** |
| **[apex](apex.md)** | production | standard_block | 43/48 | 4 | 93 | **written** |
| **[assembly](assembly.md)** | production | line_exclusive | 42/52 | 148 | 83 | **written** |
| **[c](c.md)** | production | standard_block | 50/52 | 42 | 86 | **written** |
| **[cobol](cobol.md)** | production | positional_anchored | 48/52 | 62 | 82 | **written** |
| **[cpp](cpp.md)** | production | standard_block | 52/52 | 46 | 76 | **written** |
| **[csharp](csharp.md)** | production | standard_block | 51/52 | 61 | 106 | **written** |
| css | production | standard_block | 30/48 | 18 | 74 | not written |
| dart | production | standard_block | 51/52 | 91 | 86 | not written |
| dockerfile | production | line_exclusive | 43/52 | 34 | 86 | [dockerfile.md](dockerfile.md) |
| embedded_python | production | line_exclusive | 51/52 | 64 | 107 | not written |
| **[fortran](fortran.md)** | production | positional_anchored | 45/52 | 35 | 101 | **written** |
| go | production | standard_block | 51/52 | 47 | 84 | not written |
| groovy | production | standard_block | 44/48 | 53 | 91 | not written |
| haskell | production | recursive_block_haskell | 52/52 | 48 | 97 | not written |
| html | production | block_exclusive | 39/48 | 91 | 123 | not written |
| java | production | standard_block | 50/52 | 67 | 91 | not written |
| **[javascript](javascript.md)** | production | standard_block | 61/64 | 53 | 73 | **written** |
| jcl | production | line_exclusive | 11/24 | 41 | 51 | not written |
| kotlin | production | standard_block | 51/52 | 42 | 90 | not written |
| livecode | production | multi_style_live | 47/52 | 4* | 108 | not written |
| lua | production | multi_style_dash | 50/52 | 41 | 78 | not written |
| m4 | production | line_exclusive | 31/47 | 21 | 73 | not written |
| makefile | production | line_exclusive | 39/52 | 55 | 73 | not written |
| markdown | production | line_exclusive | 4/4 | — | 11 | not written |
| matlab | production | line_exclusive | 48/52 | 45 | 70 | not written |
| objective-c | production | standard_block | 52/52 | 95 | 83 | not written |
| perl | production | line_exclusive | 52/52 | 32 | 69 | not written |
| php | production | standard_block | 51/52 | 4* | 84 | not written |
| powershell | production | embedded_syntax | 50/52 | 68 | 85 | not written |
| **[python](python.md)** | production | line_exclusive | 61/64 | 60 | 92 | **written** |
| ruby | production | line_exclusive | 51/52 | 4* | 66 | not written |
| rust | production | recursive_block | 52/52 | 51 | 68 | not written |
| scala | production | recursive_block | 51/52 | 63 | 90 | not written |
| scheme | production | recursive_block_lisp | 40/47 | 33 | 75 | not written |
| shell | production | line_exclusive | 44/52 | 72 | 82 | not written |
| solidity | production | standard_block | 40/53 | 42 | 72 | not written |
| sqlite | production | multi_style_dash | 47/52 | 63 | 96 | not written |
| swift | production | recursive_block | 51/52 | 36 | 91 | not written |
| tcl | production | line_exclusive | 40/48 | 40 | 65 | not written |
| typescript | production | standard_block | 59/62 | 76 | 101 | not written |
| yacc | production | standard_block | 31/47 | 21 | 48 | not written |
| yaml | production | line_exclusive | 31/49 | 45 | 65 | not written |
| zig | production | line_exclusive | 46/52 | 49 | 61 | not written |

\* `livecode`, `php`, `ruby` show only 4 migrated extraction tests each — their real
extraction-gauntlet coverage is still in the old monolithic `test_function_extraction.py` /
`test_args_extraction.py` / `test_class_extraction.py` / `test_dependency_extraction.py` files,
not yet split out to a per-language file. Check those before assuming thin coverage. (`apex` also
shows 4, but is confirmed fully migrated — its 4 test functions each cover multiple inline
valid/invalid/pathological cases rather than being thin; see `apex.md` §6.)

## Data formats (13, out of scope for a full doc)

`batch`, `blp`, `csv`, `glsl`, `hlo`, `json`, `mlir`, `nix`, `pbtxt`, `plaintext`, `proto`, `td`,
`xml` — recognized by the engine for identification/routing purposes but carry no structural
signatures (`rules` is empty or all keys are pure boilerplate), because there's no executable
logic to structurally signature-match. These don't get a per-language prose doc.

## Writing the next one

See `.claude/skills/language-status/SKILL.md`. Full rollout across all 46 is tracked as follow-on
work (one sub-issue per language, same shape as epic #813/#1069) rather than attempted in one
pass — `python.md` is the worked template.
