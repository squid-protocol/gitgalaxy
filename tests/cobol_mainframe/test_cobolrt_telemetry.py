"""Tests for cobolrt RuleTelemetry (#4713, #4716) and cobolrt_exit_report."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cobolrt_exit_report  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
RT = REPO / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "cobolrt"

DRIVER_JAVA = r"""package ggtest.cobolrt;

import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;

public final class TelemetryDriver {
    public static void main(String[] args) {
        if (RuleTelemetry.isEnabled()) {
            throw new AssertionError("telemetry must be off by default");
        }
        Charset cs = Cobol.recordCharset(StandardCharsets.ISO_8859_1);
        Storage sPack = new Storage(4);
        Field fPack = Field.packed(sPack, 0, 7, 2, true);
        Cobol.store(fPack, new BigDecimal("12.34"), false, cs);
        if (!RuleTelemetry.snapshot().isEmpty()) {
            throw new AssertionError("snapshot must stay empty while telemetry is off");
        }

        // Clean run with telemetry on: no quirks fire
        RuleTelemetry.reset();
        boolean prev = RuleTelemetry.swapEnabled(true);
        try {
            Cobol.store(fPack, new BigDecimal("10.00"), false, cs);
            BigDecimal v = Cobol.num(fPack, cs);
            Cobol.store(fPack, Cobol.add(v, new BigDecimal("5.25")), false, cs);
            System.out.println("CLEAN=" + RuleTelemetry.toJson());

            // Now trigger quirks: overflow truncation, divide-by-zero NaN, non-digit zoned arithmetic
            RuleTelemetry.reset();
            Storage sSmall = new Storage(2);
            Field fSmall = Field.packed(sSmall, 0, 3, 0, true);
            Cobol.store(fSmall, new BigDecimal("1234"), false, cs);  // truncates -> RT-NUM-TRUNC-BINARY
            Cobol.divide(new BigDecimal("10"), BigDecimal.ZERO);     // NaN -> RT-CBL-ZERO-DIVISOR-NAN
            Storage sZoned = new Storage(4);
            Field fZoned = Field.zoned(sZoned, 0, 4, 0, false, false, false);
            Cobol.moveFigurative(Figurative.SPACES, fZoned, cs);
            Cobol.num(fZoned, cs);                                   // dirty -> RT-NUM-NONDIGIT-GET-SIGN/ARITHMETIC
            System.out.println("QUIRKS=" + RuleTelemetry.toJson());
        } finally {
            RuleTelemetry.swapEnabled(prev);
            RuleTelemetry.reset();
        }
    }
}
"""


def _run_driver() -> tuple[dict[str, int], dict[str, int]]:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        dst = tmp / "ggtest" / "cobolrt"
        for p in list(RT.glob("*.java")) + list((RT / "standalone").glob("*.java")):
            rel = p.relative_to(RT)
            out = dst / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(p.read_text(encoding="utf-8").replace("__PACKAGE__", "ggtest"), encoding="utf-8")
        (dst / "TelemetryDriver.java").write_text(DRIVER_JAVA, encoding="utf-8")
        files = [str(p) for p in dst.rglob("*.java")]
        comp = subprocess.run(["javac", "-d", d, *files], capture_output=True, text=True)  # noqa: S603, S607
        if comp.returncode != 0:
            raise AssertionError(f"javac failed:\n{comp.stderr}")
        run = subprocess.run(  # noqa: S603
            ["java", "-cp", d, "ggtest.cobolrt.TelemetryDriver"],  # noqa: S607
            capture_output=True,
            text=True,
        )
        if run.returncode != 0:
            raise AssertionError(f"java failed:\n{run.stderr}\n{run.stdout}")
        lines = dict(line.split("=", 1) for line in run.stdout.strip().splitlines() if "=" in line)
        return json.loads(lines["CLEAN"]), json.loads(lines["QUIRKS"])


def test_rule_telemetry_and_exit_report() -> None:
    clean_counts, quirk_counts = _run_driver()

    if "RT-NUM-PACKED-SIGN" not in clean_counts:
        raise AssertionError(f"expected RT-NUM-PACKED-SIGN in clean run: {clean_counts}")
    for q in ("RT-NUM-TRUNC-BINARY", "RT-CBL-ZERO-DIVISOR-NAN", "RT-NUM-NONDIGIT-ARITHMETIC"):
        if q in clean_counts:
            raise AssertionError(f"quirk {q} should not fire in clean run: {clean_counts}")

    clean_report = cobolrt_exit_report.build_report(clean_counts)
    assert clean_report["evidence"]["total_rules_exercised"] >= 1
    safe_ids = {item["id"] for item in clean_report["exit_route"]["safe_to_simplify"]}
    assert "RT-NUM-TRUNC-BINARY" in safe_ids
    assert "RT-CBL-ZERO-DIVISOR-NAN" in safe_ids
    md = cobolrt_exit_report.render_markdown(clean_report)
    assert "Safe Plain-Java Simplifications (#4716" in md

    for expected in (
        "RT-NUM-TRUNC-BINARY",
        "RT-CBL-ZERO-DIVISOR-NAN",
        "RT-NUM-NONDIGIT-GET-SIGN",
        "RT-NUM-NONDIGIT-ARITHMETIC",
    ):
        if expected not in quirk_counts:
            raise AssertionError(f"expected {expected} in quirk run: {quirk_counts}")

    quirk_report = cobolrt_exit_report.build_report(quirk_counts)
    kept_ids = {item["id"] for item in quirk_report["exit_route"]["keep_runtime"]}
    assert {"RT-NUM-TRUNC-BINARY", "RT-CBL-ZERO-DIVISOR-NAN", "RT-NUM-NONDIGIT-ARITHMETIC"} <= kept_ids
