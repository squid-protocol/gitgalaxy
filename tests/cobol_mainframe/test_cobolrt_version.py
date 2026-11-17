"""#4718: cobolrt version stamp, compatibility checks, and fail-loudly audit."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from gitgalaxy.tools.cobol_to_java.det import program as det_prog

REPO = Path(__file__).resolve().parents[2]
RT = REPO / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "cobolrt"

DRIVER_JAVA = r"""package ggtest.cobolrt;

public final class VersionDriver {
    public static void main(String[] args) {
        if (!"0.1.0".equals(CobolRuntime.VERSION)) {
            throw new AssertionError("unexpected version: " + CobolRuntime.VERSION);
        }
        if (CobolRuntime.API_SCHEMA != 1) {
            throw new AssertionError("unexpected schema: " + CobolRuntime.API_SCHEMA);
        }
        if (!CobolRuntime.isCompatible("0.1.0")) {
            throw new AssertionError("0.1.0 must be compatible with 0.1.0");
        }
        if (CobolRuntime.isCompatible("0.2.0") || CobolRuntime.isCompatible("1.0.0")
                || CobolRuntime.isCompatible("0.1.1") || CobolRuntime.isCompatible("")) {
            throw new AssertionError("incompatible versions must return false");
        }
        CobolRuntime.requireCompatible("0.1.0");
        boolean threw = false;
        try {
            CobolRuntime.requireCompatible("0.2.0");
        } catch (IllegalStateException e) {
            threw = e.getMessage().contains("incompatible");
        }
        if (!threw) {
            throw new AssertionError("requireCompatible must fail loudly on mismatch");
        }
        System.out.println("VERSION OK");
    }
}
"""


def test_cobolrt_version_and_compatibility() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        dst = tmp / "ggtest" / "cobolrt"
        dst.mkdir(parents=True)
        src = (RT / "CobolRuntime.java").read_text(encoding="utf-8").replace("__PACKAGE__", "ggtest")
        (dst / "CobolRuntime.java").write_text(src, encoding="utf-8")
        (dst / "VersionDriver.java").write_text(DRIVER_JAVA, encoding="utf-8")
        files = [str(dst / "CobolRuntime.java"), str(dst / "VersionDriver.java")]
        comp = subprocess.run(  # noqa: S603
            ["javac", "-encoding", "UTF-8", "-d", d, *files],  # noqa: S607
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert comp.returncode == 0, comp.stderr
        run = subprocess.run(  # noqa: S603
            ["java", "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", d, "ggtest.cobolrt.VersionDriver"],  # noqa: S607
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert run.returncode == 0, run.stderr or run.stdout
        assert "VERSION OK" in run.stdout


def test_det_port_stamps_cobolrt_version(tmp_path: Path) -> None:
    cbl = tmp_path / "VER1.cbl"
    cbl.write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. VER1.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n",
        encoding="utf-8",
    )
    res = det_prog.translate(cbl, [], "package com.example.service;\npublic class Ver1Service {}\n", "com.example")
    assert 'public static final String COBOLRT_VERSION = "0.1.0";' in res.java
    assert res.stats["cobolrt_version"] == "0.1.0"


def test_cobolrt_fail_loudly_no_empty_catch_blocks() -> None:
    empty_catch = re.compile(r"catch\s*\([^)]+\)\s*\{\s*\}")
    hits: list[str] = []
    for p in sorted(RT.rglob("*.java")):
        txt = p.read_text(encoding="utf-8")
        for m in empty_catch.finditer(txt):
            line = txt[: m.start()].count("\n") + 1
            hits.append(f"{p.relative_to(RT)}:{line}")
    assert not hits, f"empty catch block(s) in cobolrt violate fail-loudly (#4718): {hits}"
