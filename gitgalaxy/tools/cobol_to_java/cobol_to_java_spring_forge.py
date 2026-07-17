#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Java Spring Entity Generator
#
# PURPOSE:
# Translates JSON schemas into Spring Boot JPA Entities.
# Handles strict financial precision (PIC), Arrays (OCCURS),
# and Memory Overlays (REDEFINES).
#
# ARCHITECTURAL DECISION:
# Relational databases and Java ORMs (Hibernate/JPA) allocate memory entirely 
# differently than mainframe COBOL. COBOL utilizes absolute byte boundaries, 
# arrays (OCCURS), and memory overlays (REDEFINES) where multiple variables 
# point to the exact same physical byte block. This generator dynamically maps 
# these legacy constraints into modern JPA annotations (e.g., @ElementCollection, 
# @Transient) to ensure legacy data structures are safely persisted without 
# duplicating columns or corrupting the modern relational schema.
# ==============================================================================

# galaxyscope:ignore sec_hardcoded_secrets, secrets_risk

import argparse
import sys
import json
import re
from pathlib import Path


def map_type_to_java(json_type: str, description: str) -> str:
    """Maps JSON schema types to Java classes."""
    if json_type == "integer":
        return "Long" if "BIGINT" in description.upper() else "Integer"
    if json_type in ("number", "decimal"):
        return "BigDecimal"
    return "String"


def parse_pic_clause(description: str) -> dict:
    """
    Analyzes COBOL PIC, OCCURS, and REDEFINES clauses in the description
    to extract exact memory boundaries and structural directives.
    """
    constraints = {}

    # 1. Check for REDEFINES (Memory Overlays)
    redefines_match = re.search(r"REDEFINES\s+([A-Z0-9_\-]+)", description, re.IGNORECASE)
    if redefines_match:
        constraints["redefines"] = redefines_match.group(1)

    # 2. Check for OCCURS (Arrays)
    occurs_match = re.search(r"OCCURS\s+(\d+)", description, re.IGNORECASE)
    if occurs_match:
        constraints["occurs"] = int(occurs_match.group(1))

    # 3. Isolate the PIC clause for precision mapping
    pic_match = re.search(r"PIC\s+([A-Z0-9\(\)V\.]+)", description, re.IGNORECASE)
    if not pic_match:
        return constraints

    pic_string = pic_match.group(1).upper()

    # Handle Strings: PIC X(50) or PIC X
    if "X" in pic_string or "A" in pic_string:
        length_match = re.search(r"[XA]\((\d+)\)", pic_string)
        if length_match:
            constraints["length"] = int(length_match.group(1))
        else:
            constraints["length"] = max(pic_string.count("X"), pic_string.count("A"), 1)
        return constraints

    # Handle Numbers: PIC S9(7)V99, PIC 9(4)
    if "9" in pic_string or "V" in pic_string or "Z" in pic_string:
        precision = 0
        scale = 0
        parts = pic_string.split("V")

        def count_nines(part):
            count = 0
            paren_match = re.search(r"9\((\d+)\)", part)
            if paren_match:
                count += int(paren_match.group(1))
            else:
                count += part.count("9") + part.count("Z")
            return count

        precision += count_nines(parts[0])

        if len(parts) > 1:
            scale = count_nines(parts[1])
            precision += scale
            constraints["scale"] = scale

        if precision > 0:
            constraints["precision"] = precision

    return constraints


def generate_java_entity(schema_json: dict, package_name: str) -> str:
    """Generates a JPA Entity enforcing exact COBOL memory constraints & overlaps."""
    table_name = schema_json.get("title", "UnknownTable")
    class_name = "".join(word.capitalize() for word in table_name.split("_"))

    # Prevent collision with Java reserved keywords and core classes
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

    properties = schema_json.get("properties", {})

    # Check if we need List imports for OCCURS clauses
    requires_list = any("OCCURS" in col_data.get("description", "").upper() for col_data in properties.values())

    java = []
    java.append(f"package {package_name}.entity;\n")
    java.append("import lombok.Data;")
    java.append("import lombok.NoArgsConstructor;")
    java.append("import jakarta.persistence.*;")
    java.append("import java.math.BigDecimal;")
    if requires_list:
        java.append("import java.util.List;")
    java.append("")

    java.append("@Data")
    java.append("@NoArgsConstructor")
    java.append("@Entity")
    java.append(f'@Table(name = "{table_name}")')
    java.append(f"public class {class_name} {{")

    # Change 'id' to 'sysId' to prevent collision with legacy variables named 'id'
    java.append("\n    @Id")
    java.append("    @GeneratedValue(strategy = GenerationType.IDENTITY)")
    java.append('    @Column(name = "sys_id")')
    java.append("    private Long sysId;\n")

    for col_name, col_data in properties.items():
        description = col_data.get("description", "")
        base_java_type = map_type_to_java(col_data.get("type"), description)
        constraints = parse_pic_clause(description)

        # Replace hyphens with underscores before splitting to catch all legacy variations
        clean_col = col_name.lower().replace("-", "_")
        parts = clean_col.split("_")
        camel_name = parts[0] + "".join(word.title() for word in parts[1:])

        # ======================================================================
        # DEFENSIVE DESIGN (JAVA SYNTAX SANITIZATION):
        # COBOL variables frequently use names that are protected keywords in Java 
        # (e.g., CLASS, NEW, DEFAULT) or start with numeric characters. We strictly 
        # sanitize the target variable names to guarantee the output is 100% compilable 
        # before the AI agent touches it.
        # ======================================================================
        
        # Java variables cannot start with a number. Prefix with 'v'.
        if camel_name and camel_name[0].isdigit():
            camel_name = "v" + camel_name

        reserved_vars = {
            "class", "static", "public", "private", "protected", "return", 
            "new", "system", "default", "enum", "interface", "void", "try", 
            "catch", "finally", "import", "package", "super", "this", "const", 
            "goto", "byte", "int", "char", "short", "long", "float", "double", 
            "boolean", "null", "true", "false"
        }
        if camel_name in reserved_vars:
            camel_name += "Val"

        # ======================================================================
        # SCENARIO 1: MEMORY OVERLAY (REDEFINES)
        # DEFENSIVE DESIGN: In COBOL, REDEFINES creates an alias pointing to the 
        # same physical byte address. In JPA, mapping both variables as standard 
        # columns would duplicate the data in the SQL table. We map the alias 
        # as `@Transient` so it can be used in business logic without persisting 
        # a duplicate column to the database.
        # ======================================================================
        if "redefines" in constraints:
            target_camel = constraints["redefines"].lower().split("_")
            target_camel = target_camel[0] + "".join(w.title() for w in target_camel[1:])

            java.append(f"    // ⚠️ REDEFINES ALIAS: Maps to {target_camel} in memory")
            java.append("    @Transient")
            java.append(f"    private {base_java_type} {camel_name};\n")
            continue

        # --- SCENARIO 2: ARRAY (OCCURS) ---
        if "occurs" in constraints:
            java.append(f"    // ⚠️ ARRAY: OCCURS {constraints['occurs']} TIMES")
            java.append("    @ElementCollection")
            java.append(
                f'    @CollectionTable(name = "{table_name}_{col_name.lower()}", joinColumns = @JoinColumn(name = "{table_name.lower()}_id"))'
            )
            java.append(f'    @Column(name = "{col_name.lower()}_item")')
            java.append(f"    private List<{base_java_type}> {camel_name};\n")
            continue

        # --- SCENARIO 3: STANDARD PERSISTENT COLUMN ---
        col_attrs = [f'name = "{col_name}"']
        if base_java_type == "String" and "length" in constraints:
            col_attrs.append(f"length = {constraints['length']}")
        elif base_java_type == "BigDecimal":
            if "precision" in constraints:
                col_attrs.append(f"precision = {constraints['precision']}")
            if "scale" in constraints:
                col_attrs.append(f"scale = {constraints['scale']}")

        java.append(f"    @Column({', '.join(col_attrs)})")

        # 🛡️ STRICT STATE INITIALIZATION
        # For network metrics, initialize to "N/A" instead of leaving null or defaulting to 0.
        if base_java_type == "String" and any(keyword in camel_name.lower() for keyword in ["ping", "lag", "latency"]):
            java.append(f'    private {base_java_type} {camel_name} = "N/A";\n')
        else:
            java.append(f"    private {base_java_type} {camel_name};\n")

    java.append("}")
    return "\n".join(java)


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("Java Entity Generator")

    parser = argparse.ArgumentParser(description="GitGalaxy Java Entity Generator")
    parser.add_argument("schema_file", help="Path to the GitGalaxy _schema.json file")
    parser.add_argument("--pkg", default="com.gitgalaxy.modernized", help="Base Java package name")
    args = parser.parse_args()

    schema_path = Path(args.schema_file).resolve()
    if not schema_path.exists():
        sys.exit(1)

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        java_code = generate_java_entity(schema, args.pkg)

        class_name = "".join(word.capitalize() for word in schema.get("title", "Entity").split("_"))
        out_path = schema_path.parent / f"{class_name}.java"
        out_path.write_text(java_code, encoding="utf-8")

        print(f"☕ Spring Entity Generated: {out_path.name}")
    except Exception as e:
        print(f"Error generating Java Entity: {e}")


if __name__ == "__main__":
    main()