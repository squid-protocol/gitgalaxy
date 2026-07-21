import pytest
import re
import math
import logging
from unittest.mock import patch

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
            "func_start": re.compile(
                r"^[ \t]*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", re.M
            ),
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
            "func_start": re.compile(
                r"^[ \t]*\w+\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{", re.M
            ),
            "memory_scraping": re.compile(r"\b(memcpy|VirtualRead)\b"),
            "exfiltration_camouflage": re.compile(r"\b(send|socket)\b"),
            "high_risk_execution": re.compile(r"\b(strcpy|gets)\b"),
            "safety": re.compile(r"\b(strncpy|fgets)\b"),
            "sec_high_risk_execution": re.compile(r"system"),
            "sec_io": re.compile(r"request_get"),
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
}


# ==============================================================================
# TEST 1: ALGORITHMIC PHYSICS (Big-O & Recursion)
# ==============================================================================
def test_detector_big_o_and_recursion():
    """
    Proves the engine accurately calculates nesting depth based on indentation,
    and flags exponential O(2^N) recursion without building an AST.
    """
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = (
        "def calculate_fibonacci(n):\n"
        "    if n <= 1:\n"
        "        return n\n"
        "    for i in range(10):\n"  # Indent Level 1
        "        if i == 5:\n"  # Indent Level 2
        "            print(i)\n"  # Indent Level 3 (Deepest)
        "    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)\n"
    )

    result = opt_detector.splice(code, "")
    assert len(result["functions"]) == 1

    func = result["functions"][0]
    assert func["name"] == "calculate_fibonacci"
    assert func["is_recursive"] is True, "Failed to flag recursive execution!"
    assert func["big_o_depth"] >= 3, "Failed to calculate Big-O nesting depth!"


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
    assert result["equations"]["memory_scraping"] >= 100, (
        "Spatial correlation failed to multiply the threat penalty!"
    )
    assert result["mitigation_telemetry"]["amplified_leaks"] == 1, (
        "Failed to log the active leak mitigation stat!"
    )


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
    assert result["equations"]["high_risk_execution"] == 0, (
        "Silencer region failed to dampen the danger signal!"
    )
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
    assert result["functions"][0]["coding_loc"] == 3, (
        "Anti-ReDoS shield destroyed the physical line count!"
    )


# ==============================================================================
# TEST 4: MODE E (TERMINATOR CLEAVING)
# ==============================================================================
def test_detector_terminator_cleaving():
    """
    Proves Mode E correctly chops SQL payloads by terminators (;) rather than
    braces or indentation scopes.
    """
    opt_detector = StructuralExtractor("sql", MOCK_LANG_DEFS)
    code = (
        "SELECT * FROM users\n"
        "WHERE active = 1;\n"
        "\n"
        "UPDATE audit_log\n"
        "SET viewed = 1\n"
        "WHERE id = 55;\n"
    )

    # Mode E requires specific handshake routing inside the engine
    with patch(
        "gitgalaxy.core.detector.ScopeParsingRegistry.get_mode", return_value="mode_e"
    ):
        result = opt_detector.splice(code, "")

        assert len(result["functions"]) >= 2, (
            "Mode E failed to cleave the file into distinct blocks!"
        )

        func_names = [f["name"] for f in result["functions"]]
        assert any("SELECT" in name for name in func_names), (
            "Failed to ignite the SELECT block!"
        )
        assert any("UPDATE" in name for name in func_names), (
            "Failed to ignite the UPDATE block!"
        )


def test_detector_class_extraction_and_lcom():
    """
    Proves the engine accurately bounds OOP entities, links internal methods,
    and calculates LCOM/State Entanglement without full AST parsing.
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
    assert cls["method_count"] == 2, (
        "Failed to spatially link methods to the parent class!"
    )
    assert cls["lcom_score"] < 100.0, "LCOM calculation failed or defaulted to 100!"
    assert cls["state_entanglement"] > 0.0, (
        "State entanglement failed to register mutations!"
    )


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

    assert "def fake_function_inside_string" not in safe_code, (
        "Shield failed to mask heredoc contents!"
    )
    assert safe_code.count("\n") == code.count("\n"), (
        "Shield altered the physical line count!"
    )


def test_detector_orphan_and_duplicate_logic():
    """
    Proves the engine accurately identifies uncalled (orphan) functions
    and duplicated function definitions within a single file.
    """
    opt_detector = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = (
        "def active_helper():\n"
        "    return True\n"
        "\n"
        "def forgotten_orphan():\n"
        "    pass\n"
        "\n"
        "def main_process():\n"
        "    if active_helper():\n"
        "        print('Running')\n"
    )

    result = opt_detector.splice(code, "")

    # active_helper is used, forgotten_orphan is not, main_process is the entry point
    orphans = [f["name"] for f in result["functions"] if f.get("usage_status") == 1]

    assert "forgotten_orphan" in orphans, (
        "Failed to flag the unused function as an orphan!"
    )
    assert "active_helper" not in orphans, (
        "Falsely flagged an active function as an orphan!"
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
    assert result["equations"]["high_risk_execution"] == 0, (
        "Failed to scrub dead preprocessor branches!"
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

    assert len(result["functions"]) == 1, (
        "Failed to extract the shell function as a single block!"
    )

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

    assert len(result["functions"]) == 2, (
        "Inline modifiers corrupted the stack depth and swallowed the file!"
    )

    names = [f["name"] for f in result["functions"]]
    assert "calculate_risk" in names
    assert "secondary_process" in names


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

    assert len(result["functions"]) == 2, (
        "Mode C failed to separate Python functions by indentation!"
    )

    parent = result["functions"][0]
    assert parent["name"] == "parent_process"
    assert parent["loc"] == 4, (
        "Mode C failed to accurately count lines inside the indentation block!"
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
    code = (
        "INIT_SYSTEM:\n"
        "    MOV EAX, 1\n"
        "    PUSH EAX\n"
        "    CALL SETUP\n"
        "ERROR_HANDLER:\n"
        "    POP EAX\n"
        "    RET\n"
    )

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
    code = (
        "def save_user_data(user_id):\n"
        "    validate_id(user_id)\n"
        "    db_insert(user_id)\n"
        "    return True\n"
    )

    result = opt_detector.splice(code, "")
    func = result["functions"][0]

    assert "validate_id" in func["calls_out_to"], (
        "Failed to extract Level 3 outbound calls!"
    )
    assert "db_insert" in func["calls_out_to"], (
        "Failed to extract Level 3 outbound calls!"
    )
    assert func["type_id"] == "mutation", (
        "Failed to classify 'save_user_data' as a mutation!"
    )


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

    comment_stream = (
        "# Architect: Ada Lovelace\n# Purpose: Handles core cryptographic operations.\n"
    )

    # We must pass raw_content to allow the Ghost Tether to search coordinates
    result = opt_detector.splice(code, comment_stream, raw_content=code)

    # Check File Metadata
    assert result["metadata"]["ownership"] == "Ada Lovelace", (
        "Failed to decode ownership from comment stream!"
    )
    assert "cryptographic operations" in result["metadata"]["purpose"], (
        "Failed to decode purpose from comment stream!"
    )

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
    assert (
        opt_detector._extract_name("- (void)initWithObjects:(NSArray *)objects {")
        == "initWithObjects"
    )
    assert opt_detector._extract_name("+ (instancetype)sharedInstance;") == "sharedInstance"

    # C++ Operators
    assert (
        opt_detector._extract_name("MyClass::operator<<(std::ostream& os)") == "operator<<"
    )
    assert opt_detector._extract_name("operator bool() const") == "operator bool"
    assert opt_detector._extract_name("operator()()") == "operator()"

    # C++ Macros
    assert opt_detector._extract_name("BOOST_AUTO_TEST_CASE(MyTestName)") == "MyTestName"
    assert opt_detector._extract_name("TEST_F(MySuite, MyGTestName)") == "MySuite"


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

    # 1. RCE Weaponization: sec_danger spatially overlapping with sec_io
    assert eqs.get("sec_tainted_injection", 0) >= 1, (
        "Failed to spatially correlate Tainted RCE Injection!"
    )

    # 2. Race Conditions: concurrency overlapping with unlocked flux (multiplies by 5)
    assert eqs.get("concurrency", 0) >= 5, (
        "Failed to detect and amplify the Race Condition penalty!"
    )
    assert mits.get("amplified_race_conditions", 0) >= 1, (
        "Failed to log the Race Condition telemetry!"
    )

    # 3. Memory Leaks: unmitigated alloc
    assert eqs.get("memory_alloc", 0) >= 1, (
        "Failed to flag the unmitigated Memory Leak!"
    )


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
        assert result["equations"] == {}, (
            "Fallback did not return an empty equations dict!"
        )
        assert result["logic_density"] == 0.0, (
            "Fallback did not zero out logic density!"
        )
        assert result["metadata"]["ownership"] == "Joe", (
            "Fallback destroyed the Ghost Mass metadata!"
        )

    # 2. TimeoutError -> Hardware Guillotine drops cleanly
    with patch.object(
        opt_detector,
        "_partition_segments",
        side_effect=TimeoutError("Hardware thread timeout exceeded"),
    ):
        with pytest.raises(TimeoutError):
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
    assert distance > footprint * 1.5, (
        "Ray-Caster failed! Massive constellations are overlapping in 3D space."
    )


# ==============================================================================
# TEST 13: THE PROSE & SINGULARITY BYPASS
# ==============================================================================
@pytest.mark.smoke
def test_detector_prose_and_empty_bypass():
    """Proves the engine gracefully aborts on Markdown, low confidence, or empty streams."""
    opt_detector = StructuralExtractor("markdown", MOCK_LANG_DEFS)

    # 1. Prose/Confidence Bypass
    res_prose = opt_detector.splice("## Header", "comment", confidence=0.40)
    assert res_prose["logic_density"] == 0.0, (
        "Prose bypass failed to abort on low confidence!"
    )

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
    assert types.get("handle_click_event") == "event", (
        "Failed to classify 'handle' as event!"
    )
    assert types.get("parse_raw_text") == "logic", (
        "Failed to classify 'parse' as logic!"
    )
    assert types.get("is_valid_user") == "check", "Failed to classify 'is_' as check!"
    assert types.get("test_identity") == "verification", (
        "Failed to classify 'test' as verification!"
    )
    assert types.get("generate_uuid") == "standard", (
        "Failed to fallback to standard taxonomy!"
    )


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
    assert res["financial_read_cost"] is None, (
        "Fallback failed to neutralize financial cost!"
    )


# ==============================================================================
# TEST 17: MODE E (EXOTIC TERMINATOR CLEAVING)
# ==============================================================================
def test_detector_mode_e_erlang_cleaving():
    """Proves Mode E correctly chops Erlang/Prolog using terminators (.) instead of braces."""
    # Inject temporary Erlang config into the mock
    MOCK_LANG_DEFS["erlang"] = {
        "lexical_family": "c_style_comment",
        "rules": {
            "func_start": re.compile(r"^[a-z_][a-zA-Z0-9_]*\s*(?:\(|->)", re.M)
        }
    }
    opt_detector = StructuralExtractor("erlang", MOCK_LANG_DEFS)
    code = (
        "server_loop() ->\n"
        "    receive\n"
        "        msg -> ok\n"
        "    end.\n"
        "\n"
        "shutdown() ->\n"
        "    halt.\n"
    )
    
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
    
    code = (
        "def malicious_funnel(user_input):\n"
        "    eval(user_input)\n"
    )
    result = opt_detector.splice(code, "")
    
    # A single hit is multiplied by 50 in the spatial correlation matrix
    assert result["equations"].get("rce_funnel", 0) >= 50, (
        "AppSec Sensor failed to amplify the RCE Funnel penalty!"
    )


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
    """Proves Mode B correctly swaps from {} to () for Lisp/Scheme/Clojure languages."""
    MOCK_LANG_DEFS["lisp"] = {
        "lexical_family": "lisp_style",
        "rules": {
            "func_start": re.compile(r"^\s*\(\s*defun\s+([a-zA-Z0-9_.-]+)", re.M)
        }
    }
    opt_detector = StructuralExtractor("lisp", MOCK_LANG_DEFS)
    code = (
        "(defun calculate-total (x y)\n"
        "  (+ x y))\n"
        "\n"
        "(defun isolate-logic ()\n"
        "  (print 'done'))\n"
    )
    
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

    comment_stream = (
        "# TODO: Refactor this entire class\n"
        "# def old_abandoned_function():\n"
        "#     pass\n"
    )
    
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
    code = (
        "def fetch_data():\n"
        "    # @gal_type: cryptography\n"
        "    return encrypt(data)\n"
    )
    
    result = opt_detector.splice(code, "")
    func = result["functions"][0]
    
    # 'fetch' normally classifies as 'io', but the tag should force it to 'cryptography'
    assert func["type_id"] == "cryptography", "Failed to apply explicit @gal_type override!"


# ==============================================================================
# TEST 23: APPSEC ACTIVE HEMORRHAGE SENSOR
# ==============================================================================
def test_detector_active_hemorrhage_leak():
    """Proves the AppSec sensor detects secrets being passed to outbound logging/print streams."""
    opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS)
    
    # Inject rules for the hemorrhage sensor
    opt_detector.primary_rules["sec_hardcoded_secrets"] = re.compile(r"password")
    opt_detector.primary_rules["telemetry"] = re.compile(r"console\.log|printf")

    code = (
        "void log_credentials() {\n"
        "    char* password = 'super_secret'; // Trigger: sec_private_info\n"  # gitleaks:allow
        "    printf(password);                // Trigger: telemetry (sink)\n"
        "}\n"
    )
    
    result = opt_detector.splice(code, "")
    
    # A single private_info hit is multiplied by 50 when correlated with a telemetry sink
    assert result["equations"].get("sec_hardcoded_secrets", 0) >= 50, (
        "AppSec Sensor failed to amplify the Active Hemorrhage penalty!"
    )
    assert result["mitigation_telemetry"].get("amplified_leaks", 0) >= 1, (
        "Failed to log the active hemorrhage telemetry!"
    )

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
    assert "MyBaseClass" in result["metadata"].get("parent_entity", ""), (
        "Failed to extract class inheritance lineage!"
    )
    
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
        "        printf(\"Unbalanced brace!\"); \\\n"
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
    ruby_code = (
        "puts 'This is global dust'\n"
        "def standard_func\n"
        "    x = 1\n"
        "end\n"
        "puts 'This is trailing dust'\n"
    )
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
    assert any("[Unterminated]" in n for n in names_sql), (
        "Mode E failed to rescue an unterminated SQL block!"
    )


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
        "# Purpose:\n"
        "# This is line 1 of the purpose.\n"
        "# This is line 2.\n"
        "# ---\n"
        "# Some other ignored comment.\n"
    )
    
    meta = opt_detector._decode_comment_stream(comment_stream)
    
    assert "line 1" in meta.get("purpose", ""), "Failed to read block metadata!"
    assert "line 2" in meta.get("purpose", ""), "Failed to continue reading block metadata!"
    assert "ignored" not in meta.get("purpose", ""), "Failed to stop at the boundary marker!"


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
        "rules": {
            "func_start": re.compile(r"function\s+([a-zA-Z0-9_]+)\s*\("),
            "branch": re.compile(r"\bif\b")
        }
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
        "rules": {
            "rogue_unregistered_rule": re.compile(r"alien_syntax")
        }
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
        "    void* ptr = malloc(100);\n" # Trigger memory_alloc, but no free()
        "}\n"
    )
    result = opt.splice(code, "")
    
    # Verify the memory leak is registered and NOT mitigated
    assert result["equations"].get("memory_alloc", 0) == 1, "Failed to flag unmitigated memory allocation!"
    assert result["mitigation_telemetry"].get("mitigated_memory_allocs", 0) == 0, "Falsely mitigated a true memory leak!"
    
# ==============================================================================
# TEST 40: GHOST TETHER - HARVEST BELOW (PYTHON DOCSTRINGS)
# ==============================================================================
def test_detector_harvest_below_docstrings():
    """Proves the Ghost Tether correctly harvests comments sitting BELOW the definition (Python)."""
    opt = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = (
        "def process_data():\n"
        "    '''\n"
        "    This is a python docstring below the def.\n"
        "    '''\n"
        "    pass\n"
    )
    result = opt.splice(code, "", raw_content=code)

    assert len(result["functions"]) == 1
    docstring = result["functions"][0]["docstring"]
    assert "docstring below the def" in docstring, (
        "Ghost Tether failed to harvest docstrings below the function!"
    )
    # Regression guard for #246: the bare closing "'''" was previously
    # misclassified as an opening marker, letting the scan run past it
    # and swallow subsequent code into the docstring field.
    assert "pass" not in docstring, (
        "Docstring extraction ran past the closing delimiter and swallowed code!"
    )


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
                
        with patch("gitgalaxy.core.detector.ENCODER", MockEncoder()):
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
        "def safe_func():\n"               # Line 1
        "    pass\n"                       # Line 2
        "\n"                               # Line 3
        "def bad_func():\n"                # Line 4
        "    x = 'password'\n"             # Line 5 (sec_hardcoded_secrets)
        "    eval(x)\n"                    # Line 6 (high_risk_execution)
    )
    
    # Manually run coding analysis
    segments = [("python", code, 0)]
    counts, mitigations, spatial_maps, parents, threat_locations = opt_detector.coding_analysis(segments)
    
    # Verify the exact line numbers were captured
    assert "sec_hardcoded_secrets" in threat_locations, "Failed to map threat location!"
    assert threat_locations["sec_hardcoded_secrets"][0] == 5, f"Expected line 5, got {threat_locations['sec_hardcoded_secrets'][0]}"
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
    code = (
        "def foo():\n"
        '    """\n'
        "    Summary line.\n"
        '    """\n'
        "    return 1\n"
    )
    result = opt.splice(code, "", raw_content=code)

    docstring = result["functions"][0]["docstring"]
    assert "Summary line." in docstring
    assert "return 1" not in docstring, (
        "Docstring extraction swallowed the function body past the closing delimiter!"
    )


def test_detector_single_line_docstring_still_terminates_correctly():
    """
    Regression guard for #246: confirms the len(nxt) > 3 single-line-docstring
    check still works correctly under the refactored state tracking — a
    docstring that opens AND closes on the same line must stop immediately
    and not bleed into the next line.
    """
    opt = StructuralExtractor("python", MOCK_LANG_DEFS)
    code = (
        "def bar():\n"
        '    """Summary on one line."""\n'
        "    return 2\n"
    )
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
    code = (
        "# Architect: Ada Lovelace\n"
        "def baz():\n"
        '    """\n'
        "    Summary line.\n"
        '    """\n'
        "    return 3\n"
    )
    result = opt.splice(code, "", raw_content=code)

    docstring = result["functions"][0]["docstring"]
    assert "Summary line." in docstring
    assert "return 3" not in docstring, (
        "Pre-existing 'harvest above' content contaminated the below-docstring scan!"
    )