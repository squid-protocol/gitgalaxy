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
        # BUG FIX (#2646): the two ecosystems this language definition explicitly
        # targets each carry a standard, single-key ownership field that no existing
        # rule captured -- action.yml's top-level `author:` (sibling of `name:`/
        # `description:`, which `doc` already matches) and OpenAPI's `info.contact:`
        # block (bounded step-over to a nested `name:`/`email:` key, same shape as
        # `api`/`args`/`class_start`'s bounded lookahead over intervening lines, capped
        # at 10 to stay linear). Precedent: jcl's `Author:|Created by:|Maintainer:` and
        # dockerfile's `MAINTAINER|LABEL maintainer=` ownership rules already treat this
        # as real morphology for comparable languages.
        # NOTE: the nested `name:`/`email:` key under a `contact:` block also
        # legitimately satisfies `doc`'s generic `^[ \t]*name:[ \t]+.*` line-match --
        # that's an intentional, expected double-classification (the field really is
        # both a generic "name:" line AND part of an ownership/contact block), not a
        # bug introduced here; `author:` itself has no such overlap since `doc` has no
        # `author:` alternative.
        "ownership": re.compile(
            r"^[ \t]*author:[ \t]+.*"
            r"|^[ \t]*contact:[ \t]*(?:#.*)?\n(?:[ \t]*(?:#.*)?\n){0,10}[ \t]+(?:name|email):",
            re.M | re.I,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "hardcoded_secrets": re.compile(
            r"\b(?:password|secret|token|api[_-]?key|client[_-]?secret|private[_-]?key)[ \t]*:[ \t]*[\"'][A-Za-z0-9\-_+/=]{16,}[\"']",
            re.I,
        ),
        # 29. spec_exposure (Spec / Audit Traceability)
        # #2732 asked for the generic bracket-tag rule python/go/java/js share,
        # verbatim, on the reasoning that "spec_exposure never sees the code
        # stream, so YAML's [a, b] flow-sequence syntax cannot FP against it."
        # That premise is wrong, and measuring it is what produced this shape:
        # coding_analysis applies EVERY non-underscore rule to the code stream,
        # and comment_analysis then adds a second pass over the comments -- it
        # supplements the code-stream pass, it does not replace it. Dropped in
        # verbatim, the generic rule scores spec_exposure=1 on a workflow with
        # no comments at all, off `needs: [audit, lint]` alone.
        # YAML is the language where that actually bites: a bracket holding bare
        # unquoted words is ordinary syntax here (flow sequences), not a tag, so
        # the absence was never as arbitrary as it looked. Anchored instead to
        # the comment marker, exactly as this file's own `dead_code` rule is --
        # prism strips `#` comments out of the code stream, so the anchor makes
        # the rule structurally comment-only and the flow-sequence FP impossible.
        # The `\b` after the alternation is a second measured fix: bare `spec`
        # has no boundary in the generic rule, so it matches "specified" and
        # "species" -- 2 of the 3 code-stream hits across 41,815 pool .yml/.yaml
        # files were exactly that (`[specified\n per-machine]` in meson's docs,
        # `[species]` in an elasticsearch test fixture).
        # ReDoS: the prefix class excludes `[` and the body class excludes `]`,
        # so each bounded run has exactly one landing site -- nothing to
        # backtrack over.
        "spec_exposure": re.compile(
            r"^[ \t]*#[^\n\[]{0,200}\[(?:[ \t]*SPEC[ \t]*-[ \t]*\d{1,10}|spec|audit)\b[^\]\n]{0,300}\]",
            re.M | re.I,
        ),
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
        # BUG FIX (#2647): ordinary shell-level resource teardown embedded in `run:`/
        # `script:` content -- `rm -rf <non-root-path>`, `docker rm`/`stop`/`down`
        # (hyphenated `docker-compose` and modern space-separated `docker compose`
        # both), bare `kill <pid>` -- matched no existing rule. `high_risk_execution`'s
        # `rm -rf` stays deliberately root-only; `panics_and_aborts`'s `kill` stays
        # deliberately numbered-signal-only (`kill -9 ...`) -- this rule is the
        # non-root/non-numbered-signal complement, not a re-claim of either.
        # BOUNDARY FIX vs. the issue's illustrative regex: its root-path exclusion
        # (`(?!/(?:[ \t]|$))`) only excluded a bare trailing `/`, so a digit-suffixed
        # root delete (`rm -rf /2`) would have matched BOTH this rule and
        # `high_risk_execution` (which explicitly claims `/` unless followed by a
        # letter -- see that rule's own regression test for the `/2` case). Widened
        # the exclusion to `(?!/(?:[^A-Za-z]|$))` -- the exact complement of
        # `high_risk_execution`'s letter-based split -- so a `/`-rooted path is cleanup's
        # only when a letter follows (`/tmp`, `/var`, a real named directory); every
        # `/`-rooted form `high_risk_execution` claims (bare `/`, `/2`, `/!`, ...) stays
        # excluded here. Also added the `docker compose down` (space, no hyphen) form
        # the issue names in prose but the illustrative regex didn't actually cover.
        # No overlap with `after_script:` either: that keyword is intentionally left to
        # `func_start`'s executable-logic anchor (already covered by existing test
        # coverage) -- this rule keys off the shell verb itself, not the block keyword,
        # so a teardown verb inside an `after_script:` block legitimately double-counts
        # with `func_start` the same way any `run:`/`script:` shell content already
        # double-counts with `branch`/`io`/`high_risk_execution` per this language's own
        # documented philosophy (shell embedded in run:/script: counts like code).
        "cleanup": re.compile(
            r"\brm[ \t]+-rf?[ \t]+(?!/(?:[^A-Za-z]|$))\S{1,200}\b"
            r"|\bdocker(?:[ \t]+compose|-compose)?[ \t]+(?:rm|stop|down)\b"
            r"|\bkill[ \t]+(?!-[0-9])\S{1,64}\b",
            re.M | re.I,
        ),
        "encapsulation": None,
        "listeners": re.compile(r"^[ \t]*webhook:", re.M | re.I),
        "test_skip": re.compile(r"\|\|[ \t]*true\b|--passWithNoTests\b|\bskipTests\b|--no-audit\b", re.I),
    },
}
