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
        "target_version": "Perl 5.42.0 (Corinna Native OOP, Signatures, Try/Catch, Defer)",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard scripts, modules, tests, POD docs, and legacy CGI web scripts.
    "extensions": [".pl", ".pm", ".t", ".pod", ".plx", ".cgi", ".al", ".ph"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Core build scripts that are purely executed Perl code.
    "exact_matches": ["Makefile.PL", "Build.PL"],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions and CPAN metadata to resolve .pl (Prolog collision) and .t.
    "discriminators": [
        ".pm",
        ".pod",
        ".pl",
        "cpanfile",
        "cpanfile.snapshot",
        "META.json",
        "META.yml",
    ],
    # EXECUTION SIGNATURES: Interpreters found on Line 1.
    "shebangs": ["perl", "perl5", "perl6"],
    # UPGRADED: Maps to Family 6 (Polyglot)
    # Rationale: Perl's interaction with POD documentation blocks (=head, =cut) and embedded regex makes it a true polyglot lexical engine.
    # #621: was "standard_block" (shared a regex with C-style languages,
    # got zero comment stripping -- standard_block never used the `#`
    # token). "line_exclusive" fixes the basic `#` line-comment case
    # (needed no new family at all -- line_exclusive's own delimiter
    # table already leads with `#`). The full "Polyglot" vision in the
    # rationale above -- POD blocks (=head/=cut) -- is NOT covered by
    # this; line_exclusive's real config has Ruby's =begin/=end but not
    # Perl's own POD markers. Known remaining gap, not fixed here.
    "lexical_family": "line_exclusive",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch: Decisions that split the flow. Includes modern try/catch/finally and defer.
        "branch": re.compile(
            r"\b(if|unless|elsif|else|while|until|for|foreach|given|when|next|last|redo|try|catch|finally|defer|goto|continue|default)\b|&&|\|\||//|\?|(?<!:):(?!:)"
        ),
        # 2. args: Parameters / Coupling. Captures modern signatures, traditional @_ unpacking, and shift.
        # #1209: parameter-list span wrapped in its own capture group in
        # the first two alternatives (was only reachable via group(0),
        # the whole match including the "sub"/"my" prefix) so detector.py's
        # counter isolates just the real parameter text -- the whole-match
        # fallback overcounted every zero/one-arg signature by +1 the same
        # way Python's did (#1199).
        # #1519: the bare `(\bshift\b)` alternative used to match ANY
        # occurrence of the word "shift" anywhere in the body -- including
        # `shift @other_queue`/`shift(@other_queue)`, which shifts a
        # DIFFERENT array, nothing to do with unpacking @_. Added a
        # negative lookahead excluding those explicit-argument forms
        # (bare `shift;`/`shift` and `my $x = shift;` both still match --
        # only an explicit `(`/`@` right after "shift" is excluded).
        # #1607 follow-up: also added a negative LOOKBEHIND excluding a
        # sigil (`$@%&`) immediately before "shift" -- without it, a local
        # variable literally NAMED `$shift` (a real, if thematically
        # ironic, idiom: e.g. exiftool's `ConvertDateTime` stores its
        # GlobalTimeShift option in `my $shift = ...`) false-matched on
        # every later bare reference to that variable (`if ($shift)`,
        # `$shift =~ ...`) as if each were its own real `shift` builtin
        # call unpacking @_ -- confirmed inflating that one function's
        # count from a real 2 to 8. `\b` alone doesn't exclude this: `$`
        # is a non-word character, so `\bshift\b` still matches the
        # "shift" substring inside `$shift` starting right after the `$`.
        # Named in `_args_findall_sum_groups` below alongside the
        # `my (...) = @_` group -- traditional Perl commonly unpacks args
        # across MULTIPLE statements (`my $class = shift;` for the
        # invocant, then later `my ($a, $b) = @_;` for the rest, or
        # several sequential `my $x = shift;` lines), and a single match
        # only ever sees the first one. `_args_findall_sum_groups` tells
        # detector.py's counter to re-scan the whole block and SUM every
        # matching statement's own contribution instead. A sub WITH a
        # real declared signature/prototype (group 2) is unaffected --
        # that always sits earlier in the text than any body-level idiom,
        # so ordinary leftmost-match search already prefers it.
        # Group 5: the OTHER extremely common "rest of the args" idiom --
        # `my @statuses = @_;`, a bare (parenless) array catching every
        # remaining positional arg after some have already been `shift`ed
        # off, e.g. `my $class = shift; my @statuses = @_;`. Distinct
        # from group 3's `my (...) = @_` (a fixed-size destructure) --
        # this is inherently variadic, so it contributes exactly 1 (a
        # single "rest" slot) via the same not-self-contained-parens
        # fallback every other non-tuple match in this sum already uses,
        # not a real element count.
        "args": re.compile(
            r"\b(?:sub|method)(\s+[a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)*)?\s*(\([^)]*\))"
            r"|\bmy\s*(\([^)]*\))\s*=\s*@_"
            r"|((?<![$@%&])\bshift\b(?!\s*[(@]))"
            r"|(\bmy\s+@\w+\s*=\s*@_\b)"
        ),
        "_args_findall_sum_groups": {3, 4, 5},
        # #1607: group 2 (the "sub/method (...)" capture) matches BOTH a real
        # modern named signature (`sub foo($a, $b)`) and a legacy bare-sigil
        # PROTOTYPE (`sub Options($$;@)`, `sub Get8u($$)`) -- the two are
        # syntactically indistinguishable from the regex alone (both are just
        # "(...)" after the sub/method keyword). detector.py uses this flag to
        # tell prototypes apart from real signatures at count time (no commas
        # ever appear in a prototype, by grammar, regardless of true arity) and
        # falls through to the same body-idiom scan (`_args_findall_sum_groups`)
        # already used for signature-less traditional subs, instead of trusting
        # a prototype's declaration for a count it can't actually give.
        "_args_prototype_groups": {2},
        # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries. EXCLUDES access modifiers and immutability.
        "structural_boundaries": re.compile(
            r"\b(my|our|state|local|field|class|role|package|sub|method|return|yield|use|require|undef|do|true|false|await)\b"
        ),
        # 4. func_start (Executable Logic Anchors)
        # Anchors executable logic blocks. MUST HAVE EXACTLY ONE CAPTURE GROUP for the name.
        #
        # LLM/MAINTAINER CONTEXT & DOMAIN KNOWLEDGE:
        # 1. THE KEYWORDS: Captures standard `sub` and Perl 5.38+ Corinna OOP `method`.
        # 2. THE CAPTURE: `([a-zA-Z_]\w*)` isolates the exact function name.
        # 3. THE LOOKAHEAD GUARDRAILS `(?= ... )`: Perl allows a lot of junk between the name and the code block.
        #    - `\(` : Safely steps over legacy Prototypes `sub foo ($$)` and modern Signatures `sub foo ($a, $b)`.
        #    - `:`  : Safely steps over Subroutine Attributes `sub foo : lvalue : method {`.
        #    - `\{` : Matches standard immediate block openings `sub foo {`.
        #    - `\n|$`: Handles K&R style newline brace placements.
        "func_start": re.compile(
            # =====================================================================
            # [ THE VERTICAL SUBROUTINE SHIELD (PERL) ]
            # Perl 5 (and modern Corinna OOP) allows newlines between the `sub`/`method`
            # keyword and the function name.
            # FIX: Exchanged `\s+` (which triggers ReDoS if unbounded) with a strictly
            # controlled `[ \t\n]+` to allow vertical jumps. Upgraded the trailing
            # lookahead to safely handle vertical gaps before the opening `{` or `(`.
            # =====================================================================
            r"^[ \t]*(?:sub|method)[ \t\n]+"
            r"([a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)*)"
            r"(?=[ \t\n]*(?::(?!:)|[\(\{]|$))",
            re.M,
        ),
        # 5. class_start: Object / Entity Declarations. Defines object-oriented and structural boundaries.
        "class_start": re.compile(
            r"^[ \t]*(?:package|class|role)\s+([a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)*)(?=[ \t\n]*[\d\.v_]*[ \t\n]*(?::(?!:)|[;\{]|$))",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety: Defensive Programming. Defensive constructs (strict, warnings, safe exceptions).
        # BUG FIX: `eval[ \t]*\{` was inside the shared \b(...)\b wrapper.
        # It ends on the literal `{` (non-word), so the trailing \b only
        # matched when a word character immediately followed the brace
        # (e.g. `eval{risky()}`) -- the far more common idiomatic style
        # with a space after `{` (`eval { risky(); }`) has a non-word
        # char (the space) right after the brace, so the boundary could
        # never fire and the whole safe-eval-block form silently never
        # matched. Also widened `[ \t]*` to `[ \t\n]*` to match perl's own
        # vertical func_start shield -- a vertically-placed opening brace
        # (`eval\n{`) is valid, if less common, style.
        "safety": re.compile(
            r"\b(?:use\s+strict|use\s+warnings|use\s+v5\.\d+|croak|confess|try|catch|finally|defer|isa|DOES)\b"
            r"|\beval[ \t\n]*\{|->isa\b|->DOES\b"
        ),
        # 7. safety_neg: Safety Bypasses. Actively bypassing safety (no strict, string eval).
        # BUG FIX: the whole alternation used to be wrapped in \b(...)\b.
        # `eval\s+(?!\w|{)` and `goto\s+\&` both end on a non-word
        # character by construction (the negative lookahead guarantees
        # the char after the trailing whitespace isn't \w, and `&` is
        # never a word char) -- so the shared trailing \b, which needs a
        # non-word/word transition, could never be satisfied. This
        # silently dropped the two most common dangerous idioms:
        # `eval $code;` / `eval($code);` (string-eval on a variable, not
        # a literal) and `goto &$sub;` (dynamic dispatch). Each
        # alternative now carries only the boundary that makes sense for
        # its own shape. Also added a dedicated `eval\s*\(` alternative
        # so the equally common no-space function-call form
        # `eval($code)` is caught alongside `eval $code` -- naively
        # widening the existing `eval\s+(?!\w|{)` to `eval\s*(?!\w|{)`
        # doesn't work here, since `\s*` can backtrack to zero-width and
        # let the lookahead be satisfied by the whitespace character
        # itself, re-admitting the safe `eval q{1}` / `eval { ... }`
        # bareword and block forms this guard exists to exclude.
        "safety_bypasses": re.compile(
            r'\b(?:no\s+strict|no\s+warnings)\b|\beval\s*["\']|\beval\s*\(|\beval\s+(?!\w|{)|\bgoto\s+&'
        ),
        # 8. danger: High-Risk Execution. Process killers and raw shell execution.
        "high_risk_execution": re.compile(r"\b(system|exec|exit|qx|CORE::dump)\b|`[^`]+`"),
        # 9. io: I/O & Network Boundaries. Disk, Network, DBI, and standard handles.
        "io": re.compile(
            r"\b(open|close|sysopen|sysread|syswrite|opendir|closedir|DBI->connect|Mojo::UserAgent|HTTP::Tiny|LWP::UserAgent|socket|connect|bind)\b|<[A-Z_0-9]+>|<>"
        ),
        # 10. api: Public Surface Area. Exposed surface area (Exports and modern routing).
        "api": re.compile(
            r'\b(?:get|post|put|del|any|patch)\s+[\'"]/[^\'"]*[\'"]|@(?:EXPORT|EXPORT_OK|EXPORT_TAGS|ISA)\b|use\s+(?:Exporter|parent|base)\b|:\s*(?:reader|writer|param)\b'
        ),
        # 11. flux: State Mutation. State mutation (assignments, array mutators, substitutions).
        # UPDATED: Removed '.=' and '=~' / '!~' to prevent massive string-builder false positives.
        "state_mutation": re.compile(
            r"\b(?:push|pop|shift|unshift|splice|delete)\b|[\$@%][a-zA-Z_]\w*(?:->|\[|\{){0,5}\s*(?:\+|-|\*|/|\||&|\^|%|x)?=(?!=)|(?:\+\+|--)|\bs/"
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural logic.
        "dead_code": re.compile(
            r"^[ \t]*#\s*(?:my|our|state|sub|method|class|package|if|unless|while|print|say)\b",
            re.M,
        ),
        # 13. doc: Structured Documentation. Structured POD documentation.
        "doc": re.compile(r"^=(?:pod|head[1-6]|item|over|back|cut|begin|end|encoding|for)\b", re.M),
        # 14. test: Testing & Assertions. Assertions and Test frameworks.
        "test": re.compile(
            r"\b(?:Test2::V0|Test::More|cmp_ok|is_deeply|subtest|done_testing|BAIL_OUT)\b|\b(?:ok|is|isnt|like|unlike|plan|diag|note)\s*\("
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency: Temporal Static. Async, forks, and threads.
        "concurrency": re.compile(
            r"\b(async|await|fork|waitpid|threads(?:->create)?|threads::shared|AnyEvent|Coro|Mojo::IOLoop|Mojo::Promise|Future|Parallel::ForkManager)\b"
        ),
        # 16. ui_framework: UI / View Components. GUI libraries and template engines.
        "ui_framework": re.compile(
            r"\b(Tk::|Wx::|Gtk2::|Gtk3::|Prima::|Template|HTML::Mason|Mojolicious::Plugin::TagHelpers)\b|\brender(?:_to_string)?\b|<%|%>|\[%|%\]"
        ),
        # 17. closures: Closures / Anonymous Functions. Anonymous subroutines.
        "closures": re.compile(r"\bsub\s*(?:\([^)]*\))?[ \t]*\{"),
        # 18. globals: Global / Shared State. Magic variables and system globals.
        # BUG FIX: `$$`, `$@`, `$!`, and `$?` were inside the shared
        # trailing \b group. Each ends on a symbolic, non-word character,
        # so the trailing \b (needed for the word-ending alternatives,
        # to stop `$a` from matching inside `$abc`) could only fire when
        # a word char immediately followed -- never true for how these
        # 4 special vars are actually written (`$$;`, `if ($@)`, `warn
        # $!;`, `$? >> 8`). All 4 of the most common Perl magic
        # variables silently never matched.
        "globals": re.compile(
            r"(?:\$a|\$b|\$_|\$0|%ENV|%SIG|@ARGV|@INC)\b|\$\$|\$@|\$!|\$\?|^[ \t]*our\s+[\$@%]",
            re.M,
        ),
        # 19. decorators: Decorators / Annotations. Subroutine and variable attributes.
        "decorators": re.compile(r":\s*[a-zA-Z_]\w*(?:\([^)]*\))?"),
        # 20. generics: Generics / Type Parameters. Parameterized types (via Type::Tiny/Moose).
        "generics": re.compile(r"\b(?:ArrayRef|HashRef|Map|Tuple|Dict|Maybe|InstanceOf|ConsumerOf|Enum)\[[^\]]*\]"),
        # 21. comprehensions: Iterators / Comprehensions. Map and Grep.
        "comprehensions": re.compile(r"\b(?:map|grep|reduce|any|all|none|notall|first|List::Util)\b"),
        # 22. scientific: Numerical / Compute Libraries. PDL and Math::BigInt.
        "scientific": re.compile(
            r"\b(Math::Trig|Math::BigInt|Math::BigFloat|Math::Complex|PDL|sin|cos|exp|log|sqrt|atan2|abs|int|rand|srand)\b"
        ),
        # 23. heat_triggers: Metaprogramming & Reflection. Metaprogramming and Symbol table hacks.
        "reflection_metaprogramming": re.compile(
            r"\b(AUTOLOAD|DESTROY|BEGIN|UNITCHECK|CHECK|INIT|END|tie|untie|bless|overload)\b|\*[a-zA-Z_]\w*[ \t]*=\s*(?:\\|&)|goto\s+&"
        ),
        # 24. import (Dependency Inclusions)
        "import": re.compile(r"\b(?:use|require|no)\s+[a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)*", re.M),
        "_dependency_capture": re.compile(
            # =====================================================================
            # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (PERL) ]
            # PURPOSE: Extracts external dependencies for the Network Graph and Firewall.
            #
            # HISTORICAL BUG: Anchored to `^[ \t]*`. While `use` is evaluated at
            # compile-time and is typically top-level, `require` is evaluated at
            # runtime and is very frequently scoped inside `if` statements or
            # subroutines to defer loading heavy modules. The line anchor blinded
            # the engine to these runtime inclusions.
            #
            # THE FIX: Stripped the `^` anchor and rely on the `\b` word boundary
            # to capture module loading anywhere in the execution path.
            # =====================================================================
            r"\b(?:use|require|no)\s+([a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)*)",
            re.M,
        ),
        # 25. ownership: Authorship metadata.
        "ownership": re.compile(
            r"^=head1\s+(?:AUTHOR|COPYRIGHT|LICENSE)|#\s*(?:Author|Maintainer|Created by):\s+([^\n]+)",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt: The Promise. Future work markers.
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure: Map vs. Territory. Audit tags.
        # BUG FIX (Rule 14, #713): adjacent unbounded quantifiers with
        # overlapping character sets (`\d+` next to `[^\]]*`) -- the
        # same ReDoS shape already found and fixed independently in
        # embedded_python, css, tcl, matlab, scheme, typescript, rust, c,
        # cpp, csharp, groovy, shell, and sqlite earlier in this epic.
        # Bounded both quantifiers.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        # 31. ssr_boundaries: View Horizon. Server-Side Rendering computation boundaries.
        "ssr_boundaries": re.compile(
            r"\b(Mojolicious::Controller|Dancer2|Catalyst::Controller|render|template|reply->|to_app)\b"
        ),
        # 32. events: Pub/Sub Network. Event-driven architecture signatures and message brokers.
        "events": re.compile(
            r'\b(?:emit|once|unsubscribe|catch|Mojo::EventEmitter|AnyEvent->condvar)\b|\b(?:on|subscribe)\s+[\'"]'
        ),
        # 33. dependency_injection: Inversion of Control. Inversion of Control (IoC) injection markers.
        "dependency_injection": re.compile(r"\b(Bread::Board|Beam::Wire|IOC|container|resolve|inject|service)\b"),
        # 34. macros: Preprocessor Hooks. Compiler pragmas or source filters.
        "macros": re.compile(
            r"\b(Filter::Simple|Filter::Util::Call|Devel::Declare|Keyword::Declare)\b|^[ \t]*BEGIN[ \t]*\{",
            re.M,
        ),
        # 35. pointers: Memory Map. Explicit tracking of memory addressing or references.
        # UPDATED: Removed '\\[$@%&*]\w+' to stop flagging standard pass-by-reference variables.
        "pointers": re.compile(r"->(?:\[[^\]]*\]|\{[^\}]*\})|@\$|%\$|\$\$|\&\$"),
        # 36. memory_alloc: Manual Memory Management. Explicit heap manipulations or reference count controls.
        "memory_alloc": re.compile(
            r"\b(Scalar::Util::weaken|Scalar::Util::isweak|Internals::SvREFCNT|Internals::SvREADONLY|undef|Devel::Peek)\b"
        ),
        # 37. inline_asm: Bare Metal. Direct architecture bridging via Inline modules.
        "inline_asm": re.compile(r'\buse\s+Inline\s+[\'"](?:C|CPP|ASM)[\'"]'),
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry: The Professional. Structured logging and observability frameworks.
        "telemetry": re.compile(
            r"\b(?:Log::Log4perl|Log::Any|Mojo::Log|log_(?:info|debug|warn|error|fatal))\b|->(?:debug|info|warn|error|fatal|trace)\b",
            re.I,
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs): The Amateur / Space Debris. Ad-hoc debug statements.
        "debug_prints": re.compile(r"\b(print|say|printf|sprintf|warn)\b"),
        # 40. explicit_casts (Explicit Type Casting): The "Trust Me" Tax. Explicitly bypassing the type-checker or manual blessing.
        # UPDATED: Removed the pointer/reference overlap.
        "explicit_casts": re.compile(r"\b(int|oct|hex|vec|ref|bless)\b"),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts): The Detonators. Forcefully destroying the current execution context.
        "panics_and_aborts": re.compile(r"\b(die|confess|croak|exit|BAIL_OUT)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) Forcing a thread to sleep or blocking waits.
        "thread_sleeps": re.compile(r"\bsleep\b"),
        # 43. bitwise_ops (Bitwise Operations) Manipulating raw bytes and memory registers.
        # UPDATED: Added negative lookbehinds '(?<![=!])~' to ignore Perl regex operators.
        "bitwise_ops": re.compile(r"(?<!&)&(?!&)|(?<!\|)\|(?!\|)|<<|>>|\^|(?<![=!])~"),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\b(lock|threads::shared|Thread::Semaphore)\b"),
        # 45. immutability_locks (Immutability Constraints) Explicitly locking data so it cannot be mutated.
        "immutability_locks": re.compile(r"\b(Readonly|Const::Fast|Internals::SvREADONLY)\b"),
        # 46. cleanup (Resource Cleanup / Teardown) Explicitly destroying state or releasing resources.
        "cleanup": re.compile(r"\b(DESTROY|undef|close|closedir|finish)\b|^[ \t]*END[ \t]*\{", re.M),
        # 47. encapsulation Explicitly hiding logic from the rest of the application.
        "encapsulation": re.compile(r"\b(my|state|local)\b|:private\b"),
        # 48. listeners (Event Listeners / Observers) Waiting to receive state from an external broadcast.
        # BUG FIX: `on\s*\(` and `subscribe\s*\(` both end in a literal
        # `(` (non-word), so the shared trailing \b could only fire when
        # a word char immediately followed -- never true for the most
        # common real call shape, `on('event', ...)`, where a quote
        # follows the paren. Both never matched at all.
        "listeners": re.compile(r"\bon\s*\(|\bsubscribe\s*\(|\badd_listener\b"),
        # 49. test_skip (Bypassed Tests / Ignored Specs) Code that bypasses test verification.
        "test_skip": re.compile(r"\b(skip|todo_skip)\b"),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Perl Specifics) ---
        "serialization_parsing": re.compile(
            r"\b(Storable::(?:thaw|fd_retrieve)|JSON::(?:decode_json|from_json)|YAML::(?:Load|LoadFile))\b"
        ),
        # BUG FIX: the trailing `\s*[/\W]` allowed the delimiter check to
        # be satisfied by an ordinary whitespace/punctuation character
        # that has nothing to do with a regex delimiter -- `\W` matches
        # ANY non-word char, including plain space. This meant an
        # ordinary bareword-named scalar (`$s`, `$m`, `$y`) followed by
        # any operator or even just a space (`$s = 5;`, `my $y = 1;`)
        # was misclassified as the `s///`/`m//`/`y///` operator. Dropped
        # `\s*` (real delimiter usage never has a space before the
        # opening delimiter) and narrowed the trailing class to actual
        # Perl regex delimiter punctuation, excluding whitespace and the
        # ordinary-code characters (`=`, `;`, `,`) that triggered the
        # false positive.
        "regex_execution": re.compile(
            r"(=~|!~|\b(?:qr|m|s|tr|y)\b[/{}\[\]()<>!|#~^])"
        ),  # Catches Perl's native binding operators and regex quotes
        "time_date_logic": re.compile(r"\b(localtime|gmtime|Time::HiRes|sleep|time)\b"),
        # BUG FIX: the whole alternation used to be wrapped in \b(...)\b.
        # \b requires a word/non-word transition; `system\s*\(` and
        # `exec\s*\(` both END in a literal `(` (non-word), so the
        # trailing \b could never match once the paren was followed by
        # anything else non-word (e.g. a string-literal quote or
        # variable sigil) -- meaning `system("ls")` and `exec("ls")`,
        # the two most common forms, never matched at all. Each
        # alternative now carries only the boundary that makes sense
        # for its own shape (leading \b for word-prefixed forms, none
        # for the punctuation-delimited backtick form).
        "ipc_rpc_bridges": re.compile(
            r"\bsystem\s*\(|\bexec\s*\(|\bfork\b|\bIPC::Open[23]\b|\bqx\b|`.*`"
        ),  # Backticks and qx// are shell executions
    },
}
