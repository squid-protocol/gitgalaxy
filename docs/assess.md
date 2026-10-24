# `gitgalaxy assess`: the offline readiness scan (#4726)

`gitgalaxy assess` reads a COBOL / CICS estate on your own machine and writes a JSON report of what it uses: counts,
feature names, program names (or, with redaction, labels in their place) and statuses. It never makes a network call,
never writes into the estate, and never copies source text into the report. You read the report before deciding
whether to send it to anyone.

## Install

Python 3.11 or later. You do not need Docker, Db2, a JDK or a compiler.

```sh
python -m venv gg && . gg/bin/activate
pip install "gitgalaxy[translator] @ git+https://github.com/squid-protocol/gitgalaxy@<tag>"   # or from a checkout: pip install -e ".[translator]"
gitgalaxy assess --help
```

A plain `pip install gitgalaxy` (no extras) runs the inventory: counts, feature names and statuses of every program. The
`translator` extra installs the COBOL grammar (`tree-sitter-language-pack`), which the translate-only dry run needs.
Without it the command prints `translate-only dry run skipped: pip install gitgalaxy[translator]` on standard error
and writes the report without the `translation` fields (the same as `--no-translate`). A test builds the wheel, installs
it into a fresh virtual environment with no extras and runs the installed command
(`tests/cobol_mainframe/test_assess_clean_install.py`). The same check runs standalone, stdlib only, as
`python scripts/check_assess_install.py` (builds the wheel, installs it into a fresh venv with `--no-index`, assesses a planted
estate with the network cut, and asserts the report; `--wheelhouse DIR` installs the translator extra from local wheels; `--estates CORPORA` also assesses each of the six
burned estates, plain and redacted, with the installed command). CI runs it with the wheelhouse and `--estates` as a step of `ports-compile.yml` (the job that already fetches the corpora). After each release `publish-assess-check.yml` runs the same script with `--from-pypi VERSION`: it installs
`gitgalaxy[translator]==VERSION` from PyPI on a clean runner (the only networked step), then assesses the planted estate
with the network cut and checks `tool_version`. Run it by hand from Actions with a version. On an offline site, build the wheels on a connected machine
(`pip wheel "gitgalaxy[translator]" -w wheels/`), copy them across, and install with
`pip install --no-index --find-links wheels/ "gitgalaxy[translator]"`.

GitGalaxy is licensed under PolyForm Noncommercial 1.0.0. For commercial use, set the `GITGALAXY_LICENSE_KEY` your
licence came with. Without a key, the scan waits a few seconds before it starts.

## Run

```sh
gitgalaxy assess /path/to/estate --out report.json
gitgalaxy assess /path/to/estate --redact --out report.json                          # labels instead of names
gitgalaxy assess /path/to/estate --redact --redact-key-file site.key --out report.json   # the same labels every run
gitgalaxy assess /path/to/estate --options estate_options.json --out report.json
gitgalaxy assess /path/to/estate --jcl /path/to/compile/jcl --out report.json        # options from your compile JCL
```

- `ESTATE` is a directory holding the programs (`.cbl`, `.cob`, `.cobol`), their copybooks and BMS maps, and any
  assembler members, in any layout.
- `--options` is the estate options file (compiler, LE, Db2 and CICS options with their provenance; see
  `gitgalaxy/core/estate_options.py`). Without it, every option is IBM's default.
- `--no-translate` skips the translate-only dry run (below); the report is then the inventory alone.
- `--jcl` is a JCL member or a directory of them (`.jcl`, `.cntl`, `.proc`, `.prc`). The `PARM` of each
  `EXEC PGM=IGYCRCTL` step is read as the compiler options, with the member and line as provenance. It cannot be
  combined with `--options` (the command refuses both by name). What the JCL leaves open is printed on standard error,
  as option names only, never JCL text:
  - Several compile steps whose `PARM`s differ: only the options all of them agree on are kept, because the JCL does
    not say which program each step builds. A step with no `PARM` leaves none.
  - `PARM='OPTFILE'`: the options are in a SYSOPTF member, which is not read; IBM's defaults apply.
  - No `IGYCRCTL` step: IBM's defaults apply.
  - Not read: `PARM.step` overrides on a cataloged compile procedure, and the LE, Db2 and CICS options (use
    `--options` for those).
- `--out` may not point inside the estate. Without `--out`, the report goes to standard output.
- `--verbose` shows the engine's own scan log on your terminal. That log can name files, and it is never part of the
  report.

## What the report holds

| field | contents |
|---|---|
| `schema`, `tool_version`, `redacted` | `gitgalaxy-assess/1`, the installed version, and whether names are labels |
| `totals` | COBOL programs, parsed, unparsed, refused by family, assembler members |
| `eras` | programs per era (0 = macro-level CICS to 4 = Enterprise COBOL), mixed-era programs, programs per era tell |
| `features` | per category (`statements`, `data_types`, `cics_commands`, `cics_options`, `sql_forms`, `intrinsic_functions`, `compile_options`, `refusal_families`): each feature name, how often it occurs, and which programs use it |
| `other` | per category, how many features fell outside its vocabulary: their count, occurrences and programs, never their text |
| `copybook_gaps` | each copybook a program COPYs that the estate does not hold, and the programs that need it |
| `programs` | each program: name, `cobol` / `assembler`, status (`parsed`, `unparsed`, `refused by family`), a reason (`missing copybook`, a parser error's class name, or the refusal family), its era tags, and for a parsed program its translate-only result (below) |
| `totals.translation` | parsed programs per translate-only result: `whole`, `holes`, `refused` |
| `rules` | with the dry run: the ranked rules to land (below) |

### Translate-only dry run

For each parsed program the command runs the deterministic translator (no model, no Docker, Db2 or JDK) and keeps only
the outcome: `translation` (`whole`, `holes` or `refused`), `statements`, `translated_statements`, `holes` (a count),
and for a refusal the exception's class name (`refusal`; `Timeout` after 60 s). A hole's text is never written, because
it can quote your program.

Read it as a lower bound. The dry run translates each program alone, against a placeholder service and no generated
project, so a CICS program's COMMAREA contract and the services of the programs it CALLs or LINKs to are not resolved,
and a callee's holes are not credited to its caller. It is a translation status, not a proof level: nothing here says a
program behaves as it does on z/OS.

### Ranked rules

With the dry run the report carries `rules`: `classes` (how many distinct gaps the estate shows) and `ranked`, the top 25.
Each hole of each program that does not translate whole is reduced to a gap class: a COBOL statement (`MOVE`), `EXEC
CICS` with the spec's command words (`EXEC CICS WRITE`), or `EXEC SQL`, plus at most one reason from a fixed list
(`no generated Db2 repository method`, `no batch package`, `key length not known`, `not modelled`, `no such item`, ...);
a refusal is `refused: <exception class>`; anything the list does not name is the one word `other`. Per rule:

- `only`: programs this rule alone keeps from whole (landing it makes them whole, as far as the dry run can tell);
- `one_away`: programs left one other rule from whole;
- `touched`: programs with the rule at all;
- `only_by_era`: the era mix of the `only` programs (`none` where no era tag).

The order is `only`, then `one_away`, then `touched`, the order of `cics_census.py blockers`. Rules carry no program
name, so redaction changes nothing here. The hole's own text, which can quote your program, is never written; `validate`
refuses a rule outside these classes. Because of the lower bound above, some top rules are the placeholder's
(`no generated screen for map`, `no batch package`), not the estate's: read them with that in mind.

A feature name is printed only if it is in a closed vocabulary:

- the words of the CICS command spec (`gitgalaxy/standards/cics/commands/`);
- IBM's COBOL statement verbs and intrinsic functions;
- the SQL statement forms, the data types and the semantic compile options;
- the refusal families and the era tells.

Anything else is counted under `other`. For example, CardDemo's sequence-area numbers, which the census fallback reads
as CICS command words, are counted there and never printed. A parser's error message is never printed, only its class
name. Source line numbers are dropped.

## How "no source text" is enforced

1. **One way out.** `gitgalaxy/tools/readiness/schema.py:project` is the only function that builds a report.
2. **Checked again before writing.** `schema.validate` re-checks the finished report: field names, vocabularies, and
   that every name is a program in the report (or a label). If the check fails, nothing is written and the command
   exits with code 3.
3. **Tests.** `tests/cobol_mainframe/test_assess.py` holds the report against the source of every burned estate. No
   string literal, comment, code line, sequence-area value, data name or paragraph name may appear. A planted estate
   puts a marker in each of those places and checks that it never appears.

**Offline:** `gitgalaxy/tools/readiness/offline.py` blocks network sockets and DNS lookups, both in the command and in
the scan it runs. Linux workers inherit the block when they fork. On macOS and Windows the scan's worker processes
start fresh, so the scan passes them `GITGALAXY_ASSESS_OFFLINE` and each worker's initializer installs the block itself
(#5235; `test_a_spawn_start_scan_worker_runs_under_the_guard` runs a spawn-start worker and checks it refuses a
connection).

**Read only:** the scan's database and the generated BMS copybooks go to a temporary directory that is deleted
afterwards. The engine scan runs `--db-only --no-dependency-cache` with git history off. The tests compare every
file's size, modification time and hash, and the directory list, before and after a run.

## Redaction

`--redact` replaces each program path with `P-` plus 12 hex digits, and each copybook name with `C-` plus 12 hex
digits. The label is an HMAC-SHA256 of the name.

- **Without a key file:** the key is random and thrown away, so nobody can map a label back to a name, and two runs
  give different labels.
- **With `--redact-key-file`:** the same key gives the same labels, so two reports can be compared. Keep the key on
  site.

Counts are the same as in the plain report.
