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

A contract's lifecycle has three states:
  draft     -- the schema comment transcribed as-is; not yet audited across the
               corpus languages. The audit baseline carries every draft.
  declared  -- the sentence, `kind` and `unit` are fixed and language-independent,
               the schema comment contains the sentence, incidence was measured on
               both corpora, and every rule the measurement shows contradicting
               the sentence is FILED, not fixed. The rules have not been brought
               into line. This is the state the unplanted, ungated domain sensors
               get in one batch (#2897, docs/domain_sensor_contracts.md): no corpus
               cell can move for them, so a per-family audit has nothing to hold
               equal. A declared row becomes stated the day it gains a plant or a
               gated consumer and gets the family audit.
  stated    -- audited against every corpus language (the `rule-contract-audit`
               skill), with a docs/<signal>_rule_contract.md giving the sentence,
               its corollaries, the fallback family and the per-language verdicts,
               and the rules edited to agree with it in the same PR.
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
   The literate pack (`lit_code_blocks`, `lit_diagrams`, `lit_headers`, `lit_links`) is the
   same shape for markdown: `prism.py`'s Prose Bypass routes the whole file into the comment
   stream and `detector.comment_analysis` runs the four rules there (#691) -- probed on the
   code stream they read 0 on every file.
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
    status: str = "draft"  # "draft" | "declared" | "stated"
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
    _c(
        "branch",
        "structure",
        "site",
        "A keyword or operator that opens a runtime choice between control-flow paths: the choosing construct or one of its alternative arms",
        status="stated",
        doc="docs/branch_rule_contract.md",
        issue=2822,
        planted=True,
    ),
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
        "A vocabulary token of straight-line execution or structural delimiting -- a return, a declaration or import keyword, a type keyword, an instruction mnemonic in a language with no other structure -- counted as a length-like tally with no structural referent",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "func_start",
        "structure",
        "declaration",
        "The syntax that opens an executable block of logic under its own name: a function, method, procedure or subroutine declaration, or the instruction that begins an executable step in a language with no named-callable form",
        status="stated",
        doc="docs/func_start_rule_contract.md",
        issue=2856,
        planted=True,
    ),
    _c(
        "class_start",
        "structure",
        "declaration",
        "The declaration of a named type -- a class, struct, record, interface, enum or object -- or the file's compilation-unit container where that container is the language's only named-entity declaration",
        status="stated",
        doc="docs/class_start_rule_contract.md",
        issue=2856,
        planted=True,
    ),
    # --- PHASE 2: SAFETY & EXECUTION RISK ---
    _c(
        "safety",
        "safety",
        "site",
        "A site that handles or forestalls a runtime failure at the value level -- a guarded region's opener or its typed handler, a runtime assertion or validation call, a fallback or handled-absence form, an installed failure handler or watchdog, or a hardening instruction -- in a form an ordinary identifier, type annotation or constructor cannot match",
        status="stated",
        doc="docs/safety_rule_contract.md",
        issue=2869,
        planted=True,
    ),
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
        "A SITE THAT HANDS CONTROL OUT OF THE PROGRAM'S OWN SEMANTICS -- it ends or halts the process, runs text or another program as code, loads or rewrites executable code at run time, destroys a whole store the program does not own, or steps outside the runtime's protections -- in the primitive's own invocation or statement form.",
        status="stated",
        doc="docs/high_risk_execution_rule_contract.md",
        issue=2878,
        planted=True,
    ),
    _c(
        "io",
        "safety",
        "site",
        "An operation that moves data between the program and a system outside its own runtime",
        status="stated",
        doc="docs/io_rule_contract.md",
        issue=2841,
        planted=True,
    ),
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
    _c(
        "test",
        "safety",
        "site",
        "A site that engages a testing framework: a test-case or fixture declaration, a framework assertion or expectation, or the framework named as such",
        status="stated",
        doc="docs/test_rule_contract.md",
        issue=2852,
        planted=True,
    ),
    # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
    _c("concurrency", "architecture", "site", "Asynchronous logic and parallel execution"),
    _c(
        "ui_framework",
        "architecture",
        "site",
        "A call, declaration or markup construct that builds or mutates a user-interface surface through a UI framework or the document tree -- a component or widget definition, a hook or lifecycle call, a DOM query or mutation, a layout or rendering directive -- in the framework's own invocation or property form",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "closures",
        "architecture",
        "declaration",
        "The syntax that opens an anonymous callable -- a lambda, arrow function, block literal or inline callback -- at the point it is defined",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "globals",
        "architecture",
        "declaration",
        "A declaration of a binding with program lifetime -- file, module, class-static or process scope -- or a read or write of the process's ambient environment through its named handle",
        status="stated",
        doc="docs/globals_rule_contract.md",
        issue=2858,
        planted=True,
    ),
    _c(
        "decorators",
        "architecture",
        "annotation",
        "A metadata attribute attached to the declaration it precedes -- an annotation, attribute, pragma or directive line -- in the language's attribute syntax",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "generics",
        "architecture",
        "annotation",
        "A type-parameter list on a declaration or an instantiation -- the bracketed parameters that make a type or callable generic -- in the language's parameterisation syntax",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "comprehensions",
        "architecture",
        "site",
        "A collection-transform expression -- a comprehension, a map/filter/fold/for-each call, or an inline iteration form -- at its invocation",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "scientific",
        "architecture",
        "site",
        "A call into, or an import of, a numeric, scientific or rendering library facility -- a math function, a linear-algebra or matrix type, an array, plotting or GPU library -- in its qualified, typed or call form",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "reflection_metaprogramming",
        "architecture",
        "site",
        "Metaprogramming, reflection, and dynamic property assignment",
    ),
    _c(
        "import",
        "architecture",
        "declaration",
        "A statement or directive that binds an external unit -- a module, package, header, library, file, stage or base image -- into the current unit, in the language's own dependency form",
        status="stated",
        doc="docs/import_rule_contract.md",
        issue=2875,
        planted=True,
    ),
    _c(
        "ownership",
        "architecture",
        "annotation",
        "A tag naming who is responsible for the unit -- an author, creator, maintainer, owner, developer or contact -- with its value, in the form the language's tooling or header convention reads as metadata",
        status="stated",
        doc="docs/ownership_rule_contract.md",
        issue=2882,
        planted=True,
    ),
    # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
    _c("planned_debt", "subsystems", "annotation", "Annotated future work", planted=True),
    _c("fragile_debt", "subsystems", "annotation", "Explicit admissions of fragile or dangerous logic", planted=True),
    _c(
        "hardcoded_secrets",
        "subsystems",
        "site",
        "A literal credential written into the file -- a password, token, key or secret assigned or configured as a string literal of credential length -- at the assignment",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c("spec_exposure", "subsystems", "annotation", "Audit tags establishing traceability of intent"),
    _c(
        "ssr_boundaries",
        "subsystems",
        "site",
        "A server-side rendering boundary -- a framework's data-loading or render-mode hook, a server/client directive, or a template-render call -- in the framework's own form",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "events",
        "subsystems",
        "site",
        "A site that publishes into or wires up an event or message channel -- an emit or dispatch call, a broker or bus client construction, a signal connect -- in call form",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "dependency_injection",
        "subsystems",
        "annotation",
        "An inversion-of-control marker -- an injection annotation, a provider or module registration, a container or factory declaration -- attached to the declaration it wires",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "macros",
        "subsystems",
        "declaration",
        "A compile-time code-generation directive -- a macro definition, a conditional-compilation or include directive, a compiler pragma -- in directive form",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "pointers",
        "subsystems",
        "site",
        "A site that takes, holds or dereferences a raw memory address -- an address-of, a pointer declaration or dereference, an unsafe pointer or raw-handle type -- in the language's pointer syntax",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "memory_alloc",
        "subsystems",
        "site",
        "A call that requests memory from the runtime or the heap explicitly -- an allocator call, an explicit object or buffer construction, a manual resize -- at its invocation",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "inline_asm",
        "subsystems",
        "site",
        "The opener of an embedded machine-code region -- an inline-assembly statement, block or intrinsic -- in the language's embedding syntax",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
    _c("telemetry", "resources", "site", "Structured logging and observability frameworks", planted=True),
    _c("debug_prints", "resources", "site", "Ad-hoc, temporary debug statements"),
    _c(
        "explicit_casts",
        "resources",
        "site",
        "A site that converts a value's type explicitly -- a cast expression, a conversion call or a cast keyword -- in cast form",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "panics_and_aborts",
        "resources",
        "site",
        "A statement that ends the current execution context by raising or aborting -- a throw or raise, a panic, an unreachable marker, a fatal-error, revert or process-exit call -- in statement or call form",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "thread_sleeps",
        "resources",
        "site",
        "A call that blocks the current thread or schedules a forced delay -- a sleep, a timed wait, a timeout-driven deferral -- at its invocation",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "bitwise_ops",
        "resources",
        "site",
        "A bitwise operator applied between value operands -- shift, and, or, xor, or the unary complement -- in operator position",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c("sync_locks", "resources", "site", "Explicitly coordinating threaded logic to prevent race conditions"),
    _c(
        "immutability_locks",
        "resources",
        "annotation",
        "AN ADDED MARKER OR LOCK CALL THAT PREVENTS A BINDING OR VALUE FROM BEING CHANGED AFTER INITIALISATION, WHERE THE LANGUAGE'S DEFAULT WOULD PERMIT IT -- a modifier or qualifier on an otherwise-mutable declaration, a restricted constant-declaration form distinct from the general-purpose binding, a runtime lock call, or an immutable reference pin; the language's ordinary binding keyword is a binding choice, not a lock, and a language whose bindings are immutable by default records the stated absence.",
        status="stated",
        doc="docs/immutability_locks_rule_contract.md",
        issue=2772,
    ),
    _c(
        "cleanup",
        "resources",
        "site",
        "A SITE THAT EXPLICITLY DESTROYS STATE OR RELEASES A HELD RESOURCE -- a deallocation or finalization call, a handle or connection close, removal of an entry from a live container or of external state the program owns, or the opener of a guaranteed-teardown region -- in call or statement form.",
        status="stated",
        doc="docs/cleanup_rule_contract.md",
        issue=2888,
        planted=True,
    ),
    _c(
        "encapsulation",
        "resources",
        "annotation",
        "One hit is a declaration-position marker that excludes a name from the public surface, in the language's own morphology",
        status="stated",
        doc="docs/encapsulation_rule_contract.md",
        issue=2766,
    ),
    _c(
        "listeners",
        "resources",
        "site",
        "A registration to receive from an external broadcast -- an event-listener, subscription or handler-binding call -- at its invocation",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "test_skip",
        "resources",
        "annotation",
        "A marker that disables or ignores a test -- a skip decorator, an ignore attribute, a `.skip`/`xit` call form -- attached to the test it silences",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    # --- HYBRID DOMAIN SENSORS ---
    _c(
        "serialization_parsing",
        "hybrid",
        "site",
        "A call that encodes to or decodes from a structured interchange format -- JSON, XML, YAML, CSV, protocol buffers, a marshal or unmarshal -- at its invocation",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "regex_execution",
        "hybrid",
        "site",
        "A site that evaluates a regular expression -- a match, substitution or split operator, a regex constructor or compile/exec call -- at its invocation",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "time_date_logic",
        "hybrid",
        "site",
        "A site that instantiates or computes with a clock or calendar value -- a now/time/date constructor, duration arithmetic, a formatting or timezone call -- at its invocation",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "ipc_rpc_bridges",
        "hybrid",
        "site",
        "A site that crosses a process or host boundary through a bridge -- an RPC or IPC client or server construction, a pipe or socket-message send, a foreign-function or platform-channel call -- at its invocation",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    # --- AI/ML EXTENSION PACK (python, javascript, typescript) ---
    _c("llm_api", "ai-ml", "site", "Direct calls into a hosted LLM provider SDK"),
    _c(
        "llm_orchestrator",
        "ai-ml",
        "declaration",
        "An import of an agent or retrieval-orchestration framework from the pack's name list -- one hit per import statement, none for a use of the imported name",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "llm_vector_store",
        "ai-ml",
        "declaration",
        "An import of a vector-database client from the pack's name list -- one hit per import statement, none for a use of the imported name",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "ml_traditional",
        "ai-ml",
        "declaration",
        "An import of a classical (non-deep-learning) machine-learning library from the pack's name list -- one hit per import statement, none for a use of the imported name",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "dl_frameworks",
        "ai-ml",
        "declaration",
        "An import of a deep-learning framework from the pack's name list -- one hit per import statement, none for a use of the imported name",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "hardware_bridge",
        "ai-ml",
        "declaration",
        "An import of a library that bridges software into physical or peripheral I/O -- serial, USB, bluetooth, printers, device sockets -- one hit per import statement",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "cryptography",
        "ai-ml",
        "declaration",
        "An import of a cryptographic-primitive, hashing, transport-security or identity library from the pack's name list -- one hit per import statement",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "lazy_evaluation",
        "ai-ml",
        "site",
        "A deferred-execution construct at its site -- a yield statement, a generator or iterator type annotation, an async-generator form",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "vectorized_math",
        "ai-ml",
        "site",
        "A tensor or matrix operation at its site -- an einsum/matmul/tensordot/dot call, or the infix matrix-multiply operator between two value operands",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    # --- APPSEC SENSORS (zero-trust pipelines) ---
    _c(
        "rce_funnel",
        "appsec",
        "site",
        "A subprocess spawn from application code whose command is a shell or interpreter -- at the spawn call, with the interpreter name in the command",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "exfiltration_camouflage",
        "appsec",
        "site",
        "An outbound HTTP call whose target or payload carries a telemetry-, metrics-, audit- or log-shaped name -- at the call",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "memory_scraping",
        "appsec",
        "site",
        "A read of another process's memory image through the operating system's process filesystem -- at the path construction or open",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    # --- LITERATE-PROGRAMMING EXTENSION PACK (markdown) ---
    _c(
        "lit_code_blocks",
        "literate",
        "site",
        "A fence line that opens or closes a code block -- a block contributes its opener and its closer, so one block is two hits",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "lit_diagrams",
        "literate",
        "site",
        "A fence line that opens an embedded diagram block by its info string -- one hit per diagram",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "lit_headers",
        "literate",
        "declaration",
        "An ATX heading line -- one to six `#` at the margin followed by a space -- one hit per heading",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
    _c(
        "lit_links",
        "literate",
        "site",
        "An inline link or image target `[text](target)` -- one hit per link",
        status="declared",
        doc="docs/domain_sensor_contracts.md",
        issue=2897,
    ),
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


# ------------------------------------------------------------------------------
# Score contracts (contract roadmap Phase 4, #2812; first entry #2908).
# One gated `risk_<metric>` formula, stated the way a signal is: one
# language-independent sentence saying what the 0-100 SCORE means, over units
# the sheet above defines -- so the equation can be checked for adding like to
# like, not just for running. The full contract (equation, D-decisions,
# acceptance table, what left the formula and why) lives in the doc; the audit
# that keeps it honest is `tests/tools/audit_score_inputs.py <metric>` (every
# recorded score reproduced from its recorded inputs, exit 1 on residual). The
# method for taking one from draft to stated is the `score-contract-audit`
# skill; #2908 (risk_documentation) is the worked precedent whose phase list
# the next contracts (risk_api_exposure, risk_tech_debt, func_complexity_gini)
# copy.
# ------------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoreContract:
    name: str  # the risk vector column, "risk_<metric>"
    contract: str  # what the score MEANS, one language-independent sentence
    status: str = "draft"  # "draft" | "stated"
    doc: str | None = None  # repo-relative path to docs/risk_<metric>_contract.md
    issue: int | None = None  # the epic that stated it


_SCORE_ROWS = [
    ScoreContract(
        "risk_documentation",
        "Of the units extracted from a file (functions, methods, paragraphs, steps), "
        "the weight-share a reader cannot recover from documentation: a public unit "
        "counts double, a unit's own reflection hits raise its weight, and a "
        "folder-level documentation umbrella shields the whole file multiplicatively. "
        "A ratio over units, never a density over lines; a file with no extracted "
        "units has no value (n/a), not zero",
        status="stated",
        doc="docs/risk_documentation_contract.md",
        issue=2908,
    ),
]

SCORE_CONTRACTS: dict[str, ScoreContract] = {row.name: row for row in _SCORE_ROWS}
if len(SCORE_CONTRACTS) != len(_SCORE_ROWS):
    raise RuntimeError("signal_contracts: duplicate score name in _SCORE_ROWS")
for _srow in _SCORE_ROWS:
    if _srow.status not in ("draft", "stated"):
        raise RuntimeError(f"signal_contracts: {_srow.name} has unknown status {_srow.status}")


def unit_of(signal: str) -> str | None:
    """The unit a formula may treat this signal's count as, or None if unknown."""
    row = CONTRACTS.get(signal)
    return row.unit if row else None
