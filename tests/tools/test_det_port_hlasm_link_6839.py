"""#6839: det_port translates a case's LINK target onto the forge's service, and an HLASM target (the forge reads COBOL
only, so it made none) onto the translator's own stub, as the case's main HLASM program already was (#5859)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import det_port  # noqa: E402

from gitgalaxy.tools.cobol_to_java.det import hlasm  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def _service_dir(tmp_path: Path) -> Path:
    d = tmp_path / "src/main/java" / det_port.PKG_DIR / "service"
    d.mkdir(parents=True)
    return d


def test_a_forge_service_is_the_stub(tmp_path):
    (_service_dir(tmp_path) / "Zecs001Service.java").write_text("// the forge's ZECS001 service\n", encoding="utf-8")
    assert det_port._service_stub(tmp_path, "ZECS001", "Source/ZECS001.cbl") == "// the forge's ZECS001 service\n"


def test_an_hlasm_program_the_forge_made_no_service_for_gets_the_translators_stub(tmp_path):
    _service_dir(tmp_path)
    stub = det_port._service_stub(tmp_path, "ZECS002", "Source/ZECS002.asm")
    assert stub == hlasm.service_stub("ZECS002", det_port.PKG)
    assert "public class Zecs002Service" in stub and "public void runTask(CicsTask task)" in stub


def test_the_zecs001_case_links_the_hlasm_zecs002():
    case = json.loads((REPO / "tests/equivalence/zecs-zecs001/case.json").read_text(encoding="utf-8"))
    assert {"program": "ZECS002", "program_source": "Source/ZECS002.asm"} in det_port._extra_programs(case)
