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
    
def test_candidate_files_entry_points_first(tmp_path):
    """Ordering contract: entry-point stems before others, shallow before
    deep, alphabetical last — regardless of os.walk's natural order."""
    pkg = tmp_path / "pkg"
    deep = pkg / "lib" / "internal"
    deep.mkdir(parents=True)
    (pkg / "aaa_helper.js").write_text("1")   # sorts first alphabetically
    (pkg / "index.js").write_text("2")        # entry point — must win anyway
    (deep / "main.js").write_text("3")        # entry point, but deeper
    (deep / "zz_util.js").write_text("4")

    recorder = SbomRecorder()
    ordered = [p.name for p in recorder._iter_candidate_files(pkg)]

    assert ordered == ["index.js", "main.js", "aaa_helper.js", "zz_util.js"], (
        f"Priority ordering violated: {ordered}"
    )


@patch("gitgalaxy.recorders.sbom_recorder.SecurityLens")
@patch("gitgalaxy.recorders.sbom_recorder.LanguageDetector")
def test_budget_spends_on_entry_point_not_alphabetical_first(mock_det, mock_sec, tmp_path):
    """
    The attack scenario this PR closes: with budget=1, the fresh scan must go
    to index.js even though 'aaa_payload.js' sorts earlier alphabetically —
    a late-named payload can no longer push the entry point out of the
    first run's budget (and vice versa: naming a payload 'zzz_*' no longer
    guarantees deferral past entry-point files… it just can't jump the queue).
    """
    project = tmp_path / "proj"
    project.mkdir()
    (project / "package.json").write_text('{"dependencies": {"lib-a": "1.0"}}')
    lib = project / "node_modules" / "lib-a"
    lib.mkdir(parents=True)
    (lib / "aaa_payload.js").write_text("evil?")
    (lib / "index.js").write_text("legit")

    mock_sec.return_value.scan_content.return_value = {"counts": {"entropy": 0.0}}
    mock_det.return_value.inspect.return_value = {"anomaly_flags": []}

    cache = DependencyAuditCache(str(tmp_path / "cache.db"))
    recorder = SbomRecorder(dependency_cache=cache, fresh_scan_budget=1)
    recorder.generate_report([], {}, {"target_directory": str(project)}, str(tmp_path / "bom.json"))

    scanned_paths = [str(c.args[0]) for c in mock_det.return_value.inspect.call_args_list]
    assert len(scanned_paths) == 1
    assert scanned_paths[0].endswith("index.js"), (
        f"Budget was spent on {scanned_paths[0]} instead of the entry point!"
    )
    cache.close()

@patch("gitgalaxy.recorders.sbom_recorder.SecurityLens")
@patch("gitgalaxy.recorders.sbom_recorder.LanguageDetector")
def test_sbom_discovers_nested_monorepo_manifests(mock_det, mock_sec, tmp_path):
    """Regression: manifests below the repo root (monorepo layout) must be
    discovered via the pipeline census, and their packages located relative
    to the manifest's own directory — not the repo root."""
    import json

    project = tmp_path / "mono"
    frontend = project / "packages" / "frontend"
    frontend.mkdir(parents=True)
    (frontend / "package.json").write_text('{"dependencies": {"lib-a": "1.0"}}')
    lib = frontend / "node_modules" / "lib-a"
    lib.mkdir(parents=True)
    (lib / "index.js").write_text("ok")

    mock_sec.return_value.scan_content.return_value = {"counts": {"entropy": 0.0}}
    mock_det.return_value.inspect.return_value = {"anomaly_flags": []}

    # This is what galaxyscope's Phase 10 now hands SbomRecorder directly;
    # generate_report no longer derives manifest locations from parsed_files.
    manifest_paths = [str(frontend / "package.json")]

    recorder = SbomRecorder()
    out = tmp_path / "bom.json"
    recorder.generate_report(
        [], {}, {"target_directory": str(project)}, str(out),
        manifest_paths=manifest_paths,
    )

    bom = json.loads(out.read_text())
    assert len(bom["components"]) == 1
    props = {p["name"]: p["value"] for p in bom["components"][0]["properties"]}
    assert props["gitgalaxy:trust_status"] != "UNVERIFIED_MISSING_ON_DISK", (
        "Package was located via repo root instead of the manifest's own directory!"
    )

# ADD these two in its place:
def test_sbom_root_fallback_does_not_recurse_into_vendored_dirs(tmp_path):
    """The no-manifest_paths fallback only checks the repo root, so a
    package.json inside node_modules is never found by it. This is a side
    effect of the fallback being root-only, not a deliberate vendor-dir
    filter — guards against someone 'improving' the fallback to recurse
    (e.g. via os.walk or Path.rglob) without also re-adding an exclusion."""
    import json

    project = tmp_path / "proj"
    dep = project / "node_modules" / "some-lib"
    dep.mkdir(parents=True)
    (dep / "package.json").write_text('{"dependencies": {"evil-transitive": "6.6.6"}}')

    recorder = SbomRecorder()
    out = tmp_path / "bom.json"
    recorder.generate_report([], {}, {"target_directory": str(project)}, str(out))

    bom = json.loads(out.read_text())
    assert bom["components"] == [], (
        "Root-only fallback found a manifest outside the repo root!"
    )


@patch("gitgalaxy.recorders.sbom_recorder.SecurityLens")
@patch("gitgalaxy.recorders.sbom_recorder.LanguageDetector")
def test_sbom_trusts_manifest_paths_without_revalidating_them(mock_det, mock_sec, tmp_path):
    """SbomRecorder no longer owns vendor-dir exclusion — that guarantee now
    lives entirely in galaxyscope Phase 10 (stem_map/aperture filtering),
    upstream of manifest_paths. This locks in that SbomRecorder itself does
    NOT re-filter: a node_modules-nested manifest handed to it via
    manifest_paths gets processed like any other manifest. If aperture's
    own filtering ever regresses, this is not where that would be caught —
    that guard belongs in a galaxyscope-level test."""
    import json

    project = tmp_path / "proj"
    dep = project / "node_modules" / "some-lib"
    dep.mkdir(parents=True)
    (dep / "package.json").write_text('{"dependencies": {"evil-transitive": "6.6.6"}}')
    inner_lib = dep / "node_modules" / "evil-transitive"
    inner_lib.mkdir(parents=True)
    (inner_lib / "index.js").write_text("ok")

    mock_sec.return_value.scan_content.return_value = {"counts": {"entropy": 0.0}}
    mock_det.return_value.inspect.return_value = {"anomaly_flags": []}

    recorder = SbomRecorder()
    out = tmp_path / "bom.json"
    recorder.generate_report(
        [], {}, {"target_directory": str(project)}, str(out),
        manifest_paths=[str(dep / "package.json")],
    )

    bom = json.loads(out.read_text())
    assert len(bom["components"]) == 1, (
        "SbomRecorder should trust manifest_paths as given -- filtering is "
        "galaxyscope's job now, not SbomRecorder's."
    )