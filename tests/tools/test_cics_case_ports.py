"""cics_case_ports: det overlays of a crucible case's programs in port_runner's layout, plus summary.json."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_case_ports as ccp
import crucible_case as ccase

STUB = """package com.x.service;

import com.x.cics.CicsTask;

public class {cls}Service {{

    public void runTask(CicsTask task) {{
    }}
}}
"""


def test_project_in_names_the_missing_forge_run(tmp_path):
    with pytest.raises(SystemExit, match="forge-compile"):
        ccp.project_in(tmp_path, "gt-x")
    (tmp_path / "gt-x" / "forge" / "java_h2").mkdir(parents=True)
    (tmp_path / "gt-x" / "forge" / "java_h2" / "pom.xml").write_text("<project/>")
    assert ccp.project_in(tmp_path, "gt-x") == tmp_path / "gt-x" / "forge" / "java_h2"


def test_forge_needs_work(tmp_path):
    (tmp_path / "case.json").write_text(json.dumps({"id": "gt-x"}))
    with pytest.raises(SystemExit, match="--forge needs --work"):
        ccp.main([str(tmp_path), "--project", str(tmp_path), "--forge", "--ports", str(tmp_path / "p")])


def test_overlays_and_summary(tmp_path, capsys):
    pytest.importorskip("tree_sitter_language_pack")
    crucible = tmp_path / "cc"
    crucible.mkdir()
    (crucible / "SPEC.md").write_text("spec")
    gen = tmp_path / "gen.py"
    assert ccase.main(["new", "ghost-tasks/gt-demo", "--programs", "GTDEMO,GTDEM2", "--transids", "GT91",
                       "--crucible", str(crucible), "--gen", str(gen)]) == 0  # fmt: skip
    subprocess.run([sys.executable, str(gen), str(crucible / "cases" / "ghost-tasks" / "gt-demo")], check=True)  # noqa: S603
    project = tmp_path / "proj"
    svc = project / "src" / "main" / "java" / "com" / "x" / "service"
    svc.mkdir(parents=True)
    (project / "pom.xml").write_text("<project/>")
    for cls in ("Gtdemo", "Gtdem2"):
        (svc / f"{cls}Service.java").write_text(STUB.format(cls=cls))
    ports = tmp_path / "ports"
    case_dir = crucible / "cases" / "ghost-tasks" / "gt-demo"
    assert ccp.main([str(case_dir), "--project", str(project), "--ports", str(ports)]) == 0
    summary = json.loads((ports / "summary.json").read_text())
    assert summary == {"GTDEMO": {"statements": 1, "translated": 1, "holes": []},
                       "GTDEM2": {"statements": 1, "translated": 1, "holes": []}}  # fmt: skip
    port = (ports / "GTDEMO" / "overlay" / "service" / "GtdemoService.java").read_text()
    assert "package com.x.service;" in port and "gitgalaxy-det-port" in port
    assert (ports / "GTDEMO" / "overlay" / "cobolrt" / "Cobol.java").is_file()
    assert "--sides cobol-stub java-ported" in capsys.readouterr().out
