"""#5460: the content payload guards keep a file that has function definitions beside a data table."""

import pytest

from gitgalaxy.core.aperture import ApertureFilter
from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

FUNCS = (
    "int add(int a, int b)\n{\n    return a + b;\n}\n\n"
    "static void reset(void) {\n    count = 0;\n}\n\n"
    "unsigned long crc_update(unsigned long crc, const unsigned char *buf)\n{\n    return crc ^ buf[0];\n}\n"
)


@pytest.fixture
def engine(tmp_path):
    return ApertureFilter(root_dir=tmp_path, language_definitions=LANGUAGE_DEFINITIONS, aperture_config=APERTURE_CONFIG)


def _hex_table() -> str:
    return (
        "static const unsigned char tab[] = {\n"
        + "".join("    0x1f, 0x2e, 0x3d, 0x4c,\n" for _ in range(3000))
        + "};\n"
    )


def _comma_table() -> str:
    return "static const int tab[] = {\n" + "".join("    1, 2, 3, 4, 5, 6, 7, 8,\n" for _ in range(3000)) + "};\n"


def _wide_row_table() -> str:
    return (
        "static const char *rows[] = {\n"
        + '    "'
        + "x" * 600
        + '",\n'
        + "".join('    "a",\n' for _ in range(50))
        + "};\n"
    )


def _flat_table() -> str:
    return "static const int tab[] = {\n" + "".join(f"    {i},\n" for i in range(2500)) + "};\n"


def _scan(engine, tmp_path, content, name="t.c"):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return engine.is_in_scope(path, content=content)["is_in_scope"]


@pytest.mark.parametrize("table", [_hex_table, _comma_table, _wide_row_table, _flat_table])
def test_a_table_with_functions_is_kept(engine, tmp_path, table):
    assert _scan(engine, tmp_path, table() + FUNCS) is True


@pytest.mark.parametrize("table", [_hex_table, _comma_table, _wide_row_table])
def test_a_pure_table_is_still_excluded(engine, tmp_path, table):
    assert _scan(engine, tmp_path, table()) is False


def test_table_rows_and_statements_are_not_definitions():
    lines = ["    FOO(1, 2),", "    {", "if (x) {", "    while (y)", "    {", "static int t[] = {", "}"]
    assert ApertureFilter._has_definitions(lines) is False


@pytest.mark.parametrize(
    "lines",
    [
        ["int main(void) {", "}"],
        ["void Foo::bar(int x)", "{", "}"],
        ["    public int Count(string s) {", "}"],
        ["static const char *name(void)", "", "{"],
        [
            "static void AES_Encrypt(aes_context_t *ctx, uint8_t *out,",
            "                        const uint8_t *in)",
            "{",
        ],
        ["InitLowerUpper()", "{"],
    ],
)
def test_definition_heads(lines):
    assert ApertureFilter._has_definitions(lines) is True


def test_a_long_line_is_skipped_not_matched():
    assert ApertureFilter._has_definitions(["int f(" + "a, " * 300 + ") {"]) is False


def test_monotony_keeps_a_file_with_definitions(engine, tmp_path):
    rows = "".join(f'  {{ "k{i}", {i} }},\n' for i in range(2100))
    body = "static const struct {\n" + rows + "} t;\n"
    assert _scan(engine, tmp_path, body, "d.cpp") is False
    assert _scan(engine, tmp_path, body + FUNCS, "d.cpp") is True


def test_name_alone_on_its_line_is_a_definition():
    assert ApertureFilter._has_definitions(["int", "SlopeDiv", "( unsigned num,", "  unsigned den )", "{"]) is True
    assert ApertureFilter._has_definitions(["    NAME", "    (1, 2)"]) is False


def test_monotony_keeps_a_file_with_one_named_function(engine, tmp_path):
    # owner ruling 2026-10-19: one named definition is enough; a file with none is still dropped.
    body = "int unrolled(void)\n{\n" + "    a += 1;\n" * 2500 + "}\n"
    assert _scan(engine, tmp_path, body, "u.c") is True
    assert _scan(engine, tmp_path, "    a += 1;\n" * 2500, "v.c") is False
