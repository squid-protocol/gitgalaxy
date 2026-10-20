# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4723: the feature inventory of one estate -- every statement, data type, CICS command and option, SQL form,
intrinsic function and compile option its COBOL programs use, with the programs that use each, plus their era tags
(#5117) and the programs the parser could not read.

Shipped in the package for the readiness scanner (#4726): `gitgalaxy assess` runs `scan_estate` and then projects
the result through `gitgalaxy.tools.readiness.schema`, the only path to its output. This raw inventory may carry
source-derived text (a parser message, a sequence number read as a command word); it is never written to a customer
report as it stands. tests/tools/feature_inventory.py writes the burned estates' committed fixtures from it.
"""

import dataclasses
import functools
import re
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gitgalaxy.core import cics_macro_level as ML
from gitgalaxy.core.estate_options import effective_options, load_estate
from gitgalaxy.core.source_text import read_source
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db
from gitgalaxy.tools.cobol_to_java.det import cics as C
from gitgalaxy.tools.cobol_to_java.det import layout as L
from gitgalaxy.tools.cobol_to_java.det import source as S
from gitgalaxy.tools.cobol_to_java.det import stmt as ST
from gitgalaxy.tools.readiness.era_tags import asm_members, mark_skipped, summarise, tag_program

REPO = Path(__file__).resolve().parents[3]  # a checkout's root: `_portable` strips it from a reason
COPY_EXTS = {".cpy", ".copy", ".cbl", ".cob", ""}  # tests/tools/det_survey.py's
_UNSET = object()


def copy_dirs(corpus: Path) -> list[Path]:
    """Every directory holding a copybook-like member, the program's own first (tests/tools/det_survey.py's)."""
    dirs = sorted({p.parent for p in corpus.rglob("*") if p.is_file() and p.suffix.lower() in COPY_EXTS
                   and ".git" not in p.parts})  # fmt: skip
    return dirs


def inventory_template():
    return {
        "statements": defaultdict(lambda: {"count": 0, "programs": set()}),
        "data_types": defaultdict(lambda: {"count": 0, "programs": set()}),
        "cics_commands": defaultdict(lambda: {"count": 0, "programs": set()}),
        "cics_options": defaultdict(lambda: {"count": 0, "programs": set()}),
        "sql_forms": defaultdict(lambda: {"count": 0, "programs": set()}),
        "intrinsic_functions": defaultdict(lambda: {"count": 0, "programs": set()}),
        "compile_options": defaultdict(lambda: {"count": 0, "programs": set()}),
        "copybook_resolution_gaps": defaultdict(lambda: {"count": 0, "programs": set()}),
    }


def count_item(inv, category, key, prog_rel):
    inv[category][key]["count"] += 1
    inv[category][key]["programs"].add(prog_rel)


def count_refusal_family(inv, family, prog_rel):
    """#5121: a program of a family refused by name (macro-level CICS, CICS Assembler). The category exists only once
    an estate has one (never an empty `refusal_families`), so an estate without any keeps its fixture byte for byte."""
    inv.setdefault("refusal_families", defaultdict(lambda: {"count": 0, "programs": set()}))
    count_item(inv, "refusal_families", family, prog_rel)


def count_stand_ins(inv, lines, prog_rel):
    """#5565: the stand-in copybooks (CEEIGZCT, the CMQ* members; register L4 / W1) a program's COPY expansion read
    from the engine's shipped directory because the estate has no member of that name. The category exists only once
    an estate has one, so an estate without any keeps its fixture byte for byte."""
    from gitgalaxy.core.copy_libraries import STAND_IN_DIR, stand_in_registers

    shipped = STAND_IN_DIR.resolve()
    members = {Path(ln.file).stem.upper() for ln in lines if Path(ln.file).resolve().parent == shipped}
    for member in sorted(members & set(stand_in_registers())):
        inv.setdefault("stand_in_copybooks", defaultdict(lambda: {"count": 0, "programs": set()}))
        count_item(inv, "stand_in_copybooks", member, prog_rel)


def count_call_target(inv, stmt, prog_rel):
    """#5565: the program a CALL names (a literal, upper-cased), or `(dynamic)` for a CALL through an identifier: an
    unmodelled API is otherwise detected only through its copybook (CMQ*). The category exists only once an estate has
    a CALL, so an estate without any keeps its fixture byte for byte."""
    if stmt.data.get("dynamic"):
        key = "(dynamic)"
    else:
        key = str(stmt.data.get("program") or "").strip("'\"").upper()
    if key and not re.fullmatch(r"GG[A-Z]{3,4}\d{4}", key):  # the parser's own EXEC / SORT / ENTRY stand-in CALLs
        inv.setdefault("call_targets", defaultdict(lambda: {"count": 0, "programs": set()}))
        count_item(inv, "call_targets", key, prog_rel)


def count_unknown(inv, category, prog_rel):
    # Just count once if we do it for a whole program failure
    count_item(inv, category, "unknown", prog_rel)


def _copy_not_found(e: Exception) -> str:
    m = re.search(r"COPY \S+", str(e))
    return m.group(0) if m else str(e).split(" found in")[0][-80:]


_FREE_FORMAT = re.compile(r"(?im)^\s*>>\s*SOURCE\s+(?:FORMAT\s+)?(?:IS\s+)?FREE\b")


def program_text(text: str) -> str:
    """#5106: fixed-form source as program words only. Columns 1-6 (sequence numbers) and 73+ (identification tag) are
    blanked and a comment line (column 7 `*` or `/`) emptied, so a regex over a multi-line `EXEC` block never reads a
    sequence number as a word (`RETRIEVE 01327507`). Line count and columns 8-72 are kept; free-form source (a
    `>>SOURCE FORMAT FREE` directive) is returned as it is."""
    if _FREE_FORMAT.search(text):
        return text
    out = []
    for ln in text.splitlines():
        if len(ln) > 6 and ln[6] in "*/":
            out.append("")
        else:
            out.append(" " * min(len(ln), 6) + ln[6:72])
    return "\n".join(out)


def fallback_parse(prog, rel_prog, inv):
    text = program_text(read_source(prog).text)
    cics_blocks = re.findall(r"(?i)\bEXEC\s+CICS\s+(.*?)\bEND-EXEC\b", text, re.S)
    for block in cics_blocks:
        try:
            words, opts = C.parse_exec("EXEC CICS " + block + " END-EXEC")
            verb = " ".join(words)
            count_item(inv, "cics_commands", verb, rel_prog)
            for opt_k in opts:
                count_item(inv, "cics_options", f"{verb}: {opt_k}", rel_prog)
        except Exception:
            count_unknown(inv, "cics_commands", rel_prog)
            count_unknown(inv, "cics_options", rel_prog)

    # SQL
    sqls = re.findall(r"(?i)\bEXEC\s+SQL\s+(.*?)\bEND-EXEC\b", text, re.S)
    for s in sqls:
        s_up = s.upper()
        if "DECLARE" in s_up and "CURSOR" in s_up:
            count_item(inv, "sql_forms", "DECLARE CURSOR", rel_prog)
        elif "WHENEVER" in s_up:
            count_item(inv, "sql_forms", "WHENEVER", rel_prog)
        elif "PREPARE" in s_up or "EXECUTE" in s_up:
            count_item(inv, "sql_forms", "DYNAMIC", rel_prog)
        else:
            count_item(inv, "sql_forms", "STATIC", rel_prog)

    # FUNCTION
    funcs = re.findall(r"(?i)\bFUNCTION\s+([A-Z0-9-]+)\b", text)
    for f in funcs:
        count_item(inv, "intrinsic_functions", f.upper(), rel_prog)

    # Statements
    verbs = [
        "MOVE",
        "PERFORM",
        "IF",
        "EVALUATE",
        "COMPUTE",
        "ADD",
        "SUBTRACT",
        "MULTIPLY",
        "DIVIDE",
        "CALL",
        "READ",
        "WRITE",
        "REWRITE",
        "DELETE",
        "START",
        "OPEN",
        "CLOSE",
        "EXIT",
        "GOBACK",
        "STOP",
        "DISPLAY",
        "ACCEPT",
        "GOTO",
        "SEARCH",
        "SORT",
        "MERGE",
        "INSPECT",
        "STRING",
        "UNSTRING",
        "INITIALIZE",
    ]
    verb_pattern = r"(?i)\b(" + "|".join(verbs) + r")\b"
    code = re.sub(r"^\s{6}\*.*", "", text, flags=re.MULTILINE)  # remove comment lines
    code = re.sub(r"'.*?'|\".*?\"", "", code)  # remove strings
    found_verbs = re.findall(verb_pattern, code)
    for v in found_verbs:
        count_item(inv, "statements", v.upper(), rel_prog)


def extract_sql_forms(text: str) -> list[str]:

    forms: list[str] = []
    body = re.sub(r"(?is)^\s*EXEC\s+SQL\b", "", text)
    body = re.sub(r"(?is)\bEND-EXEC\b\s*$", "", body).strip()
    u = body.upper()
    verb = u.split()[0] if u else ""
    if not verb:
        return forms
    forms.append(verb)
    if verb == "DECLARE" and "CURSOR" in u:
        forms.append("DECLARE CURSOR")
    if verb in ("PREPARE", "EXECUTE", "DESCRIBE", "EXECUTE IMMEDIATE"):
        forms.append("DYNAMIC")
    else:
        forms.append("STATIC")
    return forms


def walk_stmt(stmt):
    yield stmt
    for b in stmt.body:
        yield from walk_stmt(b)
    for o in stmt.orelse:
        yield from walk_stmt(o)
    for _cond, b_list in stmt.whens:
        for b in b_list:
            yield from walk_stmt(b)
    for p_body in stmt.phrases.values():
        for b in p_body:
            yield from walk_stmt(b)


def census_lines(lines: list[S.Line]) -> tuple[list[S.Line], bool]:
    """#4664: the translator refuses a program holding national / DBCS data (PIC N / G, USAGE NATIONAL / DISPLAY-1, an N / G
    literal) whole, since it would lay it out one byte a character. A census counts what the source declares, so the same
    lines with that data read as plain text (PIC X, no usage, no literal prefix) -- a stand-in for counting only, never a
    translation -- and whether any was there (counted as NATIONAL). Everything else a program holds is counted as before."""
    out, seen = [], False
    for ln in lines:
        text = ln.text
        if S._national_data(S._outside_literals(text[: S._comment_at(text)])) is not None:
            seen = True
            text = re.sub(
                r"(?<![\w-])(PIC(?:TURE)?(?:\s+IS)?\s+)(?=\S*[NGng])\S+?(?=\.?(?:\s|$))", r"\1X", text, flags=re.I
            )
            text = re.sub(r"(?:USAGE\s+(?:IS\s+)?)?" + S._NATIONAL_USAGE.pattern, "", text, flags=re.I)
            text = S._NATIONAL_LITERAL.sub("", text)
        out.append(dataclasses.replace(ln, text=text) if text != ln.text else ln)
    return out, seen


def _tag_with_copybooks(prog: Path, estate_dir: Path, rel_prog: str, lines: list[S.Line], inv) -> None:
    """#5117: re-tag a program whose COPY expansion succeeded with the tells inside the copybooks it resolved (the
    member files of the expanded lines, nested ones too), keyed by estate-relative path (a member outside the estate, e.g. the engine's own copybook: by name)."""
    members = {Path(ln.file).resolve() for ln in lines} - {prog.resolve()}
    root = estate_dir.resolve()
    books: dict[str, str] = {}
    unreadable = False
    for m in sorted(members):
        name = m.relative_to(root).as_posix() if m.is_relative_to(root) else m.name  # (engine copies: by name)
        try:
            books[name] = read_source(m).text
        except Exception:  # an unreadable member adds no tell; the program's own tag stands, marked (#5195)
            unreadable = True
    if books:
        inv["eras"][rel_prog] = tag_program(read_source(prog).text, books)
    if unreadable:
        inv["eras"][rel_prog] = mark_skipped(inv["eras"][rel_prog], "UnreadableCopybook")


def _skipped(inv, rel_prog: str, reason: str) -> None:
    """#5195: the program's COPY expansion was refused, so its tag could not read the copybooks: say so on the tag."""
    if rel_prog in inv["eras"]:
        inv["eras"][rel_prog] = mark_skipped(inv["eras"][rel_prog], reason)


def _asm_member_finder(estate_dir: Path):
    """name -> (estate-relative path, text) of the assembler / copy member of that name (case-insensitive, any of the
    assembler suffixes, `.cpy` / `.copy` / `.inc` or none), the first in path order; None if the estate has none."""
    index: dict[str, Path] = {}
    suffixes = ML.ASSEMBLER_SUFFIXES | {".cpy", ".copy", ".inc", ""}
    for p in sorted(estate_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in suffixes and ".git" not in p.parts:
            index.setdefault(p.stem.upper() if p.suffix else p.name.upper(), p)

    def find(name: str):
        p = index.get(name.upper())
        if p is None:
            return None
        try:
            return p.relative_to(estate_dir).as_posix(), read_source(p).text
        except Exception:
            return None

    return find


def _member_but(find, rel: str, name: str):
    """`find(name)` except the member being read: it never expands itself."""
    found = find(name)
    return None if found is None or found[0] == rel else found


def process_program(prog: Path, estate_dir: Path, ir, estate_opt, inv, estate_copy_dirs: list[Path]):
    rel_prog = str(prog.relative_to(estate_dir)).replace("\\", "/")

    # 0. Era tag (#5117): from the raw text, so a program the parser refuses is tagged too
    try:
        inv.setdefault("eras", {})[rel_prog] = tag_program(read_source(prog).text)
    except Exception:
        inv.setdefault("eras", {})[rel_prog] = {"era": None, "earliest": None, "mixed": False, "tells": []}

    # 1. Compile options
    try:
        source_text = read_source(prog).text
        opt = effective_options(case=None, estate=estate_opt, program=prog.stem)
        sem = opt.semantic(source_text)
        for k, v in sem.items():
            count_item(inv, "compile_options", f"{k}: {v}", rel_prog)
    except Exception:
        count_unknown(inv, "compile_options", rel_prog)

    # 2. Engine copies
    engine_copies = S.engine_copies_from_ir(ir, rel_prog, estate_dir)

    try:
        lines = S.program_lines(prog, estate_copy_dirs, engine_copies)
        _tag_with_copybooks(prog, estate_dir, rel_prog, lines, inv)
        count_stand_ins(inv, lines, rel_prog)
    except S.MacroLevelCics as e:  # #5121: refused by name, before COPY expansion; not parsed as COBOL with holes
        _skipped(inv, rel_prog, "MacroLevelCics")
        for m in re.finditer(r"(macro-level CICS|CICS Assembler) not supported", str(e)):
            count_refusal_family(inv, m.group(1), rel_prog)
        inv["unparsed_programs"].append(
            {"program": rel_prog, "reason": type(e).__name__ + " - " + _portable(str(e), estate_dir)}
        )
        return
    except S.CopyNotFound as e:
        _skipped(inv, rel_prog, "CopyNotFound")
        count_item(inv, "copybook_resolution_gaps", _copy_not_found(e), rel_prog)
        inv["unparsed_programs"].append({"program": rel_prog, "reason": f"CopyNotFound: {_copy_not_found(e)}"})
        fallback_parse(prog, rel_prog, inv)
        return
    except Exception as e:  # e.g. NotCobol (an ISPF screen dump saved as .cbl): unparsed, but already era-tagged above
        _skipped(inv, rel_prog, type(e).__name__)
        inv["unparsed_programs"].append(
            {"program": rel_prog, "reason": type(e).__name__ + " - " + _portable(str(e), estate_dir)}
        )
        return

    try:
        units = S.program_units(lines)
    except Exception as e:
        inv["unparsed_programs"].append(
            {"program": rel_prog, "reason": type(e).__name__ + " - " + _portable(str(e), estate_dir)}
        )
        fallback_parse(prog, rel_prog, inv)
        return

    for unit in units:
        unit_lines, national = census_lines(unit.lines)
        if national:
            count_item(inv, "data_types", "NATIONAL", rel_prog)
        # Data Division
        try:
            records = L.parse(unit_lines)
            for rec in records:
                for it in rec.walk():
                    u = it.usage.upper() if it.usage else ""
                    if u in {"COMP-1", "COMP-2", "COMP-3", "COMP-5", "BINARY", "PACKED", "NATIONAL"}:
                        count_item(inv, "data_types", u, rel_prog)
                    if it.p_scaled:
                        count_item(inv, "data_types", "P-SCALED", rel_prog)

                    if "EDITED" in it.category:
                        count_item(inv, "data_types", "EDITED", rel_prog)
        except Exception:
            count_unknown(inv, "data_types", rel_prog)

        # Procedure Division
        try:
            proc = ST.parse(unit_lines)
            for paragraph in proc.paragraphs:
                for top_stmt in paragraph.body:
                    for stmt in walk_stmt(top_stmt):
                        if stmt.kind == "HOLE":
                            count_unknown(inv, "statements", rel_prog)
                        elif stmt.kind == "EXEC":
                            text = stmt.text
                            if text.upper().startswith("EXEC CICS"):
                                try:
                                    words, opts = C.parse_exec(text)
                                    verb = " ".join(words)
                                    count_item(inv, "cics_commands", verb, rel_prog)
                                    for opt_k in opts:
                                        count_item(inv, "cics_options", f"{verb}: {opt_k}", rel_prog)
                                except Exception:
                                    count_unknown(inv, "cics_commands", rel_prog)
                                    count_unknown(inv, "cics_options", rel_prog)
                            elif text.upper().startswith("EXEC SQL"):
                                forms = extract_sql_forms(text)
                                if forms:
                                    for f in forms:
                                        count_item(inv, "sql_forms", f, rel_prog)
                                else:
                                    count_unknown(inv, "sql_forms", rel_prog)
                        else:
                            count_item(inv, "statements", stmt.kind, rel_prog)
                            if stmt.kind == "CALL":
                                count_call_target(inv, stmt, rel_prog)

                        # Intrinsic functions
                        funcs = re.findall(r"\bFUNCTION\s+([A-Z0-9-]+)\b", stmt.text, re.I)
                        for f in funcs:
                            count_item(inv, "intrinsic_functions", f.upper(), rel_prog)
        except Exception:
            count_unknown(inv, "statements", rel_prog)
            count_unknown(inv, "cics_commands", rel_prog)
            count_unknown(inv, "cics_options", rel_prog)
            count_unknown(inv, "sql_forms", rel_prog)
            count_unknown(inv, "intrinsic_functions", rel_prog)


def _portable(msg: str, estate_dir: Path) -> str:
    """A reason with no machine-specific path in it (#4825): the fixtures are compared byte for byte on any checkout."""
    for root in (str(estate_dir), str(REPO)):
        msg = msg.replace(root + "/", "").replace(root, ".")
    return re.sub(r"/(?:[\w.+-]+/)+([\w.+-]+)", r"\1", msg)  # any other absolute path: its last component


def scan_estate(
    estate_dir: Path, db_dir: Path, scan: Callable[[Path, Path], Path] = scan_to_db, estate_opt: object = _UNSET
) -> dict:
    """The raw inventory of `estate_dir`; `db_dir` takes the scan's master DB and the BMS copybooks. `scan` runs the
    galaxyscope scan (the assess command passes its offline-guarded one); `estate_opt` is the estate options file's
    content (default: the committed file of a corpus of that name, if any)."""
    inv = inventory_template()
    # Pre-populate unknown
    for cat in inv:
        inv[cat]["unknown"] = {"count": 0, "programs": set()}
    inv["unparsed_programs"] = []
    inv["eras"] = {}
    inv["asm_eras"] = {}

    print(f"Scanning estate: {estate_dir.name}", file=sys.stderr)
    db_path = scan(estate_dir, db_dir)
    ir = load_galaxy_ir(db_path)
    if estate_opt is _UNSET:
        estate_opt = load_estate(estate_dir.name)

    progs = sorted(
        [
            p
            for p in estate_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in {".cbl", ".cob", ".cobol"} and ".git" not in p.parts
        ]
    )

    # #5121: assembler members (CICS Assembler, macro-level CICS); a macro TABLE source (DFHFCT ...) has no hit
    find_member = _asm_member_finder(estate_dir)
    for asm in sorted(
        p
        for p in estate_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in ML.ASSEMBLER_SUFFIXES and ".git" not in p.parts
    ):
        rel_asm = str(asm.relative_to(estate_dir)).replace("\\", "/")
        try:
            asm_text = read_source(asm).text
            hits = ML.assembler_hits(asm_text.splitlines())
        except Exception:  # noqa: S112 -- an unreadable member has no hit
            continue
        # #5195: era-tag the member with the COPY / macro members it pulls in (nested too); a refused expansion is marked
        books, skip = asm_members(asm_text, functools.partial(_member_but, find_member, rel_asm))
        tag = tag_program(asm_text, books, asm=True)
        if skip:
            tag = mark_skipped(tag, skip)
        if tag["tells"] or skip:  # a member with nothing to say adds no row to the estate's tags
            inv["asm_eras"][rel_asm] = tag
        for family in ML.families(hits):
            count_refusal_family(inv, family, str(asm.relative_to(estate_dir)).replace("\\", "/"))

    bms = db_dir / "bms"
    bms.mkdir(exist_ok=True)
    S.bms_copybooks(
        [p for p in estate_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".bms" and ".git" not in p.parts], bms
    )
    estate_copy_dirs = [*copy_dirs(estate_dir), bms, C.COPY]
    for prog in progs:
        process_program(prog, estate_dir, ir, estate_opt, inv, estate_copy_dirs)

    # Convert sets to sorted lists, sort dict keys
    out: dict[str, Any] = {}
    for cat in sorted(inv.keys()):
        if cat in ("unparsed_programs", "eras", "asm_eras"):
            continue
        out[cat] = {}
        for k in sorted(inv[cat].keys()):
            # Always ensure "unknown" is present, already did via template
            out[cat][k] = {"count": inv[cat][k]["count"], "programs": sorted(inv[cat][k]["programs"])}

    tags = {p: inv["eras"][p] for p in sorted(inv["eras"])}
    out["eras"] = {"programs": tags, "summary": summarise(tags)}
    if inv["asm_eras"]:  # present only when the estate has assembler members (#5195)
        out["eras"]["assembler"] = {p: inv["asm_eras"][p] for p in sorted(inv["asm_eras"])}
    out["unparsed_programs"] = sorted(inv["unparsed_programs"], key=lambda x: x["program"])
    return out
