#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Java Spring Service Scaffolding Generator
#
# PURPOSE:
# Scaffolds the @Service class and stages cross-service dependencies discovered
# via the global DAG (lineage) for the autonomous agent.
#
# ARCHITECTURAL DECISION:
# Following domain-driven design principles, the `@Service` layer encapsulates
# pure business logic, strictly isolated from REST API routing. By scaffolding
# this layer and mapping unresolved dynamic calls (from the DAG lineage) as
# explicit constraints, we guide the autonomous agent to implement the core
# COBOL rules while preventing it from hallucinating missing Spring beans or
# breaking the overall ApplicationContext.
# ==============================================================================

# galaxyscope:ignore sec_hardcoded_secrets, secrets_risk

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import (
    java_class_base,
    output_key,
    program_key_from_ir,
)
from gitgalaxy.tools.cobol_to_java.java_target import JavaTarget


def generate_service_skeleton(
    ir_state: dict,
    package_name: str,
    unit_key: Optional[str] = None,
    target: Optional[JavaTarget] = None,
    extras: Optional[dict] = None,
) -> str:
    """Generates the Spring Boot @Service skeleton and stages DAG dependencies.

    `unit_key` is the clean-room output key this IR was written under (#3221).
    Omitted, the class is named from the IR's own file name as before, which two
    same-stemmed programs share.

    `extras` (#3615, #3616): what the verified skeleton adds -- `imports` (lines),
    `fields` ((type, name) dependencies injected through the constructor) and
    `methods` (lines): the handlers a CICS program's endpoints call and the calls it
    makes to other programs. None leaves the service as before.
    """
    prog_id = program_key_from_ir(ir_state, unit_key) or "Unknown"
    camel_prog = java_class_base(prog_id, prefix="Legacy")

    analysis = ir_state.get("analysis", {})
    lineage = analysis.get("lineage", {})
    unresolved_calls = lineage.get("unresolved_calls", [])

    java = []
    java.append(f"package {package_name}.service;\n")
    lombok = (target or JavaTarget()).lombok
    java.append("import org.springframework.stereotype.Service;")
    if lombok:
        java.append("import lombok.RequiredArgsConstructor;")
    java.append("import org.slf4j.Logger;")
    java.append("import org.slf4j.LoggerFactory;")
    extras = extras or {}
    fields = extras.get("fields", [])
    java.extend(extras.get("imports", []))
    java.append("")
    if extras.get("class_doc"):  # #3621: a class note, e.g. the program's response handling
        java += ["/**", *(f" * {line}".rstrip() for line in extras["class_doc"]), " */"]

    java.append("@Service")
    java.extend(extras.get("annotations", []))  # #3621: e.g. @Transactional
    if lombok:
        java.append("@RequiredArgsConstructor")
    java.append(f"public class {camel_prog}Service {{\n")

    java.append(f"    private static final Logger log = LoggerFactory.getLogger({camel_prog}Service.class);\n")
    if fields:
        java.extend(f"    private final {jtype} {name};" for jtype, name in fields)
        java.append("")
        if not lombok:  # #3613 plain: the constructor injection Lombok would have generated
            java.append(f"    public {camel_prog}Service({', '.join(f'{t} {n}' for t, n in fields)}) {{")
            java.extend(f"        this.{name} = {name};" for _, name in fields)
            java.append("    }\n")

    # ==========================================================================
    # DEFENSIVE DESIGN (APPLICATION CONTEXT SHIELD):
    # Cross-Service dependencies are injected as comments/TODOs rather than active
    # autowired fields. If we actively inject a dependency that hasn't been fully
    # generated yet, the Spring Boot IoC container will throw a
    # NoSuchBeanDefinitionException, preventing the pipeline from compiling.
    # ==========================================================================
    if unresolved_calls:
        java.append("    // ⚠️ UNRESOLVED EXTERNAL DEPENDENCIES (FROM DAG)")
        for call in unresolved_calls:
            call_camel = "".join(word.capitalize() for word in call.split("-"))
            java.append(f"    // TODO: AI AGENT - Implement or mock interface call to: {call_camel}Service")
        java.append("")

    java.append(f"    public void execute{camel_prog}(/* Parameters mapped from Controller */) {{")
    java.append(f'        log.info("Executing modernized business logic for {prog_id}");')
    java.append("        // TODO: [AI AGENT] Implement extracted business rules here.")
    if extras.get("methods"):
        java.append("    }\n")
        java.extend(extras["methods"])
        java.append("}")
    else:
        java.append("    }\n}")

    return "\n".join(java)


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("Service Scaffolding Generator")

    parser = argparse.ArgumentParser(description="GitGalaxy Service Scaffolding Generator")
    parser.add_argument("ir_file", help="Path to the GitGalaxy _ir.json state dump")
    parser.add_argument("--pkg", default="com.gitgalaxy.modernized", help="Base Java package name")
    args = parser.parse_args()

    ir_path = Path(args.ir_file).resolve()
    if not ir_path.exists():
        sys.exit(1)

    try:
        ir_state = json.loads(ir_path.read_text(encoding="utf-8"))
        unit_key = output_key(ir_path, "_ir")
        java_code = generate_service_skeleton(ir_state, args.pkg, unit_key=unit_key)
        out_path = ir_path.parent / f"{java_class_base(unit_key)}Service.java"
        out_path.write_text(java_code, encoding="utf-8")
        print(f"⚙️ Service Skeleton Generated: {out_path.name}")
    except Exception as e:
        print(f"Error generating Service: {e}")


if __name__ == "__main__":
    main()
