"""#4171: dead_code counts commented-out statements (call, assignment, declaration ending in `;`) in the
`;`-terminated C-family languages, not only keyword-led comment lines -- see docs/dead_code_rule_contract.md."""

import re

import pytest
from _timing import assert_cpu_below

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards._shared_patterns import COMMENTED_STATEMENT_C_FAMILY

LANGS = ["java", "c", "cpp", "csharp", "javascript", "typescript", "dart", "rust"]
COMMENTED_CODE = [
    "// ps.setDate(4, caCustomerRequest.getGenasa1Customer().getDateofbirth());",
    "// caReturnCode = 90;",
    "// errorMsg.writeErrorMessage();",
    "// insertCustomer();",
    "/* foo.bar(x); */",
    "// count += 1;",
    "// node->next = head;",
]
PROSE = [
    "// just a note",
    "// Load data;",
    "// Returns the value;",
    "// Note that a = b;",
    "// see foo(bar) for details",
    "// TODO: fix this later;",
    "// e.g. x == y;",
    "// Compare a == b;",
    "// Version 2;",
    "// step 1: call init()",
    "/** Calls foo(); */",
]


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("line", COMMENTED_CODE)
def test_a_commented_out_statement_is_dead_code(lang, line):
    assert LANGUAGE_DEFINITIONS[lang]["rules"]["dead_code"].search(line)


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("line", PROSE)
def test_prose_comments_are_not_dead_code(lang, line):
    assert not LANGUAGE_DEFINITIONS[lang]["rules"]["dead_code"].search(line)


@pytest.mark.parametrize("line", ["// CaCustomerRequest r = new CaCustomerRequest();", "// long n = 0;",
                                  "// String lgacNcs = \"ON\";", "// int x;"])  # fmt: skip
def test_java_declarations(line):
    assert LANGUAGE_DEFINITIONS["java"]["rules"]["dead_code"].search(line)


def test_the_wca4z_shape_counts_once_per_commented_line():
    src = """    // CaCustomerRequest caCustomerRequest = new CaCustomerRequest();
    ErrorMsg errorMsg = new ErrorMsg();
    // ps.setDate(4, caCustomerRequest.getGenasa1Customer().getDateofbirth());
    } catch (Exception exception) {
        // caReturnCode = 90;
        // errorMsg.writeErrorMessage();
        System.out.println("[EXCEPTION CAUGHT] " + exception);
"""
    assert len(LANGUAGE_DEFINITIONS["java"]["rules"]["dead_code"].findall(src)) == 4


@pytest.mark.parametrize("payload", ["// " + "a." * 20000 + "b(" + "x" * 20000,
                                     "// A " + "b" * 20000 + " =" + "=" * 20000, "// " + "a" * 20000 + "[" * 20000])  # fmt: skip
def test_the_statement_shape_is_linear(payload):
    # CPU-time bound (#4477): ~ms honest, a backtracking statement shape costs minutes on 40k chars
    rule = LANGUAGE_DEFINITIONS["java"]["rules"]["dead_code"]
    assert_cpu_below(lambda: rule.search(payload), 1.0, what="dead_code statement shape")


def test_the_statement_fragment_skips_doc_lines():
    # (a `///` line can still match a language's own keyword alternative, e.g. rust/javascript `let` -- unchanged)
    frag = re.compile(COMMENTED_STATEMENT_C_FAMILY)
    assert not frag.search("/// x = foo();") and not frag.search("/** foo(); */")
    assert frag.search("// x = foo();")


def test_semicolon_free_languages_keep_their_keyword_rule():
    for lang in ("kotlin", "go", "swift", "scala"):
        assert not LANGUAGE_DEFINITIONS[lang]["rules"]["dead_code"].search("// foo.bar(1);")
