# COBOL to Java: from verified facts to a proven port

This directory turns a mainframe estate into a Spring Boot project and carries each program's
business logic across with proof. It does not translate COBOL line by line, and it does not ask
a model to rewrite a program unchecked. The structure is generated from facts the engine
verified. The business logic is ported per program, by a person or a model the customer chooses.
Every port is proven byte for byte against the original COBOL before a person approves it.

The extraction tools this builds on (dead-code finder, data lineage, schema and JCL generation,
the GalaxyIR fact store) live in [`../cobol_to_cobol/`](../cobol_to_cobol/README.md). What has
been proven so far, with its limits, is in the root README's
[COBOL to Java](../../../README.md#cobol-to-java-ported-then-proven) section.

## The pipeline

```sh
cobol-refractor <estate> --scan                    # 1. facts: a staging dir with the verified skeleton
cobol-to-java <staging dir> [--config t.yaml]      # 2. the Spring Boot project, worklist and porting tickets
python -m gitgalaxy.tools.cobol_to_java.port_runner run <project> --ticket CBACT04C --backend ...   # 3. port
python -m gitgalaxy.tools.cobol_to_java.port_runner prove <project> --ticket CBACT04C ...          # 4. prove
python -m gitgalaxy.tools.cobol_to_java.port_runner review <project> --ticket CBACT04C ...         # 5. a person decides
```

1. **Facts.** `cobol-refractor` stages the estate and records what the engine verified per
   program: record layouts (copybooks, REDEFINES, OCCURS), datasets and JCL steps, CICS commands
   and COMMAREAs, CALL / LINK / XCTL targets, DB2 tables, BMS maps.
2. **Skeleton.** `cobol-to-java` builds the project from those facts, one forge per kind of fact
   (below). Where a fact is missing, or two facts disagree, it writes an item in the migration
   worklist (`migration_worklist.md`). It never guesses. Each program that still has business
   logic to write gets a porting ticket (`ai_agent_jobs/<PROGRAM>_port_ticket.md`): the COBOL,
   the generated classes it must use, and the porting rules.
3. **Port.** `port_runner run` sends a ticket to a backend: a hosted, self-hosted or air-gapped
   model, or any command. `submit` records a port a person wrote. A guardrail
   ([`cobol_to_java_guardrail.py`](cobol_to_java_guardrail.py)) checks the port against the
   generated project's inventory. It flags any call to a service or repository the COBOL never
   reached, a new component or endpoint, a record field outside the verified layout, or SQL on
   an unknown table.
4. **Prove.** `port_runner prove` runs the equivalence harness
   ([`tests/tools/equivalence.py`](../../../tests/tools/equivalence.py)): the COBOL under
   GnuCOBOL and the port on the JVM, with the same inputs. What must be equal, per case kind:
   - **batch**: every output record, field by field; the return code or abend; every DISPLAY line
     (SYSOUT, written as IBM COBOL writes it);
   - **CICS**: every task event in order: each SEND MAP (the screen's text, attributes,
     colour, highlight, cursor and options), SEND TEXT, RECEIVE MAP, the RETURN or XCTL with its
     COMMAREA, and an abend;
   - **CALL**: every USING item after each call, and the return code.

   Every case also runs fault plans: file statuses or CICS responses injected on both sides at
   the same statement, which must end the same way. A failed proof's findings become the next
   attempt's feedback: [the porting loop](../../../docs/language_status/porting_loop.md).
5. **Review.** A person approves or rejects each port. No tool marks a port approved.

How strong a proof is gets measured too: the COBOL's paragraph and branch coverage across the
runs (`tests/tools/cobol_coverage.py`), and
[mutation testing](../../../docs/language_status/mutation_testing.md): how many deliberately
broken ports the proof still catches.

## The forges

| module | generates from the facts |
|---|---|
| [`cobol_to_java_spring_forge.py`](cobol_to_java_spring_forge.py) | JPA entities and DTOs from record layouts |
| [`cobol_to_java_repository_forge.py`](cobol_to_java_repository_forge.py) | Spring Data repositories for VSAM files |
| [`cobol_to_java_db2_forge.py`](cobol_to_java_db2_forge.py) | JDBC repositories for embedded DB2 |
| [`cobol_to_java_batch_forge.py`](cobol_to_java_batch_forge.py) | Spring Batch jobs from JCL, and the batch runtime: `CobolFiles` (FILE STATUS per I/O statement), `CobolAbend`, `Sysout` (DISPLAY) |
| [`cobol_to_java_transaction_forge.py`](cobol_to_java_transaction_forge.py) | REST endpoints for CICS transactions, and `CicsTask`: a task's commands as calls |
| [`cobol_to_java_screen_forge.py`](cobol_to_java_screen_forge.py) | BMS maps as view models and web views |
| [`cobol_to_java_call_forge.py`](cobol_to_java_call_forge.py) | CALL / LINK / XCTL as service-to-service calls (`CobolRef` for BY REFERENCE) |
| [`cobol_to_java_messaging_forge.py`](cobol_to_java_messaging_forge.py) | TS / TD queues and IBM MQ as messaging ports |
| [`cobol_to_java_uow_forge.py`](cobol_to_java_uow_forge.py) | units of work as `@Transactional`, handlers as exception mapping |
| [`cobol_to_java_compare_forge.py`](cobol_to_java_compare_forge.py) | `CobolCompare`: alphanumeric comparison in the program's collating sequence |
| [`cobol_to_java_decoder_forge.py`](cobol_to_java_decoder_forge.py) | the EBCDIC, zoned and COMP-3 decoder utility (record fields themselves go through the generated `CobolRecords`) |
| [`cobol_to_java_service_forge.py`](cobol_to_java_service_forge.py), [`cobol_to_java_api_contract_forge.py`](cobol_to_java_api_contract_forge.py) | service classes (the port's home) and API contracts |
| [`cobol_to_java_build_forge.py`](cobol_to_java_build_forge.py), [`cobol_to_java_test_forge.py`](cobol_to_java_test_forge.py) | the Maven / Gradle build and the generated tests |
| [`cobol_to_java_skeleton_forges.py`](cobol_to_java_skeleton_forges.py), [`cobol_to_java_common.py`](cobol_to_java_common.py) | the skeleton-driven forges as one pipeline, and their shared pieces |
| [`cobol_to_java_worklist.py`](cobol_to_java_worklist.py) | the migration worklist: every fact the generators refused to guess |
| [`cobol_to_java_port_tickets.py`](cobol_to_java_port_tickets.py) | the porting tickets and their rules |
| [`port_runner.py`](port_runner.py), [`cobol_to_java_guardrail.py`](cobol_to_java_guardrail.py) | the porting loop's runner (run / submit / prove / review / status) and the guardrail |
| [`java_target.py`](java_target.py) | the target config (below) |

The generated skeleton alone is not a port. On the
[CICS crucible](../../../docs/language_status/cics_crucible.md) it compiles for all 10 cases, but
its generated services pass 0 of 44 scenarios. The ported ones pass 44 of 44.

## Choosing the Java you get: the target config

`cobol-to-java` writes Java 17 / Spring Boot 3.2.4 / Maven / PostgreSQL / Lombok by default. A
YAML (or JSON) config picks something else. GitGalaxy reads it with its own YAML reader, so
PyYAML is not needed:

```sh
cobol-to-java --init-config modernize.yaml          # an annotated file with every option and its default
cobol-to-java <staging dir> --config modernize.yaml
```

| section | options |
|---|---|
| `project` | `package`, `group_id`, `artifact_id`, `version`, `description`, `header_file` |
| `java` | `version` (17, 21), `build_tool` (maven, gradle), `data_classes` (lombok, plain), `dto_style` (class, record) |
| `spring_boot` | `version` (any 3.x.y) |
| `database` | `engine` (postgresql, db2, oracle, mysql, h2), `ddl_auto`, `username`, `show_sql` (no password: set `SPRING_DATASOURCE_PASSWORD` at runtime) |
| `features` | `rest_controllers`, `services`, `batch`, `ebcdic_decoder`, `mock_services`, `agent_tickets` |

Every key is validated. An unknown key or an unsupported value stops the run with an error naming
it. Explicit `--pkg` / `--header` flags override the file. Without `--config` the output is
unchanged. Every supported combination is compile-checked by `tests/tools/java_target_matrix.py`,
which generates CardDemo under 17 configs and runs the real Maven / Gradle build.

## Limits

- **The oracle is GnuCOBOL,** with a stub CICS runtime (`tests/equivalence/cics/ggcics.c`) and IBM
  Language Environment services modelled only where IBM documents them
  (`tests/equivalence/le/`). An undocumented case is refused, not guessed. Captured mainframe
  output as the oracle is [#4050](https://github.com/squid-protocol/gitgalaxy/issues/4050).
- **Data runs as ASCII pages** under GnuCOBOL. An EBCDIC data page cannot be run (#3815).
- **"Proven" means proven on the case's runs.** Read it with the coverage and mutation numbers,
  never alone.
- **A person approves every port.**
