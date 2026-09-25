#!/usr/bin/env python3
# ==============================================================================

# galaxyscope:ignore sec_io
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
#
# ENGINE IR (#3120): when the staging directory came from `cobol-refractor
# --galaxy-db/--scan`, each IR dump also carries `metadata.ir_source`,
# `analysis.copy_dependencies` and `analysis.engine_units` from the engine's
# master DB. Nothing here needs to change to pass them through.
# ==============================================================================

# galaxyscope:ignore sec_io

# galaxyscope:ignore sec_io

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Optional

from gitgalaxy.tools.cobol_to_java.cobol_to_java_agent_forge import (
    generate_java_agent_ticket,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_api_contract_forge import (
    generate_rest_controller,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_build_forge import (
    generate_application_yml,
    generate_build_gradle,
    generate_main_class,
    generate_pom_xml,
    generate_settings_gradle,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_decoder_forge import (
    generate_decoder_util,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import (
    java_class_base,
    output_key,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_service_forge import (
    generate_service_skeleton,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_skeleton_forges import SkeletonForges
from gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge import (
    dto_class_name,
    entity_class_name,
    generate_java_dto,
    generate_java_entity,
    is_transient_record,
)

# Current Imports
from gitgalaxy.tools.cobol_to_java.cobol_to_java_worklist import NATURES, write_worklist
from gitgalaxy.tools.cobol_to_java.java_target import (
    DEFAULT_CONFIG,
    ConfigError,
    load_target,
    target_as_dict,
    target_from_dict,
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
        "dto": base_dir / "dto",
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


def _write_skeleton_audit(f, skeletons: dict, forges: Optional[SkeletonForges] = None) -> None:
    """#3614: which engine facts the generated project was built against, and how far each is proven."""
    fields: dict[str, dict] = {}
    for key, path in skeletons.items():
        for sec in json.loads(path.read_text(encoding="utf-8")).get("sections", {}).values():
            if not sec.get("facts") or not isinstance(sec["facts"], list):
                continue  # the interface section is one mapping, reported by the CICS line below
            row = fields.setdefault(sec["ledger_field"], {**sec, "facts": 0, "programs": set()})
            row["facts"] += len(sec["facts"])
            row["programs"].add(key)
    f.write("[2] VERIFIED SKELETON (engine facts, 06_skeleton)\n")
    f.write("----------------------------------------------------------\n")
    f.write(f"  • Programs with a skeleton : {len(skeletons)}\n")
    f.write("  • Fact channel (ledger field)       facts  programs  field testing (public / private estates)\n")
    for name, row in sorted(fields.items()):
        f.write(
            f"    {name:<32} {row['facts']:>6}  {len(row['programs']):>8}  {row['field_testing']} "
            f"({row['tested_on_public']} / {row['tested_on_private']})\n"
        )
    f.write("  'open' = verified on the keyed reference corpora, still being field-tested on fresh estates.\n")
    if forges is not None:
        forges.write_audit(f)
    f.write("\n")


def _write_worklist_audit(f, worklist: dict) -> None:
    """#3651: the open items the generators left, by nature and category (details in migration_worklist.md)."""
    s = worklist["summary"]
    f.write("[3] MIGRATION WORKLIST (migration_worklist.md / .json)\n")
    f.write("----------------------------------------------------------\n")
    f.write(f"  • Open items : {s['items']} across {s['programs']} COBOL sources\n")
    f.write("  • By nature  : " + ", ".join(f"{n} {s['by_nature'][n]}" for n in NATURES) + "\n")
    for cid, n in s["by_category"].items():
        f.write(f"    {worklist['categories'][cid]['title']:<42} {n:>5}  ({worklist['categories'][cid]['nature']})\n")
    f.write("\n")


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("COBOL-to-Java Translator")

    parser = argparse.ArgumentParser(description="GitGalaxy COBOL to Java Controller")
    parser.add_argument(
        "clean_room", nargs="?", help="Path to the isolated staging directory (gitgalaxy_clean_[TIMESTAMP])"
    )
    parser.add_argument("--pkg", default=None, help="Base Java package name (overrides the config's project.package)")
    parser.add_argument("--header", default=None, help="Path to the custom header text file (overrides the config)")
    parser.add_argument("--config", type=Path, help="A YAML / JSON target config: Java kind, build tool, database, ...")
    parser.add_argument("--init-config", type=Path, metavar="PATH", help="Write an annotated default config and exit")
    args = parser.parse_args()

    # #3613: the target config -- explicit CLI flags, then the config file, then the defaults.
    if args.init_config:
        if args.init_config.exists():
            print(f"Error: {args.init_config} already exists; not overwriting it.")
            sys.exit(1)
        args.init_config.write_text(DEFAULT_CONFIG, encoding="utf-8")
        print(f"Wrote an annotated default config to {args.init_config}")
        return
    if not args.clean_room:
        parser.error("the staging directory is required (unless --init-config)")
    try:
        target = load_target(args.config)
        if args.pkg:
            target = target_from_dict({**target_as_dict(target), "project": {**target_as_dict(target)["project"],
                                       "package": args.pkg}})  # fmt: skip
    except (ConfigError, OSError, ValueError) as e:
        print(f"Error: invalid target config: {e}")
        sys.exit(2)
    args.pkg = target.project.package
    args.header = args.header or target.project.header_file or "header.txt"

    clean_room_path = Path(args.clean_room).resolve()
    if not clean_room_path.exists():
        print(f"Error: Target staging directory {clean_room_path} does not exist.")
        sys.exit(1)

    java_out_dir = clean_room_path.parent / f"{clean_room_path.name.replace('clean', 'java_spring')}"
    if java_out_dir.exists():
        shutil.rmtree(java_out_dir)

    # Determine Artifact ID from the isolated staging directory name
    artifact_id = target.project.artifact_id or clean_room_path.name.split("_gitgalaxy_clean")[0].lower()
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
    stats = {"entities": 0, "dtos": 0, "controllers": 0, "agent_jobs": 0, "config_files": 0}

    # Generate the build: pom.xml, or build.gradle + settings.gradle (#3613)
    if target.java.build_tool == "gradle":
        gradle = generate_build_gradle(target.group_id(), target)
        (java_dirs["root"] / "build.gradle").write_text(gradle, encoding="utf-8")
        (java_dirs["root"] / "settings.gradle").write_text(generate_settings_gradle(artifact_id), encoding="utf-8")
        stats["config_files"] += 2
    else:
        pom_content = generate_pom_xml(group_id=target.group_id(), artifact_id=artifact_id, target=target)
        (java_dirs["root"] / "pom.xml").write_text(pom_content, encoding="utf-8")
        stats["config_files"] += 1

    # Generate application.yml
    yml_content = generate_application_yml(artifact_id=artifact_id, target=target)
    (java_dirs["resources"] / "application.yml").write_text(yml_content, encoding="utf-8")
    stats["config_files"] += 1

    # Generate Application Main Class
    main_class_content = generate_main_class(args.pkg, app_class_name)
    if java_header:
        main_class_content = java_header + main_class_content
    (java_dirs["base_pkg"] / f"{app_class_name}Application.java").write_text(main_class_content, encoding="utf-8")
    stats["config_files"] += 1

    # --- Generate EBCDIC Decoder Utility ---
    if target.features.ebcdic_decoder:
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
        for schema_file in sorted(schema_dir.glob("*_schema.json"), key=lambda p: p.name):
            try:
                schema = json.loads(schema_file.read_text(encoding="utf-8"))
                unit_key = output_key(schema_file, "_schema")
                # #3233: a DFHCOMMAREA is a CICS communication area, not persistent
                # state. Every CICS program declares one, so mapping each to an
                # @Entity produced N classes on one @Table(name="DFHCOMMAREA") that
                # Hibernate refuses to start. Such a record becomes a plain DTO.
                if is_transient_record(schema):
                    java_code = generate_java_dto(schema, args.pkg, unit_key=unit_key, target=target)
                    class_name = dto_class_name(schema, unit_key)
                    out_dir, stat_key, label = java_dirs["dto"], "dtos", "DTO   "
                else:
                    java_code = generate_java_entity(schema, args.pkg, unit_key=unit_key, target=target)
                    # #3221: named from the schema's own clean-room key, so two
                    # programs that both declare a DFHCOMMAREA get two classes.
                    class_name = entity_class_name(schema, unit_key)
                    out_dir, stat_key, label = java_dirs["entity"], "entities", "Entity"

                if java_header:
                    java_code = java_header + java_code
                (out_dir / f"{class_name}.java").write_text(java_code, encoding="utf-8")
                stats[stat_key] += 1
                print(f"  [+] Generated {label}: {class_name}.java")
            except Exception as e:  # noqa: PERF203 -- per-iteration isolation: skip a malformed file, keep generating the rest of the batch
                print(f"  [!] Failed to generate entity from {schema_file.name}: {e}")

    # #3614: the refractor's verified skeletons (present when it ran with --scan / --galaxy-db)
    skeleton_dir = clean_room_path / "06_skeleton"
    skeletons = {p.name[: -len("_skeleton.json")]: p for p in sorted(skeleton_dir.glob("*_skeleton.json"))}
    # #3615-#3617 (#3657): the skeleton-driven forges -- CICS endpoints + contract DTOs, service-to-
    # service calls, VSAM repositories -- planned together and written in one go.
    forges = SkeletonForges(skeleton_dir, args.pkg, target) if skeletons and target.features.services else None
    if forges is not None:
        for stat, n in forges.write(java_dirs, java_header).items():
            stats[stat] += n
        print(f"  [+] {forges.summary()}")

    # 3. Generate REST Controllers & Service Layers from IR State Files
    ir_dir = clean_room_path / "04_ir_state_dumps"
    owners: dict[str, str] = {}
    estate_root = clean_room_path.parent / clean_room_path.name.split("_gitgalaxy_clean")[0]
    if ir_dir.exists():
        for ir_file in sorted(ir_dir.glob("*_ir.json"), key=lambda p: p.name):
            try:
                ir_state = json.loads(ir_file.read_text(encoding="utf-8"))
                # #3221: the clean room already disambiguated same-stemmed programs
                # into COBOL__SAM2 / multiroot__sam__SAM2 (#3218). Name the Java
                # from that key, not from metadata.file_name, which is SAM2.cbl for
                # both and made the later one overwrite the earlier.
                raw_prog_id = output_key(ir_file, "_ir")

                # 🛡️ Prevent collision with Spring Boot's @Service annotation AND handle empty names
                if not raw_prog_id or raw_prog_id.strip() == "":
                    raw_prog_id = "legacy"
                elif raw_prog_id.lower() == "service":
                    raw_prog_id = "legacy-service"

                safe_file_name = java_class_base(raw_prog_id)
                # #3651: the COBOL file this program's Service / Controller came from, estate-relative
                source = Path((ir_state.get("metadata") or {}).get("path") or "")
                if source.is_relative_to(estate_root):
                    owners[safe_file_name] = source.relative_to(estate_root).as_posix()
                cics_prog = None
                skeleton_key = output_key(ir_file, "_ir")
                if forges is not None and forges.class_base(skeleton_key) != safe_file_name:
                    skeleton_key = None  # a renamed key (legacy / legacy-service): keep the generic path
                if forges is not None and skeleton_key:
                    cics_prog = forges.cics_program(skeleton_key)

                # 3A. Generate the @Service Skeleton
                if target.features.services:
                    extras = forges.service_extras(skeleton_key) if forges is not None and skeleton_key else None
                    service_code = generate_service_skeleton(
                        ir_state, args.pkg, unit_key=raw_prog_id, target=target, extras=extras
                    )
                    if java_header:
                        service_code = java_header + service_code
                    out_path_svc = java_dirs["service"] / f"{safe_file_name}Service.java"
                    out_path_svc.write_text(service_code, encoding="utf-8")
                    print(f"  [+] Generated Service: {safe_file_name}Service.java")

                # 3B. Generate the @RestController
                lineage = ir_state.get("analysis", {}).get("lineage", {})
                wants_api = lineage.get("inputs") or lineage.get("outputs") or lineage.get("unresolved_calls")
                if cics_prog is not None and target.features.rest_controllers:
                    java_code = forges.cics.controller(cics_prog)
                    if java_header:
                        java_code = java_header + java_code
                    (java_dirs["controller"] / f"{safe_file_name}Controller.java").write_text(
                        java_code, encoding="utf-8"
                    )
                    stats["controllers"] += 1
                    print(f"  [+] Generated CICS API: {safe_file_name}Controller.java")
                elif target.features.rest_controllers and lineage and wants_api:
                    java_code = generate_rest_controller(ir_state, args.pkg, unit_key=raw_prog_id, target=target)
                    if java_header:
                        java_code = java_header + java_code
                    out_path_ctrl = java_dirs["controller"] / f"{safe_file_name}Controller.java"
                    out_path_ctrl.write_text(java_code, encoding="utf-8")
                    stats["controllers"] += 1
                    print(f"  [+] Generated API   : {safe_file_name}Controller.java")

                # 3C. Generate Mock Services for Unresolved Subroutines
                unresolved = lineage.get("unresolved_calls", []) if target.features.mock_services else []
                for sub in unresolved:
                    # 🛡️ Skip empty, dynamic, or invalid subroutine calls
                    if not sub or not sub.strip():
                        continue

                    safe_sub_name = java_class_base(sub, prefix="")

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
    if target.features.agent_tickets and slice_dir.exists():
        for slice_file in sorted(slice_dir.glob("*_slice.json"), key=lambda p: p.name):
            try:
                slice_data = json.loads(slice_file.read_text(encoding="utf-8"))
                # #3221: `name.split("_")[0]` returned COBOL for COBOL__SAM2_slice.json,
                # so the IR never resolved and two programs shared one job file.
                prog_id = output_key(slice_file, "_slice")
                ir_file = ir_dir / f"{prog_id}_ir.json"
                ir_state = json.loads(ir_file.read_text(encoding="utf-8")) if ir_file.exists() else None

                skeleton_file = skeletons.get(prog_id)
                skeleton = json.loads(skeleton_file.read_text(encoding="utf-8")) if skeleton_file else None
                ticket_json = generate_java_agent_ticket(
                    slice_data,
                    prog_id,
                    ir_state,
                    skeleton=skeleton,
                    skeleton_file=f"{clean_room_path.name}/06_skeleton/{skeleton_file.name}" if skeleton_file else None,
                )
                out_path = java_dirs["agent_jobs"] / f"{prog_id}_java_service_job.json"
                out_path.write_text(json.dumps(ticket_json, indent=2), encoding="utf-8")
                stats["agent_jobs"] += 1
                print(f"  [+] Generated Agent Job: {out_path.name}")
            except Exception as e:  # noqa: PERF203 -- per-iteration isolation: skip a malformed file, keep generating the rest of the batch
                print(f"  [!] Failed to generate job from {slice_file.name}: {e}")

    # 5. Generate Master CI/CD Audit Report
    # #3650: the traceability manifest, once every service and controller has been generated
    manifest = None
    if forges is not None:
        version = next((sk.get("skeleton_version") for sk in forges.skeletons.values()), None)
        manifest = forges.trace.as_dict({"clean_room": clean_room_path.name, "skeleton_version": version})
        (java_out_dir / "traceability.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    # #3651: every TODO the generators left, as one plan by category and COBOL source
    worklist = write_worklist(java_out_dir, manifest, {"clean_room": clean_room_path.name}, owners)

    audit_report_path = java_out_dir / "java_migration_audit.txt"
    with open(audit_report_path, "w", encoding="utf-8") as f:
        f.write("==========================================================\n")
        f.write(" GITGALAXY JAVA SPRING BOOT MIGRATION AUDIT\n")
        f.write("==========================================================\n\n")
        f.write(f"  • Source Staging Environment : {clean_room_path.name}\n")
        f.write(f"  • Target Artifact            : {artifact_id}\n")
        f.write(f"  • Target Package             : {args.pkg}\n")
        f.write(f"  • Corporate Header Applied   : {'Yes' if java_header else 'No'}\n")
        if args.config:  # #3613: record the target a config chose (the default run's report is unchanged)
            f.write(f"  • Target Config              : {args.config.name}\n")
            f.write(
                f"  • Java / Spring Boot / Build : {target.java.version} / {target.spring_boot.version} / "
                f"{target.java.build_tool}\n"
            )
            f.write(f"  • Data Classes / DTO Style   : {target.java.data_classes} / {target.java.dto_style}\n")
            f.write(f"  • Database                   : {target.database.engine}\n")
        f.write("\n")

        f.write("[1] GENERATED CLOUD SCAFFOLDING\n")
        f.write("----------------------------------------------------------\n")
        f.write(f"  • Build & Config Files Scaffolded : {stats['config_files']}\n")
        f.write(f"  • JPA Entities Generated          : {stats['entities']}\n")
        f.write(f"  • Transient DTOs Generated        : {stats['dtos']}\n")
        f.write(f"  • REST Controllers Generated      : {stats['controllers']}\n")
        f.write(f"  • AI Agent Tickets Generated      : {stats['agent_jobs']}\n\n")
        if skeletons:
            _write_skeleton_audit(f, skeletons, forges)
        _write_worklist_audit(f, worklist)
        f.write("==========================================================\n")

    print("\n" + "=" * 70)
    print(" 🏁 SPRING BOOT TRANSLATION COMPLETE")
    print(f" 📁 Location: {java_out_dir}")
    print("----------------------------------------------------------------------")
    print(f"  • Build & Config Files Scaffolded : {stats['config_files']}")
    print(f"  • JPA Entities Generated          : {stats['entities']}")
    print(f"  • Transient DTOs Generated        : {stats['dtos']}")
    print(f"  • REST Controllers Generated      : {stats['controllers']}")
    print(f"  • AI Agent Tickets Generated      : {stats['agent_jobs']}")
    print("======================================================================\n")


if __name__ == "__main__":
    main()
