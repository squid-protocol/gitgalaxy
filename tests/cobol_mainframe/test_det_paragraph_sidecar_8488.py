"""The paragraph -> method sidecar `<Service>.paragraph_methods.json` is written beside every det service (#8488).

The class: every place that persists a det service (`port_runner._store` overlay and attempt copy) writes the
translator's own `stats["paragraph_methods"]` next to it, in paragraph order, in both styles; an empty map writes none.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_java import port_runner
from gitgalaxy.tools.cobol_to_java.det import program as P

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from construct_map import read_provenance

SRC = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. DEMO01.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n       01 WS-X PIC 9(4) VALUE 0.\n       PROCEDURE DIVISION.\n"
    "       0000-MAIN.\n           PERFORM 1100-INIT\n           PERFORM 1200-SETUP\n           GOBACK.\n"
    "       1100-INIT.\n           ADD 1 TO WS-X.\n"
    "       1200-SETUP.\n           ADD 2 TO WS-X.\n"
)


@pytest.mark.parametrize("style", ["structured", "dispatch"])
def test_store_writes_the_sidecar_beside_overlay_and_attempt(tmp_path: Path, style: str) -> None:
    cbl = tmp_path / "DEMO01.cbl"
    cbl.write_text(SRC)
    res = P.translate(cbl, [], "public class Demo01Service {}", "com.example", [], None, style, True, True)
    pmap = res.stats["paragraph_methods"]
    assert pmap
    ticket = {"program": {"key": "DEMO01"}, "target": {"service": "Demo01Service"}}
    dest = port_runner._store(tmp_path, ticket, res.java, 1, None, pmap)
    assert read_provenance(dest) == pmap
    assert list(read_provenance(dest)) == list(pmap)  # paragraph order kept
    attempt = next((tmp_path / port_runner.PORTS / "DEMO01" / "attempts").glob("001_*.java"))
    assert read_provenance(attempt) == pmap
    assert json.loads(dest.with_name("Demo01Service.paragraph_methods.json").read_text()) == pmap


def test_an_empty_map_writes_no_sidecar(tmp_path: Path) -> None:
    java = tmp_path / "S.java"
    java.write_text("class S {}")
    assert port_runner.write_paragraph_methods(java, {}) is None
    assert port_runner.write_paragraph_methods(java, None) is None
    assert not list(tmp_path.glob("*.json"))
    ticket = {"program": {"key": "K"}, "target": {"service": "S"}}
    dest = port_runner._store(tmp_path, ticket, "class S {}", 1)
    assert not list(dest.parent.glob("*.json"))
