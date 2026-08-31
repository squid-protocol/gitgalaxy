# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

import re
from typing import Any

from .._shared_patterns import GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "YAML CI/CD (GitHub Actions / GitLab CI)",
        "status": "production",
    },
    "extensions": [".yml", ".yaml", ".yamllint"],
    "exact_matches": [
        ".prettierrc",
        ".stylelintrc",
        "clang-format",
        ".clang-format",
    ],
    "discriminators": [
        "docker-compose.yml",
        ".gitlab-ci.yml",
        "kubernetes.yaml",
        "openapi.yaml",
        ".github/workflows",
    ],
    "shebangs": [],
    "lexical_family": "line_exclusive",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        "branch": re.compile(r"\b(?:if|else|elif|fi|case|esac|for|while|do|done)\b|&&|\|\|", re.I),
        # BUG FIX (epic #813/#843): required `with:` to be immediately followed by a newline,
        # so a trailing same-line comment (`with: # inputs for this action`, a real authoring
        # style) broke the match entirely -- the block's own header line has to tolerate a
        # comment the same way a job/step name line would.
        "args": re.compile(
            r"^[ \t]*with:[ \t]*(?:#.*)?\n(?:[ \t]*(?:#.*)?\n){0,10}[ \t]+[a-zA-Z0-9_-]+:[ \t]*.*", re.M | re.I
        ),
        "structural_boundaries": re.compile(r"^[ \t]*(?:env|needs|runs-on|steps|strategy|matrix):", re.M | re.I),
        # Executable Logic Anchors: Explicit execution blocks
        "func_start": re.compile(
            r"^[ \t]*(?:-?[ \t]*run:|script:|before_script:|after_script:)[ \t]*[|>]*",
            re.M | re.I,
        ),
        # MISSING-DECLARATION-SHAPE FIX (epic #813/#843): the reusable-workflow-call/
        # container-job detection required `uses:`/`image:` to be the LITERAL FIRST line
        # after the job name -- but real jobs of this shape routinely have other keys
        # (`needs:`, `if:`, `permissions:`, etc.) before `uses:`/`image:`, e.g.
        # `call-workflow:\n  needs: [build]\n  uses: ./reusable.yml`. Added a bounded
        # (max 10, to stay safely linear -- real jobs never have anywhere near that many
        # top-level keys before uses:/image:) step-over for intervening key:value lines.
        "class_start": re.compile(
            r"^[ \t]*(?:jobs:|workflow_call:"
            r"|[a-zA-Z0-9_-]+:[ \t]*(?:#.*)?\n(?:(?:[ \t]+[a-zA-Z0-9_-]+:[ \t]*.*|[ \t]*(?:#.*)?)\n){0,10}[ \t]+(?:uses|image):)",
            re.M | re.I,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        "safety": re.compile(
            r"^[ \t]*continue-on-error:[ \t]*false|^[ \t]*permissions:[ \t]*\n(?:[ \t]+(?:contents|id-token|actions|security-events):[ \t]*read)",
            re.M | re.I,
        ),
        # Catches the classic curl-to-bash supply chain dropper inside a run block
        "safety_bypasses": re.compile(
            r"^[ \t]*continue-on-error:[ \t]*true|chmod[ \t]+777|\b(?:curl|wget)[ \t]+[^|\n]{1,200}\|[ \t]*(?:bash|sh|zsh)\b",
            re.M | re.I,
        ),
        "high_risk_execution": re.compile(r"\brm[ \t]+-rf[ \t]+/(?![A-Za-z])|\beval\b|\bexec\b", re.M | re.I),
        "io": re.compile(
            r"\b(?:wget|curl|apt-get|apk|yum|git[ \t]+clone|npm[ \t]+install|pip[ \t]+install)\b",
            re.M | re.I,
        ),
        # Webhook/Workflow triggers
        "api": re.compile(
            r"^[ \t]*on:[ \t]*(?:#.*)?\n(?:[ \t]*(?:#.*)?\n){0,10}[ \t]+(?:push|pull_request|workflow_dispatch|issues):",
            re.M | re.I,
        ),
        "state_mutation": re.compile(
            r"^[ \t]*env:[ \t]*(?:#.*)?\n(?:[ \t]*(?:#.*)?\n){0,10}[ \t]+[a-zA-Z0-9_-]+:[ \t]*.*|export[ \t]+[a-zA-Z0-9_]+[ \t]*=",
            re.M | re.I,
        ),
        "dead_code": re.compile(
            r"^[ \t]*#[ \t]*(?:-?[ \t]*run:|uses:|jobs:|steps:|script:)",
            re.M | re.I,
        ),
        "doc": re.compile(r"^[ \t]*name:[ \t]+.*|^[ \t]*description:[ \t]+.*", re.M | re.I),
        "test": re.compile(
            r"\b(?:npm[ \t]+test|pytest|make[ \t]+test|cargo[ \t]+test|go[ \t]+test)\b",
            re.M | re.I,
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        "concurrency": re.compile(
            r"^[ \t]*strategy:[ \t]*\n[ \t]+matrix:|^[ \t]*concurrency:",
            re.M | re.I,
        ),
        "ui_framework": None,
        "closures": None,
        "globals": re.compile(
            r"\$\{\{[ \t]*(?:github|env|runner|secrets)\.[a-zA-Z0-9_]+[ \t]*\}\}|\$[A-Z_]+",
            re.M,
        ),
        "decorators": None,
        "generics": None,
        "comprehensions": None,
        "scientific": None,
        # Catching complex GitHub Expression injection logic
        "reflection_metaprogramming": re.compile(r"\$\{\{[ \t]*fromJson\(|to[A-Z][a-zA-Z]{0,40}\(", re.M),
        # The Gravity Links: External dependencies
        "import": re.compile(
            r"^[ \t]*(?:-?[ \t]*uses:|image:)[ \t]*(?:(?:#.*)?\n(?:[ \t]*(?:#.*)?\n){0,10}[ \t]*)?(?:[\'\"]?[a-zA-Z0-9_./@:-]+[\'\"]?)",
            re.M | re.I,
        ),
        # BUG FIX (epic #813/#843): the bare capture class required the value to start
        # immediately with an identifier character, so a quoted `uses:`/`image:` value
        # (`uses: "actions/checkout@v4"`, a real -- if less common -- authoring style, e.g.
        # for YAML-lint rules that require consistent scalar quoting) never matched at all,
        # since the leading quote character isn't in the class. Added quoted alternatives
        # (permitting the same identifier charset inside real quotes) alongside the original
        # bare form.
        "_dependency_capture": re.compile(
            r"^[ \t]*(?:-?[ \t]*uses:|image:)[ \t]*(?:(?:#.*)?\n(?:[ \t]*(?:#.*)?\n){0,10}[ \t]*)?"
            r"(?:'([a-zA-Z0-9_./@:-]+)'|\"([a-zA-Z0-9_./@:-]+)\"|([a-zA-Z0-9_./@:-]+))",
            re.M | re.I,
        ),
        "ownership": None,
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "hardcoded_secrets": re.compile(
            r"\b(?:password|secret|token|api[_-]?key|client[_-]?secret|private[_-]?key)[ \t]*:[ \t]*[\"'][A-Za-z0-9\-_+/=]{16,}[\"']",
            re.I,
        ),
        "spec_exposure": None,
        "ssr_boundaries": None,
        "events": re.compile(
            r"^[ \t]*repository_dispatch:|^[ \t]*schedule:|^[ \t]*-?[ \t]*cron:",
            re.M | re.I,
        ),
        # Secrets injection
        "dependency_injection": re.compile(r"\$\{\{[ \t]*secrets\.[a-zA-Z0-9_]+[ \t]*\}\}", re.M),
        "macros": None,
        "pointers": None,
        "memory_alloc": None,
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        "telemetry": re.compile(r"::(?:debug|warning|error)(?:[ \t]|::)", re.M),
        "debug_prints": re.compile(r"\b(?:echo|printf)\b", re.I),
        "explicit_casts": None,
        # GitHub action specific bailout outputs
        "panics_and_aborts": re.compile(
            r"\b(?:exit[ \t]+[1-9]|kill[ \t]+-[0-9]+)\b|^[ \t]*::error::",
            re.M | re.I,
        ),
        "thread_sleeps": re.compile(r"\bsleep[ \t]+[0-9]+\b", re.I),
        "bitwise_ops": None,
        "sync_locks": None,
        # Strict SHA-1 pinning for immutable security
        "immutability_locks": re.compile(r"@[a-f0-9]{40}\b", re.I),
        "cleanup": None,
        "encapsulation": None,
        "listeners": re.compile(r"^[ \t]*webhook:", re.M | re.I),
        "test_skip": re.compile(r"\|\|[ \t]*true\b|--passWithNoTests\b|\bskipTests\b|--no-audit\b", re.I),
    },
}
