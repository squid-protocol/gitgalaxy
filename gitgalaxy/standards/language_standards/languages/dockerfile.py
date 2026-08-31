# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

import re
from typing import Any

from .._shared_patterns import GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "Dockerfile (BuildKit)",
        "last_updated": "2026-02-27",
        "blueprint_version": "",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard extensions for container definitions across Docker and Podman ecosystems.
    "extensions": [".dockerfile", ".containerfile"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: The universally recognized, extensionless architectural anchors of containerized environments.
    "exact_matches": [
        "Dockerfile",
        "Containerfile",
        "Dockerfile.prod",
        "Dockerfile.dev",
        "Dockerfile.build",
        "Dockerfile.test",
        "Dockerfile.local",
    ],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Compose files and ignore manifests acting as contextual baselines.
    "discriminators": [
        "docker-compose.yml",
        "docker-compose.yaml",
        ".dockerignore",
        "compose.yaml",
    ],
    # EXECUTION SIGNATURES: Docker natively uses BuildKit syntax directives instead of traditional shebangs.
    "shebangs": [],
    # UPGRADED: Maps to Family 3 (Pure Hash)
    # Rationale: Docker natively uses '#' exclusively for line-level comments and parser directives.
    "lexical_family": "line_exclusive",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Control flow executing inside RUN shell blocks. High density indicates complex embedded shell scripts.
        "branch": re.compile(
            r"\b(?:if|elif|else|fi|case|esac|for|while|do|done|until)\b|&&|\|\|",
            re.I,
        ),
        # 2. args (Parameters / Coupling)
        # Build arguments (`ARG`) passed into the container acting as input parameters to the satellite.
        "args": re.compile(r"^[ \t]*ARG(?:[ \t]|\\[ \t]*\r?\n)+[a-zA-Z0-9_-]+", re.M | re.I),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries defining straight-line execution and environment contexts.
        # CRITICAL GUARDRAIL: EXCLUDES `FROM` and `RUN`/`CMD` to maintain geometric stability.
        "structural_boundaries": re.compile(r"^[ \t]*(?:WORKDIR|USER|VOLUME|STOPSIGNAL|SHELL|LABEL)\b", re.M | re.I),
        # 4. func_start (Executable Logic Anchors)
        # CRITICAL GUARDRAIL: Anchors logic blocks. ONLY executable logic blocks.
        # In Docker, `RUN`, `CMD`, and `ENTRYPOINT` execute logic, generating discrete intermediate image layers.
        "func_start": re.compile(
            r"^[ \t]*(RUN|CMD|ENTRYPOINT|HEALTHCHECK)(?=[ \t\[]|\\[ \t]*(?:\r?\n|$))", re.M | re.I
        ),
        # 5. class_start (Object / Entity Declarations)
        # Defines object-oriented and structural boundaries. Drives API Surface Area math.
        # `FROM` instantiates a discrete build stage/image boundary, acting as a class wrapper.
        # Real Dockerfile syntax: `FROM <image>[:<tag>|@<digest>] [AS <stage-name>]`
        # Extending the regex to capture the stage alias (group 1) if `AS` is present, or fallback
        # to the base image reference (group 2) for bare forms (`FROM x`).
        # Flags like `--platform=$VAR` are skipped over (between FROM and image reference).
        # CRITICAL GUARDRAIL: Restricts character lengths for tokens using char-count bounds
        # like `[^\s\\]{1,300}` (Rule 5) to prevent catastrophic backtracking on long inputs without delimiters.
        "class_start": re.compile(
            r"^[ \t]*FROM(?:(?:[ \t]|\\[ \t]*(?:\r?\n))+--[^\s\\]{1,100}){0,5}(?:(?:[ \t]|\\[ \t]*(?:\r?\n))+)(?:[^\s\\]{1,300}(?:(?:[ \t]|\\[ \t]*(?:\r?\n))+)AS(?:(?:[ \t]|\\[ \t]*(?:\r?\n))+)([a-zA-Z0-9_-]{1,100})|([^\s\\]{1,300}))(?=[ \t]*(?:#|\\[ \t]*(?:\r?\n|$)|\r?\n|$))",
            re.M | re.I,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming)
        # Hardening the container. Dropping root privileges (`USER nonroot`), explicit `HEALTHCHECK`,
        # setting explicit shell crash flags (`set -e`), and safe file ownership (`--chown`).
        "safety": re.compile(
            r"^[ \t]*HEALTHCHECK\b|--chown=|^[ \t]*USER[ \t]+(?!root\b|0\b)[a-zA-Z0-9_-]+|\bset[ \t]+-[exuo]\b",
            re.M | re.I,
        ),
        # 7. safety_neg (Safety Bypasses)
        # Actively bypassing isolation or safety logic.
        # Using `:latest`, running as root, setting permissions to 777, or blindly curling directly into bash.
        # CRITICAL GUARDRAIL: Safely bounds the curl/wget pipe `[^|\n]{1,200}` to prevent ReDoS on massive RUN chains.
        "safety_bypasses": re.compile(
            r":latest\b|^[ \t]*USER[ \t]+(?:root|0)\b|chmod[ \t]+777|--privileged|--allow-unauthenticated|\b(?:curl|wget)[ \t]+[^|\n]{1,200}\|[ \t]*(?:bash|sh|zsh)\b",
            re.M | re.I,
        ),
        # 8. danger (High-Risk Execution)
        # Extreme space debris. Destructive recursive removes targeting root, and dangerous dynamic eval.
        # CRITICAL GUARDRAIL: Raw terminal prints (`echo`) strictly routed to print_hits.
        # CRITICAL GUARDRAIL (Rule 9): the `rm -rf /` alternative ends on the symbolic
        # `/` character. A shared trailing `\b` wrapped around the whole group can only
        # fire when a word char follows -- but the realistic real-world form is `rm -rf /`
        # followed by nothing (end of instruction), whitespace, or `&&`, none of which are
        # word chars, so the old pattern could never match the single most catastrophic
        # command a Dockerfile could contain. Pulled out of the shared group, same as the
        # Rule 9 playbook's canonical fix.
        "high_risk_execution": re.compile(r"\brm[ \t]+-rf[ \t]+/(?![A-Za-z])|\beval\b|\bexec\b", re.M | re.I),
        # 9. io (I/O & Network Boundaries)
        # Interaction with external networks, copying files from host, or executing package managers.
        "io": re.compile(
            r"^[ \t]*(?:COPY|ADD)[ \t]+|\b(?:wget|curl|apt-get|apk|yum|dnf|git[ \t]+clone|tar[ \t]+-[cx]f|unzip|pip[ \t]+install|npm[ \t]+install)\b",
            re.M | re.I,
        ),
        # 10. api (Public Surface Area)
        # Code exposed to the outside world. Ports explicitly exposed to the host network (`EXPOSE`).
        "api": re.compile(r"^[ \t]*EXPOSE[ \t]+[0-9]+", re.M | re.I),
        # 11. flux (State Mutation)
        # Mutation of state. Setting Environment variables that permanently alter the image layer state.
        "state_mutation": re.compile(
            r"^[ \t]*ENV[ \t]+[a-zA-Z0-9_]+|export[ \t]+[a-zA-Z0-9_]+[ \t]*=",
            re.M | re.I,
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        # Commented-out logic, commented-out structural Dockerfile commands.
        "dead_code": re.compile(
            r"^[ \t]*#[ \t]*(?:RUN|COPY|ADD|ENV|EXPOSE|FROM|CMD|ENTRYPOINT|WORKDIR)\b",
            re.M | re.I,
        ),
        # 13. doc (Structured Documentation)
        # Intent documentation meant for developers or image registries.
        "doc": re.compile(
            r"^[ \t]*LABEL[ \t]+(?:maintainer|org\.opencontainers|version|description)=|^[ \t]*#[ \t]*(?:Description|Usage|Author|Maintainer):",
            re.M | re.I,
        ),
        # 14. test (Testing & Assertions)
        # Explicit test runner executions inside the build layer (often used in CI multi-stage pipelines).
        "test": re.compile(
            r"\b(?:npm[ \t]+test|yarn[ \t]+test|pytest|go[ \t]+test|cargo[ \t]+test|make[ \t]+test)\b",
            re.M | re.I,
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        # Parallelism executed inside the build shell (e.g. compiling with all cores).
        # CRITICAL GUARDRAIL (Rule 9/10 variant): `make -j`/`xargs -P` end on a word char
        # (`j`/`P`) that is very commonly followed directly by a digit in real usage
        # (`make -j4`, `xargs -P4`) -- a shared trailing `\b` around the whole group can't
        # fire between two adjacent word chars, so the old pattern missed the compact
        # numeric-suffix form entirely (only the spaced-out `make -j 4` form worked).
        # Pulled these two out of the shared trailing-`\b` group; `nohup`/`parallel` keep
        # it since they legitimately end on whitespace/EOL in real usage.
        "concurrency": re.compile(r"&[ \t]*$|\b(?:nohup|parallel)\b|make[ \t]+-j|xargs[ \t]+-P", re.M),
        # 16. ui_framework (UI / View Components)
        # Containerizing GUI applications (X11, Wayland, GTK).
        # CRITICAL GUARDRAIL: real Debian/Ubuntu package names for these libraries are
        # almost always `lib`-prefixed (`libgtk-3-dev`, `libx11-6`, `libwayland-client0`)
        # -- both "lib" and the tag itself are word characters, so the old pattern's
        # leading `\b` could never fire inside the "lib...gtk"/"lib...x11" substring,
        # meaning it silently missed the dominant real-world package-name form entirely.
        "ui_framework": re.compile(r"\b(?:lib)?(?:xvfb|x11|wayland|gtk2?|qt5?)\b|libgl1-mesa", re.I),
        # 17. closures (Closures / Anonymous Functions)
        # Dockerfiles are purely declarative structurally; closures do not exist.
        "closures": None,
        # 18. globals (Global / Shared State)
        # Global environment variables mapping structurally.
        "globals": re.compile(r"^[ \t]*ENV[ \t]+[a-zA-Z0-9_]+", re.M | re.I),
        # 19. decorators (Decorators / Annotations)
        # Not natively applicable to Dockerfile architecture.
        "decorators": None,
        # 20. generics (Generics / Type Parameters)
        "generics": None,
        # 21. comprehensions (Iterators / Comprehensions)
        "comprehensions": None,
        # 22. scientific (Numerical / Compute Libraries)
        # Installing data science, ML base dependencies, or GPU drivers natively into the image.
        "scientific": re.compile(
            r"\b(?:nvidia/cuda|pytorch/pytorch|tensorflow/tensorflow|jupyter/)\b",
            re.I,
        ),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # High Cognitive Load: Advanced BuildKit logic. Mounting caches, secrets, cross-platform builds, or `ONBUILD` (which defers execution to downstream images).
        "reflection_metaprogramming": re.compile(
            r"^[ \t]*ONBUILD\b|--mount=type=(?:cache|secret|bind|ssh)|--platform=|<<EOF",
            re.M | re.I,
        ),
        # 24. import (Dependency Inclusions)
        # Base images or dependencies pulled from other build stages (`COPY --from=`).
        "import": re.compile(
            r"^[ \t]*(?:FROM(?:\s+(?:\\\s+)*)(?:--[\w-]+=[^\s]+(?:\s+(?:\\\s+)*))*[a-zA-Z0-9_./:-]+|COPY(?:\s+(?:\\\s+)*)(?:--[\w-]+(?:=[^\s]+)?(?:\s+(?:\\\s+)*))*--from=[a-zA-Z0-9_./:-]+)",
            re.M | re.I,
        ),
        "_dependency_capture": re.compile(
            r"^[ \t]*(?:FROM(?:\s+(?:\\\s+)*)(?:--[\w-]+=[^\s]+(?:\s+(?:\\\s+)*))*([a-zA-Z0-9_./:-]+)|COPY(?:\s+(?:\\\s+)*)(?:--[\w-]+(?:=[^\s]+)?(?:\s+(?:\\\s+)*))*--from=([a-zA-Z0-9_./:-]+))",
            re.M | re.I,
        ),
        # 25. ownership (Authorship Metadata)
        # Standard metadata tracing image ownership (legacy MAINTAINER or modern LABEL).
        "ownership": re.compile(
            r"^[ \t]*(?:MAINTAINER|LABEL[ \t]+maintainer=|LABEL[ \t]+org\.opencontainers\.image\.authors=)[ \t]*(.*)",
            re.M | re.I,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure (Spec / Audit Traceability)
        # BUG FIX (Rule 14, #713): adjacent unbounded quantifiers with
        # overlapping character sets (`\d+` next to `[^\]]*`) -- the
        # same ReDoS shape already found and fixed independently in
        # embedded_python, css, tcl, matlab, scheme, typescript, rust, c,
        # cpp, csharp, groovy, shell, and sqlite earlier in this epic.
        # Bounded both quantifiers.
        "spec_exposure": re.compile(
            r"\[(?:[ \t]*SPEC[ \t]*-[ \t]*\d{1,10}|spec|audit|CVE-\d{4}-\d+)[^\]]{0,300}\]",
            re.I,
        ),
        # 31. ssr_boundaries (Server-Side Rendering)
        "ssr_boundaries": None,
        # 32. events (Event Emitters / Pub-Sub)
        # Container lifecycle events explicitly bound to the host OS.
        "events": re.compile(r"^[ \t]*STOPSIGNAL[ \t]+", re.M | re.I),
        # 33. dependency_injection (Dependency Injection / IoC)
        # BuildKit secret and SSH mounts injecting external state at compile time securely.
        "dependency_injection": re.compile(r"--mount=type=(?:secret|ssh)", re.I),
        # 34. macros (Preprocessor Directives / Macros)
        # Docker BuildKit `# syntax=` directives which change the parser dynamically at compile-time (just like C-macros).
        "macros": re.compile(r"^[ \t]*#[ \t]*(?:syntax|escape)[ \t]*=", re.M | re.I),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        "pointers": None,
        # 36. memory_alloc (Manual Memory Management)
        # Explicit memory limits defined in ENV vars that configure Java/Node runtime heaps natively.
        "memory_alloc": re.compile(
            r"\b(?:--memory=|JAVA_OPTS|JAVA_TOOL_OPTIONS|NODE_OPTIONS|--max-old-space-size|-Xmx|-Xms)\b",
            re.I,
        ),
        # 37. inline_asm (The Bare Metal)
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        # Forcing specific logging outputs at the container level or symlinking to stdout for daemon parsing.
        "telemetry": re.compile(
            r"\b(?:LOG_LEVEL|--log-level[ \t]+(?:debug|info|warn|error)|ln[ \t]+-sf[ \t]+/dev/stdout)\b",
            re.I,
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        # Shell echos used for ad-hoc debugging in the build output log.
        "debug_prints": re.compile(r"\b(?:echo|printf)\b", re.I),
        # # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": None,
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        # Hard execution aborts forcing the build to fail dynamically.
        "panics_and_aborts": re.compile(r"\b(?:exit[ \t]+[1-9]|kill[ \t]+-[0-9]+)\b", re.I),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        # Forcing the build thread to sleep (often a hack to wait for a daemon/network).
        "thread_sleeps": re.compile(r"\bsleep[ \t]+[0-9]+\b", re.I),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": None,
        # 44. sync_locks (Resource Management & Stability)
        # Utilizing file locking to prevent parallel build collisions.
        "sync_locks": re.compile(r"\bflock\b", re.I),
        # 45. immutability_locks (Immutability Constraints)
        # Pinning dependencies to immutable SHAs rather than mutable tags. .
        # CRITICAL GUARDRAIL: real Docker/OCI digest references are ALWAYS written as
        # `@sha256:<64 hex chars>` -- the algorithm prefix is mandatory syntax, never a
        # bare `@<64 hex chars>`. The old pattern required the bare (invalid) form and
        # so could never match a real pinned image reference at all.
        "immutability_locks": re.compile(r"@sha256:[a-f0-9]{64}\b|--read-only|:ro\b", re.I),
        # 46. cleanup (Resource Cleanup / Teardown)
        # Explicitly purging apt/apk caches to reduce final container bloat. .
        "cleanup": re.compile(
            r"\b(?:apt-get[ \t]+clean|rm[ \t]+-rf[ \t]+/var/lib/apt/lists|apk[ \t]+(?:cache[ \t]+)?clean|yum[ \t]+clean[ \t]+all|npm[ \t]+cache[ \t]+clean)\b",
            re.I,
        ),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # Explicitly encapsulating logic in multi-stage builds (`AS builder`). Hides intermediate build layers.
        "encapsulation": re.compile(r"^[ \t]*FROM[ \t]+[^\n]+[ \t]+AS[ \t]+[a-zA-Z0-9_-]+", re.M | re.I),
        # 48. listeners (Event Listeners / Observers)
        # Exposing ports for network consumption. .
        "listeners": re.compile(r"^[ \t]*EXPOSE[ \t]+[0-9]+", re.M | re.I),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        # Bypassing package manager tests/audits or using logical OR to ignore failures (`|| true`).
        "test_skip": re.compile(
            r"\|\|[ \t]*true\b|\b(?:--passWithNoTests|skipTests|Dmaven\.test\.skip=true|--no-audit)\b",
            re.I,
        ),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Dockerfile Specifics) ---
        # CRITICAL GUARDRAIL: all four sensors below MUST carry re.M -- `(?i)` alone
        # anchors `^` to the true start of the whole code_stream string (Python re
        # default), not the start of each line, which silently broke every one of
        # these on any real Dockerfile (FROM is always the literal first line, so
        # e.g. ipc_rpc_bridges could never fire at all). The body-scanning sensors
        # (serialization_parsing/regex_execution/time_date_logic) also now step over
        # a bounded `\`-line-continuation run ({0,50} continued lines, each itself
        # unboundedly-but-safely scanned via `[^\n]*`) so a classic multi-line
        # `RUN a && \` / `    b && \` / `    grep ...` chain is still seen -- the
        # plain `.*` version only ever looked at the first physical line.
        "serialization_parsing": re.compile(
            r"(?im)^(?:ADD|COPY)\s+[^\n]*(?:\\\r?\n[^\n]*){0,50}\.(?:tar\.gz|zip|tgz|tar)\b"
        ),  # ADD auto-extracts archives
        "regex_execution": re.compile(
            r"(?im)^RUN\s+[^\n]*(?:\\\r?\n[^\n]*){0,50}(?:grep|sed|awk)\b"
        ),  # Catches shell-delegated regex
        "time_date_logic": re.compile(
            r"(?im)^(?:HEALTHCHECK[^\n]*(?:\\\r?\n[^\n]*){0,50}(?:--interval|--timeout)"
            r"|RUN\s+[^\n]*(?:\\\r?\n[^\n]*){0,50}sleep)\b"
        ),
        "ipc_rpc_bridges": re.compile(r"(?im)^(?:EXPOSE|VOLUME|ENTRYPOINT|CMD|STOPSIGNAL)\b"),
    },
}
