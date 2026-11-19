"""#8412: the COMP-boundary matrix, layout and image layer (no Docker, no JDK).

Blind estate 1's three first-contact data bugs shared one shape, a binary / packed / floating item crossing a data
boundary. Every boundary reads an item through two facts: how many bytes it occupies and what bytes a value becomes.
This matrix pins both for every USAGE (DISPLAY, COMP / COMP-4 / BINARY, COMP-5, COMP-3, COMP-1, COMP-2), signed and
unsigned, at the digit-count edges where IBM changes the width (Enterprise COBOL for z/OS Language Reference, USAGE:
halfword 1-4 digits, fullword 5-9, doubleword 10-18; packed digits / 2 + 1), in three places that must agree:

1. the translator's own layout (`det.layout`), which a COMMAREA, a channel container, a TS / TD record, a Db2 host
   variable and a file record are all cut from;
2. the engine's layout (`GalaxyIR.record_layout`), the authority the translator adopts (#5649);
3. the VALUE / MOVE image (`encode_number` -> `decode_number`) for the usages the translator decodes.

The Docker-backed cells (each boundary run on both runtimes) stay in the per-boundary tests named in the PR body.
Authored programs, invented names."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scan_server import scan_to_db  # noqa: E402

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import layout as L  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det.source import program_lines  # noqa: E402

# (item name, USAGE clause, PICTURE, bytes, usage the translator holds)
USAGES = {
    "COMP": ("BINARY", "COMP"),
    "COMP-4": ("BINARY", "COMP-4"),
    "BINARY": ("BINARY", "BINARY"),
    "COMP-5": ("COMP-5", "COMP-5"),
    "COMP-3": ("PACKED", "COMP-3"),
}
# digits -> bytes of a binary item (halfword / fullword / doubleword)
BINARY_WIDTH = {1: 2, 4: 2, 5: 4, 9: 4, 10: 8, 18: 8}
# digits -> bytes of a packed item
PACKED_WIDTH = {1: 1, 2: 2, 3: 2, 4: 3, 9: 5, 10: 6, 18: 10, 31: 16}

ROWS: list[tuple[str, str, str, int, str]] = []
for _signed in (False, True):
    _s = "S" if _signed else ""
    for _clause, (_held, _word) in USAGES.items():
        _table = PACKED_WIDTH if _held == "PACKED" else BINARY_WIDTH
        for _d, _bytes in _table.items():
            _name = f"{'S' if _signed else 'U'}{_clause.replace('-', '')}D{_d}"
            ROWS.append((_name, _word, f"{_s}9({_d})", _bytes, _held))
# floating point and a scaled binary item, which keeps its width (the V takes no byte)
ROWS += [
    ("FLT1", "COMP-1", "", 4, "COMP-1"),
    ("FLT2", "COMP-2", "", 8, "COMP-2"),
    ("SCAL", "COMP", "S9(4)V99", 4, "BINARY"),
    ("SCLP", "COMP-3", "S9(3)V99", 3, "PACKED"),
    ("ZONE", "DISPLAY", "S9(5)", 5, "DISPLAY"),
]


def _source() -> str:
    out = [
        "       IDENTIFICATION DIVISION.",
        "       PROGRAM-ID. MATTOY.",
        "       DATA DIVISION.",
        "       WORKING-STORAGE SECTION.",
        "       01  MAT-REC.",
    ]
    for name, word, pic, _, _ in ROWS:
        out.append(f"           05  {name:<12}{('PIC ' + pic) if pic else '':<14}USAGE {word}.")
    out += ["       PROCEDURE DIVISION.", "           GOBACK."]
    return "\n".join(out) + "\n"


@pytest.fixture(scope="module")
def estate(tmp_path_factory):
    pytest.importorskip("tree_sitter_language_pack")
    base = tmp_path_factory.mktemp("comp_matrix_8412")
    repo = base / "repo"
    repo.mkdir()
    (repo / "MATTOY.cbl").write_text(_source(), encoding="utf-8")
    ir = load_galaxy_ir(scan_to_db(repo, base / "scan"))
    lines = program_lines(repo / "MATTOY.cbl", [repo], None)
    recs = L.parse(lines)
    for r in recs:
        L.layout(r)
    items = {x.name: x for r in recs for x in r.walk()}
    return ir, items


def test_the_matrix_covers_every_width_edge():
    """A row table that silently lost a usage or an edge would make every other test here vacuous."""
    assert len(ROWS) == len({r[0] for r in ROWS})
    held = {r[4] for r in ROWS}
    assert held == {"BINARY", "COMP-5", "PACKED", "COMP-1", "COMP-2", "DISPLAY"}
    assert {r[3] for r in ROWS if r[4] == "BINARY"} == {2, 4, 8}


@pytest.mark.parametrize("row", ROWS, ids=[r[0] for r in ROWS])
def test_the_translator_sizes_each_item_as_ibm(estate, row):
    name, _, _, size, held = row
    it = estate[1][name]
    assert (it.usage, it.size) == (held, size)


def test_the_items_follow_each_other_with_no_slack_without_sync(estate):
    """No SYNC: IBM inserts no slack, so each offset is the sum of the sizes before it (SYNC cells: #5694's tests)."""
    at = 0
    for name, _, _, size, _ in ROWS:
        assert estate[1][name].offset == at, name
        at += size
    assert estate[1]["MAT-REC"].size == at


def test_the_engine_lays_the_record_out_as_the_translator_does(estate):
    ir, items = estate
    ef = ir.files["MATTOY.cbl"]
    top = next(i for i in ef.data_items if i.name == "MAT-REC")
    fields = {f["name"]: (f["offset"], f["bytes"]) for f in ir.record_layout(ef, top)["fields"]}
    ours = {n: (it.offset, it.size) for n, it in items.items() if n != "MAT-REC"}
    assert fields == ours


# the values each decoding usage must survive: zero, one digit, a full-width value and (signed) its negative
CASES = [Decimal(0), Decimal(7), Decimal("-7"), Decimal("123"), Decimal("-123")]


@pytest.mark.parametrize("row", [r for r in ROWS if r[4] == "PACKED"], ids=lambda r: r[0])
def test_a_packed_item_round_trips_and_takes_ibms_sign_nibble(estate, row):
    name, _, _, size, _ = row
    it = estate[1][name]
    for v in CASES:
        want = v if it.signed or v >= 0 else abs(v)
        if it.digits < len(str(abs(int(v)))):
            continue
        data = L.encode_number(it, want)
        assert len(data) == size
        # IBM: C positive / D negative for a signed item, F for an unsigned one (NUMPROC(NOPFD); PFD and MIG: #8412 slice)
        assert data.hex()[-1].upper() == ("D" if want < 0 else "C" if it.signed else "F")
        assert L.decode_number(it, data) == want


def test_a_zoned_item_round_trips_with_an_overpunched_sign(estate):
    it = estate[1]["ZONE"]
    for v in (Decimal(0), Decimal(5), Decimal("-5"), Decimal("12345"), Decimal("-12345")):
        data = L.encode_number(it, v)
        assert len(data) == 5
        assert L.decode_number(it, data) == v


@pytest.mark.parametrize("row", [r for r in ROWS if r[4] == "BINARY"], ids=lambda r: r[0])
def test_a_binary_item_is_big_endian_twos_complement(estate, row):
    name, _, _, size, _ = row
    it = estate[1][name]
    if it.scale:
        return
    top = 10**it.digits - 1
    for v in (0, 1, top) + ((-1, -top) if it.signed else ()):
        data = L.encode_number(it, Decimal(v))
        assert data == int(v).to_bytes(size, "big", signed=it.signed or v < 0), (name, v)


@pytest.mark.parametrize("row", [r for r in ROWS if r[4] == "COMP-5"], ids=lambda r: r[0])
def test_a_comp5_item_holds_the_native_value_in_its_bytes(estate, row):
    name, _, _, size, _ = row
    it = estate[1][name]
    for v in (0, 1, 7) + ((-1,) if it.signed else ()):
        data = L.encode_number(it, Decimal(v))
        assert len(data) == size
        assert int.from_bytes(data, L.comp5_order(), signed=it.signed) == v


# --- slice 2 (#8412): the NUMPROC sign-nibble cells and the TRUNC variants ---------------------------------------
# The image is option-independent: what the translator writes for a packed item is IBM's preferred sign (C / D signed,
# F unsigned), the one sign NUMPROC(PFD) trusts and NUMPROC(NOPFD) also repairs. So the cells below pin (a) which
# option value reaches the translator for every spelling a compile step can use, and (b) every sign nibble the image
# reads. The run-time refusal of a non-preferred sign under PFD (Codec.preferredSign) is a Java cell: Docker slice.
from gitgalaxy.tools.cobol_to_java.det import program as P  # noqa: E402

_NUMPROC = {"PFD": True, "NOPFD": False, "MIG": False, None: False}  # MIG is NOPFD (Migration Guide, Table 18)
_TRUNC = {"STD": "STD", "BIN": "BIN", "OPT": "OPT", None: "STD"}  # IBM's default is STD


def _opt_program(tmp_path, card):
    p = tmp_path / "OPTTOY.cbl"
    p.write_text(f"{card}       IDENTIFICATION DIVISION.\n       PROGRAM-ID. OPTTOY.\n       PROCEDURE DIVISION.\n"
                 "           GOBACK.\n", encoding="utf-8")  # fmt: skip
    return p


@pytest.mark.parametrize("numproc", list(_NUMPROC), ids=str)
@pytest.mark.parametrize("trunc", list(_TRUNC), ids=str)
@pytest.mark.parametrize("via", ["parm", "cbl-card"])
def test_every_numproc_and_trunc_spelling_reaches_the_translator(tmp_path, numproc, trunc, via):
    named = [f"{k}({v})" for k, v in (("NUMPROC", numproc), ("TRUNC", trunc)) if v]
    parm = named if via == "parm" else None
    card = f"       CBL {','.join(named)}\n" if via == "cbl-card" and named else ""
    prog = _opt_program(tmp_path, card)
    assert P.numproc_pfd(prog, parm) is _NUMPROC[numproc]
    assert P.trunc_mode(prog, parm) == _TRUNC[trunc]
    assert P.trunc_std(prog, parm) is (_TRUNC[trunc] != "BIN")


def test_a_cbl_card_overrides_the_compile_step_parm(tmp_path):
    prog = _opt_program(tmp_path, "       CBL NUMPROC(NOPFD),TRUNC(BIN)\n")
    assert P.numproc_pfd(prog, ["NUMPROC(PFD)"]) is False
    assert P.trunc_mode(prog, ["TRUNC(OPT)"]) == "BIN"


@pytest.mark.parametrize("row", [r for r in ROWS if r[4] == "PACKED"], ids=lambda r: r[0])
def test_every_sign_nibble_a_packed_item_can_carry_is_read_or_refused_by_name(estate, row):
    """Each nibble 0-F on every packed width: C D F read as IBM's preferred signs; none other reads as a number (the
    image returns None, never a wrong value). A / B / E (NOPFD repairs them on z/OS; PFD does not) are the sibling gap."""
    name, _, _, size, _ = row
    it = estate[1][name]
    body = "0" * (size * 2 - 2) + "7"
    seven = Decimal(7) / Decimal(10) ** it.scale
    for nib in "0123456789ABCDEF":
        got = L.decode_number(it, bytes.fromhex(body + nib))
        if nib in "CF":
            assert got == seven, (name, nib)
        elif nib == "D":
            assert got == -seven, (name, nib)
        else:
            assert got is None, (name, nib)


@pytest.mark.parametrize("row", [r for r in ROWS if r[4] == "PACKED"], ids=lambda r: r[0])
def test_the_image_writes_only_the_preferred_sign_pfd_accepts(estate, row):
    """What PFD trusts is what the image writes: a signed zero is C (never D), a signed negative D, unsigned F."""
    name = row[0]
    it = estate[1][name]
    for v in (Decimal(0), Decimal("-0"), Decimal(7), Decimal("-7")):
        data = L.encode_number(it, v)
        nib = data.hex()[-1].upper()
        if not it.signed:
            assert nib == "F"
        elif v < 0:
            assert nib == "D"
        else:
            assert nib == "C"  # a zero, positive or negative, is C: PFD refuses D on a zero (preferredSign)


@pytest.mark.parametrize("row", [r for r in ROWS if r[4] == "BINARY" and not r[2].endswith("V99")], ids=lambda r: r[0])
def test_a_binary_value_past_its_picture_keeps_the_pictures_digits_in_the_image(estate, row):
    """TRUNC(STD) / TRUNC(OPT) keep the PICTURE's low digits; the image is that, whichever TRUNC is in force, because a
    VALUE or MOVE image is built from the PICTURE (the TRUNC(BIN) full-width arithmetic is the runtime's: Docker cell)."""
    name, _, _, size, _ = row
    it = estate[1][name]
    over = Decimal(10) ** it.digits + 5  # one digit too many: 10**d + 5
    data = L.encode_number(it, over)
    assert len(data) == size
    assert int.from_bytes(data, "big", signed=it.signed) == 5, name
