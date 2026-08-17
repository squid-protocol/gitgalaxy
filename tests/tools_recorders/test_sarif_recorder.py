import json

from gitgalaxy.recorders.sarif_recorder import SarifRecorder


def test_sarif_ml_threat_confidence_reads_the_real_producer_key(tmp_path):
    """
    Regression test for #364: sarif_recorder.py was the one consumer that
    matched the OLD (wrong) producer key, "AI Threat Confidence" -- meaning
    it was the one place that quietly worked before the fix and needed to be
    moved onto "AI Threat Score" alongside every other recorder, not left as
    the odd one out.
    """
    recorder = SarifRecorder()
    output_path = tmp_path / "out.sarif.json"

    parsed_files = [
        {
            "path": "src/malicious.py",
            "is_ml_threat": True,
            "telemetry": {
                "domain_context": {
                    "AI Threat Class": "Botnet / DDoS",
                    "AI Threat Score": "97.3%",
                }
            },
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

    results = payload["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["properties"]["precision"] == "97.3%"
    assert "97.3%" in results[0]["message"]["text"]
