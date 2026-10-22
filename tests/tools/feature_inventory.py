import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

# #4726: the scan core ships in the package (gitgalaxy/tools/readiness/inventory.py); this file keeps the fixture CLI.
from gitgalaxy.tools.readiness.inventory import (  # noqa: E402, F401
    census_lines,
    extract_sql_forms,
    fallback_parse,
    inventory_template,
    process_program,
    scan_estate,
)

SCHEMA_FILE = TOOLS / "feature_inventory.schema.json"


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
            if "unparsed_programs" not in data or "eras" not in data:
                raise ValueError
            for cat in data:
                if cat in ("unparsed_programs", "eras"):
                    continue
                if "unknown" not in data[cat] and cat not in ("refusal_families", "stand_in_copybooks", "call_targets"):
                    raise ValueError
                for k in data[cat]:
                    if "count" not in data[cat][k]:
                        raise ValueError
                    if "programs" not in data[cat][k]:
                        raise ValueError

    if args.all_burned:
        corpora_root = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", REPO / ".mainframe_corpora"))
        db_dir = Path(tempfile.mkdtemp(prefix="feature-inventory-"))  # fresh scans, never a shared path (#4825)
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
        db_dir = Path(tempfile.mkdtemp(prefix="feature-inventory-"))
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
