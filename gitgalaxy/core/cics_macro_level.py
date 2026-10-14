# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
# #5121: macro-level CICS and CICS Assembler, named so they are refused by name instead of reading as broken COBOL.
#
# Two refusal families, one detector for the scanner (the feature inventory, the support matrix) and the det translator:
#   - "macro-level CICS": the pre-command-level API (era 0, ~1969-80): `DFHPC TYPE=LINK`, `DFHFC TYPE=GET` ... macro
#     calls (an assembler statement, or a COBOL `CALL 'DFHFC'`), and CSA / TCA addressing (`USING DFHCSADS`, the
#     DFHCSADS / DFHTCADS DSECTs, `CSATCA`, and the obsolete command-level `EXEC CICS ADDRESS CSA / TCA`, which IBM's
#     DFHMSCAN utility reports as a macro-level leftover).
#   - "CICS Assembler": an HLASM program written for CICS, command level (`DFHEIENT` / `DFHEISTG` / `DFHEIRET` /
#     `EXEC CICS` in assembler) or macro level. The translator reads COBOL only.
#
# Not translated, only named. What this must NOT hit (each has a test):
#   - command-level COBOL (`EXEC CICS ...`, DFHRESP / DFHVALUE / DFHCOMMAREA / DFHEIBLK, `CALL 'DFHEI1'`);
#   - the macro TABLES (DFHFCT / PCT / PPT / DCT / TST / SIT / TCT ... `TYPE=`): resource definitions, read by
#     cics_macro_tables.py, not programs;
#   - BMS map macros (DFHMSD / DFHMDI / DFHMDF), comments and string literals.
#
# Sources (IBM): "Identify macro-level programs utility (DFHMSCAN)" in the CICS TS reference (it finds the DFH macro
# expansions of macro-level programs and `EXEC CICS ADDRESS CSA`); the assembler translation output (DFHEIENT /
# DFHEIRET) in CICS TS "Assembler translation output". The family list below is the macro-level application
# macros named `DFHxx TYPE=...` in the CICS macro-level reference; IBM's DFHMSCAN page does not enumerate them, so the
# list is ASSUMED complete to the extent register entry X-macro-level says (docs/language_status/register/).
# Every pattern is bounded and linear (no nested quantifier).
# ==============================================================================
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

FAMILY_MACRO = "macro-level CICS"
FAMILY_ASSEMBLER = "CICS Assembler"
FAMILIES = (FAMILY_MACRO, FAMILY_ASSEMBLER)
ASSEMBLER_SUFFIXES = frozenset({".asm", ".mac", ".hlasm", ".assemble", ".bal"})

# the application macros: BMS, built-in functions, dump, data interchange, file, interval, journal, task, program,
# storage, syncpoint, terminal, transient data, trace, temporary storage control, wait. `TYPE=` is required, which
# is what separates `DFHFC TYPE=GET` from the table macro `DFHFCT TYPE=DATASET` (a different operation name anyway).
MACROS = ("BMS", "BP", "DC", "DI", "FC", "IC", "JC", "KC", "PC", "SC", "SP", "TC", "TD", "TR", "TS", "WT")
_MACRO_ALT = "|".join(MACROS)
_CSA_TCA_NAMES = ("DFHCSADS", "DFHTCADS", "DFHCSA", "DFHTCA")
_CSA_ALT = "|".join(_CSA_TCA_NAMES)
# command-level assembler: the translator-generated prologue / epilogue and storage, or an EXEC CICS statement
_COMMAND_LEVEL_OPS = frozenset({"DFHEIENT", "DFHEISTG", "DFHEIEND", "DFHEIRET", "DFHEIGBL"})

_COBOL_CALL = re.compile(rf"\bCALL\s+['\"](DFH(?:{_MACRO_ALT}))['\"]", re.I)
_SYM = "A-Z0-9" + "@#$_"  # an HLASM / COBOL name character (built apart: one dense literal trips the entropy scan)
_COBOL_MACRO = re.compile(rf"(?<![{_SYM}-])(DFH(?:{_MACRO_ALT}))\s+TYPE\s*=\s*([{_SYM}]*)", re.I)
_COBOL_COPY = re.compile(rf"\bCOPY\s+({_CSA_ALT})\b", re.I)
_COBOL_ADDRESS = re.compile(
    r"\bEXEC\s+CICS\s+ADDRESS\b(?:(?!END-EXEC)[\s\S]){0,300}?\b(CSA|TCA)\s*\(",
    re.I,
)
_LITERAL = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"")
_ASM_STATEMENT = re.compile(r"^(\S*)[ \t]+(\S+)(?:[ \t]+(.*))?$")
_TYPE_OPERAND = re.compile(rf"(?:^|,)[ \t]*TYPE[ \t]*=[ \t]*([{_SYM}]*)", re.I)
_CSATCA = re.compile(rf"(?<![{_SYM}])CSATCA(?![{_SYM}])", re.I)
_STATEMENT_LIMIT = 200  # lines one statement may continue over (as hlasm_cics)


@dataclass(frozen=True)
class Hit:
    """One piece of evidence: the family it belongs to, what was seen, and the 1-based line it starts on."""

    family: str
    what: str
    line: int


def _blank_literals(text: str) -> str:
    return _LITERAL.sub(lambda m: m.group(0)[0] * 2, text)


def cobol_hits(texts: Sequence[str]) -> list[Hit]:
    """Evidence in COBOL code lines (the columns-8-72 text of det's logical lines: no comment lines). Line numbers are
    positions in `texts`, 1-based; a caller with its own numbering maps them back."""
    out: list[Hit] = []
    for n, raw in enumerate(texts, 1):
        out.extend(Hit(FAMILY_MACRO, f"CALL '{m.group(1).upper()}'", n) for m in _COBOL_CALL.finditer(raw))
        text = _blank_literals(raw)
        stripped = text.lstrip()
        if stripped.startswith(("*", "/")):
            continue
        cut = text.find("*>")
        if cut >= 0:
            text = text[:cut]
        out.extend(
            Hit(FAMILY_MACRO, f"{m.group(1).upper()} TYPE={m.group(2).upper()}".rstrip("="), n)
            for m in _COBOL_MACRO.finditer(text)
        )
        out.extend(
            Hit(FAMILY_MACRO, f"COPY {m.group(1).upper()} (CSA / TCA addressing)", n)
            for m in _COBOL_COPY.finditer(text)
        )
    # EXEC CICS ADDRESS ... CSA( / TCA( may span lines: read the joined code, report the line the command starts on
    joined = "\n".join(_blank_literals(t) for t in texts)
    starts = [m.start() for m in re.finditer(r"^", joined, re.M)]
    for m in _COBOL_ADDRESS.finditer(joined):
        line = sum(1 for s in starts if s <= m.start())
        out.append(Hit(FAMILY_MACRO, f"EXEC CICS ADDRESS {m.group(1).upper()} (CSA / TCA addressing)", line))
    return sorted(out, key=lambda h: h.line)


def _asm_statements(lines: Sequence[str]) -> list[tuple[int, str]]:
    """(first line, statement text) of each assembler statement: comment lines (`*` / `.*` in column 1) dropped, a
    statement continued by a non-blank column 72 resumed at column 16, the sequence field (73-80) dropped."""
    out: list[tuple[int, str]] = []
    i, total = 0, len(lines)
    while i < total:
        line = lines[i]
        if not line.strip() or line.startswith(("*", ".*")):
            i += 1
            continue
        first, stmt, steps = i + 1, line[:71].rstrip(), 0
        while len(line) > 71 and line[71] not in " \t" and i + 1 < total and steps < _STATEMENT_LIMIT:
            i += 1
            steps += 1
            line = lines[i]
            stmt += " " + line[15:71].strip() if len(line) > 15 else ""
        out.append((first, stmt))
        i += 1
    return out


def _first_operand(operands: str) -> str:
    head = operands.split(",", 1)[0].split()
    return head[0].upper() if head else ""


def assembler_hits(lines: Sequence[str]) -> list[Hit]:
    """Evidence in an assembler source (raw lines). A macro TABLE source (DFHFCT ...) and a BMS map source (DFHMSD ...)
    hold neither a macro-level call nor a command-level prologue, so they have no hit."""
    out: list[Hit] = []
    for n, stmt in _asm_statements(lines):
        m = _ASM_STATEMENT.match(stmt)
        if not m:
            continue
        op, operands = m.group(2).upper(), m.group(3) or ""
        if op in {f"DFH{x}" for x in MACROS}:
            t = _TYPE_OPERAND.search(operands)
            if t:
                out.append(Hit(FAMILY_MACRO, f"{op} TYPE={t.group(1).upper()}".rstrip("="), n))
        elif op in ("DFHCSADS", "DFHTCADS") or (op in ("USING", "COPY") and _first_operand(operands) in _CSA_TCA_NAMES):
            name = op if op.startswith("DFH") else _first_operand(operands)
            out.append(Hit(FAMILY_MACRO, f"{name} (CSA / TCA addressing)", n))
        elif _CSATCA.search(operands):
            out.append(Hit(FAMILY_MACRO, "CSATCA (CSA / TCA addressing)", n))
        if op in _COMMAND_LEVEL_OPS:
            out.append(Hit(FAMILY_ASSEMBLER, op, n))
        elif op == "EXEC" and operands.upper().startswith("CICS") and operands[4:5] in ("", " ", "\t"):
            out.append(Hit(FAMILY_ASSEMBLER, "EXEC CICS", n))
    if any(h.family == FAMILY_MACRO for h in out) and not any(h.family == FAMILY_ASSEMBLER for h in out):
        # a macro-level assembler program is a CICS Assembler program too (counted in both families)
        out.append(Hit(FAMILY_ASSEMBLER, "macro-level CICS in assembler", min(h.line for h in out)))
    return sorted(out, key=lambda h: (h.line, FAMILIES.index(h.family)))


def families(hits: Sequence[Hit]) -> list[str]:
    """The distinct families of `hits`, in FAMILIES order."""
    seen = {h.family for h in hits}
    return [f for f in FAMILIES if f in seen]


def refusal_text(hit: Hit, file: str) -> str:
    """The by-name refusal a translator gives for `hit`. Contains `<family> not supported`, which refusal_map.json's
    entries match (and cics_census.error_key keys the blocker report by)."""
    where = f"{file}:{hit.line}"
    if hit.family == FAMILY_MACRO:
        return (
            f"{where}: {FAMILY_MACRO} not supported ({hit.what}): the pre-command-level API (era 0), not EXEC CICS; "
            "named and refused, never translated"
        )
    return (
        f"{where}: {FAMILY_ASSEMBLER} not supported ({hit.what}): an assembler program, and the translator reads COBOL; "
        "named and refused, never translated"
    )
