---
description: "Translating legacy COBOL logic into modern Java syntax solves only a fraction of the mainframe modernization challenge. An isolated `.java` file..."
---
# Cookbook: Spring Boot Build System Forge via Deterministic RAG Pipelines

## 1. The Compilation Crisis in Legacy Modernization

Translating legacy COBOL logic into modern Java syntax solves only a fraction of the mainframe modernization challenge. An isolated `.java` file containing translated business logic is not a microservice; it is merely a text file. To function in a cloud-native environment, that logic requires a rigorous compilation lifecycle, explicit dependency management, and declarative environment configuration.

When relying exclusively on Large Language Models (LLMs) to perform codebase translations, the orchestration of the project structure frequently collapses. LLMs excel at translating single-file procedural logic but struggle to generate the distributed, multi-file scaffolding required by modern build systems like Maven or Gradle. They frequently hallucinate incompatible library versions or omit critical database drivers, resulting in output that requires days of manual dependency resolution before it can even be compiled.

The GitGalaxy ecosystem resolves this via deterministic scaffolding. Because the knowledge graph has already recorded the physical boundaries of the legacy application (e.g., identifying batch vs. transactional intent, mapping physical datasets to database tables), the Spring Boot Build System Forge can deterministically generate a compilation-ready project structure, so the translated Java classes land inside a microservice scaffolding that builds. A build that compiles is not a port that behaves like the COBOL; that is checked per program by the equivalence harness.

## 2. The Java Spring Build System Forge

The `cobol_to_java_build_forge.py` script acts as the structural foundation layer within the GitGalaxy modernization pipeline. 

Instead of asking an LLM to guess the required Spring Boot starters, this Forge deterministically generates the `pom.xml`, `application.yml`, and `@SpringBootApplication` main class based on the architectural intent previously extracted from the COBOL environment. It bridges the gap between raw translated code and a deployable container.

### 2.1 Information Flow & Processing Pipeline

The pipeline executes a deterministic generation of the build and configuration artifacts required to bootstrap a modern Java application.

| Processing Stage | Deterministic Artifact | Architectural Purpose | Legacy Modernization Value |
| :--- | :--- | :--- | :--- |
| **Dependency Orchestration** | `pom.xml` | Defines the Maven build lifecycle, pinning the Java (17 or 21) and Spring Boot versions from the target config, with Maven or Gradle, and the libraries the project needs (Web, JPA, Batch, the configured database driver). | Eliminates dependency hell and hallucinated libraries, ensuring the translated logic immediately compiles against enterprise-standard frameworks. |
| **Environment Configuration** | `application.yml` | Maps database connection strings, configures the Hibernate dialect, and sets Tomcat server ports. | Prevents local development friction by providing an instantly runnable configuration matched to the previously forged PostgreSQL DDLs. |
| **Batch Safeguarding** | `spring.batch.job.enabled` | Injects configuration constraints specifically for batch-oriented legacy workloads. | Prevents Spring Batch from automatically executing legacy data pipelines upon application startup, ensuring controlled, scheduled invocations. |
| **Application Bootstrapping** | `Main.java` | Generates the standard Java entry point decorated with `@SpringBootApplication`. | Provides the necessary Inversion of Control (IoC) container initialization to launch the embedded application server. |

## 3. Notable Structures & Execution Logic

The script operates on three primary structural generators that collectively assemble the microservice environment:

### Dependency Architecture (generate_pom_xml)
This function serves as the package manager forge. It defines a strict inheritance model using `spring-boot-starter-parent` to ensure all transitive dependencies remain compatible. It explicitly includes `spring-boot-starter-batch` to support the sequential processing paradigms native to mainframe JCL operations. Additionally, it injects `lombok` to minimize the boilerplate required in the generated Data Transfer Objects (DTOs) and Entities, significantly reducing the token footprint required when an LLM later populates the domain layer.

### State Configuration (generate_application_yml)
This function establishes the runtime state of the application. The datasource, driver and Hibernate dialect follow the target config's `database.engine` (postgresql, the default, db2, oracle, mysql or h2; `cobol-to-java --config`), and with `ddl-auto: update` it structurally links the application to the schemas generated by the `cobol_schema_forge.py` spoke. So when the Spring Boot application initializes, the Object-Relational Mapping (ORM) layer is configured for the target database the config names.

## 4. Execution Interface

The forge has no command of its own (the module has no `__main__`). The `cobol-to-java` pipeline (`gitgalaxy/cobol_to_java_controller.py`) calls it to write the build file (`pom.xml`, or `build.gradle` and `settings.gradle` when the target config picks Gradle), `application.yml` and the main class; see "The forges" in the [`cobol-to-java` README](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/tools/cobol_to_java/README.md#the-forges):

```bash
cobol-to-java /path/to/legacy_repo_gitgalaxy_clean_20260419 --pkg "com.enterprise.modernized" [--config target.yaml]
```

Its functions can also be called directly from Python, for example to scaffold an empty service repository:

```python
from gitgalaxy.tools.cobol_to_java.cobol_to_java_build_forge import generate_pom_xml, generate_application_yml, generate_main_class

artifact_id = "gl-post-service"
group_id = "com.enterprise.modernized"
package_name = "com.enterprise.modernized.glpost"

pom_content = generate_pom_xml(group_id, artifact_id)
yml_content = generate_application_yml(artifact_id)
main_class_content = generate_main_class(package_name, "GlPost")

# Write artifacts to the target repository workspace
```

## 5. Recommended Next Steps (Refactoring for Enterprise Scale)

To mature this script into a comprehensive enterprise platform engineering tool, the following architectural enhancements should be prioritized:

1. **Containerization Scaffolding:** Extend the forge to generate a multi-stage `Dockerfile` and a corresponding `docker-compose.yml`. This allows the newly translated microservice and its required PostgreSQL database to be spun up locally with a single command for immediate validation testing.
2. **Dynamic Dependency Resolution:** Abstract the hardcoded Maven dependencies into a configurable JSON map. This allows the Forge to dynamically inject dependencies based on the exact intent of the COBOL program (e.g., only injecting `spring-boot-starter-batch` if the GitGalaxy graph confirms the legacy program relies on physical flat files).
3. **CI/CD Pipeline Generation:** Automate the creation of `.github/workflows/build.yml` or `Jenkinsfile` artifacts. The Forge should output the exact pipeline definitions required to compile, test, and deploy the new microservice into the organization's target cloud environment.

- - - -
this was accomplished by the blAST engine - - - -🌌 Powered by the blAST Engine
## Where the business logic comes from

This forge generates the build and configuration files. Each program's PROCEDURE DIVISION is then ported in one of two ways: by the deterministic translator (no model; every statement becomes a call into a runtime that follows COBOL's rules byte for byte, and anything it cannot translate is a named `Hole`), or by a person or model from a porting ticket. Either way, the port is checked against the original COBOL by the equivalence harness (GnuCOBOL, GitGalaxy's CICS models and a real Db2; not z/OS) and reported by [evidence level](https://github.com/squid-protocol/gitgalaxy/blob/main/docs/language_status/definition_of_done.md), from L1 (translated whole) to L5 (surviving mutants accounted for), before a person approves it. A forge's output compiling says nothing about equivalence. Current counts are on the generated [progress page](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/progress.md). See [Ported COBOL-to-Java programs and their evidence](../05-19-proven-cobol-to-java-ports.md) for how ports are checked, and the limits.

This documentation is part of the GitGalaxy Ecosystem, an AST-free, LLM-free heuristic knowledge graph engine.

🪐 Explore the GitHub Repository for code, tools, and updates.
🔭 Visualize your own repository at GitGalaxy.io using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](../index.md)**
