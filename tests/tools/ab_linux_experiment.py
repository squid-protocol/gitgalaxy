import json
import re

from gitgalaxy.core.detector import StructuralExtractor


def run_experiment():
    # Mock C function with comments, SQL strings, and real calls
    test_block = """
void mock_kernel_function() {
    // We need to call spin_lock() here before proceeding
    kfree(ptr);
    const char* query = "SELECT * FROM users WHERE ID IN (1, 2, 3)";
    /*
       Don't forget to run init_module() !
    */
    kmalloc(size, GFP_KERNEL);

    char* log_msg = "Failed to open(file)";
    do_something();
}
"""
    print("=== AST-Free A/B Experiment ===")

    # 1. Simulate the Old Method (Raw block, [:20])
    invocation_pattern = re.compile(r"\b([a-zA-Z_]\w*)\s*\(")
    old_raw_calls = invocation_pattern.findall(test_block)
    # The old method was truncated at 20, but we just want to see the false positives
    old_calls_out = list(dict.fromkeys(old_raw_calls))

    print("\n[OLD METHOD] Un-shielded Regex (Captures strings/comments):")
    print(old_calls_out)

    # 2. Simulate the New Method (Shielded block)
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
    splicer = StructuralExtractor(lang_id="c", language_definitions=LANGUAGE_DEFINITIONS)
    safe_block = splicer._apply_literal_shield(test_block, "c")
    new_raw_calls = invocation_pattern.findall(safe_block)
    new_calls_out = list(dict.fromkeys(new_raw_calls))

    print("\n[NEW METHOD] Shielded Regex:")
    print(new_calls_out)

    print("\n[METRICS]")
    print(f"False Positives Eliminated: {len(old_calls_out) - len(new_calls_out)}")
    print(f"Old JSON Size: {len(json.dumps(old_calls_out))} bytes")
    print(f"New JSON Size: {len(json.dumps(new_calls_out))} bytes")

if __name__ == "__main__":
    run_experiment()
