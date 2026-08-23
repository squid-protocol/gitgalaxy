from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
import sys
import glob

rules = LANGUAGE_DEFINITIONS["jcl"]["rules"]

for path in glob.glob("../language-crucible/data/jcl/**/*.jcl", recursive=True):
    print(f"\n--- {path} ---")
    text = open(path, encoding="utf-8", errors="replace").read()
    for rule_name in ["class_start", "func_start", "args"]:
        print(f"  {rule_name}:")
        count = 0
        for m in rules[rule_name].finditer(text):
            line_no = text[: m.start()].count("\n") + 1
            print(f"    Line {line_no}: {m.group(0).strip()} -> {m.groups()}")
            count += 1
        print(f"    Total: {count}")
