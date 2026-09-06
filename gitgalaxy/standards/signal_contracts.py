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
Signal contracts: what one hit of each structural signal means, stated once,
independent of language.

This is the sheet docs/contract_roadmap.md (D3) asked for. Every rule key the
language registry (LANGUAGE_DEFINITIONS) can report has one SignalContract here,
and tests/signal_contract_audit.py fails a PR that adds a key without one, or lets
the one-line comment in how_to_add_a_language.md's OUTPUT SCHEMA drift away from
the sentence recorded here. The rendered table is docs/signal_contracts.md.

Why a module and not a document: three tools need to read it -- the audit above,
the keyword-rosetta corpus tooling (which already imports LANGUAGE_DEFINITIONS the
same way), and the Phase 4 commensurability audit over the risk formulas, which
needs each input's `kind`/`unit` to say whether a formula adds like to like.

A contract's lifecycle has two states:
  draft   -- the schema comment transcribed as-is; not yet audited across the
             corpus languages. The audit baseline carries every draft.
  stated  -- audited against every corpus language (the `rule-contract-audit`
             skill), with a docs/<signal>_rule_contract.md giving the sentence,
             its corollaries, the fallback family and the per-language verdicts.
             `api` (#2730/#2743) and `args` (#2773/#2786) are the precedents.

Nothing at scan time imports this module. It is documentation with a type
signature, so the engine's behaviour cannot depend on it -- only its audits can.
"""

from __future__ import annotations

from dataclasses import dataclass

# ------------------------------------------------------------------------------
# The two contracts every rule inherits
# ------------------------------------------------------------------------------

STREAM_CONTRACT = """
**A rule runs over the file's code stream: the text left after `prism.py` removes the
comment surface for the language's `lexical_family`. String literals are never masked,
for any rule, in any language** (gitgalaxy#2535 traced this to ground with direct scans:
there is no shielding mechanism). Corollaries:

1. A keyword inside a string literal is a real hit for every rule. A rule that must not
   count one has to exclude it itself; a corpus that plants a decoy inside a string is
   testing the rule, not the stream (keyword-rosetta #17, #71, #73).
2. Comment-stream rules (`dead_code`, `doc`, `ownership`, `planned_debt`, `fragile_debt`,
   `spec_exposure`) read the comment surface instead; a language whose comment syntax
   `prism.py` does not know sends its comments into the code stream (gitgalaxy#2610, jcl).
3. The recorded count is the raw hit count, for every signal (gitgalaxy#2813). The
   proximity pairs in `core/spatial_correlation.py` (the x3 cascading flux on
   `state_mutation`, the silencer dampener on `high_risk_execution`, the race and
   exfiltration amplifiers; see `core/README.md`'s proximity table) tally into the per-file
   `mitigation_telemetry` and are applied only in the score layer's weighted view
   (`weighted_count()`); a corpus, recorder or manifest never sees them in a count.
"""

COUNT_CONTRACT = """
**One hit is one instance of the construct the signal's sentence names, in this file, as
written.** Corollaries every audited contract has needed so far:

1. **A reference is not a declaration.** A call site, an import, a type annotation naming
   the construct, a `switch` case on the keyword -- these consume a name; they do not
   declare, annotate or mutate anything (api corollary 1; haskell `IORef` in a type
   signature, gitgalaxy#2765).
2. **A modifier counts where it modifies, not wherever it appears.** `\\bpublic\\b` or
   `\\bstatic\\b` against the code stream counts the word. The rule must anchor the
   modifier to the declaration it applies to (api corollary 2).
3. **Where the language makes the property the default, say which side counts.** Either
   the declaration itself is the marker (api corollary 3: public-by-default languages count
   `def`), or the language records a contract-level absence (`None` rule + a ledgered
   `intended-morphology` entry) rather than a manufactured construct. The two answers cannot
   coexist inside one signal (gitgalaxy#2772: swift `let` is an annotation chosen against
   `var`; rust `let` is not an annotation at all).
4. **A token already owned by another rule for the same construct is not a second signal**
   (dockerfile `ENV` is `globals`, not also `state_mutation`; keyword-rosetta's
   `keyword-overlap` disposition records the exceptions that are deliberate).
5. **The count's unit is fixed by its kind** (table below) and a formula may only add,
   subtract or compare counts of the same unit. That is the check Phase 4 automates.
"""

# kind -> (what one hit is, the unit a formula may treat it as)
KINDS: dict[str, tuple[str, str]] = {
    "declaration": ("a thing declared: a function, class, parameter list, global, import, macro", "declarations"),
    "site": ("a code site where the construct is used or invoked: a decision, a write, a call, an allocation", "sites"),
    "annotation": (
        "a marker attached to a declaration, statement or comment: a modifier, a tag, a doc block",
        "annotations",
    ),
    "tally": ("a vocabulary token with no structural referent; a length-like quantity, never a denominator", "tokens"),
}

# Schema phases, in the order how_to_add_a_language.md presents them, plus the packs.
PHASE_ORDER = (
    "structure",
    "safety",
    "architecture",
    "subsystems",
    "resources",
    "hybrid",
    "ai-ml",
    "appsec",
    "literate",
)


@dataclass(frozen=True)
class SignalContract:
    name: str
    phase: str
    kind: str
    contract: str
    status: str = "draft"  # "draft" | "stated"
    doc: str | None = None  # repo-relative path to docs/<signal>_rule_contract.md
    issue: int | None = None  # the gitgalaxy issue that asked for the contract
    planted: bool = False  # keyword-rosetta SPEC plants a known count of it

    @property
    def unit(self) -> str:
        return KINDS[self.kind][1]


def _c(name, phase, kind, contract, **kw):  # tabular constructor, see rows below
    return SignalContract(name, phase, kind, contract, **kw)


# ------------------------------------------------------------------------------
# The sheet. `contract` for a draft row is the leading sentence of the signal's
# comment in how_to_add_a_language.md, verbatim -- the audit checks containment,
# so change both together. Planted = keyword-rosetta bias_report.PLANTED.
# ------------------------------------------------------------------------------

_ROWS = [
    # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
    _c("branch", "structure", "site", "Control flow that forces the CPU to make a decision or jump", planted=True),
    _c(
        "args",
        "structure",
        "declaration",
        "The parameters a callable declares",
        status="stated",
        doc="docs/args_rule_contract.md",
        issue=2773,
        planted=True,
    ),
    _c(
        "structural_boundaries",
        "structure",
        "tally",
        "Keywords defining structural boundaries and straight-line execution",
    ),
    _c(
        "func_start",
        "structure",
        "declaration",
        "Exact syntax anchoring the start of an executable block of logic",
        planted=True,
    ),
    _c(
        "class_start",
        "structure",
        "declaration",
        "The syntax that defines an object-oriented class, struct, or record",
        planted=True,
    ),
    # --- PHASE 2: SAFETY & EXECUTION RISK ---
    _c("safety", "safety", "site", "Defensive programming constructs that prevent crashes at runtime", planted=True),
    _c(
        "safety_bypasses",
        "safety",
        "site",
        "Syntax that actively bypasses type safety, swallows errors, or relies on unpredictable state",
        planted=True,
    ),
    _c(
        "high_risk_execution",
        "safety",
        "site",
        "Process-killing commands and catastrophic runtime vulnerabilities",
        planted=True,
    ),
    _c("io", "safety", "site", "Interaction with the disk, network, or external systems", planted=True),
    _c(
        "api",
        "safety",
        "declaration",
        "A declaration that makes a named function or type visible outside this file",
        status="stated",
        doc="docs/api_rule_contract.md",
        issue=2730,
    ),
    _c(
        "state_mutation",
        "safety",
        "site",
        "A statement that writes a new value into state that already exists",
        status="stated",
        doc="docs/state_mutation_rule_contract.md",
        issue=2765,
        planted=True,
    ),
    _c("dead_code", "safety", "annotation", "Commented-out structural code and unused logic trails"),
    _c(
        "doc", "safety", "annotation", "Structured documentation meant to be parsed by IDEs or generators", planted=True
    ),
    _c("test", "safety", "site", "Assertions and unit testing framework keywords", planted=True),
    # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
    _c("concurrency", "architecture", "site", "Asynchronous logic and parallel execution"),
    _c("ui_framework", "architecture", "site", "DOM manipulation, UI components"),
    _c("closures", "architecture", "declaration", "Anonymous functions, lambdas, inline callbacks"),
    _c(
        "globals",
        "architecture",
        "declaration",
        "Accessing global state, environment variables, or system registries",
        planted=True,
    ),
    _c("decorators", "architecture", "annotation", "Annotations applied to classes/methods"),
    _c("generics", "architecture", "annotation", "Type parameters indicating generic abstractions"),
    _c("comprehensions", "architecture", "site", "Collection iterators or inline looping"),
    _c("scientific", "architecture", "site", "Math, data science, and complex rendering libraries"),
    _c(
        "reflection_metaprogramming",
        "architecture",
        "site",
        "Metaprogramming, reflection, and dynamic property assignment",
    ),
    _c("import", "architecture", "declaration", "Dependency resolution and module loading", planted=True),
    _c("ownership", "architecture", "annotation", "Authorship metadata", planted=True),
    # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
    _c("planned_debt", "subsystems", "annotation", "Annotated future work", planted=True),
    _c("fragile_debt", "subsystems", "annotation", "Explicit admissions of fragile or dangerous logic", planted=True),
    _c("hardcoded_secrets", "subsystems", "site", "Static credentials or API keys baked into code"),
    _c("spec_exposure", "subsystems", "annotation", "Audit tags establishing traceability of intent"),
    _c("ssr_boundaries", "subsystems", "site", "Server-Side Rendering computation boundaries"),
    _c("events", "subsystems", "site", "Event-driven architecture signatures and message brokers"),
    _c("dependency_injection", "subsystems", "annotation", "Inversion of Control (IoC) injection markers"),
    _c(
        "macros",
        "subsystems",
        "declaration",
        "Compiler pragmas or macro definitions that generate code at compile-time",
    ),
    _c("pointers", "subsystems", "site", "Explicit tracking of raw memory addressing and pointer dereferencing"),
    _c("memory_alloc", "subsystems", "site", "Explicit unmanaged memory allocations and raw heap manipulations"),
    _c("inline_asm", "subsystems", "site", "Direct CPU architecture bridging"),
    # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
    _c("telemetry", "resources", "site", "Structured logging and observability frameworks", planted=True),
    _c("debug_prints", "resources", "site", "Ad-hoc, temporary debug statements"),
    _c("explicit_casts", "resources", "site", "Explicitly bypassing the compiler's type-checker"),
    _c("panics_and_aborts", "resources", "site", "Forcefully destroying the current execution context"),
    _c("thread_sleeps", "resources", "site", "Thread blocking or forced timeouts"),
    _c("bitwise_ops", "resources", "site", "Bitwise operations manipulating raw bytes"),
    _c("sync_locks", "resources", "site", "Explicitly coordinating threaded logic to prevent race conditions"),
    _c("immutability_locks", "resources", "annotation", "Explicitly locking data so it cannot be mutated", issue=2772),
    _c("cleanup", "resources", "site", "Explicitly destroying state or releasing resources", planted=True),
    _c(
        "encapsulation",
        "resources",
        "annotation",
        "Explicitly hiding logic from the rest of the application",
        issue=2766,
    ),
    _c("listeners", "resources", "site", "Waiting to receive state from an external broadcast"),
    _c("test_skip", "resources", "annotation", "Bypassed tests or ignored verification specs"),
    # --- HYBRID DOMAIN SENSORS ---
    _c("serialization_parsing", "hybrid", "site", "JSON, XML, YAML parsing libraries"),
    _c("regex_execution", "hybrid", "site", "Native regex evaluation commands"),
    _c("time_date_logic", "hybrid", "site", "Time/date instantiation and math"),
    _c("ipc_rpc_bridges", "hybrid", "site", "Inter-process or RPC bridging commands"),
    # --- AI/ML EXTENSION PACK (python, javascript, typescript) ---
    _c("llm_api", "ai-ml", "site", "Direct calls into a hosted LLM provider SDK"),
    _c("llm_orchestrator", "ai-ml", "site", "Agent/RAG orchestration frameworks"),
    _c("llm_vector_store", "ai-ml", "site", "Vector database clients"),
    _c("ml_traditional", "ai-ml", "site", "Classical (non-deep-learning) ML libraries"),
    _c("dl_frameworks", "ai-ml", "site", "Deep learning frameworks"),
    _c("hardware_bridge", "ai-ml", "site", "Bridges from software into physical/peripheral I/O"),
    _c("cryptography", "ai-ml", "site", "Cryptographic primitives and identity libraries"),
    _c("lazy_evaluation", "ai-ml", "site", "Generators and deferred-execution constructs"),
    _c("vectorized_math", "ai-ml", "site", "Tensor/matrix math operations"),
    # --- APPSEC SENSORS (zero-trust pipelines) ---
    _c("rce_funnel", "appsec", "site", "Spawning a shell/interpreter subprocess from application code"),
    _c("exfiltration_camouflage", "appsec", "site", "Outbound HTTP calls disguised as telemetry/metrics/audit traffic"),
    _c("memory_scraping", "appsec", "site", "Direct reads of process memory"),
    # --- LITERATE-PROGRAMMING EXTENSION PACK (markdown) ---
    _c("lit_code_blocks", "literate", "site", "Fenced code block delimiters"),
    _c("lit_diagrams", "literate", "site", "Embedded diagram blocks"),
    _c("lit_headers", "literate", "declaration", "Section headers, for document structure/navigation mapping"),
    _c("lit_links", "literate", "site", "Links to other documents or resources, captured as document dependencies"),
]

CONTRACTS: dict[str, SignalContract] = {row.name: row for row in _ROWS}
if len(CONTRACTS) != len(_ROWS):
    raise RuntimeError("signal_contracts: duplicate signal name in _ROWS")
for _row in _ROWS:
    if _row.kind not in KINDS or _row.phase not in PHASE_ORDER:
        raise RuntimeError(f"signal_contracts: {_row.name} has unknown kind/phase {_row.kind}/{_row.phase}")

# Signals whose definition lives in the extension-pack prose of
# how_to_add_a_language.md rather than as a `# key:` comment in the schema block.
EXTENSION_SIGNALS = frozenset(row.name for row in _ROWS if row.phase in ("ai-ml", "appsec", "literate"))

# Registry keys that are not signals: strategy switches and capture helpers read by
# detector.py / network_risk_sensor.py. They carry no count and need no contract,
# but the audit insists they be named here so a new one cannot slip in undescribed.
HELPER_KEYS: dict[str, str] = {
    "_dependency_capture": "capture group 1 = the exact dependency path string, for the import DAG",
    "_named_token_capture": "capture group(s) = the exact imported symbol names (AI/ML pack)",
    "_scope_filters": "{rule: filter_name} -- a structural filter detector.py applies after the regex (CRITICAL ENGINE RULE 17)",
    "_visibility_export": "per-function export-statement form, for the api orphan census (#2727/#2729)",
    "_visibility_export_list": "capture group(s) = a region holding MANY exported names, same census (#2823)",
    "_args_arrow_count_groups": "args strategy: arrow-function parameter groups",
    "_args_bare_body_groups": "args strategy: bare-body parameter groups",
    "_args_colon_selector_groups": "args strategy: colon-selector parameter groups (objective-c)",
    "_args_findall_max_groups": "args strategy: take the maximum over findall groups",
    "_args_findall_sum_groups": "args strategy: sum over findall groups",
    "_args_pattern_list_groups": "args strategy: pattern-list parameter groups",
    "_args_prototype_groups": "args strategy: prototype parameter groups",
    "_args_tcl_pattern_list_groups": "args strategy: tcl pattern-list parameter groups",
}


def unit_of(signal: str) -> str | None:
    """The unit a formula may treat this signal's count as, or None if unknown."""
    row = CONTRACTS.get(signal)
    return row.unit if row else None
