"""#8161 (PR 5): a PHP class's `extends` parent and the traits its body `use`s are its parents, so `$this->m()`
and `parent::m()` walk to the inherited (or trait) method: a confident `class` link, not the ambiguous `receiver`
guess (186 of composer's reference edges vs scip-php)."""

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _parse(code: str) -> dict:
    return StructuralExtractor("php", LANGUAGE_DEFINITIONS).splice(code, "")


BASE = (
    "<?php\n"
    "namespace App\\Command;\n"
    "abstract class BaseCommand extends \\Symfony\\Component\\Console\\Command\\Command\n"
    "{\n"
    "    public function getIO()\n"  # 5
    "    {\n"
    "        return 1;\n"
    "    }\n"
    "}\n"
)
TRAIT = (
    "<?php\n"
    "namespace App\\Command;\n"
    "trait CompletionTrait\n"
    "{\n"
    "    public function suggest()\n"  # 5
    "    {\n"
    "        return [];\n"
    "    }\n"
    "}\n"
)
CHILD = (
    "<?php\n"
    "namespace App\\Command;\n"
    "use App\\Other\\Helper;\n"
    "class RunCommand extends BaseCommand implements \\Countable\n"
    "{\n"
    "    use CompletionTrait;\n"
    "    public function execute()\n"  # 7
    "    {\n"
    "        $f = function () use ($x) { return $x; };\n"
    "        $io = $this->getIO();\n"
    "        return $this->suggest();\n"
    "    }\n"
    "}\n"
)
OTHER = (
    "<?php\n"
    "namespace App\\Other;\n"
    "class Helper\n"
    "{\n"
    "    public function getIO()\n"  # 5: same name, another class the child only imports
    "    {\n"
    "        return 2;\n"
    "    }\n"
    "}\n"
)


def test_extends_and_trait_use_are_the_class_parents():
    classes = {c["name"]: c["inheritance"] for c in _parse(CHILD)["classes"]}
    assert classes["RunCommand"] == ["BaseCommand", "CompletionTrait"]  # not the closure's `use ($x)`
    assert {c["name"]: c["inheritance"] for c in _parse(BASE)["classes"]}["BaseCommand"] == ["Command"]
    assert {c["name"]: c["inheritance"] for c in _parse(OTHER)["classes"]}["Helper"] == []


def test_this_calls_reach_the_inherited_and_the_trait_method():
    files = {
        "src/Command/BaseCommand.php": BASE,
        "src/Command/CompletionTrait.php": TRAIT,
        "src/Command/RunCommand.php": CHILD,
        "src/Other/Helper.php": OTHER,
    }
    parsed = []
    for path, code in files.items():
        p = _parse(code)
        parsed.append({"path": path, "lang_id": "php", "functions": p["functions"], "classes": p["classes"]})
    sites, _ = resolve_calls(parsed)
    got = {
        (s["callee"], s["step"], s["dst_path"], s["dst_line"])
        for s in sites
        if s["src_name"].endswith("execute") and s["callee"] in ("getIO", "suggest")
    }
    assert got == {
        ("getIO", "class", "src/Command/BaseCommand.php", 5),  # never the imported Helper::getIO
        ("suggest", "class", "src/Command/CompletionTrait.php", 5),
    }
