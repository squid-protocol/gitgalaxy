import json
import logging
from unittest.mock import patch

from gitgalaxy.recorders.sbom_recorder import SbomRecorder, UniversalManifestSlicer
from gitgalaxy.security.manifest_parser import SUPPORTED_MANIFEST_SUFFIXES


# ==============================================================================
# TEST 1: The Multi-Ecosystem Slicer Guard (Full Ecosystem Matrix)
# ==============================================================================
def test_universal_manifest_slicer_all_ecosystems(tmp_path):
    """Proves regex and parsing logic flawlessly extracts dependencies across the original 7 supported ecosystems.
    See test_universal_manifest_slicer_expanded_ecosystems_702 for the ecosystems added by issue #702."""
    slicer = UniversalManifestSlicer()

    # 1. NPM
    pkg_json = tmp_path / "package.json"
    pkg_json.write_text(
        '{"dependencies": {"express": "^4.17.1"}, "devDependencies": {"jest": "27.0.0"}}',
        encoding="utf-8",
    )
    assert slicer.slice_manifest(pkg_json) == (
        "npm",
        {"express": "^4.17.1", "jest": "27.0.0"},
    )

    # 2. PyPI
    req_txt = tmp_path / "requirements.txt"
    req_txt.write_text("requests==2.26.0\n# comment\nurllib3>=1.26.0", encoding="utf-8")
    assert slicer.slice_manifest(req_txt) == (
        "pypi",
        {"requests": "2.26.0", "urllib3": "latest"},
    )

    # 3. Cargo (Rust)
    cargo_toml = tmp_path / "Cargo.toml"
    cargo_toml.write_text(
        '[package]\nname="test"\n[dependencies]\ntokio = "1.0"\nserde = "1.0"',
        encoding="utf-8",
    )
    assert slicer.slice_manifest(cargo_toml) == (
        "cargo",
        {"tokio": "latest", "serde": "latest"},
    )

    # 4. Packagist (PHP Composer)
    composer_json = tmp_path / "composer.json"
    composer_json.write_text(
        '{"require": {"monolog/monolog": "2.0", "php": "^7.4"}, "require-dev": {"phpunit/phpunit": "9.0"}}',
        encoding="utf-8",
    )
    eco_php, deps_php = slicer.slice_manifest(composer_json)
    assert eco_php == "packagist"
    assert "php" not in deps_php  # Proves the PHP version stripped
    assert deps_php["monolog/monolog"] == "2.0"

    # 5. Golang
    go_mod = tmp_path / "go.mod"
    go_mod.write_text(
        "module test\nrequire (\ngin v1.0\n// comment\n)\nrequire sql v2.0",
        encoding="utf-8",
    )
    assert slicer.slice_manifest(go_mod) == ("golang", {"gin": "v1.0", "sql": "v2.0"})

    # 6. RubyGems
    gemfile = tmp_path / "Gemfile"
    gemfile.write_text("gem 'rails', '~> 6.1'\ngem \"nokogiri\"", encoding="utf-8")
    assert slicer.slice_manifest(gemfile) == (
        "rubygems",
        {"rails": "~> 6.1", "nokogiri": "latest"},
    )

    # 7. Maven (Java)
    pom_xml = tmp_path / "pom.xml"
    pom_xml.write_text(
        "<project><dependencies><dependency><artifactId>spring-boot</artifactId><version>2.5.0</version></dependency><dependency><artifactId>guava</artifactId></dependency></dependencies></project>",
        encoding="utf-8",
    )
    assert slicer.slice_manifest(pom_xml) == (
        "maven",
        {"spring-boot": "2.5.0", "guava": "latest"},
    )

    # 8. Exception Handling Fallback
    bad_file = tmp_path / "package.json"
    bad_file.write_text("THIS IS NOT VALID JSON")
    # The slicer identifies the ecosystem by filename before the JSON parsing fails
    assert slicer.slice_manifest(bad_file) == ("npm", {})


# ==============================================================================
# TEST 2: The Physical Locator Trap (Coverage for Directory Walkers)
# ==============================================================================
def test_locate_physical_package(tmp_path):
    """Proves the physical cartography logic accurately hunts down packages based on ecosystem norms."""
    slicer = UniversalManifestSlicer()

    # 1. NPM (node_modules)
    (tmp_path / "node_modules" / "express").mkdir(parents=True)
    assert slicer.locate_physical_package(tmp_path, "express", "npm") is not None
    assert slicer.locate_physical_package(tmp_path, "ghost", "npm") is None

    # 2. Packagist (vendor)
    (tmp_path / "vendor" / "monolog").mkdir(parents=True)
    assert slicer.locate_physical_package(tmp_path, "monolog", "packagist") is not None

    # 3. Golang (vendor)
    (tmp_path / "vendor" / "gin").mkdir(parents=True)
    assert slicer.locate_physical_package(tmp_path, "gin", "golang") is not None

    # 4. PyPI (venv/lib/pythonX.X/site-packages)
    site_packages = tmp_path / "venv" / "lib" / "python3.10" / "site-packages"
    (site_packages / "requests").mkdir(parents=True)
    assert slicer.locate_physical_package(tmp_path, "requests", "pypi") is not None
    assert slicer.locate_physical_package(tmp_path, "ghost", "pypi") is None

    # 5. RubyGems (vendor/bundle)
    (tmp_path / "vendor" / "bundle" / "ruby" / "3.0.0" / "rails").mkdir(parents=True)
    assert slicer.locate_physical_package(tmp_path, "rails", "rubygems") is not None
    assert slicer.locate_physical_package(tmp_path, "ghost", "rubygems") is None

    # 6. Maven (target/dependency)
    dep_dir = tmp_path / "target" / "dependency"
    dep_dir.mkdir(parents=True)
    (dep_dir / "spring-boot-2.5.0.jar").touch()
    assert slicer.locate_physical_package(tmp_path, "spring-boot", "maven") is not None
    assert slicer.locate_physical_package(tmp_path, "ghost", "maven") is None

    # 7. Unknown Ecosystem
    assert slicer.locate_physical_package(tmp_path, "pkg", "alien_eco") is None


# ==============================================================================
# TEST 2b: Issue #702 -- Expanded Ecosystem Coverage
# ==============================================================================
def test_universal_manifest_slicer_expanded_ecosystems_702(tmp_path):
    """Proves slice_manifest() extracts dependencies from every ecosystem added by issue #702."""
    slicer = UniversalManifestSlicer()

    # Modern Python: pyproject.toml (PEP 621 + Poetry)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "test"\ndependencies = [\n    "requests>=2.0",\n    "flask",\n]\n\n'
        '[tool.poetry.dependencies]\npython = "^3.9"\nnumpy = "^1.21"\n',
        encoding="utf-8",
    )
    eco, deps = slicer.slice_manifest(pyproject)
    assert eco == "pypi"
    assert deps == {"requests": "latest", "flask": "latest", "numpy": "^1.21"}

    # Modern Python: poetry.lock
    poetry_lock = tmp_path / "poetry.lock"
    poetry_lock.write_text(
        '[[package]]\nname = "requests"\nversion = "2.26.0"\n\n[[package]]\nname = "flask"\nversion = "2.0.1"\n',
        encoding="utf-8",
    )
    assert slicer.slice_manifest(poetry_lock) == ("pypi", {"requests": "2.26.0", "flask": "2.0.1"})

    # Modern Python: Pipfile
    pipfile = tmp_path / "Pipfile"
    pipfile.write_text(
        '[packages]\nrequests = "*"\nflask = ">=1.0"\n\n[dev-packages]\npytest = "*"\n', encoding="utf-8"
    )
    assert slicer.slice_manifest(pipfile) == (
        "pypi",
        {"requests": "latest", "flask": ">=1.0", "pytest": "latest"},
    )

    # .NET: packages.config
    packages_config = tmp_path / "packages.config"
    packages_config.write_text(
        '<packages>\n  <package id="Newtonsoft.Json" version="12.0.3" targetFramework="net472" />\n'
        '  <package id="NUnit" />\n</packages>\n',
        encoding="utf-8",
    )
    assert slicer.slice_manifest(packages_config) == (
        "nuget",
        {"Newtonsoft.Json": "12.0.3", "NUnit": "latest"},
    )

    # .NET: *.csproj (PackageReference), suffix-matched rather than exact filename
    csproj = tmp_path / "MyApp.csproj"
    csproj.write_text(
        '<Project Sdk="Microsoft.NET.Sdk">\n  <ItemGroup>\n'
        '    <PackageReference Include="Serilog" Version="2.10.0" />\n'
        '    <PackageReference Include="AutoMapper" />\n  </ItemGroup>\n</Project>\n',
        encoding="utf-8",
    )
    assert slicer.slice_manifest(csproj) == ("nuget", {"Serilog": "2.10.0", "AutoMapper": "latest"})

    # C/C++: conanfile.txt
    conanfile = tmp_path / "conanfile.txt"
    conanfile.write_text("[requires]\nboost/1.75.0\nzlib/1.2.11\n\n[generators]\ncmake\n", encoding="utf-8")
    assert slicer.slice_manifest(conanfile) == ("conan", {"boost": "1.75.0", "zlib": "1.2.11"})

    # C/C++: vcpkg.json
    vcpkg_json = tmp_path / "vcpkg.json"
    vcpkg_json.write_text(
        json.dumps({"name": "myapp", "dependencies": ["fmt", {"name": "curl", "features": ["ssl"]}]}),
        encoding="utf-8",
    )
    assert slicer.slice_manifest(vcpkg_json) == ("vcpkg", {"fmt": "latest", "curl": "latest"})

    # Java/Kotlin/Android: build.gradle
    gradle = tmp_path / "build.gradle"
    gradle.write_text(
        "dependencies {\n    implementation 'com.google.guava:guava:30.1-jre'\n"
        '    testImplementation("junit:junit:4.13")\n}\n',
        encoding="utf-8",
    )
    assert slicer.slice_manifest(gradle) == (
        "gradle",
        {"com.google.guava:guava": "30.1-jre", "junit:junit": "4.13"},
    )

    # Mobile: Podfile (CocoaPods)
    podfile = tmp_path / "Podfile"
    podfile.write_text("platform :ios, '13.0'\npod 'Alamofire', '~> 5.4'\npod 'SDWebImage'\n", encoding="utf-8")
    assert slicer.slice_manifest(podfile) == ("cocoapods", {"Alamofire": "~> 5.4", "SDWebImage": "latest"})

    # Mobile: Package.swift (Swift Package Manager)
    package_swift = tmp_path / "Package.swift"
    package_swift.write_text(
        'let package = Package(\n    name: "MyLib",\n    dependencies: [\n'
        '        .package(url: "https://github.com/apple/swift-log.git", from: "1.4.0"),\n'
        '        .package(url: "https://github.com/apple/swift-algorithms.git", from: "1.0.0"),\n    ]\n)\n',
        encoding="utf-8",
    )
    assert slicer.slice_manifest(package_swift) == (
        "swiftpm",
        {"swift-log": "1.4.0", "swift-algorithms": "1.0.0"},
    )

    # Dart/Flutter: pubspec.yaml
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text(
        "name: myapp\ndependencies:\n  flutter:\n    sdk: flutter\n  http: ^0.13.3\n  provider: ^6.0.0\n\n"
        "dev_dependencies:\n  test: ^1.16.0\n",
        encoding="utf-8",
    )
    eco, deps = slicer.slice_manifest(pubspec)
    assert eco == "pub"
    assert deps == {"flutter": "latest", "http": "^0.13.3", "provider": "^6.0.0"}
    assert "test" not in deps, "dev_dependencies should not be conflated with the top-level dependencies block"

    # JS/TS alternative lockfile: yarn.lock
    yarn_lock = tmp_path / "yarn.lock"
    yarn_lock.write_text(
        '"@babel/core@^7.0.0":\n  version "7.12.3"\n'
        '  resolved "https://registry.yarnpkg.com/@babel/core/-/core-7.12.3.tgz#deadbeef"\n\n'
        'ansi-styles@^3.2.1:\n  version "3.2.1"\n'
        '  resolved "https://registry.yarnpkg.com/ansi-styles/-/ansi-styles-3.2.1.tgz#cafebabe"\n',
        encoding="utf-8",
    )
    assert slicer.slice_manifest(yarn_lock) == (
        "npm",
        {"@babel/core": "7.12.3", "ansi-styles": "3.2.1"},
    )

    # JS/TS alternative lockfile: pnpm-lock.yaml
    pnpm_lock = tmp_path / "pnpm-lock.yaml"
    pnpm_lock.write_text(
        "lockfileVersion: '6.0'\n\ndependencies:\n  express:\n    specifier: ^4.18.0\n    version: 4.18.2\n"
        "  lodash:\n    specifier: ^4.17.21\n    version: 4.17.21\n\n"
        "devDependencies:\n  jest:\n    specifier: ^29.0.0\n    version: 29.0.3\n",
        encoding="utf-8",
    )
    assert slicer.slice_manifest(pnpm_lock) == (
        "npm",
        {"express": "4.18.2", "lodash": "4.17.21", "jest": "29.0.3"},
    )


def test_locate_physical_package_expanded_ecosystems_702(tmp_path):
    """Proves locate_physical_package() finds packages for every ecosystem added by issue #702."""
    slicer = UniversalManifestSlicer()

    # NuGet: project-local packages/ dir
    (tmp_path / "packages" / "Serilog").mkdir(parents=True)
    assert slicer.locate_physical_package(tmp_path, "Serilog", "nuget") is not None
    assert slicer.locate_physical_package(tmp_path, "ghost", "nuget") is None

    # Conan: project-local vcpkg_installed/
    (tmp_path / "vcpkg_installed" / "x64-linux" / "fmt").mkdir(parents=True)
    assert slicer.locate_physical_package(tmp_path, "fmt", "vcpkg") is not None
    assert slicer.locate_physical_package(tmp_path, "ghost", "vcpkg") is None

    # CocoaPods: Pods/
    (tmp_path / "Pods" / "Alamofire").mkdir(parents=True)
    assert slicer.locate_physical_package(tmp_path, "Alamofire", "cocoapods") is not None
    assert slicer.locate_physical_package(tmp_path, "ghost", "cocoapods") is None

    # Swift Package Manager: .build/checkouts/
    (tmp_path / ".build" / "checkouts" / "swift-log").mkdir(parents=True)
    assert slicer.locate_physical_package(tmp_path, "swift-log", "swiftpm") is not None
    assert slicer.locate_physical_package(tmp_path, "ghost", "swiftpm") is None


# ==============================================================================
# TEST 3: Graceful Fallbacks (Missing Targets & Empty Voids)
# ==============================================================================
def test_sbom_generator_graceful_fallbacks(tmp_path, caplog):
    """Proves the orchestrator aborts gracefully if the target is invalid or empty."""
    recorder = SbomRecorder()

    # 1. Invalid Target
    with caplog.at_level(logging.ERROR):
        recorder.generate_report([], {}, {"target_directory": "/path/does/not/exist"}, str(tmp_path / "out.json"))
    assert "does not exist" in caplog.text

    # 2. Valid Target, No Manifests
    empty_dir = tmp_path / "empty_project"
    empty_dir.mkdir()
    out_file = tmp_path / "empty_bom.json"

    with caplog.at_level(logging.WARNING):
        recorder.generate_report([], {}, {"target_directory": str(empty_dir)}, str(out_file))

    assert "No supported manifests found" in caplog.text
    # Proves it still successfully dumps the standard CycloneDX shell!
    assert out_file.exists()


# ==============================================================================
# TEST 4: The Zero-Trust CycloneDX Matrix (Spoofs & Exceptions)
# ==============================================================================
@patch("gitgalaxy.recorders.sbom_recorder.SecurityLens")
@patch("gitgalaxy.recorders.sbom_recorder.LanguageDetector")
def test_zero_trust_sbom_generation_anomalies(mock_detector_class, mock_security_class, tmp_path):
    """Proves the physical audit detects malware, missing files, and survives OS exceptions."""
    project_dir = tmp_path / "target_project"
    project_dir.mkdir()

    pkg_json = project_dir / "package.json"
    pkg_json.write_text(
        '{"dependencies": {"safe-lib": "1.0", "ghost-lib": "2.0", "broken-lib": "3.0"}}',
        encoding="utf-8",
    )

    # safe-lib: Malware Spoof
    safe_lib_dir = project_dir / "node_modules" / "safe-lib"
    safe_lib_dir.mkdir(parents=True)
    (safe_lib_dir / "index.js").write_text("console.log('hello');")

    # broken-lib: Permissions / Read Error Trap
    broken_lib_dir = project_dir / "node_modules" / "broken-lib"
    broken_lib_dir.mkdir(parents=True)
    (broken_lib_dir / "corrupt.js").write_text("bad data")

    # Mocks
    mock_sec_instance = mock_security_class.return_value
    mock_det_instance = mock_detector_class.return_value

    # safe-lib trips the threat detector
    mock_sec_instance.scan_content.return_value = {"counts": {"entropy": 5.2}}
    mock_det_instance.inspect.return_value = {"anomaly_flags": ["Disguised Executable"]}

    # Force an OS Exception on broken-lib to prove the generator survives
    original_open = open

    def conditional_open(file, *args, **kwargs):
        if "corrupt.js" in str(file):
            raise PermissionError("Locked")
        return original_open(file, *args, **kwargs)

    out_file = tmp_path / "test_bom.json"
    recorder = SbomRecorder()

    with patch("builtins.open", side_effect=conditional_open):
        recorder.generate_report([], {}, {"target_directory": str(project_dir)}, str(out_file))

    bom_data = json.loads(out_file.read_text(encoding="utf-8"))

    components = {c["name"]: c for c in bom_data["components"]}

    # Assert missing packages correctly mapped
    ghost_props = {p["name"]: p["value"] for p in components["ghost-lib"]["properties"]}
    assert ghost_props["gitgalaxy:trust_status"] == "UNVERIFIED_MISSING_ON_DISK"

    # Assert Spoof accurately mapped
    safe_props = {p["name"]: p["value"] for p in components["safe-lib"]["properties"]}
    assert safe_props["gitgalaxy:trust_status"] == "SPOOF_DETECTED"
    assert "High Entropy" in safe_props["gitgalaxy:anomaly_notes"]

    # Assert Exception Survival
    assert "broken-lib" in components


# ==============================================================================
# TEST 5: Perfect Clean Execution
# ==============================================================================
@patch("gitgalaxy.recorders.sbom_recorder.SecurityLens")
@patch("gitgalaxy.recorders.sbom_recorder.LanguageDetector")
def test_zero_trust_sbom_clean_run(mock_detector_class, mock_security_class, tmp_path):
    """Proves the generator successfully outputs a VERIFIED_SAFE SBOM status."""
    project_dir = tmp_path / "clean_project"
    project_dir.mkdir()

    pkg_json = project_dir / "package.json"
    pkg_json.write_text('{"dependencies": {"good-lib": "1.0"}}', encoding="utf-8")

    lib_dir = project_dir / "node_modules" / "good-lib"
    lib_dir.mkdir(parents=True)
    (lib_dir / "index.js").write_text("console.log('clean');")

    mock_sec_instance = mock_security_class.return_value
    mock_det_instance = mock_detector_class.return_value
    mock_sec_instance.scan_content.return_value = {"counts": {"entropy": 0.0}}
    mock_det_instance.inspect.return_value = {"anomaly_flags": []}

    out_file = tmp_path / "clean_bom.json"
    recorder = SbomRecorder()

    recorder.generate_report([], {}, {"target_directory": str(project_dir)}, str(out_file))

    bom_data = json.loads(out_file.read_text(encoding="utf-8"))

    props = {p["name"]: p["value"] for p in bom_data["components"][0]["properties"]}
    assert props["gitgalaxy:trust_status"] == "VERIFIED_SAFE"


# ==============================================================================
# TEST 6: MANIFEST REGISTRY SYNC (drift guard)
# ==============================================================================
def test_manifest_names_match_slicer_support(tmp_path):
    """
    Regression: SbomRecorder._MANIFEST_NAMES (now an alias for
    manifest_parser.SUPPORTED_MANIFEST_FILENAMES) must never drift from the
    filenames UniversalManifestSlicer.slice_manifest() actually knows how to
    parse. This is exactly the class of bug behind the
    GUIDESTAR_CONFIG["MANIFEST_MAP"] drift: two independently-maintained
    lists silently disagreeing.
    """
    slicer = UniversalManifestSlicer()
    expected_ecosystems = {
        "package.json": "npm",
        "composer.json": "packagist",
        "requirements.txt": "pypi",
        "Cargo.toml": "cargo",
        "go.mod": "golang",
        "Gemfile": "rubygems",
        "pom.xml": "maven",
        # Issue #702 additions
        "pyproject.toml": "pypi",
        "poetry.lock": "pypi",
        "Pipfile": "pypi",
        "packages.config": "nuget",
        "conanfile.txt": "conan",
        "vcpkg.json": "vcpkg",
        "build.gradle": "gradle",
        "build.gradle.kts": "gradle",
        "Podfile": "cocoapods",
        "Package.swift": "swiftpm",
        "pubspec.yaml": "pub",
        "yarn.lock": "npm",
        "pnpm-lock.yaml": "npm",
    }

    assert set(SbomRecorder._MANIFEST_NAMES) == set(expected_ecosystems), (
        "SbomRecorder._MANIFEST_NAMES no longer matches the known ecosystem set "
        "-- update this test AND confirm slice_manifest() handles the change."
    )

    for filename, expected_eco in expected_ecosystems.items():
        f = tmp_path / filename
        f.write_text("")  # ecosystem is identified by filename before content is parsed
        ecosystem, _ = slicer.slice_manifest(f)
        assert ecosystem == expected_eco, (
            f"{filename} is in _MANIFEST_NAMES but slice_manifest identified it as "
            f"'{ecosystem}' instead of '{expected_eco}' -- the two are out of sync!"
        )


def test_manifest_suffixes_match_slicer_support(tmp_path):
    """
    Suffix-based counterpart to test_manifest_names_match_slicer_support:
    SUPPORTED_MANIFEST_SUFFIXES (issue #702's *.csproj addition) exists
    because some manifests -- unlike every other entry in
    SUPPORTED_MANIFEST_FILENAMES -- are named arbitrarily per-project rather
    than with one fixed filename, so they can't live in that exact-name set.
    """
    slicer = UniversalManifestSlicer()
    assert SUPPORTED_MANIFEST_SUFFIXES == (".csproj",)

    f = tmp_path / "SomeArbitraryProjectName.csproj"
    f.write_text("")
    ecosystem, _ = slicer.slice_manifest(f)
    assert ecosystem == "nuget", (
        f"*.csproj is in SUPPORTED_MANIFEST_SUFFIXES but slice_manifest identified it as "
        f"'{ecosystem}' instead of 'nuget' -- the two are out of sync!"
    )


def test_locate_physical_package_hoisted_dependency(tmp_path):
    """Regression: npm/yarn/pnpm workspaces hoist shared deps to the
    workspace root instead of duplicating them per sub-package. Without
    repo_root, a hoisted dep must still miss (backward compatibility for
    callers that don't know about workspace roots). With repo_root, it
    must be found by walking upward -- but never past repo_root."""
    slicer = UniversalManifestSlicer()
    frontend = tmp_path / "packages" / "frontend"
    frontend.mkdir(parents=True)
    (tmp_path / "node_modules" / "react").mkdir(parents=True)

    assert slicer.locate_physical_package(frontend, "react", "npm") is None, (
        "Legacy call signature (no repo_root) must stay unaffected."
    )
    assert slicer.locate_physical_package(frontend, "react", "npm", repo_root=tmp_path) is not None, (
        "Hoisted dependency at the workspace root was not found."
    )
