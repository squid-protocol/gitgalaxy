# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

"""
gitgalaxy_config.py
Phase 0 & 1: Repository Ingestion, Filtering, and Pre-Flight Context.

This file serves as the core configuration payload. It defines the global
security exceptions and the lightweight ingestion rules used to filter
out noise before the heavy static analysis engines are loaded into memory.
"""

from typing import Any

# ------------------------------------------------------------------
# ZERO-TRUST IMPORT CONTROL (Supply Chain Firewall)
# Defines allowed and banned external dependencies (NPM, PyPI, Composer)
# ------------------------------------------------------------------
# True  = Strict Mode (Only allow packages explicitly in APPROVED_IMPORTS)
# False = Audit Mode (Allow unknown packages, but block BLACKLISTED_IMPORTS)
STRICT_IMPORT_MODE = False

APPROVED_IMPORTS: list[str] = [
    # Examples (Add your approved dependencies here)
]

BLACKLISTED_IMPORTS: list[str] = [
    # Known compromised, malicious, or troll packages
]

# ------------------------------------------------------------------
# NETWORK-CENTRALITY RISK WEIGHTING (Supply Chain Firewall)
# When True, a file's Downstream Exposure / Blast Radius (Phase 4 network
# topology) amplifies its behavioral risk score before the firewall's block
# threshold is applied -- a highly central "hub" file gets less tolerance
# for the same embedded threat signal than a peripheral one.
# Off by default: this previously never actually ran in production (it was
# reading a key nothing ever wrote), so it ships opt-in rather than
# silently changing what existing pipelines block on.
# ------------------------------------------------------------------
FIREWALL_NETWORK_WEIGHTING = False

# ------------------------------------------------------------------
# GLOBAL DENYLIST
# String patterns for files that should NEVER exist in the repository.
# If a file matches these patterns, scanners will instantly block the commit.
# Supports standard Unix wildcards (* for everything, ? for single char).
# ------------------------------------------------------------------
DENYLIST_PATTERNS: list[str] = [
    # "internal_*",         # Blocks internal_notes.txt, internal_architecture.md
    # "*.kdbx",             # Blocks all KeePass password databases
    # "*_backup.sql",       # Blocks database dumps ending in _backup.sql
    # "master_key.*",       # Blocks master_key.pem, master_key.txt, etc.
    # "*-secret-*.json"     # Blocks anything with '-secret-' in the middle
]


# ------------------------------------------------------------------
# GLOBAL ALLOWLIST
# Add exact relative paths or partial string matches here to bypass security tools.
# If a scanner finds a threat here, it will log an "Allowlist Bypass" warning
# rather than failing the build. Use this to mute mock data in test suites.
# ------------------------------------------------------------------
ALLOWLIST_PATHS = [
    # "tests/phpunit/integration/includes/Json/key1.pem",
    # "tests/phpunit/integration/includes/Json/key1.pem.pub",
    # "tests/phpunit/integration/includes/Json/key2.pem",
    # "tests/phpunit/integration/includes/Json/key2.pem.pub"
    "tests/"
]

# ------------------------------------------------------------------
# BINARY / ENTROPY SCANNER BYPASSES
# X-Ray uses information theory (Shannon Entropy) which naturally flags
# compression, foreign languages, and hashes. Add extensions or paths here
# to bypass the X-Ray engine without blinding the Secrets Scanner.
# ------------------------------------------------------------------
XRAY_BYPASS_EXTENSIONS = [
    ".json",
    ".gz",
    ".zip",
    ".tar",
    ".png",
    ".jpg",
    ".jpeg",
    ".ico",
    ".yml",
]

XRAY_BYPASS_PATHS = [
    "package-lock.json",
    "yarn.lock",
    "composer.lock",
    "gitgalaxy/core/aperture.py",
    "gitgalaxy/standards/language_standards/",
    "gitgalaxy/security/security_lens.py",
    "gitgalaxy/tools/network_auditing/full_api_network_map.py",
    "gitgalaxy/tools/cobol_to_cobol/cobol_schema_forge.py",
    "gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py",
    "gitgalaxy/tools/terabyte_log_scanning/pii_leak_hunter.py",
    "gitgalaxy/tools/supply_chain_security/binary_anomaly_detector.py",
    "gitgalaxy/tools/supply_chain_security/supply_chain_firewall.py",
    "site/css/styles.css",
]


# ------------------------------------------------------------------------------
# 1. THE INGESTION FILTER (Ingestion & Exclusion Rules)
# Consumed by: aperture.py
# ------------------------------------------------------------------------------
APERTURE_CONFIG = {
    # --- 0. THE SECRETS SHUNT ---
    # Files caught here will bypass standard structural signature analysis and instantly
    # register a 100.0 score on the Secrets Risk exposure vector.
    "SECRETS_EXTENSIONS": {
        ".pem",
        ".key",
        ".pub",
        ".crt",
        ".cer",
        ".p12",
        ".p7b",
        ".asc",
        ".gpg",
        ".sig",
        ".keystore",
        ".ovpn",
        ".pfx",
        ".jks",
        ".kdbx",
    },
    "SECRETS_EXACT": {
        "id_rsa",
        "id_dsa",
        "id_ed25519",
        "id_ecdsa",
        "truststore.jks",
        "keystore.jks",
        ".env",
        ".env.local",
        ".env.production",
        ".npmrc",
        ".htpasswd",
        ".pypirc",
        "credentials.json",
        "client_secret.json",
        "auth.json",
        "shadow",
    },
    # --- 0.5. TYPOSQUAT WHITELIST (#375) ---
    # Import/module tokens galaxyscope.py's typosquat radar (PASS_1.5) must
    # never flag, even if they're a Levenshtein neighbor of a heavily-used
    # anchor import. Empty by default -- populate with known-legitimate,
    # structurally-similar-looking package names specific to your ecosystem.
    "TYPOSQUAT_WHITELIST": set(),
    # --- 1. The Global Blocklist ---
    "IGNORED_DIRECTORIES": {
        # 1. Version Control Ghosts
        ".git",
        ".svn",
        ".hg",
        "CVS",
        ".bzr",
        ".gitignore",
        ".gitmodules",
        # 2. Package Managers, Dependencies & Third-Party Vendors
        "node_modules",
        "vendor",
        "bower_components",
        "jspm_packages",
        "Pods",
        "Carthage",
        "third_party",
        ".npm",
        # 3. Virtual Environments
        "venv",
        ".venv",
        "env",
        ".env",
        "virtualenv",
        ".tox",
        ".nox",
        # 4. Caches, Meta-Frameworks & Bytecode
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".next",
        ".nuxt",
        ".svelte-kit",
        ".expo",
        ".angular",
        ".turbo",
        ".parcel-cache",
        ".cache",
        "caches",
        ".serverless",
        # 5. Compiled Output & Native Build Targets
        "dist",
        "build",
        "_build",
        "target",
        "obj",
        "out",
        "out-tsc",
        "Release",
        "Debug",
        "cmake-build-debug",
        "CMakeFiles",
        "classes",
        # 6. Testing Output & Coverage Reports
        "coverage",
        ".nyc_output",
        "htmlcov",
        "TestResults",
        # 7. IDE, OS Metadata, & Editor Blueprints
        ".idea",
        ".vscode",
        ".vs",
        ".settings",
        ".metadata",
        ".eclipse",
        ".fleet",
        "DerivedData",
        "__MACOSX",
        # 8. Transitory Runtime Data & Temp Files / Data
        "tmp",
        "temp",
        "logs",
        "log",
        # 9. Documentation & Licensing
        "LICENSES",
        "licenses",
        "LICENSE",
        "license",
        "DOCS",
        "docs",
        "LEGAL",
        "legal",
        "site",
    },
    # --- 2. Extension Denylist ---
    "IGNORED_EXTENSIONS": {
        # 1. Vector & 3D Traps
        ".svg",
        ".eps",
        ".ai",
        ".gltf",
        ".dae",
        ".stl",
        ".obj",
        ".fbx",
        # 2. Raster Image Binaries
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".webp",
        ".tiff",
        ".bmp",
        ".heic",
        # 3. Typography & Fonts
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".otf",
        # 4. Office & Print Documents
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".odt",
        ".ods",
        ".odp",
        # 5. UI/UX Design Project Files
        ".fig",
        ".sketch",
        ".psd",
        ".xd",
        # 6. Media (Audio/Video Data)
        ".mp4",
        ".mp3",
        ".wav",
        ".avi",
        ".mov",
        ".mkv",
        ".webm",
        ".flac",
        ".ogg",
        # 7. Archives & Compression Binaries
        ".zip",
        ".tar",
        ".gz",
        ".tgz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".iso",
        ".cab",
        # 8. Core Compiled Binaries & Object Files
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".class",
        ".jar",
        ".war",
        ".ear",
        ".o",
        ".a",
        ".lib",
        ".out",
        ".pyc",
        ".pyd",
        # 9. Cryptographic Binaries & Keystores (Lethal to text parsers)
        ".p12",
        ".pfx",
        ".p7b",
        ".jks",
        ".kdbx",
        ".der",
    },
    # --- 3. Contraband Patterns ---
    "CONTRABAND_PATTERNS": [
        "*.min.js",
        "*.min.css",
        "jquery*.js",
        "bootstrap*.js",
        "typeahead*.js",
        "vue.global.js",
        "chunk-*.js",
        "*bundle.js",
        "*_full.html",
        "ltmain.sh",
        "config.guess",
        "config.sub",
        "depcomp",
        "missing",
        "install-sh",
    ],
    # --- 4. Integrity Thresholds ---
    "MAX_LINE_LENGTH": 500,
    "MINIFICATION_SCAN_LIMIT": 50,
    # Soft ceiling: content-based classifiers (binary/minified/monotony/array
    # shields) decide whether a file over this size is real signal or noise.
    # An Intent-Locked file (GuideStar-recognized as important) bypasses it.
    "MAX_FILE_SIZE_MB": 50,
    # Absolute ceiling: an unconditional, Intent-blind memory-safety backstop
    # checked before the file is ever opened for reading (see Aperture Gate
    # 1.0 in evaluate_path_integrity). Nothing bypasses this one.
    "MAX_FILE_SIZE_HARD_MB": 250,
    "VENDOR_MINIFICATION_PATHS": [
        "/vendor/",
        "/node_modules/",
        "/bower_components/",
    ],
    # --- 5. Classification Categories ---
    "BANDS": {
        "IGNORED": "ignored_system_or_hidden_file",
        "BINARY": "unreadable_binary_or_media",
        "UNSUPPORTED": "unsupported_file_type",
        "MINIFIED": "minified_or_massive_data",
        "SOURCE_CODE": "valid_source_code",
        "QUARANTINE": "critical_contraband_leak",
        "SECRET": "exposed_secret_or_key",
    },
}


# ------------------------------------------------------------------------------
# 2. PRIORITY ALLOWLIST (Architectural Anchors)
# Consumed by: guidestar_lens.py
# ------------------------------------------------------------------------------
# These files are granted a high confidence score for importance by the GuideStar Lens.
# If found, their Bayesian confidence is boosted (+0.10) to ensure they
# remain visible in the topological map as high-priority contextual baselines.
PRIORITY_WHITELIST = [
    # --- AI Ecosystem Anchor ---
    "__gitgalaxy_meta__.json",
    # --- Universal Entry Points ---
    "main.py",
    "app.py",
    "index.js",
    "server.js",
    "main.go",
    "main.rs",
    "index.ts",
    "app.ts",
    "main.cpp",
    "main.c",
    "Main.java",
    "program.cs",
    # --- Framework Specific Anchors ---
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "settings.py",  # Django/Flask
    "App.js",
    "App.tsx",
    "index.tsx",  # React/Native
    "routes.php",
    "api.php",  # Laravel
    "application.rb",
    "routes.rb",  # Rails
    "Startup.cs",
    "Program.cs",  # .NET Core
    # --- Critical Path Assets ---
    "docker-compose.yml",
    "Dockerfile",
    "Jenkinsfile",
]


# ------------------------------------------------------------------------------
# 3. HEURISTIC INTELLIGENCE (Manifests & Sector Biases)
# Consumed by: guidestar_lens.py
# ------------------------------------------------------------------------------
# Defines the rules for Bayesian Intent inference used by the GuideStar Lens
GUIDESTAR_CONFIG: dict[str, Any] = {
    "IGNORED_DIRECTORIES": APERTURE_CONFIG["IGNORED_DIRECTORIES"],
    "MANIFEST_MAP": {
        "package.json": "javascript",
        "Makefile": "makefile",
        "CMakeLists.txt": "cmake",
        "pyproject.toml": "python",
        "setup.py": "python",
        "Cargo.toml": "rust",
        "go.mod": "go",
        "Gemfile": "ruby",
        "Rakefile": "ruby",
        "pom.xml": "java",
    },
    "INTENT_BIASED_SECTORS": {
        "bin",
        "scripts",
        "tools",
        "utils",
        "src",
        "libexec",
        "hooks",
    },
    "EXEC_PREFIX_MAP": {
        "python3": "python",
        "python": "python",
        "node": "javascript",
        "npm": "javascript",
        "sh": "shell",
        "bash": "shell",
        "cargo": "rust",
        "go": "go",
    },
}


# ------------------------------------------------------------------------------
# 4. LEXICAL FAMILY HEURISTICS (Optical Delimiter Census)
# Consumed by: language_lens.py (Tier 4 Heuristic Discovery) AND prism.py
# (the real comment/code separation engine, via _compile_regex_matrix() --
# see #621: this dict was previously commented as NOT being the source of
# truth for that split, which was wrong and contributed to the bug there).
# ------------------------------------------------------------------------------
# #621: "standard_block" used to carry 9 delimiter tokens covering 3
# incompatible conventions (C-style //, /* */; SQL/Lua-style --, --[[, ]];
# Haskell-style {-, -}) shared across one regex for all 29 "standard_block"
# languages. Since C-family languages use `--` as a decrement operator and
# `#` for preprocessor directives (not comments), a shared regex that also
# treated those as comment tokens corrupted real C/C++/Java/etc. code
# (confirmed: `i-- > 0` and `#include <vector>` both got silently swallowed
# into the comment stream). Split into dedicated families instead -- each
# language now only shares a regex with languages using compatible tokens.
LEXICAL_FAMILY_HEURISTICS = {
    "lexical_families": {
        # 1. Standard Block (Non-Recursive, C-style only)
        # The language uses both line and block delimiters, but blocks CANNOT be nested.
        # Examples: C, C++, Java, JavaScript, PHP, Go, CSS.
        "standard_block": {"delimiters": ["//", "/*", "*/"]},
        # 1b. Multi-Style Dash (#621)
        # Dash-prefixed line comments, with EITHER a C-style /* */ block
        # (SQL/sqlite) OR a doubled-bracket --[[ ]] block (Lua/Haskell).
        # Sharing both block forms across this family is intentional and low
        # risk (unlike the old standard_block sharing): neither substring is
        # a meaningful operator in any of these languages, unlike C's `--`.
        # Examples: sqlite, lua, haskell.
        "multi_style_dash": {"delimiters": ["--", "/*", "*/", "--[[", "]]"]},
        # 1c. Embedded Syntax, hash-block variant (#621)
        # Hash-prefixed line comments with a <# ... #> block form.
        # Examples: powershell.
        "embedded_syntax": {"delimiters": ["#", "<#", "#>"]},
        # 1d. Multi-Style Live (#708)
        # Line comments starting with #, --, or //, plus C-style /* */ blocks.
        # Examples: livecode.
        "multi_style_live": {"delimiters": ["#", "--", "//", "/*", "*/"]},
        # 2. Recursive Block
        # The language allows block comments to be safely nested inside one another.
        # Examples: Rust, Swift, Dart, Scala.
        "recursive_block": {"delimiters": ["//", "/*", "*/"]},
        # 2b. Recursive Block, Haskell dialect (#621)
        # Same nested-block-peeling algorithm as recursive_block, but with
        # Haskell's own line/block tokens instead of C-style ones.
        # Examples: haskell.
        "recursive_block_haskell": {"delimiters": ["--", "{-", "-}"]},
        # 2c. Recursive Block, Lisp dialect (#770)
        # Same nested-block-peeling algorithm as recursive_block, but with
        # Lisp/Scheme's own line/block tokens: ';' for line comments, '#|'/'|#'
        # for genuinely-nestable block comments (R6RS/R7RS both allow
        # `#| ... #| ... |# ... |#`). Previously scheme was misclassified as
        # "line_exclusive" -- which has no cross-line state at all -- despite
        # its own inline comment already documenting an intent for nested
        # block comments that was never wired up (#770). '#|'/'|#' are moved
        # out of line_exclusive's shared delimiter list below since scheme was
        # the only language that ever needed them there, and leaving them in
        # a stateless per-line stripper is exactly what caused the bug.
        # Examples: scheme.
        "recursive_block_lisp": {"delimiters": [";", "#|", "|#"]},
        # 3. Line Exclusive
        # The language possesses no native multi-line block syntax. The engine ignores closing tags.
        # Examples: Python, Shell, Makefile, Ruby, Perl, Assembly.
        #
        # #1193: "delimiters" below used to be the ONLY list consulted by
        # prism.py -- one shared grab-bag applied identically to all ~20
        # member languages, so `;` (only real for assembly) and `%` (only
        # real for matlab) silently truncated any line containing either
        # token -- bare or inside a string literal -- for the other 18
        # (`100 % 7`, `"SELECT 1;"`, CLI `--` separators, etc.). prism.py now
        # resolves each language's real delimiter(s) from "language_delimiters"
        # below, falling back to this top-level list only for a hypothetical
        # future line_exclusive language that doesn't have its own entry yet.
        # Per-language sets verified against each language's own real syntax
        # (assembly genuinely uses both `;` NASM/Intel and `#` GAS/ARM; m4
        # genuinely uses both `#` -- GNU M4's actual default lexer comment,
        # confirmed against real curl/gnucobol configure.ac corpus in
        # test_m4_strict.py -- and the separate macro-level `dnl`; agc_assembly
        # uses only `#`, not `;`, despite superficially resembling assembly).
        # jcl is intentionally omitted (empty list): its real comment marker
        # `//*` is a whole-line prefix, and every JCL statement line also
        # starts with bare `//`, so adding `//` here would comment out the
        # entire language -- the position-anchored form this stateless
        # per-line stripper can't express. markdown is also intentionally
        # omitted: split_streams() routes it through the prose bypass before
        # this family is ever consulted, so any entry here would be dead and
        # risk misleading a future reader (markdown's `#` is a heading
        # marker, not a comment).
        "line_exclusive": {
            "delimiters": ["#"],
            "language_delimiters": {
                "python": ["#"],
                "shell": ["#"],
                "ruby": ["#", "=begin", "=end"],
                "assembly": [";", "#"],
                "agc_assembly": ["#"],
                "perl": ["#"],
                "embedded_python": ["#"],
                "zig": ["//"],
                "dockerfile": ["#"],
                "matlab": ["%"],
                "makefile": ["#"],
                "csv": ["#"],
                "yaml": ["#"],
                "pbtxt": ["#"],
                "m4": ["#", "dnl"],
                "tcl": ["#"],
                "nix": ["#"],
                "batch": ["REM", "::"],
                "jcl": [],
            },
        },
        # 3b. Line Exclusive, Dash dialect (#76)
        # Same stateless single-token stripper as line_exclusive, but scoped
        # to its own delimiter list rather than joining the shared one above.
        # `--` cannot safely join line_exclusive's grab-bag: several of that
        # family's members (Perl, Assembly) use `--` as a real operator/
        # decrement, and #621's own history is exactly this failure mode
        # (a shared delimiter list swallowing real code, e.g. `i-- > 0`) --
        # the fix there was splitting into narrower families, not widening
        # this one. Ada/SPARK has no native block-comment form at all (unlike
        # multi_style_dash's sqlite/lua/haskell, which all pair `--` with a
        # real block form), so it gets its own single-token family instead of
        # joining multi_style_dash too.
        # Examples: ada.
        "line_exclusive_dash": {"delimiters": ["--"]},
        # 4. Block Exclusive
        # The language possesses no native single-line comment syntax. All text must be enclosed.
        # Examples: HTML, XML.
        "block_exclusive": {"delimiters": ["<!--", "-->"]},
        # 5. Positional Anchored
        # The engine must verify the token's physical column placement.
        # Examples: Legacy COBOL, Legacy Fortran.
        "positional_anchored": {"delimiters": ["*>", "!", "C", "*", "D"]},
        # 5b. Positional ABAP (#746)
        # Same as positional_anchored but also recognizes " as an inline comment.
        # Examples: ABAP.
        "positional_abap": {"delimiters": ["*>", "!", "C", "*", "D", '"']},
    }
}


# ------------------------------------------------------------------------------
# 5. EXACT FILE ROUTING (Extensionless Identifiers)
# Consumed by: language_lens.py
# ------------------------------------------------------------------------------
EXACT_FILE_MATCH = {
    # --- 1. Build Systems & Manifests ---
    "Makefile": "makefile",
    "makefile": "makefile",
    "Dockerfile": "dockerfile",
    # Safely mapped to plaintext to prevent unsupported format crashes
    "CMakeLists.txt": "plaintext",
    "package.json": "plaintext",
    "BUILD": "plaintext",
    "BUILD.bazel": "plaintext",
    "WORKSPACE": "plaintext",
    "WORKSPACE.bazel": "plaintext",
    # --- 2. Environment-Specific Text / Config Bypasses ---
    "noopt_exceptions": "plaintext",
    "noopt_exceptions_f": "plaintext",
    "configure": "shell",
    "config.status": "shell",
    # --- 3. Dependency Manifests (Text Bypasses) ---
    "requirements.txt": "plaintext",
    "pyproject.toml": "plaintext",
    "Pipfile": "plaintext",
    "tox.ini": "plaintext",
    "MANIFEST.in": "plaintext",
    # --- 4. Secrets Bypass ---
    "id_rsa": "plaintext",
    "id_dsa": "plaintext",
    "id_ed25519": "plaintext",
    "id_ecdsa": "plaintext",
    "truststore.jks": "plaintext",
    "keystore.jks": "plaintext",
    ".env": "plaintext",
    ".env.local": "plaintext",
    ".env.production": "plaintext",
    ".npmrc": "plaintext",
    ".htpasswd": "plaintext",
    ".pypirc": "plaintext",
    "credentials.json": "plaintext",
    "client_secret.json": "plaintext",
    "auth.json": "plaintext",
    "shadow": "plaintext",
}


# ------------------------------------------------------------------------------
# 6. ORCHESTRATOR RULES (Global Pipeline Constraints)
# Consumed by: galaxyscope.py
# ------------------------------------------------------------------------------
ORCHESTRATOR_RULES = {
    # Stems that are too common to count as relational popularity (The Hallucination Filter)
    "POPULARITY_STOP_STEMS": {
        # Structural stems:
        "text",
        "type",
        "index",
        "main",
        "util",
        "config",
        "core",
        "base",
        # --- STANDARD LIBRARY IGNORE LIST ---
        # Python Stdlib:
        "sys",
        "os",
        "time",
        "math",
        "re",
        "json",
        "collections",
        "datetime",
        "string",
        "pathlib",
        # C/C++ Stdlib (Often imported without extensions in modern C++):
        "stdio",
        "stdlib",
        "vector",
        "map",
        "iostream",
        "memory",
        "algorithm",
    },
}


# ------------------------------------------------------------------------------
# 7. TEMPORAL SCANNER CONFIGURATION (Temporal Scanning Limits)
# Consumed by: chronometer.py
# ------------------------------------------------------------------------------
CHRONOMETER_CONFIG = {
    # The absolute ceiling for OS-level fallback scanning
    "FALLBACK_SCAN_LIMIT": 25000,
    # Process management
    "STREAM_TIMEOUT_SECONDS": 60.0,
    # Dynamic Windowing Constraints (in seconds)
    # 10% of the project's lifespan will be used, bounded by these limits:
    "DYNAMIC_WINDOW_MIN_DAYS": 30,  # Never look at less than 1 month
    "DYNAMIC_WINDOW_MAX_DAYS": 365,  # Never look at more than 1 year
    # If the dynamic window yields zero commits, fallback to this raw volume
    "DORMANT_FALLBACK_COMMITS": 500,
}


# ------------------------------------------------------------------------------
# 8. STATIC ARCHETYPES (Static Asset Labels)
# Consumed by: signal_processor.py
# ------------------------------------------------------------------------------
# Single Source of Truth for files that bypass active ML logic processing.
STATIC_ARCHETYPES = {
    "literature": "Static: Literature & Documentation",
    "data": "Static: Declarative Data & Configurations",
    "minified": "Static: Minified & Vendor Opaque Footprint",
    "unknown": "Static: Unmapped / Unsupported Format",
}

# ------------------------------------------------------------------------------
# 9. PROJECT STORIES (Project Context Injection)
# Consumed by: gpu_recorder.py
# ------------------------------------------------------------------------------
PROJECT_STORIES: dict[str, Any] = {
    # You can add your repository-specific context and UI story payloads here later.
}

# ------------------------------------------------------------------------------
# 10. TEST NAMING CONVENTIONS (Sibling Candidates)
# Consumed by: galaxyscope.py
# ------------------------------------------------------------------------------
TEST_NAMING_CONVENTIONS = [
    # Node / Python / Ruby / Go conventions
    "{stem} test",
    "test {stem}",
    "{stem}.test",
    "{stem} spec",
    "spec {stem}",
    "{stem}.spec",
    # Java / C# / Enterprise conventions
    "{stem}test",
    "test{stem}",
    "{stem}tests",
    "{stem}testcase",
    "{stem}spec",
]
