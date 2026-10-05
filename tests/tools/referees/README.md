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
| `che4z_adapter.py` | Eclipse Che4z COBOL LSP's headless `analysis` CLI: units, extents, edges, COPY, data items |
| `mapa_adapter.py` | mapa's CallTree: PROGRAM-IDs, COPY / INCLUDE, CALL / LINK / XCTL targets, DB2 tables, CICS file commands |
| `translator_adapter.py` | the det COBOL-to-Java translator's own parse (not a referee: the engine's sibling inside GitGalaxy), for the engine-vs-translator cross-check `tests/tools/fact_crosscheck.py` (#4273) |
| `estate_key.py` | estate-crucible's generated key (#4317) in the answer-key shape, so every adapter runs on it unchanged |
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

Known limits of 2.5.1's `analysis` CLI (see the scorecard): it prints no result and exits 1 on any
program containing a `CALL` statement, its `--ast` JSON writer overflows / runs out of memory on
large CICS programs, and its serialised OCCURS clause carries no DEPENDING ON. Driving the server
over LSP (`textDocument/documentSymbol`) would avoid all three; that is #4377's next phase.

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

`disagreements.json` groups every engine / referee difference by pattern
(`engine-only, in key`, `<referee>-only, not in key`, ...) with a seeded sample of each, for
adjudication against the source: engine wrong, referee wrong, definitional, or key wrong.
