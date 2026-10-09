import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

from gitgalaxy.core.estate_options import effective_options, load_estate  # noqa: E402
from gitgalaxy.core.source_text import read_source  # noqa: E402
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import layout as L  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import source as S  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import stmt as ST  # noqa: E402
from tests.tools.det_survey import copy_dirs  # noqa: E402

SCHEMA_FILE = TOOLS / "feature_inventory.schema.json"


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


def count_unknown(inv, category, prog_rel):
    # Just count once if we do it for a whole program failure
    count_item(inv, category, "unknown", prog_rel)


def _copy_not_found(e: Exception) -> str:
    m = re.search(r"COPY \S+", str(e))
    return m.group(0) if m else str(e).split(" found in")[0][-80:]


def fallback_parse(prog, rel_prog, inv):
    text = read_source(prog).text
    cics_blocks = re.findall(r"(?i)\bEXEC\s+CICS\s+(.*?)\bEND-EXEC\b", text, re.S)
    for block in cics_blocks:
        try:
            words, opts = C.parse_exec("EXEC CICS " + block + " END-EXEC")
            verb = " ".join(words)
            count_item(inv, "cics_commands", verb, rel_prog)
            for opt_k in opts:
                count_item(inv, "cics_options", f"{verb}: {opt_k}", rel_prog)
        except Exception:  # noqa: PERF203
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

    forms = []
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


def process_program(prog: Path, estate_dir: Path, ir, estate_opt, inv, estate_copy_dirs: list[Path]):
    rel_prog = str(prog.relative_to(estate_dir)).replace("\\", "/")

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
    except S.CopyNotFound as e:
        count_item(inv, "copybook_resolution_gaps", _copy_not_found(e), rel_prog)
        inv["unparsed_programs"].append({"program": rel_prog, "reason": type(e).__name__ + " - " + str(e)})
        fallback_parse(prog, rel_prog, inv)
        return

    try:
        units = S.program_units(lines)
    except Exception as e:
        inv["unparsed_programs"].append({"program": rel_prog, "reason": type(e).__name__ + " - " + str(e)})
        fallback_parse(prog, rel_prog, inv)
        return

    for unit in units:
        # Data Division
        try:
            records = L.parse(unit.lines)
            for rec in records:
                for it in rec.walk():
                    u = it.usage.upper() if it.usage else ""
                    if u in {"COMP-1", "COMP-2", "COMP-3", "COMP-5", "BINARY", "PACKED", "NATIONAL"}:
                        count_item(inv, "data_types", u, rel_prog)
                    if it.pic and it.pic.upper().startswith("N"):
                        count_item(inv, "data_types", "NATIONAL", rel_prog)

                    if it.p_scaled:
                        count_item(inv, "data_types", "P-SCALED", rel_prog)

                    if "EDITED" in it.category:
                        count_item(inv, "data_types", "EDITED", rel_prog)
        except Exception:
            count_unknown(inv, "data_types", rel_prog)

        # Procedure Division
        try:
            proc = ST.parse(unit.lines)
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


def scan_estate(estate_dir: Path, db_dir: Path) -> dict:
    inv = inventory_template()
    # Pre-populate unknown
    for cat in inv:
        inv[cat]["unknown"] = {"count": 0, "programs": set()}
    inv["unparsed_programs"] = []

    print(f"Scanning estate: {estate_dir.name}", file=sys.stderr)
    db_path = scan_to_db(estate_dir, db_dir)
    ir = load_galaxy_ir(db_path)
    estate_opt = load_estate(estate_dir.name)

    progs = sorted(
        [
            p
            for p in estate_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in {".cbl", ".cob", ".cobol"} and ".git" not in p.parts
        ]
    )

    bms = db_dir / "bms"
    bms.mkdir(exist_ok=True)
    S.bms_copybooks(
        [p for p in estate_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".bms" and ".git" not in p.parts], bms
    )
    estate_copy_dirs = [*copy_dirs(estate_dir), bms, C.COPY]
    for prog in progs:
        process_program(prog, estate_dir, ir, estate_opt, inv, estate_copy_dirs)

    # Convert sets to sorted lists, sort dict keys
    out = {}
    for cat in sorted(inv.keys()):
        if cat == "unparsed_programs":
            continue
        out[cat] = {}
        for k in sorted(inv[cat].keys()):
            # Always ensure "unknown" is present, already did via template
            out[cat][k] = {"count": inv[cat][k]["count"], "programs": sorted(inv[cat][k]["programs"])}

    out["unparsed_programs"] = sorted(inv["unparsed_programs"], key=lambda x: x["program"])
    return out


def main():
    parser = argparse.ArgumentParser(description="Feature inventory extractor")
    parser.add_argument("estate_dir", type=Path, nargs="?", help="Estate directory")
    parser.add_argument("--out", type=Path, help="Output JSON file")
    parser.add_argument("--all-burned", action="store_true", help="Run all burned estates")
    parser.add_argument("--write", action="store_true", help="Write fixtures")
    parser.add_argument("--check", action="store_true", help="Check fixtures")
    args = parser.parse_args()

    try:
        import jsonschema
    except ImportError:
        jsonschema = None

    schema = json.loads(SCHEMA_FILE.read_text())

    def validate(data):
        if jsonschema:
            jsonschema.validate(instance=data, schema=schema)
        else:
            if "unparsed_programs" not in data:
                raise ValueError
            for cat in data:
                if cat == "unparsed_programs":
                    continue
                if "unknown" not in data[cat]:
                    raise ValueError
                for k in data[cat]:
                    if "count" not in data[cat][k]:
                        raise ValueError
                    if "programs" not in data[cat][k]:
                        raise ValueError

    if args.all_burned:
        corpora_root = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", REPO / ".mainframe_corpora"))
        db_dir = Path("/tmp/gitgalaxy-scratch/agy-4723/db")  # noqa: S108
        db_dir.mkdir(parents=True, exist_ok=True)
        fixtures_dir = TOOLS.parent / "fixtures" / "feature_inventory"
        if args.write:
            fixtures_dir.mkdir(parents=True, exist_ok=True)

        estates = [
            "aws-mainframe-modernization-carddemo",
            "cics-banking-sample-application-cbsa",
            "cics-genapp",
            "zecs",
            "dbb-mortgage-application",
            "cics-async-api-credit-card-application-example",
        ]

        has_stale = False
        for estate_name in estates:
            estate_dir = corpora_root / estate_name
            if not estate_dir.is_dir():
                print(f"Skipping {estate_name}: not found at {estate_dir}", file=sys.stderr)
                continue

            data = scan_estate(estate_dir, db_dir)
            validate(data)

            fixture_path = fixtures_dir / f"{estate_name}.json"
            new_text = json.dumps(data, indent=2, sort_keys=True) + "\n"

            if args.write:
                fixture_path.write_text(new_text)
                print(f"Wrote {fixture_path}", file=sys.stderr)
            elif args.check:
                if not fixture_path.exists():
                    print(f"Missing fixture: {fixture_path}", file=sys.stderr)
                    has_stale = True
                else:
                    old_text = fixture_path.read_text()
                    if old_text != new_text:
                        print(f"Stale fixture: {fixture_path}", file=sys.stderr)
                        has_stale = True

        if args.check and has_stale:
            sys.exit(1)
    elif args.estate_dir:
        db_dir = Path("/tmp/gitgalaxy-scratch/agy-4723/db")  # noqa: S108
        db_dir.mkdir(parents=True, exist_ok=True)
        data = scan_estate(args.estate_dir, db_dir)
        validate(data)
        text = json.dumps(data, indent=2, sort_keys=True)
        if args.out:
            args.out.write_text(text + "\n")
        else:
            print(text)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
