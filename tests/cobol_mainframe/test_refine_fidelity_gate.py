"""Tests for det.refine structural fidelity guard (#7532, #8488)."""

from __future__ import annotations

from pathlib import Path

from gitgalaxy.tools.cobol_to_java.det import refine as R


def _sample_service(tmp_path: Path) -> Path:
    svc = tmp_path / "DemoService.java"
    svc.write_text(
        "public class DemoService {\n"
        "    /** 1000-CHECK. */\n"
        "    private void check() {\n"
        "        if (a > 0) {\n"
        "            if (b > 0) {\n"
        "                x = 1;\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    return svc


def test_structural_fidelity_guard_rejects_dropped_javadoc_and_branches(tmp_path: Path) -> None:
    svc = _sample_service(tmp_path)
    prove_calls = 0

    def prove() -> tuple[bool, str]:
        nonlocal prove_calls
        prove_calls += 1
        return True, ""

    answers = iter(
        [
            "```java\nprivate void check() {\n    x = 1;\n}\n```",
            "```java\n/** 1000-CHECK. */\nprivate void check() {\n    if (a > 0 && b > 0) {\n        if (true) {\n            x = 1;\n        }\n    }\n}\n```",
        ]
    )

    prompts: list[str] = []

    def ask(_sys: str, user: str, _pdir: Path) -> str:
        prompts.append(user)
        return next(answers)

    rec = R.refine(
        svc,
        ask,
        prove,
        tmp_path / "work",
        retries=1,
        fidelity_check=R.structural_fidelity_guard(min_fidelity=0.55),
    )
    assert rec["steps"][0]["verdict"] == "kept"
    assert rec["steps"][0]["attempts"] == 2
    assert prove_calls == 1
    assert "Structural fidelity check failed" in prompts[1]


def test_structural_fidelity_guard_reverts_when_below_cobol_threshold(tmp_path: Path) -> None:
    svc = _sample_service(tmp_path)
    cbl = tmp_path / "DEMO.cbl"
    cbl.write_text(
        "       PROCEDURE DIVISION.\n"
        "       1000-CHECK.\n"
        "           IF WS-A > 0\n"
        "               IF WS-B > 0\n"
        "                   IF WS-C > 0\n"
        "                       MOVE 1 TO WS-X\n"
        "                   END-IF\n"
        "               END-IF\n"
        "           END-IF.\n",
        encoding="utf-8",
    )

    def ask(_sys: str, _user: str, _pdir: Path) -> str:
        return "```java\n/** 1000-CHECK. */\nprivate void check() {\n    x = 1;\n}\n```"

    rec = R.refine(
        svc,
        ask,
        lambda: (True, ""),
        tmp_path / "work",
        retries=0,
        fidelity_check=R.structural_fidelity_guard(cbl, min_fidelity=0.90),
    )
    assert rec["steps"][0]["verdict"] == "reverted"
    assert "if (a > 0)" in svc.read_text(encoding="utf-8")


def test_port_runner_fidelity_stamp_reports_score_and_outliers(tmp_path: Path) -> None:
    from gitgalaxy.tools.cobol_to_java import port_runner as PR

    src_root = tmp_path / "cobol"
    src_root.mkdir()
    (src_root / "DEMO.cbl").write_text(
        "       PROCEDURE DIVISION.\n"
        "       1000-CHECK.\n"
        "           IF WS-A > 0\n"
        "               IF WS-B > 0\n"
        "                   MOVE 1 TO WS-X\n"
        "               END-IF\n"
        "           END-IF.\n",
        encoding="utf-8",
    )
    overlay = tmp_path / "overlay"
    (overlay / "service").mkdir(parents=True)
    (overlay / "service" / "DemoService.java").write_text(
        "public class DemoService {\n    /** 1000-CHECK. */\n    private void check() {\n        x = 1;\n    }\n}\n",
        encoding="utf-8",
    )
    ticket = {"source": "DEMO.cbl", "target": {"service": "DemoService"}}
    stamp = PR.fidelity_stamp(ticket, overlay, src_root)
    assert stamp is not None
    assert stamp["cobol_paragraphs"] == 1
    assert stamp["paired"] == 1
    assert len(stamp["outliers"]) == 1
    assert stamp["outliers"][0]["para"] == "1000-CHECK"
