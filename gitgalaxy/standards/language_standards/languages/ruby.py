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
        "target_version": "Ruby 4.0 Paradigms (Ruby 3.4+ / Ractors / Sorbet / Pattern Matching)",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard suffixes, rack configs (.ru), gem specs, and various templating/DSL extensions.
    "extensions": [
        ".rb",
        ".rbw",
        ".rake",
        ".rbi",
        ".gemspec",
        ".rbx",
        ".builder",
        ".ru",
        ".podspec",
        ".jbuilder",
        ".rabl",
    ],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless infrastructure-as-code and dependency configurations that are secretly pure Ruby.
    "exact_matches": [
        "Gemfile",
        "Rakefile",
        "Vagrantfile",
        "Guardfile",
        "Capfile",
        "Thorfile",
        "Berksfile",
        "Cheffile",
        "Podfile",
        "Fastfile",
        "Appraisals",
    ],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, lockfiles, and environment pins to lock in context.
    "discriminators": [
        ".rb",
        "Gemfile.lock",
        ".ruby-version",
        ".ruby-gemset",
        "config.ru",
    ],
    # EXECUTION SIGNATURES: Interpreters found on Line 1.
    "shebangs": ["ruby", "macruby", "jruby", "rbx"],
    # UPGRADED: Maps to Family 4 (Hybrid Hash)
    # Rationale: Uses '#' for single-line comments, but multi-line literature
    # utilizes the `=begin ... =end` block syntax, requiring hybrid parsing rules.
    "lexical_family": "line_exclusive",
    "rules": {
        # 1. branch (Control Flow / Branching)
        # Decisions and logical jumps. EXCLUDES raise/throw (bailout_hits).
        "branch": re.compile(
            r"\b(if|unless|elsif|else|case|when|in|for|while|until|begin|rescue|ensure|break|next|redo|retry)\b|&&|\|\||\?|=>"
        ),
        # 2. args (Parameters / Coupling)
        # Parameter blocks of methods, lambdas, and blocks. Bounded to prevent ReDoS.
        # #1209: parameter-list span wrapped in its own capture group in
        # all four branches (was only reachable via group(0), the whole
        # match including the "def"/"do"/"->" prefix) so detector.py's
        # counter isolates just the real parameter text -- the
        # whole-match fallback overcounted every zero/one-arg signature
        # by +1 the same way Python's did (#1199). Name group added to
        # the first branch too, purely so existing extraction tests keep
        # passing.
        "args": re.compile(
            r"\bdef\s+(?:(?:[^\W\d]\w*(?:::[^\W\d]\w*)*\.|self\.)[ \t\n]*)?([^\W\d]\w*[=!?]?|\[\]=?|<<|>>|<=>|===?|!=|=~|!~|<=?|>=?|[+\-*/%&|^~`!])\s*(\((?:(?:(?:[^()\'\"]|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")|\((?:(?:[^()\'\"]|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")|\((?:[^()\'\"]|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")*\))*\))*)\))|"
            r"\A(?!\s*\bdef\b)[\s\S]*?(?:\bdo\s*\|([^|]*)\||\{\s*\|([^|]*)\|)|"
            r"->\s*(\((?:(?:(?:[^()\'\"]|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")|\((?:(?:[^()\'\"]|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")|\((?:[^()\'\"]|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")*\))*\))*)\))",
            re.M,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries. EXCLUDES: Access modifiers (encapsulation) and const (freeze_hits).
        "structural_boundaries": re.compile(
            r"\b(class|module|def|yield|return|super|alias|undef|require|require_relative|include|extend|prepend|attr_reader|attr_writer|attr_accessor|Data\.define)\b"
        ),
        # 4. func_start (Executable Logic Anchors)
        # ONLY executable logic blocks. EXCLUDES class/module definitions.
        "func_start": re.compile(
            # =====================================================================
            # [ THE VERTICAL CLASS-METHOD SHIELD (RUBY) ]
            # Ruby allows 'def', 'self.', the function name, and the argument list
            # to be separated by vertical newlines.
            # FIX: Replaced `\s+` with `[ \t\n]+` and explicitly allowed `[ \t\n]*`
            # after `self.` so the parser doesn't break when tracking singleton methods.
            # Upgraded the trailing lookahead to safely handle newlines before `(`.
            # Upgraded name parsing to support operator overloads, unicode, and explicit namespace contexts.
            # =====================================================================
            r'^[ \t]*(?:def[ \t\n]+(?:(?:[^\W\d]\w*(?:::[^\W\d]\w*)*\.|self\.)[ \t\n]*)?|define_method[ \t\n]*\(?[ \t\n]*[:\'"]?)([^\W\d]\w*[=!?]?|\[\]=?|<<|>>|<=>|===?|!=|=~|!~|<=?|>=?|[+\-*/%&|^~`!])(?=[ \t\n]*[)(]|[\'"]?[ \t\n]*(?:\{|do)|[ \t\n]|$)',
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        "class_start": re.compile(
            r"^[ \t]*(?:class|module)\s+(?:::)?([^\W\d]\w*(?:::[^\W\d]\w*)*|<<\s*self|<<\s*@[a-zA-Z_]\w*)(?:\s*<\s*(?:::)?([^\W\d]\w*(?:::[^\W\d]\w*)*))?",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        "safety": re.compile(
            r"\&\.|\b(rescue|ensure|fetch|frozen_string_literal|freeze|catch|throw|safe_load|T\.must|T\.let|T\.cast|T\.bind)\b"
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Dynamic logic bypasses and Sorbet escape hatches.
        "safety_bypasses": re.compile(
            r"\b(eval|class_eval|instance_eval|module_eval|send|__send__|public_send|binding|instance_variable_set|unsafe_load|T\.unsafe|T\.untyped)\b"
        ),
        # 8. danger (High-Risk Execution / System Calls)
        # Process killers and shell execution. EXCLUDES puts (Phase 5).
        "high_risk_execution": re.compile(r"\b(abort|exit|exit!|system|exec|spawn|fork)\b|`[^`]+`|IO\.popen"),
        # 9. io (I/O & Network Boundaries)
        "io": re.compile(
            r"\b(File|Dir|IO|Net::HTTP|URI\.open|Socket|TCPSocket|FileUtils|ActiveRecord::Base|find|where|create|update|destroy)\b"
        ),
        # 10. api (Public Surface Area)
        # Implicit public defaults (undercased defs) + explicit module functions.
        "api": re.compile(
            r'\b(module_function)\b|^[ \t]*(?:get|post|put|patch|delete|resources?)\s+[:\'"]',
            re.M,
        ),
        # 11. flux (State Mutation)
        # Mutation of state. EXCLUDES const (freeze_hits).
        # BUG FIX: the 6 bang-method alternatives (`merge!`, `update!`,
        # `gsub!`, `map!`, `select!`, `reject!`) all end on `!`
        # (non-word), so the shared trailing \b could never fire --
        # whatever follows a Ruby bang-method call (`;`, `)`, a
        # newline, another `.method`) is never a word character. None
        # of Ruby's canonical in-place-mutation methods ever matched.
        "state_mutation": re.compile(
            r"@[a-zA-Z_]\w*\s*(?:\+|-|\*|/)?=|@@[a-zA-Z_]\w*\s*(?:\+|-|\*|/)?="
            r"|\b(?:push|pop|shift|unshift|delete|clear)\b|<<"
            r"|\bmerge!|\bupdate!|\bgsub!|\bmap!|\bselect!|\breject!"
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        "dead_code": re.compile(r"#[ \t]*(?:def|class|module|if|unless|while|puts|p)\b"),
        # 13. doc (Structured Documentation)
        # Captures YARD tags, Sorbet signatures, RDoc blocks/modifiers, and standard documentation headers.
        "doc": re.compile(
            r"^[ \t]*#\s*@(?:param|return|api|yield|raise|see|abstract|deprecated|note|example)|^[ \t]*sig[ \t]*\{|^=begin\s+(?:rdoc|pod)\b|^[ \t]*#\s*(?::nodoc:|:yields:|:args:|:return:)|^[ \t]*#\s*(?:Description|Usage|Example|Summary):\s+",
            re.M | re.I,
        ),
        # 14. test (Testing & Assertions)
        "test": re.compile(
            r'\b(describe|context|expect|assert[a-zA-Z_]*|refute[a-zA-Z_]*|setup|teardown|before|after|let|subject)\b|\b(?:it|test)\s+[\'"]'
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        "concurrency": re.compile(r"\b(Thread|Mutex|Monitor|ConditionVariable|Ractor|Fiber|Async|await|Concurrent)\b"),
        # 16. ui_framework (UI / View Components)
        "ui_framework": re.compile(
            r"\b(ActionView|render|render_to_string|ViewComponent::Base|Phlex::HTML|form_with|form_for|link_to|stylesheet_link_tag|Turbo|Stimulus|Hotwire)\b|<%|%>"
        ),
        # 17. closures (Closures / Anonymous Functions)
        # BUG FIX: all 4 alternatives shared one leading \b, but the
        # brace-block (`{ |x| ... }`) and stabby-lambda (`->(x) { ... }`)
        # forms both start with a non-word character (`{`/`-`) -- the
        # shared leading \b could only fire when a word char
        # immediately preceded them, never true for how these are
        # actually written (preceded by whitespace, `=`, or a line
        # start). Only the `do`-based forms ever matched; the brace
        # block and stabby lambda -- two of Ruby's most common closure
        # forms -- never did.
        "closures": re.compile(r"\bdo\s*\|[^|]*\||\bdo\b|\{\s*\|[^|]*\||->\s*(?:\([^)]*\))?[ \t]*\{"),
        # 18. globals (Global / Shared State)
        "globals": re.compile(r"\$[a-zA-Z_]\w*|\b(ENV|ARGV|ARGF|STDIN|STDOUT|STDERR|RUBY_VERSION)\b"),
        # 19. decorators (Decorators / Annotations)
        # Rails class macros acting as metadata descriptors.
        "decorators": re.compile(
            r"^[ \t]*(?:before_action|after_action|around_action|before_save|after_commit|validates|has_many|belongs_to|has_one)\b",
            re.M,
        ),
        # 20. generics (Generics / Type Parameters)
        # Sorbet parameterized types.
        "generics": re.compile(r"\b(?:T::|::T::)?(?:Array|Hash|Set|Enumerable|Class)\[[^\]]*\]"),
        # 21. comprehensions (Iterators / Comprehensions)
        "comprehensions": re.compile(
            r"\.(?:map|collect|select|reject|reduce|inject|filter_map|flat_map|each_with_object|partition|group_by)\b(?:[ \t]*\{|\s*do)"
        ),
        # 22. scientific (Numerical / Compute Libraries)
        "scientific": re.compile(r"\b(Math|Complex|Rational|Matrix|Vector|Numo::NArray|BigDecimal)\b"),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Metaprogramming and runtime object extensions.
        # BUG FIX: `respond_to_missing\?` ends on `?` (non-word), so the
        # shared trailing \b could never fire. Never matched.
        "reflection_metaprogramming": re.compile(
            r"\b(?:method_missing|define_method|const_missing|included|extended|prepended|class\s*<<\s*self)\b"
            r"|respond_to_missing\?"
        ),
        # 24. import (Dependency Inclusions)
        "import": re.compile(r"\b(?:require|require_relative|load|autoload)\b[^'\"]*['\"]", re.M),
        "_dependency_capture": re.compile(
            # =====================================================================
            # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (RUBY) ]
            # PURPOSE: Extracts external dependencies for the Network Graph and Supply Chain Firewall.
            #
            # HISTORICAL BUG: Originally, this regex was anchored to the start of the
            # line `^[ \t]*`. While this perfectly prevented hallucinations on commented-out
            # imports, it completely blinded the firewall to Ruby's highly dynamic execution
            # patterns. Ruby developers frequently lazy-load dependencies inside methods
            # (e.g., `def parse; require 'json'; end`) or behind conditionals. The anchored
            # regex missed these entirely, allowing Trojans to slip through.
            #
            # THE FIX: The `^` anchor has been stripped. We now rely on the `\b` word
            # boundary to find the keywords anywhere in the file.
            #
            # [ THE OPTIONAL PARENTHESIS & AUTOLOAD SHIELD ]
            # Ruby methods do not require parentheses (e.g., `require 'json'` vs `require('json')`).
            # Additionally, `autoload` takes a symbol before the path (e.g., `autoload :MyMod, 'path'`).
            # By injecting `[^'\"]*` between the keyword and the string delimiter, the engine
            # safely bridges across optional parentheses, whitespace, and `autoload` symbol arguments
            # to securely capture the target string.
            # =====================================================================
            r"\b(?:require|require_relative|load|autoload)\b[ \t\n(]*(?:['\"]([^'\"]+)['\"]|%[qQwW]\W([^ \t\n\W]+)\W)|\b(?:include|extend)\b[ \t\n(]+([^\W\d]\w*(?:::[^\W\d]\w*)*)",
            re.M,
        ),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(r"#\s*(?:Author|Created by|Maintainer|Copyright):\s+(.*)", re.I),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure (Spec / Audit Traceability)
        # BUG FIX (Rule 14, #713): adjacent unbounded quantifiers with
        # overlapping character sets (`\d+` next to `[^\]]*`) -- the
        # same ReDoS shape already found and fixed independently in
        # embedded_python, css, tcl, matlab, scheme, typescript, rust, c,
        # cpp, csharp, groovy, shell, and sqlite earlier in this epic.
        # Bounded both quantifiers.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        # 31. ssr_boundaries (Server-Side Rendering)
        "ssr_boundaries": re.compile(
            r"\b(ActionController::Base|ActionController::API|Sinatra::Base|Hanami::Action|respond_to|format\.html|format\.json)\b"
        ),
        # 32. events (Event Emitters / Pub-Sub)
        "events": re.compile(r"\b(Wisper|broadcast|subscribe|ActiveSupport::Notifications\.instrument|publish)\b"),
        # 33. dependency_injection (Dependency Injection / IoC)
        "dependency_injection": re.compile(r"\b(Dry::Container|Dry::AutoInject|include\s+Import|inject)\b"),
        # 34. macros (Preprocessor Directives / Macros)
        # Ruby DSL macros.
        "macros": re.compile(
            r"^[ \t]*(?:attr_accessor|attr_reader|attr_writer|scope|delegate)\b",
            re.M,
        ),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        "pointers": re.compile(r"\b(FFI::Pointer|Fiddle::Pointer|Fiddle::Function)\b"),
        # 36. memory_alloc (Manual Memory Management)
        "memory_alloc": re.compile(r"\b(ObjectSpace|GC\.start|GC\.disable|GC\.enable|FFI::MemoryPointer)\b"),
        # 37. inline_asm
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(
            r"\b(?:Rails\.logger|Logger\.new|SemanticLogger|[a-zA-Z_]\w*logger)\.(?:debug|info|warn|error|fatal|unknown)\b"
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        "debug_prints": re.compile(r"\b(puts|print|p|pp|warn)\b"),
        # # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": re.compile(r"\b(Integer|Float|String|Array|Hash|Complex|Rational)\b\s*\("),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        # BUG FIX: `exit!` ends on `!` (non-word), so the shared
        # trailing \b could never fire -- unlike high_risk_execution's
        # copy of this same alternative (which is harmlessly masked by
        # its own bare `exit` alternative), there's no bare `exit` here
        # to save it. Never matched.
        "panics_and_aborts": re.compile(r"\b(?:raise|fail|abort)\b|\bexit!"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\bsleep\b\s*[0-9.]+"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"\^|(?<![=!])~"),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\b(mutex|lock|synchronized|Semaphore|Monitor|Atomic[A-Z]\w*)\b", re.I),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\b(freeze|frozen_string_literal|immutable)\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"\b(close|GC\.start|dispose|shutdown|cleanup)\b\s*\("),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # Visibility modifiers in Ruby.
        "encapsulation": re.compile(r"\b(private|protected)\b"),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"\.subscribe\(|\.on\(|addEventListener"),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"\b(skip|xit|xdescribe|mock|stub|double)\b"),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Ruby Specifics) ---
        "serialization_parsing": re.compile(r"\b(JSON\.parse|YAML\.load|Marshal\.load|Nokogiri::(?:XML|HTML))\b"),
        "regex_execution": re.compile(r"\b(Regexp\.new)\b|\.(match|scan|gsub|sub)\b|=~"),
        "time_date_logic": re.compile(r"\b(Time\.now|Date\.today|DateTime\.now|sleep)\b"),
        # BUG FIX: `system\s*\(` ends on `(` and `%x\{` both starts and
        # ends on non-word characters (`%` / `{`) -- the shared \b
        # boundaries could never fire for either. Neither ever matched.
        "ipc_rpc_bridges": re.compile(r"\b(?:Open3|IO\.popen|Net::HTTP|TCPSocket)\b|\bsystem\s*\(|%x\{"),
    },
}
