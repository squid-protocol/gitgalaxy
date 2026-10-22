"""#5089: a RETURN whose COMMAREA LENGTH differs from the DFHCOMMAREA record is answered through the program's codec.

CBSA BNK1UAC returns 99 bytes of a 107-byte record ending in a POINTER (IBM: the next task sees EIBCALEN 99, the POINTER
was never passed); BNK1TFN returns LENGTH(29) over a 28-byte item (the byte past it is storage no one defined). A DTO
with no layout (fromCommarea refuses a POINTER) is read from the passed bytes through the storage codec instead, and the
harness checks that read by writing the DTO back and comparing the bytes over the span both define.

Two layers: the arithmetic of the shapes (what a record needs, what it spans) and the generated facade source.
"""

import pytest

pytest.importorskip("tree_sitter_language_pack")

from gitgalaxy.tools.cobol_to_java.det import program as P  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det.cics import POINTER_BYTES, Dto, Leaf  # noqa: E402


def _leaf(var, usage, offset, size, pic="X"):
    return Leaf(var, "String", var.upper(), pic, usage, offset, size)


class _Gp:
    def __init__(self, dtos):
        self._dtos = dtos

    def dto(self, cls):
        return self._dtos[cls]


class _Cx:
    def __init__(self, dtos):
        self.codecs = {cls: [] for cls in dtos}
        self.gp = _Gp(dtos)


def _uac_like():
    """99 bytes of text, then a POINTER (IBM 4 bytes, the port's storage 8)."""
    return Dto("Uac", leaves=[_leaf("body", "DISPLAY", 0, 99), _leaf("commPcb1Pointer", "POINTER", 99, 4)])


def test_a_trailing_pointer_is_not_needed_but_is_spanned():
    extent, need = P.wide_shapes(_Cx({"Uac": _uac_like()}))["Uac"]
    assert need == 99  # the bytes a LENGTH(99) RETURN passed are all the record needs
    assert extent == 99 + POINTER_BYTES  # the object spans the wider POINTER: 107, the record the facade answers


def test_a_record_longer_than_its_item_needs_only_the_item():
    tfn = Dto("Tfn", leaves=[_leaf("f", "DISPLAY", 0, 8), _leaf("t", "DISPLAY", 8, 8), _leaf("amt", "DISPLAY", 16, 12)])
    assert P.wide_shapes(_Cx({"Tfn": tfn}))["Tfn"] == (28, 28)  # LENGTH(29) passes one byte nothing defines


def test_a_non_pointer_field_past_the_bytes_is_never_guessed():
    """Fewer bytes than the non-POINTER properties need are answered null (task.returned refuses by name)."""
    java = "\n".join(P.codec_answer(P.wide_shapes(_Cx({"Uac": _uac_like()}))))
    assert "ebcdic.length < 99 ? null :" in java
    assert "out_Uac(wideStorage(ebcdic, 107), 0)" in java


def test_the_helpers_read_through_the_codec_and_check_the_round_trip():
    java = "\n".join(P.codec_answer(P.wide_shapes(_Cx({"Uac": _uac_like()}))))
    assert "in_Uac(d, s, 0);" in java and "public boolean wideSame(byte[] ebcdic, Object dto)" in java
    assert java.count("@facade-helper") == 3
    assert "return false;" in java  # a DTO the program has no codec for matches nothing


def _stub(ret):
    return (
        f"public class S {{\n    public {ret} handleTransaction(String transid, {ret} request) {{\n"
        '        region.run(task, "PROG", this::runTask);\n        return task.returned(' + ret + ".class);\n    }\n}\n"
    )


def test_a_facade_reads_through_the_codec_only_for_a_program_with_codecs():
    shapes = P.wide_shapes(_Cx({"Uac": _uac_like()}))
    java = "\n".join(P.facades(_stub("Uac"), True, shapes))
    assert "Uac read = wideAnswer(wide, Uac.class);" in java and "read = codecAnswer(wide, Uac.class);" in java
    assert "return task.returned(Uac.class);" in java  # what no reading covers is still refused by name
    plain = "\n".join(P.facades(_stub("Uac"), True))
    assert "codecAnswer" not in plain and "Uac read = wideAnswer(wide, Uac.class);" in plain


def test_a_program_that_passes_no_bytes_is_unchanged():
    shapes = P.wide_shapes(_Cx({"Uac": _uac_like()}))
    java = "\n".join(P.facades(_stub("Uac"), False, shapes))
    assert "codecAnswer" not in java and "wideSame" not in java
