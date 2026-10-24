"""#5401 [c:cdb8fd24]: the assumption "the COMMAREA / screen codec pads and truncates each field to its declared width".

About two dozen triaged survivors of the burned CardDemo ports (billpay, cardlist, cardview, report, tranadd, userupd)
are `equivalent` because a widened `fit()` / `spaces()` value is cut back (or padded) by the codec, so the wire bytes are
the same. Three things carry that claim, and each is checked here:

1. the harness side (`equivalence_common.text_bytes`, which encodes the case's inputs for the oracle);
2. the generated runtime (`CobolRecords.putText`, compiled with the local JDK), which encodes every DTO field on the
   Java side: one probe, short / exact / over-wide / empty / multi-byte values at every width the survivors cite, and
   the bytes next to the field must stay untouched;
3. the widths the survivors cite, against the CardDemo copybooks (skipped without the corpus).

No scenario feeds a value wider than its field (IBM cannot: a terminal or a caller sends at most the field), so the
truncation is only ever exercised on a port's own output: this pins it directly instead of through a scenario.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "tools"))

import equivalence_common as ec  # noqa: E402

from gitgalaxy.core.source_text import read_source  # noqa: E402
from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import COBOL_RECORDS_JAVA  # noqa: E402

CORPORA = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA") or REPO / ".mainframe_corpora")
CARDDEMO = CORPORA / "aws-mainframe-modernization-carddemo" / "app"
SCORES = REPO / "docs" / "language_status" / "mutation_scores.json"
PORTS = ("billpay", "cardlist", "cardview", "report", "tranadd", "tranlist", "userupd")

# survivor id -> (copybook, field, declared width, width the mutant uses; None = the mutant drops a longer fill)
CLAIMS = {
    "b70049d4eb": ("cpy/COCOM01Y.cpy", "CDEMO-LAST-MAP", 7, 8),
    "7783e32cd1": ("cpy/CVTRA05Y.cpy", "TRAN-SOURCE", 10, 11),
    "4ffae205d3": ("cpy/COCOM01Y.cpy", "CDEMO-LAST-MAP", 7, 8),
    "324faac283": ("cpy/COCOM01Y.cpy", "CDEMO-FROM-PROGRAM", 8, 9),
    "68155f528c": ("cpy/COCOM01Y.cpy", "CDEMO-LAST-MAPSET", 7, 8),
    "4b38234e04": ("cpy/COCOM01Y.cpy", "CDEMO-FROM-TRANID", 4, 5),
    "c3f23eb0a2": ("cpy/COCOM01Y.cpy", "CDEMO-ACCT-STATUS", 1, 2),
    "e171f36f96": ("cpy-bms/CORPT00.CPY", "TRNNAMEO", 4, 5),
    "75df0b428f": ("cpy/COCOM01Y.cpy", "CDEMO-CUST-MNAME", 25, 26),
    "0106e63e21": ("cpy-bms/CORPT00.CPY", "EDTYYYYI", 4, 5),
    "cf4915c232": ("cpy/COCOM01Y.cpy", "CDEMO-CUST-MNAME", 25, 26),
    "37f403e632": ("cpy-bms/COTRN02.CPY", "TRNNAMEO", 4, 5),
    "1ed21175ed": ("cpy-bms/COTRN02.CPY", "MZIPO", 10, 11),
    "db96368556": ("cpy/CVTRA05Y.cpy", "TRAN-CARD-NUM", 16, 17),
    "febcd1b7d1": ("cpy-bms/COTRN02.CPY", "TPROCDTO", 10, 11),
    "aa8a2210e3": ("cpy-bms/COUSR02.CPY", "USRIDINI", 8, 9),
    "9c7ff96bda": ("cpy-bms/COUSR02.CPY", "PGMNAMEO", 8, 9),
    "bc65c7f1c5": ("cpy-bms/COUSR02.CPY", "PASSWDO", 8, 9),
    "a7e07f2dd0": ("cpy/COCOM01Y.cpy", "CDEMO-USER-TYPE", 1, None),
    "999edaea62": ("cpy/COCOM01Y.cpy", "CDEMO-LAST-MAPSET", 7, 8),
}
CODEC_REASON = re.compile(r"\bcodec\b|DTO (?:cuts|width)|the DTO\b.*\bwidth", re.I)


def _survivors():
    ports = json.loads(SCORES.read_text(encoding="utf-8"))["ports"]
    return {
        s["id"]: (p["case"], s) for p in ports if p["case"].removeprefix("carddemo-") in PORTS for s in p["survivors"]
    }


def _widths(copybook):
    text = read_source(CARDDEMO / copybook).text
    return {
        m[1]: int(m[2] or 1) for m in re.finditer(r"^\s+\d+\s+([A-Z0-9-]+)\s+PIC\s+X(?:\((\d+)\))?\s*\.", text, re.M)
    }


# values: empty, short, exact, one over, far over, and text with a character of more than one byte
def _values(width):
    base = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return ["", "A", (base * 2)[:width], (base * 2)[: width + 1], base * 3, "Q" * (width - 1) + "é"]


WIDTHS = sorted({w for _, _, w, _ in CLAIMS.values()} | {2, 3})


@pytest.mark.parametrize("width", WIDTHS)
def test_the_harness_codec_pads_and_cuts_to_the_width(width):
    for value in _values(width):
        got = ec.text_bytes(value, width)
        assert len(got) == width
        assert got == value.encode("latin-1")[:width].ljust(width, b" ")
    # a one-wider value (the mutants' fit(x, width + 1)) is the same bytes as the declared width: the claim itself
    for value in _values(width):
        assert ec.text_bytes(value.ljust(width + 1)[: width + 1], width) == ec.text_bytes(value, width)


@pytest.mark.skipif(shutil.which("javac") is None or shutil.which("java") is None, reason="no JDK")
def test_the_generated_runtime_codec_pads_and_cuts_to_the_width(tmp_path):
    pkg = tmp_path / "t"
    pkg.mkdir()
    source = COBOL_RECORDS_JAVA.replace("__PACKAGE__", "t").replace("__BIDI_LAYOUT__", "auto")
    source = source.replace("__POSITIVE__", "{ABCDEFGHI").replace("__NEGATIVE__", "}JKLMNOPQR")
    (pkg / "CobolRecords.java").write_text(source, encoding="utf-8")
    probes = [(w, v) for w in WIDTHS for v in _values(w)]
    probes += [(w, v.ljust(w + 1)[: w + 1]) for w in WIDTHS for v in _values(w)]  # the mutants' wider fit()
    calls = "\n".join(f"        run({w}, {json.dumps(v)});" for w, v in probes)
    (pkg / "Probe.java").write_text(
        "package t;\n"
        "import java.nio.charset.Charset;\n"
        "import java.nio.charset.StandardCharsets;\n"
        "public class Probe {\n"
        "    static final Charset TEXT = StandardCharsets.ISO_8859_1;\n"
        "    static void run(int width, String value) {\n"
        "        byte[] rec = new byte[width + 4];\n"
        "        java.util.Arrays.fill(rec, (byte) '#');\n"
        "        CobolRecords.putText(rec, 2, width, value, TEXT);\n"
        '        System.out.println(new String(rec, TEXT).replace(" ", "_"));\n'
        "    }\n"
        f"    public static void main(String[] a) {{\n{calls}\n    }}\n"
        "}\n",
        encoding="utf-8",
    )
    subprocess.run(  # noqa: S603
        [
            "javac",
            "-encoding",
            "UTF-8",
            "-d",
            str(tmp_path / "out"),
            str(pkg / "CobolRecords.java"),
            str(pkg / "Probe.java"),
        ],  # noqa: S607
        check=True,
        capture_output=True,
    )
    run = subprocess.run(  # noqa: S603
        ["java", "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "out"), "t.Probe"],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    got = run.stdout.splitlines()
    assert len(got) == len(probes)
    for (width, value), line in zip(probes, got, strict=True):
        field = ec.text_bytes(value, width).decode("latin-1").replace(" ", "_")
        assert line == "##" + field + "##", (width, value)  # the sentinels either side of the field are untouched


def test_every_survivor_resting_on_the_codec_is_claimed_and_still_equivalent():
    survivors = _survivors()
    resting = {
        sid for sid, (_, s) in survivors.items() if s["verdict"] == "equivalent" and CODEC_REASON.search(s["reason"])
    }
    assert set(CLAIMS) <= set(survivors), sorted(set(CLAIMS) - set(survivors))
    assert resting <= set(CLAIMS) | NOT_A_WIDTH_CLAIM, sorted(resting - set(CLAIMS) - NOT_A_WIDTH_CLAIM)
    for sid in CLAIMS:
        assert survivors[sid][1]["verdict"] == "equivalent", sid


# codec-citing survivors that cite no one field: billpay's fit() padding (762d30d747) adds trailing spaces to any
# value, and the one-wider probes above are that case at every width
NOT_A_WIDTH_CLAIM = {"762d30d747"}


@pytest.mark.skipif(not CARDDEMO.is_dir(), reason="the CardDemo corpus is not available (GITGALAXY_MAINFRAME_CORPORA)")
@pytest.mark.parametrize("sid", sorted(CLAIMS))
def test_the_width_each_survivor_cites_is_the_copybooks(sid):
    copybook, field, declared, mutant = CLAIMS[sid]
    assert _widths(copybook).get(field) == declared, (sid, copybook, field)
    if mutant is not None:
        assert mutant == declared + 1
