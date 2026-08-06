import ast
import os
import glob
import time
import sys

# Ensure gitgalaxy module is resolvable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

DEFAULT_SIZES = [2000, 4000, 8000, 16000, 32000, 64000, 128000]

def _eval_node_with_n(node, n):
    """
    Evaluates an AST node representing an assert_redos_immune payload expression,
    injecting the provided size `n` in place of the hardcoded multiplier.
    Handles basic string arithmetic like `"prefix" + "a" * 100000 + "suffix"`.
    """
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add):
            return str(_eval_node_with_n(node.left, n)) + str(_eval_node_with_n(node.right, n))
        elif isinstance(node.op, ast.Mult):
            left = _eval_node_with_n(node.left, n)
            right = _eval_node_with_n(node.right, n)
            if isinstance(left, str) and isinstance(right, int): return left * n
            if isinstance(left, int) and isinstance(right, str): return right * n
    raise ValueError(f"Unsupported node type in payload generation: {type(node)}")

def run_sweep(sizes=DEFAULT_SIZES):
    """
    Scans all `test_*_strict.py` files to dynamically extract and evaluate every
    `assert_redos_immune` payload at geometrically scaling boundaries. This proves
    whether a rule with a 1.0s timeout is actually safe, or if it is masking a 
    hidden O(n^2) backtracking vulnerability.
    """
    vuln_count = 0
    total_tested = 0
    
    file_to_lang = {
        'test_objectivec_strict.py': 'objective-c',
        'test_embedded_python_strict.py': 'embedded_python',
    }
    
    pattern_files = glob.glob("tests/extraction/languages/test_*_strict.py")
    
    for filepath in pattern_files:
        filename = os.path.basename(filepath)
        lang = file_to_lang.get(filename, filename.split('_')[1] if '_' in filename else None)
            
        if not lang or lang not in LANGUAGE_DEFINITIONS:
            continue
            
        with open(filepath, 'r') as f:
            try:
                tree = ast.parse(f.read())
            except Exception:
                continue
            
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'assert_redos_immune':
                try:
                    if len(node.args) < 2: continue
                    rule_node = node.args[0]
                    rule_key = rule_node.slice.value if isinstance(rule_node, ast.Subscript) else getattr(rule_node, 'id', None)
                    if not rule_key or rule_key not in LANGUAGE_DEFINITIONS[lang]['rules']: continue
                    
                    pattern = LANGUAGE_DEFINITIONS[lang]['rules'][rule_key]
                    if not pattern: continue
                    
                    durations = []
                    for n in sizes:
                        payload = _eval_node_with_n(node.args[1], n)
                        start = time.perf_counter()
                        pattern.search(payload)
                        durations.append(time.perf_counter() - start)
                    
                    ratios = [durations[i] / durations[i-1] for i in range(1, len(durations)) if durations[i-1] > 0.0001]
                    total_tested += 1
                    
                    if ratios:
                        max_ratio = max(ratios)
                        # A real O(n^2) backtracking bug will consistently show ~4.0x per doubling.
                        # We also require durations[-1] to be strictly > 0.05s to filter out OS scheduling noise.
                        if max_ratio >= 3.5 and durations[-1] > 0.05:
                            print(f"[VULNERABLE] {lang}.{rule_key}: {max_ratio:.2f}x max ratio | {durations[-1]:.4f}s at N={sizes[-1]} | Ratios: {[f'{r:.1f}x' for r in ratios]}")
                            vuln_count += 1
                except Exception:
                    # Ignore payloads that are too complex to be evaluated by this basic AST scraper
                    pass

    print(f"\nReDoS Geometric Sweep Complete.")
    print(f"Tested {total_tested} rules across {len(pattern_files)} test files.")
    print(f"Found {vuln_count} true O(n^2) scaling vulnerabilities.")

if __name__ == '__main__':
    run_sweep()
