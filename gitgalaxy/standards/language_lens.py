# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
import contextlib
import logging
import math
import re
import time
from pathlib import Path
from typing import Any, Optional, TypedDict, Union

from gitgalaxy.standards.gitgalaxy_config import EXACT_FILE_MATCH
from gitgalaxy.standards.language_standards import (
    COMPILED_HANDSHAKE_REGISTRY,
    LANGUAGE_DEFINITIONS,  # noqa: F401
    LENS_CONFIG,
)

# ==============================================================================
# GitGalaxy Phase 1: The Entity Census (Linguistic Classification Engine)
# Strategy Protocol: Bayesian Inference & Confidence Hierarchy
# ==============================================================================


class DetectorResult(TypedDict):
    """Structured classification metadata for the Pipeline Orchestrator."""

    lang_id: str
    intensity: float
    family: Optional[str]
    lock_tier: Union[int, float]
    source_proof: str
    candidates: list[str]
    path: str
    lang_mix: list[dict[str, Any]]
    loc: int
    size_bytes: int
    anomaly_flags: list[str]  # Security RAM Cache for conflicting identity indicators


class FocusingError(Exception):
    """Exception raised for I/O or execution failures during linguistic classification."""

    pass


# #3116: a shebang's trigger used to be tested as a bare substring of the whole
# line, so shell's "sh" fired on `tclsh`/`wish`/`jimsh`/`swift-sh`/`racketsh`
# and javascript's "node" fired on `ts-node`. The bogus language then
# contradicted the file's own extension, and the Identity Conflict Trap dumped
# real Tcl/Swift/Scheme/TypeScript files to Tier 5 -- `undeterminable`,
# intensity 0.0, plus an "Identity Masking" anomaly flag that reads as a
# malware finding on an ordinary script. Match the interpreter as a token
# instead: the basename of the first path word after `#!`, except for the
# `env` form, where it is the first following token that is neither a flag
# (`-S`, `-u`) nor a `VAR=value` assignment.
_SHEBANG_ENV_SKIP = re.compile(r"^(?:-|[A-Za-z_]\w*=)")


def _shebang_interpreter(first_line: str) -> str:
    """The interpreter token of a shebang line, lowercased, or "" if absent."""
    if not first_line.startswith("#!"):
        return ""
    words = first_line[2:].split()
    if not words:
        return ""
    interpreter = words[0].rsplit("/", 1)[-1].lower()
    if interpreter in ("env", "env.exe"):
        # `#!/usr/bin/env -S python3 -u`, `#!/usr/bin/env VAR=1 python3`
        for word in words[1:]:
            if not _SHEBANG_ENV_SKIP.match(word):
                return word.rsplit("/", 1)[-1].lower()
        return ""
    return interpreter


# #3133: the portable-trampoline idiom. A script whose real interpreter is not
# guaranteed to live at a fixed path bootstraps through a POSIX shell and
# re-execs itself: a plain shell shebang on line 1, then
#     # the next line restarts using tclsh \
#     exec tclsh "$0" ${1+"$@"}
# That is sqlite's own test-harness header and the canonical Tcl portability
# trick. (The shebang line is described rather than quoted on purpose: a
# literal `#!` + `/bin/` sequence anywhere in the first 8 KiB trips the X-Ray
# binary-anomaly detector's embedded-execution-header check, whose exemption
# is scoped to .sh/.bash/.zsh/.command files -- so quoting it here failed CI.)
# The shebang really IS `sh`, so it legitimately contradicts
# the file's `.tcl` extension -- and the Identity Conflict Trap read that as
# masquerading and refused the file at Tier 5 with an "Identity Masking" flag.
# A generic shell shebang is the standard bootstrap vehicle and carries almost
# no identity weight; an `exec <interpreter>` in the opening lines is what the
# file actually runs as. Bounded to the first 10 lines and a single line-scan.
_TRAMPOLINE_EXEC = re.compile(r"^[ \t]*exec[ \t]+(?:\S*/)?([\w.-]{1,40})", re.M)
# Languages whose interpreters serve as portable-LAUNCHER vehicles, i.e. whose
# shebang says "bootstrap" rather than "this is what I am". Only a conflict
# raised against one of these is eligible for trampoline suppression.
_BOOTSTRAP_SHELL_LANGS = frozenset({"shell"})

# #3134: extensions that mark a file as a TEMPLATE rather than naming its
# language -- the real language is whatever sits inside (`Makefile.pre.in` is
# Makefile syntax, `langref.html.in` is HTML). A template extension therefore
# does NOT outrank a filename prefix: `Makefile.pre.in` should stay Makefile
# via its `Makefile` prefix, even though `.in` is registered to m4. (The
# separate question of whether m4 should claim `.in` at all is a registry
# matter, not this rule's.) Distinct from SAFE_WRAPPERS, which unwraps a
# wrapper to reach a KNOWN inner extension; these are the cases where the
# inner extension is absent or itself unregistered.
_TEMPLATE_EXTENSIONS = frozenset({".in", ".template", ".tmpl", ".dist"})


def _trampoline_interpreter(content: str) -> str:
    """The interpreter a trampoline re-execs, lowercased, or "" if none."""
    head = "\n".join(content.split("\n", 10)[:10])
    match = _TRAMPOLINE_EXEC.search(head)
    return match.group(1).lower() if match else ""


def _shebang_trigger_matches(trigger: str, interpreter: str) -> bool:
    """Whether a registry shebang trigger names this interpreter.

    Exact match, or the trigger plus a pure version suffix -- `python` names
    `python3` and `python3.12`, `perl` names `perl5.36`. Only digits and dots
    may follow, so `python` does NOT name `micropython` (a different word, and
    embedded_python's own trigger) and `sh` does NOT name `tclsh`.
    """
    if not trigger or not interpreter:
        return False
    if interpreter == trigger:
        return True
    if not interpreter.startswith(trigger):
        return False
    tail = interpreter[len(trigger) :]
    return bool(tail) and all(ch in "0123456789." for ch in tail)


class LanguageDetector:
    """
    Linguistic Classification Engine.

    PURPOSE:
    Converts raw text signals, file metadata, and Bayesian priors into a high-fidelity
    language classification ('Identity Lock').

    ARCHITECTURE (The Confidence Hierarchy):
    - Tier 0: Absolute Consensus (Dual Evidence: Ext+Shebang, or Ext+Manifest)
    - Tier 1: High-Confidence Prior (Manifest Alignment)
    - Tier 1.5: Ecosystem Consensus (Resolves Collisions via Macro-Environment)
    - Tier 2: Single Indicator (Extension or Shebang alone)
    - Tier 3: Contextual Indicator (README / Folder Bias)
    - Tier 4: Heuristic Discovery (Requires high lexical density threshold)
    """

    def __init__(
        self,
        language_definitions: dict[str, Any],
        lexical_heuristics: dict[str, Any],
        parent_logger: Optional[logging.Logger] = None,
        exact_file_match: Optional[dict[str, str]] = None,
    ):
        self.languages = language_definitions
        self.lexical_heuristics = lexical_heuristics
        # #335: was a direct module-level EXACT_FILE_MATCH import, which
        # meant no YAML/CLI override (#332) could ever reach it. Falls back
        # to the raw default only when the caller doesn't already have a
        # resolved config to hand over (e.g. direct/test use).
        self.exact_file_match = exact_file_match if exact_file_match is not None else EXACT_FILE_MATCH

        if parent_logger:
            self.logger = parent_logger.getChild("lens")
            self.logger.setLevel(parent_logger.level)
        else:
            self.logger = logging.getLogger("lens")
            self.logger.setLevel(logging.INFO)

        self.extension_map: dict[str, str] = {}
        self.anchor_map: dict[str, str] = {}

        # --- BAYESIAN TUNING CONSTANTS (Dynamic Fetch) ---
        self.thresholds = LENS_CONFIG.get("THRESHOLDS", {})
        self.COLLISION_FREQUENCIES = set(LENS_CONFIG.get("COLLISION_FREQUENCIES", set()))
        self.PROSE_ANCHORS = set(LENS_CONFIG.get("PROSE_ANCHORS", set()))

        # #3137: memoised sibling-content vote, keyed by (directory, contested
        # ext). Any file that reaches ecosystem gravity has already FAILED
        # content resolution (a Tier 2 internal-discriminator match locks at
        # tier 2 and never calls gravity), so the neighbourhood's verdict is
        # independent of which sibling triggered it -- one census per directory,
        # deterministic, and O(files) instead of O(files^2) over a folder.
        self._sibling_vote_cache: dict[tuple[str, str], tuple[Optional[str], float]] = {}
        # Bytes read per sibling for that vote. Internal discriminators anchor on
        # imports/headers near the top of a file, so a bounded sniff is enough
        # and keeps the extra reads cheap on mega-repos.
        self.SIBLING_SNIFF_BYTES = 65536

        # Compile syntactic disqualifiers on boot to save CPU cycles per file
        self.DISQUALIFIERS = {}
        for key, regex_str in LENS_CONFIG.get("DISQUALIFIERS", {}).items():
            self.DISQUALIFIERS[key] = re.compile(regex_str, re.M | re.I)

        # Compile hybrid language handshake triggers (e.g., HTML inside PHP)
        # #2848: this was the third copy of the same compilation, and the
        # second one missing re.M -- so `_detect_hybrids` reported a polyglot
        # `lang_mix` only for a file whose very first byte opened the embedded
        # block, and every ordinary html-with-<script> file read as
        # single-language. The one compiled registry lives beside the patterns.
        self.HANDSHAKE_REGISTRY = COMPILED_HANDSHAKE_REGISTRY

        self.logger.debug("Initializing O(1) lookup maps for Linguistic Classifier...")
        self._calibrate_lookup_maps()
        self.logger.debug(f"Classifier Online | {len(self.extension_map)} Extensions | {len(self.anchor_map)} Anchors")

    def _calibrate_lookup_maps(self):
        """Builds O(1) dictionaries mapping extensions and exact filenames to languages."""
        # #3116/#3118: the shebang trigger table, resolved ONCE at boot rather
        # than re-derived per file. Three properties the per-call substring
        # loop did not have:
        #   * triggers are normalised to an interpreter basename, so a
        #     path-shaped registry entry (tcl's `bin/expect`) still matches
        #     `#!/usr/bin/expect`;
        #   * a trigger claimed by MORE THAN ONE language is dropped entirely.
        #     `deno` and `bun` run both TypeScript and JavaScript, and `csi` is
        #     both Chicken Scheme's interpreter and the C# script runner, so the
        #     shebang genuinely does not discriminate. Resolving it to either
        #     claimant makes the other claimant's files contradict their own
        #     extension and land at Tier 5 -- measured before this change:
        #     `.ts` + `#!/usr/bin/env deno` and `.scm` + `#!/usr/bin/csi` both
        #     returned `undeterminable` with an "Identity Masking" flag. No
        #     verdict lets the extension decide, which is right for every
        #     claimant (the same refuse-rather-than-guess posture as Tier 4's
        #     margin requirement);
        #   * sorted longest-first, so a specific trigger beats a shorter one
        #     that is also a legitimate prefix, independent of registry order.
        trigger_owners: dict[str, set[str]] = {}
        for lang_id, data in self.languages.items():
            for raw_trigger in data.get("shebangs", []):
                trigger = raw_trigger.rsplit("/", 1)[-1].lower()
                if trigger:
                    trigger_owners.setdefault(trigger, set()).add(lang_id)

        self._ambiguous_shebangs = {t for t, owners in trigger_owners.items() if len(owners) > 1}
        if self._ambiguous_shebangs:
            self.logger.debug(
                f"Shebang triggers claimed by multiple languages, ignored as non-discriminating: "
                f"{sorted(self._ambiguous_shebangs)}"
            )
        self._shebang_triggers = sorted(
            ((t, next(iter(owners))) for t, owners in trigger_owners.items() if len(owners) == 1),
            key=lambda pair: -len(pair[0]),
        )

        for lang_id, data in self.languages.items():
            for ext in data.get("extensions", []):
                self.extension_map[ext.lower()] = lang_id
            for anchor in data.get("exact_matches", []):
                self.anchor_map[anchor] = lang_id

            # ---> DEFENSIVE GUARD: REGEX PRE-COMPILER <---
            # Validates and compiles definitions from external JSON/YAML safely
            if "rules" in data:
                for rule_name, regex in data["rules"].items():
                    if isinstance(regex, str):
                        # Safely bypass malformed strings in external definitions
                        with contextlib.suppress(re.error):
                            data["rules"][rule_name] = re.compile(regex)

        for anchor in self.PROSE_ANCHORS:
            if anchor not in self.anchor_map:
                self.anchor_map[anchor] = "markdown" if anchor == "README" else "plaintext"

    def focus(
        self, file_path: Union[str, Path], content_sample: str = "", **kwargs
    ) -> tuple[str, float, Optional[str]]:
        """Legacy Support Gateway for systems expecting the older Tuple return format."""
        result = self.inspect(file_path, content_sample, **kwargs)
        if result["intensity"] < 0.25:
            self.logger.debug(
                f"Classification Failure on '{Path(file_path).name}': Intensity {result['intensity']:.2f} is purely ambiguous."
            )
            return "undeterminable", 0.0, None
        return result["lang_id"], result["intensity"], result["family"]

    def inspect(
        self,
        file_path: Union[str, Path],
        content_sample: str = "",
        has_intent: bool = False,
        intent_lang: str = "",
        intent_vector: Optional[dict[str, Any]] = None,
        ext_tally: Optional[dict[str, int]] = None,
        **kwargs,  # noqa: ARG002 -- absorbs caller-side extra kwargs (e.g. galaxyscope.py's census=) so focus()'s legacy passthrough and forward-compatible callers don't hit a TypeError
    ) -> DetectorResult:
        """Primary classification orchestrator combining metadata, context, and lexical analysis."""

        path_obj = Path(file_path)
        name = path_obj.name
        ext = path_obj.suffix.lower()

        # =====================================================================
        # DEFENSIVE GUARD: MULTI-DOT & DOTFILE RESOLUTION
        # =====================================================================
        # 1. Dotfiles (like .bashrc) shouldn't be treated as having a file extension
        if name.startswith(".") and name.count(".") == 1:
            ext = ""

        # 2. Extract hidden true extensions (e.g. script.sh.template -> .sh)
        # ONLY extract if the final extension is a known, safe wrapper. This prevents
        # spoofing attacks like malware.exe.txt
        else:
            SAFE_WRAPPERS = {
                ".template",
                ".tmpl",
                ".bak",
                ".old",
                ".orig",
                ".dist",
                ".gen",
                ".in",
            }
            if (ext not in self.extension_map or ext in SAFE_WRAPPERS) and len(path_obj.suffixes) > 1:  # noqa: SIM102 -- merging the inner `ext in SAFE_WRAPPERS` guard would duplicate the condition
                if ext in SAFE_WRAPPERS:
                    for middle_ext in reversed(path_obj.suffixes[:-1]):
                        if middle_ext.lower() in self.extension_map:
                            ext = middle_ext.lower()
                            self.logger.debug(f"[{name}] Extracted underlying extension '{ext}' from template wrapper")
                            break

        if not intent_vector and has_intent:
            intent_vector = {
                "lang_id": intent_lang,
                "prior_confidence": 0.75,
                "source_proof": "Legacy Context Pass",
            }

        prior_lang = intent_vector.get("lang_id", "unknown") if intent_vector else "unknown"
        prior_conf = intent_vector.get("prior_confidence", 0.10) if intent_vector else 0.10
        prior_proof = intent_vector.get("source_proof", "Discovery") if intent_vector else "Discovery"

        result: DetectorResult = {
            "lang_id": "undeterminable",
            "intensity": 0.0,
            "family": None,
            "lock_tier": 4,
            "source_proof": "Unclassified Baseline",
            "candidates": [],
            "path": str(file_path),
            "lang_mix": [],
            "loc": 0,
            "size_bytes": 0,
            "anomaly_flags": [],
        }

        if not content_sample:
            content_sample = self._capture_raw_signal(file_path)

        if name in self.exact_file_match:
            return self._forge_result(
                lang_id=self.exact_file_match[name],
                intensity=0.95,
                tier=2,
                proof="Single Indicator (Exact Match)",
                base=result,
                content_sample=content_sample,
            )

        # =====================================================================
        # PRE-FLIGHT: PROSE & METADATA ANCHORS
        # =====================================================================
        upper_stem = path_obj.stem.upper()

        if ext in {".md", ".mdx", ".rst", ".rtf", ".txt", ".log"}:
            # ---> DEFENSIVE GUARD: Catch disguised payloads before early exit <---
            shebang_lang, evidence_kind = self._tier_2_fingerprint_check(content_sample, ext)
            if shebang_lang and shebang_lang != "undeterminable":
                self.logger.warning(
                    f"[{name}] IDENTITY CONFLICT: Prose Ext '{ext}' contradicts Executable {evidence_kind} '{shebang_lang}'"
                )
                result["anomaly_flags"].append(
                    f"Identity Masking: Prose Extension ({ext}) vs Executable {evidence_kind} ({shebang_lang})"
                )
                # Drop to lowest trust tier
                return self._forge_result(
                    "undeterminable",
                    0.0,
                    5,
                    f"Identity Conflict ({ext} != {shebang_lang})",
                    result,
                    content_sample,
                )

            prose_target_id = "markdown" if ext in {".md", ".mdx"} else "plaintext"
            return self._forge_result(
                prose_target_id,
                self.thresholds.get("PROSE_CONFIDENCE", 0.95),
                1,
                f"Prose Extension ({ext})",
                result,
                content_sample,
            )

        # ---> DEFENSIVE GUARD: The Executable Shield <---
        # Do not allow textual anchor hijacking (e.g., a file named README.sh) if it has an executable extension
        is_known_code_ext = ext in self.extension_map and ext not in {
            ".txt",
            ".md",
            ".log",
        }

        is_prose = False
        if not is_known_code_ext:
            is_prose = upper_stem in self.PROSE_ANCHORS

            if not is_prose:
                is_prose = any(
                    upper_stem.endswith(f"_{anchor}")
                    or upper_stem.endswith(f"-{anchor}")
                    or upper_stem.endswith(f".{anchor}")
                    or upper_stem.startswith(f"{anchor}_")
                    or upper_stem.startswith(f"{anchor}-")
                    or upper_stem.startswith(f"{anchor}.")
                    for anchor in self.PROSE_ANCHORS
                )

        target_id: Optional[str] = None
        anchor_proof = f"Metadata Anchor ({name})"

        if name in self.anchor_map:
            target_id = self.anchor_map.get(name)
        elif name.split(".")[0] in self.anchor_map and not (is_known_code_ext and ext not in _TEMPLATE_EXTENSIONS):
            # #3134: a real extension outranks a filename PREFIX. `BUILD.mk` is
            # a Makefile that happens to start with Bazel's `BUILD` anchor, and
            # anchoring won it for python at Tier 1 before its own `.mk` was
            # ever consulted (measured by the #3117 harness). An EXACT filename
            # match still outranks an extension, above -- `Makefile` and
            # `Dockerfile` have no meaningful extension to defer to; it is only
            # the prefix form that yields.
            base_anchor = name.split(".")[0]
            target_id = self.anchor_map.get(base_anchor)
            anchor_proof = f"Prefix Anchor ({base_anchor})"
        elif is_prose:
            target_id = "markdown" if "README" in upper_stem else "plaintext"
            anchor_proof = f"Prose Anchor ({path_obj.stem})"

        if target_id:
            if target_id == "undeterminable":
                target_id = "plaintext"
            return self._forge_result(
                target_id,
                self.thresholds.get("PROSE_CONFIDENCE", 0.95),
                1,
                anchor_proof,
                result,
                content_sample,
            )

        # ---> HEURISTIC: Sibling Anchors <---
        # Fast-tracks C/C++/Obj-C header files based on the presence of implementation siblings
        if ext in self.COLLISION_FREQUENCIES and ext_tally:
            base_stem = path_obj.stem.lower()
            if ext == ".h":
                if f"{base_stem}.c" in ext_tally:
                    return self._forge_result("c", 0.99, 0, "Sibling Anchor (.c)", result, content_sample)
                elif f"{base_stem}.cpp" in ext_tally or f"{base_stem}.cc" in ext_tally:
                    return self._forge_result("cpp", 0.99, 0, "Sibling Anchor (C++)", result, content_sample)
                elif f"{base_stem}.m" in ext_tally:
                    return self._forge_result(
                        "objective-c",
                        0.99,
                        0,
                        "Sibling Anchor (.m)",
                        result,
                        content_sample,
                    )
            elif ext == ".m" and f"{base_stem}.h" in ext_tally:
                return self._forge_result(
                    "objective-c",
                    0.99,
                    0,
                    "Sibling Anchor (.h)",
                    result,
                    content_sample,
                )

        # 1. Gather Physical Signals
        ext_lang = self._tier_1_metadata_lock(ext, name)
        shebang_lang, evidence_kind = self._tier_2_fingerprint_check(content_sample, ext)

        # =========================================================================
        # DEFENSIVE GUARD: IDENTITY CONFLICT TRAP
        # =========================================================================
        # If both a known extension AND a known shebang exist, but they contradict
        # each other, the file is lying about its structural identity.
        is_conflict = (
            (ext_lang and ext_lang != "undeterminable")
            and (shebang_lang and shebang_lang != "undeterminable")
            and (ext_lang != shebang_lang)
        )

        # #3129: a generic-shell shebang that re-execs another interpreter is a
        # portable-launcher bootstrap, not a masquerade. Only suppress the
        # conflict when the re-exec'd interpreter is one the EXTENSION's own
        # language claims -- so `.tcl` + `exec tclsh` is cleared while a `.txt`
        # that re-execs something unrelated still trips the trap.
        if is_conflict and evidence_kind == "Shebang" and shebang_lang in _BOOTSTRAP_SHELL_LANGS:
            relaunched = _trampoline_interpreter(content_sample)
            if relaunched:
                claimed = self.languages.get(ext_lang or "", {}).get("shebangs", [])
                if any(_shebang_trigger_matches(t.rsplit("/", 1)[-1].lower(), relaunched) for t in claimed):
                    self.logger.debug(
                        f"[{name}] Trampoline bootstrap: shell shebang re-execs '{relaunched}', "
                        f"which {ext_lang} claims -- no identity conflict."
                    )
                    is_conflict = False
                    shebang_lang, evidence_kind = ext_lang, "Trampoline Exec"

        if is_conflict:
            self.logger.warning(
                f"[{name}] IDENTITY CONFLICT: Ext '{ext_lang}' contradicts {evidence_kind} '{shebang_lang}'"
            )

            # 1. Cache the threat into RAM for the SAST Engine
            result["anomaly_flags"].append(
                f"Identity Masking: Extension ({ext_lang}) vs {evidence_kind} ({shebang_lang})"
            )

            # 2. Force the file into the Unclassified Baseline
            return self._forge_result(
                lang_id="undeterminable",
                intensity=0.0,
                tier=5,  # Tier 5: Absolute Distrust
                proof=f"Identity Conflict ({ext_lang} != {shebang_lang})",
                base=result,
                content_sample=content_sample,
            )

        # =========================================================================
        # THE CONFIDENCE HIERARCHY (Bayesian Inference)
        # =========================================================================
        best_lang = "undeterminable"
        best_conf = 0.10
        # float, not int: sub-tiers like 1.5/1.7 are intentional (see Tier 1.5/1.7 below).
        lock_tier: float = 4
        source_proof = "Heuristic Discovery"

        # TIER 0: ABSOLUTE CONSENSUS
        if (
            ext_lang
            and ext_lang != "undeterminable"
            and shebang_lang
            and shebang_lang != "undeterminable"
            and shebang_lang == ext_lang
        ):
            best_lang, best_conf, lock_tier, source_proof = (
                ext_lang,
                0.999,
                0,
                f"Absolute Consensus (Ext + {evidence_kind})",
            )
        elif ext_lang and ext_lang != "undeterminable" and prior_lang == ext_lang and prior_conf >= 0.75:
            best_lang, best_conf, lock_tier, source_proof = (
                ext_lang,
                0.999,
                0,
                f"Absolute Consensus (Ext + {prior_proof})",
            )
        elif shebang_lang and shebang_lang != "undeterminable" and prior_lang == shebang_lang and prior_conf >= 0.75:
            best_lang, best_conf, lock_tier, source_proof = (
                shebang_lang,
                0.999,
                0,
                f"Absolute Consensus ({evidence_kind} + {prior_proof})",
            )

        # TIER 1: HIGH-CONFIDENCE PRIOR
        elif prior_conf >= 0.95 and prior_lang != "unknown":
            best_lang, best_conf, lock_tier, source_proof = (
                prior_lang,
                prior_conf,
                1,
                prior_proof,
            )

        # TIER 2: SINGLE INDICATOR
        elif shebang_lang and shebang_lang != "undeterminable":
            best_lang, best_conf, lock_tier, source_proof = (
                shebang_lang,
                0.91,
                2,
                f"Single Indicator ({evidence_kind})",
            )
        elif ext_lang and ext_lang != "undeterminable":
            best_lang, best_conf, lock_tier, source_proof = (
                ext_lang,
                0.91,
                2,
                f"Single Indicator (Ext: {ext})",
            )

        # TIER 3: CONTEXTUAL INDICATOR
        elif prior_conf >= 0.90 and prior_lang != "unknown":
            best_lang, best_conf, lock_tier, source_proof = (
                prior_lang,
                prior_conf,
                3,
                prior_proof,
            )

        # =========================================================================
        # TIER 1.5: ECOSYSTEM CONSENSUS (Collision Resolution)
        # =========================================================================
        gravity_lang = None
        # Only apply Ecosystem Consensus if we don't already have a strong Tier 2 internal signature
        #
        # NOTE (#3129/#3132/#3137): a SAME-extension collision (both rivals
        # claim `ext`) cannot be resolved by counting extensions -- both score
        # over the identical files -- which is why 7 of 14 real MicroPython
        # files in `embedded_python/meow_turtle` once locked to `python` here at
        # "72% Local Dominance". Two cheap fixes were measured on the #3117
        # harness and both LOST: making gravity ABSTAIN on same-extension
        # collisions (0.9964 -> 0.9840, 32 sqlite files fall to db2_sql at Tier
        # 3), and stripping the contested ext from every discriminator list
        # (same loss). The fix that landed is inside `_evaluate_ecosystem_gravity`
        # (#3137): for a same-extension neighbourhood it votes on what the
        # siblings actually RESOLVED to by content, not their filenames, and
        # abstains to Tier 3 only when that vote is empty or split. Mixed
        # neighbourhoods (.h beside .c) still take the extension-count physics.
        if ext in self.COLLISION_FREQUENCIES and ext_tally and lock_tier > 2:
            gravity_lang, dominance = self._evaluate_ecosystem_gravity(file_path, ext, ext_tally)

            if gravity_lang and dominance >= self.thresholds.get("ECOSYSTEM_DOMINANCE_MIN", 0.70):
                best_lang = gravity_lang
                best_conf = 0.95
                lock_tier = 1.5
                source_proof = f"Ecosystem Consensus Lock ({dominance * 100:.0f}% Local Dominance)"
                self.logger.debug(f"[{name}] Fast-tracked via Ecosystem Consensus -> {gravity_lang}")

        # =========================================================================
        # TIER 1.7: UNKNOWN EXTENSION FALLBACK
        # =========================================================================
        # If an extension is not in our definition maps but meets standard alphanumeric rules,
        # register it as a distinct identity so that it is properly grouped in audits.
        is_known_ext = ext in self.extension_map
        if ext and not is_known_ext and lock_tier == 4:
            clean_ext = ext.lstrip(".").lower()
            if 0 < len(clean_ext) <= 12 and clean_ext.isalnum():
                best_lang = clean_ext
                best_conf = 0.95
                lock_tier = 1.7
                source_proof = f"Unknown Extension Fallback (Ext: {ext})"
                self.logger.debug(f"[{name}] Unknown Extension Fallback -> '{best_lang}'")

        # =========================================================================
        # MANDATORY LEXICAL VERIFICATION
        # =========================================================================
        # Triggered if confidence falls below baseline OR the extension is highly contested.
        needs_spectral = (best_conf < self.thresholds.get("INTENSITY_FLOOR", 0.78)) or (
            ext in self.COLLISION_FREQUENCIES and lock_tier > 2
        )

        if needs_spectral:
            self.logger.debug(
                f"[{name}] Classification Unverified ({best_lang} at Tier {lock_tier}). Engaging Lexical Scan."
            )

            is_true_unknown = (
                lock_tier == 4 and best_lang in ("undeterminable", "unknown") and ext not in self.COLLISION_FREQUENCIES
            )

            if is_true_unknown:
                coding_loc = max(content_sample.count("\n") + (1 if content_sample else 0), 1)
                spectral_id, spec_intensity = self._tier_4_heuristic_discovery(
                    content_sample, coding_loc, ext, gravity_lang
                )
            else:
                spectral_id, spec_intensity = self._tier_3_lexical_scan(
                    content_sample,
                    ext,
                    claimed_lang=best_lang,
                    gravity_lang=gravity_lang,
                )

            if spectral_id != "undeterminable":
                if spectral_id == best_lang:
                    best_conf = max(best_conf, 0.95)
                    lock_tier = 0
                    source_proof = f"Absolute Consensus (Lexically Verified: {source_proof})"
                    self.logger.debug(f"[{name}] Verification Success -> {source_proof}")
                else:
                    if ext in self.COLLISION_FREQUENCIES:
                        best_lang = spectral_id
                        best_conf = min(max(spec_intensity + 0.10, 0.92), 1.0)
                        lock_tier = 4
                        source_proof = f"Collision Resolved ({ext} -> {spectral_id})"
                    elif lock_tier == 4:
                        if spec_intensity >= self.thresholds.get("FLOOR_TIER_4", 0.92):
                            best_lang, best_conf = spectral_id, spec_intensity
                            source_proof = (
                                f"Heuristic Discovery (Passed {self.thresholds.get('FLOOR_TIER_4', 0.92)} Baseline)"
                            )
                        else:
                            best_lang, best_conf = "undeterminable", spec_intensity
                            source_proof = f"Failed Discovery Baseline ({spec_intensity:.2f})"
                    elif lock_tier >= 2:
                        if spec_intensity > best_conf:
                            best_lang = spectral_id
                            best_conf = spec_intensity
                            lock_tier = 4
                            source_proof = f"Lexical Override (Evidence {spec_intensity:.2f} > {source_proof})"
                        else:
                            best_conf = min(best_conf, spec_intensity)
                            source_proof += " (Unverified / Conflicting Lexical Score)"
            else:
                if lock_tier == 4:
                    if not ext:
                        best_lang, best_conf, lock_tier, source_proof = (
                            "plaintext",
                            0.70,
                            4,
                            "Prose Fallback (Low Signal)",
                        )
                else:
                    source_proof += " (Unverified Lexical Score)"

        self.logger.debug(f"[{name}] Final Classification -> '{best_lang}' (Tier: {lock_tier} | Conf: {best_conf:.2f})")

        if best_lang not in ("undeterminable", "plaintext", "unknown") and content_sample:
            result["lang_mix"] = self._detect_hybrids(content_sample, best_lang)

        return self._forge_result(best_lang, best_conf, lock_tier, source_proof, result, content_sample)

    def _evaluate_ecosystem_gravity(
        self, file_path: Union[str, Path], ext: str, global_tally: dict[str, int]
    ) -> tuple[Optional[str], float]:
        """
        Resolves identical extension collisions (e.g., .h) by surveying the surrounding
        directory neighborhood for dominating implementation languages (C vs C++ vs Obj-C).
        """
        # 1. GATHER CANDIDATES
        candidates = [lid for lid, data in self.languages.items() if ext in data.get("extensions", [])]

        if ext == ".h" and "cpp" not in candidates and "cpp" in self.languages:
            candidates.append("cpp")

        if not candidates:
            return None, 0.0

        # 2. GATHER LOCAL FOLDER CENSUS
        local_tally: dict[str, int] = {}
        try:
            parent_dir = Path(file_path).parent
            for child in parent_dir.iterdir():
                if child.is_file():
                    local_tally[child.suffix.lower()] = local_tally.get(child.suffix.lower(), 0) + 1
                    local_tally[child.name.lower()] = local_tally.get(child.name.lower(), 0) + 1
        except Exception as e:
            self.logger.debug(f"Local folder census failed for '{file_path}': {e}")

        # 2b. SIBLING-CLASSIFICATION VOTE (#3137, closes the #3132 residual)
        # For a SAME-extension collision the extension-count physics below is
        # information-free by construction: both rivals score over the identical
        # set of contested-extension files, so the base-mass fallback (:~780)
        # counts the same files for each, and the only tie-breaker left is a
        # `discriminators` self-reference -- python lists its own `.py`, which is
        # literally where the reported "72% Local Dominance" comes from (base 14
        # + 14x2 = 42 vs embedded_python's 14 + 1x2 = 16). Counting filenames
        # cannot separate two languages that share the extension. So when the
        # neighbourhood carries no DIFFERENT extension-shaped anchor -- the exact
        # regime where physics is blind -- weigh what the siblings actually
        # RESOLVED to via their own content instead. The mixed-extension
        # neighbourhoods gravity was built for (.h beside .c, .asm beside
        # .jcl/.cbl) keep the extension-count physics untouched.
        if len(candidates) >= 2 and self._is_same_extension_neighbourhood(candidates, ext, local_tally):
            sib_lang, sib_dominance = self._resolve_by_sibling_content(file_path, ext, candidates)
            if sib_lang:
                return sib_lang, sib_dominance

        # 3. TWO-PASS PHYSICS (Local Neighborhood -> Global Repository)
        for scope_name, tally in [("Local", local_tally), ("Global", global_tally)]:
            if not tally:
                continue

            scores = {}
            debug_scoreboard = {}

            for lid in candidates:
                data = self.languages.get(lid, {})

                support_exts = [e for e in data.get("extensions", []) if e != ext]
                base_contributors = {e: tally.get(e.lower(), 0) for e in support_exts if tally.get(e.lower(), 0) > 0}

                # Single-Extension Ecosystem Support (e.g., MATLAB)
                if sum(base_contributors.values()) == 0:
                    base_contributors[ext] = tally.get(ext.lower(), 0)

                base_mass = sum(base_contributors.values())

                # #3132/#3137: the CONTESTED extension is counted here as
                # positive evidence for one of its own claimants -- four profiles
                # list their own contested ext as a discriminator (python `.py`,
                # sqlite `.sql`, matlab `.m`, objective-c `.m`) -- and where only
                # one rival self-references it wins by construction (python 14 +
                # 14x2 = 42 vs embedded_python's 14 + 1x2 = 16, the old "72%
                # Local Dominance"). This self-reference cannot simply be removed:
                # it does real work in BOTH directions on the #3117 corpus
                # (removing only python's `.py` broke SEVEN plain-python files
                # into embedded_python), and `.sql` has no content signal to
                # replace it with -- sqlite's strongest markers cover ~a quarter
                # of its 80 files. So this physics is LEFT AS IS for the
                # mixed-extension neighbourhoods it handles well; the
                # same-extension collisions it is structurally blind to are
                # short-circuited before this loop by the sibling-content vote
                # (step 2b above), which never reaches here.
                discriminators = data.get("discriminators", [])
                discrim_contributors = {
                    d: tally.get(d.lower(), 0) for d in discriminators if tally.get(d.lower(), 0) > 0
                }
                discrim_mass = sum(discrim_contributors.values())

                disqualifiers = data.get("disqualifiers", [])
                toxic_contributors = {
                    dq: tally.get(dq.lower(), 0) for dq in disqualifiers if tally.get(dq.lower(), 0) > 0
                }
                toxic_mass = sum(toxic_contributors.values())

                final_score = 0.0
                status = "Evaluated"

                if toxic_mass > 0:
                    final_score = 0.0
                    status = f"Collapsed (Toxic: {toxic_contributors})"
                elif base_mass == 0:
                    final_score = discrim_mass * 0.1
                    status = "Ghost (Discrim only)"
                else:
                    final_score = base_mass + (discrim_mass * 2.0)
                    status = "Healthy"

                scores[lid] = final_score

                if self.logger.isEnabledFor(logging.DEBUG):
                    debug_scoreboard[lid] = {
                        "base": f"{base_mass} {base_contributors}",
                        "discrim": f"{discrim_mass} {discrim_contributors}",
                        "toxic": f"{toxic_mass} {toxic_contributors}",
                        "score": final_score,
                        "status": status,
                    }

            total_gravity = sum(scores.values())
            if total_gravity == 0:
                continue  # Inconclusive. Fall back to the Global tally loop.

            # lambda, not scores.get -- dict.get is overloaded (1-arg vs
            # 2-arg-with-default), which mypy can't resolve when passed
            # bare as max()'s key function. Every key here is already a
            # member of scores (we're iterating its own keys), so a direct
            # __getitem__ lookup needs no default anyway.
            top_lid = max(scores, key=lambda lid: scores[lid])
            dominance = scores[top_lid] / total_gravity

            if ext == ".h" and set(scores.keys()).issubset({"c", "cpp", "objective-c"}) and dominance >= 0.55:
                dominance = max(dominance, self.thresholds.get("ECOSYSTEM_DOMINANCE_MIN", 0.70))

            # Evaluate if this scope produced a statistical winner
            threshold = self.thresholds.get("ECOSYSTEM_DOMINANCE_MIN", 0.70)
            if scope_name == "Local":
                threshold = 0.60  # Local folders need slightly less dominance to prove intent

            if dominance >= threshold:
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(
                        f"\n{scope_name} Ecosystem Consensus for '{ext}': Winner {top_lid} ({dominance * 100:.1f}%)\n"
                    )
                return top_lid, dominance

        return None, 0.0

    def _is_same_extension_neighbourhood(self, candidates: list[str], ext: str, local_tally: dict[str, int]) -> bool:
        """#3137: True when the ONLY extension-shaped signal present locally is
        the contested extension itself -- no candidate has a *different*-extension
        ecosystem anchor (a support extension or an extension-shaped
        `discriminators` entry, e.g. `.c`, `.mpy`, `.jcl`, `.db`) in this folder.

        That is exactly the regime where the extension-count physics is
        information-free and the sibling-content vote should decide. A
        mixed-extension neighbourhood -- `.h` beside `.c`, `.asm` beside
        `.jcl`/`.cbl` -- has a real cross-extension signal and stays with the
        physics, which was built for it. Filename discriminators (`boot.py`,
        `requirements.txt`) are deliberately NOT treated as extension anchors:
        they are too weak to make counting reliable (embedded_python's `boot.py`
        is the single point that the physics already fails on in #3132).
        """
        for lid in candidates:
            data = self.languages.get(lid, {})
            for token in list(data.get("extensions", [])) + list(data.get("discriminators", [])):
                t = token.lower()
                if t == ext or not t.startswith("."):
                    continue
                if local_tally.get(t, 0) > 0:
                    return False
        return True

    def _resolve_by_sibling_content(
        self, file_path: Union[str, Path], ext: str, candidates: list[str]
    ) -> tuple[Optional[str], float]:
        """#3137: weigh a same-extension neighbourhood by what its siblings
        actually RESOLVED to via their own content (shebang / internal
        discriminator), not by their filenames.

        Returns ``(lang, dominance)`` on a strict, high-dominance content
        majority among ``candidates``, else ``(None, 0.0)`` so the caller falls
        back to the extension-count physics. A sibling that classified as
        ``embedded_python`` because it imports ``machine`` is real evidence about
        its neighbours; a sibling that merely SHARES the contested extension is
        not evidence at all and casts no vote. An evenly split or empty
        neighbourhood abstains -- Tier 3 then decides -- rather than letting
        ``max()`` iteration order pick a winner (the #3118 silent
        order-dependence). Memoised per directory+extension (see
        ``self._sibling_vote_cache``).
        """
        try:
            parent_dir = Path(file_path).parent
        except Exception:
            return None, 0.0

        cache_key = (str(parent_dir), ext)
        cached = self._sibling_vote_cache.get(cache_key)
        if cached is not None:
            return cached

        result: tuple[Optional[str], float] = (None, 0.0)
        candidate_set = set(candidates)
        try:
            siblings = sorted(
                (c for c in parent_dir.iterdir() if c.is_file() and c.suffix.lower() == ext),
                key=lambda p: p.name,
            )
        except Exception as e:
            self.logger.debug(f"Sibling-content census failed for '{file_path}': {e}")
            self._sibling_vote_cache[cache_key] = result
            return result

        votes: dict[str, int] = {}
        for sib in siblings:
            try:
                with sib.open("r", encoding="utf-8", errors="ignore") as fh:
                    sample = fh.read(self.SIBLING_SNIFF_BYTES)
            except OSError as e:
                self.logger.debug(f"Sibling read failed for '{sib}': {e}")
                continue
            sib_lang, _kind = self._tier_2_fingerprint_check(sample, ext)
            if sib_lang in candidate_set:
                votes[sib_lang] = votes.get(sib_lang, 0) + 1

        total = sum(votes.values())
        if total:
            # deterministic order: highest vote first, ties broken by name so the
            # abstain-on-tie test below never depends on filesystem order.
            ranked = sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))
            top_lang, top_count = ranked[0]
            runner_up = ranked[1][1] if len(ranked) > 1 else 0
            dominance = top_count / total
            threshold = self.thresholds.get("ECOSYSTEM_DOMINANCE_MIN", 0.70)
            if top_count > runner_up and dominance >= threshold:
                self.logger.debug(
                    f"[{parent_dir.name}] Sibling-content consensus for '{ext}': "
                    f"{top_lang} ({dominance * 100:.0f}% of {total} resolved siblings, votes={votes})"
                )
                result = (top_lang, dominance)

        self._sibling_vote_cache[cache_key] = result
        return result

    def _tier_1_metadata_lock(self, ext: str, file_name: str) -> Optional[str]:
        if file_name in self.anchor_map:
            return self.anchor_map[file_name]

        # DEFENSIVE GUARD: Collisions cannot be locked at Tier 1 based on extension alone.
        # This prevents generic files from bypassing deep-inspection.
        if ext in self.COLLISION_FREQUENCIES:
            return None

        if ext in self.extension_map:
            return self.extension_map[ext]
        return None

    def _tier_2_fingerprint_check(self, content: str, ext: str) -> tuple[Optional[str], str]:
        """Content-evidence classification: returns `(lang_id, evidence_kind)`.

        `evidence_kind` is `"Shebang"` or `"Internal Signature"` -- #3116
        follow-up: this method has always resolved BOTH mechanisms, but every
        caller labelled the result "Shebang", so a file resolved by its
        internal discriminator (`ACCTPGM CSECT` in a `.asm`, `/* REXX */` in a
        `.cmd`) reported `Single Indicator (Shebang)` with no `#!` anywhere in
        it, and an identity conflict raised against a discriminator match
        reported the contradiction against a shebang that did not exist.
        `source_proof` is a load-bearing claim in this engine, so the mechanism
        travels with the verdict. Kind is `""` when no language matched.
        """
        # 1. Standard Executable Shebang Check
        if content.startswith("#!"):
            first_line = content.split("\n", 1)[0].lower()
            self.logger.debug(f"Fingerprint Scan: Analyzing shebang line: '{first_line.strip()}'")

            # #3116: token match on the interpreter basename, never a substring
            # of the whole line, against the boot-time trigger table built in
            # `_calibrate_lookup_maps` (already basename-normalised,
            # longest-first, and with non-discriminating triggers removed).
            interpreter = _shebang_interpreter(first_line.strip())
            if interpreter:
                for trigger, lang_id in self._shebang_triggers:
                    if _shebang_trigger_matches(trigger, interpreter):
                        return lang_id, "Shebang"

        # 2. INTERNAL DISCRIMINATOR (Collision Resolution Only)
        # DEFENSIVE GUARD: Internal discriminators are strictly for resolving known
        # extension collisions (e.g., Obj-C vs MATLAB .m files). They MUST NOT be used
        # as global scanners for extensionless files, as their regexes are highly specific.
        if ext:
            for lang_id, data in self.languages.items():
                if ext in data.get("extensions", []):
                    internal_disc = data.get("internal_discriminator")
                    if internal_disc and internal_disc.search(content):
                        self.logger.debug(
                            f"Fingerprint Scan: Internal discriminator matched for '{lang_id}' via '{ext}'"
                        )
                        return lang_id, "Internal Signature"

        return None, ""

    def _tier_3_lexical_scan(
        self,
        content: str,
        ext: str,
        claimed_lang: str = "undeterminable",
        gravity_lang: Optional[str] = None,
    ) -> tuple[str, float]:
        """
        The Strict Boundary Scanner.
        Evaluates the specific structural syntax of a file to verify a claimed extension.
        If a file has an extension, it MUST be claimed by one of the known languages
        for that extension; it is not allowed to randomly match an unrelated schema.
        """
        candidates = []
        if ext:
            candidates = [l for l, d in self.languages.items() if ext in d.get("extensions", [])]

            # --- DEFENSIVE GUARD: STRICT BOUNDARY ---
            if not candidates:
                self.logger.debug(
                    f"Strict Boundary Lock: Extension '{ext}' is entirely unknown. Aborting lexical scan to prevent regex hallucination."
                )
                return "undeterminable", 0.0

        # Only allow 'Scan All Definitions' fallback for truly extensionless files
        if not candidates and not ext:
            candidates = list(self.languages.keys())

        if not candidates:
            return "undeterminable", 0.0

        loc = max(content.count("\n") + 1, 1)
        content_len = len(content)
        scores = {}

        for lid in candidates:
            data = self.languages.get(lid, {})
            family = data.get("lexical_family")

            # Syntax Disqualification Phase
            if family in self.DISQUALIFIERS and self.DISQUALIFIERS[family].search(content):
                continue

            raw_score = 0.0
            rules = data.get("rules", {})

            for rule_name, regex in rules.items():
                # #1209: underscore-prefixed keys are metadata, not scannable
                # rules (e.g. `_args_arrow_count_groups`, a plain set consumed
                # directly by detector.py's args-counter) -- same convention
                # `coding_analysis` already uses. Skipping them here avoids a
                # caught-but-noisy AttributeError on `.findall()` every scan.
                if rule_name.startswith("_") or not regex:
                    continue
                try:
                    c = len(regex.findall(content))
                    if c > content_len:
                        c = 0  # Prevents runaway overlaps
                    raw_score += c * 10.0
                except Exception as e:
                    self.logger.debug(f"Rule regex evaluation failed for '{lid}', skipping this rule: {e}")

            # Apply Ecosystem Consensus Boost
            if lid == gravity_lang:
                raw_score *= 1.25

            # Claimed Language Boost: reinforces the tentative ID already
            # established by extension-tier classification, mirroring the
            # gravity_lang consensus treatment above.
            if lid == claimed_lang:
                raw_score *= 1.25

            # Comment Delimiter Bonus
            family_key = data.get("lexical_family", "standard_block")
            delims = self.lexical_heuristics.get("lexical_families", {}).get(family_key, {}).get("delimiters", [])
            for d in delims:
                if d in content:
                    raw_score += 15.0

            # Historic Language Handicaps
            if lid in ("abap", "fortran", "cobol"):
                raw_score *= 0.4

            scores[lid] = raw_score / math.log1p(loc)

        if not scores:
            return "undeterminable", 0.0

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_id, top_signal = sorted_scores[0]

        if top_signal < self.thresholds.get("PROSE_BASELINE_SIGNAL", 3.0):
            return "plaintext", 0.5

        confidence = min(top_signal / 50.0, 1.0)
        return top_id, confidence

    # =========================================================================
    # THE TIER 4 HEURISTIC DISCOVERY FUNNEL
    # =========================================================================
    def _tier_4_heuristic_discovery(
        self,
        content: str,
        coding_loc: int,
        ext: str = "",
        gravity_lang: Optional[str] = None,
    ) -> tuple[str, float]:
        """
        Heuristic Discovery for unknown or extensionless files.
        Prioritizes graceful failure over blind guessing by enforcing a strict 1.5x margin
        between the leading language candidate and the runner-up.
        """
        if coding_loc < self.thresholds.get("TIER_4_MIN_LINES", 20):
            self.logger.debug(f"Tier 4 Discovery aborted: Insufficient physical mass ({coding_loc} < 20 lines).")
            return "plaintext", 0.40

        # #3188: data-shape fast-exit (wordlist / dictionary / bare-token data).
        # A file with effectively no code-structure punctuation, dominated by
        # single-token lines, is data -- not code. The discovery scan below would
        # run every candidate language's full ruleset against it (measured ~0.9s
        # on haiku's 28,137-line `src/apps/mail/words`) only to find no lexical
        # family and return `undeterminable` -- which inspect() then turns into
        # the plaintext "Prose Fallback" anyway. Return that SAME verdict up front
        # without the scan: byte-identical classification, ~900x cheaper on this
        # class. Decided on a bounded prefix so the check itself stays O(1) in
        # file size; the two conditions together (near-zero structural
        # punctuation AND overwhelmingly one-token-per-line) cannot be met by real
        # code, whose rules need exactly that punctuation to score at all.
        _sample = content[:65536]
        _data_lines = [ln.strip() for ln in _sample.splitlines() if ln.strip()]
        if len(_data_lines) >= self.thresholds.get("TIER_4_MIN_LINES", 20):
            _code_punct = sum(_sample.count(ch) for ch in "{}()[];=")
            _single_token = sum(1 for ln in _data_lines if " " not in ln and "\t" not in ln)
            if _code_punct <= len(_data_lines) // 50 and _single_token >= len(_data_lines) * 0.85:
                self.logger.debug(
                    f"Tier 4 [data-shape]: {_single_token}/{len(_data_lines)} single-token lines, "
                    f"{_code_punct} structural-punct chars -> data, skipping discovery scan."
                )
                return "undeterminable", 0.0

        loc = max(coding_loc, 1)
        content_len = len(content)

        # =========================================================================
        # PHASE 1: Comment Family Isolation
        # =========================================================================
        family_scores = {}
        lexical_families = self.lexical_heuristics.get("lexical_families", {})

        if lexical_families:
            for fam_key, fam_data in lexical_families.items():
                delims = fam_data.get("delimiters", [])
                family_scores[fam_key] = sum(content.count(d) for d in delims)
        else:
            # Fallback for the 5 standardized lexical families if not externally defined
            xml_delim = "<" + "!--"
            family_scores = {
                "standard_block": content.count("//") + content.count("/*") + content.count("--"),
                "recursive_block": content.count("//") + content.count("/*"),
                "line_exclusive": content.count("#") + content.count(";"),
                "block_exclusive": content.count(xml_delim),
                "positional_anchored": content.count("*>") + content.count("!"),
            }

        # lambda, not family_scores.get -- same overload-resolution issue as
        # the max() call above. key is only ever invoked on elements from
        # family_scores itself, so a direct lookup is safe even with default=None.
        winning_family = max(family_scores, key=lambda fam: family_scores[fam], default=None)

        # Fail gracefully if no comments/structure exist to establish a lexical family
        if not winning_family or family_scores.get(winning_family, 0) == 0:
            self.logger.debug("Tier 4 [Phase 1]: Failed to establish a lexical comment family (No delimiters found).")
            return "undeterminable", 0.0

        self.logger.debug(
            f"Tier 4 [Phase 1]: Lexical Family Isolated -> '{winning_family}' (Score: {family_scores[winning_family]})"
        )

        candidates = [lid for lid, data in self.languages.items() if data.get("lexical_family") == winning_family]

        if not candidates:
            self.logger.debug(f"Tier 4 [Phase 1]: No candidate languages found for family '{winning_family}'.")
            return "undeterminable", 0.0

        # =========================================================================
        # PHASE 2: Heuristic Disqualification (The Blacklist)
        # =========================================================================
        surviving_candidates = []
        for lid in candidates:
            family_key = self.languages.get(lid, {}).get("lexical_family")
            if family_key in self.DISQUALIFIERS and self.DISQUALIFIERS[family_key].search(content):
                self.logger.debug(f"Tier 4 [Phase 2]: Pruning '{lid}' via Heuristic Blacklist.")
                continue  # Pruned by specific anti-patterns
            surviving_candidates.append(lid)

        if not surviving_candidates:
            self.logger.debug("Tier 4 [Phase 2]: All candidates pruned by heuristic blacklist.")
            return "undeterminable", 0.0

        self.logger.debug(f"Tier 4 [Phase 2]: Surviving candidates -> {surviving_candidates}")

        # =========================================================================
        # PHASE 3: Structural Density Scan
        # =========================================================================
        density_scores = {}
        friction_scores = {}

        for lid in surviving_candidates:
            regex_hits: float = 0  # float: the abap handicap below multiplies by 0.7
            rules = self.languages.get(lid, {}).get("rules", {})
            t_start = time.time()

            for rule_name, regex in rules.items():
                # #1209: same underscore-prefixed-metadata skip as the
                # scoring loop above -- see its comment.
                if rule_name.startswith("_") or not regex:
                    continue

                # ---> DEFENSIVE GUARD: REGEX BACKTRACKING PREVENTION <---
                # Aborts execution on extremely greedy, non-terminating patterns
                # that would lock the CPU during multi-line heuristic scanning.
                raw_pat = getattr(regex, "pattern", str(regex))
                clean_pat = raw_pat.replace("(?i)", "").replace("(?m)", "").replace("(?s)", "").strip()
                if clean_pat in ("", "()", "(?:)", "^", "$"):
                    continue

                try:
                    if hasattr(regex, "findall"):
                        hits = len(regex.findall(content))
                    else:
                        hits = len(re.findall(str(regex), content))

                    # Safety clamp: Regex hits cannot exceed total string length
                    if hits > content_len and content_len > 0:
                        hits = 0

                    regex_hits += hits
                except Exception as e:
                    self.logger.debug(f"Rule regex evaluation failed for '{lid}', skipping this rule: {e}")

            # ---> HEURISTIC BOOST: C/C++ Macro Execution <---
            family_key = self.languages.get(lid, {}).get("lexical_family")
            if family_key == "c_style_comment":
                macro_hits = len(
                    re.findall(
                        r"^\s*#(?:define|ifdef|ifndef|endif|include|pragma|if)\b",
                        content,
                        re.M,
                    )
                )
                if macro_hits > content_len and content_len > 0:
                    macro_hits = 0
                regex_hits += macro_hits

            # Specific Language Handicap
            if lid == "abap":
                regex_hits *= 0.7

            # =====================================================================
            # PHASE 4: The Density Equation (Hits / loc)
            # =====================================================================
            density_scores[lid] = regex_hits / loc

            # Record execution time to penalize extremely slow, backtracking regex evaluations
            friction_scores[lid] = time.time() - t_start

        if not density_scores:
            self.logger.debug("Tier 4 [Phase 3]: No structural signals detected for any candidate.")
            return "undeterminable", 0.0

        sorted_scores = sorted(density_scores.items(), key=lambda x: x[1], reverse=True)
        top_id, top_density = sorted_scores[0]

        self.logger.debug(f"Tier 4 [Phase 3]: Top signals -> {[(k, round(v, 4)) for k, v in sorted_scores[:3]]}")

        if top_density == 0.0:
            self.logger.debug("Tier 4 [Phase 3]: Top density is 0.0. Failing gracefully.")
            return "undeterminable", 0.0

        # =========================================================================
        # PHASE 5: Ensemble Reconciliation Engine
        # =========================================================================
        if len(sorted_scores) > 1:
            runner_up_id = sorted_scores[1][0]
            runner_up_density = sorted_scores[1][1]

            density_margin = top_density / max(runner_up_density, 0.0001)

            top_friction = friction_scores[top_id]
            runner_up_friction = friction_scores[runner_up_id]
            friction_ratio = top_friction / max(runner_up_friction, 0.000001)

            # --- DYNAMIC THRESHOLD ALIGNMENT ---

            # 1. Strong Structural Lead (Must be 1.5x denser than runner-up)
            if density_margin >= 1.5:
                # If it's vastly slower, the regex engine is likely thrashing on false positives
                if friction_ratio > 5.0:
                    self.logger.warning(f"Tier 4 [Reconciliation]: TEMPORAL FRICTION ANOMALY on {top_id}...")
                    return "undeterminable", 0.0

                return top_id, min(top_density, 1.0)

            # 2. Friction Tie-Breaker (If margin is tight, penalize slow regex execution)
            elif density_margin >= self.thresholds.get("TIER_4_OUTLIER_MARGIN", 1.10):
                if friction_ratio > 0.5:
                    self.logger.debug(
                        f"Tier 4 [Reconciliation]: Collision. {top_id} density margin ({density_margin:.2f}x) was too weak, and friction ratio ({friction_ratio:.2f}x) failed to break the tie."
                    )
                    return "undeterminable", 0.0
                self.logger.debug(f"Tier 4 [Reconciliation]: Friction Tie-Breaker utilized for {top_id}.")
                return top_id, min(top_density, 1.0)

            # 3. Absolute Ambiguity Resolution
            else:
                if ext == ".h" and {top_id, runner_up_id}.issubset({"c", "cpp", "objective-c"}):
                    if gravity_lang in {"c", "cpp", "objective-c"}:
                        self.logger.debug(
                            f"Tier 4 [Reconciliation]: C/C++ Tie broken by Ecosystem Consensus -> {gravity_lang}"
                        )
                        return gravity_lang, min(top_density, 1.0)
                    # If no consensus exists, default to C as the lowest-level structural base
                    self.logger.debug("Tier 4 [Reconciliation]: C/C++ Tie broken by default architectural base -> c")
                    return "c", min(top_density, 1.0)

                return "undeterminable", 0.0

        # 4. Single Candidate Victory
        return top_id, min(top_density, 1.0)

    def _forge_result(
        self,
        lang_id: str,
        intensity: float,
        tier: float,
        proof: str,
        base: DetectorResult,
        content_sample: str = "",
    ) -> DetectorResult:
        """Packs metadata and metrics into the formal classification dictionary structure."""
        family = self.languages.get(lang_id, {}).get("lexical_family")

        file_loc = content_sample.count("\n") + 1 if content_sample else 0
        file_size = len(content_sample.encode("utf-8")) if content_sample else 0

        base.update(
            {
                "lang_id": lang_id,
                "intensity": intensity,
                "family": family,
                "lock_tier": tier,
                "source_proof": proof,
                "candidates": [lang_id] if lang_id != "undeterminable" else [],
                "loc": file_loc,
                "size_bytes": file_size,
            }
        )
        return base

    def _capture_raw_signal(self, file_path: Union[str, Path]) -> str:
        """
        DEFENSIVE GUARD: Restricts I/O memory allocation to 50KB.
        Prevents Out-Of-Memory (OOM) crashes if the user accidentally points the
        analyzer at massive log dumps or multi-gigabyte auto-generated monoliths.
        """
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                return f.read(1024 * 50)
        except (PermissionError, FileNotFoundError, OSError) as e:
            self.logger.error(f"Hardware/IO failure reading '{file_path}': {e!s}")
            raise FocusingError(f"Failed to focus lens on {file_path}") from e

    def _find_balanced_end(self, text: str, start_pos: int, opener: str, closer: str) -> int:
        depth = 0
        in_string: Optional[str] = None
        # int(): self.thresholds is Dict[str, float] (THRESHOLDS mixes float
        # confidence values with integer limits like this one) -- range()
        # below needs an actual int, and a character-position limit was
        # always meant to be a whole number anyway.
        limit = int(
            min(
                start_pos + self.thresholds.get("HANDSHAKE_LOOKAHEAD_LIMIT", 50000),
                len(text),
            )
        )

        for i in range(start_pos, limit):
            char = text[i]

            if char in ('"', "'", "`") and (i == 0 or text[i - 1] != "\\"):
                if not in_string:
                    in_string = char
                elif in_string == char:
                    in_string = None
                continue

            if in_string:
                continue

            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth <= 0:
                    return i + 1

        return limit

    def _detect_hybrids(self, content: str, primary_id: str) -> list[dict[str, Any]]:
        """Identifies secondary logic streams (like HTML inside PHP files) via syntax handshakes."""
        total_len = len(content)
        if total_len == 0:
            return []

        distribution = {primary_id: total_len}
        last_processed_idx = 0
        triggers = [
            {
                "start": m.start(),
                "trigger_end": m.end(),
                "target": hs["target"],
                "end_pattern": hs["end"],
                "pair": hs.get("pair"),
            }
            for hs in self.HANDSHAKE_REGISTRY
            for m in hs["trigger"].finditer(content)
        ]

        triggers.sort(key=lambda x: x["start"])

        for t in triggers:
            if t["start"] < last_processed_idx:
                continue

            if t["pair"]:
                open_char, close_char = t["pair"]
                end_idx = self._find_balanced_end(content, t["start"], open_char, close_char)
            else:
                search_limit = min(
                    t["trigger_end"] + self.thresholds.get("HANDSHAKE_LOOKAHEAD_LIMIT", 50000),
                    total_len,
                )
                end_match = t["end_pattern"].search(content, pos=t["trigger_end"], endpos=search_limit)
                end_idx = end_match.end() if end_match else total_len

            segment_len = end_idx - t["start"]
            target = t["target"]

            distribution[target] = distribution.get(target, 0) + segment_len
            distribution[primary_id] -= segment_len
            last_processed_idx = end_idx

        mix = []
        for lid, m_len in distribution.items():
            if m_len > 0:
                pct = round((m_len / total_len) * 100, 1)
                if pct >= 1.0:
                    mix.append({"id": lid, "pct": pct})

        return sorted(mix, key=lambda x: x["pct"], reverse=True)
