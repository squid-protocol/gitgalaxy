"""#4711: the cobolrt rule catalogue (docs/language_status/cobolrt_rules.json) against the runtime's code, both ways.

The real catalogue must be consistent; each failure class of the checker is shown on a synthetic runtime (a site with
no entry, an entry with no site, an unclassified or a missing method, a misplaced marker, a bad IBM / option / register
/ calibration field, an unlisted file); `mark` writes markers that change no code; and det_port's comparison of a
runtime class ignores comments but nothing else (a rule ID cited at its site moves no port).
"""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cobolrt_rules as cr
import det_port

JAVA = """package __PACKAGE__.cobolrt;

/** A runtime class. */
final class Demo {
    private Demo() {}

    /** ADD (register C14). */
    // [rule RT-DEMO-ADD]
    static int add(int a, int b) {
        return a + b;
    }

    @Override
    // [rule RT-DEMO-TEXT]
    public String toString() {
        return "[rule RT-DEMO-NOPE] // not a comment /* nor this */";
    }

    static int helper(int a) {
        return a;
    }
}
"""


def _cat():
    rule = {"family": "DEMO", "options": [], "register": [], "status": "MATCHED", "calibration": "uncalibrated",
            "ibm": {"doc": "lr", "section": "ADD statement"}}  # fmt: skip
    return {
        "about": ["demo"],
        "documents": {"lr": {"title": "Language Reference"}},
        "options": {"TRUNC": {"kind": "compile", "about": "t"}, "DPC": {"kind": "source", "about": "d"}},
        "families": [
            {
                "id": "DEMO",
                "prefix": "DEMO",
                "title": "demo",
                "files": ["Demo.java"],
                "done": True,
                "about": "a",
                "plumbing": ["helper"],
            }
        ],  # fmt: skip
        "rules": [
            {**rule, "id": "RT-DEMO-ADD", "title": "add", "methods": ["add"], "register": ["C14"]},
            {**rule, "id": "RT-DEMO-TEXT", "title": "text", "methods": ["toString"]},
        ],
    }


REGISTER = {"C14": "MATCHED", "C5": "MATCHED"}


@pytest.fixture
def rt(tmp_path):
    (tmp_path / "Demo.java").write_text(JAVA, encoding="utf-8")
    return tmp_path


def _probs(cat, rt):
    return cr.check(cat, rt, REGISTER)


def _has(probs, text):
    assert any(text in p for p in probs), probs


def test_the_catalogue_matches_the_runtime():
    assert cr.check() == []


def test_the_catalogue_covers_every_runtime_file_and_family():
    cat = cr.load()
    listed = {f for fam in cat["families"] for f in fam["files"]}
    assert listed == {p.relative_to(cr.RT).as_posix() for p in cr.RT.rglob("*.java")}
    assert all(fam["done"] for fam in cat["families"])
    assert {r["family"] for r in cat["rules"]} == {fam["id"] for fam in cat["families"]}


def test_synthetic_runtime_is_consistent(rt):
    assert _probs(_cat(), rt) == []


def test_a_site_without_an_entry_fails(rt):
    cat = _cat()
    cat["rules"] = cat["rules"][:1]
    cat["families"][0]["plumbing"].append("toString")
    _has(_probs(cat, rt), "[rule RT-DEMO-TEXT] has no catalogue entry")


def test_an_entry_without_a_site_fails(rt):
    cat = _cat()
    cat["rules"].append({**cat["rules"][1], "id": "RT-DEMO-HELPER", "methods": ["helper"]})
    _has(_probs(cat, rt), "RT-DEMO-HELPER: no code site")


def test_a_marker_inside_a_string_literal_is_no_site(rt):
    cat = _cat()
    cat["rules"].append({**cat["rules"][1], "id": "RT-DEMO-NOPE", "methods": ["helper"]})
    _has(_probs(cat, rt), "RT-DEMO-NOPE: no code site")


def test_an_unclassified_method_fails(rt):
    cat = _cat()
    cat["families"][0]["plumbing"] = []
    _has(_probs(cat, rt), "method helper is in no rule of DEMO and not in its plumbing")


def test_a_named_method_that_does_not_exist_fails(rt):
    cat = _cat()
    cat["rules"][0]["methods"].append("subtract")
    cat["families"][0]["plumbing"].append("gone")
    probs = _probs(cat, rt)
    _has(probs, "subtract (named by a rule or plumbing) is not a method")
    _has(probs, "gone (named by a rule or plumbing) is not a method")


def test_a_marker_before_another_rules_method_fails(rt):
    cat = _cat()
    cat["rules"][1]["methods"] = ["helper"]
    cat["families"][0]["plumbing"] = ["toString"]
    _has(_probs(cat, rt), "[rule RT-DEMO-TEXT] stands before toString, not one of its methods")


def test_a_marker_of_another_family_fails(rt):
    cat = _cat()
    (rt / "Other.java").write_text("final class Other {\n    static void x() {}\n}\n", encoding="utf-8")
    cat["families"].append({"id": "OTH", "prefix": "OTH", "title": "o", "files": ["Other.java"], "done": True,
                            "about": "o", "plumbing": ["x"]})  # fmt: skip
    cat["rules"][1]["family"] = "OTH"
    _has(_probs(cat, rt), "[rule RT-DEMO-TEXT] is a rule of OTH, not DEMO")


def test_a_marker_in_a_family_not_catalogued_yet_fails(rt):
    cat = _cat()
    cat["families"][0]["done"] = False
    _has(_probs(cat, rt), "which is not catalogued yet (done: false)")


def test_a_runtime_file_no_family_lists_fails(rt):
    (rt / "Stray.java").write_text("final class Stray {}\n", encoding="utf-8")
    _has(_probs(_cat(), rt), "Stray.java: a runtime file no family lists")


@pytest.mark.parametrize(
    ("edit", "expect"),
    [
        (lambda c: c["rules"].append(copy.deepcopy(c["rules"][0])), "RT-DEMO-ADD: listed twice"),
        (lambda c: c["rules"][0].update(id="RT-X-ADD"), "is RT-DEMO-<NAME>"),
        (lambda c: c["rules"][0].update(status="MODELLED"), "status 'MODELLED' is not one of"),
        (
            lambda c: c["rules"][0].update(ibm=None, ibm_note="silent"),
            "no IBM reference -- only a rule that is not MATCHED",
        ),
        (lambda c: c["rules"][0].update(ibm=None, status="ASSUMED"), "no IBM reference"),
        (lambda c: c["rules"][0].update(ibm={"doc": "pg", "section": "x"}), "ibm needs a doc of `documents`"),
        (lambda c: c["rules"][0].update(ibm={"doc": "lr", "section": ""}), "ibm needs a doc of `documents`"),
        (lambda c: c["rules"][0].update(options=["NOSUCH"]), "option 'NOSUCH' is not in `options`"),
        (
            lambda c: c["options"].update(BOGUS={"kind": "compile", "about": "b"}),
            "option BOGUS: not an Enterprise COBOL",
        ),
        (lambda c: c["options"].update(DPC={"kind": "whim", "about": "d"}), "kind 'whim' is not one of"),
        (lambda c: c["rules"][0].update(register=["Z99"]), "no register entry Z99"),
        (lambda c: c["rules"][0].update(register=[]), "Demo.java: cites register C14, which no rule of DEMO carries"),
        (lambda c: c["rules"][0].update(register="C14"), "register is a list"),
        (lambda c: c["rules"][0].update(calibration="measured"), "calibration 'measured' is not one of"),
        (lambda c: c["rules"][0].update(calibration="z/OS-measured"), "z/OS-measured needs `evidence`"),
        (lambda c: c["rules"][0].update(site="nowhere"), "its site 'nowhere' is no method"),
        (lambda c: c["rules"][0].update(family="NOPE"), "no family 'NOPE'"),
        (lambda c: c["rules"][0].update(title=""), "RT-DEMO-ADD: no title"),
    ],
)
def test_each_field_rule(rt, edit, expect):
    cat = _cat()
    edit(cat)
    _has(_probs(cat, rt), expect)


def test_a_rule_not_matched_may_name_why_ibm_is_silent(rt):
    cat = _cat()
    cat["rules"][0].update(ibm=None, ibm_note="IBM documents no result", status="DIFFERS")
    cat["rules"][1].update(
        calibration="z/OS-measured", evidence="tests/equivalence/zos/demo.json", calibrated_under=_under()
    )
    assert _probs(cat, rt) == []


def _under():
    from gitgalaxy.core.runtime_options import RUNTIME_OPTION_TABLE  # noqa: PLC0415

    return {k: r["default"] for k, r in RUNTIME_OPTION_TABLE.items() if r["policy"]}


@pytest.mark.parametrize(
    ("edit", "expect"),
    [
        (lambda u: u.clear(), "calibrated_under is a non-empty"),
        (lambda u: u.pop("le.runtime_options.TRAP"), "le.runtime_options.TRAP: judged by the table"),
        (lambda u: u.update({"le.runtime_options.TRAP": "OFF"}), "TRAP=OFF: measured under a value the harness cannot"),
        (lambda u: u.update({"le.runtime_options.NEWOPT": "X"}), "NEWOPT: no row in the runtime option table"),
    ],
)
def test_a_measurement_names_the_options_it_held_under(rt, edit, expect):
    cat = _cat()
    under = _under()
    edit(under)
    cat["rules"][1].update(calibration="z/OS-measured", evidence="e.json", calibrated_under=under)
    _has(_probs(cat, rt), expect)


def test_a_measurement_with_no_options_fails(rt):
    cat = _cat()
    cat["rules"][1].update(calibration="z/OS-measured", evidence="e.json")
    _has(_probs(cat, rt), "RT-DEMO-TEXT: calibrated_under is a non-empty")


def test_mark_writes_the_missing_markers_and_changes_no_code(rt):
    bare = "\n".join(ln for ln in JAVA.split("\n") if "// [rule" not in ln)
    (rt / "Demo.java").write_text(bare, encoding="utf-8")
    cat = _cat()
    cat["rules"].append({**cat["rules"][1], "id": "RT-DEMO-HELPER", "methods": ["helper"]})
    cat["families"][0]["plumbing"] = []
    assert cr.mark(cat, rt) == ["Demo.java"]
    out = (rt / "Demo.java").read_text(encoding="utf-8")
    assert _probs(cat, rt) == []
    assert det_port.java_code(out) == det_port.java_code(bare)
    assert "    // [rule RT-DEMO-TEXT]\n    @Override\n" in out  # above the annotations
    assert cr.mark(cat, rt) == []  # idempotent


def test_mark_puts_two_rules_of_one_site_on_one_line(rt):
    bare = "\n".join(ln for ln in JAVA.split("\n") if "// [rule" not in ln)
    (rt / "Demo.java").write_text(bare, encoding="utf-8")
    cat = _cat()
    cat["rules"].append({**cat["rules"][0], "id": "RT-DEMO-ADD-ALSO", "register": []})
    cr.mark(cat, rt)
    assert "// [rule RT-DEMO-ADD] [rule RT-DEMO-ADD-ALSO]\n    static int add" in (rt / "Demo.java").read_text()
    assert _probs(cat, rt) == []


def test_site_picks_the_nth_declaration_and_a_file():
    decls = {"A.java": [(3, "f"), (9, "f")], "B.java": [(4, "f")]}
    files = ["A.java", "B.java"]
    assert cr.site_of({"methods": ["f"]}, files, decls) == ("A.java", 3)
    assert cr.site_of({"methods": ["f"], "site": "f@2"}, files, decls) == ("A.java", 9)
    assert cr.site_of({"methods": ["f"], "site": "B.java:f"}, files, decls) == ("B.java", 4)
    assert cr.site_of({"methods": ["f"], "site": "f@4"}, files, decls) is None


def test_declarations_skip_calls_constructors_and_records():
    text = """class A {
    A(int x) {}
    private record PastFrom(int n) {}
    static <T> java.util.List<T> list(T t) { return null; }
    int[] arr(int n) {
        int y = call(n);
        return new int[] {y};
    }
    else if (x) {}
    public BigDecimal two(String a,
                          int b) {}
}"""
    assert cr.methods(text) == ["list", "arr", "two"]


def test_render_is_deterministic_and_names_every_rule():
    page = cr.render()
    assert page == cr.render()
    cat = cr.load()
    assert all(f"| {r['id']} |" in page for r in cat["rules"])
    assert f"{len(cat['rules'])} rules:" in page
    reg = cr.register_status()
    assert f"C14 ({reg['C14']})" in page  # the register's own status, live


def test_rule_ids_are_stable_kebab_case_and_unique():
    ids = [r["id"] for r in cr.load()["rules"]]
    assert len(ids) == len(set(ids))
    assert all(cr.ID_RE.match(i) for i in ids)


def test_the_catalogue_file_is_canonical_json():
    text = cr.CATALOGUE.read_text(encoding="utf-8")
    assert text == json.dumps(json.loads(text), indent=1, ensure_ascii=False) + "\n"


# ---- det_port: a runtime class compared as code, comments aside ----------------------------------------------------
@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        ("int f() { return 1; }", "/** doc */\n// [rule RT-X-Y]\nint f() {\n  return 1; // c\n}", True),
        ("int f() { return 1; }", "int f() { return 2; }", False),
        ('String s = "a // b";', 'String s = "a // c";', False),
        ('String s = "a /* b */";', 'String s = "a /* c */";', False),
        ('String s = "a  b";', 'String s = "a b";', False),  # whitespace inside a literal counts
        ("char q = '\"'; int x;", "char q = '\"';  /* c */ int x;", True),
        ('String t = """\n  x // y\n""";', 'String t = """\n  x // z\n""";', False),
        ('String s = "esc \\" // still";', 'String s = "esc \\" // still";  // c', True),
        ("int a/**/b;", "int a b;", True),
        ("/* unterminated", "/* unterminated ", False),  # does not lex: compared as text
    ],
)
def test_java_code_ignores_comments_and_layout_only(a, b, same):
    assert (det_port.java_code(a) == det_port.java_code(b)) is same


def test_java_segments_round_trip_every_runtime_file():
    for p in cr.RT.rglob("*.java"):
        t = p.read_text(encoding="utf-8")
        assert "".join(s for _, s in det_port.java_segments(t)) == t, p


def _port(root: Path, case: str, files: dict[str, str]) -> None:
    for rel, text in files.items():
        f = root / case / "port" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")


def test_compare_a_comment_in_a_runtime_class_moves_no_port(tmp_path):
    svc = {"service/S.java": "class S { void m() { Cobol.move(a, b, cs); } }"}
    _port(tmp_path / "a", "c1", {**svc, "cobolrt/Cobol.java": "class Cobol { static void move() {} }"})
    _port(
        tmp_path / "b",
        "c1",
        {**svc, "cobolrt/Cobol.java": "class Cobol {\n    // [rule RT-CBL-X]\n    static void move() {}\n}"},
    )
    assert det_port.compare(tmp_path / "a", tmp_path / "b") == [{"case": "c1", "status": "unchanged", "files": []}]
    _port(tmp_path / "b", "c1", {**svc, "cobolrt/Cobol.java": "class Cobol { static void move() { x(); } }"})
    rows = det_port.compare(tmp_path / "a", tmp_path / "b")
    assert rows[0]["status"] == "changed" and rows[0]["files"][0]["file"] == "cobolrt/Cobol.java"


def test_compare_a_comment_in_the_ports_own_code_still_counts(tmp_path):
    _port(tmp_path / "a", "c1", {"service/S.java": "class S {}"})
    _port(tmp_path / "b", "c1", {"service/S.java": "class S {} // a translator comment is output"})
    assert det_port.compare(tmp_path / "a", tmp_path / "b")[0]["status"] == "changed"


@pytest.mark.parametrize("features", [[], ["MOVE"], [3]])
def test_a_features_key_is_a_non_empty_list_of_category_key_strings(rt, features):
    cat = _cat()
    cat["rules"][0]["features"] = features
    assert any("features is a non-empty list" in p for p in _probs(cat, rt))


def test_a_keyed_rule_passes_the_check(rt):
    cat = _cat()
    cat["rules"][0]["features"] = ["statements: MOVE"]
    assert _probs(cat, rt) == []
