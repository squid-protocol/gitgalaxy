"""
HCL (#6572): `.tf` / `.tfvars` / `.hcl` are mapped, every column-0 block header (`resource`, `data`, `module`,
`variable`, `output`, `provider`, `locals`, `terraform`, ...) is a sliced unit with its own span, `resource` / `data`
are class_start hits, and a `module` block's `source` names its dependency in `_dependency_capture` (no module is read
from a comment, a heredoc or a multi-line string, and the `source` of a non-module block is not a dependency). Every
snippet is real HCL.
"""

import re
import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune_all  # noqa: E402 # type: ignore

HCL = LANGUAGE_DEFINITIONS["hcl"]
RULES = HCL["rules"]

SRC = (
    'terraform {\n  required_version = ">= 1.5"\n}\n'
    "\n"
    '# resource "old" "gone" {\n'
    'variable "region" {\n'
    "  type = string\n"
    '  description = "AWS region"\n'
    "}\n"
    "\n"
    'module "vpc" {\n'
    '  source = "./modules/vpc"\n'
    "}\n"
    "\n"
    'resource "aws_instance" "web" {\n'
    "  count = var.enabled ? 1 : 0\n"
    "}\n"
    "\n"
    'output "id" {\n'
    "  value = aws_instance.web[0].id\n"
    "}\n"
)


def _route(name: str, content: str) -> str:
    return LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus(name, content)[0]


def _splice(content: str) -> dict:
    return StructuralExtractor("hcl", LANGUAGE_DEFINITIONS).splice(content, "")


def _hits(rule: str, content: str) -> list[str]:
    return [m.group(0).strip() for m in RULES[rule].finditer(content)]


def _kept(content: str) -> str:
    """Mirror galaxyscope: a one-line literal is kept, a comment or span crossing lines is blanked."""
    blank = re.compile(HCL["import_capture_blank"])
    return blank.sub(lambda m: m.group() if "\n" not in m.group() else re.sub(r"[^\n]", " ", m.group()), content)


def _sources(content: str) -> list[str]:
    return [m.group(1) for m in RULES["_dependency_capture"].finditer(_kept(content))]


@pytest.mark.parametrize("name", ["main.tf", "prod.tfvars", "packer.pkr.hcl", "tests/main.tftest.hcl", "MAIN.TF"])
def test_every_hcl_extension_routes_to_hcl(name):
    assert _route(name, SRC) == "hcl"


def test_header_blocks_are_units_with_spans():
    spans = sorted((f["start_line"], f["end_line"]) for f in _splice(SRC)["functions"])
    # terraform, variable (the commented `resource` is not a unit), module, resource, output
    assert len(spans) == 5
    assert spans[0] == (1, 3)


def test_func_start_covers_every_block_type_and_label_count():
    src = (
        'resource "a" "b" {\n}\n'
        'data "a" "b" {\n}\n'
        'module "m" {\n}\n'
        'variable "v" {\n}\n'
        'output "o" {\n}\n'
        'provider "aws" {\n}\n'
        "locals {\n}\n"
        "terraform {\n}\n"
        'check "health" {\n}\n'
        "moved {\n}\n"
        "import {\n}\n"
        "removed {\n}\n"
        'run "plan_it" {\n}\n'
        'mock_provider "aws" {\n}\n'
    )
    assert [m.group(0).split()[0] for m in RULES["func_start"].finditer(src)] == [
        "resource",
        "data",
        "module",
        "variable",
        "output",
        "provider",
        "locals",
        "terraform",
        "check",
        "moved",
        "import",
        "removed",
        "run",
        "mock_provider",
    ]


def test_func_start_ignores_indented_commented_and_lookalike_headers():
    src = (
        '  dynamic "ingress" {\n}\n'
        '  provisioner "local-exec" {\n}\n'
        '# resource "a" "b" {\n'
        'resources "a" {\n'
        'resource_group "a" {\n'
        'variable_x "a" {\n'
        "locals_x {\n"
        'module "a" "b" "c" {\n'
        'resource "unterminated {\n'
    )
    assert _hits("func_start", src) == []


def test_class_start_is_the_typed_entity():
    src = (
        'resource "aws_s3_bucket" "logs" {\n}\n'
        'data "aws_ami" "ubuntu" {\n}\n'
        'module "vpc" {\n}\n'
        'resource "only_one_label" {\n}\n'
        'variable "x" {\n}\n'
    )
    assert _hits("class_start", src) == ['resource "aws_s3_bucket" "logs"', 'data "aws_ami" "ubuntu"']


def test_dependencies_capture_the_module_source():
    src = (
        'module "vpc" {\n  source = "./modules/vpc"\n}\n'
        'module "reg" {\n  source  = "terraform-aws-modules/vpc/aws"\n  version = "5.0"\n}\n'
        'module "git" {\n  version = "1"\n  source = "git::https://example.com/x.git?ref=v1"\n}\n'
        'module "prov" {\n  providers = { aws = aws.east }\n  source = "../shared"\n}\n'
    )
    assert _sources(src) == [
        "./modules/vpc",
        "terraform-aws-modules/vpc/aws",
        "git::https://example.com/x.git?ref=v1",
        "../shared",
    ]


def test_source_of_a_non_module_block_is_not_a_dependency():
    src = (
        'resource "aws_s3_object" "o" {\n  source = "files/a.txt"\n}\n'
        'terraform {\n  required_providers {\n    aws = {\n      source = "hashicorp/aws"\n    }\n  }\n}\n'
        'module "no_source" {\n  cidr = "10.0.0.0/16"\n}\n'
        'variable "x" {\n  source = "not a module"\n}\n'
    )
    assert _sources(src) == []


def test_a_module_does_not_borrow_the_next_blocks_source():
    src = 'module "a" {\n  cidr = "x"\n}\nresource "t" "n" {\n  source = "files/a.txt"\n}\n'
    assert _sources(src) == []


def test_import_capture_blank_hides_comments_heredocs_and_multiline_strings():
    src = (
        '# module "h1" {\n  source = "h1"\n}\n'
        '// module "h2" {\n'
        '/* module "h3" {\n  source = "h3" */\n'
        'resource "t" "n" {\n  user_data = <<-EOT\n  module "h4" {\n    source = "h4"\n  }\n  EOT\n}\n'
        'module "real" {\n  source = "./real" # trailing\n}\n'
        'module "real2" {\n  source = "git::https://x.io/a.git"\n}\n'
    )
    assert HCL["import_capture_multiline_only"] is True
    assert _sources(src) == ["./real", "git::https://x.io/a.git"]


def test_import_counts_module_headers_only():
    assert _hits("import", SRC) == ['module "vpc" {']
    assert _hits("import", 'resource "t" "n" {\n}\n# module "x" {\n  module "y" {\n') == []


def test_safety_bypasses_are_switches_that_turn_a_protection_off():
    src = (
        "prevent_destroy = false\n"
        "skip_credentials_validation = true\n"
        "insecure = true\n"
        "force_destroy = true\n"
        "ignore_changes = [tags]\n"
        "prevent_destroy = true\n"
        "skip_region_validation = false\n"
    )
    assert _hits("safety_bypasses", src) == [
        "prevent_destroy = false",
        "skip_credentials_validation = true",
        "insecure = true",
        "force_destroy = true",
        "ignore_changes =",
    ]


def test_safety_is_a_guard_the_plan_enforces():
    src = "validation {\n}\nprecondition {\n}\nprevent_destroy = true\nsensitive = true\nx = try(a, b)\ny = can(c)\n"
    assert _hits("safety", src) == [
        "validation {",
        "precondition {",
        "prevent_destroy = true",
        "sensitive = true",
        "try(",
        "can(",
    ]


def test_branches_are_conditionals_for_clauses_and_count_for_each_arguments():
    src = (
        "count = var.on ? 1 : 0\n"
        "for_each = toset(var.xs)\n"
        'ys = [for x in var.xs : x if x != ""]\n'
        "name = format_for_each\n"
        "count = 2\n"
    )
    assert _hits("branch", src) == ["count =", "?", "for_each =", "for", "if", "count ="]


def test_doc_and_test_signals():
    assert _hits("doc", 'description = "x"\n  description = "y"\nnot_description = 1\n') == [
        "description =",
        "description =",
    ]
    assert _hits("test", 'run "a" {\n  command = plan\n  assert {\n  }\n}\n') == ['run "a" {', "assert {"]


def test_provisioners_are_high_risk_execution():
    hits = _hits("high_risk_execution", 'provisioner "local-exec" {\n  interpreter = ["bash"]\n}\nnull_resource.x\n')
    assert hits == ["provisioner", "interpreter =", "null_resource"]


def test_dead_code_is_a_commented_out_block():
    src = '# resource "a" "b" {\n// module "m" {\n# a plain remark about resource\n'
    assert _hits("dead_code", src) == ['# resource "a"', '// module "m"']


def test_every_rule_survives_pathological_input():
    payloads = [
        'module "a" {\n' + "  x = { a = 1 }\n" * 4000,
        'module "a" {\n' + "{" * 5000 + "\n",
        'module "a" {' + " source " * 5000 + "\n",
        "resource" + ' "a"' * 5000 + "\n",
        'variable "' + "a" * 20000 + "\n",
        "# " + 'module "a" {' * 3000 + "\n",
        "x = <<EOT\n" + "a\n" * 20000,
        "x = <<" + "A" * 20000 + "\n",
        '"' + "a\n" * 5000,
        "/*" + "a" * 30000,
        "for " * 5000 + "\n",
        "provider = " + "a." * 5000 + "\n",
        "[for " + "a, " * 5000 + "\n",
        "description" + " =" * 5000 + "\n",
    ]
    pairs = [(rule, p) for rule in [r for r in RULES.values() if hasattr(r, "finditer")] for p in payloads]
    assert_redos_immune_all(pairs)
    blank = re.compile(HCL["import_capture_blank"])
    assert_redos_immune_all([(blank, p) for p in payloads])
