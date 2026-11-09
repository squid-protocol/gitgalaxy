"""#8161: a Java receiver the function does not declare is a field, typed from the file's FIELD declarations
only. The file-wide scan used to read every method's locals too, so a lambda parameter `c` took the type of
another method's `Tool c` and got a false confident `typed` link."""

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor, _java_field_text
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

ROOT = "src/main/java/p/"
FILES = {
    "Tool.java": "package p;\npublic class Tool {\n    public int area() { return 1; }\n}\n",
    "Other.java": "package p;\npublic class Other {\n    public int area() { return 2; }\n}\n",
    "Client.java": (
        "package p;\n"
        "import java.util.List;\n"
        "public class Client {\n"
        "    private Tool field = new Tool();\n"
        "    void typed() {\n"
        "        Tool c = new Tool();\n"
        "        c.area();\n"
        "    }\n"
        "    void lambdaLeak(List<Other> os) {\n"
        "        os.forEach(c -> c.area());\n"
        "    }\n"
        "    int viaField() { return field.area(); }\n"
        "}\n"
    ),
}


def _area_sites():
    files = []
    for name, code in FILES.items():
        parsed = StructuralExtractor("java", LANGUAGE_DEFINITIONS).splice(code, "")
        files.append(
            {"path": ROOT + name, "lang_id": "java", "functions": parsed["functions"], "classes": parsed["classes"]}
        )
    sites, _ = resolve_calls(files)
    return {s["src_name"]: (s["step"], s["dst_path"]) for s in sites if s["callee"] == "area"}


def test_a_lambda_parameter_takes_no_other_methods_local_type():
    assert _area_sites()["lambdaLeak"][0] != "typed"


def test_locals_and_fields_still_type_their_receivers():
    sites = _area_sites()
    assert sites["typed"] == ("typed", ROOT + "Tool.java")
    assert sites["viaField"] == ("typed", ROOT + "Tool.java")


def test_field_text_keeps_fields_and_blanks_bodies():
    text = FILES["Client.java"]
    kept = _java_field_text(text)
    assert len(kept) == len(text) and kept.count("\n") == text.count("\n")
    assert "private Tool field = new Tool" in kept
    assert "Tool c" not in kept and "List<Other> os" not in kept
