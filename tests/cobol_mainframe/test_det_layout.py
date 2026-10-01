"""det-port layout (gitgalaxy/tools/cobol_to_java/det/layout.py): every WORKING-STORAGE record of the programs of
the proven equivalence cases, its size and its initial bytes, against GnuCOBOL's own (-std=ibm -fsign=EBCDIC, the
harness's oracle). The program's PROCEDURE DIVISION is replaced by calls that print each record's bytes as hex."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/tools"))
sys.path.insert(0, str(ROOT))

from gitgalaxy.tools.cobol_to_java.det import layout as L  # noqa: E402

CASES = ROOT / "tests/equivalence"
CICS_COPY = CASES / "cics"
DUMP_C = r"""
#include <stdio.h>
int GGDUMP(unsigned char *p, int n) {
    for (int i = 0; i < n; i++) printf("%02X", p[i]);
    printf("\n");
    return 0;
}
"""


def _cases() -> list[str]:
    out = []
    for d in sorted(CASES.glob("carddemo-*")):
        if (d / "port").is_dir() and (d / "case.json").is_file():
            out.append(d.name)
    return out


def _corpus() -> Path:
    base = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ""))
    return base / "aws-mainframe-modernization-carddemo"


def _dirs(case: dict, corpus: Path) -> list[Path]:
    return [corpus / d for d in case.get("copy_dirs", ["app/cpy"])] + [CICS_COPY]


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"), reason="needs Docker")
@pytest.mark.parametrize("name", _cases())
def test_the_initial_image_is_gnucobols(name, tmp_path):
    case = json.loads((CASES / name / "case.json").read_text())
    corpus = _corpus()
    program = corpus / case["program_source"]
    records = [r for r in L.records(program, _dirs(case, corpus)) if r.section == "WORKING-STORAGE"]
    named = [r for r in records if r.name != "FILLER"]
    # the program up to its PROCEDURE DIVISION, then one CALL per named record
    text = program.read_text(encoding="latin-1")
    if case.get("kind") == "cics":  # its LINKAGE names EIBCALEN: the harness's translation adds the EIB block
        import equivalence_cics as ec

        text = ec.translate(text)[0]
    head = re.split(r"(?im)^.{6} +PROCEDURE\s+DIVISION\b", text)[0]
    calls = "".join(f"           CALL 'GGDUMP' USING {r.name}\n               BY VALUE LENGTH OF {r.name}\n"
                    for r in named)  # fmt: skip
    (tmp_path / "P.cbl").write_text(head + "       PROCEDURE DIVISION.\n" + calls + "           GOBACK.\n",
                                    encoding="latin-1")  # fmt: skip
    (tmp_path / "ggdump.c").write_text(DUMP_C)
    for d in _dirs(case, corpus):
        for f in d.glob("*"):
            if f.is_file():
                shutil.copy(f, tmp_path / f.name)
                shutil.copy(f, tmp_path / (f.stem.upper() + ".cpy"))
    proc = subprocess.run(["docker", "run", "--rm", "-v", f"{tmp_path}:/w", "-w", "/w", "gitgalaxy-gnucobol:3",  # noqa: S603, S607
                           "bash", "-c", "cobc -x -std=ibm -fsign=EBCDIC -I . -o p P.cbl ggdump.c && ./p"],
                          capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 0, proc.stderr[-3000:]
    got = proc.stdout.split()
    assert len(got) == len(named)
    bad = []
    for r, hexed in zip(named, got):
        mine = L.image(r).hex().upper()
        if any(i.depending for i in r.walk()):  # OCCURS DEPENDING ON: LENGTH OF is the current length
            mine = mine[: len(hexed)]
        for it in L.runtime_init(r):  # set at run time by the runtime's editing: proven end to end, not here
            for k in range(max(1, it.occurs)):
                a = (it.offset + k * it.size) * 2
                mine = mine[:a] + hexed[a : a + it.size * 2] + mine[a + it.size * 2 :]
        if mine != hexed:
            first = next(i for i in range(min(len(mine), len(hexed))) if mine[i] != hexed[i]) // 2 \
                if len(mine) == len(hexed) else -1  # fmt: skip
            item = next((i.name for i in r.walk() if i.offset <= first < i.offset + max(i.size, 1)
                         and not i.children), "?") if first >= 0 else "size"  # fmt: skip
            bad.append(f"{r.name}: size {len(mine) // 2} vs {len(hexed) // 2}, first diff at byte {first} ({item}): "
                       f"mine {mine[max(0, first * 2 - 4):first * 2 + 12]} gnucobol {hexed[max(0, first * 2 - 4):first * 2 + 12]}")  # fmt: skip
    assert not bad, "\n".join(bad)
