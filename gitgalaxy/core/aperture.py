# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at [https://polyformproject.org/licenses/noncommercial/1.0.0/](https://polyformproject.org/licenses/noncommercial/1.0.0/)
# ==============================================================================
import fnmatch
import logging
import os
import re
from pathlib import Path
from typing import Any, TypedDict

from gitgalaxy.core.model_magic import MODEL_EXTENSIONS, sniff_model_format
from gitgalaxy.core.source_text import decode_bytes, open_source
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

# ==============================================================================
# GitGalaxy Phase 0.1: Ingestion & Filtering (The Aperture Filter)
# Strategy: (Monolith Ceilings, Array Shields & Intent Overrides)
# Architecture: Path Evaluation -> Intent Resolution -> Content Validation
# ==============================================================================

# --- DECLARED PORTS ---
# A deterministic COBOL-to-Java port (gitgalaxy/tools/cobol_to_java/det) opens with this line. Its
# output is machine-translated by design -- uniform indentation, long compound conditions -- so the
# generated-noise classifiers (Gates 4.1, 4.3, 5.1) would drop the very files a migrated estate is
# made of. The line is a self-declaration anyone can write; it is trusted because what it lifts are
# noise filters, never the binary, payload, size or secrets gates: a forged header only admits code
# to the scan (where every sensor reads it), it cannot hide any. Long lines stay bounded
# (DECLARED_PORT_MAX_LINE_LENGTH) for the regex engines downstream.
DET_PORT_MARKER = "// gitgalaxy-det-port:"
_DET_PORT_LINE = re.compile(r"// gitgalaxy-det-port: COBOL ([A-Z0-9#@$-]{1,30}) ")


def declared_port(content: str | None, rel_path: str) -> str | None:
    """The COBOL program a .java file declares itself a deterministic port of (its first line), or None."""
    if not content or not rel_path.lower().endswith(".java"):
        return None
    m = _DET_PORT_LINE.match(content[:200])
    return m.group(1) if m else None


# --- VIRTUALENV DETECTION (#4542) ---
# `venv` / `.venv` stay in IGNORED_DIRECTORIES by name: nobody names a source directory that.
# These names are also ordinary source directory names (room4doom's `gameplay/src/env/` holds
# 3,646 lines of doors, floors and lights; pypa/virtualenv's package is `src/virtualenv/`), so a
# directory with one of them is a virtualenv only when it carries a virtualenv's markers.
VIRTUALENV_CANDIDATE_NAMES = frozenset({"env", ".env", "virtualenv"})


def looks_like_virtualenv(directory: Path) -> bool:
    """True when `directory` carries a Python virtualenv's (or conda env's) on-disk markers."""
    try:
        if not directory.is_dir():
            return False
        if (directory / "pyvenv.cfg").is_file() or (directory / "conda-meta").is_dir():
            return True
        for activate in ("bin/activate", "Scripts/activate", "Scripts/activate.bat"):
            if (directory / activate).is_file():
                return True
        if (directory / "Lib" / "site-packages").is_dir():
            return True
        lib = directory / "lib"
        return lib.is_dir() and any(
            p.name.startswith("python") and (p / "site-packages").is_dir() for p in lib.iterdir()
        )
    except OSError:
        return False


# --- VENDORED CODE DETECTION (#4545) ---
# Vendored code is EXCLUDED from the scan, like `third_party/` and `vendor/` always were (they sit
# in IGNORED_DIRECTORIES), not flagged: every first-party metric (size, complexity tails, risk,
# SARIF) then reads first-party code only. The unambiguous spellings (`third-party`, `thirdparty`,
# `3rdparty`, `vendored`, ...) are in IGNORED_DIRECTORIES by name; an Apple `*.framework` bundle is
# excluded by its suffix. Two kinds of name are also ordinary first-party names, so they count only
# on evidence of a separate project -- a license file of its own that differs from the scan root's
# (no root license, no evidence):
#   - a container (`libraries/`, `libs/`, `deps/`, `extern(al)/`) when at least half of its
#     non-empty subdirectories carry such a license (gzdoom's `libraries/`: bzip2, cppdap, webp,
#     ZMusic, ZVulkan, ...; an Nx-style `libs/` of first-party packages carries none, or the root's);
#   - a versioned directory (`SDL2-2.32.10/`, `SDL2_mixer-2.8.2/`) carrying one itself. id's own
#     `linuxdoom-1.10/` is versioned too but has no license of its own: it stays scanned.
# The scan root itself is never a candidate: only the directories under it are tested.
# #5464: the name is no longer a precondition. Two more shapes:
#   - a `third_party_*` / `3rdparty-*` prefix is excluded by name, like `third_party/` itself
#     (a `third_party_libs/` holding 367k lines of SDL2);
#   - a container spelled `*_libs` / `*-libraries` / `*_deps` follows the container rule above;
#   - ANY other directory carrying a license of its own that differs from the root's is a separate
#     project (eternity's `libpng/`, doomretro's `src/yyjson/`).
# A first-party backend directory (srb2 `src/sdl/`) has no license of its own and stays scanned.
# #5525: "differs" ignores a title line above the same text (gson's `gson/LICENSE` = `Google Gson` + the root's Apache-2.0).
VENDOR_CONTAINER_NAMES = frozenset({"libraries", "libs", "deps", "extern", "external", "externals"})
_THIRD_PARTY_PREFIX = re.compile(r"^(?:third|3rd)[_-]?party[_-]", re.I)
_CONTAINER_SUFFIX = re.compile(r"[_-](?:libs|libraries|deps|extern|external|externals)$", re.I)
# (c) a directory named after a well-known third-party library, with no license file of its own (eternity's
# `zlib/`, doom3-bfg's `jpeg-6/`, a bundled `lzma/` or `gdtoa/`, eternity's `nlohmann/`): the name list is the
# decision (a header fingerprint needs a per-library corpus; the list is reviewable and cheap). A trailing version
# (`jpeg-6`, `zlib-1.2.11`) is dropped before the lookup. A directory that carries the ROOT's own license is the
# project's own copy of it and stays scanned.
KNOWN_LIBRARY_NAMES = frozenset(
    {
        "zlib",
        "minizip",
        "libpng",
        "lpng",
        "jpeg",
        "libjpeg",
        "lzma",
        "gdtoa",
        "nlohmann",
        "miniz",
        "yyjson",
        "bzip2",
        "libbz2",
        "freetype",
        "sqlite3",
        "cjson",
        "rapidjson",
        "tinyxml",
        "tinyxml2",
        "jsoncpp",
        "expat",
        "lz4",
        "zstd",
    }
)
_VERSION_SUFFIX = re.compile(r"[-_ ]v?\d[\w.]*$", re.I)
_LICENSE_FILE = re.compile(r"^(?:licen[cs]e|copying|unlicense)(?:[-_.][\w.-]*)?$", re.I)
_LICENSE_DIRS = frozenset({"licenses", "licences"})
_LICENSE_READ_BYTES = 262144
_LICENSE_FAMILY_CHARS = 40
_LICENSE_WINDOW_CHARS = 240


def _license_family(text: str) -> str:
    """#5464: a license's identity -- the head of its text with copyright lines dropped.

    The same license differs byte for byte by copyright holder and by the FSF's address revision (fastdoom's
    `FASTDOOM/LICENSE` is the root's GPL-2 with another address), which is no evidence of a separate project.
    """
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip(" *#/;-").lower().startswith("copyright"))
    return " ".join(body.split()).lower()[:_LICENSE_WINDOW_CHARS]


def _same_license(a: str, b: str) -> bool:
    """#5525: two family windows name one license when the head of one sits anywhere in the other.

    A module copy often carries a title line (`Google Gson`) above the root's text, or the root does; a fixed-width
    prefix compare then calls the first-party module foreign. An empty family (empty file, `licenses/` marker) only
    matches another empty one.
    """
    if not a or not b:
        return a == b
    return a[:_LICENSE_FAMILY_CHARS] in b or b[:_LICENSE_FAMILY_CHARS] in a


class VendorDirectoryDetector:
    """#4545: decides whether a directory under `root` is a vendored copy of another project."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self._cache: dict[str, bool] = {}
        self._root_licenses: frozenset[str] | None = None

    @staticmethod
    def is_container_name(name: str) -> bool:
        low = name.lower()
        return low in VENDOR_CONTAINER_NAMES or bool(_CONTAINER_SUFFIX.search(low))

    def is_vendored(self, rel_dir: str) -> bool:
        """`rel_dir` is a POSIX path relative to the root (never empty: the root is not a candidate)."""
        hit = self._cache.get(rel_dir)
        if hit is None:
            hit = self._cache[rel_dir] = self._probe(rel_dir)
        return hit

    def _probe(self, rel_dir: str) -> bool:
        name = rel_dir.rsplit("/", 1)[-1]
        if not rel_dir or name.startswith("."):
            return False
        if _THIRD_PARTY_PREFIX.match(name):
            return True
        directory = self.root.joinpath(*rel_dir.split("/"))
        try:
            if not directory.is_dir():
                return False
            low = name.lower()
            if low.endswith(".framework"):
                return True
            if self.is_container_name(name):
                children = [
                    c for c in directory.iterdir() if c.is_dir() and not c.name.startswith(".") and any(c.iterdir())
                ]
                foreign = sum(1 for c in children if self._has_foreign_license(c))
                return foreign > 0 and 2 * foreign >= len(children)
            if self._has_foreign_license(directory):
                return True
            return _VERSION_SUFFIX.sub("", low) in KNOWN_LIBRARY_NAMES and not self._has_root_license(directory)
        except OSError:
            return False

    @staticmethod
    def _license_texts(directory: Path) -> tuple[set[str], bool]:
        """Normalized texts of the license files directly in `directory`, and whether it has a licenses/ dir."""
        texts: set[str] = set()
        has_dir = False
        for entry in directory.iterdir():
            if entry.is_dir():
                has_dir = has_dir or entry.name.lower() in _LICENSE_DIRS
            elif _LICENSE_FILE.match(entry.name):
                try:
                    with open(entry, "rb") as fh:
                        raw = fh.read(_LICENSE_READ_BYTES)
                except OSError:
                    continue
                texts.add(_license_family(raw.decode("utf-8", "ignore")))
        return texts, has_dir

    def _root_license_set(self) -> frozenset[str]:
        if self._root_licenses is None:
            try:
                root_texts, root_dir = self._license_texts(self.root)
            except OSError:
                root_texts, root_dir = set(), False
            # a root with only a licenses/ directory still declares a license of its own
            self._root_licenses = frozenset(root_texts | ({""} if root_dir else set()))
        return self._root_licenses

    def _has_root_license(self, directory: Path) -> bool:
        texts, _ = self._license_texts(directory)
        roots = self._root_license_set()
        return any(_same_license(t, r) for t in texts for r in roots)

    def _has_foreign_license(self, directory: Path) -> bool:
        root_licenses = self._root_license_set()
        if not root_licenses:
            return False
        texts, has_dir = self._license_texts(directory)
        return has_dir or any(not any(_same_license(t, r) for r in root_licenses) for t in texts)


# --- COMMENT LINES IN THE SATURATION GATE (#4543) ---
# Gate 4.1 blocks a file whose head carries a line longer than MAX_LINE_LENGTH: minifier output
# and data payloads. A long line that is wholly a comment in the file's own syntax is neither (a
# 684-char paragraph inside crispy-doom's hexen p_map.c block comment, room4doom's `//!` module
# docs), so it does not count -- up to MAX_COMMENT_LINE_LENGTH, and only while it reads as prose
# (spaced words, not a base64 / inline source-map blob).
# family -> (line comment tokens, block comment (open, close) pairs)
_FAMILY_COMMENT_SYNTAX: dict[str, tuple[tuple[str, ...], tuple[tuple[str, str], ...]]] = {
    "standard_block": (("//",), (("/*", "*/"),)),
    "recursive_block": (("//",), (("/*", "*/"),)),
    "recursive_block_rexx": (("--",), (("/*", "*/"),)),
    "multi_style_dash": (("--",), (("/*", "*/"),)),
    "multi_style_live": (("#", "--", "//"), (("/*", "*/"),)),
    "embedded_syntax": (("#",), (("<#", "#>"),)),
    "recursive_block_haskell": (("--",), (("{-", "-}"),)),
    "recursive_block_lisp": ((";",), (("#|", "|#"),)),
    "line_exclusive_dash": (("--",), ()),
    "block_exclusive": ((), (("<!--", "-->"),)),
}
# A prose comment has a space at least this often (characters per space).
_PROSE_CHARS_PER_SPACE = 30


# --- CUSTOM EXCEPTION HIERARCHY ---


# #4126: a block reason a caller can act on without matching its wording. The Binary Analysis
# Sensor used to test the reason text for "Blacklisted Extension", and a rename of Gate 1.3's
# message (3477c48cc) silently disconnected it. A reason now carries its gate as `.kind`; the text
# stays a plain str for every log, report and SARIF consumer.
DENIED_EXTENSION = "denied_extension"


# #4548: armor headers of material that is public by construction. A file is exempt from the
# extension-based secrets shunt only when its content carries one of these AND no PRIVATE marker.
_PUBLIC_ARMOR = re.compile(
    rb"-----BEGIN (?:PGP PUBLIC KEY BLOCK|PUBLIC KEY|RSA PUBLIC KEY|(?:TRUSTED |X509 )?CERTIFICATE|CERTIFICATE REQUEST|PGP SIGNATURE)-----"
)


# #4987: scan cap for a key/cert-named file, and the extensions whose binary (DER) form can be a public
# certificate. `.p12` / `.pfx` (PKCS#12) always bundle a private key, so they never qualify.
_PUBLIC_SCAN_CAP = 8 * 1024 * 1024
_PUBLIC_SCAN_CHUNK = 1024 * 1024
_PUBLIC_SCAN_OVERLAP = 64
_DER_CERT_EXTENSIONS = frozenset({".cer", ".crt", ".der", ".p7b"})
_PKCS7_SIGNED_DATA_OID = bytes.fromhex("06092a864886f70d010702")
_PKCS12_OID = bytes.fromhex("2a864886f70d010c")  # 1.2.840.113549.1.12 (PKCS#12 and its bag types)


def _der_seq_body(buf: bytes, pos: int) -> int | None:
    """Offset just past the header of a DER SEQUENCE at `pos`, or None when it is not one."""
    if pos + 2 > len(buf) or buf[pos] != 0x30:
        return None
    first = buf[pos + 1]
    if first < 0x80:
        return pos + 2
    n = first & 0x7F
    return pos + 2 + n if 1 <= n <= 4 and pos + 2 + n <= len(buf) else None


def _is_der_public_certificate(head: bytes) -> bool:
    """A binary X.509 certificate (SEQUENCE { SEQUENCE tbsCertificate ... }) or a PKCS#7 signedData bundle.
    A PKCS#8 key opens SEQUENCE { INTEGER 0 ... } (encrypted: SEQUENCE { SEQUENCE { OID ... } ... }); a PKCS#12 carries OID 1.2.840.113549.1.12. Neither qualifies."""
    if _PKCS12_OID in head:
        return False
    body = _der_seq_body(head, 0)
    if body is None:
        return False
    if head.startswith(_PKCS7_SIGNED_DATA_OID, body):
        return True
    # tbsCertificate opens with the v3 `[0]` version (0xA0) or, for a v1 cert, the serial INTEGER (0x02). An
    # encrypted PKCS#8 key is SEQUENCE { SEQUENCE { AlgorithmIdentifier OID ... } OCTET STRING }: its inner
    # SEQUENCE opens with an OID (0x06), so it is not cleared.
    inner = _der_seq_body(head, body)
    return inner is not None and inner < len(head) and head[inner] in (0xA0, 0x02)


_AR_MAGIC = b"!<arch>\n"


def _is_ar_archive(path_obj: Path) -> bool:
    """True for a `.a` file that opens with the `ar` magic (#5624). One 8-byte read, `.a` only."""
    if path_obj.suffix != ".a":
        return False
    try:
        with open(path_obj, "rb") as fh:
            return fh.read(len(_AR_MAGIC)) == _AR_MAGIC
    except OSError:
        return False


def _is_public_key_material(path_obj: Path) -> bool:
    """True when a key/cert-named file holds only public material. The file is read in bounded chunks (8 MB
    cap, overlapped so a marker cannot straddle a boundary): armor text counts only with no PRIVATE marker
    anywhere. A cert-named binary DER file counts when it parses as a certificate. A file past the cap, or a
    shape not recognised, stays a leak candidate (#4987)."""
    try:
        with open(path_obj, "rb") as fh:
            head = window = fh.read(_PUBLIC_SCAN_CHUNK)
            total, armor = len(head), False
            while True:
                if b"PRIVATE" in window.upper():
                    return False
                armor = armor or bool(_PUBLIC_ARMOR.search(window))
                chunk = fh.read(_PUBLIC_SCAN_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > _PUBLIC_SCAN_CAP:
                    return False
                window = window[-_PUBLIC_SCAN_OVERLAP:] + chunk
    except OSError:
        return False
    if armor:
        return True
    return path_obj.suffix.lower() in _DER_CERT_EXTENSIONS and _is_der_public_certificate(head)


class ApertureReason(str):
    """A block reason (a str) that also names the gate that produced it."""

    kind: str

    def __new__(cls, text: str, kind: str = "") -> "ApertureReason":
        obj = super().__new__(cls, text)
        obj.kind = kind
        return obj

    def __reduce__(self) -> tuple[Any, ...]:
        # survive the ProcessPoolExecutor's pickling with the kind intact
        return (ApertureReason, (str(self), self.kind))


class ApertureError(Exception):
    """Base class for all errors generated by the Aperture filtering process."""

    pass


class InaccessibleArtifactError(ApertureError):
    """Raised when an artifact cannot be accessed due to OS permissions or path corruption."""

    pass


class SaturationError(ApertureError):
    """Raised when a signal is too dense or minified to be safely evaluated by the engine."""

    pass


class FilterResult(TypedDict):
    """Structured telemetry returned by the Filter for the Pipeline Orchestrator."""

    is_in_scope: bool
    classification: str  # e.g., 'source_code', 'binary_payload', 'generated_noise'
    reason: str | None
    path: str
    size_bytes: int
    total_loc: int


class ApertureFilter:
    """
    Primary ingestion filter for the analysis engine. Performs perimeter gating to ensure
    only valid, maintainable source code reaches the CPU-bound Structural Signature extractors.
    Integrates with GuideStar's Bayesian 'Contextual Baselines' to dynamically adjust suppression
    thresholds for known, high-priority artifacts (like package.json).
    """

    def __init__(
        self,
        root_dir: str | Path,
        language_definitions: dict[str, Any],
        aperture_config: dict[str, Any],
        parent_logger: logging.Logger | None = None,
    ):
        # --- TELEMETRY SYNC ---
        if parent_logger:
            self.logger = parent_logger.getChild("filter")
            self.logger.setLevel(parent_logger.level)
        else:
            self.logger = logging.getLogger("filter")
            self.logger.setLevel(logging.INFO)

        self.root = Path(root_dir).resolve()
        self.registry = language_definitions
        self.config = aperture_config or {}

        self.ignored_directories = {d.lower() for d in self.config.get("IGNORED_DIRECTORIES", set())}
        self.ignored_extensions = set(self.config.get("IGNORED_EXTENSIONS", set()))
        self.denylist_patterns = self.config.get("CONTRABAND_PATTERNS", [])

        # ---> AUTO-GENERATED DOC SHIELD <---
        # DEFENSIVE DESIGN: Parsers waste massive compute on Doxygen/Sphinx HTML dumps.
        # This regex identifies the exact generator signatures.
        self.doc_generator_pattern = re.compile(
            r'<meta\s+name=["\']generator["\']\s+content=["\'](?:jazzy|Doxygen|Sphinx|JSDoc|TypeDoc|appledoc|Docco|MkDocs|Hugo|DocFX|Docgen).*?["\']'
        )

        # ---> MACHINE-GENERATED SOURCE SHIELD <---
        # Identifies source code generated by external transpilers or ORMs.
        # #4559: match generator BANNERS, not prose. The old unanchored `generated by \S+` dropped
        # hand-written room4doom wgpu.rs for a doc comment saying thresholds "are generated by
        # `surface_wgsl`". A banner is a line whose text, after comment syntax and whitespace, BEGINS
        # with the marker (Go `// Code generated ... DO NOT EDIT.`, protoc, thrift, flatc, SWIG,
        # bison/flex, `@generated`, "This file is (auto-)generated"), or the structural
        # `<auto-generated>` tag / an upper-case `DO NOT EDIT` banner anywhere on a line.
        self.machine_gen_pattern = re.compile(
            r"(?i)^(?:"
            r"@generated\b"
            r"|(?:code\s+)?(?:auto-?|automatically\s+)?generated\s+by\s+\S"
            r"|auto-?generated\b|automatically\s+generated\b"
            r"|do\s+not\s+edit\b"
            r"|this\s+(?:file|code|source)\s+(?:is|was)\s+(?:auto-?|automatically\s+)generated\b"
            r"|this\s+(?:file|code|source)\s+(?:is|was)\s+generated\s+by\s+\S"
            r"|this\s+file\s+is\s+generated\b"
            r"|this\s+is\s+an?\s+(?:auto-?|automatically\s+)?generated\b"
            r"|a\s+bison\s+parser\b|a\s+lexical\s+scanner\s+generated\s+by\s+flex\b"
            r")"
        )
        self._machine_gen_anywhere = re.compile(r"(?i)<auto-generated>")
        self._machine_gen_shout = re.compile(r"\bDO NOT EDIT\b")

        # ---> SEMANTIC PATH SHIELD <---
        # #3278: CI configuration is real, hand-written source (GitHub Actions / GitLab CI
        # / CircleCI / Buildkite pipelines carry the repo's build and release logic), but it
        # lives under dot-directories, and the hidden-path gate in _check_ignore_rules
        # blocked every one of them -- `.github/workflows/*.yml` never reached the yaml
        # surface in any real repo. These trees, and the dot-named files inside them
        # (moby's reusable `.github/workflows/.test.yml`), are exempt; every other hidden
        # path stays blocked. The two root-level CI dotfiles are exempt by name.
        self._CI_CONFIG_DIRS = frozenset({".github", ".gitlab", ".circleci", ".buildkite"})
        self._CI_CONFIG_FILES = frozenset({".gitlab-ci.yml", ".travis.yml"})

        # SQL DDL/DML is already treated as its own data-shaped format elsewhere in this
        # file (Gate 3.3's size-tiered Static Asset Bloat Deflector, Gate 4.1's `is_prose`
        # minification exemption) -- unlike compiled JS bundles or generated protobuf
        # bindings, a SQL schema/migration file with "generated"/"scripts" as a real,
        # common path segment (MediaWiki's generateSchemaChangeSql.php convention,
        # SQLite's own `sqlite_cli_scripts/`) is almost always canonical, committed,
        # hand-reviewed content -- exactly the DDL/DML GalaxyScope's legacy-modernization
        # use case exists to scan, not vendor noise. Confirmed case (#2512): 45% of
        # language-crucible's sqlite corpus was silently dropped by the (since removed,
        # #3278) path-word shield and the Gate 4.3 machine-generated-content sensor
        # below, both keyed off conventions that are false signals for this format.
        self._SQL_DDL_EXTENSIONS = frozenset({".sql", ".ddl", ".dml"})
        # #4365: COBOL copy members -- copybooks and DCLGEN output (see Gate 4.3)
        self._COPY_MEMBER_EXTENSIONS = (".cpy", ".copy", ".dcl")

        # --- STATE CACHE & DYNAMIC STATE ---
        self._intent_cache: set[str] = set()
        self._generated_docs_dir_cache: dict[str, bool] = {}
        self._source_dir_cache: dict[str, bool] = {}

        self.logger.debug(f"Initializing Aperture Filter for project: '{self.root.name}'...")

        # Optimized Lookup Construction
        self.whitelisted_extensions: set[str] = set()
        self.exact_match_files: set[str] = set()

        for data in self.registry.values():
            self.whitelisted_extensions.update(data.get("extensions", []))
            self.exact_match_files.update(data.get("exact_matches", []))

        # #4542: candidate-named directories (rel path -> is it a virtualenv), probed once each.
        self._virtualenv_cache: dict[str, bool] = {}
        # #4545: vendored copies of other projects under non-reserved names.
        self._vendor_dirs = VendorDirectoryDetector(self.root)
        # #4543: extension -> the comment syntax every language claiming it agrees on.
        self._comment_syntax = self._build_comment_syntax()

        self.ignore_patterns = self._load_gitignore_patterns()

        self.logger.info(f"Aperture Filter Online | Tracking {len(self.whitelisted_extensions)} valid extensions.")

    def evaluate_path_integrity(self, file_path: str | Path, has_intent: bool = False) -> tuple[bool, int, str]:
        """
        [GATE 1: Perimeter Gating (Zero-I/O Path Evaluation)]
        Performs high-speed path analysis to build the initial File Census.

        DEFENSIVE DESIGN: We determine if a file is physically valid based on OS metadata
        *before* any disk I/O (file opening/reading) occurs. All operations here are fast
        string matching to prevent unnecessary disk reads and drastically reduce Memory/CPU
        overhead on large monolithic repositories.
        """
        path_obj = Path(file_path)
        normalized_path = path_obj.as_posix()
        _, ext = os.path.splitext(path_obj.name)

        try:
            relative_path = path_obj.relative_to(self.root).as_posix()
        except ValueError:
            relative_path = normalized_path

        try:
            size_bytes = path_obj.stat().st_size if path_obj.exists() else 0
        except OSError:
            size_bytes = 0

        # --- Gate 1.1: Credential Exposure Radar ---
        # #4548: the extension only nominates a candidate (as the model gate below does). A key/cert
        # file whose content proves it is PUBLIC material -- a PGP public key block, a certificate,
        # a public key -- is published on purpose, not a leaked credential.
        secrets_exact = path_obj.name in self.config.get("SECRETS_EXACT", set())
        secrets_ext = ext.lower() in self.config.get("SECRETS_EXTENSIONS", set())
        if secrets_exact or (secrets_ext and not _is_public_key_material(path_obj)):
            reason = f"CRITICAL LEAK (Exposed Secret: '{path_obj.name}')"
            return False, size_bytes, reason

        # --- Gate 1.2: Model Weight Shunt ---
        # #4138: the extension only nominates a candidate; the header has to prove
        # the format (model_magic.py: one bounded head read, never the whole file).
        # A `.pb`/`.bin`/`.onnx` that is ordinary protobuf or binary data falls
        # through to the gates below instead of becoming a "local model" -- and an
        # `llm_local_compute` hit -- on its name alone.
        if ext.lower() in MODEL_EXTENSIONS:
            model_format = sniff_model_format(path_obj, size_bytes)
            if model_format:
                reason = f"AI MODEL WEIGHTS (Bypassing Standard Logic: '{ext}', {model_format} header)"
                self.logger.info(f"NEURAL SHUNT: Routing {path_obj.name} away from standard regex engines.")
                return False, size_bytes, reason
            self.logger.debug(f"NEURAL SHUNT: {path_obj.name} has a model extension but no model header.")

        # --- Gate 1.2.5: Absolute Mass Ceiling (Zero-I/O Memory Backstop) ---
        # DEFENSIVE DESIGN: Checked here, before the file is ever opened for
        # reading, using the os.stat() size already gathered above. This is an
        # unconditional, Intent-blind physical safety net against truly extreme
        # artifacts (multi-GB dumps) -- distinct from the *soft* MAX_FILE_SIZE_MB
        # ceiling in is_in_scope(), which content-based classification and an
        # Intent Lock can override. Nothing overrides this one.
        hard_max_mb = self.config.get("MAX_FILE_SIZE_HARD_MB", 250)
        if size_bytes > (hard_max_mb * 1024 * 1024):
            reason = f"Blocked (File size exceeds absolute {hard_max_mb}MB safety ceiling)"
            return False, size_bytes, reason

        # --- Gate 1.3: Explicit Extension Firewall ---
        # #5624: `.a` is also assembly source (a language now claims it, which lifts the denial), so a
        # static-library archive is recognised by its `ar` magic rather than by the extension alone.
        if (
            ext.lower() in self.ignored_extensions and ext.lower() not in self.whitelisted_extensions
        ) or _is_ar_archive(path_obj):
            reason = ApertureReason(f"Blocked (Explicitly Denied Extension: '{ext}')", DENIED_EXTENSION)
            return False, size_bytes, reason

        # Establish Intent Lock
        active_intent = has_intent or (normalized_path in self._intent_cache)
        if active_intent:
            self._intent_cache.add(normalized_path)

        # --- Gate 1.4: Ecosystem Ignore Resolver (.gitignore, node_modules, etc.) ---
        if not self._check_ignore_rules(relative_path, has_intent=active_intent):
            reason = "Blocked (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)"
            return False, size_bytes, reason

        # --- Gate 1.5: Language Registry Validation ---
        if active_intent:
            return True, size_bytes, "Passed (GuideStar Intent Lock)"

        if not ext:
            return True, size_bytes, "Passed (Extensionless -> Subject to Shebang scan)"

        if path_obj.name in self.exact_match_files or ext.lower() in self.whitelisted_extensions:
            return True, size_bytes, "Passed (Whitelisted)"

        # #2555: defensive -- never emit a malformed extension into user-facing text.
        # The census is now dequoted upstream (git ls-files -z), but any path that
        # reaches here carrying stray bytes (a quotepath artifact, a non-git census
        # path) must not leak e.g. a trailing `"` into the reason. Mirror the REGEX
        # SHIELD used by galaxyscope's anomaly summarizer.
        safe_ext = ext if re.match(r"^\.[a-z0-9_\-+]+$", ext.lower()) else "no_extension"
        reason = f"Blocked (Unsupported Extension: '{safe_ext}')"
        return False, size_bytes, reason

    def is_in_scope(
        self,
        file_path: str | Path,
        content: str | None = None,
        has_intent: bool = False,
    ) -> FilterResult:
        """
        [GATE 2: Physical Mass Gating (OS Metadata)]
        The final Content Gate. Validates the physical matter of the artifact
        to ensure it is not binary, minified, or auto-generated debris.
        """
        path_obj = Path(file_path)
        normalized_path = path_obj.as_posix()
        relative_path = (
            path_obj.relative_to(self.root).as_posix() if path_obj.is_relative_to(self.root) else normalized_path
        )
        active_intent = has_intent or (normalized_path in self._intent_cache)

        result: FilterResult = {
            "is_in_scope": False,
            "classification": "source_code",
            "reason": None,
            "path": normalized_path,
            "size_bytes": 0,
            "total_loc": 0,
        }

        try:
            if not path_obj.exists():
                raise InaccessibleArtifactError("Artifact missing on disk")

            stats = path_obj.stat()
            result["size_bytes"] = stats.st_size

            # --- Gate 2.1: Mass Saturation Limit (Soft Ceiling) ---
            # DEFENSIVE DESIGN: Above this size, raw byte count alone no longer decides
            # exclusion -- the content-based classifiers below (binary/minified/monotony/
            # array shields) are usually a better judge of "is this actual noise" than a
            # blunt threshold, so an Intent-Locked file (GuideStar-recognized as
            # important) is allowed through to them. The absolute, Intent-blind backstop
            # against truly extreme artifacts lives in evaluate_path_integrity (Gate
            # 1.2.5), checked before any disk read even happens.
            soft_max_mb = self.config.get("MAX_FILE_SIZE_MB", 50)
            if stats.st_size > (soft_max_mb * 1024 * 1024) and not active_intent:
                result.update(
                    {
                        "classification": "oversized_minified",
                        "reason": f"Blocked (File size exceeds {soft_max_mb}MB limit without Intent Lock)",
                    }
                )
                self.logger.warning(f"Aperture excluded {relative_path}: {result['reason']}")
                return result

            # --- Gate 1 & 2 Execution: PATH VALIDATION ---
            is_valid, _size_bytes, reason = self.evaluate_path_integrity(path_obj, has_intent=active_intent)

            if not is_valid:
                result.update({"classification": "generated_noise", "reason": reason})
                self._log_exclusion(relative_path, result["reason"])
                return result

            # --- THE SHUNT: SECRETS BYPASS ---
            if reason and "CRITICAL LEAK" in reason:
                result.update(
                    {
                        "is_in_scope": True,
                        "classification": "source_code",
                        "reason": reason,
                        "total_loc": len(content.splitlines()) if content else 0,
                    }
                )
                return result

            # --- CONTENT VALIDATION ---
            if content is None:
                result["reason"] = "Protocol Violation: Missing content buffer"
                self.logger.warning(f"Aperture excluded {relative_path}: {result['reason']}")
                return result

            integrity = self._check_artifact_integrity(
                content, relative_path, has_intent=active_intent, port=declared_port(content, relative_path) is not None
            )
            result["total_loc"] = integrity["loc"]

            if not integrity["valid"]:
                result.update({"classification": integrity["classification"], "reason": integrity["reason"]})
                self._log_exclusion(relative_path, result["reason"])
                return result

            # --- MISSION SUCCESS ---
            result["is_in_scope"] = True
            return result

        except Exception as e:
            self.logger.error(f"Filter Collision on '{relative_path}': {e!s}")
            result["reason"] = f"Internal Exception: {e!s}"
            return result

    def _check_artifact_integrity(
        self, content: str, rel_path: str, has_intent: bool = False, port: bool = False
    ) -> dict[str, Any]:
        """
        Deep-scans the content buffer for corruption, binary data, arrays,
        or documentation generator signatures.

        `port`: the file declares itself a deterministic port (declared_port): the generated-noise
        gates (4.1 up to DECLARED_PORT_MAX_LINE_LENGTH, 4.3, 5.1) admit it; every other gate stands.
        """
        report = {
            "valid": True,
            "classification": "source_code",
            "reason": None,
            "loc": 0,
        }

        # ==============================================================================
        # Gate 3: Raw Buffer Gating (C-Backed String Operations)
        # DEFENSIVE DESIGN: Allocating a massive array of strings via splitlines() is an
        # O(N) memory operation that will crash the worker if the file is a 50MB compiled binary.
        # We delay line splitting and use highly optimized C-backed string methods first.
        # ==============================================================================

        # Fast line count estimation using C-backed count
        loc = content.count("\n") + 1
        report["loc"] = loc

        # --- Gate 3.1: Opaque Binary Sensor ---
        # DEFENSIVE DESIGN: Checking for a null byte is the fastest, most reliable
        # heuristic to identify compiled binaries masquerading as text files.
        # #3491: by DENSITY, not presence. Mainframe source transferred out of EBCDIC
        # can carry a stray NUL (navikt/DSF: 29 PL/I programs with exactly 2 NULs in
        # 15-318 KB of text were dropped whole). Every binary in the pinned crucible
        # carries 178+ NULs per 1000 characters (tar, .mat); text damaged in transfer
        # carries a handful. More than 1 per 1000 is binary.
        # #4351: ... unless the member is short and the NULs are a handful: a 168-byte PL/I member
        # with 2 NULs at the end of a comment (estate-crucible NULREST.pli, H-0037) is 12 per 1000.
        # At most _STRAY_NULS NULs, with no more than as many other control characters, is
        # transfer damage in text, whatever the size; a binary carries control bytes beyond its NULs.
        nuls = content.count("\x00") if "\x00" in content else 0
        if nuls and nuls * 1000 > len(content) and not self._stray_nuls(content, nuls):
            report.update(
                {
                    "valid": False,
                    "classification": "binary_payload",
                    "reason": "Blocked (Binary Format Detected)",
                }
            )
            return report

        # --- Gate 3.2: Monolith Amalgamation Shield ---
        # DEFENSIVE DESIGN: a file past MAX_FILE_LOC is an amalgamation (sqlite3.c is ~250k lines).
        # #5459: the cut was 30,000, which dropped whole single-file engines (gore doom.go, 43,874 lines;
        # PureDOOM.h, 48,604). Both extract in under 10 s; the regex backtracking risk is bounded by the
        # per-file ReDoS fuse (galaxyscope SIGALRM), not by a line count, so the cut is only a backstop.
        max_loc = self.config.get("MAX_FILE_LOC", 150000)
        if loc > max_loc:
            report.update(
                {
                    "valid": False,
                    "classification": "oversized_minified",
                    "reason": f"Blocked (Monolithic Amalgamation: {loc} LOC exceeds the {max_loc} LOC backstop)",
                }
            )
            return report

        low_path = rel_path.lower()

        # --- Gate 3.3: Static Asset Bloat Deflector ---
        # DEFENSIVE DESIGN: Static Assets contain zero executable payload. If they exceed
        # a few thousand lines, they are data dumps, not configuration files.
        # #4917: CI workflows and pipeline definitions are executable code, not static blobs.
        if low_path.endswith(
            (".yml", ".yaml", ".json", ".xml", ".svg", ".sql", ".csv", ".tsv")
        ) and not self._is_pipeline_config(rel_path, content):
            if loc > 2500:
                report.update(
                    {
                        "valid": False,
                        "classification": "generated_noise",
                        "reason": f"Blocked (Massive Static Asset Blob: {loc} LOC)",
                    }
                )
                return report
            elif not has_intent and loc > 1000 and not (low_path.endswith(".sql") and self._has_sql_structure(content)):
                report.update(
                    {
                        "valid": False,
                        "classification": "generated_noise",
                        "reason": f"Blocked (Static Asset Blob without Intent: {loc} LOC)",
                    }
                )
                return report

        # --- Gate 3.4: Embedded Matrix Shield ---
        # DEFENSIVE DESIGN: Massive comma-separated arrays or hex blobs (like embedded images
        # inside C++ headers) contain 0 executable payload, but will completely stall a structural parser.
        # #5460: ... unless the file also holds function definitions (`tables.c`, `aes_prng.c`:
        # hand-written code beside a constant table); a pure table has none and is still blocked.
        if loc > 500:
            hex_count = content.count("0x") + content.count("0X")
            comma_count = content.count(",")
            if (hex_count > loc or comma_count > (loc * 3)) and self._has_definitions(content.splitlines()):
                hex_count = comma_count = 0
            if hex_count > loc:
                report.update(
                    {
                        "valid": False,
                        "classification": "binary_payload",
                        "reason": f"Blocked (Embedded Hex Payload: {hex_count} hex tokens in {loc} LOC)",
                    }
                )
                return report

            if comma_count > (loc * 3):
                report.update(
                    {
                        "valid": False,
                        "classification": "binary_payload",
                        "reason": f"Blocked (Embedded Array/Matrix Payload: {comma_count} commas in {loc} LOC)",
                    }
                )
                return report

        # ==============================================================================
        # Gate 4: Header & Signature Gating (Shallow Regex)
        # DEFENSIVE DESIGN: The file has survived the binary and mass structural checks.
        # It is now safe to allocate memory for the line array. We slice the file into
        # lines, but limit expensive regex operations to the first 100 lines (the header).
        # ==============================================================================
        lines_list = content.splitlines()

        # --- Gate 4.1: Minification & Saturation Gate ---
        # DEFENSIVE DESIGN: Code minifiers remove newlines, creating ultra-long strings
        # that cause regex engines to hang (ReDoS). We check the first 100 lines for length.
        max_line = self.config.get("MAX_LINE_LENGTH", 500)
        if port:
            max_line = self.config.get("DECLARED_PORT_MAX_LINE_LENGTH", 5000)
        is_prose = low_path.endswith((".md", ".markdown", ".txt", ".json", ".csv", ".rst", ".sql", ".svg"))

        head = lines_list[:100]
        long_lines = [i for i, line in enumerate(head) if len(line) > max_line] if not is_prose else []
        if long_lines:
            # #4543: a long line that is wholly a prose comment is not minifier output or a payload.
            syntax = self._comment_syntax.get(os.path.splitext(low_path)[1])
            if syntax:
                comment = self._comment_lines(head, syntax)
                max_comment = self.config.get("MAX_COMMENT_LINE_LENGTH", 5000)
                long_lines = [
                    i
                    for i in long_lines
                    if not (i in comment and len(head[i]) <= max_comment and self._reads_as_prose(head[i]))
                ]
        # #5460: a long line beside real definitions is a data row (`sound.h`), not minifier output.
        if long_lines and self._has_definitions(lines_list):
            long_lines = []
        if long_lines:
            report.update(
                {
                    "valid": False,
                    "classification": "oversized_minified",
                    "reason": f"Blocked (Saturation: Line {long_lines[0] + 1} exceeds {max_line} chars)",
                }
            )
            return report

        head_sample = "\n".join(lines_list[:100])

        # --- Gate 4.2: Auto-Generated Documentation Shield ---
        # #5458: this blocks the one file only. Whether its directory is generated output is a
        # separate, order-independent verdict from the directory's own listing (_is_generated_docs_dir).
        if low_path.endswith((".html", ".htm", ".xml")) and self.doc_generator_pattern.search(head_sample):
            report.update(
                {
                    "valid": False,
                    "classification": "generated_noise",
                    "reason": "Blocked (Machine-Generated Documentation Signature)",
                }
            )
            return report

        # --- Gate 4.3: Machine-Generated Source Sensor ---
        # SQL DDL/DML is exempt -- see _SQL_DDL_EXTENSIONS' own comment (#2512). Gate 3.3
        # above already runs its own size-tiered noise gate for this exact extension set;
        # this gate's blunt "any generator-signature comment blocks it" is redundant at
        # best and wrong at worst for a format where "generated by a migration tool" means
        # canonical and committed (MediaWiki's abstractSchemaChanges, Prisma migrations),
        # not vendor/transpiler noise.
        # #4365: a COBOL copybook (or DCLGEN member) is exempt too. It is text the compiler pastes into
        # a program, and its generator comment says how it was made -- `SYMBOLIC MAP FOR MAPSET CUSTMS
        # -- GENERATED BY BMS ASSEMBLY`, DCLGEN's banner -- not that it is vendor noise. Excluded, the
        # member vanished: `COPY CUSTMS` lost its record layout and resolved to the .bms mapset.
        if (
            not low_path.endswith(tuple(self._SQL_DDL_EXTENSIONS))
            and not low_path.endswith(self._COPY_MEMBER_EXTENSIONS)
            and self._has_generator_banner(lines_list[:100])
            and (not has_intent or loc > 1000)
            and not port
        ):
            report.update(
                {
                    "valid": False,
                    "classification": "generated_noise",
                    "reason": f"Blocked (Machine-Generated Source Code Signature: {loc} LOC)",
                }
            )
            return report

        # ==============================================================================
        # Gate 5: Deep Structural Gating (Python Iteration)
        # DEFENSIVE DESIGN: This calculates indentation frequencies to detect highly repetitive,
        # machine-generated code. Because it requires a Python `for` loop and string stripping,
        # it is the most computationally expensive check and sits at the absolute bottom of the funnel.
        # ==============================================================================

        # --- Gate 5.1: Lexical Monotony Sensor ---
        # Fixed-format mainframe source (COBOL, PL/I #2502) is uniformly indented by
        # construction, which this indentation-frequency sensor reads as machine output.
        if (
            loc > 2000
            and not has_intent
            and not port
            and not low_path.endswith((".cpy", ".cbl", ".cob", ".pli", ".pl1"))
        ):
            sample_lines = lines_list[:500]
            meaningful_lines = [l for l in sample_lines if l.strip()]

            if len(meaningful_lines) > 100:
                indent_counts: dict[int, int] = {}
                for l in meaningful_lines:
                    indent = len(l) - len(l.lstrip())
                    indent_counts[indent] = indent_counts.get(indent, 0) + 1

                max_indent_freq = max(indent_counts.values())
                # #5460 (owner ruling 2026-10-19): a file with at least one named function definition
                # is source, not generated noise (tables.c).
                if (max_indent_freq / len(meaningful_lines)) > 0.85 and not self._has_definitions(lines_list):
                    report.update(
                        {
                            "valid": False,
                            "classification": "generated_noise",
                            "reason": f"Blocked (Lexical Monotony: High structural repetition detected in {loc} LOC)",
                        }
                    )
                    return report

        return report

    # #5460: a definition is a body-opening `{` (`...) {` or a lone `{`) whose argument list closes
    # just before it and whose head -- `[type] name(` within _DEF_SPAN lines above -- reads as a
    # declaration. Every quantifier is bounded and a line over _DEF_LINE_MAX is skipped, so the
    # check is linear and cannot backtrack on minified or packed input.
    _DEF_LINE_MAX = 200
    _DEF_SPAN = 8
    _DEF_HEAD = re.compile(r"^[ \t]{0,8}([A-Za-z_~][\w:<>~*&]{0,60})(?:[ \t*&]+[\w:<>~*&]{1,60}){0,5}[ \t]{0,4}\(")
    _DEF_NAME_ONLY = re.compile(r"^[A-Za-z_][\w:~]{0,60}[ \t]{0,4}$")
    _DEF_NOT = frozenset({"if", "for", "while", "switch", "return", "else", "do", "sizeof", "typedef", "case", "goto"})

    @classmethod
    def _has_definitions(cls, lines: list[str], need: int = 1) -> bool:
        """#5460: True when the file carries `need` function definitions outside any data table.

        The payload guards (3.4 hex and array, 4.1 saturation, 5.1 monotony) read counts that a
        hand-written file with a large constant table next to its functions also trips; a file
        with a definition is source and is scanned, a pure table has none and is still excluded.
        """
        n = len(lines)
        found = 0
        prev = -1  # index of the last non-blank line before i
        for i, raw in enumerate(lines):
            if len(raw) > cls._DEF_LINE_MAX:
                prev = i
                continue
            text = raw.strip()
            if not text:
                continue
            # GNU / id style: the name alone at column 0, its argument list on the next line.
            if (
                i + 1 < n
                and cls._DEF_NAME_ONLY.match(raw)
                and lines[i + 1].lstrip().startswith("(")
                and text not in cls._DEF_NOT
            ):
                found += 1
                if found >= need:
                    return True
            close = -1
            if text == "{" and prev >= 0 and lines[prev].rstrip().endswith(")"):
                close = prev
            elif text.endswith("{") and ")" in text:
                close = i
            prev = i
            if close < 0:
                continue
            for j in range(close, max(close - cls._DEF_SPAN, 0) - 1, -1):
                line = lines[j]
                if len(line) > cls._DEF_LINE_MAX or ";" in line or "=" in line.split("(", 1)[0]:
                    break
                m = cls._DEF_HEAD.match(line)
                if m:
                    if m.group(1) not in cls._DEF_NOT:
                        found += 1
                        if found >= need:
                            return True
                    break
        return False

    # #4351: the most NULs (and, separately, other C0 control characters) a member may carry and
    # still be text damaged in transfer rather than a binary.
    _STRAY_NULS = 4
    _CONTROL_CHARS = re.compile(r"[\x01-\x08\x0e-\x1f\x7f]")

    @classmethod
    def _stray_nuls(cls, content: str, nuls: int) -> bool:
        """#4351: a handful of NULs in a member that is otherwise text (see Gate 3.1)."""
        if nuls > cls._STRAY_NULS:
            return False
        # stops at the first control character past the limit
        return all(n <= cls._STRAY_NULS for n, _ in enumerate(cls._CONTROL_CHARS.finditer(content), 1))

    def _is_virtualenv(self, rel_dir: str) -> bool:
        """#4542: a candidate-named directory is excluded only when it is really a virtualenv."""
        hit = self._virtualenv_cache.get(rel_dir)
        if hit is None:
            hit = self._virtualenv_cache[rel_dir] = looks_like_virtualenv(self.root.joinpath(*rel_dir.split("/")))
        return hit

    def _log_exclusion(self, relative_path: str, reason: str | None) -> None:
        """#4917: a heuristic exclusion that can hide real code (a "Static Asset Blob") is a WARNING, so it is never
        silent; the bulk exclusions (binaries, minified / generated noise) stay at DEBUG, or a large repo floods the console."""
        if reason and "Static Asset Blob" in reason:
            self.logger.warning(f"Aperture excluded {relative_path}: {reason}")
        else:
            self.logger.debug(f"Aperture excluded {relative_path}: {reason}")

    # #4917: CI workflows and pipeline definitions are executable code, not static blobs.
    _PIPELINE_FILENAMES = frozenset(
        {
            "action.yml",
            "action.yaml",
            "bitbucket-pipelines.yml",
            "bitbucket-pipelines.yaml",
            ".gitlab-ci.yml",
            ".gitlab-ci.yaml",
            "azure-pipelines.yml",
            "azure-pipelines.yaml",
        }
    )
    _PIPELINE_KEY_PATTERN = re.compile(r"^\s*(?:-\s*)?(?:jobs|steps|run)\s*:", re.MULTILINE)

    @classmethod
    def _is_pipeline_config(cls, rel_path: str, content: str) -> bool:
        """#4917: decides whether a YAML file is a recognized CI/CD pipeline or action definition."""
        low_path = rel_path.lower().replace("\\", "/")
        if not low_path.endswith((".yml", ".yaml")):
            return False
        filename = low_path.rsplit("/", 1)[-1]
        if filename in cls._PIPELINE_FILENAMES:
            return True
        if filename.startswith("azure-pipelines") and filename.endswith((".yml", ".yaml")):
            return True
        if "/.github/workflows/" in ("/" + low_path):
            return True
        parts = set(low_path.split("/")[:-1])
        if parts & {".gitlab", ".circleci", ".buildkite"}:
            return True
        # Content check: YAML with many run:/steps:/jobs: keys is workflow code
        return len(cls._PIPELINE_KEY_PATTERN.findall(content, 0, 200_000)) >= 3

    # #5636: query structure -- a clause opening a line, or a CTE definition `name AS (`.
    _SQL_STRUCTURE_LINE = re.compile(
        r"^[ \t]*(?:select|from|(?:left |right |inner |outer |cross |full )?join|where|group by|order by|case"
        r"|,?[ \t]*\w+[ \t]+as[ \t]*\()\b",
        re.IGNORECASE | re.MULTILINE,
    )
    _SQL_DATA_LINE = re.compile(r"^[ \t]*(?:insert|values|\()", re.IGNORECASE | re.MULTILINE)

    @classmethod
    def _has_sql_structure(cls, content: str) -> bool:
        """#5636: a SQL file is query source, not a data dump, when query-structure lines are a tenth of its lines
        and outnumber its row lines (`INSERT` / `VALUES` / `(...)`). A CTE-fragment file has no leading statement, so
        its first statement cannot be the test; a dump of rows has few structure lines, whatever its header."""
        window = content[:400_000]
        lines = window.count("\n") + 1
        structure = sum(1 for _ in cls._SQL_STRUCTURE_LINE.finditer(window))
        if structure * 10 < lines:
            return False
        return structure > sum(1 for _ in cls._SQL_DATA_LINE.finditer(window))

    # Characters that open a comment in some language (`//`, `///`, `/*`, ` *`, `#`, `--`, `;`, `%`,
    # `'`, `<!--`, `"""`) plus whitespace; stripped from the front of a line to reach its text.
    _BANNER_PREFIX_CHARS = " \t/*#;%-'\"!<>{}()=+_"

    def _has_generator_banner(self, head_lines: list[str]) -> bool:
        """#4559: True if a header line is a generator banner (not prose that mentions generation)."""
        for raw in head_lines:
            if self._machine_gen_anywhere.search(raw) or self._machine_gen_shout.search(raw):
                return True
            text = raw.lstrip(self._BANNER_PREFIX_CHARS)
            if text and self.machine_gen_pattern.match(text):
                return True
        return False

    def _build_comment_syntax(self) -> dict[str, tuple[tuple[str, ...], tuple[tuple[str, str], ...]]]:
        """#4543: per extension, the comment tokens shared by every language that claims it.

        An extension two languages claim (`.h`: c, cpp, objective-c) gets only the tokens both
        agree on, so no language's code line (C's `#define`) can pass as another's comment.
        """
        families: dict[str, Any] = dict(LEXICAL_FAMILY_HEURISTICS.get("lexical_families", {}))
        per_lang: dict[str, list[str]] = families.get("line_exclusive", {}).get("language_delimiters", {})
        Syntax = tuple[frozenset[str], frozenset[tuple[str, str]]]
        by_ext: dict[str, list[Syntax]] = {}
        for lang_id, data in self.registry.items():
            family = data.get("lexical_family")
            syntax: Syntax
            if family == "line_exclusive":
                tokens = [t for t in per_lang.get(lang_id, []) if t not in ("=begin", "=end")]
                syntax = (frozenset(tokens), frozenset())
            elif family in _FAMILY_COMMENT_SYNTAX:
                family_lines, family_blocks = _FAMILY_COMMENT_SYNTAX[family]
                syntax = (frozenset(family_lines), frozenset(family_blocks))
            else:
                syntax = (frozenset(), frozenset())
            for ext in data.get("extensions", []):
                by_ext.setdefault(ext.lower(), []).append(syntax)
        result: dict[str, tuple[tuple[str, ...], tuple[tuple[str, str], ...]]] = {}
        for ext, syntaxes in by_ext.items():
            shared_lines = frozenset.intersection(*(s[0] for s in syntaxes))
            shared_blocks = frozenset.intersection(*(s[1] for s in syntaxes))
            if shared_lines or shared_blocks:
                result[ext] = (tuple(sorted(shared_lines, key=len, reverse=True)), tuple(sorted(shared_blocks)))
        return result

    @staticmethod
    def _comment_lines(lines: list[str], syntax: tuple[tuple[str, ...], tuple[tuple[str, str], ...]]) -> set[int]:
        """#4543: indexes of the lines that are wholly comment (a line comment, or inside/one block)."""
        line_tokens, blocks = syntax
        comment: set[int] = set()
        open_block: tuple[str, str] | None = None
        for i, line in enumerate(lines):
            text = line.strip()
            if open_block is not None:
                close = text.find(open_block[1])
                if close < 0:
                    comment.add(i)
                    continue
                rest = text[close + len(open_block[1]) :].strip()
                open_block = None
                if not rest:
                    comment.add(i)
                continue
            if line_tokens and text.startswith(line_tokens):
                comment.add(i)
                continue
            for opener, closer in blocks:
                if text.startswith(opener):
                    close = text.find(closer, len(opener))
                    if close < 0:
                        open_block = (opener, closer)
                        comment.add(i)
                    elif not text[close + len(closer) :].strip():
                        comment.add(i)
                    break
        return comment

    @staticmethod
    def _reads_as_prose(line: str) -> bool:
        """#4543: a comment line of spaced words, not a base64 / inline source-map payload."""
        if "base64," in line or "sourceMappingURL=data:" in line:
            return False
        return line.count(" ") * _PROSE_CHARS_PER_SPACE >= len(line)

    # #5458: assets a Doxygen/Sphinx/JSDoc output directory holds besides its HTML.
    _DOC_ASSET_EXTENSIONS = frozenset(
        {".html", ".htm", ".xml", ".css", ".js", ".json", ".md", ".txt", ".map", ".php", ".hhc", ".hhk", ".hhp"}
    )
    # #6266: a build manifest is a build file whatever its extension (`CMakeLists.txt` reads as a `.txt` doc asset), so
    # a directory holding one is not a generated-docs dir and its feature-toggle `-DX` definitions reach the scan.
    _BUILD_MANIFEST_NAMES = frozenset({"cmakelists.txt", "makefile", "gnumakefile", "meson.build", "build.bazel"})
    _DOC_PROBE_BYTES = 8192
    _DOC_PROBE_MAX_FILES = 64

    def _list_dir_files(self, rel_dir: str) -> list[str]:
        """Sorted file names directly inside rel_dir ([] when unreadable)."""
        try:
            with os.scandir(self.root.joinpath(*rel_dir.split("/"))) as it:
                return sorted(e.name for e in it if e.is_file())
        except OSError:
            return []

    def _holds_source_files(self, rel_dir: str) -> bool:
        """True when rel_dir directly holds source or build files (not doc assets)."""
        cached = self._source_dir_cache.get(rel_dir)
        if cached is None:
            cached = False
            for name in self._list_dir_files(rel_dir):
                ext = os.path.splitext(name)[1].lower()
                if name in self.exact_match_files or name.lower() in self._BUILD_MANIFEST_NAMES or (
                    ext in self.whitelisted_extensions and ext not in self._DOC_ASSET_EXTENSIONS
                ):
                    cached = True
                    break
            self._source_dir_cache[rel_dir] = cached
        return cached

    def _is_generated_docs_dir(self, rel_dir: str) -> bool:
        """Order-independent verdict: most of the directory's own markup files carry a doc-generator
        signature and the directory holds no source/build files (#5458)."""
        cached = self._generated_docs_dir_cache.get(rel_dir)
        if cached is not None:
            return cached
        verdict = False
        markup = [n for n in self._list_dir_files(rel_dir) if n.lower().endswith((".html", ".htm", ".xml"))]
        if markup and not self._holds_source_files(rel_dir):
            sample = markup[: self._DOC_PROBE_MAX_FILES]
            hits = 0
            for name in sample:
                try:
                    with open(self.root.joinpath(*rel_dir.split("/"), name), "rb") as fh:
                        head = decode_bytes(fh.read(self._DOC_PROBE_BYTES))
                except OSError:
                    continue
                if self.doc_generator_pattern.search("\n".join(head.splitlines()[:100])):
                    hits += 1
            verdict = hits * 2 > len(sample)
        if verdict:
            self.logger.debug(f"Directory '{rel_dir}' flagged as Auto-Generated Docs.")
        self._generated_docs_dir_cache[rel_dir] = verdict
        return verdict

    def _check_ignore_rules(self, rel_path: str, has_intent: bool = False) -> bool:
        """
        Determines if the path is in a blocked, ignored, or dynamically
        infected sector. Implements standard .gitignore functionality alongside
        hardcoded vendor/infrastructure exclusions.
        """
        parts = rel_path.split("/")

        # 1. Static Ignored Directories & Hidden Paths (CI trees exempt, #3278)
        in_ci_tree = not self._CI_CONFIG_DIRS.isdisjoint(parts)
        for i, part in enumerate(parts):
            low_part = part.lower()
            if low_part in self.ignored_directories:
                return False
            if low_part in VIRTUALENV_CANDIDATE_NAMES and self._is_virtualenv("/".join(parts[: i + 1])):
                return False
            # the last part is the file itself: only directories are probed (no stat per file)
            if i < len(parts) - 1 and self._vendor_dirs.is_vendored("/".join(parts[: i + 1])):
                return False

            if (
                part.startswith(".")
                and part not in self.exact_match_files
                and part not in self._CI_CONFIG_FILES
                and not in_ci_tree
                and not has_intent
            ):
                return False

        # 2. Dynamic Documentation Debris Shield
        path_obj = Path(rel_path)
        # #5458: a directory is generated docs on evidence about the directory, never one file.
        # A flagged ancestor covers descendants only while they hold no source/build files.
        flagged_ancestor = False
        for parent in path_obj.parents:
            if str(parent) != "." and self._is_generated_docs_dir(str(parent)):
                flagged_ancestor = True
                break
        if flagged_ancestor and not self._holds_source_files(str(path_obj.parent)):
            self.logger.debug(f"Dynamic Deflection: Asset '{rel_path}' blocked in auto-generated directory.")
            return False

        # 3. (removed, #3278) The "Semantic Infrastructure & Test Target Shield" dropped
        # any path containing a word like lib/spec/test/build/out/docs/scripts. Since
        # #2555 it only fired on scans with no root manifest, where it cut real source
        # (DOOM's hu_lib.c / p_spec.c, 72% of sqlite, 12 of the yaml corpus's 44 files).
        # Vendor/dependency trees are caught by IGNORED_DIRECTORIES above, generated and
        # minified output by the content gates in is_in_scope.

        # 4. The Denylist (Vendor Blob Deflection)
        filename = parts[-1]
        for pattern in self.denylist_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return False

        # 5. Standard Iterative .gitignore Logic
        for pattern in self.ignore_patterns:
            if pattern.endswith("/"):
                if any(fnmatch.fnmatch(p + "/", pattern) for p in parts):
                    return False
            else:
                if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(filename, pattern):
                    return False

        return True

    def _load_gitignore_patterns(self) -> list[str]:
        """Reads local .gitignore files to identify un-tracked noise."""
        patterns = []
        ignore_file = self.root / ".gitignore"

        if ignore_file.exists():
            try:
                with open_source(ignore_file) as f:
                    for line in f:
                        clean_line = line.strip()
                        if clean_line and not clean_line.startswith("#"):
                            patterns.append(clean_line)
            except Exception as e:
                self.logger.warning(f"Failed to parse .gitignore: {e}")

        return patterns
