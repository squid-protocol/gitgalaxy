"""#8058: the named-counter commands' operands against IBM's declared types (CICS TS 6.x, `summary-<verb>-counter-<verb>-dcounter`
per command; the table is docs/language_status/cics_operand_types_counters.md).

IBM's syntax diagrams: GET COUNTER VALUE is a data-area (a receiver); INCREMENT / COMPAREMIN / COMPAREMAX, UPDATE VALUE /
COMPAREMIN / COMPAREMAX, DEFINE VALUE / MINIMUM / MAXIMUM and REWIND INCREMENT are data-values for COUNTER (a constant is
valid, "For a data-value, you can also use a constant"); the DCOUNTER diagrams of GET, UPDATE, DEFINE MAXIMUM and REWIND
print some of those as data-area (their headings say data-value). QUERY VALUE / MINIMUM / MAXIMUM are data-areas.
det reads the senders through `long_` / `int_` (a literal or a data name) and the receivers through `Cics.ref` (a data
name only, #7959). This pins both sides for COUNTER AND DCOUNTER, so no data-value option is refused as "not a data area"."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_det_translate import _LenCics  # noqa: E402

from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402


class _StrictCics(_LenCics):
    """The test stubs' lax `ref` replaced by the real one, which refuses anything but a data name."""

    ref = C.Cics.ref


# (command, option) senders IBM declares a data-value (COUNTER) or whose DCOUNTER diagram prints data-area: det takes both
SENDERS = [
    ("GET {K}(C) VALUE(V) INCREMENT({x}) NOHANDLE", "INCREMENT"),
    ("GET {K}(C) VALUE(V) COMPAREMIN({x}) NOHANDLE", "COMPAREMIN"),
    ("GET {K}(C) VALUE(V) COMPAREMAX({x}) NOHANDLE", "COMPAREMAX"),
    ("UPDATE {K}(C) VALUE({x})", "UPDATE VALUE"),
    ("DEFINE {K}(C) VALUE({x})", "DEFINE VALUE"),
    ("DEFINE {K}(C) VALUE(1) MINIMUM({x})", "DEFINE MINIMUM"),
    ("DEFINE {K}(C) VALUE(1) MAXIMUM({x})", "DEFINE MAXIMUM"),
    ("REWIND {K}(C) INCREMENT({x})", "REWIND INCREMENT"),
]

# receivers IBM declares a data-area: a literal is refused by name
RECEIVERS = [
    "GET {K}(C) VALUE({x})",
    "QUERY {K}(C) VALUE({x})",
    "QUERY {K}(C) MINIMUM({x})",
    "QUERY {K}(C) MAXIMUM({x})",
]


@pytest.mark.parametrize("kind", ["COUNTER", "DCOUNTER"])
@pytest.mark.parametrize("operand", ["5", "WS-N"])
@pytest.mark.parametrize(("template", "option"), SENDERS, ids=[o for _, o in SENDERS])
def test_a_counter_sender_takes_a_constant_or_a_data_name(template, option, kind, operand):
    out = _StrictCics().command(template.format(K=kind, x=operand), "")
    assert out and "not a data area" not in " ".join(out), option


@pytest.mark.parametrize("kind", ["COUNTER", "DCOUNTER"])
@pytest.mark.parametrize("template", RECEIVERS)
def test_a_counter_receiver_refuses_a_constant_and_takes_a_data_name(template, kind):
    with pytest.raises(C.CicsError, match="not a data area"):
        _StrictCics().command(template.format(K=kind, x="7"), "")
    assert _StrictCics().command(template.format(K=kind, x="WS-N"), "")


@pytest.mark.parametrize("kind", ["COUNTER", "DCOUNTER"])
@pytest.mark.parametrize("opt", ["COMPAREMIN", "COMPAREMAX"])
def test_update_compare_options_are_refused_as_not_modelled_never_as_a_data_area(kind, opt):
    """IBM does not say whether the range tests the new VALUE or the current value: a modelling refusal, not a type one."""
    with pytest.raises(C.CicsError, match="not modelled") as e:
        _StrictCics().command(f"UPDATE {kind}(C) VALUE(1) {opt}(5)", "")
    assert "not a data area" not in str(e.value)


def test_the_counter_audit_page_lists_every_option():
    page = HERE.parents[1] / "docs" / "language_status" / "cics_operand_types_counters.md"
    text = page.read_text(encoding="utf-8")
    for opt in ("VALUE", "INCREMENT", "COMPAREMIN", "COMPAREMAX", "MINIMUM", "MAXIMUM", "COUNTER", "DCOUNTER", "POOL"):
        assert f"`{opt}`" in text, f"{opt} missing from {page.name}"
