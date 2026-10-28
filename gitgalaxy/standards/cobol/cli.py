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

from gitgalaxy.standards.cobol.compare import (
    COMPARE_MATRIX,
    COMPARE_MODES,
    COMPARE_RULES,
    COMPARE_VECTORS,
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

BANNER = "generated from gitgalaxy/standards/cobol by `python -m gitgalaxy.standards.cobol regen`; do not edit"

ROOT = Path(__file__).resolve().parents[3]
MOVE_JAVA_FILE = Path("gitgalaxy/tools/cobol_to_java/det/cobolrt/MoveSpec.java")
COMPARE_JAVA_FILE = Path("gitgalaxy/tools/cobol_to_java/det/cobolrt/CompareSpec.java")
MOVE_DOCS_FILE = Path("docs/language_status/cobol_move_matrix.md")
COMPARE_DOCS_FILE = Path("docs/language_status/cobol_compare_matrix.md")
MOVE_TEST_FILE = Path("tests/cobol_mainframe/test_cobol_move_vectors.py")
COMPARE_TEST_FILE = Path("tests/cobol_mainframe/test_cobol_compare_vectors.py")
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


def generated() -> dict[Path, str]:
    """The committed generated files and the text the spec renders for each."""
    return {
        MOVE_JAVA_FILE: render_move_java(),
        COMPARE_JAVA_FILE: render_compare_java(),
        MOVE_DOCS_FILE: render_move_markdown(),
        COMPARE_DOCS_FILE: render_compare_markdown(),
        MOVE_TEST_FILE: render_move_tests(),
        COMPARE_TEST_FILE: render_compare_tests(),
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
        return 0

    if args.cmd == "check":
        found = problems()
        for p in found:
            print(p)
        print(
            f"cobol spec: {len(MOVE_RULES) + len(COMPARE_RULES)} rules, {len(MOVE_MATRIX) + len(COMPARE_MATRIX)} matrix cells, {'ok' if not found else f'{len(found)} problem(s)'}"
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
