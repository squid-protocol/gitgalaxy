"""#2986: the ML threat layer run against a REAL (stand-in) XGBoost model, not a mock.

No production model ships, so every other ML test patches the classifier. This leg trains a tiny
5-class model on synthetic rows, saves it, and loads it through `SecurityAuditor`, so the real
`load_model` -> `feature_names_in_` -> `reindex` -> `predict_proba` -> threat-mapping -> recorder
chain runs wherever numpy, pandas and xgboost are installed. It says nothing about detection
quality: the model separates `structural_mass` bands, not malware.
"""

import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("pandas")
xgb = pytest.importorskip("xgboost")
# xgboost.XGBClassifier (what SecurityAuditor loads) raises ImportError without scikit-learn; the `full`
# extra installs it (pinned by test_ml_boundary_2986.py), so this skips only on a partial install.
pytest.importorskip("sklearn", reason="XGBClassifier needs scikit-learn (part of the `full` extra)")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ml_boundary_2986 import _artifacts, _recorded_columns  # noqa: E402

from gitgalaxy.security.security_auditor import SecurityAuditor  # noqa: E402

# structural_mass band -> class (0.1 -> Safe, 0.3 -> Botnet, 0.5 -> Trojan, 0.7 -> Dropper, 0.9 -> Infector)
BAND_CENTRES = (0.1, 0.3, 0.5, 0.7, 0.9)


@pytest.fixture(scope="module")
def model_path(tmp_path_factory):
    rng = np.random.default_rng(2986)
    x = np.concatenate([rng.normal(c, 0.02, 60) for c in BAND_CENTRES])
    y = np.repeat(np.arange(5), 60)
    # "ghost_feature" is not produced by the auditor: it must reindex to NaN, not crash.
    frame = {"structural_mass": x, "ghost_feature": np.zeros_like(x)}
    import pandas as pd

    model = xgb.XGBClassifier(n_estimators=30, max_depth=3, learning_rate=0.5, n_jobs=1, random_state=0)
    model.fit(pd.DataFrame(frame), y)
    path = tmp_path_factory.mktemp("model_2986") / "stand_in_model.json"
    model.save_model(str(path))
    return path


def _scored(model_path, mass, lang="python", **kwargs):
    auditor = SecurityAuditor(model_path=str(model_path))
    artifacts = _artifacts()
    artifacts[0]["file_impact"] = mass
    artifacts[0]["lang_id"] = lang
    return auditor, auditor.audit_repository(artifacts, **kwargs)


def test_real_model_loads_and_scores_each_class(model_path):
    for klass, centre in enumerate(BAND_CENTRES):
        auditor, audited = _scored(model_path, centre)
        assert auditor.model is not None
        assert list(auditor.feature_names) == ["structural_mass", "ghost_feature"]
        assert auditor.inference_ran is True
        ctx = audited[0]["telemetry"]["domain_context"]
        if klass == 0:
            assert audited[0]["is_ml_threat"] is False
            assert "AI Threat Class" not in ctx
        else:
            assert audited[0]["is_ml_threat"] is True
            assert ctx["AI Threat Class"] == SecurityAuditor.CLASS_NAMES[klass]
            assert float(ctx["AI Threat Score"].rstrip("%")) >= auditor.ai_threshold


def test_threshold_gates_a_real_prediction(model_path):
    auditor = SecurityAuditor(model_path=str(model_path))
    auditor.ai_threshold = 101.0
    artifacts = _artifacts()
    artifacts[0]["file_impact"] = 0.9
    audited = auditor.audit_repository(artifacts)
    assert auditor.inference_ran is True
    assert audited[0]["is_ml_threat"] is False


@pytest.mark.parametrize("lang", ["markdown", "json", "perl", "assembly"])
def test_static_asset_shield_overrides_a_real_threat_class(model_path, lang):
    _, audited = _scored(model_path, 0.9, lang=lang)
    assert audited[0]["is_ml_threat"] is False


def test_shadow_patch_forces_trojan_over_a_safe_prediction(model_path):
    _, audited = _scored(model_path, 0.6, is_shadow_patch=True)
    ctx = audited[0]["telemetry"]["domain_context"]
    assert ctx["AI Threat Class"] == SecurityAuditor.CLASS_NAMES[2]
    assert ctx["AI Threat Score"] == "100.0%"


def test_scored_values_reach_the_db_columns(model_path, tmp_path):
    auditor, audited = _scored(model_path, 0.9)
    row = _recorded_columns(tmp_path, audited, auditor.inference_ran)
    assert None not in row
    assert row[0] == SecurityAuditor.CLASS_NAMES[4]
    assert row[3] == 1


def test_corrupt_model_file_leaves_the_layer_unexercised(tmp_path):
    bad = tmp_path / "corrupt.json"
    bad.write_text("{not a model", encoding="utf-8")
    auditor = SecurityAuditor(model_path=str(bad))
    audited = auditor.audit_repository(_artifacts())
    assert auditor.model is None
    assert auditor.inference_ran is False
    assert _recorded_columns(tmp_path, audited, auditor.inference_ran) == (None, None, None, None)
