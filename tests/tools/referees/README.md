# COBOL / CICS referee panel (#4377)

Independent open-source COBOL parsers ("referees") scored against the engine and against the
hand-verified answer keys, per fact channel. Test / validation tooling only: nothing here is
imported by `gitgalaxy/`, and no referee's code is vendored. Every referee is installed outside
the repository and invoked as an external, unmodified tool.

| file | role |
|---|---|
| `facts.py` | the common `referee-facts/1` format, the canonical value shapes, and the answer key as a fact source |
| `engine_adapter.py` | the engine: a scanned corpus's master DB through GalaxyIR (+ the unit graph `cobol_answer_key.py` reads) |
| `cobrix_adapter.py` + `java/CobrixFacts.java` | Cobrix: copybook record layouts (offsets, sizes) |
| `treesitter_adapter.py` | Spantree tree-sitter-cobol-enterprise: units, extents, edges, calls, COPY, data items, typed EXEC CICS / SQL |
| `che4z_adapter.py` | Eclipse Che4z COBOL LSP, driven over LSP (`documentSymbol`, #4438): PROGRAM-IDs, units, extents, COPY, data item level + name; `--mode cli` keeps the headless `analysis` CLI (all channels, but fragile) |
| `mapa_adapter.py` | mapa's CallTree: PROGRAM-IDs, COPY / INCLUDE, CALL / LINK / XCTL targets, DB2 tables, CICS file commands |
| `translator_adapter.py` | the det COBOL-to-Java translator's own parse (not a referee: the engine's sibling inside GitGalaxy), for the engine-vs-translator cross-check `tests/tools/fact_crosscheck.py` (#4273) |
| `estate_key.py` | estate-crucible's generated key (#4317) in the answer-key shape, so every adapter runs on it unchanged |
| `run_panel.py` | the nightly entry point: the steps below in order for every burned keyed corpus, scratch results only (#4438) |
| `score.py` | the scorecard: each source vs the key, agreement with the engine, disagreements for adjudication |

The scoring rules are in `score.py`'s docstring and pinned by `tests/cobol_mainframe/test_referee_score.py`.

## Installing the referees

Put them anywhere outside the checkout (the examples use `$REF`). Record the versions you ran: the
scorecard prints each source's version.

**Cobrix** (Apache-2.0, AbsaOSS/cobrix; JDK 11+ and Maven):

```sh
git clone https://github.com/AbsaOSS/cobrix $REF/cobrix
cd $REF/cobrix
# the parent POM still targets Java 7, which current JDKs refuse
mvn -q -pl cobol-parser -am -DskipTests -Dmaven.compiler.source=8 -Dmaven.compiler.target=8 package
mvn -q -pl cobol-parser dependency:build-classpath -Dmdep.outputFile=$REF/cobrix.cp
export COBRIX_CLASSPATH=$(cat $REF/cobrix.cp):$(ls $REF/cobrix/cobol-parser/target/cobol-parser_2.12-*-SNAPSHOT.jar | grep -v javadoc)
```

The adapter compiles `java/CobrixFacts.java` into `$REFEREES_CACHE` (default
`~/.cache/gitgalaxy-referees`) on first use.

**Spantree tree-sitter-cobol-enterprise** (MIT; node, a C compiler, py-tree-sitter >= 0.22):

```sh
git clone https://github.com/Spantree/tree-sitter-cobol-enterprise $REF/tree-sitter-cobol-enterprise
(cd $REF && npm install tree-sitter-cli@0.25)            # src/parser.c is not committed upstream
cd $REF/tree-sitter-cobol-enterprise && $REF/node_modules/.bin/tree-sitter generate   # ~5 min
cc -O2 -fPIC -shared -I src src/parser.c src/scanner.c -o $REF/cobol_enterprise.so
pip install tree-sitter
export TS_COBOL_ENTERPRISE_LIB=$REF/cobol_enterprise.so TS_COBOL_ENTERPRISE_REPO=$REF/tree-sitter-cobol-enterprise
```

**Eclipse Che4z COBOL Language Support** (EPL-2.0; JDK 17+). The server jar ships in the VS Code
extension; it is used unmodified, as an external process:

```sh
gh release download 2.5.1 -R eclipse-che4z/che-che4z-lsp-for-cobol -p 'cobol-language-support-2.5.1.vsix' -D $REF/che4z
unzip -q $REF/che4z/cobol-language-support-2.5.1.vsix -d $REF/che4z/vsix
export CHE4Z_SERVER_JAR=$REF/che4z/vsix/extension/server/jar/server.jar
```

Default mode is LSP (`che4z_adapter.py ... --mode lsp`): one `java -jar server.jar pipeEnabled` per corpus, `didOpen`,
the server's diagnostics (analysis done), then `textDocument/documentSymbol`. The server asks the client to resolve
copybooks (`copybook/resolve`, then `file/content`); the adapter answers from the corpus's copybook dirs. A symbol tree
carries no PERFORM / GO TO edges and no PIC / USAGE / OCCURS / REDEFINES / VALUE clauses, so LSP mode does not produce
those channels (the scorecard shows n/a, not a miss) and reads a data item's level from its source line. A section's
extent ends where its first paragraph starts and trailing blank / comment lines are dropped. Compared with
`--mode cli`, which exits 1 on any program containing a `CALL`, overflows / runs out of memory on large CICS
programs, and serialises OCCURS without DEPENDING ON, LSP mode parses those members. A member that gets no diagnostics
within 120 s (e.g. a pathological estate-crucible program) is a `fail`.

**mapa** (MIT, cschneid-the-elder/mapa; JDK 21). `cobol/CallTree.jar` is committed upstream:

```sh
git clone https://github.com/cschneid-the-elder/mapa $REF/mapa
export MAPA_CALLTREE_JAR=$REF/mapa/cobol/CallTree.jar
```

## Running the panel

```sh
# 1. engine facts: scan with the checkout under test (cached per engine commit), then extract
python tests/tools/mainframe_corpus.py scan <corpus>
python tests/tools/referees/engine_adapter.py --db "$(python tests/tools/mainframe_corpus.py path <corpus> --db)" \
    --corpus <corpus> --key tests/cobol_mainframe/answer_key/<corpus>.json --out $FACTS/<corpus>/engine.json

# 2. each referee, on the same members (the key's programs / keyed copybooks)
for a in cobrix treesitter che4z mapa; do
  python tests/tools/referees/${a}_adapter.py --corpus <corpus> --root "$(python tests/tools/mainframe_corpus.py path <corpus>)" \
      --key tests/cobol_mainframe/answer_key/<corpus>.json --out $FACTS/<corpus>/$a.json
done

# estate-crucible: convert its key once, scan with tests/tools/estate_crucible.py --scan-dir, then as above
python tests/tools/referees/estate_key.py --crucible ../estate-crucible \
    --out $WORK/estate-crucible.answer_key.json --facts $FACTS/estate-crucible/key.json

# 3. the scorecard
python tests/tools/referees/score.py --facts $FACTS --md scorecard.md --json scorecard.json \
    --disagreements disagreements.json
```

## Nightly run

`run_panel.py` is the whole recipe above in one command, for the burned keyed corpora (`estate4_draw.BURNED_NAMES`):

```sh
python tests/tools/referees/run_panel.py                 # results in /tmp/gitgalaxy-scratch/referees/<engine key>/
python tests/tools/referees/run_panel.py --corpus zecs --dry-run   # print the commands, run nothing
```

It writes `scorecard.md`, `scorecard.json`, `disagreements.json` and `run.json` (engine key, referee versions,
step exit codes and seconds, per-source member status counts) under the scratch directory and nowhere else: an
`--out` inside the checkout is refused, and nothing is posted or published (the owner's hold, #4438). It exits 2
before running anything when a referee's variable (`COBRIX_CLASSPATH`, `TS_COBOL_ENTERPRISE_LIB`,
`CHE4Z_SERVER_JAR`, `MAPA_CALLTREE_JAR`) is unset or names a missing file, and 1 after all corpora ran when a
step failed or a referee parsed no member of any corpus. A referee that cannot parse one corpus (tree-sitter on
`dbb-mortgage-application`'s `CBL` cards) or has no members there (Cobrix reads layouts only) is a `notes` entry in
`run.json`, not a failure (first dispatch, #4438). JVM start-up and the 5-minute grammar generation make it a
poor PR gate, so it is meant for a scheduled or manual run, never a `pull_request` trigger.

With two or more referees the scorecard also has an "Engine vs the referee majority" table (#4438): per
channel, the files with a majority, the majority scored against the key, the engine's agreement with the
majority, and the engine-only / majority-only values split by whether the key has them. A value is in the
majority when MORE than half of the voting referees report it (2 of 3; with 2 voters both). A voter is a
referee that produces the channel and parsed the file; a file with fewer than 2 voters is skipped. The
same pairs are sampled under `referee-majority` in `disagreements.json`. Scorecards that name other tools
are not published until the owner's review clears it (see #4438).

`.github/workflows/referee-panel.yml` runs it nightly and on `workflow_dispatch` (no `pull_request` or `push` trigger,
`contents: read`). The upstream refs (Cobrix, tree-sitter-cobol-enterprise and mapa by commit, Che4z by release tag,
the tree-sitter CLI by version) are env values at the top of that file, and the installs are cached under a key
that hashes the file, so bumping a ref reinstalls. The scorecard, JSON, disagreements and `run.json` are uploaded as a
3-day artifact: nothing is published.

`disagreements.json` groups every engine / referee difference by pattern
(`engine-only, in key`, `<referee>-only, not in key`, ...) with a seeded sample of each, for
adjudication against the source: engine wrong, referee wrong, definitional, or key wrong.
