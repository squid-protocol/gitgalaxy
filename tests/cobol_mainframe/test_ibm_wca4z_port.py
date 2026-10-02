"""ibm_wca4z_port.py's source rewrites: the INSERT-CUSTOMER swap and the diagnostic ERROR-MSG clamp (offline)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests" / "tools"))

import ibm_wca4z_port as iw

FIELDS = "\n".join(f"    Field f{n}_{v};" for n, v in enumerate(iw.HOST_VARIABLES, start=10))
SERVICE = f"""class Lgacdb01Service {{
{FIELDS}

    /** INSERT-CUSTOMER. */
    private int p3() {{
        // MOVE ' INSERT CUSTOMER' TO EM-SQLREQ
        if (x) {{
            return GOTO | 9;
        }}
        return 4;
    }}

    /** WRITE-ERROR-MESSAGE. */
    private int p4() {{
        return 5;
    }}
}}
"""


def test_adapt_swaps_only_the_paragraph() -> None:
    out = iw.adapt(SERVICE)
    assert "com.ibm.wcaz.implementation.Lgacdb01.insertCustomer(" in out
    assert "MOVE ' INSERT CUSTOMER'" not in out  # the det body is gone
    assert (
        "        return 4;\n    }\n\n    /** WRITE-ERROR-MESSAGE. */\n    private int p4() {\n        return 5;" in out
    )
    assert "Cobol.text(f13_CA_FIRST_NAME, CS)" in out  # host variables resolved to the det port's fields
    assert out.count("{") == out.count("}")


def test_adapt_refuses_an_ambiguous_field() -> None:
    with pytest.raises(SystemExit, match="CA_DOB"):
        iw.adapt(SERVICE.replace("    /** INSERT-CUSTOMER", "    Field f99_CA_DOB;\n\n    /** INSERT-CUSTOMER"))


def test_clamp_touches_only_error_msg_marshalling() -> None:
    src = """    private void fill_Lgacdb01CaErrorMsg(Lgacdb01CaErrorMsg d, Storage s, int base) {
        d.setCaData(Cobol.text(Field.alphanumeric(s, base + 9, 90, false), CS));
    }

    private void fill_Other(Other d, Storage s, int base) {
        d.setX(Cobol.text(Field.alphanumeric(s, base + 9, 90, false), CS));
    }
"""
    out = iw.clamp_error_msg(src)
    assert "Math.min(90, s.bytes.length - base - 9)" in out.split("fill_Other")[0]
    assert "Field.alphanumeric(s, base + 9, 90, false)" in out.split("fill_Other")[1]
