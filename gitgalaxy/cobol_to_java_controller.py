#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: COBOL to Java Translation Controller
#
# PURPOSE:
# Orchestrates the Cloud Modernization Pathway. Ingests the JSON Intermediate
# Representation (IR) from the isolated staging environment and generates a 
# Spring Boot microservice scaffolding ready for an autonomous agent to complete.
# Includes Corporate Header injection, CI/CD Audit Reporting, and Maven Build generation.
#
# ARCHITECTURAL DECISION:
# Autonomous AI agents struggle to generate entire enterprise architectures from 
# scratch without hallucinating external dependencies or breaking Dependency 
# Injection (DI) chains. This controller deterministically generates the 100% 
# compilable boilerplate (POM, YML, JPA Entities, REST Controllers, and Mock 
# Services) based on the strict COBOL structural extraction. It delegates ONLY 
# the internal business logic to the AI agent, ensuring architectural integrity 
# and guaranteed compilability out-of-the-box.
# ==============================================================================

# galaxyscope:ignore sec_io

import argparse
import sys
import json
import shutil
from pathlib import Path

# Current Imports
from gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge import (
    generate_java_entity,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_api_contract_forge import (
    generate_rest_controller,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_agent_forge import (
    generate_java_agent_ticket,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_build_forge import (
    generate_pom_xml,
    generate_application_yml,
    generate_main_class,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_service_forge import (
    generate_service_skeleton,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_decoder_forge import (
    generate_decoder_util,
)


def build_spring_boot_scaffold(output_dir: Path, package_name: str) -> dict:
    """Creates the standard Spring Boot directory architecture."""
    pkg_path = package_name.replace(".", "/")
    base_dir = output_dir / "src" / "main" / "java" / pkg_path
    resources_dir = output_dir / "src" / "main" / "resources"

    dirs = {
        "root": output_dir,
        "base_pkg": base_dir,
        "resources": resources_dir,
        "entity": base_dir / "entity",
        "controller": base_dir / "controller",
        "service": base_dir / "service",
        "repository": base_dir / "repository",
        "util": base_dir / "util",  # <-- ADD THIS LINE
        "agent_jobs": output_dir / "ai_agent_jobs",
    }

    for name, path in dirs.items():
        if name != "root":
            path.mkdir(parents=True, exist_ok=True)

    return dirs


def format_java_header(header_text: str) -> str:
    """Wraps the corporate header in a clean Java block comment."""
    if not header_text.strip():
        return ""
    lines = header_text.strip().split("\n")
    out = "/* ==============================================================================\n"
    for line in lines:
        out += f" * {line}\n"
    out += " * ============================================================================== */\n"
    return out


def generate_mock_service(subroutine_name: str, package_name: str) -> str:
    """Generates a mock @Service interface to satisfy Spring DI for missing external dependencies."""
    camel_name = "".join(word.capitalize() for word in subroutine_name.replace("-", "_").split("_"))
    return f"""package {package_name}.service;

import org.springframework.stereotype.Service;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * ⚠️ AUTO-GENERATED MOCK SERVICE
 * This module intercepts unresolved COBOL calls to '{subroutine_name}'.
 * It allows the Spring Context to load and the AI Agent to write code 
 * without crashing due to missing dependencies.
 */
@Service
public class {camel_name}Service {{
    private static final Logger log = LoggerFactory.getLogger({camel_name}Service.class);

    public void executeDummyCall() {{
        log.warn("Mock Service {camel_name}Service was invoked. Implementation missing.");
    }}
}}
"""


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("COBOL-to-Java Translator")

    parser = argparse.ArgumentParser(description="GitGalaxy COBOL to Java Controller")
    parser.add_argument("clean_room", help="Path to the isolated staging directory (gitgalaxy_clean_[TIMESTAMP])")
    parser.add_argument("--pkg", default="com.gitgalaxy.modernized", help="Base Java package name")
    parser.add_argument("--header", default="header.txt", help="Path to the custom header text file")
    args = parser.parse_args()

    clean_room_path = Path(args.clean_room).resolve()
    if not clean_room_path.exists():
        print(f"Error: Target staging directory {clean_room_path} does not exist.")
        sys.exit(1)

    java_out_dir = clean_room_path.parent / f"{clean_room_path.name.replace('clean', 'java_spring')}"
    if java_out_dir.exists():
        shutil.rmtree(java_out_dir)

    # Determine Artifact ID from the isolated staging directory name
    artifact_id = clean_room_path.name.split("_gitgalaxy_clean")[0].lower()
    app_class_name = "".join(word.capitalize() for word in artifact_id.split("-"))

    print("\n" + "=" * 70)
    print(" ☕ GITGALAXY JAVA SPRING BOOT GENERATOR ENGAGED")
    print(f" Ingesting : {clean_room_path.name}")
    print(f" Artifact  : {artifact_id}")
    print(f" Package   : {args.pkg}")
    print("=" * 70 + "\n")

    # 0. Load the Corporate Header
    header_file = Path(args.header).resolve()
    java_header = ""
    if header_file.exists():
        raw_header = header_file.read_text(encoding="utf-8", errors="ignore")
        java_header = format_java_header(raw_header)
        print(f"  🛡️  Compliance Header Loaded from: {header_file.name}")
    else:
        print("  ⚠️  No header file found. Skipping header injection.")

    # 1. Build the Folder Structure & Scaffolding
    java_dirs = build_spring_boot_scaffold(java_out_dir, args.pkg)
    stats = {"entities": 0, "controllers": 0, "agent_jobs": 0, "config_files": 0}

    # Generate pom.xml
    pom_content = generate_pom_xml(group_id=args.pkg, artifact_id=artifact_id)
    (java_dirs["root"] / "pom.xml").write_text(pom_content, encoding="utf-8")
    stats["config_files"] += 1

    # Generate application.yml
    yml_content = generate_application_yml(artifact_id=artifact_id)
    (java_dirs["resources"] / "application.yml").write_text(yml_content, encoding="utf-8")
    stats["config_files"] += 1

    # Generate Application Main Class
    main_class_content = generate_main_class(args.pkg, app_class_name)
    if java_header:
        main_class_content = java_header + main_class_content
    (java_dirs["base_pkg"] / f"{app_class_name}Application.java").write_text(main_class_content, encoding="utf-8")
    stats["config_files"] += 1

    # --- Generate EBCDIC Decoder Utility ---
    decoder_content = generate_decoder_util(args.pkg)
    if java_header:
        decoder_content = java_header + decoder_content
    (java_dirs["util"] / "EbcdicDecoderUtil.java").write_text(decoder_content, encoding="utf-8")
    stats["config_files"] += 1
    # -------------------------------------------

    print("  [+] Generated Build System: pom.xml, application.yml, Main Class, DecoderUtil")

    # 2. Generate JPA Entities from Schemas
    schema_dir = clean_room_path / "02_cloud_schemas"
    if schema_dir.exists():
        for schema_file in schema_dir.glob("*_schema.json"):
            try:
                schema = json.loads(schema_file.read_text(encoding="utf-8"))
                java_code = generate_java_entity(schema, args.pkg)
                if java_header:
                    java_code = java_header + java_code
                class_name = "".join(word.capitalize() for word in schema.get("title", "Entity").split("_"))

                # Apply the exact same reserved word sanitization to the file name
                reserved_classes = {
                    "Entity",
                    "Class",
                    "System",
                    "Object",
                    "String",
                    "Enum",
                    "Record",
                    "Thread",
                }
                if class_name in reserved_classes:
                    class_name = "Legacy" + class_name

                out_path = java_dirs["entity"] / f"{class_name}.java"
                out_path.write_text(java_code, encoding="utf-8")
                stats["entities"] += 1
                print(f"  [+] Generated Entity: {class_name}.java")
            except Exception as e:
                print(f"  [!] Failed to generate entity from {schema_file.name}: {e}")

    # 3. Generate REST Controllers & Service Layers from IR State Files
    ir_dir = clean_room_path / "04_ir_state_dumps"
    if ir_dir.exists():
        for ir_file in ir_dir.glob("*_ir.json"):
            try:
                ir_state = json.loads(ir_file.read_text(encoding="utf-8"))
                raw_prog_id = ir_state.get("metadata", {}).get("file_name", "Unknown").split(".")[0]

                # 🛡️ Prevent collision with Spring Boot's @Service annotation AND handle empty names
                if not raw_prog_id or raw_prog_id.strip() == "":
                    raw_prog_id = "legacy"
                elif raw_prog_id.lower() == "service":
                    raw_prog_id = "legacy-service"

                # ⚠️ CRITICAL: Inject the safe raw name back into IR State so the generators process it correctly
                ir_state.setdefault("metadata", {})["file_name"] = raw_prog_id + ".cbl"

                # Ensure file names are perfectly camel-cased with no hyphens for this controller
                safe_file_name = "".join(word.capitalize() for word in raw_prog_id.split("-"))

                # 3A. Generate the @Service Skeleton
                service_code = generate_service_skeleton(ir_state, args.pkg)
                if java_header:
                    service_code = java_header + service_code
                out_path_svc = java_dirs["service"] / f"{safe_file_name}Service.java"
                out_path_svc.write_text(service_code, encoding="utf-8")
                print(f"  [+] Generated Service: {safe_file_name}Service.java")

                # 3B. Generate the @RestController
                lineage = ir_state.get("analysis", {}).get("lineage", {})
                if lineage and (lineage.get("inputs") or lineage.get("outputs") or lineage.get("unresolved_calls")):
                    java_code = generate_rest_controller(ir_state, args.pkg)
                    if java_header:
                        java_code = java_header + java_code
                    out_path_ctrl = java_dirs["controller"] / f"{safe_file_name}Controller.java"
                    out_path_ctrl.write_text(java_code, encoding="utf-8")
                    stats["controllers"] += 1
                    print(f"  [+] Generated API   : {safe_file_name}Controller.java")

                # 3C. Generate Mock Services for Unresolved Subroutines
                unresolved = lineage.get("unresolved_calls", [])
                for sub in unresolved:
                    # 🛡️ Skip empty, dynamic, or invalid subroutine calls
                    if not sub or not sub.strip():
                        continue

                    safe_sub_name = "".join(word.capitalize() for word in sub.replace("-", "_").split("_"))

                    # If it stripped down to nothing, skip it to prevent writing "Service.java"
                    if not safe_sub_name:
                        continue

                    # Ensure we don't accidentally overwrite a real service if it was already generated
                    out_path_mock = java_dirs["service"] / f"{safe_sub_name}Service.java"
                    if not out_path_mock.exists():
                        mock_code = generate_mock_service(sub, args.pkg)
                        if java_header:
                            mock_code = java_header + mock_code
                        out_path_mock.write_text(mock_code, encoding="utf-8")
                        print(f"  [+] Generated Mock  : {safe_sub_name}Service.java")

            except Exception as e:
                print(f"  [!] Failed to generate architecture from {ir_file.name}: {e}")

    # 4. Generate Autonomous AI Agent Tickets
    slice_dir = clean_room_path / "05_microservice_slices"
    if slice_dir.exists():
        for slice_file in slice_dir.glob("*_slice.json"):
            try:
                slice_data = json.loads(slice_file.read_text(encoding="utf-8"))
                prog_id = slice_file.name.split("_")[0]
                ir_file = ir_dir / f"{prog_id}_ir.json"
                ir_state = json.loads(ir_file.read_text(encoding="utf-8")) if ir_file.exists() else None

                ticket_json = generate_java_agent_ticket(slice_data, prog_id, ir_state)
                out_path = java_dirs["agent_jobs"] / f"{prog_id}_java_service_job.json"
                out_path.write_text(json.dumps(ticket_json, indent=2), encoding="utf-8")
                stats["agent_jobs"] += 1
                print(f"  [+] Generated Agent Job: {out_path.name}")
            except Exception as e:
                print(f"  [!] Failed to generate job from {slice_file.name}: {e}")

    # 5. Generate Master CI/CD Audit Report
    audit_report_path = java_out_dir / "java_migration_audit.txt"
    with open(audit_report_path, "w", encoding="utf-8") as f:
        f.write("==========================================================\n")
        f.write(" GITGALAXY JAVA SPRING BOOT MIGRATION AUDIT\n")
        f.write("==========================================================\n\n")
        f.write(f"  • Source Staging Environment : {clean_room_path.name}\n")
        f.write(f"  • Target Artifact            : {artifact_id}\n")
        f.write(f"  • Target Package             : {args.pkg}\n")
        f.write(f"  • Corporate Header Applied   : {'Yes' if java_header else 'No'}\n\n")

        f.write("[1] GENERATED CLOUD SCAFFOLDING\n")
        f.write("----------------------------------------------------------\n")
        f.write(f"  • Build & Config Files Scaffolded : {stats['config_files']}\n")
        f.write(f"  • JPA Entities Generated          : {stats['entities']}\n")
        f.write(f"  • REST Controllers Generated      : {stats['controllers']}\n")
        f.write(f"  • AI Agent Tickets Generated      : {stats['agent_jobs']}\n\n")
        f.write("==========================================================\n")

    print("\n" + "=" * 70)
    print(" 🏁 SPRING BOOT TRANSLATION COMPLETE")
    print(f" 📁 Location: {java_out_dir}")
    print("----------------------------------------------------------------------")
    print(f"  • Build & Config Files Scaffolded : {stats['config_files']}")
    print(f"  • JPA Entities Generated          : {stats['entities']}")
    print(f"  • REST Controllers Generated      : {stats['controllers']}")
    print(f"  • AI Agent Tickets Generated      : {stats['agent_jobs']}")
    print("======================================================================\n")


if __name__ == "__main__":
    main()