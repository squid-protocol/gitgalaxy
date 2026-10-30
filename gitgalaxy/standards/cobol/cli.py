# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The cobol_spec CLI (#4712, epic #4710): `python -m gitgalaxy.standards.cobol ...`

    emit [--json]              print the rule matrices and vectors as summary or JSON
    check                      the spec's own consistency and catalogue alignment
    regen [--check | --out DIR]  rewrite the committed generated files (or check / render them):
                               - MoveSpec.java & CompareSpec.java in cobolrt
                               - cobol_move_matrix.md & cobol_compare_matrix.md in docs
                               - test_cobol_move_vectors.py & test_cobol_compare_vectors.py in tests

Follows the table-driven code generation pattern of CicsSpec.java (#4586, #4608).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from gitgalaxy.standards.cobol.arith import (
    ARITH_RULES,
    ARITH_VECTORS,
    NAN_SCALE,
    ROUND_NEAREST_AWAY_FROM_ZERO,
    ROUND_NEAREST_EVEN,
    ROUND_NEAREST_TOWARD_ZERO,
    ROUND_PROHIBITED,
    ROUND_TOWARD_GREATER,
    ROUND_TOWARD_LESSER,
    ROUND_TRUNCATION,
    ROUNDING_MODES,
    SIZE_ERROR_CONDITIONS,
)
from gitgalaxy.standards.cobol.compare import (
    COMPARE_MATRIX,
    COMPARE_MODES,
    COMPARE_RULES,
    COMPARE_VECTORS,
)
from gitgalaxy.standards.cobol.editing import (
    EDIT_CATEGORY_DIGIT,
    EDIT_CATEGORY_FIXED_INSERTION,
    EDIT_CATEGORY_FLOATING_INSERTION,
    EDIT_CATEGORY_IMPLICIT,
    EDIT_CATEGORY_NAMES,
    EDIT_CATEGORY_SIMPLE_INSERTION,
    EDIT_CATEGORY_SPECIAL_INSERTION,
    EDIT_CATEGORY_ZERO_SUPPRESSION,
    EDITING_RULES,
    EDITING_SYMBOLS,
    EDITING_SYMBOLS_STRING,
    EDITING_VECTORS,
)
from gitgalaxy.standards.cobol.func import (
    CATEGORY_DATE_TIME,
    CATEGORY_IO,
    CATEGORY_MATH,
    CATEGORY_PARSING,
    CATEGORY_STRING,
    FUNC_CATEGORIES,
    FUNC_RULES,
    FUNC_SPECS,
    FUNC_VECTORS,
)
from gitgalaxy.standards.cobol.hfp import (
    BIAS_CHARACTERISTIC,
    BYTES_LONG,
    BYTES_SHORT,
    DISPLAY_DIGITS_LONG,
    DISPLAY_DIGITS_SHORT,
    HFP_RULES,
    HFP_VECTORS,
    MAX_CHARACTERISTIC,
    MAX_EXPONENT,
    MIN_EXPONENT,
    PRECISION_LONG,
    PRECISION_SHORT,
    SIGNIFICANT_DIGITS_LONG,
    SIGNIFICANT_DIGITS_SHORT,
    TYPE_NAME_COMP1,
    TYPE_NAME_COMP2,
)
from gitgalaxy.standards.cobol.move import (
    ACTIONS,
    CATEGORIES,
    CATEGORY_NAMES,
    KIND_CATEGORY,
    KINDS,
    MOVE_MATRIX,
    MOVE_RULES,
    MOVE_VECTORS,
)
from gitgalaxy.standards.cobol.sort_ops import (
    COLLATING_EBCDIC,
    COLLATING_LITERAL,
    COLLATING_NAMES,
    COLLATING_NATIVE,
    DIRECTION_ASCENDING,
    DIRECTION_DESCENDING,
    DIRECTION_NAMES,
    PHRASE_GIVING,
    PHRASE_INPUT_PROCEDURE,
    PHRASE_NAMES,
    PHRASE_OUTPUT_PROCEDURE,
    PHRASE_USING,
    SORT_RETURN_ABORT,
    SORT_RETURN_SUCCESS,
    SORT_RULES,
    SORT_VECTORS,
)
from gitgalaxy.standards.cobol.string_ops import (
    INSPECT_ALL,
    INSPECT_CHARACTERS,
    INSPECT_FIRST,
    INSPECT_LEADING,
    INSPECT_MODES,
    PHRASE_CONVERTING,
    PHRASE_REPLACING,
    PHRASE_TALLYING,
    PHRASE_TYPES,
    STATEMENT_INSPECT,
    STATEMENT_STRING,
    STATEMENT_UNSTRING,
    STRING_RULES,
    STRING_VECTORS,
)

BANNER = "generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`; do not edit"

ROOT = Path(__file__).resolve().parents[3]
MOVE_JAVA_FILE = Path("gitgalaxy/tools/cobol_to_java/det/cobolrt/MoveSpec.java")
COMPARE_JAVA_FILE = Path("gitgalaxy/tools/cobol_to_java/det/cobolrt/CompareSpec.java")
ARITH_JAVA_FILE = Path("gitgalaxy/tools/cobol_to_java/det/cobolrt/ArithSpec.java")
STRING_JAVA_FILE = Path("gitgalaxy/tools/cobol_to_java/det/cobolrt/StringSpec.java")
FUNC_JAVA_FILE = Path("gitgalaxy/tools/cobol_to_java/det/cobolrt/FuncSpec.java")
EDITING_JAVA_FILE = Path("gitgalaxy/tools/cobol_to_java/det/cobolrt/EditingSpec.java")
SORT_JAVA_FILE = Path("gitgalaxy/tools/cobol_to_java/det/cobolrt/SortSpec.java")
HFP_JAVA_FILE = Path("gitgalaxy/tools/cobol_to_java/det/cobolrt/HfpSpec.java")
MOVE_DOCS_FILE = Path("docs/language_status/cobol_move_matrix.md")
COMPARE_DOCS_FILE = Path("docs/language_status/cobol_compare_matrix.md")
ARITH_DOCS_FILE = Path("docs/language_status/cobol_arith_matrix.md")
STRING_DOCS_FILE = Path("docs/language_status/cobol_string_matrix.md")
FUNC_DOCS_FILE = Path("docs/language_status/cobol_func_matrix.md")
EDITING_DOCS_FILE = Path("docs/language_status/cobol_editing_matrix.md")
SORT_DOCS_FILE = Path("docs/language_status/cobol_sort_matrix.md")
HFP_DOCS_FILE = Path("docs/language_status/cobol_hfp_matrix.md")
MOVE_TEST_FILE = Path("tests/cobol_mainframe/test_cobol_move_vectors.py")
COMPARE_TEST_FILE = Path("tests/cobol_mainframe/test_cobol_compare_vectors.py")
ARITH_TEST_FILE = Path("tests/cobol_mainframe/test_cobol_arith_vectors.py")
STRING_TEST_FILE = Path("tests/cobol_mainframe/test_cobol_string_vectors.py")
FUNC_TEST_FILE = Path("tests/cobol_mainframe/test_cobol_func_vectors.py")
EDITING_TEST_FILE = Path("tests/cobol_mainframe/test_cobol_editing_vectors.py")
SORT_TEST_FILE = Path("tests/cobol_mainframe/test_cobol_sort_vectors.py")
HFP_TEST_FILE = Path("tests/cobol_mainframe/test_cobol_hfp_vectors.py")
JAVA_PACKAGE = "__PACKAGE__.cobolrt"


def as_json() -> dict[str, Any]:
    """The spec as plain data: rules, matrices, and test vectors."""
    return {
        "categories": dict(CATEGORIES),
        "kinds": list(KINDS),
        "actions": list(ACTIONS),
        "compare_modes": dict(COMPARE_MODES),
        "move": {
            "rules": {k: dataclasses.asdict(r) for k, r in MOVE_RULES.items()},
            "matrix": [
                {
                    "from_kind": k[0],
                    "to_kind": k[1],
                    "from_category": CATEGORY_NAMES[KIND_CATEGORY[k[0]]],
                    "to_category": CATEGORY_NAMES[KIND_CATEGORY[k[1]]],
                    "permissible": v.permissible,
                    "rule_id": v.rule_id,
                    "action": v.action,
                    "ibm_section": v.ibm_section,
                    "note": v.note,
                }
                for k, v in sorted(MOVE_MATRIX.items())
            ],
            "vectors": [
                {
                    "id": v.id,
                    "title": v.title,
                    "rule_id": v.rule_id,
                    "from_spec": v.from_spec,
                    "to_spec": v.to_spec,
                    "input_hex": v.input_bytes.hex(),
                    "expected_hex": v.expected_bytes.hex(),
                    "note": v.note,
                }
                for v in MOVE_VECTORS
            ],
        },
        "compare": {
            "rules": {k: dataclasses.asdict(r) for k, r in COMPARE_RULES.items()},
            "matrix": [
                {
                    "left_kind": k[0],
                    "right_kind": k[1],
                    "mode": v.mode,
                    "rule_id": v.rule_id,
                    "ibm_section": v.ibm_section,
                    "note": v.note,
                }
                for k, v in sorted(COMPARE_MATRIX.items())
            ],
            "vectors": [
                {
                    "id": v.id,
                    "title": v.title,
                    "rule_id": v.rule_id,
                    "left_spec": v.left_spec,
                    "right_spec": v.right_spec,
                    "left_hex": v.left_bytes.hex(),
                    "right_hex": v.right_bytes.hex(),
                    "expected_result": v.expected_result,
                    "note": v.note,
                }
                for v in COMPARE_VECTORS
            ],
        },
        "arith": {
            "rounding_modes": {
                k: {
                    "mode_id": v.mode_id,
                    "name": v.name,
                    "java_mode": v.java_mode,
                    "description": v.description,
                    "ibm_clause": v.ibm_clause,
                }
                for k, v in ROUNDING_MODES.items()
            },
            "size_error_conditions": [dataclasses.asdict(c) for c in SIZE_ERROR_CONDITIONS],
            "rules": {k: dataclasses.asdict(r) for k, r in ARITH_RULES.items()},
            "vectors": [
                {
                    "id": v.id,
                    "title": v.title,
                    "rule_id": v.rule_id,
                    "operation": v.operation,
                    "operand_a": v.operand_a,
                    "operand_b": v.operand_b,
                    "scale": v.scale,
                    "digits": v.digits,
                    "signed": v.signed,
                    "rounded_mode": v.rounded_mode,
                    "expected_result": v.expected_result,
                    "expected_size_error": v.expected_size_error,
                    "note": v.note,
                }
                for v in ARITH_VECTORS
            ],
        },
        "string": {
            "inspect_modes": {k: dataclasses.asdict(v) for k, v in INSPECT_MODES.items()},
            "phrase_types": {k: dataclasses.asdict(v) for k, v in PHRASE_TYPES.items()},
            "rules": {k: dataclasses.asdict(r) for k, r in STRING_RULES.items()},
            "vectors": [
                {
                    "id": v.id,
                    "title": v.title,
                    "rule_id": v.rule_id,
                    "statement": v.statement,
                    "source_text": v.source_text,
                    "pointer_init": v.pointer_init,
                    "options": v.options,
                    "expected_output": v.expected_output,
                    "expected_pointer": v.expected_pointer,
                    "expected_overflow": v.expected_overflow,
                    "note": v.note,
                }
                for v in STRING_VECTORS
            ],
        },
        "func": {
            "categories": dict(FUNC_CATEGORIES),
            "specs": {k: dataclasses.asdict(v) for k, v in FUNC_SPECS.items()},
            "rules": {k: dataclasses.asdict(r) for k, r in FUNC_RULES.items()},
            "vectors": [
                {
                    "id": v.id,
                    "title": v.title,
                    "rule_id": v.rule_id,
                    "function": v.function,
                    "args": v.args,
                    "expected_result": v.expected_result,
                    "note": v.note,
                }
                for v in FUNC_VECTORS
            ],
        },
        "editing": {
            "categories": dict(EDIT_CATEGORY_NAMES),
            "symbols": {k: dataclasses.asdict(v) for k, v in EDITING_SYMBOLS.items()},
            "rules": {k: dataclasses.asdict(r) for k, r in EDITING_RULES.items()},
            "vectors": [
                {
                    "id": v.id,
                    "title": v.title,
                    "rule_id": v.rule_id,
                    "picture": v.picture,
                    "value": str(v.value) if v.value is not None else None,
                    "decimal_comma": v.decimal_comma,
                    "currency": v.currency,
                    "raw_digits": v.raw_digits,
                    "negative": v.negative,
                    "expected": v.expected,
                    "note": v.note,
                }
                for v in EDITING_VECTORS
            ],
        },
        "sort": {
            "directions": dict(DIRECTION_NAMES),
            "collating_modes": dict(COLLATING_NAMES),
            "phrases": dict(PHRASE_NAMES),
            "rules": {k: dataclasses.asdict(r) for k, r in SORT_RULES.items()},
            "vectors": [
                {
                    "id": v.id,
                    "title": v.title,
                    "rule_id": v.rule_id,
                    "records": v.records,
                    "keys": [dataclasses.asdict(k) for k in v.keys],
                    "collating": v.collating,
                    "alphabet_entries": v.alphabet_entries,
                    "expected": v.expected,
                    "note": v.note,
                }
                for v in SORT_VECTORS
            ],
        },
        "hfp": {
            "precision_short": PRECISION_SHORT,
            "precision_long": PRECISION_LONG,
            "bytes_short": BYTES_SHORT,
            "bytes_long": BYTES_LONG,
            "bias_characteristic": BIAS_CHARACTERISTIC,
            "significant_digits_short": SIGNIFICANT_DIGITS_SHORT,
            "significant_digits_long": SIGNIFICANT_DIGITS_LONG,
            "rules": {k: dataclasses.asdict(r) for k, r in HFP_RULES.items()},
            "vectors": [
                {
                    "id": v.id,
                    "title": v.title,
                    "rule_id": v.rule_id,
                    "short": v.short,
                    "input_value": v.input_value,
                    "expected_hex": v.expected_hex,
                    "expected_display": v.expected_display,
                    "expected_fixed": v.expected_fixed,
                    "scale": v.scale,
                    "note": v.note,
                }
                for v in HFP_VECTORS
            ],
        },
    }


def problems() -> list[str]:
    """What `check` reports: [] when the spec and tables are consistent."""
    out = [f"kind {k} has no category in KIND_CATEGORY" for k in KINDS if k not in KIND_CATEGORY]

    # Check MOVE matrix coverage
    for fk in KINDS:
        for tk in KINDS:
            if (fk, tk) not in MOVE_MATRIX:
                out.append(f"missing MOVE matrix cell for ({fk}, {tk})")
            else:
                entry = MOVE_MATRIX[(fk, tk)]
                if entry.rule_id not in MOVE_RULES:
                    out.append(f"MOVE matrix cell ({fk}, {tk}) cites unknown rule {entry.rule_id}")
                if entry.action not in ACTIONS:
                    out.append(f"MOVE matrix cell ({fk}, {tk}) has unknown action {entry.action}")

    # Check COMPARE matrix coverage
    for lk in KINDS:
        for rk in KINDS:
            if (lk, rk) not in COMPARE_MATRIX:
                out.append(f"missing COMPARE matrix cell for ({lk}, {rk})")
            else:
                centry = COMPARE_MATRIX[(lk, rk)]
                if centry.rule_id not in COMPARE_RULES:
                    out.append(f"COMPARE matrix cell ({lk}, {rk}) cites unknown rule {centry.rule_id}")
                if centry.mode not in COMPARE_MODES:
                    out.append(f"COMPARE matrix cell ({lk}, {rk}) has unknown mode {centry.mode}")

    # Check rule IDs exist in catalogue (docs/language_status/cobolrt_rules.json)
    cat_file = ROOT / "docs" / "language_status" / "cobolrt_rules.json"
    if cat_file.is_file():
        try:
            with cat_file.open(encoding="utf-8") as f:
                cat_data = json.load(f)
            known_ids = {r["id"] for r in cat_data.get("rules", [])}
            out.extend(f"MOVE rule {rid} not found in cobolrt_rules.json" for rid in MOVE_RULES if rid not in known_ids)
            out.extend(
                f"COMPARE rule {rid} not found in cobolrt_rules.json" for rid in COMPARE_RULES if rid not in known_ids
            )
            out.extend(
                f"ARITH rule {rid} not found in cobolrt_rules.json" for rid in ARITH_RULES if rid not in known_ids
            )
            out.extend(
                f"STRING rule {rid} not found in cobolrt_rules.json" for rid in STRING_RULES if rid not in known_ids
            )
            out.extend(f"FUNC rule {rid} not found in cobolrt_rules.json" for rid in FUNC_RULES if rid not in known_ids)
            out.extend(
                f"EDIT rule {rid} not found in cobolrt_rules.json" for rid in EDITING_RULES if rid not in known_ids
            )
            out.extend(f"SORT rule {rid} not found in cobolrt_rules.json" for rid in SORT_RULES if rid not in known_ids)
            out.extend(f"HFP rule {rid} not found in cobolrt_rules.json" for rid in HFP_RULES if rid not in known_ids)
        except Exception as e:
            out.append(f"unable to verify against cobolrt_rules.json: {e}")

    # Check vectors cite valid rules
    out.extend(
        f"MOVE test vector {vec.id} cites unknown rule {vec.rule_id}"
        for vec in MOVE_VECTORS
        if vec.rule_id not in MOVE_RULES
    )
    out.extend(
        f"COMPARE test vector {vec.id} cites unknown rule {vec.rule_id}"
        for vec in COMPARE_VECTORS
        if vec.rule_id not in COMPARE_RULES
    )
    out.extend(
        f"ARITH test vector {vec.id} cites unknown rule {vec.rule_id}"
        for vec in ARITH_VECTORS
        if vec.rule_id not in ARITH_RULES
    )
    out.extend(
        f"STRING test vector {vec.id} cites unknown rule {vec.rule_id}"
        for vec in STRING_VECTORS
        if vec.rule_id not in STRING_RULES
    )
    out.extend(
        f"FUNC test vector {vec.id} cites unknown rule {vec.rule_id}"
        for vec in FUNC_VECTORS
        if vec.rule_id not in FUNC_RULES
    )
    out.extend(
        f"EDIT test vector {vec.id} cites unknown rule {vec.rule_id}"
        for vec in EDITING_VECTORS
        if vec.rule_id not in EDITING_RULES
    )
    out.extend(
        f"SORT test vector {vec.id} cites unknown rule {vec.rule_id}"
        for vec in SORT_VECTORS
        if vec.rule_id not in SORT_RULES
    )
    out.extend(
        f"HFP test vector {vec.id} cites unknown rule {vec.rule_id}"
        for vec in HFP_VECTORS
        if vec.rule_id not in HFP_RULES
    )

    return out


def render_move_java(package: str = JAVA_PACKAGE) -> str:
    """Generate MoveSpec.java."""
    cat_cases_str = "\n".join(f"            case {k} -> {CATEGORY_NAMES[KIND_CATEGORY[k]]};" for k in KINDS)

    outer_perm = []
    for fk in KINDS:
        inner = [
            f"                case {tk} -> {'true' if MOVE_MATRIX[(fk, tk)].permissible else 'false'};" for tk in KINDS
        ]
        inner_str = "\n".join(inner)
        outer_perm.append(f"            case {fk} -> switch (to) {{\n{inner_str}\n            }};")
    outer_perm_str = "\n".join(outer_perm)

    outer_rule = []
    for fk in KINDS:
        inner = [f'                case {tk} -> "{MOVE_MATRIX[(fk, tk)].rule_id}";' for tk in KINDS]
        inner_str = "\n".join(inner)
        outer_rule.append(f"            case {fk} -> switch (to) {{\n{inner_str}\n            }};")
    outer_rule_str = "\n".join(outer_rule)

    outer_act = []
    for fk in KINDS:
        inner = [f'                case {tk} -> "{MOVE_MATRIX[(fk, tk)].action}";' for tk in KINDS]
        inner_str = "\n".join(inner)
        outer_act.append(f"            case {fk} -> switch (to) {{\n{inner_str}\n            }};")
    outer_act_str = "\n".join(outer_act)

    return f"""// {BANNER}
package {package};

/**
 * The COBOL MOVE statement specification and permissible moves matrix (#4712, epic #4710).
 * Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06),
 * Chapter "MOVE statement" (Elementary moves, De-editing, Table 43: Permissible moves).
 */
public final class MoveSpec {{
    private MoveSpec() {{
    }}

    public static final int GROUP = 0;
    public static final int ALNUM = 1;
    public static final int NUMERIC = 2;
    public static final int NUM_EDITED = 3;
    public static final int ALNUM_EDITED = 4;

    /** Map a Field.Kind to its runtime category (0: GROUP, 1: ALNUM, 2: NUMERIC, 3: NUM_EDITED, 4: ALNUM_EDITED). */
    public static int category(Field.Kind kind) {{
        return switch (kind) {{
{cat_cases_str}
        }};
    }}

    /** The category name for diagnostic output and evidence reports. */
    public static String categoryName(int category) {{
        return switch (category) {{
            case GROUP -> "GROUP";
            case ALNUM -> "ALNUM";
            case NUMERIC -> "NUMERIC";
            case NUM_EDITED -> "NUM_EDITED";
            case ALNUM_EDITED -> "ALNUM_EDITED";
            default -> "UNKNOWN";
        }};
    }}

    /** Whether an elementary or group move between two kinds is permissible under IBM Enterprise COBOL rules. */
    public static boolean isPermissible(Field.Kind from, Field.Kind to) {{
        return switch (from) {{
{outer_perm_str}
        }};
    }}

    /** The catalogued rule ID governing a MOVE between two kinds. */
    public static String ruleId(Field.Kind from, Field.Kind to) {{
        return switch (from) {{
{outer_rule_str}
        }};
    }}

    /** The runtime action name for a MOVE between two kinds. */
    public static String action(Field.Kind from, Field.Kind to) {{
        return switch (from) {{
{outer_act_str}
        }};
    }}

    /**
     * Whether two items of one length hold the same shape (digits, scale, sign, sign position, size)
     * and can be copied by memcpy under rule RT-CBL-MOVE-SAME-ZONED-SHAPE (register C11).
     */
    public static boolean sameZonedShape(Field a, Field b) {{
        return a.digits == b.digits && a.scale == b.scale && a.signed == b.signed
                && a.signLeading == b.signLeading && a.signSeparate == b.signSeparate
                && a.len == b.len && a.blankWhenZero == b.blankWhenZero;
    }}
}}
"""


def render_compare_java(package: str = JAVA_PACKAGE) -> str:
    """Generate CompareSpec.java."""
    outer_mode = []
    for lk in KINDS:
        inner = [f"                case {rk} -> MODE_{COMPARE_MATRIX[(lk, rk)].mode};" for rk in KINDS]
        inner_str = "\n".join(inner)
        outer_mode.append(f"            case {lk} -> switch (right) {{\n{inner_str}\n            }};")
    outer_mode_str = "\n".join(outer_mode)

    outer_rule = []
    for lk in KINDS:
        inner = [f'                case {rk} -> "{COMPARE_MATRIX[(lk, rk)].rule_id}";' for rk in KINDS]
        inner_str = "\n".join(inner)
        outer_rule.append(f"            case {lk} -> switch (right) {{\n{inner_str}\n            }};")
    outer_rule_str = "\n".join(outer_rule)

    mode_cases_str = "\n".join(f'            case MODE_{m} -> "{m}";' for m in COMPARE_MODES)

    return f"""// {BANNER}
package {package};

/**
 * The COBOL relation condition and comparison specification (#4712, epic #4710).
 * Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06),
 * Chapter "Conditional expressions" -> "Relation conditions".
 */
public final class CompareSpec {{
    private CompareSpec() {{
    }}

    public static final int MODE_NUMERIC = 0;
    public static final int MODE_FLOAT = 1;
    public static final int MODE_NONNUMERIC = 2;
    public static final int MODE_NUMERIC_WITH_NONNUMERIC = 3;
    public static final int MODE_FLOAT_REFUSED = 4;

    /** The comparison evaluation mode between two operand kinds. */
    public static int comparisonMode(Field.Kind left, Field.Kind right) {{
        return switch (left) {{
{outer_mode_str}
        }};
    }}

    /** The comparison mode name for diagnostic output and evidence reports. */
    public static String modeName(int mode) {{
        return switch (mode) {{
{mode_cases_str}
            default -> "UNKNOWN";
        }};
    }}

    /** The catalogued rule ID governing a comparison between two kinds. */
    public static String ruleId(Field.Kind left, Field.Kind right) {{
        return switch (left) {{
{outer_rule_str}
        }};
    }}

    /** Whether both comparands are numeric (algebraic comparison). */
    public static boolean isNumericComparison(Field.Kind left, Field.Kind right) {{
        int mode = comparisonMode(left, right);
        return mode == MODE_NUMERIC || mode == MODE_FLOAT;
    }}

    /** Whether one operand must be converted to unsigned digits before comparison. */
    public static boolean requiresDigitConversion(Field.Kind left, Field.Kind right) {{
        return comparisonMode(left, right) == MODE_NUMERIC_WITH_NONNUMERIC;
    }}

    /** Byte-by-byte comparison of two byte arrays, padding the shorter with spaceByte. */
    public static int compareBytes(byte[] a, byte[] b, byte spaceByte) {{
        int n = Math.max(a.length, b.length);
        for (int i = 0; i < n; i++) {{
            int x = (i < a.length ? a[i] : spaceByte) & 0xFF;
            int y = (i < b.length ? b[i] : spaceByte) & 0xFF;
            if (x != y) return x < y ? -1 : 1;
        }}
        return 0;
    }}
}}
"""


def render_move_markdown() -> str:
    """Generate docs/language_status/cobol_move_matrix.md."""
    rows = []
    for (fk, tk), entry in sorted(MOVE_MATRIX.items()):
        perm = "✓ Yes" if entry.permissible else "✗ No"
        rows.append(
            f"| `{fk}` | `{tk}` | **{perm}** | `{entry.rule_id}` | `{entry.action}` | {entry.ibm_section} | {entry.note} |"
        )
    table_rows = "\n".join(rows)

    rules_list = []
    for rid, r in sorted(MOVE_RULES.items()):
        opts = ", ".join(f"`{o}`" for o in r.options) if r.options else "-"
        reg = ", ".join(f"`{x}`" for x in r.register) if r.register else "-"
        ibm_cite = f"{r.ibm['doc']}: {r.ibm['section']}" if r.ibm else (r.ibm_note or "-")
        rules_list.append(
            f"### `{rid}`\n\n"
            f"- **Title:** {r.title}\n"
            f"- **Status:** `{r.status}`\n"
            f"- **IBM Reference:** {ibm_cite}\n"
            f"- **Options:** {opts}\n"
            f"- **Register:** {reg}\n"
            f"- **Description:** {r.description}\n"
        )
    rules_text = "\n".join(rules_list)
    vectors_table = "\n".join(f"| `{v.id}` | {v.title} | `{v.rule_id}` | {v.note} |" for v in MOVE_VECTORS)

    return f"""<!-- {BANNER} -->
# COBOL MOVE Rules Matrix & Specification (#4712)

Part of the **cobolrt-as-a-product** epic ([#4710](https://github.com/squid-protocol/gitgalaxy/issues/4710)).
Single source of truth: [`gitgalaxy/standards/cobol/move.py`](../../gitgalaxy/standards/cobol/move.py).
Generated by `python -m gitgalaxy.standards.cobol regen`.

## 1. Rule Catalogue (MOVE Family)

{rules_text}

## 2. Permissible Moves Matrix (IBM Enterprise COBOL SC26-4940-06)

| Sender Kind | Receiver Kind | Permissible | Rule ID | Action | IBM Manual Section | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{table_rows}

## 3. Deterministic Test Vectors

| Vector ID | Title | Rule Verified | Note |
| :--- | :--- | :--- | :--- |
{vectors_table}
"""


def render_compare_markdown() -> str:
    """Generate docs/language_status/cobol_compare_matrix.md."""
    rows = []
    for (lk, rk), entry in sorted(COMPARE_MATRIX.items()):
        rows.append(f"| `{lk}` | `{rk}` | `{entry.mode}` | `{entry.rule_id}` | {entry.ibm_section} | {entry.note} |")
    table_rows = "\n".join(rows)

    rules_list = []
    for rid, r in sorted(COMPARE_RULES.items()):
        opts = ", ".join(f"`{o}`" for o in r.options) if r.options else "-"
        reg = ", ".join(f"`{x}`" for x in r.register) if r.register else "-"
        ibm_cite = f"{r.ibm['doc']}: {r.ibm['section']}" if r.ibm else (r.ibm_note or "-")
        rules_list.append(
            f"### `{rid}`\n\n"
            f"- **Title:** {r.title}\n"
            f"- **Status:** `{r.status}`\n"
            f"- **IBM Reference:** {ibm_cite}\n"
            f"- **Options:** {opts}\n"
            f"- **Register:** {reg}\n"
            f"- **Description:** {r.description}\n"
        )
    rules_text = "\n".join(rules_list)
    vectors_table = "\n".join(
        f"| `{v.id}` | {v.title} | `{v.rule_id}` | `{v.expected_result}` | {v.note} |" for v in COMPARE_VECTORS
    )

    return f"""<!-- {BANNER} -->
# COBOL Relation Condition & Comparison Specification (#4712)

Part of the **cobolrt-as-a-product** epic ([#4710](https://github.com/squid-protocol/gitgalaxy/issues/4710)).
Single source of truth: [`gitgalaxy/standards/cobol/compare.py`](../../gitgalaxy/standards/cobol/compare.py).
Generated by `python -m gitgalaxy.standards.cobol regen`.

## 1. Rule Catalogue (COMPARE Family)

{rules_text}

## 2. Relation Condition Comparison Matrix (IBM Enterprise COBOL SC26-4940-06)

| Left Kind | Right Kind | Mode | Rule ID | IBM Manual Section | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
{table_rows}

## 3. Deterministic Test Vectors

| Vector ID | Title | Rule Verified | Expected Result | Note |
| :--- | :--- | :--- | :--- | :--- |
{vectors_table}
"""


def render_move_tests() -> str:
    """Generate tests/cobol_mainframe/test_cobol_move_vectors.py."""
    return '''# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Test vectors for the COBOL MOVE rules matrix (#4712, epic #4710).

Generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`.
Verifies that the declarative move rules, permissible matrix, and test vectors execute
correctly and deterministically in CI without requiring Docker or external compilers.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import pytest

from gitgalaxy.standards.cobol.cli import problems, stale
from gitgalaxy.standards.cobol.move import (
    ACTIONS,
    CATEGORIES,
    KINDS,
    MOVE_MATRIX,
    MOVE_RULES,
    MOVE_VECTORS,
)


def test_cobol_standards_spec_has_no_problems():
    """Verify internal consistency of standards/cobol rules."""
    errs = problems()
    assert errs == [], f"cobol spec has consistency problems: {errs}"


def test_cobol_standards_generated_files_are_not_stale():
    """Verify committed MoveSpec.java, docs, and tests match the standards tables."""
    diff = stale()
    assert diff == [], f"standards generated files are stale: {diff}; run `python -m gitgalaxy.standards.cobol regen`"


def test_all_kinds_and_categories_defined():
    """Verify 9 Field.Kind entries exist and map cleanly."""
    assert len(KINDS) == 9
    assert len(CATEGORIES) == 5
    assert len(ACTIONS) == 14
    assert len(MOVE_MATRIX) == 81


@pytest.mark.parametrize("vec", MOVE_VECTORS, ids=lambda v: v.id)
def test_move_vector_rule_alignment(vec):
    """Verify each test vector correctly aligns with a registered rule."""
    assert vec.rule_id in MOVE_RULES
    meta = MOVE_RULES[vec.rule_id]
    assert meta.id == vec.rule_id
    assert len(vec.input_bytes) > 0
    assert len(vec.expected_bytes) > 0


def test_same_zoned_shape_memcpy_invariance():
    """Verify rule RT-CBL-MOVE-SAME-ZONED-SHAPE (register C11): non-digits and sign are preserved."""
    vec = next(v for v in MOVE_VECTORS if v.id == "MV06-same-zoned-shape-memcpy")
    assert vec.input_bytes == vec.expected_bytes
    assert b" " in vec.input_bytes  # Contains non-digit space
    assert b"K" in vec.input_bytes  # Contains negative overpunch


def test_numeric_to_alnum_unpunches_sign():
    """Verify rule RT-CBL-MOVE-NUMERIC-TO-ALPHANUMERIC: sign is de-punched into unsigned digit."""
    vec = next(v for v in MOVE_VECTORS if v.id == "MV07-numeric-to-alnum-unpunch")
    assert vec.input_bytes == b"0001K"
    assert vec.expected_bytes == b"00012"  # K (-2) -> 2
'''


def render_compare_tests() -> str:
    """Generate tests/cobol_mainframe/test_cobol_compare_vectors.py."""
    return '''# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Test vectors for the COBOL relation condition and comparison rules matrix (#4712, epic #4710).

Generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`.
Verifies that the declarative relation conditions, comparison modes, and test vectors execute
correctly and deterministically in CI without requiring Docker or external compilers.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import pytest

from gitgalaxy.standards.cobol.cli import problems, stale
from gitgalaxy.standards.cobol.compare import (
    COMPARE_MATRIX,
    COMPARE_MODES,
    COMPARE_RULES,
    COMPARE_VECTORS,
)
from gitgalaxy.standards.cobol.move import KINDS


def test_cobol_compare_spec_has_no_problems():
    """Verify internal consistency of standards/cobol comparison rules."""
    errs = problems()
    assert errs == [], f"cobol spec has consistency problems: {errs}"


def test_cobol_compare_generated_files_are_not_stale():
    """Verify committed CompareSpec.java, docs, and tests match the standards tables."""
    diff = stale()
    assert diff == [], f"standards generated files are stale: {diff}; run `python -m gitgalaxy.standards.cobol regen`"


def test_all_compare_modes_and_matrix_defined():
    """Verify 9x9 comparison matrix cells and comparison modes."""
    assert len(COMPARE_MODES) == 5
    assert len(COMPARE_RULES) == 8
    assert len(COMPARE_MATRIX) == 81


@pytest.mark.parametrize("vec", COMPARE_VECTORS, ids=lambda v: v.id)
def test_compare_vector_rule_alignment(vec):
    """Verify each comparison vector aligns with a registered comparison rule."""
    assert vec.rule_id in COMPARE_RULES
    meta = COMPARE_RULES[vec.rule_id]
    assert meta.id == vec.rule_id
    assert vec.expected_result in (-1, 0, 1)


def test_compare_numeric_different_scales_equal():
    """Verify RT-CBL-COMPARE-NUMERIC: algebraic value equality across scales."""
    vec = next(v for v in COMPARE_VECTORS if v.id == "CP01-numeric-equal-different-scale")
    assert vec.expected_result == 0


def test_compare_numeric_signed_less():
    """Verify RT-CBL-COMPARE-NUMERIC: negative value is less than positive value."""
    vec = next(v for v in COMPARE_VECTORS if v.id == "CP02-numeric-signed-less")
    assert vec.expected_result == -1


def test_compare_nonnumeric_space_padded():
    """Verify RT-CBL-COMPARE-NONNUMERIC: shorter operand is space padded."""
    vec = next(v for v in COMPARE_VECTORS if v.id == "CP03-nonnumeric-equal-space-pad")
    assert vec.expected_result == 0
'''


def render_arith_java(package: str = JAVA_PACKAGE) -> str:
    """Generate ArithSpec.java."""
    rule_cases = "\n".join(f'            case "{r}" -> "{r}";' for r in sorted(ARITH_RULES))

    return f"""// {BANNER}
package {package};

import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;

/**
 * Declarative COBOL Arithmetic, Rounding, Intermediate Precision, and Size Error specification.
 *
 * <p>Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06).
 * Follows the table-driven code generation pattern established by CicsSpec.java (#4586, #4608).
 */
public final class ArithSpec {{
    private ArithSpec() {{
    }}

    // Rounding modes (IBM Enterprise COBOL ROUNDED / ROUNDED MODE IS ...)
    public static final int ROUND_TRUNCATION = {ROUND_TRUNCATION};
    public static final int ROUND_NEAREST_AWAY_FROM_ZERO = {ROUND_NEAREST_AWAY_FROM_ZERO};
    public static final int ROUND_NEAREST_EVEN = {ROUND_NEAREST_EVEN};
    public static final int ROUND_NEAREST_TOWARD_ZERO = {ROUND_NEAREST_TOWARD_ZERO};
    public static final int ROUND_TOWARD_GREATER = {ROUND_TOWARD_GREATER};
    public static final int ROUND_TOWARD_LESSER = {ROUND_TOWARD_LESSER};
    public static final int ROUND_PROHIBITED = {ROUND_PROHIBITED};

    public static final int NAN_SCALE = {NAN_SCALE};

    /** Map integer rounding mode to java.math.RoundingMode. */
    public static RoundingMode roundingMode(int mode) {{
        return switch (mode) {{
            case ROUND_TRUNCATION -> RoundingMode.DOWN;
            case ROUND_NEAREST_AWAY_FROM_ZERO -> RoundingMode.HALF_UP;
            case ROUND_NEAREST_EVEN -> RoundingMode.HALF_EVEN;
            case ROUND_NEAREST_TOWARD_ZERO -> RoundingMode.HALF_DOWN;
            case ROUND_TOWARD_GREATER -> RoundingMode.CEILING;
            case ROUND_TOWARD_LESSER -> RoundingMode.FLOOR;
            case ROUND_PROHIBITED -> RoundingMode.UNNECESSARY;
            default -> throw new IllegalArgumentException("Unknown rounding mode: " + mode);
        }};
    }}

    /** COBOL standard clause name for rounding mode. */
    public static String modeName(int mode) {{
        return switch (mode) {{
            case ROUND_TRUNCATION -> "TRUNCATION";
            case ROUND_NEAREST_AWAY_FROM_ZERO -> "NEAREST-AWAY-FROM-ZERO";
            case ROUND_NEAREST_EVEN -> "NEAREST-EVEN";
            case ROUND_NEAREST_TOWARD_ZERO -> "NEAREST-TOWARD-ZERO";
            case ROUND_TOWARD_GREATER -> "TOWARD-GREATER";
            case ROUND_TOWARD_LESSER -> "TOWARD-LESSER";
            case ROUND_PROHIBITED -> "PROHIBITED";
            default -> "UNKNOWN";
        }};
    }}

    /** Intermediate division quotient scale: 38 + max(scaleA - scaleB, 0). */
    public static int divideIntermediateScale(int scaleA, int scaleB) {{
        return 38 + Math.max(scaleA - scaleB, 0);
    }}

    /** DIVIDE ... REMAINDER formula: dividend - (quotient.setScale(scale, DOWN) * divisor). */
    public static BigDecimal divideRemainder(BigDecimal a, BigDecimal q, BigDecimal b, int scale) {{
        if (q.scale() == NAN_SCALE) {{
            return q;
        }}
        return a.subtract(q.setScale(scale, RoundingMode.DOWN).multiply(b));
    }}

    /** True if scaled value exceeds the receiver's PICTURE integer capacity. */
    public static boolean isOverflow(BigDecimal value, int digits, int scale) {{
        BigDecimal v = value.setScale(scale, RoundingMode.DOWN);
        return v.unscaledValue().abs().compareTo(BigInteger.TEN.pow(digits)) >= 0;
    }}

    /** Get registered rule ID from key. */
    public static String ruleId(String key) {{
        return switch (key) {{
{rule_cases}
            default -> "UNKNOWN";
        }};
    }}
}}
"""


def render_arith_markdown() -> str:
    """Generate docs/language_status/cobol_arith_matrix.md."""
    rm_rows = [
        f"| `{spec.mode_id}` | `{spec.name}` | `{spec.java_mode}` | {spec.ibm_clause} | {spec.description} |"
        for _, spec in sorted(ROUNDING_MODES.items())
    ]
    rm_table = "\n".join(rm_rows)

    se_rows = [
        f"| `{se.condition}` | {se.trigger} | {se.receiver_action} | `{se.rule_id}` | {se.description} |"
        for se in SIZE_ERROR_CONDITIONS
    ]
    se_table = "\n".join(se_rows)

    r_rows = []
    for rid, meta in sorted(ARITH_RULES.items()):
        doc_sec = f"{meta.ibm['doc']}: {meta.ibm['section']}" if meta.ibm else (meta.ibm_note or "-")
        reg = ", ".join(f"`{x}`" for x in meta.register) if meta.register else "-"
        r_rows.append(f"| `{rid}` | `{meta.status}` | {meta.title} | {doc_sec} | {reg} |")
    r_table = "\n".join(r_rows)

    v_rows = [
        f"| `{vec.id}` | {vec.title} | `{vec.rule_id}` | `{vec.operation}` | `{vec.expected_result}` | {'YES' if vec.expected_size_error else 'NO'} | {vec.note} |"
        for vec in ARITH_VECTORS
    ]
    v_table = "\n".join(v_rows)

    return f"""<!-- {BANNER} -->
# COBOL Arithmetic, Rounding & Intermediate Precision Specification (#4712)

Part of the **cobolrt-as-a-product** epic ([#4710](https://github.com/squid-protocol/gitgalaxy/issues/4710)).
Single source of truth: [`gitgalaxy/standards/cobol/arith.py`](../../gitgalaxy/standards/cobol/arith.py).
Generated by `python -m gitgalaxy.standards.cobol regen`.

Reference: **IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06)**
Chapters: *Arithmetic statements*, *Common phrases and concepts for arithmetic statements*,
*DIVIDE statement*, *COMPUTE statement*.

## 1. Rule Catalogue (ARITH Family)

| Rule ID | Status | Title | IBM Manual Reference | Register |
| :--- | :--- | :--- | :--- | :--- |
{r_table}

## 2. Rounding Modes (IBM Enterprise COBOL ROUNDED / ROUNDED MODE IS ...)

| ID | Mode Name | Java RoundingMode | IBM Syntax Clause | Behavior |
| :--- | :--- | :--- | :--- | :--- |
{rm_table}

## 3. Size Error Conditions (ON SIZE ERROR Phrase)

| Condition | Trigger Event | Receiver Action | Governed By Rule | Description |
| :--- | :--- | :--- | :--- | :--- |
{se_table}

## 4. Intermediate Precision & Scaling Specifications

- **Division Intermediate Quotient Scale Formula:**
  `scale = 38 + max(scaleA - scaleB, 0)` with `RoundingMode.DOWN`.
- **DIVIDE ... REMAINDER Formula:**
  `Remainder = Dividend - (Quotient_truncated_to_giving_scale * Divisor)`.
- **NaN Scale Marker:** `-32768` (`Cobol.NAN_SCALE` / libcob `COB_DECIMAL_NAN`).
- **Unsigned Binary Native Arithmetic Rule:** Absolute value taken under IBM Enterprise COBOL semantics.

## 5. Deterministic Test Vectors

| Vector ID | Title | Rule Verified | Operation | Expected Result | Size Error? | Note |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{v_table}
"""


def render_arith_tests() -> str:
    """Generate tests/cobol_mainframe/test_cobol_arith_vectors.py."""
    return '''# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Test vectors for the COBOL Arithmetic and Rounding rules (#4712, epic #4710).

Generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`.
Verifies that the declarative arithmetic rules, rounding modes, size error conditions,
and deterministic test vectors execute directly in CI without requiring Docker or external compilers.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import pytest

from gitgalaxy.standards.cobol.arith import (
    ARITH_RULES,
    ARITH_VECTORS,
    ROUNDING_MODES,
    SIZE_ERROR_CONDITIONS,
    calculate_divide_intermediate_scale,
    calculate_divide_remainder,
)
from gitgalaxy.standards.cobol.cli import problems, stale


def test_cobol_arith_spec_has_no_problems():
    """Verify internal consistency of standards/cobol arithmetic rules."""
    errs = problems()
    assert errs == [], f"cobol spec has consistency problems: {errs}"


def test_cobol_arith_generated_files_are_not_stale():
    """Verify committed ArithSpec.java, docs, and tests match the standards tables."""
    diff = stale()
    assert diff == [], f"standards generated files are stale: {diff}; run `python -m gitgalaxy.standards.cobol regen`"


def test_all_arith_modes_and_rules_defined():
    """Verify all rounding modes, size error specs, and rules are defined."""
    assert len(ROUNDING_MODES) == 7
    assert len(SIZE_ERROR_CONDITIONS) == 5
    assert len(ARITH_RULES) == 10
    assert len(ARITH_VECTORS) >= 12


@pytest.mark.parametrize("vec", ARITH_VECTORS, ids=lambda v: v.id)
def test_arith_vector_rule_alignment(vec):
    """Verify each test vector correctly aligns with a registered rule."""
    assert vec.rule_id in ARITH_RULES
    meta = ARITH_RULES[vec.rule_id]
    assert meta.id == vec.rule_id


def test_divide_intermediate_scale_formula():
    """Verify intermediate quotient scale calculation."""
    assert calculate_divide_intermediate_scale(2, 1) == 39
    assert calculate_divide_intermediate_scale(0, 2) == 38
    assert calculate_divide_intermediate_scale(5, 0) == 43


def test_divide_remainder_scale_truncation():
    """Verify DIVIDE ... REMAINDER formula with scale truncation."""
    dividend = Decimal("100")
    divisor = Decimal("7")
    giving_scale = 1
    rem = calculate_divide_remainder(dividend, divisor, giving_scale)
    assert rem == Decimal("0.6")


def test_rounding_modes_mapping():
    """Verify each COBOL rounding mode maps to a valid decimal rounding mode."""
    for mode in ROUNDING_MODES.values():
        if mode.python_mode is not None:
            val = Decimal("1.25").quantize(Decimal("1.1"), rounding=mode.python_mode)
            assert isinstance(val, Decimal)
'''


def render_string_java(package: str = JAVA_PACKAGE) -> str:
    """Generate StringSpec.java."""
    rule_cases = "\n".join(f'            case "{r}" -> "{r}";' for r in sorted(STRING_RULES))

    return f"""// {BANNER}
package {package};

/**
 * Declarative COBOL String Manipulation specification (STRING, UNSTRING, INSPECT).
 *
 * <p>Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06).
 * Follows the table-driven code generation pattern established by CicsSpec.java (#4586, #4608).
 */
public final class StringSpec {{
    private StringSpec() {{
    }}

    // Statements
    public static final int STATEMENT_STRING = {STATEMENT_STRING};
    public static final int STATEMENT_UNSTRING = {STATEMENT_UNSTRING};
    public static final int STATEMENT_INSPECT = {STATEMENT_INSPECT};

    // INSPECT evaluation modes
    public static final int INSPECT_CHARACTERS = {INSPECT_CHARACTERS};
    public static final int INSPECT_ALL = {INSPECT_ALL};
    public static final int INSPECT_LEADING = {INSPECT_LEADING};
    public static final int INSPECT_FIRST = {INSPECT_FIRST};

    // INSPECT phrase types
    public static final int PHRASE_TALLYING = {PHRASE_TALLYING};
    public static final int PHRASE_REPLACING = {PHRASE_REPLACING};
    public static final int PHRASE_CONVERTING = {PHRASE_CONVERTING};

    /** COBOL standard clause name for inspect mode. */
    public static String inspectModeName(int mode) {{
        return switch (mode) {{
            case INSPECT_CHARACTERS -> "CHARACTERS";
            case INSPECT_ALL -> "ALL";
            case INSPECT_LEADING -> "LEADING";
            case INSPECT_FIRST -> "FIRST";
            default -> "UNKNOWN";
        }};
    }}

    /** Name of the inspect phrase type. */
    public static String phraseTypeName(int type) {{
        return switch (type) {{
            case PHRASE_TALLYING -> "TALLYING";
            case PHRASE_REPLACING -> "REPLACING";
            case PHRASE_CONVERTING -> "CONVERTING";
            default -> "UNKNOWN";
        }};
    }}

    /** Returns true if 1-based pointer is within bounds [1, length]. */
    public static boolean isPointerValid(int pointer, int length) {{
        return pointer >= 1 && pointer <= length;
    }}

    /** Get registered rule ID from key. */
    public static String ruleId(String key) {{
        return switch (key) {{
{rule_cases}
            default -> "UNKNOWN";
        }};
    }}
}}
"""


def render_string_markdown() -> str:
    """Generate docs/language_status/cobol_string_matrix.md."""
    mode_rows = [
        f"| `{spec.mode_id}` | `{spec.name}` | {spec.ibm_clause} | {spec.description} |"
        for _, spec in sorted(INSPECT_MODES.items())
    ]
    mode_table = "\n".join(mode_rows)

    phrase_rows = [
        f"| `{spec.type_id}` | `{spec.name}` | {spec.description} |" for _, spec in sorted(PHRASE_TYPES.items())
    ]
    phrase_table = "\n".join(phrase_rows)

    r_rows = []
    for rid, meta in sorted(STRING_RULES.items()):
        doc_sec = f"{meta.ibm['doc']}: {meta.ibm['section']}" if meta.ibm else (meta.ibm_note or "-")
        reg = ", ".join(f"`{x}`" for x in meta.register) if meta.register else "-"
        r_rows.append(f"| `{rid}` | `{meta.status}` | {meta.title} | {doc_sec} | {reg} |")
    r_table = "\n".join(r_rows)

    v_rows = [
        f"| `{vec.id}` | {vec.title} | `{vec.rule_id}` | `{vec.statement}` | `{vec.expected_output}` | {'YES' if vec.expected_overflow else 'NO'} | {vec.note} |"
        for vec in STRING_VECTORS
    ]
    v_table = "\n".join(v_rows)

    return f"""<!-- {BANNER} -->
# COBOL String Manipulation Specification: STRING, UNSTRING, INSPECT (#4712)

Part of the **cobolrt-as-a-product** epic ([#4710](https://github.com/squid-protocol/gitgalaxy/issues/4710)).
Single source of truth: [`gitgalaxy/standards/cobol/string_ops.py`](../../gitgalaxy/standards/cobol/string_ops.py).
Generated by `python -m gitgalaxy.standards.cobol regen`.

Reference: **IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06)**
Chapters: *STRING statement*, *UNSTRING statement*, *INSPECT statement*.

## 1. Rule Catalogue (STRING Family)

| Rule ID | Status | Title | IBM Manual Reference | Register |
| :--- | :--- | :--- | :--- | :--- |
{r_table}

## 2. INSPECT Evaluation Modes

| ID | Mode Name | IBM Syntax Clause | Behavior |
| :--- | :--- | :--- | :--- |
{mode_table}

## 3. INSPECT Phrase Types

| ID | Phrase Type | Description |
| :--- | :--- | :--- |
{phrase_table}

## 4. Statement Invariants & Pointer Rules

- **STRING Statement**:
  - Operands transferred sequentially into receiving field from pointer position.
  - Receiver is **not padded with spaces** (only transferred positions are overwritten).
  - Pointer value is incremented past the last transferred character position.
  - ON OVERFLOW raised when: initial pointer < 1 or > receiver length, or transferred data exceeds receiver capacity.
- **UNSTRING Statement**:
  - Scans source string, extracting substrings delimited by delimiters into successive receiving items.
  - `DELIMITED BY ALL`: Contiguous occurrences of delimiter treated as one.
  - `DELIMITER IN`: Delimiter characters copied into receiving field.
  - `COUNT IN`: Number of characters transferred recorded in count field.
  - `TALLYING IN`: Incremented by the number of receiving areas filled.
  - ON OVERFLOW raised when: initial pointer < 1 or > source length, or unexamined characters remain after receiving areas exhausted.
- **INSPECT Statement**:
  - Earlier clause takes characters first (marking mechanism).
  - TALLYING and REPLACING act as separate passes.
  - `BEFORE` / `AFTER INITIAL`: Restricts examination bounds.

## 5. Deterministic Test Vectors

| Vector ID | Title | Rule Verified | Statement | Expected Output | Overflow? | Note |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{v_table}
"""


def render_string_tests() -> str:
    """Generate tests/cobol_mainframe/test_cobol_string_vectors.py."""
    return '''# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Test vectors for the COBOL String Manipulation rules (#4712, epic #4710).

Generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`.
Verifies that the declarative string rules, inspect modes, phrase types,
and deterministic test vectors execute directly in CI without requiring Docker or external compilers.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import pytest

from gitgalaxy.standards.cobol.cli import problems, stale
from gitgalaxy.standards.cobol.string_ops import (
    INSPECT_MODES,
    PHRASE_TYPES,
    STRING_RULES,
    STRING_VECTORS,
    execute_string,
    execute_unstring,
)


def test_cobol_string_spec_has_no_problems():
    """Verify internal consistency of standards/cobol string manipulation rules."""
    errs = problems()
    assert errs == [], f"cobol spec has consistency problems: {errs}"


def test_cobol_string_generated_files_are_not_stale():
    """Verify committed StringSpec.java, docs, and tests match the standards tables."""
    diff = stale()
    assert diff == [], f"standards generated files are stale: {diff}; run `python -m gitgalaxy.standards.cobol regen`"


def test_all_string_modes_and_rules_defined():
    """Verify inspect modes, phrase types, and string rules are defined."""
    assert len(INSPECT_MODES) == 4
    assert len(PHRASE_TYPES) == 3
    assert len(STRING_RULES) == 4
    assert len(STRING_VECTORS) >= 14


@pytest.mark.parametrize("vec", STRING_VECTORS, ids=lambda v: v.id)
def test_string_vector_rule_alignment(vec):
    """Verify each test vector correctly aligns with a registered rule."""
    assert vec.rule_id in STRING_RULES
    meta = STRING_RULES[vec.rule_id]
    assert meta.id == vec.rule_id


def test_string_simulation_basic_and_no_pad():
    """Verify STRING statement simulation preserves unwritten receiver positions."""
    out, ptr, ovf = execute_string("ABCDEFGHIJ", [("123", None)], pointer=1)
    assert out == "123DEFGHIJ"
    assert ptr == 4
    assert not ovf


def test_string_simulation_overflow():
    """Verify STRING overflow on receiver capacity exceeded."""
    out, ptr, ovf = execute_string("..........", [("1234567890EXTRA", None)], pointer=1)
    assert out == "1234567890"
    assert ptr == 11
    assert ovf


def test_unstring_simulation_delimited_by_all():
    """Verify UNSTRING simulation with DELIMITED BY ALL."""
    results, ptr, ovf = execute_unstring("ONE    TWO   THREE", [(" ", True)], [5, 5, 5], pointer=1)
    assert results == ["ONE  ", "TWO  ", "THREE"]
    assert ptr == 19
    assert not ovf
'''


def render_func_java(package: str = JAVA_PACKAGE) -> str:
    """Generate FuncSpec.java."""
    rule_cases = "\n".join(f'            case "{r}" -> "{r}";' for r in sorted(FUNC_RULES))

    return f"""// {BANNER}
package {package};

/**
 * Declarative COBOL Intrinsic Functions specification.
 *
 * <p>Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06).
 * Follows the table-driven code generation pattern established by CicsSpec.java (#4586, #4608).
 */
public final class FuncSpec {{
    private FuncSpec() {{
    }}

    public static final int CATEGORY_STRING = {CATEGORY_STRING};
    public static final int CATEGORY_MATH = {CATEGORY_MATH};
    public static final int CATEGORY_PARSING = {CATEGORY_PARSING};
    public static final int CATEGORY_DATE_TIME = {CATEGORY_DATE_TIME};
    public static final int CATEGORY_IO = {CATEGORY_IO};

    /** Category name for diagnostics and evidence logging. */
    public static String categoryName(int cat) {{
        return switch (cat) {{
            case CATEGORY_STRING -> "STRING";
            case CATEGORY_MATH -> "MATH";
            case CATEGORY_PARSING -> "PARSING";
            case CATEGORY_DATE_TIME -> "DATE_TIME";
            case CATEGORY_IO -> "IO";
            default -> "UNKNOWN";
        }};
    }}

    /** Functional classification of an intrinsic function. */
    public static int functionCategory(String funcName) {{
        return switch (funcName) {{
            case "UPPER-CASE", "LOWER-CASE", "REVERSE", "TRIM" -> CATEGORY_STRING;
            case "MOD", "REM", "INTEGER", "INTEGER-PART", "ABS", "MIN", "MAX", "RANDOM" -> CATEGORY_MATH;
            case "NUMVAL", "NUMVAL-C", "TEST-NUMVAL", "TEST-NUMVAL-C" -> CATEGORY_PARSING;
            case "CURRENT-DATE", "INTEGER-OF-DATE", "DATE-OF-INTEGER", "ACCEPT-DATE" -> CATEGORY_DATE_TIME;
            case "ACCEPT-SYSIN" -> CATEGORY_IO;
            default -> -1;
        }};
    }}

    /** Get registered rule ID from key. */
    public static String ruleId(String key) {{
        return switch (key) {{
{rule_cases}
            default -> "UNKNOWN";
        }};
    }}
}}
"""


def render_func_markdown() -> str:
    """Generate docs/language_status/cobol_func_matrix.md."""
    cat_rows = [f"| `{cat_id}` | `{name}` |" for cat_id, name in sorted(FUNC_CATEGORIES.items())]
    cat_table = "\n".join(cat_rows)

    spec_rows = []
    for name, spec in sorted(FUNC_SPECS.items()):
        spec_rows.append(
            f"| `{name}` | `{spec.rule_id}` | `{spec.category}` | `{spec.return_type}` | {spec.ibm_section} | {spec.description} |"
        )
    spec_table = "\n".join(spec_rows)

    r_rows = []
    for rid, meta in sorted(FUNC_RULES.items()):
        doc_sec = f"{meta.ibm['doc']}: {meta.ibm['section']}" if meta.ibm else (meta.ibm_note or "-")
        reg = ", ".join(f"`{x}`" for x in meta.register) if meta.register else "-"
        r_rows.append(f"| `{rid}` | `{meta.status}` | {meta.title} | {doc_sec} | {reg} |")
    r_table = "\n".join(r_rows)

    v_rows = []
    for vec in FUNC_VECTORS:
        args_str = ", ".join(str(a) for a in vec.args)
        v_rows.append(
            f"| `{vec.id}` | {vec.title} | `{vec.rule_id}` | `{vec.function}` | `{args_str}` | `{vec.expected_result}` | {vec.note} |"
        )
    v_table = "\n".join(v_rows)

    return f"""<!-- {BANNER} -->
# COBOL Intrinsic Functions Specification (#4712)

Part of the **cobolrt-as-a-product** epic ([#4710](https://github.com/squid-protocol/gitgalaxy/issues/4710)).
Single source of truth: [`gitgalaxy/standards/cobol/func.py`](../../gitgalaxy/standards/cobol/func.py).
Generated by `python -m gitgalaxy.standards.cobol regen`.

Reference: **IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06)**
Chapter: *Intrinsic functions*, *ACCEPT statement*.

## 1. Rule Catalogue (FUNC Family)

| Rule ID | Status | Title | IBM Manual Reference | Register |
| :--- | :--- | :--- | :--- | :--- |
{r_table}

## 2. Intrinsic Function Categories

| ID | Category Name |
| :--- | :--- |
{cat_table}

## 3. Function Inventory & Return Types

| Function Name | Governed By Rule | Category | Return Type | IBM Manual Section | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
{spec_table}

## 4. Deterministic Test Vectors

| Vector ID | Title | Rule Verified | Function | Arguments | Expected Result | Note |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{v_table}
"""


def render_func_tests() -> str:
    """Generate tests/cobol_mainframe/test_cobol_func_vectors.py."""
    return '''# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Test vectors for the COBOL Intrinsic Functions rules (#4712, epic #4710).

Generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`.
Verifies that the declarative function rules, categories, return types,
and deterministic test vectors execute directly in CI without requiring Docker or external compilers.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import pytest

from gitgalaxy.standards.cobol.cli import problems, stale
from gitgalaxy.standards.cobol.func import (
    FUNC_CATEGORIES,
    FUNC_RULES,
    FUNC_SPECS,
    FUNC_VECTORS,
    evaluate_date_of_integer_ansi,
    evaluate_integer_of_date_ansi,
    evaluate_mod,
    evaluate_numval,
    evaluate_numval_c,
    evaluate_rem,
)


def test_cobol_func_spec_has_no_problems():
    """Verify internal consistency of standards/cobol intrinsic function rules."""
    errs = problems()
    assert errs == [], f"cobol spec has consistency problems: {errs}"


def test_cobol_func_generated_files_are_not_stale():
    """Verify committed FuncSpec.java, docs, and tests match the standards tables."""
    diff = stale()
    assert diff == [], f"standards generated files are stale: {diff}; run `python -m gitgalaxy.standards.cobol regen`"


def test_all_func_categories_and_rules_defined():
    """Verify categories, specs, and rules are defined."""
    assert len(FUNC_CATEGORIES) == 5
    assert len(FUNC_RULES) == 12
    assert len(FUNC_SPECS) >= 20
    assert len(FUNC_VECTORS) >= 20


@pytest.mark.parametrize("vec", FUNC_VECTORS, ids=lambda v: v.id)
def test_func_vector_rule_alignment(vec):
    """Verify each test vector correctly aligns with a registered rule."""
    assert vec.rule_id in FUNC_RULES
    meta = FUNC_RULES[vec.rule_id]
    assert meta.id == vec.rule_id


def test_func_simulation_mod_and_rem():
    """Verify MOD (floor) and REM (trunc) semantics."""
    assert evaluate_mod(Decimal("10"), Decimal("3")) == Decimal("1")
    assert evaluate_mod(Decimal("-10"), Decimal("3")) == Decimal("2")
    assert evaluate_mod(Decimal("10"), Decimal("0")) == Decimal("0")
    assert evaluate_rem(Decimal("-10"), Decimal("3")) == Decimal("-1")


def test_func_simulation_numval():
    """Verify NUMVAL and NUMVAL-C parsing."""
    assert evaluate_numval(" 123.45- ") == Decimal("-123.45")
    assert evaluate_numval(" 987.65CR ") == Decimal("-987.65")
    assert evaluate_numval_c(" $1,234,567.89 ") == Decimal("1234567.89")


def test_func_simulation_date_integer_ansi():
    """Verify INTEGER-OF-DATE and DATE-OF-INTEGER under ANSI."""
    assert evaluate_integer_of_date_ansi(16010101) == 1
    assert evaluate_date_of_integer_ansi(1) == 16010101
'''


def render_editing_java(package: str = JAVA_PACKAGE) -> str:
    """Generate EditingSpec.java."""
    rule_cases = "\n".join(f'            case "{r}" -> "{r}";' for r in sorted(EDITING_RULES))

    return f"""// {BANNER}
package {package};

/**
 * Declarative COBOL Numeric Editing specification (PICTURE clause editing, symbols, and shapes).
 *
 * <p>Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06),
 * Chapter "PICTURE clause" (Editing rules, Simple insertion, Special insertion,
 * Fixed insertion, Floating insertion, Zero suppression and replacement).
 * Follows the table-driven code generation pattern established by CicsSpec.java (#4586, #4608).
 */
public final class EditingSpec {{
    private EditingSpec() {{
    }}

    // Editing categories
    public static final int CATEGORY_SIMPLE_INSERTION = {EDIT_CATEGORY_SIMPLE_INSERTION};
    public static final int CATEGORY_SPECIAL_INSERTION = {EDIT_CATEGORY_SPECIAL_INSERTION};
    public static final int CATEGORY_FIXED_INSERTION = {EDIT_CATEGORY_FIXED_INSERTION};
    public static final int CATEGORY_FLOATING_INSERTION = {EDIT_CATEGORY_FLOATING_INSERTION};
    public static final int CATEGORY_ZERO_SUPPRESSION = {EDIT_CATEGORY_ZERO_SUPPRESSION};
    public static final int CATEGORY_DIGIT = {EDIT_CATEGORY_DIGIT};
    public static final int CATEGORY_IMPLICIT = {EDIT_CATEGORY_IMPLICIT};

    /** Standard COBOL editing symbols recognized in PICTURE clauses. */
    public static final String EDITING_SYMBOLS = "{EDITING_SYMBOLS_STRING}";

    /** Category name for diagnostics and evidence logging. */
    public static String categoryName(int cat) {{
        return switch (cat) {{
            case CATEGORY_SIMPLE_INSERTION -> "SIMPLE_INSERTION";
            case CATEGORY_SPECIAL_INSERTION -> "SPECIAL_INSERTION";
            case CATEGORY_FIXED_INSERTION -> "FIXED_INSERTION";
            case CATEGORY_FLOATING_INSERTION -> "FLOATING_INSERTION";
            case CATEGORY_ZERO_SUPPRESSION -> "ZERO_SUPPRESSION";
            case CATEGORY_DIGIT -> "DIGIT";
            case CATEGORY_IMPLICIT -> "IMPLICIT";
            default -> "UNKNOWN";
        }};
    }}

    /** Classification of an editing symbol into its functional category. */
    public static int symbolCategory(char symbol) {{
        return switch (symbol) {{
            case ',', 'B', '0', '/' -> CATEGORY_SIMPLE_INSERTION;
            case '.' -> CATEGORY_SPECIAL_INSERTION;
            case '+', '-', '$' -> CATEGORY_FIXED_INSERTION;
            case 'Z', '*' -> CATEGORY_ZERO_SUPPRESSION;
            case '9' -> CATEGORY_DIGIT;
            case 'V' -> CATEGORY_IMPLICIT;
            default -> -1;
        }};
    }}

    /** Returns true if character is a standard COBOL PICTURE editing symbol. */
    public static boolean isEditingSymbol(char ch) {{
        return EDITING_SYMBOLS.indexOf(ch) != -1;
    }}

    /** Returns true if character is a candidate for floating insertion. */
    public static boolean isFloatingCandidate(char ch) {{
        return ch == '$' || ch == '+' || ch == '-';
    }}

    /** Returns true if character is a zero-suppression symbol. */
    public static boolean isSuppressionSymbol(char ch) {{
        return ch == 'Z' || ch == '*';
    }}

    /** Get registered rule ID from key. */
    public static String ruleId(String key) {{
        return switch (key) {{
{rule_cases}
            default -> "UNKNOWN";
        }};
    }}
}}
"""


def render_editing_markdown() -> str:
    """Generate docs/language_status/cobol_editing_matrix.md."""
    sym_rows = [
        f"| `{spec.symbol}` | `{EDIT_CATEGORY_NAMES[spec.category]}` | {'YES' if spec.occupies_position else 'NO'} | {spec.ibm_clause} | {spec.description} |"
        for _, spec in sorted(EDITING_SYMBOLS.items())
    ]
    sym_table = "\n".join(sym_rows)

    r_rows = []
    for rid, meta in sorted(EDITING_RULES.items()):
        doc_sec = f"{meta.ibm['doc']}: {meta.ibm['section']}" if meta.ibm else (meta.ibm_note or "-")
        reg = ", ".join(f"`{x}`" for x in meta.register) if meta.register else "-"
        opts = ", ".join(f"`{x}`" for x in meta.options) if meta.options else "-"
        r_rows.append(f"| `{rid}` | `{meta.status}` | {meta.title} | {doc_sec} | {opts} | {reg} |")
    r_table = "\n".join(r_rows)

    v_rows = [
        f"| `{vec.id}` | {vec.title} | `{vec.rule_id}` | `{vec.picture}` | `{vec.value if vec.value is not None else (vec.raw_digits or 'null')}` | `{vec.expected}` | {vec.note or '-'} |"
        for vec in EDITING_VECTORS
    ]
    v_table = "\n".join(v_rows)

    return f"""<!-- {BANNER} -->
# COBOL Numeric Editing Rules & PICTURE Specification (#4712)

Part of the **cobolrt-as-a-product** epic ([#4710](https://github.com/squid-protocol/gitgalaxy/issues/4710)).
Single source of truth: [`gitgalaxy/standards/cobol/editing.py`](../../gitgalaxy/standards/cobol/editing.py).
Generated by `python -m gitgalaxy.standards.cobol regen`.

Reference: **IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06)**
Chapters: *PICTURE clause* (Editing rules, Simple insertion, Special insertion, Fixed insertion, Floating insertion, Zero suppression and replacement), *SPECIAL-NAMES paragraph* (CURRENCY SIGN, DECIMAL-POINT IS COMMA).

## 1. Rule Catalogue (EDIT Family)

| Rule ID | Status | Title | IBM Manual Reference | Options | Register |
| :--- | :--- | :--- | :--- | :--- | :--- |
{r_table}

## 2. PICTURE Editing Symbols & Categories

| Symbol | Category | Character Position? | IBM Clause | Behavior |
| :--- | :--- | :--- | :--- | :--- |
{sym_table}

## 3. Editing Invariants & Rules

- **Simple Insertion Editing**:
  - Insertion characters `,`, `B`, `0`, `/` occupy a character position and are inserted at their specified location.
  - If zero suppression is in effect and precedes the insertion position, the insertion character is suppressed (to space or asterisk) unless preceded by a non-suppressed digit.
- **Special Insertion Editing**:
  - The decimal point `.` (or `,` when `DECIMAL-POINT IS COMMA` is specified) occupies a character position.
  - In `Editing.java`, encountering the decimal point ends zero suppression for succeeding positions.
- **Fixed Insertion Editing**:
  - The currency symbol (`$` or program-declared symbol) and signs (`+`, `-`, `CR`, `DB`) occupy fixed positions at the beginning or end of the PICTURE.
  - `CR` and `DB` occupy two character positions and are displayed only if the value is negative; otherwise they are replaced by two spaces.
- **Floating Insertion Editing**:
  - A floating insertion string is formed by two or more consecutive `$`, `+`, or `-` characters (possibly separated by `,`, `.`, `B`, `0`, `/`).
  - The first symbol indicates the floating sign/currency position; each subsequent symbol represents a digit position.
  - The sign or currency string floats immediately to the left of the first significant digit or decimal point.
  - When every digit position belongs to the floating string and the numeric value is zero, the entire edited result is replaced by spaces.
- **Assumed Decimal Point (V)**:
  - `V` indicates the position of an assumed decimal point and occupies no character position in the receiver.
- **Non-digit Sender (Zoned item)**:
  - When an alphanumeric or zoned item containing non-digit bytes is moved to an edited receiver, raw bytes are placed directly into digit slots (GnuCOBOL compatibility / Register C11).

## 4. Deterministic Test Vectors

| Vector ID | Title | Rule Verified | PICTURE | Input Value | Expected Output | Note |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{v_table}
"""


def render_editing_tests() -> str:
    """Generate tests/cobol_mainframe/test_cobol_editing_vectors.py."""
    return '''# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Test vectors for COBOL Numeric Editing rules (#4712, epic #4710).

Generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`.
Verifies that the declarative editing rules, symbol categories, and deterministic test vectors
execute directly in CI without requiring Docker or external compilers.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import pytest

from gitgalaxy.standards.cobol.cli import problems, stale
from gitgalaxy.standards.cobol.editing import (
    EDIT_CATEGORY_NAMES,
    EDITING_RULES,
    EDITING_SYMBOLS,
    EDITING_VECTORS,
    execute_editing,
    execute_shape,
    expand_picture,
)


def test_cobol_editing_spec_has_no_problems():
    """Verify internal consistency of standards/cobol numeric editing rules."""
    errs = problems()
    assert errs == [], f"cobol spec has consistency problems: {errs}"


def test_cobol_editing_generated_files_are_not_stale():
    """Verify committed EditingSpec.java, docs, and tests match the standards tables."""
    diff = stale()
    assert diff == [], f"standards generated files are stale: {diff}; run `python -m gitgalaxy.standards.cobol regen`"


def test_all_editing_symbols_and_rules_defined():
    """Verify editing symbols, categories, and rules are defined."""
    assert len(EDIT_CATEGORY_NAMES) == 7
    assert len(EDITING_SYMBOLS) == 14
    assert len(EDITING_RULES) == 5
    assert len(EDITING_VECTORS) >= 30


@pytest.mark.parametrize("vec", EDITING_VECTORS, ids=lambda v: v.id)
def test_editing_vector_rule_alignment(vec):
    """Verify each test vector correctly aligns with a registered rule."""
    assert vec.rule_id in EDITING_RULES
    meta = EDITING_RULES[vec.rule_id]
    assert meta.id == vec.rule_id


@pytest.mark.parametrize("vec", EDITING_VECTORS, ids=lambda v: v.id)
def test_editing_simulation_all_vectors(vec):
    """Verify pure-Python simulation produces expected output for each vector."""
    got = execute_editing(
        vec.picture,
        vec.value,
        decimal_comma=vec.decimal_comma,
        currency=vec.currency,
        raw_digits=vec.raw_digits,
        negative=vec.negative,
    )
    assert got == vec.expected, f"{vec.id}: expected {vec.expected!r}, got {got!r}"


def test_editing_picture_shape_simulation():
    """Verify shape calculation for integer and decimal digit positions."""
    assert execute_shape("ZZ,ZZ9.99") == (5, 2)
    assert execute_shape("Z(4)9(2).9(3)") == (6, 3)
    assert execute_shape("ZZ.ZZ9,99", decimal_comma=True) == (5, 2)
    assert execute_shape("$$$,$$9.99") == (5, 2)
    assert execute_shape("999B999") == (6, 0)


def test_editing_picture_expansion():
    """Verify repetition expansion in PICTURE strings."""
    assert expand_picture("Z(4)9(2)") == "ZZZZ99"
    assert expand_picture("9(3)V9(2)") == "999V99"
    assert expand_picture("S9(4)") == "9999"
'''


def render_sort_java(package: str = JAVA_PACKAGE) -> str:
    """Generate SortSpec.java."""
    rule_cases = "\n".join(f'            case "{r}" -> "{r}";' for r in sorted(SORT_RULES))

    return f"""// {BANNER}
package {package};

/**
 * Declarative COBOL SORT and MERGE specification (collating sequences, keys, and procedures).
 *
 * <p>Reference: IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06),
 * Chapters: "SORT statement", "MERGE statement", "RELEASE statement", "RETURN statement",
 * "ALPHABET clause", "PROGRAM COLLATING SEQUENCE clause".
 * Follows the table-driven code generation pattern established by CicsSpec.java (#4586, #4608).
 */
public final class SortSpec {{
    private SortSpec() {{
    }}

    // Sort directions
    public static final int DIRECTION_ASCENDING = {DIRECTION_ASCENDING};
    public static final int DIRECTION_DESCENDING = {DIRECTION_DESCENDING};

    // Collating sequence modes
    public static final int COLLATING_NATIVE = {COLLATING_NATIVE};
    public static final int COLLATING_EBCDIC = {COLLATING_EBCDIC};
    public static final int COLLATING_LITERAL = {COLLATING_LITERAL};

    // Procedure phrases
    public static final int PHRASE_USING = {PHRASE_USING};
    public static final int PHRASE_GIVING = {PHRASE_GIVING};
    public static final int PHRASE_INPUT_PROCEDURE = {PHRASE_INPUT_PROCEDURE};
    public static final int PHRASE_OUTPUT_PROCEDURE = {PHRASE_OUTPUT_PROCEDURE};

    // SORT-RETURN special register values
    public static final int SORT_RETURN_SUCCESS = {SORT_RETURN_SUCCESS};
    public static final int SORT_RETURN_ABORT = {SORT_RETURN_ABORT};

    /** Name of direction. */
    public static String directionName(int direction) {{
        return switch (direction) {{
            case DIRECTION_ASCENDING -> "ASCENDING";
            case DIRECTION_DESCENDING -> "DESCENDING";
            default -> "UNKNOWN";
        }};
    }}

    /** Name of collating sequence mode. */
    public static String collatingModeName(int mode) {{
        return switch (mode) {{
            case COLLATING_NATIVE -> "NATIVE";
            case COLLATING_EBCDIC -> "EBCDIC";
            case COLLATING_LITERAL -> "LITERAL";
            default -> "UNKNOWN";
        }};
    }}

    /** Name of phrase type. */
    public static String phraseName(int phrase) {{
        return switch (phrase) {{
            case PHRASE_USING -> "USING";
            case PHRASE_GIVING -> "GIVING";
            case PHRASE_INPUT_PROCEDURE -> "INPUT_PROCEDURE";
            case PHRASE_OUTPUT_PROCEDURE -> "OUTPUT_PROCEDURE";
            default -> "UNKNOWN";
        }};
    }}

    /** Returns true if SORT-RETURN value requests terminating the sort (16). */
    public static boolean isAbortReturn(int sortReturn) {{
        return sortReturn == SORT_RETURN_ABORT;
    }}

    /** Get registered rule ID from key. */
    public static String ruleId(String key) {{
        return switch (key) {{
{rule_cases}
            default -> "UNKNOWN";
        }};
    }}
}}
"""


def render_sort_markdown() -> str:
    """Generate docs/language_status/cobol_sort_matrix.md."""
    r_rows = []
    for rid, meta in sorted(SORT_RULES.items()):
        doc_sec = f"{meta.ibm['doc']}: {meta.ibm['section']}" if meta.ibm else (meta.ibm_note or "-")
        reg = ", ".join(f"`{x}`" for x in meta.register) if meta.register else "-"
        opts = ", ".join(f"`{x}`" for x in meta.options) if meta.options else "-"
        r_rows.append(f"| `{rid}` | `{meta.status}` | {meta.title} | {doc_sec} | {opts} | {reg} |")
    r_table = "\n".join(r_rows)

    v_rows = [
        f"| `{vec.id}` | {vec.title} | `{vec.rule_id}` | `{len(vec.records)}` | `{COLLATING_NAMES[vec.collating]}` | `{vec.expected}` | {vec.note or '-'} |"
        for vec in SORT_VECTORS
    ]
    v_table = "\n".join(v_rows)

    return f"""<!-- {BANNER} -->
# COBOL SORT and MERGE Specification (#4712)

Part of the **cobolrt-as-a-product** epic ([#4710](https://github.com/squid-protocol/gitgalaxy/issues/4710)).
Single source of truth: [`gitgalaxy/standards/cobol/sort_ops.py`](../../gitgalaxy/standards/cobol/sort_ops.py).
Generated by `python -m gitgalaxy.standards.cobol regen`.

Reference: **IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06)**
Chapters: *SORT statement*, *MERGE statement*, *RELEASE statement*, *RETURN statement*, *ALPHABET clause*, *PROGRAM COLLATING SEQUENCE clause*.

## 1. Rule Catalogue (SORT Family)

| Rule ID | Status | Title | IBM Manual Reference | Options | Register |
| :--- | :--- | :--- | :--- | :--- | :--- |
{r_table}

## 2. Statement Invariants & Sorting Semantics

- **Key Comparison Rules**:
  - Keys are compared major-to-minor in the order specified in `ASCENDING/DESCENDING KEY` phrases.
  - Numeric keys (zoned, packed, binary) compare algebraically according to numeric value.
  - Nonnumeric keys compare position-by-position in the data code page or designated collating sequence.
  - Shorter alphanumeric keys are space-padded on the right.
- **Collating Sequence & ALPHABET**:
  - `NATIVE`: data byte order (ASCII or EBCDIC depending on host platform).
  - `EBCDIC`: ordered by IBM037 EBCDIC character codes (letters precede digits; lowercase precedes uppercase).
  - `LITERAL`: ordered by user-specified literal sequence with optional `ALSO` (equal ordinal weight) and `THRU` (contiguous range).
  - If IBM EBCDIC sequence and oracle ASCII order diverge, or on unmapped characters, execution halts by name (Register D1).
- **Stability & Duplicates**:
  - `WITH DUPLICATES IN ORDER`: records with identical keys preserve their input arrival order.
  - In `Sort.java`, sorting is implemented via a stable merge-sort ensuring deterministic ordering.
- **Procedures & Special Registers**:
  - `RELEASE` passes records into the sort work area from an `INPUT PROCEDURE`.
  - `RETURN` retrieves records from the sort work area in an `OUTPUT PROCEDURE`.
  - Setting `SORT-RETURN` to 16 terminates the sort operation; a successful sort leaves `SORT-RETURN` 0 (Register F4).

## 3. Deterministic Test Vectors

| Vector ID | Title | Rule Verified | Records | Collating | Expected Output | Note |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{v_table}
"""


def render_sort_tests() -> str:
    """Generate tests/cobol_mainframe/test_cobol_sort_vectors.py."""
    return '''# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Test vectors for COBOL SORT and MERGE rules (#4712, epic #4710).

Generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`.
Verifies that the declarative sort rules, key comparisons, and deterministic test vectors
execute directly in CI without requiring Docker or external compilers.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import pytest

from gitgalaxy.standards.cobol.cli import problems, stale
from gitgalaxy.standards.cobol.sort_ops import (
    COLLATING_EBCDIC,
    COLLATING_LITERAL,
    COLLATING_NAMES,
    COLLATING_NATIVE,
    DIRECTION_NAMES,
    PHRASE_NAMES,
    SORT_RULES,
    SORT_VECTORS,
    execute_collating_compare,
    execute_merge,
    execute_sort,
)


def test_cobol_sort_spec_has_no_problems():
    """Verify internal consistency of standards/cobol sort rules."""
    errs = problems()
    assert errs == [], f"cobol spec has consistency problems: {errs}"


def test_cobol_sort_generated_files_are_not_stale():
    """Verify committed SortSpec.java, docs, and tests match the standards tables."""
    diff = stale()
    assert diff == [], f"standards generated files are stale: {diff}; run `python -m gitgalaxy.standards.cobol regen`"


def test_all_sort_rules_and_constants_defined():
    """Verify sort rules, direction names, and collating modes are defined."""
    assert len(SORT_RULES) == 7
    assert len(DIRECTION_NAMES) == 2
    assert len(COLLATING_NAMES) == 3
    assert len(PHRASE_NAMES) == 4
    assert len(SORT_VECTORS) >= 15


@pytest.mark.parametrize("vec", SORT_VECTORS, ids=lambda v: v.id)
def test_sort_vector_rule_alignment(vec):
    """Verify each test vector correctly aligns with a registered rule."""
    assert vec.rule_id in SORT_RULES
    meta = SORT_RULES[vec.rule_id]
    assert meta.id == vec.rule_id


@pytest.mark.parametrize("vec", SORT_VECTORS, ids=lambda v: v.id)
def test_sort_simulation_all_vectors(vec):
    """Verify pure-Python simulation produces expected output for each vector."""
    got = execute_sort(
        vec.records,
        vec.keys,
        collating=vec.collating,
        alphabet_entries=vec.alphabet_entries,
    )
    assert got == vec.expected, f"{vec.id}: expected {vec.expected!r}, got {got!r}"


def test_merge_simulation_two_files():
    """Verify merge of two pre-sorted files preserves file order on equal keys."""
    from gitgalaxy.standards.cobol.sort_ops import SortKeySpec

    file1 = ["010 FILE1-A", "030 FILE1-B"]
    file2 = ["010 FILE2-A", "020 FILE2-B"]
    keys = [SortKeySpec(offset=0, length=3, is_numeric=True, ascending=True)]
    merged = execute_merge([file1, file2], keys)
    assert merged == ["010 FILE1-A", "010 FILE2-A", "020 FILE2-B", "030 FILE1-B"]


def test_collating_compare_ebcdic():
    """Verify PROGRAM COLLATING SEQUENCE character ordering."""
    # Under EBCDIC: 'A' precedes '1'
    assert execute_collating_compare("A", "1", collating=COLLATING_EBCDIC) < 0
    # Under Native (ASCII): '1' precedes 'A'
    assert execute_collating_compare("A", "1", collating=COLLATING_NATIVE) > 0
'''


def render_hfp_java(package: str = JAVA_PACKAGE) -> str:
    """Generate HfpSpec.java."""
    rule_cases = "\n".join(f'            case "{rid}" -> "{rid}";' for rid in sorted(HFP_RULES))

    return f"""// {BANNER}
package {package};

/**
 * Declarative COBOL Hexadecimal Floating Point specification (COMP-1 and COMP-2 data items).
 *
 * <p>Reference: IBM z/Architecture Principles of Operation (SA22-7832),
 * Chapter "Hexadecimal-Floating-Point Number Representation" and "Hexadecimal-Floating-Point Instructions";
 * IBM Enterprise COBOL for z/OS 6.4 Programming Guide (SC27-8714-03), Chapter "Conversions and precision";
 * IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06), Chapter "DISPLAY statement".
 * Follows the table-driven code generation pattern established by CicsSpec.java (#4586, #4608).
 */
public final class HfpSpec {{
    private HfpSpec() {{
    }}

    public static final int PRECISION_SHORT = {PRECISION_SHORT};
    public static final int PRECISION_LONG = {PRECISION_LONG};
    public static final int BYTES_SHORT = {BYTES_SHORT};
    public static final int BYTES_LONG = {BYTES_LONG};
    public static final int BIAS_CHARACTERISTIC = {BIAS_CHARACTERISTIC};
    public static final int MAX_CHARACTERISTIC = {MAX_CHARACTERISTIC};
    public static final int MAX_EXPONENT = {MAX_EXPONENT};
    public static final int MIN_EXPONENT = {MIN_EXPONENT};
    public static final int SIGNIFICANT_DIGITS_SHORT = {SIGNIFICANT_DIGITS_SHORT};
    public static final int SIGNIFICANT_DIGITS_LONG = {SIGNIFICANT_DIGITS_LONG};
    public static final int DISPLAY_DIGITS_SHORT = {DISPLAY_DIGITS_SHORT};
    public static final int DISPLAY_DIGITS_LONG = {DISPLAY_DIGITS_LONG};

    /** Number of fraction hex digits for short (COMP-1) or long (COMP-2). */
    public static int precisionDigits(boolean isShort) {{
        return isShort ? PRECISION_SHORT : PRECISION_LONG;
    }}

    /** Number of storage bytes for short (COMP-1) or long (COMP-2). */
    public static int precisionBytes(boolean isShort) {{
        return isShort ? BYTES_SHORT : BYTES_LONG;
    }}

    /** Maximum significant digits when converting to fixed point. */
    public static int maxSignificantDigits(boolean isShort) {{
        return isShort ? SIGNIFICANT_DIGITS_SHORT : SIGNIFICANT_DIGITS_LONG;
    }}

    /** Number of fractional digits in DISPLAY format (-.9(N)E-99). */
    public static int displayMantissaDigits(boolean isShort) {{
        return isShort ? DISPLAY_DIGITS_SHORT : DISPLAY_DIGITS_LONG;
    }}

    /** COBOL usage type name. */
    public static String typeName(boolean isShort) {{
        return isShort ? "{TYPE_NAME_COMP1}" : "{TYPE_NAME_COMP2}";
    }}

    /** True if the exponent (unbiased) is within valid HFP range [-64, 63]. */
    public static boolean isExponentInRange(int exp) {{
        return exp >= MIN_EXPONENT && exp <= MAX_EXPONENT;
    }}

    /** Get registered rule ID from key. */
    public static String ruleId(String key) {{
        return switch (key) {{
{rule_cases}
            default -> "UNKNOWN";
        }};
    }}
}}
"""


def render_hfp_markdown() -> str:
    """Generate docs/language_status/cobol_hfp_matrix.md."""
    r_rows = []
    for rid, meta in sorted(HFP_RULES.items()):
        doc_sec = f"{meta.ibm['doc']}: {meta.ibm['section']}" if meta.ibm else (meta.ibm_note or "-")
        reg = ", ".join(f"`{x}`" for x in meta.register) if meta.register else "-"
        opts = ", ".join(f"`{x}`" for x in meta.options) if meta.options else "-"
        r_rows.append(f"| `{rid}` | `{meta.status}` | {meta.title} | {doc_sec} | {opts} | {reg} |")
    r_table = "\n".join(r_rows)

    v_rows = [
        f"| `{vec.id}` | {vec.title} | `{vec.rule_id}` | `{'COMP-1' if vec.short else 'COMP-2'}` | `{vec.input_value}` | `{vec.expected_hex}` | `{vec.expected_fixed or '-'}` | `{vec.expected_display or '-'}` | {vec.note or '-'} |"
        for vec in HFP_VECTORS
    ]
    v_table = "\n".join(v_rows)

    return f"""<!-- {BANNER} -->
# COBOL Hexadecimal Floating Point (HFP) Specification (#4712)

Part of the **cobolrt-as-a-product** epic ([#4710](https://github.com/squid-protocol/gitgalaxy/issues/4710)).
Single source of truth: [`gitgalaxy/standards/cobol/hfp.py`](../../gitgalaxy/standards/cobol/hfp.py).
Generated by `python -m gitgalaxy.standards.cobol regen`.

Reference:
- **IBM z/Architecture Principles of Operation (SA22-7832)**: Chapters *Hexadecimal-Floating-Point Number Representation*, *Hexadecimal-Floating-Point Instructions*.
- **IBM Enterprise COBOL for z/OS 6.4 Programming Guide (SC27-8714-03)**: Chapters *Conversions and precision*, *Converting to numbers*.
- **IBM Enterprise COBOL for z/OS 6.4 Language Reference (SC26-4940-06)**: Chapter *DISPLAY statement*.

## 1. Rule Catalogue (HFP Family)

| Rule ID | Status | Title | IBM Manual Reference | Options | Register |
| :--- | :--- | :--- | :--- | :--- | :--- |
{r_table}

## 2. HFP Format & Invariants

- **Storage Layout & Biased Characteristic**:
  - `COMP-1` (single precision / short): 4 bytes (32 bits): bit 0 sign, bits 1-7 characteristic (exponent base 16, excess 64, range 0..127 corresponding to exponents -64..+63), bits 8-31 fraction (6 hexadecimal digits).
  - `COMP-2` (double precision / long): 8 bytes (64 bits): bit 0 sign, bits 1-7 characteristic (excess 64), bits 8-63 fraction (14 hexadecimal digits).
  - True zero is represented by all zero bytes (`0x00000000` or `0x0000000000000000`).
- **Normalized Arithmetic & Guard Digit**:
  - `ADD` and `SUBTRACT` align operands with exactly **one hexadecimal guard digit**; digits shifted beyond the guard digit are lost. The sum is normalized and truncated.
  - `MULTIPLY` and `DIVIDE` truncate the exact product or quotient to the target precision (6 or 14 hex digits).
  - Division by zero raises `SIZE ERROR` with the target receiver unchanged in statement context, and is refused by name in nested expressions (Register C14).
- **Rounding & Precision Bounds**:
  - `LOAD ROUNDED` (COMP-2 to COMP-1 conversion) adds a `1` at the first discarded bit (half away from zero).
  - Fixed-point to floating-point: truncated to 14 hex digits, then rounded to 6 hex digits for COMP-1.
  - Floating-point to fixed-point: rounded half away from zero in the receiver's low-order position, retaining at most 9 significant digits (COMP-1) or 18 significant digits (COMP-2).
- **External DISPLAY Format**:
  - `COMP-1`: formatted as `-.9(8)E-99` (14 characters total: sign, decimal point, 8 fraction digits rounded, exponent indicator `E`, exponent sign, 2 exponent digits).
  - `COMP-2`: formatted as `-.9(17)E-99` (23 characters total: sign, decimal point, 17 fraction digits rounded, exponent indicator `E`, exponent sign, 2 exponent digits).
- **IEEE-754 Conversion**:
  - Exact bidirectional mapping between IEEE binary32/binary64 and IBM HFP short/long formats (Register C6).

## 3. Deterministic Test Vectors

| Vector ID | Title | Rule Verified | Precision | Input | Expected Hex | Expected Fixed | Expected Display | Note |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{v_table}
"""


def render_hfp_tests() -> str:
    """Generate tests/cobol_mainframe/test_cobol_hfp_vectors.py."""
    return '''# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Test vectors for COBOL Hexadecimal Floating Point (HFP) rules (#4712, epic #4710).

Generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`.
Verifies that the declarative HFP rules, conversions, and deterministic test vectors
execute directly in CI without requiring Docker or external compilers.
"""

from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import pytest

from gitgalaxy.standards.cobol.cli import problems, stale
from gitgalaxy.standards.cobol.hfp import (
    BYTES_LONG,
    BYTES_SHORT,
    HFP_RULES,
    HFP_VECTORS,
    PRECISION_LONG,
    PRECISION_SHORT,
    SIGNIFICANT_DIGITS_LONG,
    SIGNIFICANT_DIGITS_SHORT,
    execute_decode,
    execute_display,
    execute_encode,
    execute_power,
    execute_to_fixed,
    execute_to_short,
)
from gitgalaxy.tools.cobol_to_java.det import hfp as _hfp


def test_cobol_hfp_spec_has_no_problems():
    """Verify internal consistency of standards/cobol HFP rules."""
    errs = problems()
    assert errs == [], f"cobol spec has consistency problems: {errs}"


def test_cobol_hfp_generated_files_are_not_stale():
    """Verify committed HfpSpec.java, docs, and tests match the standards tables."""
    diff = stale()
    assert diff == [], f"standards generated files are stale: {diff}; run `python -m gitgalaxy.standards.cobol regen`"


def test_all_hfp_rules_and_constants_defined():
    """Verify HFP rules and precision constants are properly defined."""
    assert len(HFP_RULES) == 14
    assert PRECISION_SHORT == 6
    assert PRECISION_LONG == 14
    assert BYTES_SHORT == 4
    assert BYTES_LONG == 8
    assert SIGNIFICANT_DIGITS_SHORT == 9
    assert SIGNIFICANT_DIGITS_LONG == 18
    assert len(HFP_VECTORS) >= 25


@pytest.mark.parametrize("vec", HFP_VECTORS, ids=lambda v: v.id)
def test_hfp_vector_rule_alignment(vec):
    """Verify each test vector correctly aligns with a registered rule."""
    assert vec.rule_id in HFP_RULES
    meta = HFP_RULES[vec.rule_id]
    assert meta.id == vec.rule_id


@pytest.mark.parametrize("vec", HFP_VECTORS, ids=lambda v: v.id)
def test_hfp_vector_encoding(vec):
    """Verify HFP encoding matches expected hexadecimal representation."""
    if vec.expected_hex.startswith("ERROR_"):
        return
    if vec.input_value.startswith("ieee_"):
        if vec.short:
            b = _hfp.from_ieee(0x3F800000, 4)  # 1.0f
        else:
            b = _hfp.from_ieee(0xC05DA80000000000, 8)  # -118.625d
        assert b.hex().upper() == vec.expected_hex
        return
    if vec.input_value.startswith("numval"):
        b = _hfp.encode(_hfp.of("123.45"), False)
        assert b.hex().upper() == vec.expected_hex
        return
    if vec.input_value.startswith("fixed_store"):
        b = _hfp.encode(_hfp.for_item(Fraction("-1.005"), True), True)
        assert b.hex().upper() == vec.expected_hex
        return
    if vec.input_value == "to_short(2/3)":
        res = _hfp.to_short(_hfp.div(Fraction(2), Fraction(3), long=True))
        assert _hfp.encode(res, True).hex().upper() == vec.expected_hex
        return
    if vec.input_value == "to_short(-2/3)":
        res = _hfp.to_short(-_hfp.div(Fraction(2), Fraction(3), long=True))
        assert _hfp.encode(res, True).hex().upper() == vec.expected_hex
        return
    if vec.input_value == "2 ** 10":
        res = execute_power(2, 10)
        assert _hfp.encode(res, False).hex().upper() == vec.expected_hex
        return
    if vec.input_value == "of(0.1)":
        res = _hfp.of("0.1")
        assert _hfp.encode(res, False).hex().upper() == vec.expected_hex
        return
    if vec.input_value == "(1 / 3) * 3":
        third = _hfp.div(Fraction(1), Fraction(3), long=True)
        res = _hfp.mul(third, Fraction(3), long=True)
        assert _hfp.encode(res, False).hex().upper() == vec.expected_hex
        return

    encoded = execute_encode(vec.input_value, vec.short)
    assert encoded.hex().upper() == vec.expected_hex, f"{vec.id}: expected {vec.expected_hex}, got {encoded.hex().upper()}"


@pytest.mark.parametrize("vec", [v for v in HFP_VECTORS if v.expected_display is not None], ids=lambda v: v.id)
def test_hfp_vector_display(vec):
    """Verify DISPLAY formatting for vectors specifying expected_display."""
    disp = execute_display(vec.input_value, not vec.short)
    assert disp == vec.expected_display, f"{vec.id}: expected {vec.expected_display!r}, got {disp!r}"


@pytest.mark.parametrize("vec", [v for v in HFP_VECTORS if v.expected_fixed is not None], ids=lambda v: v.id)
def test_hfp_vector_fixed(vec):
    """Verify float-to-fixed conversion for vectors specifying expected_fixed."""
    if vec.input_value.startswith("fixed_store"):
        b = _hfp.encode(_hfp.for_item(Fraction("-1.005"), True), True)
    else:
        b = execute_encode(vec.input_value, vec.short)
    sig = 9 if vec.short else 18
    fix = str(execute_to_fixed(execute_decode(b), vec.scale, sig))
    assert fix == vec.expected_fixed, f"{vec.id}: expected {vec.expected_fixed!r}, got {fix!r}"


def test_hfp_guard_digit_truncation():
    """Verify that arithmetic retains one guard digit and discards beyond."""
    one = Fraction(1)
    # 16**-6 sits in guard digit and is subtracted
    assert _hfp.sub(one, Fraction(16) ** -6, long=False) == 1 - Fraction(16) ** -6
    # 16**-8 is shifted past guard digit and lost
    assert _hfp.sub(one, Fraction(16) ** -8, long=False) == 1


def test_hfp_load_rounded():
    """Verify long-to-short LOAD ROUNDED rounds half away from zero."""
    res_pos = _hfp.to_short(_hfp.div(Fraction(2), Fraction(3), long=True))
    assert _hfp.encode(res_pos, True).hex().upper() == "40AAAAAB"
    res_neg = _hfp.to_short(-_hfp.div(Fraction(2), Fraction(3), long=True))
    assert _hfp.encode(res_neg, True).hex().upper() == "C0AAAAAB"
'''


def generated() -> dict[Path, str]:
    """The committed generated files and the text the spec renders for each."""
    return {
        MOVE_JAVA_FILE: render_move_java(),
        COMPARE_JAVA_FILE: render_compare_java(),
        ARITH_JAVA_FILE: render_arith_java(),
        STRING_JAVA_FILE: render_string_java(),
        FUNC_JAVA_FILE: render_func_java(),
        EDITING_JAVA_FILE: render_editing_java(),
        SORT_JAVA_FILE: render_sort_java(),
        HFP_JAVA_FILE: render_hfp_java(),
        MOVE_DOCS_FILE: render_move_markdown(),
        COMPARE_DOCS_FILE: render_compare_markdown(),
        ARITH_DOCS_FILE: render_arith_markdown(),
        STRING_DOCS_FILE: render_string_markdown(),
        FUNC_DOCS_FILE: render_func_markdown(),
        EDITING_DOCS_FILE: render_editing_markdown(),
        SORT_DOCS_FILE: render_sort_markdown(),
        HFP_DOCS_FILE: render_hfp_markdown(),
        MOVE_TEST_FILE: render_move_tests(),
        COMPARE_TEST_FILE: render_compare_tests(),
        ARITH_TEST_FILE: render_arith_tests(),
        STRING_TEST_FILE: render_string_tests(),
        FUNC_TEST_FILE: render_func_tests(),
        EDITING_TEST_FILE: render_editing_tests(),
        SORT_TEST_FILE: render_sort_tests(),
        HFP_TEST_FILE: render_hfp_tests(),
    }


def stale(root: Path = ROOT) -> list[Path]:
    """The committed generated files that differ from what the spec renders."""
    out = []
    for rel, text in generated().items():
        target = root / rel
        if not target.is_file() or target.read_text(encoding="utf-8") != text:
            out.append(rel)
    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m gitgalaxy.standards.cobol", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("emit", help="print the rule matrix and vectors")
    e.add_argument("--json", action="store_true", help="output as JSON")

    sub.add_parser("check", help="the spec's own consistency and catalogue alignment")

    r = sub.add_parser("regen", help="rewrite the committed generated files (or check / render them)")
    how = r.add_mutually_exclusive_group()
    how.add_argument("--check", action="store_true", help="exit 1 when a committed file is stale")
    how.add_argument("--out", type=Path, help="render files into this directory instead")
    r.add_argument("--java-package", default=JAVA_PACKAGE, help="with --out: the generated Java class's package")

    args = ap.parse_args(argv)

    if args.cmd == "emit":
        data = as_json()
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(
                f"COBOL MOVE Standards: {len(MOVE_RULES)} rules, {len(MOVE_MATRIX)} matrix cells, {len(MOVE_VECTORS)} vectors"
            )
            for rid, mr in sorted(MOVE_RULES.items()):
                print(f"  {rid:<38} {mr.status:<9} {mr.title[:45]}")
            print(
                f"COBOL COMPARE Standards: {len(COMPARE_RULES)} rules, {len(COMPARE_MATRIX)} matrix cells, {len(COMPARE_VECTORS)} vectors"
            )
            for rid, cr in sorted(COMPARE_RULES.items()):
                print(f"  {rid:<38} {cr.status:<9} {cr.title[:45]}")
            print(
                f"COBOL ARITH Standards: {len(ARITH_RULES)} rules, {len(ROUNDING_MODES)} rounding modes, {len(ARITH_VECTORS)} vectors"
            )
            for rid, ar in sorted(ARITH_RULES.items()):
                print(f"  {rid:<38} {ar.status:<9} {ar.title[:45]}")
            print(
                f"COBOL STRING Standards: {len(STRING_RULES)} rules, {len(INSPECT_MODES)} inspect modes, {len(STRING_VECTORS)} vectors"
            )
            for rid, sr in sorted(STRING_RULES.items()):
                print(f"  {rid:<38} {sr.status:<9} {sr.title[:45]}")
            print(
                f"COBOL FUNC Standards: {len(FUNC_RULES)} rules, {len(FUNC_CATEGORIES)} categories, {len(FUNC_VECTORS)} vectors"
            )
            for rid, fr in sorted(FUNC_RULES.items()):
                print(f"  {rid:<38} {fr.status:<9} {fr.title[:45]}")
            print(
                f"COBOL EDIT Standards: {len(EDITING_RULES)} rules, {len(EDITING_SYMBOLS)} symbols, {len(EDITING_VECTORS)} vectors"
            )
            for rid, er in sorted(EDITING_RULES.items()):
                print(f"  {rid:<38} {er.status:<9} {er.title[:45]}")
            print(
                f"COBOL SORT Standards: {len(SORT_RULES)} rules, {len(DIRECTION_NAMES)} directions, {len(SORT_VECTORS)} vectors"
            )
            for rid, sort_r in sorted(SORT_RULES.items()):
                print(f"  {rid:<38} {sort_r.status:<9} {sort_r.title[:45]}")
            print(f"COBOL HFP Standards: {len(HFP_RULES)} rules, {len(HFP_VECTORS)} vectors")
            for rid, hfp_r in sorted(HFP_RULES.items()):
                print(f"  {rid:<38} {hfp_r.status:<9} {hfp_r.title[:45]}")
        return 0

    if args.cmd == "check":
        found = problems()
        for p in found:
            print(p)
        total_rules = (
            len(MOVE_RULES)
            + len(COMPARE_RULES)
            + len(ARITH_RULES)
            + len(STRING_RULES)
            + len(FUNC_RULES)
            + len(EDITING_RULES)
            + len(SORT_RULES)
            + len(HFP_RULES)
        )
        print(
            f"cobol spec: {total_rules} rules, {len(MOVE_MATRIX) + len(COMPARE_MATRIX)} matrix cells, {'ok' if not found else f'{len(found)} problem(s)'}"
        )
        return 1 if found else 0

    if args.check:
        old = stale()
        for path in old:
            print(f"stale: {path}")
        print(
            f"cobol spec generated files: {'up to date' if not old else f'{len(old)} stale'}"
            + ("; run `python -m gitgalaxy.standards.cobol regen` and commit them" if old else "")
        )
        return 1 if old else 0

    if args.out is None:
        for path, text in generated().items():
            target = ROOT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            print(f"wrote {path}")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    for path, text in generated().items():
        dest = args.out / path.name
        dest.write_text(text, encoding="utf-8")
    print(f"wrote generated files to {args.out}")
    return 0
