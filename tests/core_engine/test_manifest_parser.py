import json
import logging

import pytest

# Adjust this import based on your actual project structure
from gitgalaxy.security.manifest_parser import ManifestParser


@pytest.fixture
def parser():
    """Provides a fresh ManifestParser instance with a silenced logger for clean test output."""
    logger = logging.getLogger("test_manifest_parser")
    logger.addHandler(logging.NullHandler())
    p = ManifestParser(parent_logger=logger)

    # Intercept and flatten the nested alias map so legacy unit tests don't need to be rewritten
    original_build = p.build_resolution_map

    def flat_build_wrapper(manifest_paths):
        nested_map = original_build(manifest_paths)
        flat_map = {}
        for local_map in nested_map.values():
            flat_map.update(local_map)
        return flat_map

    p.build_resolution_map = flat_build_wrapper
    return p


# ==============================================================================
# 1. package.json Tests (Aliasing & Direct URI Resolution)
# ==============================================================================
def test_package_json_npm_aliasing(parser, tmp_path):
    """
    Verifies that npm: aliases and scoped aliases are correctly dereferenced to their
    true upstream package names to ensure accurate vulnerability tracking.
    """
    pkg_file = tmp_path / "package.json"
    pkg_file.write_text(
        json.dumps(
            {
                "dependencies": {
                    "lodash": "npm:malicious-lodash@1.0.0",
                    "express": "npm:@hacker-scope/express-shadow@2.1.1",
                    "react": "^18.0.0",  # Standard package, should be ignored
                }
            }
        )
    )

    resolution_map = parser.build_resolution_map([str(pkg_file)])

    assert "lodash" in resolution_map
    assert resolution_map["lodash"] == "malicious-lodash"

    assert "express" in resolution_map
    assert resolution_map["express"] == "@hacker-scope/express-shadow"

    # Standard packages shouldn't be added to the resolution map by package.json
    assert "react" not in resolution_map


def test_package_json_direct_uri_resolution(parser, tmp_path):
    """
    Verifies that direct file system or git repository overrides are flagged.
    These bypass Subresource Integrity (SRI) checks and are massive supply chain risks.
    """
    pkg_file = tmp_path / "package.json"
    pkg_file.write_text(
        json.dumps(
            {
                "devDependencies": {
                    "jest": "github:evil/jest",
                    "mocha": "file:./local-malware.js",
                    "eslint": "git+https://evil.com/eslint.git",
                }
            }
        )
    )

    resolution_map = parser.build_resolution_map([str(pkg_file)])

    assert resolution_map["jest"] == "github:evil/jest"
    assert resolution_map["mocha"] == "file:./local-malware.js"
    assert resolution_map["eslint"] == "git+https://evil.com/eslint.git"


def test_package_json_invalid_json(parser, tmp_path):
    """Ensures the parser degrades gracefully without crashing if the structural definition is corrupted."""
    pkg_file = tmp_path / "package.json"
    pkg_file.write_text("{ THIS IS INVALID JSON ]")

    # Should not throw an exception, just return an empty map
    resolution_map = parser.build_resolution_map([str(pkg_file)])
    assert resolution_map == {}


def test_package_json_empty_dependencies(parser, tmp_path):
    """Proves the parser does not crash when a manifest lacks dependency blocks entirely."""
    pkg_file = tmp_path / "package.json"
    pkg_file.write_text(json.dumps({"name": "my-app", "version": "1.0.0"}))

    resolution_map = parser.build_resolution_map([str(pkg_file)])
    assert resolution_map == {}, "Parser hallucinated dependencies from an empty block!"


# ==============================================================================
# 2. package-lock.json Tests (Registry Spoofing)
# ==============================================================================
def test_package_lock_registry_spoofing(parser, tmp_path):
    """
    Verifies that external, non-NPM registry resolutions are intercepted.
    Neutralizes attacks where internal packages are hijacked to point to malicious domains.
    """
    lock_file = tmp_path / "package-lock.json"

    lock_file.write_text(
        json.dumps(
            {
                "packages": {
                    "node_modules/clean-pkg": {"resolved": "https://registry.npmjs.org/clean-pkg.tgz"},
                    "node_modules/dirty-pkg": {"resolved": "https://evil-registry.com/dirty-pkg.tgz"},
                }
            }
        )
    )

    resolution_map = parser.build_resolution_map([str(lock_file)])

    # Standard registries should be ignored (trusted baseline)
    assert "clean-pkg" not in resolution_map

    # Suspicious registries must be mapped so the supply chain firewall can block them
    assert "dirty-pkg" in resolution_map
    assert resolution_map["dirty-pkg"] == "https://evil-registry.com/dirty-pkg.tgz"


# ==============================================================================
# 3. requirements.txt Tests (Direct URI References & Constraints)
# ==============================================================================
def test_requirements_txt_direct_uri_references(parser, tmp_path):
    """
    Verifies standard python packages are indexed and Direct URI references
    (which bypass PyPI registry verification) are captured exactly as written.
    """
    req_file = tmp_path / "requirements.txt"
    req_file.write_text(
        "# This is a comment\n"
        "requests==2.25.1\n"
        "flask>=1.1.0\n"
        "git+https://github.com/hacker/malware.git\n"
        "file:///etc/passwd\n"
    )

    resolution_map = parser.build_resolution_map([str(req_file)])

    # Standard packages map to themselves to ensure tracking
    assert resolution_map["requests"] == "requests"
    assert resolution_map["flask"] == "flask"

    # Direct URI references map the full string to ensure the firewall catches the untrusted URL
    assert resolution_map["git+https://github.com/hacker/malware.git"] == "git+https://github.com/hacker/malware.git"
    assert resolution_map["file:///etc/passwd"] == "file:///etc/passwd"


def test_requirements_txt_complex_constraints(parser, tmp_path):
    """
    Proves the Regex engine correctly extracts the base package name even when
    mixed with complex version constraints or environment markers.
    """
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("Django>=3.0,<4.0\npytest~=7.0\nurllib3==1.26.15; python_version >= '3.6'\n")

    resolution_map = parser.build_resolution_map([str(req_file)])

    assert "Django" in resolution_map
    assert "pytest" in resolution_map
    assert "urllib3" in resolution_map


# ==============================================================================
# 4. pip.conf Tests (Insecure Protocol Routing)
# ==============================================================================
def test_pip_conf_insecure_registry(parser, tmp_path):
    """
    Verifies that HTTP (MitM vulnerable) or ngrok tunnel registries are instantly flagged
    to prevent Dependency Confusion vulnerabilities.
    """
    pip_file = tmp_path / "pip.conf"
    pip_file.write_text(
        "[global]\n"
        "index-url = http://pypi.org/simple\n"  # Insecure HTTP
        "extra-index-url = https://hacker-tunnel.ngrok.io\n"  # ngrok tunneling
        "trusted-host = pypi.org\n"
    )

    resolution_map = parser.build_resolution_map([str(pip_file)])

    assert "INSECURE_REGISTRY_pip.conf" in resolution_map
    assert "ngrok" in resolution_map["INSECURE_REGISTRY_pip.conf"]


def test_pip_conf_trusted_registry(parser, tmp_path):
    """Ensures legitimate HTTPS internal registries (like Artifactory) do not trigger false positives."""
    pip_file = tmp_path / "pip.conf"
    pip_file.write_text("[global]\nindex-url = https://artifactory.internal.company.com/api/pypi/simple\n")

    resolution_map = parser.build_resolution_map([str(pip_file)])

    assert "INSECURE_REGISTRY_pip.conf" not in resolution_map, "Trusted registry falsely flagged as insecure!"


def test_pip_conf_insecure_registry_url_with_query_string_equals(parser, tmp_path):
    """
    Regression test for #253: a registry URL containing its own '=' (e.g. a
    query string or embedded token) must still be flagged as insecure —
    previously line.split("=") returned 3+ parts and the len(parts) == 2
    check silently skipped the line entirely.
    """
    pip_file = tmp_path / "pip.conf"
    pip_file.write_text("[global]\nindex-url = http://example.com/simple?token=abc123\n")

    resolution_map = parser.build_resolution_map([str(pip_file)])

    assert "INSECURE_REGISTRY_pip.conf" in resolution_map, (
        "Insecure registry URL containing a second '=' was silently skipped."
    )
    assert resolution_map["INSECURE_REGISTRY_pip.conf"] == "http://example.com/simple?token=abc123"


def test_pip_conf_insecure_registry_url_with_multiple_equals(parser, tmp_path):
    """
    Regression test for #253: proves the fix generalizes beyond exactly one
    extra '=' — a URL with several embedded '=' characters must still be
    captured in full, not truncated at the first extra one.
    """
    pip_file = tmp_path / "pip.conf"
    pip_file.write_text("[global]\nextra-index-url = http://example.com/path?a=1&b=2&sig=deadbeef\n")

    resolution_map = parser.build_resolution_map([str(pip_file)])

    assert "INSECURE_REGISTRY_pip.conf" in resolution_map
    assert resolution_map["INSECURE_REGISTRY_pip.conf"] == "http://example.com/path?a=1&b=2&sig=deadbeef", (
        "URL was truncated instead of captured whole."
    )


def test_pip_conf_repository_keyword_with_equals_in_value(parser, tmp_path):
    """
    Regression test for #253 via the 'repository' trigger keyword (.pypirc
    style), which had no prior test coverage at all. Confirms the same
    maxsplit fix applies regardless of which of the three trigger keywords
    (index-url / extra-index-url / repository) matched the line.
    """
    pypirc_file = tmp_path / ".pypirc"
    pypirc_file.write_text(
        "[distutils]\nindex-servers = internal\n\n[internal]\nrepository = http://example.com/simple?token=abc123\n"
    )

    resolution_map = parser.build_resolution_map([str(pypirc_file)])

    assert "INSECURE_REGISTRY_.pypirc" in resolution_map, (
        "'repository' keyword line with an embedded '=' was silently skipped."
    )
    assert resolution_map["INSECURE_REGISTRY_.pypirc"] == "http://example.com/simple?token=abc123"


# ==============================================================================
# 4b. Issue #702 -- Expanded Security Auditing (pyproject.toml, yarn.lock, Gradle)
# ==============================================================================
def test_pyproject_toml_pep621_direct_uri_reference(parser, tmp_path):
    """Verifies PEP 621 `dependencies = [...]` entries with a direct `@ git+...`/URL
    reference (which bypass PyPI registry verification) are flagged, same as requirements.txt."""
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(
        '[project]\nname = "test"\ndependencies = [\n'
        '    "requests>=2.0",\n'
        '    "evil-pkg @ git+https://github.com/hacker/malware.git",\n'
        "]\n"
    )

    resolution_map = parser.build_resolution_map([str(pyproject_file)])

    assert "requests" not in resolution_map, "Standard packages shouldn't be added to the resolution map"
    assert resolution_map["evil-pkg"] == "git+https://github.com/hacker/malware.git"


def test_pyproject_toml_poetry_direct_git_reference(parser, tmp_path):
    """Verifies Poetry-style `[tool.poetry.dependencies]` table entries with an inline
    git/url table are flagged, and the `python` version constraint entry is ignored."""
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(
        '[tool.poetry.dependencies]\npython = "^3.9"\nnumpy = "^1.21"\n'
        'evil-pkg = {git = "https://github.com/hacker/malware.git"}\n'
    )

    resolution_map = parser.build_resolution_map([str(pyproject_file)])

    assert "python" not in resolution_map
    assert "numpy" not in resolution_map, "Standard packages shouldn't be added to the resolution map"
    assert resolution_map["evil-pkg"] == "git+https://github.com/hacker/malware.git"


def test_yarn_lock_registry_spoofing(parser, tmp_path):
    """Verifies yarn.lock's counterpart to package-lock.json's registry-spoofing check:
    resolutions outside the standard Yarn/npm registries must be intercepted."""
    yarn_lock = tmp_path / "yarn.lock"
    yarn_lock.write_text(
        'ansi-styles@^3.2.1:\n  version "3.2.1"\n'
        '  resolved "https://registry.yarnpkg.com/ansi-styles/-/ansi-styles-3.2.1.tgz#cafebabe"\n\n'
        '"@hacker-scope/evil-pkg@^1.0.0":\n  version "1.0.0"\n'
        '  resolved "https://evil-registry.com/evil-pkg-1.0.0.tgz"\n'
    )

    resolution_map = parser.build_resolution_map([str(yarn_lock)])

    assert "ansi-styles" not in resolution_map, "Standard registry resolutions should be trusted"
    assert resolution_map["@hacker-scope/evil-pkg"] == "https://evil-registry.com/evil-pkg-1.0.0.tgz"


def test_gradle_insecure_repository(parser, tmp_path):
    """Verifies build.gradle repository blocks using an insecure `http://` URL are flagged,
    the Maven/Gradle equivalent of pip.conf's insecure index-url check."""
    gradle_file = tmp_path / "build.gradle"
    gradle_file.write_text(
        "repositories {\n    mavenCentral()\n    maven {\n        url 'http://insecure-mirror.example.com/repo'\n"
        "    }\n}\n"
    )

    resolution_map = parser.build_resolution_map([str(gradle_file)])

    assert "INSECURE_REGISTRY_build.gradle" in resolution_map
    assert resolution_map["INSECURE_REGISTRY_build.gradle"] == "http://insecure-mirror.example.com/repo"


def test_gradle_trusted_repository(parser, tmp_path):
    """Ensures a Gradle build script using only HTTPS repositories does not false-positive."""
    gradle_file = tmp_path / "build.gradle"
    gradle_file.write_text("repositories {\n    mavenCentral()\n    google()\n}\n")

    resolution_map = parser.build_resolution_map([str(gradle_file)])

    assert resolution_map == {}, "Trusted HTTPS-only repositories falsely flagged as insecure!"


# ==============================================================================
# 5. Global Monorepo Tests
# ==============================================================================


def test_multiple_manifests_simultaneously(parser, tmp_path):
    """Verifies the parser can handle a monorepo setup with multiple manifest formats at once."""
    pkg_file = tmp_path / "package.json"
    req_file = tmp_path / "requirements.txt"

    pkg_file.write_text(json.dumps({"dependencies": {"lodash": "npm:evil-lodash"}}))
    req_file.write_text("numpy==1.20.0")

    resolution_map = parser.build_resolution_map([str(pkg_file), str(req_file)])

    assert len(resolution_map) == 2
    assert resolution_map["lodash"] == "evil-lodash"
    assert resolution_map["numpy"] == "numpy"


def test_unsupported_manifest_bypass(parser, tmp_path):
    """Proves the parser gracefully skips unrelated files without crashing the loop."""
    random_file = tmp_path / "docker-compose.yml"
    random_file.write_text("version: '3.8'\nservices:\n  app:\n    image: node:18")

    resolution_map = parser.build_resolution_map([str(random_file)])

    assert resolution_map == {}, "Parser hallucinated resolutions from an unsupported file type!"


def test_manifest_parser_scope_is_npm_and_pypi_only(parser, tmp_path):
    """
    Documents current scope, not a bug: ManifestParser.build_resolution_map
    only builds an alias/registry-spoofing map for npm-family, PyPI-family,
    and (since issue #702) Gradle files. It does NOT recognize composer.json,
    Cargo.toml, Gemfile, or pom.xml -- even though UniversalManifestSlicer
    (this module's OTHER class, used for the SBOM) parses all of those. Since
    galaxyscope's Phase 10 now feeds the SAME manifest_paths list to both
    consumers, these filenames silently no-op here. Locking this in so a
    future contributor extending SUPPORTED_MANIFEST_FILENAMES doesn't assume
    ManifestParser gained matching coverage for free.
    """
    cargo_file = tmp_path / "Cargo.toml"
    cargo_file.write_text('[dependencies]\nserde = "1.0"')
    composer_file = tmp_path / "composer.json"
    composer_file.write_text(json.dumps({"require": {"monolog/monolog": "npm:evil@1.0"}}))

    resolution_map = parser.build_resolution_map([str(cargo_file), str(composer_file)])

    assert resolution_map == {}, (
        "ManifestParser started resolving Cargo.toml/composer.json -- if this "
        "is intentional, great, but SUPPORTED_MANIFEST_FILENAMES coverage "
        "claims in sbom_recorder/galaxyscope comments should be revisited too."
    )
