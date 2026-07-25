#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Spring Boot API Contract Generator
#
# PURPOSE:
# Translates structural DAG intent into modern REST Controller interfaces and
# auto-wires the corresponding @Service layer via constructor injection.
#
# ARCHITECTURAL DECISION:
# In an AI-assisted modernization pipeline, allowing an LLM to generate the 
# REST API entry points often leads to hallucinated routing and broken Dependency 
# Injection (DI) chains. This module deterministically generates the `@RestController` 
# layer directly from the COBOL static analysis. It establishes a rigid API contract 
# and auto-wires the `@Service` layer, forcing the AI agent to focus exclusively 
# on internal business logic without altering the external system boundaries.
# ==============================================================================
import argparse
import sys
import json
from pathlib import Path
from typing import Dict


def generate_rest_controller(ir_state: dict, package_name: str) -> str:
    """Generates the API endpoints and auto-wires the Service layer."""
    prog_id = ir_state.get("metadata", {}).get("file_name", "Unknown").split(".")[0]
    camel_prog = "".join(word.capitalize() for word in prog_id.split("-"))
    service_var = camel_prog[0].lower() + camel_prog[1:] if camel_prog else "unknown"

    analysis = ir_state.get("analysis", {})
    lineage = analysis.get("lineage", {})
    base_intent = analysis.get("base_intent", {})

    inputs = lineage.get("inputs", [])
    outputs = lineage.get("outputs", [])
    files_requested = base_intent.get("files_requested", [])
    is_cics = base_intent.get("is_cics", False)

    is_batch = len(files_requested) > 0 and not is_cics

    java = []
    java.append(f"package {package_name}.controller;\n")
    java.append("import org.springframework.web.bind.annotation.*;")
    java.append("import org.springframework.http.ResponseEntity;")
    java.append("import lombok.RequiredArgsConstructor;")
    java.append(f"import {package_name}.service.{camel_prog}Service;\n")

    if is_batch:
        java.append("import org.springframework.web.multipart.MultipartFile;")
        java.append("import org.springframework.http.MediaType;")
    java.append("")

    java.append("@RestController")
    java.append(f'@RequestMapping("/api/v1/{prog_id.lower()}")')
    java.append("@RequiredArgsConstructor")
    java.append(f"public class {camel_prog}Controller {{\n")

    java.append(f"    private final {camel_prog}Service {service_var}Service;\n")

    if is_batch:
        # --- BATCH PARADIGM ---
        java.append('    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)')
        java.append(f"    public ResponseEntity<?> execute{camel_prog}Batch(")

        params = []
        # ======================================================================
        # DEFENSIVE DESIGN (SPRING VARIABLE COLLISION PREVENTION):
        # Legacy COBOL programs can assign multiple internal files to the same 
        # external physical DD name. If mapped directly to Java, this causes 
        # duplicate variable names in the method signature, breaking compilation.
        # We track `seen_vars` and dynamically append numerical suffixes to 
        # ensure perfectly compiling Spring `@RequestParam` annotations.
        # ======================================================================
        seen_vars: Dict[str, int] = {}

        for file_req in files_requested:
            dd_name_raw = file_req.get("dd_name", "UNKNOWN").lower()

            # Strip hyphens and camelCase the Java variable
            dd_parts = dd_name_raw.split("-")
            safe_dd_name = dd_parts[0] + "".join(word.title() for word in dd_parts[1:])
            base_var_name = f"{safe_dd_name}File"

            # Enforce unique variable names and Spring request params
            if base_var_name in seen_vars:
                seen_vars[base_var_name] += 1
                unique_var_name = f"{base_var_name}{seen_vars[base_var_name]}"
                unique_param_name = f"{dd_name_raw}File{seen_vars[base_var_name]}"
            else:
                seen_vars[base_var_name] = 1
                unique_var_name = base_var_name
                unique_param_name = f"{dd_name_raw}File"

            params.append(f'@RequestParam("{unique_param_name}") MultipartFile {unique_var_name}')

        if params:
            java.append("        " + ",\n        ".join(params))
        else:
            java.append('        @RequestParam("file") MultipartFile file')

        java.append("    ) {")
        java.append("        // BATCH PARADIGM DETECTED")
        java.append("        // Pass the InputStream directly to the Service layer.")
        java.append(f"        {service_var}Service.execute{camel_prog}(/* pass streams here */);\n")

    else:
        # --- TRANSACTIONAL PARADIGM ---
        java.append('    @PostMapping("/execute")')
        java.append(f"    public ResponseEntity<?> execute{camel_prog}(")

        params = []
        if inputs:
            for i in inputs:
                safe_class = "".join(word.capitalize() for word in i.split("-"))
                safe_var = safe_class[0].lower() + safe_class[1:]
                params.append(f"@RequestBody {safe_class}DTO {safe_var}Data")

        if params:
            java.append("        " + ",\n        ".join(params))
        else:
            java.append("        /* No external data dependencies detected */")

        java.append("    ) {")
        java.append("        // TRANSACTIONAL PARADIGM DETECTED")
        java.append(f"        {service_var}Service.execute{camel_prog}(/* pass DTOs here */);\n")

    if outputs:
        java.append(f"        // Expected Outputs: {', '.join(outputs)}")
        java.append("        return ResponseEntity.ok().build();")
    else:
        java.append("        return ResponseEntity.noContent().build();")

    java.append("    }\n}")
    return "\n".join(java)


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("API Contract Generator")

    parser = argparse.ArgumentParser(description="GitGalaxy API Contract Generator")
    parser.add_argument("ir_file", help="Path to the GitGalaxy _ir.json state dump")
    parser.add_argument("--pkg", default="com.gitgalaxy.modernized", help="Base Java package name")
    args = parser.parse_args()

    ir_path = Path(args.ir_file).resolve()
    if not ir_path.exists():
        sys.exit(1)

    try:
        ir_state = json.loads(ir_path.read_text(encoding="utf-8"))
        java_code = generate_rest_controller(ir_state, args.pkg)
        prog_id = ir_state.get("metadata", {}).get("file_name", "Unknown").split(".")[0].capitalize()
        out_path = ir_path.parent / f"{prog_id}Controller.java"
        out_path.write_text(java_code, encoding="utf-8")
        print(f"🌐 API Contract Generated: {out_path.name}")
    except Exception as e:
        print(f"Error generating Controller: {e}")


if __name__ == "__main__":
    main()