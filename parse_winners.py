import json
import glob
import os

langs_won = []
langs_tied = []

for filepath in glob.glob("tests/tri_comparison_baseline_*.json"):
    lang = os.path.basename(filepath).replace("tri_comparison_baseline_", "").replace(".json", "")
    with open(filepath) as f:
        data = json.load(f)
    
    # We want to check if gitgalaxy is the winner in func_precision or class_precision or args
    # But the baseline JSON just stores the precision numbers, maybe?
    # Let's just print one to see what it contains
    print(lang, data.get("func_precision"), data.get("class_precision"))
    break
