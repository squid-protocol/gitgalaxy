"""#8161 (G1): a Go package is its directory. Each file maps its import names (an alias, else the import
path's last element) to the package they name: `pkg.F()` resolves among ALL files of that package and
nowhere else, and a package outside the repo (`errors.New`, `strings.NewReader`) is never a repo function.
And a Go method is owned by its receiver type (`func (s *S) f(`): several `Close` methods in one file are
several classes, and a call on the method's own receiver variable is the `class` step."""

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.galaxyscope import extract_namespace_imports
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

FILES = {
    "a/a.go": "package a\n\nfunc New() int { return 1 }\n",
    "a/util.go": "package a\n\nfunc Parse(s string) int { return 2 }\n",
    "a/a_test.go": "package a\n\nfunc Helper() int { return 3 }\n",
    "c/c.go": "package c\n\nfunc Parse(s string) int { return 4 }\n",
    "b/b.go": (
        "package b\n\n"
        'import (\n\t"errors"\n\t"strings"\n\n\t"example.com/m/a"\n\tcc "example.com/m/c"\n)\n\n'
        'func New() error { return errors.New("b") }\n\n'
        "func NewReader(s string) int { return 0 }\n\n"
        "func Run() int {\n"
        '\t_ = strings.NewReader("s")\n'
        '\treturn a.New() + a.Parse("1") + cc.Parse("2") + a.Helper()\n'
        "}\n"
    ),
    "d/d.go": (
        "package d\n\n"
        "type F struct{}\n\n"
        "func (f *F) Close() error { return nil }\n\n"
        "type G struct{ inner *F }\n\n"
        "func (g *G) Close() error { return g.inner.Close() }\n\n"
        "func (g *G) Flush() error {\n\treturn g.Close()\n}\n\n"
        "func Use(x *F) error { return x.Close() }\n"
    ),
}
IMPORTS = [{"src": "b/b.go", "dst": "a/a.go"}, {"src": "b/b.go", "dst": "c/c.go"}]


def _parse(code: str) -> dict:
    return StructuralExtractor("go", LANGUAGE_DEFINITIONS).splice(code, "")


def _sites():
    parsed_files = []
    for path, code in FILES.items():
        parsed = _parse(code)
        parsed_files.append(
            {"path": path, "lang_id": "go", "functions": parsed["functions"], "classes": parsed.get("classes", [])}
        )
    # what NetworkRiskSensor hands over: each import name -> the package's representative file, "" outside the repo
    aliases = {"b/b.go": {"errors": "", "strings": "", "a": "a/a.go", "cc": "c/c.go"}}
    sites, _ = resolve_calls(parsed_files, IMPORTS, namespace_aliases=aliases)
    return {(s["src_name"], s["src_line"], s["callee"]): (s["step"], s["dst_path"], s["dst_line"]) for s in sites}


def _site(sites, caller, callee):
    (row,) = [v for (src, _, c), v in sites.items() if src == caller and c == callee]
    return row


def test_a_package_qualifier_reaches_any_file_of_the_package():
    sites = _sites()
    assert _site(sites, "Run", "New") == ("import", "a/a.go", 3)
    assert _site(sites, "Run", "Parse") == ("import", "a/util.go", 3)


def test_an_aliased_import_names_its_package():
    # `cc.Parse` is package c's, though package a (not imported here) also defines `Parse`
    files = {
        "c/c.go": FILES["c/c.go"],
        "a/util.go": FILES["a/util.go"],
        "b/b.go": 'package b\n\nimport cc "example.com/m/c"\n\nfunc Run() int {\n\treturn cc.Parse("2")\n}\n',
    }
    parsed_files = [{"path": p, "lang_id": "go", "functions": _parse(c)["functions"]} for p, c in files.items()]
    sites, _ = resolve_calls(
        parsed_files, [{"src": "b/b.go", "dst": "c/c.go"}], namespace_aliases={"b/b.go": {"cc": "c/c.go"}}
    )
    (row,) = [s for s in sites if s["callee"] == "Parse"]
    assert (row["step"], row["dst_path"]) == ("import", "c/c.go")


def test_an_external_package_qualifier_is_no_repo_function():
    sites = _sites()
    assert _site(sites, "New", "New")[0] == "none"  # errors.New in b's own New
    assert _site(sites, "Run", "NewReader")[0] == "none"  # strings.NewReader beside b.NewReader


def test_a_test_file_is_not_part_of_the_imported_package():
    assert _site(_sites(), "Run", "Helper")[0] == "none"


def test_a_method_is_owned_by_its_receiver_type():
    owners = {(f["name"], f["start_line"]): f.get("parent_class_name") for f in _parse(FILES["d/d.go"])["functions"]}
    assert owners == {("Close", 5): "F", ("Close", 9): "G", ("Flush", 11): "G", ("Use", 15): None}
    code = "package e\n\ntype T[K any] struct{}\n\nfunc (T[K]) Get() {}\n\nfunc (t *T[K]) Put() {}\n"
    assert {f["name"]: f.get("parent_class_name") for f in _parse(code)["functions"]} == {"Get": "T", "Put": "T"}


def test_the_own_receiver_is_the_class_step_and_same_file_methods_do_not_collide():
    sites = _sites()
    assert _site(sites, "Flush", "Close") == ("class", "d/d.go", 9)
    # `x.Close()` / `g.inner.Close()`: two types in the file define Close; the parameter `x *F` and the field
    # `inner *F` type the receiver (X3), so both reach F's Close, not G's
    assert _site(sites, "Use", "Close") == ("typed", "d/d.go", 5)
    assert _site(sites, "Close", "Close") == ("typed", "d/d.go", 5)


def test_import_names_are_extracted():
    code = (
        "package app\n\n"
        'import (\n\t"fmt"\n\taa "example.com/m/a"\n\t. "example.com/m/x"\n\t_ "example.com/m/side"\n'
        '\t"example.com/m/v2"\n\t"gopkg.in/yaml.v3"\n\t"example.com/m/lib/v3"\n)\n'
        'import "os"\n\n'
        'var s = []string{\n\t"not/an/import",\n}\n'
    )
    assert extract_namespace_imports(code, "go") == {
        "fmt": "fmt",
        "aa": "example.com/m/a",
        ". example.com/m/x": "example.com/m/x",
        "m": "example.com/m/v2",
        "yaml": "gopkg.in/yaml.v3",
        "lib": "example.com/m/lib/v3",
        "os": "os",
    }
