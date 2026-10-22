"""#4723 feature inventory: per-category synthetic snippets, determinism, the schema, and the committed fixtures."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")  # the det parser; the ground-truth CI job has no translator extra

from tests.tools.feature_inventory import SCHEMA_FILE, TOOLS, scan_estate  # noqa: E402

CORPORA = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", TOOLS.parents[1] / ".mainframe_corpora"))


SNIPPETS = {
    "era_mixed": """       ID DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 BLL-CELLS PIC X.
       PROCEDURE DIVISION.
           EXEC CICS HANDLE CONDITION NOTFND(E1) END-EXEC.
           EXEC CICS PUT CONTAINER('C') CHANNEL('CH')
               FROM(BLL-CELLS) END-EXEC.
           GOBACK.
""",
    "era_copy": """       ID DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY ERACPY.
       PROCEDURE DIVISION.
           GOBACK.
""",
    "era_unparsed": """       ID DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY NOSUCHCPY.
       PROCEDURE DIVISION.
           EXEC SQL COMMIT END-EXEC.
           GOBACK.
""",
    "statements": "       ID DIVISION.\n       PROGRAM-ID. P.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n       01 X PIC 9.\n       PROCEDURE DIVISION.\n           ADD 1 TO X.\n           GOBACK.\n",
    "data_types": """       ID DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 V1 PIC S9(4) COMP-3.
       01 V2 PIC 99PP.
       01 V3 PIC $$$,$$$.99.
       01 V4 USAGE COMP-1.
       01 V5 USAGE COMP-2.
       01 V6 PIC N(10) USAGE NATIONAL.
       PROCEDURE DIVISION.
           GOBACK.
""",
    "cics_commands_and_options": """       ID DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 V1 PIC X(10).
       PROCEDURE DIVISION.
           EXEC CICS SEND TEXT FROM(V1) END-EXEC.
           GOBACK.
""",
    "sql_forms": """       ID DIVISION.
       PROGRAM-ID. P.
       PROCEDURE DIVISION.
           EXEC SQL DECLARE C1 CURSOR FOR SELECT * FROM T1 END-EXEC.
           EXEC SQL WHENEVER NOT FOUND GO TO ERR END-EXEC.
           EXEC SQL PREPARE S1 FROM :SQL-STMT END-EXEC.
           GOBACK.
""",
    "intrinsic_functions": """       ID DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 V1 PIC X(20).
       PROCEDURE DIVISION.
           MOVE FUNCTION CURRENT-DATE TO V1.
           GOBACK.
""",
    "compile_options": """CBL NUMPROC(PFD)
       ID DIVISION.
       PROGRAM-ID. P.
       PROCEDURE DIVISION.
           GOBACK.
""",
    "copybook_gap": """       ID DIVISION.
       PROGRAM-ID. P.
       PROCEDURE DIVISION.
           COPY MISSING.
           GOBACK.
""",
    "fallback": """       ID DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 V1 PIC 99.
       PROCEDURE DIVISION.
           COPY MISSING.
           EXEC CICS READ FILE('bogus') END-EXEC.
           EXEC SQL EXECUTE S1 END-EXEC.
           MOVE 1 TO V1.
           GOBACK.
""",
}  # one program per feature category, all scanned together ONCE (a full engine scan is 18-33 s)


COPYBOOKS = {"ERACPY": "       01 BLL-CELLS PIC X.\n"}  # a tell that only a copybook shows
# #5195 assembler members: a COPY member, a macro member called by name, nested ones, and a COPY that resolves to nothing
ASM = {
    "era_asm.asm": "ASMMAIN  CSECT\n         COPY  ASMBOOK\n         ASMMAC X\n         END\n",
    "ASMBOOK.mac": "         COPY  ASMDEEP\n",
    "ASMDEEP.mac": "         DFHPC TYPE=LINK,PROGRAM=SUB\n",
    "ASMMAC.mac": "         MACRO\n         ASMMAC &A\n         DFHTC TYPE=WRITE\n         MEND\n",
    "era_asm_gap.asm": "GAPMAIN  CSECT\n         COPY  NOSUCH\n         END\n",
}


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    """(estate dir, db dir, inventory) for the combined synthetic estate; tmp_path_factory keeps it xdist-safe."""
    base = tmp_path_factory.mktemp("feature_inventory")
    d = base / "estate"
    d.mkdir()
    for name, code in SNIPPETS.items():
        (d / f"{name}.cbl").write_text(code)
    for name, code in COPYBOOKS.items():
        (d / f"{name}.cpy").write_text(code)
    for name, code in ASM.items():
        (d / name).write_text(code)
    db_dir = base / "db"
    db_dir.mkdir()
    return d, db_dir, scan_estate(d, db_dir)


def has(inv, category, key, snippet):
    """The feature `key` was reported in `category` by the program of that snippet (not by a sibling's)."""
    return key in inv[category] and f"{snippet}.cbl" in inv[category][key]["programs"]


def test_determinism(synthetic):
    d, db_dir, inv1 = synthetic
    inv2 = scan_estate(d, db_dir)
    assert json.dumps(inv1, sort_keys=True) == json.dumps(inv2, sort_keys=True)  # noqa: S101


def test_statements(synthetic):
    inv = synthetic[2]
    assert has(inv, "statements", "ARITH", "statements")  # noqa: S101
    assert has(inv, "statements", "GOBACK", "statements")  # noqa: S101


def test_data_types(synthetic):
    inv = synthetic[2]
    assert has(inv, "data_types", "PACKED", "data_types")  # noqa: S101
    assert has(inv, "data_types", "P-SCALED", "data_types")  # noqa: S101
    assert has(inv, "data_types", "EDITED", "data_types")  # noqa: S101
    assert has(inv, "data_types", "COMP-1", "data_types")  # noqa: S101
    assert has(inv, "data_types", "COMP-2", "data_types")  # noqa: S101
    assert has(inv, "data_types", "NATIONAL", "data_types")  # noqa: S101


def test_era_tags(synthetic):
    """#5117: every scanned program is tagged, a mixed one says so, and a program the parser refuses is still tagged."""
    eras = synthetic[2]["eras"]
    assert sorted(eras["programs"]) == sorted(f"{n}.cbl" for n in SNIPPETS)  # noqa: S101
    mixed = eras["programs"]["era_mixed.cbl"]
    assert (mixed["era"], mixed["earliest"], mixed["mixed"]) == (4, 1, True)  # noqa: S101
    unparsed = eras["programs"]["era_unparsed.cbl"]
    assert (unparsed["era"], unparsed["mixed"]) == (2, False)  # noqa: S101
    assert "era_unparsed.cbl" in {u["program"] for u in synthetic[2]["unparsed_programs"]}  # noqa: S101
    assert eras["programs"]["statements.cbl"]["era"] is None  # noqa: S101
    copy = eras["programs"]["era_copy.cbl"]  # the tell is in the copybook only: seen through the COPY expansion
    assert (copy["era"], copy["earliest"], copy["mixed"]) == (1, 1, False)  # noqa: S101
    assert copy["tells"] == [  # noqa: S101
        {
            "tell": "bll-cells",
            "era": 1,
            "count": 1,
            "first_line": None,
            "via_copybook": True,
            "copybooks": ["ERACPY.cpy"],
        }
    ]
    assert copy["program_era"] is None and "program_era" not in mixed  # noqa: S101
    assert not synthetic[2]["copybook_resolution_gaps"]["unknown"]["count"]  # noqa: S101
    s = eras["summary"]
    assert s["programs"] == len(SNIPPETS) and s["mixed"] == 1 and s["by_era"]["4"] == 1  # noqa: S101


def test_copybook_pass_skipped_is_marked_on_the_tag(synthetic):
    """#5195: a program whose COPY expansion is refused carries `copybook_skipped`; one whose expansion ran does not."""
    eras = synthetic[2]["eras"]
    assert eras["programs"]["copybook_gap.cbl"]["copybook_skipped"] == "CopyNotFound"  # noqa: S101
    assert eras["programs"]["fallback.cbl"]["copybook_skipped"] == "CopyNotFound"  # noqa: S101
    marked = {p for p, t in eras["programs"].items() if "copybook_skipped" in t}
    assert marked == {"copybook_gap.cbl", "fallback.cbl", "era_unparsed.cbl"}  # noqa: S101  (era_copy's expansion ran)
    assert eras["summary"]["copybook_skipped"] == 3  # noqa: S101


def test_assembler_members_are_era_tagged_through_their_copy_and_macro_members(synthetic):
    asm = synthetic[2]["eras"]["assembler"]
    tag = asm["era_asm.asm"]
    assert (tag["era"], "copybook_skipped" in tag) == (0, False)  # noqa: S101
    # the tell is in two members the program never mentions in its own text: both are listed, ASMDEEP through ASMBOOK
    by_tell = {t["tell"]: t for t in tag["tells"]}
    assert by_tell["dfh-macro-call"]["via_copybook"] is True  # noqa: S101
    assert by_tell["dfh-macro-call"]["copybooks"] == ["ASMDEEP.mac", "ASMMAC.mac"]  # noqa: S101
    assert asm["era_asm_gap.asm"]["copybook_skipped"] == "CopyNotFound"  # noqa: S101
    # a member that only COPYs another is a member too: it sees the tell through ASMDEEP, and ASMDEEP holds it itself
    assert (
        asm["ASMBOOK.mac"]["tells"][0]["copybooks"] == ["ASMDEEP.mac"]
        and "via_copybook" in asm["ASMBOOK.mac"]["tells"][0]
    )  # noqa: S101
    assert "via_copybook" not in asm["ASMDEEP.mac"]["tells"][0]  # noqa: S101


def test_cics_commands_and_options(synthetic):
    inv = synthetic[2]
    assert has(inv, "cics_commands", "SEND TEXT", "cics_commands_and_options")  # noqa: S101
    assert has(inv, "cics_options", "SEND TEXT: FROM", "cics_commands_and_options")  # noqa: S101


def test_sql_forms(synthetic):
    inv = synthetic[2]
    assert has(inv, "sql_forms", "DECLARE CURSOR", "sql_forms")  # noqa: S101
    assert has(inv, "sql_forms", "WHENEVER", "sql_forms")  # noqa: S101
    assert has(inv, "sql_forms", "DYNAMIC", "sql_forms")  # noqa: S101


def test_intrinsic_functions(synthetic):
    inv = synthetic[2]
    assert has(inv, "intrinsic_functions", "CURRENT-DATE", "intrinsic_functions")  # noqa: S101


def test_compile_options(synthetic):
    inv = synthetic[2]
    assert any(
        "NUMPROC: PFD" in k and "compile_options.cbl" in v["programs"] for k, v in inv["compile_options"].items()
    )  # noqa: S101


def test_copybook_gap(synthetic):
    inv = synthetic[2]
    assert any(
        "COPY MISSING" in k and "copybook_gap.cbl" in v["programs"] for k, v in inv["copybook_resolution_gaps"].items()
    )  # noqa: S101


def test_fallback(synthetic):
    inv = synthetic[2]
    assert any(x["program"] == "fallback.cbl" for x in inv["unparsed_programs"])  # noqa: S101
    assert has(inv, "cics_commands", "READ", "fallback")  # noqa: S101
    assert has(inv, "sql_forms", "DYNAMIC", "fallback")  # noqa: S101
    assert has(inv, "statements", "MOVE", "fallback")  # noqa: S101
    assert has(inv, "statements", "GOBACK", "fallback")  # noqa: S101


def _seq(lines, tag="PROG0001"):
    """Fixed-form lines with a sequence number in columns 1-6 and an identification tag in 73-80."""
    return "\n".join(f"{i * 100 + 100:06d}" + ln.ljust(66)[:66] + tag for i, ln in enumerate(lines)) + "\n"


def _fallback(tmp_path, text):
    from gitgalaxy.tools.readiness.inventory import fallback_parse, inventory_template

    f = tmp_path / "p.cbl"
    f.write_text(text)
    inv = inventory_template()
    fallback_parse(f, "p.cbl", inv)
    return inv


def test_fallback_ignores_the_sequence_and_identification_areas(tmp_path):  # #5106
    inv = _fallback(
        tmp_path,
        _seq(
            [
                "      PROCEDURE DIVISION.",
                "          EXEC CICS RETRIEVE",
                "              INTO(WS-X)",
                "              LENGTH(WS-L)",
                "          END-EXEC.",
                "          EXEC SQL EXECUTE S1",
                "          END-EXEC.",
                "          MOVE FUNCTION UPPER-CASE(A) TO B.",
                "* MOVE IN A COMMENT",
                "          GOBACK.",
            ]
        ),
    )
    keys = [k for cat in inv.values() for k in cat]
    assert not [k for k in keys if re.search(r"\b\d{6,8}\b", k)]  # noqa: S101
    assert "RETRIEVE" in inv["cics_commands"]  # noqa: S101
    assert {"RETRIEVE: INTO", "RETRIEVE: LENGTH"} <= set(inv["cics_options"])  # noqa: S101
    assert "UPPER-CASE" in inv["intrinsic_functions"]  # noqa: S101
    assert inv["statements"]["MOVE"]["count"] == 1  # the comment's MOVE is not counted  # noqa: S101


def test_fallback_does_not_count_a_verb_in_the_identification_area(tmp_path):  # #5106
    line = "      " + " " + "GOBACK.".ljust(65) + "MOVE    "  # a tag naming a verb, columns 73-80
    inv = _fallback(tmp_path, line + "\n")
    assert "MOVE" not in inv["statements"]  # noqa: S101
    assert "GOBACK" in inv["statements"]  # noqa: S101


def test_fallback_free_form_source_is_read_whole(tmp_path):  # #5106
    inv = _fallback(tmp_path, ">>SOURCE FORMAT FREE\nMOVE 1 TO A. " + "x" * 80 + " GOBACK.\n")
    assert {"MOVE", "GOBACK"} <= set(inv["statements"])  # noqa: S101


TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def check_schema(data, node, root, where="$"):
    """The keywords feature_inventory.schema.json uses ($ref, type, required, properties, additionalProperties, items,
    minimum), checked without the jsonschema package (not installed in every venv / CI job)."""
    if "$ref" in node:
        node = root["$defs"][node["$ref"].split("/")[-1]]
    t = node.get("type")
    if t:
        ok = [x for x in ([t] if isinstance(t, str) else t) if isinstance(data, TYPES[x])]
        assert ok and not (ok == ["integer"] and isinstance(data, bool)), f"{where}: not {t}"  # noqa: S101
    if "minimum" in node and data is not None:
        assert data >= node["minimum"], f"{where}: below {node['minimum']}"  # noqa: S101
    if isinstance(data, dict):
        for k in node.get("required", []):
            assert k in data, f"{where}: missing {k}"  # noqa: S101
        props = node.get("properties", {})
        extra = node.get("additionalProperties", True)
        for k, v in data.items():
            if k in props:
                check_schema(v, props[k], root, f"{where}.{k}")
            elif isinstance(extra, dict):
                check_schema(v, extra, root, f"{where}.{k}")
            else:
                assert extra is not False, f"{where}: unexpected key {k}"  # noqa: S101
    if isinstance(data, list) and "items" in node:
        for i, v in enumerate(data):
            check_schema(v, node["items"], root, f"{where}[{i}]")


def test_schema_over_fixtures():
    schema = json.loads(SCHEMA_FILE.read_text())
    fixtures = sorted((TOOLS.parent / "fixtures" / "feature_inventory").glob("*.json"))
    assert len(fixtures) == 6  # noqa: S101 -- one per burned estate
    for f in fixtures:
        check_schema(json.loads(f.read_text()), schema, schema, f.name)
    for f in fixtures:  # #5117: every program the inventory counts has an era tag, and the summary adds up
        d = json.loads(f.read_text())
        counted = {
            p
            for c, v in d.items()
            if c
            not in (
                "eras",
                "unparsed_programs",
                "refusal_families",
            )  # (#5121: assembler members carry no COBOL era tag)
            for x in v.values()
            for p in x["programs"]
        }
        assert counted <= set(d["eras"]["programs"]), f.name  # noqa: S101
        s = d["eras"]["summary"]
        assert s["programs"] == len(d["eras"]["programs"]) == sum(s["by_era"].values()), f.name  # noqa: S101
    with pytest.raises(AssertionError):
        check_schema({"statements": "not an object"}, schema, schema)


def test_no_committed_inventory_key_is_a_sequence_number():  # #5235 (item 1 of the #5106 class)
    """A key carrying a 6-8 digit run is a card's sequence area leaking into a feature name (`ASKTIME 03430012`):
    every committed estate fixture, not one, is free of it."""
    import re

    fixtures = sorted((TOOLS.parent / "fixtures" / "feature_inventory").glob("*.json"))
    assert fixtures  # noqa: S101
    leaks = [
        f"{f.name}: {section}: {key}"
        for f in fixtures
        for section, entries in json.loads(f.read_text()).items()
        if isinstance(entries, dict)
        for key in entries
        if re.search(r"\b\d{6,8}\b", key)
    ]
    assert not leaks, leaks[:10]  # noqa: S101


@pytest.mark.nightly
@pytest.mark.skipif(
    not os.environ.get("GITGALAXY_NIGHTLY"), reason="nightly (~170 s, all estates): set GITGALAXY_NIGHTLY=1"
)
@pytest.mark.skipif(not (CORPORA / "cics-genapp").is_dir(), reason="no mainframe corpora (mainframe_corpus.py fetch)")
def test_feature_inventory_cli_check():
    res = subprocess.run([sys.executable, str(TOOLS / "feature_inventory.py"), "--all-burned", "--check"],  # noqa: S603
                         capture_output=True, text=True, check=False)  # fmt: skip
    assert res.returncode == 0  # noqa: S101


@pytest.mark.parametrize("national", ["PIC N(4)", "PIC G(4)", "PIC X(4) USAGE NATIONAL", "PIC X(4) USAGE IS DISPLAY-1"])
def test_national_data_does_not_hide_the_rest_of_the_program(national):
    """#4664: the translator refuses PIC N / G, USAGE NATIONAL / DISPLAY-1 and N / G literals whole; the census still reads
    every other data type and statement of that program, whichever national form it holds."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests" / "tools"))
    import feature_inventory as FI
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import source as S
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    rows = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. P.", "DATA DIVISION.", "WORKING-STORAGE SECTION.", f"01 N1 {national}.",
            "01 B1 PIC S9(4) BINARY.", "01 P1 PIC S9(4) COMP-3.", "01 F1 USAGE COMP-1.", "PROCEDURE DIVISION.",
            "    MOVE N'AB' TO N1", "    GOBACK."]  # fmt: skip
    lines = [S.Line(t, "/x/P.cbl", n) for n, t in enumerate(rows, 1)]
    with pytest.raises(L.LayoutError):
        L.parse(lines)  # the translator itself still refuses it
    census, seen = FI.census_lines(lines)
    assert seen
    usages = {it.name: it.usage for r in L.parse(census) for it in r.walk()}
    assert usages["B1"] == "BINARY" and usages["P1"] == "PACKED" and usages["F1"] == "COMP-1"
    assert [s.kind for pg in ST.parse(census).paragraphs for s in pg.body] == ["MOVE", "GOBACK"]
