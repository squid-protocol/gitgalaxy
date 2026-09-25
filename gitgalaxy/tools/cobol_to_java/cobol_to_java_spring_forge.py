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
import json
import re
import sys
from pathlib import Path
from typing import Callable, Optional

from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import java_identifier as _java_field_name
from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base, output_key
from gitgalaxy.tools.cobol_to_java.java_target import JavaTarget


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


def _render_field(col_name: str, col_data: dict, table_name: str, *, jpa: bool) -> list[str]:
    """Render one COBOL column as Java field lines.

    Shared by the JPA entity and the plain DTO paths. With ``jpa=True`` the field
    carries persistence annotations (``@Column`` / ``@Transient`` /
    ``@ElementCollection``); with ``jpa=False`` it is a bare POJO field, because a
    DFHCOMMAREA is a transient communication area, not persistent state (#3233).
    The structural comments (REDEFINES alias, OCCURS array) are kept either way.
    """
    description = col_data.get("description", "")
    base_java_type = map_type_to_java(col_data.get("type", ""), description)
    constraints = parse_pic_clause(description)
    camel_name = _java_field_name(col_name)

    lines: list[str] = []

    # ======================================================================
    # SCENARIO 1: MEMORY OVERLAY (REDEFINES)
    # In COBOL, REDEFINES creates an alias pointing to the same physical byte
    # address. As a persistent entity we map the alias @Transient so it is not
    # a duplicate SQL column; as a DTO the alias is just a plain field.
    # ======================================================================
    if "redefines" in constraints:
        target_camel = constraints["redefines"].lower().split("_")
        target_camel = target_camel[0] + "".join(w.title() for w in target_camel[1:])

        lines.append(f"    // ⚠️ REDEFINES ALIAS: Maps to {target_camel} in memory")
        if jpa:
            lines.append("    @Transient")
        lines.append(f"    private {base_java_type} {camel_name};\n")
        return lines

    # --- SCENARIO 2: ARRAY (OCCURS) ---
    if "occurs" in constraints:
        lines.append(f"    // ⚠️ ARRAY: OCCURS {constraints['occurs']} TIMES")
        if jpa:
            lines.append("    @ElementCollection")
            lines.append(
                f'    @CollectionTable(name = "{table_name}_{col_name.lower()}", joinColumns = @JoinColumn(name = "{table_name.lower()}_id"))'
            )
            lines.append(f'    @Column(name = "{col_name.lower()}_item")')
        lines.append(f"    private List<{base_java_type}> {camel_name};\n")
        return lines

    # --- SCENARIO 3: STANDARD COLUMN ---
    if jpa:
        col_attrs = [f'name = "{col_name}"']
        if base_java_type == "String" and "length" in constraints:
            col_attrs.append(f"length = {constraints['length']}")
        elif base_java_type == "BigDecimal":
            if "precision" in constraints:
                col_attrs.append(f"precision = {constraints['precision']}")
            if "scale" in constraints:
                col_attrs.append(f"scale = {constraints['scale']}")
        lines.append(f"    @Column({', '.join(col_attrs)})")

    # 🛡️ STRICT STATE INITIALIZATION
    # For network metrics, initialize to "N/A" instead of leaving null or defaulting to 0.
    if base_java_type == "String" and any(keyword in camel_name.lower() for keyword in ["ping", "lag", "latency"]):
        lines.append(f'    private {base_java_type} {camel_name} = "N/A";\n')
    else:
        lines.append(f"    private {base_java_type} {camel_name};\n")
    return lines


def is_transient_record(schema_json: dict) -> bool:
    """Whether a schema describes transient state rather than a persistent table.

    #3233: a CICS `DFHCOMMAREA` is the program's communication area -- a parameter
    block passed between programs, not a shared table. Every CICS program declares
    one, so mapping each to a JPA `@Entity` produced N classes all bound to
    `@Table(name = "DFHCOMMAREA")`, which Hibernate refuses to start. Such a record
    becomes a plain DTO instead. The signal is the 01-level title alone -- the only
    datum the schema carries; a lineage-driven rule (persist only records a program
    reads/writes to a file) is the more faithful successor, blocked on #3201.
    """
    return (schema_json.get("title") or "").upper() == "DFHCOMMAREA"


def entity_class_name(schema_json: dict, unit_key: Optional[str] = None) -> str:
    """The JPA Entity class a schema generates.

    #3221: a record title is not unique across a repository -- every CICS program
    declares a `DFHCOMMAREA`, so 29 of CBSA's schemas produced one Dfhcommarea.java
    and 28 programs' layouts were overwritten. Prefixing the owning program's
    clean-room key makes each one its own class. Without a key the name is the
    title alone, as before.
    """
    title = java_class_base(schema_json.get("title", "Entity"))
    return java_class_base(unit_key) + title if unit_key else title


def dto_class_name(schema_json: dict, unit_key: Optional[str] = None) -> str:
    """The DTO class a transient schema generates: the entity name plus a `Dto`
    suffix (e.g. `Bnk1cacDfhcommareaDto`), so it never collides with a real entity."""
    return entity_class_name(schema_json, unit_key) + "Dto"


_FIELD_DECL = re.compile(r"^    private ([\w<>]+) (\w+)(?: = [^;]+)?;$")


def _declared_fields(lines: list[str]) -> list[tuple[str, str]]:
    """(type, name) of every `private T name;` line _render_field wrote."""
    return [(m.group(1), m.group(2)) for m in (_FIELD_DECL.match(ln.rstrip("\n")) for ln in lines) if m]


def _accessors(class_name: str, fields: list[tuple[str, str]]) -> list[str]:
    """#3613 `data_classes: plain`: the no-args constructor and the getters / setters
    Lombok's @Data / @NoArgsConstructor would have generated."""
    out = [f"    public {class_name}() {{", "    }", ""]
    for java_type, name in fields:
        cap = name[0].upper() + name[1:]
        out += [f"    public {java_type} get{cap}() {{", f"        return {name};", "    }", ""]
        out += [f"    public void set{cap}({java_type} {name}) {{", f"        this.{name} = {name};", "    }", ""]
    return out


def generate_java_entity(
    schema_json: dict, package_name: str, unit_key: Optional[str] = None, target: Optional[JavaTarget] = None
) -> str:
    """Generates a JPA Entity enforcing exact COBOL memory constraints & overlaps.

    `target` (#3613): Lombok `@Data` (the default), or plain explicit accessors."""
    lombok = (target or JavaTarget()).lombok
    # The table keeps the legacy record name: the class is disambiguated, the
    # COBOL 01-level it maps is not renamed.
    table_name = schema_json.get("title", "UnknownTable")
    class_name = entity_class_name(schema_json, unit_key)

    properties = schema_json.get("properties", {})

    # Check if we need List imports for OCCURS clauses
    requires_list = any("OCCURS" in col_data.get("description", "").upper() for col_data in properties.values())

    java = []
    java.append(f"package {package_name}.entity;\n")
    if lombok:
        java.append("import lombok.Data;")
        java.append("import lombok.NoArgsConstructor;")
    java.append("import jakarta.persistence.*;")
    java.append("import java.math.BigDecimal;")
    if requires_list:
        java.append("import java.util.List;")
    java.append("")

    if lombok:
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

    body: list[str] = []
    for col_name, col_data in properties.items():
        body.extend(_render_field(col_name, col_data, table_name, jpa=True))
    java.extend(body)
    if not lombok:
        java.extend(_accessors(class_name, [("Long", "sysId"), *_declared_fields(body)]))

    java.append("}")
    return "\n".join(java)


def generate_java_dto(
    schema_json: dict, package_name: str, unit_key: Optional[str] = None, target: Optional[JavaTarget] = None
) -> str:
    """Generates a plain Lombok POJO DTO for a transient record (#3233).

    A DFHCOMMAREA is a CICS communication area -- a parameter block, not persistent
    state -- so it carries no JPA mapping: no `@Entity`/`@Table`, no synthetic `@Id`
    surrogate key, no `@Column`. The exact COBOL layout (field order, precision,
    OCCURS arrays, REDEFINES aliases) is preserved as plain fields, since the block
    is still read and written by the migrated business logic.

    `target` (#3613): a Lombok class (the default), a plain class with explicit
    accessors, or (`dto_style: record`) a Java record of the same fields.
    """
    t = target or JavaTarget()
    class_name = dto_class_name(schema_json, unit_key)
    properties = schema_json.get("properties", {})

    requires_list = any("OCCURS" in col_data.get("description", "").upper() for col_data in properties.values())

    body: list[str] = []
    for col_name, col_data in properties.items():
        body.extend(_render_field(col_name, col_data, class_name, jpa=False))

    return render_dto_class(f"{package_name}.dto", class_name, body, requires_list, t)


def render_dto_class(
    package: str,
    class_name: str,
    body: list[str],
    requires_list: bool,
    target: JavaTarget,
    javadoc: Optional[list[str]] = None,
    methods: Optional[Callable[[bool], list[str]]] = None,
) -> str:
    """A DTO from its field lines (`_render_field` shape: `//` comments and `    private T name;`),
    in the target's style: a Lombok class, a plain class with accessors, or a Java record.
    `methods(is_record)` adds method lines inside the class / record body (#3655)."""
    t = target
    java = []
    java.append(f"package {package};\n")
    use_lombok = t.lombok and t.java.dto_style == "class"
    if use_lombok:
        java.append("import lombok.Data;")
        java.append("import lombok.NoArgsConstructor;")
    java.append("import java.math.BigDecimal;")
    if requires_list:
        java.append("import java.util.List;")
    java.append("")
    if javadoc:
        java.append("/**")
        java.extend(f" * {ln}".rstrip() for ln in javadoc)
        java.append(" */")

    if t.java.dto_style == "record":
        # A record's components are its fields: each keeps its structural comments.
        components: list[str] = []
        for ln in body:
            m = _FIELD_DECL.match(ln.rstrip("\n"))
            if m:
                components.append(f"        {m.group(1)} {m.group(2)}")
            elif ln.strip().startswith("//"):
                components.append("    " + ln.rstrip("\n"))
        decl = list(components)
        idx = [i for i, c in enumerate(decl) if not c.strip().startswith("//")]
        for i in idx[:-1]:
            decl[i] += ","
        java.append(f"public record {class_name}(")
        java.extend(decl)
        java.append(") {")
        java.extend(methods(True) if methods else [])
        java.append("}")
        return "\n".join(java)

    if use_lombok:
        java.append("@Data")
        java.append("@NoArgsConstructor")
    java.append(f"public class {class_name} {{\n")
    java.extend(body)
    if not use_lombok:
        java.extend(_accessors(class_name, _declared_fields(body)))
    java.extend(methods(False) if methods else [])
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
        unit_key = output_key(schema_path, "_schema")
        if is_transient_record(schema):
            java_code = generate_java_dto(schema, args.pkg, unit_key=unit_key)
            out_path = schema_path.parent / f"{dto_class_name(schema, unit_key)}.java"
            out_path.write_text(java_code, encoding="utf-8")
            print(f"☕ Spring DTO Generated: {out_path.name}")
        else:
            java_code = generate_java_entity(schema, args.pkg, unit_key=unit_key)
            out_path = schema_path.parent / f"{entity_class_name(schema, unit_key)}.java"
            out_path.write_text(java_code, encoding="utf-8")
            print(f"☕ Spring Entity Generated: {out_path.name}")
    except Exception as e:
        print(f"Error generating Java class: {e}")


if __name__ == "__main__":
    main()
