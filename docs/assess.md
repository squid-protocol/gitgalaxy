# `gitgalaxy assess`: the offline readiness scan (#4726)

`gitgalaxy assess` reads a COBOL / CICS estate on your own machine and writes a JSON report of what it uses: counts,
feature names, program names (or, with redaction, labels in their place) and statuses. It never makes a network call,
never writes into the estate, and never copies source text into the report. You read the report before deciding
whether to send it to anyone.

## Install

Python 3.10 or later. You do not need Docker, Db2, a JDK or a compiler.

```sh
python -m venv gg && . gg/bin/activate
pip install "gitgalaxy[translator] @ git+https://github.com/squid-protocol/gitgalaxy@<tag>"   # or from a checkout: pip install -e ".[translator]"
gitgalaxy assess --help
```

The `translator` extra installs the COBOL grammar (`tree-sitter-language-pack`), which is what reads the programs. There is no
published package or tested clean-machine install yet; both are follow-ups of #4726. On an offline site, build the
wheels on a connected machine (`pip wheel "gitgalaxy[translator]" -w wheels/`), copy them across, and install with
`pip install --no-index --find-links wheels/ "gitgalaxy[translator]"`.

GitGalaxy is licensed under PolyForm Noncommercial 1.0.0. For commercial use, set the `GITGALAXY_LICENSE_KEY` your
licence came with. Without a key, the scan waits a few seconds before it starts.

## Run

```sh
gitgalaxy assess /path/to/estate --out report.json
gitgalaxy assess /path/to/estate --redact --out report.json                          # labels instead of names
gitgalaxy assess /path/to/estate --redact --redact-key-file site.key --out report.json   # the same labels every run
gitgalaxy assess /path/to/estate --options estate_options.json --out report.json
```

- `ESTATE` is a directory holding the programs (`.cbl`, `.cob`, `.cobol`), their copybooks and BMS maps, and any
  assembler members, in any layout.
- `--options` is the estate options file (compiler, LE, Db2 and CICS options with their provenance; see
  `gitgalaxy/core/estate_options.py`). Without it, every option is IBM's default.
- `--jcl` is not supported yet. The command refuses it by name and does not ignore it. Until it is supported, pass the
  options your JCL sets with `--options`.
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
| `programs` | each program: name, `cobol` / `assembler`, status (`parsed`, `unparsed`, `refused by family`), a reason (`missing copybook`, a parser error's class name, or the refusal family), and its era tags |

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
start fresh without it, which is a follow-up.

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

## Follow-ups (#4726)

- A published package, and a CI job that installs it on a clean machine.
- The translate-only dry run per program (whole / with holes / refused) with no JDK.
- `--jcl`.
- The readiness report's ranked rules once #5228 lands.
- The network block on spawn-start platforms (macOS and Windows).
