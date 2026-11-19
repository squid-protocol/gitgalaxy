import json

from gitgalaxy.recorders.sarif_recorder import SarifRecorder


def test_sarif_emits_no_ml_threat_results(tmp_path):
    """#8430: the XGBoost classifier is removed, so legacy ML fields on a node produce no SARIF result and no GG-ML rule."""
    recorder = SarifRecorder()
    output_path = tmp_path / "out.sarif.json"

    parsed_files = [
        {
            "path": "src/benign.py",
            "telemetry": {"domain_context": {"purpose": "Routes traffic"}},
        }
    ]

    recorder.generate_report(
        parsed_files=parsed_files,
        summary={},
        session_meta={},
        output_path=str(output_path),
    )

    with open(output_path, encoding="utf-8") as f:
        payload = json.load(f)

    run = payload["runs"][0]
    assert run["results"] == []
    assert not [r for r in run["tool"]["driver"]["rules"] if r["id"].startswith("GG-ML-")]
