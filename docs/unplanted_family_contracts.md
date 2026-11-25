---
description: "Four unplanted draft contracts of the keyword-family validity epic (#8863 / #8862) declared: dead_code, reflection_metaprogramming, spec_exposure, llm_api -- sentence, measured incidence, contradictions listed."
---
# The `dead_code`, `reflection_metaprogramming`, `spec_exposure` and `llm_api` contracts, declared (#8862)

Part of #8863 (keyword-family validity); the sequel to `docs/resource_family_contracts.md`, which declared
`debug_prints`, `sync_locks` and `concurrency`. These are the last four unplanted `draft` rows. They move to
**`declared`** (#2897): the sentence, `kind` and `unit` are fixed and language-independent; the sentence is contained
verbatim in the `# key:` comment of `gitgalaxy/standards/how_to_add_a_language.md`; incidence was measured on both
corpora; every rule that contradicts the sentence is **listed, not fixed**. No rule is edited, so no corpus cell moves
and nothing is re-blessed. `dead_code` keeps its partial statement-shape note, `docs/dead_code_rule_contract.md`
(#4171), which this sentence does not replace.

## The sentences

| signal | contract |
|---|---|
| `dead_code` | A comment that holds code the program no longer runs -- a keyword-led line or a statement in the language's own syntax inside a comment, as opposed to prose or documentation -- read from the comment surface |
| `reflection_metaprogramming` | A site that inspects or alters a program's own structure at run time -- a reflection or introspection call, a dynamic attribute or member lookup or assignment, or a macro, quote or code-generation form -- in its own call or keyword form |
| `spec_exposure` | A comment tag that ties code to a requirement, specification or audit item -- a bracketed identifier such as [SPEC-123] or an audit marker -- read from the comment surface |
| `llm_api` | A site that binds the program to a hosted LLM provider's SDK -- an import of the provider's client package or a call on its client -- in the language's own import or call form |

`dead_code` and `spec_exposure` are `annotation` rows read from the comment stream (the Prism comment surface);
`reflection_metaprogramming` and `llm_api` are `site` rows read from the code stream.
Two readings this settles (a reading of the existing words; the maintainer can overrule it by editing the sentence):

1. **`llm_api` counts the import as a site.** The rule's own hits are `from openai import` and `import OpenAI from 'openai'`:
   binding to the provider's SDK is the observable form in a static scan, and a call on the client is the second form.
2. **A tokenizer or model-name package is not an LLM API site** (`@anthropic-ai/tokenizer` runs locally and calls no hosted model).

## What was measured

`tests/tools/rule_probe.py <rule> all` over the Prism streams (the text `detector.py` hands the rule). Crucible =
`language-crucible` v1.8.0, rosetta = `keyword-rosetta` main (`2e67433`). 79 language definitions; "defined" counts
those that carry a rule (the rest record `None`, a contract-level absence).

| signal | defined / None | crucible hits | rosetta hits | densest language (hits per file) |
|---|---|---|---|---|
| `dead_code` | 61 / 18 | 747 | 4 | `fortran` 11.0; `scheme` 7.4; `csharp` 3.2 |
| `reflection_metaprogramming` | 58 / 21 | 9801 | 16 | `scheme` 96.4; `agc_assembly` 34.4; `go` 25.0 |
| `spec_exposure` | 61 / 18 | 298 | 5 | `embedded_python` 17.2; `agc_assembly` 3.2; `solidity` 1.7 |
| `llm_api` | 3 / 76 | 12 | 0 | `typescript` 0.1 (python, javascript, typescript only) |

## Contradictions found (listed; the c / go / elixir `spec_exposure` rows are fixed)

| signal | language | what the rule counts | reads the sentence? |
|---|---|---|---|
| `dead_code` | assembly | `// MOV X1,` matched in the code stream (8 of 13 hits) | no: the sentence reads the comment surface |
| `dead_code` | assembly, css | prose comments (`# add NUL terminator (again)`, `/*.run + * {`) | no: prose, not code; listed, not fixed |
| `dead_code` | dockerfile | prose led by an instruction word (`# from the ... repo`, `# Copy the sources`, `#  run one of ...`, `# FROM statement is updated`) | no: prose -- fixed: the keyword is uppercase and takes an operand, `FROM` must end after `image [AS name]`; crucible hits 5 -> 1 (`tests/extraction/languages/test_dockerfile_dead_code_shape_8862.py`) |
| `dead_code` | bms | `*FLDDEAD DFHMDF ...` a map label line | design question: a commented-out macro line, but the label is a name |
| `spec_exposure` | c, go, elixir | `[SPECIAL___ENTER__] = {`, `[Spec=%v, ...]` in a log string, `[spec, return]` a list pattern, all in the code stream | no: not a comment tag -- fixed: the keyword must be a whole word not followed by `,` or `=`; crucible hits 4/1/3 -> 0 (`tests/extraction/test_spec_exposure_code_stream.py`). matlab (`[specdata;[real(tmp) imag(tmp)]]` in `runica.m`, 1 hit) and objective-c (`[spec ...]` is a message send) carry the same guard, crucible matlab 1 -> 0. Every other language carries the same unguarded regex with 0 measured hits (crucible and rosetta): listed, not yet guarded |
| `spec_exposure` | objective-c | `WorldWideWeb` inside a `NXGetDefaultValue("WorldWideWeb", ...)` string (4 code-stream hits) | design question: a deliberate product-name alternation pinned by `test_language_standards_strict.py`, not a tag; left as is |
| `spec_exposure` | agc_assembly | `Colossus` / `Comanche` in a `# Purpose:` line | no: a program name, not a traceability tag |
| `spec_exposure` | embedded_python | `[Spec 10.9.4]` section citations in prose (241 hits) | partly: a bracketed spec reference, but a citation of a document, not a tag on code |
| `reflection_metaprogramming` | c, cobol, db2_sql | `goto`, `EXEC SQL` / `EXEC CICS`, `GET DIAGNOSTICS` | no: control flow and embedded-SQL statements, not self-inspection |
| `reflection_metaprogramming` | cpp, css, dart, dockerfile | `sizeof...` (a compile-time pack size), `calc(`, the word `reflect` in a string, `--mount=type=cache` | no |
| `reflection_metaprogramming` | csharp, java, rust | `using ...Emit;` (a namespace import), a `ClassLoader` type name, `PhantomData` | no: a type or import, not a call that inspects or alters structure |
| `reflection_metaprogramming` | python | `@property` / `@classmethod` (322 hits), a decorator (`decorators`) | no |
| `reflection_metaprogramming` | agc_assembly | `INDEX` (an address-modifier instruction) | design question: indirect addressing, not self-inspection |
| `llm_api` | javascript, typescript | `@anthropic-ai/tokenizer` import | no: reading 2 -- fixed: `JS_LLM_API` excludes that exact package name (`@anthropic-ai/sdk` and every other scope member still fire); `tests/extraction/languages/test_llm_api_anchor_4137.py` |
| `llm_api` | 76 languages | rule is `None` | stated absence, listed below: no rule is written until a language's provider-client import form is measured on a corpus |

### `llm_api` stated absences (#8862)

The rule is `None` (a stated absence, not a missed rule) for every language other than python, javascript and
typescript; `test_every_llm_api_language_uses_an_anchored_pattern` pins that set. Languages with a published
provider client, where a rule is a candidate once a corpus carries a positive: java, kotlin, go, csharp, ruby, php,
rust, swift, dart, scala, elixir. Everything else (assembly and mainframe languages, markup, config, shell, query
languages) has no hosted-LLM client form, so the absence is by morphology. The crucible holds no positive in any
candidate language (12 hits, all python, javascript, typescript), so a rule written now would be unmeasured.

`tests/family_validity_baseline.json` carries parser-oracle scores only for families with an oracle; none exists for
these four (`dead_code` and `spec_exposure` have no parser oracle: they need planted positives and negatives).

## What this does not do

- It edits no rule and writes no ledger entry; each contradiction above is a one-layer rule fix that can land with its
  own timing.
- It does not touch the five planted drafts (`safety_bypasses`, `doc`, `telemetry`, `planned_debt`, `fragile_debt`),
  which need the full family audit.

## Reproducing the measurement

```sh
export LANGUAGE_CRUCIBLE_PATH=<clean language-crucible v1.8.0> KEYWORD_ROSETTA_PATH=<keyword-rosetta main>
for r in dead_code reflection_metaprogramming spec_exposure llm_api; do
  python tests/tools/rule_probe.py $r all --samples 2 --json /tmp/$r.json
done
```
