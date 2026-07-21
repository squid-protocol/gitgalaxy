import pytest
from unittest.mock import patch

from gitgalaxy.security.dependency_audit_cache import DependencyAuditCache
from gitgalaxy.recorders.sbom_recorder import SbomRecorder


@pytest.fixture
def cache(tmp_path):
    c = DependencyAuditCache(str(tmp_path / "dep_cache.db"))
    yield c
    c.close()


def test_cache_miss_then_hit_roundtrip(cache, tmp_path):
    """A recorded verdict is returned on the next lookup for the same bytes."""
    f = tmp_path / "index.js"
    f.write_text("console.log('hello');")
    h = cache.hash_file(f)

    assert cache.lookup("npm", "some-lib", "index.js", h) is None

    cache.record("npm", "some-lib", "index.js", h, "VERIFIED_SAFE", "")
    cache.commit()

    hit = cache.lookup("npm", "some-lib", "index.js", h)
    assert hit is not None
    assert hit["trust_status"] == "VERIFIED_SAFE"


def test_cache_invalidated_when_content_changes(cache, tmp_path):
    """Changing even one byte produces a different hash -> cache miss.
    This is the shadow-patch defense: modified vendored files can never
    ride a stale verdict."""
    f = tmp_path / "index.js"
    f.write_text("console.log('hello');")
    h1 = cache.hash_file(f)
    cache.record("npm", "some-lib", "index.js", h1, "VERIFIED_SAFE", "")
    cache.commit()

    f.write_text("console.log('hello');/*payload*/")
    h2 = cache.hash_file(f)

    assert h1 != h2
    assert cache.lookup("npm", "some-lib", "index.js", h2) is None


def test_hash_covers_full_file_not_prefix(cache, tmp_path):
    """A change PAST the 8KB scan-depth mark must still change the hash —
    change detection is full-content even while scan depth is limited."""
    f = tmp_path / "big.js"
    base = "a" * 10000
    f.write_text(base)
    h1 = cache.hash_file(f)

    f.write_text(base[:-1] + "b")  # mutate the final byte, past 8KB
    h2 = cache.hash_file(f)

    assert h1 != h2


@patch("gitgalaxy.recorders.sbom_recorder.SecurityLens")
@patch("gitgalaxy.recorders.sbom_recorder.LanguageDetector")
def test_sbom_second_run_uses_cache(mock_det, mock_sec, tmp_path):
    """Run 1 scans fresh and populates the cache; run 2 reuses it without
    re-invoking the scanner, and both runs disclose coverage."""
    import json

    project = tmp_path / "proj"
    project.mkdir()
    (project / "package.json").write_text('{"dependencies": {"lib-a": "1.0"}}')
    lib = project / "node_modules" / "lib-a"
    lib.mkdir(parents=True)
    (lib / "index.js").write_text("console.log('x');")

    mock_sec.return_value.scan_content.return_value = {"counts": {"entropy": 0.0}}
    mock_det.return_value.inspect.return_value = {"anomaly_flags": []}

    cache = DependencyAuditCache(str(tmp_path / "cache.db"))
    recorder = SbomRecorder(dependency_cache=cache)
    meta = {"target_directory": str(project)}

    out1 = tmp_path / "bom1.json"
    recorder.generate_report([], {}, meta, str(out1))
    first_scan_calls = mock_sec.return_value.scan_content.call_count
    assert first_scan_calls == 1

    out2 = tmp_path / "bom2.json"
    recorder.generate_report([], {}, meta, str(out2))
    assert mock_sec.return_value.scan_content.call_count == first_scan_calls, (
        "Second run re-scanned an unchanged file instead of using the cache!"
    )

    bom = json.loads(out2.read_text())
    props = {p["name"]: p["value"] for p in bom["components"][0]["properties"]}
    assert "1 cached" in props["gitgalaxy:audit_coverage"]
    cache.close()


@patch("gitgalaxy.recorders.sbom_recorder.SecurityLens")
@patch("gitgalaxy.recorders.sbom_recorder.LanguageDetector")
def test_sbom_budget_defers_and_discloses(mock_det, mock_sec, tmp_path):
    """With a fresh-scan budget of 1 and two files, one is deferred, the
    status downgrades to PARTIALLY_VERIFIED, and coverage says so."""
    import json

    project = tmp_path / "proj"
    project.mkdir()
    (project / "package.json").write_text('{"dependencies": {"lib-a": "1.0"}}')
    lib = project / "node_modules" / "lib-a"
    lib.mkdir(parents=True)
    (lib / "a.js").write_text("1")
    (lib / "b.js").write_text("2")

    mock_sec.return_value.scan_content.return_value = {"counts": {"entropy": 0.0}}
    mock_det.return_value.inspect.return_value = {"anomaly_flags": []}

    cache = DependencyAuditCache(str(tmp_path / "cache.db"))
    recorder = SbomRecorder(dependency_cache=cache, fresh_scan_budget=1)
    out = tmp_path / "bom.json"
    recorder.generate_report([], {}, {"target_directory": str(project)}, str(out))

    bom = json.loads(out.read_text())
    props = {p["name"]: p["value"] for p in bom["components"][0]["properties"]}
    assert props["gitgalaxy:trust_status"] == "PARTIALLY_VERIFIED"
    assert "deferred" in props["gitgalaxy:audit_coverage"]
    cache.close()


@patch("gitgalaxy.recorders.sbom_recorder.SecurityLens")
@patch("gitgalaxy.recorders.sbom_recorder.LanguageDetector")
def test_sbom_no_cache_preserves_legacy_behavior(mock_det, mock_sec, tmp_path):
    """With no cache configured, sampling is capped as before and the
    coverage property says so explicitly."""
    import json

    project = tmp_path / "proj"
    project.mkdir()
    (project / "package.json").write_text('{"dependencies": {"lib-a": "1.0"}}')
    lib = project / "node_modules" / "lib-a"
    lib.mkdir(parents=True)
    for i in range(7):
        (lib / f"f{i}.js").write_text(str(i))

    mock_sec.return_value.scan_content.return_value = {"counts": {"entropy": 0.0}}
    mock_det.return_value.inspect.return_value = {"anomaly_flags": []}

    recorder = SbomRecorder()  # no cache
    out = tmp_path / "bom.json"
    recorder.generate_report([], {}, {"target_directory": str(project)}, str(out))

    assert mock_sec.return_value.scan_content.call_count == 5  # per-dir cap

    bom = json.loads(out.read_text())
    props = {p["name"]: p["value"] for p in bom["components"][0]["properties"]}
    assert "5/7" in props["gitgalaxy:audit_coverage"]
    assert "no dependency cache configured" in props["gitgalaxy:audit_coverage"]