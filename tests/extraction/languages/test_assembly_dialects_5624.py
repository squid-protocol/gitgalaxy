"""Assembly dialects with colonless column-0 labels (#5624): Argonaut 65816/SuperFX, Devpac/vasm 68k.

Covers the three layers the DOOM-FX engine sources needed: the aperture keeps a text `.a` (and drops a
static-library archive), the lens maps `.a` / `.i` / `.inc` / `.asm` by dialect evidence only, and
`func_start` reads a column-0 label with no colon as an entry when code follows it.
"""

import pytest

from gitgalaxy.core.aperture import ApertureFilter
from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG
from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS, LENS_CONFIG

ASM = LANGUAGE_DEFINITIONS["assembly"]
FUNC_START = ASM["rules"]["func_start"]

# 65816 / SuperFX, Argonaut style (DOOM-FX rlirq.a shape).
ARGONAUT_65816 = (
    ";  ENGINE IRQ MODULE\n"
    "\tinclude\trage.i\n"
    "\tpublic\t_RLInitIRQ\n"
    "\tSECTION\tENGINE\n"
    ";\n"
    "\tdbr\t?\n"
    "_RLInitIRQ\n"
    "\tmode\t'A!'\n"
    "\tstz\tIRQTPhase\t\t; Phase of TOP IRQ\n"
    "\tjml\tInitIRQ\n"
    "_RIB1000\n"
    "\tpha\n"
    "\trts\n"
)

# 68k Devpac / vasm (DOOM-FX ripdoomiff.asm shape): xref/xdef, comment after the label, blank line.
DEVPAC_68K = (
    "\tinclude\tripdoom.i\n"
    "\txref\tDosBase\n"
    "\tsection\tIFF,CODE\n"
    "\txdef\tFindIFFChunk,GetIFFByte\n"
    "FindIFFChunk\t\t\t; find a chunk\n"
    "\tmove.l\t4(a2),d2\n"
    "FIC200\n"
    "\tsubq.l\t#4,d2\n"
    "\tbne\tFIC200\n"
    "\trts\n"
    "\n"
    "GetIFFByte\n"
    "\n"
    "\ttst.b\tIFFComp\n"
    "\trts\n"
)

# Include file: constants, structure offsets and a macro, no code label at all.
INCLUDE_FILE = (
    "rlod\t\t\tvar\t0\n"
    "rlodFlags\t\tequ\trlod\t\t; Flags\n"
    "rlodfKill\t\tequ\t$0002\n"
    "HALT\tMACRO\n"
    "\tife\tNOAICESE\n"
    "\tENDM\n"
)

_X86_NASM = "section .text\nglobal _start\n_start:\n    mov rax, 60\n    syscall\n"
_HLASM_MEMBER = "ACCTPGM  CSECT\n         USING *,12\n         L     R1,0(R2)\n         BR    14\n"


def _names(text: str) -> list[str]:
    return FUNC_START.findall(text)


# ---- func_start --------------------------------------------------------------------------------------------


def test_argonaut_label_followed_by_code_is_an_entry():
    # `_RIB1000` is the dialect's local-label shape (name ending in 3+ digits): not an entry.
    assert _names(ARGONAUT_65816) == ["_RLInitIRQ"]


def test_devpac_labels_with_trailing_comment_and_blank_lines_are_entries():
    assert _names(DEVPAC_68K) == ["FindIFFChunk", "GetIFFByte"]


@pytest.mark.parametrize(
    "snippet",
    [
        "rlodFlags\t\tequ\trlod\n\tmove.l\td0,d1\n",  # EQU keeps its statement on the label line
        "HALT\tMACRO\n\tife\tX\n",  # macro definition
        "rlod\t\tvar\t0\n\tmove.l\td0,d1\n",
        "Table\n\tdc.b\t1,2,3\n",  # data label
        "Buf\n\tds.w\t16\n",
        "Flags\n\tequ\t3\n",
        "Msg\n\tdb\t'hi',0\n",
        "\tmove.l\td0,d1\n",  # an instruction is not a label
        "\tpublic\t_RLInitIRQ\n\tmove.l\td0,d1\n",  # an export statement is not a label
        "end\n\tmove.l\td0,d1\n",
        "ENDM\n\tmove.l\td0,d1\n",
        "_Last\n",  # a label with nothing after it
        "_Last\n\n\n",
    ],
)
def test_definitions_and_data_labels_are_not_entries(snippet):
    assert _names(snippet) == []


def test_include_file_has_no_entries():
    assert _names(INCLUDE_FILE) == []


@pytest.mark.parametrize(
    "snippet, expected",
    [
        ("main:\n    mov eax, 1\n", ["main"]),  # the colon form is unchanged
        ("  helper: ret\n", ["helper"]),
        (".Lloop:\n    ret\n", []),
        ('msg:\n    .asciz "x"\n', []),
        ("Foo\n    mov eax, 1\n", ["Foo"]),  # NASM colonless label alone on its line
    ],
)
def test_colon_form_and_other_dialects_keep_their_behaviour(snippet, expected):
    assert _names(snippet) == expected


# ---- lens: `.a` / `.i` / `.inc` / `.asm` mapped by content ------------------------------------------------------


def test_a_and_i_are_registered_collisions_owned_on_proof():
    for ext in (".a", ".i"):
        assert ext in LENS_CONFIG["COLLISION_FREQUENCIES"]
        assert ext in ASM["extensions"]
        assert ext in ASM["extensions_needing_discriminator"]


@pytest.mark.parametrize(
    "path, text",
    [
        ("source/rlirq.a", ARGONAUT_65816),
        ("source/ripdoomiff.asm", DEVPAC_68K),
        ("source/rlirq.s", DEVPAC_68K),
        ("source/rage.inc", DEVPAC_68K),
        ("source/rlobjects.i", INCLUDE_FILE),
        ("source/rlmath.a.i", ARGONAUT_65816),
    ],
)
def test_dialect_sources_resolve_to_assembly(path, text):
    lang, _conf, _family = LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus(path, text)
    assert lang == "assembly", f"{path} must map to assembly (got {lang!r})"


@pytest.mark.parametrize(
    "path, text",
    [
        ("api/foo.i", '%module foo\n%{\n#include "foo.h"\n%}\nint add(int a, int b);\n'),  # SWIG
        ("build/pre.i", '# 1 "x.c"\nint main(void) { return 0; }\n'),  # preprocessed C
        ("lib/readme.a", "; notes\nsome words here\n"),
    ],
)
def test_a_and_i_without_dialect_evidence_are_not_assembly(path, text):
    lang, _conf, _family = LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus(path, text)
    assert lang != "assembly", f"{path} has no assembly evidence (got {lang!r})"


def test_hlasm_and_x86_asm_are_not_taken_by_the_new_evidence():
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    assert detector.focus("src/acctpgm.asm", _HLASM_MEMBER)[0] == "hlasm"
    assert detector.focus("src/boot.asm", _X86_NASM)[0] == "assembly"
    assert not ASM["internal_discriminator"].search(_HLASM_MEMBER)


# ---- aperture: a text `.a` passes, an `ar` archive does not -----------------------------------------------------


@pytest.fixture
def aperture(tmp_path):
    return ApertureFilter(root_dir=tmp_path, language_definitions=LANGUAGE_DEFINITIONS, aperture_config=APERTURE_CONFIG)


def test_text_a_file_passes_the_extension_firewall(aperture, tmp_path):
    src = tmp_path / "rlirq.a"
    src.write_text(ARGONAUT_65816)
    ok, _size, reason = aperture.evaluate_path_integrity(src)
    assert ok, reason


def test_ar_archive_is_still_denied(aperture, tmp_path):
    lib = tmp_path / "libiconv.a"
    lib.write_bytes(b"!<arch>\n/               0           0     0     0       8         `\n\x00\x01\x02")
    ok, _size, reason = aperture.evaluate_path_integrity(lib)
    assert not ok
    assert "Denied Extension" in str(reason)
